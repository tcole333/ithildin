#!/usr/bin/env python3
"""Query Georgia's official county-property routing and land-index sources.

Georgia publishes two complementary statewide entry points:

* the Department of Revenue's county-by-county property-record directory; and
* the Superior Court Clerks' Cooperative Authority statewide real-estate
  index, whose search summaries are available through a free account.

The first source is queried directly.  The second is represented as a verified
acquisition handoff so agents can retain its statewide coverage and account
path without treating a login page as a failed search.

Examples:
    uv run python tools/query_georgia_property_sources.py sources --json
    uv run python tools/query_georgia_property_sources.py directory \
        --county Fulton --json
    uv run python tools/query_georgia_property_sources.py directory qpublic \
        --limit 50 --json
    uv run python tools/query_georgia_property_sources.py platforms --json
    uv run python tools/query_georgia_property_sources.py handoff --json
    uv run python tools/query_georgia_property_sources.py probe \
        --source us-ga-dor-county-property-records-directory --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qsl, urljoin, urlsplit

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


DIRECTORY_SOURCE_ID = "us-ga-dor-county-property-records-directory"
GSCCCA_SOURCE_ID = "us-ga-gsccca-real-estate-index"
STATE_CODE = "GA"
STATE_GEOID = "13"

DIRECTORY_URL = "https://dor.georgia.gov/property-records-online"
GSCCCA_INFORMATION_URL = (
    "https://www.gsccca.org/learn/search-systems/real-estate-index"
)
GSCCCA_SEARCH_URL = "https://search.gsccca.org/RealEstate/"
GSCCCA_LOGIN_GATE_URL = (
    "https://search.gsccca.org/RealEstate/names.asp?Type=0"
)
GSCCCA_LIMITED_USE_URL = (
    "https://account.gsccca.org/LimitedUseCharges.asp"
)
GSCCCA_REGISTRATION_URL = "https://account.gsccca.org/default.asp"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.5
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_LIMIT = 50
MAXIMUM_HTML_BYTES = 16 * 1024 * 1024
CURSOR_PREFIX = "ga-property-directory:v1:"
OUTPUT_SCHEMA_VERSION = "georgia-property-sources/1.0"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

# Georgia's current county codes follow the historical odd-number sequence.
# Codes 041 (Campbell) and 203 (Milton) are retired.
COUNTY_NAMES = (
    "Appling",
    "Atkinson",
    "Bacon",
    "Baker",
    "Baldwin",
    "Banks",
    "Barrow",
    "Bartow",
    "Ben Hill",
    "Berrien",
    "Bibb",
    "Bleckley",
    "Brantley",
    "Brooks",
    "Bryan",
    "Bulloch",
    "Burke",
    "Butts",
    "Calhoun",
    "Camden",
    "Candler",
    "Carroll",
    "Catoosa",
    "Charlton",
    "Chatham",
    "Chattahoochee",
    "Chattooga",
    "Cherokee",
    "Clarke",
    "Clay",
    "Clayton",
    "Clinch",
    "Cobb",
    "Coffee",
    "Colquitt",
    "Columbia",
    "Cook",
    "Coweta",
    "Crawford",
    "Crisp",
    "Dade",
    "Dawson",
    "Decatur",
    "DeKalb",
    "Dodge",
    "Dooly",
    "Dougherty",
    "Douglas",
    "Early",
    "Echols",
    "Effingham",
    "Elbert",
    "Emanuel",
    "Evans",
    "Fannin",
    "Fayette",
    "Floyd",
    "Forsyth",
    "Franklin",
    "Fulton",
    "Gilmer",
    "Glascock",
    "Glynn",
    "Gordon",
    "Grady",
    "Greene",
    "Gwinnett",
    "Habersham",
    "Hall",
    "Hancock",
    "Haralson",
    "Harris",
    "Hart",
    "Heard",
    "Henry",
    "Houston",
    "Irwin",
    "Jackson",
    "Jasper",
    "Jeff Davis",
    "Jefferson",
    "Jenkins",
    "Johnson",
    "Jones",
    "Lamar",
    "Lanier",
    "Laurens",
    "Lee",
    "Liberty",
    "Lincoln",
    "Long",
    "Lowndes",
    "Lumpkin",
    "McDuffie",
    "McIntosh",
    "Macon",
    "Madison",
    "Marion",
    "Meriwether",
    "Miller",
    "Mitchell",
    "Monroe",
    "Montgomery",
    "Morgan",
    "Murray",
    "Muscogee",
    "Newton",
    "Oconee",
    "Oglethorpe",
    "Paulding",
    "Peach",
    "Pickens",
    "Pierce",
    "Pike",
    "Polk",
    "Pulaski",
    "Putnam",
    "Quitman",
    "Rabun",
    "Randolph",
    "Richmond",
    "Rockdale",
    "Schley",
    "Screven",
    "Seminole",
    "Spalding",
    "Stephens",
    "Stewart",
    "Sumter",
    "Talbot",
    "Taliaferro",
    "Tattnall",
    "Taylor",
    "Telfair",
    "Terrell",
    "Thomas",
    "Tift",
    "Toombs",
    "Towns",
    "Treutlen",
    "Troup",
    "Turner",
    "Twiggs",
    "Union",
    "Upson",
    "Walker",
    "Walton",
    "Ware",
    "Warren",
    "Washington",
    "Wayne",
    "Webster",
    "Wheeler",
    "White",
    "Whitfield",
    "Wilcox",
    "Wilkes",
    "Wilkinson",
    "Worth",
)
_CURRENT_COUNTY_CODES = tuple(
    code
    for code in range(1, 322, 2)
    if code not in {41, 203}
)
COUNTY_GEOIDS = {
    name: f"{STATE_GEOID}{code:03d}"
    for name, code in zip(
        COUNTY_NAMES,
        _CURRENT_COUNTY_CODES,
        strict=True,
    )
}
COUNTY_BY_KEY = {
    re.sub(r"[^a-z0-9]+", "", name.casefold()): name
    for name in COUNTY_NAMES
}
COUNTY_BY_GEOID = {
    geoid: name for name, geoid in COUNTY_GEOIDS.items()
}

DIRECTORY_SOURCE_METADATA = SourceMetadata(
    source_id=DIRECTORY_SOURCE_ID,
    name="Georgia DOR County Property Records Directory",
    source_role="official_statewide_county_property_source_directory",
    base_url=DIRECTORY_URL,
    dataset_id="georgia-dor-county-property-records-directory",
    metadata={
        "authority": "Georgia Department of Revenue",
        "operator": "State of Georgia",
        "authentication": "none",
        "coverage_model": "county_assessor_and_tax_system_routes",
    },
)
GSCCCA_SOURCE_METADATA = SourceMetadata(
    source_id=GSCCCA_SOURCE_ID,
    name="Georgia Consolidated Real Estate Index",
    source_role="official_statewide_deed_lien_and_plat_index",
    base_url=GSCCCA_INFORMATION_URL,
    dataset_id="georgia-gsccca-real-estate-index",
    metadata={
        "authority": (
            "Georgia Superior Court Clerks' Cooperative Authority"
        ),
        "operator": (
            "Georgia Superior Court Clerks' Cooperative Authority"
        ),
        "authentication": "account",
        "coverage_model": "statewide_county_recording_index",
    },
)
SOURCE_METADATA_BY_ID = {
    DIRECTORY_SOURCE_ID: DIRECTORY_SOURCE_METADATA,
    GSCCCA_SOURCE_ID: GSCCCA_SOURCE_METADATA,
}
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Georgia",
    state_code=STATE_CODE,
    metadata={"scope": "statewide_property_source_routing"},
)

DIRECTORY_WARNINGS = (
    "Directory rows identify county property-record destinations; each "
    "destination's fields and history remain source-specific.",
    "Published link disagreements and missing counties are retained as "
    "source observations.",
)
GSCCCA_WARNINGS = (
    "The statewide index and county assessor systems are complementary "
    "sources with separate record identities.",
)
_CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "captcha",
)
_OFFICIAL_HOSTS = frozenset(
    {
        "dor.georgia.gov",
        "www.gsccca.org",
        "search.gsccca.org",
        "account.gsccca.org",
        "apps.gsccca.org",
    }
)


@dataclass(frozen=True)
class Artifact:
    content: bytes
    source_url: str
    media_type: str | None
    headers: Mapping[str, str]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True)
class ParsedDirectory:
    records: tuple[Mapping[str, Any], ...]
    missing_counties: tuple[str, ...]
    unexpected_counties: tuple[str, ...]
    route_disagreements: tuple[str, ...]
    source_url: str
    source_document_sha256: str


class GeorgiaPropertySourceError(RuntimeError):
    """Transport, access, schema, or query-selection failure."""

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


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    result = " ".join(str(value).replace("\x00", "").split()).strip()
    return result or None


def _required(value: Any, field: str) -> str:
    result = _clean(value)
    if result is None:
        raise GeorgiaPropertySourceError(
            "source_field_missing",
            f"Georgia property source {field} is blank",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"field": field},
        )
    return result


def _media_type(response: Any) -> str | None:
    headers = getattr(response, "headers", {})
    value = headers.get("Content-Type", headers.get("content-type"))
    return (
        str(value).split(";", 1)[0].strip().casefold()
        if value
        else None
    )


def _retry_after(response: Any) -> float | None:
    headers = getattr(response, "headers", {})
    value = headers.get("Retry-After", headers.get("retry-after"))
    try:
        return max(0.0, float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _official_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname not in _OFFICIAL_HOSTS:
        raise GeorgiaPropertySourceError(
            "unrecognized_official_url",
            "Georgia source request must use a verified official HTTPS host",
            category="selection",
            details={"url": value},
        )
    return value


class GeorgiaPropertySourceClient:
    """Bounded, retrying client with an injectable requests-like session."""

    def __init__(
        self,
        *,
        session: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=DEFAULT_MAX_ATTEMPTS
        )
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.sleeper = sleeper

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def get(self, url: str) -> Artifact:
        _official_url(url)
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    "GET",
                    url,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise GeorgiaPropertySourceError(
                    "transport_error",
                    str(error),
                    category="transport",
                    retryable=True,
                    details={"url": url},
                ) from error

            status_code = int(getattr(response, "status_code", 0))
            if (
                status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(
                    self.retry_policy.delay(
                        attempt,
                        _retry_after(response),
                    )
                )
                continue
            if status_code == 429:
                raise GeorgiaPropertySourceError(
                    "rate_limited",
                    "Georgia property source rate limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="rate_limit",
                    retryable=True,
                    details={"url": url, "status_code": status_code},
                )
            if status_code in {401, 403}:
                raise GeorgiaPropertySourceError(
                    "access_restricted",
                    f"Georgia property source returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"url": url, "status_code": status_code},
                )
            if status_code < 200 or status_code >= 300:
                raise GeorgiaPropertySourceError(
                    "http_status",
                    f"Georgia property source returned HTTP {status_code}",
                    category="http",
                    retryable=status_code >= 500,
                    details={"url": url, "status_code": status_code},
                )

            content = bytes(getattr(response, "content", b""))
            if not content and getattr(response, "text", None):
                content = str(response.text).encode()
            if len(content) > MAXIMUM_HTML_BYTES:
                raise GeorgiaPropertySourceError(
                    "response_too_large",
                    "Georgia property source response exceeds the bound",
                    category="response_size",
                    details={
                        "url": url,
                        "byte_length": len(content),
                        "maximum_bytes": MAXIMUM_HTML_BYTES,
                    },
                )
            response_url = str(getattr(response, "url", None) or url)
            _official_url(response_url)
            return Artifact(
                content=content,
                source_url=response_url,
                media_type=_media_type(response),
                headers={
                    str(key).casefold(): str(value)
                    for key, value in getattr(
                        response,
                        "headers",
                        {},
                    ).items()
                },
            )
        raise GeorgiaPropertySourceError(
            "transport_error",
            str(last_error or "request failed"),
            category="transport",
            retryable=True,
            details={"url": url},
        )


def _html_soup(artifact: Artifact, *, marker: str) -> BeautifulSoup:
    if artifact.media_type and "html" not in artifact.media_type:
        raise GeorgiaPropertySourceError(
            "unexpected_media_type",
            "Georgia property source did not return HTML",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={
                "url": artifact.source_url,
                "media_type": artifact.media_type,
            },
        )
    soup = BeautifulSoup(artifact.content, "html.parser")
    text = soup.get_text(" ", strip=True)
    folded = text.casefold()
    if any(value in folded for value in _CHALLENGE_MARKERS):
        raise GeorgiaPropertySourceError(
            "human_verification",
            "Georgia property source returned a verification page",
            status=ResultStatus.HUMAN_REQUIRED,
            category="access",
            details={"url": artifact.source_url},
        )
    if marker.casefold() not in folded:
        raise GeorgiaPropertySourceError(
            "source_marker_missing",
            f"Georgia property source lacks expected marker {marker!r}",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"url": artifact.source_url, "marker": marker},
        )
    return soup


def _county_key(value: str) -> str:
    normalized = re.sub(
        r"\s+county$",
        "",
        value.strip(),
        flags=re.IGNORECASE,
    )
    return re.sub(r"[^a-z0-9]+", "", normalized.casefold())


def _county_name(value: str) -> str:
    raw = value.strip()
    if raw in COUNTY_BY_GEOID:
        return COUNTY_BY_GEOID[raw]
    if re.fullmatch(r"\d{3}", raw):
        geoid = STATE_GEOID + raw
        if geoid in COUNTY_BY_GEOID:
            return COUNTY_BY_GEOID[geoid]
    key = _county_key(raw)
    if key in COUNTY_BY_KEY:
        return COUNTY_BY_KEY[key]
    raise GeorgiaPropertySourceError(
        "unknown_county",
        f"Georgia county is not recognized: {value}",
        category="query_selection",
        details={"county": value},
    )


def _route_target_key(url: str) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(
        r"/index\.html?$",
        "/",
        parsed.path,
        flags=re.IGNORECASE,
    )
    path = re.sub(r"/+", "/", path).rstrip("/").casefold()
    return host, path, tuple(sorted(parse_qsl(parsed.query)))


def _platform_family(url: str) -> str:
    host = (urlsplit(url).hostname or "").casefold()
    if host.removeprefix("www.") == "qpublic.net":
        return "qpublic_legacy"
    if host == "qpublic.schneidercorp.com":
        return "qpublic_schneider"
    return "county_hosted"


def parse_directory_page(artifact: Artifact) -> ParsedDirectory:
    """Parse DOR's published county routing table and coverage observations."""
    soup = _html_soup(artifact, marker="Property Records Online")
    table = soup.select_one("table#datatable")
    if table is None:
        raise GeorgiaPropertySourceError(
            "directory_table_missing",
            "Georgia DOR property directory table is missing",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"url": artifact.source_url},
        )
    headers = [
        _clean(cell.get_text(" ", strip=True))
        for cell in table.select("thead th")
    ]
    if headers != ["Link", "Description"]:
        raise GeorgiaPropertySourceError(
            "directory_headers_changed",
            "Georgia DOR property directory headers changed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"url": artifact.source_url, "headers": headers},
        )

    records: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    route_disagreements: list[str] = []
    unexpected: list[str] = []
    for ordinal, row in enumerate(table.select("tbody tr"), start=1):
        cells = row.select("td")
        if len(cells) != 2:
            raise GeorgiaPropertySourceError(
                "directory_row_width_changed",
                "Georgia DOR property directory row must have two cells",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
                details={
                    "url": artifact.source_url,
                    "ordinal": ordinal,
                    "cell_count": len(cells),
                },
            )
        county_raw = _required(
            cells[0].get_text(" ", strip=True),
            "county",
        )
        county = COUNTY_BY_KEY.get(_county_key(county_raw))
        if county is None:
            unexpected.append(county_raw)
            continue
        if county in seen:
            raise GeorgiaPropertySourceError(
                "directory_duplicate_county",
                f"Georgia DOR property directory repeats {county}",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
                details={"county": county, "url": artifact.source_url},
            )
        seen.add(county)

        primary_anchor = cells[0].select_one("a[href]")
        description_anchor = cells[1].select_one("a[href]")
        if primary_anchor is None or description_anchor is None:
            raise GeorgiaPropertySourceError(
                "directory_route_missing",
                f"Georgia DOR property directory lacks a route for {county}",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
                details={"county": county, "url": artifact.source_url},
            )
        primary_url = urljoin(
            artifact.source_url,
            _required(primary_anchor.get("href"), "primary route"),
        )
        description_url = urljoin(
            artifact.source_url,
            _required(
                description_anchor.get("href"),
                "description route",
            ),
        )
        for candidate in (primary_url, description_url):
            if urlsplit(candidate).scheme not in {"http", "https"}:
                raise GeorgiaPropertySourceError(
                    "directory_route_invalid",
                    f"Georgia DOR route is not HTTP(S): {candidate}",
                    status=ResultStatus.SOURCE_CHANGED,
                    category="source_schema",
                    details={"county": county, "url": candidate},
                )
        disagreement = (
            _route_target_key(primary_url)
            != _route_target_key(description_url)
        )
        if disagreement:
            route_disagreements.append(county)
        geoid = COUNTY_GEOIDS[county]
        records.append(
            {
                "canonical_ref": (
                    f"GA-DOR-PROPERTY-ROUTE:{geoid}"
                ),
                "evidence_ref": (
                    f"GA-DOR-PROPERTY-DIRECTORY:{geoid}"
                ),
                "source_id": DIRECTORY_SOURCE_ID,
                "record_kind": "county_property_source_route",
                "county_name": county,
                "county_geoid": geoid,
                "state_code": STATE_CODE,
                "published_primary_url": primary_url,
                "published_description_url": description_url,
                "route_target_disagreement": disagreement,
                "platform_family": _platform_family(primary_url),
                "destination_host": (
                    urlsplit(primary_url).hostname or ""
                ).casefold(),
                "directory_ordinal": ordinal,
                "source_url": artifact.source_url,
                "source_document_sha256": artifact.sha256,
                "projection": {
                    "projectable_as_property_record": False,
                    "scope": "official_county_source_route",
                },
            }
        )

    if not records:
        raise GeorgiaPropertySourceError(
            "directory_empty",
            "Georgia DOR property directory contains no county routes",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"url": artifact.source_url},
        )
    missing = sorted(set(COUNTY_NAMES) - seen)
    return ParsedDirectory(
        records=tuple(records),
        missing_counties=tuple(missing),
        unexpected_counties=tuple(sorted(unexpected)),
        route_disagreements=tuple(sorted(route_disagreements)),
        source_url=artifact.source_url,
        source_document_sha256=artifact.sha256,
    )


def parse_gsccca_handoff(
    information: Artifact,
    limited_use: Artifact,
    login_gate: Artifact,
) -> dict[str, Any]:
    """Parse the official coverage, free-account, and login-gate facts."""
    information_soup = _html_soup(
        information,
        marker="Search Systems Real Estate Index",
    )
    limited_soup = _html_soup(
        limited_use,
        marker="Limited-Use Account Charges",
    )
    gate_soup = BeautifulSoup(login_gate.content, "html.parser")

    information_text = _required(
        information_soup.get_text(" ", strip=True),
        "GSCCCA coverage text",
    )
    limited_text = _required(
        limited_soup.get_text(" ", strip=True),
        "GSCCCA limited-use text",
    )
    required_information = (
        "all counties in Georgia",
        "since at least January 1, 1999",
        "names of the parties",
        "book and page",
    )
    missing_information = [
        marker
        for marker in required_information
        if marker.casefold() not in information_text.casefold()
    ]
    required_limited = (
        "search the Deed, Lien, Plat, and UCC indexes",
        "There is no cost to create a Limited-Use account",
        "Cannot view images",
    )
    missing_limited = [
        marker
        for marker in required_limited
        if marker.casefold() not in limited_text.casefold()
    ]
    gate_form = gate_soup.select_one(
        'form[action*="apps.gsccca.org/login.asp"]'
    )
    if missing_information or missing_limited or gate_form is None:
        raise GeorgiaPropertySourceError(
            "gsccca_handoff_changed",
            "GSCCCA coverage or account handoff markers changed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={
                "missing_information_markers": missing_information,
                "missing_limited_use_markers": missing_limited,
                "login_gate_present": gate_form is not None,
            },
        )
    action = urljoin(
        login_gate.source_url,
        _required(gate_form.get("action"), "login handoff URL"),
    )
    if urlsplit(action).hostname != "apps.gsccca.org":
        raise GeorgiaPropertySourceError(
            "gsccca_login_route_changed",
            "GSCCCA login handoff no longer uses its official app host",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"action": action},
        )

    component_hashes = {
        "information": information.sha256,
        "limited_use": limited_use.sha256,
        "login_gate": login_gate.sha256,
    }
    return {
        "canonical_ref": (
            f"GA-GSCCCA-REAL-ESTATE-INDEX:{STATE_GEOID}/handoff"
        ),
        "evidence_ref": (
            f"GA-GSCCCA-REAL-ESTATE-INDEX:{STATE_GEOID}"
        ),
        "source_id": GSCCCA_SOURCE_ID,
        "record_kind": "property_index_acquisition_handoff",
        "authority": (
            "Georgia Superior Court Clerks' Cooperative Authority"
        ),
        "coverage": {
            "geography": "all Georgia counties",
            "deed_index_since_at_least": "1999-01-01",
            "historical_data": "continually_added",
            "search_dimensions": [
                "party_name",
                "property_subdivision_unit_block_lot",
                "county_book_page",
                "date_range",
                "party_type",
                "instrument_type",
                "county_or_region_or_statewide",
            ],
            "summary_fields": [
                "instrument_parties",
                "property_location",
                "deed_book",
                "deed_page",
            ],
        },
        "access": {
            "search_requires_account": True,
            "limited_use_account_cost": "no_cost",
            "limited_use_recurring_fee": False,
            "limited_use_summary_index_access": True,
            "limited_use_document_images": False,
            "registration_url": GSCCCA_REGISTRATION_URL,
            "search_url": GSCCCA_SEARCH_URL,
            "login_handoff_url": action,
        },
        "complementary_sources": [
            {
                "source_id": DIRECTORY_SOURCE_ID,
                "relationship": (
                    "county assessor and tax-system routing"
                ),
            },
            {
                "source_id": "us-ga-county-superior-court-clerks",
                "relationship": (
                    "county record custodians and local filing offices"
                ),
            },
        ],
        "source_urls": [
            information.source_url,
            limited_use.source_url,
            login_gate.source_url,
        ],
        "source_document_sha256": sha256_fingerprint(
            component_hashes
        ),
        "component_sha256": component_hashes,
        "projection": {
            "projectable_as_property_record": False,
            "scope": "verified_acquisition_handoff",
        },
    }


def _source_records() -> list[dict[str, Any]]:
    return [
        {
            "source_id": DIRECTORY_SOURCE_ID,
            "record_kind": "source_description",
            "name": DIRECTORY_SOURCE_METADATA.name,
            "authority": "Georgia Department of Revenue",
            "official_url": DIRECTORY_URL,
            "operations": ["directory", "platforms", "probe"],
            "roles": [
                "county_assessment_source_routing",
                "county_tax_source_routing",
                "vendor_family_discovery",
            ],
        },
        {
            "source_id": GSCCCA_SOURCE_ID,
            "record_kind": "source_description",
            "name": GSCCCA_SOURCE_METADATA.name,
            "authority": (
                "Georgia Superior Court Clerks' Cooperative Authority"
            ),
            "official_url": GSCCCA_INFORMATION_URL,
            "operations": ["handoff", "probe"],
            "roles": [
                "statewide_deed_index",
                "statewide_lien_index",
                "statewide_plat_index",
            ],
        },
    ]


def _manifest_record(source_id: str) -> dict[str, Any]:
    if source_id == DIRECTORY_SOURCE_ID:
        return {
            "source_id": source_id,
            "record_kind": "source_manifest",
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "authority": "Georgia Department of Revenue",
            "operations": ["directory", "platforms", "probe"],
            "coverage": {
                "expected_counties": len(COUNTY_NAMES),
                "county_geoids": list(COUNTY_GEOIDS.values()),
                "destination_capabilities": "source_specific",
            },
            "stable_identity": [
                "source_id",
                "county_geoid",
                "published_primary_url",
            ],
            "complementary_source_ids": [GSCCCA_SOURCE_ID],
        }
    if source_id == GSCCCA_SOURCE_ID:
        return {
            "source_id": source_id,
            "record_kind": "source_manifest",
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "authority": (
                "Georgia Superior Court Clerks' Cooperative Authority"
            ),
            "operations": ["handoff", "probe"],
            "coverage": {
                "geography": "statewide",
                "deed_index_since_at_least": "1999-01-01",
                "limited_use_summary_search": "free_account",
                "limited_use_document_images": False,
            },
            "stable_identity": [
                "canonical_ref",
            ],
            "complementary_source_ids": [DIRECTORY_SOURCE_ID],
        }
    raise ValueError(f"unknown Georgia property source {source_id}")


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    ignored = {
        "command",
        "output",
        "json_out",
        "quiet",
        "timeout",
        "minimum_interval",
        "max_attempts",
    }
    return {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
        if key not in ignored and value is not None
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    source_id = getattr(args, "source", DIRECTORY_SOURCE_ID)
    return PublicRecordsQuery(
        source=SOURCE_METADATA_BY_ID[source_id],
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _failure(
    query: PublicRecordsQuery,
    error: GeorgiaPropertySourceError,
    *,
    warnings: tuple[str, ...],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category=error.category,
                retryable=error.retryable,
                details=error.details,
            )
        ],
        warnings=warnings,
    )


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
    *,
    warnings: tuple[str, ...],
) -> PublicRecordsResult:
    status_value = str(
        decision.get("result_status")
        or decision.get("status")
        or (
            ResultStatus.HUMAN_REQUIRED.value
            if decision.get("automation_disposition")
            == "human_required"
            else ResultStatus.RESTRICTED.value
        )
    )
    try:
        status = ResultStatus(status_value)
    except ValueError:
        status = ResultStatus.RESTRICTED
    return PublicRecordsResult.failure(
        query,
        status,
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


def _query_key(
    query: str | None,
    county: str | None,
    platform: str | None,
) -> str:
    return sha256_fingerprint(
        {
            "query": query,
            "county": county,
            "platform": platform,
        }
    )


def _encode_cursor(
    *,
    query_key: str,
    source_sha256: str,
    offset: int,
    boundary_ref: str,
) -> str:
    payload = canonical_json(
        {
            "query_key": query_key,
            "source_sha256": source_sha256,
            "offset": offset,
            "boundary_ref": boundary_ref,
        }
    ).encode()
    token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return CURSOR_PREFIX + token


def _decode_cursor(
    cursor: str | None,
    *,
    query_key: str,
    source_sha256: str,
    records: list[Mapping[str, Any]],
) -> int:
    if cursor is None:
        return 0
    if not cursor.startswith(CURSOR_PREFIX):
        raise GeorgiaPropertySourceError(
            "invalid_cursor",
            "Georgia property-directory cursor prefix is invalid",
            category="query_selection",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(
                token + "=" * (-len(token) % 4)
            ).decode()
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GeorgiaPropertySourceError(
            "invalid_cursor",
            "Georgia property-directory cursor is malformed",
            category="query_selection",
        ) from error
    if not isinstance(payload, Mapping):
        raise GeorgiaPropertySourceError(
            "invalid_cursor",
            "Georgia property-directory cursor payload is invalid",
            category="query_selection",
        )
    if payload.get("query_key") != query_key:
        raise GeorgiaPropertySourceError(
            "cursor_query_mismatch",
            "Georgia property-directory cursor belongs to another query",
            category="query_selection",
        )
    if payload.get("source_sha256") != source_sha256:
        raise GeorgiaPropertySourceError(
            "cursor_source_changed",
            "Georgia property-directory source changed after cursor issue",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    offset = payload.get("offset")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 1
        or offset > len(records)
    ):
        raise GeorgiaPropertySourceError(
            "invalid_cursor",
            "Georgia property-directory cursor offset is invalid",
            category="query_selection",
        )
    previous = records[offset - 1]
    if payload.get("boundary_ref") != previous.get("canonical_ref"):
        raise GeorgiaPropertySourceError(
            "cursor_boundary_changed",
            "Georgia property-directory cursor boundary changed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    return offset


def _filter_directory(
    parsed: ParsedDirectory,
    *,
    query: str | None,
    county: str | None,
    platform: str | None,
) -> list[Mapping[str, Any]]:
    county_name = _county_name(county) if county else None
    needle = _clean(query)
    if needle in {None, "*"}:
        needle = None
    folded = needle.casefold() if needle else None
    records = []
    for record in parsed.records:
        if county_name and record["county_name"] != county_name:
            continue
        if platform and record["platform_family"] != platform:
            continue
        if folded:
            haystack = " ".join(
                str(record.get(field) or "")
                for field in (
                    "county_name",
                    "county_geoid",
                    "published_primary_url",
                    "published_description_url",
                    "platform_family",
                    "destination_host",
                )
            ).casefold()
            if folded not in haystack:
                continue
        records.append(record)
    return records


def _page_directory(
    parsed: ParsedDirectory,
    *,
    query: str | None,
    county: str | None,
    platform: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[Mapping[str, Any]], str | None]:
    records = _filter_directory(
        parsed,
        query=query,
        county=county,
        platform=platform,
    )
    query_key = _query_key(query, county, platform)
    offset = _decode_cursor(
        cursor,
        query_key=query_key,
        source_sha256=parsed.source_document_sha256,
        records=records,
    )
    selected = records[offset : offset + limit]
    next_offset = offset + len(selected)
    next_cursor = None
    if selected and next_offset < len(records):
        next_cursor = _encode_cursor(
            query_key=query_key,
            source_sha256=parsed.source_document_sha256,
            offset=next_offset,
            boundary_ref=str(selected[-1]["canonical_ref"]),
        )
    return selected, next_cursor


def _platform_records(
    parsed: ParsedDirectory,
) -> list[dict[str, Any]]:
    counties: dict[str, list[str]] = defaultdict(list)
    hosts: dict[str, Counter[str]] = defaultdict(Counter)
    for record in parsed.records:
        platform = str(record["platform_family"])
        counties[platform].append(str(record["county_name"]))
        hosts[platform][str(record["destination_host"])] += 1
    return [
        {
            "canonical_ref": (
                f"GA-DOR-PROPERTY-PLATFORM:{platform}"
            ),
            "source_id": DIRECTORY_SOURCE_ID,
            "record_kind": "county_property_platform_summary",
            "platform_family": platform,
            "county_count": len(counties[platform]),
            "counties": counties[platform],
            "destination_hosts": dict(
                sorted(hosts[platform].items())
            ),
            "source_url": parsed.source_url,
            "source_document_sha256": (
                parsed.source_document_sha256
            ),
        }
        for platform in sorted(counties)
    ]


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: GeorgiaPropertySourceClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = build_query(args)
    warnings = (
        DIRECTORY_WARNINGS
        if query.source.source_id == DIRECTORY_SOURCE_ID
        else GSCCCA_WARNINGS
    )
    if access_decision is not None and not access_decision.get(
        "allowed",
        False,
    ):
        result = _decision_failure(
            query,
            access_decision,
            warnings=warnings,
        )
        if log_results:
            log_search(canonical_json(query.to_dict()), query.source.source_id, None)
        return result

    network_command = args.command in {
        "directory",
        "platforms",
        "handoff",
        "probe",
    }
    source_client = client
    if network_command and source_client is None:
        source_client = GeorgiaPropertySourceClient(
            timeout=args.timeout,
            minimum_interval=args.minimum_interval,
            retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        )
    try:
        if args.command == "sources":
            result = PublicRecordsResult.success(
                query,
                _source_records(),
                warnings=DIRECTORY_WARNINGS,
            )
        elif args.command == "manifest":
            result = PublicRecordsResult.success(
                query,
                [_manifest_record(args.source)],
                warnings=warnings,
            )
        elif args.command in {"directory", "platforms"}:
            parsed = parse_directory_page(
                source_client.get(DIRECTORY_URL)
            )
            if args.command == "directory":
                records, next_cursor = _page_directory(
                    parsed,
                    query=args.query,
                    county=args.county,
                    platform=args.platform,
                    limit=args.limit,
                    cursor=args.cursor,
                )
                result = PublicRecordsResult.success(
                    query,
                    records,
                    next_cursor=next_cursor,
                    warnings=DIRECTORY_WARNINGS,
                )
            else:
                result = PublicRecordsResult.success(
                    query,
                    _platform_records(parsed),
                    warnings=DIRECTORY_WARNINGS,
                )
        elif args.command == "handoff":
            record = parse_gsccca_handoff(
                source_client.get(GSCCCA_INFORMATION_URL),
                source_client.get(GSCCCA_LIMITED_USE_URL),
                source_client.get(GSCCCA_LOGIN_GATE_URL),
            )
            result = PublicRecordsResult.success(
                query,
                [record],
                warnings=GSCCCA_WARNINGS,
            )
        elif args.command == "probe":
            if args.source == DIRECTORY_SOURCE_ID:
                parsed = parse_directory_page(
                    source_client.get(DIRECTORY_URL)
                )
                platform_counts = Counter(
                    str(record["platform_family"])
                    for record in parsed.records
                )
                record = {
                    "source_id": DIRECTORY_SOURCE_ID,
                    "record_kind": "source_probe",
                    "status": "ok",
                    "row_count": len(parsed.records),
                    "expected_county_count": len(COUNTY_NAMES),
                    "missing_counties": list(
                        parsed.missing_counties
                    ),
                    "unexpected_counties": list(
                        parsed.unexpected_counties
                    ),
                    "route_disagreements": list(
                        parsed.route_disagreements
                    ),
                    "platform_counts": dict(
                        sorted(platform_counts.items())
                    ),
                    "source_url": parsed.source_url,
                    "source_document_sha256": (
                        parsed.source_document_sha256
                    ),
                    "stable_schema_sha256": sha256_fingerprint(
                        {
                            "record_kind": (
                                "county_property_source_route"
                            ),
                            "fields": sorted(parsed.records[0]),
                            "expected_counties": (
                                list(COUNTY_NAMES)
                            ),
                        }
                    ),
                }
            else:
                handoff = parse_gsccca_handoff(
                    source_client.get(GSCCCA_INFORMATION_URL),
                    source_client.get(GSCCCA_LIMITED_USE_URL),
                    source_client.get(GSCCCA_LOGIN_GATE_URL),
                )
                record = {
                    "source_id": GSCCCA_SOURCE_ID,
                    "record_kind": "source_probe",
                    "status": "ok",
                    "coverage": handoff["coverage"],
                    "access": handoff["access"],
                    "component_sha256": (
                        handoff["component_sha256"]
                    ),
                    "stable_schema_sha256": sha256_fingerprint(
                        {
                            "record_kind": handoff["record_kind"],
                            "coverage_fields": sorted(
                                handoff["coverage"]
                            ),
                            "access_fields": sorted(
                                handoff["access"]
                            ),
                        }
                    ),
                }
            result = PublicRecordsResult.success(
                query,
                [record],
                warnings=warnings,
            )
        else:
            raise ValueError(
                f"unsupported Georgia property command {args.command!r}"
            )
    except GeorgiaPropertySourceError as error:
        result = _failure(query, error, warnings=warnings)
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
            warnings=warnings,
        )
    finally:
        if network_command and client is None and source_client is not None:
            source_client.close()

    if log_results:
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
        log_search(
            canonical_json(query.to_dict()),
            query.source.source_id,
            count,
        )
    return result


def _add_runtime(parser: argparse.ArgumentParser) -> None:
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
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Georgia's official county property routes and statewide "
            "real-estate-index acquisition handoff"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="List the complementary official source identities",
    )
    sources.set_defaults(source=DIRECTORY_SOURCE_ID)
    _add_runtime(sources)

    manifest = sub.add_parser(
        "manifest",
        help="Describe one source's coverage and operations",
    )
    manifest.add_argument(
        "--source",
        choices=sorted(SOURCE_METADATA_BY_ID),
        default=DIRECTORY_SOURCE_ID,
    )
    _add_runtime(manifest)

    directory = sub.add_parser(
        "directory",
        help="Search DOR's county property-record routing table",
    )
    directory.add_argument("query", nargs="?", default="*")
    directory.add_argument("--county")
    directory.add_argument(
        "--platform",
        choices=(
            "qpublic_legacy",
            "qpublic_schneider",
            "county_hosted",
        ),
    )
    directory.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    directory.add_argument("--cursor")
    directory.set_defaults(source=DIRECTORY_SOURCE_ID)
    _add_runtime(directory)

    platforms = sub.add_parser(
        "platforms",
        help="Summarize reusable destination platform families",
    )
    platforms.set_defaults(source=DIRECTORY_SOURCE_ID)
    _add_runtime(platforms)

    handoff = sub.add_parser(
        "handoff",
        help="Verify the GSCCCA statewide-index account handoff",
    )
    handoff.set_defaults(source=GSCCCA_SOURCE_ID)
    _add_runtime(handoff)

    probe = sub.add_parser(
        "probe",
        help="Run one bounded source-specific sentinel",
    )
    probe.add_argument(
        "--source",
        choices=sorted(SOURCE_METADATA_BY_ID),
        default=DIRECTORY_SOURCE_ID,
    )
    _add_runtime(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Georgia property sources {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Georgia property sources {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        label = (
            record.get("county_name")
            or record.get("platform_family")
            or record.get("source_id")
            or record.get("canonical_ref")
        )
        print(f"  {label}")
    for error in result.errors:
        print(
            f"ERROR [{error.code}]: {error.message}",
            file=sys.stderr,
        )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.minimum_interval < 0:
        parser.error("--minimum-interval must not be negative")
    if args.max_attempts <= 0:
        parser.error("--max-attempts must be positive")
    if getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
