#!/usr/bin/env python3
"""Query official Lane and Marion County, Oregon parcel source components.

Lane County publishes assessor parcels and a last-three-years sales layer as
separate ArcGIS components.  The adapter keeps those records separate and
surfaces their account/map-taxlot join keys.  Marion County publishes a richer
parcel layer whose sale fields describe only the latest transfer coded as a
verified sale.

Usage:
    uv run python tools/query_oregon_lane_marion_parcels.py sources
    uv run python tools/query_oregon_lane_marion_parcels.py parcel \
        1501000000100 --source us-or-lane-county-assessor-parcels
    uv run python tools/query_oregon_lane_marion_parcels.py search \
        "KCK PARTNERS" --source us-or-marion-county-assessor-parcels \
        --field owner
    uv run python tools/query_oregon_lane_marion_parcels.py sale \
        2024-019914 --source us-or-lane-county-recent-property-sales
    uv run python tools/query_oregon_lane_marion_parcels.py probe --all
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args
    from tools.public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
        sha256_fingerprint,
    )
    from tools.public_records_http import (
        ArcGISRESTClient,
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        arcgis_declared_schema,
        failure_result,
        schema_fingerprint,
    )
    from tools.public_records_store import canonical_property_ref
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args
    from public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
        sha256_fingerprint,
    )
    from public_records_http import (
        ArcGISRESTClient,
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        arcgis_declared_schema,
        failure_result,
        schema_fingerprint,
    )
    from public_records_store import canonical_property_ref


STATE_CODE = "OR"
STATE_FIPS = "41"
LANE_GEOID = "41039"
MARION_GEOID = "41047"

LANE_PARCELS_SOURCE_ID = "us-or-lane-county-assessor-parcels"
LANE_SALES_SOURCE_ID = "us-or-lane-county-recent-property-sales"
MARION_PARCELS_SOURCE_ID = "us-or-marion-county-assessor-parcels"

LANE_SERVICE_URL = (
    "https://lcmaps.lanecounty.org/arcgis/rest/services/AT/AddressParcelSales/MapServer"
)
MARION_LAYER_URL = (
    "https://services3.arcgis.com/SXXjryU22GsO8OEC/ArcGIS/rest/services/"
    "Parcels/FeatureServer/0"
)

OUTPUT_SCHEMA_VERSION = "oregon-lane-marion-property-sources/1.0"
PROBE_SCHEMA_VERSION = "oregon-lane-marion-property-probe/1.0"
CURSOR_PREFIX = "oregon-lane-marion-property:v1:"
CURSOR_VERSION = 1


@dataclass(frozen=True)
class SearchColumn:
    """One source-native search column and its match behavior."""

    name: str
    contains: bool = False


@dataclass(frozen=True)
class SourceConfig:
    """Verified field, identity, and completeness contract for one layer."""

    source_id: str
    name: str
    layer_url: str
    service_item_id: str
    expected_layer_name: str
    publisher: str
    county_name: str
    county_geoid: str
    source_role: str
    record_kind: str
    object_id_field: str
    required_fields: tuple[str, ...]
    search_fields: Mapping[str, tuple[SearchColumn, ...]]
    native_id_fields: tuple[str, ...]
    max_page_size: int
    original_crs: str
    cadence_fact: str
    component_scope: str
    complement_keys: tuple[str, ...]
    warnings: tuple[str, ...]
    sentinel_field: str
    sentinel_value: str

    def source_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_id=self.source_id,
            name=self.name,
            source_role=self.source_role,
            base_url=self.layer_url,
            dataset_id=self.service_item_id,
            metadata={
                "publisher": self.publisher,
                "county_name": self.county_name,
                "county_geoid": self.county_geoid,
                "record_kind": self.record_kind,
                "component_scope": self.component_scope,
                "cadence_fact": self.cadence_fact,
                "original_crs": self.original_crs,
                "complement_keys": list(self.complement_keys),
            },
        )


LANE_PARCEL_FIELDS = (
    "OBJECTID",
    "RLID",
    "PROPACCT",
    "MAPTAXLOT",
    "MAPNUMBER",
    "TAXLOT",
    "ACCTNO",
    "OWNNAME",
    "ADDR1",
    "ADDR2",
    "ADDR3",
    "OWNERCITY",
    "OWNERPRVST",
    "OWNERZIP",
    "OWNERCNTRY",
    "MAPACRES",
    "GEOCITY",
    "UGB",
    "AscendAcres",
    "zoningdesc",
    "plandesdesc",
    "LastEditedDate",
    "EditType",
)

LANE_SALE_PREFIX = "SalesLayerCityJoin_SalesforGISLayerAll_"
LANE_SALE_FIELDS = (
    "OBJECTID",
    "SalesLayerCityJoin_district",
    "SalesLayerCityJoin_names",
    "SalesLayerCityJoin_inccityname",
    f"{LANE_SALE_PREFIX}account",
    f"{LANE_SALE_PREFIX}maplot",
    f"{LANE_SALE_PREFIX}deed_transfer_no",
    f"{LANE_SALE_PREFIX}property_class",
    f"{LANE_SALE_PREFIX}stat_class",
    f"{LANE_SALE_PREFIX}deed_type",
    f"{LANE_SALE_PREFIX}reject_code",
    f"{LANE_SALE_PREFIX}sale_price",
    f"{LANE_SALE_PREFIX}group_sale_desc",
    f"{LANE_SALE_PREFIX}situs_address",
    f"{LANE_SALE_PREFIX}city",
    f"{LANE_SALE_PREFIX}state",
    f"{LANE_SALE_PREFIX}zip",
    f"{LANE_SALE_PREFIX}IncorpArea",
    "dbo_rlid_neighborhood_neighborhood",
    "dbo_rlid_neighborhood_description",
    "DeedDate",
)

MARION_PARCEL_FIELDS = (
    "OBJECTID",
    "TAXLOT",
    "TAXACCT",
    "OTHERACCTS",
    "ALT_TAXLOT",
    "ALT_TAXACCT",
    "STREETNUM",
    "PRE_DIR",
    "STREETNAME",
    "STREETTYPE",
    "POST_DIR",
    "UNITNUM",
    "SITUS",
    "SITUSCSZ",
    "PLATNAME",
    "BLOCK",
    "LOT",
    "ACRES",
    "LASTUPDATE",
    "OWNERNAME",
    "OWNERADDR",
    "OWNERCSZ",
    "INSTNUM",
    "INSTTYPE",
    "INSTDATE",
    "SALEPRICE",
    "ZONECODE",
    "ZONEAUTH",
    "ZONEWEB",
    "YEARBUILT",
    "BLDGAREA",
    "PROPCLASS",
    "RMVLND",
    "RMVIMP",
    "RMVTOTAL",
    "ASSDVAL",
    "TAXCODE",
    "CITY",
    "SCHLDIST",
    "FIREDIST",
    "REFLINK",
    "MAPLINK",
    "X_COORD",
    "Y_COORD",
)

LANE_PARCELS = SourceConfig(
    source_id=LANE_PARCELS_SOURCE_ID,
    name="Lane County Assessor Parcels",
    layer_url=f"{LANE_SERVICE_URL}/2",
    service_item_id="e86ccb75b9524cb0a25cd60e64640352",
    expected_layer_name="Parcels",
    publisher="Lane County Assessment and Taxation",
    county_name="Lane County, Oregon",
    county_geoid=LANE_GEOID,
    source_role="county_assessor_parcel_owner_zoning_geometry",
    record_kind="parcel",
    object_id_field="OBJECTID",
    required_fields=LANE_PARCEL_FIELDS,
    search_fields={
        "parcel": (
            SearchColumn("MAPTAXLOT"),
            SearchColumn("RLID"),
            SearchColumn("MAPNUMBER"),
            SearchColumn("TAXLOT"),
        ),
        "account": (
            SearchColumn("PROPACCT"),
            SearchColumn("ACCTNO"),
        ),
        "owner": (SearchColumn("OWNNAME", contains=True),),
        "address": (
            SearchColumn("ADDR1", contains=True),
            SearchColumn("ADDR2", contains=True),
            SearchColumn("ADDR3", contains=True),
            SearchColumn("OWNERCITY", contains=True),
        ),
        "zoning": (
            SearchColumn("zoningdesc", contains=True),
            SearchColumn("plandesdesc", contains=True),
        ),
    },
    native_id_fields=("MAPTAXLOT", "RLID"),
    max_page_size=2_000,
    original_crs="EPSG:2914",
    cadence_fact="Layer description says assessor taxlots publish weekly.",
    component_scope=(
        "Current assessor parcel identity, owner/mailing, acreage, zoning, "
        "planning, and geometry; no assessment values or sale fields."
    ),
    complement_keys=("account", "map_taxlot"),
    warnings=(
        "Lane parcel records are a weekly-described assessor component.",
        "Lane recent sales are published in a separate last-three-years layer "
        "and are linked here only by account or map-taxlot.",
    ),
    sentinel_field="parcel",
    sentinel_value="1501000000100",
)

LANE_SALES = SourceConfig(
    source_id=LANE_SALES_SOURCE_ID,
    name="Lane County Property Sales (last 3 years)",
    layer_url=f"{LANE_SERVICE_URL}/1",
    service_item_id="e86ccb75b9524cb0a25cd60e64640352",
    expected_layer_name="Sales (last 3 years)",
    publisher="Lane County Assessment and Taxation",
    county_name="Lane County, Oregon",
    county_geoid=LANE_GEOID,
    source_role="county_assessor_recent_sale_analysis",
    record_kind="sale_reference",
    object_id_field="OBJECTID",
    required_fields=LANE_SALE_FIELDS,
    search_fields={
        "parcel": (SearchColumn(f"{LANE_SALE_PREFIX}maplot"),),
        "account": (SearchColumn(f"{LANE_SALE_PREFIX}account"),),
        "instrument": (SearchColumn(f"{LANE_SALE_PREFIX}deed_transfer_no"),),
        "address": (
            SearchColumn(f"{LANE_SALE_PREFIX}situs_address", contains=True),
            SearchColumn(f"{LANE_SALE_PREFIX}city", contains=True),
        ),
    },
    native_id_fields=(
        f"{LANE_SALE_PREFIX}deed_transfer_no",
        f"{LANE_SALE_PREFIX}account",
    ),
    max_page_size=2_000,
    original_crs="EPSG:2914",
    cadence_fact=("The official layer is explicitly labeled Sales (last 3 years)."),
    component_scope=(
        "Assessor sale-analysis rows for the last three years, including deed "
        "reference, reject code, price, situs, district, and neighborhood."
    ),
    complement_keys=("account", "map_taxlot"),
    warnings=(
        "The publisher labels this component as the last three years, so it is "
        "not a complete historical sale series.",
        "Deed numbers are recorder references; the layer does not include the "
        "recorded document image.",
    ),
    sentinel_field="account",
    sentinel_value="0057313",
)

MARION_PARCELS = SourceConfig(
    source_id=MARION_PARCELS_SOURCE_ID,
    name="Marion County Assessor Parcels",
    layer_url=MARION_LAYER_URL,
    service_item_id="bc90901732a4443bbfa1f949cc9cc205",
    expected_layer_name="Parcels",
    publisher="Marion County Assessor's Office",
    county_name="Marion County, Oregon",
    county_geoid=MARION_GEOID,
    source_role="county_assessor_parcel_owner_value_sale_reference_geometry",
    record_kind="parcel",
    object_id_field="OBJECTID",
    required_fields=MARION_PARCEL_FIELDS,
    search_fields={
        "parcel": (
            SearchColumn("TAXLOT"),
            SearchColumn("ALT_TAXLOT"),
        ),
        "account": (
            SearchColumn("TAXACCT"),
            SearchColumn("ALT_TAXACCT"),
            SearchColumn("OTHERACCTS", contains=True),
        ),
        "owner": (SearchColumn("OWNERNAME", contains=True),),
        "address": (
            SearchColumn("SITUS", contains=True),
            SearchColumn("SITUSCSZ", contains=True),
            SearchColumn("OWNERADDR", contains=True),
            SearchColumn("OWNERCSZ", contains=True),
        ),
        "instrument": (SearchColumn("INSTNUM"),),
        "zoning": (
            SearchColumn("ZONECODE", contains=True),
            SearchColumn("ZONEAUTH", contains=True),
        ),
    },
    native_id_fields=("TAXLOT", "ALT_TAXLOT"),
    max_page_size=2_000,
    original_crs="EPSG:2913",
    cadence_fact=(
        "ArcGIS metadata exposes a service data-edit timestamp; the linked "
        "Property Records application states that it updates every 24 hours."
    ),
    component_scope=(
        "Parcel, owner/mailing, assessment, zoning, improvement summary, "
        "districts, links, geometry, and latest verified-sale reference."
    ),
    complement_keys=("account", "taxlot", "instrument"),
    warnings=(
        "Marion sale fields describe the most recent transfer coded as a "
        "verified sale, not a complete sale history.",
        "The official Property Records application and annual sales downloads "
        "provide complementary current and historical detail.",
    ),
    sentinel_field="parcel",
    sentinel_value="032W290000400",
)

SOURCES = {
    config.source_id: config for config in (LANE_PARCELS, LANE_SALES, MARION_PARCELS)
}

COMPLEMENTARY_SOURCES: dict[str, tuple[dict[str, Any], ...]] = {
    LANE_PARCELS_SOURCE_ID: (
        {
            "name": "Lane County Property Account Information",
            "url": "https://apps.lanecounty.org/propertyaccountinformation/",
            "adds": (
                "Interactive account detail searchable by account, map-taxlot, "
                "address, or owner name."
            ),
            "access": "public_interactive",
        },
        {
            "name": "Lane County Deeds & Records",
            "url": (
                "https://www.lanecountyor.gov/government/county_departments/"
                "county_administration/general_county_administration/"
                "operations/county_clerk/real_property_recording"
            ),
            "adds": (
                "Recorded real-property source documents through the public "
                "research library or copy requests by email or mail."
            ),
            "access": "public_library_or_copy_request",
        },
        {
            "name": "Lane County Tax Maps",
            "url": "https://apps.lanecounty.org/TaxMap/Search.aspx",
            "adds": "Official tax-map images searchable by location or map lot.",
            "access": "public_interactive",
        },
        {
            "name": "Regional Land Information Database",
            "url": "https://www.rlid.org/",
            "adds": "Subscribed online regional property information.",
            "access": "subscription",
        },
    ),
    LANE_SALES_SOURCE_ID: (
        {
            "name": "Lane County Deeds & Records",
            "url": (
                "https://www.lanecountyor.gov/government/county_departments/"
                "county_administration/general_county_administration/"
                "operations/county_clerk/real_property_recording"
            ),
            "adds": "Recorded documents corresponding to deed references.",
            "access": "public_library_or_copy_request",
        },
        {
            "name": "Lane County Property Account Information",
            "url": "https://apps.lanecounty.org/propertyaccountinformation/",
            "adds": "Current assessor account context for a sale row.",
            "access": "public_interactive",
        },
    ),
    MARION_PARCELS_SOURCE_ID: (
        {
            "name": "Marion County Assessor Property Records",
            "url": "https://mcasr.co.marion.or.us/",
            "adds": (
                "Linked property and tax detail; the official site states a "
                "24-hour update cycle."
            ),
            "access": "public_interactive",
        },
        {
            "name": "Marion County Sales Data",
            "url": "https://www.co.marion.or.us/AO/Pages/datacenter.aspx",
            "adds": (
                "Weekly annual spreadsheets with current and historical sales "
                "files extending back to the 1940s."
            ),
            "access": "public_download",
        },
        {
            "name": "Marion County Comprehensive Download",
            "url": "https://www.co.marion.or.us/AO/Pages/datacenter.aspx",
            "adds": (
                "Monthly assessment download; the county states owner name and "
                "mailing address are omitted."
            ),
            "access": "public_download",
        },
        {
            "name": "Marion County Assessor Data Request",
            "url": "https://apps.co.marion.or.us/AssessorDataRequest/",
            "adds": "Official custom-data request route with published fees.",
            "access": "paid_request",
        },
    ),
}


class SourceSelectionError(ValueError):
    """A caller selection or cursor error with a result status."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category="selection",
            retryable=False,
            details=self.details,
        )


@dataclass(frozen=True)
class CursorState:
    source_id: str
    operation: str
    criteria_fingerprint: str
    offset: int
    anchor: int
    total_count: int
    schema_fingerprint: str


@dataclass(frozen=True)
class ArcGISBatch:
    features: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    total_count: int
    start_offset: int
    schema_fingerprint: str
    metadata: Mapping[str, Any]
    pages_fetched: int
    errors: tuple[PublicRecordsError, ...]


class OregonCountyArcGISClient(ArcGISRESTClient):
    """Small metadata/count/page facade over the shared ArcGIS transport."""

    def __init__(
        self,
        config: SourceConfig,
        *,
        page_size: int,
        timeout: float,
        minimum_interval: float,
        retry_attempts: int,
    ) -> None:
        super().__init__(
            config.layer_url,
            page_size=page_size,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=RetryPolicy(max_attempts=retry_attempts),
            user_agent="Ithildin-Public-Records/1.0",
        )
        self.config = config

    def fetch_metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(self.layer_url, params={"f": "json"})
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "ArcGIS layer metadata must be a JSON object",
                url=self.layer_url,
            )
        if "error" in payload:
            raise SourceResponseError(
                "ArcGIS returned an error for layer metadata",
                url=self.layer_url,
                details={"response": payload["error"]},
            )
        return payload

    def fetch_count(self, where: str) -> int:
        payload = self._request_json(
            self.query_url,
            params={
                "where": where,
                "returnCountOnly": "true",
                "f": "json",
            },
        )
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "ArcGIS returned an invalid count response",
                url=self.query_url,
                details={"response": payload},
            )
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "ArcGIS count response lacks a non-negative integer",
                url=self.query_url,
                details={"count": count},
            )
        return count

    def fetch_page(
        self,
        *,
        where: str,
        offset: int,
        record_count: int,
        out_fields: str = "*",
        return_geometry: bool,
    ) -> tuple[Mapping[str, Any], ...]:
        params: dict[str, Any] = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": str(return_geometry).lower(),
            "resultOffset": offset,
            "resultRecordCount": record_count,
            "orderByFields": f"{self.config.object_id_field} ASC",
            "f": "json",
        }
        if return_geometry:
            params["outSR"] = 4326
        payload = self._request_json(self.query_url, params=params)
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "ArcGIS returned an invalid feature response",
                url=self.query_url,
                details={"response": payload},
            )
        features = payload.get("features")
        if not isinstance(features, list) or any(
            not isinstance(feature, Mapping) for feature in features
        ):
            raise SourceSchemaError(
                "ArcGIS feature response lacks a valid features array",
                url=self.query_url,
            )
        return tuple(features)


def _source(source_id: str) -> SourceConfig:
    try:
        return SOURCES[source_id]
    except KeyError as error:
        raise SourceSelectionError(
            "unknown_source",
            f"unknown Lane/Marion source: {source_id}",
            details={"known_sources": sorted(SOURCES)},
        ) from error


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


def _sql_text(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        raise SourceSelectionError(
            "blank_query",
            "search value must not be blank",
        )
    return text.replace("'", "''")


def _first_text(
    attributes: Mapping[str, Any],
    field_names: Sequence[str],
) -> str | None:
    for field_name in field_names:
        value = _clean_text(attributes.get(field_name))
        if value:
            return value
    return None


def _unique_text(
    attributes: Mapping[str, Any],
    field_names: Sequence[str],
) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for field_name in field_names:
        value = _clean_text(attributes.get(field_name))
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            values.append(value)
    return values


def _delimited_text(value: Any) -> list[str]:
    text = _clean_text(value)
    if not text:
        return []
    values: list[str] = []
    seen: set[str] = set()
    for candidate in re.split(r"[,;|\n]+", text):
        normalized = _clean_text(candidate)
        if normalized and normalized.casefold() not in seen:
            seen.add(normalized.casefold())
            values.append(normalized)
    return values


def _date(value: Any) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return (
                datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()
            )
        except (OverflowError, OSError, ValueError):
            return None
    text = _clean_text(value)
    if not text:
        return None
    for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return text


def _feature_attributes(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise ValueError("ArcGIS feature lacks an attributes object")
    return attributes


def _feature_oid(config: SourceConfig, feature: Mapping[str, Any]) -> int:
    value = _feature_attributes(feature).get(config.object_id_field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SourceSchemaError(
            f"ArcGIS feature lacks integer {config.object_id_field}",
            url=config.layer_url,
            details={"value": value},
        )
    return value


def _where(
    config: SourceConfig,
    *,
    operation: str,
    selector: str,
    search_field: str,
) -> str:
    value = _sql_text(selector)
    if operation == "parcel":
        if config.record_kind != "parcel":
            raise SourceSelectionError(
                "operation_not_supported",
                f"{config.source_id} is a sale component, not a parcel component",
            )
        groups = ("parcel",)
    elif operation == "sale":
        if config.source_id != LANE_SALES_SOURCE_ID:
            raise SourceSelectionError(
                "operation_not_supported",
                "sale lookup is available on the Lane recent-sales component",
            )
        groups = ("instrument",)
    elif search_field == "auto":
        groups = tuple(config.search_fields)
    else:
        if search_field not in config.search_fields:
            raise SourceSelectionError(
                "unsupported_search_field",
                f"{config.source_id} does not publish a searchable {search_field} field",
                details={"supported_fields": sorted(config.search_fields)},
            )
        groups = (search_field,)

    clauses: list[str] = []
    for group in groups:
        for column in config.search_fields[group]:
            if column.contains:
                clauses.append(f"UPPER({column.name}) LIKE '%{value.upper()}%'")
            else:
                clauses.append(f"UPPER({column.name}) = '{value.upper()}'")
    if not clauses:
        raise SourceSelectionError(
            "unsupported_search_field",
            f"{config.source_id} has no fields for {search_field}",
        )
    return clauses[0] if len(clauses) == 1 else f"({' OR '.join(clauses)})"


def _jurisdiction(config: SourceConfig) -> JurisdictionMetadata:
    return JurisdictionMetadata(
        jurisdiction_id=config.county_geoid,
        name=config.county_name,
        state_code=STATE_CODE,
        county_fips=config.county_geoid,
        metadata={
            "state_fips": STATE_FIPS,
            "publisher": config.publisher,
        },
    )


def _build_query(
    config: SourceConfig,
    *,
    operation: str,
    selector: str,
    search_field: str,
    limit: int,
    cursor: str | None,
    geometry: bool,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=config.source_metadata(),
        jurisdiction=_jurisdiction(config),
        query=QueryMetadata(
            operation=operation,
            parameters={
                "selector": selector,
                "field": search_field,
                "geometry": geometry,
                "component_scope": config.component_scope,
            },
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "pagination": "count_snapshot_offset_with_oid_anchor",
                "complement_keys": list(config.complement_keys),
                "access_decision": dict(access_decision or {}),
            },
        ),
    )


def _metadata_schema(
    config: SourceConfig,
    metadata: Mapping[str, Any],
) -> tuple[str, int]:
    if metadata.get("name") != config.expected_layer_name:
        raise SourceSchemaError(
            "ArcGIS layer name changed",
            url=config.layer_url,
            details={
                "expected": config.expected_layer_name,
                "observed": metadata.get("name"),
            },
        )
    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "ArcGIS metadata lacks valid field declarations",
            url=config.layer_url,
        )
    declared = arcgis_declared_schema(fields)
    declared_names = {
        str(field.get("name")) for field in fields if field.get("name") is not None
    }
    missing = sorted(set(config.required_fields) - declared_names)
    if missing:
        raise SourceSchemaError(
            "ArcGIS layer is missing required fields",
            url=config.layer_url,
            details={"missing_fields": missing},
        )
    advanced = metadata.get("advancedQueryCapabilities")
    if (
        not isinstance(advanced, Mapping)
        or not advanced.get("supportsPagination")
        or not advanced.get("supportsOrderBy")
    ):
        raise SourceSchemaError(
            "ArcGIS layer no longer declares ordered offset pagination",
            url=config.layer_url,
        )
    maximum = metadata.get("maxRecordCount")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        raise SourceSchemaError(
            "ArcGIS metadata lacks a positive maxRecordCount",
            url=config.layer_url,
            details={"maxRecordCount": maximum},
        )
    return schema_fingerprint(declared), min(maximum, config.max_page_size)


def _criteria_fingerprint(
    config: SourceConfig,
    *,
    operation: str,
    where: str,
    geometry: bool,
) -> str:
    return sha256_fingerprint(
        {
            "source_id": config.source_id,
            "operation": operation,
            "where": where,
            "geometry": geometry,
            "ordering": f"{config.object_id_field} ASC",
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "source": state.source_id,
        "operation": state.operation,
        "criteria": state.criteria_fingerprint,
        "offset": state.offset,
        "anchor": state.anchor,
        "total": state.total_count,
        "schema": state.schema_fingerprint,
    }
    token = (
        base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{CURSOR_PREFIX}{token}"


def _decode_cursor(cursor: str | None) -> CursorState | None:
    if cursor is None:
        return None
    if not cursor.startswith(CURSOR_PREFIX):
        raise SourceSelectionError(
            "invalid_cursor",
            "cursor does not belong to the Lane/Marion property adapter",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(token + padding).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceSelectionError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if not isinstance(payload, Mapping) or payload.get("v") != CURSOR_VERSION:
        raise SourceSelectionError(
            "invalid_cursor",
            "cursor version is unsupported",
        )
    try:
        state = CursorState(
            source_id=str(payload["source"]),
            operation=str(payload["operation"]),
            criteria_fingerprint=str(payload["criteria"]),
            offset=int(payload["offset"]),
            anchor=int(payload["anchor"]),
            total_count=int(payload["total"]),
            schema_fingerprint=str(payload["schema"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SourceSelectionError(
            "invalid_cursor",
            "cursor payload lacks required values",
        ) from error
    if (
        state.offset <= 0
        or state.anchor < 0
        or state.total_count < state.offset
        or not re.fullmatch(r"[0-9a-f]{64}", state.schema_fingerprint)
    ):
        raise SourceSelectionError(
            "invalid_cursor",
            "cursor values are inconsistent",
        )
    return state


def _pagination_error(
    code: str,
    message: str,
    **details: Any,
) -> PublicRecordsError:
    return PublicRecordsError(
        code=code,
        message=message,
        category="pagination",
        retryable=True,
        details=details,
    )


def _fetch_batch(
    client: Any,
    config: SourceConfig,
    *,
    operation: str,
    where: str,
    limit: int,
    cursor: str | None,
    return_geometry: bool,
) -> ArcGISBatch:
    metadata = client.fetch_metadata()
    current_schema, server_page_size = _metadata_schema(config, metadata)
    criteria = _criteria_fingerprint(
        config,
        operation=operation,
        where=where,
        geometry=return_geometry,
    )
    cursor_state = _decode_cursor(cursor)
    if cursor_state is not None:
        if (
            cursor_state.source_id != config.source_id
            or cursor_state.operation != operation
            or cursor_state.criteria_fingerprint != criteria
        ):
            raise SourceSelectionError(
                "cursor_query_mismatch",
                "cursor belongs to different source or query criteria",
            )
        if cursor_state.schema_fingerprint != current_schema:
            raise SourceSelectionError(
                "cursor_schema_changed",
                "source schema changed after the cursor was issued",
                status=ResultStatus.SOURCE_CHANGED,
            )

    start_count = client.fetch_count(where)
    offset = cursor_state.offset if cursor_state else 0
    start_offset = offset
    if offset > start_count:
        raise SourceSelectionError(
            "cursor_out_of_range",
            "cursor offset exceeds the current source result count",
            details={"cursor_offset": offset, "source_count": start_count},
        )

    errors: list[PublicRecordsError] = []
    last_oid: int | None = None
    safe_to_resume = True
    if cursor_state is not None:
        boundary = client.fetch_page(
            where=where,
            offset=offset - 1,
            record_count=1,
            out_fields=config.object_id_field,
            return_geometry=False,
        )
        if len(boundary) != 1:
            raise SourceSelectionError(
                "cursor_snapshot_changed",
                "cursor boundary row is no longer available",
            )
        observed_anchor = _feature_oid(config, boundary[0])
        if observed_anchor != cursor_state.anchor:
            raise SourceSelectionError(
                "cursor_snapshot_changed",
                "ordered cursor boundary changed",
                details={
                    "expected_anchor": cursor_state.anchor,
                    "observed_anchor": observed_anchor,
                },
            )
        last_oid = observed_anchor
        if cursor_state.total_count != start_count:
            errors.append(
                _pagination_error(
                    "count_changed_since_cursor",
                    "result count changed after the cursor was issued",
                    cursor_count=cursor_state.total_count,
                    current_count=start_count,
                )
            )
            safe_to_resume = False

    page_size = min(
        int(getattr(client, "page_size", server_page_size)),
        server_page_size,
    )
    collected: list[Mapping[str, Any]] = []
    seen_oids: set[int] = set()
    pages_fetched = 0
    while offset < start_count and len(collected) < limit:
        requested = min(page_size, limit - len(collected))
        try:
            page = client.fetch_page(
                where=where,
                offset=offset,
                record_count=requested,
                out_fields="*",
                return_geometry=return_geometry,
            )
        except PublicRecordsHTTPError as error:
            if not collected:
                raise
            errors.append(error.to_contract_error())
            safe_to_resume = False
            break
        pages_fetched += 1
        if not page:
            errors.append(
                _pagination_error(
                    "pagination_no_progress",
                    "ArcGIS returned an empty page before the count was reached",
                    offset=offset,
                    source_count=start_count,
                )
            )
            safe_to_resume = False
            break
        if len(page) > requested:
            errors.append(
                _pagination_error(
                    "pagination_page_oversized",
                    "ArcGIS returned more rows than requested",
                    requested=requested,
                    returned=len(page),
                )
            )
            safe_to_resume = False
            break
        valid_page = True
        for feature in page:
            oid = _feature_oid(config, feature)
            if oid in seen_oids or (last_oid is not None and oid <= last_oid):
                errors.append(
                    _pagination_error(
                        "pagination_repeat_or_reorder",
                        "ArcGIS repeated or reordered a feature",
                        object_id=oid,
                        previous_object_id=last_oid,
                    )
                )
                safe_to_resume = False
                valid_page = False
                break
            seen_oids.add(oid)
            last_oid = oid
            collected.append(feature)
        if not valid_page:
            break
        offset += len(page)

    try:
        end_count = client.fetch_count(where)
    except PublicRecordsHTTPError as error:
        if not collected:
            raise
        errors.append(error.to_contract_error())
        safe_to_resume = False
        end_count = start_count
    if end_count != start_count:
        errors.append(
            _pagination_error(
                "count_changed_during_traversal",
                "result count changed during pagination",
                initial_count=start_count,
                final_count=end_count,
            )
        )
        safe_to_resume = False

    next_cursor = None
    if safe_to_resume and collected and offset < end_count and last_oid is not None:
        next_cursor = _encode_cursor(
            CursorState(
                source_id=config.source_id,
                operation=operation,
                criteria_fingerprint=criteria,
                offset=offset,
                anchor=last_oid,
                total_count=end_count,
                schema_fingerprint=current_schema,
            )
        )
    return ArcGISBatch(
        features=tuple(collected),
        next_cursor=next_cursor,
        total_count=end_count,
        start_offset=start_offset,
        schema_fingerprint=current_schema,
        metadata=dict(metadata),
        pages_fetched=pages_fetched,
        errors=tuple(errors),
    )


def _address(
    *,
    raw: Any,
    city_state_zip: Any = None,
    city: Any = None,
    state: Any = None,
    postal_code: Any = None,
    country: Any = "US",
    lines: Sequence[Any] = (),
) -> dict[str, Any]:
    line_values = [value for value in (_clean_text(line) for line in lines) if value]
    raw_value = _clean_text(raw)
    csz_value = _clean_text(city_state_zip)
    if not raw_value and line_values:
        raw_value = ", ".join(line_values)
    if raw_value and csz_value:
        raw_value = f"{raw_value}, {csz_value}"
    return {
        "raw": raw_value,
        "address_lines": line_values,
        "city_state_zip_raw": csz_value,
        "city": _clean_text(city),
        "state": _clean_text(state),
        "postal_code": _clean_text(postal_code),
        "country": _clean_text(country),
    }


def _owners(attributes: Mapping[str, Any], field_name: str) -> list[dict[str, Any]]:
    name = _clean_text(attributes.get(field_name))
    if not name:
        return []
    return [
        {
            "raw_name": name,
            "role": "primary_assessor_owner",
            "assertion_type": "assessment_roll",
            "confidence": "high",
        }
    ]


def _base_record(
    config: SourceConfig,
    feature: Mapping[str, Any],
    *,
    response_schema_fingerprint: str,
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    attributes = _feature_attributes(feature)
    object_id = _feature_oid(config, feature)
    native_id = _first_text(attributes, config.native_id_fields)
    if not native_id:
        native_id = str(object_id)
    record = {
        "canonical_ref": canonical_property_ref(
            config.source_id,
            config.county_geoid,
            config.record_kind,
            native_id,
        ),
        "source_id": config.source_id,
        "source_url": config.layer_url,
        "record_kind": config.record_kind,
        "snapshot_complete": config.record_kind == "parcel",
        "source_record_id": str(object_id),
        "object_id": object_id,
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": config.county_name.removesuffix(", Oregon"),
            "county_geoid": config.county_geoid,
        },
        "source_lineage": {
            "publisher": config.publisher,
            "service_item_id": config.service_item_id,
            "layer_name": config.expected_layer_name,
            "layer_url": config.layer_url,
            "component_scope": config.component_scope,
            "cadence_fact": config.cadence_fact,
        },
        "component_completeness": {
            "scope": config.component_scope,
            "complement_keys": list(config.complement_keys),
            "complementary_source_count": len(COMPLEMENTARY_SOURCES[config.source_id]),
        },
        "response_schema_fingerprint": response_schema_fingerprint,
        "adapter_schema_fingerprint": sha256_fingerprint(
            {
                "normalization_version": 1,
                "source_id": config.source_id,
                "record_kind": config.record_kind,
                "required_fields": list(config.required_fields),
                "search_fields": {
                    group: [
                        {"name": column.name, "contains": column.contains}
                        for column in columns
                    ]
                    for group, columns in sorted(config.search_fields.items())
                },
            }
        ),
        "raw_attributes": dict(attributes),
    }
    return record, attributes


def _add_geometry(
    record: dict[str, Any],
    feature: Mapping[str, Any],
    config: SourceConfig,
    *,
    requested: bool,
) -> None:
    record["source_geometry_crs"] = config.original_crs
    if requested and isinstance(feature.get("geometry"), Mapping):
        record["geometry"] = dict(feature["geometry"])
        record["geometry_format"] = "esri_json"
        record["geometry_crs"] = "EPSG:4326"
        record["geometry_lineage"] = {
            "source_crs": config.original_crs,
            "requested_output_crs": "EPSG:4326",
            "transformation": "ArcGIS outSR=4326",
        }


def _normalize_lane_parcel(
    feature: Mapping[str, Any],
    *,
    schema_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    record, attributes = _base_record(
        LANE_PARCELS,
        feature,
        response_schema_fingerprint=schema_value,
    )
    native_id = _first_text(attributes, ("MAPTAXLOT", "RLID")) or str(
        record["object_id"]
    )
    record["native_parcel_id"] = native_id
    record["parcel_identity_basis"] = (
        "published_parcel_id"
        if _first_text(attributes, ("MAPTAXLOT", "RLID"))
        else "source_object_id_fallback"
    )
    record["alternate_parcel_ids"] = [
        value
        for value in _unique_text(
            attributes,
            ("RLID", "MAPTAXLOT", "MAPNUMBER", "TAXLOT"),
        )
        if value != native_id
    ]
    record["assessment_account_ids"] = _unique_text(
        attributes,
        ("PROPACCT", "ACCTNO"),
    )
    record["owners"] = _owners(attributes, "OWNNAME")
    record["owner_visibility"] = {
        "state": "published",
        "source_field": "OWNNAME",
    }
    record["mailing_address"] = _address(
        raw=None,
        lines=(
            attributes.get("ADDR1"),
            attributes.get("ADDR2"),
            attributes.get("ADDR3"),
        ),
        city=attributes.get("OWNERCITY"),
        state=attributes.get("OWNERPRVST"),
        postal_code=attributes.get("OWNERZIP"),
        country=attributes.get("OWNERCNTRY") or "US",
    )
    record["parcel_acres"] = attributes.get("MAPACRES")
    record["parcel_acre_observations"] = {
        "map_acres": attributes.get("MAPACRES"),
        "assessor_acres_raw": _clean_text(attributes.get("AscendAcres")),
    }
    record["zoning_and_plan"] = {
        "zoning_description": _clean_text(attributes.get("zoningdesc")),
        "plan_description": _clean_text(attributes.get("plandesdesc")),
        "geo_city": _clean_text(attributes.get("GEOCITY")),
        "urban_growth_boundary": _clean_text(attributes.get("UGB")),
    }
    record["source_last_edited"] = _date(attributes.get("LastEditedDate"))
    record["source_edit_type"] = _clean_text(attributes.get("EditType"))
    record["related_components"] = [
        {
            "source_id": LANE_SALES_SOURCE_ID,
            "relationship": "separate_official_recent_sales_component",
            "join_keys": {
                "account": record["assessment_account_ids"],
                "map_taxlot": native_id,
            },
            "coverage": "publisher-labeled last three years",
        }
    ]
    _add_geometry(
        record,
        feature,
        LANE_PARCELS,
        requested=geometry_requested,
    )
    return record


def _normalize_lane_sale(
    feature: Mapping[str, Any],
    *,
    schema_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    record, attributes = _base_record(
        LANE_SALES,
        feature,
        response_schema_fingerprint=schema_value,
    )
    account = _clean_text(attributes.get(f"{LANE_SALE_PREFIX}account"))
    maplot = _clean_text(attributes.get(f"{LANE_SALE_PREFIX}maplot"))
    instrument = _clean_text(attributes.get(f"{LANE_SALE_PREFIX}deed_transfer_no"))
    deed_date = _date(attributes.get("DeedDate"))
    sale_price = attributes.get(f"{LANE_SALE_PREFIX}sale_price")
    semantic_values = {
        "account": account,
        "maplot": maplot,
        "instrument": instrument,
        "deed_date": deed_date,
        "sale_price": sale_price,
    }
    record["native_sale_id"] = sha256_fingerprint(semantic_values)
    record["canonical_ref"] = canonical_property_ref(
        LANE_SALES.source_id,
        LANE_SALES.county_geoid,
        LANE_SALES.record_kind,
        record["native_sale_id"],
    )
    record["join_keys"] = {
        "assessment_account_id": account,
        "map_taxlot": maplot,
        "related_source_id": LANE_PARCELS_SOURCE_ID,
    }
    record["instrument_reference"] = {
        "instrument_number": instrument,
        "instrument_type": _clean_text(attributes.get(f"{LANE_SALE_PREFIX}deed_type")),
        "recording_date": deed_date,
        "source_kind": "assessor_sale_analysis_reference",
    }
    record["sale"] = {
        "sale_date": deed_date,
        "consideration": sale_price,
        "currency": "USD",
        "reject_code": _clean_text(attributes.get(f"{LANE_SALE_PREFIX}reject_code")),
        "group_sale_description": _clean_text(
            attributes.get(f"{LANE_SALE_PREFIX}group_sale_desc")
        ),
        "property_class": attributes.get(f"{LANE_SALE_PREFIX}property_class"),
        "statistical_class": _clean_text(
            attributes.get(f"{LANE_SALE_PREFIX}stat_class")
        ),
    }
    record["situs_address"] = _address(
        raw=attributes.get(f"{LANE_SALE_PREFIX}situs_address"),
        city=attributes.get(f"{LANE_SALE_PREFIX}city"),
        state=attributes.get(f"{LANE_SALE_PREFIX}state"),
        postal_code=attributes.get(f"{LANE_SALE_PREFIX}zip"),
    )
    record["district"] = {
        "district_id": _clean_text(attributes.get("SalesLayerCityJoin_district")),
        "district_name": _clean_text(attributes.get("SalesLayerCityJoin_names")),
        "incorporated_city": _clean_text(
            attributes.get("SalesLayerCityJoin_inccityname")
        ),
        "incorporated_area": _clean_text(
            attributes.get(f"{LANE_SALE_PREFIX}IncorpArea")
        ),
    }
    record["neighborhood"] = {
        "code": attributes.get("dbo_rlid_neighborhood_neighborhood"),
        "description": _clean_text(attributes.get("dbo_rlid_neighborhood_description")),
    }
    record["coverage_period"] = {
        "source_label": "last 3 years",
        "scope": "rolling_recent_sale_analysis",
    }
    _add_geometry(
        record,
        feature,
        LANE_SALES,
        requested=geometry_requested,
    )
    return record


def _normalize_marion_parcel(
    feature: Mapping[str, Any],
    *,
    schema_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    record, attributes = _base_record(
        MARION_PARCELS,
        feature,
        response_schema_fingerprint=schema_value,
    )
    native_id = _first_text(attributes, ("TAXLOT", "ALT_TAXLOT")) or str(
        record["object_id"]
    )
    record["native_parcel_id"] = native_id
    record["parcel_identity_basis"] = (
        "published_parcel_id"
        if _first_text(attributes, ("TAXLOT", "ALT_TAXLOT"))
        else "source_object_id_fallback"
    )
    record["alternate_parcel_ids"] = [
        value
        for value in _unique_text(attributes, ("ALT_TAXLOT",))
        if value != native_id
    ]
    record["assessment_account_ids"] = _unique_text(
        attributes,
        ("TAXACCT", "ALT_TAXACCT"),
    )
    for account_id in _delimited_text(attributes.get("OTHERACCTS")):
        if account_id.casefold() not in {
            value.casefold() for value in record["assessment_account_ids"]
        }:
            record["assessment_account_ids"].append(account_id)
    record["owners"] = _owners(attributes, "OWNERNAME")
    record["owner_visibility"] = {
        "state": "published",
        "source_field": "OWNERNAME",
    }
    record["situs_address"] = _address(
        raw=attributes.get("SITUS"),
        city_state_zip=attributes.get("SITUSCSZ"),
    )
    record["mailing_address"] = _address(
        raw=attributes.get("OWNERADDR"),
        city_state_zip=attributes.get("OWNERCSZ"),
    )
    record["legal_and_plat"] = {
        "plat_name": _clean_text(attributes.get("PLATNAME")),
        "block": _clean_text(attributes.get("BLOCK")),
        "lot": _clean_text(attributes.get("LOT")),
    }
    record["parcel_acres"] = attributes.get("ACRES")
    record["parcel_acre_observations"] = {
        "published_acres": attributes.get("ACRES"),
    }
    record["source_last_updated"] = _date(attributes.get("LASTUPDATE"))
    instrument_number = _clean_text(attributes.get("INSTNUM"))
    instrument_date = _date(attributes.get("INSTDATE"))
    record["latest_verified_sale_reference"] = {
        "instrument_number": instrument_number,
        "instrument_type": _clean_text(attributes.get("INSTTYPE")),
        "recording_date": instrument_date,
        "consideration": attributes.get("SALEPRICE"),
        "currency": "USD",
        "scope": "latest_transfer_coded_as_verified_sale",
    }
    record["zoning"] = {
        "code": _clean_text(attributes.get("ZONECODE")),
        "authority": _clean_text(attributes.get("ZONEAUTH")),
        "authority_url": _clean_text(attributes.get("ZONEWEB")),
    }
    record["physical_characteristics"] = {
        "year_built": attributes.get("YEARBUILT"),
        "building_ground_floor_area": attributes.get("BLDGAREA"),
        "property_class": _clean_text(attributes.get("PROPCLASS")),
    }
    record["assessment"] = {
        "real_market_land": attributes.get("RMVLND"),
        "real_market_improvements": attributes.get("RMVIMP"),
        "real_market_total": attributes.get("RMVTOTAL"),
        "assessed_value": attributes.get("ASSDVAL"),
        "currency": "USD",
    }
    record["tax_and_districts"] = {
        "tax_codes": _clean_text(attributes.get("TAXCODE")),
        "cities": _clean_text(attributes.get("CITY")),
        "school_districts": _clean_text(attributes.get("SCHLDIST")),
        "fire_districts": _clean_text(attributes.get("FIREDIST")),
    }
    record["official_links"] = {
        "property_record": _clean_text(attributes.get("REFLINK")),
        "tax_map": _clean_text(attributes.get("MAPLINK")),
    }
    record["source_centroid"] = {
        "x": attributes.get("X_COORD"),
        "y": attributes.get("Y_COORD"),
        "crs": "EPSG:2913",
    }
    _add_geometry(
        record,
        feature,
        MARION_PARCELS,
        requested=geometry_requested,
    )
    return record


def _normalize_feature(
    config: SourceConfig,
    feature: Mapping[str, Any],
    *,
    schema_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    if config.source_id == LANE_PARCELS_SOURCE_ID:
        return _normalize_lane_parcel(
            feature,
            schema_value=schema_value,
            geometry_requested=geometry_requested,
        )
    if config.source_id == LANE_SALES_SOURCE_ID:
        return _normalize_lane_sale(
            feature,
            schema_value=schema_value,
            geometry_requested=geometry_requested,
        )
    if config.source_id == MARION_PARCELS_SOURCE_ID:
        return _normalize_marion_parcel(
            feature,
            schema_value=schema_value,
            geometry_requested=geometry_requested,
        )
    raise ValueError(f"no normalizer configured for {config.source_id}")


def _client(args: argparse.Namespace, config: SourceConfig) -> OregonCountyArcGISClient:
    return OregonCountyArcGISClient(
        config,
        page_size=min(args.page_size, config.max_page_size),
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def _best_effort_log(
    query: PublicRecordsQuery,
    source_id: str,
    result: PublicRecordsResult,
) -> None:
    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    try:
        log_search(canonical_json(query.to_dict()), source_id, count)
    except Exception as error:
        print(f"Warning: search log was not updated: {error}", file=sys.stderr)


def _records_result(
    query: PublicRecordsQuery,
    config: SourceConfig,
    batch: ArcGISBatch,
    *,
    geometry_requested: bool,
) -> PublicRecordsResult:
    records: list[dict[str, Any]] = []
    errors = list(batch.errors)
    for index, feature in enumerate(batch.features):
        try:
            record = _normalize_feature(
                config,
                feature,
                schema_value=batch.schema_fingerprint,
                geometry_requested=geometry_requested,
            )
            records.append(record)
        except (TypeError, ValueError, PublicRecordsHTTPError) as error:
            errors.append(
                PublicRecordsError(
                    code="normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                    details={"record_index": index},
                )
            )
            break

    editing_info = batch.metadata.get("editingInfo")
    service_data_last_edit = (
        _date(editing_info.get("dataLastEditDate"))
        if isinstance(editing_info, Mapping)
        else None
    )
    retrieval_snapshot = {
        "total_matching_records": batch.total_count,
        "window_start_offset": batch.start_offset,
        "window_returned_records": len(records),
        "window_complete": batch.next_cursor is None and not errors,
        "continuation_available": batch.next_cursor is not None and not errors,
        "pages_fetched": batch.pages_fetched,
        "schema_fingerprint": batch.schema_fingerprint,
        "service_data_last_edit": service_data_last_edit,
    }
    for record in records:
        record["retrieval_snapshot"] = retrieval_snapshot

    if errors:
        status = ResultStatus.PARTIAL if records else ResultStatus.SOURCE_CHANGED
        return PublicRecordsResult.failure(
            query,
            status,
            errors,
            records=records,
            next_cursor=batch.next_cursor if records and not batch.errors else None,
            warnings=config.warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
        warnings=config.warnings,
    )


def _execute_records(
    args: argparse.Namespace,
    *,
    client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    config = _source(args.source)
    operation = args.command
    selector = args.query
    search_field = (
        "parcel"
        if operation == "parcel"
        else "instrument"
        if operation == "sale"
        else args.field
    )
    query = _build_query(
        config,
        operation=operation,
        selector=selector,
        search_field=search_field,
        limit=args.limit,
        cursor=args.cursor,
        geometry=args.geometry,
        access_decision=access_decision,
    )
    try:
        where = _where(
            config,
            operation=operation,
            selector=selector,
            search_field=search_field,
        )
        active_client = client or _client(args, config)
        batch = _fetch_batch(
            active_client,
            config,
            operation=operation,
            where=where,
            limit=args.limit,
            cursor=args.cursor,
            return_geometry=args.geometry,
        )
        result = _records_result(
            query,
            config,
            batch,
            geometry_requested=args.geometry,
        )
    except SourceSelectionError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=config.warnings,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=config.warnings)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="adapter_failure",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=config.warnings,
        )
    if log_results:
        _best_effort_log(query, config.source_id, result)
    return result


def _execute_probe(
    args: argparse.Namespace,
    config: SourceConfig,
    *,
    client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = _build_query(
        config,
        operation="probe",
        selector=config.sentinel_value,
        search_field=config.sentinel_field,
        limit=1,
        cursor=None,
        geometry=False,
        access_decision=access_decision,
    )
    try:
        active_client = client or _client(args, config)
        metadata = active_client.fetch_metadata()
        schema_value, maximum = _metadata_schema(config, metadata)
        total_count = active_client.fetch_count("1=1")
        if config.source_id == LANE_SALES_SOURCE_ID:
            sentinel_strategy = "first_ordered_current_row"
            where = "1=1"
            sentinel_count = total_count
        else:
            sentinel_strategy = "configured_exact_identifier"
            where = _where(
                config,
                operation="search",
                selector=config.sentinel_value,
                search_field=config.sentinel_field,
            )
            sentinel_count = active_client.fetch_count(where)
        if sentinel_count <= 0:
            raise SourceSchemaError(
                "configured source sentinel was not found",
                url=config.layer_url,
                details={
                    "sentinel_field": config.sentinel_field,
                    "sentinel_value": config.sentinel_value,
                },
            )
        page = active_client.fetch_page(
            where=where,
            offset=0,
            record_count=1,
            out_fields="*",
            return_geometry=False,
        )
        if len(page) != 1:
            raise SourceSchemaError(
                "sentinel query did not return one record",
                url=config.layer_url,
                details={"returned": len(page)},
            )
        sentinel = _normalize_feature(
            config,
            page[0],
            schema_value=schema_value,
            geometry_requested=False,
        )
        editing_info = metadata.get("editingInfo")
        data_last_edit = (
            _date(editing_info.get("dataLastEditDate"))
            if isinstance(editing_info, Mapping)
            else None
        )
        result = PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": config.source_id,
                    "component_total_count": total_count,
                    "schema_fingerprint": schema_value,
                    "layer_name": metadata.get("name"),
                    "service_item_id": metadata.get("serviceItemId"),
                    "max_record_count": maximum,
                    "source_crs": config.original_crs,
                    "service_data_last_edit": data_last_edit,
                    "cadence_fact": config.cadence_fact,
                    "component_scope": config.component_scope,
                    "sentinel_strategy": sentinel_strategy,
                    "sentinel_count": sentinel_count,
                    "sentinel": sentinel,
                    "complementary_sources": list(
                        COMPLEMENTARY_SOURCES[config.source_id]
                    ),
                }
            ],
            warnings=config.warnings,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=config.warnings)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="probe_normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=config.warnings,
        )
    if log_results:
        _best_effort_log(query, config.source_id, result)
    return result


def _sources_payload() -> dict[str, Any]:
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "sources": [
            {
                **config.source_metadata().to_dict(),
                "object_id_field": config.object_id_field,
                "maximum_page_size": config.max_page_size,
                "search_fields": sorted(config.search_fields),
                "required_fields": list(config.required_fields),
                "warnings": list(config.warnings),
                "complementary_sources": list(COMPLEMENTARY_SOURCES[config.source_id]),
            }
            for config in SOURCES.values()
        ],
        "process_learnings": [
            {
                "scope": "lane_county_component_model",
                "learning": (
                    "Parcel publication cadence and rolling sale-period coverage "
                    "are distinct facts even when layers share one ArcGIS service."
                ),
            },
            {
                "scope": "marion_county_freshness",
                "learning": (
                    "Layer data-edit time, parcel LASTUPDATE, and linked "
                    "application update cadence are retained independently."
                ),
            },
            {
                "scope": "cross_component_join",
                "learning": (
                    "Lane parcel and sale rows retain account/map-taxlot join "
                    "keys and their own provenance rather than being flattened."
                ),
            },
        ],
    }


def _all_probe_payload(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> dict[str, Any]:
    components = [
        _execute_probe(
            args,
            config,
            access_decision=access_decision,
            log_results=log_results,
        ).to_dict()
        for config in SOURCES.values()
    ]
    successful = sum(
        component["status"] in {"ok", "no_results"} for component in components
    )
    status = (
        "ok"
        if successful == len(components)
        else "partial"
        if successful
        else "unavailable"
    )
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "status": status,
        "components": components,
    }


def execute(
    args: argparse.Namespace,
    *,
    client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute a source listing, source query, or bounded live probe."""

    if args.command == "sources":
        return _sources_payload()
    if args.command == "probe":
        if args.all_sources:
            return _all_probe_payload(
                args,
                access_decision=access_decision,
                log_results=log_results,
            )
        return _execute_probe(
            args,
            _source(args.source),
            client=client,
            access_decision=access_decision,
            log_results=log_results,
        )
    return _execute_records(
        args,
        client=client,
        access_decision=access_decision,
        log_results=log_results,
    )


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _payload(
    value: PublicRecordsResult | Mapping[str, Any],
) -> dict[str, Any]:
    return value.to_dict() if isinstance(value, PublicRecordsResult) else dict(value)


def _emit(
    value: PublicRecordsResult | Mapping[str, Any],
    args: argparse.Namespace,
) -> None:
    payload = _payload(value)
    if args.output:
        destination = Path(args.output).expanduser()
        _atomic_json_write(destination, payload)
        records = payload.get("records")
        count = (
            len(records)
            if isinstance(records, list)
            else len(payload.get("components", payload.get("sources", [])))
        )
        print(f"{count} results (Lane/Marion {args.command}) saved to {destination}")
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if args.command == "sources":
        print(f"Lane/Marion property source components: {len(payload['sources'])}")
        for source in payload["sources"]:
            print(
                f"  {source['source_id']} | "
                f"{source['metadata']['record_kind']} | "
                f"{', '.join(source['search_fields'])}"
            )
        return
    if args.command == "probe" and args.all_sources:
        print(f"Lane/Marion probes: {payload['status']}")
        for component in payload["components"]:
            print(
                f"  {component['query']['source']['source_id']} | {component['status']}"
            )
        return
    records = payload.get("records", [])
    print(
        f"Lane/Marion {args.command}: {payload.get('status')} ({len(records)} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in records:
        native_id = (
            record.get("native_parcel_id")
            or record.get("native_sale_id")
            or record.get("record_kind")
        )
        print(f"  {native_id} | {record.get('source_id')}")
    for error in payload.get("errors", []):
        print(
            f"ERROR [{error.get('code')}]: {error.get('message')}",
            file=sys.stderr,
        )


def _add_transport_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--page-size", type=int, default=1_000)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--minimum-interval", type=float, default=0.25)
    parser.add_argument("--retry-attempts", type=int, default=3)
    add_output_args(parser)


def _add_query_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        required=True,
        choices=sorted(SOURCES),
        help="Exact publisher/component-scoped source ID",
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--cursor",
        help="Query-bound continuation cursor returned by an earlier result",
    )
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="Request source geometry transformed to WGS84",
    )
    _add_transport_arguments(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Query official Lane and Marion County ArcGIS property components")
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser("sources", help="List source and complement coverage")
    add_output_args(sources)

    search = sub.add_parser("search", help="Search one selected component")
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=(
            "auto",
            "parcel",
            "account",
            "owner",
            "address",
            "instrument",
            "zoning",
        ),
        default="auto",
    )
    _add_query_arguments(search)

    parcel = sub.add_parser("parcel", help="Look up an exact parcel identifier")
    parcel.add_argument("query")
    parcel.set_defaults(field="parcel")
    _add_query_arguments(parcel)

    sale = sub.add_parser("sale", help="Look up an exact Lane deed reference")
    sale.add_argument("query")
    sale.set_defaults(field="instrument")
    _add_query_arguments(sale)

    probe = sub.add_parser("probe", help="Run bounded component health probes")
    selection = probe.add_mutually_exclusive_group(required=True)
    selection.add_argument("--source", choices=sorted(SOURCES))
    selection.add_argument(
        "--all",
        action="store_true",
        dest="all_sources",
        help="Probe every configured component",
    )
    probe.set_defaults(all_sources=False)
    _add_transport_arguments(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    for field_name in ("page_size", "retry_attempts"):
        if getattr(args, field_name, 1) <= 0:
            parser.error(f"--{field_name.replace('_', '-')} must be positive")
    if getattr(args, "timeout", 1) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    if getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    if hasattr(args, "query") and not args.query.strip():
        parser.error("query must not be blank")
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
