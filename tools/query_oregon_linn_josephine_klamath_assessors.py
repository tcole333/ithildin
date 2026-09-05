#!/usr/bin/env python3
"""Query official Linn, Josephine, and Klamath County assessor parcel layers.

The three publishers expose compatible ArcGIS query mechanics but materially
different assessor schemas. This adapter shares bounded keyset traversal while
retaining native county identifiers, field names, value meanings, update
signals, source CRS, and links to official complementary records.

Examples:
    uv run python tools/query_oregon_linn_josephine_klamath_assessors.py sources
    uv run python tools/query_oregon_linn_josephine_klamath_assessors.py owner \
        "BEAR" --source us-or-linn-county-assessor-taxlots --limit 25
    uv run python tools/query_oregon_linn_josephine_klamath_assessors.py account \
        R333020 --source us-or-josephine-county-assessor-taxlots --geometry
    uv run python tools/query_oregon_linn_josephine_klamath_assessors.py probe --all
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

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

SOURCE_FAMILY_ID = "oregon-linn-josephine-klamath-assessor-arcgis"
LINN_SOURCE_ID = "us-or-linn-county-assessor-taxlots"
JOSEPHINE_SOURCE_ID = "us-or-josephine-county-assessor-taxlots"
KLAMATH_SOURCE_ID = "us-or-klamath-county-assessor-taxlots"

LINN_ACCOUNT_DETAIL_SOURCE_ID = "us-or-linn-county-account-detail"
LINN_MAPS_SOURCE_ID = "us-or-linn-county-assessor-maps"
JOSEPHINE_PROPERTY_DETAIL_SOURCE_ID = "us-or-josephine-property-detail"
JOSEPHINE_RECORDER_SOURCE_ID = "us-or-josephine-digital-research-room"
KLAMATH_PROPERTY_DETAIL_SOURCE_ID = "us-or-klamath-property-search-online"
KLAMATH_TAX_MAP_SOURCE_ID = "us-or-klamath-tax-maps"
KLAMATH_RECORDER_SOURCE_ID = "us-or-klamath-digital-research-room"
KLAMATH_RECORDS_REQUEST_SOURCE_ID = "us-or-klamath-public-records-request"

OUTPUT_SCHEMA_VERSION = "oregon-linn-josephine-klamath-assessors/1.0"
PROBE_SCHEMA_VERSION = "oregon-linn-josephine-klamath-assessor-probe/1.0"
CURSOR_PREFIX = "oregon-linn-josephine-klamath-assessors:v1:"
CURSOR_VERSION = 1


@dataclass(frozen=True)
class SearchColumn:
    """One native field and its query comparison."""

    name: str
    contains: bool = False
    numeric: bool = False


@dataclass(frozen=True)
class FieldMap:
    """Source-specific mapping without discarding source-native fields."""

    accounts: tuple[str, ...]
    map_taxlots: tuple[str, ...]
    owners: tuple[str, ...]
    mailing_lines: tuple[str, ...]
    mailing_city: str | None
    mailing_state: str | None
    mailing_zip: str | None
    mailing_csz: str | None
    situs: str
    situs_city: str | None
    situs_state: str | None
    situs_zip: str | None
    assessed_value: str | None
    market_value: str | None
    market_land: str | None
    market_improvements: str | None
    sale_price: str | None
    sale_date: str | None
    sale_year: str | None
    sale_month: str | None
    instrument: str | None
    deed_type: str | None
    sale_type: str | None
    acreage: tuple[str, ...]
    year_built: str | None
    property_class: tuple[str, ...]
    property_type: str | None
    legal: str | None
    tax_amount: str | None
    tax_code: str | None
    native_links: Mapping[str, str]


@dataclass(frozen=True)
class SourceConfig:
    """Verified source identity and county-native schema contract."""

    source_id: str
    name: str
    publisher: str
    county_name: str
    county_geoid: str
    layer_url: str
    service_url: str
    layer_id: int
    service_item_id: str
    item_api_url: str | None
    item_page_url: str | None
    expected_layer_name: str
    source_wkid: int
    max_page_size: int
    baseline_count: int
    baseline_observed_at: str
    expected_schema_fingerprint: str
    required_fields: tuple[str, ...]
    native_id_fields: tuple[str, ...]
    search_fields: Mapping[str, tuple[SearchColumn, ...]]
    fields: FieldMap
    update_fields: tuple[str, ...]
    update_order_field: str | None
    cadence_fact: str
    official_hosts: tuple[str, ...]
    authoritative_item_identities: tuple[str, ...]
    expected_wgs84_extent: tuple[float, float, float, float]
    complementary_sources: tuple[Mapping[str, Any], ...]
    warnings: tuple[str, ...] = ()

    @property
    def object_id_field(self) -> str:
        return "OBJECTID"

    @property
    def source_crs(self) -> str:
        return f"EPSG:{self.source_wkid}"

    def source_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_id=self.source_id,
            name=self.name,
            source_role="official_county_assessor_parcel_layer",
            base_url=self.layer_url,
            dataset_id=self.service_item_id,
            metadata={
                "publisher": self.publisher,
                "county_name": self.county_name,
                "county_geoid": self.county_geoid,
                "record_kind": "parcel",
                "layer_id": self.layer_id,
                "source_crs": self.source_crs,
                "source_family_id": SOURCE_FAMILY_ID,
                "umbrella_source_id": SOURCE_FAMILY_ID,
                "umbrella_source_id_is_external_source": False,
            },
        )


LINN_LAYER_URL = (
    "https://gis.co.linn.or.us/public/rest/services/"
    "AssessmentTax/pub11_taxlots/MapServer/0"
)
LINN_SERVICE_URL = LINN_LAYER_URL.rsplit("/", 1)[0]
LINN_ITEM_ID = "a2baa70a21de4f7fbcdb31884b562603"
LINN_ITEM_API_URL = (
    "https://gis.co.linn.or.us/portal/sharing/rest/content/items/"
    f"{LINN_ITEM_ID}"
)
LINN_ITEM_PAGE_URL = (
    "https://gis.co.linn.or.us/portal/home/item.html?id=" f"{LINN_ITEM_ID}"
)

JOSEPHINE_LAYER_URL = (
    "https://gis.co.josephine.or.us/arcgis/rest/services/"
    "Assessor/Assessor_Taxlots/FeatureServer/0"
)
JOSEPHINE_SERVICE_URL = JOSEPHINE_LAYER_URL.rsplit("/", 1)[0]
JOSEPHINE_ITEM_ID = "e6a1823c9fc44fe7b29dbbe210139c32"

KLAMATH_LAYER_URL = (
    "https://services.arcgis.com/H6Mh1bySxR4oHx6x/arcgis/rest/services/"
    "KC_Taxlots/FeatureServer/1"
)
KLAMATH_SERVICE_URL = KLAMATH_LAYER_URL.rsplit("/", 1)[0]
KLAMATH_ITEM_ID = "e3ea8ceb692f405caad95e28eed50688"
KLAMATH_ITEM_API_URL = (
    "https://www.arcgis.com/sharing/rest/content/items/" f"{KLAMATH_ITEM_ID}"
)
KLAMATH_ITEM_PAGE_URL = (
    "https://www.arcgis.com/home/item.html?id=" f"{KLAMATH_ITEM_ID}"
)


LINN = SourceConfig(
    source_id=LINN_SOURCE_ID,
    name="Linn County Oregon Assessor Tax Lots",
    publisher="Linn County Assessment and Taxation",
    county_name="Linn County, Oregon",
    county_geoid="41043",
    layer_url=LINN_LAYER_URL,
    service_url=LINN_SERVICE_URL,
    layer_id=0,
    service_item_id=LINN_ITEM_ID,
    item_api_url=LINN_ITEM_API_URL,
    item_page_url=LINN_ITEM_PAGE_URL,
    expected_layer_name="Tax Lots",
    source_wkid=2913,
    max_page_size=2_000,
    baseline_count=54_600,
    baseline_observed_at="2026-07-29",
    expected_schema_fingerprint=(
        "0592bda23014beba31a4607067eab9bd"
        "6003fe42f1b94453ba66d08ba08a4d54"
    ),
    required_fields=(
        "OBJECTID",
        "PIN",
        "ACTNUM",
        "OWNER1",
        "SITUSSTR",
        "AV",
        "RMV",
        "SALEPR",
        "LASTUPDATE",
    ),
    native_id_fields=("PIN", "ACTNUM", "TXID", "PID", "UID", "GlobalID"),
    search_fields={
        "account": (
            SearchColumn("ACTNUM", numeric=True),
            SearchColumn("TXID"),
            SearchColumn("PID"),
        ),
        "parcel": (
            SearchColumn("PIN", contains=True),
            SearchColumn("MAP"),
            SearchColumn("UID"),
        ),
        "owner": (
            SearchColumn("OWNER1", contains=True),
            SearchColumn("OWNER2", contains=True),
            SearchColumn("OWNER3", contains=True),
        ),
        "situs": (
            SearchColumn("SITUSSTR", contains=True),
            SearchColumn("SITUSCITY", contains=True),
        ),
    },
    fields=FieldMap(
        accounts=("ACTNUM", "TXID", "PID"),
        map_taxlots=("PIN", "MAP", "MTAXLOT"),
        owners=("OWNER1", "OWNER2", "OWNER3"),
        mailing_lines=("MAIL1", "MAIL2"),
        mailing_city="MAILCITY",
        mailing_state="MAILST",
        mailing_zip="ZIP",
        mailing_csz=None,
        situs="SITUSSTR",
        situs_city="SITUSCITY",
        situs_state=None,
        situs_zip="SITUSZIP",
        assessed_value="AV",
        market_value="RMV",
        market_land="RMVLAND",
        market_improvements="RMVIMPR",
        sale_price="SALEPR",
        sale_date=None,
        sale_year="YRSOLD",
        sale_month="MOSOLD",
        instrument="BOOKPG",
        deed_type=None,
        sale_type=None,
        acreage=("ACRES", "TaxlotAcre", "MapAcre"),
        year_built="YRBLT",
        property_class=("PCLS", "PCLSD", "PCLC", "PCLCD"),
        property_type="PROPTYP",
        legal=None,
        tax_amount=None,
        tax_code="TXCD",
        native_links={},
    ),
    update_fields=("LASTUPDATE", "created_date", "last_edited_date"),
    update_order_field="last_edited_date",
    cadence_fact=(
        "The layer publishes LASTUPDATE plus ArcGIS created and last-edited "
        "timestamps; each is retained as a separate native observation."
    ),
    official_hosts=("gis.co.linn.or.us",),
    authoritative_item_identities=("kolsen",),
    expected_wgs84_extent=(-123.28, 44.18, -121.78, 44.82),
    complementary_sources=(
        {
            "source_id": LINN_ACCOUNT_DETAIL_SOURCE_ID,
            "name": "Linn County Public Account Detail Search",
            "url": "https://www.linncountyor.gov/assessor/page/account-detail",
            "join_fields": ["ACTNUM", "SITUSSTR"],
            "adds": [
                "property descriptions",
                "tax amounts",
                "maps and diagrams",
                "assessor summary report",
            ],
        },
        {
            "source_id": LINN_MAPS_SOURCE_ID,
            "name": "Linn County Maps and Property Information",
            "url": "https://www.linncountyor.gov/property/page/maps-info",
            "join_fields": ["ACTNUM", "SITUSSTR"],
            "adds": ["planning map", "surveyor map", "property search guidance"],
        },
    ),
)

JOSEPHINE = SourceConfig(
    source_id=JOSEPHINE_SOURCE_ID,
    name="Josephine County Oregon Assessor Taxlots",
    publisher="Josephine County Assessor",
    county_name="Josephine County, Oregon",
    county_geoid="41033",
    layer_url=JOSEPHINE_LAYER_URL,
    service_url=JOSEPHINE_SERVICE_URL,
    layer_id=0,
    service_item_id=JOSEPHINE_ITEM_ID,
    item_api_url=None,
    item_page_url=None,
    expected_layer_name="Assessor Taxlots",
    source_wkid=2270,
    max_page_size=2_000,
    baseline_count=41_990,
    baseline_observed_at="2026-07-29",
    expected_schema_fingerprint=(
        "46dca0f553feb4ba3c7d3d69a694afdb"
        "7c3b86fd4a7f16c1b57013a77d52ad6f"
    ),
    required_fields=(
        "OBJECTID",
        "MapNum",
        "ACCOUNT",
        "NAME",
        "SITUS",
        "ASSD_VALUE",
        "RMV",
        "SALE_DATE",
        "INST_NO",
    ),
    native_id_fields=("ACCOUNT", "MapNum", "MNX"),
    search_fields={
        "account": (SearchColumn("ACCOUNT"),),
        "parcel": (
            SearchColumn("MapNum"),
            SearchColumn("MNX"),
            SearchColumn("TAXLOT"),
        ),
        "owner": (SearchColumn("NAME", contains=True),),
        "situs": (
            SearchColumn("SITUS", contains=True),
            SearchColumn("SITUS_CITY", contains=True),
        ),
    },
    fields=FieldMap(
        accounts=("ACCOUNT",),
        map_taxlots=("MapNum", "MNX", "TAXLOT"),
        owners=("NAME",),
        mailing_lines=("ADDR1", "ADDR2", "ADDR3"),
        mailing_city="City",
        mailing_state="State",
        mailing_zip="ZIP",
        mailing_csz="CSZ",
        situs="SITUS",
        situs_city="SITUS_CITY",
        situs_state="SITUS_ST",
        situs_zip="SITUS_ZIP",
        assessed_value="ASSD_VALUE",
        market_value="RMV",
        market_land="LAND_MKT",
        market_improvements="IMP_VALUE",
        sale_price="SALE_PRICE",
        sale_date="SALE_DATE",
        sale_year=None,
        sale_month=None,
        instrument="INST_NO",
        deed_type="DEED_TYPE",
        sale_type="SALE_TYPE",
        acreage=("ACREAGE", "LEGAL_ACRE", "GIS_Acres"),
        year_built="YR_BLT",
        property_class=("PROP_CLASS", "BLDG_CLASS"),
        property_type="TYPE",
        legal="LOC_DESC",
        tax_amount="Taxes",
        tax_code="CODE",
        native_links={},
    ),
    update_fields=(),
    update_order_field=None,
    cadence_fact=(
        "The layer does not publish an explicit row-edit timestamp; retrieval "
        "time, count, schema fingerprint, and service identity form the update packet."
    ),
    official_hosts=("gis.co.josephine.or.us",),
    authoritative_item_identities=(),
    expected_wgs84_extent=(-124.0, 41.96, -122.9, 42.8),
    complementary_sources=(
        {
            "source_id": JOSEPHINE_PROPERTY_DETAIL_SOURCE_ID,
            "name": "Josephine County Property Assessment and Tax Data",
            "url": "https://jcpa.josephinecounty.gov/home",
            "detail_url_template": (
                "https://jcpa.josephinecounty.gov/Property-Detail/"
                "PropertyQuickRefID/{ACCOUNT}"
            ),
            "join_fields": ["ACCOUNT"],
            "adds": [
                "certified and in-process values",
                "sales history",
                "improvements and land segments",
                "tax summary and payment information",
                "related properties",
            ],
        },
        {
            "source_id": JOSEPHINE_RECORDER_SOURCE_ID,
            "name": "Josephine County Clerk Digital Research Room",
            "url": "https://alt.co.josephine.or.us/",
            "join_fields": ["INST_NO", "SALE_DATE"],
            "adds": ["recorded deed and instrument search"],
        },
    ),
)

KLAMATH = SourceConfig(
    source_id=KLAMATH_SOURCE_ID,
    name="Klamath County Oregon Assessor Taxlots",
    publisher="Klamath County Assessor and Klamath County GIS",
    county_name="Klamath County, Oregon",
    county_geoid="41035",
    layer_url=KLAMATH_LAYER_URL,
    service_url=KLAMATH_SERVICE_URL,
    layer_id=1,
    service_item_id=KLAMATH_ITEM_ID,
    item_api_url=KLAMATH_ITEM_API_URL,
    item_page_url=KLAMATH_ITEM_PAGE_URL,
    expected_layer_name="KC_Taxlot_Publish",
    source_wkid=2914,
    max_page_size=1_000,
    baseline_count=61_228,
    baseline_observed_at="2026-07-29",
    expected_schema_fingerprint=(
        "56dc02c633c97c8d4b8c88ab68d2d9de"
        "7386e1bec5fcdfc3232972595493c042"
    ),
    required_fields=(
        "OBJECTID",
        "PROP_ID",
        "MTL",
        "OWNER_NAME",
        "SITUS_ADDRESS",
        "M50_VALUE",
        "Tot_Appr",
        "SALE_DATE",
        "HelionLink",
        "RDATE",
    ),
    native_id_fields=("PROP_ID", "MTL", "ORTaxlot", "GlobalID"),
    search_fields={
        "account": (SearchColumn("PROP_ID", numeric=True),),
        "parcel": (
            SearchColumn("MTL"),
            SearchColumn("ORTaxlot"),
            SearchColumn("MapNumber"),
            SearchColumn("Taxmap"),
        ),
        "owner": (SearchColumn("OWNER_NAME", contains=True),),
        "situs": (
            SearchColumn("SITUS_ADDRESS", contains=True),
            SearchColumn("SITUS_CSZ", contains=True),
        ),
    },
    fields=FieldMap(
        accounts=("PROP_ID",),
        map_taxlots=("MTL", "MAP_TAXLOT", "ORTaxlot", "MapNumber", "Taxmap"),
        owners=("OWNER_NAME",),
        mailing_lines=("OWNER_ADDR1", "OWNER_ADDR2", "OWNER_ADDR3"),
        mailing_city=None,
        mailing_state=None,
        mailing_zip=None,
        mailing_csz="OWNER_CSZ",
        situs="SITUS_ADDRESS",
        situs_city="SITUSCITY",
        situs_state=None,
        situs_zip="SITUSZIP",
        assessed_value="M50_VALUE",
        market_value="Tot_Appr",
        market_land="LND_APPR",
        market_improvements="IMP_APPR",
        sale_price="SALE_PRICE",
        sale_date="SALE_DATE",
        sale_year="YRSOLD",
        sale_month="MOSOLD",
        instrument="REC",
        deed_type=None,
        sale_type=None,
        acreage=("ACREAGE", "VALUATION_ACRES", "GIS_Acres"),
        year_built="YRBLT",
        property_class=("PROP_CLASS", "PCLS", "PCLSD", "PCLC", "PCLCD"),
        property_type="PROPTYP",
        legal="LEGAL",
        tax_amount=None,
        tax_code="Taxcode",
        native_links={
            "property_detail": "HelionLink",
            "recorder_document": "REC_PATH",
            "current_tax_map": "TaxmapWebPath",
            "historical_tax_map": "HistWebPth",
        },
    ),
    update_fields=("RDATE", "DDate", "Heliondate"),
    update_order_field="RDATE",
    cadence_fact=(
        "Klamath County states that taxlot linework and owner/value data are "
        "updated weekly; the layer also publishes RDATE and editingInfo."
    ),
    official_hosts=(),
    authoritative_item_identities=("H6Mh1bySxR4oHx6x", "ewilde"),
    expected_wgs84_extent=(-122.35, 41.96, -120.86, 43.64),
    complementary_sources=(
        {
            "source_id": KLAMATH_PROPERTY_DETAIL_SOURCE_ID,
            "name": "Klamath County Property Search Online",
            "url": "https://assessor.klamathcounty.org/PSO/",
            "detail_url_template": (
                "https://assessor.klamathcounty.org/PSO/detail/{PROP_ID}/R"
            ),
            "join_fields": ["PROP_ID"],
            "adds": [
                "value history",
                "assessment summary",
                "deed and sales history",
                "tax statements, balances, payments, and payoff",
            ],
        },
        {
            "source_id": KLAMATH_TAX_MAP_SOURCE_ID,
            "name": "Klamath County Current and Historical Tax Maps",
            "url_fields": ["TaxmapWebPath", "HistWebPth"],
            "join_fields": ["Taxmap", "MapNumber"],
            "adds": ["current tax map PDF", "historical tax map PDF"],
        },
        {
            "source_id": KLAMATH_RECORDER_SOURCE_ID,
            "name": "Klamath County Clerk Digital Research Room",
            "url_field": "REC_PATH",
            "join_fields": ["REC", "SALE_DATE"],
            "adds": ["recorded instrument detail"],
        },
        {
            "source_id": KLAMATH_RECORDS_REQUEST_SOURCE_ID,
            "name": "Klamath County Public Records Request",
            "url": "https://klamathcountyor.nextrequest.com/",
            "join_fields": ["PROP_ID", "MTL"],
            "adds": ["request route for records absent from published systems"],
        },
    ),
)

SOURCES: Mapping[str, SourceConfig] = {
    config.source_id: config for config in (LINN, JOSEPHINE, KLAMATH)
}

SOURCE_CATALOG_METADATA: Mapping[str, Mapping[str, Any]] = {
    config.source_id: {
        "source_id": config.source_id,
        "name": config.name,
        "category": "property",
        "record_types": ["parcel"],
        "jurisdiction": config.county_geoid,
        "access_method": "rest_api",
        "auth": "none",
        "official": True,
        "url": config.layer_url,
        "query_tool": "tools/query_oregon_linn_josephine_klamath_assessors.py",
        "search_fields": sorted(config.search_fields),
        "supports_geometry": True,
        "pagination": "object_id_keyset",
    }
    for config in SOURCES.values()
}
CATALOG_METADATA = SOURCE_CATALOG_METADATA


class SourceSelectionError(ValueError):
    """Source/query selection failure with contract status."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.SOURCE_CHANGED,
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
class LayerContract:
    schema_fingerprint: str
    server_page_size: int
    object_id_field: str
    source_wkid: int


@dataclass(frozen=True)
class CursorState:
    source_id: str
    operation: str
    criteria_fingerprint: str
    anchor: int
    total_count: int
    schema_fingerprint: str


@dataclass(frozen=True)
class ArcGISBatch:
    features: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    total_count: int
    start_anchor: int | None
    end_anchor: int | None
    remaining_after_anchor: int
    schema_fingerprint: str
    metadata: Mapping[str, Any]
    pages_fetched: int
    errors: tuple[PublicRecordsError, ...]


class OregonTriCountyAssessorClient(ArcGISRESTClient):
    """Small facade for metadata, counts, keyset pages, and update sentinels."""

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
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "ArcGIS returned invalid layer metadata",
                url=self.layer_url,
                details={"response": payload},
            )
        return payload

    def fetch_item_metadata(self) -> Mapping[str, Any] | None:
        if self.config.item_api_url is None:
            return None
        payload = self._request_json(self.config.item_api_url, params={"f": "json"})
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "ArcGIS returned invalid item metadata",
                url=self.config.item_api_url,
                details={"response": payload},
            )
        return payload

    def fetch_count(self, where: str) -> int:
        payload = self._request_json(
            self.query_url,
            params={"where": where, "returnCountOnly": "true", "f": "json"},
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
        record_count: int,
        return_geometry: bool,
        out_fields: str = "*",
    ) -> tuple[Mapping[str, Any], ...]:
        params: dict[str, Any] = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": str(return_geometry).lower(),
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
                "ArcGIS response lacks a valid features array",
                url=self.query_url,
            )
        return tuple(features)

    def fetch_latest_update(self, field_name: str) -> Mapping[str, Any] | None:
        payload = self._request_json(
            self.query_url,
            params={
                "where": f"{field_name} IS NOT NULL",
                "outFields": f"{self.config.object_id_field},{field_name}",
                "returnGeometry": "false",
                "resultRecordCount": 1,
                "orderByFields": (
                    f"{field_name} DESC,{self.config.object_id_field} DESC"
                ),
                "f": "json",
            },
        )
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "ArcGIS returned an invalid update-sentinel response",
                url=self.query_url,
                details={"response": payload},
            )
        features = payload.get("features")
        if not isinstance(features, list):
            raise SourceSchemaError(
                "ArcGIS update-sentinel response lacks features",
                url=self.query_url,
            )
        return features[0] if features else None


def _source(source_id: str) -> SourceConfig:
    try:
        return SOURCES[source_id]
    except KeyError as error:
        raise SourceSelectionError(
            "unknown_source",
            f"unknown Linn/Josephine/Klamath assessor source: {source_id}",
            details={"known_sources": sorted(SOURCES)},
        ) from error


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


def _number(value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = _clean_text(value)
    if not text:
        return None
    try:
        parsed = float(text.replace(",", "").replace("$", ""))
    except ValueError:
        return None
    return int(parsed) if parsed.is_integer() else parsed


def _instant(value: Any) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return (
                datetime.fromtimestamp(value / 1000, tz=timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )
        except (OSError, OverflowError, ValueError):
            return None
    return _clean_text(value)


def _date_from_epoch(value: Any) -> str | None:
    instant = _instant(value)
    return instant[:10] if instant and re.match(r"\d{4}-\d{2}-\d{2}", instant) else None


def _yyyymmdd(value: Any) -> str | None:
    text = _clean_text(value)
    if not text or not re.fullmatch(r"\d{8}", text):
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def _unique_text(
    attributes: Mapping[str, Any],
    fields: Sequence[str],
) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for field_name in fields:
        value = _clean_text(attributes.get(field_name))
        if value and value.casefold() not in seen:
            values.append(value)
            seen.add(value.casefold())
    return values


def _first_text(
    attributes: Mapping[str, Any],
    fields: Sequence[str],
) -> str | None:
    values = _unique_text(attributes, fields)
    return values[0] if values else None


def _zip(value: Any) -> str | None:
    text = _clean_text(value)
    if text and text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
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
    declared_oid = metadata.get("objectIdField")
    if not declared_oid:
        declared_oid = next(
            (
                field.get("name")
                for field in fields
                if field.get("type") == "esriFieldTypeOID"
            ),
            None,
        )
    if declared_oid != config.object_id_field:
        raise SourceSchemaError(
            "ArcGIS object ID field changed",
            url=config.layer_url,
            details={
                "expected": config.object_id_field,
                "observed": declared_oid,
            },
        )
    advanced = metadata.get("advancedQueryCapabilities")
    if (
        not isinstance(advanced, Mapping)
        or not advanced.get("supportsPagination")
        or not advanced.get("supportsOrderBy")
    ):
        raise SourceSchemaError(
            "ArcGIS layer no longer declares ordered query support",
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
        object_id_field=declared_oid,
        source_wkid=observed_wkid,
    )


def _extent_center(extent: Any) -> tuple[float, float] | None:
    if (
        not isinstance(extent, list)
        or len(extent) != 2
        or any(not isinstance(point, list) or len(point) < 2 for point in extent)
    ):
        return None
    try:
        return (
            (float(extent[0][0]) + float(extent[1][0])) / 2,
            (float(extent[0][1]) + float(extent[1][1])) / 2,
        )
    except (TypeError, ValueError):
        return None


def candidate_jurisdiction_evidence(
    item: Mapping[str, Any],
    *,
    expected_extent: tuple[float, float, float, float],
    official_hosts: Sequence[str] = (),
    authoritative_identities: Sequence[str] = (),
) -> dict[str, Any]:
    """Return positive identity signals for an ArcGIS discovery candidate."""

    host = (urlparse(_clean_text(item.get("url")) or "").hostname or "").lower()
    item_identities = {
        value.casefold()
        for value in (_clean_text(item.get("owner")), _clean_text(item.get("orgId")))
        if value
    }
    expected_identities = {
        value.casefold() for value in authoritative_identities if value
    }
    center = _extent_center(item.get("extent"))
    min_x, min_y, max_x, max_y = expected_extent
    extent_matches = bool(
        center
        and min_x <= center[0] <= max_x
        and min_y <= center[1] <= max_y
    )
    host_matches = any(
        host == expected.lower() or host.endswith(f".{expected.lower()}")
        for expected in official_hosts
    )
    identity_matches = bool(item_identities & expected_identities)
    return {
        "title": _clean_text(item.get("title")),
        "owner": _clean_text(item.get("owner")),
        "org_id": _clean_text(item.get("orgId")),
        "service_host": host or None,
        "extent_center": list(center) if center else None,
        "official_host_matches": host_matches,
        "publisher_identity_matches": identity_matches,
        "extent_matches": extent_matches,
        "verified": host_matches and extent_matches
        or identity_matches and extent_matches,
        "decision_basis": (
            "official_host_plus_extent"
            if host_matches and extent_matches
            else "publisher_identity_plus_extent"
            if identity_matches and extent_matches
            else "insufficient_positive_jurisdiction_evidence"
        ),
    }


def _item_identity(
    config: SourceConfig,
    item: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if item is None:
        return {
            "item_id": config.service_item_id,
            "item_api_url": None,
            "item_page_url": None,
            "identity_source": "layer_serviceItemId_and_official_county_host",
            "jurisdiction_evidence": {
                "official_service_host": urlparse(config.layer_url).hostname,
                "verified": True,
            },
        }
    if item.get("id") != config.service_item_id:
        raise SourceSchemaError(
            "ArcGIS item identity changed",
            url=config.item_api_url or config.layer_url,
            details={
                "expected": config.service_item_id,
                "observed": item.get("id"),
            },
        )
    evidence = candidate_jurisdiction_evidence(
        item,
        expected_extent=config.expected_wgs84_extent,
        official_hosts=config.official_hosts,
        authoritative_identities=config.authoritative_item_identities,
    )
    if not evidence["verified"]:
        raise SourceSchemaError(
            "ArcGIS item lacks positive jurisdiction identity evidence",
            url=config.item_api_url or config.layer_url,
            details=evidence,
        )
    return {
        "item_id": item.get("id"),
        "title": _clean_text(item.get("title")),
        "type": _clean_text(item.get("type")),
        "owner": _clean_text(item.get("owner")),
        "org_id": _clean_text(item.get("orgId")),
        "access": _clean_text(item.get("access")),
        "service_url": _clean_text(item.get("url")),
        "item_api_url": config.item_api_url,
        "item_page_url": config.item_page_url,
        "created": _instant(item.get("created")),
        "modified": _instant(item.get("modified")),
        "jurisdiction_evidence": evidence,
    }


def _sql_text(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        raise SourceSelectionError("blank_query", "search value must not be blank")
    return text.replace("'", "''")


def _column_clause(column: SearchColumn, selector: str) -> str | None:
    if column.numeric:
        if not re.fullmatch(r"[+-]?\d+", selector):
            return None
        return f"{column.name} = {int(selector)}"
    value = selector.upper()
    if column.contains:
        return f"UPPER({column.name}) LIKE '%{value}%'"
    return f"UPPER({column.name}) = '{value}'"


def _where(
    config: SourceConfig,
    *,
    selector: str | None,
    search_field: str,
) -> str:
    if search_field == "all":
        return "1=1"
    value = _sql_text(selector)
    groups = (
        tuple(config.search_fields)
        if search_field == "auto"
        else (search_field,)
    )
    if any(group not in config.search_fields for group in groups):
        raise SourceSelectionError(
            "unsupported_search_field",
            f"{config.source_id} does not publish searchable {search_field} fields",
            details={"supported_fields": sorted(config.search_fields)},
        )
    clauses = [
        clause
        for group in groups
        for column in config.search_fields[group]
        if (clause := _column_clause(column, value)) is not None
    ]
    if not clauses:
        raise SourceSelectionError(
            "selector_type_mismatch",
            f"{selector!r} is not compatible with {search_field}",
        )
    return clauses[0] if len(clauses) == 1 else f"({' OR '.join(clauses)})"


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
            "pagination": "object_id_keyset",
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "source": state.source_id,
        "operation": state.operation,
        "criteria": state.criteria_fingerprint,
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
            "cursor does not belong to the Linn/Josephine/Klamath adapter",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(token + padding).decode())
        state = CursorState(
            source_id=str(payload["source"]),
            operation=str(payload["operation"]),
            criteria_fingerprint=str(payload["criteria"]),
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
        or state.anchor < 0
        or state.total_count < 0
        or not re.fullmatch(r"[0-9a-f]{64}", state.schema_fingerprint)
    ):
        raise SourceSelectionError(
            "invalid_cursor",
            "cursor values are inconsistent",
        )
    return state


def _after_anchor_where(config: SourceConfig, where: str, anchor: int) -> str:
    return f"({where}) AND {config.object_id_field} > {anchor}"


def _pagination_error(code: str, message: str, **details: Any) -> PublicRecordsError:
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
    contract = _metadata_schema(config, metadata)
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
        if cursor_state.schema_fingerprint != contract.schema_fingerprint:
            raise SourceSelectionError(
                "cursor_schema_changed",
                "source schema changed after the cursor was issued",
            )

    initial_count = client.fetch_count(where)
    if cursor_state is not None and cursor_state.total_count != initial_count:
        raise SourceSelectionError(
            "cursor_snapshot_changed",
            "matching source count changed after the cursor was issued",
            details={
                "cursor_count": cursor_state.total_count,
                "current_count": initial_count,
            },
        )

    start_anchor = cursor_state.anchor if cursor_state else None
    anchor = start_anchor
    page_size = min(
        int(getattr(client, "page_size", contract.server_page_size)),
        contract.server_page_size,
    )
    collected: list[Mapping[str, Any]] = []
    pages_fetched = 0
    errors: list[PublicRecordsError] = []
    while len(collected) < limit:
        page_where = (
            _after_anchor_where(config, where, anchor)
            if anchor is not None
            else where
        )
        requested = min(page_size, limit - len(collected))
        page = client.fetch_page(
            where=page_where,
            record_count=requested,
            return_geometry=return_geometry,
        )
        pages_fetched += 1
        if not page:
            break
        prior = anchor
        for feature in page:
            oid = _feature_oid(config, feature)
            if prior is not None and oid <= prior:
                errors.append(
                    _pagination_error(
                        "pagination_repeat_or_reorder",
                        "ArcGIS repeated or reordered a feature",
                        object_id=oid,
                        previous_object_id=prior,
                    )
                )
                break
            collected.append(feature)
            prior = oid
        if errors:
            break
        anchor = prior
        if len(page) < requested:
            break

    final_count = client.fetch_count(where)
    if final_count != initial_count:
        errors.append(
            _pagination_error(
                "count_changed_during_traversal",
                "matching source count changed during keyset traversal",
                initial_count=initial_count,
                final_count=final_count,
            )
        )

    remaining = 0
    if anchor is not None and not errors:
        remaining = client.fetch_count(_after_anchor_where(config, where, anchor))
    next_cursor = None
    if anchor is not None and remaining > 0 and not errors:
        next_cursor = _encode_cursor(
            CursorState(
                source_id=config.source_id,
                operation=operation,
                criteria_fingerprint=criteria,
                anchor=anchor,
                total_count=final_count,
                schema_fingerprint=contract.schema_fingerprint,
            )
        )
    return ArcGISBatch(
        features=tuple(collected),
        next_cursor=next_cursor,
        total_count=final_count,
        start_anchor=start_anchor,
        end_anchor=anchor,
        remaining_after_anchor=remaining,
        schema_fingerprint=contract.schema_fingerprint,
        metadata=dict(metadata),
        pages_fetched=pages_fetched,
        errors=tuple(errors),
    )


def _address(
    attributes: Mapping[str, Any],
    *,
    lines: Sequence[str],
    city: str | None,
    state: str | None,
    postal_code: str | None,
    csz: str | None,
) -> dict[str, Any]:
    line_values = _unique_text(attributes, lines)
    csz_value = _clean_text(attributes.get(csz)) if csz else None
    raw = ", ".join([*line_values, *([csz_value] if csz_value else [])]) or None
    return {
        "raw": raw,
        "address_lines": line_values,
        "city_state_zip_raw": csz_value,
        "city": _clean_text(attributes.get(city)) if city else None,
        "state": _clean_text(attributes.get(state)) if state else None,
        "postal_code": _zip(attributes.get(postal_code)) if postal_code else None,
        "country": "US",
    }


def _value_observation(
    attributes: Mapping[str, Any],
    field_name: str | None,
    interpretation: str,
) -> dict[str, Any] | None:
    if not field_name or attributes.get(field_name) is None:
        return None
    return {
        "interpretation": interpretation,
        "source_field": field_name,
        "raw_value": attributes.get(field_name),
        "value": _number(attributes.get(field_name)),
        "currency": "USD",
    }


def _sale(
    config: SourceConfig,
    attributes: Mapping[str, Any],
) -> dict[str, Any]:
    fields = config.fields
    date_info: dict[str, Any] | None = None
    if fields.sale_date and attributes.get(fields.sale_date) is not None:
        date_info = {
            "date_iso": _date_from_epoch(attributes.get(fields.sale_date)),
            "precision": "day",
            "source_field": fields.sale_date,
            "raw_value": attributes.get(fields.sale_date),
        }
    elif fields.sale_year:
        year = _clean_text(attributes.get(fields.sale_year))
        month = (
            _clean_text(attributes.get(fields.sale_month))
            if fields.sale_month
            else None
        )
        if year and re.fullmatch(r"\d{4}", year):
            month_number = int(month) if month and month.isdigit() else 0
            if 1 <= month_number <= 12:
                date_info = {
                    "date_iso": f"{year}-{month_number:02d}",
                    "precision": "month",
                    "source_fields": [fields.sale_year, fields.sale_month],
                    "raw_year": attributes.get(fields.sale_year),
                    "raw_month": attributes.get(fields.sale_month),
                }
            else:
                date_info = {
                    "date_iso": year,
                    "precision": "year",
                    "source_field": fields.sale_year,
                    "raw_year": attributes.get(fields.sale_year),
                }
    return {
        "date": date_info,
        "price": _number(attributes.get(fields.sale_price))
        if fields.sale_price
        else None,
        "price_source_field": fields.sale_price,
        "instrument": _clean_text(attributes.get(fields.instrument))
        if fields.instrument
        else None,
        "instrument_source_field": fields.instrument,
        "deed_type": _clean_text(attributes.get(fields.deed_type))
        if fields.deed_type
        else None,
        "sale_type": _clean_text(attributes.get(fields.sale_type))
        if fields.sale_type
        else None,
        "scope": "latest_sale_fields_published_on_current_parcel_row",
    }


def _record_links(
    config: SourceConfig,
    attributes: Mapping[str, Any],
) -> dict[str, str]:
    links = {
        label: value
        for label, field_name in config.fields.native_links.items()
        if (value := _clean_text(attributes.get(field_name)))
    }
    if config.source_id == JOSEPHINE_SOURCE_ID:
        account = _clean_text(attributes.get("ACCOUNT"))
        if account:
            links["property_detail"] = (
                "https://jcpa.josephinecounty.gov/Property-Detail/"
                f"PropertyQuickRefID/{account}"
            )
    if config.source_id == LINN_SOURCE_ID:
        links["account_detail_search"] = (
            "https://www.linncountyor.gov/assessor/page/account-detail"
        )
    return links


def _update_evidence(
    config: SourceConfig,
    attributes: Mapping[str, Any],
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    for field_name in config.update_fields:
        raw_value = attributes.get(field_name)
        if raw_value is None:
            continue
        if field_name == "RDATE":
            normalized = _yyyymmdd(raw_value)
            value_kind = "source_date"
        else:
            normalized = _instant(raw_value)
            value_kind = "source_timestamp"
        observations.append(
            {
                "source_field": field_name,
                "raw_value": raw_value,
                "normalized": normalized,
                "value_kind": value_kind,
            }
        )
    return {
        "observations": observations,
        "publisher_cadence_fact": config.cadence_fact,
        "explicit_row_update_field_published": bool(config.update_fields),
    }


def _normalize_feature(
    config: SourceConfig,
    feature: Mapping[str, Any],
    *,
    schema_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes = _feature_attributes(feature)
    oid = _feature_oid(config, feature)
    native_id = _first_text(attributes, config.native_id_fields) or str(oid)
    fields = config.fields
    owner_values = _unique_text(attributes, fields.owners)
    value_observations = [
        observation
        for observation in (
            _value_observation(
                attributes, fields.assessed_value, "assessed_value"
            ),
            _value_observation(
                attributes, fields.market_value, "real_market_or_appraised_total"
            ),
            _value_observation(
                attributes, fields.market_land, "market_or_appraised_land"
            ),
            _value_observation(
                attributes,
                fields.market_improvements,
                "market_or_appraised_improvements",
            ),
        )
        if observation is not None
    ]
    acreage_observations = {
        field_name: _number(attributes.get(field_name))
        for field_name in fields.acreage
        if attributes.get(field_name) is not None
    }
    situs_raw = _clean_text(attributes.get(fields.situs))
    situs_city = (
        _clean_text(attributes.get(fields.situs_city))
        if fields.situs_city
        else None
    )
    situs_state = (
        _clean_text(attributes.get(fields.situs_state))
        if fields.situs_state
        else STATE_CODE
    )
    situs_zip = (
        _zip(attributes.get(fields.situs_zip)) if fields.situs_zip else None
    )
    geometry = feature.get("geometry") if geometry_requested else None
    if geometry_requested and geometry is not None and not isinstance(
        geometry, Mapping
    ):
        raise ValueError("ArcGIS feature geometry is not an object")
    record = {
        "canonical_ref": canonical_property_ref(
            config.source_id,
            config.county_geoid,
            "parcel",
            native_id,
        ),
        "record_kind": "parcel",
        "source_id": config.source_id,
        "county": {
            "name": config.county_name,
            "geoid": config.county_geoid,
            "state": STATE_CODE,
        },
        "object_id": oid,
        "native_id": native_id,
        "native_identity": {
            field_name: attributes.get(field_name)
            for field_name in config.native_id_fields
            if attributes.get(field_name) is not None
        },
        "assessment_account_ids": _unique_text(attributes, fields.accounts),
        "map_taxlot_ids": _unique_text(attributes, fields.map_taxlots),
        "owners": [
            {
                "raw_name": owner,
                "role": "assessment_roll_owner",
                "assertion_type": "assessment_roll",
                "confidence": "high",
                "source_field": next(
                    field_name
                    for field_name in fields.owners
                    if _clean_text(attributes.get(field_name)) == owner
                ),
            }
            for owner in owner_values
        ],
        "mailing_address": _address(
            attributes,
            lines=fields.mailing_lines,
            city=fields.mailing_city,
            state=fields.mailing_state,
            postal_code=fields.mailing_zip,
            csz=fields.mailing_csz,
        ),
        "situs_address": {
            "raw": situs_raw,
            "city": situs_city,
            "state": situs_state,
            "postal_code": situs_zip,
            "source_fields": [
                name
                for name in (
                    fields.situs,
                    fields.situs_city,
                    fields.situs_state,
                    fields.situs_zip,
                )
                if name
            ],
        },
        "assessment": {
            "assessed_value": _number(attributes.get(fields.assessed_value))
            if fields.assessed_value
            else None,
            "market_or_appraised_total": _number(
                attributes.get(fields.market_value)
            )
            if fields.market_value
            else None,
            "market_or_appraised_land": _number(
                attributes.get(fields.market_land)
            )
            if fields.market_land
            else None,
            "market_or_appraised_improvements": _number(
                attributes.get(fields.market_improvements)
            )
            if fields.market_improvements
            else None,
            "currency": "USD",
            "native_observations": value_observations,
        },
        "sale": _sale(config, attributes),
        "property": {
            "acreage_observations": acreage_observations,
            "year_built": _number(attributes.get(fields.year_built))
            if fields.year_built
            else None,
            "classification": {
                field_name: _clean_text(attributes.get(field_name))
                for field_name in fields.property_class
                if attributes.get(field_name) is not None
            },
            "property_type": _clean_text(attributes.get(fields.property_type))
            if fields.property_type
            else None,
            "legal_description": _clean_text(attributes.get(fields.legal))
            if fields.legal
            else None,
        },
        "tax": {
            "published_amount": _number(attributes.get(fields.tax_amount))
            if fields.tax_amount
            else None,
            "tax_code": _clean_text(attributes.get(fields.tax_code))
            if fields.tax_code
            else None,
            "source_fields": [
                field_name
                for field_name in (fields.tax_amount, fields.tax_code)
                if field_name
            ],
        },
        "official_links": _record_links(config, attributes),
        "update_evidence": _update_evidence(config, attributes),
        "source_geometry_crs": config.source_crs,
        "geometry_crs": "EPSG:4326" if geometry is not None else None,
        "geometry": dict(geometry) if isinstance(geometry, Mapping) else None,
        "native_fields": dict(attributes),
        "provenance": {
            "publisher": config.publisher,
            "layer_url": config.layer_url,
            "query_url": f"{config.layer_url}/query",
            "service_item_id": config.service_item_id,
            "item_page_url": config.item_page_url,
            "object_id_field": config.object_id_field,
            "object_id": oid,
            "schema_fingerprint": schema_value,
            "normalization": "county_specific_field_map_with_native_fields_retained",
        },
    }
    return record


def _jurisdiction(config: SourceConfig) -> JurisdictionMetadata:
    return JurisdictionMetadata(
        jurisdiction_id=config.county_geoid,
        name=config.county_name,
        state_code=STATE_CODE,
        county_fips=config.county_geoid,
        metadata={"state_fips": STATE_FIPS, "publisher": config.publisher},
    )


def _build_query(
    config: SourceConfig,
    *,
    operation: str,
    selector: str | None,
    search_field: str,
    limit: int,
    cursor: str | None,
    geometry: bool,
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
            },
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "pagination": "object_id_keyset",
                "ordering": f"{config.object_id_field} ASC",
            },
        ),
    )


def _client(
    args: argparse.Namespace,
    config: SourceConfig,
) -> OregonTriCountyAssessorClient:
    return OregonTriCountyAssessorClient(
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
    errors = list(batch.errors)
    records: list[dict[str, Any]] = []
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
                    details={"record_index": index},
                )
            )
            break
    editing_info = batch.metadata.get("editingInfo")
    data_last_edit = (
        _instant(editing_info.get("dataLastEditDate"))
        if isinstance(editing_info, Mapping)
        else None
    )
    snapshot = {
        "total_matching_records": batch.total_count,
        "start_object_id_exclusive": batch.start_anchor,
        "end_object_id_inclusive": batch.end_anchor,
        "returned_records": len(records),
        "remaining_after_anchor": batch.remaining_after_anchor,
        "continuation_available": batch.next_cursor is not None,
        "pages_fetched": batch.pages_fetched,
        "schema_fingerprint": batch.schema_fingerprint,
        "service_data_last_edit": data_last_edit,
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
            warnings=config.warnings,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
        warnings=config.warnings,
    )


def _command_field(args: argparse.Namespace) -> str:
    if args.command in {"owner", "account", "parcel", "situs"}:
        return args.command
    if args.command == "scan":
        return "all"
    return args.field


def _execute_records(
    args: argparse.Namespace,
    *,
    client: Any = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    config = _source(args.source)
    search_field = _command_field(args)
    selector = getattr(args, "query", None)
    query = _build_query(
        config,
        operation=args.command,
        selector=selector,
        search_field=search_field,
        limit=args.limit,
        cursor=args.cursor,
        geometry=args.geometry,
    )
    try:
        where = _where(config, selector=selector, search_field=search_field)
        batch = _fetch_batch(
            client or _client(args, config),
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
    log_results: bool = True,
) -> PublicRecordsResult:
    sentinel_value = (
        "761920"
        if config is LINN
        else "R333020"
        if config is JOSEPHINE
        else "871965"
    )
    query = _build_query(
        config,
        operation="probe",
        selector=sentinel_value,
        search_field="account",
        limit=1,
        cursor=None,
        geometry=True,
    )
    try:
        active_client = client or _client(args, config)
        metadata = active_client.fetch_metadata()
        contract = _metadata_schema(config, metadata)
        item = _item_identity(config, active_client.fetch_item_metadata())
        total_count = active_client.fetch_count("1=1")
        where = _where(
            config,
            selector=sentinel_value,
            search_field="account",
        )
        sentinel_count = active_client.fetch_count(where)
        if sentinel_count <= 0:
            raise SourceSchemaError(
                "configured source sentinel was not found",
                url=config.layer_url,
                details={"selector": sentinel_value},
            )
        rows = active_client.fetch_page(
            where=where,
            record_count=1,
            return_geometry=True,
        )
        if len(rows) != 1:
            raise SourceSchemaError(
                "source sentinel did not return exactly one row",
                url=config.layer_url,
                details={"returned": len(rows)},
            )
        latest_update = (
            active_client.fetch_latest_update(config.update_order_field)
            if config.update_order_field
            else None
        )
        editing_info = metadata.get("editingInfo")
        representative = _normalize_feature(
            config,
            rows[0],
            schema_value=contract.schema_fingerprint,
            geometry_requested=True,
        )
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
                        "object_id_field": contract.object_id_field,
                        "geometry_type": metadata.get("geometryType"),
                    },
                    "item_identity": item,
                    "component_total_count": total_count,
                    "maximum_page_size": contract.server_page_size,
                    "source_crs": f"EPSG:{contract.source_wkid}",
                    "schema_fingerprint": contract.schema_fingerprint,
                    "schema_baseline": {
                        "expected_fingerprint": (
                            config.expected_schema_fingerprint
                        ),
                        "matches": (
                            contract.schema_fingerprint
                            == config.expected_schema_fingerprint
                        ),
                        "field_count": len(metadata.get("fields", [])),
                    },
                    "count_baseline": {
                        "observed_count": config.baseline_count,
                        "observed_at": config.baseline_observed_at,
                        "current_count": total_count,
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
                        "latest_native_update_row": (
                            dict(_feature_attributes(latest_update))
                            if latest_update
                            else None
                        ),
                        "latest_native_update_field": config.update_order_field,
                        "cadence_fact": config.cadence_fact,
                    },
                    "sentinel_strategy": "configured_exact_account",
                    "sentinel_count": sentinel_count,
                    "representative_row": representative,
                    "complementary_sources": list(config.complementary_sources),
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
                    code="probe_failed",
                    message=str(error),
                    category="source_schema",
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
        "source_family_id": SOURCE_FAMILY_ID,
        "umbrella_source_id": SOURCE_FAMILY_ID,
        "umbrella_source_id_is_external_source": False,
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
                "update_fields": list(config.update_fields),
                "complementary_sources": list(config.complementary_sources),
                "warnings": list(config.warnings),
            }
            for config in SOURCES.values()
        ],
        "process_learnings": [
            {
                "scope": "jurisdiction_validation",
                "learning": (
                    "County-name title matching is insufficient. Discovery "
                    "packets retain official host or ArcGIS organization, "
                    "publisher identity, item ID, and extent evidence."
                ),
            },
            {
                "scope": "county_field_maps",
                "learning": (
                    "Shared ArcGIS transport does not imply shared assessor "
                    "semantics; canonical observations identify their native "
                    "field while the full native row remains available."
                ),
            },
            {
                "scope": "paging",
                "learning": (
                    "OBJECTID keyset anchors avoid offset drift and cursors are "
                    "bound to source, query, geometry mode, count, and schema."
                ),
            },
            {
                "scope": "complementary_records",
                "learning": (
                    "Parcel rows expose join keys to richer official account "
                    "detail, recorder, tax-map, and public-request routes."
                ),
            },
        ],
    }


def _all_probe_payload(
    args: argparse.Namespace,
    *,
    log_results: bool = True,
) -> dict[str, Any]:
    components = [
        _execute_probe(args, config, log_results=log_results).to_dict()
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
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute source listing, record lookup/scan, or bounded live probe."""

    if args.command == "sources":
        return _sources_payload()
    if args.command == "probe":
        if args.all_sources:
            return _all_probe_payload(args, log_results=log_results)
        return _execute_probe(
            args,
            _source(args.source),
            client=client,
            log_results=log_results,
        )
    return _execute_records(args, client=client, log_results=log_results)


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
        summary=f"Linn/Josephine/Klamath assessors {args.command}",
        result_count=count,
    ):
        return
    if args.command == "sources":
        print(f"Linn/Josephine/Klamath assessor sources: {count}")
        for source in payload["sources"]:
            print(
                f"  {source['source_id']} | "
                f"{', '.join(source['search_fields'])}"
            )
        return
    if args.command == "probe" and args.all_sources:
        print(f"Linn/Josephine/Klamath assessor probes: {payload['status']}")
        for component in payload["components"]:
            print(
                f"  {component['query']['source']['source_id']} | "
                f"{component['status']}"
            )
        return
    print(
        f"Linn/Josephine/Klamath {args.command}: "
        f"{payload.get('status')} ({count} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in payload.get("records", []):
        print(f"  {record.get('native_id')} | {record.get('source_id')}")
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
    parser.add_argument("--source", required=True, choices=sorted(SOURCES))
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--cursor",
        help="Query-bound OBJECTID continuation cursor from an earlier result",
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
            "Query official Linn, Josephine, and Klamath County assessor parcels"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser("sources", help="List parcel and complementary sources")
    add_output_args(sources)

    search = sub.add_parser("search", help="Search one selected assessor layer")
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=("auto", "account", "parcel", "owner", "situs"),
        default="auto",
    )
    _add_query_arguments(search)

    for command in ("owner", "account", "parcel", "situs"):
        query_parser = sub.add_parser(
            command,
            help=f"Search the selected layer by {command}",
        )
        query_parser.add_argument("query")
        query_parser.set_defaults(field=command)
        _add_query_arguments(query_parser)

    scan = sub.add_parser("scan", help="Traverse one layer in OBJECTID order")
    scan.set_defaults(field="all", query=None)
    _add_query_arguments(scan)

    probe = sub.add_parser("probe", help="Run bounded source probe packets")
    selection = probe.add_mutually_exclusive_group(required=True)
    selection.add_argument("--source", choices=sorted(SOURCES))
    selection.add_argument("--all", action="store_true", dest="all_sources")
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
    if hasattr(args, "query") and args.query is not None and not args.query.strip():
        parser.error("query must not be blank")
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
