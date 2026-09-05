#!/usr/bin/env python3
"""Query Yamhill County, Oregon property and assessment-event sources.

The adapter keeps four official components independently attributable:

* Aumentum AscendWeb property search and rich account detail;
* the county's canonical current A&T Taxlots ArcGIS layer;
* the ConnectExplorer retired-taxlot lineage layer; and
* the current annual assessment-permit ArcGIS layer.

Examples:
    uv run python tools/query_oregon_yamhill_property.py sources
    uv run python tools/query_oregon_yamhill_property.py search 41270 \
        --source us-or-yamhill-county-ascendweb-property --field account
    uv run python tools/query_oregon_yamhill_property.py detail 41270 \
        --source us-or-yamhill-county-ascendweb-property --tax-year 2025
    uv run python tools/query_oregon_yamhill_property.py search LUTZE \
        --source us-or-yamhill-county-at-taxlots --field owner --geometry
    uv run python tools/query_oregon_yamhill_property.py probe --all
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

try:
    from tools import oregon_ascendweb as ascend_shared
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
    import oregon_ascendweb as ascend_shared
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
COUNTY_GEOID = "41071"
COUNTY_NAME = "Yamhill County, Oregon"
PUBLISHER = "Yamhill County Assessment and Taxation / Yamhill County GIS"

ASCEND_SOURCE_ID = "us-or-yamhill-county-ascendweb-property"
TAXLOT_SOURCE_ID = "us-or-yamhill-county-at-taxlots"
RETIRED_SOURCE_ID = "us-or-yamhill-county-retired-taxlots"
PERMIT_SOURCE_ID = "us-or-yamhill-county-assessment-permits"
SOURCE_IDS = (
    ASCEND_SOURCE_ID,
    TAXLOT_SOURCE_ID,
    RETIRED_SOURCE_ID,
    PERMIT_SOURCE_ID,
)

ASCEND_ROOT_URL = "https://ascendweb.co.yamhill.or.us/AcsendWeb/"
ASCEND_HOME_URL = f"{ASCEND_ROOT_URL}default.aspx"
ASCEND_DETAIL_URL = f"{ASCEND_ROOT_URL}ParcelInfo.aspx"
ASCEND_VERSION_OBSERVED = "4.0.3.0"

ARCGIS_ORG_ID = "toubSXwoan3LMhOW"
ARCGIS_ORG_SEARCH_URL = "https://www.arcgis.com/sharing/rest/search"
TAXLOT_LAYER_URL = (
    "https://services6.arcgis.com/toubSXwoan3LMhOW/arcgis/rest/services/"
    "AT_Taxlots/FeatureServer/1"
)
RETIRED_LAYER_URL = (
    "https://services6.arcgis.com/toubSXwoan3LMhOW/arcgis/rest/services/"
    "ConnectExplorer_Taxlots/FeatureServer/3"
)
PERMIT_YEAR = 2026
PERMIT_LAYER_URL = (
    "https://services6.arcgis.com/toubSXwoan3LMhOW/arcgis/rest/services/"
    f"{PERMIT_YEAR}_Permits/FeatureServer/1"
)

COUNTY_ASSESSOR_URL = "https://www.yamhillcounty.gov/assessor"
COUNTY_ACCOUNT_INFO_URL = "https://www.yamhillcounty.gov/368/Account-Payment-Info"
COUNTY_FEE_SCHEDULE_URL = "https://www.yamhillcounty.gov/370/Fee-Schedule"
COUNTY_INFORMATION_REQUEST_URL = (
    "https://www.yamhillcounty.gov/DocumentCenter/View/17200/"
    "Request-for-Public-Information-PDF"
)
HELION_SOURCE_ID = "us-or-yamhill-helion-recorder"

OUTPUT_SCHEMA_VERSION = "oregon-yamhill-property/1.0"
PROBE_SCHEMA_VERSION = "oregon-yamhill-property-probe/1.0"
ASCEND_CURSOR_PREFIX = "oregon-yamhill-ascend:v1:"
ARCGIS_CURSOR_PREFIX = "oregon-yamhill-arcgis:v1:"
CURSOR_VERSION = 1
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_PAGE_SIZE = 1_000
DEFAULT_USER_AGENT = "Ithildin-Public-Records/1.0"
ASCEND_OBSERVED_BROAD_SEARCH_BYTES = 251_098
ASCEND_MAX_HTML_BYTES = 16 * 1024 * 1024

ASCEND_REQUIRED_FORM_FIELDS = (
    "mParcelID2",
    "mAlternateParcelID",
    "mStreetAddress",
    "mCity",
    "mStateProvince",
    "mPostalCode",
    "mSubmit",
)
ASCEND_RESULT_HEADERS = ("Parcel Number", "Location Address")
REPRESENTATION_GROUP = "yamhill_county_assessment_gis"

YAMHILL_ASCEND_MANIFEST = ascend_shared.AscendTenantManifest(
    source_id=ASCEND_SOURCE_ID,
    jurisdiction=COUNTY_NAME,
    county_geoid=COUNTY_GEOID,
    root_url=ASCEND_ROOT_URL,
    home_path="default.aspx",
    detail_path="ParcelInfo.aspx",
    observed_versions=(ASCEND_VERSION_OBSERVED,),
    form_aliases={
        "account": "mParcelID2",
        "alternate": "mAlternateParcelID",
        "address": "mStreetAddress",
        "city": "mCity",
        "state": "mStateProvince",
        "postal_code": "mPostalCode",
        "submit": "mSubmit",
    },
    submit_value="Account Info",
    form_action_suffixes=("default.aspx",),
    result_table_id="mGrid",
    result_headers=ASCEND_RESULT_HEADERS,
    result_columns=("account_number", "situs_address"),
    result_count_selectors=("#Table2",),
    result_count_pattern=r"([0-9,]+)\s+records?\s+returned",
    detail_link_parameter="parcel_number",
    detail_table_ids={
        "general_information": "mGeneralInformation",
        "tax_rate": "mTaxRate",
        "property_characteristics": "mPropertyCharacteristics",
        "related_properties": "mRelatedProperties",
        "parties": "mParties",
        "property_values": "mPropertyValues",
        "active_exemptions": "mActiveExemptions",
        "receipts": "mReceipts",
        "sales_history": "mSalesHistory",
        "property_details": "mPropertyDetails",
        "installments": "mGrid",
    },
    identity_mode="table",
    identity_account_label="Account Number",
    identity_table_id="ParcelSitusTable",
    installment_link_id="mInstallments",
    installment_event_target="mInstallments",
    installment_year_field="mDifferentYear",
    maximum_html_bytes=ASCEND_MAX_HTML_BYTES,
)


@dataclass(frozen=True)
class SearchColumn:
    name: str
    contains: bool = False
    numeric: bool = False


@dataclass(frozen=True)
class ArcGISSource:
    source_id: str
    name: str
    layer_url: str
    layer_id: int
    service_item_id: str
    expected_layer_name: str
    object_id_field: str
    record_kind: str
    source_role: str
    required_fields: tuple[str, ...]
    search_fields: Mapping[str, tuple[SearchColumn, ...]]
    source_crs: str
    warnings: tuple[str, ...]
    publication_year: int | None = None
    representation_role: str | None = None

    def source_metadata(self) -> SourceMetadata:
        metadata: dict[str, Any] = {
            "publisher": PUBLISHER,
            "county_geoid": COUNTY_GEOID,
            "record_kind": self.record_kind,
            "layer_id": self.layer_id,
            "layer_name": self.expected_layer_name,
            "source_crs": self.source_crs,
            "output_geometry_crs": "EPSG:4326",
        }
        if self.representation_role:
            metadata.update(
                {
                    "representation_group": REPRESENTATION_GROUP,
                    "representation_role": self.representation_role,
                    "overlap_interpretation": (
                        "same_county_system_representation_not_independent_"
                        "corroboration"
                    ),
                }
            )
        if self.publication_year is not None:
            metadata["publication_year"] = self.publication_year
            metadata["annual_discovery"] = {
                "organization_id": ARCGIS_ORG_ID,
                "search_url": ARCGIS_ORG_SEARCH_URL,
                "title_pattern": "<year> Permits",
                "rollover_behavior": (
                    "probe_returns_source_changed_when_selected_year_or_item_"
                    "differs"
                ),
            }
        return SourceMetadata(
            source_id=self.source_id,
            name=self.name,
            source_role=self.source_role,
            base_url=self.layer_url,
            dataset_id=self.service_item_id,
            metadata=metadata,
        )


COMMON_TAXLOT_FIELDS = (
    "maptaxlot",
    "acctnbr",
    "account_num",
    "situs1",
    "situscity",
    "situszip",
    "owner1",
    "owner2",
    "owner3",
    "mailadd1",
    "mailadd2",
    "mailcity",
    "mailstate",
    "mailzip",
    "account_acres",
    "parcel_acres",
    "sqft",
    "instyr",
    "instnbr",
    "deedtype",
    "saledate",
    "saleprice",
    "yearbuilt",
    "bedrms",
    "bathrms",
    "halfbaths",
    "maplink",
    "propsumlink",
    "retired_by",
    "parent_taxlot",
    "globalid",
)
TAXLOT_SEARCH_FIELDS = {
    "account": (
        SearchColumn("acctnbr"),
        SearchColumn("account_num", numeric=True),
    ),
    "map_taxlot": (SearchColumn("maptaxlot"),),
    "owner": (
        SearchColumn("owner1", contains=True),
        SearchColumn("owner2", contains=True),
        SearchColumn("owner3", contains=True),
    ),
    "address": (
        SearchColumn("situs1", contains=True),
        SearchColumn("situscity", contains=True),
        SearchColumn("mailadd1", contains=True),
        SearchColumn("mailadd2", contains=True),
        SearchColumn("mailcity", contains=True),
    ),
    "recording": (
        SearchColumn("instyr"),
        SearchColumn("instnbr"),
    ),
    "global_id": (SearchColumn("globalid"),),
    "parent_taxlot": (SearchColumn("parent_taxlot"),),
    "retired_by": (SearchColumn("retired_by"),),
}

TAXLOTS = ArcGISSource(
    source_id=TAXLOT_SOURCE_ID,
    name="Yamhill County A&T Taxlots",
    layer_url=TAXLOT_LAYER_URL,
    layer_id=1,
    service_item_id="2d7b3aa4cc654b89b92821a9c10d03aa",
    expected_layer_name="A&T Taxlots",
    object_id_field="objectid",
    record_kind="current_assessment_taxlot",
    source_role="official_county_current_assessment_taxlot_layer",
    required_fields=("objectid", *COMMON_TAXLOT_FIELDS),
    search_fields=TAXLOT_SEARCH_FIELDS,
    source_crs="EPSG:2913",
    warnings=(
        "This is the selected current county taxlot representation.",
        "AscendWeb detail and Helion recorder rows add account history and "
        "instrument detail through explicit account, taxlot, and recording joins.",
    ),
    representation_role="canonical_current_taxlots",
)

RETIRED_TAXLOTS = ArcGISSource(
    source_id=RETIRED_SOURCE_ID,
    name="Yamhill County Retired Taxlots",
    layer_url=RETIRED_LAYER_URL,
    layer_id=3,
    service_item_id="2f45dbf4b808465f98c16d22d8d666f4",
    expected_layer_name="TAXLOTS - RETIRED",
    object_id_field="objectid",
    record_kind="retired_assessment_taxlot",
    source_role="official_county_retired_taxlot_lineage_layer",
    required_fields=("objectid", *COMMON_TAXLOT_FIELDS),
    search_fields=TAXLOT_SEARCH_FIELDS,
    source_crs="EPSG:6885 (latest WKID; service extent declares WKID 102378)",
    warnings=(
        "Parent-taxlot and retired-by identifiers are preserved as published "
        "lineage observations.",
        "Shared assessment attributes overlap the current layer as a county "
        "system representation, not as independent corroboration.",
    ),
    representation_role="retired_taxlot_lineage",
)

PERMIT_SEARCH_FIELDS = {
    "account": (SearchColumn("account"),),
    "map_taxlot": (SearchColumn("taxlot"),),
    "native_id": (SearchColumn("Permit"),),
    "owner": (
        SearchColumn("owner", contains=True),
        SearchColumn("owner_1", contains=True),
        SearchColumn("owner_12", contains=True),
    ),
    "address": (
        SearchColumn("situs_address", contains=True),
        SearchColumn("situs_city", contains=True),
        SearchColumn("mailing_address_1", contains=True),
        SearchColumn("mailing_address_2", contains=True),
        SearchColumn("mailing_city", contains=True),
    ),
    "description": (SearchColumn("Description", contains=True),),
    "global_id": (SearchColumn("globalid"),),
}
PERMIT_FIELDS = (
    "OBJECTID",
    "taxlot",
    "account",
    "situs_address",
    "situs_city",
    "situs_zip",
    "owner",
    "owner_1",
    "owner_12",
    "mailing_address_1",
    "mailing_address_2",
    "mailing_city",
    "mailing_state",
    "mailing_zip",
    "Permit",
    "IssueDate",
    "Description",
    "Situs_Address_1",
    "StreetDirection",
    "StreetName",
    "Space_",
    "City",
    "PCA_1",
    "APPRAISER",
    "globalid",
)
PERMITS = ArcGISSource(
    source_id=PERMIT_SOURCE_ID,
    name=f"Yamhill County {PERMIT_YEAR} Assessment Permits",
    layer_url=PERMIT_LAYER_URL,
    layer_id=1,
    service_item_id="dc4665d460cf46dfb1c2b63ae93eebc6",
    expected_layer_name="All Permits",
    object_id_field="OBJECTID",
    record_kind="annual_assessment_permit_observation",
    source_role="official_county_annual_assessment_permit_layer",
    required_fields=PERMIT_FIELDS,
    search_fields=PERMIT_SEARCH_FIELDS,
    source_crs="EPSG:2913",
    warnings=(
        "The publication year and ArcGIS item identity are retained with each "
        "permit observation.",
        "The organization search reports the newest annual permit item so a "
        "different year or item returns a source-changed probe.",
    ),
    publication_year=PERMIT_YEAR,
)

ARCGIS_SOURCES = {
    config.source_id: config
    for config in (TAXLOTS, RETIRED_TAXLOTS, PERMITS)
}

ASCEND_SOURCE_METADATA = SourceMetadata(
    source_id=ASCEND_SOURCE_ID,
    name="Yamhill County Aumentum AscendWeb Property Search",
    source_role="official_county_property_assessment_tax_and_sale_detail",
    base_url=ASCEND_HOME_URL,
    dataset_id="yamhill-ascendweb-4",
    metadata={
        "publisher": "Yamhill County Assessment and Taxation",
        "county_geoid": COUNTY_GEOID,
        "platform_family": "aumentum_ascendweb",
        "native_path": "/AcsendWeb/",
        "session_contract": "aspnet_cookieless_session_and_viewstate",
        "search_result_contract": "complete_server_rendered_table",
        "detail_sections": [
            "identity",
            "classification",
            "parties",
            "five_year_values",
            "tax_rate_and_balance",
            "receipts",
            "sales_and_recording_references",
            "property_characteristics",
        ],
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality="Yamhill County",
    metadata={"state_fips": STATE_FIPS},
)

SOURCE_METADATA = {
    ASCEND_SOURCE_ID: ASCEND_SOURCE_METADATA,
    **{
        source_id: config.source_metadata()
        for source_id, config in ARCGIS_SOURCES.items()
    },
}

CATALOG_METADATA: Mapping[str, Mapping[str, Any]] = {
    ASCEND_SOURCE_ID: {
        "source_id": ASCEND_SOURCE_ID,
        "category": "property",
        "record_types": [
            "property_account",
            "assessment_value_history",
            "tax_receipt",
            "property_sale",
        ],
        "jurisdiction": COUNTY_GEOID,
        "access_method": "web_form",
        "auth": "none",
        "official": True,
        "url": ASCEND_HOME_URL,
        "query_tool": "tools/query_oregon_yamhill_property.py",
        "pagination": "query_schema_snapshot_bound_local_window",
    },
    TAXLOT_SOURCE_ID: {
        "source_id": TAXLOT_SOURCE_ID,
        "category": "property",
        "record_types": ["current_assessment_taxlot"],
        "jurisdiction": COUNTY_GEOID,
        "access_method": "rest_api",
        "auth": "none",
        "official": True,
        "url": TAXLOT_LAYER_URL,
        "query_tool": "tools/query_oregon_yamhill_property.py",
        "pagination": "query_schema_boundary_bound_object_id_keyset",
        "supports_geometry": True,
    },
    RETIRED_SOURCE_ID: {
        "source_id": RETIRED_SOURCE_ID,
        "category": "property",
        "record_types": ["retired_taxlot_lineage"],
        "jurisdiction": COUNTY_GEOID,
        "access_method": "rest_api",
        "auth": "none",
        "official": True,
        "url": RETIRED_LAYER_URL,
        "query_tool": "tools/query_oregon_yamhill_property.py",
        "pagination": "query_schema_boundary_bound_object_id_keyset",
        "supports_geometry": True,
    },
    PERMIT_SOURCE_ID: {
        "source_id": PERMIT_SOURCE_ID,
        "category": "property",
        "record_types": ["annual_assessment_permit"],
        "jurisdiction": COUNTY_GEOID,
        "access_method": "rest_api",
        "auth": "none",
        "official": True,
        "url": PERMIT_LAYER_URL,
        "query_tool": "tools/query_oregon_yamhill_property.py",
        "pagination": "query_schema_boundary_bound_object_id_keyset",
        "supports_geometry": True,
    },
}

COMPLEMENTARY_SOURCES: Mapping[str, tuple[Mapping[str, Any], ...]] = {
    ASCEND_SOURCE_ID: (
        {
            "source_id": TAXLOT_SOURCE_ID,
            "relationship": "current_parcel_geometry_and_owner_representation",
            "join_keys": ["account_number", "map_taxlot"],
        },
        {
            "source_id": RETIRED_SOURCE_ID,
            "relationship": "parcel_lineage_representation",
            "join_keys": ["account_number", "map_taxlot", "parent_taxlot"],
        },
        {
            "source_id": HELION_SOURCE_ID,
            "relationship": "recorded_instrument_detail_complement",
            "join_keys": ["recording_number", "party_name", "sale_date"],
        },
        {
            "kind": "assessment_public_information_request",
            "url": COUNTY_INFORMATION_REQUEST_URL,
            "relationship": "additional_account_or_historical_data_request",
            "published_formats": ["Excel", "Access", "text delimited"],
        },
        {
            "kind": "assessment_data_extracts",
            "url": COUNTY_FEE_SCHEDULE_URL,
            "relationship": "sales_real_estate_taxlot_and_tax_code_extracts",
        },
    ),
    TAXLOT_SOURCE_ID: (
        {
            "source_id": ASCEND_SOURCE_ID,
            "relationship": "rich_account_tax_value_and_sale_detail",
            "join_keys": ["account_number", "map_taxlot"],
        },
        {
            "source_id": RETIRED_SOURCE_ID,
            "relationship": "retired_taxlot_lineage_representation",
            "join_keys": ["map_taxlot", "parent_taxlot", "global_id"],
        },
        {
            "source_id": PERMIT_SOURCE_ID,
            "relationship": "annual_assessment_event_complement",
            "join_keys": ["account_number", "map_taxlot"],
        },
        {
            "source_id": HELION_SOURCE_ID,
            "relationship": "recorded_instrument_detail_complement",
            "join_keys": ["recording_number", "owner_name"],
        },
    ),
    RETIRED_SOURCE_ID: (
        {
            "source_id": TAXLOT_SOURCE_ID,
            "relationship": "current_taxlot_representation",
            "join_keys": ["map_taxlot", "parent_taxlot", "global_id"],
        },
        {
            "source_id": ASCEND_SOURCE_ID,
            "relationship": "account_history_and_sale_detail",
            "join_keys": ["account_number", "map_taxlot"],
        },
    ),
    PERMIT_SOURCE_ID: (
        {
            "source_id": TAXLOT_SOURCE_ID,
            "relationship": "current_parcel_and_geometry_context",
            "join_keys": ["account_number", "map_taxlot"],
        },
        {
            "source_id": ASCEND_SOURCE_ID,
            "relationship": "assessment_account_and_value_context",
            "join_keys": ["account_number", "map_taxlot"],
        },
    ),
}

ASCEND_WARNINGS = (
    "Exact account searches can open the native detail page directly; broader "
    "searches return one complete server-rendered result table.",
    "Continuation windows are tied to the form criteria, parsed schema, and "
    "complete result snapshot.",
)


class SourceSelectionError(ValueError):
    """A source, search field, detail selector, or cursor mismatch."""

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
class HTMLPage:
    html: str
    source_url: str
    request_url: str
    body_bytes: int | None = None


@dataclass(frozen=True)
class AscendHomeContract:
    form_fields: tuple[str, ...]
    version: str
    schema_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class AscendSearchPage:
    records: tuple[Mapping[str, Any], ...]
    total_count: int
    schema_fingerprint: str
    snapshot_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class ArcGISCursorState:
    source_id: str
    criteria_fingerprint: str
    schema_fingerprint: str
    boundary_object_id: int
    last_object_id: int
    snapshot_count: int


@dataclass(frozen=True)
class ArcGISBatch:
    features: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    total_count: int
    bounded_count: int
    boundary_object_id: int | None
    last_object_id: int | None
    schema_fingerprint: str
    pages_fetched: int
    count_changed_since_cursor: bool


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "get_text"):
        value = value.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()
    if not text or text == "-":
        return None
    return text


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (_clean(value) or "").casefold()).strip("_")


def _number(value: Any) -> int | float | None:
    text = _clean(value)
    if text is None:
        return None
    normalized = re.sub(r"[$,%\s]", "", text).replace(",", "")
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = f"-{normalized[1:-1]}"
    if not normalized or normalized == "-":
        return None
    try:
        number = float(normalized)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _date_iso(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    text = re.sub(r"\s+00:00:00$", "", text)
    for pattern in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _epoch_observation(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    observation: dict[str, Any] = {"raw": value}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            parsed = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return observation
        observation["utc_datetime"] = (
            parsed.isoformat(timespec="seconds").replace("+00:00", "Z")
        )
        observation["utc_date"] = parsed.date().isoformat()
    return observation


def _canonical_ascend_url(value: str) -> str:
    return ascend_shared.canonical_url(YAMHILL_ASCEND_MANIFEST, value)


def _ascend_url(path_or_url: str) -> str:
    return _canonical_ascend_url(urljoin(ASCEND_ROOT_URL, path_or_url))


def _ascend_request_url(path_or_url: str) -> str:
    """Validate a request URL while retaining its live cookieless session."""
    return ascend_shared.request_url(YAMHILL_ASCEND_MANIFEST, path_or_url)


def _table_rows(table: Tag | None) -> list[list[str]]:
    if table is None:
        return []
    rows: list[list[str]] = []
    for row in table.find_all("tr"):
        cells = [
            _clean(cell) or ""
            for cell in row.find_all(["th", "td"], recursive=False)
        ]
        if cells:
            rows.append(cells)
    return rows


def _key_value_table(soup: BeautifulSoup, table_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for row in _table_rows(soup.select_one(f"#{table_id}")):
        if len(row) < 2:
            continue
        key = _slug(row[0])
        if not key:
            continue
        result[key] = _clean(row[1])
    return result


def _row_table(soup: BeautifulSoup, table_id: str) -> list[dict[str, Any]]:
    rows = _table_rows(soup.select_one(f"#{table_id}"))
    if len(rows) < 2:
        return []
    headers = [_slug(value) or f"column_{index}" for index, value in enumerate(rows[0])]
    return [
        {
            header: (_clean(row[index]) if index < len(row) else None)
            for index, header in enumerate(headers)
        }
        for row in rows[1:]
        if any(_clean(value) for value in row)
    ]


def _row_table_or_message(
    soup: BeautifulSoup,
    table_id: str,
) -> list[dict[str, Any]]:
    rows = _table_rows(soup.select_one(f"#{table_id}"))
    if len(rows) == 1 and len(rows[0]) == 1:
        message = _clean(rows[0][0])
        return [{"message": message}] if message else []
    return _row_table(soup, table_id)


def parse_ascend_home(
    html: str,
    *,
    source_url: str = ASCEND_HOME_URL,
) -> AscendHomeContract:
    """Validate the anonymous ASP.NET form through the shared family parser."""

    shared = ascend_shared.parse_home(
        YAMHILL_ASCEND_MANIFEST,
        html,
        source_url=source_url,
    )
    return AscendHomeContract(
        form_fields=shared.form_fields,
        version=shared.version,
        schema_fingerprint=shared.schema_fingerprint,
        source_url=shared.source_url,
    )


def parse_ascend_search(
    html: str,
    *,
    source_url: str,
) -> AscendSearchPage:
    """Parse the complete result table through the shared family parser."""

    shared = ascend_shared.parse_search(
        YAMHILL_ASCEND_MANIFEST,
        html,
        source_url=source_url,
    )
    records: list[dict[str, Any]] = []
    for raw in shared.records:
        account_number = str(raw["account_number"])
        address = _clean(raw.get("situs_address"))
        canonical_ref = canonical_property_ref(
            ASCEND_SOURCE_ID,
            COUNTY_GEOID,
            "property_account_search_result",
            account_number,
        )
        records.append(
            {
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "source_id": ASCEND_SOURCE_ID,
                "source_url": source_url,
                "record_kind": "property_account_search_result",
                "account_number": account_number,
                "situs_address": address,
                "detail_url": raw["detail_url"],
                "native_position": raw["native_position"],
                "join_candidates": {
                    TAXLOT_SOURCE_ID: {
                        "account_number": account_number,
                        "relationship": "account_to_current_taxlot",
                    }
                },
            }
        )
    return AscendSearchPage(
        records=tuple(records),
        total_count=shared.total_count,
        schema_fingerprint=shared.schema_fingerprint,
        snapshot_fingerprint=shared.snapshot_fingerprint,
        source_url=shared.source_url,
    )


def _parse_value_history(soup: BeautifulSoup) -> list[dict[str, Any]]:
    rows = _table_rows(soup.select_one("#mPropertyValues"))
    if len(rows) < 2 or not rows[0] or rows[0][0] != "Value Type":
        return []
    years: list[str] = []
    for value in rows[0][1:]:
        match = re.search(r"(20[0-9]{2})", value)
        years.append(match.group(1) if match else value)
    history: list[dict[str, Any]] = []
    for row in rows[1:]:
        if not row:
            continue
        raw_type = _clean(row[0])
        if raw_type is None:
            continue
        code_match = re.match(r"(.+?)\s+([A-Z][A-Z0-9]{2,7})$", raw_type)
        history.append(
            {
                "value_type": (
                    _clean(code_match.group(1)) if code_match else raw_type
                ),
                "value_code": code_match.group(2) if code_match else None,
                "raw_value_type": raw_type,
                "values_by_tax_year": {
                    year: {
                        "amount": _number(row[index + 1])
                        if index + 1 < len(row)
                        else None,
                        "raw": _clean(row[index + 1])
                        if index + 1 < len(row)
                        else None,
                    }
                    for index, year in enumerate(years)
                },
            }
        )
    return history


def _recording_number(year: Any, number: Any) -> str | None:
    year_text = _clean(year)
    number_text = _clean(number)
    if not year_text or not number_text:
        return None
    if not year_text.isdigit() or not number_text.isdigit():
        return None
    return f"{int(year_text):04d}-{int(number_text):05d}"


def parse_ascend_detail(
    html: str,
    *,
    source_url: str,
    installment_html: str | None = None,
    installment_source_url: str | None = None,
) -> dict[str, Any]:
    """Normalize the rich account detail while retaining source-native rows."""

    soup = BeautifulSoup(html, "lxml")
    situs_rows = _table_rows(soup.select_one("#ParcelSitusTable"))
    if not situs_rows or len(situs_rows[0]) < 4:
        raise SourceSchemaError(
            "Yamhill AscendWeb account identity table changed",
            url=source_url,
        )
    identity = situs_rows[0]
    if _slug(identity[0]) not in {"account_number", "parcel_number"}:
        raise SourceSchemaError(
            "Yamhill AscendWeb account identity label changed",
            url=source_url,
            details={"label": identity[0]},
        )
    account_number = _clean(identity[1])
    situs_address = _clean(identity[3])
    if account_number is None:
        raise SourceSchemaError(
            "Yamhill AscendWeb detail lacks an account number",
            url=source_url,
        )

    parties = []
    for row in _table_rows(soup.select_one("#mParties"))[1:]:
        if len(row) < 2 or not _clean(row[1]):
            continue
        parties.append(
            {
                "role": _slug(row[0]),
                "role_raw": _clean(row[0]),
                "name": _clean(row[1]),
                "assertion_type": "published_assessment_account_party",
            }
        )

    receipts: list[dict[str, Any]] = []
    for row in _row_table(soup, "mReceipts"):
        receipt_number = _clean(row.get("receipt_no"))
        receipts.append(
            {
                **row,
                "date_iso": _date_iso(row.get("date")),
                "receipt_number": receipt_number,
                "amount_applied_value": _number(row.get("amount_applied")),
                "amount_due_value": _number(row.get("amount_due")),
                "tendered_value": _number(row.get("tendered")),
                "change_value": _number(row.get("change")),
                "detail_url": (
                    f"{ASCEND_ROOT_URL}ReceiptDetail.aspx?receiptnumber="
                    f"{quote(receipt_number, safe='')}"
                    if receipt_number
                    else None
                ),
            }
        )

    sales: list[dict[str, Any]] = []
    recording_numbers: list[str] = []
    for row in _row_table(soup, "mSalesHistory"):
        recorder_number = _clean(row.get("recording_number"))
        if recorder_number:
            recording_numbers.append(recorder_number)
        sales.append(
            {
                **row,
                "sale_date_iso": _date_iso(row.get("sale_date")),
                "entry_date_iso": _date_iso(row.get("entry_date")),
                "sale_amount_value": _number(row.get("sale_amount")),
                "recording_number": recorder_number,
                "recorder_join": (
                    {
                        "source_id": HELION_SOURCE_ID,
                        "recording_number": recorder_number,
                        "relationship": "recorded_instrument_detail",
                    }
                    if recorder_number
                    else None
                ),
            }
        )

    general = _key_value_table(soup, "mGeneralInformation")
    characteristics = _key_value_table(soup, "mPropertyCharacteristics")
    tax_rate = _key_value_table(soup, "mTaxRate")
    property_details: dict[str, Any] = {}
    property_rows = _table_rows(soup.select_one("#mPropertyDetails"))
    if len(property_rows) >= 2:
        property_details = {
            _slug(header): _clean(property_rows[1][index])
            if index < len(property_rows[1])
            else None
            for index, header in enumerate(property_rows[0])
        }

    installment: dict[str, Any] | None = None
    if installment_html is not None:
        installment_soup = BeautifulSoup(installment_html, "lxml")
        installment_rows = _row_table(installment_soup, "mGrid")
        normalized_rows = []
        for row in installment_rows:
            normalized_rows.append(
                {
                    **row,
                    "charged_value": _number(row.get("charged")),
                    "minimum_value": _number(row.get("minimum")),
                    "balance_due_value": _number(row.get("balance_due")),
                    "due_date_iso": _date_iso(row.get("due_date")),
                }
            )
        installment = {
            "source_url": installment_source_url,
            "rows": normalized_rows,
        }

    alternate = _clean(general.get("alternate_property"))
    canonical_ref = canonical_property_ref(
        ASCEND_SOURCE_ID,
        COUNTY_GEOID,
        "property_account",
        account_number,
    )
    detail_schema = sha256_fingerprint(
        {
            "identity_headers": identity[::2],
            "table_ids": sorted(
                element.get("id")
                for element in soup.select("table[id]")
                if element.get("id")
            ),
        }
    )
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": ASCEND_SOURCE_ID,
        "source_url": source_url,
        "record_kind": "property_account",
        "account_number": account_number,
        "alternate_map_taxlot": alternate,
        "situs_address": situs_address,
        "general_information": general,
        "tax_rate": {
            **tax_rate,
            "total_rate_value": _number(tax_rate.get("total_rate")),
        },
        "tax_balance_observation": _clean(soup.select_one("#mNoChargesOwing")),
        "property_characteristics": {
            **characteristics,
            "account_acres_value": _number(characteristics.get("account_acres")),
        },
        "parties": parties,
        "related_properties": _row_table_or_message(
            soup,
            "mRelatedProperties",
        ),
        "value_history": _parse_value_history(soup),
        "active_exemptions": _row_table_or_message(
            soup,
            "mActiveExemptions",
        ),
        "receipts": receipts,
        "sales": sales,
        "property_details": {
            key: {
                "raw": value,
                "value": _number(value),
            }
            for key, value in property_details.items()
        },
        "installment_detail": installment,
        "source_response_schema_fingerprint": detail_schema,
        "join_candidates": {
            TAXLOT_SOURCE_ID: {
                "account_number": account_number,
                "map_taxlot": alternate,
                "relationship": "current_taxlot_geometry_and_owner_representation",
            },
            RETIRED_SOURCE_ID: {
                "account_number": account_number,
                "map_taxlot": alternate,
                "relationship": "retired_taxlot_lineage_representation",
            },
            HELION_SOURCE_ID: {
                "recording_numbers": recording_numbers,
                "party_names": [
                    party["name"] for party in parties if party.get("name")
                ],
                "relationship": "recorded_instrument_detail",
            },
        },
    }


class AscendWebClient(ascend_shared.AscendWebClient):
    """Yamhill binding for the shared, manifest-driven AscendWeb client."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(
            YAMHILL_ASCEND_MANIFEST,
            session=session,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_attempts=retry_attempts,
            sleeper=sleeper,
        )

    @staticmethod
    def _read_html(
        response: Any,
        *,
        maximum_bytes: int = ASCEND_MAX_HTML_BYTES,
    ) -> tuple[str, int]:
        """Retain the prior testable reader API while using shared mechanics."""

        manifest = (
            YAMHILL_ASCEND_MANIFEST
            if maximum_bytes == ASCEND_MAX_HTML_BYTES
            else ascend_shared.AscendTenantManifest(
                **{
                    **YAMHILL_ASCEND_MANIFEST.__dict__,
                    "maximum_html_bytes": maximum_bytes,
                }
            )
        )
        client = object.__new__(ascend_shared.AscendWebClient)
        client.manifest = manifest
        return ascend_shared.AscendWebClient._read_html(client, response)

    @classmethod
    def _page(cls, response: Any) -> HTMLPage:
        request_target = str(response.url)
        canonical_target = _canonical_ascend_url(request_target)
        html, body_bytes = cls._read_html(response)
        return HTMLPage(
            html=html,
            source_url=canonical_target,
            request_url=request_target,
            body_bytes=body_bytes,
        )


class YamhillArcGISClient(ArcGISRESTClient):
    """Metadata, count, and ordered GeoJSON page facade."""

    def __init__(
        self,
        config: ArcGISSource,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
    ) -> None:
        super().__init__(
            config.layer_url,
            page_size=page_size,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=RetryPolicy(max_attempts=retry_attempts),
            user_agent=DEFAULT_USER_AGENT,
        )
        self.config = config

    def fetch_metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(self.layer_url, params={"f": "json"})
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "Yamhill ArcGIS returned invalid layer metadata",
                url=self.layer_url,
                details={"response": payload},
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
                "Yamhill ArcGIS returned an invalid count response",
                url=self.query_url,
                details={"response": payload},
            )
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "Yamhill ArcGIS count response is not a non-negative integer",
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
        descending: bool = False,
    ) -> tuple[Mapping[str, Any], ...]:
        payload = self._request_json(
            self.query_url,
            params={
                "where": where,
                "outFields": "*",
                "returnGeometry": str(return_geometry).lower(),
                "outSR": 4326,
                "orderByFields": (
                    f"{self.config.object_id_field} "
                    f"{'DESC' if descending else 'ASC'}"
                ),
                "resultRecordCount": record_count,
                "f": "geojson",
            },
        )
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "Yamhill ArcGIS returned an invalid feature response",
                url=self.query_url,
                details={"response": payload},
            )
        features = payload.get("features")
        if not isinstance(features, list) or any(
            not isinstance(feature, Mapping) for feature in features
        ):
            raise SourceSchemaError(
                "Yamhill ArcGIS response lacks a valid GeoJSON features array",
                url=self.query_url,
            )
        return tuple(features)


class PermitDiscoveryClient(ArcGISRESTClient):
    """Discover annual permit feature services within the county ArcGIS org."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
    ) -> None:
        super().__init__(
            ARCGIS_ORG_SEARCH_URL,
            page_size=100,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=RetryPolicy(max_attempts=retry_attempts),
            user_agent=DEFAULT_USER_AGENT,
        )

    def fetch_items(self) -> tuple[Mapping[str, Any], ...]:
        payload = self._request_json(
            self.layer_url,
            params={
                "q": (
                    f"orgid:{ARCGIS_ORG_ID} AND title:Permits "
                    'AND type:"Feature Service"'
                ),
                "f": "json",
                "num": 100,
                "sortField": "modified",
                "sortOrder": "desc",
            },
        )
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "ArcGIS organization search returned an invalid response",
                url=self.layer_url,
                details={"response": payload},
            )
        results = payload.get("results")
        if not isinstance(results, list) or any(
            not isinstance(item, Mapping) for item in results
        ):
            raise SourceSchemaError(
                "ArcGIS organization search lacks a valid results array",
                url=self.layer_url,
            )
        return tuple(results)


def parse_permit_discovery(
    items: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Select the newest official annual permit feature-service item."""

    candidates: list[dict[str, Any]] = []
    for item in items:
        title = _clean(item.get("title"))
        item_type = _clean(item.get("type"))
        item_id = _clean(item.get("id"))
        url = _clean(item.get("url"))
        match = re.fullmatch(r"(20[0-9]{2})\s+Permits", title or "", re.I)
        if not match or item_type != "Feature Service" or not item_id or not url:
            continue
        parsed = urlparse(url)
        if (
            parsed.scheme.casefold() != "https"
            or parsed.hostname != "services6.arcgis.com"
            or not parsed.path.startswith(
                f"/{ARCGIS_ORG_ID}/arcgis/rest/services/"
            )
        ):
            continue
        candidates.append(
            {
                "year": int(match.group(1)),
                "item_id": item_id,
                "title": title,
                "url": url,
                "modified_epoch_ms": item.get("modified"),
            }
        )
    if not candidates:
        raise SourceSchemaError(
            "ArcGIS organization search found no annual Yamhill permit item",
            url=ARCGIS_ORG_SEARCH_URL,
        )
    candidates.sort(
        key=lambda item: (
            int(item["year"]),
            int(item["modified_epoch_ms"] or 0),
        ),
        reverse=True,
    )
    selected = candidates[0]
    return {
        "organization_id": ARCGIS_ORG_ID,
        "selected": selected,
        "configured_year": PERMIT_YEAR,
        "configured_item_id": PERMITS.service_item_id,
        "rollover_observed": (
            selected["year"] != PERMIT_YEAR
            or selected["item_id"] != PERMITS.service_item_id
        ),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def _encode_cursor(prefix: str, payload: Mapping[str, Any]) -> str:
    body = dict(payload)
    envelope = {
        "payload": body,
        "digest": sha256_fingerprint(body),
    }
    token = (
        base64.urlsafe_b64encode(canonical_json(envelope).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{prefix}{token}"


def _decode_cursor(prefix: str, cursor: str) -> Mapping[str, Any]:
    if not cursor.startswith(prefix):
        raise SourceSelectionError(
            "invalid_cursor",
            "continuation cursor belongs to a different source adapter",
        )
    token = cursor[len(prefix) :]
    try:
        padding = "=" * (-len(token) % 4)
        envelope = json.loads(
            base64.urlsafe_b64decode(token + padding).decode("utf-8")
        )
        payload = envelope["payload"]
        digest = str(envelope["digest"])
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise SourceSelectionError(
            "invalid_cursor",
            "continuation cursor payload is malformed",
        ) from error
    if not isinstance(payload, Mapping) or digest != sha256_fingerprint(payload):
        raise SourceSelectionError(
            "invalid_cursor",
            "continuation cursor integrity check failed",
        )
    if payload.get("v") != CURSOR_VERSION:
        raise SourceSelectionError(
            "invalid_cursor",
            "continuation cursor version is not supported",
        )
    return payload


def _ascend_criteria(
    *,
    field: str,
    query: str,
    city: str,
    state: str,
    postal_code: str,
) -> tuple[str, dict[str, str]]:
    cleaned_query = _clean(query)
    if not cleaned_query:
        raise SourceSelectionError("blank_query", "search value must not be blank")
    selected = field
    if selected == "auto":
        if cleaned_query.isdigit():
            selected = "account"
        elif re.match(r"^[RMP][0-9]", cleaned_query, re.I):
            selected = "alternate"
        else:
            selected = "address"
    if selected not in {"account", "alternate", "address"}:
        raise SourceSelectionError(
            "unsupported_search_field",
            f"AscendWeb does not publish a {selected} search field",
        )
    parameters = {
        "account": cleaned_query if selected == "account" else "",
        "alternate": cleaned_query if selected == "alternate" else "",
        "address": cleaned_query if selected == "address" else "",
        "city": _clean(city) or "",
        "state": _clean(state) or "",
        "postal_code": _clean(postal_code) or "",
    }
    criteria = sha256_fingerprint(
        {
            "source_id": ASCEND_SOURCE_ID,
            "operation": "search",
            "field": selected,
            **parameters,
            "ordering": "native_complete_table_order",
        }
    )
    return criteria, parameters


def _sql_text(value: Any) -> str:
    text = _clean(value)
    if not text:
        raise SourceSelectionError("blank_query", "search value must not be blank")
    return text.replace("'", "''")


def _arcgis_source(source_id: str) -> ArcGISSource:
    try:
        return ARCGIS_SOURCES[source_id]
    except KeyError as error:
        raise SourceSelectionError(
            "unknown_source",
            f"unknown Yamhill ArcGIS component: {source_id}",
            details={"known_sources": sorted(ARCGIS_SOURCES)},
        ) from error


def _attributes(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("properties", "attributes"):
        attributes = feature.get(key)
        if isinstance(attributes, Mapping):
            return attributes
    raise SourceSchemaError(
        "Yamhill ArcGIS feature lacks properties",
        url="arcgis://feature",
        details={"feature_keys": sorted(str(key) for key in feature)},
    )


def _object_id(config: ArcGISSource, feature: Mapping[str, Any]) -> int:
    value = _attributes(feature).get(config.object_id_field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SourceSchemaError(
            "Yamhill ArcGIS feature lacks an integer object ID",
            url=config.layer_url,
            details={
                "object_id_field": config.object_id_field,
                "value": value,
            },
        )
    return value


def _metadata_contract(
    config: ArcGISSource,
    metadata: Mapping[str, Any],
) -> tuple[str, int]:
    expected = {
        "id": config.layer_id,
        "name": config.expected_layer_name,
        "serviceItemId": config.service_item_id,
        "objectIdField": config.object_id_field,
    }
    changed = {
        key: {"expected": value, "observed": metadata.get(key)}
        for key, value in expected.items()
        if metadata.get(key) != value
    }
    if changed:
        raise SourceSchemaError(
            "Yamhill ArcGIS layer identity changed",
            url=config.layer_url,
            details={"changed": changed},
        )
    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "Yamhill ArcGIS metadata lacks field declarations",
            url=config.layer_url,
        )
    names = {
        str(field.get("name"))
        for field in fields
        if field.get("name") is not None
    }
    missing = sorted(set(config.required_fields) - names)
    if missing:
        raise SourceSchemaError(
            "Yamhill ArcGIS layer is missing expected fields",
            url=config.layer_url,
            details={"missing_fields": missing},
        )
    advanced = metadata.get("advancedQueryCapabilities")
    if not isinstance(advanced, Mapping) or not all(
        advanced.get(capability)
        for capability in ("supportsOrderBy", "supportsPagination")
    ):
        raise SourceSchemaError(
            "Yamhill ArcGIS layer no longer declares ordered pagination",
            url=config.layer_url,
        )
    maximum = metadata.get("maxRecordCount")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        raise SourceSchemaError(
            "Yamhill ArcGIS metadata lacks a positive maxRecordCount",
            url=config.layer_url,
            details={"maxRecordCount": maximum},
        )
    return schema_fingerprint(arcgis_declared_schema(fields)), maximum


def _recording_where(value: str) -> str:
    text = _sql_text(value)
    match = re.fullmatch(r"(20[0-9]{2})[-/]0*([0-9]+)", text)
    if not match:
        raise SourceSelectionError(
            "invalid_recording_number",
            "recording lookup expects a year-number value such as 2026-03177",
        )
    year, number = match.groups()
    return (
        f"(instyr = '{year}' AND "
        f"(instnbr = '{number}' OR instnbr = '{int(number)}'))"
    )


def _column_clause(column: SearchColumn, value: str) -> str | None:
    if column.numeric:
        if not value.isdigit():
            return None
        return f"{column.name} = {int(value)}"
    if column.contains:
        return f"UPPER({column.name}) LIKE '%{value.upper()}%'"
    return f"UPPER({column.name}) = '{value.upper()}'"


def _arcgis_where(
    config: ArcGISSource,
    *,
    operation: str,
    selector: str,
    field: str,
) -> str:
    value = _sql_text(selector)
    if field == "object_id":
        if not value.isdigit():
            raise SourceSelectionError(
                "invalid_object_id",
                "ArcGIS object ID detail lookup expects an integer",
            )
        return f"{config.object_id_field} = {int(value)}"
    selected = field
    if selected == "auto" and operation == "detail":
        if value.isdigit():
            selected = "account"
        elif value.startswith("{") and value.endswith("}"):
            selected = "global_id"
        elif config is PERMITS:
            selected = "native_id"
        else:
            selected = "map_taxlot"
    if selected == "recording":
        if config is PERMITS:
            raise SourceSelectionError(
                "unsupported_search_field",
                "the annual permit layer does not publish recorder numbers",
            )
        return _recording_where(value)
    groups: tuple[str, ...]
    if selected == "auto":
        groups = tuple(
            key for key in config.search_fields if key != "recording"
        )
    elif selected in config.search_fields:
        groups = (selected,)
    else:
        raise SourceSelectionError(
            "unsupported_search_field",
            f"{config.source_id} does not publish a searchable {selected} field",
            details={"supported_fields": sorted(config.search_fields)},
        )
    clauses: list[str] = []
    for group in groups:
        for column in config.search_fields[group]:
            clause = _column_clause(column, value)
            if clause:
                clauses.append(clause)
    if selected == "auto" and re.fullmatch(r"20[0-9]{2}[-/]0*[0-9]+", value):
        if config is not PERMITS:
            clauses.append(_recording_where(value))
    if not clauses:
        raise SourceSelectionError(
            "unsupported_search_value",
            f"{config.source_id} cannot apply {selected} to this value",
        )
    return clauses[0] if len(clauses) == 1 else f"({' OR '.join(clauses)})"


def _arcgis_criteria(
    config: ArcGISSource,
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


def _bounded_where(
    config: ArcGISSource,
    base_where: str,
    *,
    boundary: int,
    anchor: int | None = None,
) -> str:
    clauses = [
        f"({base_where})",
        f"{config.object_id_field} <= {boundary}",
    ]
    if anchor is not None:
        clauses.append(f"{config.object_id_field} > {anchor}")
    return " AND ".join(clauses)


def _decode_arcgis_cursor(cursor: str) -> ArcGISCursorState:
    payload = _decode_cursor(ARCGIS_CURSOR_PREFIX, cursor)
    try:
        state = ArcGISCursorState(
            source_id=str(payload["source"]),
            criteria_fingerprint=str(payload["criteria"]),
            schema_fingerprint=str(payload["schema"]),
            boundary_object_id=int(payload["boundary"]),
            last_object_id=int(payload["last_oid"]),
            snapshot_count=int(payload["snapshot_count"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SourceSelectionError(
            "invalid_cursor",
            "ArcGIS continuation cursor values are malformed",
        ) from error
    if (
        state.boundary_object_id < 0
        or state.last_object_id < 0
        or state.last_object_id > state.boundary_object_id
        or state.snapshot_count < 0
        or not re.fullmatch(r"[0-9a-f]{64}", state.schema_fingerprint)
    ):
        raise SourceSelectionError(
            "invalid_cursor",
            "ArcGIS continuation cursor values are inconsistent",
        )
    return state


def _fetch_arcgis_batch(
    client: Any,
    config: ArcGISSource,
    *,
    operation: str,
    where: str,
    limit: int | None,
    cursor: str | None,
    return_geometry: bool,
) -> ArcGISBatch:
    metadata = client.fetch_metadata()
    current_schema, server_page_size = _metadata_contract(config, metadata)
    criteria = _arcgis_criteria(
        config,
        operation=operation,
        where=where,
        geometry=return_geometry,
    )
    cursor_state = _decode_arcgis_cursor(cursor) if cursor else None
    if cursor_state is not None:
        if (
            cursor_state.source_id != config.source_id
            or cursor_state.criteria_fingerprint != criteria
        ):
            raise SourceSelectionError(
                "cursor_query_mismatch",
                "continuation cursor belongs to different source or criteria",
            )
        if cursor_state.schema_fingerprint != current_schema:
            raise SourceSelectionError(
                "cursor_schema_changed",
                "source schema changed after this cursor was issued",
                status=ResultStatus.SOURCE_CHANGED,
            )

    total_count = client.fetch_count(where)
    if cursor_state is None:
        boundary_page = client.fetch_page(
            where=where,
            record_count=1,
            return_geometry=False,
            descending=True,
        )
        boundary = (
            _object_id(config, boundary_page[0]) if boundary_page else None
        )
        bounded_count = total_count
        anchor = None
        snapshot_count = bounded_count
    else:
        boundary = cursor_state.boundary_object_id
        anchor = cursor_state.last_object_id
        bounded_count = client.fetch_count(
            _bounded_where(config, where, boundary=boundary)
        )
        snapshot_count = cursor_state.snapshot_count
    if boundary is None:
        return ArcGISBatch(
            features=(),
            next_cursor=None,
            total_count=total_count,
            bounded_count=0,
            boundary_object_id=None,
            last_object_id=None,
            schema_fingerprint=current_schema,
            pages_fetched=0,
            count_changed_since_cursor=False,
        )

    collected: list[Mapping[str, Any]] = []
    seen: set[int] = set()
    pages_fetched = 0
    target = limit + 1 if limit is not None else None
    page_size = min(int(client.page_size), server_page_size)
    last_seen = anchor
    while target is None or len(collected) < target:
        requested = (
            page_size
            if target is None
            else min(page_size, target - len(collected))
        )
        page = client.fetch_page(
            where=_bounded_where(
                config,
                where,
                boundary=boundary,
                anchor=last_seen,
            ),
            record_count=requested,
            return_geometry=return_geometry,
        )
        pages_fetched += 1
        if not page:
            break
        for feature in page:
            object_id = _object_id(config, feature)
            if (
                object_id in seen
                or (last_seen is not None and object_id <= last_seen)
                or object_id > boundary
            ):
                raise SourceSchemaError(
                    "Yamhill ArcGIS ordered continuation repeated or crossed "
                    "its snapshot boundary",
                    url=config.layer_url,
                    details={
                        "object_id": object_id,
                        "previous_object_id": last_seen,
                        "boundary_object_id": boundary,
                    },
                )
            seen.add(object_id)
            last_seen = object_id
            collected.append(feature)
        if (
            target is None
            and cursor_state is None
            and len(collected) >= bounded_count
        ):
            break
        if len(page) < requested:
            break
    has_more = limit is not None and len(collected) > limit
    returned = collected if limit is None else collected[:limit]
    returned_last = (
        _object_id(config, returned[-1]) if returned else None
    )
    next_cursor = None
    if has_more and returned_last is not None:
        next_cursor = _encode_cursor(
            ARCGIS_CURSOR_PREFIX,
            {
                "v": CURSOR_VERSION,
                "source": config.source_id,
                "criteria": criteria,
                "schema": current_schema,
                "boundary": boundary,
                "last_oid": returned_last,
                "snapshot_count": snapshot_count,
            },
        )
    return ArcGISBatch(
        features=tuple(returned),
        next_cursor=next_cursor,
        total_count=total_count,
        bounded_count=bounded_count,
        boundary_object_id=boundary,
        last_object_id=returned_last,
        schema_fingerprint=current_schema,
        pages_fetched=pages_fetched,
        count_changed_since_cursor=(
            cursor_state is not None and bounded_count != snapshot_count
        ),
    )


def _address(
    *parts: Any,
) -> dict[str, Any]:
    cleaned = [_clean(part) for part in parts]
    return {
        "raw_parts": cleaned,
        "formatted": ", ".join(part for part in cleaned if part) or None,
    }


def _owners(attributes: Mapping[str, Any], fields: Sequence[str]) -> list[dict[str, Any]]:
    owners = []
    for field in fields:
        name = _clean(attributes.get(field))
        if name:
            owners.append(
                {
                    "name": name,
                    "role": "published_assessment_owner",
                    "source_field": field,
                }
            )
    return owners


def _normalize_taxlot(
    config: ArcGISSource,
    feature: Mapping[str, Any],
    *,
    schema_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes = _attributes(feature)
    object_id = _object_id(config, feature)
    account = _clean(attributes.get("acctnbr")) or _clean(
        attributes.get("account_num")
    )
    map_taxlot = _clean(attributes.get("maptaxlot"))
    instrument = _recording_number(
        attributes.get("instyr"),
        attributes.get("instnbr"),
    )
    canonical_ref = canonical_property_ref(
        config.source_id,
        COUNTY_GEOID,
        config.record_kind,
        str(object_id),
    )
    lineage = None
    if config is RETIRED_TAXLOTS:
        lineage = {
            "parent_taxlot": _clean(attributes.get("parent_taxlot")),
            "retired_by_global_id": _clean(attributes.get("retired_by")),
            "retired_taxlot_global_id": _clean(attributes.get("globalid")),
            "assertion_type": "published_retired_taxlot_lineage",
        }
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": config.source_id,
        "source_url": config.layer_url,
        "record_kind": config.record_kind,
        "source_record_id": str(object_id),
        "object_id": object_id,
        "account_number": account,
        "account_number_numeric": attributes.get("account_num"),
        "map_taxlot": map_taxlot,
        "global_id": _clean(attributes.get("globalid")),
        "status": (
            "retired_representation"
            if config is RETIRED_TAXLOTS
            else "current_representation"
        ),
        "representation": {
            "group": REPRESENTATION_GROUP,
            "role": config.representation_role,
            "overlap_interpretation": (
                "same_county_system_representation_not_independent_corroboration"
            ),
        },
        "owners": _owners(attributes, ("owner1", "owner2", "owner3")),
        "situs": _address(
            attributes.get("situs1"),
            attributes.get("situscity"),
            STATE_CODE,
            attributes.get("situszip"),
        ),
        "mailing": _address(
            attributes.get("mailadd1"),
            attributes.get("mailadd2"),
            attributes.get("mailcity"),
            attributes.get("mailstate"),
            attributes.get("mailzip"),
        ),
        "parcel": {
            "account_acres": _number(attributes.get("account_acres")),
            "parcel_acres": _number(attributes.get("parcel_acres")),
            "lot_square_feet": _number(attributes.get("sqft")),
        },
        "latest_deed_or_sale": {
            "instrument_year": _clean(attributes.get("instyr")),
            "instrument_number_raw": _clean(attributes.get("instnbr")),
            "recording_number": instrument,
            "deed_type": _clean(attributes.get("deedtype")),
            "sale_date_raw": _clean(attributes.get("saledate")),
            "sale_date_iso": _date_iso(attributes.get("saledate")),
            "sale_price": _number(attributes.get("saleprice")),
        },
        "building": {
            "year_built": _number(attributes.get("yearbuilt")),
            "bedrooms": _number(attributes.get("bedrms")),
            "full_bathrooms": _number(attributes.get("bathrms")),
            "half_bathrooms": _number(attributes.get("halfbaths")),
        },
        "lineage": lineage,
        "published_links": {
            "assessor_map": _clean(attributes.get("maplink")),
            "property_summary": _clean(attributes.get("propsumlink")),
        },
        "geometry": feature.get("geometry") if geometry_requested else None,
        "geometry_crs": "EPSG:4326" if geometry_requested else None,
        "source_response_schema_fingerprint": schema_value,
        "raw_attributes": dict(attributes),
        "join_candidates": {
            ASCEND_SOURCE_ID: {
                "account_number": account,
                "map_taxlot": map_taxlot,
                "relationship": "rich_account_assessment_and_tax_detail",
            },
            HELION_SOURCE_ID: {
                "recording_number": instrument,
                "owner_names": [
                    owner["name"]
                    for owner in _owners(
                        attributes,
                        ("owner1", "owner2", "owner3"),
                    )
                ],
                "relationship": "recorded_instrument_detail",
            },
        },
    }


def _normalize_permit(
    config: ArcGISSource,
    feature: Mapping[str, Any],
    *,
    schema_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes = _attributes(feature)
    object_id = _object_id(config, feature)
    native_id = _clean(attributes.get("Permit")) or str(object_id)
    account = _clean(attributes.get("account"))
    taxlot = _clean(attributes.get("taxlot"))
    canonical_ref = canonical_property_ref(
        config.source_id,
        COUNTY_GEOID,
        config.record_kind,
        f"{native_id}:{object_id}",
    )
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": config.source_id,
        "source_url": config.layer_url,
        "record_kind": config.record_kind,
        "source_record_id": str(object_id),
        "object_id": object_id,
        "native_permit_id": native_id,
        "publication_year": config.publication_year,
        "service_item_id": config.service_item_id,
        "account_number": account,
        "map_taxlot": taxlot,
        "owners": _owners(attributes, ("owner", "owner_1", "owner_12")),
        "situs": _address(
            attributes.get("situs_address"),
            attributes.get("situs_city"),
            STATE_CODE,
            attributes.get("situs_zip"),
        ),
        "mailing": _address(
            attributes.get("mailing_address_1"),
            attributes.get("mailing_address_2"),
            attributes.get("mailing_city"),
            attributes.get("mailing_state"),
            attributes.get("mailing_zip"),
        ),
        "permit": {
            "issue_date": _epoch_observation(attributes.get("IssueDate")),
            "description": _clean(attributes.get("Description")),
            "address_number": _clean(attributes.get("Situs_Address_1")),
            "street_direction": _clean(attributes.get("StreetDirection")),
            "street_name": _clean(attributes.get("StreetName")),
            "space": _clean(attributes.get("Space_")),
            "city": _clean(attributes.get("City")),
            "pca": attributes.get("PCA_1"),
            "appraiser": _clean(attributes.get("APPRAISER")),
        },
        "global_id": _clean(attributes.get("globalid")),
        "geometry": feature.get("geometry") if geometry_requested else None,
        "geometry_crs": "EPSG:4326" if geometry_requested else None,
        "source_response_schema_fingerprint": schema_value,
        "raw_attributes": dict(attributes),
        "join_candidates": {
            TAXLOT_SOURCE_ID: {
                "account_number": account,
                "map_taxlot": taxlot,
                "relationship": "current_taxlot_and_geometry_context",
            },
            ASCEND_SOURCE_ID: {
                "account_number": account,
                "map_taxlot": taxlot,
                "relationship": "assessment_account_and_value_context",
            },
        },
    }


def _normalize_arcgis(
    config: ArcGISSource,
    feature: Mapping[str, Any],
    *,
    schema_value: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    if config is PERMITS:
        return _normalize_permit(
            config,
            feature,
            schema_value=schema_value,
            geometry_requested=geometry_requested,
        )
    return _normalize_taxlot(
        config,
        feature,
        schema_value=schema_value,
        geometry_requested=geometry_requested,
    )


def _build_query(
    source_id: str,
    *,
    operation: str,
    parameters: Mapping[str, Any],
    requested_limit: int | None,
    cursor: str | None,
    access_decision: Mapping[str, Any] | None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA[source_id],
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
            metadata={
                "access_decision": dict(access_decision or {}),
                "continuation_contract": (
                    "query_schema_snapshot_bound_local_window"
                    if source_id == ASCEND_SOURCE_ID
                    else "query_schema_boundary_bound_object_id_keyset"
                ),
            },
        ),
    )


def _best_effort_log(
    query: PublicRecordsQuery,
    result: PublicRecordsResult,
) -> None:
    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    try:
        log_search(
            canonical_json(query.to_dict()),
            query.source.source_id,
            count,
        )
    except Exception as error:
        print(f"Warning: search log was not updated: {error}", file=sys.stderr)


def _selected_client(client: Any, source_id: str) -> Any:
    if isinstance(client, Mapping):
        return client.get(source_id)
    return client


def _new_ascend_client(args: argparse.Namespace) -> AscendWebClient:
    return AscendWebClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def _new_arcgis_client(
    args: argparse.Namespace,
    config: ArcGISSource,
) -> YamhillArcGISClient:
    return YamhillArcGISClient(
        config,
        page_size=args.page_size,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def _source_record(source_id: str) -> dict[str, Any]:
    metadata = SOURCE_METADATA[source_id].to_dict()
    if source_id == ASCEND_SOURCE_ID:
        search_fields = ["account", "address", "alternate"]
        required_fields = list(ASCEND_REQUIRED_FORM_FIELDS)
        observed = {
            "observed_at": "2026-07-29",
            "platform_version": ASCEND_VERSION_OBSERVED,
            "native_contract": YAMHILL_ASCEND_MANIFEST.contract_record(),
            "representative_complete_search": {
                "street": "MAIN",
                "record_count": 887,
                "response_bytes": ASCEND_OBSERVED_BROAD_SEARCH_BYTES,
            },
            "html_response_bound_bytes": ASCEND_MAX_HTML_BYTES,
            "sentinel_account": {
                "account_number": "41270",
                "map_taxlot": "R3218AB 00301",
                "recording_number": "2026-03177",
            },
        }
        warnings = list(ASCEND_WARNINGS)
    else:
        config = _arcgis_source(source_id)
        search_fields = sorted(
            {*config.search_fields, "object_id", "auto"}
        )
        required_fields = list(config.required_fields)
        observed_counts = {
            TAXLOT_SOURCE_ID: 51_507,
            RETIRED_SOURCE_ID: 810,
            PERMIT_SOURCE_ID: 3_216,
        }
        observed = {
            "observed_at": "2026-07-29",
            "component_count": observed_counts[source_id],
            "max_record_count": 2_000,
            "supports_ordered_pagination": True,
            "supports_geojson": True,
        }
        if source_id == TAXLOT_SOURCE_ID:
            observed["sentinel"] = {
                "account_number": "41270",
                "object_id": 5_144_427,
                "map_taxlot": "R3218AB 00301",
                "recording_number": "2026-03177",
            }
        if source_id == PERMIT_SOURCE_ID:
            observed["annual_item_discovery"] = {
                "organization_id": ARCGIS_ORG_ID,
                "configured_year": PERMIT_YEAR,
                "configured_item_id": PERMITS.service_item_id,
                "rollover_behavior": (
                    "probe_status_source_changed_when_selected_item_differs"
                ),
            }
        warnings = list(config.warnings)
    return {
        **metadata,
        "catalog_metadata": dict(CATALOG_METADATA[source_id]),
        "search_fields": search_fields,
        "required_fields": required_fields,
        "observed_contract": observed,
        "complementary_sources": [
            dict(item) for item in COMPLEMENTARY_SOURCES[source_id]
        ],
        "warnings": warnings,
    }


def _sources_payload() -> dict[str, Any]:
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "platform_family": "yamhill_county_property_components",
        "jurisdiction": JURISDICTION.to_dict(),
        "sources": [_source_record(source_id) for source_id in SOURCE_IDS],
        "process_learnings": [
            {
                "scope": "native_session_contract",
                "learning": (
                    "The published path is AcsendWeb and the ASP.NET session "
                    "segment and VIEWSTATE are refreshed from the live form."
                ),
            },
            {
                "scope": "complete_table_continuation",
                "learning": (
                    "AscendWeb returns broad matches in one complete table, so "
                    "bounded continuation is a local window tied to the query, "
                    "schema, and full-table snapshot."
                ),
            },
            {
                "scope": "representation_identity",
                "learning": (
                    "Current and retired ArcGIS taxlots share assessment fields "
                    "but provide current and lineage representations from the "
                    "same county system."
                ),
            },
            {
                "scope": "annual_source_discovery",
                "learning": (
                    "Searching the official ArcGIS organization for annual "
                    "permit feature services exposes publication rollover "
                    "without guessing the next service URL."
                ),
            },
        ],
    }


def _source_result(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None,
) -> PublicRecordsResult:
    query = _build_query(
        args.source,
        operation="source",
        parameters={"source_id": args.source},
        requested_limit=1,
        cursor=None,
        access_decision=access_decision,
    )
    return PublicRecordsResult.success(query, [_source_record(args.source)])


def _ascend_search_result(
    args: argparse.Namespace,
    *,
    client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> PublicRecordsResult:
    query = _build_query(
        ASCEND_SOURCE_ID,
        operation="search",
        parameters={
            "selector": args.query,
            "field": args.field,
            "city": args.city,
            "state": args.state,
            "postal_code": args.postal_code,
            "geometry": args.geometry,
        },
        requested_limit=args.limit,
        cursor=args.cursor,
        access_decision=access_decision,
    )
    try:
        criteria, parameters = _ascend_criteria(
            field=args.field,
            query=args.query,
            city=args.city,
            state=args.state,
            postal_code=args.postal_code,
        )
        active_client = client or _new_ascend_client(args)
        page = active_client.search(**parameters)
        soup = BeautifulSoup(page.html, "lxml")
        warnings = list(ASCEND_WARNINGS)
        if args.geometry:
            warnings.append(
                "AscendWeb publishes account detail without polygon geometry; "
                "the A&T Taxlots component supplies the geometry join."
            )
        if soup.select_one("#ParcelSitusTable") is not None:
            if args.cursor:
                raise SourceSelectionError(
                    "cursor_query_mismatch",
                    "exact account detail has no local result-table continuation",
                )
            record = parse_ascend_detail(
                page.html,
                source_url=page.source_url,
            )
            record["retrieval_snapshot"] = {
                "native_response": "exact_account_detail",
                "total_matching_records": 1,
                "window_returned_records": 1,
                "continuation_available": False,
            }
            result = PublicRecordsResult.success(
                query,
                [record],
                warnings=warnings,
            )
        else:
            parsed = parse_ascend_search(
                page.html,
                source_url=page.source_url,
            )
            offset = 0
            if args.cursor:
                payload = _decode_cursor(ASCEND_CURSOR_PREFIX, args.cursor)
                try:
                    source_id = str(payload["source"])
                    cursor_criteria = str(payload["criteria"])
                    cursor_schema = str(payload["schema"])
                    cursor_snapshot = str(payload["snapshot"])
                    offset = int(payload["offset"])
                    cursor_total = int(payload["total"])
                except (KeyError, TypeError, ValueError) as error:
                    raise SourceSelectionError(
                        "invalid_cursor",
                        "AscendWeb continuation cursor values are malformed",
                    ) from error
                if source_id != ASCEND_SOURCE_ID or cursor_criteria != criteria:
                    raise SourceSelectionError(
                        "cursor_query_mismatch",
                        "AscendWeb cursor belongs to different search criteria",
                    )
                if cursor_schema != parsed.schema_fingerprint:
                    raise SourceSelectionError(
                        "cursor_schema_changed",
                        "AscendWeb result schema changed after cursor issuance",
                        status=ResultStatus.SOURCE_CHANGED,
                    )
                if (
                    cursor_snapshot != parsed.snapshot_fingerprint
                    or cursor_total != parsed.total_count
                ):
                    raise SourceSelectionError(
                        "cursor_snapshot_changed",
                        "AscendWeb complete result snapshot changed after "
                        "cursor issuance",
                        status=ResultStatus.SOURCE_CHANGED,
                    )
                if offset < 0 or offset > parsed.total_count:
                    raise SourceSelectionError(
                        "invalid_cursor",
                        "AscendWeb cursor offset is outside the result snapshot",
                    )
            end = (
                parsed.total_count
                if args.limit is None
                else min(offset + args.limit, parsed.total_count)
            )
            window = [dict(record) for record in parsed.records[offset:end]]
            next_cursor = None
            if end < parsed.total_count:
                next_cursor = _encode_cursor(
                    ASCEND_CURSOR_PREFIX,
                    {
                        "v": CURSOR_VERSION,
                        "source": ASCEND_SOURCE_ID,
                        "criteria": criteria,
                        "schema": parsed.schema_fingerprint,
                        "snapshot": parsed.snapshot_fingerprint,
                        "offset": end,
                        "total": parsed.total_count,
                    },
                )
            snapshot = {
                "native_response": "complete_search_table",
                "total_matching_records": parsed.total_count,
                "window_offset": offset,
                "window_returned_records": len(window),
                "continuation_available": next_cursor is not None,
                "schema_fingerprint": parsed.schema_fingerprint,
                "snapshot_fingerprint": parsed.snapshot_fingerprint,
            }
            for record in window:
                record["source_response_schema_fingerprint"] = (
                    parsed.schema_fingerprint
                )
                record["retrieval_snapshot"] = snapshot
            result = PublicRecordsResult.success(
                query,
                window,
                next_cursor=next_cursor,
                warnings=warnings,
            )
    except SourceSelectionError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=ASCEND_WARNINGS,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=ASCEND_WARNINGS)
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
            warnings=ASCEND_WARNINGS,
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def _ascend_detail_result(
    args: argparse.Namespace,
    *,
    client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> PublicRecordsResult:
    query = _build_query(
        ASCEND_SOURCE_ID,
        operation="detail",
        parameters={
            "account_number": args.query,
            "tax_year": args.tax_year,
        },
        requested_limit=1,
        cursor=None,
        access_decision=access_decision,
    )
    try:
        account = _clean(args.query)
        if account is None:
            raise SourceSelectionError(
                "blank_query",
                "account number must not be blank",
            )
        active_client = client or _new_ascend_client(args)
        detail, installment = active_client.detail(
            account,
            tax_year=args.tax_year,
        )
        record = parse_ascend_detail(
            detail.html,
            source_url=detail.source_url,
            installment_html=installment.html if installment else None,
            installment_source_url=(
                installment.source_url if installment else None
            ),
        )
        if record["account_number"] != account:
            raise SourceSchemaError(
                "AscendWeb returned a different account detail",
                url=detail.source_url,
                details={
                    "requested": account,
                    "returned": record["account_number"],
                },
            )
        record["retrieval_snapshot"] = {
            "native_response": "exact_account_detail",
            "tax_year_postback_requested": args.tax_year,
            "installment_detail_returned": installment is not None,
        }
        result = PublicRecordsResult.success(
            query,
            [record],
            warnings=ASCEND_WARNINGS,
        )
    except SourceSelectionError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=ASCEND_WARNINGS,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=ASCEND_WARNINGS)
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
            warnings=ASCEND_WARNINGS,
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def _arcgis_records_result(
    args: argparse.Namespace,
    config: ArcGISSource,
    *,
    client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> PublicRecordsResult:
    query = _build_query(
        config.source_id,
        operation=args.command,
        parameters={
            "selector": args.query,
            "field": args.field,
            "geometry": args.geometry,
        },
        requested_limit=args.limit,
        cursor=args.cursor,
        access_decision=access_decision,
    )
    try:
        where = _arcgis_where(
            config,
            operation=args.command,
            selector=args.query,
            field=args.field,
        )
        active_client = client or _new_arcgis_client(args, config)
        batch = _fetch_arcgis_batch(
            active_client,
            config,
            operation=args.command,
            where=where,
            limit=args.limit,
            cursor=args.cursor,
            return_geometry=args.geometry,
        )
        records = [
            _normalize_arcgis(
                config,
                feature,
                schema_value=batch.schema_fingerprint,
                geometry_requested=args.geometry,
            )
            for feature in batch.features
        ]
        snapshot = {
            "total_matching_records_at_retrieval": batch.total_count,
            "records_inside_cursor_boundary": batch.bounded_count,
            "boundary_object_id": batch.boundary_object_id,
            "last_object_id": batch.last_object_id,
            "window_returned_records": len(records),
            "continuation_available": batch.next_cursor is not None,
            "pages_fetched": batch.pages_fetched,
            "schema_fingerprint": batch.schema_fingerprint,
            "count_changed_inside_boundary_since_cursor": (
                batch.count_changed_since_cursor
            ),
        }
        for record in records:
            record["retrieval_snapshot"] = snapshot
        warnings = list(config.warnings)
        if batch.count_changed_since_cursor:
            warnings.append(
                "The count inside the original object-ID boundary changed "
                "since cursor issuance; the same boundary remained in force."
            )
        result = PublicRecordsResult.success(
            query,
            records,
            next_cursor=batch.next_cursor,
            warnings=warnings,
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
                    code="normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=config.warnings,
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def _ascend_probe_result(
    args: argparse.Namespace,
    *,
    client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> PublicRecordsResult:
    query = _build_query(
        ASCEND_SOURCE_ID,
        operation="probe",
        parameters={"sentinel_account": args.sentinel_account},
        requested_limit=1,
        cursor=None,
        access_decision=access_decision,
    )
    try:
        active_client = client or _new_ascend_client(args)
        home = active_client.fetch_home()
        contract = parse_ascend_home(
            home.html,
            source_url=home.source_url,
        )
        detail, _ = active_client.detail(args.sentinel_account)
        record = parse_ascend_detail(
            detail.html,
            source_url=detail.source_url,
        )
        result = PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": ASCEND_SOURCE_ID,
                    "platform_version": contract.version,
                    "version_observed_during_discovery": (
                        ASCEND_VERSION_OBSERVED
                    ),
                    "home_schema_fingerprint": contract.schema_fingerprint,
                    "form_fields": list(contract.form_fields),
                    "native_path": "/AcsendWeb/",
                    "session_contract": (
                        "aspnet_cookieless_session_and_viewstate"
                    ),
                    "sentinel": {
                        "account_number": record["account_number"],
                        "map_taxlot": record["alternate_map_taxlot"],
                        "party_count": len(record["parties"]),
                        "value_series_count": len(record["value_history"]),
                        "receipt_count": len(record["receipts"]),
                        "sale_count": len(record["sales"]),
                        "recording_numbers": record["join_candidates"][
                            HELION_SOURCE_ID
                        ]["recording_numbers"],
                    },
                    "complementary_sources": [
                        dict(item)
                        for item in COMPLEMENTARY_SOURCES[ASCEND_SOURCE_ID]
                    ],
                }
            ],
            warnings=ASCEND_WARNINGS,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=ASCEND_WARNINGS)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="probe_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=ASCEND_WARNINGS,
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def _arcgis_probe_result(
    args: argparse.Namespace,
    config: ArcGISSource,
    *,
    client: Any,
    discovery_client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> PublicRecordsResult:
    query = _build_query(
        config.source_id,
        operation="probe",
        parameters={"where": "1=1"},
        requested_limit=2,
        cursor=None,
        access_decision=access_decision,
    )
    try:
        active_client = client or _new_arcgis_client(args, config)
        metadata = active_client.fetch_metadata()
        schema_value, maximum = _metadata_contract(config, metadata)
        count = active_client.fetch_count("1=1")
        first_page = active_client.fetch_page(
            where="1=1",
            record_count=1,
            return_geometry=False,
        )
        last_page = active_client.fetch_page(
            where="1=1",
            record_count=1,
            return_geometry=False,
            descending=True,
        )
        annual_discovery = None
        discovery_warning = None
        if config is PERMITS:
            try:
                permit_client = discovery_client or PermitDiscoveryClient(
                    timeout=args.timeout,
                    minimum_interval=args.minimum_interval,
                    retry_attempts=args.retry_attempts,
                )
                annual_discovery = parse_permit_discovery(
                    permit_client.fetch_items()
                )
            except PublicRecordsHTTPError as discovery_error:
                annual_discovery = {
                    "status": "unavailable",
                    "error": discovery_error.to_contract_error().to_dict(),
                }
                discovery_warning = (
                    "The configured permit layer probed successfully, while "
                    "annual item discovery was unavailable in this probe."
                )
        first = (
            _normalize_arcgis(
                config,
                first_page[0],
                schema_value=schema_value,
                geometry_requested=False,
            )
            if first_page
            else None
        )
        last = (
            _normalize_arcgis(
                config,
                last_page[0],
                schema_value=schema_value,
                geometry_requested=False,
            )
            if last_page
            else None
        )
        warnings = list(config.warnings)
        if discovery_warning:
            warnings.append(discovery_warning)
        probe_record = {
            "record_kind": "source_probe",
            "source_id": config.source_id,
            "component_total_count": count,
            "schema_fingerprint": schema_value,
            "layer_name": metadata.get("name"),
            "layer_id": metadata.get("id"),
            "service_item_id": metadata.get("serviceItemId"),
            "max_record_count": maximum,
            "source_crs": config.source_crs,
            "output_geometry_crs": "EPSG:4326",
            "geometry_type": metadata.get("geometryType"),
            "first_ordered_observation": first,
            "last_ordered_observation": last,
            "annual_discovery": annual_discovery,
            "complementary_sources": [
                dict(item)
                for item in COMPLEMENTARY_SOURCES[config.source_id]
            ],
        }
        if (
            config is PERMITS
            and isinstance(annual_discovery, Mapping)
            and annual_discovery.get("rollover_observed") is True
        ):
            selected = annual_discovery.get("selected")
            result = PublicRecordsResult.failure(
                query,
                ResultStatus.SOURCE_CHANGED,
                [
                    PublicRecordsError(
                        code="annual_permit_rollover",
                        message=(
                            "The official ArcGIS organization selected a "
                            "different annual permit year or item"
                        ),
                        category="source_schema",
                        retryable=False,
                        details={
                            "configured_year": PERMIT_YEAR,
                            "configured_item_id": PERMITS.service_item_id,
                            "selected": selected,
                        },
                    )
                ],
                records=[probe_record],
                warnings=warnings,
            )
        else:
            result = PublicRecordsResult.success(
                query,
                [probe_record],
                warnings=warnings,
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
                    retryable=False,
                )
            ],
            warnings=config.warnings,
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def _all_probe_payload(
    args: argparse.Namespace,
    *,
    client: Any,
    discovery_client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    for source_id in SOURCE_IDS:
        selected = _selected_client(client, source_id)
        if source_id == ASCEND_SOURCE_ID:
            result = _ascend_probe_result(
                args,
                client=selected,
                access_decision=access_decision,
                log_results=log_results,
            )
        else:
            result = _arcgis_probe_result(
                args,
                _arcgis_source(source_id),
                client=selected,
                discovery_client=discovery_client,
                access_decision=access_decision,
                log_results=log_results,
            )
        components.append(result.to_dict())
    successful = sum(
        component["status"] in {"ok", "no_results"}
        for component in components
    )
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "status": (
            "ok"
            if successful == len(components)
            else "partial"
            if successful
            else "unavailable"
        ),
        "components": components,
    }


def execute(
    args: argparse.Namespace,
    *,
    client: Any = None,
    discovery_client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute source listing, source detail, query, detail, or probe."""

    if args.command == "sources":
        return _sources_payload()
    if args.command == "source":
        return _source_result(args, access_decision=access_decision)
    if args.command == "probe":
        if args.all_sources:
            return _all_probe_payload(
                args,
                client=client,
                discovery_client=discovery_client,
                access_decision=access_decision,
                log_results=log_results,
            )
        selected = _selected_client(client, args.source)
        if args.source == ASCEND_SOURCE_ID:
            return _ascend_probe_result(
                args,
                client=selected,
                access_decision=access_decision,
                log_results=log_results,
            )
        return _arcgis_probe_result(
            args,
            _arcgis_source(args.source),
            client=selected,
            discovery_client=discovery_client,
            access_decision=access_decision,
            log_results=log_results,
        )
    selected = _selected_client(client, args.source)
    if args.source == ASCEND_SOURCE_ID:
        if args.command == "detail":
            return _ascend_detail_result(
                args,
                client=selected,
                access_decision=access_decision,
                log_results=log_results,
            )
        return _ascend_search_result(
            args,
            client=selected,
            access_decision=access_decision,
            log_results=log_results,
        )
    return _arcgis_records_result(
        args,
        _arcgis_source(args.source),
        client=selected,
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
    result_count = (
        len(records)
        if isinstance(records, list)
        else len(payload.get("components", payload.get("sources", [])))
    )
    if write_output(
        payload,
        args,
        summary=f"Yamhill property {args.command}",
        result_count=result_count,
    ):
        return
    if args.command == "sources":
        print(f"Yamhill County property components: {len(payload['sources'])}")
        for source in payload["sources"]:
            print(f"  {source['source_id']} | {source['source_role']}")
        return
    if args.command == "probe" and args.all_sources:
        print(f"Yamhill County property probes: {payload['status']}")
        for component in payload["components"]:
            print(
                f"  {component['query']['source']['source_id']} | "
                f"{component['status']}"
            )
        return
    rows = payload.get("records", [])
    print(
        f"Yamhill property {args.command}: "
        f"{payload.get('status')} ({len(rows)} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in rows:
        identity = (
            record.get("account_number")
            or record.get("native_permit_id")
            or record.get("source_record_id")
            or record.get("source_id")
        )
        print(f"  {identity} | {record.get('record_kind')}")
    for error in payload.get("errors", []):
        print(
            f"ERROR [{error.get('code')}]: {error.get('message')}",
            file=sys.stderr,
        )


def _add_transport_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_page_size: bool = True,
) -> None:
    if include_page_size:
        parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    else:
        parser.set_defaults(page_size=DEFAULT_PAGE_SIZE)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=int, default=3)
    add_output_args(parser)


SEARCH_FIELD_CHOICES = (
    "auto",
    "account",
    "alternate",
    "address",
    "map_taxlot",
    "owner",
    "recording",
    "native_id",
    "description",
    "global_id",
    "parent_taxlot",
    "retired_by",
    "object_id",
)


def _add_record_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        required=True,
        choices=SOURCE_IDS,
        help="Exact component-scoped source ID",
    )
    parser.add_argument(
        "--field",
        choices=SEARCH_FIELD_CHOICES,
        default="auto",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Return at most this many records; omitted traverses all matches",
    )
    parser.add_argument(
        "--cursor",
        help="Continuation cursor returned by the same source and criteria",
    )
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="Include WGS84 geometry when the selected component publishes it",
    )
    parser.add_argument("--city", default="")
    parser.add_argument("--state", default="")
    parser.add_argument("--postal-code", default="")
    parser.set_defaults(tax_year=None)
    _add_transport_arguments(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Yamhill County AscendWeb property accounts, "
            "current and retired taxlots, and annual assessment permits"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="List independently attributable components and complements",
    )
    add_output_args(sources)

    source = sub.add_parser(
        "source",
        help="Show one component's source contract",
    )
    source.add_argument("--source", required=True, choices=SOURCE_IDS)
    add_output_args(source)

    search = sub.add_parser(
        "search",
        help="Search one selected component",
    )
    search.add_argument("query")
    _add_record_arguments(search)

    detail = sub.add_parser(
        "detail",
        help="Fetch exact account or component detail",
    )
    detail.add_argument("query")
    _add_record_arguments(detail)
    detail.add_argument(
        "--tax-year",
        type=int,
        help="AscendWeb installment year postback",
    )

    probe = sub.add_parser(
        "probe",
        help="Run bounded component health probes",
    )
    selection = probe.add_mutually_exclusive_group(required=True)
    selection.add_argument("--source", choices=SOURCE_IDS)
    selection.add_argument("--all", action="store_true", dest="all_sources")
    probe.set_defaults(all_sources=False)
    probe.add_argument("--sentinel-account", default="41270")
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
    if (
        getattr(args, "limit", None) is not None
        and args.limit <= 0
    ):
        parser.error("--limit must be positive")
    if hasattr(args, "query") and not args.query.strip():
        parser.error("query must not be blank")
    tax_year = getattr(args, "tax_year", None)
    if tax_year is not None and not 1900 <= tax_year <= 2200:
        parser.error("--tax-year must be a four-digit year")
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
