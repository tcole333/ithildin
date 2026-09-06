#!/usr/bin/env python3
"""Benton County, Oregon taxlot-owner and assessment artifact adapter.

The official county publishes three complementary representations:

* an ArcGIS TaxlotOwners layer containing owner-party, account, situs,
  mailing, map-taxlot, ORTaxlot, and polygon geometry fields;
* current assessment ZIP archives in an IIS directory listing; and
* individually updated assessment-map PDFs in a separate directory.

The components retain distinct source identities and release evidence while
sharing one command-line entry point.

Examples:
    uv run python tools/query_oregon_benton_property.py sources
    uv run python tools/query_oregon_benton_property.py owner "NOLAN LACY"
    uv run python tools/query_oregon_benton_property.py account 802377 --geometry
    uv run python tools/query_oregon_benton_property.py bulk-manifest
    uv run python tools/query_oregon_benton_property.py maps \
        --map-number 11513A --match prefix
    uv run python tools/query_oregon_benton_property.py artifact-probe \
        --component bulk --artifact TaxlotOwners.zip
    uv run python tools/query_oregon_benton_property.py probe --all
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import URLError
from urllib.parse import urljoin, urlparse

import requests

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_bulk import (
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
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
    from tools.public_records_http import (
        ArcGISRESTClient,
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
        arcgis_declared_schema,
        failure_result,
        schema_fingerprint,
        system_trust_session,
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
    from public_records_http import (
        ArcGISRESTClient,
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
        arcgis_declared_schema,
        failure_result,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref


STATE_CODE = "OR"
STATE_FIPS = "41"
COUNTY_GEOID = "41003"
COUNTY_NAME = "Benton County, Oregon"

UMBRELLA_SOURCE_ID = "us-or-benton-county-property-records"
PARCEL_SOURCE_ID = "us-or-benton-county-taxlot-owners"
BULK_SOURCE_ID = "us-or-benton-county-assessment-bulk"
MAP_SOURCE_ID = "us-or-benton-county-assessment-maps"
GIS_ATTRIBUTION_SOURCE_ID = "us-or-benton-county-gis"
ACCOUNT_API_SOURCE_ID = "us-or-benton-county-assessment-account-api"
HELION_SOURCE_ID = "us-or-benton-helion-property"

PARCEL_SERVICE_URL = (
    "https://gis.co.benton.or.us/arcgis/rest/services/"
    "Public/TaxlotOwners/MapServer"
)
PARCEL_LAYER_URL = f"{PARCEL_SERVICE_URL}/0"
PARCEL_QUERY_URL = f"{PARCEL_LAYER_URL}/query"
GIS_ATTRIBUTION_URL = "https://maps.bentoncountyor.gov/"

ASSESSMENT_DIRECTORY_URL = "https://gis.co.benton.or.us/gisdata/Assessment/"
ASSESSMENT_MAP_DIRECTORY_URL = (
    "https://gis.co.benton.or.us/gisdata/Assessment/AssessmentMapsPDF/"
)
ASSESSMENT_TOWNSHIP_DIRECTORY_URL = (
    "https://gis.co.benton.or.us/gisdata/Assessment/"
    "AssessmentMapsByTownship/"
)

ACCOUNT_SEARCH_URL = (
    "https://assessment.bentoncountyor.gov/property-account-search/"
)
ACCOUNT_API_ROOT = "https://assessment.bentoncountyor.gov/wp-json/bcaps/v1"
HELION_URL = "https://apps.benton-or.helioncloud.com/PSO/"

CURRENT_BULK_FILENAMES = (
    "BentonTaxlots.gdb.zip",
    "Taxlot.zip",
    "TaxlotOwners.zip",
)
LEGACY_BULK_FILENAMES = ("BentonTaxlotsGDB.zip",)

EXPECTED_LAYER_NAME = "TaxlotOwners"
EXPECTED_SERVICE_DESCRIPTION = "Benton County Tax Lots with Account Information"
EXPECTED_COPYRIGHT = "Benton County, Oregon"
EXPECTED_SOURCE_WKID = 2913
EXPECTED_SCHEMA_FINGERPRINT = (
    "6cdcc3e2c95aced6f48f23492abf0f10"
    "4a8aafc57c230752f9264136d3848d8e"
)
BASELINE_COUNT = 107_939
BASELINE_OBSERVED_AT = "2026-07-29"
EXPECTED_WGS84_EXTENT = (-123.83, 44.26, -123.05, 44.74)

OUTPUT_SCHEMA_VERSION = "oregon-benton-property/1.0"
PROBE_SCHEMA_VERSION = "oregon-benton-property-probe/1.0"
PARCEL_CURSOR_PREFIX = "oregon-benton-taxlot-owners:v1:"
MAP_CURSOR_PREFIX = "oregon-benton-assessment-maps:v1:"
CURSOR_VERSION = 1

OBJECT_ID_FIELD = "OBJECTID"
REQUIRED_FIELDS = (
    "OBJECTID",
    "Account_Num",
    "MapTaxlot",
    "Tax_Code_Area",
    "ORTaxlot",
    "Situs_Addr1",
    "Situs_City",
    "Situs_State",
    "Situs_Zip",
    "Party_Name",
    "In_Care_Of",
    "Mail_Line1",
    "Mail_Line2",
    "Mail_City",
    "Mail_State",
    "Mail_Zip",
    "MapNumber",
)

PARCEL_SOURCE_METADATA = SourceMetadata(
    source_id=PARCEL_SOURCE_ID,
    name="Benton County Oregon TaxlotOwners",
    source_role="official_county_assessor_taxlot_owner_party_layer",
    base_url=PARCEL_LAYER_URL,
    dataset_id="Public/TaxlotOwners/MapServer/0",
    metadata={
        "publisher": "Benton County GIS and Benton County Assessment",
        "county_geoid": COUNTY_GEOID,
        "record_kind": "taxlot_owner_party",
        "source_crs": "EPSG:2913",
        "official_gis_attribution": GIS_ATTRIBUTION_URL,
        "umbrella_source_id": UMBRELLA_SOURCE_ID,
    },
)

BULK_SOURCE_METADATA = SourceMetadata(
    source_id=BULK_SOURCE_ID,
    name="Benton County Oregon Assessment Bulk Files",
    source_role="official_county_assessment_gis_bulk_snapshots",
    base_url=ASSESSMENT_DIRECTORY_URL,
    dataset_id="Assessment-IIS-directory",
    metadata={
        "publisher": "Benton County GIS",
        "county_geoid": COUNTY_GEOID,
        "release_scope": "county",
        "manifest_transport": "official_iis_directory_listing",
        "official_gis_attribution": GIS_ATTRIBUTION_URL,
        "umbrella_source_id": UMBRELLA_SOURCE_ID,
    },
)

MAP_SOURCE_METADATA = SourceMetadata(
    source_id=MAP_SOURCE_ID,
    name="Benton County Oregon Assessment Map PDFs",
    source_role="official_county_assessment_map_documents",
    base_url=ASSESSMENT_MAP_DIRECTORY_URL,
    dataset_id="AssessmentMapsPDF-IIS-directory",
    metadata={
        "publisher": "Benton County GIS",
        "county_geoid": COUNTY_GEOID,
        "record_kind": "assessment_map",
        "manifest_transport": "official_iis_directory_listing",
        "official_gis_attribution": GIS_ATTRIBUTION_URL,
        "umbrella_source_id": UMBRELLA_SOURCE_ID,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=COUNTY_NAME,
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality="Benton County",
    metadata={"state_fips": STATE_FIPS},
)

BULK_DATA_MODEL = {
    "release_kind": "current_county_snapshot",
    "artifacts": {
        "BentonTaxlots.gdb.zip": {
            "format": "Esri file geodatabase ZIP",
            "scope": "assessment taxlot data",
        },
        "Taxlot.zip": {
            "format": "Esri shapefile ZIP",
            "scope": "taxlot geometry and identifiers",
        },
        "TaxlotOwners.zip": {
            "format": "Esri shapefile ZIP",
            "scope": "taxlot owner-party, address, account, and geometry",
        },
    },
    "source_crs": "EPSG:2913",
    "native_join_fields": [
        "Account_Num",
        "MapTaxlot",
        "ORTaxlot",
        "MapNumber",
    ],
}

CATALOG_METADATA: Mapping[str, Mapping[str, Any]] = {
    PARCEL_SOURCE_ID: {
        "source_id": PARCEL_SOURCE_ID,
        "category": "property",
        "record_types": ["taxlot_owner_party"],
        "jurisdiction": COUNTY_GEOID,
        "access_method": "rest_api",
        "auth": "none",
        "official": True,
        "url": PARCEL_LAYER_URL,
        "query_tool": "tools/query_oregon_benton_property.py",
        "pagination": "object_id_keyset",
        "supports_geometry": True,
    },
    BULK_SOURCE_ID: {
        "source_id": BULK_SOURCE_ID,
        "category": "property",
        "record_types": ["bulk_release"],
        "jurisdiction": COUNTY_GEOID,
        "access_method": "bulk_download",
        "auth": "none",
        "official": True,
        "url": ASSESSMENT_DIRECTORY_URL,
        "query_tool": "tools/query_oregon_benton_property.py",
    },
    MAP_SOURCE_ID: {
        "source_id": MAP_SOURCE_ID,
        "category": "property",
        "record_types": ["assessment_map"],
        "jurisdiction": COUNTY_GEOID,
        "access_method": "bulk_download",
        "auth": "none",
        "official": True,
        "url": ASSESSMENT_MAP_DIRECTORY_URL,
        "query_tool": "tools/query_oregon_benton_property.py",
    },
}


@dataclass(frozen=True)
class SearchColumn:
    name: str
    contains: bool = False


SEARCH_FIELDS: Mapping[str, tuple[SearchColumn, ...]] = {
    "account": (SearchColumn("Account_Num"),),
    "map_taxlot": (SearchColumn("MapTaxlot"),),
    "or_taxlot": (SearchColumn("ORTaxlot"),),
    "map_number": (SearchColumn("MapNumber"),),
    "owner": (SearchColumn("Party_Name", contains=True),),
    "address": (
        SearchColumn("Situs_Addr1", contains=True),
        SearchColumn("Situs_City", contains=True),
        SearchColumn("Mail_Line1", contains=True),
        SearchColumn("Mail_Line2", contains=True),
        SearchColumn("Mail_City", contains=True),
    ),
}


class SelectionError(ValueError):
    """Invalid source selector, cursor, artifact, or map filter."""

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
    source_wkid: int


@dataclass(frozen=True)
class ParcelCursorState:
    operation: str
    criteria_fingerprint: str
    anchor: int
    total_count: int
    schema_fingerprint: str


@dataclass(frozen=True)
class ParcelBatch:
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


@dataclass(frozen=True)
class DirectoryEntry:
    """One file or child directory parsed from an IIS directory listing."""

    name: str
    url: str
    href: str
    modified_raw: str
    modified_local_iso: str
    size: int | None
    is_directory: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "href": self.href,
            "modified_raw": self.modified_raw,
            "modified_local_iso": self.modified_local_iso,
            "source_timezone": "not_declared_by_iis_listing",
            "size": self.size,
            "is_directory": self.is_directory,
        }


@dataclass(frozen=True)
class DirectoryListing:
    source_url: str
    source_path: str
    entries: tuple[DirectoryEntry, ...]
    listing_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_url": self.source_url,
            "source_path": self.source_path,
            "entry_count": len(self.entries),
            "listing_fingerprint": self.listing_fingerprint,
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True)
class MapCursorState:
    criteria_fingerprint: str
    listing_fingerprint: str
    anchor_filename: str


class BentonTaxlotOwnersClient(ArcGISRESTClient):
    """Metadata, service, extent, count, and keyset-page facade."""

    def __init__(
        self,
        *,
        page_size: int,
        timeout: float,
        minimum_interval: float,
        retry_attempts: int,
    ) -> None:
        super().__init__(
            PARCEL_LAYER_URL,
            page_size=page_size,
            timeout=timeout,
            minimum_interval=minimum_interval,
            retry_policy=RetryPolicy(max_attempts=retry_attempts),
            user_agent="Ithildin-Public-Records/1.0",
        )

    def _object(self, url: str, *, params: Mapping[str, Any]) -> Mapping[str, Any]:
        payload = self._request_json(url, params=params)
        if not isinstance(payload, Mapping) or "error" in payload:
            raise SourceResponseError(
                "Benton County ArcGIS returned an invalid response",
                url=url,
                details={"response": payload},
            )
        return payload

    def fetch_metadata(self) -> Mapping[str, Any]:
        return self._object(PARCEL_LAYER_URL, params={"f": "json"})

    def fetch_service_metadata(self) -> Mapping[str, Any]:
        return self._object(PARCEL_SERVICE_URL, params={"f": "json"})

    def fetch_wgs84_extent(self) -> Mapping[str, Any]:
        payload = self._object(
            PARCEL_QUERY_URL,
            params={
                "where": "1=1",
                "returnExtentOnly": "true",
                "outSR": 4326,
                "f": "json",
            },
        )
        extent = payload.get("extent")
        if not isinstance(extent, Mapping):
            raise SourceSchemaError(
                "Benton County ArcGIS extent response lacks an extent object",
                url=PARCEL_QUERY_URL,
            )
        return extent

    def fetch_count(self, where: str) -> int:
        payload = self._object(
            PARCEL_QUERY_URL,
            params={
                "where": where,
                "returnCountOnly": "true",
                "f": "json",
            },
        )
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "Benton County ArcGIS count is not a non-negative integer",
                url=PARCEL_QUERY_URL,
                details={"count": count},
            )
        return count

    def fetch_page(
        self,
        *,
        where: str,
        record_count: int,
        return_geometry: bool,
    ) -> tuple[Mapping[str, Any], ...]:
        params: dict[str, Any] = {
            "where": where,
            "outFields": "*",
            "returnGeometry": str(return_geometry).lower(),
            "resultRecordCount": record_count,
            "orderByFields": f"{OBJECT_ID_FIELD} ASC",
            "f": "json",
        }
        if return_geometry:
            params["outSR"] = 4326
        payload = self._object(PARCEL_QUERY_URL, params=params)
        features = payload.get("features")
        if not isinstance(features, list) or any(
            not isinstance(feature, Mapping) for feature in features
        ):
            raise SourceSchemaError(
                "Benton County ArcGIS response lacks a valid features array",
                url=PARCEL_QUERY_URL,
            )
        return tuple(features)


_IIS_ENTRY_RE = re.compile(
    r"(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+"
    r"(?P<time>\d{1,2}:\d{2}\s+[AP]M)\s+"
    r"(?P<size>\d+|&lt;dir&gt;)\s+"
    r'<A\s+HREF="(?P<href>[^"]+)">(?P<name>[^<]+)</A>',
    re.IGNORECASE,
)


class IISDirectoryClient:
    """Retrying text client for the official county IIS listings."""

    def __init__(
        self,
        *,
        transport: Any = None,
        timeout: float = 30.0,
        minimum_interval: float = 0.25,
        retry_attempts: int = 3,
        sleeper: Any = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if retry_attempts <= 0:
            raise ValueError("retry_attempts must be positive")
        self.transport = transport or system_trust_session()
        self.timeout = timeout
        self.retry_policy = RetryPolicy(max_attempts=retry_attempts)
        self._sleeper = sleeper or time.sleep
        self._rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=self._sleeper,
        )

    def fetch_text(self, url: str) -> str:
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            try:
                response = self.transport.request(
                    "GET",
                    url,
                    params=None,
                    headers={
                        "Accept": "text/html",
                        "User-Agent": "Ithildin-Public-Records/1.0",
                    },
                    timeout=self.timeout,
                )
            except (
                requests.RequestException,
                URLError,
                TimeoutError,
                ConnectionError,
                OSError,
            ) as error:
                last_error = error
                if attempt >= self.retry_policy.max_attempts:
                    raise TransportError(
                        f"Benton County directory request failed: {error}",
                        url=url,
                        details={"attempts": attempt},
                    ) from error
                self._sleeper(self.retry_policy.delay(attempt))
                continue
            status = int(
                getattr(response, "status_code", getattr(response, "status", 0))
            )
            text = getattr(response, "text", "")
            if status in self.retry_policy.retry_statuses:
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt))
                    continue
                if status == 429:
                    raise RateLimitedHTTPError(
                        status,
                        url=url,
                        response_text=str(text),
                    )
                raise HTTPStatusError(
                    status,
                    url=url,
                    response_text=str(text),
                )
            if status in {401, 403}:
                raise RestrictedHTTPError(
                    status,
                    url=url,
                    response_text=str(text),
                )
            if status in {404, 410}:
                raise SourceChangedHTTPError(
                    status,
                    url=url,
                    response_text=str(text),
                )
            if status < 200 or status >= 300:
                raise HTTPStatusError(
                    status,
                    url=url,
                    response_text=str(text),
                )
            return str(text)
        raise TransportError(
            f"Benton County directory request failed: {last_error}",
            url=url,
            details={"attempts": self.retry_policy.max_attempts},
        )

    def listing(self, url: str, *, expected_path: str) -> DirectoryListing:
        return parse_iis_listing(
            self.fetch_text(url),
            source_url=url,
            expected_path=expected_path,
        )


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", "").split()).strip()
    return text or None


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


def _parse_iis_time(date_text: str, time_text: str) -> tuple[str, str]:
    raw = f"{date_text} {time_text}"
    try:
        parsed = datetime.strptime(raw, "%m/%d/%Y %I:%M %p")
    except ValueError as error:
        raise ValueError(f"invalid IIS directory timestamp: {raw}") from error
    return raw, parsed.isoformat(timespec="minutes")


def parse_iis_listing(
    html: str,
    *,
    source_url: str,
    expected_path: str,
) -> DirectoryListing:
    """Parse and positively identify one county IIS directory listing."""

    title_pattern = re.compile(
        r"<title>\s*gis\.co\.benton\.or\.us\s+-\s+"
        + re.escape(expected_path)
        + r"\s*</title>",
        re.IGNORECASE,
    )
    if not title_pattern.search(html):
        raise SourceSchemaError(
            "IIS listing title does not match the Benton County directory",
            url=source_url,
            details={"expected_path": expected_path},
        )
    parsed_url = urlparse(source_url)
    if parsed_url.hostname != "gis.co.benton.or.us":
        raise SourceSchemaError(
            "IIS listing is not hosted by Benton County GIS",
            url=source_url,
            details={"observed_host": parsed_url.hostname},
        )
    entries: list[DirectoryEntry] = []
    expected_prefix = expected_path.rstrip("/") + "/"
    for match in _IIS_ENTRY_RE.finditer(html):
        href = unescape(match.group("href"))
        name = unescape(match.group("name")).strip()
        if name == "[To Parent Directory]":
            continue
        absolute_url = urljoin(source_url, href)
        artifact_path = urlparse(absolute_url).path
        if (
            urlparse(absolute_url).hostname != "gis.co.benton.or.us"
            or not artifact_path.startswith(expected_prefix)
        ):
            raise SourceSchemaError(
                "IIS listing contains an unexpected artifact location",
                url=source_url,
                details={"href": href},
            )
        modified_raw, modified_iso = _parse_iis_time(
            match.group("date"),
            match.group("time"),
        )
        raw_size = match.group("size")
        is_directory = unescape(raw_size).casefold() == "<dir>"
        size = None if is_directory else int(raw_size)
        entries.append(
            DirectoryEntry(
                name=name,
                url=absolute_url,
                href=href,
                modified_raw=modified_raw,
                modified_local_iso=modified_iso,
                size=size,
                is_directory=is_directory,
            )
        )
    if not entries:
        raise SourceSchemaError(
            "Benton County IIS listing contains no entries",
            url=source_url,
        )
    entries.sort(key=lambda entry: entry.name.casefold())
    payload = [entry.to_dict() for entry in entries]
    return DirectoryListing(
        source_url=source_url,
        source_path=expected_path,
        entries=tuple(entries),
        listing_fingerprint=sha256_fingerprint(payload),
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


def _metadata_schema(metadata: Mapping[str, Any]) -> LayerContract:
    if metadata.get("name") != EXPECTED_LAYER_NAME:
        raise SourceSchemaError(
            "Benton County ArcGIS layer name changed",
            url=PARCEL_LAYER_URL,
            details={
                "expected": EXPECTED_LAYER_NAME,
                "observed": metadata.get("name"),
            },
        )
    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "Benton County layer lacks valid field declarations",
            url=PARCEL_LAYER_URL,
        )
    declared_names = {
        str(field.get("name")) for field in fields if field.get("name") is not None
    }
    missing = sorted(set(REQUIRED_FIELDS) - declared_names)
    if missing:
        raise SourceSchemaError(
            "Benton County layer is missing required native fields",
            url=PARCEL_LAYER_URL,
            details={"missing_fields": missing},
        )
    oid = metadata.get("objectIdField")
    if not oid:
        oid = next(
            (
                field.get("name")
                for field in fields
                if field.get("type") == "esriFieldTypeOID"
            ),
            None,
        )
    if oid != OBJECT_ID_FIELD:
        raise SourceSchemaError(
            "Benton County layer object ID field changed",
            url=PARCEL_LAYER_URL,
            details={"expected": OBJECT_ID_FIELD, "observed": oid},
        )
    advanced = metadata.get("advancedQueryCapabilities")
    if (
        not isinstance(advanced, Mapping)
        or not advanced.get("supportsPagination")
        or not advanced.get("supportsOrderBy")
    ):
        raise SourceSchemaError(
            "Benton County layer no longer declares ordered query support",
            url=PARCEL_LAYER_URL,
        )
    maximum = metadata.get("maxRecordCount")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        raise SourceSchemaError(
            "Benton County layer lacks a positive maxRecordCount",
            url=PARCEL_LAYER_URL,
        )
    wkid = _source_wkid(metadata)
    if wkid != EXPECTED_SOURCE_WKID:
        raise SourceSchemaError(
            "Benton County layer source CRS changed",
            url=PARCEL_LAYER_URL,
            details={"expected": EXPECTED_SOURCE_WKID, "observed": wkid},
        )
    return LayerContract(
        schema_fingerprint=schema_fingerprint(arcgis_declared_schema(fields)),
        server_page_size=maximum,
        source_wkid=wkid,
    )


def jurisdiction_identity_evidence(
    *,
    service_url: str,
    service_metadata: Mapping[str, Any],
    wgs84_extent: Mapping[str, Any],
    source_wkid: int,
) -> dict[str, Any]:
    """Evaluate positive county/state identity signals for the ArcGIS source."""

    host = (urlparse(service_url).hostname or "").lower()
    copyright_text = _clean_text(service_metadata.get("copyrightText"))
    description = _clean_text(service_metadata.get("serviceDescription"))
    try:
        extent = (
            float(wgs84_extent["xmin"]),
            float(wgs84_extent["ymin"]),
            float(wgs84_extent["xmax"]),
            float(wgs84_extent["ymax"]),
        )
    except (KeyError, TypeError, ValueError):
        extent = None
    expected_min_x, expected_min_y, expected_max_x, expected_max_y = (
        EXPECTED_WGS84_EXTENT
    )
    extent_matches = bool(
        extent
        and expected_min_x <= extent[0] <= expected_max_x
        and expected_min_y <= extent[1] <= expected_max_y
        and expected_min_x <= extent[2] <= expected_max_x
        and expected_min_y <= extent[3] <= expected_max_y
    )
    signals = {
        "official_host_matches": host == "gis.co.benton.or.us",
        "county_copyright_matches": copyright_text == EXPECTED_COPYRIGHT,
        "service_description_matches": (
            description == EXPECTED_SERVICE_DESCRIPTION
        ),
        "source_crs_matches": source_wkid == EXPECTED_SOURCE_WKID,
        "wgs84_extent_matches": extent_matches,
    }
    return {
        "service_host": host or None,
        "copyright_text": copyright_text,
        "service_description": description,
        "source_wkid": source_wkid,
        "wgs84_extent": list(extent) if extent else None,
        "signals": signals,
        "verified": all(signals.values()),
        "official_gis_attribution_url": GIS_ATTRIBUTION_URL,
    }


def _validate_identity(
    service_metadata: Mapping[str, Any],
    wgs84_extent: Mapping[str, Any],
    contract: LayerContract,
) -> dict[str, Any]:
    evidence = jurisdiction_identity_evidence(
        service_url=PARCEL_SERVICE_URL,
        service_metadata=service_metadata,
        wgs84_extent=wgs84_extent,
        source_wkid=contract.source_wkid,
    )
    if not evidence["verified"]:
        raise SourceSchemaError(
            "Benton County ArcGIS source lacks complete jurisdiction evidence",
            url=PARCEL_SERVICE_URL,
            details=evidence,
        )
    return evidence


def _feature_attributes(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        raise ValueError("Benton County ArcGIS feature lacks attributes")
    return attributes


def _feature_oid(feature: Mapping[str, Any]) -> int:
    value = _feature_attributes(feature).get(OBJECT_ID_FIELD)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SourceSchemaError(
            f"Benton County feature lacks integer {OBJECT_ID_FIELD}",
            url=PARCEL_LAYER_URL,
            details={"value": value},
        )
    return value


def _sql_text(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        raise SelectionError("blank_query", "search value must not be blank")
    return text.replace("'", "''")


def _column_clause(column: SearchColumn, selector: str) -> str:
    value = selector.upper()
    if column.contains:
        return f"UPPER({column.name}) LIKE '%{value}%'"
    return f"UPPER({column.name}) = '{value}'"


def _where(selector: str | None, search_field: str) -> str:
    if search_field == "all":
        return "1=1"
    value = _sql_text(selector)
    groups = tuple(SEARCH_FIELDS) if search_field == "auto" else (search_field,)
    if any(group not in SEARCH_FIELDS for group in groups):
        raise SelectionError(
            "unsupported_search_field",
            f"Benton TaxlotOwners does not publish searchable {search_field} fields",
            details={"supported_fields": sorted(SEARCH_FIELDS)},
        )
    clauses = [
        _column_clause(column, value)
        for group in groups
        for column in SEARCH_FIELDS[group]
    ]
    return clauses[0] if len(clauses) == 1 else f"({' OR '.join(clauses)})"


def _criteria_fingerprint(
    *,
    operation: str,
    where: str,
    geometry: bool,
) -> str:
    return sha256_fingerprint(
        {
            "source_id": PARCEL_SOURCE_ID,
            "operation": operation,
            "where": where,
            "geometry": geometry,
            "ordering": f"{OBJECT_ID_FIELD} ASC",
            "pagination": "object_id_keyset",
        }
    )


def _encode_parcel_cursor(state: ParcelCursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "source": PARCEL_SOURCE_ID,
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
    return f"{PARCEL_CURSOR_PREFIX}{token}"


def _decode_parcel_cursor(cursor: str | None) -> ParcelCursorState | None:
    if cursor is None:
        return None
    if not cursor.startswith(PARCEL_CURSOR_PREFIX):
        raise SelectionError(
            "invalid_cursor",
            "cursor does not belong to the Benton TaxlotOwners adapter",
        )
    token = cursor[len(PARCEL_CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(token + padding).decode())
        state = ParcelCursorState(
            operation=str(payload["operation"]),
            criteria_fingerprint=str(payload["criteria"]),
            anchor=int(payload["anchor"]),
            total_count=int(payload["total"]),
            schema_fingerprint=str(payload["schema"]),
        )
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise SelectionError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from None
    if (
        not isinstance(payload, Mapping)
        or payload.get("v") != CURSOR_VERSION
        or payload.get("source") != PARCEL_SOURCE_ID
        or state.anchor < 0
        or state.total_count < 0
        or not re.fullmatch(r"[0-9a-f]{64}", state.schema_fingerprint)
    ):
        raise SelectionError("invalid_cursor", "cursor values are inconsistent")
    return state


def _after_anchor_where(where: str, anchor: int) -> str:
    return f"({where}) AND {OBJECT_ID_FIELD} > {anchor}"


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


def _fetch_parcel_batch(
    client: Any,
    *,
    operation: str,
    where: str,
    limit: int,
    cursor: str | None,
    return_geometry: bool,
) -> ParcelBatch:
    metadata = client.fetch_metadata()
    contract = _metadata_schema(metadata)
    criteria = _criteria_fingerprint(
        operation=operation,
        where=where,
        geometry=return_geometry,
    )
    cursor_state = _decode_parcel_cursor(cursor)
    if cursor_state is not None:
        if (
            cursor_state.operation != operation
            or cursor_state.criteria_fingerprint != criteria
        ):
            raise SelectionError(
                "cursor_query_mismatch",
                "cursor belongs to different query criteria",
            )
        if cursor_state.schema_fingerprint != contract.schema_fingerprint:
            raise SelectionError(
                "cursor_schema_changed",
                "Benton TaxlotOwners schema changed after cursor issuance",
            )
    initial_count = client.fetch_count(where)
    if cursor_state is not None and cursor_state.total_count != initial_count:
        raise SelectionError(
            "cursor_snapshot_changed",
            "matching TaxlotOwners count changed after cursor issuance",
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
    features: list[Mapping[str, Any]] = []
    errors: list[PublicRecordsError] = []
    pages_fetched = 0
    while len(features) < limit:
        page_where = (
            _after_anchor_where(where, anchor) if anchor is not None else where
        )
        requested = min(page_size, limit - len(features))
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
            oid = _feature_oid(feature)
            if prior is not None and oid <= prior:
                errors.append(
                    _pagination_error(
                        "pagination_repeat_or_reorder",
                        "Benton ArcGIS repeated or reordered a feature",
                        object_id=oid,
                        previous_object_id=prior,
                    )
                )
                break
            features.append(feature)
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
                "matching TaxlotOwners count changed during keyset traversal",
                initial_count=initial_count,
                final_count=final_count,
            )
        )
    remaining = 0
    if anchor is not None and not errors:
        remaining = client.fetch_count(_after_anchor_where(where, anchor))
    next_cursor = None
    if anchor is not None and remaining > 0 and not errors:
        next_cursor = _encode_parcel_cursor(
            ParcelCursorState(
                operation=operation,
                criteria_fingerprint=criteria,
                anchor=anchor,
                total_count=final_count,
                schema_fingerprint=contract.schema_fingerprint,
            )
        )
    return ParcelBatch(
        features=tuple(features),
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
    city: str,
    state: str,
    postal_code: str,
) -> dict[str, Any]:
    line_values: list[str] = []
    seen: set[str] = set()
    for field_name in lines:
        value = _clean_text(attributes.get(field_name))
        if value and value.casefold() not in seen:
            line_values.append(value)
            seen.add(value.casefold())
    city_value = _clean_text(attributes.get(city))
    state_value = _clean_text(attributes.get(state))
    zip_value = _clean_text(attributes.get(postal_code))
    locality = ", ".join(
        value
        for value in (
            city_value,
            " ".join(value for value in (state_value, zip_value) if value),
        )
        if value
    )
    raw = ", ".join([*line_values, *([locality] if locality else [])]) or None
    return {
        "raw": raw,
        "address_lines": line_values,
        "city": city_value,
        "state": state_value,
        "postal_code": zip_value,
        "country": "US",
    }


def _account_complement_links(account: str | None) -> dict[str, str]:
    if not account:
        return {}
    return {
        "county_account_search": ACCOUNT_SEARCH_URL,
        "county_account_summary_api": (
            f"{ACCOUNT_API_ROOT}/bcaps-summary/{account}"
        ),
        "county_value_api": f"{ACCOUNT_API_ROOT}/bcaps-value/{account}",
        "county_sales_api": f"{ACCOUNT_API_ROOT}/bcaps-sales/{account}",
        "county_improvements_api": (
            f"{ACCOUNT_API_ROOT}/bcaps-improvements/{account}"
        ),
        "county_value_graph_api": (
            f"{ACCOUNT_API_ROOT}/bcaps-value-graph/{account}"
        ),
        "helion_property_search": HELION_URL,
    }


def normalize_taxlot_owner(
    feature: Mapping[str, Any],
    *,
    source_schema_fingerprint: str,
    geometry_requested: bool,
) -> dict[str, Any]:
    """Normalize one owner-party row while retaining every native field."""

    attributes = _feature_attributes(feature)
    oid = _feature_oid(feature)
    account = _clean_text(attributes.get("Account_Num"))
    map_taxlot = _clean_text(attributes.get("MapTaxlot"))
    or_taxlot = _clean_text(attributes.get("ORTaxlot"))
    map_number = _clean_text(attributes.get("MapNumber"))
    party_name = _clean_text(attributes.get("Party_Name"))
    geometry = feature.get("geometry") if geometry_requested else None
    if geometry_requested and geometry is not None and not isinstance(
        geometry, Mapping
    ):
        raise ValueError("Benton County geometry is not a JSON object")
    links = _account_complement_links(account)
    if map_number:
        links["candidate_assessment_map_pdf"] = (
            f"{ASSESSMENT_MAP_DIRECTORY_URL}{map_number}.pdf"
        )
    return {
        "canonical_ref": canonical_property_ref(
            PARCEL_SOURCE_ID,
            COUNTY_GEOID,
            "taxlot_owner_party",
            str(oid),
        ),
        "record_kind": "taxlot_owner_party",
        "source_id": PARCEL_SOURCE_ID,
        "county": {
            "name": COUNTY_NAME,
            "geoid": COUNTY_GEOID,
            "state": STATE_CODE,
        },
        "object_id": oid,
        "native_identity": {
            "OBJECTID": oid,
            "Account_Num": account,
            "MapTaxlot": map_taxlot,
            "ORTaxlot": or_taxlot,
            "MapNumber": map_number,
        },
        "account_number": account,
        "map_taxlot": map_taxlot,
        "or_taxlot": or_taxlot,
        "map_number": map_number,
        "tax_code_area": _clean_text(attributes.get("Tax_Code_Area")),
        "owner_party": {
            "raw_name": party_name,
            "in_care_of": _clean_text(attributes.get("In_Care_Of")),
            "role": "assessment_roll_owner_party",
            "assertion_type": "assessment_roll",
            "source_field": "Party_Name",
            "confidence": "high",
        },
        "situs_address": _address(
            attributes,
            lines=("Situs_Addr1",),
            city="Situs_City",
            state="Situs_State",
            postal_code="Situs_Zip",
        ),
        "mailing_address": _address(
            attributes,
            lines=("Mail_Line1", "Mail_Line2"),
            city="Mail_City",
            state="Mail_State",
            postal_code="Mail_Zip",
        ),
        "geometry": dict(geometry) if isinstance(geometry, Mapping) else None,
        "geometry_crs": "EPSG:4326" if geometry is not None else None,
        "source_geometry_crs": "EPSG:2913",
        "official_links": links,
        "update_evidence": {
            "explicit_row_update_field_published": False,
            "observation": (
                "The live layer publishes no row-edit timestamp; schema, count, "
                "service identity, and retrieval time describe the query snapshot. "
                "Current bulk artifacts retain separate directory modification evidence."
            ),
        },
        "native_fields": dict(attributes),
        "provenance": {
            "publisher": "Benton County GIS and Benton County Assessment",
            "layer_url": PARCEL_LAYER_URL,
            "query_url": PARCEL_QUERY_URL,
            "object_id_field": OBJECT_ID_FIELD,
            "object_id": oid,
            "source_schema_fingerprint": source_schema_fingerprint,
            "official_gis_attribution_url": GIS_ATTRIBUTION_URL,
            "entity_grain": (
                "one source row is an owner-party/account assertion and taxlot "
                "geometry may repeat across parties or accounts"
            ),
            "normalization": "source_specific_with_native_fields_retained",
        },
    }


def _directory_client(args: argparse.Namespace) -> IISDirectoryClient:
    return IISDirectoryClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def _parcel_client(args: argparse.Namespace) -> BentonTaxlotOwnersClient:
    return BentonTaxlotOwnersClient(
        page_size=min(args.page_size, 1_000),
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_attempts=args.retry_attempts,
    )


def _bulk_client(args: argparse.Namespace) -> BulkTransferClient:
    return BulkTransferClient(
        timeout=args.timeout,
        max_attempts=args.retry_attempts,
        chunk_size=getattr(args, "chunk_size", 1024 * 1024),
    )


def _assessment_listing(client: Any) -> DirectoryListing:
    return client.listing(
        ASSESSMENT_DIRECTORY_URL,
        expected_path="/gisdata/Assessment/",
    )


def _map_listing(client: Any) -> DirectoryListing:
    return client.listing(
        ASSESSMENT_MAP_DIRECTORY_URL,
        expected_path="/gisdata/Assessment/AssessmentMapsPDF/",
    )


def _entry_by_name(
    listing: DirectoryListing,
    filename: str,
) -> DirectoryEntry | None:
    selector = filename.casefold()
    return next(
        (
            entry
            for entry in listing.entries
            if not entry.is_directory and entry.name.casefold() == selector
        ),
        None,
    )


def _required_entry(
    listing: DirectoryListing,
    filename: str,
) -> DirectoryEntry:
    entry = _entry_by_name(listing, filename)
    if entry is None:
        raise SelectionError(
            "artifact_disappeared",
            f"official directory no longer contains {filename!r}",
        )
    return entry


def _bulk_artifact(entry: DirectoryEntry) -> BulkArtifact:
    if entry.name not in CURRENT_BULK_FILENAMES:
        raise SelectionError(
            "unknown_bulk_artifact",
            f"{entry.name} is not a current Benton assessment artifact",
            details={"current_artifacts": list(CURRENT_BULK_FILENAMES)},
        )
    artifact_id = {
        "BentonTaxlots.gdb.zip": "file_geodatabase",
        "Taxlot.zip": "taxlot_shapefile",
        "TaxlotOwners.zip": "taxlot_owner_shapefile",
    }[entry.name]
    return BulkArtifact(
        artifact_id=artifact_id,
        url=entry.url,
        filename=entry.name,
        media_type="application/zip",
        archive_format="zip",
        expected_size=entry.size,
        last_modified=entry.modified_raw,
        metadata={
            "directory_source_id": BULK_SOURCE_ID,
            "directory_modified_local": entry.modified_local_iso,
            "directory_source_timezone": "not_declared_by_iis_listing",
            "source_crs": "EPSG:2913",
        },
    )


def build_bulk_manifest(listing: DirectoryListing) -> dict[str, Any]:
    """Build the current three-artifact county snapshot manifest."""

    current_entries: list[DirectoryEntry] = []
    missing: list[str] = []
    for filename in CURRENT_BULK_FILENAMES:
        entry = _entry_by_name(listing, filename)
        if entry is None:
            missing.append(filename)
        else:
            current_entries.append(entry)
    if missing:
        raise SourceSchemaError(
            "Benton assessment directory is missing current artifacts",
            url=ASSESSMENT_DIRECTORY_URL,
            details={"missing": missing},
        )
    artifacts = tuple(_bulk_artifact(entry) for entry in current_entries)
    release_basis = {
        "artifacts": [
            {
                "filename": entry.name,
                "size": entry.size,
                "modified_local_iso": entry.modified_local_iso,
            }
            for entry in current_entries
        ],
        "listing_fingerprint": listing.listing_fingerprint,
    }
    release_fingerprint = sha256_fingerprint(release_basis)
    latest_modified = max(
        entry.modified_local_iso for entry in current_entries
    )
    legacy_present = [
        filename
        for filename in LEGACY_BULK_FILENAMES
        if _entry_by_name(listing, filename) is not None
    ]
    manifest = BulkDatasetManifest(
        source_id=BULK_SOURCE_ID,
        dataset_id="Benton-County-Assessment-GIS",
        release=BulkReleaseMetadata(
            release_id=f"directory:{release_fingerprint[:20]}",
            kind="snapshot",
            coverage={
                "county_geoid": COUNTY_GEOID,
                "source_crs": "EPSG:2913",
                "artifact_count": len(artifacts),
            },
        ),
        artifacts=artifacts,
        schema=BULK_DATA_MODEL,
        metadata={
            "source_directory": ASSESSMENT_DIRECTORY_URL,
            "source_listing_fingerprint": listing.listing_fingerprint,
            "latest_directory_modified_local": latest_modified,
            "source_timezone": "not_declared_by_iis_listing",
            "designated_current_filenames": list(CURRENT_BULK_FILENAMES),
            "legacy_similarly_named_artifacts_excluded": legacy_present,
            "official_gis_attribution_url": GIS_ATTRIBUTION_URL,
        },
    )
    return {
        "canonical_ref": canonical_property_ref(
            BULK_SOURCE_ID,
            COUNTY_GEOID,
            "bulk_release",
            manifest.release.release_id,
        ),
        "record_kind": "bulk_release",
        "source_id": BULK_SOURCE_ID,
        "release_kind": "snapshot",
        "manifest": manifest.to_dict(),
        "directory_observation": {
            "listing_fingerprint": listing.listing_fingerprint,
            "entry_count": len(listing.entries),
            "latest_current_artifact_modified_local": latest_modified,
            "source_timezone": "not_declared_by_iis_listing",
        },
    }


def _bulk_artifact_from_release(
    release: Mapping[str, Any],
    selector: str,
) -> BulkArtifact:
    key = selector.strip().casefold()
    if not key:
        raise SelectionError(
            "blank_artifact",
            "artifact selector must not be blank",
        )
    for data in release["manifest"]["artifacts"]:
        aliases = {
            str(data["artifact_id"]).casefold(),
            str(data["filename"]).casefold(),
            Path(str(data["filename"])).stem.casefold(),
        }
        if key in aliases:
            return BulkArtifact(
                artifact_id=str(data["artifact_id"]),
                url=str(data["url"]),
                filename=str(data["filename"]),
                media_type=data.get("media_type"),
                archive_format=data.get("archive_format"),
                expected_size=data.get("expected_size"),
                expected_sha256=data.get("expected_sha256"),
                etag=data.get("etag"),
                last_modified=data.get("last_modified"),
                metadata=data.get("metadata") or {},
            )
    raise SelectionError(
        "unknown_bulk_artifact",
        f"current Benton bulk manifest has no artifact {selector!r}",
        details={"current_artifacts": list(CURRENT_BULK_FILENAMES)},
    )


def _map_kind(stem: str) -> str:
    upper = stem.upper()
    if upper.endswith("MAPINDEX"):
        return "map_index"
    if upper.endswith("DLCINDEX"):
        return "dlc_index"
    if re.search(r"_\d{1,2}-\d{1,2}-\d{4}$", upper):
        return "dated_archive"
    return "assessment_map"


def _map_record(
    entry: DirectoryEntry,
    *,
    listing_fingerprint: str,
) -> dict[str, Any]:
    stem = Path(entry.name).stem
    artifact = BulkArtifact(
        artifact_id=stem,
        url=entry.url,
        filename=entry.name,
        media_type="application/pdf",
        expected_size=entry.size,
        last_modified=entry.modified_raw,
        metadata={
            "directory_source_id": MAP_SOURCE_ID,
            "map_kind": _map_kind(stem),
            "directory_modified_local": entry.modified_local_iso,
            "directory_source_timezone": "not_declared_by_iis_listing",
        },
    )
    return {
        "canonical_ref": canonical_property_ref(
            MAP_SOURCE_ID,
            COUNTY_GEOID,
            "assessment_map",
            entry.name,
        ),
        "record_kind": "assessment_map",
        "source_id": MAP_SOURCE_ID,
        "filename": entry.name,
        "map_number": stem,
        "map_kind": _map_kind(stem),
        "modified_raw": entry.modified_raw,
        "modified_local_iso": entry.modified_local_iso,
        "source_timezone": "not_declared_by_iis_listing",
        "size": entry.size,
        "url": entry.url,
        "artifact": artifact.to_dict(),
        "provenance": {
            "directory_url": ASSESSMENT_MAP_DIRECTORY_URL,
            "listing_fingerprint": listing_fingerprint,
            "official_gis_attribution_url": GIS_ATTRIBUTION_URL,
        },
    }


def _map_criteria(
    *,
    map_number: str | None,
    match_mode: str,
    map_kind: str,
    updated_after: str | None,
) -> dict[str, Any]:
    return {
        "source_id": MAP_SOURCE_ID,
        "map_number": _clean_text(map_number).upper()
        if _clean_text(map_number)
        else None,
        "match": match_mode,
        "map_kind": map_kind,
        "updated_after": updated_after,
        "ordering": "filename_casefold_asc",
    }


def _parse_updated_after(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise SelectionError(
            "invalid_updated_after",
            "--updated-after must be an ISO date",
        ) from error


def _filter_map_entries(
    listing: DirectoryListing,
    *,
    map_number: str | None,
    match_mode: str,
    map_kind: str,
    updated_after: str | None,
) -> list[DirectoryEntry]:
    selector = _clean_text(map_number)
    selector = (
        Path(selector).stem.upper() if selector is not None else None
    )
    after_date = _parse_updated_after(updated_after)
    matches: list[DirectoryEntry] = []
    for entry in listing.entries:
        if entry.is_directory or not entry.name.casefold().endswith(".pdf"):
            continue
        stem = Path(entry.name).stem.upper()
        if selector:
            if match_mode == "exact" and stem != selector:
                continue
            if match_mode == "prefix" and not stem.startswith(selector):
                continue
            if match_mode == "contains" and selector not in stem:
                continue
        if map_kind != "all" and _map_kind(stem) != map_kind:
            continue
        if after_date:
            modified = datetime.fromisoformat(entry.modified_local_iso).date()
            if modified <= after_date:
                continue
        matches.append(entry)
    return sorted(matches, key=lambda entry: entry.name.casefold())


def _encode_map_cursor(state: MapCursorState) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "source": MAP_SOURCE_ID,
        "criteria": state.criteria_fingerprint,
        "listing": state.listing_fingerprint,
        "anchor": state.anchor_filename,
    }
    token = (
        base64.urlsafe_b64encode(canonical_json(payload).encode())
        .decode()
        .rstrip("=")
    )
    return f"{MAP_CURSOR_PREFIX}{token}"


def _decode_map_cursor(cursor: str | None) -> MapCursorState | None:
    if cursor is None:
        return None
    if not cursor.startswith(MAP_CURSOR_PREFIX):
        raise SelectionError(
            "invalid_map_cursor",
            "cursor does not belong to Benton assessment maps",
        )
    token = cursor[len(MAP_CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(token + padding).decode())
        state = MapCursorState(
            criteria_fingerprint=str(payload["criteria"]),
            listing_fingerprint=str(payload["listing"]),
            anchor_filename=str(payload["anchor"]),
        )
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise SelectionError(
            "invalid_map_cursor",
            "assessment-map cursor payload is malformed",
        ) from None
    if (
        not isinstance(payload, Mapping)
        or payload.get("v") != CURSOR_VERSION
        or payload.get("source") != MAP_SOURCE_ID
        or not re.fullmatch(r"[0-9a-f]{64}", state.criteria_fingerprint)
        or not re.fullmatch(r"[0-9a-f]{64}", state.listing_fingerprint)
        or not state.anchor_filename
    ):
        raise SelectionError(
            "invalid_map_cursor",
            "assessment-map cursor values are inconsistent",
        )
    return state


def map_records(
    listing: DirectoryListing,
    *,
    map_number: str | None,
    match_mode: str,
    map_kind: str,
    updated_after: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[dict[str, Any]], str | None, int]:
    criteria = _map_criteria(
        map_number=map_number,
        match_mode=match_mode,
        map_kind=map_kind,
        updated_after=updated_after,
    )
    criteria_fingerprint = sha256_fingerprint(criteria)
    cursor_state = _decode_map_cursor(cursor)
    if cursor_state is not None:
        if cursor_state.criteria_fingerprint != criteria_fingerprint:
            raise SelectionError(
                "map_cursor_query_mismatch",
                "assessment-map cursor belongs to different filters",
            )
        if cursor_state.listing_fingerprint != listing.listing_fingerprint:
            raise SelectionError(
                "map_listing_changed",
                "assessment-map directory changed after cursor issuance",
            )
    matches = _filter_map_entries(
        listing,
        map_number=map_number,
        match_mode=match_mode,
        map_kind=map_kind,
        updated_after=updated_after,
    )
    if cursor_state is not None:
        matches = [
            entry
            for entry in matches
            if entry.name.casefold()
            > cursor_state.anchor_filename.casefold()
        ]
    selected = matches[:limit]
    records = [
        _map_record(
            entry,
            listing_fingerprint=listing.listing_fingerprint,
        )
        for entry in selected
    ]
    next_cursor = None
    if len(matches) > len(selected) and selected:
        next_cursor = _encode_map_cursor(
            MapCursorState(
                criteria_fingerprint=criteria_fingerprint,
                listing_fingerprint=listing.listing_fingerprint,
                anchor_filename=selected[-1].name,
            )
        )
    return records, next_cursor, len(matches)


def _map_artifact_from_listing(
    listing: DirectoryListing,
    selector: str,
) -> BulkArtifact:
    filename = selector.strip()
    if not filename:
        raise SelectionError(
            "blank_artifact",
            "assessment-map artifact selector must not be blank",
        )
    if not filename.casefold().endswith(".pdf"):
        filename = f"{filename}.pdf"
    entry = _entry_by_name(listing, filename)
    if entry is None:
        raise SelectionError(
            "unknown_map_artifact",
            f"assessment-map directory has no artifact {filename!r}",
        )
    return BulkArtifact(
        artifact_id=Path(entry.name).stem,
        url=entry.url,
        filename=entry.name,
        media_type="application/pdf",
        expected_size=entry.size,
        last_modified=entry.modified_raw,
        metadata={
            "directory_source_id": MAP_SOURCE_ID,
            "map_kind": _map_kind(Path(entry.name).stem),
            "directory_modified_local": entry.modified_local_iso,
            "directory_source_timezone": "not_declared_by_iis_listing",
        },
    )


def _public_query(
    source: SourceMetadata,
    *,
    operation: str,
    parameters: Mapping[str, Any],
    limit: int | None = None,
    cursor: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=source,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
            metadata=dict(metadata or {}),
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


def _parcel_command_field(args: argparse.Namespace) -> str:
    command_fields = {
        "owner": "owner",
        "address": "address",
        "account": "account",
        "map-taxlot": "map_taxlot",
        "or-taxlot": "or_taxlot",
        "map-number": "map_number",
        "scan": "all",
    }
    return command_fields.get(args.command, args.field)


def _parcel_result(
    query: PublicRecordsQuery,
    batch: ParcelBatch,
    *,
    geometry_requested: bool,
) -> PublicRecordsResult:
    errors = list(batch.errors)
    records: list[dict[str, Any]] = []
    for index, feature in enumerate(batch.features):
        try:
            records.append(
                normalize_taxlot_owner(
                    feature,
                    source_schema_fingerprint=batch.schema_fingerprint,
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
    snapshot = {
        "total_matching_owner_party_rows": batch.total_count,
        "start_object_id_exclusive": batch.start_anchor,
        "end_object_id_inclusive": batch.end_anchor,
        "returned_rows": len(records),
        "remaining_after_anchor": batch.remaining_after_anchor,
        "continuation_available": batch.next_cursor is not None,
        "pages_fetched": batch.pages_fetched,
        "source_schema_fingerprint": batch.schema_fingerprint,
        "source_entity_grain": "taxlot_owner_party",
    }
    for record in records:
        record["retrieval_snapshot"] = snapshot
    if errors:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL if records else ResultStatus.SOURCE_CHANGED,
            errors,
            records=records,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=batch.next_cursor,
    )


def execute_parcel_query(
    args: argparse.Namespace,
    *,
    client: Any = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    search_field = _parcel_command_field(args)
    selector = getattr(args, "query", None)
    query = _public_query(
        PARCEL_SOURCE_METADATA,
        operation=args.command,
        parameters={
            "selector": selector,
            "field": search_field,
            "geometry": args.geometry,
        },
        limit=args.limit,
        cursor=args.cursor,
        metadata={
            "pagination": "object_id_keyset",
            "ordering": f"{OBJECT_ID_FIELD} ASC",
            "record_grain": "taxlot_owner_party",
        },
    )
    try:
        where = _where(selector, search_field)
        batch = _fetch_parcel_batch(
            client or _parcel_client(args),
            operation=args.command,
            where=where,
            limit=args.limit,
            cursor=args.cursor,
            return_geometry=args.geometry,
        )
        result = _parcel_result(
            query,
            batch,
            geometry_requested=args.geometry,
        )
    except SelectionError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="benton_parcel_adapter_failure",
                    message=str(error),
                    category="source_schema",
                )
            ],
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def execute_bulk_manifest(
    args: argparse.Namespace,
    *,
    directory_client: Any = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = _public_query(
        BULK_SOURCE_METADATA,
        operation="bulk-manifest",
        parameters={"designated_artifacts": list(CURRENT_BULK_FILENAMES)},
    )
    try:
        listing = _assessment_listing(
            directory_client or _directory_client(args)
        )
        result = PublicRecordsResult.success(
            query,
            [build_bulk_manifest(listing)],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except (SelectionError, TypeError, ValueError) as error:
        contract_error = (
            error.to_contract_error()
            if isinstance(error, SelectionError)
            else PublicRecordsError(
                code="benton_bulk_manifest_changed",
                message=str(error),
                category="source_schema",
            )
        )
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [contract_error],
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def execute_maps(
    args: argparse.Namespace,
    *,
    directory_client: Any = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = _public_query(
        MAP_SOURCE_METADATA,
        operation="maps",
        parameters={
            "map_number": args.map_number,
            "match": args.match,
            "map_kind": args.map_kind,
            "updated_after": args.updated_after,
        },
        limit=args.limit,
        cursor=args.cursor,
        metadata={
            "pagination": "filename_keyset_bound_to_listing_fingerprint",
            "ordering": "filename_casefold_asc",
        },
    )
    try:
        listing = _map_listing(directory_client or _directory_client(args))
        records, next_cursor, remaining_window = map_records(
            listing,
            map_number=args.map_number,
            match_mode=args.match,
            map_kind=args.map_kind,
            updated_after=args.updated_after,
            limit=args.limit,
            cursor=args.cursor,
        )
        for record in records:
            record["retrieval_snapshot"] = {
                "directory_entry_count": len(listing.entries),
                "filtered_rows_from_cursor": remaining_window,
                "returned_rows": len(records),
                "continuation_available": next_cursor is not None,
                "listing_fingerprint": listing.listing_fingerprint,
            }
        result = PublicRecordsResult.success(
            query,
            records,
            next_cursor=next_cursor,
        )
    except SelectionError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="benton_map_manifest_changed",
                    message=str(error),
                    category="source_schema",
                )
            ],
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def _artifact_source(component: str) -> SourceMetadata:
    if component == "bulk":
        return BULK_SOURCE_METADATA
    if component == "map":
        return MAP_SOURCE_METADATA
    raise SelectionError(
        "unknown_artifact_component",
        f"unknown Benton artifact component: {component}",
    )


def _resolve_artifact(
    args: argparse.Namespace,
    directory_client: Any,
) -> tuple[dict[str, Any], BulkArtifact]:
    if args.component == "bulk":
        listing = _assessment_listing(directory_client)
        release = build_bulk_manifest(listing)
        return release, _bulk_artifact_from_release(release, args.artifact)
    listing = _map_listing(directory_client)
    artifact = _map_artifact_from_listing(listing, args.artifact)
    record = _map_record(
        _required_entry(listing, artifact.filename),
        listing_fingerprint=listing.listing_fingerprint,
    )
    return record, artifact


def execute_artifact_probe(
    args: argparse.Namespace,
    *,
    directory_client: Any = None,
    bulk_client: Any = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    source = _artifact_source(args.component)
    query = _public_query(
        source,
        operation="artifact-probe",
        parameters={
            "component": args.component,
            "artifact": args.artifact,
            "range_bytes": args.range_bytes,
        },
    )
    try:
        context, artifact = _resolve_artifact(
            args,
            directory_client or _directory_client(args),
        )
        probe = (bulk_client or _bulk_client(args)).probe(
            artifact,
            sample_bytes=args.range_bytes,
        )
        if (
            artifact.expected_size is not None
            and probe.content_length is not None
            and artifact.expected_size != probe.content_length
        ):
            raise SourceSchemaError(
                "artifact size differs from the official directory listing",
                url=artifact.url,
                details={
                    "directory_size": artifact.expected_size,
                    "probe_size": probe.content_length,
                },
            )
        result = PublicRecordsResult.success(
            query,
            [
                {
                    "source_context": context,
                    "selected_artifact": artifact.to_dict(),
                    "probe": probe.to_dict(),
                }
            ],
        )
    except SelectionError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except BulkSourceError as error:
        result = PublicRecordsResult.failure(
            query,
            error.result_status,
            [error.to_contract_error()],
        )
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="benton_artifact_probe_failed",
                    message=str(error),
                    category="source_schema",
                )
            ],
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def execute_artifact_download(
    args: argparse.Namespace,
    *,
    directory_client: Any = None,
    bulk_client: Any = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    source = _artifact_source(args.component)
    query = _public_query(
        source,
        operation="artifact-download",
        parameters={
            "component": args.component,
            "artifact": args.artifact,
            "destination": args.destination,
            "resume": args.resume,
            "expected_sha256": args.expected_sha256,
            "max_download_bytes": args.max_download_bytes,
            "dry_run": args.dry_run,
        },
    )
    try:
        context, artifact = _resolve_artifact(
            args,
            directory_client or _directory_client(args),
        )
        if args.expected_sha256:
            artifact = replace(
                artifact,
                expected_sha256=args.expected_sha256,
            )
        destination = Path(args.destination)
        if destination.exists() and destination.is_dir():
            destination = destination / artifact.filename
        if args.dry_run:
            output = {
                "source_context": context,
                "selected_artifact": artifact.to_dict(),
                "download": {
                    "status": "planned",
                    "destination": str(destination),
                    "resume": args.resume,
                    "max_bytes": args.max_download_bytes,
                    "checksum_verification": (
                        "caller_expected_sha256"
                        if args.expected_sha256
                        else "source_checksum_if_published_plus_computed_sha256"
                    ),
                },
            }
            result = PublicRecordsResult.success(query, [output])
        else:
            download = (bulk_client or _bulk_client(args)).download(
                artifact,
                destination,
                resume=args.resume,
                max_bytes=args.max_download_bytes,
            )
            output = {
                "source_context": context,
                "selected_artifact": artifact.to_dict(),
                "download": download.to_dict(),
                "integrity": {
                    "computed_sha256": download.sha256,
                    "expected_sha256": download.expected_sha256,
                    "expected_checksum_matched": (
                        download.expected_sha256 is not None
                        and download.sha256 == download.expected_sha256
                    ),
                    "source_size_matched": (
                        artifact.expected_size is None
                        or artifact.expected_size == download.size
                    ),
                },
            }
            if args.component == "bulk":
                output["archive"] = inspect_zip(download.path).to_dict()
            result = PublicRecordsResult.success(
                query,
                [output],
                raw_artifact_refs=[download.path],
            )
    except SelectionError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except BulkSourceError as error:
        result = PublicRecordsResult.failure(
            query,
            error.result_status,
            [error.to_contract_error()],
        )
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="local_io_error",
                    message=str(error),
                    category="local_io",
                )
            ],
        )
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="benton_artifact_download_failed",
                    message=str(error),
                    category="source_schema",
                )
            ],
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def execute_parcel_probe(
    args: argparse.Namespace,
    *,
    client: Any = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = _public_query(
        PARCEL_SOURCE_METADATA,
        operation="probe",
        parameters={
            "component": "parcel",
            "sentinel_account": "000012",
            "geometry": True,
        },
        limit=1,
    )
    try:
        source_client = client or _parcel_client(args)
        metadata = source_client.fetch_metadata()
        contract = _metadata_schema(metadata)
        service = source_client.fetch_service_metadata()
        wgs84_extent = source_client.fetch_wgs84_extent()
        identity = _validate_identity(service, wgs84_extent, contract)
        total_count = source_client.fetch_count("1=1")
        sentinel_where = _where("000012", "account")
        sentinel_count = source_client.fetch_count(sentinel_where)
        if sentinel_count <= 0:
            raise SourceSchemaError(
                "Benton TaxlotOwners sentinel account was not found",
                url=PARCEL_QUERY_URL,
            )
        rows = source_client.fetch_page(
            where=sentinel_where,
            record_count=1,
            return_geometry=True,
        )
        if len(rows) != 1:
            raise SourceSchemaError(
                "Benton TaxlotOwners sentinel did not return one row",
                url=PARCEL_QUERY_URL,
                details={"returned": len(rows)},
            )
        representative = normalize_taxlot_owner(
            rows[0],
            source_schema_fingerprint=contract.schema_fingerprint,
            geometry_requested=True,
        )
        result = PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": PARCEL_SOURCE_ID,
                    "component": "parcel_api",
                    "layer_identity": {
                        "service_url": PARCEL_SERVICE_URL,
                        "layer_url": PARCEL_LAYER_URL,
                        "layer_id": 0,
                        "layer_name": metadata.get("name"),
                        "object_id_field": OBJECT_ID_FIELD,
                        "geometry_type": metadata.get("geometryType"),
                        "source_crs": f"EPSG:{contract.source_wkid}",
                        "maximum_page_size": contract.server_page_size,
                        "supported_query_formats": metadata.get(
                            "supportedQueryFormats"
                        ),
                    },
                    "jurisdiction_identity": identity,
                    "component_total_count": total_count,
                    "count_baseline": {
                        "observed_count": BASELINE_COUNT,
                        "observed_at": BASELINE_OBSERVED_AT,
                        "current_count": total_count,
                    },
                    "schema_fingerprint": contract.schema_fingerprint,
                    "schema_baseline": {
                        "expected_fingerprint": EXPECTED_SCHEMA_FINGERPRINT,
                        "matches": (
                            contract.schema_fingerprint
                            == EXPECTED_SCHEMA_FINGERPRINT
                        ),
                        "field_count": len(metadata.get("fields", [])),
                    },
                    "update_evidence": {
                        "explicit_row_update_field_published": False,
                        "snapshot_signals": [
                            "schema_fingerprint",
                            "component_total_count",
                            "service_identity",
                            "retrieval_timestamp",
                        ],
                    },
                    "sentinel_count": sentinel_count,
                    "representative_row": representative,
                }
            ],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="benton_parcel_probe_failed",
                    message=str(error),
                    category="source_schema",
                )
            ],
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def execute_bulk_probe(
    args: argparse.Namespace,
    *,
    directory_client: Any = None,
    bulk_client: Any = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = _public_query(
        BULK_SOURCE_METADATA,
        operation="probe",
        parameters={
            "component": "bulk",
            "range_bytes": args.range_bytes,
            "artifacts": list(CURRENT_BULK_FILENAMES),
        },
    )
    try:
        listing = _assessment_listing(
            directory_client or _directory_client(args)
        )
        release = build_bulk_manifest(listing)
        transfer = bulk_client or _bulk_client(args)
        probes: list[dict[str, Any]] = []
        for data in release["manifest"]["artifacts"]:
            artifact = BulkArtifact(
                artifact_id=str(data["artifact_id"]),
                url=str(data["url"]),
                filename=str(data["filename"]),
                media_type=data.get("media_type"),
                archive_format=data.get("archive_format"),
                expected_size=data.get("expected_size"),
                expected_sha256=data.get("expected_sha256"),
                etag=data.get("etag"),
                last_modified=data.get("last_modified"),
                metadata=data.get("metadata") or {},
            )
            probe = transfer.probe(
                artifact,
                sample_bytes=args.range_bytes,
            )
            if (
                artifact.expected_size is not None
                and probe.content_length is not None
                and artifact.expected_size != probe.content_length
            ):
                raise SourceSchemaError(
                    "bulk artifact size differs from directory listing",
                    url=artifact.url,
                    details={
                        "directory_size": artifact.expected_size,
                        "probe_size": probe.content_length,
                    },
                )
            if args.range_bytes > 0 and probe.format_hint != "zip":
                raise SourceSchemaError(
                    "bulk artifact does not have a ZIP signature",
                    url=artifact.url,
                    details={"signature_hex": probe.signature_hex},
                )
            probes.append(
                {
                    "artifact": artifact.to_dict(),
                    "probe": probe.to_dict(),
                }
            )
        result = PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": BULK_SOURCE_ID,
                    "component": "assessment_bulk",
                    "directory_identity": {
                        "url": ASSESSMENT_DIRECTORY_URL,
                        "host": "gis.co.benton.or.us",
                        "path": "/gisdata/Assessment/",
                        "official_gis_attribution_url": GIS_ATTRIBUTION_URL,
                    },
                    "directory_entry_count": len(listing.entries),
                    "listing_fingerprint": listing.listing_fingerprint,
                    "release": release,
                    "artifact_probes": probes,
                }
            ],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except BulkSourceError as error:
        result = PublicRecordsResult.failure(
            query,
            error.result_status,
            [error.to_contract_error()],
        )
    except (SelectionError, TypeError, ValueError) as error:
        contract_error = (
            error.to_contract_error()
            if isinstance(error, SelectionError)
            else PublicRecordsError(
                code="benton_bulk_probe_failed",
                message=str(error),
                category="source_schema",
            )
        )
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [contract_error],
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def execute_map_probe(
    args: argparse.Namespace,
    *,
    directory_client: Any = None,
    bulk_client: Any = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    map_artifact = getattr(args, "map_artifact", None) or "10329.pdf"
    query = _public_query(
        MAP_SOURCE_METADATA,
        operation="probe",
        parameters={
            "component": "maps",
            "map_artifact": map_artifact,
            "range_bytes": args.range_bytes,
        },
    )
    try:
        listing = _map_listing(directory_client or _directory_client(args))
        pdf_entries = [
            entry
            for entry in listing.entries
            if not entry.is_directory and entry.name.casefold().endswith(".pdf")
        ]
        artifact = _map_artifact_from_listing(listing, map_artifact)
        probe = (bulk_client or _bulk_client(args)).probe(
            artifact,
            sample_bytes=args.range_bytes,
        )
        if (
            artifact.expected_size is not None
            and probe.content_length is not None
            and artifact.expected_size != probe.content_length
        ):
            raise SourceSchemaError(
                "assessment-map size differs from directory listing",
                url=artifact.url,
            )
        if (
            args.range_bytes > 0
            and not (probe.signature_hex or "").startswith("25504446")
        ):
            raise SourceSchemaError(
                "assessment-map artifact lacks a PDF signature",
                url=artifact.url,
                details={"signature_hex": probe.signature_hex},
            )
        latest = max(
            pdf_entries,
            key=lambda entry: (
                entry.modified_local_iso,
                entry.name.casefold(),
            ),
        )
        result = PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": MAP_SOURCE_ID,
                    "component": "assessment_maps",
                    "directory_identity": {
                        "url": ASSESSMENT_MAP_DIRECTORY_URL,
                        "host": "gis.co.benton.or.us",
                        "path": (
                            "/gisdata/Assessment/AssessmentMapsPDF/"
                        ),
                        "official_gis_attribution_url": GIS_ATTRIBUTION_URL,
                    },
                    "pdf_count": len(pdf_entries),
                    "listing_fingerprint": listing.listing_fingerprint,
                    "latest_directory_entry": latest.to_dict(),
                    "representative_map": _map_record(
                        _required_entry(listing, artifact.filename),
                        listing_fingerprint=listing.listing_fingerprint,
                    ),
                    "artifact_probe": probe.to_dict(),
                }
            ],
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error)
    except BulkSourceError as error:
        result = PublicRecordsResult.failure(
            query,
            error.result_status,
            [error.to_contract_error()],
        )
    except (SelectionError, TypeError, ValueError) as error:
        contract_error = (
            error.to_contract_error()
            if isinstance(error, SelectionError)
            else PublicRecordsError(
                code="benton_map_probe_failed",
                message=str(error),
                category="source_schema",
            )
        )
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [contract_error],
        )
    if log_results:
        _best_effort_log(query, result)
    return result


def _sources_payload() -> dict[str, Any]:
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "umbrella_source_id": UMBRELLA_SOURCE_ID,
        "sources": [
            {
                **PARCEL_SOURCE_METADATA.to_dict(),
                "catalog_metadata": CATALOG_METADATA[PARCEL_SOURCE_ID],
                "search_fields": sorted(SEARCH_FIELDS),
                "required_fields": list(REQUIRED_FIELDS),
                "expected_schema_fingerprint": EXPECTED_SCHEMA_FINGERPRINT,
                "baseline_count": BASELINE_COUNT,
                "baseline_observed_at": BASELINE_OBSERVED_AT,
            },
            {
                **BULK_SOURCE_METADATA.to_dict(),
                "catalog_metadata": CATALOG_METADATA[BULK_SOURCE_ID],
                "current_artifacts": list(CURRENT_BULK_FILENAMES),
                "legacy_artifacts_not_in_current_manifest": list(
                    LEGACY_BULK_FILENAMES
                ),
            },
            {
                **MAP_SOURCE_METADATA.to_dict(),
                "catalog_metadata": CATALOG_METADATA[MAP_SOURCE_ID],
                "map_directory": ASSESSMENT_MAP_DIRECTORY_URL,
                "township_directory": ASSESSMENT_TOWNSHIP_DIRECTORY_URL,
                "filter_fields": [
                    "map_number",
                    "match",
                    "map_kind",
                    "updated_after",
                ],
            },
        ],
        "complementary_sources": [
            {
                "source_id": ACCOUNT_API_SOURCE_ID,
                "name": "Benton County Assessment Property Account Search",
                "url": ACCOUNT_SEARCH_URL,
                "anonymous_endpoint_templates": [
                    f"{ACCOUNT_API_ROOT}/bcaps-summary/{{ACCOUNT}}",
                    f"{ACCOUNT_API_ROOT}/bcaps-value/{{ACCOUNT}}",
                    f"{ACCOUNT_API_ROOT}/bcaps-sales/{{ACCOUNT}}",
                    f"{ACCOUNT_API_ROOT}/bcaps-improvements/{{ACCOUNT}}",
                    f"{ACCOUNT_API_ROOT}/bcaps-value-graph/{{ACCOUNT}}",
                ],
                "join_fields": ["Account_Num", "MapTaxlot", "Party_Name"],
                "adds": [
                    "account summary",
                    "value history",
                    "sales",
                    "improvements",
                    "value graph",
                ],
            },
            {
                "source_id": HELION_SOURCE_ID,
                "name": "Benton County Helion Property Search Online",
                "url": HELION_URL,
                "join_fields": ["Account_Num", "MapTaxlot", "Party_Name"],
                "relationship": "separately_integrated_property_detail_tenant",
            },
            {
                "source_id": GIS_ATTRIBUTION_SOURCE_ID,
                "name": "Benton County GIS, Oregon",
                "url": GIS_ATTRIBUTION_URL,
                "adds": [
                    "official publisher attribution",
                    "interactive maps",
                    "public GIS data links",
                ],
            },
        ],
        "process_learnings": [
            {
                "scope": "entity_grain",
                "learning": (
                    "TaxlotOwners is an owner-party layer, so a taxlot or "
                    "account can legitimately repeat across party assertions."
                ),
            },
            {
                "scope": "component_identity",
                "learning": (
                    "Live owner-party rows, bulk assessment snapshots, and "
                    "individually updated map PDFs retain separate source IDs "
                    "and release evidence."
                ),
            },
            {
                "scope": "current_artifact_selection",
                "learning": (
                    "Exact designated filenames distinguish the current "
                    "BentonTaxlots.gdb.zip from the older similarly named "
                    "BentonTaxlotsGDB.zip."
                ),
            },
            {
                "scope": "directory_time_provenance",
                "learning": (
                    "IIS listing times are retained as local display values "
                    "because the listing does not declare its timezone; HTTP "
                    "artifact probes preserve independent Last-Modified values."
                ),
            },
        ],
    }


def execute_all_probes(
    args: argparse.Namespace,
    *,
    log_results: bool = True,
) -> dict[str, Any]:
    components = [
        execute_parcel_probe(args, log_results=log_results).to_dict(),
        execute_bulk_probe(args, log_results=log_results).to_dict(),
        execute_map_probe(args, log_results=log_results).to_dict(),
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
    parcel_client: Any = None,
    directory_client: Any = None,
    bulk_client: Any = None,
    log_results: bool = True,
) -> PublicRecordsResult | dict[str, Any]:
    """Execute a source listing, query, manifest, transfer, or live probe."""

    if args.command == "sources":
        return _sources_payload()
    if args.command in {
        "search",
        "owner",
        "address",
        "account",
        "map-taxlot",
        "or-taxlot",
        "map-number",
        "scan",
    }:
        return execute_parcel_query(
            args,
            client=parcel_client,
            log_results=log_results,
        )
    if args.command == "bulk-manifest":
        return execute_bulk_manifest(
            args,
            directory_client=directory_client,
            log_results=log_results,
        )
    if args.command == "maps":
        return execute_maps(
            args,
            directory_client=directory_client,
            log_results=log_results,
        )
    if args.command == "artifact-probe":
        return execute_artifact_probe(
            args,
            directory_client=directory_client,
            bulk_client=bulk_client,
            log_results=log_results,
        )
    if args.command == "artifact-download":
        return execute_artifact_download(
            args,
            directory_client=directory_client,
            bulk_client=bulk_client,
            log_results=log_results,
        )
    if args.command == "probe":
        if args.all_components:
            return execute_all_probes(args, log_results=log_results)
        if args.component == "parcel":
            return execute_parcel_probe(
                args,
                client=parcel_client,
                log_results=log_results,
            )
        if args.component == "bulk":
            return execute_bulk_probe(
                args,
                directory_client=directory_client,
                bulk_client=bulk_client,
                log_results=log_results,
            )
        return execute_map_probe(
            args,
            directory_client=directory_client,
            bulk_client=bulk_client,
            log_results=log_results,
        )
    raise ValueError(f"unknown command: {args.command}")


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
        summary=f"Benton County property {args.command}",
        result_count=count,
    ):
        return
    if args.command == "sources":
        print(f"Benton County property sources: {count}")
        for source in payload["sources"]:
            print(
                f"  {source['source_id']} | "
                f"{source['source_role']} | {source['base_url']}"
            )
        return
    if args.command == "probe" and args.all_components:
        print(f"Benton County property probes: {payload['status']}")
        for component in payload["components"]:
            print(
                f"  {component['query']['source']['source_id']} | "
                f"{component['status']}"
            )
        return
    print(
        f"Benton County property {args.command}: "
        f"{payload.get('status')} ({count} records)"
    )
    if payload.get("next_cursor"):
        print(f"Next cursor: {payload['next_cursor']}")
    for record in payload.get("records", []):
        identity = (
            record.get("object_id")
            or record.get("filename")
            or record.get("record_kind")
            or "record"
        )
        print(f"  {identity} | {record.get('source_id', '')}")
    for error in payload.get("errors", []):
        print(
            f"ERROR [{error.get('code')}]: {error.get('message')}",
            file=sys.stderr,
        )


def _add_output(parser: argparse.ArgumentParser) -> None:
    add_output_args(parser)


def _add_transport_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_page_size: bool = False,
) -> None:
    if include_page_size:
        parser.add_argument(
            "--page-size",
            type=int,
            default=1_000,
            help="Maximum ArcGIS records requested per page",
        )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--minimum-interval", type=float, default=0.25)
    parser.add_argument("--retry-attempts", type=int, default=3)
    _add_output(parser)


def _add_parcel_arguments(parser: argparse.ArgumentParser) -> None:
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
    _add_transport_arguments(parser, include_page_size=True)


def _add_directory_arguments(parser: argparse.ArgumentParser) -> None:
    _add_transport_arguments(parser)


def _add_artifact_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--component",
        required=True,
        choices=("bulk", "map"),
        help="Assessment bulk archive or assessment-map PDF",
    )
    parser.add_argument(
        "--artifact",
        required=True,
        help="Current bulk filename/artifact ID or assessment-map number/PDF",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Benton County Oregon TaxlotOwners, assessment "
            "bulk files, and assessment-map PDFs"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="List the distinct official components and complements",
    )
    _add_output(sources)

    search = sub.add_parser("search", help="Search TaxlotOwners fields")
    search.add_argument("query")
    search.add_argument(
        "--field",
        choices=(
            "auto",
            "owner",
            "address",
            "account",
            "map_taxlot",
            "or_taxlot",
            "map_number",
        ),
        default="auto",
    )
    _add_parcel_arguments(search)

    parcel_commands = {
        "owner": "owner",
        "address": "address",
        "account": "account",
        "map-taxlot": "map_taxlot",
        "or-taxlot": "or_taxlot",
        "map-number": "map_number",
    }
    for command, field_name in parcel_commands.items():
        query_parser = sub.add_parser(
            command,
            help=f"Search TaxlotOwners by {command}",
        )
        query_parser.add_argument("query")
        query_parser.set_defaults(field=field_name)
        _add_parcel_arguments(query_parser)

    scan = sub.add_parser(
        "scan",
        help="Traverse TaxlotOwners in stable OBJECTID order",
    )
    scan.set_defaults(field="all", query=None)
    _add_parcel_arguments(scan)

    manifest = sub.add_parser(
        "bulk-manifest",
        help="Resolve the current three-file assessment snapshot",
    )
    _add_directory_arguments(manifest)

    maps = sub.add_parser(
        "maps",
        help="Discover and filter official assessment-map PDFs",
    )
    maps.add_argument("--map-number")
    maps.add_argument(
        "--match",
        choices=("exact", "prefix", "contains"),
        default="exact",
    )
    maps.add_argument(
        "--map-kind",
        choices=(
            "all",
            "assessment_map",
            "map_index",
            "dlc_index",
            "dated_archive",
        ),
        default="all",
    )
    maps.add_argument(
        "--updated-after",
        help="Return entries with a directory date after YYYY-MM-DD",
    )
    maps.add_argument("--limit", type=int, default=100)
    maps.add_argument(
        "--cursor",
        help="Filter- and listing-bound filename continuation cursor",
    )
    _add_directory_arguments(maps)

    artifact_probe = sub.add_parser(
        "artifact-probe",
        help="Probe one listed ZIP or PDF without downloading it",
    )
    _add_artifact_arguments(artifact_probe)
    artifact_probe.add_argument("--range-bytes", type=int, default=8)
    _add_directory_arguments(artifact_probe)

    artifact_download = sub.add_parser(
        "artifact-download",
        help="Download one listed ZIP or PDF with resumable verification",
    )
    _add_artifact_arguments(artifact_download)
    artifact_download.add_argument("--destination", required=True)
    artifact_download.add_argument(
        "--no-resume",
        action="store_false",
        dest="resume",
        help="Restart instead of resuming a compatible partial download",
    )
    artifact_download.set_defaults(resume=True)
    artifact_download.add_argument("--expected-sha256")
    artifact_download.add_argument("--max-download-bytes", type=int)
    artifact_download.add_argument(
        "--chunk-size",
        type=int,
        default=1024 * 1024,
    )
    artifact_download.add_argument("--dry-run", action="store_true")
    _add_directory_arguments(artifact_download)

    probe = sub.add_parser(
        "probe",
        help="Run bounded identity and availability probes",
    )
    selection = probe.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--component",
        choices=("parcel", "bulk", "maps"),
    )
    selection.add_argument(
        "--all",
        action="store_true",
        dest="all_components",
    )
    probe.set_defaults(all_components=False)
    probe.add_argument(
        "--map-artifact",
        default="10329.pdf",
        help="Representative assessment-map PDF for the map probe",
    )
    probe.add_argument("--range-bytes", type=int, default=8)
    _add_transport_arguments(probe, include_page_size=True)

    return parser


def _validate_cli(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    for field_name in ("page_size", "retry_attempts", "chunk_size"):
        if hasattr(args, field_name) and getattr(args, field_name) <= 0:
            parser.error(f"--{field_name.replace('_', '-')} must be positive")
    if hasattr(args, "timeout") and args.timeout <= 0:
        parser.error("--timeout must be positive")
    if hasattr(args, "minimum_interval") and args.minimum_interval < 0:
        parser.error("--minimum-interval must not be negative")
    if hasattr(args, "limit") and args.limit <= 0:
        parser.error("--limit must be positive")
    if hasattr(args, "range_bytes") and args.range_bytes < 0:
        parser.error("--range-bytes must not be negative")
    if (
        hasattr(args, "max_download_bytes")
        and args.max_download_bytes is not None
        and args.max_download_bytes <= 0
    ):
        parser.error("--max-download-bytes must be positive")
    if hasattr(args, "query") and args.query is not None and not args.query.strip():
        parser.error("query must not be blank")
    if (
        hasattr(args, "expected_sha256")
        and args.expected_sha256 is not None
        and not re.fullmatch(r"[0-9A-Fa-f]{64}", args.expected_sha256)
    ):
        parser.error("--expected-sha256 must be a 64-character hex digest")
    if hasattr(args, "destination") and not args.destination.strip():
        parser.error("--destination must not be blank")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _validate_cli(parser, args)
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
