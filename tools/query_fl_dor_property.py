#!/usr/bin/env python3
"""Florida DOR assessment-roll and parcel-GIS bulk release adapter.

The Florida Department of Revenue publishes the current county NAL and SDF
archives and multiple years of county GIS archives through official SharePoint
directories. This adapter discovers those directories at query time and uses
the shared public-records bulk family for fingerprints, bounded probes, and
resumable transfers.

Usage:
    uv run python tools/query_fl_dor_property.py list --type nal
    uv run python tools/query_fl_dor_property.py manifest --type sdf \
        --county Baker --year 2026
    uv run python tools/query_fl_dor_property.py probe --type gis-pin \
        --county 12 --year 2026
    uv run python tools/query_fl_dor_property.py dry-run --type nal \
        --county Baker --destination /tmp/fl-dor
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import time
import zipfile
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_bulk import (
        BulkArtifact,
        BulkDatasetManifest,
        BulkHTTPStatusError,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
        BulkTransportError,
        inspect_zip,
    )
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        acquisition_result_status,
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
    from tools.seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_bulk import (
        BulkArtifact,
        BulkDatasetManifest,
        BulkHTTPStatusError,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
        BulkTransportError,
        inspect_zip,
    )
    from public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        acquisition_result_status,
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
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-fl-dor-property-roll"
SOURCE_PAGE = (
    "https://www.floridarevenue.com/property/Pages/"
    "DataPortal_RequestAssessmentRollGISData.aspx"
)
SHAREPOINT_ORIGIN = "https://www.floridarevenue.com"
SHAREPOINT_API = (
    f"{SHAREPOINT_ORIGIN}/property/dataportal/_api/web"
)
TAX_ROLL_ROOT = (
    "/property/dataportal/Documents/PTO Data Portal/Tax Roll Data Files"
)
MAP_DATA_ROOT = "/property/dataportal/Documents/PTO Data Portal/Map Data"

NAL_SCHEMA_URL = (
    "https://floridarevenue.com/property/Documents/2026NALSummaryTable.pdf"
)
SDF_SCHEMA_URL = (
    "https://floridarevenue.com/property/Documents/2026SDFSummaryTable.pdf"
)
GIS_SCHEMA_URL = (
    "https://floridarevenue.com/property/Documents/2026giseditguide.pdf"
)
GIS_README_URL = (
    "https://www.floridarevenue.com/property/dataportal/Documents/"
    "PTO%20Data%20Portal/Map%20Data/Parcel%20Shapefiles%20Readme.pdf"
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Florida DOR Property Roll and GIS",
    source_role="assessment_sales_parcel_geometry_bulk",
    base_url=SOURCE_PAGE,
    dataset_id="PTO-Data-Portal",
    metadata={
        "authority": "Florida Department of Revenue",
        "release_scope": "county",
        "tax_roll_availability": "current_published_release",
        "gis_availability": "multiple_published_years",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-fl",
    name="Florida",
    state_code="FL",
    metadata={"state_fips": "12"},
)

DATASET_TYPES = ("nal", "sdf", "gis-pin", "gis-par")
MAX_CSV_HEADER_CHARS = 1_000_000
TAX_FOLDER_NAMES = {"nal": "NAL", "sdf": "SDF"}
GIS_VARIANTS = {"gis-pin": "PIN", "gis-par": "PAR"}
RELEASE_FOLDER_RE = re.compile(r"^(?P<year>\d{4})(?P<stage>[PF])$")

# Florida DOR county numbers are distinct from Census county FIPS codes.
COUNTIES = (
    (11, "Alachua"),
    (12, "Baker"),
    (13, "Bay"),
    (14, "Bradford"),
    (15, "Brevard"),
    (16, "Broward"),
    (17, "Calhoun"),
    (18, "Charlotte"),
    (19, "Citrus"),
    (20, "Clay"),
    (21, "Collier"),
    (22, "Columbia"),
    (23, "Dade"),
    (24, "DeSoto"),
    (25, "Dixie"),
    (26, "Duval"),
    (27, "Escambia"),
    (28, "Flagler"),
    (29, "Franklin"),
    (30, "Gadsden"),
    (31, "Gilchrist"),
    (32, "Glades"),
    (33, "Gulf"),
    (34, "Hamilton"),
    (35, "Hardee"),
    (36, "Hendry"),
    (37, "Hernando"),
    (38, "Highlands"),
    (39, "Hillsborough"),
    (40, "Holmes"),
    (41, "Indian River"),
    (42, "Jackson"),
    (43, "Jefferson"),
    (44, "Lafayette"),
    (45, "Lake"),
    (46, "Lee"),
    (47, "Leon"),
    (48, "Levy"),
    (49, "Liberty"),
    (50, "Madison"),
    (51, "Manatee"),
    (52, "Marion"),
    (53, "Martin"),
    (54, "Monroe"),
    (55, "Nassau"),
    (56, "Okaloosa"),
    (57, "Okeechobee"),
    (58, "Orange"),
    (59, "Osceola"),
    (60, "Palm Beach"),
    (61, "Pasco"),
    (62, "Pinellas"),
    (63, "Polk"),
    (64, "Putnam"),
    (65, "Saint Johns"),
    (66, "Saint Lucie"),
    (67, "Santa Rosa"),
    (68, "Sarasota"),
    (69, "Seminole"),
    (70, "Sumter"),
    (71, "Suwannee"),
    (72, "Taylor"),
    (73, "Union"),
    (74, "Volusia"),
    (75, "Wakulla"),
    (76, "Walton"),
    (77, "Washington"),
)


def _county_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


COUNTY_BY_NUMBER = {number: name for number, name in COUNTIES}
COUNTY_NUMBER_BY_KEY = {
    _county_key(name): number for number, name in COUNTIES
}
COUNTY_NUMBER_BY_KEY.update(
    {
        "miamidade": 23,
        "stjohns": 65,
        "stlucie": 66,
    }
)

SOURCE_OMISSIONS = {
    "public_download": (
        "The publisher omits confidential and exempt owner records from public "
        "assessment-roll files."
    ),
    "gis_join_effect": (
        "A published parcel polygon can therefore lack a matching public NAL row."
    ),
    "representation": "publisher_omitted_records_remain_absent",
    "source_page": SOURCE_PAGE,
    "gis_readme": GIS_README_URL,
}

NAL_SCHEMA = {
    "schema_year": 2026,
    "format": "comma_delimited",
    "documentation_url": NAL_SCHEMA_URL,
    "documented_logical_field_count": 92,
    "field_count_semantics": (
        "The summary-table PDF numbers 92 logical fields. Published CSV "
        "archives can expand repeating groups into additional physical "
        "columns and omit nonpublic fields."
    ),
    "join": {
        "nal_field": "PARCEL_ID",
        "nal_position": 2,
        "gis_field": "PARCELNO",
    },
    "documented_key_fields": [
        {"position": 1, "name": "COUNTY_NUMBER", "type": "numeric"},
        {"position": 2, "name": "PARCEL_ID", "type": "alphanumeric"},
        {"position": 3, "name": "FILE_TYPE", "type": "alphabetical"},
        {"position": 4, "name": "ASSESSMENT_YEAR", "type": "numeric"},
        {"position": 5, "name": "DOR_LAND_USE_CODE", "type": "numeric"},
        {"position": 8, "name": "TOTAL_JUST_VALUE", "type": "numeric"},
        {"position": 38, "name": "LAND_VALUE", "type": "numeric"},
        {"position": 44, "name": "EFFECTIVE_YEAR_BUILT", "type": "numeric"},
        {"position": 45, "name": "ACTUAL_YEAR_BUILT", "type": "numeric"},
        {"position": 51, "name": "OWNER_NAME", "type": "alphanumeric"},
        {"position": 52, "name": "OWNER_ADDRESS_1", "type": "alphanumeric"},
        {"position": 53, "name": "OWNER_ADDRESS_2", "type": "alphanumeric"},
        {"position": 54, "name": "OWNER_CITY", "type": "alphanumeric"},
        {"position": 55, "name": "OWNER_STATE_OR_COUNTRY", "type": "alphabetical"},
        {"position": 56, "name": "OWNER_US_ZIP", "type": "numeric"},
        {"position": 65, "name": "SHORT_LEGAL_DESCRIPTION", "type": "alphanumeric"},
        {"position": 70, "name": "CONFIDENTIALITY_CODE", "type": "numeric"},
        {"position": 79, "name": "PHYSICAL_ADDRESS_1", "type": "alphanumeric"},
        {"position": 80, "name": "PHYSICAL_ADDRESS_2", "type": "alphanumeric"},
        {"position": 81, "name": "PHYSICAL_CITY", "type": "alphanumeric"},
        {"position": 82, "name": "PHYSICAL_US_ZIP", "type": "numeric"},
        {"position": 83, "name": "ALTERNATE_KEY", "type": "alphanumeric"},
        {"position": 91, "name": "PARCEL_ID_CHANGE", "type": "alphanumeric"},
        {"position": 92, "name": "FILE_SEQUENCE_NUMBER", "type": "alphanumeric"},
    ],
    "published_csv": {
        "header_row": True,
        "sampled_release": "2026P",
        "sampled_physical_field_count": 165,
        "sampled_key_columns": [
            {"position": 1, "name": "CO_NO", "role": "county_number"},
            {"position": 2, "name": "PARCEL_ID", "role": "parcel_id"},
            {"position": 3, "name": "FILE_T", "role": "file_type"},
            {"position": 4, "name": "ASMNT_YR", "role": "assessment_year"},
            {"position": 8, "name": "DOR_UC", "role": "dor_land_use_code"},
            {"position": 11, "name": "JV", "role": "total_just_value"},
            {"position": 41, "name": "LND_VAL", "role": "land_value"},
            {
                "position": 48,
                "name": "EFF_YR_BLT",
                "role": "effective_year_built",
            },
            {
                "position": 49,
                "name": "ACT_YR_BLT",
                "role": "actual_year_built",
            },
            {"position": 74, "name": "OWN_NAME", "role": "owner_name"},
            {"position": 75, "name": "OWN_ADDR1", "role": "owner_address_1"},
            {"position": 76, "name": "OWN_ADDR2", "role": "owner_address_2"},
            {"position": 77, "name": "OWN_CITY", "role": "owner_city"},
            {"position": 78, "name": "OWN_STATE", "role": "owner_state"},
            {"position": 79, "name": "OWN_ZIPCD", "role": "owner_zip"},
            {"position": 88, "name": "S_LEGAL", "role": "short_legal"},
            {"position": 99, "name": "PHY_ADDR1", "role": "situs_address_1"},
            {"position": 100, "name": "PHY_ADDR2", "role": "situs_address_2"},
            {"position": 101, "name": "PHY_CITY", "role": "situs_city"},
            {"position": 102, "name": "PHY_ZIPCD", "role": "situs_zip"},
            {"position": 103, "name": "ALT_KEY", "role": "alternate_key"},
            {"position": 159, "name": "SEQ_NO", "role": "file_sequence"},
            {"position": 162, "name": "STATE_PAR_ID", "role": "state_parcel_id"},
        ],
    },
}

NAL_REQUIRED_PUBLIC_COLUMNS = frozenset(
    {
        "CO_NO",
        "PARCEL_ID",
        "FILE_T",
        "ASMNT_YR",
        "DOR_UC",
        "JV",
        "LND_VAL",
        "OWN_NAME",
        "OWN_ADDR1",
        "OWN_CITY",
        "S_LEGAL",
        "PHY_ADDR1",
        "PHY_CITY",
        "ALT_KEY",
        "SEQ_NO",
    }
)

SDF_SCHEMA = {
    "schema_year": 2026,
    "format": "comma_delimited",
    "documentation_url": SDF_SCHEMA_URL,
    "documented_logical_field_count": 14,
    "field_count_semantics": (
        "The summary-table PDF describes 14 logical sale fields. Published "
        "CSV archives include county, parcel, and grouping context as "
        "additional physical columns."
    ),
    "documented_fields": [
        {"position": 1, "name": "FILE_TYPE", "type": "alphabetical"},
        {"position": 2, "name": "COUNTY_NUMBER", "type": "numeric"},
        {"position": 3, "name": "PARCEL_ID", "type": "alphanumeric"},
        {"position": 4, "name": "ASSESSMENT_YEAR", "type": "numeric"},
        {"position": 5, "name": "TRANSFER_QUALIFICATION_CODE", "type": "numeric"},
        {"position": 6, "name": "VACANT_OR_IMPROVED", "type": "alphabetical"},
        {"position": 7, "name": "SALE_PROPERTY_CHANGE_CODE", "type": "numeric"},
        {"position": 8, "name": "SALE_PRICE", "type": "numeric"},
        {"position": 9, "name": "SALE_YEAR", "type": "numeric"},
        {"position": 10, "name": "SALE_MONTH", "type": "numeric"},
        {"position": 11, "name": "OFFICIAL_RECORD_BOOK", "type": "alphanumeric"},
        {"position": 12, "name": "OFFICIAL_RECORD_PAGE", "type": "alphanumeric"},
        {"position": 13, "name": "CLERK_INSTRUMENT_NUMBER", "type": "numeric"},
        {"position": 14, "name": "SALE_IDENTIFICATION_CODE", "type": "alphanumeric"},
    ],
    "published_csv": {
        "header_row": True,
        "sampled_release": "2026P",
        "sampled_physical_field_count": 23,
        "sampled_columns": [
            "CO_NO",
            "PARCEL_ID",
            "ASMNT_YR",
            "ATV_STRT",
            "GRP_NO",
            "DOR_UC",
            "NBRHD_CD",
            "MKT_AR",
            "CENSUS_BK",
            "SALE_ID_CD",
            "SAL_CHG_CD",
            "VI_CD",
            "OR_BOOK",
            "OR_PAGE",
            "CLERK_NO",
            "QUAL_CD",
            "SALE_YR",
            "SALE_MO",
            "SALE_PRC",
            "MULTI_PAR_SAL",
            "RS_ID",
            "MP_ID",
            "STATE_PARCEL_ID",
        ],
    },
}

SDF_REQUIRED_PUBLIC_COLUMNS = frozenset(
    {
        "CO_NO",
        "PARCEL_ID",
        "ASMNT_YR",
        "SALE_ID_CD",
        "SAL_CHG_CD",
        "VI_CD",
        "OR_BOOK",
        "OR_PAGE",
        "CLERK_NO",
        "QUAL_CD",
        "SALE_YR",
        "SALE_MO",
        "SALE_PRC",
        "MULTI_PAR_SAL",
    }
)

GIS_SCHEMA = {
    "schema_year": 2026,
    "format": "esri_shapefile_zip",
    "minimum_fields": [
        {"name": "FID", "role": "feature_identifier"},
        {"name": "Shape", "role": "parcel_geometry"},
        {"name": "PARCELNO", "role": "nal_join_key", "maximum_length": 26},
    ],
    "pin": "Parcel geometry with the minimum published GIS fields.",
    "par": "PIN geometry joined by the publisher to a current public NAL roll.",
    "documentation_url": GIS_SCHEMA_URL,
    "readme_url": GIS_README_URL,
}


class FloridaDORSchemaError(BulkSourceError):
    """The official directory response no longer has the expected shape."""

    result_status = ResultStatus.SOURCE_CHANGED
    code = "fl_dor_directory_schema_changed"
    category = "source_schema"


class FloridaDORSelectorError(BulkSourceError):
    """A county or release selector could not be resolved."""

    result_status = ResultStatus.UNAVAILABLE
    code = "fl_dor_selector_unresolved"
    category = "query"


def _inspect_public_csv_archive(
    path: str | Path,
    *,
    dataset_label: str,
    required_columns: frozenset[str],
    documented_logical_field_count: int,
) -> dict[str, Any]:
    """Read and validate one bounded header row from a DOR CSV archive."""

    display_label = dataset_label.upper()
    archive_path = Path(path)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            csv_members = [
                member
                for member in archive.infolist()
                if not member.is_dir() and member.filename.casefold().endswith(".csv")
            ]
            if len(csv_members) != 1:
                raise FloridaDORSchemaError(
                    f"Florida DOR {display_label} archive must contain one "
                    "CSV member",
                    details={
                        "dataset_type": dataset_label,
                        "archive_path": str(archive_path),
                        "csv_members": [
                            member.filename for member in csv_members
                        ],
                    },
                )
            member = csv_members[0]
            with archive.open(member) as raw:
                with io.TextIOWrapper(
                    raw,
                    encoding="utf-8-sig",
                    errors="strict",
                    newline="",
                ) as text:
                    header_line = text.readline(MAX_CSV_HEADER_CHARS + 1)
                    if len(header_line) > MAX_CSV_HEADER_CHARS:
                        raise FloridaDORSchemaError(
                            f"Florida DOR {display_label} CSV header exceeds "
                            "the bounded inspection size",
                            details={
                                "dataset_type": dataset_label,
                                "maximum_header_chars": (
                                    MAX_CSV_HEADER_CHARS
                                ),
                            },
                        )
                    header = next(csv.reader([header_line]), None)
    except FloridaDORSchemaError:
        raise
    except (
        csv.Error,
        OSError,
        UnicodeDecodeError,
        zipfile.BadZipFile,
    ) as error:
        raise FloridaDORSchemaError(
            f"Florida DOR {display_label} CSV header could not be read",
            details={
                "dataset_type": dataset_label,
                "archive_path": str(archive_path),
                "error": str(error),
            },
        ) from error

    fields = [value.strip() for value in (header or [])]
    if not fields or any(not value for value in fields):
        raise FloridaDORSchemaError(
            f"Florida DOR {display_label} CSV header is empty or contains "
            "blank columns",
            details={
                "dataset_type": dataset_label,
                "archive_path": str(archive_path),
            },
        )
    duplicates = sorted(
        field for field, count in Counter(fields).items() if count > 1
    )
    if duplicates:
        raise FloridaDORSchemaError(
            f"Florida DOR {display_label} CSV header contains duplicate "
            "columns",
            details={
                "dataset_type": dataset_label,
                "duplicates": duplicates,
            },
        )
    missing = sorted(required_columns - set(fields))
    if missing:
        raise FloridaDORSchemaError(
            f"Florida DOR {display_label} CSV header lacks projection columns",
            details={
                "dataset_type": dataset_label,
                "archive_path": str(archive_path),
                "missing_columns": missing,
                "observed_field_count": len(fields),
            },
        )

    return {
        "member": member.filename,
        "dataset_type": dataset_label,
        "encoding": "utf-8-sig",
        "header_row": True,
        "header_read_limit_chars": MAX_CSV_HEADER_CHARS,
        "physical_field_count": len(fields),
        "header_fields": fields,
        "header_fingerprint": sha256_fingerprint(fields),
        "documented_logical_field_count": documented_logical_field_count,
        "required_projection_columns": sorted(required_columns),
        "required_projection_columns_present": True,
    }


def inspect_nal_csv_archive(path: str | Path) -> dict[str, Any]:
    """Read the bounded header row from one downloaded public NAL archive."""

    return _inspect_public_csv_archive(
        path,
        dataset_label="nal",
        required_columns=NAL_REQUIRED_PUBLIC_COLUMNS,
        documented_logical_field_count=int(
            NAL_SCHEMA["documented_logical_field_count"]
        ),
    )


def inspect_sdf_csv_archive(path: str | Path) -> dict[str, Any]:
    """Read the bounded header row from one downloaded public SDF archive."""

    return _inspect_public_csv_archive(
        path,
        dataset_label="sdf",
        required_columns=SDF_REQUIRED_PUBLIC_COLUMNS,
        documented_logical_field_count=int(
            SDF_SCHEMA["documented_logical_field_count"]
        ),
    )


class FloridaDORDirectoryClient:
    """Small retrying client for Florida DOR's public SharePoint directories."""

    def __init__(
        self,
        *,
        timeout: float = 60.0,
        max_attempts: int = 3,
        minimum_interval: float = 0.0,
        opener=urlopen,
        sleeper=time.sleep,
        clock=time.monotonic,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if minimum_interval < 0:
            raise ValueError("minimum_interval must not be negative")
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.minimum_interval = minimum_interval
        self._opener = opener
        self._sleeper = sleeper
        self._clock = clock
        self._last_request_at: float | None = None

    def _wait(self) -> None:
        if self._last_request_at is not None:
            remaining = self.minimum_interval - (
                self._clock() - self._last_request_at
            )
            if remaining > 0:
                self._sleeper(remaining)
        self._last_request_at = self._clock()

    @staticmethod
    def _collection_url(
        server_relative_path: str,
        collection: str,
    ) -> str:
        escaped_path = server_relative_path.replace("'", "''")
        encoded_path = quote(escaped_path, safe="/")
        fields = (
            "Name,ServerRelativeUrl,TimeLastModified,ItemCount"
            if collection == "Folders"
            else "Name,ServerRelativeUrl,TimeLastModified,Length"
        )
        return (
            f"{SHAREPOINT_API}/GetFolderByServerRelativeUrl"
            f"(%27{encoded_path}%27)/{collection}"
            f"?$select={fields}&$orderby=Name"
        )

    def _get_json(self, url: str) -> Mapping[str, Any]:
        last_error: BulkSourceError | None = None
        for attempt in range(1, self.max_attempts + 1):
            self._wait()
            request = Request(
                url,
                headers={
                    "Accept": "application/json;odata=nometadata",
                    "User-Agent": "Ithildin-Public-Records/1.0",
                },
                method="GET",
            )
            try:
                with self._opener(request, timeout=self.timeout) as response:
                    status = int(getattr(response, "status", 200))
                    if status < 200 or status >= 300:
                        raise BulkHTTPStatusError(status, url)
                    try:
                        payload = json.loads(
                            response.read().decode("utf-8", errors="replace")
                        )
                    except (UnicodeDecodeError, json.JSONDecodeError) as error:
                        raise FloridaDORSchemaError(
                            "Florida DOR directory did not return JSON",
                            details={"url": url},
                        ) from error
                    if not isinstance(payload, Mapping):
                        raise FloridaDORSchemaError(
                            "Florida DOR directory response is not an object",
                            details={"url": url},
                        )
                    return payload
            except HTTPError as error:
                body = error.read(500).decode("utf-8", errors="replace")
                last_error = BulkHTTPStatusError(
                    error.code,
                    url,
                    body,
                )
            except (URLError, TimeoutError, ConnectionError, OSError) as error:
                last_error = BulkTransportError(
                    f"Florida DOR directory request failed: {error}",
                    details={"url": url},
                )
            except BulkSourceError as error:
                last_error = error
            if (
                last_error is None
                or not last_error.retryable
                or attempt >= self.max_attempts
            ):
                assert last_error is not None
                raise last_error
            self._sleeper(min(0.25 * (2 ** (attempt - 1)), 5.0))
        assert last_error is not None
        raise last_error

    def _collection(
        self,
        path: str,
        collection: str,
    ) -> list[dict[str, Any]]:
        url: str | None = self._collection_url(path, collection)
        records: list[dict[str, Any]] = []
        while url is not None:
            payload = self._get_json(url)
            values = payload.get("value")
            if not isinstance(values, list) or any(
                not isinstance(value, Mapping) for value in values
            ):
                raise FloridaDORSchemaError(
                    "Florida DOR directory response lacks a value array",
                    details={"url": url},
                )
            records.extend(dict(value) for value in values)
            next_url = payload.get("@odata.nextLink")
            if next_url is not None and not isinstance(next_url, str):
                raise FloridaDORSchemaError(
                    "Florida DOR directory next link is not text",
                    details={"url": url},
                )
            url = next_url
        records.sort(key=lambda row: str(row.get("Name", "")).casefold())
        return records

    def list_folders(self, path: str) -> list[dict[str, Any]]:
        return self._collection(path, "Folders")

    def list_files(self, path: str) -> list[dict[str, Any]]:
        return self._collection(path, "Files")


def _directory_client(args: argparse.Namespace) -> FloridaDORDirectoryClient:
    return FloridaDORDirectoryClient(
        timeout=args.timeout,
        max_attempts=args.retry_attempts,
        minimum_interval=args.minimum_interval,
    )


def _bulk_client(args: argparse.Namespace) -> BulkTransferClient:
    return BulkTransferClient(
        timeout=args.timeout,
        max_attempts=args.retry_attempts,
        chunk_size=getattr(args, "chunk_size", 1024 * 1024),
    )


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog_db = Path(args.catalog_db).expanduser()
    catalog_config = Path(args.catalog_config).expanduser()
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=catalog_db,
        config_path=catalog_config,
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _stage_name(stage_code: str) -> str:
    return "preliminary" if stage_code == "P" else "final"


def _schema(dataset_type: str) -> Mapping[str, Any]:
    if dataset_type == "nal":
        return NAL_SCHEMA
    if dataset_type == "sdf":
        return SDF_SCHEMA
    return {**GIS_SCHEMA, "variant": GIS_VARIANTS[dataset_type]}


def _source_directory_url(path: str) -> str:
    encoded = quote(path, safe="/")
    return (
        f"{SHAREPOINT_ORIGIN}/property/dataportal/Pages/default.aspx"
        f"?path={encoded}"
    )


def _download_url(server_relative_url: str) -> str:
    return f"{SHAREPOINT_ORIGIN}{quote(server_relative_url, safe='/')}"


def _normalize_release_folder(
    *,
    dataset_type: str,
    row: Mapping[str, Any],
    item_count: int | None = None,
) -> dict[str, Any] | None:
    name = str(row.get("Name") or "")
    match = RELEASE_FOLDER_RE.fullmatch(name)
    if match is None:
        return None
    year = int(match.group("year"))
    stage_code = match.group("stage")
    path = str(row.get("ServerRelativeUrl") or "")
    release = {
        "release_id": f"{dataset_type}:{name}",
        "dataset_type": dataset_type,
        "assessment_year": year,
        "submission_code": stage_code,
        "submission_stage": _stage_name(stage_code),
        "server_relative_path": path,
        "directory_url": _source_directory_url(path),
        "last_modified": row.get("TimeLastModified"),
        "artifact_count": (
            item_count if item_count is not None else row.get("ItemCount")
        ),
        "schema": _schema(dataset_type),
        "source_omissions": SOURCE_OMISSIONS,
    }
    release["release_fingerprint"] = sha256_fingerprint(release)
    return release


def _release_directories(
    client: FloridaDORDirectoryClient,
    dataset_type: str,
) -> list[dict[str, Any]]:
    if dataset_type in TAX_FOLDER_NAMES:
        folder = TAX_FOLDER_NAMES[dataset_type]
        rows = client.list_folders(f"{TAX_ROLL_ROOT}/{folder}")
        releases = [
            release
            for row in rows
            if (
                release := _normalize_release_folder(
                    dataset_type=dataset_type,
                    row=row,
                )
            )
            is not None
        ]
    else:
        variant = GIS_VARIANTS[dataset_type]
        releases = []
        for year_row in client.list_folders(MAP_DATA_ROOT):
            name = str(year_row.get("Name") or "")
            match = RELEASE_FOLDER_RE.fullmatch(name)
            if match is None:
                continue
            subfolder_name = f"{name} {variant}"
            subfolders = client.list_folders(
                str(year_row["ServerRelativeUrl"])
            )
            subfolder = next(
                (
                    row
                    for row in subfolders
                    if str(row.get("Name")) == subfolder_name
                ),
                None,
            )
            if subfolder is None:
                continue
            release = _normalize_release_folder(
                dataset_type=dataset_type,
                row={
                    **dict(year_row),
                    "ServerRelativeUrl": subfolder["ServerRelativeUrl"],
                    "TimeLastModified": subfolder.get("TimeLastModified"),
                },
                item_count=int(subfolder.get("ItemCount") or 0),
            )
            if release is not None:
                releases.append(release)
    releases.sort(
        key=lambda release: (
            release["assessment_year"],
            release["submission_code"],
            release["dataset_type"],
        )
    )
    return releases


def _selected_releases(
    client: FloridaDORDirectoryClient,
    *,
    dataset_types: Sequence[str],
    year: int | None,
    latest_only: bool,
) -> list[dict[str, Any]]:
    selected = []
    for dataset_type in dataset_types:
        releases = _release_directories(client, dataset_type)
        if year is not None:
            releases = [
                release
                for release in releases
                if release["assessment_year"] == year
            ]
        elif latest_only and releases:
            latest_year = max(
                release["assessment_year"] for release in releases
            )
            releases = [
                release
                for release in releases
                if release["assessment_year"] == latest_year
            ]
        selected.extend(releases)
    selected.sort(key=lambda release: release["release_id"])
    return selected


def _county_from_selector(value: str | None) -> tuple[int, str] | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    if not cleaned:
        raise FloridaDORSelectorError("county selector is blank")
    if cleaned.isdigit():
        number = int(cleaned)
    else:
        number = COUNTY_NUMBER_BY_KEY.get(_county_key(cleaned), -1)
    if number not in COUNTY_BY_NUMBER:
        raise FloridaDORSelectorError(
            f"unknown Florida DOR county selector: {value}",
            details={"county": value},
        )
    return number, COUNTY_BY_NUMBER[number]


def _county_from_filename_prefix(
    prefix: str,
) -> tuple[int, str, int | None]:
    parts = prefix.rsplit(" ", 1)
    published_number = (
        int(parts[1])
        if len(parts) == 2 and re.fullmatch(r"\d{2}", parts[1])
        else None
    )
    county_text = parts[0] if published_number is not None else prefix
    canonical_number = COUNTY_NUMBER_BY_KEY.get(_county_key(county_text))
    if canonical_number is None:
        raise FloridaDORSchemaError(
            f"unrecognized county in Florida DOR artifact: {county_text}",
            details={"filename_prefix": prefix},
        )
    return (
        canonical_number,
        COUNTY_BY_NUMBER[canonical_number],
        published_number,
    )


def _tax_file_metadata(
    row: Mapping[str, Any],
    dataset_type: str,
) -> dict[str, Any]:
    name = str(row.get("Name") or "")
    suffix = re.search(
        r" (?P<stage>Preliminary|Final) "
        rf"(?P<kind>{dataset_type.upper()}) "
        r"(?P<year>\d{4})\.zip$",
        name,
        flags=re.IGNORECASE,
    )
    if suffix is None:
        raise FloridaDORSchemaError(
            "Florida DOR tax-roll filename no longer matches its published pattern",
            details={"filename": name},
        )
    prefix = name[: suffix.start()]
    county_number, county_name, published_number = _county_from_filename_prefix(
        prefix
    )
    stage = suffix.group("stage").casefold()
    return {
        "county_number": county_number,
        "county_name": county_name,
        "published_county_number": published_number,
        "published_county_number_matches": (
            None
            if published_number is None
            else published_number == county_number
        ),
        "assessment_year": int(suffix.group("year")),
        "submission_stage": stage,
        "submission_code": "P" if stage == "preliminary" else "F",
        "artifact_role": dataset_type,
    }


def _gis_file_metadata(
    row: Mapping[str, Any],
    dataset_type: str,
) -> dict[str, Any]:
    name = str(row.get("Name") or "")
    variant = GIS_VARIANTS[dataset_type].casefold()
    standard = re.fullmatch(
        rf"(?P<county>.+)_(?P<year>\d{{4}}){variant}(?:\.shp)?\.zip",
        name,
        flags=re.IGNORECASE,
    )
    related = re.fullmatch(
        r"(?P<county>miamidade|stjohns)_?condos?_(?P<year>\d{4})\.zip",
        name,
        flags=re.IGNORECASE,
    )
    match = standard or related
    if match is None:
        raise FloridaDORSchemaError(
            "Florida DOR GIS filename no longer matches a published pattern",
            details={"filename": name, "dataset_type": dataset_type},
        )
    county_number = COUNTY_NUMBER_BY_KEY.get(
        _county_key(match.group("county"))
    )
    if county_number is None:
        raise FloridaDORSchemaError(
            "Florida DOR GIS filename contains an unknown county",
            details={"filename": name},
        )
    return {
        "county_number": county_number,
        "county_name": COUNTY_BY_NUMBER[county_number],
        "published_county_number": None,
        "published_county_number_matches": None,
        "assessment_year": int(match.group("year")),
        "submission_stage": "final",
        "submission_code": "F",
        "artifact_role": (
            f"{dataset_type}-related-table"
            if related is not None
            else dataset_type
        ),
    }


def _manifest_record(
    *,
    release: Mapping[str, Any],
    file_row: Mapping[str, Any],
) -> dict[str, Any]:
    dataset_type = str(release["dataset_type"])
    metadata = (
        _tax_file_metadata(file_row, dataset_type)
        if dataset_type in TAX_FOLDER_NAMES
        else _gis_file_metadata(file_row, dataset_type)
    )
    filename = str(file_row["Name"])
    server_relative_url = str(file_row["ServerRelativeUrl"])
    artifact = BulkArtifact(
        artifact_id=metadata["artifact_role"],
        url=_download_url(server_relative_url),
        filename=filename,
        media_type="application/zip",
        archive_format="zip",
        expected_size=int(file_row["Length"]),
        last_modified=(
            str(file_row["TimeLastModified"])
            if file_row.get("TimeLastModified")
            else None
        ),
        metadata={
            **metadata,
            "server_relative_url": server_relative_url,
        },
    )
    release_id = (
        f"{dataset_type}:{metadata['assessment_year']}"
        f"{metadata['submission_code']}:{metadata['county_number']:02d}:"
        f"{metadata['artifact_role']}"
    )
    manifest = BulkDatasetManifest(
        source_id=SOURCE_ID,
        dataset_id=f"Florida-DOR-{dataset_type}",
        release=BulkReleaseMetadata(
            release_id=release_id,
            kind="snapshot",
            effective_at=(
                str(file_row["TimeLastModified"])
                if file_row.get("TimeLastModified")
                else None
            ),
            coverage={
                "state": "Florida",
                "county_name": metadata["county_name"],
                "county_dor_number": metadata["county_number"],
                "assessment_year": metadata["assessment_year"],
                "submission_stage": metadata["submission_stage"],
                "dataset_type": dataset_type,
                "artifact_role": metadata["artifact_role"],
            },
        ),
        artifacts=[artifact],
        schema=_schema(dataset_type),
        metadata={
            "release_directory": {
                key: release.get(key)
                for key in (
                    "release_id",
                    "server_relative_path",
                    "directory_url",
                    "last_modified",
                    "artifact_count",
                    "release_fingerprint",
                )
            },
            "published_filename_county_number": metadata[
                "published_county_number"
            ],
            "published_filename_county_number_matches": metadata[
                "published_county_number_matches"
            ],
            "source_omissions": SOURCE_OMISSIONS,
            "source_page": SOURCE_PAGE,
        },
    )
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            "12",
            "bulk_release",
            release_id,
        ),
        "county_name": metadata["county_name"],
        "county_dor_number": metadata["county_number"],
        "assessment_year": metadata["assessment_year"],
        "dataset_type": dataset_type,
        "submission_stage": metadata["submission_stage"],
        "artifact_role": metadata["artifact_role"],
        "published_filename_county_number": metadata[
            "published_county_number"
        ],
        "published_filename_county_number_matches": metadata[
            "published_county_number_matches"
        ],
        "manifest": manifest.to_dict(),
    }


def _fetch_manifest_records(
    client: FloridaDORDirectoryClient,
    *,
    dataset_types: Sequence[str],
    year: int | None,
    county: tuple[int, str] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    releases = _selected_releases(
        client,
        dataset_types=dataset_types,
        year=year,
        latest_only=True,
    )
    records: list[dict[str, Any]] = []
    warnings = []
    for release in releases:
        files = client.list_files(str(release["server_relative_path"]))
        if not files:
            warnings.append(
                f"{release['release_id']} directory currently contains no artifacts"
            )
        for file_row in files:
            record = _manifest_record(
                release=release,
                file_row=file_row,
            )
            if county is not None and record["county_dor_number"] != county[0]:
                continue
            records.append(record)
    records.sort(
        key=lambda record: (
            record["dataset_type"],
            record["assessment_year"],
            record["county_dor_number"],
            record["artifact_role"],
        )
    )
    return records, warnings


def _paginate(
    records: Sequence[Mapping[str, Any]],
    *,
    limit: int | None,
    cursor: str | None,
) -> tuple[list[Mapping[str, Any]], str | None]:
    if cursor is None:
        offset = 0
    else:
        try:
            offset = int(cursor)
        except ValueError as error:
            raise FloridaDORSelectorError(
                "cursor must be a non-negative integer offset",
                details={"cursor": cursor},
            ) from error
        if offset < 0:
            raise FloridaDORSelectorError(
                "cursor must be a non-negative integer offset",
                details={"cursor": cursor},
            )
    end = len(records) if limit is None else offset + limit
    selected = list(records[offset:end])
    next_cursor = str(end) if end < len(records) else None
    return selected, next_cursor


def _select_exact_artifact(
    records: Sequence[Mapping[str, Any]],
    *,
    dataset_type: str,
    county: tuple[int, str],
) -> tuple[Mapping[str, Any], BulkArtifact]:
    exact = [
        record
        for record in records
        if record["dataset_type"] == dataset_type
        and record["county_dor_number"] == county[0]
        and not str(record["artifact_role"]).endswith("related-table")
    ]
    if not exact:
        raise FloridaDORSelectorError(
            "No published artifact matches the requested release selectors",
            details={
                "dataset_type": dataset_type,
                "county_dor_number": county[0],
                "county_name": county[1],
            },
        )
    if len(exact) != 1:
        raise FloridaDORSelectorError(
            "Release selectors resolve to more than one artifact; add a year",
            details={"matches": len(exact)},
        )
    record = exact[0]
    artifact_data = record["manifest"]["artifacts"][0]
    artifact = BulkArtifact(
        artifact_id=artifact_data["artifact_id"],
        url=artifact_data["url"],
        filename=artifact_data["filename"],
        media_type=artifact_data.get("media_type"),
        archive_format=artifact_data.get("archive_format"),
        expected_size=artifact_data.get("expected_size"),
        expected_sha256=artifact_data.get("expected_sha256"),
        etag=artifact_data.get("etag"),
        last_modified=artifact_data.get("last_modified"),
        metadata=artifact_data.get("metadata") or {},
    )
    return record, artifact


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters = {
        key: value
        for key, value in (
            ("dataset_type", getattr(args, "dataset_type", None)),
            ("county", getattr(args, "county", None)),
            ("year", getattr(args, "year", None)),
            ("destination", getattr(args, "destination", None)),
            ("range_bytes", getattr(args, "range_bytes", None)),
            ("resume", getattr(args, "resume", None)),
            ("max_download_bytes", getattr(args, "max_download_bytes", None)),
            ("dry_run", getattr(args, "dry_run", None)),
        )
        if value is not None
    }
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _access_failure(
    query: PublicRecordsQuery,
    error: AcquisitionUnavailableError,
) -> PublicRecordsResult:
    decision = error.decision
    status = ResultStatus(acquisition_result_status(decision))
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code")
                    or "machine_acquisition_denied"
                ),
                message=str(error),
                category="access_policy",
                details=decision,
            )
        ],
    )


def execute(
    args: argparse.Namespace,
    *,
    access_contract: Mapping[str, Any] | None = None,
    directory_client: FloridaDORDirectoryClient | None = None,
    bulk_client: BulkTransferClient | None = None,
) -> PublicRecordsResult:
    """Execute one release-directory or artifact operation."""
    query = build_query(args)
    try:
        if access_contract is None:
            access_contract = _access_contract(args)
        del access_contract  # The catalog decision is the only access preflight.
        directory = directory_client or _directory_client(args)
        dataset_types = (
            [args.dataset_type]
            if getattr(args, "dataset_type", None)
            else list(DATASET_TYPES)
        )
        county = _county_from_selector(getattr(args, "county", None))

        if args.command == "list":
            releases = _selected_releases(
                directory,
                dataset_types=dataset_types,
                year=args.year,
                latest_only=False,
            )
            selected, next_cursor = _paginate(
                releases,
                limit=args.limit,
                cursor=args.cursor,
            )
            result = PublicRecordsResult.success(
                query,
                selected,
                next_cursor=next_cursor,
            )
        else:
            records, warnings = _fetch_manifest_records(
                directory,
                dataset_types=dataset_types,
                year=args.year,
                county=county,
            )
            if args.command == "manifest":
                selected, next_cursor = _paginate(
                    records,
                    limit=args.limit,
                    cursor=args.cursor,
                )
                result = PublicRecordsResult.success(
                    query,
                    selected,
                    next_cursor=next_cursor,
                    warnings=warnings,
                )
            else:
                assert county is not None
                record, artifact = _select_exact_artifact(
                    records,
                    dataset_type=args.dataset_type,
                    county=county,
                )
                transfer = bulk_client or _bulk_client(args)
                if args.command == "probe":
                    probe = transfer.probe(
                        artifact,
                        sample_bytes=args.range_bytes,
                    )
                    result = PublicRecordsResult.success(
                        query,
                        [
                            {
                                **record,
                                "selected_artifact": artifact.to_dict(),
                                "probe": probe.to_dict(),
                            }
                        ],
                        warnings=warnings,
                    )
                elif args.command == "dry-run" or getattr(
                    args, "dry_run", False
                ):
                    destination = Path(args.destination)
                    if destination.exists() and destination.is_dir():
                        destination = destination / artifact.filename
                    result = PublicRecordsResult.success(
                        query,
                        [
                            {
                                **record,
                                "selected_artifact": artifact.to_dict(),
                                "download": {
                                    "status": "planned",
                                    "destination": str(destination),
                                    "resume": args.resume,
                                    "max_bytes": args.max_download_bytes,
                                },
                            }
                        ],
                        warnings=warnings,
                    )
                else:
                    if args.expected_sha256:
                        artifact = replace(
                            artifact,
                            expected_sha256=args.expected_sha256,
                        )
                    download = transfer.download(
                        artifact,
                        args.destination,
                        resume=args.resume,
                        max_bytes=args.max_download_bytes,
                    )
                    archive = inspect_zip(download.path).to_dict()
                    csv_inspection = None
                    csv_inspection_key = None
                    if Path(download.path).is_file():
                        if args.dataset_type == "nal":
                            csv_inspection = inspect_nal_csv_archive(
                                download.path
                            )
                            csv_inspection_key = "nal_csv"
                        elif args.dataset_type == "sdf":
                            csv_inspection = inspect_sdf_csv_archive(
                                download.path
                            )
                            csv_inspection_key = "sdf_csv"
                    result = PublicRecordsResult.success(
                        query,
                        [
                            {
                                **record,
                                "selected_artifact": artifact.to_dict(),
                                "download": download.to_dict(),
                                "archive": archive,
                                **(
                                    {
                                        str(csv_inspection_key): (
                                            csv_inspection
                                        )
                                    }
                                    if csv_inspection is not None
                                    and csv_inspection_key is not None
                                    else {}
                                ),
                            }
                        ],
                        raw_artifact_refs=[download.path],
                        warnings=warnings,
                    )
    except AcquisitionUnavailableError as error:
        result = _access_failure(query, error)
    except BulkSourceError as error:
        result = PublicRecordsResult.failure(
            query,
            error.result_status,
            [error.to_contract_error()],
        )
    except (KeyError, OSError, TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="fl_dor_bulk_operation_failed",
                    message=str(error),
                    category="bulk_source",
                    retryable=False,
                )
            ],
        )

    result_count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), SOURCE_ID, result_count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Florida DOR property {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Florida DOR property {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        if "county_name" in record:
            print(
                f"  {record['county_name']} | {record['dataset_type']} | "
                f"{record['assessment_year']} | {record['canonical_ref']}"
            )
        elif "release_id" in record:
            print(
                f"  {record['release_id']} | "
                f"{record.get('artifact_count')} artifacts"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--retry-attempts", type=int, default=3)
    parser.add_argument("--minimum-interval", type=float, default=0.0)


def _add_selectors(
    parser: argparse.ArgumentParser,
    *,
    require_type: bool = False,
    require_county: bool = False,
) -> None:
    parser.add_argument(
        "--type",
        dest="dataset_type",
        choices=DATASET_TYPES,
        required=require_type,
    )
    parser.add_argument(
        "--county",
        required=require_county,
        help="Florida DOR county number or county name",
    )
    parser.add_argument("--year", type=int)


def _add_transfer_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--destination", required=True)
    parser.add_argument(
        "--no-resume",
        action="store_false",
        dest="resume",
    )
    parser.set_defaults(resume=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--max-download-bytes", type=int)
    parser.add_argument("--chunk-size", type=int, default=1024 * 1024)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover and transfer official Florida DOR property releases"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser(
        "list",
        help="List published release directories",
    )
    _add_selectors(list_parser)
    list_parser.add_argument("--limit", type=int)
    list_parser.add_argument("--cursor")
    _add_connection_args(list_parser)
    add_output_args(list_parser)

    manifest = sub.add_parser(
        "manifest",
        help="List artifact manifests from the current or selected release",
    )
    _add_selectors(manifest)
    manifest.add_argument("--limit", type=int)
    manifest.add_argument("--cursor")
    _add_connection_args(manifest)
    add_output_args(manifest)

    probe = sub.add_parser(
        "probe",
        help="Make a bounded metadata and leading-range probe",
    )
    _add_selectors(probe, require_type=True, require_county=True)
    probe.add_argument("--range-bytes", type=int, default=4096)
    _add_connection_args(probe)
    add_output_args(probe)

    dry_run = sub.add_parser(
        "dry-run",
        help="Resolve an artifact and emit a transfer plan",
    )
    _add_selectors(dry_run, require_type=True, require_county=True)
    _add_transfer_args(dry_run)
    _add_connection_args(dry_run)
    add_output_args(dry_run)

    download = sub.add_parser(
        "download",
        help="Download and fingerprint one county release",
    )
    _add_selectors(download, require_type=True, require_county=True)
    _add_transfer_args(download)
    download.add_argument("--dry-run", action="store_true")
    _add_connection_args(download)
    add_output_args(download)
    return parser


def _validate_args(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> None:
    for name in (
        "limit",
        "year",
        "retry_attempts",
        "chunk_size",
        "max_download_bytes",
    ):
        value = getattr(args, name, None)
        if value is not None and value <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if getattr(args, "timeout", 1) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    if getattr(args, "range_bytes", 0) < 0:
        parser.error("--range-bytes must not be negative")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(parser, args)
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
