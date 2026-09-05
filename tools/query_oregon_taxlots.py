#!/usr/bin/env python3
"""Query official Oregon ArcGIS parcel and assessment sources.

The adapter keeps three independently published source components distinct
while sharing one count-driven ArcGIS retrieval core:

* City of Portland Regional Taxlots (owner-bearing tri-county view)
* Metro RLIS Taxlots (Public) (tri-county assessment, sales, and geometry)
* Oregon Water Resources Department public tax lots (13-county parcel view)

Usage:
    uv run python tools/query_oregon_taxlots.py sources
    uv run python tools/query_oregon_taxlots.py search PORTLAND \
        --source us-or-portland-regional-taxlots --field owner
    uv run python tools/query_oregon_taxlots.py parcel 21E35BB01800 \
        --source us-or-metro-rlis-public-taxlots --geometry
    uv run python tools/query_oregon_taxlots.py probe --all
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
    from tools.public_records_catalog import acquisition_result_status
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
    from public_records_catalog import acquisition_result_status
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


STATE_FIPS = "41"
STATE_CODE = "OR"
CURSOR_PREFIX = "oregon-taxlots:v1:"
CURSOR_VERSION = 1
OUTPUT_SCHEMA_VERSION = "oregon-taxlots-sources/1.0"
PROBE_SCHEMA_VERSION = "oregon-taxlots-probe/1.0"

PORTLAND_SOURCE_ID = "us-or-portland-regional-taxlots"
METRO_SOURCE_ID = "us-or-metro-rlis-public-taxlots"
OWRD_SOURCE_ID = "us-or-owrd-public-tax-lots"


@dataclass(frozen=True)
class CountyInfo:
    """Canonical Oregon county identity plus source-native selector."""

    name: str
    geoid: str
    native_value: str


OREGON_COUNTY_FIPS = {
    "Baker": "001",
    "Benton": "003",
    "Clackamas": "005",
    "Clatsop": "007",
    "Columbia": "009",
    "Coos": "011",
    "Crook": "013",
    "Curry": "015",
    "Deschutes": "017",
    "Douglas": "019",
    "Gilliam": "021",
    "Grant": "023",
    "Harney": "025",
    "Hood River": "027",
    "Jackson": "029",
    "Jefferson": "031",
    "Josephine": "033",
    "Klamath": "035",
    "Lake": "037",
    "Lane": "039",
    "Lincoln": "041",
    "Linn": "043",
    "Malheur": "045",
    "Marion": "047",
    "Morrow": "049",
    "Multnomah": "051",
    "Polk": "053",
    "Sherman": "055",
    "Tillamook": "057",
    "Umatilla": "059",
    "Union": "061",
    "Wallowa": "063",
    "Wasco": "065",
    "Washington": "067",
    "Wheeler": "069",
    "Yamhill": "071",
}
OREGON_COUNTIES = {
    name: CountyInfo(name=name, geoid=f"{STATE_FIPS}{fips}", native_value=name)
    for name, fips in OREGON_COUNTY_FIPS.items()
}


@dataclass(frozen=True)
class SourceConfig:
    """Field and lineage configuration for one official ArcGIS layer."""

    source_id: str
    name: str
    layer_url: str
    dataset_id: str
    publisher: str
    source_role: str
    object_id_field: str
    max_page_size: int
    required_fields: tuple[str, ...]
    search_fields: Mapping[str, tuple[str, ...]]
    native_id_fields: tuple[str, ...]
    alternate_id_fields: tuple[str, ...]
    account_fields: tuple[str, ...]
    owner_fields: tuple[str, ...]
    county_field: str
    county_native_values: Mapping[str, str]
    coverage: tuple[str, ...]
    warnings: tuple[str, ...]
    sentinel_field: str
    sentinel_value: str
    sentinel_county: str
    original_crs: str
    owner_name_state: str
    upstream_field: str | None = None
    verified_data_date: str | None = None

    def source_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_id=self.source_id,
            name=self.name,
            source_role=self.source_role,
            base_url=self.layer_url,
            dataset_id=self.dataset_id,
            metadata={
                "publisher": self.publisher,
                "coverage": list(self.coverage),
                "search_fields": sorted(self.search_fields),
                "owner_name_state": self.owner_name_state,
                "lineage_model": "publisher_and_upstream_county",
                "verified_data_date": self.verified_data_date,
            },
        )


_TRI_COUNTY_NATIVE = {
    "Clackamas": "C",
    "Multnomah": "M",
    "Washington": "W",
}
_OWRD_COVERAGE = (
    "Baker",
    "Benton",
    "Clackamas",
    "Curry",
    "Grant",
    "Harney",
    "Jackson",
    "Jefferson",
    "Klamath",
    "Lake",
    "Lincoln",
    "Tillamook",
    "Wheeler",
)

PORTLAND_CONFIG = SourceConfig(
    source_id=PORTLAND_SOURCE_ID,
    name="City of Portland Regional Taxlots",
    layer_url=(
        "https://www.portlandmaps.com/arcgis/rest/services/"
        "Public/Taxlots/MapServer/0"
    ),
    dataset_id="Taxlots_pdx/Regional Taxlots",
    publisher="City of Portland",
    source_role="regional_assessment_owner_sales_geometry",
    object_id_field="OBJECTID",
    max_page_size=4_000,
    required_fields=(
        "OBJECTID",
        "STATE_ID",
        "RNO",
        "OWNER1",
        "OWNER2",
        "OWNER3",
        "OWNERADDR",
        "OWNERCITY",
        "OWNERSTATE",
        "OWNERZIP",
        "SITEADDR",
        "SITECITY",
        "SITE_STATE",
        "SITEZIP",
        "LEGAL_DESC",
        "TAXCODE",
        "PROP_CODE",
        "PRPCD_DESC",
        "LANDUSE",
        "YEARBUILT",
        "BLDGSQFT",
        "BEDROOMS",
        "FLOORS",
        "UNITS",
        "MKTVALYR1",
        "LANDVAL1",
        "BLDGVAL1",
        "TOTALVAL1",
        "MKTVALYR2",
        "LANDVAL2",
        "BLDGVAL2",
        "TOTALVAL2",
        "MKTVALYR3",
        "LANDVAL3",
        "BLDGVAL3",
        "TOTALVAL3",
        "SALEDATE",
        "SALEPRICE",
        "ACC_STATUS",
        "A_T_SQFT",
        "A_T_ACRES",
        "FRONTAGE",
        "COUNTY",
        "SOURCE",
        "PROPERTYID",
        "TLID",
    ),
    search_fields={
        "parcel": ("TLID", "STATE_ID"),
        "account": ("RNO", "PROPERTYID"),
        "address": ("SITEADDR", "OWNERADDR"),
        "owner": ("OWNER1", "OWNER2", "OWNER3"),
    },
    native_id_fields=("TLID", "STATE_ID", "PROPERTYID"),
    alternate_id_fields=("STATE_ID",),
    account_fields=("RNO", "PROPERTYID"),
    owner_fields=("OWNER1", "OWNER2", "OWNER3"),
    county_field="COUNTY",
    county_native_values=_TRI_COUNTY_NATIVE,
    coverage=("Clackamas", "Multnomah", "Washington"),
    warnings=(
        "The City of Portland publishes this tri-county view; each row's SOURCE "
        "field identifies Metro or Multnomah upstream data.",
        "This layer overlaps county-derived Metro records and preserves shared "
        "lineage rather than representing independent corroboration.",
    ),
    sentinel_field="TLID",
    sentinel_value="11E25BA23600",
    sentinel_county="Clackamas",
    original_crs="EPSG:3857",
    owner_name_state="published",
    upstream_field="SOURCE",
    verified_data_date="2026-07-27",
)

METRO_CONFIG = SourceConfig(
    source_id=METRO_SOURCE_ID,
    name="Metro RLIS Taxlots (Public)",
    layer_url=(
        "https://services2.arcgis.com/McQ0OlIABe29rJJy/arcgis/rest/services/"
        "Taxlots_%28Public%29/FeatureServer/3"
    ),
    dataset_id="b3cabe5845ec47eab61c54e0c631313c/layer-3",
    publisher="Oregon Metro RLIS",
    source_role="regional_assessment_sales_geometry",
    object_id_field="FID",
    max_page_size=2_000,
    required_fields=(
        "TLID",
        "PRIMACCNUM",
        "ALTACCNUM",
        "SITEADDR",
        "SITECITY",
        "SITEZIP",
        "BLDGSQFT",
        "A_T_ACRES",
        "YEARBUILT",
        "PROP_CODE",
        "LANDUSE",
        "TAXCODE",
        "SALEDATE",
        "SALEPRICE",
        "COUNTY",
        "X_COORD",
        "Y_COORD",
        "JURIS_CITY",
        "GIS_ACRES",
        "STATECLASS",
        "ORTAXLOT",
        "LANDVAL",
        "BLDGVAL",
        "TOTALVAL",
        "ASSESSVAL",
        "FID",
        "HAS_MANY",
        "PUBLIC_OWN",
        "OWNERTYPE",
    ),
    search_fields={
        "parcel": ("TLID", "ORTAXLOT"),
        "account": ("PRIMACCNUM", "ALTACCNUM"),
        "address": ("SITEADDR",),
    },
    native_id_fields=("TLID", "ORTAXLOT", "PRIMACCNUM"),
    alternate_id_fields=("ORTAXLOT",),
    account_fields=("PRIMACCNUM", "ALTACCNUM"),
    owner_fields=(),
    county_field="COUNTY",
    county_native_values=_TRI_COUNTY_NATIVE,
    coverage=("Clackamas", "Multnomah", "Washington"),
    warnings=(
        "Metro standardizes Clackamas, Multnomah, and Washington County taxlots "
        "and does not publish personal owner-name fields in this public layer.",
        "This layer overlaps county-derived Portland records while adding public "
        "rights-of-way and Metro-specific classifications.",
    ),
    sentinel_field="TLID",
    sentinel_value="21E35BB01800",
    sentinel_county="Clackamas",
    original_crs="EPSG:2913",
    owner_name_state="not_published_by_source",
    verified_data_date="2026-04-17",
)

OWRD_CONFIG = SourceConfig(
    source_id=OWRD_SOURCE_ID,
    name="Oregon Water Resources Department Public Tax Lots",
    layer_url=(
        "https://gis.wrd.state.or.us/server/rest/services/tax/"
        "Tax_Lots_Public_View_WGS84/FeatureServer/2"
    ),
    dataset_id="289a86ef9fab481fb0a5507813dcd296/layer-2",
    publisher="Oregon Water Resources Department",
    source_role="state_aggregated_parcel_geometry_address",
    object_id_field="OBJECTID",
    max_page_size=2_000,
    required_fields=(
        "OBJECTID",
        "county_code",
        "county_name",
        "maptaxlot",
        "taxlot",
        "owner_address",
        "owner_citystatezip",
        "site_address",
        "site_citystatezip",
        "taxlot_acre",
        "meridian",
        "township",
        "township_char",
        "range",
        "range_char",
        "sctn",
        "qtr160",
        "qtr40",
        "qtr_sort",
        "tr_key",
        "trs_key",
        "trsqq_key",
        "effective_date",
        "last_update_date",
        "rec_creation_date",
    ),
    search_fields={
        "parcel": ("maptaxlot", "taxlot", "trsqq_key"),
        "address": (
            "site_address",
            "site_citystatezip",
            "owner_address",
            "owner_citystatezip",
        ),
    },
    native_id_fields=("maptaxlot", "taxlot", "trsqq_key"),
    alternate_id_fields=("taxlot", "trsqq_key"),
    account_fields=(),
    owner_fields=(),
    county_field="county_name",
    county_native_values={name: name for name in _OWRD_COVERAGE},
    coverage=_OWRD_COVERAGE,
    warnings=(
        "OWRD publishes county-contributed parcel coverage for the counties "
        "listed in source metadata; coverage and county update dates can change.",
        "The layer publishes mailing and situs address fields but no owner-name "
        "field.",
    ),
    sentinel_field="maptaxlot",
    sentinel_value="21E10DC12800",
    sentinel_county="Clackamas",
    original_crs="EPSG:2992",
    owner_name_state="not_published_by_source",
)

SOURCES: Mapping[str, SourceConfig] = {
    config.source_id: config
    for config in (PORTLAND_CONFIG, METRO_CONFIG, OWRD_CONFIG)
}


class OregonTaxlotsSelectionError(ValueError):
    """Caller selection or continuation cursor is invalid."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.SOURCE_CHANGED,
        category: str = "query",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.category = category
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=False,
            details=self.details,
        )


@dataclass(frozen=True)
class CursorState:
    """Opaque, query-bound continuation position."""

    query_fingerprint: str
    offset: int
    anchor: int
    total_count: int
    schema_fingerprint: str


@dataclass(frozen=True)
class ArcGISBatch:
    """Count-driven ArcGIS result slice and traversal diagnostics."""

    features: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    total_count: int
    schema_fingerprint: str
    pages_fetched: int
    errors: tuple[PublicRecordsError, ...] = ()


class OregonArcGISClient(ArcGISRESTClient):
    """ArcGIS client exposing metadata, count, and explicit offset pages."""

    def __init__(
        self,
        config: SourceConfig,
        *,
        page_size: int,
        timeout: float,
        minimum_interval: float,
        retry_attempts: int,
        transport: Any = None,
    ) -> None:
        kwargs: dict[str, Any] = {
            "page_size": min(page_size, config.max_page_size),
            "timeout": timeout,
            "minimum_interval": minimum_interval,
            "retry_policy": RetryPolicy(max_attempts=retry_attempts),
        }
        if transport is not None:
            kwargs["transport"] = transport
        super().__init__(config.layer_url, **kwargs)
        self.config = config

    @staticmethod
    def _mapping_payload(
        payload: Any,
        *,
        url: str,
        operation: str,
    ) -> Mapping[str, Any]:
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                f"ArcGIS {operation} response must be a JSON object",
                url=url,
                details={"response_type": type(payload).__name__},
            )
        if "error" in payload:
            raise SourceResponseError(
                f"ArcGIS returned an error during {operation}",
                url=url,
                details={"response": payload.get("error")},
            )
        return payload

    def fetch_metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(self.layer_url, params={"f": "json"})
        return self._mapping_payload(
            payload,
            url=self.layer_url,
            operation="layer metadata",
        )

    def fetch_count(self, where: str) -> int:
        payload = self._request_json(
            self.query_url,
            params={
                "where": where,
                "returnCountOnly": "true",
                "f": "json",
            },
        )
        data = self._mapping_payload(
            payload,
            url=self.query_url,
            operation="count query",
        )
        count = data.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "ArcGIS count response lacks a non-negative integer count",
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
        data = self._mapping_payload(
            payload,
            url=self.query_url,
            operation="record query",
        )
        features = data.get("features")
        if not isinstance(features, list):
            raise SourceSchemaError(
                "ArcGIS record response is missing a features array",
                url=self.query_url,
            )
        if any(not isinstance(feature, Mapping) for feature in features):
            raise SourceSchemaError(
                "ArcGIS features array contains a non-object feature",
                url=self.query_url,
            )
        return tuple(features)


def _source(source_id: str) -> SourceConfig:
    try:
        return SOURCES[source_id]
    except KeyError as error:
        raise OregonTaxlotsSelectionError(
            "unknown_source",
            f"unknown Oregon taxlot source: {source_id}",
            status=ResultStatus.UNAVAILABLE,
            details={"source_id": source_id, "known_sources": sorted(SOURCES)},
        ) from error


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    if text and re.fullmatch(r"""['"]+""", text):
        return None
    return text or None


def _sql_literal(value: Any) -> str:
    normalized = _clean_text(value)
    if not normalized:
        raise OregonTaxlotsSelectionError(
            "blank_query",
            "search or parcel value must not be blank",
            status=ResultStatus.UNAVAILABLE,
        )
    return normalized.replace("'", "''")


def _first_text(attributes: Mapping[str, Any], fields: Sequence[str]) -> str | None:
    for field_name in fields:
        value = _clean_text(attributes.get(field_name))
        if value:
            return value
    return None


def _unique_text(attributes: Mapping[str, Any], fields: Sequence[str]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for field_name in fields:
        value = _clean_text(attributes.get(field_name))
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return values


def _county_alias(value: str) -> str:
    normalized = " ".join(value.strip().split())
    normalized = re.sub(r"\s+county$", "", normalized, flags=re.IGNORECASE)
    return normalized


def _resolve_county(
    config: SourceConfig,
    value: str | None,
) -> CountyInfo | None:
    if value is None:
        return None
    normalized = _county_alias(value)
    if not normalized:
        raise OregonTaxlotsSelectionError(
            "invalid_county",
            "county must not be blank",
            status=ResultStatus.UNAVAILABLE,
        )
    digits = "".join(character for character in normalized if character.isdigit())
    matched_name: str | None = None
    if digits:
        if len(digits) == 5 and digits.startswith(STATE_FIPS):
            digits = digits[2:]
        if len(digits) == 3:
            for name, fips in OREGON_COUNTY_FIPS.items():
                if fips == digits:
                    matched_name = name
                    break
    if matched_name is None:
        for name in OREGON_COUNTIES:
            if name.casefold() == normalized.casefold():
                matched_name = name
                break
    if matched_name is None:
        for name, native_value in config.county_native_values.items():
            if native_value.casefold() == normalized.casefold():
                matched_name = name
                break
    if matched_name is None or matched_name not in config.coverage:
        raise OregonTaxlotsSelectionError(
            "county_out_of_coverage",
            f"{value!r} is not in {config.source_id} coverage",
            status=ResultStatus.UNAVAILABLE,
            details={"coverage": list(config.coverage)},
        )
    canonical = OREGON_COUNTIES[matched_name]
    return CountyInfo(
        name=canonical.name,
        geoid=canonical.geoid,
        native_value=config.county_native_values[matched_name],
    )


def _county_from_attributes(
    config: SourceConfig,
    attributes: Mapping[str, Any],
) -> CountyInfo:
    native = _clean_text(attributes.get(config.county_field))
    if not native:
        raise ValueError(f"feature lacks county field {config.county_field}")
    for name in config.coverage:
        if (
            name.casefold() == native.casefold()
            or config.county_native_values[name].casefold() == native.casefold()
        ):
            canonical = OREGON_COUNTIES[name]
            return CountyInfo(
                name=canonical.name,
                geoid=canonical.geoid,
                native_value=native,
            )
    raise ValueError(
        f"feature county {native!r} is outside declared {config.source_id} coverage"
    )


def _field_expression(field_name: str, value: str, *, contains: bool) -> str:
    if contains:
        return f"UPPER({field_name}) LIKE '%{value.upper()}%'"
    return f"{field_name} = '{value.upper()}'"


def _where(
    config: SourceConfig,
    *,
    operation: str,
    selector: str,
    search_field: str,
    county: CountyInfo | None,
) -> str:
    value = _sql_literal(selector)
    if operation == "parcel":
        field_groups = ("parcel",)
    elif search_field == "auto":
        field_groups = tuple(config.search_fields)
    else:
        if search_field not in config.search_fields:
            raise OregonTaxlotsSelectionError(
                "unsupported_search_field",
                f"{config.source_id} does not publish a searchable {search_field} field",
                status=ResultStatus.UNAVAILABLE,
                details={
                    "requested_field": search_field,
                    "supported_fields": sorted(config.search_fields),
                },
            )
        field_groups = (search_field,)

    clauses = []
    for field_group in field_groups:
        contains = field_group in {"address", "owner"}
        clauses.extend(
            _field_expression(field_name, value, contains=contains)
            for field_name in config.search_fields[field_group]
        )
    if not clauses:
        raise OregonTaxlotsSelectionError(
            "unsupported_search_field",
            f"{config.source_id} has no fields for {search_field}",
            status=ResultStatus.UNAVAILABLE,
        )
    expression = clauses[0] if len(clauses) == 1 else f"({' OR '.join(clauses)})"
    if county is not None:
        county_value = _sql_literal(county.native_value)
        expression = (
            f"({expression}) AND {config.county_field} = '{county_value}'"
        )
    return expression


def _jurisdiction(county: CountyInfo | None) -> JurisdictionMetadata:
    if county is None:
        return JurisdictionMetadata(
            jurisdiction_id=STATE_FIPS,
            name="Oregon",
            state_code=STATE_CODE,
            metadata={"state_fips": STATE_FIPS},
        )
    return JurisdictionMetadata(
        jurisdiction_id=county.geoid,
        name=f"{county.name} County, Oregon",
        state_code=STATE_CODE,
        county_fips=county.geoid,
        metadata={
            "state_fips": STATE_FIPS,
            "county_name": county.name,
            "source_native_county": county.native_value,
        },
    )


def _build_query(
    config: SourceConfig,
    *,
    operation: str,
    selector: str | None,
    search_field: str | None,
    county: CountyInfo | None,
    limit: int | None,
    cursor: str | None,
    geometry: bool,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=config.source_metadata(),
        jurisdiction=_jurisdiction(county),
        query=QueryMetadata(
            operation=operation,
            parameters={
                "selector": selector,
                "search_field": search_field,
                "county": county.name if county else None,
                "return_geometry": geometry,
            },
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "adapter_family": "oregon_arcgis_taxlots",
                "pagination": "count_driven_object_id_order",
                "access_decision": dict(access_decision or {}),
            },
        ),
    )


def _criteria_fingerprint(
    config: SourceConfig,
    *,
    operation: str,
    where: str,
    geometry: bool,
) -> str:
    return sha256_fingerprint(
        {
            "cursor_version": CURSOR_VERSION,
            "source_id": config.source_id,
            "operation": operation,
            "where": where,
            "return_geometry": geometry,
            "out_fields": "*",
            "order_by": f"{config.object_id_field} ASC",
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "q": state.query_fingerprint,
        "o": state.offset,
        "a": state.anchor,
        "n": state.total_count,
        "s": state.schema_fingerprint,
    }
    token = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii")
    return f"{CURSOR_PREFIX}{token.rstrip('=')}"


def _decode_cursor(
    cursor: str | None,
    *,
    expected_query_fingerprint: str,
) -> CursorState | None:
    if cursor is None:
        return None
    if not cursor.startswith(CURSOR_PREFIX):
        raise OregonTaxlotsSelectionError(
            "invalid_cursor",
            "cursor must be an Oregon taxlots continuation returned by this tool",
            details={"cursor": cursor},
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(f"{token}{padding}").decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OregonTaxlotsSelectionError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if not isinstance(payload, Mapping) or payload.get("v") != CURSOR_VERSION:
        raise OregonTaxlotsSelectionError(
            "invalid_cursor",
            "cursor version or payload is invalid",
        )
    observed_query = payload.get("q")
    if observed_query != expected_query_fingerprint:
        raise OregonTaxlotsSelectionError(
            "cursor_query_mismatch",
            "cursor belongs to different Oregon taxlot search parameters",
            details={
                "cursor_query_fingerprint": observed_query,
                "search_query_fingerprint": expected_query_fingerprint,
            },
        )
    values = {key: payload.get(key) for key in ("o", "a", "n")}
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in values.values()
    ):
        raise OregonTaxlotsSelectionError(
            "invalid_cursor",
            "cursor offset, anchor, and count must be non-negative integers",
        )
    schema_value = payload.get("s")
    if not isinstance(schema_value, str) or not schema_value:
        raise OregonTaxlotsSelectionError(
            "invalid_cursor",
            "cursor lacks a schema fingerprint",
        )
    if values["o"] == 0 or values["a"] == 0:
        raise OregonTaxlotsSelectionError(
            "invalid_cursor",
            "continuation cursor requires a positive offset and anchor",
        )
    return CursorState(
        query_fingerprint=str(observed_query),
        offset=values["o"],
        anchor=values["a"],
        total_count=values["n"],
        schema_fingerprint=schema_value,
    )


def _metadata_schema(
    config: SourceConfig,
    metadata: Mapping[str, Any],
) -> tuple[str, int]:
    capabilities = {
        value.strip()
        for value in str(metadata.get("capabilities") or "").split(",")
        if value.strip()
    }
    if "Query" not in capabilities:
        raise SourceSchemaError(
            "ArcGIS layer no longer advertises Query capability",
            url=config.layer_url,
            details={"capabilities": sorted(capabilities)},
        )
    advanced = metadata.get("advancedQueryCapabilities")
    if not isinstance(advanced, Mapping):
        raise SourceSchemaError(
            "ArcGIS layer lacks advanced query capability metadata",
            url=config.layer_url,
        )
    if advanced.get("supportsPagination") is not True:
        raise SourceSchemaError(
            "ArcGIS layer no longer supports result-offset pagination",
            url=config.layer_url,
        )
    if advanced.get("supportsOrderBy") is not True:
        raise SourceSchemaError(
            "ArcGIS layer no longer supports stable OBJECTID ordering",
            url=config.layer_url,
        )
    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field_definition, Mapping) for field_definition in fields
    ):
        raise SourceSchemaError(
            "ArcGIS layer field declarations are missing or malformed",
            url=config.layer_url,
        )
    field_names = {
        str(field_definition.get("name"))
        for field_definition in fields
        if field_definition.get("name")
    }
    missing = sorted(set(config.required_fields) - field_names)
    if missing:
        raise SourceSchemaError(
            "ArcGIS layer is missing fields required by the Oregon normalizer",
            url=config.layer_url,
            details={"missing_fields": missing},
        )
    oid_definition = next(
        (
            field_definition
            for field_definition in fields
            if field_definition.get("name") == config.object_id_field
        ),
        None,
    )
    if (
        oid_definition is None
        or oid_definition.get("type") != "esriFieldTypeOID"
    ):
        raise SourceSchemaError(
            "Configured ArcGIS ordering field is no longer the layer OID",
            url=config.layer_url,
            details={"object_id_field": config.object_id_field},
        )
    maximum = metadata.get("maxRecordCount")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        raise SourceSchemaError(
            "ArcGIS layer lacks a positive maxRecordCount",
            url=config.layer_url,
            details={"maxRecordCount": maximum},
        )
    declared = arcgis_declared_schema(fields)
    return schema_fingerprint(declared), min(maximum, config.max_page_size)


def _feature_attributes(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise SourceSchemaError(
            "ArcGIS feature lacks an attributes object",
            url="source-feature",
        )
    return attributes


def _feature_oid(config: SourceConfig, feature: Mapping[str, Any]) -> int:
    value = _feature_attributes(feature).get(config.object_id_field)
    if isinstance(value, bool):
        raise SourceSchemaError(
            "ArcGIS feature OID must be an integer",
            url=config.layer_url,
        )
    try:
        oid = int(value)
    except (TypeError, ValueError) as error:
        raise SourceSchemaError(
            "ArcGIS feature lacks a usable OID",
            url=config.layer_url,
            details={"object_id_field": config.object_id_field, "value": value},
        ) from error
    if oid <= 0:
        raise SourceSchemaError(
            "ArcGIS feature OID must be positive",
            url=config.layer_url,
            details={"value": oid},
        )
    return oid


def _pagination_error(
    code: str,
    message: str,
    **details: Any,
) -> PublicRecordsError:
    return PublicRecordsError(
        code=code,
        message=message,
        category="pagination",
        retryable=False,
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
    criteria_fingerprint = _criteria_fingerprint(
        config,
        operation=operation,
        where=where,
        geometry=return_geometry,
    )
    cursor_state = _decode_cursor(
        cursor,
        expected_query_fingerprint=criteria_fingerprint,
    )
    metadata = client.fetch_metadata()
    current_schema_fingerprint, server_page_size = _metadata_schema(config, metadata)
    if (
        cursor_state is not None
        and cursor_state.schema_fingerprint != current_schema_fingerprint
    ):
        raise OregonTaxlotsSelectionError(
            "cursor_schema_mismatch",
            "ArcGIS schema changed since the continuation cursor was issued",
            details={
                "cursor_schema_fingerprint": cursor_state.schema_fingerprint,
                "current_schema_fingerprint": current_schema_fingerprint,
            },
        )

    start_count = client.fetch_count(where)
    offset = cursor_state.offset if cursor_state else 0
    errors: list[PublicRecordsError] = []
    if offset > start_count:
        raise OregonTaxlotsSelectionError(
            "cursor_out_of_range",
            "cursor offset exceeds the source's current result count",
            details={"cursor_offset": offset, "source_count": start_count},
        )

    last_oid: int | None = None
    if cursor_state is not None:
        boundary = client.fetch_page(
            where=where,
            offset=offset - 1,
            record_count=1,
            out_fields=config.object_id_field,
            return_geometry=False,
        )
        if len(boundary) != 1:
            raise OregonTaxlotsSelectionError(
                "cursor_snapshot_changed",
                "continuation boundary no longer exists at the cursor offset",
                details={"cursor_offset": offset, "boundary_rows": len(boundary)},
            )
        observed_anchor = _feature_oid(config, boundary[0])
        if observed_anchor != cursor_state.anchor:
            raise OregonTaxlotsSelectionError(
                "cursor_snapshot_changed",
                "ArcGIS result ordering changed at the continuation boundary",
                details={
                    "expected_anchor": cursor_state.anchor,
                    "observed_anchor": observed_anchor,
                    "cursor_offset": offset,
                },
            )
        last_oid = cursor_state.anchor
        if cursor_state.total_count != start_count:
            errors.append(
                _pagination_error(
                    "count_changed_since_cursor",
                    "ArcGIS result count changed since the cursor was issued",
                    cursor_count=cursor_state.total_count,
                    current_count=start_count,
                )
            )

    page_size = min(
        int(getattr(client, "page_size", server_page_size)),
        server_page_size,
    )
    collected: list[Mapping[str, Any]] = []
    seen_oids: set[int] = set()
    pages_fetched = 0
    safe_to_resume = not errors

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
                    "ArcGIS returned an empty page before its reported count was reached",
                    offset=offset,
                    snapshot_count=start_count,
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
                    offset=offset,
                )
            )
            safe_to_resume = False
            break

        page_valid = True
        for feature in page:
            try:
                oid = _feature_oid(config, feature)
            except PublicRecordsHTTPError as error:
                errors.append(error.to_contract_error())
                safe_to_resume = False
                page_valid = False
                break
            if oid in seen_oids or (last_oid is not None and oid <= last_oid):
                errors.append(
                    _pagination_error(
                        "pagination_repeat_or_reorder",
                        "ArcGIS repeated or reordered a feature during traversal",
                        object_id=oid,
                        previous_object_id=last_oid,
                        offset=offset,
                    )
                )
                safe_to_resume = False
                page_valid = False
                break
            seen_oids.add(oid)
            last_oid = oid
            collected.append(feature)
        if not page_valid:
            break
        offset += len(page)
        # A short page is not terminal when the count snapshot says rows remain.

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
                "ArcGIS result count changed during pagination",
                initial_count=start_count,
                final_count=end_count,
            )
        )
        safe_to_resume = False

    next_cursor = None
    if (
        safe_to_resume
        and collected
        and len(collected) >= limit
        and offset < end_count
        and last_oid is not None
    ):
        next_cursor = _encode_cursor(
            CursorState(
                query_fingerprint=criteria_fingerprint,
                offset=offset,
                anchor=last_oid,
                total_count=end_count,
                schema_fingerprint=current_schema_fingerprint,
            )
        )
    return ArcGISBatch(
        features=tuple(collected),
        next_cursor=next_cursor,
        total_count=end_count,
        schema_fingerprint=current_schema_fingerprint,
        pages_fetched=pages_fetched,
        errors=tuple(errors),
    )


def _arcgis_date(value: Any) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return (
                datetime.fromtimestamp(value / 1000, tz=timezone.utc)
                .date()
                .isoformat()
            )
        except (OverflowError, OSError, ValueError):
            return None
    text = _clean_text(value)
    if not text:
        return None
    for date_format in (
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    if re.fullmatch(r"\d{6}", text):
        try:
            return datetime.strptime(text, "%Y%m").strftime("%Y-%m")
        except ValueError:
            return text
    if re.fullmatch(r"\d{4}", text):
        return text
    return text


def _address(
    *,
    raw: Any,
    city: Any = None,
    state: Any = None,
    postal_code: Any = None,
) -> dict[str, Any]:
    return {
        "raw": _clean_text(raw),
        "city": _clean_text(city),
        "state": _clean_text(state),
        "postal_code": _clean_text(postal_code),
        "country": "US",
    }


_CITY_STATE_ZIP = re.compile(
    r"^(?P<city>.*?)[,\s]+(?P<state>[A-Z]{2})\s+(?P<zip>\d{5}(?:-\d{4})?)$",
    re.IGNORECASE,
)


def _combined_address(street: Any, city_state_zip: Any) -> dict[str, Any]:
    street_text = _clean_text(street)
    combined = _clean_text(city_state_zip)
    city = state = postal_code = None
    if combined:
        match = _CITY_STATE_ZIP.match(combined)
        if match:
            city = _clean_text(match.group("city"))
            state = match.group("state").upper()
            postal_code = match.group("zip")
    raw = " ".join(value for value in (street_text, combined) if value) or None
    return _address(
        raw=raw,
        city=city,
        state=state,
        postal_code=postal_code,
    )


def _owners(
    attributes: Mapping[str, Any],
    fields: Sequence[str],
) -> list[dict[str, Any]]:
    result = []
    seen: set[str] = set()
    for index, field_name in enumerate(fields):
        raw_name = _clean_text(attributes.get(field_name))
        if not raw_name or raw_name.casefold() in seen:
            continue
        seen.add(raw_name.casefold())
        result.append(
            {
                "raw_name": raw_name,
                "role": (
                    "primary_assessor_owner"
                    if index == 0
                    else "additional_assessor_owner"
                ),
                "assertion_type": "assessment_roll",
                "confidence": "high",
            }
        )
    return result


def _source_lineage(
    config: SourceConfig,
    county: CountyInfo,
    attributes: Mapping[str, Any],
) -> dict[str, Any]:
    native_source = (
        _clean_text(attributes.get(config.upstream_field))
        if config.upstream_field
        else None
    )
    return {
        "publisher": config.publisher,
        "native_source": native_source or config.publisher,
        "upstream_custodian": f"{county.name} County Assessor",
        "shared_origin": "county_assessor_parcel_data",
    }


def _base_record(
    config: SourceConfig,
    feature: Mapping[str, Any],
    *,
    response_schema_fingerprint: str,
) -> tuple[dict[str, Any], Mapping[str, Any], CountyInfo]:
    attributes = _feature_attributes(feature)
    county = _county_from_attributes(config, attributes)
    native_id = _first_text(attributes, config.native_id_fields)
    if not native_id:
        raise ValueError(
            f"{config.source_id} feature lacks a stable parcel identifier"
        )
    aliases = [
        value
        for value in _unique_text(attributes, config.alternate_id_fields)
        if value != native_id
    ]
    accounts = _unique_text(attributes, config.account_fields)
    record = {
        "canonical_ref": canonical_property_ref(
            config.source_id,
            county.geoid,
            "parcel",
            native_id,
        ),
        "source_id": config.source_id,
        "source_url": config.layer_url,
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": county.name,
            "county_geoid": county.geoid,
            "source_native_county": county.native_value,
        },
        "native_parcel_id": native_id,
        "alternate_parcel_ids": aliases,
        "assessment_account_ids": accounts,
        "object_id": _feature_oid(config, feature),
        "source_record_id": str(_feature_oid(config, feature)),
        "owners": _owners(attributes, config.owner_fields),
        "owner_visibility": {
            "state": config.owner_name_state,
            "owner_name_fields": list(config.owner_fields),
        },
        "source_lineage": _source_lineage(config, county, attributes),
        "response_schema_fingerprint": response_schema_fingerprint,
        "adapter_schema_fingerprint": sha256_fingerprint(
            {
                "normalization_version": 1,
                "source_id": config.source_id,
                "required_fields": list(config.required_fields),
                "native_id_fields": list(config.native_id_fields),
                "search_fields": {
                    key: list(value)
                    for key, value in sorted(config.search_fields.items())
                },
            }
        ),
        "snapshot_complete": True,
        "raw_attributes": dict(attributes),
    }
    return record, attributes, county


def _geometry(
    record: dict[str, Any],
    feature: Mapping[str, Any],
    *,
    requested: bool,
) -> None:
    if requested and isinstance(feature.get("geometry"), Mapping):
        record["geometry"] = dict(feature["geometry"])
        record["geometry_format"] = "esri_json"
        record["geometry_crs"] = "EPSG:4326"
        record["geometry_disclaimer"] = (
            "Source-provided taxlot geometry was requested from ArcGIS in WGS84."
        )


def _normalize_portland(
    feature: Mapping[str, Any],
    *,
    schema_fingerprint_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    record, attributes, _county = _base_record(
        PORTLAND_CONFIG,
        feature,
        response_schema_fingerprint=schema_fingerprint_value,
    )
    record["situs_address"] = _address(
        raw=attributes.get("SITEADDR"),
        city=attributes.get("SITECITY"),
        state=attributes.get("SITE_STATE") or STATE_CODE,
        postal_code=attributes.get("SITEZIP"),
    )
    record["mailing_address"] = _address(
        raw=attributes.get("OWNERADDR"),
        city=attributes.get("OWNERCITY"),
        state=attributes.get("OWNERSTATE"),
        postal_code=attributes.get("OWNERZIP"),
    )
    history = []
    for index in (1, 2, 3):
        year = _clean_text(attributes.get(f"MKTVALYR{index}"))
        land = attributes.get(f"LANDVAL{index}")
        improvements = attributes.get(f"BLDGVAL{index}")
        total = attributes.get(f"TOTALVAL{index}")
        if all(value in (None, "") for value in (year, land, improvements, total)):
            continue
        if year is None and all(
            value in (None, "", 0, 0.0)
            for value in (land, improvements, total)
        ):
            continue
        history.append(
            {
                "tax_year": year,
                "land_value": land,
                "improvement_value": improvements,
                "parcel_value": total,
                "currency": "USD",
            }
        )
    if history:
        record["assessment_history"] = history
        record["assessment"] = history[0]
        record["tax_year"] = history[0].get("tax_year")
    sale_date = _arcgis_date(attributes.get("SALEDATE"))
    if sale_date or attributes.get("SALEPRICE") not in (None, ""):
        record["last_sale"] = {
            "sale_date": sale_date,
            "consideration": attributes.get("SALEPRICE"),
            "currency": "USD",
        }
    record["legal_description_raw"] = _clean_text(attributes.get("LEGAL_DESC"))
    record["property_class"] = {
        "code": _clean_text(attributes.get("PROP_CODE")),
        "description": _clean_text(attributes.get("PRPCD_DESC")),
        "land_use": _clean_text(attributes.get("LANDUSE")),
    }
    record["physical_characteristics"] = {
        "year_built": attributes.get("YEARBUILT"),
        "building_square_feet": attributes.get("BLDGSQFT"),
        "bedrooms": attributes.get("BEDROOMS"),
        "floors": attributes.get("FLOORS"),
        "units": attributes.get("UNITS"),
        "assessor_acres": attributes.get("A_T_ACRES"),
        "frontage": attributes.get("FRONTAGE"),
    }
    record["tax_code"] = _clean_text(attributes.get("TAXCODE"))
    record["account_status"] = _clean_text(attributes.get("ACC_STATUS"))
    _geometry(record, feature, requested=geometry_requested)
    return record


def _normalize_metro(
    feature: Mapping[str, Any],
    *,
    schema_fingerprint_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    record, attributes, _county = _base_record(
        METRO_CONFIG,
        feature,
        response_schema_fingerprint=schema_fingerprint_value,
    )
    record["situs_address"] = _address(
        raw=attributes.get("SITEADDR"),
        city=attributes.get("SITECITY"),
        state=STATE_CODE,
        postal_code=attributes.get("SITEZIP"),
    )
    assessment = {
        "land_value": attributes.get("LANDVAL"),
        "improvement_value": attributes.get("BLDGVAL"),
        "parcel_value": attributes.get("TOTALVAL"),
        "assessed_value": attributes.get("ASSESSVAL"),
        "assessment_class": _clean_text(attributes.get("STATECLASS")),
        "currency": "USD",
    }
    if any(value not in (None, "") for value in assessment.values()):
        record["assessment"] = assessment
    sale_date = _arcgis_date(attributes.get("SALEDATE"))
    if sale_date or attributes.get("SALEPRICE") not in (None, ""):
        record["last_sale"] = {
            "sale_date": sale_date,
            "consideration": attributes.get("SALEPRICE"),
            "currency": "USD",
        }
    record["property_class"] = {
        "code": _clean_text(attributes.get("PROP_CODE")),
        "state_class": _clean_text(attributes.get("STATECLASS")),
        "land_use": _clean_text(attributes.get("LANDUSE")),
    }
    record["physical_characteristics"] = {
        "year_built": attributes.get("YEARBUILT"),
        "building_square_feet": attributes.get("BLDGSQFT"),
        "assessor_acres": attributes.get("A_T_ACRES"),
        "gis_acres": attributes.get("GIS_ACRES"),
    }
    record["public_ownership"] = {
        "public_owned": attributes.get("PUBLIC_OWN"),
        "owner_type": _clean_text(attributes.get("OWNERTYPE")),
    }
    record["tax_code"] = _clean_text(attributes.get("TAXCODE"))
    record["jurisdiction_city"] = _clean_text(attributes.get("JURIS_CITY"))
    _geometry(record, feature, requested=geometry_requested)
    return record


def _normalize_owrd(
    feature: Mapping[str, Any],
    *,
    schema_fingerprint_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    record, attributes, _county = _base_record(
        OWRD_CONFIG,
        feature,
        response_schema_fingerprint=schema_fingerprint_value,
    )
    record["situs_address"] = _combined_address(
        attributes.get("site_address"),
        attributes.get("site_citystatezip"),
    )
    record["mailing_address"] = _combined_address(
        attributes.get("owner_address"),
        attributes.get("owner_citystatezip"),
    )
    record["parcel_acres"] = attributes.get("taxlot_acre")
    record["plss"] = {
        "meridian": attributes.get("meridian"),
        "township": attributes.get("township"),
        "township_direction": attributes.get("township_char"),
        "range": attributes.get("range"),
        "range_direction": attributes.get("range_char"),
        "section": attributes.get("sctn"),
        "quarter_160": attributes.get("qtr160"),
        "quarter_40": attributes.get("qtr40"),
        "quarter_sort": attributes.get("qtr_sort"),
        "township_range_key": attributes.get("tr_key"),
        "township_range_section_key": attributes.get("trs_key"),
        "township_range_section_quarter_key": attributes.get("trsqq_key"),
    }
    record["effective_date"] = _arcgis_date(attributes.get("effective_date"))
    record["source_last_updated"] = _arcgis_date(
        attributes.get("last_update_date")
    )
    record["source_revised_date"] = record["source_last_updated"]
    record["record_created_date"] = _arcgis_date(
        attributes.get("rec_creation_date")
    )
    _geometry(record, feature, requested=geometry_requested)
    return record


def _normalize_feature(
    config: SourceConfig,
    feature: Mapping[str, Any],
    *,
    schema_fingerprint_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    if config.source_id == PORTLAND_SOURCE_ID:
        return _normalize_portland(
            feature,
            schema_fingerprint_value=schema_fingerprint_value,
            geometry_requested=geometry_requested,
        )
    if config.source_id == METRO_SOURCE_ID:
        return _normalize_metro(
            feature,
            schema_fingerprint_value=schema_fingerprint_value,
            geometry_requested=geometry_requested,
        )
    if config.source_id == OWRD_SOURCE_ID:
        return _normalize_owrd(
            feature,
            schema_fingerprint_value=schema_fingerprint_value,
            geometry_requested=geometry_requested,
        )
    raise ValueError(f"no normalizer configured for {config.source_id}")


def _client(
    args: argparse.Namespace,
    config: SourceConfig,
    access_decision: Mapping[str, Any] | None = None,
) -> OregonArcGISClient:
    limits = (
        access_decision.get("limits") or {}
        if access_decision is not None
        else {}
    )
    reviewed_page_size = limits.get("maximum_page_size")
    page_size = min(args.page_size, config.max_page_size)
    if reviewed_page_size is not None:
        page_size = min(page_size, int(reviewed_page_size))
    reviewed_interval = float(
        limits.get("minimum_interval_seconds") or 0
    )
    return OregonArcGISClient(
        config,
        page_size=page_size,
        timeout=args.timeout,
        minimum_interval=max(args.minimum_interval, reviewed_interval),
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
    except Exception:
        # Search logging is useful provenance, but an unavailable local tracker
        # must not replace a successfully retrieved official-source result.
        pass


def _selection_failure(
    query: PublicRecordsQuery,
    error: OregonTaxlotsSelectionError,
    *,
    warnings: Sequence[str],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=warnings,
    )


def _access_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
    *,
    warnings: Sequence[str],
) -> PublicRecordsResult:
    """Return the catalog's acquisition decision as a structured result."""

    return PublicRecordsResult.failure(
        query,
        ResultStatus(acquisition_result_status(decision)),
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code")
                    or "acquisition_route_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or "Catalogued acquisition route is unavailable"
                ),
                category="access",
                retryable=False,
                details=dict(decision),
            )
        ],
        warnings=warnings,
    )


def _access_mismatch_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
    *,
    warnings: Sequence[str],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code="catalog_decision_source_mismatch",
                message="Catalog decision belongs to another source component",
                category="access",
                retryable=False,
                details={
                    "decision_source_id": decision.get("source_id"),
                    "query_source_id": query.source.source_id,
                },
            )
        ],
        warnings=warnings,
    )


def _enforce_access_decision(
    query: PublicRecordsQuery,
    access_decision: Mapping[str, Any] | None,
    *,
    warnings: Sequence[str],
) -> PublicRecordsResult | None:
    if access_decision is None:
        return None
    decision_source_id = access_decision.get("source_id")
    if (
        decision_source_id is not None
        and decision_source_id != query.source.source_id
    ):
        return _access_mismatch_failure(
            query,
            access_decision,
            warnings=warnings,
        )
    if not access_decision.get("allowed", False):
        return _access_failure(
            query,
            access_decision,
            warnings=warnings,
        )
    return None


def _normalization_result(
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
            records.append(
                _normalize_feature(
                    config,
                    feature,
                    schema_fingerprint_value=batch.schema_fingerprint,
                    geometry_requested=geometry_requested,
                )
            )
        except (PublicRecordsHTTPError, TypeError, ValueError) as error:
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
    warnings = config.warnings
    if errors:
        status = ResultStatus.PARTIAL if records else ResultStatus.SOURCE_CHANGED
        return PublicRecordsResult.failure(
            query,
            status,
            errors,
            records=records,
            next_cursor=batch.next_cursor if records else None,
            warnings=warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
        warnings=warnings,
    )


def _execute_records(
    args: argparse.Namespace,
    *,
    client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult:
    config = _source(args.source)
    county = _resolve_county(config, getattr(args, "county", None))
    operation = args.command
    selector = args.query
    search_field = "parcel" if operation == "parcel" else args.field
    query = _build_query(
        config,
        operation=operation,
        selector=selector,
        search_field=search_field,
        county=county,
        limit=args.limit,
        cursor=args.cursor,
        geometry=args.geometry,
        access_decision=access_decision,
    )
    access_failure = _enforce_access_decision(
        query,
        access_decision,
        warnings=config.warnings,
    )
    if access_failure is not None:
        _best_effort_log(query, config.source_id, access_failure)
        return access_failure
    try:
        where = _where(
            config,
            operation=operation,
            selector=selector,
            search_field=search_field,
            county=county,
        )
        active_client = client or _client(args, config, access_decision)
        batch = _fetch_batch(
            active_client,
            config,
            operation=operation,
            where=where,
            limit=args.limit,
            cursor=args.cursor,
            return_geometry=args.geometry,
        )
        result = _normalization_result(
            query,
            config,
            batch,
            geometry_requested=args.geometry,
        )
    except OregonTaxlotsSelectionError as error:
        result = _selection_failure(query, error, warnings=config.warnings)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=config.warnings)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=config.warnings,
        )
    _best_effort_log(query, config.source_id, result)
    return result


def _execute_probe(
    args: argparse.Namespace,
    config: SourceConfig,
    *,
    client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult:
    county = _resolve_county(config, config.sentinel_county)
    query = _build_query(
        config,
        operation="probe",
        selector=config.sentinel_value,
        search_field="parcel",
        county=county,
        limit=1,
        cursor=None,
        geometry=False,
        access_decision=access_decision,
    )
    access_failure = _enforce_access_decision(
        query,
        access_decision,
        warnings=config.warnings,
    )
    if access_failure is not None:
        _best_effort_log(query, config.source_id, access_failure)
        return access_failure
    try:
        active_client = client or _client(args, config, access_decision)
        metadata = active_client.fetch_metadata()
        schema_fingerprint_value, _page_size = _metadata_schema(config, metadata)
        total_count = active_client.fetch_count("1=1")
        where = _where(
            config,
            operation="parcel",
            selector=config.sentinel_value,
            search_field="parcel",
            county=county,
        )
        sentinel_count = active_client.fetch_count(where)
        if sentinel_count <= 0:
            raise SourceSchemaError(
                "Configured Oregon taxlot sentinel was not found",
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
                "Oregon taxlot sentinel query did not return one record",
                url=config.layer_url,
                details={"returned": len(page), "sentinel_count": sentinel_count},
            )
        sentinel = _normalize_feature(
            config,
            page[0],
            schema_fingerprint_value=schema_fingerprint_value,
            geometry_requested=False,
        )
        result = PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": config.source_id,
                    "component_total_count": total_count,
                    "sentinel_count": sentinel_count,
                    "schema_fingerprint": schema_fingerprint_value,
                    "layer_name": metadata.get("name"),
                    "max_record_count": metadata.get("maxRecordCount"),
                    "sentinel": sentinel,
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
                "owner_name_state": config.owner_name_state,
                "coverage": [
                    {
                        "county_name": name,
                        "county_geoid": OREGON_COUNTIES[name].geoid,
                        "source_native_county": config.county_native_values[name],
                    }
                    for name in config.coverage
                ],
                "warnings": list(config.warnings),
            }
            for config in SOURCES.values()
        ],
    }


def _all_probe_payload(
    args: argparse.Namespace,
) -> dict[str, Any]:
    component_results = [
        _execute_probe(args, config).to_dict() for config in SOURCES.values()
    ]
    successful = sum(
        result["status"] in {"ok", "no_results"} for result in component_results
    )
    if successful == len(component_results):
        status = "ok"
    elif successful:
        status = "partial"
    else:
        status = "unavailable"
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "status": status,
        "components": component_results,
    }


def execute(
    args: argparse.Namespace,
    *,
    client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute a local source listing, record query, or bounded probe."""

    if args.command == "sources":
        return _sources_payload()
    if args.command == "probe":
        if args.all_sources:
            return _all_probe_payload(args)
        return _execute_probe(
            args,
            _source(args.source),
            client=client,
            access_decision=access_decision,
        )
    return _execute_records(
        args,
        client=client,
        access_decision=access_decision,
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


def _payload(value: PublicRecordsResult | Mapping[str, Any]) -> dict[str, Any]:
    return value.to_dict() if isinstance(value, PublicRecordsResult) else dict(value)


def _emit(value: PublicRecordsResult | Mapping[str, Any], args: argparse.Namespace) -> None:
    payload = _payload(value)
    output = getattr(args, "output", None)
    if output:
        destination = Path(output).expanduser()
        _atomic_json_write(destination, payload)
        records = payload.get("records")
        count = len(records) if isinstance(records, list) else len(
            payload.get("components", payload.get("sources", []))
        )
        print(
            f"{count} results (Oregon taxlots {args.command}) saved to {destination}"
        )
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if args.command == "sources":
        print(f"Oregon taxlot sources: {len(payload['sources'])}")
        for source in payload["sources"]:
            print(
                f"  {source['source_id']} | "
                f"{', '.join(source['search_fields'])}"
            )
        return
    if args.command == "probe" and args.all_sources:
        print(f"Oregon taxlot probes: {payload['status']}")
        for component in payload["components"]:
            print(
                f"  {component['query']['source']['source_id']} | "
                f"{component['status']}"
            )
        return
    records = payload.get("records", [])
    print(
        f"Oregon taxlots {args.command}: {payload.get('status')} "
        f"({len(records)} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in records:
        print(
            f"  {record.get('native_parcel_id') or record.get('record_kind')} | "
            f"{record.get('jurisdiction', {}).get('county_name', '?')}"
        )
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
        help="Exact publisher-scoped source ID",
    )
    parser.add_argument(
        "--county",
        help="Optional Oregon county name, 3-digit county FIPS, or 5-digit GEOID",
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
        description="Query official Oregon ArcGIS taxlot source components"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser("sources", help="List configured source capabilities")
    add_output_args(sources)

    search = sub.add_parser("search", help="Search one explicitly selected source")
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=("auto", "parcel", "account", "address", "owner"),
        default="auto",
        help="Source field family; auto fans across fields published by the source",
    )
    _add_query_arguments(search)

    parcel = sub.add_parser("parcel", help="Look up an exact parcel identifier")
    parcel.add_argument("query")
    parcel.set_defaults(field="parcel")
    _add_query_arguments(parcel)

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
        value = getattr(args, field_name, 1)
        if value <= 0:
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
