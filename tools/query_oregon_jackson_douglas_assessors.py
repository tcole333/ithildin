#!/usr/bin/env python3
"""Query official Jackson and Douglas County, Oregon assessor parcel layers.

The two counties publish distinct ArcGIS FeatureServer components. This
adapter shares transport and pagination mechanics while retaining each
publisher's native identifiers, field meanings, source CRS, item metadata,
and complementary products.

Usage:
    uv run python tools/query_oregon_jackson_douglas_assessors.py sources
    uv run python tools/query_oregon_jackson_douglas_assessors.py owner \
        "O & C REVESTED GRANT" \
        --source us-or-douglas-county-assessor-parcels
    uv run python tools/query_oregon_jackson_douglas_assessors.py parcel \
        30-2E-100 --source us-or-jackson-county-assessor-taxlots --geometry
    uv run python tools/query_oregon_jackson_douglas_assessors.py probe --all
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
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
    from output_util import add_output_args, write_output
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
JACKSON_GEOID = "41029"
DOUGLAS_GEOID = "41019"

JACKSON_SOURCE_ID = "us-or-jackson-county-assessor-taxlots"
DOUGLAS_SOURCE_ID = "us-or-douglas-county-assessor-parcels"
DOUGLAS_BULK_SOURCE_ID = "us-or-douglas-county-assessor-data-products"
JACKSON_DATA_REQUEST_SOURCE_ID = "us-or-jackson-county-assessor-data-request"
JACKSON_MAPS_SOURCE_ID = "us-or-jackson-county-assessment-maps"
JACKSON_RECORDER_SOURCE_ID = "us-or-jackson-helion-recorder"

JACKSON_SERVICE_URL = (
    "https://jcportal.jacksoncountyor.gov/server/rest/services/"
    "Property/Taxlots/FeatureServer"
)
JACKSON_LAYER_URL = f"{JACKSON_SERVICE_URL}/2"
JACKSON_ITEM_ID = "30a37e5d29a44710ae760acf13c06724"
JACKSON_PORTAL_ITEM_API_URL = (
    "https://jcportal.jacksoncountyor.gov/portal/sharing/rest/content/items/"
    f"{JACKSON_ITEM_ID}"
)
JACKSON_PORTAL_ITEM_PAGE_URL = (
    "https://jcportal.jacksoncountyor.gov/portal/home/item.html?id="
    f"{JACKSON_ITEM_ID}"
)

DOUGLAS_SERVICE_URL = (
    "https://gis.co.douglas.or.us/server/rest/services/"
    "Parcel/Parcels/FeatureServer"
)
DOUGLAS_LAYER_URL = f"{DOUGLAS_SERVICE_URL}/0"
DOUGLAS_ITEM_ID = "5eadf9aa1f8c485d8f04d54e7206d937"
DOUGLAS_PORTAL_ITEM_API_URL = (
    "https://gis.co.douglas.or.us/portal/sharing/rest/content/items/"
    f"{DOUGLAS_ITEM_ID}"
)
DOUGLAS_PORTAL_ITEM_PAGE_URL = (
    "https://gis.co.douglas.or.us/portal/home/item.html?id="
    f"{DOUGLAS_ITEM_ID}"
)

DOUGLAS_BULK_URL = (
    "https://fir.co.douglas.or.us/FileRepository/ASSESSOR/"
    "Subscriptions/Subscriptions.pdf"
)
JACKSON_PUBLIC_RECORDS_REQUEST_URL = (
    "https://jacksoncountyor.gov/Document%20Center/Departments/"
    "Counsel/Public%20Records%20Request.pdf"
)
JACKSON_ASSESSMENT_MAPS_URL = (
    "https://apps.jacksoncountyor.gov/asmtmaps/Home/Help"
)
JACKSON_JIM_GUIDE_URL = (
    "https://apps.jacksoncountyor.gov/gis/helpdocs/JimInstructions.pdf"
)
JACKSON_RECORDER_URL = (
    "https://apps.jacksoncountyor.gov/DigitalResearchRoomPublic/"
)

OUTPUT_SCHEMA_VERSION = "oregon-jackson-douglas-assessors/1.0"
PROBE_SCHEMA_VERSION = "oregon-jackson-douglas-assessor-probe/1.0"
CURSOR_PREFIX = "oregon-jackson-douglas-assessors:v1:"
CURSOR_VERSION = 1


@dataclass(frozen=True)
class SearchColumn:
    """One source-native search column and its comparison behavior."""

    name: str
    contains: bool = False
    numeric: bool = False


@dataclass(frozen=True)
class SourceConfig:
    """Verified identity, schema, search, and provenance for one county layer."""

    source_id: str
    name: str
    publisher: str
    county_name: str
    county_geoid: str
    layer_url: str
    service_url: str
    layer_id: int
    service_item_id: str
    portal_item_api_url: str
    portal_item_page_url: str
    expected_layer_name: str
    object_id_field: str
    source_wkid: int
    max_page_size: int
    required_fields: tuple[str, ...]
    native_id_fields: tuple[str, ...]
    search_fields: Mapping[str, tuple[SearchColumn, ...]]
    source_role: str
    component_scope: str
    cadence_fact: str
    sentinel_field: str
    sentinel_value: str
    expected_schema_fingerprint: str
    baseline_count: int
    baseline_observed_at: str
    baseline_item_created: str
    baseline_item_modified: str
    warnings: tuple[str, ...]

    @property
    def original_crs(self) -> str:
        return f"EPSG:{self.source_wkid}"

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
                "record_kind": "parcel",
                "layer_id": self.layer_id,
                "source_crs": self.original_crs,
                "component_scope": self.component_scope,
                "cadence_fact": self.cadence_fact,
                "portal_item_url": self.portal_item_page_url,
            },
        )


JACKSON_FIELDS = (
    "OBJECTID",
    "MAPNUMBER",
    "MAPNUM",
    "TM_MAPLOT",
    "ACCOUNT",
    "LOTTYPE",
    "FEEOWNER",
    "CONTRACT",
    "INCAREOF",
    "ADDRESS1",
    "ADDRESS2",
    "CITY",
    "STATE",
    "ZIPCODE",
    "COMMSQFT",
    "ACREAGE",
    "IMPVALUE",
    "LANDVALUE",
    "LOTDEPTH",
    "LOTWIDTH",
    "PROPCLASS",
    "ADDRESSNUM",
    "STREETNAME",
    "BUILDCODE",
    "YEARBLT",
    "TAXCODE",
    "ASSESSIMP",
    "ASSESSLAND",
    "MAINTENANC",
    "SCHEDULECO",
    "NEIGHBORHO",
    "OWNERSORT",
    "ADDSORT",
    "TRSSORT",
    "SITEADD",
    "TAXLOT",
    "Shape__Area",
    "Shape__Length",
    "GIS_AREA",
    "MAPLOT",
)

DOUGLAS_FIELDS = (
    "TAXID",
    "PROP_ID",
    "NAME",
    "ADDR1",
    "ADDR2",
    "ADDR3",
    "CSZ",
    "ACCT_ACREAGE",
    "ALT_ACCTNUM",
    "ASSD_VALUE",
    "LAND_MKT_VALUE",
    "MARKET_VALUE",
    "IMPRV_VALUE",
    "PROPCLASS",
    "LEGAL",
    "INST_NO",
    "LOC_CODE",
    "MAINTAREA",
    "NBHDCODE",
    "OWNER_ID",
    "CODEAREA",
    "BLOCK",
    "LOT",
    "SPECINTEREST",
    "MTLACREAGE",
    "TotalAcreage",
    "SaleDate",
    "SitusAddress",
    "SitusCSZ",
    "OBJECTID",
)

JACKSON = SourceConfig(
    source_id=JACKSON_SOURCE_ID,
    name="Jackson County Assessor Taxlots",
    publisher="Jackson County Assessor and Jackson County GIS",
    county_name="Jackson County, Oregon",
    county_geoid=JACKSON_GEOID,
    layer_url=JACKSON_LAYER_URL,
    service_url=JACKSON_SERVICE_URL,
    layer_id=2,
    service_item_id=JACKSON_ITEM_ID,
    portal_item_api_url=JACKSON_PORTAL_ITEM_API_URL,
    portal_item_page_url=JACKSON_PORTAL_ITEM_PAGE_URL,
    expected_layer_name="Taxlots",
    object_id_field="OBJECTID",
    source_wkid=6827,
    max_page_size=2_000,
    required_fields=JACKSON_FIELDS,
    native_id_fields=("TM_MAPLOT", "MAPLOT", "MAPNUMBER"),
    search_fields={
        "parcel": (
            SearchColumn("TM_MAPLOT"),
            SearchColumn("MAPLOT"),
            SearchColumn("MAPNUMBER"),
            SearchColumn("MAPNUM"),
            SearchColumn("TAXLOT", numeric=True),
        ),
        "account": (SearchColumn("ACCOUNT", numeric=True),),
        "owner": (
            SearchColumn("FEEOWNER", contains=True),
            SearchColumn("CONTRACT", contains=True),
        ),
        "address": (
            SearchColumn("SITEADD", contains=True),
            SearchColumn("ADDRESS1", contains=True),
            SearchColumn("ADDRESS2", contains=True),
            SearchColumn("CITY", contains=True),
            SearchColumn("STREETNAME", contains=True),
        ),
    },
    source_role="county_assessor_taxlot_owner_value_geometry",
    component_scope=(
        "Current assessor taxlot identity, owner and mailing fields, situs, "
        "acreage, property values, classification, selected improvements, "
        "tax codes, and polygon geometry."
    ),
    cadence_fact=(
        "Jackson County's official JIM instructions say the property taxlot "
        "information is updated on Friday mornings."
    ),
    sentinel_field="parcel",
    sentinel_value="30-2E-100",
    expected_schema_fingerprint=(
        "cbf9a621d1fabba5c770bde34b3b1db6fe2d17e747699889dd2e659b6d0a560e"
    ),
    baseline_count=104_747,
    baseline_observed_at="2026-07-30T01:03:47Z",
    baseline_item_created="2025-08-15T14:15:50Z",
    baseline_item_modified="2025-11-24T17:18:17Z",
    warnings=(
        "The taxlot layer does not publish legal-description or recorded-"
        "instrument fields; official assessment maps, data requests, and "
        "recorder records provide those adjacent representations.",
        "Layer metadata omits editingInfo, so the portal item timestamp and "
        "the publisher's Friday-morning update statement are retained "
        "separately.",
    ),
)

DOUGLAS = SourceConfig(
    source_id=DOUGLAS_SOURCE_ID,
    name="Douglas County Assessor Parcels",
    publisher="Douglas County Assessor and Douglas County GIS",
    county_name="Douglas County, Oregon",
    county_geoid=DOUGLAS_GEOID,
    layer_url=DOUGLAS_LAYER_URL,
    service_url=DOUGLAS_SERVICE_URL,
    layer_id=0,
    service_item_id=DOUGLAS_ITEM_ID,
    portal_item_api_url=DOUGLAS_PORTAL_ITEM_API_URL,
    portal_item_page_url=DOUGLAS_PORTAL_ITEM_PAGE_URL,
    expected_layer_name="Parcels",
    object_id_field="OBJECTID",
    source_wkid=2270,
    max_page_size=50_000,
    required_fields=DOUGLAS_FIELDS,
    native_id_fields=("TAXID",),
    search_fields={
        "parcel": (SearchColumn("TAXID"),),
        "account": (
            SearchColumn("PROP_ID"),
            SearchColumn("ALT_ACCTNUM"),
        ),
        "owner": (SearchColumn("NAME", contains=True),),
        "address": (
            SearchColumn("SitusAddress", contains=True),
            SearchColumn("SitusCSZ", contains=True),
            SearchColumn("ADDR1", contains=True),
            SearchColumn("ADDR2", contains=True),
            SearchColumn("ADDR3", contains=True),
            SearchColumn("CSZ", contains=True),
        ),
        "instrument": (SearchColumn("INST_NO", contains=True),),
    },
    source_role="county_assessor_parcel_owner_value_sale_reference_geometry",
    component_scope=(
        "Current assessor parcel and account identifiers, owner and mailing "
        "fields, situs, acreage observations, assessed and market values, "
        "legal description, instrument and sale-date references, and polygon "
        "geometry."
    ),
    cadence_fact=(
        "The layer does not publish editingInfo; its Enterprise portal item "
        "created and modified timestamps are retained as separate update facts."
    ),
    sentinel_field="parcel",
    sentinel_value="19080000100",
    expected_schema_fingerprint=(
        "17cfdb9c9b70104b9243298250a5932094d28eb82fe62927a9ce9b35ce141a0e"
    ),
    baseline_count=68_890,
    baseline_observed_at="2026-07-30T01:03:47Z",
    baseline_item_created="2026-03-26T19:40:35Z",
    baseline_item_modified="2026-03-30T15:22:40Z",
    warnings=(
        "The parcel row's instrument and sale-date fields are retained as "
        "published current-row references rather than expanded into a "
        "separate sale history.",
        "Douglas County's certified rolls, improvement and land segments, "
        "three-year sales, map images, and GIS subscription products are "
        "catalogued as a separate complementary source.",
    ),
)

SOURCES = {config.source_id: config for config in (JACKSON, DOUGLAS)}

COMPLEMENTARY_SOURCES: dict[str, tuple[dict[str, Any], ...]] = {
    JACKSON_SOURCE_ID: (
        {
            "source_id": JACKSON_MAPS_SOURCE_ID,
            "name": "Jackson County Assessment Maps",
            "url": JACKSON_ASSESSMENT_MAPS_URL,
            "access": "public_interactive",
            "adds": (
                "Cadastral assessment maps, subdivisions, partition plats, "
                "donation land claims, map-number search, and a starting point "
                "for interpreting legal descriptions."
            ),
            "join_keys": ["map_taxlot", "map_number"],
        },
        {
            "source_id": JACKSON_DATA_REQUEST_SOURCE_ID,
            "name": "Jackson County Assessor Data and Public Records Request",
            "url": JACKSON_PUBLIC_RECORDS_REQUEST_URL,
            "access": "official_request_with_published_fees",
            "adds": (
                "Custom assessor or property-record requests identified by "
                "property address, parcel number, or map ID."
            ),
            "join_keys": ["address", "parcel", "map_id", "account"],
        },
        {
            "source_id": JACKSON_RECORDER_SOURCE_ID,
            "name": "Jackson County Helion Digital Research Room",
            "url": JACKSON_RECORDER_URL,
            "access": "public_disclaimer_with_interactive_challenge",
            "adds": (
                "Recorded-instrument index and document context corresponding "
                "to assessor ownership, taxlot, and legal-description pivots."
            ),
            "join_keys": [
                "owner_name",
                "taxlot",
                "account",
                "recording_number",
                "legal_description",
            ],
        },
        {
            "source_id": "us-or-jackson-county-jim-property-map",
            "name": "Jackson County Interactive Map property view",
            "url": JACKSON_JIM_GUIDE_URL,
            "access": "public_interactive",
            "adds": (
                "Official property-map workflow, address and account search, "
                "tax maps, and the publisher's Friday update statement."
            ),
            "join_keys": ["map_taxlot", "address", "account"],
        },
    ),
    DOUGLAS_SOURCE_ID: (
        {
            "source_id": DOUGLAS_BULK_SOURCE_ID,
            "name": "Douglas County Assessor Web Subscription and Data Products",
            "url": DOUGLAS_BULK_URL,
            "access": "subscription_or_one_time_product",
            "adds": (
                "Certified property values and present-owner CSV, geoparcel "
                "and parcel shapefiles, assessor map images, improvement and "
                "building components, land segments, manufactured-home rows, "
                "certified web-sales snapshot, and last-three-years sales CSV."
            ),
            "published_products": [
                "Certified All Property values and Present Owner CSV",
                "GIS Geoparcel shapefile",
                "GIS Parcels shapefile",
                "Assessor Map Tax Lot images",
                "Improvement Segments and Building Components CSV",
                "Land Segments CSV",
                "Certified Websales snapshot CSV",
                "Sales Data Last 3 Years CSV",
            ],
            "join_keys": ["tax_id", "property_id", "owner", "instrument"],
        },
    ),
}

COMPLEMENT_CATALOG_METADATA: dict[str, dict[str, Any]] = {
    item["source_id"]: dict(item)
    for values in COMPLEMENTARY_SOURCES.values()
    for item in values
}

SOURCE_CATALOG_METADATA: dict[str, dict[str, Any]] = {
    JACKSON_SOURCE_ID: {
        "source_id": JACKSON_SOURCE_ID,
        "record_identity_source_id": JACKSON_SOURCE_ID,
        "complementary_source_ids": [
            item["source_id"] for item in COMPLEMENTARY_SOURCES[JACKSON_SOURCE_ID]
        ],
        "name": JACKSON.name,
        "domain": "property",
        "roles": [
            "assessment_roll",
            "owner_index",
            "owner_mailing_address",
            "parcel_geometry",
            "assessed_values",
            "market_values",
            "building_attributes",
            "tax_classification",
        ],
        "authority": "Jackson County Assessor",
        "operator": "Jackson County",
        "jurisdiction_geoids": [STATE_FIPS, JACKSON_GEOID],
        "official_url": JACKSON_LAYER_URL,
        "platform_family": "arcgis_featureserver",
        "authentication": "none",
        "fees": "none_for_live_layer",
        "stable_keys": ["tm_maplot", "maplot", "account", "objectid"],
        "adapter_family": "oregon_jackson_douglas_assessors",
        "adapter_version": 1,
        "adapter_tool": Path(__file__).name,
        "adapter_commands": [
            "sources",
            "search",
            "owner",
            "address",
            "parcel",
            "account",
            "probe",
        ],
        "endpoints": {
            "service": JACKSON_SERVICE_URL,
            "layer": JACKSON_LAYER_URL,
            "query": f"{JACKSON_LAYER_URL}/query",
            "service_item": JACKSON_PORTAL_ITEM_PAGE_URL,
            "service_item_api": JACKSON_PORTAL_ITEM_API_URL,
        },
        "probe_evidence": {
            "anonymous_query_verified": True,
            "service_item_id": JACKSON_ITEM_ID,
            "layer_id": JACKSON.layer_id,
            "layer_name": JACKSON.expected_layer_name,
            "observed_count": JACKSON.baseline_count,
            "maximum_page_size": JACKSON.max_page_size,
            "object_id_field": JACKSON.object_id_field,
            "source_crs": JACKSON.original_crs,
            "schema_fingerprint": JACKSON.expected_schema_fingerprint,
            "representative_identifier": JACKSON.sentinel_value,
            "portal_item_created": JACKSON.baseline_item_created,
            "portal_item_modified": JACKSON.baseline_item_modified,
            "observed_at": JACKSON.baseline_observed_at,
        },
    },
    DOUGLAS_SOURCE_ID: {
        "source_id": DOUGLAS_SOURCE_ID,
        "record_identity_source_id": DOUGLAS_SOURCE_ID,
        "complementary_source_ids": [
            item["source_id"] for item in COMPLEMENTARY_SOURCES[DOUGLAS_SOURCE_ID]
        ],
        "name": DOUGLAS.name,
        "domain": "property",
        "roles": [
            "assessment_roll",
            "owner_index",
            "owner_mailing_address",
            "parcel_geometry",
            "assessed_values",
            "market_values",
            "legal_description",
            "latest_sale_reference",
            "recorded_instrument_reference",
        ],
        "authority": "Douglas County Assessor",
        "operator": "Douglas County",
        "jurisdiction_geoids": [STATE_FIPS, DOUGLAS_GEOID],
        "official_url": DOUGLAS_LAYER_URL,
        "platform_family": "arcgis_featureserver",
        "authentication": "none",
        "fees": "none_for_live_layer",
        "stable_keys": ["taxid", "prop_id", "alt_acctnum", "objectid"],
        "adapter_family": "oregon_jackson_douglas_assessors",
        "adapter_version": 1,
        "adapter_tool": Path(__file__).name,
        "adapter_commands": [
            "sources",
            "search",
            "owner",
            "address",
            "parcel",
            "account",
            "probe",
        ],
        "endpoints": {
            "service": DOUGLAS_SERVICE_URL,
            "layer": DOUGLAS_LAYER_URL,
            "query": f"{DOUGLAS_LAYER_URL}/query",
            "service_item": DOUGLAS_PORTAL_ITEM_PAGE_URL,
            "service_item_api": DOUGLAS_PORTAL_ITEM_API_URL,
        },
        "probe_evidence": {
            "anonymous_query_verified": True,
            "service_item_id": DOUGLAS_ITEM_ID,
            "layer_id": DOUGLAS.layer_id,
            "layer_name": DOUGLAS.expected_layer_name,
            "observed_count": DOUGLAS.baseline_count,
            "maximum_page_size": DOUGLAS.max_page_size,
            "object_id_field": DOUGLAS.object_id_field,
            "source_crs": DOUGLAS.original_crs,
            "schema_fingerprint": DOUGLAS.expected_schema_fingerprint,
            "representative_identifier": DOUGLAS.sentinel_value,
            "portal_item_created": DOUGLAS.baseline_item_created,
            "portal_item_modified": DOUGLAS.baseline_item_modified,
            "observed_at": DOUGLAS.baseline_observed_at,
        },
    },
}

# Stable aliases for shared integration code to import without parsing CLI output.
CATALOG_METADATA = SOURCE_CATALOG_METADATA
CATALOG_COMPLEMENTS = COMPLEMENT_CATALOG_METADATA


class SourceSelectionError(ValueError):
    """A source, command, selector, or cursor mismatch."""

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
class LayerContract:
    schema_fingerprint: str
    server_page_size: int
    object_id_field: str
    source_wkid: int


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


class OregonAssessorArcGISClient(ArcGISRESTClient):
    """Metadata, item, count, and ordered-page facade over shared transport."""

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

    def fetch_item_metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(
            self.config.portal_item_api_url,
            params={"f": "json"},
        )
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "ArcGIS portal item metadata must be a JSON object",
                url=self.config.portal_item_api_url,
            )
        if "error" in payload:
            raise SourceResponseError(
                "ArcGIS portal returned an error for the service item",
                url=self.config.portal_item_api_url,
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
            f"unknown Jackson/Douglas assessor source: {source_id}",
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


def _date(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue
    return text


def _instant(value: Any) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(
                value / 1000,
                tz=timezone.utc,
            ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        except (OverflowError, OSError, ValueError):
            return None
    return _clean_text(value)


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    text = _clean_text(value)
    if not text:
        return None
    try:
        number = float(text.replace(",", ""))
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _sum_values(*values: Any) -> int | float | None:
    numbers = [number for value in values if (number := _number(value)) is not None]
    return sum(numbers) if numbers else None


def _zip_code(value: Any) -> str | None:
    text = _clean_text(value)
    if not text or text == "0":
        return None
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def _address(
    *,
    raw: Any = None,
    city_state_zip: Any = None,
    lines: Sequence[Any] = (),
    city: Any = None,
    state: Any = None,
    postal_code: Any = None,
    country: str = "US",
) -> dict[str, Any]:
    line_values = [text for item in lines if (text := _clean_text(item))]
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
        "postal_code": _zip_code(postal_code),
        "country": country,
    }


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


def _column_clause(column: SearchColumn, selector: str) -> str | None:
    if column.numeric:
        if not re.fullmatch(r"[+-]?\d+", selector):
            return None
        return f"{column.name} = {int(selector)}"
    escaped = selector.upper()
    if column.contains:
        return f"UPPER({column.name}) LIKE '%{escaped}%'"
    return f"UPPER({column.name}) = '{escaped}'"


def _where(
    config: SourceConfig,
    *,
    operation: str,
    selector: str,
    search_field: str,
) -> str:
    value = _sql_text(selector)
    if operation in {"owner", "address", "parcel", "account"}:
        groups = (operation,)
    elif search_field == "auto":
        groups = tuple(config.search_fields)
    elif search_field in config.search_fields:
        groups = (search_field,)
    else:
        raise SourceSelectionError(
            "unsupported_search_field",
            f"{config.source_id} does not publish a searchable {search_field} field",
            details={"supported_fields": sorted(config.search_fields)},
        )

    clauses = [
        clause
        for group in groups
        for column in config.search_fields.get(group, ())
        if (clause := _column_clause(column, value)) is not None
    ]
    if not clauses:
        raise SourceSelectionError(
            "selector_type_mismatch",
            f"{selector!r} is not compatible with {search_field}",
            details={"supported_fields": sorted(config.search_fields)},
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
                "access_decision": dict(access_decision or {}),
            },
        ),
    )


def _source_wkid(metadata: Mapping[str, Any]) -> int | None:
    candidates = (
        metadata.get("sourceSpatialReference"),
        metadata.get("spatialReference"),
        metadata.get("extent", {}).get("spatialReference")
        if isinstance(metadata.get("extent"), Mapping)
        else None,
    )
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            value = candidate.get("latestWkid") or candidate.get("wkid")
            if isinstance(value, int) and not isinstance(value, bool):
                return value
    return None


def _metadata_schema(
    config: SourceConfig,
    metadata: Mapping[str, Any],
) -> LayerContract:
    if metadata.get("name") != config.expected_layer_name:
        raise SourceSchemaError(
            "ArcGIS layer name changed",
            url=config.layer_url,
            details={
                "expected": config.expected_layer_name,
                "observed": metadata.get("name"),
            },
        )
    if metadata.get("serviceItemId") != config.service_item_id:
        raise SourceSchemaError(
            "ArcGIS service item identity changed",
            url=config.layer_url,
            details={
                "expected": config.service_item_id,
                "observed": metadata.get("serviceItemId"),
            },
        )
    object_id_field = metadata.get("objectIdField")
    if object_id_field != config.object_id_field:
        raise SourceSchemaError(
            "ArcGIS object ID field changed",
            url=config.layer_url,
            details={
                "expected": config.object_id_field,
                "observed": object_id_field,
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
    observed_wkid = _source_wkid(metadata)
    if observed_wkid != config.source_wkid:
        raise SourceSchemaError(
            "ArcGIS source spatial reference changed",
            url=config.layer_url,
            details={
                "expected": config.source_wkid,
                "observed": observed_wkid,
            },
        )
    return LayerContract(
        schema_fingerprint=schema_fingerprint(arcgis_declared_schema(fields)),
        server_page_size=min(maximum, config.max_page_size),
        object_id_field=object_id_field,
        source_wkid=observed_wkid,
    )


def _item_identity(
    config: SourceConfig,
    item: Mapping[str, Any],
) -> dict[str, Any]:
    if item.get("id") != config.service_item_id:
        raise SourceSchemaError(
            "ArcGIS portal item identity changed",
            url=config.portal_item_api_url,
            details={
                "expected": config.service_item_id,
                "observed": item.get("id"),
            },
        )
    return {
        "item_id": item.get("id"),
        "title": _clean_text(item.get("title")),
        "type": _clean_text(item.get("type")),
        "owner": _clean_text(item.get("owner")),
        "access": _clean_text(item.get("access")),
        "service_url": _clean_text(item.get("url")),
        "item_api_url": config.portal_item_api_url,
        "item_page_url": config.portal_item_page_url,
        "created": _instant(item.get("created")),
        "modified": _instant(item.get("modified")),
    }


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
        base64.urlsafe_b64encode(canonical_json(payload).encode())
        .decode()
        .rstrip("=")
    )
    return f"{CURSOR_PREFIX}{token}"


def _decode_cursor(cursor: str | None) -> CursorState | None:
    if cursor is None:
        return None
    if not cursor.startswith(CURSOR_PREFIX):
        raise SourceSelectionError(
            "invalid_cursor",
            "cursor does not belong to the Jackson/Douglas assessor adapter",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(token + padding).decode())
        state = CursorState(
            source_id=str(payload["source"]),
            operation=str(payload["operation"]),
            criteria_fingerprint=str(payload["criteria"]),
            offset=int(payload["offset"]),
            anchor=int(payload["anchor"]),
            total_count=int(payload["total"]),
            schema_fingerprint=str(payload["schema"]),
        )
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise SourceSelectionError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from None
    if (
        not isinstance(payload, Mapping)
        or payload.get("v") != CURSOR_VERSION
        or state.offset <= 0
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
    layer_contract = _metadata_schema(config, metadata)
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
        if cursor_state.schema_fingerprint != layer_contract.schema_fingerprint:
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
    safe_to_resume = True
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
        int(getattr(client, "page_size", layer_contract.server_page_size)),
        layer_contract.server_page_size,
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
                schema_fingerprint=layer_contract.schema_fingerprint,
            )
        )
    return ArcGISBatch(
        features=tuple(collected),
        next_cursor=next_cursor,
        total_count=end_count,
        start_offset=start_offset,
        schema_fingerprint=layer_contract.schema_fingerprint,
        metadata=dict(metadata),
        pages_fetched=pages_fetched,
        errors=tuple(errors),
    )


def _owner(
    value: Any,
    *,
    role: str,
    source_field: str,
) -> dict[str, Any] | None:
    name = _clean_text(value)
    if not name:
        return None
    return {
        "raw_name": name,
        "role": role,
        "assertion_type": "assessment_roll",
        "source_field": source_field,
        "confidence": "high",
    }


def _base_record(
    config: SourceConfig,
    feature: Mapping[str, Any],
    *,
    response_schema_fingerprint: str,
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    attributes = _feature_attributes(feature)
    object_id = _feature_oid(config, feature)
    native_id = _first_text(attributes, config.native_id_fields) or str(object_id)
    record = {
        "canonical_ref": canonical_property_ref(
            config.source_id,
            config.county_geoid,
            "parcel",
            native_id,
        ),
        "source_id": config.source_id,
        "source_url": config.layer_url,
        "record_kind": "parcel",
        "snapshot_complete": True,
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
            "service_url": config.service_url,
            "service_item_id": config.service_item_id,
            "portal_item_url": config.portal_item_page_url,
            "layer_id": config.layer_id,
            "layer_name": config.expected_layer_name,
            "layer_url": config.layer_url,
            "component_scope": config.component_scope,
            "cadence_fact": config.cadence_fact,
        },
        "component_completeness": {
            "scope": config.component_scope,
            "complementary_source_ids": [
                item["source_id"]
                for item in COMPLEMENTARY_SOURCES[config.source_id]
            ],
        },
        "response_schema_fingerprint": response_schema_fingerprint,
        "adapter_schema_fingerprint": sha256_fingerprint(
            {
                "normalization_version": 1,
                "source_id": config.source_id,
                "required_fields": list(config.required_fields),
                "search_fields": {
                    group: [
                        {
                            "name": column.name,
                            "contains": column.contains,
                            "numeric": column.numeric,
                        }
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


def _normalize_jackson(
    feature: Mapping[str, Any],
    *,
    schema_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    record, attributes = _base_record(
        JACKSON,
        feature,
        response_schema_fingerprint=schema_value,
    )
    published_id = _first_text(attributes, JACKSON.native_id_fields)
    native_id = published_id or str(record["object_id"])
    record["native_parcel_id"] = native_id
    record["parcel_identity_basis"] = (
        "published_taxlot_identifier"
        if published_id
        else "source_object_id_fallback"
    )
    record["alternate_parcel_ids"] = [
        value
        for value in _unique_text(
            attributes,
            ("MAPLOT", "TM_MAPLOT", "MAPNUMBER", "MAPNUM", "TAXLOT"),
        )
        if value != native_id
    ]
    record["map_taxlot"] = {
        "combined": _clean_text(attributes.get("TM_MAPLOT")),
        "compact": _clean_text(attributes.get("MAPLOT")),
        "map_number": _clean_text(attributes.get("MAPNUMBER")),
        "alternate_map_number": _clean_text(attributes.get("MAPNUM")),
        "taxlot": _clean_text(attributes.get("TAXLOT")),
    }
    record["assessment_account_ids"] = _unique_text(attributes, ("ACCOUNT",))
    owners = [
        owner
        for owner in (
            _owner(
                attributes.get("FEEOWNER"),
                role="fee_owner",
                source_field="FEEOWNER",
            ),
            _owner(
                attributes.get("CONTRACT"),
                role="contract_name",
                source_field="CONTRACT",
            ),
        )
        if owner
    ]
    record["owners"] = owners
    record["owner_visibility"] = {
        "state": "published",
        "source_fields": ["FEEOWNER", "CONTRACT"],
    }
    record["care_of"] = _clean_text(attributes.get("INCAREOF"))
    record["mailing_address"] = _address(
        lines=(attributes.get("ADDRESS1"), attributes.get("ADDRESS2")),
        city=attributes.get("CITY"),
        state=attributes.get("STATE"),
        postal_code=attributes.get("ZIPCODE"),
    )
    record["situs_address"] = _address(
        raw=attributes.get("SITEADD"),
        lines=(attributes.get("ADDRESSNUM"), attributes.get("STREETNAME")),
    )
    record["parcel_acres"] = _number(attributes.get("ACREAGE"))
    record["parcel_acre_observations"] = {
        "assessor_acreage": _number(attributes.get("ACREAGE")),
        "gis_area": _number(attributes.get("GIS_AREA")),
        "shape_area_square_feet": _number(attributes.get("Shape__Area")),
    }
    record["assessment"] = {
        "market_land": _number(attributes.get("LANDVALUE")),
        "market_improvements": _number(attributes.get("IMPVALUE")),
        "market_total": _sum_values(
            attributes.get("LANDVALUE"),
            attributes.get("IMPVALUE"),
        ),
        "assessed_land": _number(attributes.get("ASSESSLAND")),
        "assessed_improvements": _number(attributes.get("ASSESSIMP")),
        "assessed_total": _sum_values(
            attributes.get("ASSESSLAND"),
            attributes.get("ASSESSIMP"),
        ),
        "currency": "USD",
    }
    record["physical_characteristics"] = {
        "commercial_square_feet": _number(attributes.get("COMMSQFT")),
        "year_built": _number(attributes.get("YEARBLT")),
        "building_code": _clean_text(attributes.get("BUILDCODE")),
        "lot_depth": _number(attributes.get("LOTDEPTH")),
        "lot_width": _number(attributes.get("LOTWIDTH")),
    }
    record["classification"] = {
        "lot_type": _clean_text(attributes.get("LOTTYPE")),
        "property_class": _clean_text(attributes.get("PROPCLASS")),
        "tax_code": _clean_text(attributes.get("TAXCODE")),
        "maintenance_code": _clean_text(attributes.get("MAINTENANC")),
        "schedule_code": _clean_text(attributes.get("SCHEDULECO")),
        "neighborhood_code": _clean_text(attributes.get("NEIGHBORHO")),
    }
    record["native_sort_keys"] = {
        "owner": _clean_text(attributes.get("OWNERSORT")),
        "address": _clean_text(attributes.get("ADDSORT")),
        "township_range_section": _clean_text(attributes.get("TRSSORT")),
    }
    _add_geometry(record, feature, JACKSON, requested=geometry_requested)
    return record


def _normalize_douglas(
    feature: Mapping[str, Any],
    *,
    schema_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    record, attributes = _base_record(
        DOUGLAS,
        feature,
        response_schema_fingerprint=schema_value,
    )
    published_id = _clean_text(attributes.get("TAXID"))
    native_id = published_id or str(record["object_id"])
    record["native_parcel_id"] = native_id
    record["parcel_identity_basis"] = (
        "published_tax_id" if published_id else "source_object_id_fallback"
    )
    record["alternate_parcel_ids"] = []
    record["tax_id"] = published_id
    record["assessment_account_ids"] = _unique_text(
        attributes,
        ("PROP_ID", "ALT_ACCTNUM"),
    )
    primary_owner = _owner(
        attributes.get("NAME"),
        role="primary_assessor_owner",
        source_field="NAME",
    )
    record["owners"] = [primary_owner] if primary_owner else []
    record["owner_visibility"] = {
        "state": "published",
        "source_field": "NAME",
    }
    record["owner_id"] = _clean_text(attributes.get("OWNER_ID"))
    record["mailing_address"] = _address(
        lines=(
            attributes.get("ADDR1"),
            attributes.get("ADDR2"),
            attributes.get("ADDR3"),
        ),
        city_state_zip=attributes.get("CSZ"),
    )
    record["situs_address"] = _address(
        raw=attributes.get("SitusAddress"),
        city_state_zip=attributes.get("SitusCSZ"),
    )
    record["parcel_acres"] = (
        _number(attributes.get("MTLACREAGE"))
        if _number(attributes.get("MTLACREAGE")) is not None
        else _number(attributes.get("ACCT_ACREAGE"))
    )
    record["parcel_acre_observations"] = {
        "account_acreage": _number(attributes.get("ACCT_ACREAGE")),
        "map_taxlot_acreage": _number(attributes.get("MTLACREAGE")),
        "total_acreage": _number(attributes.get("TotalAcreage")),
    }
    record["assessment"] = {
        "assessed_value": _number(attributes.get("ASSD_VALUE")),
        "market_land": _number(attributes.get("LAND_MKT_VALUE")),
        "market_improvements": _number(attributes.get("IMPRV_VALUE")),
        "market_total": _number(attributes.get("MARKET_VALUE")),
        "currency": "USD",
    }
    record["legal_description"] = _clean_text(attributes.get("LEGAL"))
    record["legal_and_plat"] = {
        "legal_description": record["legal_description"],
        "block": _clean_text(attributes.get("BLOCK")),
        "lot": _clean_text(attributes.get("LOT")),
    }
    record["published_instrument_and_sale_reference"] = {
        "instrument_number": _clean_text(attributes.get("INST_NO")),
        "sale_date": _date(attributes.get("SaleDate")),
        "scope": "published_on_current_parcel_row",
    }
    record["classification"] = {
        "property_class": _clean_text(attributes.get("PROPCLASS")),
        "location_code": _clean_text(attributes.get("LOC_CODE")),
        "maintenance_area": _clean_text(attributes.get("MAINTAREA")),
        "neighborhood_code": _clean_text(attributes.get("NBHDCODE")),
        "tax_code_area": _clean_text(attributes.get("CODEAREA")),
        "special_interest": _clean_text(attributes.get("SPECINTEREST")),
    }
    _add_geometry(record, feature, DOUGLAS, requested=geometry_requested)
    return record


def _normalize_feature(
    config: SourceConfig,
    feature: Mapping[str, Any],
    *,
    schema_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    if config.source_id == JACKSON_SOURCE_ID:
        return _normalize_jackson(
            feature,
            schema_value=schema_value,
            geometry_requested=geometry_requested,
        )
    if config.source_id == DOUGLAS_SOURCE_ID:
        return _normalize_douglas(
            feature,
            schema_value=schema_value,
            geometry_requested=geometry_requested,
        )
    raise ValueError(f"no normalizer configured for {config.source_id}")


def _client(
    args: argparse.Namespace,
    config: SourceConfig,
) -> OregonAssessorArcGISClient:
    return OregonAssessorArcGISClient(
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
            records.append(
                _normalize_feature(
                    config,
                    feature,
                    schema_value=batch.schema_fingerprint,
                    geometry_requested=geometry_requested,
                )
            )
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
        _instant(editing_info.get("dataLastEditDate"))
        if isinstance(editing_info, Mapping)
        else None
    )
    snapshot = {
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
        record["retrieval_snapshot"] = snapshot

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


def _command_field(args: argparse.Namespace) -> str:
    if args.command in {"owner", "address", "parcel", "account"}:
        return args.command
    return args.field


def _execute_records(
    args: argparse.Namespace,
    *,
    client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    config = _source(args.source)
    search_field = _command_field(args)
    query = _build_query(
        config,
        operation=args.command,
        selector=args.query,
        search_field=search_field,
        limit=args.limit,
        cursor=args.cursor,
        geometry=args.geometry,
        access_decision=access_decision,
    )
    try:
        where = _where(
            config,
            operation=args.command,
            selector=args.query,
            search_field=search_field,
        )
        active_client = client or _client(args, config)
        batch = _fetch_batch(
            active_client,
            config,
            operation=args.command,
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
        geometry=True,
        access_decision=access_decision,
    )
    try:
        active_client = client or _client(args, config)
        metadata = active_client.fetch_metadata()
        item_metadata = active_client.fetch_item_metadata()
        layer_contract = _metadata_schema(config, metadata)
        item_identity = _item_identity(config, item_metadata)
        total_count = active_client.fetch_count("1=1")
        where = _where(
            config,
            operation="parcel",
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
            return_geometry=True,
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
            schema_value=layer_contract.schema_fingerprint,
            geometry_requested=True,
        )
        editing_info = metadata.get("editingInfo")
        result = PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": config.source_id,
                    "service_identity": {
                        "service_url": config.service_url,
                        "service_item_id": config.service_item_id,
                    },
                    "layer_identity": {
                        "layer_url": config.layer_url,
                        "layer_id": config.layer_id,
                        "layer_name": metadata.get("name"),
                        "object_id_field": layer_contract.object_id_field,
                        "geometry_type": metadata.get("geometryType"),
                    },
                    "item_identity": item_identity,
                    "component_total_count": total_count,
                    "maximum_page_size": layer_contract.server_page_size,
                    "source_crs": f"EPSG:{layer_contract.source_wkid}",
                    "schema_fingerprint": layer_contract.schema_fingerprint,
                    "schema_baseline": {
                        "expected_fingerprint": config.expected_schema_fingerprint,
                        "matches": (
                            layer_contract.schema_fingerprint
                            == config.expected_schema_fingerprint
                        ),
                        "field_count": len(metadata.get("fields", [])),
                    },
                    "update_metadata": {
                        "layer_editing_info": (
                            dict(editing_info)
                            if isinstance(editing_info, Mapping)
                            else None
                        ),
                        "service_data_last_edit": (
                            _instant(editing_info.get("dataLastEditDate"))
                            if isinstance(editing_info, Mapping)
                            else None
                        ),
                        "portal_item_created": item_identity["created"],
                        "portal_item_modified": item_identity["modified"],
                        "cadence_fact": config.cadence_fact,
                    },
                    "count_baseline": {
                        "observed_count": config.baseline_count,
                        "observed_at": config.baseline_observed_at,
                        "current_count": total_count,
                    },
                    "sentinel_strategy": "configured_exact_identifier",
                    "sentinel_count": sentinel_count,
                    "representative_row": sentinel,
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
                "catalog_metadata": SOURCE_CATALOG_METADATA[config.source_id],
                "object_id_field": config.object_id_field,
                "maximum_page_size": config.max_page_size,
                "search_fields": sorted(config.search_fields),
                "required_fields": list(config.required_fields),
                "expected_schema_fingerprint": (
                    config.expected_schema_fingerprint
                ),
                "baseline_count": config.baseline_count,
                "baseline_observed_at": config.baseline_observed_at,
                "warnings": list(config.warnings),
                "complementary_sources": list(
                    COMPLEMENTARY_SOURCES[config.source_id]
                ),
            }
            for config in SOURCES.values()
        ],
        "process_learnings": [
            {
                "scope": "source_specific_field_maps",
                "learning": (
                    "Shared ArcGIS transport does not imply shared assessor "
                    "semantics; each county retains an explicit field map."
                ),
            },
            {
                "scope": "update_observations",
                "learning": (
                    "Layer editingInfo, Enterprise item modification time, "
                    "and publisher cadence statements remain separate facts."
                ),
            },
            {
                "scope": "complementary_products",
                "learning": (
                    "Live parcel layers, certified bulk products, cadastral "
                    "maps, data requests, and recorder documents remain "
                    "distinct representations joined through native keys."
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
    successful = sum(component["status"] == "ok" for component in components)
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


def _payload(
    value: PublicRecordsResult | Mapping[str, Any],
) -> dict[str, Any]:
    return value.to_dict() if isinstance(value, PublicRecordsResult) else dict(value)


def _emit(
    value: PublicRecordsResult | Mapping[str, Any],
    args: argparse.Namespace,
) -> None:
    payload = _payload(value)
    records = payload.get("records")
    count = (
        len(records)
        if isinstance(records, list)
        else len(payload.get("components", payload.get("sources", [])))
    )
    if write_output(
        payload,
        args,
        summary=f"Jackson/Douglas assessors {args.command}",
        result_count=count,
    ):
        return
    if args.command == "sources":
        print(f"Jackson/Douglas assessor sources: {len(payload['sources'])}")
        for source in payload["sources"]:
            print(
                f"  {source['source_id']} | "
                f"{', '.join(source['search_fields'])}"
            )
        return
    if args.command == "probe" and args.all_sources:
        print(f"Jackson/Douglas assessor probes: {payload['status']}")
        for component in payload["components"]:
            print(
                f"  {component['query']['source']['source_id']} | "
                f"{component['status']}"
            )
        return
    print(
        f"Jackson/Douglas {args.command}: "
        f"{payload.get('status')} ({count} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in payload.get("records", []):
        native_id = record.get("native_parcel_id") or record.get("record_kind")
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
        help="Exact county assessor source ID",
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--cursor",
        help="Query-bound continuation cursor returned by an earlier result",
    )
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="Request polygon geometry transformed to WGS84",
    )
    _add_transport_arguments(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Jackson and Douglas County ArcGIS assessor parcels"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser("sources", help="List direct and complementary sources")
    add_output_args(sources)

    search = sub.add_parser("search", help="Search one selected assessor layer")
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=("auto", "parcel", "account", "owner", "address", "instrument"),
        default="auto",
    )
    _add_query_arguments(search)

    for command in ("owner", "address", "parcel", "account"):
        query_parser = sub.add_parser(
            command,
            help=f"Search the selected source by {command}",
        )
        query_parser.add_argument("query")
        query_parser.set_defaults(field=command)
        _add_query_arguments(query_parser)

    probe = sub.add_parser("probe", help="Run bounded source probe packets")
    selection = probe.add_mutually_exclusive_group(required=True)
    selection.add_argument("--source", choices=sorted(SOURCES))
    selection.add_argument(
        "--all",
        action="store_true",
        dest="all_sources",
        help="Probe both official assessor layers",
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
