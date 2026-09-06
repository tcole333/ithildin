#!/usr/bin/env python3
"""Discover, transfer, inspect, and search Marion County public downloads.

Marion County publishes two related but separately attributable assessor
datasets from one official Reports & Data page:

* weekly current-year and historical sales artifacts reaching 1940; and
* a replaceable comprehensive assessment ZIP published around monthly.

The adapter keeps a publication slot (for example ``sales-2026``) separate
from each downloaded occurrence of that slot.  ZIP member occurrences and row
occurrences are then bound to the downloaded artifact digest.  A semantic sale
identity and parcel/account join keys remain separate from all three.

Examples:
    uv run python tools/query_oregon_marion_downloads.py manifest --json
    uv run python tools/query_oregon_marion_downloads.py probe \
        --source us-or-marion-sales-data --json
    uv run python tools/query_oregon_marion_downloads.py download \
        --source us-or-marion-comprehensive-assessment-download \
        --destination /tmp/marion-comprehensive.zip --inspect \
        --output /tmp/marion-download.json
    uv run python tools/query_oregon_marion_downloads.py search "032W29" \
        --source us-or-marion-comprehensive-assessment-download \
        --field parcel --output /tmp/marion-assessment.json
    uv run python tools/query_oregon_marion_downloads.py search "2026-480" \
        --source us-or-marion-sales-data --field instrument \
        --output /tmp/marion-sales.json
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import re
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, BinaryIO, Callable, Iterator, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_bulk import (
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
        DownloadResult,
        file_sha256,
        inspect_zip,
    )
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
    from tools.public_records_store import canonical_property_ref
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_bulk import (
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
        DownloadResult,
        file_sha256,
        inspect_zip,
    )
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
    from public_records_store import canonical_property_ref


SALES_SOURCE_ID = "us-or-marion-sales-data"
ASSESSMENT_SOURCE_ID = (
    "us-or-marion-comprehensive-assessment-download"
)
SOURCE_IDS = (SALES_SOURCE_ID, ASSESSMENT_SOURCE_ID)

STATE_CODE = "OR"
STATE_FIPS = "41"
COUNTY_GEOID = "41047"
COUNTY_NAME = "Marion County, Oregon"

LANDING_URL = "https://www.co.marion.or.us/AO/Pages/datacenter.aspx"
COMPREHENSIVE_URL = (
    "https://apps.co.marion.or.us/AO/ComprehensiveDownload/"
    "ComprehensiveDownload.zip"
)
MARION_PARCELS_SOURCE_ID = "us-or-marion-county-assessor-parcels"
MARION_PROPERTY_RECORDS_SOURCE_ID = "us-or-marion-property-records"
MARION_DATA_REQUEST_SOURCE_ID = "us-or-marion-assessor-data-request"
MARION_CLERK_RECORDS_URL = (
    "https://www.co.marion.or.us/CO/Pages/Records.aspx"
)
MARION_RECORDED_DOCUMENTS_URL = (
    "https://lrmw-marioncountygcc.msappproxy.net/"
    "DigitalResearchRoomPublic/"
)
MARION_HISTORICAL_DEEDS_URL = (
    "https://apps.co.marion.or.us/DeedSearch/Disclaimer.aspx"
)

OUTPUT_SCHEMA_VERSION = "oregon-marion-public-downloads/1.0"
MANIFEST_SCHEMA_VERSION = "oregon-marion-download-manifest/1.0"
PROBE_SCHEMA_VERSION = "oregon-marion-download-probe/1.0"
CURSOR_PREFIX = "oregon-marion-downloads:v1:"
CURSOR_VERSION = 1

DEFAULT_TIMEOUT = 60.0
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_CHUNK_SIZE = 1024 * 1024
DEFAULT_SAMPLE_BYTES = 4096
DEFAULT_CACHE_DIR = (
    Path(tempfile.gettempdir()) / "ithildin-oregon-marion-downloads"
)
CSV_FIELD_SIZE_LIMIT = 16 * 1024 * 1024

COMPREHENSIVE_PRIMARY_MEMBER = "ORCATS999_(NEW).csv"
COMPREHENSIVE_DATA_MEMBERS = (
    COMPREHENSIVE_PRIMARY_MEMBER,
    "ORCATS_Improvement.csv",
    "ORCATS_Improvement_Floors.csv",
    "ORCATS_Inventory.csv",
    "ORCATS_Land_Fragments.csv",
)
COMPREHENSIVE_REQUIRED_PRIMARY_FIELDS = (
    "TYYYY",
    "RDATE",
    "TXID",
    "ACCOUNT_ID",
    "TXCD",
    "PCLS",
    "PCLSD",
    "AV",
    "RMVLAND",
    "RMVIMPR",
    "SITUSSTR",
    "SITUSCITY",
    "SITUSZIP",
    "BOOKPG",
    "SALEPR",
    "SALE_GRANTEE",
    "SALE_GRANTOR",
)
COMPREHENSIVE_OWNER_COLUMNS_OMITTED_SINCE_2015 = (
    "OWNER_NAME",
    "OWNERNAME",
    "OWNER_MAILING_ADDRESS",
    "OWNER_ADDRESS",
)

SALES_V3_RAW_HEADER = (
    "Sale ID",
    "Ratio Year",
    "Roll Type: (R) Real / (MS) Manufactured Structure",
    "Number of Accounts Included in Sale",
    "Deed, Reel & Page Number",
    "Deed Instrument Number",
    (
        "Personal Property Manufactured Structre Instrument Source "
        "(Blank/Null for Real Property)"
    ),
    "Document Type Code",
    "Deed Type Code Description",
    "Primary Account Flag (1 indicates primary)",
    "Account Number",
    "Account Number for Manufactured Structure",
    "Map Taxlot",
    "Maintenance Area, Study Area, Neighborhood",
    "Property Class",
    "Property Class Description",
    "RMV Property Class",
    "RMV Property Class Description",
    "Primary Statistical Classification",
    "Primary Statistical Classification Description",
    "Code Area for Fragment(s) (Land)",
    "Code Area for Improvement(s)",
    "Code Area for On Site Developement(s)",
    "Model of Manufactured Structure",
    "Brand of Manufactured Structure",
    "Subdivision, Lot & Block or Partition Plat",
    "Total Fragment (Land) Acres",
    "Total Fragment (Land) Sq.Ft.",
    "Sale Price",
    "Sale Date",
    "Condition Code",
    "Condition Code Description",
    "Year Built of Primary Improvement",
    "Square Footage of Primary Imp",
    "Bedrooms",
    "Bathrooms",
    "Half Bathrooms",
    "Situs Address",
    "Primary Situs Address Flag (1 indicates primary)",
    "Grantor (Seller) Name",
    "Grantor (Seller) Address",
    "Grantee (Buyer) Name",
    "Grantee (Buyer) Address",
)
SALES_V3_COLUMNS = (
    "sale_id",
    "ratio_year",
    "roll_type",
    "number_of_accounts",
    "deed_reel_page",
    "instrument_number",
    "instrument_source",
    "document_type_code",
    "document_type_description",
    "primary_account_flag",
    "account_number",
    "manufactured_structure_account_number",
    "map_taxlot",
    "maintenance_study_neighborhood",
    "property_class",
    "property_class_description",
    "rmv_property_class",
    "rmv_property_class_description",
    "statistical_classification",
    "statistical_classification_description",
    "land_code_area",
    "improvement_code_area",
    "onsite_development_code_area",
    "manufactured_structure_model",
    "manufactured_structure_brand",
    "subdivision_lot_block_or_partition",
    "land_acres",
    "land_square_feet",
    "sale_price",
    "sale_date",
    "condition_code",
    "condition_description",
    "year_built",
    "building_square_feet",
    "bedrooms",
    "bathrooms",
    "half_bathrooms",
    "situs_address",
    "primary_situs_flag",
    "grantor_name",
    "grantor_address",
    "grantee_name",
    "grantee_address",
)

SALES_V2_RAW_HEADER = (
    "RATIO_YEAR",
    "DEED_REEL_PAGE",
    "SOURCE",
    "DOCUMENT_TYPE_CODE",
    "DOCUMENT_DESC",
    "INST_ID",
    "NUM_ACCOUNTS",
    "PRIMARY_ACCOUNT_FLAG",
    "ACCOUNT_ID",
    "MS_ACCOUNT_ID",
    "MTL",
    "MaSaNh",
    "PROPERTY_CLASS",
    "PROPERTY_CLASS_DESCRIPTION",
    "RMV_PROPERTY_CLASS",
    "RMV_PROPERTY_CLASS_DESCRIPTION",
    "PRIMARY_STATISTICAL_CLASSIFICATION",
    "DESCRIPTION",
    "MS_MODEL",
    "MS_BRAND",
    "SUBDIVISION_LOT_BLOCK or PART_PLAT",
    "TOTAL_FRAGMENT_ACRES",
    "TOTAL_FRAGMENT_SQFT",
    "SALE_PRICE",
    "SALE_DATE",
    "CONDITION_CODE",
    "CONDITION_CODE_DESCRIPTION",
    "YEAR_BUILT",
    "LIVABLE_AREA",
    "BEDROOMS",
    "BATHS",
    "HALF_BATHS",
    "SITUS_ADDRESS",
    "GRANTOR_NAME",
    "GRANTOR_ADDRESS",
    "GRANTEE_NAME",
    "GRANTEE_ADDRESS",
)
SALES_V2_COLUMNS = (
    "ratio_year",
    "deed_reel_page",
    "instrument_source",
    "document_type_code",
    "document_type_description",
    "instrument_number",
    "number_of_accounts",
    "primary_account_flag",
    "account_number",
    "manufactured_structure_account_number",
    "map_taxlot",
    "maintenance_study_neighborhood",
    "property_class",
    "property_class_description",
    "rmv_property_class",
    "rmv_property_class_description",
    "statistical_classification",
    "statistical_classification_description",
    "manufactured_structure_model",
    "manufactured_structure_brand",
    "subdivision_lot_block_or_partition",
    "land_acres",
    "land_square_feet",
    "sale_price",
    "sale_date",
    "condition_code",
    "condition_description",
    "year_built",
    "building_square_feet",
    "bedrooms",
    "bathrooms",
    "half_bathrooms",
    "situs_address",
    "grantor_name",
    "grantor_address",
    "grantee_name",
    "grantee_address",
)

SALES_V1_RAW_HEADER = (
    "RATIO_YEAR",
    "SALE_DATE",
    "DEED_REEL_PAGE",
    "SOURCE",
    "DOCUMENT_TYPE_CODE",
    "DOCUMENT_DESC",
    "INST_ID",
    "NUM_ACCOUNTS",
    "PRIMARY_ACCOUNT_FLAG",
    "ACCOUNT_ID",
    "MS_ACCOUNT_ID",
    "MTL",
    "MaSaNh",
    "PROPERTY_CLASS",
    "PROPERTY_CLASS_DESCRIPTION",
    "RMV_PROPERTY_CLASS",
    "RMV_PROPERTY_CLASS_DESCRIPTION",
    "PRIMARY_STATISTICAL_CLASSIFICATION",
    "DESCRIPTION",
    "MS_MODEL",
    "MS_BRAND",
    "SUBDIVISION_LOT_BLOCK or PART_PLAT",
    "TOTAL_FRAGMENT_ACRES",
    "TOTAL_FRAGMENT_SQFT",
    "SALE_PRICE",
    "SALE_DATE",
    "CONDITION_CODE",
    "DESCRIPTION",
    "YEAR_BUILT",
    "LIVABLE_AREA",
    "BEDROOMS",
    "BATHS",
    "HALF_BATHS",
    "SITUS_ADDRESS",
    "GRANTOR_NAME",
    "GRANTOR_ADDRESS",
    "GRANTEE_NAME",
    "GRANTEE_ADDRESS",
)
SALES_V1_COLUMNS = (
    "ratio_year",
    "legacy_leading_sale_date",
    "deed_reel_page",
    "instrument_source",
    "document_type_code",
    "document_type_description",
    "instrument_number",
    "number_of_accounts",
    "primary_account_flag",
    "account_number",
    "manufactured_structure_account_number",
    "map_taxlot",
    "maintenance_study_neighborhood",
    "property_class",
    "property_class_description",
    "rmv_property_class",
    "rmv_property_class_description",
    "statistical_classification",
    "statistical_classification_description",
    "manufactured_structure_model",
    "manufactured_structure_brand",
    "subdivision_lot_block_or_partition",
    "land_acres",
    "land_square_feet",
    "sale_price",
    "sale_date",
    "condition_code",
    "condition_description",
    "year_built",
    "building_square_feet",
    "bedrooms",
    "bathrooms",
    "half_bathrooms",
    "situs_address",
    "grantor_name",
    "grantor_address",
    "grantee_name",
    "grantee_address",
)

SALES_SCHEMA_PROFILES = {
    "sales_csv_descriptive_v3": {
        "raw_header": SALES_V3_RAW_HEADER,
        "canonical_columns": SALES_V3_COLUMNS,
        "row_search_supported": True,
        "coverage": "2022_and_later",
        "duplicate_header_positions": [],
    },
    "sales_csv_abbreviated_v2": {
        "raw_header": SALES_V2_RAW_HEADER,
        "canonical_columns": SALES_V2_COLUMNS,
        "row_search_supported": True,
        "coverage": "2021",
        "duplicate_header_positions": [],
    },
    "sales_csv_duplicate_header_v1": {
        "raw_header": SALES_V1_RAW_HEADER,
        "canonical_columns": SALES_V1_COLUMNS,
        "row_search_supported": True,
        "coverage": "2020",
        "duplicate_header_positions": [
            {
                "raw_name": "SALE_DATE",
                "zero_based_positions": [1, 25],
                "canonical_names": [
                    "legacy_leading_sale_date",
                    "sale_date",
                ],
            },
            {
                "raw_name": "DESCRIPTION",
                "zero_based_positions": [18, 27],
                "canonical_names": [
                    "statistical_classification_description",
                    "condition_description",
                ],
            },
        ],
    },
    "sales_workbook_archive_legacy": {
        "raw_header": (),
        "canonical_columns": (),
        "row_search_supported": False,
        "coverage": "1980_through_2019",
        "duplicate_header_positions": [],
        "reason": (
            "The official decade ZIPs contain per-year XLS/XLSB workbooks. "
            "The artifact and member manifests are supported; row search is "
            "not claimed without an explicit workbook conversion."
        ),
    },
    "sales_workbook_legacy": {
        "raw_header": (),
        "canonical_columns": (),
        "row_search_supported": False,
        "coverage": "1940_through_1979",
        "duplicate_header_positions": [],
        "reason": (
            "The official decade artifact is an XLS workbook. Artifact "
            "inspection is supported; row search is not claimed without an "
            "explicit workbook conversion."
        ),
    },
}

SOURCE_WARNINGS = {
    SALES_SOURCE_ID: (
        "The current-year sales URL is a replaceable weekly publication slot. "
        "Preserve its validator or downloaded digest as the release occurrence.",
        "Sale parties and deed numbers are assessor sale-index fields. They do "
        "not establish current ownership, title, or the contents of a recorded "
        "instrument.",
        "Historical workbook formats expose per-artifact capabilities. An XLS "
        "or XLSB member that is not row-searchable does not make the source "
        "manifest unavailable.",
    ),
    ASSESSMENT_SOURCE_ID: (
        "The comprehensive ZIP is a replaceable assessment snapshot. Preserve "
        "the RDATE value, artifact digest, member identity, and row occurrence.",
        "Marion County states that owner names and mailing addresses have been "
        "omitted from this download since February 1, 2015.",
        "SALE_GRANTOR and SALE_GRANTEE are assessor latest-sale labels. They "
        "are not projected as current ownership or title evidence.",
    ),
}


def _source_metadata(source_id: str) -> SourceMetadata:
    if source_id == SALES_SOURCE_ID:
        return SourceMetadata(
            source_id=source_id,
            name="Marion County Assessor Sales Data",
            source_role="county_assessor_sale_history_bulk",
            base_url=LANDING_URL,
            dataset_id="marion-assessor-sales",
            metadata={
                "authority": "Marion County Assessor's Office",
                "coverage_start": 1940,
                "current_publication_cadence": "weekly",
                "release_discovery": "official Reports & Data page",
            },
        )
    if source_id == ASSESSMENT_SOURCE_ID:
        return SourceMetadata(
            source_id=source_id,
            name="Marion County Comprehensive Assessment Download",
            source_role="county_assessment_snapshot_bulk",
            base_url=LANDING_URL,
            dataset_id="marion-comprehensive-assessment",
            metadata={
                "authority": "Marion County Assessor's Office",
                "publication_cadence": (
                    "around_monthly_except_October_roll_certification"
                ),
                "release_vintage_field": "ORCATS999_(NEW).csv:RDATE",
                "owner_name_and_mailing_omitted_since": "2015-02-01",
            },
        )
    raise ValueError(f"unknown Marion download source: {source_id}")


JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    county_fips="047",
    metadata={"state_fips": STATE_FIPS},
)


class MarionDownloadError(RuntimeError):
    """Structured source, artifact, or selector failure."""

    status = ResultStatus.SOURCE_CHANGED
    code = "marion_download_source_changed"
    category = "source_schema"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
        status: ResultStatus | None = None,
        code: str | None = None,
        category: str | None = None,
    ) -> None:
        super().__init__(message)
        self.details = dict(details or {})
        if status is not None:
            self.status = status
        if code is not None:
            self.code = code
        if category is not None:
            self.category = category

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


class ManifestTransportError(MarionDownloadError):
    status = ResultStatus.UNAVAILABLE
    code = "marion_download_manifest_unavailable"
    category = "transport"
    retryable = True


class CursorError(MarionDownloadError):
    code = "marion_download_cursor_invalid"
    category = "cursor"


@dataclass(frozen=True)
class Release:
    """One publisher-visible artifact slot from the official page."""

    source_id: str
    release_id: str
    label: str
    url: str
    coverage_start: int | None
    coverage_end: int | None
    publication_kind: str
    format: str
    schema_profile: str

    @property
    def filename(self) -> str:
        return Path(unquote(urlsplit(self.url).path)).name

    @property
    def row_search_supported(self) -> bool:
        if self.source_id == ASSESSMENT_SOURCE_ID:
            return True
        profile = SALES_SCHEMA_PROFILES[self.schema_profile]
        return bool(profile["row_search_supported"])

    @property
    def capability(self) -> dict[str, Any]:
        return {
            "artifact_manifest": True,
            "resumable_validated_transfer": True,
            "local_artifact_inspection": True,
            "local_row_search": self.row_search_supported,
            "schema_profile": self.schema_profile,
            "unsupported_reason": (
                None
                if self.row_search_supported
                else SALES_SCHEMA_PROFILES[self.schema_profile].get("reason")
            ),
        }

    @property
    def release_slot_identity(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "release_id": self.release_id,
            "artifact_url": self.url,
            "meaning": (
                "publisher_visible_slot_not_a_downloaded_occurrence"
            ),
        }

    def artifact(self) -> BulkArtifact:
        media_types = {
            "csv": "application/octet-stream",
            "zip": "application/x-zip-compressed",
            "xls": "application/vnd.ms-excel",
        }
        return BulkArtifact.from_url(
            f"{self.release_id}-artifact",
            self.url,
            media_type=media_types[self.format],
            archive_format="zip" if self.format == "zip" else None,
            metadata={
                "release_id": self.release_id,
                "source_id": self.source_id,
                "schema_profile": self.schema_profile,
                "publication_kind": self.publication_kind,
                "capability": self.capability,
            },
        )

    def manifest_record(
        self,
        snapshot: "ManifestSnapshot",
    ) -> dict[str, Any]:
        schema = (
            {
                "schema_profile": self.schema_profile,
                **SALES_SCHEMA_PROFILES[self.schema_profile],
            }
            if self.source_id == SALES_SOURCE_ID
            else {
                "schema_profile": self.schema_profile,
                "primary_member": COMPREHENSIVE_PRIMARY_MEMBER,
                "required_data_members": list(COMPREHENSIVE_DATA_MEMBERS),
                "required_primary_fields": list(
                    COMPREHENSIVE_REQUIRED_PRIMARY_FIELDS
                ),
                "release_vintage_field": "RDATE",
                "owner_name_and_mailing_omitted_since": "2015-02-01",
            }
        )
        manifest = BulkDatasetManifest(
            source_id=self.source_id,
            dataset_id=_source_metadata(self.source_id).dataset_id or self.source_id,
            release=BulkReleaseMetadata(
                release_id=self.release_id,
                kind="snapshot",
                coverage={
                    "calendar_year_start": self.coverage_start,
                    "calendar_year_end": self.coverage_end,
                    "publication_kind": self.publication_kind,
                    "replacement_semantics": (
                        "replaceable_publication_slot"
                        if self.publication_kind
                        in {"weekly_current_year", "monthly_current_snapshot"}
                        else "published_historical_artifact"
                    ),
                },
            ),
            artifacts=(self.artifact(),),
            schema=schema,
            metadata={
                "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
                "official_listing_url": LANDING_URL,
                "official_link_label": self.label,
                "release_set_fingerprint": snapshot.fingerprint,
                "release_slot_identity": self.release_slot_identity,
                "download_occurrence_identity": {
                    "pre_download": [
                        "artifact_url",
                        "etag",
                        "last_modified",
                        "content_length",
                    ],
                    "post_download": ["artifact_sha256"],
                    "interchangeable_with_release_slot": False,
                },
                "capability": self.capability,
            },
        )
        return {
            "canonical_ref": canonical_property_ref(
                self.source_id,
                COUNTY_GEOID,
                "bulk_release_slot",
                self.release_id,
            ),
            "source_id": self.source_id,
            "record_kind": "bulk_release_manifest",
            "release_id": self.release_id,
            "label": self.label,
            "url": self.url,
            "filename": self.filename,
            "format": self.format,
            "schema_profile": self.schema_profile,
            "release_slot_identity": self.release_slot_identity,
            "capability": self.capability,
            "manifest": manifest.to_dict(),
            "source_url": LANDING_URL,
        }


@dataclass(frozen=True)
class ManifestSnapshot:
    """Complete set of recognized publication links on one landing page."""

    releases: tuple[Release, ...]
    landing_sha256: str

    @property
    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "landing_url": LANDING_URL,
            "releases": [
                {
                    "source_id": release.source_id,
                    "release_id": release.release_id,
                    "url": release.url,
                    "schema_profile": release.schema_profile,
                    "capability": release.capability,
                }
                for release in self.releases
            ],
        }

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(self.fingerprint_payload)

    def by_source(self, source_id: str) -> tuple[Release, ...]:
        return tuple(
            release
            for release in self.releases
            if release.source_id == source_id
        )

    def by_id(self, release_id: str) -> Release | None:
        return next(
            (
                release
                for release in self.releases
                if release.release_id == release_id
            ),
            None,
        )


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "a":
            return
        self._href = dict(attrs).get("href")
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        label = " ".join("".join(self._text).split())
        self.links.append((self._href, label))
        self._href = None
        self._text = []


_CURRENT_SALES_RE = re.compile(
    r"(?P<year>20\d{2})SalesData\.csv$",
    re.I,
)
_ANNUAL_SALES_RE = re.compile(
    r"(?P<year>20\d{2})sales\.csv$",
    re.I,
)
_DECADE_ZIP_RE = re.compile(
    r"(?P<start>\d{4})-(?P<end>\d{4})sales\.zip$",
    re.I,
)
_DECADE_XLS_RE = re.compile(
    r"(?P<start>\d{4})(?P<end>\d{4})sales\.xls$",
    re.I,
)


def _sales_schema_profile(
    *,
    coverage_start: int,
    format: str,
) -> str:
    if format == "zip":
        return "sales_workbook_archive_legacy"
    if format == "xls":
        return "sales_workbook_legacy"
    if coverage_start >= 2022:
        return "sales_csv_descriptive_v3"
    if coverage_start == 2021:
        return "sales_csv_abbreviated_v2"
    if coverage_start == 2020:
        return "sales_csv_duplicate_header_v1"
    raise MarionDownloadError(
        "Recognized sales CSV falls outside known schema profiles",
        details={"coverage_start": coverage_start, "format": format},
    )


def parse_release_manifest(
    html_text: str,
    *,
    base_url: str = LANDING_URL,
) -> ManifestSnapshot:
    """Parse every recognized sales and comprehensive download link."""

    parser = _AnchorParser()
    parser.feed(html_text)
    releases: dict[tuple[str, str], Release] = {}
    for href, label in parser.links:
        absolute_url = urljoin(base_url, href)
        filename = Path(unquote(urlsplit(absolute_url).path)).name
        if filename.casefold() == "comprehensivedownload.zip":
            release = Release(
                source_id=ASSESSMENT_SOURCE_ID,
                release_id="comprehensive-current",
                label=label or filename,
                url=absolute_url,
                coverage_start=None,
                coverage_end=None,
                publication_kind="monthly_current_snapshot",
                format="zip",
                schema_profile="comprehensive_assessment_v1",
            )
        else:
            match = _CURRENT_SALES_RE.fullmatch(filename)
            publication_kind = "weekly_current_year"
            format = "csv"
            if match is None:
                match = _ANNUAL_SALES_RE.fullmatch(filename)
                publication_kind = "annual_csv"
            if match is not None:
                start = int(match.group("year"))
                end = start
            else:
                match = _DECADE_ZIP_RE.fullmatch(filename)
                publication_kind = "historical_decade_archive"
                format = "zip"
                if match is None:
                    match = _DECADE_XLS_RE.fullmatch(filename)
                    publication_kind = "historical_decade_workbook"
                    format = "xls"
                if match is None:
                    continue
                start = int(match.group("start"))
                end = int(match.group("end"))
            release = Release(
                source_id=SALES_SOURCE_ID,
                release_id=(
                    f"sales-{start}"
                    if start == end
                    else f"sales-{start}-{end}"
                ),
                label=label or filename,
                url=absolute_url,
                coverage_start=start,
                coverage_end=end,
                publication_kind=publication_kind,
                format=format,
                schema_profile=_sales_schema_profile(
                    coverage_start=start,
                    format=format,
                ),
            )
        key = (release.source_id, release.release_id)
        previous = releases.get(key)
        if previous is not None and previous.url != release.url:
            raise MarionDownloadError(
                "Official page declares conflicting URLs for one release slot",
                details={
                    "source_id": release.source_id,
                    "release_id": release.release_id,
                    "first_url": previous.url,
                    "second_url": release.url,
                },
            )
        releases[key] = release

    assessment = [
        release
        for release in releases.values()
        if release.source_id == ASSESSMENT_SOURCE_ID
    ]
    sales = [
        release
        for release in releases.values()
        if release.source_id == SALES_SOURCE_ID
    ]
    if len(assessment) != 1 or not sales:
        raise MarionDownloadError(
            "Official page did not expose both Marion download families",
            details={
                "assessment_release_count": len(assessment),
                "sales_release_count": len(sales),
                "landing_url": base_url,
            },
        )
    earliest = min(
        release.coverage_start
        for release in sales
        if release.coverage_start is not None
    )
    if earliest > 1940:
        raise MarionDownloadError(
            "Sales manifest no longer reaches the publisher-described 1940s",
            details={"earliest_recognized_year": earliest},
        )
    covered_through = 1939
    for release in sorted(
        sales,
        key=lambda item: (
            item.coverage_start or 9999,
            item.coverage_end or 9999,
        ),
    ):
        assert release.coverage_start is not None
        assert release.coverage_end is not None
        if release.coverage_start > covered_through + 1:
            raise MarionDownloadError(
                "Recognized sales manifest has a calendar-year coverage gap",
                details={
                    "covered_through": covered_through,
                    "next_coverage_start": release.coverage_start,
                    "next_release_id": release.release_id,
                },
            )
        covered_through = max(covered_through, release.coverage_end)
    ordered = tuple(
        sorted(
            releases.values(),
            key=lambda release: (
                0 if release.source_id == ASSESSMENT_SOURCE_ID else 1,
                -(release.coverage_end or 9999),
                release.release_id,
            ),
        )
    )
    return ManifestSnapshot(
        releases=ordered,
        landing_sha256=hashlib.sha256(
            html_text.encode("utf-8")
        ).hexdigest(),
    )


def _response_status(response: Any) -> int:
    return int(
        getattr(response, "status", getattr(response, "status_code", 200))
    )


def fetch_release_manifest(
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    opener: Callable[..., Any] = urlopen,
) -> ManifestSnapshot:
    """Fetch and parse the official Reports & Data page."""

    request = Request(
        LANDING_URL,
        headers={
            "User-Agent": "Ithildin-Public-Records/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    last_error: Exception | None = None
    for attempt in range(1, retry_attempts + 1):
        try:
            with opener(request, timeout=timeout) as response:
                status = _response_status(response)
                if status < 200 or status >= 300:
                    raise ManifestTransportError(
                        f"Official Marion listing returned HTTP {status}",
                        details={
                            "url": LANDING_URL,
                            "http_status": status,
                        },
                    )
                body = response.read()
            return parse_release_manifest(
                body.decode("utf-8", errors="replace")
            )
        except HTTPError as error:
            last_error = error
            retryable = error.code in {429, 500, 502, 503, 504}
            if not retryable or attempt >= retry_attempts:
                raise ManifestTransportError(
                    f"Official Marion listing returned HTTP {error.code}",
                    details={
                        "url": LANDING_URL,
                        "http_status": error.code,
                    },
                ) from error
        except (URLError, TimeoutError, ConnectionError, OSError) as error:
            last_error = error
            if attempt >= retry_attempts:
                raise ManifestTransportError(
                    f"Could not fetch the official Marion listing: {error}",
                    details={"url": LANDING_URL},
                ) from error
        if attempt < retry_attempts:
            time.sleep(min(0.25 * (2 ** (attempt - 1)), 2.0))
    assert last_error is not None
    raise ManifestTransportError(str(last_error))


def _encode_cursor(payload: Mapping[str, Any]) -> str:
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii")
    return CURSOR_PREFIX + encoded.rstrip("=")


def _decode_cursor(cursor: str) -> dict[str, Any]:
    if not cursor.startswith(CURSOR_PREFIX):
        raise CursorError("Cursor does not belong to Marion downloads")
    encoded = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        value = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CursorError("Cursor payload is invalid") from error
    if not isinstance(value, dict) or value.get("version") != CURSOR_VERSION:
        raise CursorError("Cursor version is not supported")
    return value


def _manifest_page(
    snapshot: ManifestSnapshot,
    releases: Sequence[Release],
    *,
    limit: int | None,
    cursor: str | None,
) -> tuple[tuple[Release, ...], str | None]:
    selection_fingerprint = sha256_fingerprint(
        [
            {
                "source_id": release.source_id,
                "release_id": release.release_id,
            }
            for release in releases
        ]
    )
    offset = 0
    if cursor is not None:
        payload = _decode_cursor(cursor)
        if payload.get("kind") != "manifest":
            raise CursorError("Cursor is not a manifest cursor")
        if payload.get("release_set_fingerprint") != snapshot.fingerprint:
            raise CursorError(
                "Official Marion release listing changed after this cursor",
            )
        if payload.get("selection_fingerprint") != selection_fingerprint:
            raise CursorError(
                "Manifest cursor no longer matches the release selection",
            )
        offset = payload.get("offset")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise CursorError("Manifest cursor offset is invalid")
    end = len(releases) if limit is None else min(len(releases), offset + limit)
    next_cursor = None
    if end < len(releases):
        next_cursor = _encode_cursor(
            {
                "version": CURSOR_VERSION,
                "kind": "manifest",
                "release_set_fingerprint": snapshot.fingerprint,
                "selection_fingerprint": selection_fingerprint,
                "offset": end,
            }
        )
    return tuple(releases[offset:end]), next_cursor


def _selected_releases(
    *,
    snapshot: ManifestSnapshot,
    source_id: str | None,
    release_id: str | None,
    year: int | None,
) -> tuple[Release, ...]:
    releases = tuple(
        release
        for release in snapshot.releases
        if source_id in {None, "all", release.source_id}
        and release_id in {None, release.release_id}
        and (
            year is None
            or (
                release.coverage_start is not None
                and release.coverage_end is not None
                and release.coverage_start <= year <= release.coverage_end
            )
        )
    )
    return releases


def _one_release(
    *,
    snapshot: ManifestSnapshot,
    source_id: str,
    release_id: str | None,
    year: int | None,
) -> Release:
    if release_id is None and year is None:
        candidates = snapshot.by_source(source_id)
        if source_id == ASSESSMENT_SOURCE_ID and len(candidates) == 1:
            return candidates[0]
        if source_id == SALES_SOURCE_ID:
            current = [
                release
                for release in candidates
                if release.publication_kind == "weekly_current_year"
            ]
            if len(current) == 1:
                return current[0]
    selected = _selected_releases(
        snapshot=snapshot,
        source_id=source_id,
        release_id=release_id,
        year=year,
    )
    if len(selected) != 1:
        raise MarionDownloadError(
            "Operation requires selectors resolving to one release",
            details={
                "source_id": source_id,
                "release_id": release_id,
                "year": year,
                "matched_release_ids": [
                    release.release_id for release in selected
                ],
            },
            status=ResultStatus.UNAVAILABLE,
            code="marion_download_release_selection",
            category="query_selection",
        )
    return selected[0]


def _local_release(
    *,
    source_id: str,
    artifact_path: Path | str,
    release_id: str | None,
    year: int | None,
) -> Release:
    """Resolve inspection metadata from local selectors without a web fetch."""

    name = Path(artifact_path).expanduser().name
    if source_id == ASSESSMENT_SOURCE_ID:
        if release_id not in {None, "comprehensive-current"}:
            raise MarionDownloadError(
                "Comprehensive local inspection uses its current release slot",
                details={"release_id": release_id},
                status=ResultStatus.UNAVAILABLE,
                code="marion_download_release_selection",
                category="query_selection",
            )
        return Release(
            source_id=source_id,
            release_id="comprehensive-current",
            label=name,
            url=COMPREHENSIVE_URL,
            coverage_start=None,
            coverage_end=None,
            publication_kind="local_snapshot_artifact",
            format="zip",
            schema_profile="comprehensive_assessment_v1",
        )

    parsed_start: int | None = None
    parsed_end: int | None = None
    artifact_format = Path(name).suffix.casefold().lstrip(".")
    for pattern in (
        _CURRENT_SALES_RE,
        _ANNUAL_SALES_RE,
        _DECADE_ZIP_RE,
        _DECADE_XLS_RE,
    ):
        matched = pattern.fullmatch(name)
        if matched is None:
            continue
        parsed_start = int(
            matched.groupdict().get("year")
            or matched.groupdict()["start"]
        )
        parsed_end = int(
            matched.groupdict().get("year")
            or matched.groupdict().get("end")
            or parsed_start
        )
        break
    if year is not None:
        if parsed_start is not None and not (
            parsed_start <= year <= (parsed_end or parsed_start)
        ):
            raise MarionDownloadError(
                "Local artifact filename and selected year disagree",
                details={"filename": name, "year": year},
                status=ResultStatus.UNAVAILABLE,
                code="marion_download_release_selection",
                category="query_selection",
            )
        parsed_start = parsed_start or year
        parsed_end = parsed_end or year
    if parsed_start is None and release_id:
        match = re.fullmatch(
            r"sales-(?P<start>\d{4})(?:-(?P<end>\d{4}))?",
            release_id,
        )
        if match:
            parsed_start = int(match.group("start"))
            parsed_end = int(match.group("end") or parsed_start)
    if (
        parsed_start is None
        or parsed_end is None
        or artifact_format not in {"csv", "zip", "xls"}
    ):
        raise MarionDownloadError(
            "Local sales inspection needs a recognized official filename, "
            "--year, or --release selector",
            details={
                "filename": name,
                "release_id": release_id,
                "year": year,
            },
            status=ResultStatus.UNAVAILABLE,
            code="marion_download_release_selection",
            category="query_selection",
        )
    resolved_release_id = (
        f"sales-{parsed_start}"
        if parsed_start == parsed_end
        else f"sales-{parsed_start}-{parsed_end}"
    )
    if release_id not in {None, resolved_release_id}:
        raise MarionDownloadError(
            "Local artifact and release selectors disagree",
            details={
                "filename": name,
                "release_id": release_id,
                "resolved_release_id": resolved_release_id,
            },
            status=ResultStatus.UNAVAILABLE,
            code="marion_download_release_selection",
            category="query_selection",
        )
    return Release(
        source_id=source_id,
        release_id=resolved_release_id,
        label=name,
        url=LANDING_URL,
        coverage_start=parsed_start,
        coverage_end=parsed_end,
        publication_kind="local_artifact",
        format=artifact_format,
        schema_profile=_sales_schema_profile(
            coverage_start=parsed_start,
            format=artifact_format,
        ),
    )


def _normalize_header_name(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def _sales_columns(
    profile_name: str,
    raw_header: Sequence[str],
) -> tuple[str, ...]:
    profile = SALES_SCHEMA_PROFILES[profile_name]
    expected = tuple(profile["raw_header"])
    if len(raw_header) != len(expected) or tuple(
        _normalize_header_name(value) for value in raw_header
    ) != tuple(_normalize_header_name(value) for value in expected):
        raise MarionDownloadError(
            "Sales CSV header no longer matches its historical schema profile",
            details={
                "schema_profile": profile_name,
                "expected_raw_header": list(expected),
                "observed_raw_header": list(raw_header),
            },
        )
    return tuple(profile["canonical_columns"])


def _csv_reader(stream: io.TextIOBase) -> csv.reader:
    csv.field_size_limit(CSV_FIELD_SIZE_LIMIT)
    return csv.reader(stream)


def _csv_member_header(
    archive: zipfile.ZipFile,
    member_name: str,
) -> tuple[str, ...]:
    with archive.open(member_name) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        reader = _csv_reader(text)
        try:
            return tuple(next(reader))
        except StopIteration as error:
            raise MarionDownloadError(
                "Comprehensive CSV member is empty",
                details={"member": member_name},
            ) from error


def _member_occurrence(
    *,
    artifact_sha256: str,
    path: str,
    size: int,
    crc32: str | None,
) -> dict[str, Any]:
    payload = {
        "artifact_sha256": artifact_sha256,
        "member_path": path,
        "member_size": size,
        "member_crc32": crc32,
    }
    return {
        **payload,
        "member_occurrence_id": sha256_fingerprint(payload),
    }


def _legacy_member_profile(member_name: str) -> dict[str, Any]:
    suffix = Path(member_name).suffix.casefold()
    year_match = re.search(r"(19|20)\d{2}", Path(member_name).name)
    year = int(year_match.group()) if year_match else None
    return {
        "member_name": member_name,
        "calendar_year": year,
        "format": suffix.lstrip(".") or "unknown",
        "row_search_supported": suffix == ".csv",
        "schema_profile": (
            _sales_schema_profile(coverage_start=year, format="csv")
            if suffix == ".csv" and year is not None and year >= 2020
            else "legacy_workbook_member"
        ),
        "unsupported_reason": (
            None
            if suffix == ".csv"
            else (
                "This official member is retained and transferable, but its "
                "legacy workbook format is not parsed by this adapter."
            )
        ),
    }


def _inspect_sales_artifact(
    artifact_path: Path,
    release: Release,
    *,
    scan_rows: bool,
) -> dict[str, Any]:
    artifact_sha256 = file_sha256(artifact_path)
    base = {
        "path": str(artifact_path),
        "artifact_sha256": artifact_sha256,
        "artifact_size": artifact_path.stat().st_size,
        "source_id": release.source_id,
        "release_id": release.release_id,
        "release_slot_identity": release.release_slot_identity,
        "release_occurrence_identity": {
            "artifact_sha256": artifact_sha256,
            "interchangeable_with_release_slot": False,
        },
        "schema_profile": release.schema_profile,
        "capability": release.capability,
    }
    if release.format == "csv":
        row_count = 0
        with artifact_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as stream:
            reader = _csv_reader(stream)
            try:
                raw_header = tuple(next(reader))
            except StopIteration as error:
                raise MarionDownloadError(
                    "Sales CSV is empty",
                    details={"path": str(artifact_path)},
                ) from error
            columns = _sales_columns(release.schema_profile, raw_header)
            if scan_rows:
                for row_number, row in enumerate(reader, start=2):
                    if len(row) != len(columns):
                        raise MarionDownloadError(
                            "Sales CSV row width differs from its header",
                            details={
                                "row_number": row_number,
                                "expected_columns": len(columns),
                                "observed_columns": len(row),
                            },
                        )
                    row_count += 1
        member = _member_occurrence(
            artifact_sha256=artifact_sha256,
            path=artifact_path.name,
            size=artifact_path.stat().st_size,
            crc32=None,
        )
        return {
            **base,
            "format": "csv",
            "raw_header": list(raw_header),
            "canonical_columns": list(columns),
            "schema_fingerprint": sha256_fingerprint(
                {
                    "schema_profile": release.schema_profile,
                    "raw_header": raw_header,
                    "canonical_columns": columns,
                }
            ),
            "member_occurrences": [member],
            "row_count": row_count if scan_rows else None,
            "complete_row_scan": scan_rows,
        }
    if release.format == "zip":
        archive_inspection = inspect_zip(artifact_path)
        member_capabilities = []
        for member in archive_inspection.members:
            if member["kind"] != "file":
                continue
            member_capabilities.append(
                {
                    **_legacy_member_profile(str(member["path"])),
                    **_member_occurrence(
                        artifact_sha256=artifact_sha256,
                        path=str(member["path"]),
                        size=int(member["size"]),
                        crc32=str(member["crc32"]),
                    ),
                }
            )
        return {
            **base,
            "format": "zip",
            "archive": archive_inspection.to_dict(),
            "member_occurrences": member_capabilities,
            "row_search_supported_members": [
                member["member_name"]
                for member in member_capabilities
                if member["row_search_supported"]
            ],
            "unsupported_member_formats": sorted(
                {
                    member["format"]
                    for member in member_capabilities
                    if not member["row_search_supported"]
                }
            ),
            "source_manifest_accessible": True,
        }
    return {
        **base,
        "format": release.format,
        "member_occurrences": [
            {
                **_legacy_member_profile(artifact_path.name),
                **_member_occurrence(
                    artifact_sha256=artifact_sha256,
                    path=artifact_path.name,
                    size=artifact_path.stat().st_size,
                    crc32=None,
                ),
            }
        ],
        "source_manifest_accessible": True,
    }


def _inspect_comprehensive_artifact(
    artifact_path: Path,
    release: Release,
    *,
    scan_rows: bool,
) -> dict[str, Any]:
    archive_inspection = inspect_zip(artifact_path)
    artifact_sha256 = archive_inspection.archive_sha256
    members = {
        str(member["path"]): member
        for member in archive_inspection.members
        if member["kind"] == "file"
    }
    missing = [
        member
        for member in COMPREHENSIVE_DATA_MEMBERS
        if member not in members
    ]
    if missing:
        raise MarionDownloadError(
            "Comprehensive archive lacks required data members",
            details={"missing_members": missing},
        )
    schemas: dict[str, Any] = {}
    row_counts: dict[str, int | None] = {}
    vintages: set[str] = set()
    with zipfile.ZipFile(artifact_path) as archive:
        for member_name in COMPREHENSIVE_DATA_MEMBERS:
            header = _csv_member_header(archive, member_name)
            if len(header) != len(set(header)):
                raise MarionDownloadError(
                    "Comprehensive CSV contains duplicate header names",
                    details={
                        "member": member_name,
                        "header": list(header),
                    },
                )
            schemas[member_name] = {
                "raw_header": list(header),
                "schema_fingerprint": sha256_fingerprint(header),
            }
            row_counts[member_name] = None
        primary_header = tuple(
            schemas[COMPREHENSIVE_PRIMARY_MEMBER]["raw_header"]
        )
        absent = [
            field
            for field in COMPREHENSIVE_REQUIRED_PRIMARY_FIELDS
            if field not in primary_header
        ]
        if absent:
            raise MarionDownloadError(
                "Comprehensive primary CSV lacks required fields",
                details={"missing_fields": absent},
            )
        if scan_rows:
            for member_name in COMPREHENSIVE_DATA_MEMBERS:
                with archive.open(member_name) as raw:
                    text = io.TextIOWrapper(
                        raw,
                        encoding="utf-8-sig",
                        newline="",
                    )
                    reader = _csv_reader(text)
                    header = tuple(next(reader))
                    count = 0
                    rdate_index = (
                        header.index("RDATE")
                        if member_name == COMPREHENSIVE_PRIMARY_MEMBER
                        else None
                    )
                    for row_number, row in enumerate(reader, start=2):
                        if len(row) != len(header):
                            raise MarionDownloadError(
                                "Comprehensive CSV row width changed",
                                details={
                                    "member": member_name,
                                    "row_number": row_number,
                                    "expected_columns": len(header),
                                    "observed_columns": len(row),
                                },
                            )
                        count += 1
                        if rdate_index is not None:
                            value = row[rdate_index].strip()
                            if value:
                                vintages.add(value)
                    row_counts[member_name] = count
    owner_columns_present = sorted(
        field
        for field in COMPREHENSIVE_OWNER_COLUMNS_OMITTED_SINCE_2015
        if field in primary_header
    )
    member_occurrences = [
        _member_occurrence(
            artifact_sha256=artifact_sha256,
            path=member_name,
            size=int(members[member_name]["size"]),
            crc32=str(members[member_name]["crc32"]),
        )
        for member_name in sorted(members)
    ]
    return {
        "path": str(artifact_path),
        "artifact_sha256": artifact_sha256,
        "artifact_size": archive_inspection.archive_size,
        "source_id": release.source_id,
        "release_id": release.release_id,
        "release_slot_identity": release.release_slot_identity,
        "release_occurrence_identity": {
            "artifact_sha256": artifact_sha256,
            "interchangeable_with_release_slot": False,
        },
        "format": "zip",
        "schema_profile": release.schema_profile,
        "schema_fingerprint": sha256_fingerprint(schemas),
        "archive": archive_inspection.to_dict(),
        "member_schemas": schemas,
        "member_occurrences": member_occurrences,
        "row_counts": row_counts,
        "complete_row_scan": scan_rows,
        "rdate_values": sorted(vintages),
        "owner_publication_state": {
            "owner_names_included": bool(owner_columns_present),
            "owner_mailing_addresses_included": bool(owner_columns_present),
            "unexpected_owner_columns": owner_columns_present,
            "publisher_omission_effective": "2015-02-01",
        },
        "latest_sale_field_interpretation": {
            "fields": [
                "YRSOLD",
                "MOSOLD",
                "INSTRTYP",
                "SALEBK",
                "SALEPR",
                "SALE_GRANTEE",
                "SALE_GRANTOR",
            ],
            "role": "assessor_latest_sale_labels",
            "establishes_current_owner": False,
            "establishes_title": False,
            "verifies_recorded_instrument": False,
        },
        "capability": release.capability,
    }


def inspect_local_artifact(
    path: Path | str,
    *,
    release: Release,
    scan_rows: bool = True,
) -> dict[str, Any]:
    artifact_path = Path(path).expanduser().resolve()
    if not artifact_path.is_file():
        raise MarionDownloadError(
            "Local Marion artifact does not exist",
            details={"path": str(artifact_path)},
            status=ResultStatus.UNAVAILABLE,
            code="marion_download_artifact_missing",
            category="query_selection",
        )
    if release.source_id == SALES_SOURCE_ID:
        return _inspect_sales_artifact(
            artifact_path,
            release,
            scan_rows=scan_rows,
        )
    return _inspect_comprehensive_artifact(
        artifact_path,
        release,
        scan_rows=scan_rows,
    )


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).strip().split())
    if normalized.casefold() in {"", "null", "none"}:
        return None
    return normalized


def _integer(value: Any) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    text = text.replace(",", "")
    try:
        return int(text)
    except ValueError:
        return None


def _number(value: Any) -> int | float | None:
    text = _clean(value)
    if text is None:
        return None
    text = text.replace(",", "")
    try:
        number = float(text)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _sum_present(*values: int | float | None) -> int | float | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _date_iso(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    for source_format in ("%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, source_format).date().isoformat()
        except ValueError:
            continue
    return None


def _row_occurrence(
    *,
    source_id: str,
    release: Release,
    artifact_sha256: str,
    member_occurrence_id: str,
    row_number: int,
    values: Sequence[str],
) -> dict[str, Any]:
    raw_row_sha256 = sha256_fingerprint(list(values))
    payload = {
        "source_id": source_id,
        "release_id": release.release_id,
        "artifact_sha256": artifact_sha256,
        "member_occurrence_id": member_occurrence_id,
        "row_number": row_number,
        "raw_row_sha256": raw_row_sha256,
    }
    return {
        **payload,
        "row_occurrence_id": sha256_fingerprint(payload),
    }


def _source_columns(
    raw_header: Sequence[str],
    canonical_columns: Sequence[str],
    values: Sequence[str],
) -> list[dict[str, Any]]:
    return [
        {
            "zero_based_position": index,
            "raw_header": raw_header[index],
            "canonical_name": canonical_columns[index],
            "raw_value": values[index],
        }
        for index in range(len(values))
    ]


def _normalize_sale_row(
    values: Sequence[str],
    *,
    raw_header: Sequence[str],
    canonical_columns: Sequence[str],
    release: Release,
    artifact_sha256: str,
    member_occurrence_id: str,
    row_number: int,
) -> dict[str, Any]:
    raw = dict(zip(canonical_columns, values, strict=True))
    explicit_sale_id = _clean(raw.get("sale_id"))
    semantic_components = {
        "account_number": _clean(raw.get("account_number")),
        "map_taxlot": _clean(raw.get("map_taxlot")),
        "sale_date": _date_iso(raw.get("sale_date")),
        "instrument_number": _clean(raw.get("instrument_number")),
        "deed_reel_page": _clean(raw.get("deed_reel_page")),
        "sale_price": _number(raw.get("sale_price")),
    }
    native_sale_id = (
        f"sale-id:{explicit_sale_id}"
        if explicit_sale_id
        else f"semantic:{sha256_fingerprint(semantic_components)}"
    )
    occurrence = _row_occurrence(
        source_id=release.source_id,
        release=release,
        artifact_sha256=artifact_sha256,
        member_occurrence_id=member_occurrence_id,
        row_number=row_number,
        values=values,
    )
    account_number = _clean(raw.get("account_number"))
    map_taxlot = _clean(raw.get("map_taxlot"))
    ms_account = _clean(
        raw.get("manufactured_structure_account_number")
    )
    sale_date = _date_iso(raw.get("sale_date"))
    instrument_number = _clean(raw.get("instrument_number"))
    deed_reel_page = _clean(raw.get("deed_reel_page"))
    grantor = _clean(raw.get("grantor_name"))
    grantee = _clean(raw.get("grantee_name"))
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "canonical_ref": canonical_property_ref(
            release.source_id,
            COUNTY_GEOID,
            "assessor_sale",
            native_sale_id,
        ),
        "source_id": release.source_id,
        "record_kind": "assessor_sale_observation",
        "native_sale_id": native_sale_id,
        "sale_identity": {
            "basis": (
                "publisher_sale_id"
                if explicit_sale_id
                else "semantic_source_fields"
            ),
            "publisher_sale_id": explicit_sale_id,
            "semantic_components": semantic_components,
            "interchangeable_with_release_occurrence": False,
            "interchangeable_with_parcel_join": False,
        },
        "release_slot_identity": release.release_slot_identity,
        "release_occurrence_identity": {
            "artifact_sha256": artifact_sha256,
            "interchangeable_with_sale_identity": False,
        },
        "member_occurrence_id": member_occurrence_id,
        "row_occurrence": occurrence,
        "source_occurrence_id": occurrence["row_occurrence_id"],
        "parcel_join_keys": {
            "assessment_account_id": account_number,
            "map_taxlot": map_taxlot,
            "manufactured_structure_account_id": ms_account,
            "related_source_id": MARION_PARCELS_SOURCE_ID,
        },
        "join_keys": {
            "assessment_account_id": account_number,
            "map_taxlot": map_taxlot,
            "related_source_id": MARION_PARCELS_SOURCE_ID,
        },
        "sale": {
            "sale_date": sale_date,
            "sale_date_raw": _clean(raw.get("sale_date")),
            "legacy_leading_sale_date_raw": _clean(
                raw.get("legacy_leading_sale_date")
            ),
            "consideration": _number(raw.get("sale_price")),
            "ratio_year": _integer(raw.get("ratio_year")),
            "condition_code": _clean(raw.get("condition_code")),
            "condition_description": _clean(
                raw.get("condition_description")
            ),
            "number_of_accounts": _integer(
                raw.get("number_of_accounts")
            ),
            "primary_account_flag": _clean(
                raw.get("primary_account_flag")
            ),
        },
        "instrument_reference": {
            "instrument_number": instrument_number,
            "deed_reel_page": deed_reel_page,
            "instrument_type": _clean(raw.get("document_type_code")),
            "instrument_type_description": _clean(
                raw.get("document_type_description")
            ),
            "instrument_source": _clean(raw.get("instrument_source")),
            "source_kind": "assessor_sale_index_reference",
            "recorder_document_verified": False,
        },
        "transaction_parties": [
            party
            for party in (
                {
                    "role": "grantor_label",
                    "raw_name": grantor,
                    "raw_address": _clean(raw.get("grantor_address")),
                    "current_owner_inference": False,
                    "title_inference": False,
                },
                {
                    "role": "grantee_label",
                    "raw_name": grantee,
                    "raw_address": _clean(raw.get("grantee_address")),
                    "current_owner_inference": False,
                    "title_inference": False,
                },
            )
            if party["raw_name"] is not None
            or party["raw_address"] is not None
        ],
        "situs_address": {
            "raw": _clean(raw.get("situs_address")),
        },
        "property_context": {
            "roll_type": _clean(raw.get("roll_type")),
            "property_class": _clean(raw.get("property_class")),
            "property_class_description": _clean(
                raw.get("property_class_description")
            ),
            "statistical_classification": _clean(
                raw.get("statistical_classification")
            ),
            "statistical_classification_description": _clean(
                raw.get("statistical_classification_description")
            ),
            "year_built": _integer(raw.get("year_built")),
            "building_square_feet": _number(
                raw.get("building_square_feet")
            ),
            "land_acres": _number(raw.get("land_acres")),
            "land_square_feet": _number(raw.get("land_square_feet")),
            "subdivision_lot_block_or_partition": _clean(
                raw.get("subdivision_lot_block_or_partition")
            ),
        },
        "schema_profile": release.schema_profile,
        "source_columns": _source_columns(
            raw_header,
            canonical_columns,
            values,
        ),
        "raw_attributes": raw,
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": COUNTY_NAME,
            "county_geoid": COUNTY_GEOID,
        },
        "source_url": release.url,
    }


def _map_components(raw: Mapping[str, str]) -> dict[str, Any]:
    return {
        "map_township": _clean(raw.get("MTOWN")),
        "map_township_direction": _clean(raw.get("MTOWND")),
        "map_range": _clean(raw.get("MRANGE")),
        "map_range_direction": _clean(raw.get("MRANGED")),
        "map_section": _clean(raw.get("MSECTION")),
        "map_quarter_section": _clean(raw.get("MQSECT")),
        "map_sixteenth_section": _clean(raw.get("MXSECT")),
        "map_taxlot_component": _clean(raw.get("MTAXLOT")),
        "oregon_taxlot_component": _clean(raw.get("ORTAXLOT")),
    }


def _normalize_assessment_row(
    values: Sequence[str],
    *,
    raw_header: Sequence[str],
    release: Release,
    artifact_sha256: str,
    member_occurrence_id: str,
    row_number: int,
) -> dict[str, Any]:
    raw = dict(zip(raw_header, values, strict=True))
    account_id = _clean(raw.get("ACCOUNT_ID"))
    if account_id is None:
        raise MarionDownloadError(
            "Comprehensive assessment row lacks ACCOUNT_ID",
            details={"row_number": row_number},
        )
    txid = _clean(raw.get("TXID"))
    rdate_raw = _clean(raw.get("RDATE"))
    source_vintage = _date_iso(rdate_raw)
    occurrence = _row_occurrence(
        source_id=release.source_id,
        release=release,
        artifact_sha256=artifact_sha256,
        member_occurrence_id=member_occurrence_id,
        row_number=row_number,
        values=values,
    )
    sale_price = _number(raw.get("SALEPR"))
    latest_sale_labels = {
        "year_sold": _integer(raw.get("YRSOLD")),
        "month_sold": _integer(raw.get("MOSOLD")),
        "instrument_type": _clean(raw.get("INSTRTYP")),
        "book_page_label": _clean(raw.get("SALEBK")),
        "sale_price": sale_price,
        "grantor_label": _clean(raw.get("SALE_GRANTOR")),
        "grantee_label": _clean(raw.get("SALE_GRANTEE")),
        "source_role": "assessor_latest_sale_labels",
        "establishes_current_owner": False,
        "establishes_title": False,
        "verifies_recorded_instrument": False,
    }
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "canonical_ref": canonical_property_ref(
            release.source_id,
            COUNTY_GEOID,
            "assessment_account_snapshot",
            f"{account_id}:{rdate_raw or 'undated'}",
        ),
        "source_id": release.source_id,
        "record_kind": "assessment_account_snapshot",
        "native_parcel_id": account_id,
        "native_assessment_account_id": account_id,
        "assessment_account_ids": [
            value
            for value in dict.fromkeys((account_id, txid))
            if value is not None
        ],
        "alternate_parcel_ids": [
            value
            for value in (txid,)
            if value is not None and value != account_id
        ],
        "parcel_join_keys": {
            "assessment_account_id": account_id,
            "transaction_id": txid,
            "map_components": _map_components(raw),
            "related_source_id": MARION_PARCELS_SOURCE_ID,
        },
        "release_slot_identity": release.release_slot_identity,
        "release_occurrence_identity": {
            "artifact_sha256": artifact_sha256,
            "interchangeable_with_account_identity": False,
        },
        "member_occurrence_id": member_occurrence_id,
        "row_occurrence": occurrence,
        "source_occurrence_id": occurrence["row_occurrence_id"],
        "roll_year": _integer(raw.get("TYYYY")),
        "source_vintage": {
            "rdate_raw": rdate_raw,
            "rdate_iso": source_vintage,
            "field": f"{COMPREHENSIVE_PRIMARY_MEMBER}:RDATE",
        },
        "source_last_updated": source_vintage,
        "situs_address": {
            "raw": ", ".join(
                value
                for value in (
                    _clean(raw.get("SITUSSTR")),
                    _clean(raw.get("SITUSCITY")),
                    _clean(raw.get("SITUSZIP")),
                )
                if value is not None
            )
            or None,
            "street": _clean(raw.get("SITUSSTR")),
            "city": _clean(raw.get("SITUSCITY")),
            "postal_code": _clean(raw.get("SITUSZIP")),
        },
        "assessment": {
            "tax_year": _integer(raw.get("TYYYY")),
            "assessed_value": _number(raw.get("AV")),
            "real_market_land": _number(raw.get("RMVLAND")),
            "real_market_improvements": _number(raw.get("RMVIMPR")),
            "real_market_total": _sum_present(
                _number(raw.get("RMVLAND")),
                _number(raw.get("RMVIMPR")),
            ),
            "gross_tax": _number(raw.get("GROSSTAX")),
            "tax_due": _number(raw.get("TAXDUE")),
            "tax_code": _clean(raw.get("TXCD")),
            "tax_status": _clean(raw.get("TX_STAT")),
            "property_class": _clean(raw.get("PCLS")),
            "property_class_description": _clean(raw.get("PCLSD")),
            "property_type": _clean(raw.get("PROPTYP")),
        },
        "physical_characteristics": {
            "improvement_type": _clean(raw.get("IMPTYP")),
            "finished_square_feet": _number(raw.get("FINSQFT")),
            "manufactured_structure_make": _clean(raw.get("MSMAKE")),
            "manufactured_home_size": _clean(raw.get("MHSIZE")),
            "acres": _number(raw.get("ACRES")),
            "subdivision": _clean(raw.get("SUBDIVISION")),
            "block": _clean(raw.get("BLOCK")),
            "lot": _clean(raw.get("LOT")),
        },
        "latest_sale_labels": latest_sale_labels,
        "owner_publication_state": {
            "owner_names_included": False,
            "owner_mailing_addresses_included": False,
            "publisher_omission_effective": "2015-02-01",
            "sale_party_labels_are_owner_fields": False,
        },
        "owners": [],
        "snapshot_complete": False,
        "snapshot_completeness": {
            "published_assessment_row_complete": True,
            "owner_scope_omitted_by_publisher": True,
            "does_not_establish": [
                "current_owner",
                "mailing_address",
                "recorded_title",
                "recorded_instrument_contents",
            ],
        },
        "schema_profile": release.schema_profile,
        "raw_attributes": raw,
        "jurisdiction": {
            "state_code": STATE_CODE,
            "state_fips": STATE_FIPS,
            "county_name": COUNTY_NAME,
            "county_geoid": COUNTY_GEOID,
        },
        "source_url": release.url,
    }


def _text_key(value: Any) -> str:
    return " ".join((_clean(value) or "").casefold().split())


def _identifier_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _text_key(value))


def _matches_value(
    value: Any,
    query: str,
    *,
    match: str,
    identifier: bool,
) -> bool:
    candidate = _identifier_key(value) if identifier else _text_key(value)
    needle = _identifier_key(query) if identifier else _text_key(query)
    if match == "exact":
        return candidate == needle
    if match == "prefix":
        return candidate.startswith(needle)
    return needle in candidate


SALES_SEARCH_FIELDS = {
    "any": (
        "sale_id",
        "instrument_number",
        "deed_reel_page",
        "account_number",
        "manufactured_structure_account_number",
        "map_taxlot",
        "situs_address",
        "grantor_name",
        "grantor_address",
        "grantee_name",
        "grantee_address",
    ),
    "sale-id": ("sale_id",),
    "instrument": ("instrument_number", "deed_reel_page"),
    "account": (
        "account_number",
        "manufactured_structure_account_number",
    ),
    "parcel": ("map_taxlot",),
    "address": (
        "situs_address",
        "grantor_address",
        "grantee_address",
    ),
    "grantor": ("grantor_name",),
    "grantee": ("grantee_name",),
    "party": ("grantor_name", "grantee_name"),
}
ASSESSMENT_SEARCH_FIELDS = {
    "any": (
        "ACCOUNT_ID",
        "TXID",
        "MTAXLOT",
        "ORTAXLOT",
        "SITUSSTR",
        "SITUSCITY",
        "BOOKPG",
        "SALE_GRANTOR",
        "SALE_GRANTEE",
    ),
    "account": ("ACCOUNT_ID", "TXID"),
    "parcel": ("MTAXLOT", "ORTAXLOT"),
    "address": ("SITUSSTR", "SITUSCITY", "SITUSZIP"),
    "instrument": ("BOOKPG",),
    "latest-sale-party": ("SALE_GRANTOR", "SALE_GRANTEE"),
}


def _row_matches(
    raw: Mapping[str, str],
    *,
    source_id: str,
    field: str,
    query: str,
    match: str,
) -> bool:
    fields = (
        SALES_SEARCH_FIELDS[field]
        if source_id == SALES_SOURCE_ID
        else ASSESSMENT_SEARCH_FIELDS[field]
    )
    identifier = field in {"sale-id", "instrument", "account", "parcel"}
    return any(
        _matches_value(
            raw.get(name),
            query,
            match=match,
            identifier=identifier,
        )
        for name in fields
    )


def _search_cursor_start(
    cursor: str | None,
    *,
    release: Release,
    artifact_sha256: str,
    criteria_fingerprint: str,
) -> int:
    if cursor is None:
        return 0
    payload = _decode_cursor(cursor)
    expected = {
        "kind": "search",
        "source_id": release.source_id,
        "release_id": release.release_id,
        "artifact_sha256": artifact_sha256,
        "criteria_fingerprint": criteria_fingerprint,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise CursorError(
                "Search cursor no longer matches source, release, artifact, "
                "or query criteria",
                details={"field": key},
            )
    offset = payload.get("match_offset")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise CursorError("Search cursor match offset is invalid")
    return offset


def _next_search_cursor(
    *,
    release: Release,
    artifact_sha256: str,
    criteria_fingerprint: str,
    match_offset: int,
) -> str:
    return _encode_cursor(
        {
            "version": CURSOR_VERSION,
            "kind": "search",
            "source_id": release.source_id,
            "release_id": release.release_id,
            "artifact_sha256": artifact_sha256,
            "criteria_fingerprint": criteria_fingerprint,
            "match_offset": match_offset,
        }
    )


def _open_search_rows(
    artifact_path: Path,
    *,
    release: Release,
) -> Iterator[
    tuple[
        tuple[str, ...],
        tuple[str, ...],
        str,
        Iterator[tuple[int, list[str]]],
        BinaryIO | io.TextIOBase,
    ]
]:
    if release.source_id == SALES_SOURCE_ID:
        if release.format != "csv":
            raise MarionDownloadError(
                "Selected historical sales artifact is manifest-only for row "
                "search because its members use legacy workbook formats",
                details={
                    "release_id": release.release_id,
                    "format": release.format,
                    "capability": release.capability,
                },
                status=ResultStatus.UNAVAILABLE,
                code="marion_sales_member_format_not_searchable",
                category="artifact_capability",
            )
        stream = artifact_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        )
        try:
            reader = _csv_reader(stream)
            try:
                raw_header = tuple(next(reader))
            except StopIteration as error:
                raise MarionDownloadError(
                    "Sales CSV is empty",
                    details={"path": str(artifact_path)},
                ) from error
            canonical_columns = _sales_columns(
                release.schema_profile,
                raw_header,
            )
            member_occurrence_id = _member_occurrence(
                artifact_sha256=file_sha256(artifact_path),
                path=artifact_path.name,
                size=artifact_path.stat().st_size,
                crc32=None,
            )["member_occurrence_id"]
            yield (
                raw_header,
                canonical_columns,
                str(member_occurrence_id),
                enumerate(reader, start=2),
                stream,
            )
        finally:
            stream.close()
        return

    archive = zipfile.ZipFile(artifact_path)
    raw = archive.open(COMPREHENSIVE_PRIMARY_MEMBER)
    text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
    reader = _csv_reader(text)
    raw_header = tuple(next(reader))
    members = {
        info.filename: info for info in archive.infolist()
    }
    info = members[COMPREHENSIVE_PRIMARY_MEMBER]
    member_occurrence_id = sha256_fingerprint(
        {
            "artifact_sha256": file_sha256(artifact_path),
            "member_path": COMPREHENSIVE_PRIMARY_MEMBER,
            "member_size": info.file_size,
            "member_crc32": f"{info.CRC:08x}",
        }
    )
    try:
        yield (
            raw_header,
            raw_header,
            member_occurrence_id,
            enumerate(reader, start=2),
            text,
        )
    finally:
        text.close()
        archive.close()


def search_local_artifact(
    path: Path | str,
    query: str,
    *,
    release: Release,
    field: str,
    match: str,
    limit: int | None,
    cursor: str | None,
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any]]:
    if not _clean(query):
        raise MarionDownloadError(
            "Search query must not be blank",
            status=ResultStatus.UNAVAILABLE,
            code="marion_download_query_blank",
            category="query_selection",
        )
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    fields = (
        SALES_SEARCH_FIELDS
        if release.source_id == SALES_SOURCE_ID
        else ASSESSMENT_SEARCH_FIELDS
    )
    if field not in fields:
        raise MarionDownloadError(
            "Search field is not supported by this Marion source",
            details={
                "source_id": release.source_id,
                "field": field,
                "supported_fields": sorted(fields),
            },
            status=ResultStatus.UNAVAILABLE,
            code="marion_download_search_field",
            category="query_selection",
        )
    artifact_path = Path(path).expanduser().resolve()
    inspection = inspect_local_artifact(
        artifact_path,
        release=release,
        scan_rows=False,
    )
    artifact_sha256 = str(inspection["artifact_sha256"])
    criteria_fingerprint = sha256_fingerprint(
        {
            "query": _text_key(query),
            "field": field,
            "match": match,
        }
    )
    start_offset = _search_cursor_start(
        cursor,
        release=release,
        artifact_sha256=artifact_sha256,
        criteria_fingerprint=criteria_fingerprint,
    )
    records: list[dict[str, Any]] = []
    matched = 0
    next_cursor = None
    for (
        raw_header,
        canonical_columns,
        member_occurrence_id,
        row_iterator,
        _resource,
    ) in _open_search_rows(artifact_path, release=release):
        for row_number, values in row_iterator:
            if len(values) != len(canonical_columns):
                raise MarionDownloadError(
                    "CSV row width differs from its selected schema",
                    details={
                        "row_number": row_number,
                        "expected_columns": len(canonical_columns),
                        "observed_columns": len(values),
                    },
                )
            raw = dict(zip(canonical_columns, values, strict=True))
            if not _row_matches(
                raw,
                source_id=release.source_id,
                field=field,
                query=query,
                match=match,
            ):
                continue
            if matched < start_offset:
                matched += 1
                continue
            if limit is not None and len(records) >= limit:
                next_cursor = _next_search_cursor(
                    release=release,
                    artifact_sha256=artifact_sha256,
                    criteria_fingerprint=criteria_fingerprint,
                    match_offset=start_offset + len(records),
                )
                break
            if release.source_id == SALES_SOURCE_ID:
                record = _normalize_sale_row(
                    values,
                    raw_header=raw_header,
                    canonical_columns=canonical_columns,
                    release=release,
                    artifact_sha256=artifact_sha256,
                    member_occurrence_id=member_occurrence_id,
                    row_number=row_number,
                )
            else:
                record = _normalize_assessment_row(
                    values,
                    raw_header=raw_header,
                    release=release,
                    artifact_sha256=artifact_sha256,
                    member_occurrence_id=member_occurrence_id,
                    row_number=row_number,
                )
            records.append(record)
            matched += 1
        if next_cursor is not None:
            break
    return records, next_cursor, inspection


def _validator_occurrence(
    release: Release,
    probe: Mapping[str, Any],
) -> dict[str, Any]:
    payload = {
        "artifact_url": release.url,
        "etag": probe.get("etag"),
        "last_modified": probe.get("last_modified"),
        "content_length": probe.get("content_length"),
    }
    return {
        **payload,
        "validator_occurrence_id": sha256_fingerprint(payload),
        "interchangeable_with_release_slot": False,
    }


def _bulk_client(args: argparse.Namespace) -> BulkTransferClient:
    return BulkTransferClient(
        timeout=args.timeout,
        max_attempts=args.retry_attempts,
        chunk_size=args.chunk_size,
    )


def _resolve_local_artifact(
    args: argparse.Namespace,
    *,
    release: Release,
    transfer: BulkTransferClient,
) -> tuple[Path, DownloadResult | None, dict[str, Any] | None]:
    artifact = _clean(getattr(args, "artifact", None))
    if artifact:
        return Path(artifact).expanduser().resolve(), None, None
    probe = transfer.probe(release.artifact(), sample_bytes=0)
    probe_dict = probe.to_dict()
    occurrence = _validator_occurrence(release, probe_dict)
    cache_dir = Path(args.cache_dir).expanduser().resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / (
        f"{release.release_id}-"
        f"{occurrence['validator_occurrence_id'][:16]}-"
        f"{release.filename}"
    )
    download = transfer.download(
        release.artifact(),
        destination,
        resume=True,
        max_bytes=args.max_download_bytes,
    )
    return Path(download.path), download, occurrence


def source_records() -> list[dict[str, Any]]:
    return [
        {
            "source_id": SALES_SOURCE_ID,
            "record_kind": "source_contract",
            "name": "Marion County Assessor Sales Data",
            "official_url": LANDING_URL,
            "coverage_start": 1940,
            "publication_cadence": "weekly_current_year",
            "operations": [
                "manifest",
                "probe",
                "download",
                "inspect",
                "search",
            ],
            "search_fields": sorted(SALES_SEARCH_FIELDS),
            "schema_profiles": SALES_SCHEMA_PROFILES,
            "identity_contract": {
                "release_slot": [
                    "source_id",
                    "release_id",
                    "artifact_url",
                ],
                "download_occurrence": ["artifact_sha256"],
                "member_occurrence": [
                    "artifact_sha256",
                    "member_path",
                    "member_crc32",
                    "member_size",
                ],
                "row_occurrence": [
                    "member_occurrence_id",
                    "row_number",
                    "raw_row_sha256",
                ],
                "sale_identity": (
                    "publisher_sale_id_or_semantic_sale_fields"
                ),
                "parcel_join": [
                    "assessment_account_id",
                    "map_taxlot",
                ],
                "identities_are_interchangeable": False,
            },
            "source_url": LANDING_URL,
        },
        {
            "source_id": ASSESSMENT_SOURCE_ID,
            "record_kind": "source_contract",
            "name": "Marion County Comprehensive Assessment Download",
            "official_url": LANDING_URL,
            "publication_cadence": (
                "around_monthly_except_October_roll_certification"
            ),
            "operations": [
                "manifest",
                "probe",
                "download",
                "inspect",
                "search",
            ],
            "search_fields": sorted(ASSESSMENT_SEARCH_FIELDS),
            "release_vintage_field": (
                f"{COMPREHENSIVE_PRIMARY_MEMBER}:RDATE"
            ),
            "owner_publication_state": {
                "owner_names_included": False,
                "owner_mailing_addresses_included": False,
                "publisher_omission_effective": "2015-02-01",
            },
            "latest_sale_field_interpretation": {
                "role": "assessor_latest_sale_labels",
                "establishes_current_owner": False,
                "establishes_title": False,
            },
            "identity_contract": {
                "release_slot": [
                    "source_id",
                    "release_id",
                    "artifact_url",
                ],
                "download_occurrence": ["artifact_sha256"],
                "member_occurrence": [
                    "artifact_sha256",
                    "member_path",
                    "member_crc32",
                    "member_size",
                ],
                "row_occurrence": [
                    "member_occurrence_id",
                    "row_number",
                    "raw_row_sha256",
                ],
                "assessment_account": ["ACCOUNT_ID", "RDATE"],
                "parcel_join": [
                    "ACCOUNT_ID",
                    "TXID",
                    "map_components",
                ],
                "identities_are_interchangeable": False,
            },
            "source_url": LANDING_URL,
        },
    ]


def alternative_records() -> list[dict[str, Any]]:
    return [
        {
            "source_id": MARION_PARCELS_SOURCE_ID,
            "name": "Marion County Assessor Parcels",
            "url": (
                "https://services3.arcgis.com/SXXjryU22GsO8OEC/ArcGIS/"
                "rest/services/Parcels/FeatureServer/0"
            ),
            "adds": [
                "current_owner_name",
                "owner_mailing_address",
                "parcel_geometry",
                "current_values",
                "latest_verified_sale_reference",
            ],
            "lineage": "same_county_assessor_different_representation",
            "relationship": (
                "field_oriented_current_complement_not_independent_"
                "assessment_corroboration"
            ),
        },
        {
            "source_id": MARION_PROPERTY_RECORDS_SOURCE_ID,
            "name": "Marion County Assessor Property Records",
            "url": "https://mcasr.co.marion.or.us/",
            "adds": [
                "current_property_account_detail",
                "owner_name",
                "mailing_address",
                "tax_detail",
            ],
            "lineage": "same_county_assessor_current_account_portal",
        },
        {
            "source_id": SALES_SOURCE_ID,
            "name": "Marion County Assessor Sales Data",
            "url": LANDING_URL,
            "adds": ["1940_to_current_assessor_sale_history"],
            "lineage": "county_assessor_sale_index",
            "applies_to": ASSESSMENT_SOURCE_ID,
        },
        {
            "source_id": "us-or-marion-clerk-recorded-documents",
            "name": "Marion County Clerk recorded documents",
            "url": MARION_RECORDED_DOCUMENTS_URL,
            "landing_url": MARION_CLERK_RECORDS_URL,
            "adds": [
                "recorded_instrument_index",
                "document_copy_route",
                "title_affecting_document_evidence",
            ],
            "lineage": "county_clerk_recorded_instrument",
            "relationship": (
                "separate_recorder_lineage_required_to_verify_deed_"
                "references_or_title"
            ),
        },
        {
            "source_id": "us-or-marion-clerk-historical-deeds",
            "name": "Marion County historical deed search",
            "url": MARION_HISTORICAL_DEEDS_URL,
            "coverage": "1855_to_1976_described",
            "adds": ["historical_deed_index"],
            "lineage": "county_clerk_recorded_instrument_archive",
        },
        {
            "source_id": MARION_DATA_REQUEST_SOURCE_ID,
            "name": "Marion County Assessor Data Request",
            "url": "https://apps.co.marion.or.us/AssessorDataRequest/",
            "adds": ["request_defined_assessor_fields"],
            "access": "request_specific_with_published_fees",
        },
    ]


def _build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    source_id = (
        args.source
        if getattr(args, "source", None) in SOURCE_IDS
        else SALES_SOURCE_ID
    )
    parameters: dict[str, Any] = {}
    for name in (
        "source",
        "release",
        "year",
        "query",
        "field",
        "match",
        "artifact",
        "destination",
        "sample_bytes",
    ):
        value = getattr(args, name, None)
        if value is not None:
            parameters[name] = str(value) if isinstance(value, Path) else value
    return PublicRecordsQuery(
        source=_source_metadata(source_id),
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
            metadata={
                "output_schema_version": OUTPUT_SCHEMA_VERSION,
            },
        ),
    )


def _download_record(
    release: Release,
    snapshot: ManifestSnapshot,
    download: DownloadResult,
) -> dict[str, Any]:
    return {
        **release.manifest_record(snapshot),
        "record_kind": "bulk_artifact_download",
        "download": download.to_dict(),
        "release_occurrence_identity": {
            "artifact_sha256": download.sha256,
            "etag": download.etag,
            "last_modified": download.last_modified,
            "size": download.size,
            "interchangeable_with_release_slot": False,
        },
    }


def execute(
    args: argparse.Namespace,
    *,
    manifest_snapshot: ManifestSnapshot | None = None,
    transfer_client: BulkTransferClient | None = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    del access_decision
    query = _build_query(args)
    source_id = str(getattr(args, "source", SALES_SOURCE_ID))
    warnings = SOURCE_WARNINGS.get(source_id, ())
    try:
        if args.command == "sources":
            result = PublicRecordsResult.success(query, source_records())
        elif args.command == "alternatives":
            result = PublicRecordsResult.success(query, alternative_records())
        elif args.command == "inspect":
            release = _local_release(
                source_id=source_id,
                artifact_path=args.artifact,
                release_id=args.release,
                year=args.year,
            )
            inspection = inspect_local_artifact(
                args.artifact,
                release=release,
            )
            result = PublicRecordsResult.success(
                query,
                [
                    {
                        "canonical_ref": canonical_property_ref(
                            source_id,
                            COUNTY_GEOID,
                            "artifact_inspection",
                            str(inspection["artifact_sha256"]),
                        ),
                        "source_id": source_id,
                        "record_kind": "local_artifact_inspection",
                        "inspection": inspection,
                        "source_url": release.url,
                    }
                ],
                raw_artifact_refs=[str(args.artifact)],
                warnings=warnings,
            )
        else:
            snapshot = manifest_snapshot or fetch_release_manifest(
                timeout=args.timeout,
                retry_attempts=args.retry_attempts,
            )
            if args.command == "manifest":
                releases = _selected_releases(
                    snapshot=snapshot,
                    source_id=(
                        None if args.source == "all" else args.source
                    ),
                    release_id=args.release,
                    year=args.year,
                )
                selected, next_cursor = _manifest_page(
                    snapshot,
                    releases,
                    limit=args.limit,
                    cursor=args.cursor,
                )
                result = PublicRecordsResult.success(
                    query,
                    [
                        release.manifest_record(snapshot)
                        for release in selected
                    ],
                    next_cursor=next_cursor,
                )
            else:
                release = _one_release(
                    snapshot=snapshot,
                    source_id=source_id,
                    release_id=args.release,
                    year=args.year,
                )
                transfer = transfer_client or _bulk_client(args)
                if args.command == "probe":
                    probe = transfer.probe(
                        release.artifact(),
                        sample_bytes=args.sample_bytes,
                    )
                    probe_dict = probe.to_dict()
                    result = PublicRecordsResult.success(
                        query,
                        [
                            {
                                **release.manifest_record(snapshot),
                                "record_kind": "source_probe",
                                "probe_schema_version": (
                                    PROBE_SCHEMA_VERSION
                                ),
                                "artifact_probe": probe_dict,
                                "validator_occurrence_identity": (
                                    _validator_occurrence(
                                        release,
                                        probe_dict,
                                    )
                                ),
                                "format_expectation": {
                                    "declared": release.format,
                                    "zip_signature_observed": (
                                        probe.format_hint == "zip"
                                    ),
                                    "csv_header_sample_observed": (
                                        release.format == "csv"
                                        and probe.sample_size > 0
                                    ),
                                },
                            }
                        ],
                        warnings=warnings,
                    )
                elif args.command == "download":
                    artifact = release.artifact()
                    if args.expected_sha256:
                        artifact = BulkArtifact(
                            **{
                                **artifact.to_dict(),
                                "expected_sha256": (
                                    args.expected_sha256
                                ),
                            }
                        )
                    download = transfer.download(
                        artifact,
                        args.destination,
                        resume=args.resume,
                        max_bytes=args.max_download_bytes,
                    )
                    record = _download_record(
                        release,
                        snapshot,
                        download,
                    )
                    if args.inspect:
                        record["inspection"] = inspect_local_artifact(
                            download.path,
                            release=release,
                        )
                    result = PublicRecordsResult.success(
                        query,
                        [record],
                        raw_artifact_refs=[download.path],
                        warnings=warnings,
                    )
                elif args.command == "search":
                    (
                        artifact_path,
                        download,
                        validator_occurrence,
                    ) = _resolve_local_artifact(
                        args,
                        release=release,
                        transfer=transfer,
                    )
                    records, next_cursor, inspection = (
                        search_local_artifact(
                            artifact_path,
                            args.query,
                            release=release,
                            field=args.field,
                            match=args.match,
                            limit=args.limit,
                            cursor=args.cursor,
                        )
                    )
                    if download is not None:
                        for record in records:
                            record["download_occurrence"] = {
                                **download.to_dict(),
                                "validator_identity": (
                                    validator_occurrence
                                ),
                            }
                    if records:
                        records[0]["artifact_inspection_summary"] = {
                            "artifact_sha256": inspection[
                                "artifact_sha256"
                            ],
                            "schema_profile": inspection[
                                "schema_profile"
                            ],
                            "schema_fingerprint": inspection.get(
                                "schema_fingerprint"
                            ),
                        }
                    result = PublicRecordsResult.success(
                        query,
                        records,
                        next_cursor=next_cursor,
                        raw_artifact_refs=[str(artifact_path)],
                        warnings=warnings,
                    )
                else:
                    raise ValueError(
                        f"unsupported Marion download command {args.command}"
                    )
    except MarionDownloadError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=warnings,
        )
    except BulkSourceError as error:
        result = PublicRecordsResult.failure(
            query,
            error.result_status,
            [error.to_contract_error()],
            warnings=warnings,
        )
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="marion_download_operation_failed",
                    message=str(error),
                    category="source_or_query",
                    retryable=False,
                )
            ],
            warnings=warnings,
        )
    if log_results:
        result_count = (
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        )
        log_search(
            canonical_json(result.query.to_dict()),
            source_id,
            result_count,
        )
    return result


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=DEFAULT_RETRY_ATTEMPTS,
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
    )
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=0.0,
        help="Accepted for shared routing; no adapter pacing is added by default",
    )


def _add_release_args(
    parser: argparse.ArgumentParser,
    *,
    source_default: str | None = None,
    allow_all: bool = False,
) -> None:
    parser.add_argument(
        "--source",
        choices=(*SOURCE_IDS, "all") if allow_all else SOURCE_IDS,
        default=source_default,
        required=source_default is None,
    )
    parser.add_argument("--release")
    parser.add_argument("--year", type=int)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Discover and search Marion County assessor public downloads"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="Describe both source contracts",
    )
    sources.set_defaults(source=SALES_SOURCE_ID)
    add_output_args(sources)

    alternatives = sub.add_parser(
        "alternatives",
        help="List field-oriented official complements",
    )
    alternatives.set_defaults(source=SALES_SOURCE_ID)
    add_output_args(alternatives)

    manifest = sub.add_parser(
        "manifest",
        help="Discover the complete official artifact manifest",
    )
    _add_release_args(
        manifest,
        source_default="all",
        allow_all=True,
    )
    manifest.add_argument("--limit", type=int)
    manifest.add_argument("--cursor")
    _add_runtime_args(manifest)
    add_output_args(manifest)

    probe = sub.add_parser(
        "probe",
        help="Probe one selected artifact with a bounded byte sample",
    )
    _add_release_args(probe)
    probe.add_argument(
        "--sample-bytes",
        type=int,
        default=DEFAULT_SAMPLE_BYTES,
    )
    _add_runtime_args(probe)
    add_output_args(probe)

    download = sub.add_parser(
        "download",
        help="Resume and validate one selected artifact transfer",
    )
    _add_release_args(download)
    download.add_argument("--destination", required=True)
    download.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    download.add_argument("--expected-sha256")
    download.add_argument("--max-download-bytes", type=int)
    download.add_argument("--inspect", action="store_true")
    _add_runtime_args(download)
    add_output_args(download)

    inspect_parser = sub.add_parser(
        "inspect",
        help="Inspect a downloaded artifact without network access",
    )
    inspect_parser.add_argument("artifact")
    _add_release_args(inspect_parser)
    _add_runtime_args(inspect_parser)
    add_output_args(inspect_parser)

    search = sub.add_parser(
        "search",
        help="Search a local or automatically cached supported artifact",
    )
    search.add_argument("query")
    _add_release_args(search)
    search.add_argument("--artifact")
    search.add_argument(
        "--field",
        default="any",
        choices=sorted(
            set(SALES_SEARCH_FIELDS) | set(ASSESSMENT_SEARCH_FIELDS)
        ),
    )
    search.add_argument(
        "--match",
        choices=("exact", "prefix", "contains"),
        default="contains",
    )
    search.add_argument("--limit", type=int)
    search.add_argument("--cursor")
    search.add_argument(
        "--cache-dir",
        default=str(DEFAULT_CACHE_DIR),
    )
    search.add_argument("--max-download-bytes", type=int)
    _add_runtime_args(search)
    add_output_args(search)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Marion downloads {args.command} "
            f"({result.status.value})"
        ),
        result_count=(
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Marion downloads {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    for record in result.records:
        label = (
            record.get("native_sale_id")
            or record.get("native_assessment_account_id")
            or record.get("release_id")
            or record.get("record_kind")
        )
        print(f"  {label}")
    for error in result.errors:
        print(
            f"  ERROR {error.code}: {error.message}",
            file=sys.stderr,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "limit", 1) is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if getattr(args, "sample_bytes", 0) < 0:
        parser.error("--sample-bytes must not be negative")
    if getattr(args, "retry_attempts", 1) <= 0:
        parser.error("--retry-attempts must be positive")
    if getattr(args, "chunk_size", 1) <= 0:
        parser.error("--chunk-size must be positive")
    if getattr(args, "max_download_bytes", None) is not None and (
        args.max_download_bytes <= 0
    ):
        parser.error("--max-download-bytes must be positive")
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
