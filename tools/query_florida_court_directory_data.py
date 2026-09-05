#!/usr/bin/env python3
"""Query Florida's official statewide court directory and data-source family.

Florida Courts publishes complementary resources rather than one statewide
trial-court case feed: a courthouse and clerk-routing directory, the Virtual
Courtroom Directory, an OSCA public-records request route, and downloadable
trial-court statistical publications.  This adapter retains a separate source
identity for each publication role.

Examples:
    uv run python tools/query_florida_court_directory_data.py sources --json
    uv run python tools/query_florida_court_directory_data.py manifest --json
    uv run python tools/query_florida_court_directory_data.py locations \
        --query Miami --json
    uv run python tools/query_florida_court_directory_data.py virtual \
        --county "Lee County" --json
    uv run python tools/query_florida_court_directory_data.py data-request --json
    uv run python tools/query_florida_court_directory_data.py statistics \
        --fiscal-year 2024-25 --section Statistics --json
    uv run python tools/query_florida_court_directory_data.py download \
        2472276 /tmp/fl-overall-statistics.pdf --json
    uv run python tools/query_florida_court_directory_data.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

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
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
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
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )


STATE_CODE = "FL"
STATE_GEOID = "12"
AUTHORITY = "Florida State Courts System"
ADAPTER_FAMILY = "florida_courts_directory_and_data"
OUTPUT_SCHEMA_VERSION = "florida-court-directory-data/1.0"

SITE_BASE_URL = "https://www.flcourts.gov"
CMS_BASE_URL = "https://flcourts-media.ccplatform.net"
COURTROOMS_BASE_URL = "https://courtrooms.flcourts.gov"

LOCATION_DIRECTORY_URL = (
    f"{SITE_BASE_URL}/Courts-System/court-structure/court-locations"
)
LOCATION_CATEGORY_SELECTOR = "1dca,2dca,3dca,4dca,5dca,6dca,"
LOCATION_API_URL = (
    f"{CMS_BASE_URL}/poi/get_map_view_category_items/"
    f"{LOCATION_CATEGORY_SELECTOR}"
)
VIRTUAL_DIRECTORY_URL = f"{COURTROOMS_BASE_URL}/"
VIRTUAL_API_URL = f"{CMS_BASE_URL}/vcd/2/"
PUBLIC_RECORDS_URL = (
    f"{SITE_BASE_URL}/Services/Communications/public-records"
)
STATISTICS_CATALOG_URL = (
    f"{SITE_BASE_URL}/Data/trial-court-statistical-reference-guide"
)
JDMS_URL = (
    f"{SITE_BASE_URL}/Services/court-services/"
    "judicial-data-management-services-jdms"
)
LEGACY_TRIAL_STATS_URL = "http://trialstats.flcourts.org/"
FCCC_PUBLIC_RECORDS_DIRECTORY_URL = (
    "https://www.flclerks.com/page/publicrecords"
)
ACIS_URL = "https://acis.flcourts.gov/portal/home"

LOCATION_SOURCE_ID = "us-fl-state-court-location-directory"
VIRTUAL_SOURCE_ID = "us-fl-virtual-courtroom-directory"
PUBLIC_RECORDS_SOURCE_ID = "us-fl-osca-public-records-request"
STATISTICS_SOURCE_ID = (
    "us-fl-trial-court-statistical-reference-guide"
)
FAMILY_ID = "fl-courts-directory-data-family"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_MAX_ATTEMPTS = 3
MAXIMUM_JSON_BYTES = 16 * 1024 * 1024
MAXIMUM_HTML_BYTES = 32 * 1024 * 1024
MAXIMUM_PDF_BYTES = 160 * 1024 * 1024
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

EXPECTED_DISTRICTS = {
    "1dca": "First District",
    "2dca": "Second District",
    "3dca": "Third District",
    "4dca": "Fourth District",
    "5dca": "Fifth District",
    "6dca": "Sixth District",
}

COUNTY_GEOID_BY_NAME = {
    "Alachua": "12001",
    "Baker": "12003",
    "Bay": "12005",
    "Bradford": "12007",
    "Brevard": "12009",
    "Broward": "12011",
    "Calhoun": "12013",
    "Charlotte": "12015",
    "Citrus": "12017",
    "Clay": "12019",
    "Collier": "12021",
    "Columbia": "12023",
    "DeSoto": "12027",
    "Dixie": "12029",
    "Duval": "12031",
    "Escambia": "12033",
    "Flagler": "12035",
    "Franklin": "12037",
    "Gadsden": "12039",
    "Gilchrist": "12041",
    "Glades": "12043",
    "Gulf": "12045",
    "Hamilton": "12047",
    "Hardee": "12049",
    "Hendry": "12051",
    "Hernando": "12053",
    "Highlands": "12055",
    "Hillsborough": "12057",
    "Holmes": "12059",
    "Indian River": "12061",
    "Jackson": "12063",
    "Jefferson": "12065",
    "Lafayette": "12067",
    "Lake": "12069",
    "Lee": "12071",
    "Leon": "12073",
    "Levy": "12075",
    "Liberty": "12077",
    "Madison": "12079",
    "Manatee": "12081",
    "Marion": "12083",
    "Martin": "12085",
    "Miami-Dade": "12086",
    "Monroe": "12087",
    "Nassau": "12089",
    "Okaloosa": "12091",
    "Okeechobee": "12093",
    "Orange": "12095",
    "Osceola": "12097",
    "Palm Beach": "12099",
    "Pasco": "12101",
    "Pinellas": "12103",
    "Polk": "12105",
    "Putnam": "12107",
    "St. Johns": "12109",
    "St. Lucie": "12111",
    "Santa Rosa": "12113",
    "Sarasota": "12115",
    "Seminole": "12117",
    "Sumter": "12119",
    "Suwannee": "12121",
    "Taylor": "12123",
    "Union": "12125",
    "Volusia": "12127",
    "Wakulla": "12129",
    "Walton": "12131",
    "Washington": "12133",
}

WARNINGS = (
    "The location directory is a statewide court, clerk, and jury-route "
    "directory rather than a trial-case index.",
    "The Virtual Courtroom Directory includes existing virtual courtrooms; "
    "its judge and hearing-officer names are a partial personnel roster.",
    "The Statistical Reference Guide contains aggregate fiscal-year data.",
    "The OSCA request route covers records held by OSCA; local court records "
    "are maintained by the applicable courts and clerks.",
)

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    flags=re.DOTALL,
)
_EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    flags=re.IGNORECASE,
)
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)"
)
_FISCAL_YEAR_RE = re.compile(r"\b(\d{4}-\d{2})\b")
_DOWNLOAD_ID_RE = re.compile(r"/content/download/(\d+)(?:/|$)")
_CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "challenges.cloudflare.com",
)


@dataclass(frozen=True)
class Component:
    source_id: str
    name: str
    source_role: str
    base_url: str
    access_state: str
    operations: tuple[str, ...]
    coverage: str
    relationship: str


COMPONENTS = {
    LOCATION_SOURCE_ID: Component(
        source_id=LOCATION_SOURCE_ID,
        name="Florida State Courts Court Location Directory",
        source_role="official_statewide_court_and_clerk_route_directory",
        base_url=LOCATION_DIRECTORY_URL,
        access_state="open_json_endpoint_used_by_official_directory",
        operations=("locations",),
        coverage=(
            "the current official map's county courthouse entries, Supreme "
            "Court, and six District Courts of Appeal, with court, clerk, "
            "jury, address, and map routes"
        ),
        relationship="statewide court-system discovery and routing",
    ),
    VIRTUAL_SOURCE_ID: Component(
        source_id=VIRTUAL_SOURCE_ID,
        name="Florida Virtual Courtroom Directory",
        source_role="official_virtual_courtroom_and_partial_judicial_directory",
        base_url=VIRTUAL_DIRECTORY_URL,
        access_state="open_json_endpoint_used_by_official_directory",
        operations=("virtual",),
        coverage=(
            "published virtual courtrooms, participating counties, judges or "
            "hearing officers when named, jurisdiction routes, and live state"
        ),
        relationship="current virtual proceeding and partial personnel context",
    ),
    PUBLIC_RECORDS_SOURCE_ID: Component(
        source_id=PUBLIC_RECORDS_SOURCE_ID,
        name="OSCA Public Records Request Program",
        source_role="official_osca_public_records_request_route",
        base_url=PUBLIC_RECORDS_URL,
        access_state="published_email_and_phone_request_process",
        operations=("data-request",),
        coverage=(
            "records held by the Office of the State Courts Administrator"
        ),
        relationship="request path for OSCA-held records and tailored extracts",
    ),
    STATISTICS_SOURCE_ID: Component(
        source_id=STATISTICS_SOURCE_ID,
        name="Florida Trial Courts Statistical Reference Guide",
        source_role="official_trial_court_aggregate_publication_catalog",
        base_url=STATISTICS_CATALOG_URL,
        access_state="open_pdf_catalog",
        operations=("statistics", "download"),
        coverage=(
            "annual statewide and circuit/county aggregate filings, "
            "dispositions, workload, and contextual publications"
        ),
        relationship="downloadable aggregate substitute for case-level bulk",
    ),
}


def _component_metadata(component: Component) -> SourceMetadata:
    return SourceMetadata(
        source_id=component.source_id,
        name=component.name,
        source_role=component.source_role,
        base_url=component.base_url,
        dataset_id=component.source_id,
        metadata={
            "authority": AUTHORITY,
            "adapter_family": ADAPTER_FAMILY,
            "access_state": component.access_state,
            "operations": list(component.operations),
            "coverage": component.coverage,
            "relationship": component.relationship,
        },
    )


SOURCE_METADATA = {
    source_id: _component_metadata(component)
    for source_id, component in COMPONENTS.items()
}
FAMILY_METADATA = SourceMetadata(
    source_id=FAMILY_ID,
    name="Florida Courts Directory and Data Source Family",
    source_role="official_court_source_family_catalog",
    base_url=SITE_BASE_URL,
    dataset_id="florida-courts-directory-data",
    metadata={
        "authority": AUTHORITY,
        "adapter_family": ADAPTER_FAMILY,
        "components": list(COMPONENTS),
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Florida",
    state_code=STATE_CODE,
    metadata={"scope": "statewide"},
)


class FloridaCourtDataError(RuntimeError):
    """Transport, source-schema, or query-selection error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        category: str = "source",
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.category = category
        self.retryable = retryable
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


class SourceChangedError(FloridaCourtDataError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details=details,
        )


class SelectionError(FloridaCourtDataError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            category="query_selection",
            details=details,
        )


@dataclass(frozen=True)
class Artifact:
    content: bytes
    source_url: str
    media_type: str
    headers: Mapping[str, str]
    status_code: int = 200

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


class FloridaCourtsClient:
    """Bounded HTTP client for the Florida Courts source family."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.rate_limiter = MinimumIntervalRateLimiter(minimum_interval)
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=DEFAULT_MAX_ATTEMPTS
        )
        self.sleeper = sleeper

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def __enter__(self) -> FloridaCourtsClient:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        siteaccess: str | None = None,
        accept: str = "*/*",
        maximum_bytes: int = MAXIMUM_HTML_BYTES,
    ) -> Artifact:
        headers = {
            "Accept": accept,
            "User-Agent": DEFAULT_USER_AGENT,
        }
        if siteaccess is not None:
            headers["X-Siteaccess"] = siteaccess
        response: requests.Response | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    stream=True,
                )
            except requests.RequestException as exc:
                if attempt >= self.retry_policy.max_attempts:
                    raise FloridaCourtDataError(
                        "transport_error",
                        f"Florida Courts request failed: {exc}",
                        category="transport",
                        retryable=True,
                        details={"url": url},
                    ) from exc
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if (
                response.status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                retry_after = _retry_after(response)
                response.close()
                self.sleeper(
                    self.retry_policy.delay(
                        attempt,
                        retry_after=retry_after,
                    )
                )
                continue
            break
        if response is None:
            raise FloridaCourtDataError(
                "transport_error",
                "Florida Courts request did not produce a response",
                category="transport",
                retryable=True,
                details={"url": url},
            )
        response_url = str(response.url or url)
        status_code = int(response.status_code)
        if status_code == 429:
            response.close()
            raise FloridaCourtDataError(
                "rate_limited",
                "Florida Courts returned HTTP 429",
                status=ResultStatus.RATE_LIMITED,
                category="rate_limit",
                retryable=True,
                details={"url": response_url},
            )
        if status_code in {401, 403}:
            response.close()
            raise FloridaCourtDataError(
                "access_restricted",
                f"Florida Courts returned HTTP {status_code}",
                status=ResultStatus.RESTRICTED,
                category="access",
                details={"url": response_url, "status_code": status_code},
            )
        if status_code < 200 or status_code >= 300:
            response.close()
            raise FloridaCourtDataError(
                "http_status",
                f"Florida Courts returned HTTP {status_code}",
                retryable=status_code >= 500,
                category="http",
                details={"url": response_url, "status_code": status_code},
            )
        declared_length = response.headers.get("Content-Length")
        if declared_length is not None:
            try:
                if int(declared_length) > maximum_bytes:
                    response.close()
                    raise FloridaCourtDataError(
                        "response_too_large",
                        "Florida Courts response exceeds the configured bound",
                        category="transport",
                        details={
                            "url": response_url,
                            "content_length": int(declared_length),
                            "maximum_bytes": maximum_bytes,
                        },
                    )
            except ValueError:
                pass
        chunks: list[bytes] = []
        byte_length = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            byte_length += len(chunk)
            if byte_length > maximum_bytes:
                response.close()
                raise FloridaCourtDataError(
                    "response_too_large",
                    "Florida Courts response exceeds the configured bound",
                    category="transport",
                    details={
                        "url": response_url,
                        "maximum_bytes": maximum_bytes,
                    },
                )
            chunks.append(chunk)
        media_type = str(response.headers.get("Content-Type", "")).split(
            ";",
            1,
        )[0].strip().lower()
        artifact = Artifact(
            content=b"".join(chunks),
            source_url=response_url,
            media_type=media_type,
            headers={
                str(key): str(value)
                for key, value in response.headers.items()
            },
            status_code=status_code,
        )
        response.close()
        return artifact

    def locations(self) -> Artifact:
        return self.get(
            LOCATION_API_URL,
            siteaccess="osca2",
            accept="application/json",
            maximum_bytes=MAXIMUM_JSON_BYTES,
        )

    def virtual(
        self,
        *,
        county: str | None = None,
        judge: str | None = None,
    ) -> Artifact:
        params = (
            {"judge": judge}
            if judge is not None
            else {"county": county or "All"}
        )
        return self.get(
            VIRTUAL_API_URL,
            params=params,
            siteaccess="vcd",
            accept="application/json",
            maximum_bytes=MAXIMUM_JSON_BYTES,
        )

    def page(self, url: str) -> Artifact:
        return self.get(
            url,
            accept="text/html,application/xhtml+xml",
            maximum_bytes=MAXIMUM_HTML_BYTES,
        )


def _retry_after(response: Any) -> float | None:
    value = getattr(response, "headers", {}).get("Retry-After")
    try:
        return max(0.0, float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return cleaned or None


def _required(value: Any, field: str) -> str:
    cleaned = _clean(value)
    if cleaned is None:
        raise SourceChangedError(
            "required_field_missing",
            f"Florida Courts response lacks {field}",
            details={"field": field},
        )
    return cleaned


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise SourceChangedError(
            "invalid_integer",
            f"Florida Courts {field} is not an integer",
            details={"field": field, "value": value},
        )
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise SourceChangedError(
            "invalid_integer",
            f"Florida Courts {field} is not an integer",
            details={"field": field, "value": value},
        ) from exc


def _json_payload(artifact: Artifact) -> Any:
    try:
        return json.loads(artifact.text)
    except json.JSONDecodeError as exc:
        raise SourceChangedError(
            "invalid_json",
            "Florida Courts endpoint did not return valid JSON",
            details={
                "source_url": artifact.source_url,
                "media_type": artifact.media_type,
            },
        ) from exc


def _next_page_props(artifact: Artifact) -> Mapping[str, Any]:
    lowered = artifact.text[:10000].casefold()
    if any(marker in lowered for marker in _CHALLENGE_MARKERS):
        raise FloridaCourtDataError(
            "verification_page",
            "Florida Courts returned a verification page",
            status=ResultStatus.HUMAN_REQUIRED,
            category="access",
            details={"source_url": artifact.source_url},
        )
    match = _NEXT_DATA_RE.search(artifact.text)
    if match is None:
        raise SourceChangedError(
            "next_data_missing",
            "Florida Courts page lacks its embedded page data",
            details={"source_url": artifact.source_url},
        )
    try:
        payload = json.loads(html.unescape(match.group(1)))
        page_props = payload["props"]["pageProps"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SourceChangedError(
            "next_data_invalid",
            "Florida Courts embedded page data changed shape",
            details={"source_url": artifact.source_url},
        ) from exc
    if not isinstance(page_props, Mapping):
        raise SourceChangedError(
            "next_data_invalid",
            "Florida Courts embedded page properties are not an object",
            details={"source_url": artifact.source_url},
        )
    return page_props


def _absolute_route(value: Any, *, base: str = SITE_BASE_URL) -> str | None:
    cleaned = _clean(value)
    return urljoin(base, cleaned) if cleaned is not None else None


def _route_record(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    link = _absolute_route(value.get("link"))
    text = _clean(value.get("text"))
    if link is None and text is None:
        return None
    return {"url": link, "label": text}


def _location_record(
    item: Mapping[str, Any],
    *,
    category_id: str,
    category_name: str,
    source_url: str,
) -> dict[str, Any]:
    node_id = _integer(item.get("node_id"), "location.node_id")
    content_id = _integer(item.get("object_id"), "location.object_id")
    name = _required(item.get("name"), "location.name")
    location = item.get("location")
    if not isinstance(location, Mapping):
        raise SourceChangedError(
            "location_object_missing",
            "Florida Courts location item lacks its location object",
            details={"node_id": node_id},
        )
    published_location_county = _clean(location.get("county")) or name
    is_dca = bool(re.search(r"\bdistrict\s+dca$", name, re.IGNORECASE))
    is_supreme = name.casefold() == "supreme court"
    is_appellate = is_dca or is_supreme
    county_name = None if is_appellate else published_location_county
    county_geoid = (
        None
        if county_name is None
        else COUNTY_GEOID_BY_NAME.get(county_name)
    )
    if not is_appellate and county_geoid is None:
        raise SourceChangedError(
            "unknown_county",
            "Florida Courts location directory contains an unknown county",
            details={
                "node_id": node_id,
                "county": published_location_county,
            },
        )
    geolocation = location.get("geolocation")
    if not isinstance(geolocation, Mapping):
        geolocation = {}
    published_region = location.get("region")
    if not isinstance(published_region, Mapping):
        published_region = {}
    published_region_id = _clean(published_region.get("identifier"))
    routes = {
        "court": _route_record(item.get("court_site")),
        "clerk": _route_record(item.get("clerk_site")),
        "jury": _route_record(item.get("jury")),
        "directory_detail": {
            "url": _absolute_route(item.get("url")),
            "label": "Directory detail",
        },
        "map_info": {
            "url": _absolute_route(item.get("view"), base=CMS_BASE_URL),
            "label": "Map detail",
        },
    }
    routes = {
        key: value
        for key, value in routes.items()
        if value is not None and value.get("url") is not None
    }
    canonical_ref = f"FL-COURTS:LOCATION:{node_id}"
    return {
        "record_kind": (
            "district_court_of_appeal_location"
            if is_dca
            else (
                "state_supreme_court_location"
                if is_supreme
                else "county_courthouse_location"
            )
        ),
        "source_id": LOCATION_SOURCE_ID,
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "native_record_id": str(node_id),
        "content_id": str(content_id),
        "name": name,
        "county": county_name,
        "county_geoid": county_geoid,
        "published_location_county": published_location_county,
        "state_code": STATE_CODE,
        "appellate_map_category": {
            "identifier": category_id,
            "name": category_name,
        },
        "address": {
            "formatted": _clean(location.get("address")),
            "city": _clean(location.get("city")),
            "state": _clean(location.get("state")),
            "postal_code": _clean(location.get("zip")),
        },
        "geolocation": {
            "latitude": geolocation.get("latitude"),
            "longitude": geolocation.get("longitude"),
            "source_modified": geolocation.get("contentobject_modified"),
        },
        "published_region": (
            {
                "identifier": published_region_id,
                "name": _clean(published_region.get("name")),
            }
            if published_region
            else None
        ),
        "published_region_matches_map_category": (
            published_region_id == category_id
            if published_region_id is not None
            else None
        ),
        "routes": routes,
        "source_url": source_url,
        "source_record_fingerprint": sha256_fingerprint(item),
        "projection": {
            "projectable_as_case": False,
            "scope": "court_directory_snapshot",
        },
    }


def parse_location_directory(
    artifact: Artifact,
) -> tuple[dict[str, Any], ...]:
    payload = _json_payload(artifact)
    if not isinstance(payload, list):
        raise SourceChangedError(
            "location_payload_invalid",
            "Florida Courts location endpoint must return an array",
            details={"source_url": artifact.source_url},
        )
    observed_categories: dict[str, Mapping[str, Any]] = {}
    for category in payload:
        if not isinstance(category, Mapping):
            raise SourceChangedError(
                "location_category_invalid",
                "Florida Courts location category is not an object",
            )
        category_id = _required(
            category.get("category_id"),
            "location.category_id",
        )
        if category_id in observed_categories:
            raise SourceChangedError(
                "location_category_duplicate",
                "Florida Courts location endpoint repeated a category",
                details={"category_id": category_id},
            )
        observed_categories[category_id] = category
    if set(observed_categories) != set(EXPECTED_DISTRICTS):
        raise SourceChangedError(
            "location_categories_changed",
            "Florida Courts location categories changed",
            details={
                "expected": sorted(EXPECTED_DISTRICTS),
                "observed": sorted(observed_categories),
            },
        )
    records: list[dict[str, Any]] = []
    seen_node_ids: set[str] = set()
    for category_id in EXPECTED_DISTRICTS:
        category = observed_categories[category_id]
        content = category.get("content")
        if not isinstance(content, Mapping):
            raise SourceChangedError(
                "location_content_missing",
                "Florida Courts location category lacks content",
                details={"category_id": category_id},
            )
        category_metadata = content.get("category")
        if not isinstance(category_metadata, Mapping):
            raise SourceChangedError(
                "location_category_metadata_missing",
                "Florida Courts location category lacks metadata",
                details={"category_id": category_id},
            )
        category_name = _required(
            category_metadata.get("name"),
            "location.category.name",
        )
        if category_name != EXPECTED_DISTRICTS[category_id]:
            raise SourceChangedError(
                "location_category_name_changed",
                "Florida Courts location category name changed",
                details={
                    "category_id": category_id,
                    "expected": EXPECTED_DISTRICTS[category_id],
                    "observed": category_name,
                },
            )
        items = content.get("items")
        if not isinstance(items, list):
            raise SourceChangedError(
                "location_items_missing",
                "Florida Courts location category lacks its item array",
                details={"category_id": category_id},
            )
        advertised_count = _integer(
            content.get("items_count"),
            "location.items_count",
        )
        if advertised_count != len(items):
            raise SourceChangedError(
                "location_count_mismatch",
                "Florida Courts location category count does not match its rows",
                details={
                    "category_id": category_id,
                    "advertised": advertised_count,
                    "observed": len(items),
                },
            )
        for item in items:
            if not isinstance(item, Mapping):
                raise SourceChangedError(
                    "location_item_invalid",
                    "Florida Courts location row is not an object",
                    details={"category_id": category_id},
                )
            record = _location_record(
                item,
                category_id=category_id,
                category_name=category_name,
                source_url=artifact.source_url,
            )
            native_id = str(record["native_record_id"])
            if native_id in seen_node_ids:
                raise SourceChangedError(
                    "location_duplicate",
                    "Florida Courts location endpoint repeated a record",
                    details={"native_record_id": native_id},
                )
            seen_node_ids.add(native_id)
            records.append(record)
    return tuple(records)


def _virtual_record(
    item: Mapping[str, Any],
    *,
    source_url: str,
) -> dict[str, Any]:
    location_id = _integer(
        item.get("location_id"),
        "virtual.location_id",
    )
    content_id = _integer(
        item.get("content_id"),
        "virtual.content_id",
    )
    counties = item.get("counties")
    if not isinstance(counties, list) or any(
        not isinstance(value, str) or not value.strip()
        for value in counties
    ):
        raise SourceChangedError(
            "virtual_counties_invalid",
            "Florida Virtual Courtroom row has invalid counties",
            details={"location_id": location_id},
        )
    stream = item.get("stream")
    if not isinstance(stream, Mapping):
        raise SourceChangedError(
            "virtual_stream_invalid",
            "Florida Virtual Courtroom row lacks stream state",
            details={"location_id": location_id},
        )
    live = stream.get("live")
    if not isinstance(live, bool):
        raise SourceChangedError(
            "virtual_live_state_invalid",
            "Florida Virtual Courtroom row has an invalid live state",
            details={"location_id": location_id},
        )
    youtube_id = _clean(item.get("youtube_id"))
    stream_link = _absolute_route(stream.get("link"))
    if stream_link is None and youtube_id is not None:
        stream_link = f"https://www.youtube.com/channel/{youtube_id}"
    canonical_ref = f"FL-COURTS:VIRTUAL:{location_id}"
    return {
        "record_kind": "virtual_courtroom_directory_entry",
        "source_id": VIRTUAL_SOURCE_ID,
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "native_record_id": str(location_id),
        "content_id": str(content_id),
        "name": _required(item.get("name"), "virtual.name"),
        "judge_or_hearing_officer": _clean(item.get("judge")),
        "court": _required(item.get("court"), "virtual.court"),
        "counties": [value.strip() for value in counties],
        "all_counties": [
            str(value).strip()
            for value in item.get("all_counties", [])
            if _clean(value) is not None
        ],
        "jurisdiction_url": _absolute_route(
            item.get("jurisdiction_link")
        ),
        "youtube_channel_id": youtube_id,
        "stream": {
            "live": live,
            "url": stream_link,
            "tags": (
                list(stream.get("tags", []))
                if isinstance(stream.get("tags", []), list)
                else []
            ),
        },
        "source_url": source_url,
        "source_record_fingerprint": sha256_fingerprint(item),
        "projection": {
            "projectable_as_case": False,
            "scope": "virtual_courtroom_snapshot",
        },
    }


def parse_virtual_directory(
    artifact: Artifact,
) -> tuple[dict[str, Any], ...]:
    payload = _json_payload(artifact)
    if not isinstance(payload, Mapping) or not isinstance(
        payload.get("items"),
        list,
    ):
        raise SourceChangedError(
            "virtual_payload_invalid",
            "Florida Virtual Courtroom endpoint lacks its item array",
            details={"source_url": artifact.source_url},
        )
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in payload["items"]:
        if not isinstance(item, Mapping):
            raise SourceChangedError(
                "virtual_item_invalid",
                "Florida Virtual Courtroom row is not an object",
            )
        record = _virtual_record(item, source_url=artifact.source_url)
        native_id = str(record["native_record_id"])
        if native_id in seen:
            raise SourceChangedError(
                "virtual_item_duplicate",
                "Florida Virtual Courtroom endpoint repeated a row",
                details={"native_record_id": native_id},
            )
        seen.add(native_id)
        records.append(record)
    return tuple(records)


def parse_data_request_program(artifact: Artifact) -> dict[str, Any]:
    page_props = _next_page_props(artifact)
    page_data = page_props.get("pageData")
    if not isinstance(page_data, Mapping):
        raise SourceChangedError(
            "request_page_missing",
            "Florida Courts public-records page lacks page data",
        )
    description = page_data.get("description")
    if not isinstance(description, Mapping):
        raise SourceChangedError(
            "request_description_missing",
            "Florida Courts public-records page lacks its description",
        )
    description_html = _required(
        description.get("html5"),
        "public_records.description",
    )
    text = _clean(
        BeautifulSoup(description_html, "html.parser").get_text(" ")
    )
    emails = sorted(set(_EMAIL_RE.findall(text or "")))
    phones = sorted(set(_PHONE_RE.findall(text or "")))
    if "oscapio@flcourts.org" not in {
        value.casefold() for value in emails
    }:
        raise SourceChangedError(
            "request_contact_changed",
            "Florida Courts public-records contact sentinel changed",
            details={"published_emails": emails},
        )
    canonical_ref = "FL-COURTS:OSCA-PUBLIC-RECORDS"
    return {
        "record_kind": "public_records_request_program",
        "source_id": PUBLIC_RECORDS_SOURCE_ID,
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "authority": "Office of the State Courts Administrator",
        "request_scope": "records_held_by_osca",
        "request_methods": [
            {
                "method": "email",
                "address": value,
            }
            for value in emails
        ]
        + [
            {
                "method": "telephone_assistance",
                "number": value,
            }
            for value in phones
        ],
        "published_process": text,
        "fee_estimate_notice_published": bool(
            text and "estimate" in text.casefold()
        ),
        "source_url": artifact.source_url,
        "source_sha256": artifact.sha256,
        "projection": {
            "projectable_as_case": False,
            "scope": "request_program_snapshot",
        },
    }


def _statistics_description_html(
    artifact: Artifact,
) -> str:
    page_props = _next_page_props(artifact)
    page_data = page_props.get("pageData")
    if not isinstance(page_data, Mapping):
        raise SourceChangedError(
            "statistics_page_missing",
            "Florida Courts statistics page lacks page data",
        )
    description = page_data.get("description")
    if not isinstance(description, Mapping):
        raise SourceChangedError(
            "statistics_description_missing",
            "Florida Courts statistics page lacks its description",
        )
    return _required(
        description.get("html5"),
        "statistics.description",
    )


def parse_statistics_catalog(
    artifact: Artifact,
) -> tuple[dict[str, Any], ...]:
    soup = BeautifulSoup(
        _statistics_description_html(artifact),
        "html.parser",
    )
    fiscal_year: str | None = None
    section: str | None = None
    records: list[dict[str, Any]] = []
    seen_occurrences: set[tuple[str, str, str]] = set()
    for node in soup.find_all(["h2", "p", "a"]):
        text_value = _clean(node.get_text(" ", strip=True)) or ""
        if node.name == "h2":
            match = _FISCAL_YEAR_RE.search(text_value)
            fiscal_year = match.group(1) if match else fiscal_year
            if match:
                section = None
            continue
        if (
            node.name == "p"
            and fiscal_year is not None
            and node.find("strong") is not None
        ):
            section = text_value
            continue
        if node.name != "a" or fiscal_year is None:
            continue
        href = _clean(node.get("href"))
        if href is None or "/content/download/" not in href:
            continue
        id_match = _DOWNLOAD_ID_RE.search(href)
        if id_match is None:
            raise SourceChangedError(
                "statistics_artifact_id_missing",
                "Florida Courts statistics link lacks a content ID",
                details={"href": href},
            )
        artifact_id = id_match.group(1)
        metadata: Mapping[str, Any] = {}
        data_content = _clean(node.get("data-content"))
        if data_content is not None:
            try:
                decoded = json.loads(data_content)
                if isinstance(decoded, Mapping):
                    metadata = decoded
            except json.JSONDecodeError as exc:
                raise SourceChangedError(
                    "statistics_link_metadata_invalid",
                    "Florida Courts statistics link metadata is invalid JSON",
                    details={"artifact_id": artifact_id},
                ) from exc
        list_item = node.find_parent("li")
        title = (
            _clean(list_item.get_text(" ", strip=True))
            if list_item is not None
            else _clean(node.get("title"))
        )
        title = re.sub(
            r"\s*[-–]\s*PDF\s*$",
            "",
            title or _clean(metadata.get("linkTitle")) or f"Artifact {artifact_id}",
            flags=re.IGNORECASE,
        ).strip()
        download_url = (
            _absolute_route(
                metadata.get("downloadUrl"),
                base=CMS_BASE_URL,
            )
            or _absolute_route(href, base=CMS_BASE_URL)
        )
        occurrence_key = (fiscal_year, section or "", artifact_id)
        if occurrence_key in seen_occurrences:
            raise SourceChangedError(
                "statistics_occurrence_duplicate",
                "Florida Courts statistics catalog repeated an occurrence",
                details={
                    "fiscal_year": fiscal_year,
                    "section": section,
                    "artifact_id": artifact_id,
                },
            )
        seen_occurrences.add(occurrence_key)
        canonical_ref = (
            f"FL-COURTS:TRIAL-STATS:{fiscal_year}:"
            f"{section or 'unsectioned'}:{artifact_id}"
        )
        records.append(
            {
                "record_kind": "trial_court_statistical_publication",
                "source_id": STATISTICS_SOURCE_ID,
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "native_document_id": artifact_id,
                "fiscal_year": fiscal_year,
                "catalog_section": section,
                "title": title,
                "filename": _clean(metadata.get("fileName")),
                "artifact_url": download_url,
                "catalog_url": artifact.source_url,
                "media_type": (
                    _clean(metadata.get("mimeType"))
                    or "application/pdf"
                ),
                "published_file_size": _clean(
                    metadata.get("fileSize")
                ),
                "source_link_title": _clean(
                    metadata.get("linkTitle")
                ),
                "projection": {
                    "projectable_as_case": False,
                    "scope": "aggregate_statistical_publication",
                },
            }
        )
    if not records:
        raise SourceChangedError(
            "statistics_catalog_empty",
            "Florida Courts statistics catalog has no downloadable records",
            details={"source_url": artifact.source_url},
        )
    return tuple(records)


def _component_records() -> list[dict[str, Any]]:
    return [
        {
            "record_kind": "source_component",
            "source_id": component.source_id,
            "component_source_id": component.source_id,
            "adapter_family": ADAPTER_FAMILY,
            "canonical_ref": f"FL-COURTS:SOURCE:{component.source_id}",
            "name": component.name,
            "source_role": component.source_role,
            "base_url": component.base_url,
            "access_state": component.access_state,
            "operations": list(component.operations),
            "coverage": component.coverage,
            "relationship": component.relationship,
            "authority": AUTHORITY,
        }
        for component in COMPONENTS.values()
    ]


def _manifest_record() -> dict[str, Any]:
    return {
        "record_kind": "source_family_manifest",
        "source_id": FAMILY_ID,
        "component_source_id": FAMILY_ID,
        "adapter_family": ADAPTER_FAMILY,
        "canonical_ref": "FL-COURTS:MANIFEST:DIRECTORY-DATA",
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "authority": AUTHORITY,
        "components": [
            {
                "source_id": component.source_id,
                "source_role": component.source_role,
                "access_state": component.access_state,
                "operations": list(component.operations),
                "relationship": component.relationship,
            }
            for component in COMPONENTS.values()
        ],
        "source_relationships": {
            "court_locations": (
                "court, clerk, jury, address, and official-site discovery"
            ),
            "virtual_courtrooms": (
                "participating virtual courtrooms and partial personnel context"
            ),
            "osca_public_records": "request path for OSCA-held records",
            "statistical_reference_guide": (
                "downloadable aggregate trial-court activity"
            ),
            "appellate_cases": "covered separately by us-fl-acis",
            "local_trial_cases": (
                "published by the applicable county clerk or circuit court"
            ),
        },
        "catalog_observations": [
            {
                "observed_on": "2026-07-30",
                "source_id": LOCATION_SOURCE_ID,
                "observation": (
                    "the official all-locations feed published 73 rows: "
                    "66 county courthouse rows, the Supreme Court, and six "
                    "District Courts of Appeal"
                ),
                "published_county_omissions": ["Gadsden"],
            }
        ],
        "bulk_and_request_landscape": [
            {
                "name": "OSCA Judicial Data Management Services / UCR",
                "url": JDMS_URL,
                "role": (
                    "state-level case-activity consolidation, specifications, "
                    "and reporting"
                ),
                "observed_access": (
                    "public specifications; the published web service requires "
                    "credentials and coordinated network access"
                ),
            },
            {
                "name": "Trial Court Statistics Search",
                "url": LEGACY_TRIAL_STATS_URL,
                "role": "legacy interactive aggregate-statistics route",
                "probe_observation": (
                    "the published root returned a generic IIS landing page "
                    "during the 2026-07-30 adapter probe"
                ),
                "useful_substitute": STATISTICS_SOURCE_ID,
            },
            {
                "name": "Florida Court Clerks Public Records Directory",
                "url": FCCC_PUBLIC_RECORDS_DIRECTORY_URL,
                "authority": "Florida Court Clerks & Comptrollers",
                "role": (
                    "county clerk websites and local public-records processes"
                ),
            },
            {
                "name": "Florida Appellate Case Information System",
                "url": ACIS_URL,
                "source_id": "us-fl-acis",
                "role": (
                    "public Supreme Court and District Court of Appeal case, "
                    "docket, document, and calendar access"
                ),
            },
        ],
    }


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    ignored = {
        "command",
        "output",
        "json_out",
        "timeout",
        "minimum_interval",
        "max_attempts",
        "retry_backoff",
    }
    return {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
        if key not in ignored and value is not None
    }


def _command_source_id(args: argparse.Namespace) -> str:
    if args.command in {"sources", "manifest", "probe"}:
        return FAMILY_ID
    if args.command == "locations":
        return LOCATION_SOURCE_ID
    if args.command == "virtual":
        return VIRTUAL_SOURCE_ID
    if args.command == "data-request":
        return PUBLIC_RECORDS_SOURCE_ID
    if args.command in {"statistics", "download"}:
        return STATISTICS_SOURCE_ID
    raise SelectionError(
        "unsupported_command",
        f"unsupported Florida Courts command {args.command!r}",
    )


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    source_id = _command_source_id(args)
    source = (
        FAMILY_METADATA
        if source_id == FAMILY_ID
        else SOURCE_METADATA[source_id]
    )
    return PublicRecordsQuery(
        source=source,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=getattr(args, "limit", None),
        ),
    )


def _filter_locations(
    records: Sequence[Mapping[str, Any]],
    *,
    query_text: str | None,
    district: str | None,
    kind: str | None,
) -> list[Mapping[str, Any]]:
    selected: list[Mapping[str, Any]] = []
    for record in records:
        if (
            district is not None
            and record["appellate_map_category"]["identifier"] != district
        ):
            continue
        if kind is not None:
            expected_kind = (
                "county_courthouse_location"
                if kind == "county"
                else "district_court_of_appeal_location"
            )
            if record["record_kind"] != expected_kind:
                continue
        if (
            query_text is not None
            and query_text.casefold()
            not in canonical_json(record).casefold()
        ):
            continue
        selected.append(record)
    return selected


def _filter_virtual(
    records: Sequence[Mapping[str, Any]],
    *,
    query_text: str | None,
    live_only: bool,
) -> list[Mapping[str, Any]]:
    selected: list[Mapping[str, Any]] = []
    for record in records:
        if live_only and not record["stream"]["live"]:
            continue
        searchable = {
            "name": record.get("name"),
            "judge_or_hearing_officer": record.get(
                "judge_or_hearing_officer"
            ),
            "court": record.get("court"),
            "counties": record.get("counties"),
            "all_counties": record.get("all_counties"),
            "jurisdiction_url": record.get("jurisdiction_url"),
            "youtube_channel_id": record.get("youtube_channel_id"),
            "stream": record.get("stream"),
        }
        if (
            query_text is not None
            and query_text.casefold()
            not in canonical_json(searchable).casefold()
        ):
            continue
        selected.append(record)
    return selected


def _filter_statistics(
    records: Sequence[Mapping[str, Any]],
    *,
    fiscal_year: str | None,
    section: str | None,
    query_text: str | None,
    limit: int | None,
) -> list[Mapping[str, Any]]:
    selected: list[Mapping[str, Any]] = []
    for record in records:
        if fiscal_year is not None and record["fiscal_year"] != fiscal_year:
            continue
        if (
            section is not None
            and str(record["catalog_section"] or "").casefold()
            != section.casefold()
        ):
            continue
        if (
            query_text is not None
            and query_text.casefold()
            not in canonical_json(record).casefold()
        ):
            continue
        selected.append(record)
    return selected[:limit] if limit is not None else selected


def _resolve_statistics_artifact(
    records: Sequence[Mapping[str, Any]],
    selector: str,
) -> Mapping[str, Any]:
    needle = selector.strip().casefold()
    if not needle:
        raise SelectionError(
            "empty_selector",
            "statistics artifact selector must not be empty",
        )
    exact = [
        record
        for record in records
        if needle
        in {
            str(record.get("native_document_id") or "").casefold(),
            str(record.get("canonical_ref") or "").casefold(),
            str(record.get("filename") or "").casefold(),
            str(record.get("title") or "").casefold(),
        }
    ]
    if not exact:
        exact = [
            record
            for record in records
            if needle in canonical_json(record).casefold()
        ]
    if not exact:
        raise SelectionError(
            "artifact_not_found",
            f"no Florida statistics artifact matches {selector!r}",
        )
    urls = {
        str(record["artifact_url"])
        for record in exact
        if record.get("artifact_url")
    }
    if len(urls) != 1:
        raise SelectionError(
            "artifact_selector_ambiguous",
            f"Florida statistics selector {selector!r} is ambiguous",
            details={
                "matches": [
                    {
                        "native_document_id": record[
                            "native_document_id"
                        ],
                        "fiscal_year": record["fiscal_year"],
                        "title": record["title"],
                        "artifact_url": record["artifact_url"],
                    }
                    for record in exact
                ]
            },
        )
    return exact[0]


def _write_pdf(
    artifact: Artifact,
    *,
    destination: Path,
    overwrite: bool,
    catalog_record: Mapping[str, Any],
) -> dict[str, Any]:
    if not artifact.content.startswith(b"%PDF-"):
        raise SourceChangedError(
            "artifact_not_pdf",
            "Florida statistics artifact is not a PDF",
            details={
                "source_url": artifact.source_url,
                "media_type": artifact.media_type,
            },
        )
    if destination.exists() and not overwrite:
        raise SelectionError(
            "destination_exists",
            f"destination already exists: {destination}",
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(artifact.content)
    sha256 = artifact.sha256
    canonical_ref = f"FL-COURTS:STATISTICS-PDF:{sha256}"
    return {
        "record_kind": "trial_court_statistical_pdf_artifact",
        "source_id": STATISTICS_SOURCE_ID,
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "native_document_id": catalog_record["native_document_id"],
        "title": catalog_record["title"],
        "fiscal_year": catalog_record["fiscal_year"],
        "catalog_section": catalog_record["catalog_section"],
        "artifact_url": artifact.source_url,
        "artifact_path": str(destination.resolve()),
        "media_type": artifact.media_type or "application/pdf",
        "byte_length": len(artifact.content),
        "sha256": sha256,
        "catalog_record": dict(catalog_record),
        "projection": {
            "projectable_as_case": False,
            "scope": "downloaded_aggregate_publication",
        },
    }


def _probe_records(
    client: FloridaCourtsClient | Any,
) -> list[dict[str, Any]]:
    locations = parse_location_directory(client.locations())
    county_records = [
        record
        for record in locations
        if record["record_kind"] == "county_courthouse_location"
    ]
    dca_records = [
        record
        for record in locations
        if record["record_kind"] == "district_court_of_appeal_location"
    ]
    supreme_records = [
        record
        for record in locations
        if record["record_kind"] == "state_supreme_court_location"
    ]
    by_name = {str(record["name"]): record for record in locations}
    published_counties = {
        str(record["county"])
        for record in county_records
    }
    missing_counties = sorted(
        set(COUNTY_GEOID_BY_NAME) - published_counties
    )
    if (
        len(locations) != 73
        or len(county_records) != 66
        or len(dca_records) != 6
        or len(supreme_records) != 1
        or missing_counties != ["Gadsden"]
        or "Miami-Dade" not in by_name
        or "First District DCA" not in by_name
        or "Supreme Court" not in by_name
    ):
        raise SourceChangedError(
            "location_probe_changed",
            "Florida court-location directory sentinel changed",
            details={
                "county_count": len(county_records),
                "dca_count": len(dca_records),
                "supreme_court_count": len(supreme_records),
                "missing_counties": missing_counties,
                "has_miami_dade": "Miami-Dade" in by_name,
                "has_first_dca": "First District DCA" in by_name,
                "has_supreme_court": "Supreme Court" in by_name,
            },
        )
    virtual = parse_virtual_directory(client.virtual())
    if not virtual:
        raise SourceChangedError(
            "virtual_probe_empty",
            "Florida Virtual Courtroom Directory returned no records",
        )
    request_program = parse_data_request_program(
        client.page(PUBLIC_RECORDS_URL)
    )
    statistics = parse_statistics_catalog(
        client.page(STATISTICS_CATALOG_URL)
    )
    fiscal_years = sorted(
        {str(record["fiscal_year"]) for record in statistics},
        reverse=True,
    )
    published_region_mismatches = [
        {
            "name": record["name"],
            "map_category": record["appellate_map_category"][
                "identifier"
            ],
            "published_region": record["published_region"][
                "identifier"
            ],
        }
        for record in locations
        if record["published_region_matches_map_category"] is False
    ]
    return [
        {
            "record_kind": "source_health_check",
            "source_id": LOCATION_SOURCE_ID,
            "canonical_ref": (
                f"FL-COURTS:PROBE:{LOCATION_SOURCE_ID}"
            ),
            "status": "ok",
            "record_count": len(locations),
            "county_count": len(county_records),
            "district_court_of_appeal_count": len(dca_records),
            "supreme_court_count": len(supreme_records),
            "published_county_omissions": missing_counties,
            "published_region_mismatch_count": len(
                published_region_mismatches
            ),
            "published_region_mismatches": published_region_mismatches,
        },
        {
            "record_kind": "source_health_check",
            "source_id": VIRTUAL_SOURCE_ID,
            "canonical_ref": (
                f"FL-COURTS:PROBE:{VIRTUAL_SOURCE_ID}"
            ),
            "status": "ok",
            "record_count": len(virtual),
            "named_judicial_officer_count": sum(
                bool(record["judge_or_hearing_officer"])
                for record in virtual
            ),
            "live_count": sum(
                bool(record["stream"]["live"])
                for record in virtual
            ),
        },
        {
            "record_kind": "source_health_check",
            "source_id": PUBLIC_RECORDS_SOURCE_ID,
            "canonical_ref": (
                f"FL-COURTS:PROBE:{PUBLIC_RECORDS_SOURCE_ID}"
            ),
            "status": "ok",
            "request_method_count": len(
                request_program["request_methods"]
            ),
        },
        {
            "record_kind": "source_health_check",
            "source_id": STATISTICS_SOURCE_ID,
            "canonical_ref": (
                f"FL-COURTS:PROBE:{STATISTICS_SOURCE_ID}"
            ),
            "status": "ok",
            "publication_count": len(statistics),
            "fiscal_years": fiscal_years,
            "latest_fiscal_year": fiscal_years[0],
        },
    ]


def _execute(
    args: argparse.Namespace,
    client: FloridaCourtsClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command == "sources":
        return PublicRecordsResult.success(
            query,
            _component_records(),
            warnings=WARNINGS,
        )
    if args.command == "manifest":
        return PublicRecordsResult.success(
            query,
            [_manifest_record()],
            warnings=WARNINGS,
        )
    if args.command == "locations":
        artifact = client.locations()
        records = _filter_locations(
            parse_location_directory(artifact),
            query_text=args.query,
            district=args.district,
            kind=args.kind,
        )
        return PublicRecordsResult.success(
            query,
            records,
            raw_artifact_refs=[artifact.source_url],
            warnings=WARNINGS,
        )
    if args.command == "virtual":
        artifact = client.virtual(
            county=args.county,
            judge=args.judge,
        )
        records = _filter_virtual(
            parse_virtual_directory(artifact),
            query_text=args.query,
            live_only=args.live_only,
        )
        return PublicRecordsResult.success(
            query,
            records,
            raw_artifact_refs=[artifact.source_url],
            warnings=WARNINGS,
        )
    if args.command == "data-request":
        artifact = client.page(PUBLIC_RECORDS_URL)
        return PublicRecordsResult.success(
            query,
            [parse_data_request_program(artifact)],
            raw_artifact_refs=[artifact.source_url],
            warnings=WARNINGS,
        )
    if args.command == "statistics":
        artifact = client.page(STATISTICS_CATALOG_URL)
        records = _filter_statistics(
            parse_statistics_catalog(artifact),
            fiscal_year=args.fiscal_year,
            section=args.section,
            query_text=args.query,
            limit=args.limit,
        )
        return PublicRecordsResult.success(
            query,
            records,
            raw_artifact_refs=[artifact.source_url],
            warnings=WARNINGS,
        )
    if args.command == "download":
        catalog_artifact = client.page(STATISTICS_CATALOG_URL)
        catalog_record = _resolve_statistics_artifact(
            parse_statistics_catalog(catalog_artifact),
            args.selector,
        )
        pdf = client.get(
            str(catalog_record["artifact_url"]),
            accept="application/pdf",
            maximum_bytes=MAXIMUM_PDF_BYTES,
        )
        record = _write_pdf(
            pdf,
            destination=args.destination,
            overwrite=args.overwrite,
            catalog_record=catalog_record,
        )
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=[record["artifact_path"]],
            warnings=WARNINGS,
        )
    if args.command == "probe":
        return PublicRecordsResult.success(
            query,
            _probe_records(client),
            warnings=WARNINGS,
        )
    raise SelectionError(
        "unsupported_command",
        f"unsupported Florida Courts command {args.command!r}",
    )


def _log(result: PublicRecordsResult) -> None:
    count = (
        len(result.records)
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else None
    )
    try:
        log_search(
            canonical_json(result.query.to_dict()),
            result.query.source.source_id,
            count,
        )
    except Exception as exc:
        print(
            f"WARNING: could not log Florida Courts search: {exc}",
            file=sys.stderr,
        )


def execute(
    args: argparse.Namespace,
    *,
    client: FloridaCourtsClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = build_query(args)
    own_client = client is None
    source_client = client or FloridaCourtsClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )
    try:
        result = _execute(args, source_client, query)
    except FloridaCourtDataError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=WARNINGS,
        )
    finally:
        if own_client:
            source_client.close()
    if log_results:
        _log(result)
    return result


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
    )
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Florida's official statewide court directory and "
            "data-source family"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("sources", "List distinct source components and roles"),
        ("manifest", "Show source relationships and adjacent routes"),
        ("data-request", "Read the current OSCA public-records request route"),
        ("probe", "Verify all four official source components"),
    ):
        subparser = subparsers.add_parser(command, help=help_text)
        _add_runtime_and_output(subparser)

    locations = subparsers.add_parser(
        "locations",
        help="List or search statewide county and DCA locations",
    )
    locations.add_argument("--query")
    locations.add_argument(
        "--district",
        choices=tuple(EXPECTED_DISTRICTS),
    )
    locations.add_argument(
        "--kind",
        choices=("county", "dca"),
    )
    _add_runtime_and_output(locations)

    virtual = subparsers.add_parser(
        "virtual",
        help="Search the Virtual Courtroom Directory",
    )
    virtual_selection = virtual.add_mutually_exclusive_group()
    virtual_selection.add_argument("--county")
    virtual_selection.add_argument("--judge")
    virtual.add_argument("--query")
    virtual.add_argument("--live-only", action="store_true")
    _add_runtime_and_output(virtual)

    statistics = subparsers.add_parser(
        "statistics",
        help="List or search downloadable trial-court statistics",
    )
    statistics.add_argument("--fiscal-year")
    statistics.add_argument("--section")
    statistics.add_argument("--query")
    statistics.add_argument("--limit", type=int)
    _add_runtime_and_output(statistics)

    download = subparsers.add_parser(
        "download",
        help="Download one exact statistical publication",
    )
    download.add_argument(
        "selector",
        help="Content ID, canonical reference, filename, or exact title",
    )
    download.add_argument("destination", type=Path)
    download.add_argument("--overwrite", action="store_true")
    _add_runtime_and_output(download)
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.minimum_interval < 0:
        raise SystemExit("--minimum-interval must not be negative")
    if args.max_attempts <= 0:
        raise SystemExit("--max-attempts must be positive")
    if args.retry_backoff < 0:
        raise SystemExit("--retry-backoff must not be negative")
    if getattr(args, "limit", None) is not None and args.limit <= 0:
        raise SystemExit("--limit must be positive")


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Florida Courts {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Florida Courts {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    for record in result.records:
        label = (
            record.get("name")
            or record.get("title")
            or record.get("record_kind")
            or "?"
        )
        detail = (
            record.get("source_url")
            or record.get("artifact_url")
            or record.get("base_url")
            or ""
        )
        print(f"  {label} | {detail}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    args = build_parser().parse_args()
    _validate_args(args)
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
