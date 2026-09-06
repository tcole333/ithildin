#!/usr/bin/env python3
"""Query Multnomah County, Oregon SAIL property and survey components.

The 2026 Survey and Assessor Image Locator (SAIL) publishes eight separately
attributable ArcGIS components.  This adapter preserves each component's
source-native row identity and schema while resolving the county's image-viewer
representations for survey, plat, corner, and field-book records.

Examples:
    uv run python tools/query_oregon_multnomah_sail.py sources
    uv run python tools/query_oregon_multnomah_sail.py search 05335 \
        --source us-or-multnomah-sail-survey-records --field survey-id \
        --match exact
    uv run python tools/query_oregon_multnomah_sail.py record 7220 \
        --source us-or-multnomah-sail-survey-records --geometry
    uv run python tools/query_oregon_multnomah_sail.py image 05335 \
        --source us-or-multnomah-sail-survey-records
    uv run python tools/query_oregon_multnomah_sail.py download 05335 \
        --source us-or-multnomah-sail-survey-records \
        --destination /tmp/05335.pdf
    uv run python tools/query_oregon_multnomah_sail.py probe --all
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote, unquote, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

try:
    from tools import oregon_arcgis_keyset as arcgis_shared
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
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TransportError,
        failure_result,
        system_trust_session,
    )
    from tools.public_records_store import canonical_property_ref
except ImportError:
    import oregon_arcgis_keyset as arcgis_shared
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
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TransportError,
        failure_result,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref


STATE_CODE = "OR"
STATE_FIPS = "41"
COUNTY_NAME = "Multnomah County, Oregon"
COUNTY_GEOID = "41051"

EXPERIENCE_ID = "56186ebe00fc4ad9b922e08c9025cd1f"
EXPERIENCE_URL = (
    "https://experience.arcgis.com/experience/"
    f"{EXPERIENCE_ID}/"
)
EXPERIENCE_DATA_URL = (
    "https://www.arcgis.com/sharing/rest/content/items/"
    f"{EXPERIENCE_ID}/data"
)
EXPERIENCE_MODIFIED_OBSERVED = "2026-06-03"
ARCGIS_ORG_BASE = (
    "https://services5.arcgis.com/x7DNZL1YqNQVNykA/ArcGIS/rest/services"
)
IMAGE_VIEWER_TEMPLATE = (
    "https://www3.multco.us/viewimage/view_survey.aspx?docid={survey_id}"
)

TAX_PARCEL_SOURCE_ID = "us-or-multnomah-sail-tax-parcels"
SURVEY_SOURCE_ID = "us-or-multnomah-sail-survey-records"
SUBDIVISION_SOURCE_ID = "us-or-multnomah-sail-subdivision-plats"
PARTITION_SOURCE_ID = "us-or-multnomah-sail-partition-plats"
CONDOMINIUM_SOURCE_ID = "us-or-multnomah-sail-condominium-plats"
ROAD_SOURCE_ID = "us-or-multnomah-sail-road-surveys"
CORNER_SOURCE_ID = (
    "us-or-multnomah-sail-bearing-tree-public-land-corners"
)
FIELD_BOOK_SOURCE_ID = (
    "us-or-multnomah-sail-field-book-quarter-sheets"
)

SOURCE_IDS = (
    TAX_PARCEL_SOURCE_ID,
    SURVEY_SOURCE_ID,
    SUBDIVISION_SOURCE_ID,
    PARTITION_SOURCE_ID,
    CONDOMINIUM_SOURCE_ID,
    ROAD_SOURCE_ID,
    CORNER_SOURCE_ID,
    FIELD_BOOK_SOURCE_ID,
)
IMAGE_SOURCE_IDS = tuple(
    source_id for source_id in SOURCE_IDS if source_id != TAX_PARCEL_SOURCE_ID
)

DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_PAGE_SIZE = 1_000
DEFAULT_MAXIMUM_HTML_BYTES = 4 * 1024 * 1024
DEFAULT_MAXIMUM_DOCUMENT_BYTES = 128 * 1024 * 1024
DEFAULT_MAXIMUM_ERROR_BYTES = 8 * 1024
USER_AGENT = "IthildinOSINT/1.0 Multnomah County SAIL client"
OUTPUT_SCHEMA_VERSION = "oregon-multnomah-sail/1.0"
PROBE_SCHEMA_VERSION = "oregon-multnomah-sail-probe/1.0"

KNOWN_SURVEY_ID = "05335"
KNOWN_SURVEY_OBJECT_ID = 7220
KNOWN_SURVEY_PDF_BYTES = 27_434
KNOWN_SURVEY_PDF_SHA256 = (
    "43fa876fdbfbf039f01eeb00bb43b24e"
    "97311ff8737cccfa6383aafbe59e73c5"
)
KNOWN_TAX_PROPERTY_ID = "R330254"

COMMON_SURVEY_FIELDS = (
    "OBJECTID",
    "SURVEYID",
    "CLIENT",
    "SURVEYORKE",
    "FIRM",
    "CLERKNUMBE",
    "SURVEYTYPE",
    "SUBDIVISIO",
    "COMMENTS",
    "NUMBEROFSH",
    "VERIFIED",
    "DATEMODIFI",
    "MODIFIEDBY",
    "X_COORD",
    "Y_COORD",
    "SD_DATE",
    "FD_DATE",
    "SURVEYDATE",
    "FILEDATE",
)
SURVEY_FIELDS = (*COMMON_SURVEY_FIELDS, "ORIG_FID")
PLAT_FIELDS = (*COMMON_SURVEY_FIELDS, "Shape__Area", "Shape__Length")
CORNER_FIELDS = (
    "OBJECTID",
    "POINT",
    "NORTHING",
    "EASTING",
    "TYPE",
    "TOWNSHIP",
    "CORNER_NAM",
    "DLC",
    "NEWBLMID",
    "RELIABILIT",
    "DOCUMENTNA",
    "SURVEYID",
    "QUALITY",
    "SURVEY",
    "DATESURVEY",
    "STRBLMID",
    "BT_BK_PAGE",
    "BT_BOOK",
    "BT_PAGE",
    "Documentn1",
)
FIELD_BOOK_FIELDS = (
    "OBJECTID",
    "SURVEYID",
    "SurveyType",
    "Shape__Area",
    "Shape__Length",
)
TAX_FIELDS = (
    "OBJECTID_1",
    "MAPTAXLOT",
    "PROPID",
    "ALTACCTNUM",
    "NAME",
    "NAME2",
    "ADDR1",
    "ADDR2",
    "CITY",
    "STATE",
    "ZIP",
    "SITUSNUM",
    "SITUSDIR",
    "SITUSNAME",
    "SITUSSUFFIX",
    "SITUSSUFFIX2",
    "SITUSUNITTYPE",
    "SITUSUNITNUM",
    "SITUSADDR",
    "SITUSCITY",
    "SITUSSTATE",
    "SITUSZIP",
    "MAPID",
    "LEGAL",
    "TRACTLOT",
    "BLOCK",
    "ADDLEGAL",
    "LOC_CODE",
    "ACCOUNT_STATUS",
    "LEVYCODE",
    "NBOCODE",
    "IMP_COUNT",
    "PROPCLASS",
    "PROP_CODE",
    "DEED_TYPE",
    "INST_NUM",
    "DEED_DATE",
    "SALE_PRICE",
    "SALE_DATE",
    "EXEMPTION",
    "ZONING",
    "SIZEACRES",
    "SIZESQFT",
    "IMPTYPE",
    "ACTYEARBUILT",
    "MAINAREA",
    "UNITS",
    "MAIN_SQFT",
    "ROLLYEAR",
    "ROLLLAND",
    "ROLLIMP",
    "ROLLM50",
    "TownshipRange",
    "AssessorMap",
    "Shape__Area",
    "Shape__Length",
)

COMMON_SURVEY_SEARCH_FIELDS: Mapping[str, tuple[str, ...]] = {
    "auto": (
        "SURVEYID",
        "CLIENT",
        "SURVEYORKE",
        "FIRM",
        "CLERKNUMBE",
        "SURVEYTYPE",
        "SUBDIVISIO",
        "COMMENTS",
        "SURVEYDATE",
        "FILEDATE",
    ),
    "survey-id": ("SURVEYID",),
    "client": ("CLIENT",),
    "surveyor": ("SURVEYORKE",),
    "firm": ("FIRM",),
    "clerk": ("CLERKNUMBE",),
    "type": ("SURVEYTYPE",),
    "subdivision": ("SUBDIVISIO",),
    "comment": ("COMMENTS",),
}
CORNER_SEARCH_FIELDS: Mapping[str, tuple[str, ...]] = {
    "auto": (
        "SURVEYID",
        "TYPE",
        "TOWNSHIP",
        "CORNER_NAM",
        "DLC",
        "NEWBLMID",
        "DOCUMENTNA",
        "BT_BK_PAGE",
        "BT_BOOK",
        "BT_PAGE",
    ),
    "survey-id": ("SURVEYID",),
    "point": ("POINT",),
    "type": ("TYPE",),
    "township": ("TOWNSHIP",),
    "corner": ("CORNER_NAM",),
    "document": ("DOCUMENTNA", "Documentn1"),
    "book-page": ("BT_BK_PAGE",),
}
FIELD_BOOK_SEARCH_FIELDS: Mapping[str, tuple[str, ...]] = {
    "auto": ("SURVEYID", "SurveyType"),
    "survey-id": ("SURVEYID",),
    "type": ("SurveyType",),
}
TAX_SEARCH_FIELDS: Mapping[str, tuple[str, ...]] = {
    "auto": (
        "MAPTAXLOT",
        "PROPID",
        "ALTACCTNUM",
        "NAME",
        "NAME2",
        "SITUSADDR",
        "ADDR1",
        "ADDR2",
        "INST_NUM",
        "LEGAL",
        "ADDLEGAL",
    ),
    "property-id": ("PROPID",),
    "account": ("PROPID", "ALTACCTNUM"),
    "map-taxlot": ("MAPTAXLOT",),
    "owner": ("NAME", "NAME2"),
    "address": ("SITUSADDR", "ADDR1", "ADDR2"),
    "instrument": ("INST_NUM",),
    "legal": ("LEGAL", "ADDLEGAL"),
}


@dataclass(frozen=True)
class SAILComponent:
    key: str
    source_id: str
    name: str
    service_name: str
    layer_name: str
    item_id: str
    object_id_field: str
    fields: tuple[str, ...]
    source_crs_wkids: tuple[int, ...]
    source_crs_label: str
    geometry_type: str
    record_kind: str
    source_role: str
    observed_count: int
    search_fields: Mapping[str, tuple[str, ...]]
    numeric_fields: tuple[str, ...] = ()
    image_capable: bool = True
    publisher_note: str | None = None

    @property
    def layer_url(self) -> str:
        return (
            f"{ARCGIS_ORG_BASE}/{self.service_name}/FeatureServer/0"
        )

    @property
    def manifest(self) -> arcgis_shared.ArcGISLayerManifest:
        return arcgis_shared.ArcGISLayerManifest(
            source_id=self.source_id,
            name=self.name,
            layer_url=self.layer_url,
            layer_id=0,
            service_item_id=self.item_id,
            expected_layer_name=self.layer_name,
            object_id_field=self.object_id_field,
            required_fields=self.fields,
            source_crs_wkids=self.source_crs_wkids,
            record_kind=self.record_kind,
            publisher="Multnomah County",
            observed_count=self.observed_count,
        )


COMPONENTS: Mapping[str, SAILComponent] = {
    TAX_PARCEL_SOURCE_ID: SAILComponent(
        key="tax-parcels",
        source_id=TAX_PARCEL_SOURCE_ID,
        name="Multnomah County SAIL Tax Parcels",
        service_name="Multnomah_County_Taxlot_Parcels",
        layer_name="Multnomah County Tax Parcels",
        item_id="13a535596a1f4fe0887b03d14d943229",
        object_id_field="OBJECTID_1",
        fields=TAX_FIELDS,
        source_crs_wkids=(102100, 3857),
        source_crs_label="EPSG:3857 (native WKID 102100)",
        geometry_type="esriGeometryPolygon",
        record_kind="current_assessment_tax_parcel",
        source_role=(
            "official_county_current_tax_parcel_assessment_owner_and_sale"
        ),
        observed_count=284_039,
        search_fields=TAX_SEARCH_FIELDS,
        image_capable=False,
    ),
    SURVEY_SOURCE_ID: SAILComponent(
        key="survey-records",
        source_id=SURVEY_SOURCE_ID,
        name="Multnomah County SAIL Survey Records",
        service_name="SAIL_Survey_Records",
        layer_name="Survey Records",
        item_id="1f0a8b50952540119fe013d193f77778",
        object_id_field="OBJECTID",
        fields=SURVEY_FIELDS,
        source_crs_wkids=(2913,),
        source_crs_label="EPSG:2913",
        geometry_type="esriGeometryPoint",
        record_kind="survey_record",
        source_role="official_county_survey_record_index_geometry_and_images",
        observed_count=87_179,
        search_fields=COMMON_SURVEY_SEARCH_FIELDS,
    ),
    SUBDIVISION_SOURCE_ID: SAILComponent(
        key="subdivision-plats",
        source_id=SUBDIVISION_SOURCE_ID,
        name="Multnomah County SAIL Subdivision Plats",
        service_name="SAIL_Subdivision_Plat",
        layer_name="Subdivision Plat",
        item_id="6e48c416548544b283c3fba1538333bd",
        object_id_field="OBJECTID",
        fields=PLAT_FIELDS,
        source_crs_wkids=(102100, 3857),
        source_crs_label="EPSG:3857 (native WKID 102100)",
        geometry_type="esriGeometryPolygon",
        record_kind="subdivision_plat",
        source_role="official_county_subdivision_plat_index_geometry_and_images",
        observed_count=6_314,
        search_fields=COMMON_SURVEY_SEARCH_FIELDS,
    ),
    PARTITION_SOURCE_ID: SAILComponent(
        key="partition-plats",
        source_id=PARTITION_SOURCE_ID,
        name="Multnomah County SAIL Partition Plats",
        service_name="SAIL_Partition_Plat",
        layer_name="Partition Plat",
        item_id="48d3bf9fbacb4a6abc53456f2aaa1f77",
        object_id_field="OBJECTID",
        fields=PLAT_FIELDS,
        source_crs_wkids=(102100, 3857),
        source_crs_label="EPSG:3857 (native WKID 102100)",
        geometry_type="esriGeometryPolygon",
        record_kind="partition_plat",
        source_role="official_county_partition_plat_index_geometry_and_images",
        observed_count=4_454,
        search_fields=COMMON_SURVEY_SEARCH_FIELDS,
    ),
    CONDOMINIUM_SOURCE_ID: SAILComponent(
        key="condominium-plats",
        source_id=CONDOMINIUM_SOURCE_ID,
        name="Multnomah County SAIL Condominium Plats",
        service_name="SAIL_Condominium_Plat",
        layer_name="Condominium Plat",
        item_id="92b959a6491340619dd7250becf7ba62",
        object_id_field="OBJECTID",
        fields=PLAT_FIELDS,
        source_crs_wkids=(2913,),
        source_crs_label="EPSG:2913",
        geometry_type="esriGeometryPolygon",
        record_kind="condominium_plat",
        source_role="official_county_condominium_plat_index_geometry_and_images",
        observed_count=1_720,
        search_fields=COMMON_SURVEY_SEARCH_FIELDS,
    ),
    ROAD_SOURCE_ID: SAILComponent(
        key="road-surveys",
        source_id=ROAD_SOURCE_ID,
        name="Multnomah County SAIL Road Surveys",
        service_name="SAIL_Road_Survey",
        layer_name="Road Surveys",
        item_id="ff53eb6c206347538e1594e4c58fca00",
        object_id_field="OBJECTID",
        fields=PLAT_FIELDS,
        source_crs_wkids=(2913,),
        source_crs_label="EPSG:2913",
        geometry_type="esriGeometryPolygon",
        record_kind="road_survey",
        source_role="official_county_road_survey_index_geometry_and_images",
        observed_count=4_439,
        search_fields=COMMON_SURVEY_SEARCH_FIELDS,
        publisher_note=(
            "The County's SAIL help text states that the Road Survey layer "
            "does not represent a complete collection of County Road "
            "information and directs additional road questions to the County "
            "Surveyor's Office."
        ),
    ),
    CORNER_SOURCE_ID: SAILComponent(
        key="bearing-tree-public-land-corners",
        source_id=CORNER_SOURCE_ID,
        name="Multnomah County SAIL Bearing Trees and Public Land Corners",
        service_name="SAIL_Bearing_Tree_Public_Land_Corner",
        layer_name="Bearing Tree Public Land Corner",
        item_id="0c14743a6e89402d8d348af9497c77e7",
        object_id_field="OBJECTID",
        fields=CORNER_FIELDS,
        source_crs_wkids=(2913,),
        source_crs_label="EPSG:2913",
        geometry_type="esriGeometryPoint",
        record_kind="bearing_tree_public_land_corner",
        source_role=(
            "official_county_bearing_tree_public_land_corner_index_geometry"
            "_and_images"
        ),
        observed_count=8_997,
        search_fields=CORNER_SEARCH_FIELDS,
        numeric_fields=("POINT", "NEWBLMID", "SURVEY", "STRBLMID", "BT_PAGE"),
    ),
    FIELD_BOOK_SOURCE_ID: SAILComponent(
        key="field-book-quarter-sheets",
        source_id=FIELD_BOOK_SOURCE_ID,
        name="Multnomah County SAIL Field Books and Quarter Sheets",
        service_name="SAIL_Field_Book_Quarter_Sheets",
        layer_name="Field Book",
        item_id="9f877a2a76db4209bb9e4e04092a7148",
        object_id_field="OBJECTID",
        fields=FIELD_BOOK_FIELDS,
        source_crs_wkids=(2913,),
        source_crs_label="EPSG:2913",
        geometry_type="esriGeometryPolygon",
        record_kind="field_book_quarter_sheet",
        source_role="official_county_field_book_quarter_sheet_index_and_images",
        observed_count=2_714,
        search_fields=FIELD_BOOK_SEARCH_FIELDS,
    ),
}

SEARCH_FIELDS = tuple(
    sorted(
        {
            "object-id",
            *(
                field
                for component in COMPONENTS.values()
                for field in component.search_fields
            ),
        }
    )
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality="Multnomah County",
    metadata={"state_fips": STATE_FIPS},
)

PROPERTY_SEARCH_TOOLS_URL = (
    "https://multco.us/info/property-search-tools-and-maps"
)
SURVEYOR_OFFICE_URL = (
    "https://multco.us/departments/county-surveyors-office"
)
PROPERTY_RECORDS_URL = (
    "https://multco.us/info/property-records-and-recording"
)

COMPLEMENTARY_SOURCES: tuple[Mapping[str, Any], ...] = (
    {
        "name": "MultcoPropTax guest property search",
        "url": "https://multcoproptax.com/",
        "relationship": "current_property_account_detail",
        "join_fields": ["PROPID", "address"],
        "adds": [
            "land and building detail",
            "values and tax amounts",
            "payment history",
            "tax bill",
        ],
        "access_fact": (
            "The county describes a free guest login; the current guest entry "
            "also presents an interactive verification step."
        ),
    },
    {
        "name": "MultcoRecords recorded-document search",
        "url": "https://multcorecords.com/",
        "relationship": "recorded_instrument_index_and_copy_route",
        "join_fields": ["INST_NUM", "party", "recording date", "legal"],
        "adds": [
            "recorded documents since February 2002",
            "party names and types",
            "document type and recording date",
            "legal description and document copies",
        ],
    },
    {
        "name": "DART standard reports and public-record requests",
        "url": PROPERTY_SEARCH_TOOLS_URL,
        "relationship": "standard_bulk_report_and_custom_request_route",
        "join_fields": ["PROPID", "MAPTAXLOT", "address"],
        "adds": [
            "defined assessment and taxation reports",
            "older or custom property records",
        ],
    },
    {
        "name": "Multnomah County property records and recording",
        "url": PROPERTY_RECORDS_URL,
        "relationship": "older_record_image_and_office_request_route",
        "join_fields": ["INST_NUM", "party", "recording date"],
        "adds": [
            "older recorded-document image ordering",
            "lobby research",
            "public-record request route",
        ],
    },
    {
        "source_id": "us-or-portland-regional-taxlots",
        "name": "Portland and Metro regional taxlot representations",
        "url": "https://www.portlandmaps.com/",
        "relationship": "overlapping_regional_parcel_and_context_representation",
        "join_fields": ["PROPID", "MAPTAXLOT", "address"],
        "adds": ["regional parcel context", "planning and permit context"],
        "lineage_note": (
            "The SAIL parcel row and regional taxlot rows can share county "
            "upstream data; matching rows are representations, not independent "
            "corroboration."
        ),
    },
    {
        "name": "Oregon ORMAP assessor-map program",
        "url": "https://ormap.net/",
        "relationship": "statewide_assessor_map_complement",
        "join_fields": ["MAPTAXLOT", "TownshipRange", "AssessorMap"],
        "adds": ["statewide cadastral map discovery"],
    },
    {
        "name": "Multnomah County Surveyor assistance",
        "url": SURVEYOR_OFFICE_URL,
        "relationship": "survey_record_and_additional_road_information_route",
        "join_fields": ["SURVEYID", "road", "public land corner"],
        "adds": [
            "survey record assistance",
            "additional County Road information",
            "records not located through SAIL",
        ],
        "contact": "survey.records@multco.us",
    },
)


def _source_metadata(component: SAILComponent) -> SourceMetadata:
    metadata: dict[str, Any] = {
        "publisher": "Multnomah County",
        "county_geoid": COUNTY_GEOID,
        "platform_family": "arcgis_feature_service",
        "experience": {
            "item_id": EXPERIENCE_ID,
            "url": EXPERIENCE_URL,
            "modified_observed": EXPERIENCE_MODIFIED_OBSERVED,
            "configuration_url": EXPERIENCE_DATA_URL,
        },
        "native_crs": component.source_crs_label,
        "output_geometry_crs": "EPSG:4326",
        "native_row_identity": component.object_id_field,
        "cursor_sort_tuple": [component.object_id_field],
        "image_viewer_template": (
            IMAGE_VIEWER_TEMPLATE if component.image_capable else None
        ),
    }
    if component.publisher_note:
        metadata["publisher_note"] = component.publisher_note
    if component.source_id == TAX_PARCEL_SOURCE_ID:
        metadata["lineage"] = (
            "Keep this county SAIL parcel representation distinct from, but "
            "lineage-linked to, Portland and Metro regional taxlot rows."
        )
    return SourceMetadata(
        source_id=component.source_id,
        name=component.name,
        source_role=component.source_role,
        base_url=component.layer_url,
        dataset_id=component.item_id,
        metadata=metadata,
    )


SOURCE_METADATA: Mapping[str, SourceMetadata] = {
    source_id: _source_metadata(component)
    for source_id, component in COMPONENTS.items()
}


@dataclass(frozen=True)
class ResponseArtifact:
    content: bytes
    source_url: str
    headers: Mapping[str, str]
    status_code: int

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    @property
    def content_type(self) -> str | None:
        for key, value in self.headers.items():
            if str(key).casefold() == "content-type":
                return str(value).split(";", 1)[0].strip().casefold()
        return None


class SourceSelectionError(ValueError):
    """Structured component, field, cursor, or document-selection failure."""

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


class _RateLimitedSession:
    """Session proxy sharing one limiter across all ArcGIS components."""

    def __init__(
        self,
        session: requests.Session | Any,
        limiter: MinimumIntervalRateLimiter,
    ) -> None:
        self.session = session
        self.limiter = limiter

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        self.limiter.wait()
        return self.session.request(method, url, **kwargs)

    def close(self) -> None:
        return None


class MultnomahSAILClient:
    """Shared bounded transport for SAIL ArcGIS and image representations."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if page_size < 1:
            raise ValueError("page_size must be positive")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.page_size = page_size
        self.timeout = timeout
        self.retry_policy = RetryPolicy(max_attempts=retry_attempts)
        self.sleeper = sleeper
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            clock=clock,
            sleeper=sleeper,
        )
        self._rate_session = _RateLimitedSession(
            self.session,
            self.rate_limiter,
        )
        self.headers = {
            "Accept": "*/*",
            "User-Agent": USER_AGENT,
        }

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def layer_client(
        self,
        component: SAILComponent,
    ) -> arcgis_shared.BoundedArcGISClient:
        return arcgis_shared.BoundedArcGISClient(
            component.manifest,
            session=self._rate_session,
            page_size=self.page_size,
            timeout=self.timeout,
            minimum_interval=0,
            retry_attempts=self.retry_policy.max_attempts,
            sleeper=self.sleeper,
        )

    @staticmethod
    def _header(response: Any, name: str) -> str | None:
        for key, value in getattr(response, "headers", {}).items():
            if str(key).casefold() == name.casefold():
                return str(value)
        return None

    @staticmethod
    def _retry_after(response: Any) -> float | None:
        raw = MultnomahSAILClient._header(response, "retry-after")
        if raw is None:
            return None
        try:
            return max(0.0, float(raw))
        except ValueError:
            return None

    @staticmethod
    def _read_bounded(
        response: Any,
        *,
        maximum_bytes: int,
    ) -> tuple[bytes, bool]:
        body = bytearray()
        truncated = False
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                remaining = maximum_bytes - len(body)
                if remaining <= 0:
                    truncated = True
                    break
                body.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    truncated = True
                    break
            return bytes(body), truncated
        finally:
            response.close()

    @staticmethod
    def _validate_viewer_url(value: str) -> None:
        parsed = urlparse(value)
        if (
            parsed.scheme.casefold() != "https"
            or parsed.hostname != "www3.multco.us"
            or parsed.username
            or parsed.password
            or parsed.path.casefold() != "/viewimage/view_survey.aspx"
        ):
            raise SourceSchemaError(
                "SAIL image-viewer response left the official viewer route",
                url=value,
            )

    @staticmethod
    def _validate_pdf_url(value: str) -> None:
        parsed = urlparse(value)
        if (
            parsed.scheme.casefold() != "https"
            or parsed.hostname != "www4.multco.us"
            or parsed.username
            or parsed.password
            or not parsed.path.casefold().startswith("/surveyimages/")
            or not parsed.path.casefold().endswith(".pdf")
        ):
            raise SourceSchemaError(
                "SAIL document link is outside the official PDF repository",
                url=value,
            )

    def _request_bytes(
        self,
        url: str,
        *,
        maximum_bytes: int,
        validator: Callable[[str], None],
        accept: str,
    ) -> ResponseArtifact:
        validator(url)
        last_error: requests.RequestException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    "GET",
                    url,
                    headers={**self.headers, "Accept": accept},
                    timeout=self.timeout,
                    allow_redirects=True,
                    stream=True,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                break
            try:
                for hop in [*getattr(response, "history", ()), response]:
                    validator(str(getattr(hop, "url", url)))
            except Exception:
                response.close()
                raise
            status = int(getattr(response, "status_code", 0))
            if (
                status in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                delay = self.retry_policy.delay(
                    attempt,
                    self._retry_after(response),
                )
                response.close()
                self.sleeper(delay)
                continue
            if status == 429:
                response.close()
                raise RateLimitedHTTPError(status, url=url)
            if status in {401, 403}:
                response.close()
                raise RestrictedHTTPError(status, url=url)
            if status in {404, 410}:
                response.close()
                raise SourceChangedHTTPError(status, url=url)
            if status < 200 or status >= 300:
                body, truncated = self._read_bounded(
                    response,
                    maximum_bytes=DEFAULT_MAXIMUM_ERROR_BYTES,
                )
                excerpt = body.decode("utf-8", errors="replace")
                raise HTTPStatusError(
                    status,
                    url=url,
                    response_text=f"{excerpt}{'…' if truncated else ''}",
                )
            declared = self._header(response, "content-length")
            if declared is not None:
                try:
                    declared_bytes = int(declared)
                except ValueError:
                    declared_bytes = None
                if (
                    declared_bytes is not None
                    and declared_bytes > maximum_bytes
                ):
                    response.close()
                    raise SourceSchemaError(
                        "SAIL response exceeds its declared byte bound",
                        url=url,
                        details={
                            "declared_bytes": declared_bytes,
                            "maximum_bytes": maximum_bytes,
                        },
                    )
            headers = {
                str(key): str(value)
                for key, value in getattr(response, "headers", {}).items()
            }
            source_url = str(getattr(response, "url", url))
            body, truncated = self._read_bounded(
                response,
                maximum_bytes=maximum_bytes + 1,
            )
            if truncated or len(body) > maximum_bytes:
                raise SourceSchemaError(
                    "SAIL response exceeded its byte bound while streaming",
                    url=url,
                    details={
                        "bytes_read": len(body),
                        "maximum_bytes": maximum_bytes,
                    },
                )
            return ResponseArtifact(
                content=body,
                source_url=source_url,
                headers=headers,
                status_code=status,
            )
        raise TransportError(
            "SAIL request failed after bounded retries",
            url=url,
            details={"error": str(last_error or "retry attempts exhausted")},
        )

    def fetch_image_viewer(self, survey_id: str) -> ResponseArtifact:
        url = image_viewer_url(survey_id)
        return self._request_bytes(
            url,
            maximum_bytes=DEFAULT_MAXIMUM_HTML_BYTES,
            validator=self._validate_viewer_url,
            accept="text/html,application/xhtml+xml",
        )

    def fetch_pdf(
        self,
        url: str,
        *,
        maximum_bytes: int = DEFAULT_MAXIMUM_DOCUMENT_BYTES,
    ) -> ResponseArtifact:
        artifact = self._request_bytes(
            url,
            maximum_bytes=maximum_bytes,
            validator=self._validate_pdf_url,
            accept="application/pdf,*/*;q=0.8",
        )
        if not artifact.content.startswith(b"%PDF-"):
            raise SourceResponseError(
                "SAIL document response is not a PDF",
                url=artifact.source_url,
                details={
                    "content_type": artifact.content_type,
                    "prefix_hex": artifact.content[:8].hex(),
                },
            )
        return artifact


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _epoch_milliseconds(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return (
            datetime.fromtimestamp(value / 1_000, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
    except (OSError, OverflowError, ValueError):
        return None


def _source_crs_record(component: SAILComponent) -> dict[str, Any]:
    return {
        "label": component.source_crs_label,
        "accepted_native_wkids": list(component.source_crs_wkids),
        "geometry_type": component.geometry_type,
    }


def image_viewer_url(survey_id: str) -> str:
    value = _clean(survey_id)
    if value is None:
        raise SourceSelectionError(
            "blank_survey_id",
            "survey document ID must not be blank",
        )
    return IMAGE_VIEWER_TEMPLATE.format(survey_id=quote(value, safe="-_."))


def _normalize_pdf_link(href: str, *, viewer_url: str) -> str:
    value = href.strip().replace("\\", "/")
    parsed = urlparse(urljoin(viewer_url, value))
    if parsed.scheme.casefold() == "http" and parsed.hostname == "www4.multco.us":
        parsed = parsed._replace(scheme="https")
    normalized = urlunparse(parsed._replace(fragment=""))
    MultnomahSAILClient._validate_pdf_url(normalized)
    return normalized


def parse_image_viewer(
    html: str,
    *,
    survey_id: str,
    source_url: str,
) -> dict[str, Any]:
    """Parse and normalize every official PDF representation in viewer HTML."""

    soup = BeautifulSoup(html, "lxml")
    representations: list[dict[str, Any]] = []
    seen: set[str] = set()
    anchor_contract: list[dict[str, Any]] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", "")).strip()
        if not href:
            continue
        anchor_contract.append(
            {
                "id": _clean(anchor.get("id")),
                "target": _clean(anchor.get("target")),
                "extension": Path(
                    urlparse(href.replace("\\", "/")).path
                ).suffix.casefold(),
            }
        )
        try:
            pdf_url = _normalize_pdf_link(href, viewer_url=source_url)
        except SourceSchemaError:
            continue
        if pdf_url in seen:
            continue
        seen.add(pdf_url)
        representations.append(
            {
                "index": len(representations) + 1,
                "label": _clean(anchor.get_text(" ", strip=True)),
                "pdf_url": pdf_url,
                "source_href": href,
            }
        )
    form = soup.find("form")
    form_action = _clean(form.get("action")) if form else None
    return {
        "record_kind": "sail_image_viewer",
        "survey_document_id": survey_id,
        "viewer_url": source_url,
        "viewer_schema_fingerprint": sha256_fingerprint(
            {
                "form_action_present": form_action is not None,
                "anchors": anchor_contract,
            }
        ),
        "form_action": form_action,
        "representations": representations,
    }


def _normalize_geometry(
    feature: Mapping[str, Any],
    *,
    component: SAILComponent,
    requested: bool,
) -> dict[str, Any]:
    value = feature.get("geometry") if requested else None
    return {
        "requested": requested,
        "value": value,
        "output_crs": "EPSG:4326" if value is not None else None,
        "native_crs": _source_crs_record(component),
    }


def _representation_for_survey_id(
    component: SAILComponent,
    survey_id: str | None,
) -> list[dict[str, Any]]:
    if not component.image_capable or survey_id is None:
        return []
    return [
        {
            "representation_kind": "county_image_viewer",
            "url": image_viewer_url(survey_id),
            "join_field": "SURVEYID",
            "join_value": survey_id,
        }
    ]


def _normalize_survey_component(
    component: SAILComponent,
    attributes: Mapping[str, Any],
    feature: Mapping[str, Any],
    *,
    schema_fingerprint: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    object_id = attributes.get(component.object_id_field)
    if isinstance(object_id, bool) or not isinstance(object_id, int):
        raise SourceSchemaError(
            "SAIL feature lacks its integer object ID",
            url=component.layer_url,
            details={
                "object_id_field": component.object_id_field,
                "value": object_id,
            },
        )
    survey_id = _clean(attributes.get("SURVEYID"))
    client = _clean(attributes.get("CLIENT"))
    record = {
        "record_kind": component.record_kind,
        "source_id": component.source_id,
        "source_record_id": str(object_id),
        "canonical_ref": canonical_property_ref(
            component.source_id,
            COUNTY_GEOID,
            component.record_kind,
            str(object_id),
        ),
        "jurisdiction_geoid": COUNTY_GEOID,
        "native_ids": {
            component.object_id_field: object_id,
            "SURVEYID": survey_id,
            "ORIG_FID": attributes.get("ORIG_FID"),
        },
        "object_id": object_id,
        "survey_document_id": survey_id,
        "client": client,
        "road_name": client if component.source_id == ROAD_SOURCE_ID else None,
        "surveyor": _clean(attributes.get("SURVEYORKE")),
        "firm": _clean(attributes.get("FIRM")),
        "clerk_number": _clean(attributes.get("CLERKNUMBE")),
        "survey_type": _clean(attributes.get("SURVEYTYPE")),
        "subdivision_or_plat_name": _clean(attributes.get("SUBDIVISIO")),
        "comments": _clean(attributes.get("COMMENTS")),
        "number_of_sheets": attributes.get("NUMBEROFSH"),
        "verified": _clean(attributes.get("VERIFIED")),
        "modified_by": _clean(attributes.get("MODIFIEDBY")),
        "coordinates_native_fields": {
            "x": attributes.get("X_COORD"),
            "y": attributes.get("Y_COORD"),
        },
        "dates": {
            "survey_epoch_raw": attributes.get("SD_DATE"),
            "survey_epoch_iso": _epoch_milliseconds(
                attributes.get("SD_DATE")
            ),
            "file_epoch_raw": attributes.get("FD_DATE"),
            "file_epoch_iso": _epoch_milliseconds(
                attributes.get("FD_DATE")
            ),
            "survey_date_raw": _clean(attributes.get("SURVEYDATE")),
            "file_date_raw": _clean(attributes.get("FILEDATE")),
            "date_modified_raw": _clean(attributes.get("DATEMODIFI")),
        },
        "shape_metrics": {
            "area": attributes.get("Shape__Area"),
            "length": attributes.get("Shape__Length"),
        },
        "representations": _representation_for_survey_id(
            component,
            survey_id,
        ),
        "geometry": _normalize_geometry(
            feature,
            component=component,
            requested=geometry_requested,
        ),
        "source_response_schema_fingerprint": schema_fingerprint,
        "raw_attributes": dict(attributes),
        "source_url": component.layer_url,
    }
    if survey_id is not None:
        record["join_candidates"] = {
            "sail_image_viewer": {
                "field": "SURVEYID",
                "value": survey_id,
                "relationship": "exact_document_representation_join",
            }
        }
    else:
        record["join_candidates"] = {}
    return record


def _normalize_corner(
    component: SAILComponent,
    attributes: Mapping[str, Any],
    feature: Mapping[str, Any],
    *,
    schema_fingerprint: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    object_id = attributes.get(component.object_id_field)
    if isinstance(object_id, bool) or not isinstance(object_id, int):
        raise SourceSchemaError(
            "SAIL corner feature lacks integer OBJECTID",
            url=component.layer_url,
            details={"OBJECTID": object_id},
        )
    survey_id = _clean(attributes.get("SURVEYID"))
    return {
        "record_kind": component.record_kind,
        "source_id": component.source_id,
        "source_record_id": str(object_id),
        "canonical_ref": canonical_property_ref(
            component.source_id,
            COUNTY_GEOID,
            component.record_kind,
            str(object_id),
        ),
        "jurisdiction_geoid": COUNTY_GEOID,
        "native_ids": {
            "OBJECTID": object_id,
            "POINT": attributes.get("POINT"),
            "SURVEYID": survey_id,
            "NEWBLMID": attributes.get("NEWBLMID"),
            "STRBLMID": attributes.get("STRBLMID"),
        },
        "object_id": object_id,
        "survey_document_id": survey_id,
        "point_number": attributes.get("POINT"),
        "northing": attributes.get("NORTHING"),
        "easting": attributes.get("EASTING"),
        "corner_type": _clean(attributes.get("TYPE")),
        "township": _clean(attributes.get("TOWNSHIP")),
        "corner_name": _clean(attributes.get("CORNER_NAM")),
        "donation_land_claim": _clean(attributes.get("DLC")),
        "reliability": _clean(attributes.get("RELIABILIT")),
        "quality": _clean(attributes.get("QUALITY")),
        "document_name": _clean(attributes.get("DOCUMENTNA")),
        "document_name_alternate": _clean(attributes.get("Documentn1")),
        "survey_number": attributes.get("SURVEY"),
        "survey_date_raw": _clean(attributes.get("DATESURVEY")),
        "bearing_tree": {
            "book_page": _clean(attributes.get("BT_BK_PAGE")),
            "book": _clean(attributes.get("BT_BOOK")),
            "page": attributes.get("BT_PAGE"),
        },
        "representations": _representation_for_survey_id(
            component,
            survey_id,
        ),
        "geometry": _normalize_geometry(
            feature,
            component=component,
            requested=geometry_requested,
        ),
        "source_response_schema_fingerprint": schema_fingerprint,
        "raw_attributes": dict(attributes),
        "source_url": component.layer_url,
        "join_candidates": (
            {
                "sail_image_viewer": {
                    "field": "SURVEYID",
                    "value": survey_id,
                    "relationship": "exact_document_representation_join",
                }
            }
            if survey_id is not None
            else {}
        ),
    }


def _normalize_field_book(
    component: SAILComponent,
    attributes: Mapping[str, Any],
    feature: Mapping[str, Any],
    *,
    schema_fingerprint: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    object_id = attributes.get(component.object_id_field)
    if isinstance(object_id, bool) or not isinstance(object_id, int):
        raise SourceSchemaError(
            "SAIL field-book feature lacks integer OBJECTID",
            url=component.layer_url,
            details={"OBJECTID": object_id},
        )
    survey_id = _clean(attributes.get("SURVEYID"))
    return {
        "record_kind": component.record_kind,
        "source_id": component.source_id,
        "source_record_id": str(object_id),
        "canonical_ref": canonical_property_ref(
            component.source_id,
            COUNTY_GEOID,
            component.record_kind,
            str(object_id),
        ),
        "jurisdiction_geoid": COUNTY_GEOID,
        "native_ids": {
            "OBJECTID": object_id,
            "SURVEYID": survey_id,
        },
        "object_id": object_id,
        "survey_document_id": survey_id,
        "survey_type": _clean(attributes.get("SurveyType")),
        "shape_metrics": {
            "area": attributes.get("Shape__Area"),
            "length": attributes.get("Shape__Length"),
        },
        "representations": _representation_for_survey_id(
            component,
            survey_id,
        ),
        "geometry": _normalize_geometry(
            feature,
            component=component,
            requested=geometry_requested,
        ),
        "source_response_schema_fingerprint": schema_fingerprint,
        "raw_attributes": dict(attributes),
        "source_url": component.layer_url,
        "join_candidates": (
            {
                "sail_image_viewer": {
                    "field": "SURVEYID",
                    "value": survey_id,
                    "relationship": "exact_document_representation_join",
                }
            }
            if survey_id is not None
            else {}
        ),
    }


def _normalize_tax_parcel(
    component: SAILComponent,
    attributes: Mapping[str, Any],
    feature: Mapping[str, Any],
    *,
    schema_fingerprint: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    object_id = attributes.get(component.object_id_field)
    if isinstance(object_id, bool) or not isinstance(object_id, int):
        raise SourceSchemaError(
            "SAIL tax-parcel feature lacks integer OBJECTID_1",
            url=component.layer_url,
            details={"OBJECTID_1": object_id},
        )
    property_id = _clean(attributes.get("PROPID"))
    map_taxlot = _clean(attributes.get("MAPTAXLOT"))
    alternate_account = _clean(attributes.get("ALTACCTNUM"))
    instrument = _clean(attributes.get("INST_NUM"))
    assessor_map = _clean(attributes.get("AssessorMap"))
    representations: list[dict[str, Any]] = []
    if assessor_map is not None:
        representations.append(
            {
                "representation_kind": "county_assessor_map_pdf",
                "url": assessor_map.replace("http://", "https://", 1),
                "join_field": "AssessorMap",
                "join_value": assessor_map,
            }
        )
    return {
        "record_kind": component.record_kind,
        "source_id": component.source_id,
        "source_record_id": str(object_id),
        "canonical_ref": canonical_property_ref(
            component.source_id,
            COUNTY_GEOID,
            component.record_kind,
            str(object_id),
        ),
        "jurisdiction_geoid": COUNTY_GEOID,
        "native_ids": {
            "OBJECTID_1": object_id,
            "PROPID": property_id,
            "MAPTAXLOT": map_taxlot,
            "ALTACCTNUM": alternate_account,
        },
        "object_id": object_id,
        "native_parcel_id": property_id or map_taxlot,
        "property_id": property_id,
        "map_taxlot": map_taxlot,
        "alternate_account_number": alternate_account,
        "owners": [
            value
            for value in (
                _clean(attributes.get("NAME")),
                _clean(attributes.get("NAME2")),
            )
            if value is not None
        ],
        "mailing": {
            "address_1": _clean(attributes.get("ADDR1")),
            "address_2": _clean(attributes.get("ADDR2")),
            "city": _clean(attributes.get("CITY")),
            "state": _clean(attributes.get("STATE")),
            "postal_code": _clean(attributes.get("ZIP")),
        },
        "situs": {
            "number": _clean(attributes.get("SITUSNUM")),
            "direction": _clean(attributes.get("SITUSDIR")),
            "street_name": _clean(attributes.get("SITUSNAME")),
            "suffix": _clean(attributes.get("SITUSSUFFIX")),
            "suffix_2": _clean(attributes.get("SITUSSUFFIX2")),
            "unit_type": _clean(attributes.get("SITUSUNITTYPE")),
            "unit_number": _clean(attributes.get("SITUSUNITNUM")),
            "address": _clean(attributes.get("SITUSADDR")),
            "city": _clean(attributes.get("SITUSCITY")),
            "state": _clean(attributes.get("SITUSSTATE")),
            "postal_code": _clean(attributes.get("SITUSZIP")),
        },
        "map": {
            "map_id": _clean(attributes.get("MAPID")),
            "township_range": _clean(attributes.get("TownshipRange")),
            "assessor_map_url": assessor_map,
        },
        "legal": {
            "description": _clean(attributes.get("LEGAL")),
            "tract_lot": _clean(attributes.get("TRACTLOT")),
            "block": _clean(attributes.get("BLOCK")),
            "additional": _clean(attributes.get("ADDLEGAL")),
        },
        "classification": {
            "location_code": _clean(attributes.get("LOC_CODE")),
            "account_status": _clean(attributes.get("ACCOUNT_STATUS")),
            "levy_code": _clean(attributes.get("LEVYCODE")),
            "neighborhood_code": _clean(attributes.get("NBOCODE")),
            "property_class": _clean(attributes.get("PROPCLASS")),
            "property_code": _clean(attributes.get("PROP_CODE")),
            "exemption": _clean(attributes.get("EXEMPTION")),
            "zoning": _clean(attributes.get("ZONING")),
        },
        "latest_deed_or_sale": {
            "deed_type": _clean(attributes.get("DEED_TYPE")),
            "instrument_number": instrument,
            "deed_date_raw": attributes.get("DEED_DATE"),
            "deed_date_iso": _epoch_milliseconds(
                attributes.get("DEED_DATE")
            ),
            "sale_price": attributes.get("SALE_PRICE"),
            "sale_date_raw": attributes.get("SALE_DATE"),
            "sale_date_iso": _epoch_milliseconds(
                attributes.get("SALE_DATE")
            ),
        },
        "land": {
            "size_acres": attributes.get("SIZEACRES"),
            "size_square_feet": attributes.get("SIZESQFT"),
        },
        "improvements": {
            "count": _clean(attributes.get("IMP_COUNT")),
            "type": _clean(attributes.get("IMPTYPE")),
            "actual_year_built": attributes.get("ACTYEARBUILT"),
            "main_area": attributes.get("MAINAREA"),
            "units": attributes.get("UNITS"),
            "main_square_feet": attributes.get("MAIN_SQFT"),
        },
        "roll_values": {
            "year": attributes.get("ROLLYEAR"),
            "land": attributes.get("ROLLLAND"),
            "improvements": attributes.get("ROLLIMP"),
            "measure_50": attributes.get("ROLLM50"),
        },
        "shape_metrics": {
            "area": attributes.get("Shape__Area"),
            "length": attributes.get("Shape__Length"),
        },
        "representations": representations,
        "geometry": _normalize_geometry(
            feature,
            component=component,
            requested=geometry_requested,
        ),
        "source_response_schema_fingerprint": schema_fingerprint,
        "raw_attributes": dict(attributes),
        "source_url": component.layer_url,
        "join_candidates": {
            "multco_property_tax": {
                "property_id": property_id,
                "alternate_account_number": alternate_account,
                "relationship": "exact_property_account_join",
            },
            "multco_recorder": {
                "instrument_number": instrument,
                "relationship": "recorded_instrument_detail_complement",
            },
            "portland_metro_regional_taxlots": {
                "property_id": property_id,
                "map_taxlot": map_taxlot,
                "relationship": (
                    "overlapping_regional_representation_with_shared_lineage"
                ),
            },
        },
    }


def normalize_feature(
    component: SAILComponent,
    feature: Mapping[str, Any],
    *,
    schema_fingerprint: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    attributes = dict(arcgis_shared.feature_attributes(feature))
    if component.source_id == TAX_PARCEL_SOURCE_ID:
        return _normalize_tax_parcel(
            component,
            attributes,
            feature,
            schema_fingerprint=schema_fingerprint,
            geometry_requested=geometry_requested,
        )
    if component.source_id == CORNER_SOURCE_ID:
        return _normalize_corner(
            component,
            attributes,
            feature,
            schema_fingerprint=schema_fingerprint,
            geometry_requested=geometry_requested,
        )
    if component.source_id == FIELD_BOOK_SOURCE_ID:
        return _normalize_field_book(
            component,
            attributes,
            feature,
            schema_fingerprint=schema_fingerprint,
            geometry_requested=geometry_requested,
        )
    return _normalize_survey_component(
        component,
        attributes,
        feature,
        schema_fingerprint=schema_fingerprint,
        geometry_requested=geometry_requested,
    )


CATALOG_METADATA: Mapping[str, Mapping[str, Any]] = {
    source_id: {
        "source_id": source_id,
        "category": "property",
        "record_types": [component.record_kind],
        "jurisdiction": COUNTY_GEOID,
        "access_method": "rest_api",
        "auth": "none",
        "official": True,
        "url": component.layer_url,
        "query_tool": "tools/query_oregon_multnomah_sail.py",
        "pagination": "query_schema_boundary_bound_full_order_tuple_keyset",
        "supports_geometry": True,
        "supports_document_resolution": component.image_capable,
    }
    for source_id, component in COMPONENTS.items()
}


def _source_record(component: SAILComponent) -> dict[str, Any]:
    return {
        **SOURCE_METADATA[component.source_id].to_dict(),
        "catalog_metadata": dict(CATALOG_METADATA[component.source_id]),
        "component_key": component.key,
        "layer_name": component.layer_name,
        "layer_url": component.layer_url,
        "service_item_id": component.item_id,
        "record_kind": component.record_kind,
        "object_id_field": component.object_id_field,
        "sort_tuple": [component.object_id_field],
        "cursor_contract": {
            "ordering": f"{component.object_id_field} ASC",
            "complete_sort_tuple": [component.object_id_field],
            "snapshot_boundary": (
                f"maximum matching {component.object_id_field} at first page"
            ),
            "criteria_binding": [
                "source_id",
                "operation",
                "where",
                "return_geometry",
                "ordering",
                "declared_schema_fingerprint",
            ],
        },
        "geometry": {
            "native": _source_crs_record(component),
            "query_output": "EPSG:4326",
        },
        "required_fields": list(component.fields),
        "search_fields": sorted(
            {"object-id", *component.search_fields.keys()}
        ),
        "observed_contract": {
            "observed_at": "2026-07-30",
            "component_count": component.observed_count,
            "max_record_count": 2_000,
            "native_manifest": component.manifest.contract_record(),
            "image_viewer_template": (
                IMAGE_VIEWER_TEMPLATE if component.image_capable else None
            ),
            "publisher_note": component.publisher_note,
        },
        "complementary_sources": [
            dict(item) for item in COMPLEMENTARY_SOURCES
        ],
    }


def source_manifest() -> dict[str, Any]:
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "platform_family": "multnomah_county_sail_2026_components",
        "jurisdiction": JURISDICTION.to_dict(),
        "experience": {
            "item_id": EXPERIENCE_ID,
            "url": EXPERIENCE_URL,
            "configuration_url": EXPERIENCE_DATA_URL,
            "modified_observed": EXPERIENCE_MODIFIED_OBSERVED,
            "component_count": len(COMPONENTS),
        },
        "sources": [
            _source_record(COMPONENTS[source_id])
            for source_id in SOURCE_IDS
        ],
        "component_relationships": {
            "image_resolution": (
                "The Experience configuration constructs county image-viewer "
                "links from each document component's SURVEYID."
            ),
            "parcel_lineage": (
                "SAIL tax parcels and Portland/Metro regional taxlots are "
                "separately attributable representations that can share "
                "county upstream data."
            ),
            "row_identity": (
                "Each component's unique OID is the row identity and complete "
                "cursor ordering tuple; SURVEYID and property identifiers are "
                "retained as document and parcel joins."
            ),
        },
        "complementary_sources": [
            dict(item) for item in COMPLEMENTARY_SOURCES
        ],
    }


def _sql_text(value: str) -> str:
    return value.replace("'", "''")


EXACT_DEFAULT_FIELDS = frozenset(
    {
        "object-id",
        "survey-id",
        "property-id",
        "account",
        "map-taxlot",
        "instrument",
        "point",
        "book-page",
    }
)


def build_where(
    component: SAILComponent,
    query: str,
    *,
    field: str,
    match: str,
) -> tuple[str, str]:
    value = _clean(query)
    if value is None:
        raise SourceSelectionError(
            "blank_query",
            "query must not be blank",
        )
    if field == "object-id":
        try:
            object_id = int(value)
        except ValueError as error:
            raise SourceSelectionError(
                "invalid_object_id",
                "object ID must be an integer",
                details={"query": value},
            ) from error
        if object_id < 0:
            raise SourceSelectionError(
                "invalid_object_id",
                "object ID must be non-negative",
                details={"query": value},
            )
        return f"{component.object_id_field} = {object_id}", "exact"
    native_fields = component.search_fields.get(field)
    if native_fields is None:
        raise SourceSelectionError(
            "unsupported_field",
            f"{component.source_id} does not publish search field {field!r}",
            details={
                "source_id": component.source_id,
                "supported_fields": sorted(
                    {"object-id", *component.search_fields.keys()}
                ),
            },
        )
    selected_match = (
        "exact"
        if match == "auto" and field in EXACT_DEFAULT_FIELDS
        else "contains"
        if match == "auto"
        else match
    )
    clauses: list[str] = []
    for native_field in native_fields:
        if native_field in component.numeric_fields:
            if selected_match != "exact":
                continue
            try:
                numeric = int(value)
            except ValueError as error:
                raise SourceSelectionError(
                    "invalid_numeric_query",
                    f"{field} requires an integer for exact matching",
                    details={"field": field, "query": value},
                ) from error
            clauses.append(f"{native_field} = {numeric}")
            continue
        escaped = _sql_text(value)
        if selected_match == "exact":
            clauses.append(f"{native_field} = '{escaped}'")
        else:
            clauses.append(f"{native_field} LIKE '%{escaped}%'")
    if not clauses:
        raise SourceSelectionError(
            "unsupported_match",
            f"{field} does not support {selected_match} matching",
            details={
                "source_id": component.source_id,
                "field": field,
                "match": selected_match,
            },
        )
    if len(clauses) == 1:
        return clauses[0], selected_match
    return f"({' OR '.join(clauses)})", selected_match


def _build_query(
    component: SAILComponent,
    *,
    operation: str,
    parameters: Mapping[str, Any],
    requested_limit: int | None,
    cursor: str | None,
    access_decision: Mapping[str, Any] | None,
) -> PublicRecordsQuery:
    query_metadata: dict[str, Any] = {
        "county_geoid": COUNTY_GEOID,
        "experience_item_id": EXPERIENCE_ID,
        "native_row_identity": component.object_id_field,
        "complete_order_tuple": [component.object_id_field],
    }
    if access_decision is not None:
        query_metadata["access_decision"] = dict(access_decision)
    return PublicRecordsQuery(
        source=SOURCE_METADATA[component.source_id],
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
            metadata=query_metadata,
        ),
    )


def _warnings(component: SAILComponent) -> tuple[str, ...]:
    warnings: list[str] = []
    if component.publisher_note:
        warnings.append(component.publisher_note)
    if component.source_id == TAX_PARCEL_SOURCE_ID:
        warnings.append(
            "SAIL tax parcels and Portland/Metro regional taxlots can share "
            "county upstream lineage; overlapping rows are representations."
        )
    return tuple(warnings)


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
        log_search(canonical_json(query.to_dict()), query.source.source_id, count)
    except Exception as error:
        print(f"Warning: search log was not updated: {error}", file=sys.stderr)


def _selection_failure(
    query: PublicRecordsQuery,
    error: SourceSelectionError,
    *,
    warnings: Sequence[str],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=warnings,
    )


def _normalization_failure(
    query: PublicRecordsQuery,
    error: Exception,
    *,
    code: str,
    warnings: Sequence[str],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.SOURCE_CHANGED,
        [
            PublicRecordsError(
                code=code,
                message=str(error),
                category="source_schema",
                retryable=False,
            )
        ],
        warnings=warnings,
    )


class _ValidatedLayerClient:
    """Cache and validate component metadata before shared keyset access."""

    def __init__(
        self,
        client: Any,
        component: SAILComponent,
    ) -> None:
        self.client = client
        self.component = component
        self.page_size = client.page_size
        self._metadata: Mapping[str, Any] | None = None

    def fetch_metadata(self) -> Mapping[str, Any]:
        if self._metadata is None:
            metadata = self.client.fetch_metadata()
            observed_geometry = metadata.get("geometryType")
            if observed_geometry != self.component.geometry_type:
                raise SourceSchemaError(
                    "SAIL component geometry type changed",
                    url=self.component.layer_url,
                    details={
                        "expected": self.component.geometry_type,
                        "observed": observed_geometry,
                    },
                )
            self._metadata = metadata
        return self._metadata

    def fetch_count(self, where: str) -> int:
        return self.client.fetch_count(where)

    def fetch_page(self, **kwargs: Any) -> tuple[Mapping[str, Any], ...]:
        return self.client.fetch_page(**kwargs)


def _layer_client(
    active_client: Any,
    component: SAILComponent,
) -> _ValidatedLayerClient:
    candidate = active_client
    if isinstance(candidate, Mapping):
        candidate = candidate.get(component.source_id)
    if candidate is None:
        raise SourceSelectionError(
            "missing_client",
            f"no client was supplied for {component.source_id}",
        )
    if hasattr(candidate, "layer_client"):
        candidate = candidate.layer_client(component)
    return _ValidatedLayerClient(candidate, component)


def _document_client(active_client: Any, component: SAILComponent) -> Any:
    candidate = active_client
    if isinstance(candidate, Mapping):
        candidate = candidate.get(component.source_id) or candidate.get(
            "documents"
        )
    if candidate is None or not hasattr(candidate, "fetch_image_viewer"):
        raise SourceSelectionError(
            "missing_document_client",
            f"no image-viewer client was supplied for {component.source_id}",
        )
    return candidate


def _snapshot_record(
    batch: arcgis_shared.ArcGISBatch,
    *,
    returned_count: int,
    component: SAILComponent,
) -> dict[str, Any]:
    return {
        "ordering": f"{component.object_id_field} ASC",
        "complete_sort_tuple": [component.object_id_field],
        "total_matching_records_at_retrieval": batch.total_count,
        "records_inside_cursor_boundary": batch.bounded_count,
        "boundary_object_id": batch.boundary_object_id,
        "last_object_id": batch.last_object_id,
        "window_returned_records": returned_count,
        "continuation_available": batch.next_cursor is not None,
        "pages_fetched": batch.pages_fetched,
        "schema_fingerprint": batch.schema_fingerprint,
        "count_changed_inside_boundary_since_cursor": (
            batch.count_changed_since_cursor
        ),
    }


def _query_result(
    args: argparse.Namespace,
    *,
    active_client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> PublicRecordsResult:
    component = COMPONENTS[args.source]
    operation = args.command
    query_value = str(args.query)
    field = "object-id" if operation == "record" else args.field
    match = "exact" if operation == "record" else args.match
    limit = 2 if operation == "record" else args.limit
    fetch_limit = limit if limit is not None else sys.maxsize
    cursor = None if operation == "record" else args.cursor
    query = _build_query(
        component,
        operation=operation,
        parameters={
            "selector": query_value,
            "field": field,
            "match": match,
            "geometry": args.geometry,
        },
        requested_limit=limit,
        cursor=cursor,
        access_decision=access_decision,
    )
    warnings = _warnings(component)
    try:
        where, selected_match = build_where(
            component,
            query_value,
            field=field,
            match=match,
        )
        layer_client = _layer_client(active_client, component)
        batch = arcgis_shared.fetch_batch(
            layer_client,
            component.manifest,
            adapter_slug=f"multnomah-sail-{component.key}",
            operation=operation,
            where=where,
            limit=fetch_limit,
            cursor=cursor,
            return_geometry=args.geometry,
        )
        records = [
            normalize_feature(
                component,
                feature,
                schema_fingerprint=batch.schema_fingerprint,
                geometry_requested=args.geometry,
            )
            for feature in batch.features
        ]
        if operation == "record" and len(records) > 1:
            raise SourceSchemaError(
                "SAIL object-ID query returned multiple rows",
                url=component.layer_url,
                details={
                    "object_id": query_value,
                    "returned_records": len(records),
                },
            )
        snapshot = _snapshot_record(
            batch,
            returned_count=len(records),
            component=component,
        )
        snapshot["selected_match"] = selected_match
        for record in records:
            record["retrieval_snapshot"] = snapshot
        result = PublicRecordsResult.success(
            query,
            records,
            next_cursor=batch.next_cursor,
            warnings=warnings,
        )
    except SourceSelectionError as error:
        result = _selection_failure(query, error, warnings=warnings)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=warnings)
    except ValueError as error:
        result = _selection_failure(
            query,
            SourceSelectionError(
                "cursor_query_mismatch",
                str(error),
                status=ResultStatus.SOURCE_CHANGED,
            ),
            warnings=warnings,
        )
    except TypeError as error:
        result = _normalization_failure(
            query,
            error,
            code="normalization_failed",
            warnings=warnings,
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def _image_result(
    args: argparse.Namespace,
    *,
    active_client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> PublicRecordsResult:
    component = COMPONENTS[args.source]
    survey_id = _clean(args.query) or ""
    query = _build_query(
        component,
        operation="image",
        parameters={"survey_document_id": survey_id},
        requested_limit=1,
        cursor=None,
        access_decision=access_decision,
    )
    warnings = _warnings(component)
    try:
        document_client = _document_client(active_client, component)
        artifact = document_client.fetch_image_viewer(survey_id)
        parsed = parse_image_viewer(
            artifact.content.decode("utf-8", errors="replace"),
            survey_id=survey_id,
            source_url=artifact.source_url,
        )
        parsed.update(
            {
                "source_id": component.source_id,
                "viewer_sha256": artifact.sha256,
                "viewer_bytes": len(artifact.content),
                "viewer_content_type": artifact.content_type,
            }
        )
        records = [parsed] if parsed["representations"] else []
        result = PublicRecordsResult.success(
            query,
            records,
            raw_artifact_refs=[artifact.source_url],
            warnings=warnings,
        )
    except SourceSelectionError as error:
        result = _selection_failure(query, error, warnings=warnings)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=warnings)
    except (TypeError, ValueError) as error:
        result = _normalization_failure(
            query,
            error,
            code="image_viewer_parse_failed",
            warnings=warnings,
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def _write_atomic(destination: Path, content: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".part",
        dir=str(destination.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _download_result(
    args: argparse.Namespace,
    *,
    active_client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> PublicRecordsResult:
    component = COMPONENTS[args.source]
    survey_id = _clean(args.query) or ""
    query = _build_query(
        component,
        operation="download",
        parameters={
            "survey_document_id": survey_id,
            "representation_index": args.index,
            "destination": str(args.destination),
            "maximum_document_bytes": args.max_document_bytes,
        },
        requested_limit=1,
        cursor=None,
        access_decision=access_decision,
    )
    warnings = _warnings(component)
    try:
        if args.index < 1:
            raise SourceSelectionError(
                "invalid_representation_index",
                "representation index must be positive",
            )
        document_client = _document_client(active_client, component)
        viewer = document_client.fetch_image_viewer(survey_id)
        parsed = parse_image_viewer(
            viewer.content.decode("utf-8", errors="replace"),
            survey_id=survey_id,
            source_url=viewer.source_url,
        )
        links = parsed["representations"]
        if not links:
            result = PublicRecordsResult.success(
                query,
                [],
                raw_artifact_refs=[viewer.source_url],
                warnings=warnings,
            )
        else:
            if args.index > len(links):
                raise SourceSelectionError(
                    "representation_index_out_of_range",
                    "representation index exceeds the viewer result count",
                    details={
                        "requested_index": args.index,
                        "available_count": len(links),
                    },
                )
            representation = links[args.index - 1]
            pdf = document_client.fetch_pdf(
                representation["pdf_url"],
                maximum_bytes=args.max_document_bytes,
            )
            destination = Path(args.destination).expanduser().resolve()
            _write_atomic(destination, pdf.content)
            record = {
                "record_kind": "sail_document_artifact",
                "source_id": component.source_id,
                "survey_document_id": survey_id,
                "representation_index": args.index,
                "viewer_url": viewer.source_url,
                "document_url": pdf.source_url,
                "destination": str(destination),
                "filename": unquote(Path(urlparse(pdf.source_url).path).name),
                "content_type": pdf.content_type,
                "bytes": len(pdf.content),
                "sha256": pdf.sha256,
                "viewer_sha256": viewer.sha256,
                "viewer_schema_fingerprint": parsed[
                    "viewer_schema_fingerprint"
                ],
            }
            result = PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=[viewer.source_url, pdf.source_url],
                warnings=warnings,
            )
    except SourceSelectionError as error:
        result = _selection_failure(query, error, warnings=warnings)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=warnings)
    except (OSError, TypeError, ValueError) as error:
        result = _normalization_failure(
            query,
            error,
            code="document_write_failed",
            warnings=warnings,
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def _probe_where(component: SAILComponent) -> str:
    if component.source_id == SURVEY_SOURCE_ID:
        return f"SURVEYID = '{KNOWN_SURVEY_ID}'"
    if component.source_id == TAX_PARCEL_SOURCE_ID:
        return f"PROPID = '{KNOWN_TAX_PROPERTY_ID}'"
    return f"{component.object_id_field} = 1"


def _component_probe(
    args: argparse.Namespace,
    component: SAILComponent,
    *,
    active_client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> PublicRecordsResult:
    query = _build_query(
        component,
        operation="probe",
        parameters={
            "sentinel_where": _probe_where(component),
            "resolve_image": (
                args.resolve_image and component.source_id == SURVEY_SOURCE_ID
            ),
        },
        requested_limit=1,
        cursor=None,
        access_decision=access_decision,
    )
    warnings = _warnings(component)
    try:
        layer_client = _layer_client(active_client, component)
        metadata = layer_client.fetch_metadata()
        schema_value, maximum = arcgis_shared.metadata_contract(
            component.manifest,
            metadata,
        )
        count = layer_client.fetch_count("1=1")
        features = layer_client.fetch_page(
            where=_probe_where(component),
            record_count=1,
            return_geometry=True,
        )
        if not features:
            raise SourceSchemaError(
                "SAIL probe sentinel no longer resolves",
                url=component.layer_url,
                details={"sentinel_where": _probe_where(component)},
            )
        sentinel = normalize_feature(
            component,
            features[0],
            schema_fingerprint=schema_value,
            geometry_requested=True,
        )
        image_resolution = None
        if args.resolve_image and component.source_id == SURVEY_SOURCE_ID:
            document_client = _document_client(active_client, component)
            viewer = document_client.fetch_image_viewer(KNOWN_SURVEY_ID)
            image_resolution = parse_image_viewer(
                viewer.content.decode("utf-8", errors="replace"),
                survey_id=KNOWN_SURVEY_ID,
                source_url=viewer.source_url,
            )
            if not image_resolution["representations"]:
                raise SourceSchemaError(
                    "SAIL survey sentinel image no longer resolves",
                    url=viewer.source_url,
                )
            image_resolution.update(
                {
                    "viewer_sha256": viewer.sha256,
                    "viewer_bytes": len(viewer.content),
                }
            )
        record = {
            "record_kind": "source_probe",
            "source_id": component.source_id,
            "component_total_count": count,
            "observed_count_reference": component.observed_count,
            "schema_fingerprint": schema_value,
            "layer_name": metadata.get("name"),
            "layer_id": metadata.get("id"),
            "service_item_id": metadata.get("serviceItemId"),
            "geometry_type": metadata.get("geometryType"),
            "native_crs": component.source_crs_label,
            "max_record_count": maximum,
            "ordering": f"{component.object_id_field} ASC",
            "complete_sort_tuple": [component.object_id_field],
            "sentinel": sentinel,
            "image_resolution": image_resolution,
        }
        result = PublicRecordsResult.success(
            query,
            [record],
            warnings=warnings,
        )
    except SourceSelectionError as error:
        result = _selection_failure(query, error, warnings=warnings)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=warnings)
    except (TypeError, ValueError) as error:
        result = _normalization_failure(
            query,
            error,
            code="probe_failed",
            warnings=warnings,
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def _all_probe_payload(
    args: argparse.Namespace,
    *,
    active_client: Any,
    access_decision: Mapping[str, Any] | None,
    log_results: bool,
) -> dict[str, Any]:
    components = [
        _component_probe(
            args,
            COMPONENTS[source_id],
            active_client=active_client,
            access_decision=access_decision,
            log_results=log_results,
        ).to_dict()
        for source_id in SOURCE_IDS
    ]
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
        "successful_components": successful,
        "component_count": len(components),
        "components": components,
    }


def _source_result(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None,
) -> PublicRecordsResult:
    component = COMPONENTS[args.source]
    query = _build_query(
        component,
        operation="source",
        parameters={"source_id": component.source_id},
        requested_limit=1,
        cursor=None,
        access_decision=access_decision,
    )
    return PublicRecordsResult.success(query, [_source_record(component)])


def _new_client(args: argparse.Namespace) -> MultnomahSAILClient:
    return MultnomahSAILClient(
        page_size=args.page_size,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: Any = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute source discovery, ArcGIS queries, document access, or probes."""

    if args.command == "sources":
        return source_manifest()
    if args.command == "source":
        return _source_result(args, access_decision=access_decision)
    active_client = client or _new_client(args)
    owns_client = client is None
    try:
        if args.command in {"search", "record"}:
            return _query_result(
                args,
                active_client=active_client,
                access_decision=access_decision,
                log_results=log_results,
            )
        if args.command == "image":
            return _image_result(
                args,
                active_client=active_client,
                access_decision=access_decision,
                log_results=log_results,
            )
        if args.command == "download":
            return _download_result(
                args,
                active_client=active_client,
                access_decision=access_decision,
                log_results=log_results,
            )
        if args.command == "probe":
            if args.all_sources:
                return _all_probe_payload(
                    args,
                    active_client=active_client,
                    access_decision=access_decision,
                    log_results=log_results,
                )
            return _component_probe(
                args,
                COMPONENTS[args.source],
                active_client=active_client,
                access_decision=access_decision,
                log_results=log_results,
            )
        raise ValueError(f"unsupported command {args.command!r}")
    finally:
        if owns_client:
            active_client.close()


def _payload(
    value: PublicRecordsResult | Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(value, PublicRecordsResult):
        return value.to_dict()
    return dict(value)


def _emit(
    value: PublicRecordsResult | Mapping[str, Any],
    args: argparse.Namespace,
) -> None:
    payload = _payload(value)
    if isinstance(payload.get("records"), list):
        result_count = len(payload["records"])
    elif isinstance(payload.get("components"), list):
        result_count = len(payload["components"])
    else:
        result_count = len(payload.get("sources", []))
    if write_output(
        payload,
        args,
        summary=f"Multnomah SAIL {args.command}",
        result_count=result_count,
    ):
        return
    if getattr(args, "json_out", False):
        return
    if args.command == "sources":
        print(f"Multnomah County SAIL components: {len(payload['sources'])}")
        for source in payload["sources"]:
            print(
                f"  {source['source_id']} | "
                f"{source['record_kind']} | "
                f"{source['observed_contract']['component_count']:,}"
            )
        print(
            "Complementary sources: "
            f"{len(payload['complementary_sources'])}"
        )
        return
    if args.command == "probe" and getattr(args, "all_sources", False):
        print(
            f"Multnomah SAIL probe: {payload['status']} "
            f"({payload['successful_components']}/"
            f"{payload['component_count']} components)"
        )
        return
    print(f"Status: {payload.get('status')}")
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in payload.get("records", []):
        identity = (
            record.get("survey_document_id")
            or record.get("property_id")
            or record.get("object_id")
            or record.get("source_id")
        )
        print(f"  {identity} | {record.get('record_kind')}")
        if record.get("destination"):
            print(f"    saved: {record['destination']}")
    for error in payload.get("errors", []):
        print(
            f"ERROR [{error.get('code')}]: {error.get('message')}",
            file=sys.stderr,
        )


def _add_transport_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=DEFAULT_RETRY_ATTEMPTS,
    )
    add_output_args(parser)


def _add_source_argument(
    parser: argparse.ArgumentParser,
    *,
    image_only: bool = False,
) -> None:
    parser.add_argument(
        "--source",
        required=True,
        choices=IMAGE_SOURCE_IDS if image_only else SOURCE_IDS,
        help="Exact component-scoped source ID",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Multnomah County SAIL tax parcels, surveys, plats, "
            "corners, field books, and source PDFs"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="List all component contracts and complementary sources",
    )
    add_output_args(sources)

    source = subparsers.add_parser(
        "source",
        help="Show one component contract",
    )
    _add_source_argument(source)
    add_output_args(source)

    search = subparsers.add_parser(
        "search",
        help="Search one selected ArcGIS component",
    )
    search.add_argument("query")
    _add_source_argument(search)
    search.add_argument("--field", choices=SEARCH_FIELDS, default="auto")
    search.add_argument(
        "--match",
        choices=("auto", "exact", "contains"),
        default="auto",
    )
    search.add_argument(
        "--limit",
        type=int,
        help="Return at most this many records; omitted traverses all matches",
    )
    search.add_argument(
        "--cursor",
        help="Continuation from the same component, query, and geometry mode",
    )
    search.add_argument(
        "--geometry",
        action="store_true",
        help="Include WGS84 geometry and native-CRS provenance",
    )
    _add_transport_arguments(search)

    record = subparsers.add_parser(
        "record",
        help="Fetch one source-native row by unique object ID",
    )
    record.add_argument("query")
    _add_source_argument(record)
    record.add_argument("--geometry", action="store_true")
    record.set_defaults(field="object-id", match="exact", limit=2, cursor=None)
    _add_transport_arguments(record)

    image = subparsers.add_parser(
        "image",
        help="Resolve a SURVEYID through the official image viewer",
    )
    image.add_argument("query")
    _add_source_argument(image, image_only=True)
    _add_transport_arguments(image)

    download = subparsers.add_parser(
        "download",
        help="Resolve and atomically save one official PDF representation",
    )
    download.add_argument("query")
    _add_source_argument(download, image_only=True)
    download.add_argument("--destination", required=True)
    download.add_argument("--index", type=int, default=1)
    download.add_argument(
        "--max-document-bytes",
        type=int,
        default=DEFAULT_MAXIMUM_DOCUMENT_BYTES,
    )
    _add_transport_arguments(download)

    probe = subparsers.add_parser(
        "probe",
        help="Run bounded metadata, count, sentinel, and resolver checks",
    )
    selection = probe.add_mutually_exclusive_group(required=True)
    selection.add_argument("--source", choices=SOURCE_IDS)
    selection.add_argument("--all", dest="all_sources", action="store_true")
    probe.set_defaults(all_sources=False)
    probe.add_argument(
        "--resolve-image",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Resolve the known survey image while probing the survey component",
    )
    _add_transport_arguments(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    limit = getattr(args, "limit", None)
    if limit is not None and limit < 1:
        parser.error("--limit must be positive")
    if getattr(args, "page_size", 1) < 1:
        parser.error("--page-size must be positive")
    if getattr(args, "timeout", 1) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    if getattr(args, "retry_attempts", 1) < 1:
        parser.error("--retry-attempts must be positive")
    if getattr(args, "max_document_bytes", 1) < 1:
        parser.error("--max-document-bytes must be positive")
    if getattr(args, "index", 1) < 1:
        parser.error("--index must be positive")
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
