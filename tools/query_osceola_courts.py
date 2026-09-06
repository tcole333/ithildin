#!/usr/bin/env python3
"""Query Osceola County Clerk's public Pioneer Benchmark court portal.

The portal uses a normal ASP.NET session plus an anti-forgery token for
searches. Search results are served by a session-scoped DataTables endpoint;
case summary, docket, history, charge, and document-page metadata are exposed
through separate public routes. This adapter reacquires session locators from
stable case numbers and docket IDs instead of persisting signed digests.

Examples:
    uv run python tools/query_osceola_courts.py sources --json
    uv run python tools/query_osceola_courts.py search SMITH --json
    uv run python tools/query_osceola_courts.py search \
        "2023 CF 001540" --search-mode case-number --json
    uv run python tools/query_osceola_courts.py case \
        "2023 CF 001540" --output /tmp/osceola-case.json
    uv run python tools/query_osceola_courts.py docket \
        "2023 CF 001540" --json
    uv run python tools/query_osceola_courts.py document-metadata \
        "2023 CF 001540" 56773534 --json
    uv run python tools/query_osceola_courts.py reports --json
    uv run python tools/query_osceola_courts.py report calendar \
        --artifact-output /tmp/osceola-calendar.pdf --json
    uv run python tools/query_osceola_courts.py request-handoff \
        --case-number "2023 CF 001540" --docket-id 56773534 --json
    uv run python tools/query_osceola_courts.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, Tag

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
    from tools.public_records_store import canonical_court_ref
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
    from public_records_store import canonical_court_ref


PORTAL_SOURCE_ID = "us-fl-osceola-benchmark-courts"
CALENDAR_SOURCE_ID = "us-fl-osceola-court-hearing-calendar"
FORECLOSURE_SOURCE_ID = "us-fl-osceola-mortgage-foreclosure-schedule"
STATE_CODE = "FL"
COUNTY_GEOID = "12097"
JUDICIAL_CIRCUIT = "9"

PORTAL_BASE_URL = "https://courts.osceolaclerk.com/BenchmarkWeb/"
SEARCH_LANDING_URL = urljoin(PORTAL_BASE_URL, "Home.aspx/Search")
CASE_SEARCH_URL = urljoin(PORTAL_BASE_URL, "CourtCase.aspx/CaseSearch")
RESULT_DATA_URL = urljoin(PORTAL_BASE_URL, "Search.aspx/CaseSearch")
DOCKET_REQUEST_URL = urljoin(
    PORTAL_BASE_URL,
    "CaseDocket.aspx/Request",
)
CALENDAR_URL = "https://courts.osceolaclerk.com/reports/CourtCalendarWeb.pdf"
FORECLOSURE_URL = (
    "https://courts.osceolaclerk.com/reports/CivilMortgageForeclosuresWeb.pdf"
)
PUBLIC_RECORDS_URL = "https://osceolaclerk.com/request-a-public-record/"
REGISTRATION_URL = "https://osceolaclerk.com/court-records-registration/"
JUSTFOIA_URL = "https://osceolaclerkfl.justfoia.com/publicportal/home/newrequest"
ECERTIFIED_URL = (
    "https://www.clerkecertify.com/OrderOfficialRecords?PublisherCode=12097"
)

PLATFORM_FAMILY = "pioneer_benchmark_2_x"
OUTPUT_SCHEMA_VERSION = "osceola-benchmark-courts/1.0"
CURSOR_PREFIX = "osceola-benchmark:v1:"
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.5
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_LIMIT = 50
MAXIMUM_HTML_BYTES = 24 * 1024 * 1024
MAXIMUM_JSON_BYTES = 24 * 1024 * 1024
MAXIMUM_PDF_BYTES = 96 * 1024 * 1024
SOURCE_RESULT_CEILING = 5000
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

SEARCH_MODE_TO_NATIVE = {
    "name": "Name",
    "case-number": "CaseNumber",
    "citation-number": "CitationNumber",
    "arresting-case-number": "CaseNumberArresting",
}
NATIVE_SEARCH_MODES = frozenset(SEARCH_MODE_TO_NATIVE.values())

PORTAL_WARNINGS = (
    "Benchmark search and document locators are reacquired in a live session "
    "from stable case-number and docket identities.",
    "A search reported at the portal's 5,000-row broad-query ceiling is "
    "returned as partial.",
    "Document metadata describes the public portal state; certified copies "
    "use the Clerk's separate acquisition route.",
)
REPORT_WARNINGS = (
    "The hearing calendar is forward-looking and does not include past hearings.",
    "Foreclosure schedules can change; the Clerk identifies the case record "
    "as the source for cancellation status.",
)

PORTAL_SOURCE = SourceMetadata(
    source_id=PORTAL_SOURCE_ID,
    name="Osceola County Clerk Benchmark Court Records",
    source_role=("county_clerk_case_index_docket_document_metadata_and_request_routes"),
    base_url=SEARCH_LANDING_URL,
    dataset_id="osceola-pioneer-benchmark-public-court-records",
    metadata={
        "authority": ("Osceola County Clerk of the Circuit Court & County Comptroller"),
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "judicial_circuit": JUDICIAL_CIRCUIT,
        "platform_family": PLATFORM_FAMILY,
        "authentication": "anonymous_public_search",
        "registered_access_route": REGISTRATION_URL,
    },
)
CALENDAR_SOURCE = SourceMetadata(
    source_id=CALENDAR_SOURCE_ID,
    name="Osceola County Court Hearing Calendar",
    source_role="county_court_forward_hearing_calendar_pdf",
    base_url=CALENDAR_URL,
    dataset_id="osceola-court-hearing-calendar-current",
    metadata={
        "authority": ("Osceola County Clerk of the Circuit Court & County Comptroller"),
        "county_geoid": COUNTY_GEOID,
        "record_grain": "scheduled_hearing",
    },
)
FORECLOSURE_SOURCE = SourceMetadata(
    source_id=FORECLOSURE_SOURCE_ID,
    name="Osceola County Scheduled Mortgage Foreclosure Sales",
    source_role="county_clerk_forward_mortgage_foreclosure_schedule_pdf",
    base_url=FORECLOSURE_URL,
    dataset_id="osceola-mortgage-foreclosure-schedule-current",
    metadata={
        "authority": ("Osceola County Clerk of the Circuit Court & County Comptroller"),
        "county_geoid": COUNTY_GEOID,
        "record_grain": "scheduled_mortgage_foreclosure_sale",
    },
)
SOURCE_BY_ID = {
    PORTAL_SOURCE_ID: PORTAL_SOURCE,
    CALENDAR_SOURCE_ID: CALENDAR_SOURCE,
    FORECLOSURE_SOURCE_ID: FORECLOSURE_SOURCE,
}
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name="Osceola County, Florida",
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality="Osceola County",
    metadata={"judicial_circuit": JUDICIAL_CIRCUIT},
)

_CIRCUIT_CASE_CODES = frozenset({"CA", "CF", "CJ", "CP", "DP", "DR", "GA", "MH"})
_COUNTY_CASE_CODES = frozenset({"CC", "CO", "CT", "MM", "SC", "TR"})
_PLATFORM_VERSION_RE = re.compile(r"[?&]version=(\d+(?:\.\d+){2,})")
_CASE_ID_RE = re.compile(r"/Details/(\d+)", re.IGNORECASE)
_PARTY_ID_RE = re.compile(r"/Party\.aspx/Index/(\d+)", re.IGNORECASE)
_EVENT_ID_RE = re.compile(r"/CourtDocket\.aspx/Cases/(\d+)", re.IGNORECASE)
_SHELL_CASE_ID_RE = re.compile(r"\bvar\s+cid\s*=\s*(\d+)", re.IGNORECASE)
_SHELL_DIGEST_RE = re.compile(
    r"\bvar\s+caseDigest\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
_SHELL_CASE_NUMBER_RE = re.compile(
    r"\bvar\s+caseNumber\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
_CHALLENGE_MARKERS = (
    "enable javascript and cookies to continue",
    "checking your browser before accessing",
)


@dataclass(frozen=True)
class Artifact:
    """One bounded source response."""

    content: bytes
    source_url: str
    status_code: int
    media_type: str | None
    headers: Mapping[str, str]

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True)
class BenchmarkSearchForm:
    """Verified search-form state for one fresh Benchmark session."""

    action_url: str
    hidden_fields: Mapping[str, str]
    native_search_modes: tuple[str, ...]
    platform_version: str | None
    source_url: str
    source_document_sha256: str


@dataclass(frozen=True)
class BenchmarkCaseLocator:
    """Session-local case locator retained only inside the client."""

    case_id: str
    digest: str
    case_number: str
    detail_url: str
    caption: str | None = None


@dataclass(frozen=True)
class BenchmarkSearchHit:
    """One raw result row plus its session-local detail route."""

    record: Mapping[str, Any]
    locator: BenchmarkCaseLocator


@dataclass(frozen=True)
class BenchmarkSearchPage:
    """One server-side result page."""

    hits: tuple[BenchmarkSearchHit, ...]
    source_row_count: int
    total_reported: int
    offset: int
    too_broad: bool
    source_document_sha256: str


@dataclass(frozen=True)
class DocketLocator:
    """Session-local docket locator."""

    docket_id: str
    digest: str | None
    source_access_state: str


@dataclass(frozen=True)
class BenchmarkCaseBundle:
    """Normalized case plus its session-local docket locators."""

    record: Mapping[str, Any]
    docket_locators: Mapping[str, DocketLocator]
    source_document_sha256: str


class OsceolaCourtError(RuntimeError):
    """Transport, access, schema, or selection failure."""

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
    result = re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip()
    return result or None


def _attribute(node: Tag, name: str) -> str | None:
    value = node.get(name)
    if value is None:
        value = node.get(name.casefold())
    if isinstance(value, (list, tuple)):
        value = value[0] if len(value) == 1 else " ".join(map(str, value))
    return _clean(value)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _case_number(value: Any) -> str | None:
    normalized = _clean(value)
    return normalized.upper() if normalized else None


def _date(value: Any) -> str | None:
    normalized = _clean(value)
    if normalized is None:
        return None
    for date_format in (
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y-%m-%d",
    ):
        try:
            parsed = datetime.strptime(normalized, date_format)
        except ValueError:
            continue
        if "%H" in date_format or "%I" in date_format:
            return parsed.isoformat(timespec="minutes")
        return parsed.date().isoformat()
    return None


def _media_type(response: Any) -> str | None:
    headers = getattr(response, "headers", {})
    value = headers.get("Content-Type", headers.get("content-type"))
    if not value:
        return None
    return str(value).split(";", 1)[0].strip().casefold()


def _header_map(response: Any) -> dict[str, str]:
    return {
        str(key).casefold(): str(value)
        for key, value in getattr(response, "headers", {}).items()
    }


def _retry_after(response: Any) -> float | None:
    value = _header_map(response).get("retry-after")
    try:
        return max(0.0, float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _court_kind(
    case_number: str,
    *,
    court_type: str | None = None,
) -> str:
    label = (court_type or "").casefold()
    if any(
        token in label
        for token in (
            "circuit",
            "felony",
            "domestic",
            "probate",
            "guardianship",
            "juvenile",
        )
    ):
        return "circuit"
    if any(
        token in label
        for token in (
            "county",
            "misdemeanor",
            "traffic",
            "small claim",
        )
    ):
        return "county"
    match = re.match(r"^\d{4}\s+([A-Z]{2})(?:\s|$)", case_number.upper())
    code = match.group(1) if match else None
    if code in _CIRCUIT_CASE_CODES:
        return "circuit"
    if code in _COUNTY_CASE_CODES:
        return "county"
    return "generic"


def _court_payload(
    case_number: str,
    *,
    court_type: str | None = None,
) -> dict[str, Any]:
    kind = _court_kind(case_number, court_type=court_type)
    if kind == "circuit":
        court_id = "fl-09-osceola-circuit"
        name = "Osceola Circuit Court, Ninth Judicial Circuit"
        level = "circuit"
    elif kind == "county":
        court_id = "fl-09-osceola-county"
        name = "Osceola County Court, Ninth Judicial Circuit"
        level = "county"
    else:
        court_id = "fl-09-osceola"
        name = "Osceola Courts, Ninth Judicial Circuit"
        level = None
    return {
        "court_id": court_id,
        "native_court_id": court_type or kind,
        "name": name,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "court_level": level,
        "division": court_type,
        "judicial_circuit": JUDICIAL_CIRCUIT,
        "official_url": SEARCH_LANDING_URL,
    }


def _case_ref(
    case_number: str,
    *,
    case_id: str | None = None,
    court_type: str | None = None,
    record_kind: str = "case",
    native_id: str | None = None,
) -> str:
    court = _court_payload(case_number, court_type=court_type)
    identity = native_id if native_id is not None else case_id
    return canonical_court_ref(
        PORTAL_SOURCE_ID,
        str(court["court_id"]),
        case_number,
        record_kind=record_kind,
        native_id=identity,
    )


def _assert_portal_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "courts.osceolaclerk.com":
        raise OsceolaCourtError(
            "unexpected_source_url",
            "Osceola court response left the official Clerk portal",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"url": url},
        )
    return url


def _html_soup(
    artifact: Artifact,
    *,
    marker: str | None = None,
) -> BeautifulSoup:
    if artifact.media_type and "html" not in artifact.media_type:
        raise OsceolaCourtError(
            "unexpected_media_type",
            "Osceola Benchmark route did not return HTML",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={
                "url": artifact.source_url,
                "media_type": artifact.media_type,
            },
        )
    soup = BeautifulSoup(artifact.content, "html.parser")
    text = _clean(soup.get_text(" ", strip=True)) or ""
    folded = text.casefold()
    title = _clean(soup.title.get_text(" ", strip=True) if soup.title else "")
    if (title or "").casefold() == "just a moment..." or any(
        value in folded for value in _CHALLENGE_MARKERS
    ):
        raise OsceolaCourtError(
            "human_verification",
            "The official source returned a browser verification page",
            status=ResultStatus.HUMAN_REQUIRED,
            category="access",
            details={"url": artifact.source_url},
        )
    if marker and marker.casefold() not in folded:
        raise OsceolaCourtError(
            "source_marker_missing",
            f"Osceola Benchmark page lacks expected marker {marker!r}",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"url": artifact.source_url, "marker": marker},
        )
    return soup


def parse_search_form(artifact: Artifact) -> BenchmarkSearchForm:
    """Parse the verified anti-forgery form and configured search modes."""

    soup = _html_soup(artifact, marker="Case Search")
    form = soup.select_one("form.searchform")
    if form is None:
        raise OsceolaCourtError(
            "search_form_missing",
            "Osceola Benchmark search form is missing",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    hidden_fields = {
        str(node.get("name")): str(node.get("value") or "")
        for node in form.select('input[type="hidden"][name]')
    }
    token = hidden_fields.get("__RequestVerificationToken")
    if not token:
        raise OsceolaCourtError(
            "verification_token_missing",
            "Osceola Benchmark anti-forgery token is missing",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    modes = tuple(
        dict.fromkeys(
            str(node.get("searchtype"))
            for node in soup.select("input.radioButton[searchtype]")
            if node.get("searchtype")
        )
    )
    if set(modes) != set(NATIVE_SEARCH_MODES):
        raise OsceolaCourtError(
            "search_modes_changed",
            "Osceola Benchmark search-mode set changed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={
                "expected": sorted(NATIVE_SEARCH_MODES),
                "observed": sorted(modes),
            },
        )
    version_match = _PLATFORM_VERSION_RE.search(artifact.text)
    return BenchmarkSearchForm(
        action_url=CASE_SEARCH_URL,
        hidden_fields=hidden_fields,
        native_search_modes=modes,
        platform_version=(version_match.group(1) if version_match else None),
        source_url=artifact.source_url,
        source_document_sha256=artifact.sha256,
    )


def _case_locator_from_url(
    url: str,
    *,
    case_number: str,
    caption: str | None = None,
) -> BenchmarkCaseLocator:
    absolute = _assert_portal_url(url)
    parsed = urlsplit(absolute)
    match = _CASE_ID_RE.search(parsed.path)
    digest = parse_qs(parsed.query).get("digest", [None])[0]
    if match is None or not digest:
        raise OsceolaCourtError(
            "case_locator_changed",
            "Osceola Benchmark detail route lacks its case ID or digest",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"url": absolute},
        )
    return BenchmarkCaseLocator(
        case_id=match.group(1),
        digest=digest,
        case_number=case_number,
        detail_url=absolute,
        caption=caption,
    )


def parse_case_shell(artifact: Artifact) -> BenchmarkCaseLocator:
    """Parse one signed detail shell into its internal session locator."""

    soup = _html_soup(artifact)
    case_id_match = _SHELL_CASE_ID_RE.search(artifact.text)
    digest_match = _SHELL_DIGEST_RE.search(artifact.text)
    number_match = _SHELL_CASE_NUMBER_RE.search(artifact.text)
    if not case_id_match or not digest_match or not number_match:
        raise OsceolaCourtError(
            "case_shell_changed",
            "Osceola Benchmark case shell lacks its locator variables",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"url": artifact.source_url},
        )
    number = _case_number(number_match.group(1))
    if not number:
        raise OsceolaCourtError(
            "case_number_missing",
            "Osceola Benchmark case shell lacks a case number",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    header = soup.select_one(".headerTitle")
    header_text = _clean(header.get_text(" ", strip=True) if header else None)
    caption = None
    if header_text and " - " in header_text:
        caption = _clean(header_text.split(" - ", 1)[1])
    return BenchmarkCaseLocator(
        case_id=case_id_match.group(1),
        digest=digest_match.group(1),
        case_number=number,
        detail_url=artifact.source_url,
        caption=caption,
    )


def parse_search_results_page(
    artifact: Artifact,
) -> tuple[list[str], int, bool]:
    """Parse result headers, reported total, and the broad-query marker."""

    soup = _html_soup(artifact, marker="Case Search Results")
    found = soup.select_one(".caseFoundFilter")
    found_text = _clean(found.get_text(" ", strip=True) if found else None)
    match = re.search(r"Cases Found\s+([\d,]+)", found_text or "", re.I)
    if match is None:
        raise OsceolaCourtError(
            "result_count_missing",
            "Osceola Benchmark result page lacks its reported count",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    total = int(match.group(1).replace(",", ""))
    table = soup.select_one("#gridSearchResults")
    if table is None:
        if total == 0:
            return [], 0, False
        raise OsceolaCourtError(
            "result_table_missing",
            "Osceola Benchmark reported results without a result table",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"total_reported": total},
        )
    headers = [
        _clean(node.get_text(" ", strip=True)) or f"Column {index}"
        for index, node in enumerate(table.select("thead th"))
    ]
    required = {"Case Number", "Status"}
    if not required <= set(headers):
        raise OsceolaCourtError(
            "result_columns_changed",
            "Osceola Benchmark result columns changed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"headers": headers},
        )
    page_text = _clean(soup.get_text(" ", strip=True)) or ""
    too_broad = "search may be too broad" in page_text.casefold()
    return headers, total, too_broad


def _cell_soup(value: Any) -> BeautifulSoup:
    return BeautifulSoup(str(value or ""), "html.parser")


def _cell_text(value: Any) -> str | None:
    return _clean(_cell_soup(value).get_text(" ", strip=True))


def _parse_search_hit(
    raw: Mapping[str, Any],
    headers: Sequence[str],
) -> BenchmarkSearchHit:
    cells = {
        header: raw.get(str(index), raw.get(index))
        for index, header in enumerate(headers)
    }
    case_cell = _cell_soup(cells.get("Case Number"))
    case_anchor = case_cell.select_one('a[href*="CourtCase.aspx/Details/"]')
    case_number = _case_number(
        case_anchor.get_text(" ", strip=True) if case_anchor else None
    )
    summary_cell = _cell_soup(cells.get("Summary"))
    detail_anchor = summary_cell.select_one('a[href*="CourtCase.aspx/Details/"]')
    if detail_anchor is None:
        detail_anchor = case_anchor
    if not case_number or detail_anchor is None:
        raise OsceolaCourtError(
            "result_row_changed",
            "Osceola Benchmark result row lacks case identity",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"headers": list(headers)},
        )
    detail_url = urljoin(RESULT_DATA_URL, str(detail_anchor.get("href")))
    locator = _case_locator_from_url(
        detail_url,
        case_number=case_number,
    )

    name_soup = _cell_soup(cells.get("Name"))
    name_anchor = name_soup.select_one("a")
    name = _clean(name_anchor.get_text(" ", strip=True) if name_anchor else None)
    name_text = _clean(name_soup.get_text(" ", strip=True)) or ""
    birth_match = re.search(r"\((\d{4})\)", name_text)
    alias = "(alias)" in name_text.casefold()
    party_id = None
    if name_anchor and name_anchor.get("href"):
        party_match = _PARTY_ID_RE.search(str(name_anchor["href"]))
        party_id = party_match.group(1) if party_match else None
    status = _cell_text(cells.get("Status"))
    party_type = _cell_text(cells.get("Party Type"))
    citation = _cell_text(cells.get("Citation #"))
    arresting = _cell_text(
        cells.get("Arresting Case Number") or cells.get("Agency Case Number")
    )
    court = _court_payload(case_number)
    record = {
        "canonical_ref": _case_ref(
            case_number,
            case_id=locator.case_id,
        ),
        "source_id": PORTAL_SOURCE_ID,
        "record_kind": "case_search_hit",
        "court": court,
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "source_internal_id": locator.case_id,
        "status": status,
        "citation_number": citation,
        "arresting_case_number": arresting,
        "search_matches": [
            {
                "matched_party_name": name,
                "native_party_id": party_id,
                "party_type": party_type,
                "birth_year": (int(birth_match.group(1)) if birth_match else None),
                "alias": alias,
            }
        ],
        "source_result_row_count": 1,
        "detail_available": True,
        "source_url": SEARCH_LANDING_URL,
        "projection": {"projectable_as_case_record": True},
    }
    return BenchmarkSearchHit(record=record, locator=locator)


def parse_search_rows(
    payload: Mapping[str, Any],
    headers: Sequence[str],
) -> tuple[tuple[BenchmarkSearchHit, ...], int]:
    """Normalize one DataTables response without retaining signed digests."""

    raw_rows = payload.get("data")
    if not isinstance(raw_rows, list):
        raise OsceolaCourtError(
            "result_payload_changed",
            "Osceola Benchmark result payload lacks a data list",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    hits = []
    for row in raw_rows:
        if not isinstance(row, Mapping):
            raise OsceolaCourtError(
                "result_payload_changed",
                "Osceola Benchmark result row is not an object",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
            )
        hits.append(_parse_search_hit(row, headers))
    return tuple(hits), len(raw_rows)


def merge_search_hits(
    hits: Sequence[BenchmarkSearchHit],
) -> list[dict[str, Any]]:
    """Merge alias/party rows that identify the same case on one page."""

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for hit in hits:
        key = (hit.locator.case_id, hit.locator.case_number)
        existing = merged.get(key)
        if existing is None:
            merged[key] = dict(hit.record)
            continue
        matches = list(existing["search_matches"])
        for match in hit.record["search_matches"]:
            if match not in matches:
                matches.append(dict(match))
        existing["search_matches"] = matches
        existing["source_result_row_count"] = int(
            existing["source_result_row_count"]
        ) + int(hit.record["source_result_row_count"])
        for field in ("status", "citation_number", "arresting_case_number"):
            if existing.get(field) is None and hit.record.get(field) is not None:
                existing[field] = hit.record[field]
    return list(merged.values())


def _summary_fields(soup: BeautifulSoup) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for term in soup.select("#summaryAccordionCollapse dt"):
        value = term.find_next_sibling("dd")
        if value is None:
            continue
        label = _clean(term.get_text(" ", strip=True))
        if not label:
            continue
        key = _slug(label.rstrip(":"))
        checkbox = value.select_one('input[type="checkbox"]')
        if checkbox is not None:
            fields[key] = checkbox.has_attr("checked")
        else:
            fields[key] = _clean(value.get_text(" ", strip=True))
    required = {"case_number", "court_type", "status"}
    if not required <= set(fields):
        raise OsceolaCourtError(
            "case_summary_changed",
            "Osceola Benchmark case summary fields changed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"observed_fields": sorted(fields)},
        )
    return fields


def _table_rows(
    soup: BeautifulSoup,
    selector: str,
) -> list[dict[str, Any]]:
    table = soup.select_one(selector)
    if table is None:
        return []
    headers = [
        _clean(node.get_text(" ", strip=True)) or f"column_{index}"
        for index, node in enumerate(table.select("thead th"))
    ]
    records = []
    for row in table.select("tbody > tr"):
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        if len(cells) == 1 and cells[0].has_attr("colspan"):
            continue
        record = {
            _slug(headers[index]): _clean(cell.get_text(" ", strip=True))
            for index, cell in enumerate(cells)
            if index < len(headers)
        }
        record["_row_id"] = _clean(row.get("id"))
        record["_row"] = row
        records.append(record)
    return records


def _parse_parties(
    soup: BeautifulSoup,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    parties = []
    attorneys: dict[str, dict[str, Any]] = {}
    table = soup.select_one("#gridParties")
    if table is None:
        return parties, []
    for row in table.select("tbody > tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        role = _clean(cells[0].get_text(" ", strip=True))
        party_anchor = cells[1].select_one("a")
        raw_name = _clean(
            party_anchor.get_text(" ", strip=True)
            if party_anchor
            else cells[1].get_text(" ", strip=True)
        )
        party_id = None
        if party_anchor and party_anchor.get("href"):
            match = _PARTY_ID_RE.search(str(party_anchor["href"]))
            party_id = match.group(1) if match else None
        party_attorneys = []
        if len(cells) >= 3:
            for anchor in cells[2].select("a"):
                attorney_name = _clean(anchor.get_text(" ", strip=True))
                href = str(anchor.get("href") or "")
                match = _PARTY_ID_RE.search(href)
                attorney_id = match.group(1) if match else attorney_name
                if not attorney_id or not attorney_name:
                    continue
                label = _clean(cells[2].get_text(" ", strip=True))
                attorney = {
                    "native_attorney_id": attorney_id,
                    "raw_name": attorney_name,
                    "source_role": label,
                }
                attorneys[attorney_id] = attorney
                party_attorneys.append(attorney_id)
        parties.append(
            {
                "native_party_id": party_id,
                "raw_name": raw_name,
                "role": role.casefold() if role else None,
                "source_role": role,
                "attorney_ids": party_attorneys,
            }
        )
    return parties, list(attorneys.values())


def _parse_charges(soup: BeautifulSoup) -> list[dict[str, Any]]:
    charges = []
    for row in _table_rows(soup, "#gridCharges"):
        row_node = row.pop("_row")
        row_id = row.pop("_row_id")
        count = row.get("count")
        charges.append(
            {
                "native_charge_id": (row_id.removeprefix("summ_") if row_id else None),
                "count": int(count) if count and count.isdigit() else count,
                "description": row.get("description"),
                "level": row.get("level"),
                "degree": row.get("degree"),
                "plea": row.get("plea"),
                "disposition": row.get("disposition"),
                "disposition_date": _date(row.get("disposition_date")),
                "disposition_date_raw": row.get("disposition_date"),
                "source_row_id": _clean(row_node.get("id")),
            }
        )
    return charges


def _parse_events(soup: BeautifulSoup) -> list[dict[str, Any]]:
    events = []
    table = soup.select_one("#gridCaseEvents")
    if table is None:
        return events
    for row in table.select("tbody > tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 5:
            continue
        anchor = cells[1].select_one("a")
        event_id = None
        if anchor and anchor.get("href"):
            match = _EVENT_ID_RE.search(str(anchor["href"]))
            event_id = match.group(1) if match else None
        date_raw = _clean(cells[0].get_text(" ", strip=True))
        events.append(
            {
                "native_event_id": event_id,
                "event_date": _date(date_raw),
                "event_date_raw": date_raw,
                "event_type": _clean(cells[1].get_text(" ", strip=True)),
                "judge": _clean(cells[2].get_text(" ", strip=True)),
                "location": _clean(cells[3].get_text(" ", strip=True)),
                "result": _clean(cells[4].get_text(" ", strip=True)),
            }
        )
    return events


def _parse_fees(soup: BeautifulSoup) -> list[dict[str, Any]]:
    table = soup.select_one("#feesAccordion table")
    if table is None:
        return []
    headers = [
        _clean(node.get_text(" ", strip=True)) or f"column_{index}"
        for index, node in enumerate(table.select("thead th"))
    ]
    fees = []
    for row in table.select("tbody > tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != len(headers):
            continue
        fee = {
            _slug(headers[index]): _clean(cell.get_text(" ", strip=True))
            for index, cell in enumerate(cells)
        }
        fees.append(fee)
    return fees


def parse_summary(
    artifact: Artifact,
    locator: BenchmarkCaseLocator,
) -> dict[str, Any]:
    """Normalize the case summary, parties, charges, events, and fees."""

    soup = _html_soup(artifact, marker="Summary")
    fields = _summary_fields(soup)
    case_number = _case_number(fields.get("case_number"))
    if case_number != locator.case_number:
        raise OsceolaCourtError(
            "case_identity_mismatch",
            "Osceola Benchmark summary case number changed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={
                "expected": locator.case_number,
                "observed": case_number,
            },
        )
    court_type = _clean(fields.get("court_type"))
    court = _court_payload(case_number, court_type=court_type)
    parties, attorneys = _parse_parties(soup)
    return {
        "canonical_ref": _case_ref(
            case_number,
            case_id=locator.case_id,
            court_type=court_type,
        ),
        "source_id": PORTAL_SOURCE_ID,
        "record_kind": "case",
        "court": court,
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "source_internal_id": locator.case_id,
        "uniform_case_number": _clean(fields.get("uniform_case_number")),
        "caption": locator.caption,
        "case_type": _clean(fields.get("case_type")),
        "court_type": court_type,
        "status": _clean(fields.get("status")),
        "status_date": _date(fields.get("status_date")),
        "status_date_raw": _clean(fields.get("status_date")),
        "filing_date": _date(fields.get("clerk_file_date")),
        "filing_date_raw": _clean(fields.get("clerk_file_date")),
        "judge": _clean(fields.get("judge")),
        "agency": _clean(fields.get("agency")),
        "agency_report_number": _clean(fields.get("agency_report_number")),
        "custody_location": _clean(fields.get("custody_location")),
        "waive_speedy_trial": fields.get("waive_speedy_trial"),
        "total_fees_due_raw": _clean(fields.get("total_fees_due")),
        "parties": parties,
        "attorneys": attorneys,
        "charges": _parse_charges(soup),
        "case_events": _parse_events(soup),
        "fees": _parse_fees(soup),
        "source_url": SEARCH_LANDING_URL,
        "source_document_sha256": artifact.sha256,
        "projection": {"projectable_as_case_record": True},
    }


def _docket_document_descriptor(
    *,
    case_number: str,
    case_id: str,
    docket_id: str,
    source_access_state: str,
) -> dict[str, Any]:
    if source_access_state == "public_image_metadata":
        access_state = "public"
    elif source_access_state == "view_on_request":
        access_state = "restricted"
    else:
        access_state = "unavailable"
    return {
        "canonical_ref": _case_ref(
            case_number,
            case_id=case_id,
            record_kind="document",
            native_id=docket_id,
        ),
        "native_document_id": docket_id,
        "access_state": access_state,
        "source_access_state": source_access_state,
        "document_metadata_available": (source_access_state == "public_image_metadata"),
        "request_available": source_access_state == "view_on_request",
    }


def parse_dockets(
    artifact: Artifact,
    locator: BenchmarkCaseLocator,
) -> tuple[list[dict[str, Any]], dict[str, DocketLocator]]:
    """Parse stable docket IDs and public/request/no-image states."""

    soup = _html_soup(artifact)
    table = soup.select_one("#gridDockets")
    if table is None:
        raise OsceolaCourtError(
            "docket_table_missing",
            "Osceola Benchmark docket table is missing",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    headers = [
        _clean(node.get_text(" ", strip=True)) or f"column_{index}"
        for index, node in enumerate(table.select("thead th"))
    ]
    date_index = next(
        (index for index, header in enumerate(headers) if header.casefold() == "date"),
        None,
    )
    entry_index = next(
        (index for index, header in enumerate(headers) if header.casefold() == "entry"),
        None,
    )
    if date_index is None or entry_index is None:
        raise OsceolaCourtError(
            "docket_columns_changed",
            "Osceola Benchmark docket columns changed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"headers": headers},
        )

    records = []
    locators: dict[str, DocketLocator] = {}
    for row in table.select("tbody > tr"):
        cells = row.find_all("td", recursive=False)
        if max(date_index, entry_index) >= len(cells):
            continue
        public_anchor = row.select_one("a.casedocketimage[rel]")
        request_button = row.select_one(
            ".submitvor[CaseDocketID], .submitvor[casedocketid]"
        )
        no_image = row.select_one(".casedocketnoimage[rel]")
        docket_id = None
        digest = None
        if public_anchor is not None:
            docket_id = _attribute(public_anchor, "rel")
            digest = _attribute(public_anchor, "digest")
            access_state = "public_image_metadata"
        elif request_button is not None:
            docket_id = _attribute(
                request_button,
                "CaseDocketID",
            )
            access_state = "view_on_request"
        elif no_image is not None:
            docket_id = _attribute(no_image, "rel")
            access_state = "not_available_online"
        else:
            continue
        if not docket_id:
            continue
        date_raw = _clean(cells[date_index].get_text(" ", strip=True))
        entry_text = _clean(cells[entry_index].get_text(" ", strip=True))
        document = _docket_document_descriptor(
            case_number=locator.case_number,
            case_id=locator.case_id,
            docket_id=docket_id,
            source_access_state=access_state,
        )
        record = {
            "canonical_ref": _case_ref(
                locator.case_number,
                case_id=locator.case_id,
                record_kind="docket_entry",
                native_id=docket_id,
            ),
            "source_id": PORTAL_SOURCE_ID,
            "record_kind": "docket_entry",
            "court": _court_payload(locator.case_number),
            "raw_case_number": locator.case_number,
            "source_internal_id": locator.case_id,
            "native_entry_id": docket_id,
            "entry_date": _date(date_raw),
            "entry_date_raw": date_raw,
            "entry_text": entry_text,
            "document_available": access_state == "public_image_metadata",
            "source_document_state": access_state,
            "documents": [document],
            "request_handoff": (
                {
                    "request_route": DOCKET_REQUEST_URL,
                    "request_fields": ["caseDocketID", "email"],
                    "submission_performed": False,
                }
                if access_state == "view_on_request"
                else None
            ),
            "source_url": SEARCH_LANDING_URL,
        }
        records.append(record)
        locators[docket_id] = DocketLocator(
            docket_id=docket_id,
            digest=digest,
            source_access_state=access_state,
        )
    return records, locators


def _history_table(
    soup: BeautifulSoup,
    selector: str,
    *,
    relation_kind: str,
) -> list[dict[str, Any]]:
    table = soup.select_one(selector)
    if table is None:
        return []
    headers = [
        _clean(node.get_text(" ", strip=True)) or f"column_{index}"
        for index, node in enumerate(table.select("thead th"))
    ]
    records = []
    for row in table.select("tbody > tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) == 1 and cells[0].has_attr("colspan"):
            continue
        values = {
            _slug(headers[index]): _clean(cell.get_text(" ", strip=True))
            for index, cell in enumerate(cells)
            if index < len(headers)
        }
        number = _case_number(values.get("case_number"))
        if not number:
            continue
        anchor = cells[0].select_one('a[href*="/Details/"]') if cells else None
        case_id = None
        if anchor and anchor.get("href"):
            match = _CASE_ID_RE.search(str(anchor["href"]))
            case_id = match.group(1) if match else None
        records.append(
            {
                "canonical_ref": _case_ref(number, case_id=case_id),
                "relation_kind": relation_kind,
                "raw_case_number": number,
                "source_internal_id": case_id,
                **{key: value for key, value in values.items() if key != "case_number"},
            }
        )
    return records


def parse_history(artifact: Artifact) -> dict[str, list[dict[str, Any]]]:
    """Parse additional and explicitly related case tables."""

    soup = _html_soup(artifact)
    return {
        "additional_cases": _history_table(
            soup,
            "#gridHistory",
            relation_kind="additional_case_for_party",
        ),
        "related_cases": _history_table(
            soup,
            "#relatedCasesSortableGrid",
            relation_kind="source_related_case",
        ),
    }


def parse_charge_details(artifact: Artifact) -> list[dict[str, Any]]:
    """Preserve the expanded charge overview when the source exposes it."""

    soup = _html_soup(artifact)
    details = []
    for row in _table_rows(soup, "#gridCaseCharges"):
        row.pop("_row", None)
        row.pop("_row_id", None)
        if any(value for value in row.values()):
            details.append(row)
    return details


def parse_document_pages(
    artifact: Artifact,
    *,
    case_number: str,
    case_id: str,
    docket_id: str,
) -> list[dict[str, Any]]:
    """Normalize the source's page descriptors without fetching images."""

    if artifact.media_type and artifact.media_type not in {
        "application/json",
        "json",
        "text/json",
        "text/plain",
    }:
        raise OsceolaCourtError(
            "unexpected_document_metadata_type",
            "Osceola docket page route did not return JSON",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"media_type": artifact.media_type},
        )
    try:
        payload = json.loads(artifact.text)
    except json.JSONDecodeError as error:
        raise OsceolaCourtError(
            "invalid_document_metadata",
            "Osceola docket page route returned invalid JSON",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        ) from error
    if not isinstance(payload, list):
        raise OsceolaCourtError(
            "document_metadata_changed",
            "Osceola docket page metadata is not a list",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    records = []
    for page in payload:
        if not isinstance(page, Mapping) or page.get("DocumentId") is None:
            raise OsceolaCourtError(
                "document_metadata_changed",
                "Osceola docket page metadata lacks DocumentId",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
            )
        document_id = str(page["DocumentId"])
        hidden = bool(page.get("HidePage"))
        redaction = page.get("RedactStatus")
        route = urljoin(
            PORTAL_BASE_URL,
            "Image.aspx/ShowImage?" + urlencode({"did": document_id, "dr": 0}),
        )
        records.append(
            {
                "canonical_ref": _case_ref(
                    case_number,
                    case_id=case_id,
                    record_kind="document_page",
                    native_id=f"{docket_id}:{document_id}",
                ),
                "source_id": PORTAL_SOURCE_ID,
                "record_kind": "document_page_metadata",
                "court": _court_payload(case_number),
                "raw_case_number": case_number,
                "source_internal_id": case_id,
                "native_entry_id": docket_id,
                "native_document_id": document_id,
                "document_extension": _clean(page.get("DocumentExtension")),
                "document_sequence": page.get("DocumentSequence"),
                "page_sequence": page.get("PageSequence"),
                "source_table_id": (
                    str(page["SourceTableID"])
                    if page.get("SourceTableID") is not None
                    else None
                ),
                "hide_page": hidden,
                "redact_status": redaction,
                "access_state": "restricted" if hidden else "public",
                "source_access_state": (
                    "hidden_page" if hidden else "public_image_route"
                ),
                "image_url": route,
                "session_context": "current_portal_session",
                "source_url": artifact.source_url,
                "source_document_sha256": artifact.sha256,
            }
        )
    return records


def _report_records() -> list[dict[str, Any]]:
    return [
        {
            "canonical_ref": "OSCEOLA-COURT-HEARING-CALENDAR:CURRENT",
            "source_id": CALENDAR_SOURCE_ID,
            "record_kind": "rolling_court_hearing_calendar",
            "title": "Osceola County Court Hearing Calendar",
            "artifact_url": CALENDAR_URL,
            "media_type": "application/pdf",
            "coverage": {
                "time_scope": "scheduled hearings for the next two years",
                "past_hearings": False,
                "juvenile_cases_displayed": False,
                "source_update_statement": (
                    "updated every evening after close of business"
                ),
            },
            "stable_identity": ["canonical_ref"],
            "projection": {
                "projectable_as_case_record": False,
                "scope": "forward_hearing_calendar_artifact",
            },
        },
        {
            "canonical_ref": ("OSCEOLA-MORTGAGE-FORECLOSURE-SCHEDULE:CURRENT"),
            "source_id": FORECLOSURE_SOURCE_ID,
            "record_kind": "rolling_mortgage_foreclosure_sale_schedule",
            "title": "Scheduled Mortgage Foreclosure Sales",
            "artifact_url": FORECLOSURE_URL,
            "media_type": "application/pdf",
            "coverage": {
                "time_scope": "forward scheduled mortgage foreclosure sales",
                "source_update_statement": ("refreshes each weekday before 8:00 a.m."),
                "cancellation_reference": "Benchmark case record",
            },
            "stable_identity": ["canonical_ref"],
            "projection": {
                "projectable_as_case_record": False,
                "scope": "forward_foreclosure_schedule_artifact",
            },
        },
    ]


def _report_record(kind: str) -> dict[str, Any]:
    index = 0 if kind == "calendar" else 1
    return dict(_report_records()[index])


def parse_report_artifact(
    artifact: Artifact,
    *,
    kind: str,
) -> dict[str, Any]:
    """Validate and describe one current official report PDF."""

    if artifact.media_type and artifact.media_type not in {
        "application/pdf",
        "application/octet-stream",
    }:
        raise OsceolaCourtError(
            "unexpected_report_media_type",
            "Osceola report route did not return a PDF",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"media_type": artifact.media_type},
        )
    if not artifact.content.startswith(b"%PDF-"):
        raise OsceolaCourtError(
            "invalid_report_pdf",
            "Osceola report artifact lacks a PDF signature",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    record = _report_record(kind)
    record.update(
        {
            "record_kind": record["record_kind"] + "_artifact",
            "artifact_byte_length": len(artifact.content),
            "artifact_sha256": artifact.sha256,
            "artifact_media_type": artifact.media_type or "application/pdf",
            "last_modified": artifact.headers.get("last-modified"),
            "etag": artifact.headers.get("etag"),
            "source_url": artifact.source_url,
            "source_document_sha256": artifact.sha256,
        }
    )
    return record


def _request_handoff_record(
    *,
    case_number: str | None,
    docket_id: str | None,
) -> dict[str, Any]:
    return {
        "canonical_ref": ("OSCEOLA-COURT-RECORDS-ACQUISITION-HANDOFF:12097"),
        "source_id": PORTAL_SOURCE_ID,
        "record_kind": "court_record_acquisition_handoff",
        "case_number": _case_number(case_number),
        "native_entry_id": docket_id,
        "routes": [
            {
                "route_kind": "in_portal_view_on_request",
                "request_url": DOCKET_REQUEST_URL,
                "method": "POST",
                "request_fields": ["caseDocketID", "email"],
                "requires_current_case_session": True,
                "submission_performed": False,
            },
            {
                "route_kind": "older_or_not_online_public_record_request",
                "information_url": PUBLIC_RECORDS_URL,
                "request_url": JUSTFOIA_URL,
                "coverage": [
                    "older court cases",
                    "court records not available online",
                    "administrative records",
                ],
                "submission_performed": False,
            },
            {
                "route_kind": "electronic_certified_copy",
                "request_url": ECERTIFIED_URL,
                "publisher_code": COUNTY_GEOID,
                "submission_performed": False,
            },
            {
                "route_kind": "registered_and_bulk_data",
                "information_url": REGISTRATION_URL,
                "coverage": [
                    "registered electronic court-record access",
                    "bulk data purchases for specific court types",
                ],
                "submission_performed": False,
            },
        ],
        "submission_performed": False,
        "source_url": PUBLIC_RECORDS_URL,
        "projection": {
            "projectable_as_case_record": False,
            "scope": "verified_acquisition_routes",
        },
    }


class PioneerBenchmarkClient:
    """Reusable session client for the verified Pioneer Benchmark 2.x shape."""

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
        self.request_count = 0
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.sleeper = sleeper

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, Any] | None = None,
        allow_redirects: bool = True,
        maximum_bytes: int = MAXIMUM_HTML_BYTES,
        accept: str = "text/html,application/xhtml+xml",
    ) -> Artifact:
        _assert_portal_url(url)
        headers = {
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": SEARCH_LANDING_URL,
            "User-Agent": DEFAULT_USER_AGENT,
        }
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    data=data,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=allow_redirects,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise OsceolaCourtError(
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
                self.sleeper(self.retry_policy.delay(attempt, _retry_after(response)))
                continue
            if status_code == 429:
                raise OsceolaCourtError(
                    "rate_limited",
                    "Osceola Benchmark rate limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="rate_limit",
                    retryable=True,
                    details={"url": url, "status_code": status_code},
                )
            if status_code in {401, 403}:
                raise OsceolaCourtError(
                    "access_restricted",
                    f"Osceola Benchmark returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"url": url, "status_code": status_code},
                )
            redirect_ok = not allow_redirects and status_code in {
                301,
                302,
                303,
                307,
                308,
            }
            if not redirect_ok and not 200 <= status_code < 300:
                raise OsceolaCourtError(
                    "http_status",
                    f"Osceola Benchmark returned HTTP {status_code}",
                    category="http",
                    retryable=status_code >= 500,
                    details={"url": url, "status_code": status_code},
                )
            content = bytes(getattr(response, "content", b""))
            if not content and getattr(response, "text", None):
                content = str(response.text).encode()
            if len(content) > maximum_bytes:
                raise OsceolaCourtError(
                    "response_too_large",
                    "Osceola Benchmark response exceeds the configured bound",
                    category="response_size",
                    details={
                        "url": url,
                        "byte_length": len(content),
                        "maximum_bytes": maximum_bytes,
                    },
                )
            response_url = str(getattr(response, "url", None) or url)
            _assert_portal_url(response_url)
            return Artifact(
                content=content,
                source_url=response_url,
                status_code=status_code,
                media_type=_media_type(response),
                headers=_header_map(response),
            )
        raise OsceolaCourtError(
            "transport_error",
            str(last_error or "request failed"),
            category="transport",
            retryable=True,
            details={"url": url},
        )

    def bootstrap(self) -> BenchmarkSearchForm:
        return parse_search_form(self._request("GET", SEARCH_LANDING_URL))

    def _start_search(
        self,
        query: str,
        native_mode: str,
    ) -> tuple[BenchmarkSearchForm, Artifact]:
        form = self.bootstrap()
        if native_mode not in form.native_search_modes:
            raise OsceolaCourtError(
                "unsupported_search_mode",
                f"Osceola Benchmark does not expose {native_mode}",
                category="query_selection",
                details={"available": list(form.native_search_modes)},
            )
        payload = dict(form.hidden_fields)
        payload.update(
            {
                "type": native_mode,
                "search": query,
                "openedFrom": "",
                "openedTo": "",
                "closedFrom": "",
                "closedTo": "",
            }
        )
        artifact = self._request(
            "POST",
            form.action_url,
            data=payload,
            allow_redirects=False,
        )
        return form, artifact

    def search(
        self,
        query: str,
        *,
        native_mode: str,
        offset: int,
        limit: int,
    ) -> BenchmarkSearchPage:
        form, initial = self._start_search(query, native_mode)
        if initial.status_code in {301, 302, 303, 307, 308}:
            location = initial.headers.get("location")
            if not location:
                raise OsceolaCourtError(
                    "case_redirect_changed",
                    "Osceola Benchmark case redirect lacks Location",
                    status=ResultStatus.SOURCE_CHANGED,
                    category="source_schema",
                )
            detail_url = urljoin(initial.source_url, location)
            detail = self._request("GET", detail_url)
            locator = parse_case_shell(detail)
            hit = BenchmarkSearchHit(
                record={
                    "canonical_ref": _case_ref(
                        locator.case_number,
                        case_id=locator.case_id,
                    ),
                    "source_id": PORTAL_SOURCE_ID,
                    "record_kind": "case_search_hit",
                    "court": _court_payload(locator.case_number),
                    "raw_case_number": locator.case_number,
                    "display_case_number": locator.case_number,
                    "source_internal_id": locator.case_id,
                    "caption": locator.caption,
                    "search_matches": [],
                    "source_result_row_count": 1,
                    "detail_available": True,
                    "source_url": SEARCH_LANDING_URL,
                    "projection": {"projectable_as_case_record": True},
                },
                locator=locator,
            )
            return BenchmarkSearchPage(
                hits=(hit,) if offset == 0 else (),
                source_row_count=1 if offset == 0 else 0,
                total_reported=1,
                offset=offset,
                too_broad=False,
                source_document_sha256=detail.sha256,
            )

        headers, total, too_broad = parse_search_results_page(initial)
        if total == 0:
            return BenchmarkSearchPage(
                hits=(),
                source_row_count=0,
                total_reported=0,
                offset=offset,
                too_broad=False,
                source_document_sha256=initial.sha256,
            )
        case_column = headers.index("Case Number")
        data: dict[str, Any] = {
            "draw": "1",
            "start": str(offset),
            "length": str(limit),
            "search[value]": "",
            "search[regex]": "false",
            "order[0][column]": str(case_column),
            "order[0][dir]": "desc",
        }
        for index in range(len(headers)):
            prefix = f"columns[{index}]"
            data.update(
                {
                    f"{prefix}[data]": str(index),
                    f"{prefix}[name]": "",
                    f"{prefix}[searchable]": "true",
                    f"{prefix}[orderable]": "true",
                    f"{prefix}[search][value]": "",
                    f"{prefix}[search][regex]": "false",
                }
            )
        payload_artifact = self._request(
            "POST",
            RESULT_DATA_URL,
            data=data,
            maximum_bytes=MAXIMUM_JSON_BYTES,
            accept="application/json,text/javascript,*/*;q=0.1",
        )
        try:
            payload = json.loads(payload_artifact.text)
        except json.JSONDecodeError as error:
            raise OsceolaCourtError(
                "invalid_result_json",
                "Osceola Benchmark result endpoint returned invalid JSON",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
            ) from error
        if not isinstance(payload, Mapping):
            raise OsceolaCourtError(
                "result_payload_changed",
                "Osceola Benchmark result payload is not an object",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
            )
        hits, row_count = parse_search_rows(payload, headers)
        filtered = payload.get("recordsFiltered", payload.get("recordsTotal"))
        try:
            payload_total = int(filtered)
        except (TypeError, ValueError):
            payload_total = total
        return BenchmarkSearchPage(
            hits=hits,
            source_row_count=row_count,
            total_reported=payload_total,
            offset=offset,
            too_broad=too_broad,
            source_document_sha256=payload_artifact.sha256,
        )

    def _detail_locator(self, case_number: str) -> BenchmarkCaseLocator:
        page = self.search(
            case_number,
            native_mode="CaseNumber",
            offset=0,
            limit=50,
        )
        expected = _case_number(case_number)
        matches = [
            hit.locator for hit in page.hits if hit.locator.case_number == expected
        ]
        if not matches:
            raise OsceolaCourtError(
                "case_not_found",
                f"Osceola County case not found: {case_number}",
                status=ResultStatus.NO_RESULTS,
                category="not_found",
                details={"case_number": case_number},
            )
        return matches[0]

    def fetch_case(self, case_number: str) -> BenchmarkCaseBundle:
        locator = self._detail_locator(case_number)
        encoded = quote(locator.digest, safe="")
        base = PORTAL_BASE_URL
        summary = self._request(
            "GET",
            urljoin(
                base,
                f"CourtCase.aspx/DetailsSummary/{locator.case_id}?digest={encoded}",
            ),
        )
        dockets = self._request(
            "GET",
            urljoin(
                base,
                f"CourtCase.aspx/CaseDockets/{locator.case_id}?digest={encoded}",
            ),
        )
        history = self._request(
            "GET",
            urljoin(
                base,
                f"CourtCase.aspx/DetailsHistory/{locator.case_id}?digest={encoded}",
            ),
        )
        charge_details = self._request(
            "GET",
            urljoin(
                base,
                f"CourtCase.aspx/DetailsCharges/{locator.case_id}?digest={encoded}",
            ),
        )
        record = parse_summary(summary, locator)
        docket_records, docket_locators = parse_dockets(dockets, locator)
        record["docket_entries"] = docket_records
        record.update(parse_history(history))
        record["charge_details"] = parse_charge_details(charge_details)
        record["source_bundle_sha256"] = sha256_fingerprint(
            {
                "summary": summary.sha256,
                "dockets": dockets.sha256,
                "history": history.sha256,
                "charge_details": charge_details.sha256,
            }
        )
        return BenchmarkCaseBundle(
            record=record,
            docket_locators=docket_locators,
            source_document_sha256=str(record["source_bundle_sha256"]),
        )

    def document_metadata(
        self,
        case_number: str,
        docket_id: str,
    ) -> list[dict[str, Any]]:
        bundle = self.fetch_case(case_number)
        return self.document_metadata_from_bundle(bundle, docket_id)

    def document_metadata_from_bundle(
        self,
        bundle: BenchmarkCaseBundle,
        docket_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch page metadata using an already hydrated case bundle."""

        locator = bundle.docket_locators.get(str(docket_id))
        if locator is None:
            raise OsceolaCourtError(
                "docket_not_found",
                (
                    f"Docket entry {docket_id} was not found on "
                    f"{bundle.record.get('raw_case_number')}"
                ),
                status=ResultStatus.NO_RESULTS,
                category="not_found",
                details={
                    "case_number": bundle.record.get("raw_case_number"),
                    "docket_id": str(docket_id),
                },
            )
        if locator.source_access_state != "public_image_metadata":
            raise OsceolaCourtError(
                "document_metadata_unavailable",
                (
                    f"Docket entry {docket_id} has source state "
                    f"{locator.source_access_state}"
                ),
                status=ResultStatus.RESTRICTED,
                category="access",
                details={
                    "case_number": bundle.record.get("raw_case_number"),
                    "docket_id": str(docket_id),
                    "source_access_state": locator.source_access_state,
                },
            )
        pages_url = urljoin(
            PORTAL_BASE_URL,
            "CaseDocket.aspx/Pages?" + urlencode({"did": docket_id}),
        )
        artifact = self._request(
            "GET",
            pages_url,
            maximum_bytes=MAXIMUM_JSON_BYTES,
            accept="application/json,text/javascript,*/*;q=0.1",
        )
        case_id = str(bundle.record["source_internal_id"])
        return parse_document_pages(
            artifact,
            case_number=str(bundle.record["raw_case_number"]),
            case_id=case_id,
            docket_id=str(docket_id),
        )

    def report(self, kind: str) -> Artifact:
        url = CALENDAR_URL if kind == "calendar" else FORECLOSURE_URL
        return self._request(
            "GET",
            url,
            maximum_bytes=MAXIMUM_PDF_BYTES,
            accept="application/pdf,application/octet-stream",
        )

    def report_head(self, kind: str) -> Artifact:
        url = CALENDAR_URL if kind == "calendar" else FORECLOSURE_URL
        return self._request(
            "HEAD",
            url,
            maximum_bytes=0,
            accept="application/pdf,application/octet-stream",
        )


def _source_records() -> list[dict[str, Any]]:
    return [
        {
            "source_id": PORTAL_SOURCE_ID,
            "record_kind": "source_description",
            "name": PORTAL_SOURCE.name,
            "official_url": SEARCH_LANDING_URL,
            "operations": [
                "search",
                "case",
                "docket",
                "document-metadata",
                "request-handoff",
                "probe",
            ],
            "platform_family": PLATFORM_FAMILY,
        },
        {
            "source_id": CALENDAR_SOURCE_ID,
            "record_kind": "source_description",
            "name": CALENDAR_SOURCE.name,
            "official_url": CALENDAR_URL,
            "operations": ["reports", "report", "probe"],
        },
        {
            "source_id": FORECLOSURE_SOURCE_ID,
            "record_kind": "source_description",
            "name": FORECLOSURE_SOURCE.name,
            "official_url": FORECLOSURE_URL,
            "operations": ["reports", "report", "probe"],
        },
    ]


def _manifest_record(source_id: str) -> dict[str, Any]:
    if source_id == PORTAL_SOURCE_ID:
        return {
            "source_id": source_id,
            "record_kind": "source_manifest",
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "platform_family": PLATFORM_FAMILY,
            "operations": [
                "search",
                "case",
                "docket",
                "document-metadata",
                "request-handoff",
                "probe",
            ],
            "search_modes": list(SEARCH_MODE_TO_NATIVE),
            "coverage": {
                "case_index": True,
                "parties_and_attorneys": True,
                "charges": True,
                "hearings_and_events": True,
                "docket_entries": True,
                "document_page_metadata": True,
                "in_portal_view_on_request": True,
                "registered_and_bulk_route": True,
            },
            "stable_identity": [
                "canonical_ref",
                "source_internal_id",
                "raw_case_number",
            ],
            "session_locator_fields_persisted": [],
            "complementary_source_ids": [
                CALENDAR_SOURCE_ID,
                FORECLOSURE_SOURCE_ID,
                "us-fl-ninth-circuit-appellate-opinions-archive",
            ],
        }
    if source_id == CALENDAR_SOURCE_ID:
        return {
            "source_id": source_id,
            "record_kind": "source_manifest",
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "operations": ["reports", "report", "probe"],
            "coverage": _report_records()[0]["coverage"],
            "stable_identity": ["canonical_ref"],
            "complementary_source_ids": [PORTAL_SOURCE_ID],
        }
    if source_id == FORECLOSURE_SOURCE_ID:
        return {
            "source_id": source_id,
            "record_kind": "source_manifest",
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "operations": ["reports", "report", "probe"],
            "coverage": _report_records()[1]["coverage"],
            "stable_identity": ["canonical_ref"],
            "complementary_source_ids": [PORTAL_SOURCE_ID],
        }
    raise ValueError(f"unknown Osceola court source {source_id}")


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    ignored = {
        "command",
        "output",
        "json_out",
        "quiet",
        "timeout",
        "minimum_interval",
        "max_attempts",
        "artifact_output",
    }
    return {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
        if key not in ignored and value is not None
    }


def _source_for_args(args: argparse.Namespace) -> SourceMetadata:
    if args.command == "report":
        return CALENDAR_SOURCE if args.kind == "calendar" else FORECLOSURE_SOURCE
    source_id = getattr(args, "source", None) or PORTAL_SOURCE_ID
    return SOURCE_BY_ID[source_id]


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=_source_for_args(args),
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _encode_cursor(
    *,
    query: str,
    native_mode: str,
    offset: int,
) -> str:
    token = canonical_json(
        {
            "query_sha256": sha256_fingerprint(
                {"query": query, "native_mode": native_mode}
            ),
            "offset": offset,
        }
    ).encode()
    return CURSOR_PREFIX + base64.urlsafe_b64encode(token).decode().rstrip("=")


def _decode_cursor(
    cursor: str | None,
    *,
    query: str,
    native_mode: str,
) -> int:
    if cursor is None:
        return 0
    if not cursor.startswith(CURSOR_PREFIX):
        raise OsceolaCourtError(
            "invalid_cursor",
            "Osceola Benchmark cursor prefix is invalid",
            category="query_selection",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OsceolaCourtError(
            "invalid_cursor",
            "Osceola Benchmark cursor is malformed",
            category="query_selection",
        ) from error
    expected = sha256_fingerprint({"query": query, "native_mode": native_mode})
    if not isinstance(payload, Mapping) or payload.get("query_sha256") != expected:
        raise OsceolaCourtError(
            "cursor_query_mismatch",
            "Osceola Benchmark cursor belongs to another query",
            category="query_selection",
        )
    offset = payload.get("offset")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 1:
        raise OsceolaCourtError(
            "invalid_cursor",
            "Osceola Benchmark cursor offset is invalid",
            category="query_selection",
        )
    return offset


def _failure(
    query: PublicRecordsQuery,
    error: OsceolaCourtError,
    *,
    warnings: Sequence[str] = PORTAL_WARNINGS,
) -> PublicRecordsResult:
    if error.status == ResultStatus.NO_RESULTS:
        return PublicRecordsResult.success(query, [], warnings=warnings)
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


def _search_result(
    query: PublicRecordsQuery,
    page: BenchmarkSearchPage,
    *,
    raw_query: str,
    native_mode: str,
) -> PublicRecordsResult:
    records = merge_search_hits(page.hits)
    next_offset = page.offset + page.source_row_count
    next_cursor = None
    if page.source_row_count and next_offset < page.total_reported:
        next_cursor = _encode_cursor(
            query=raw_query,
            native_mode=native_mode,
            offset=next_offset,
        )
    if page.too_broad and page.total_reported >= SOURCE_RESULT_CEILING:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [
                PublicRecordsError(
                    code="source_result_ceiling",
                    message=(
                        "Osceola Benchmark reported its 5,000-row "
                        "broad-query ceiling; additional matches may exist"
                    ),
                    category="source_limit",
                    retryable=False,
                    details={
                        "source_total_reported": page.total_reported,
                        "source_result_ceiling": SOURCE_RESULT_CEILING,
                        "source_rows_on_page": page.source_row_count,
                    },
                )
            ],
            records=records,
            next_cursor=next_cursor,
            warnings=PORTAL_WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=next_cursor,
        warnings=PORTAL_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: PioneerBenchmarkClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = build_query(args)
    source_client = client
    network_command = args.command in {
        "search",
        "case",
        "docket",
        "document-metadata",
        "report",
        "probe",
    }
    if network_command and source_client is None:
        source_client = PioneerBenchmarkClient(
            timeout=args.timeout,
            minimum_interval=args.minimum_interval,
            retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        )
    warnings: Sequence[str] = (
        REPORT_WARNINGS
        if query.source.source_id in {CALENDAR_SOURCE_ID, FORECLOSURE_SOURCE_ID}
        else PORTAL_WARNINGS
    )
    try:
        if args.command == "sources":
            result = PublicRecordsResult.success(
                query,
                _source_records(),
                warnings=PORTAL_WARNINGS,
            )
        elif args.command == "manifest":
            result = PublicRecordsResult.success(
                query,
                [_manifest_record(args.source)],
                warnings=warnings,
            )
        elif args.command == "search":
            native_mode = SEARCH_MODE_TO_NATIVE[args.search_mode]
            offset = _decode_cursor(
                args.cursor,
                query=args.query,
                native_mode=native_mode,
            )
            page = source_client.search(
                args.query,
                native_mode=native_mode,
                offset=offset,
                limit=args.limit,
            )
            result = _search_result(
                query,
                page,
                raw_query=args.query,
                native_mode=native_mode,
            )
        elif args.command in {"case", "docket"}:
            bundle = source_client.fetch_case(args.case_number)
            records = (
                [bundle.record]
                if args.command == "case"
                else list(bundle.record["docket_entries"])
            )
            result = PublicRecordsResult.success(
                query,
                records,
                warnings=PORTAL_WARNINGS,
            )
        elif args.command == "document-metadata":
            records = source_client.document_metadata(
                args.case_number,
                args.docket_id,
            )
            result = PublicRecordsResult.success(
                query,
                records,
                warnings=PORTAL_WARNINGS,
            )
        elif args.command == "reports":
            result = PublicRecordsResult.success(
                query,
                _report_records(),
                warnings=REPORT_WARNINGS,
            )
        elif args.command == "report":
            artifact = source_client.report(args.kind)
            record = parse_report_artifact(artifact, kind=args.kind)
            if args.artifact_output:
                output_path = Path(args.artifact_output)
                output_path.write_bytes(artifact.content)
                record["artifact_storage_path"] = str(output_path.resolve())
            result = PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=(
                    [str(Path(args.artifact_output).resolve())]
                    if args.artifact_output
                    else []
                ),
                warnings=REPORT_WARNINGS,
            )
        elif args.command == "request-handoff":
            result = PublicRecordsResult.success(
                query,
                [
                    _request_handoff_record(
                        case_number=args.case_number,
                        docket_id=args.docket_id,
                    )
                ],
                warnings=PORTAL_WARNINGS,
            )
        elif args.command == "probe":
            form = source_client.bootstrap()
            report_heads = {
                kind: source_client.report_head(kind)
                for kind in ("calendar", "foreclosure")
            }
            result = PublicRecordsResult.success(
                query,
                [
                    {
                        "source_id": PORTAL_SOURCE_ID,
                        "record_kind": "source_probe",
                        "status": "ok",
                        "platform_family": PLATFORM_FAMILY,
                        "platform_version": form.platform_version,
                        "search_modes": list(form.native_search_modes),
                        "search_action_url": form.action_url,
                        "verification_token_present": True,
                        "report_routes": {
                            kind: {
                                "source_id": (
                                    CALENDAR_SOURCE_ID
                                    if kind == "calendar"
                                    else FORECLOSURE_SOURCE_ID
                                ),
                                "url": report.source_url,
                                "media_type": report.media_type,
                                "content_length": report.headers.get("content-length"),
                                "last_modified": report.headers.get("last-modified"),
                                "etag": report.headers.get("etag"),
                            }
                            for kind, report in report_heads.items()
                        },
                        "source_document_sha256": (form.source_document_sha256),
                        "stable_schema_sha256": sha256_fingerprint(
                            {
                                "search_modes": list(form.native_search_modes),
                                "search_action": form.action_url,
                                "report_media_types": {
                                    kind: report.media_type
                                    for kind, report in report_heads.items()
                                },
                            }
                        ),
                    }
                ],
                warnings=PORTAL_WARNINGS + REPORT_WARNINGS,
            )
        else:
            raise ValueError(f"unsupported Osceola court command {args.command!r}")
    except OsceolaCourtError as error:
        result = _failure(query, error, warnings=warnings)
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="artifact_write_failed",
                    message=str(error),
                    category="local_artifact",
                    retryable=False,
                )
            ],
            warnings=warnings,
        )
    except (TypeError, ValueError, KeyError) as error:
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
            "Query Osceola County Clerk Benchmark cases, dockets, "
            "document metadata, forward reports, and acquisition handoffs"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="List the Benchmark portal and complementary report sources",
    )
    sources.set_defaults(source=PORTAL_SOURCE_ID)
    _add_runtime(sources)

    manifest = sub.add_parser(
        "manifest",
        help="Describe one Osceola court source contract",
    )
    manifest.add_argument(
        "--source",
        choices=sorted(SOURCE_BY_ID),
        default=PORTAL_SOURCE_ID,
    )
    _add_runtime(manifest)

    search = sub.add_parser(
        "search",
        help="Search the public Benchmark case index",
    )
    search.add_argument("query")
    search.add_argument(
        "--search-mode",
        choices=sorted(SEARCH_MODE_TO_NATIVE),
        default="name",
    )
    search.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    search.add_argument("--cursor")
    search.set_defaults(source=PORTAL_SOURCE_ID)
    _add_runtime(search)

    case = sub.add_parser(
        "case",
        help="Fetch one exact case summary and its related sections",
    )
    case.add_argument("case_number")
    case.set_defaults(source=PORTAL_SOURCE_ID)
    _add_runtime(case)

    docket = sub.add_parser(
        "docket",
        help="List stable docket entries for one exact case",
    )
    docket.add_argument("case_number")
    docket.set_defaults(source=PORTAL_SOURCE_ID)
    _add_runtime(docket)

    document = sub.add_parser(
        "document-metadata",
        help="Fetch public page metadata for one docket entry",
    )
    document.add_argument("case_number")
    document.add_argument("docket_id")
    document.set_defaults(source=PORTAL_SOURCE_ID)
    _add_runtime(document)

    reports = sub.add_parser(
        "reports",
        help="List current hearing-calendar and foreclosure artifacts",
    )
    reports.set_defaults(source=PORTAL_SOURCE_ID)
    _add_runtime(reports)

    report = sub.add_parser(
        "report",
        help="Fetch and validate one current report PDF",
    )
    report.add_argument("kind", choices=("calendar", "foreclosure"))
    report.add_argument(
        "--artifact-output",
        help="Optional path for the validated PDF bytes",
    )
    _add_runtime(report)

    handoff = sub.add_parser(
        "request-handoff",
        help="Describe document, older-case, certified, and bulk routes",
    )
    handoff.add_argument("--case-number")
    handoff.add_argument("--docket-id")
    handoff.set_defaults(source=PORTAL_SOURCE_ID)
    _add_runtime(handoff)

    probe = sub.add_parser(
        "probe",
        help="Probe the search form and report metadata routes",
    )
    probe.set_defaults(source=PORTAL_SOURCE_ID)
    _add_runtime(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(f"Osceola court records {args.command} ({result.status.value})"),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Osceola court records {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    try:
        result = execute(args)
    except ValueError as error:
        parser.error(str(error))
        return
    _emit(result, args)
    if result.status not in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    }:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
