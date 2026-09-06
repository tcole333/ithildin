#!/usr/bin/env python3
"""Discover, download, inspect, and search official TxGIO land parcels.

The Texas Geographic Information Office (TxGIO) DataHub publishes annual
statewide land-parcel collections as county ZIP archives. Each current archive
contains a standardized shapefile, file geodatabase, and metadata. The
shapefile DBF carries county appraisal-district parcel identifiers, owner-name
snapshots, situs and mailing addresses, land/improvement/market values, land
use, legal descriptions, acquisition dates, tax years, and related attributes.

Examples:
    uv run python tools/query_txgio_land_parcels.py releases
    uv run python tools/query_txgio_land_parcels.py manifest --county Harris
    uv run python tools/query_txgio_land_parcels.py probe --county 48261
    uv run python tools/query_txgio_land_parcels.py download --county Kenedy \
        --destination /tmp/txgio-kenedy.zip
    uv run python tools/query_txgio_land_parcels.py inspect \
        /tmp/txgio-kenedy.zip
    uv run python tools/query_txgio_land_parcels.py search \
        /tmp/txgio-kenedy.zip "KING RANCH" --field owner
"""

from __future__ import annotations

import argparse
import base64
import binascii
import codecs
import contextlib
import json
import re
import struct
import sys
import zipfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterator, Mapping, Sequence
from urllib.parse import urlsplit

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_bulk import (
        ArchiveSafetyPolicy,
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
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
    from tools.public_records_http import (
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceSchemaError,
        _BaseJSONClient,
        failure_result,
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
        ArchiveSafetyPolicy,
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
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
    from public_records_http import (
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceSchemaError,
        _BaseJSONClient,
        failure_result,
    )
    from public_records_store import canonical_property_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-tx-txgio-land-parcels"
STATE_CODE = "TX"
STATE_FIPS = "48"
LANDING_URL = "https://gio.texas.gov/stratmap/land-parcels.html"
DATAHUB_URL = "https://data.geographic.texas.gov/"
API_ROOT = "https://api.tnris.org/api/v1"
COLLECTIONS_ENDPOINT = f"{API_ROOT}/collections/"
RESOURCES_ENDPOINT = f"{API_ROOT}/resources/"
SCHEMA_URL = "https://cdn.tnris.org/documents/tnris-land-parcel-schema.pdf"
CURRENT_MAPSERVER_URL = (
    "https://feature.geographic.texas.gov/arcgis/rest/services/"
    "Parcels/stratmap_land_parcels_48_most_recent/MapServer"
)
APPRAISAL_DIRECTORY_URL = (
    "https://comptroller.texas.gov/taxes/property-tax/county-directory/"
)
OFFICIAL_DOWNLOADER_SOURCE = (
    "https://github.com/TNRIS/go-bulk-downloader/blob/main/bulk-downloader.go"
)

DEFAULT_TIMEOUT = 60.0
DEFAULT_MINIMUM_INTERVAL = 0.1
DEFAULT_CHUNK_SIZE = 1024 * 1024
DOWNLOAD_USER_AGENT = "TxGIO Bulk Downloader 1.1.3"
CURSOR_PREFIX = "txgio-land-parcels:v1:"
RESOURCE_FILENAME_RE = re.compile(
    r"^stratmap(?P<release>\d+)-landparcels_(?P<fips>48(?:\d{3})?)_lp\.zip$",
    re.IGNORECASE,
)

PUBLISHED_FIELDS = {
    "PROP_ID": ("PROP_ID",),
    "GEO_ID": ("GEO_ID",),
    "OWNER_NAME": ("OWNER_NAME",),
    "NAME_CARE": ("NAME_CARE",),
    "LEGAL_AREA": ("LEGAL_AREA",),
    "LGL_AREA_UNIT": ("LGL_AREA_U", "LGL_AREA_UNIT"),
    "GIS_AREA": ("GIS_AREA",),
    "GIS_AREA_UNIT": ("GIS_AREA_U", "GIS_AREA_UNIT"),
    "LEGAL_DESC": ("LEGAL_DESC",),
    "STAT_LAND_USE": ("STAT_LAND_", "STAT_LAND_USE"),
    "LOC_LAND_USE": ("LOC_LAND_U", "LOC_LAND_USE"),
    "LAND_VALUE": ("LAND_VALUE",),
    "IMP_VALUE": ("IMP_VALUE",),
    "MKT_VALUE": ("MKT_VALUE",),
    "SITUS_ADDR": ("SITUS_ADDR",),
    "SITUS_NUM": ("SITUS_NUM",),
    "SITUS_STRE": ("SITUS_STRE",),
    "SITUS_ST_1": ("SITUS_ST_1",),
    "SITUS_ST_2": ("SITUS_ST_2",),
    "SITUS_CITY": ("SITUS_CITY",),
    "SITUS_STAT": ("SITUS_STAT",),
    "SITUS_ZIP": ("SITUS_ZIP",),
    "MAIL_ADDR": ("MAIL_ADDR",),
    "MAIL_LINE1": ("MAIL_LINE1",),
    "MAIL_LINE2": ("MAIL_LINE2",),
    "MAIL_CITY": ("MAIL_CITY",),
    "MAIL_STAT": ("MAIL_STAT",),
    "MAIL_ZIP": ("MAIL_ZIP",),
    "SOURCE": ("SOURCE",),
    "DATE_ACQ": ("DATE_ACQ",),
    "FIPS": ("FIPS",),
    "COUNTY": ("COUNTY",),
    "TAX_YEAR": ("TAX_YEAR",),
    "YEAR_BUILT": ("YEAR_BUILT",),
}

SEARCH_FIELDS = {
    "parcel": ("PROP_ID", "GEO_ID"),
    "owner": ("OWNER_NAME", "NAME_CARE"),
    "address": (
        "SITUS_ADDR",
        "SITUS_NUM",
        "SITUS_STRE",
        "SITUS_ST_1",
        "SITUS_ST_2",
        "SITUS_CITY",
        "SITUS_ZIP",
        "MAIL_ADDR",
        "MAIL_LINE1",
        "MAIL_LINE2",
        "MAIL_CITY",
        "MAIL_ZIP",
    ),
    "legal": ("LEGAL_DESC",),
    "any": tuple(PUBLISHED_FIELDS),
}

DECLARED_SCHEMA = {
    "schema_reference": SCHEMA_URL,
    "logical_fields": tuple(PUBLISHED_FIELDS),
    "archive_contents": (
        "standardized_county_shapefile",
        "file_geodatabase",
        "shapefile_metadata",
    ),
    "native_identity_fields": ("FIPS", "PROP_ID", "GEO_ID"),
    "feature_occurrence": (
        "DBF/shapefile record position is retained separately because "
        "published parcel identifiers can occur on multiple features."
    ),
    "geometry_role": "county_appraisal_mapping_polygon",
    "attribute_roles": (
        "assessment_roll_owner_name",
        "situs_and_mailing_address",
        "land_improvement_and_market_value",
        "land_use",
        "legal_description_copied_into_appraisal_data",
        "tax_year",
        "year_built",
    ),
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="TxGIO Statewide Land Parcels",
    source_role="statewide_county_parcel_geometry_and_assessment_snapshot_bulk",
    base_url=LANDING_URL,
    dataset_id="TXGIO-LAND-PARCELS",
    metadata={
        "authority": "Texas Geographic Information Office",
        "operator": "Texas Water Development Board",
        "upstream_sources": "county appraisal districts and their vendors",
        "collection_api": COLLECTIONS_ENDPOINT,
        "resource_api": RESOURCES_ENDPOINT,
        "schema_reference": SCHEMA_URL,
        "license": "CC0-1.0",
        "release_selection": "latest publication by default; explicit collection ID accepted",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-tx",
    name="Texas",
    state_code=STATE_CODE,
    metadata={"state_fips": STATE_FIPS},
)


class TxGIOLandParcelError(RuntimeError):
    """Source, selection, or local-artifact failure with envelope semantics."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.SOURCE_CHANGED,
        category: str = "source_schema",
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
class DBFField:
    name: str
    field_type: str
    length: int
    decimal_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.field_type,
            "length": self.length,
            "decimal_count": self.decimal_count,
        }


@dataclass(frozen=True)
class DBFSchema:
    member_name: str
    version: int
    last_update: str | None
    record_count: int
    header_length: int
    record_length: int
    language_driver: int
    encoding: str
    fields: tuple[DBFField, ...]

    @property
    def field_lookup(self) -> dict[str, str]:
        return {field.name.casefold(): field.name for field in self.fields}

    @property
    def schema_fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "record_length": self.record_length,
                "encoding": self.encoding,
                "fields": [field.to_dict() for field in self.fields],
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_name": self.member_name,
            "version": self.version,
            "last_update": self.last_update,
            "record_count": self.record_count,
            "header_length": self.header_length,
            "record_length": self.record_length,
            "language_driver": self.language_driver,
            "encoding": self.encoding,
            "fields": [field.to_dict() for field in self.fields],
            "schema_fingerprint": self.schema_fingerprint,
        }


@dataclass(frozen=True)
class LocalDatasetInspection:
    path: str
    artifact_sha256: str
    archive: Mapping[str, Any]
    dbf: DBFSchema
    shapefile: Mapping[str, Any]
    projection_wkt: str | None
    metadata_member: str | None
    supporting_metadata_members: tuple[str, ...]
    compatibility: Mapping[str, Any]
    schema_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "artifact_sha256": self.artifact_sha256,
            "archive": dict(self.archive),
            "dbf": self.dbf.to_dict(),
            "shapefile": dict(self.shapefile),
            "projection_wkt": self.projection_wkt,
            "metadata_member": self.metadata_member,
            "supporting_metadata_members": list(
                self.supporting_metadata_members
            ),
            "compatibility": dict(self.compatibility),
            "schema_fingerprint": self.schema_fingerprint,
        }


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


def _clean_address(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None or not re.search(r"[A-Za-z0-9]", text):
        return None
    return text


def _require_text(value: Any, field: str, *, url: str) -> str:
    text = _clean_text(value)
    if text is None:
        raise SourceSchemaError(
            f"TxGIO response is missing {field}",
            url=url,
            details={"field": field},
        )
    return text


def _require_date(value: Any, field: str, *, url: str) -> str:
    text = _require_text(value, field, url=url)
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError as error:
        raise SourceSchemaError(
            f"TxGIO {field} is not an ISO date",
            url=url,
            details={"field": field, "value": text},
        ) from error


def _page(payload: Any, *, url: str) -> tuple[list[Mapping[str, Any]], str | None, int]:
    if not isinstance(payload, Mapping):
        raise SourceSchemaError(
            "TxGIO API page is not an object",
            url=url,
            details={"observed_type": type(payload).__name__},
        )
    results = payload.get("results")
    count = payload.get("count")
    next_url = payload.get("next")
    if not isinstance(results, list) or isinstance(count, bool) or not isinstance(count, int):
        raise SourceSchemaError(
            "TxGIO API page is missing results or count",
            url=url,
            details={"keys": sorted(str(key) for key in payload)},
        )
    if next_url is not None and not isinstance(next_url, str):
        raise SourceSchemaError(
            "TxGIO API next link is not text",
            url=url,
            details={"observed_type": type(next_url).__name__},
        )
    rows: list[Mapping[str, Any]] = []
    for index, row in enumerate(results):
        if not isinstance(row, Mapping):
            raise SourceSchemaError(
                "TxGIO API result is not an object",
                url=url,
                details={"row_index": index},
            )
        rows.append(row)
    return rows, next_url, count


def _validate_next_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.netloc != "api.tnris.org":
        raise TxGIOLandParcelError(
            "txgio_pagination_url_changed",
            "TxGIO API returned an unexpected pagination URL",
            details={"url": value},
        )
    if not parsed.path.startswith("/api/v1/"):
        raise TxGIOLandParcelError(
            "txgio_pagination_path_changed",
            "TxGIO API returned an unexpected pagination path",
            details={"url": value},
        )
    return value


def _collection_record(row: Mapping[str, Any]) -> dict[str, Any]:
    collection_id = _require_text(
        row.get("collection_id"),
        "collection_id",
        url=COLLECTIONS_ENDPOINT,
    )
    name = _require_text(row.get("name"), "name", url=COLLECTIONS_ENDPOINT)
    if name.casefold() != "land parcels":
        raise SourceSchemaError(
            "TxGIO collection search returned a different dataset",
            url=COLLECTIONS_ENDPOINT,
            details={"collection_id": collection_id, "name": name},
        )
    publication_date = _require_date(
        row.get("publication_date"),
        "publication_date",
        url=COLLECTIONS_ENDPOINT,
    )
    acquisition_date = _require_date(
        row.get("acquisition_date"),
        "acquisition_date",
        url=COLLECTIONS_ENDPOINT,
    )
    counties = [
        item.strip()
        for item in str(row.get("counties") or "").split(",")
        if item.strip()
    ]
    return {
        "collection_id": collection_id,
        "name": name,
        "acquisition_date": acquisition_date,
        "publication_date": publication_date,
        "public": row.get("public"),
        "authoritative_flag": row.get("authoritative"),
        "availability": _clean_text(row.get("availability")),
        "file_type": _clean_text(row.get("file_type")),
        "spatial_reference": _clean_text(row.get("spatial_reference")),
        "source_name": _clean_text(row.get("source_name")),
        "source_abbreviation": _clean_text(row.get("source_abbreviation")),
        "license_name": _clean_text(row.get("license_name")),
        "license_abbreviation": _clean_text(row.get("license_abbreviation")),
        "license_url": _clean_text(row.get("license_url")),
        "resource_types": _clean_text(row.get("resource_types")),
        "s3_key": _clean_text(row.get("s_three_key")),
        "supplemental_report_url": _clean_text(row.get("supplemental_report_url")),
        "map_service_url": _clean_text(row.get("popup_link")),
        "wms_url": _clean_text(row.get("wms_link")),
        "counties": counties,
        "county_count_declared": len(counties),
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            STATE_FIPS,
            "bulk_collection",
            collection_id,
        ),
        "source_url": f"{DATAHUB_URL}collection/?c={collection_id}",
    }


def _resource_record(row: Mapping[str, Any], collection_id: str) -> dict[str, Any]:
    resource_id = _require_text(
        row.get("resource_id"),
        "resource_id",
        url=RESOURCES_ENDPOINT,
    )
    resource_url = _require_text(
        row.get("resource"),
        "resource",
        url=RESOURCES_ENDPOINT,
    )
    response_collection_id = _require_text(
        row.get("collection_id"),
        "collection_id",
        url=RESOURCES_ENDPOINT,
    )
    if response_collection_id != collection_id:
        raise SourceSchemaError(
            "TxGIO resource belongs to a different collection",
            url=RESOURCES_ENDPOINT,
            details={
                "requested_collection_id": collection_id,
                "response_collection_id": response_collection_id,
                "resource_id": resource_id,
            },
        )
    parsed_url = urlsplit(resource_url)
    filename = Path(parsed_url.path).name
    match = RESOURCE_FILENAME_RE.fullmatch(filename)
    if (
        parsed_url.scheme != "https"
        or parsed_url.netloc != "data.geographic.texas.gov"
        or match is None
    ):
        raise SourceSchemaError(
            "TxGIO land-parcel resource URL or filename changed",
            url=RESOURCES_ENDPOINT,
            details={"resource_id": resource_id, "resource": resource_url},
        )
    filesize = row.get("filesize")
    if isinstance(filesize, bool) or not isinstance(filesize, int) or filesize <= 0:
        raise SourceSchemaError(
            "TxGIO resource has an invalid filesize",
            url=RESOURCES_ENDPOINT,
            details={"resource_id": resource_id, "filesize": filesize},
        )
    jurisdiction_fips = match.group("fips")
    area_name = _require_text(
        row.get("area_type_name"),
        "area_type_name",
        url=RESOURCES_ENDPOINT,
    )
    area_type = _clean_text(row.get("area_type"))
    expected_area_type = "county" if len(jurisdiction_fips) == 5 else "state"
    if area_type != expected_area_type:
        raise SourceSchemaError(
            "TxGIO land-parcel resource scope does not match its filename",
            url=RESOURCES_ENDPOINT,
            details={
                "resource_id": resource_id,
                "area_type": row.get("area_type"),
                "jurisdiction_fips": jurisdiction_fips,
            },
        )
    return {
        "resource_id": resource_id,
        "url": resource_url,
        "filename": filename,
        "expected_size": filesize,
        "scope": expected_area_type,
        "jurisdiction_fips": jurisdiction_fips,
        "county_fips": (
            jurisdiction_fips if expected_area_type == "county" else None
        ),
        "county_name": area_name if expected_area_type == "county" else None,
        "area_name": area_name,
        "area_type_id": _require_text(
            row.get("area_type_id"),
            "area_type_id",
            url=RESOURCES_ENDPOINT,
        ),
        "resource_type_name": _clean_text(row.get("resource_type_name")),
        "resource_type_abbreviation": _clean_text(
            row.get("resource_type_abbreviation")
        ),
    }


class TxGIODataHubClient(_BaseJSONClient):
    """Client for the official TxGIO collection and resource APIs."""

    def _all_pages(
        self,
        url: str,
        *,
        params: Mapping[str, Any],
    ) -> tuple[list[Mapping[str, Any]], int]:
        rows: list[Mapping[str, Any]] = []
        expected_count: int | None = None
        next_url: str | None = url
        next_params = dict(params)
        seen_urls: set[str] = set()
        while next_url is not None:
            if next_url in seen_urls:
                raise TxGIOLandParcelError(
                    "txgio_pagination_loop",
                    "TxGIO API repeated a pagination URL",
                    details={"url": next_url},
                )
            seen_urls.add(next_url)
            payload = self._request_json(next_url, params=next_params)
            page_rows, following, count = _page(payload, url=next_url)
            if expected_count is None:
                expected_count = count
            elif count != expected_count:
                raise TxGIOLandParcelError(
                    "txgio_pagination_count_changed",
                    "TxGIO API changed its total count between pages",
                    details={"expected": expected_count, "observed": count},
                )
            rows.extend(page_rows)
            next_url = _validate_next_url(following) if following else None
            next_params = {}
        assert expected_count is not None
        if len(rows) != expected_count:
            raise TxGIOLandParcelError(
                "txgio_pagination_incomplete",
                "TxGIO API pagination did not return its declared result count",
                details={"declared_count": expected_count, "observed_count": len(rows)},
            )
        return rows, expected_count

    def releases(self) -> list[dict[str, Any]]:
        rows, _ = self._all_pages(
            COLLECTIONS_ENDPOINT,
            params={"search": "land parcels"},
        )
        records = [_collection_record(row) for row in rows]
        ids = [record["collection_id"] for record in records]
        if len(ids) != len(set(ids)):
            raise TxGIOLandParcelError(
                "txgio_duplicate_collection",
                "TxGIO returned duplicate land-parcel collection identifiers",
            )
        return sorted(
            records,
            key=lambda record: (
                record["publication_date"],
                record["acquisition_date"],
                record["collection_id"],
            ),
            reverse=True,
        )

    def resources(self, collection_id: str) -> list[dict[str, Any]]:
        rows, _ = self._all_pages(
            RESOURCES_ENDPOINT,
            params={"collection_id": collection_id},
        )
        records = [_resource_record(row, collection_id) for row in rows]
        resource_ids = [record["resource_id"] for record in records]
        fips_codes = [record["jurisdiction_fips"] for record in records]
        if len(resource_ids) != len(set(resource_ids)):
            raise TxGIOLandParcelError(
                "txgio_duplicate_resource",
                "TxGIO returned duplicate resource identifiers",
                details={"collection_id": collection_id},
            )
        if len(fips_codes) != len(set(fips_codes)):
            raise TxGIOLandParcelError(
                "txgio_duplicate_county_resource",
                "TxGIO returned more than one land-parcel archive for a county",
                details={"collection_id": collection_id},
            )
        return sorted(records, key=lambda record: record["jurisdiction_fips"])


def _client(args: argparse.Namespace) -> TxGIODataHubClient:
    return TxGIODataHubClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
        minimum_interval=args.minimum_interval,
    )


def _bulk_client(args: argparse.Namespace) -> BulkTransferClient:
    return BulkTransferClient(
        timeout=args.timeout,
        max_attempts=args.retry_attempts,
        chunk_size=getattr(args, "chunk_size", DEFAULT_CHUNK_SIZE),
        user_agent=DOWNLOAD_USER_AGENT,
    )


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=Path(args.catalog_db).expanduser(),
        config_path=Path(args.catalog_config).expanduser(),
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _selected_collection(
    releases: Sequence[Mapping[str, Any]],
    collection_id: str | None,
) -> Mapping[str, Any] | None:
    if collection_id is None:
        return releases[0] if releases else None
    return next(
        (
            release
            for release in releases
            if release.get("collection_id") == collection_id
        ),
        None,
    )


def _county_key(value: str) -> str:
    key = re.sub(r"[^a-z0-9]", "", value.casefold())
    return key.removesuffix("county")


def _select_resources(
    resources: Sequence[Mapping[str, Any]],
    county: str | None,
) -> list[Mapping[str, Any]]:
    if county is None:
        return list(resources)
    key = _county_key(county)
    return [
        resource
        for resource in resources
        if key
        in {
            _county_key(str(resource["county_name"])),
            _county_key(str(resource["area_name"])),
            _county_key(str(resource["jurisdiction_fips"])),
            _county_key(str(resource["jurisdiction_fips"])[2:]),
        }
    ]


def normalize_manifest(
    collection: Mapping[str, Any],
    resources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    collection_id = str(collection["collection_id"])
    artifacts = [
        BulkArtifact(
            artifact_id=str(resource["resource_id"]),
            url=str(resource["url"]),
            filename=str(resource["filename"]),
            media_type="application/zip",
            archive_format="zip",
            expected_size=int(resource["expected_size"]),
            metadata={
                "county_fips": resource["county_fips"],
                "county_name": resource["county_name"],
                "scope": resource["scope"],
                "jurisdiction_fips": resource["jurisdiction_fips"],
                "area_name": resource["area_name"],
                "area_type_id": resource["area_type_id"],
                "resource_type_name": resource["resource_type_name"],
                "resource_type_abbreviation": resource[
                    "resource_type_abbreviation"
                ],
            },
        )
        for resource in resources
    ]
    release_id = f"{collection['publication_date']}:{collection_id}"
    county_fips = [
        str(resource["county_fips"])
        for resource in resources
        if resource["county_fips"] is not None
    ]
    statewide_artifacts = [
        resource for resource in resources if resource["scope"] == "state"
    ]
    manifest = BulkDatasetManifest(
        source_id=SOURCE_ID,
        dataset_id=f"TXGIO-LAND-PARCELS-{collection_id}",
        release=BulkReleaseMetadata(
            release_id=release_id,
            kind="snapshot",
            effective_at=str(collection["publication_date"]),
            coverage={
                "state_fips": STATE_FIPS,
                "acquisition_date": collection["acquisition_date"],
                "publication_date": collection["publication_date"],
                "resource_count": len(resources),
                "county_count": len(county_fips),
                "county_fips": county_fips,
                "county_artifact_count": len(county_fips),
                "statewide_artifact_count": len(statewide_artifacts),
                "declared_county_count": collection["county_count_declared"],
            },
        ),
        artifacts=artifacts,
        schema=DECLARED_SCHEMA,
        metadata={
            "collection": dict(collection),
            "collection_api": COLLECTIONS_ENDPOINT,
            "resource_api": RESOURCES_ENDPOINT,
            "download_user_agent": DOWNLOAD_USER_AGENT,
            "download_user_agent_source": OFFICIAL_DOWNLOADER_SOURCE,
        },
    )
    jurisdiction = (
        str(resources[0]["jurisdiction_fips"])
        if len(resources) == 1
        else STATE_FIPS
    )
    return {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            jurisdiction,
            "bulk_release",
            release_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "bulk_dataset_manifest",
        "collection": dict(collection),
        "manifest": manifest.to_dict(),
        "source_url": collection["source_url"],
    }


def _manifest_artifact(record: Mapping[str, Any]) -> BulkArtifact:
    artifacts = record["manifest"]["artifacts"]
    if len(artifacts) != 1:
        raise TxGIOLandParcelError(
            "txgio_county_selection_required",
            "Select one county for probe or download",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
            details={"artifact_count": len(artifacts)},
        )
    artifact = artifacts[0]
    return BulkArtifact(
        artifact_id=artifact["artifact_id"],
        url=artifact["url"],
        filename=artifact["filename"],
        media_type=artifact.get("media_type"),
        archive_format=artifact.get("archive_format"),
        expected_size=artifact.get("expected_size"),
        expected_sha256=artifact.get("expected_sha256"),
        etag=artifact.get("etag"),
        last_modified=artifact.get("last_modified"),
        metadata=artifact.get("metadata") or {},
    )


def _archive_policy(args: argparse.Namespace) -> ArchiveSafetyPolicy:
    return ArchiveSafetyPolicy(
        max_members=getattr(args, "max_archive_members", None),
        max_total_uncompressed_bytes=getattr(args, "max_uncompressed_bytes", None),
        max_member_uncompressed_bytes=getattr(
            args,
            "max_member_uncompressed_bytes",
            None,
        ),
        max_compression_ratio=getattr(args, "max_compression_ratio", None),
    )


def _zip_members(
    archive: zipfile.ZipFile,
    suffix: str,
    *,
    directory: str | None = None,
) -> list[zipfile.ZipInfo]:
    suffix_key = suffix.casefold()
    return [
        member
        for member in archive.infolist()
        if not member.is_dir()
        and Path(member.filename).suffix.casefold() == suffix_key
        and (
            directory is None
            or Path(member.filename).parts[0].casefold() == directory.casefold()
        )
    ]


def _zip_single(
    archive: zipfile.ZipFile,
    suffix: str,
    *,
    directory: str | None = None,
    required: bool = True,
) -> zipfile.ZipInfo | None:
    members = _zip_members(archive, suffix, directory=directory)
    if not members and not required:
        return None
    if len(members) != 1:
        raise TxGIOLandParcelError(
            "txgio_archive_member_count",
            f"TxGIO archive must contain one {suffix} member in {directory or 'the archive'}",
            details={"members": [member.filename for member in members]},
        )
    return members[0]


def _zip_named(
    archive: zipfile.ZipFile,
    name: str,
    *,
    required: bool = True,
) -> zipfile.ZipInfo | None:
    matches = [
        member
        for member in archive.infolist()
        if not member.is_dir() and member.filename.casefold() == name.casefold()
    ]
    if not matches and not required:
        return None
    if len(matches) != 1:
        raise TxGIOLandParcelError(
            "txgio_archive_member_count",
            f"TxGIO archive must contain one member named {name}",
            details={"members": [member.filename for member in matches]},
        )
    return matches[0]


def _encoding(archive: zipfile.ZipFile) -> str:
    member = _zip_single(archive, ".cpg", directory="shp", required=False)
    raw = archive.read(member).decode("ascii", errors="replace") if member else "UTF-8"
    candidate = (_clean_text(raw) or "UTF-8").casefold()
    aliases = {
        "65001": "utf-8",
        "utf8": "utf-8",
        "ansi 1252": "cp1252",
        "1252": "cp1252",
    }
    try:
        return codecs.lookup(aliases.get(candidate, candidate)).name
    except LookupError as error:
        raise TxGIOLandParcelError(
            "txgio_dbf_encoding_unknown",
            "TxGIO archive declares an unknown DBF encoding",
            details={"cpg": raw},
        ) from error


def _dbf_date(header: bytes) -> str | None:
    try:
        return datetime(
            1900 + header[1],
            header[2],
            header[3],
            tzinfo=timezone.utc,
        ).date().isoformat()
    except ValueError:
        return None


def _parse_dbf_header(
    stream: BinaryIO,
    *,
    member_name: str,
    member_size: int,
    encoding: str,
) -> DBFSchema:
    header = stream.read(32)
    if len(header) != 32:
        raise TxGIOLandParcelError(
            "txgio_dbf_header_truncated",
            "TxGIO parcel DBF header is truncated",
            details={"member": member_name},
        )
    record_count = struct.unpack("<I", header[4:8])[0]
    header_length = struct.unpack("<H", header[8:10])[0]
    record_length = struct.unpack("<H", header[10:12])[0]
    if header_length < 33 or record_length < 2:
        raise TxGIOLandParcelError(
            "txgio_dbf_header_invalid",
            "TxGIO parcel DBF declares an invalid layout",
            details={
                "header_length": header_length,
                "record_length": record_length,
            },
        )
    if header_length + record_count * record_length > member_size:
        raise TxGIOLandParcelError(
            "txgio_dbf_records_truncated",
            "TxGIO parcel DBF is shorter than its declared record table",
            details={"member": member_name, "member_size": member_size},
        )
    fields: list[DBFField] = []
    consumed = 32
    while consumed < header_length:
        first = stream.read(1)
        consumed += 1
        if first == b"\r":
            break
        remainder = stream.read(31)
        consumed += len(remainder)
        if len(remainder) != 31:
            raise TxGIOLandParcelError(
                "txgio_dbf_descriptor_truncated",
                "TxGIO parcel DBF field descriptor is truncated",
                details={"member": member_name},
            )
        descriptor = first + remainder
        name = descriptor[:11].split(b"\x00", 1)[0].decode("ascii", errors="strict")
        length = descriptor[16]
        if not name or length <= 0:
            raise TxGIOLandParcelError(
                "txgio_dbf_descriptor_invalid",
                "TxGIO parcel DBF contains an invalid field descriptor",
                details={"member": member_name, "field": name},
            )
        fields.append(
            DBFField(
                name=name,
                field_type=chr(descriptor[11]),
                length=length,
                decimal_count=descriptor[17],
            )
        )
    else:
        raise TxGIOLandParcelError(
            "txgio_dbf_terminator_missing",
            "TxGIO parcel DBF header has no field terminator",
            details={"member": member_name},
        )
    if consumed < header_length:
        padding = stream.read(header_length - consumed)
        if len(padding) != header_length - consumed:
            raise TxGIOLandParcelError(
                "txgio_dbf_header_truncated",
                "TxGIO parcel DBF header padding is truncated",
                details={"member": member_name},
            )
    if 1 + sum(field.length for field in fields) != record_length:
        raise TxGIOLandParcelError(
            "txgio_dbf_record_layout_changed",
            "TxGIO parcel DBF record length does not match its fields",
            details={"member": member_name},
        )
    names = [field.name.casefold() for field in fields]
    if len(names) != len(set(names)):
        raise TxGIOLandParcelError(
            "txgio_dbf_duplicate_fields",
            "TxGIO parcel DBF contains duplicate field names",
            details={"member": member_name},
        )
    return DBFSchema(
        member_name=member_name,
        version=header[0],
        last_update=_dbf_date(header),
        record_count=record_count,
        header_length=header_length,
        record_length=record_length,
        language_driver=header[29],
        encoding=encoding,
        fields=tuple(fields),
    )


def _shapefile_header(data: bytes, member_name: str) -> dict[str, Any]:
    if len(data) < 100:
        raise TxGIOLandParcelError(
            "txgio_shapefile_header_truncated",
            "TxGIO parcel shapefile header is truncated",
            details={"member": member_name},
        )
    file_code = struct.unpack(">i", data[0:4])[0]
    version = struct.unpack("<i", data[28:32])[0]
    shape_type = struct.unpack("<i", data[32:36])[0]
    if file_code != 9994 or version != 1000:
        raise TxGIOLandParcelError(
            "txgio_shapefile_header_invalid",
            "TxGIO parcel artifact is not a compatible Esri shapefile",
            details={"member": member_name, "file_code": file_code, "version": version},
        )
    xmin, ymin, xmax, ymax = struct.unpack("<4d", data[36:68])
    return {
        "member_name": member_name,
        "file_length_bytes": struct.unpack(">i", data[24:28])[0] * 2,
        "shape_type": shape_type,
        "shape_type_role": "polygon" if shape_type in {5, 15, 25} else "other",
        "bounds": {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax},
    }


def _physical_mapping(schema: DBFSchema) -> tuple[dict[str, str], list[str], list[str]]:
    lookup = schema.field_lookup
    mapping: dict[str, str] = {}
    missing: list[str] = []
    for logical, aliases in PUBLISHED_FIELDS.items():
        observed = next(
            (lookup[alias.casefold()] for alias in aliases if alias.casefold() in lookup),
            None,
        )
        if observed is None:
            missing.append(logical)
        else:
            mapping[logical] = observed
    used = {value.casefold() for value in mapping.values()}
    additional = [
        field.name for field in schema.fields if field.name.casefold() not in used
    ]
    return mapping, missing, additional


def inspect_local_dataset(
    path: Path | str,
    *,
    policy: ArchiveSafetyPolicy | None = None,
) -> LocalDatasetInspection:
    artifact_path = Path(path).expanduser().resolve()
    if not artifact_path.is_file():
        raise TxGIOLandParcelError(
            "txgio_artifact_missing",
            "TxGIO parcel artifact does not exist",
            status=ResultStatus.UNAVAILABLE,
            category="local_artifact",
            details={"path": str(artifact_path)},
        )
    archive_inspection = inspect_zip(artifact_path, policy=policy)
    with zipfile.ZipFile(artifact_path) as archive:
        dbf_member = _zip_single(archive, ".dbf", directory="shp")
        shp_member = _zip_single(archive, ".shp", directory="shp")
        prj_member = _zip_single(archive, ".prj", directory="shp", required=False)
        assert dbf_member is not None and shp_member is not None
        metadata_member = _zip_named(
            archive,
            f"{shp_member.filename}.xml",
            required=False,
        )
        supporting_metadata_members = tuple(
            sorted(
                member.filename
                for member in _zip_members(archive, ".xml", directory="shp")
                if (
                    metadata_member is None
                    or member.filename.casefold()
                    != metadata_member.filename.casefold()
                )
            )
        )
        if Path(dbf_member.filename).stem.casefold() != Path(
            shp_member.filename
        ).stem.casefold():
            raise TxGIOLandParcelError(
                "txgio_archive_dataset_mismatch",
                "TxGIO parcel DBF and shapefile names do not match",
                details={
                    "dbf_member": dbf_member.filename,
                    "shapefile_member": shp_member.filename,
                },
            )
        encoding = _encoding(archive)
        with archive.open(dbf_member) as stream:
            dbf = _parse_dbf_header(
                stream,
                member_name=dbf_member.filename,
                member_size=dbf_member.file_size,
                encoding=encoding,
            )
        shapefile = _shapefile_header(
            archive.read(shp_member)[:100],
            shp_member.filename,
        )
        projection_wkt = (
            archive.read(prj_member).decode("utf-8-sig", errors="replace").strip()
            if prj_member is not None
            else None
        )
    mapping, missing, additional = _physical_mapping(dbf)
    field_lookup = dbf.field_lookup
    occurrence_field = next(
        (
            field_lookup[name.casefold()]
            for name in ("OBJECTID_1", "OBJECTID", "FID")
            if name.casefold() in field_lookup
        ),
        None,
    )
    compatibility = {
        "search_ready": not missing,
        "published_logical_fields": list(PUBLISHED_FIELDS),
        "logical_to_physical": mapping,
        "missing_published_fields": missing,
        "additional_snapshot_fields": additional,
        "additive_fields_accepted": True,
        "feature_identity": {
            "parcel_join_fields": ["FIPS", "PROP_ID", "GEO_ID"],
            "feature_occurrence_field": occurrence_field or "DBF record index",
            "published_identifier_uniqueness": "not_assumed",
        },
    }
    schema_fingerprint = sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "dbf": dbf.to_dict(),
            "shapefile": shapefile,
            "projection_wkt": projection_wkt,
            "logical_to_physical": mapping,
        }
    )
    return LocalDatasetInspection(
        path=str(artifact_path),
        artifact_sha256=archive_inspection.archive_sha256,
        archive=archive_inspection.to_dict(),
        dbf=dbf,
        shapefile=shapefile,
        projection_wkt=projection_wkt,
        metadata_member=metadata_member.filename if metadata_member else None,
        supporting_metadata_members=supporting_metadata_members,
        compatibility=compatibility,
        schema_fingerprint=schema_fingerprint,
    )


@contextlib.contextmanager
def _open_dbf(
    inspection: LocalDatasetInspection,
) -> Iterator[tuple[BinaryIO, zipfile.ZipFile]]:
    archive = zipfile.ZipFile(inspection.path)
    try:
        stream = archive.open(inspection.dbf.member_name)
        try:
            yield stream, archive
        finally:
            stream.close()
    finally:
        archive.close()


def _decode_dbf(raw: bytes, field: DBFField, encoding: str) -> Any:
    field_type = field.field_type.upper()
    if field_type in {"C", "M"}:
        return raw.decode(encoding, errors="replace").replace("\x00", "").strip() or None
    text = raw.decode("ascii", errors="replace").strip()
    if not text or set(text) <= {"*"}:
        return None
    if field_type in {"N", "F"}:
        try:
            return float(text) if field.decimal_count else int(text)
        except ValueError:
            return text
    if field_type == "L":
        if text[:1].upper() in {"T", "Y"}:
            return True
        if text[:1].upper() in {"F", "N"}:
            return False
        return None
    if field_type == "D" and re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d").date().isoformat()
        except ValueError:
            return text
    if field_type == "I" and len(raw) == 4:
        return struct.unpack("<i", raw)[0]
    return text


def _dbf_rows(
    stream: BinaryIO,
    schema: DBFSchema,
    *,
    start_row: int = 0,
) -> Iterator[tuple[int, dict[str, Any]]]:
    if start_row < 0 or start_row > schema.record_count:
        raise TxGIOLandParcelError(
            "txgio_dbf_start_row_invalid",
            "TxGIO parcel DBF start row is outside the record table",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
            details={
                "start_row": start_row,
                "record_count": schema.record_count,
            },
        )
    stream.seek(
        schema.header_length + start_row * schema.record_length
    )
    for row_index in range(start_row, schema.record_count):
        raw_record = stream.read(schema.record_length)
        if len(raw_record) != schema.record_length:
            raise TxGIOLandParcelError(
                "txgio_dbf_record_truncated",
                "TxGIO parcel DBF record table ended unexpectedly",
                details={"row_index": row_index},
            )
        if raw_record[:1] == b"*":
            continue
        if raw_record[:1] != b" ":
            raise TxGIOLandParcelError(
                "txgio_dbf_record_marker",
                "TxGIO parcel DBF contains an unknown record marker",
                details={"row_index": row_index, "marker": raw_record[:1].hex()},
            )
        values: dict[str, Any] = {}
        offset = 1
        for field in schema.fields:
            raw = raw_record[offset : offset + field.length]
            offset += field.length
            values[field.name] = _decode_dbf(raw, field, schema.encoding)
        yield row_index, values


def _logical_value(
    row: Mapping[str, Any],
    mapping: Mapping[str, str],
    logical: str,
) -> Any:
    physical = mapping.get(logical)
    return row.get(physical) if physical else None


def _date_from_integer(value: Any) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    text = str(value).strip()
    if re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d").date().isoformat(), "day"
        except ValueError:
            return text, "unknown"
    if re.fullmatch(r"\d{6}", text):
        try:
            parsed = datetime.strptime(text, "%Y%m")
            return parsed.strftime("%Y-%m"), "month"
        except ValueError:
            return text, "unknown"
    return text, "unknown"


def _year_value(value: Any, *, zero_is_missing: bool = False) -> int | str | None:
    text = _clean_text(value)
    if text is None:
        return None
    if re.fullmatch(r"\d{1,4}", text):
        year = int(text)
        if zero_is_missing and year == 0:
            return None
        return year
    return text


def _structured_address(
    row: Mapping[str, Any],
    mapping: Mapping[str, str],
    *,
    prefix: str,
) -> dict[str, Any] | None:
    if prefix == "SITUS":
        raw = _clean_address(_logical_value(row, mapping, "SITUS_ADDR"))
        fields = {
            "number": _clean_text(_logical_value(row, mapping, "SITUS_NUM")),
            "direction_or_unit": _clean_text(
                _logical_value(row, mapping, "SITUS_STRE")
            ),
            "street": _clean_text(_logical_value(row, mapping, "SITUS_ST_1")),
            "street_info": _clean_text(
                _logical_value(row, mapping, "SITUS_ST_2")
            ),
            "city": _clean_text(_logical_value(row, mapping, "SITUS_CITY")),
            "state": _clean_text(_logical_value(row, mapping, "SITUS_STAT")),
            "postal_code": _clean_text(
                _logical_value(row, mapping, "SITUS_ZIP")
            ),
        }
    else:
        raw = _clean_address(_logical_value(row, mapping, "MAIL_ADDR"))
        fields = {
            "line1": _clean_text(_logical_value(row, mapping, "MAIL_LINE1")),
            "line2": _clean_text(_logical_value(row, mapping, "MAIL_LINE2")),
            "city": _clean_text(_logical_value(row, mapping, "MAIL_CITY")),
            "state": _clean_text(_logical_value(row, mapping, "MAIL_STAT")),
            "postal_code": _clean_text(_logical_value(row, mapping, "MAIL_ZIP")),
        }
    if raw is None and not any(fields.values()):
        return None
    return {"raw": raw, **fields, "country": "US"}


def _record_from_row(
    row: Mapping[str, Any],
    *,
    row_index: int,
    inspection: LocalDatasetInspection,
) -> dict[str, Any]:
    mapping = inspection.compatibility["logical_to_physical"]
    fips = _clean_text(_logical_value(row, mapping, "FIPS"))
    county = _clean_text(_logical_value(row, mapping, "COUNTY"))
    if fips is None or not re.fullmatch(r"48\d{3}", fips):
        raise TxGIOLandParcelError(
            "txgio_row_county_fips_invalid",
            "TxGIO parcel row lacks a Texas county FIPS",
            details={"row_index": row_index, "fips": fips},
        )
    prop_id = _clean_text(_logical_value(row, mapping, "PROP_ID"))
    geo_id = _clean_text(_logical_value(row, mapping, "GEO_ID"))
    join_id = prop_id or geo_id
    occurrence_field = inspection.compatibility["feature_identity"][
        "feature_occurrence_field"
    ]
    object_id = (
        _clean_text(row.get(occurrence_field))
        if occurrence_field != "DBF record index"
        else None
    )
    occurrence_id = object_id or str(row_index)
    canonical_ref = (
        canonical_property_ref(SOURCE_ID, fips, "parcel", join_id)
        if join_id
        else None
    )
    feature_ref = canonical_property_ref(
        SOURCE_ID,
        fips,
        "parcel_feature",
        f"{join_id or 'unlinked'}:{occurrence_id}:{row_index}",
    )
    owners = []
    seen_owners: set[str] = set()
    for logical, role in (
        ("OWNER_NAME", "assessment_snapshot_owner_name"),
        ("NAME_CARE", "assessment_snapshot_care_of_name"),
    ):
        value = _clean_text(_logical_value(row, mapping, logical))
        if value and value.casefold() not in seen_owners:
            seen_owners.add(value.casefold())
            owners.append(
                {
                    "raw_name": value,
                    "role": role,
                    "source_field": mapping[logical],
                }
            )
    tax_year = _year_value(_logical_value(row, mapping, "TAX_YEAR"))
    year_built = _year_value(
        _logical_value(row, mapping, "YEAR_BUILT"),
        zero_is_missing=True,
    )
    date_acquired, date_acquired_precision = _date_from_integer(
        _logical_value(row, mapping, "DATE_ACQ")
    )
    return {
        "canonical_ref": canonical_ref,
        "feature_ref": feature_ref,
        "evidence_ref": f"TXGIO-LP:{inspection.artifact_sha256}:{row_index}",
        "source_id": SOURCE_ID,
        "record_kind": "parcel_assessment_geometry_snapshot",
        "record_type": "txgio_county_parcel_feature_snapshot",
        "jurisdiction": {
            "state_code": STATE_CODE,
            "county_fips": fips,
            "county_name": county,
        },
        "native_parcel_id": join_id,
        "parcel_identifiers": {"prop_id": prop_id, "geo_id": geo_id},
        "parcel_join_key": {
            "county_fips": fips,
            "preferred_field": "PROP_ID" if prop_id else ("GEO_ID" if geo_id else None),
            "value": join_id,
            "uniqueness_in_artifact": "not_assumed",
        },
        "feature_occurrence": {
            "dbf_record_index": row_index,
            "native_object_id": object_id,
            "feature_ref": feature_ref,
        },
        "owners": owners,
        "situs_address": _structured_address(row, mapping, prefix="SITUS"),
        "mailing_address": _structured_address(row, mapping, prefix="MAIL"),
        "assessment": {
            "tax_year": tax_year,
            "land_value": _logical_value(row, mapping, "LAND_VALUE"),
            "improvement_value": _logical_value(row, mapping, "IMP_VALUE"),
            "market_value": _logical_value(row, mapping, "MKT_VALUE"),
            "currency": "USD",
        },
        "land": {
            "legal_area": _logical_value(row, mapping, "LEGAL_AREA"),
            "legal_area_units": _clean_text(
                _logical_value(row, mapping, "LGL_AREA_UNIT")
            ),
            "gis_area": _logical_value(row, mapping, "GIS_AREA"),
            "gis_area_units": _clean_text(
                _logical_value(row, mapping, "GIS_AREA_UNIT")
            ),
            "state_land_use": _clean_text(
                _logical_value(row, mapping, "STAT_LAND_USE")
            ),
            "local_land_use": _clean_text(
                _logical_value(row, mapping, "LOC_LAND_USE")
            ),
        },
        "legal_description": _clean_text(
            _logical_value(row, mapping, "LEGAL_DESC")
        ),
        "year_built": year_built,
        "source_name": _clean_text(_logical_value(row, mapping, "SOURCE")),
        "date_acquired": date_acquired,
        "date_acquired_precision": date_acquired_precision,
        "geometry_available": {
            "artifact_path": inspection.path,
            "shapefile": dict(inspection.shapefile),
            "projection_wkt": inspection.projection_wkt,
            "dbf_record_index": row_index,
            "projection_status": "geometry_present_not_decoded_by_local_search",
        },
        "artifact_snapshot": {
            "path": inspection.path,
            "sha256": inspection.artifact_sha256,
            "dbf_last_update": inspection.dbf.last_update,
            "dbf_record_index": row_index,
            "dbf_record_count": inspection.dbf.record_count,
            "schema_fingerprint": inspection.schema_fingerprint,
        },
        "source_roles": {
            "owner_name": "county_appraisal_snapshot",
            "legal_description": "appraisal_dataset_attribute",
            "geometry": "county_appraisal_mapping_polygon",
        },
        "schema_fingerprint": inspection.schema_fingerprint,
        "source_url": LANDING_URL,
        "raw_attributes": dict(row),
    }


def _criteria_fingerprint(query: str, field: str, match: str) -> str:
    return sha256_fingerprint(
        {
            "query": query,
            "field": field,
            "match": match,
        }
    )


def _encode_cursor(
    *,
    artifact_sha256: str,
    criteria_fingerprint: str,
    next_row_index: int,
) -> str:
    payload = canonical_json(
        {
            "version": 1,
            "artifact_sha256": artifact_sha256,
            "criteria_fingerprint": criteria_fingerprint,
            "next_row_index": next_row_index,
        }
    ).encode("utf-8")
    return CURSOR_PREFIX + base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(
    value: str | None,
    *,
    artifact_sha256: str,
    criteria_fingerprint: str,
) -> int:
    if value is None:
        return 0
    if not value.startswith(CURSOR_PREFIX):
        raise TxGIOLandParcelError(
            "txgio_cursor_invalid",
            "TxGIO parcel cursor has an unexpected format",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
        )
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
    except (binascii.Error, ValueError, TypeError, json.JSONDecodeError) as error:
        raise TxGIOLandParcelError(
            "txgio_cursor_invalid",
            "TxGIO parcel cursor could not be decoded",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
        ) from error
    if not isinstance(payload, Mapping) or payload.get("version") != 1:
        raise TxGIOLandParcelError(
            "txgio_cursor_invalid",
            "TxGIO parcel cursor version is invalid",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
        )
    if payload.get("artifact_sha256") != artifact_sha256:
        raise TxGIOLandParcelError(
            "txgio_cursor_snapshot_changed",
            "TxGIO parcel cursor belongs to another artifact snapshot",
            status=ResultStatus.SOURCE_CHANGED,
            category="pagination",
        )
    if payload.get("criteria_fingerprint") != criteria_fingerprint:
        raise TxGIOLandParcelError(
            "txgio_cursor_query_changed",
            "TxGIO parcel cursor belongs to different search criteria",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
        )
    next_row_index = payload.get("next_row_index")
    if (
        isinstance(next_row_index, bool)
        or not isinstance(next_row_index, int)
        or next_row_index < 0
    ):
        raise TxGIOLandParcelError(
            "txgio_cursor_invalid",
            "TxGIO parcel cursor row position is invalid",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
        )
    return next_row_index


def _matches(value: Any, query: str, *, field: str, match: str) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    if field == "parcel":
        candidate = re.sub(r"[^a-z0-9]", "", text.casefold())
        needle = re.sub(r"[^a-z0-9]", "", query.casefold())
    else:
        candidate = text.casefold()
        needle = query.casefold()
    if match == "exact":
        return candidate == needle
    if match == "prefix":
        return candidate.startswith(needle)
    return needle in candidate


def search_local_dataset(
    path: Path | str,
    query: str,
    *,
    field: str = "any",
    match: str = "contains",
    limit: int | None = None,
    cursor: str | None = None,
    policy: ArchiveSafetyPolicy | None = None,
) -> tuple[list[dict[str, Any]], str | None, LocalDatasetInspection]:
    query_text = _clean_text(query)
    if query_text is None:
        raise TxGIOLandParcelError(
            "txgio_query_empty",
            "TxGIO parcel search query must not be empty",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
        )
    if field == "parcel" and not re.sub(
        r"[^a-z0-9]",
        "",
        query_text.casefold(),
    ):
        raise TxGIOLandParcelError(
            "txgio_query_empty",
            "TxGIO parcel identifier query must contain a letter or number",
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
        )
    inspection = inspect_local_dataset(path, policy=policy)
    if not inspection.compatibility["search_ready"]:
        raise TxGIOLandParcelError(
            "txgio_published_fields_missing",
            "TxGIO parcel DBF is missing fields from the published schema",
            details=dict(inspection.compatibility),
        )
    criteria = _criteria_fingerprint(query_text, field, match)
    start_row = _decode_cursor(
        cursor,
        artifact_sha256=inspection.artifact_sha256,
        criteria_fingerprint=criteria,
    )
    mapping = inspection.compatibility["logical_to_physical"]
    physical_fields = [
        mapping[logical]
        for logical in SEARCH_FIELDS[field]
        if logical in mapping
    ]
    records: list[dict[str, Any]] = []
    next_row: int | None = None
    with _open_dbf(inspection) as (stream, _archive):
        for row_index, row in _dbf_rows(
            stream,
            inspection.dbf,
            start_row=start_row,
        ):
            if not any(
                _matches(row.get(field_name), query_text, field=field, match=match)
                for field_name in physical_fields
            ):
                continue
            if limit is not None and len(records) >= limit:
                next_row = row_index
                break
            records.append(
                _record_from_row(
                    row,
                    row_index=row_index,
                    inspection=inspection,
                )
            )
    next_cursor = (
        _encode_cursor(
            artifact_sha256=inspection.artifact_sha256,
            criteria_fingerprint=criteria,
            next_row_index=next_row,
        )
        if next_row is not None
        else None
    )
    return records, next_cursor, inspection


def _source_record() -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "record_kind": "source_description",
        "landing_url": LANDING_URL,
        "datahub_url": DATAHUB_URL,
        "collection_api": COLLECTIONS_ENDPOINT,
        "resource_api": RESOURCES_ENDPOINT,
        "schema_reference": SCHEMA_URL,
        "declared_schema": DECLARED_SCHEMA,
        "download_transport": {
            "user_agent": DOWNLOAD_USER_AGENT,
            "verified_source_code": OFFICIAL_DOWNLOADER_SOURCE,
        },
        "release_strategy": "discover latest published collection at runtime",
    }


def _alternatives() -> list[dict[str, Any]]:
    return [
        {
            "route_id": "txgio-datahub-county-archives",
            "name": "TxGIO DataHub county parcel archives",
            "url": DATAHUB_URL,
            "role": "statewide standardized bulk acquisition",
            "integration": "implemented",
        },
        {
            "route_id": "texas-local-appraisal-districts",
            "name": "Texas local appraisal districts and tax offices",
            "url": APPRAISAL_DIRECTORY_URL,
            "role": "newer or more detailed local appraisal and tax information",
            "integration": "directory pivot",
        },
        {
            "route_id": "txgio-current-parcel-map-service",
            "name": "TxGIO most-recent parcel map service",
            "url": CURRENT_MAPSERVER_URL,
            "role": "interactive spatial discovery and map-service metadata",
            "integration": "cataloged complement",
        },
    ]


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    for name in (
        "collection_id",
        "county",
        "artifact",
        "query",
        "field",
        "match",
        "destination",
        "sample_bytes",
    ):
        value = getattr(args, name, None)
        if value is not None:
            parameters[name] = str(value)
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


def _failure(
    query: PublicRecordsQuery,
    error: TxGIOLandParcelError | BulkSourceError,
) -> PublicRecordsResult:
    status = getattr(error, "status", getattr(error, "result_status", None))
    return PublicRecordsResult.failure(
        query,
        status or ResultStatus.UNAVAILABLE,
        [error.to_contract_error()],
    )


def execute(
    args: argparse.Namespace,
    *,
    access_contract: Mapping[str, Any] | None = None,
    client: TxGIODataHubClient | Any | None = None,
    bulk_client: BulkTransferClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = build_query(args)
    try:
        if args.command == "sources":
            result = PublicRecordsResult.success(query, [_source_record()])
        elif args.command == "alternatives":
            result = PublicRecordsResult.success(query, _alternatives())
        elif args.command == "inspect":
            inspection = inspect_local_dataset(
                args.artifact,
                policy=_archive_policy(args),
            )
            result = PublicRecordsResult.success(
                query,
                [
                    {
                        "canonical_ref": (
                            f"TXGIO-LP-INSPECTION:{inspection.artifact_sha256}"
                        ),
                        "source_id": SOURCE_ID,
                        "record_kind": "local_artifact_inspection",
                        "inspection": inspection.to_dict(),
                        "source_url": LANDING_URL,
                    }
                ],
                raw_artifact_refs=[inspection.path],
            )
        elif args.command == "search":
            records, next_cursor, inspection = search_local_dataset(
                args.artifact,
                args.query,
                field=args.field,
                match=args.match,
                limit=args.limit,
                cursor=args.cursor,
                policy=_archive_policy(args),
            )
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=next_cursor,
                raw_artifact_refs=[inspection.path],
            )
        else:
            if access_contract is None:
                _access_contract(args)
            source_client = client or _client(args)
            releases = source_client.releases()
            if args.command == "releases":
                result = PublicRecordsResult.success(query, releases)
            else:
                selected_collection = _selected_collection(
                    releases,
                    args.collection_id,
                )
                if selected_collection is None:
                    result = PublicRecordsResult.success(query, [])
                else:
                    resources = _select_resources(
                        source_client.resources(
                            str(selected_collection["collection_id"])
                        ),
                        args.county,
                    )
                    if not resources:
                        result = PublicRecordsResult.success(query, [])
                    else:
                        manifest = normalize_manifest(
                            selected_collection,
                            resources,
                        )
                        if args.command == "manifest":
                            result = PublicRecordsResult.success(query, [manifest])
                        else:
                            artifact = _manifest_artifact(manifest)
                            transfer = bulk_client or _bulk_client(args)
                            if args.command == "probe":
                                probe = transfer.probe(
                                    artifact,
                                    sample_bytes=args.sample_bytes,
                                )
                                if probe.format_hint != "zip":
                                    raise TxGIOLandParcelError(
                                        "txgio_artifact_format_changed",
                                        "TxGIO county parcel artifact no longer has a ZIP signature",
                                        details={"probe": probe.to_dict()},
                                    )
                                if (
                                    probe.content_length is not None
                                    and artifact.expected_size is not None
                                    and probe.content_length != artifact.expected_size
                                ):
                                    raise TxGIOLandParcelError(
                                        "txgio_artifact_size_changed",
                                        "TxGIO county parcel artifact size differs from its API metadata",
                                        details={
                                            "api_size": artifact.expected_size,
                                            "probe_size": probe.content_length,
                                        },
                                    )
                                result = PublicRecordsResult.success(
                                    query,
                                    [
                                        {
                                            **manifest,
                                            "record_kind": "source_probe",
                                            "selected_artifact": artifact.to_dict(),
                                            "probe": probe.to_dict(),
                                        }
                                    ],
                                )
                            elif args.command == "download":
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
                                record = {
                                    **manifest,
                                    "record_kind": "bulk_artifact_download",
                                    "selected_artifact": artifact.to_dict(),
                                    "download": download.to_dict(),
                                }
                                if args.inspect:
                                    record["inspection"] = inspect_local_dataset(
                                        download.path,
                                        policy=_archive_policy(args),
                                    ).to_dict()
                                result = PublicRecordsResult.success(
                                    query,
                                    [record],
                                    raw_artifact_refs=[download.path],
                                )
                            else:
                                raise ValueError(
                                    f"unsupported TxGIO command {args.command}"
                                )
    except AcquisitionUnavailableError as error:
        decision = error.decision
        result = PublicRecordsResult.failure(
            query,
            ResultStatus(acquisition_result_status(decision)),
            [
                PublicRecordsError(
                    code=str(
                        decision.get("reason_code")
                        or "machine_acquisition_not_available"
                    ),
                    message=str(error),
                    category="access_policy",
                    details=decision,
                )
            ],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except (TxGIOLandParcelError, BulkSourceError) as error:
        result = _failure(query, error)
    except (OSError, zipfile.BadZipFile) as error:
        result = _failure(
            query,
            TxGIOLandParcelError(
                "txgio_local_artifact_error",
                f"Could not read TxGIO parcel artifact: {error}",
                status=ResultStatus.UNAVAILABLE,
                category="local_artifact",
                details={"artifact": getattr(args, "artifact", None)},
            ),
        )
    if log_results:
        result_count = (
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        log_search(canonical_json(query.to_dict()), SOURCE_ID, result_count)
    return result


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
        help="Public-record source catalog",
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
        help="Tracked source manifests and access reviews",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--retry-attempts", type=int, default=3)


def _add_collection_args(
    parser: argparse.ArgumentParser,
    *,
    require_county: bool = False,
) -> None:
    parser.add_argument("--collection-id")
    parser.add_argument("--county", required=require_county)
    _add_runtime_args(parser)


def _add_archive_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-archive-members", type=int)
    parser.add_argument("--max-uncompressed-bytes", type=int)
    parser.add_argument("--max-member-uncompressed-bytes", type=int)
    parser.add_argument("--max-compression-ratio", type=float)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query official TxGIO statewide county parcel archives"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("sources", "Describe the TxGIO source and schema"),
        ("alternatives", "List official complementary Texas property routes"),
    ):
        command = sub.add_parser(name, help=help_text)
        add_output_args(command)

    releases = sub.add_parser(
        "releases",
        help="List every published TxGIO land-parcel collection",
    )
    _add_runtime_args(releases)
    add_output_args(releases)

    manifest = sub.add_parser(
        "manifest",
        help="Build a deterministic collection or county manifest",
    )
    _add_collection_args(manifest)
    add_output_args(manifest)

    probe = sub.add_parser(
        "probe",
        help="Probe one county archive using TxGIO's public transport contract",
    )
    _add_collection_args(probe, require_county=True)
    probe.add_argument("--sample-bytes", type=int, default=4096)
    add_output_args(probe)

    download = sub.add_parser(
        "download",
        help="Download and fingerprint one county archive",
    )
    _add_collection_args(download, require_county=True)
    download.add_argument("--destination", required=True)
    download.add_argument("--expected-sha256")
    download.add_argument("--max-download-bytes", type=int)
    download.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    download.add_argument("--no-resume", action="store_false", dest="resume")
    download.add_argument("--inspect", action="store_true")
    download.set_defaults(resume=True)
    _add_archive_args(download)
    add_output_args(download)

    inspect_command = sub.add_parser(
        "inspect",
        help="Inspect a downloaded county ZIP and its live DBF schema",
    )
    inspect_command.add_argument("artifact")
    _add_archive_args(inspect_command)
    add_output_args(inspect_command)

    search = sub.add_parser(
        "search",
        help="Search the standardized DBF in a downloaded county ZIP",
    )
    search.add_argument("artifact")
    search.add_argument("query")
    search.add_argument("--field", choices=tuple(SEARCH_FIELDS), default="any")
    search.add_argument(
        "--match",
        choices=("contains", "prefix", "exact"),
        default="contains",
    )
    search.add_argument("--limit", type=int)
    search.add_argument("--cursor")
    _add_archive_args(search)
    add_output_args(search)
    return parser


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    for name in (
        "timeout",
        "retry_attempts",
        "sample_bytes",
        "chunk_size",
        "limit",
        "max_download_bytes",
        "max_archive_members",
        "max_uncompressed_bytes",
        "max_member_uncompressed_bytes",
    ):
        value = getattr(args, name, None)
        if value is not None and value <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    ratio = getattr(args, "max_compression_ratio", None)
    if ratio is not None and ratio <= 0:
        parser.error("--max-compression-ratio must be positive")


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=f"TxGIO land parcels {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"TxGIO land parcels {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        label = (
            record.get("county_name")
            or record.get("publication_date")
            or record.get("native_parcel_id")
            or record.get("canonical_ref")
        )
        if label:
            print(f"  {label}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(parser, args)
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
