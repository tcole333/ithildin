#!/usr/bin/env python3
"""Query Virginia's General District Court Online Case Information System.

The official application is a cookie-backed, server-rendered system.  Every
query is scoped to one source-published court component and one of the Civil or
Traffic/Criminal divisions.  Name, exact-case-number, hearing-date, and
service/process searches are distinct source operations.

Search-result continuation is session-bound.  This adapter follows native
20-row pages until the source removes its Next control.  A caller limit returns
a replayable cursor containing query identity and a page-boundary check; the
cursor never treats a client-search counter or a transient detail link as a
stable case identifier.

Examples:
    uv run python tools/query_va_general_district.py routes --json
    uv run python tools/query_va_general_district.py courts --json
    uv run python tools/query_va_general_district.py name 013 \
        "ARLINGTON COUNTY" --division civil --status all \
        --limit 50 --output /tmp/va-gdc-name.json
    uv run python tools/query_va_general_district.py hearing 013 2026-07-30 \
        --division traffic-criminal --limit 25 \
        --output /tmp/va-gdc-hearings.json
    uv run python tools/query_va_general_district.py service 013 SMITH \
        --division civil --output /tmp/va-gdc-service.json
    uv run python tools/query_va_general_district.py case 013 GV26004683-00 \
        --division civil --output /tmp/va-gdc-case.json
    uv run python tools/query_va_general_district.py probe --court 013 --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

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
    )
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-va-general-district-court-case-information"
STATE_CODE = "VA"
STATE_GEOID = "51"
BASE_URL = "https://eapps.courts.state.va.us"
APP_BASE_URL = f"{BASE_URL}/gdcourts/"
LANDING_URL = f"{APP_BASE_URL}landing.do?landing=landing"
LANDING_POST_URL = f"{APP_BASE_URL}landing.do"
CHANGE_COURT_URL = f"{APP_BASE_URL}changeCourt.do"
NAME_SEARCH_URL = f"{APP_BASE_URL}nameSearch.do"
CASE_SEARCH_URL = f"{APP_BASE_URL}caseSearch.do"
CASE_NUMBER_SEARCH_URL = f"{APP_BASE_URL}criminalCivilCaseSearch.do"
WELCOME_URL = f"{APP_BASE_URL}welcomePage.do"
HELP_URL = f"{APP_BASE_URL}help.do"

STATEWIDE_OCIS_URL = f"{BASE_URL}/ocis/index.html"
CIRCUIT_CASE_URL = "https://eapps.courts.state.va.us/CJISWeb/circuit.jsp?hl=en-US"
GDC_HOME_URL = "https://vacourts.gov/courts/gd/home"
GDC_DIRECTORY_URL = "https://vacourts.gov/static/directories/dist.pdf"
PUBLIC_RECORDS_REQUEST_URL = "https://vacourts.gov/courtadmin/aoc/lpr/reqpubrec/home"
GDC_MANUAL_URL = (
    "https://www.vacourts.gov/static/courtadmin/aoc/djs/resources/"
    "manuals/gdman/gd_manual.pdf"
)
COURT_OF_APPEALS_URL = "https://vacourts.gov/courts/cav/home"
SUPREME_COURT_URL = "https://vacourts.gov/courts/scv/home"
LAND_RECORDS_URL = "https://risweb.vacourts.gov/jsra/sra/"
VDBC_URL = "https://www.vacourts.gov/online/vdbc/home"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.5
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)
NATIVE_PAGE_SIZE = 20
CURSOR_PREFIX = "va-gdc:v1:"

DIVISION_CODES = {
    "civil": "V",
    "traffic-criminal": "T",
    "traffic_criminal": "T",
    "traffic": "T",
    "criminal": "T",
}
DIVISION_NAMES = {
    "V": "Civil",
    "T": "Traffic/Criminal",
}
STATUS_CODES = {
    "current": "A",
    "archived": "I",
    "all": "O",
}
STATUS_NAMES = {
    "A": "Current",
    "I": "Archived",
    "O": "All",
    "S": "Service/Process source state",
}

HEARING_TYPES = (
    ("", ""),
    ("AA", "Appointment of Attorney"),
    ("AC", "Arraignment by Clerk"),
    ("AH", "Administrative Hearing"),
    ("AJ", "Adjudicatory"),
    ("AR", "Arraignment"),
    ("AV", "Attorney Review"),
    ("CH", "Contested Hearing"),
    ("CV", "Civil Hearing"),
    ("BD", "Bond"),
    ("DP", "Dismissed"),
    ("DS", "Disposition"),
    ("DT", "Detention"),
    ("EX", "Extradition"),
    ("MO", "Motion"),
    ("PP", "Prepayment"),
    ("PR", "Preliminary"),
    ("PT", "Pre Trial"),
    ("RG", "Review Hearing"),
    ("RH", "Re-hearing"),
    ("RO", "Re-open"),
    ("RP", "Review Progress"),
    ("RV", "Revocation"),
    ("ST", "Sentencing"),
    ("TR", "Transfer"),
    ("WV", "Hearing waived"),
)
HEARING_TYPE_LABELS = dict(HEARING_TYPES)

COMPLEMENTARY_SOURCES = (
    {
        "source_id": "us-va-ocis-statewide-search",
        "name": "Virginia Online Case Information System 2.0",
        "url": STATEWIDE_OCIS_URL,
        "adds": (
            "Statewide discovery across General District criminal/traffic "
            "records and selected Circuit Court records."
        ),
        "does_not_replace": (
            "Locality-scoped civil, service/process, judgment, garnishment, "
            "eviction, or payment-related General District metadata."
        ),
        "equivalent": False,
    },
    {
        "source_id": "us-va-general-district-court-directory",
        "name": "Virginia General District Court Directory and Local Pages",
        "url": GDC_DIRECTORY_URL,
        "adds": (
            "District, court address, judges, clerk contacts, hours, local "
            "court pages, schedules, and local practices."
        ),
        "does_not_replace": "Case-level search results or case-detail metadata.",
        "equivalent": False,
    },
    {
        "source_id": "us-va-local-court-clerk-records",
        "name": "Individual General District Court Clerks",
        "url": PUBLIC_RECORDS_REQUEST_URL,
        "adds": (
            "Official or certified case records and copies available under "
            "the responsible clerk's record procedures."
        ),
        "does_not_replace": (
            "Anonymous statewide discovery; availability and copy procedures "
            "are court-specific."
        ),
        "equivalent": False,
    },
    {
        "source_id": "us-va-circuit-court-case-information",
        "name": "Virginia Circuit Court Case Information",
        "url": CIRCUIT_CASE_URL,
        "adds": ("Civil and criminal case metadata for participating Circuit Courts."),
        "does_not_replace": "General District Court coverage.",
        "equivalent": False,
    },
    {
        "source_id": "us-va-appellate-opinions",
        "name": "Virginia Appellate Opinions, Dockets, and Audio",
        "url": COURT_OF_APPEALS_URL,
        "additional_url": SUPREME_COURT_URL,
        "adds": (
            "Published and unpublished appellate dispositions, schedules, "
            "dockets, argued orders, and oral-argument recordings where "
            "published."
        ),
        "does_not_replace": "Trial-court case metadata or clerk files.",
        "equivalent": False,
    },
    {
        "source_id": "us-va-secure-remote-access-land-records",
        "name": "Virginia Secure Remote Access to Land Records",
        "url": LAND_RECORDS_URL,
        "adds": (
            "Participating Circuit Court land-record, deed, judgment, will, "
            "marriage-license, financing-statement, and image access."
        ),
        "does_not_replace": (
            "General District case information; registration, fees, and "
            "coverage are set by participating clerks."
        ),
        "equivalent": False,
    },
    {
        "source_id": "us-va-virginia-date-of-birth-confirmation",
        "name": "Virginia Date of Birth Confirmation",
        "url": VDBC_URL,
        "adds": (
            "Registered organizational confirmation of a consenting "
            "individual's identity against eligible criminal/traffic records."
        ),
        "does_not_replace": "Anonymous case discovery or civil case metadata.",
        "equivalent": False,
    },
)

SOURCE_WARNINGS = (
    "The source states that its information is not the official court record "
    "and may be corrected or updated.",
    "Searches are scoped to one source-published court component; the "
    "three-digit component code is retained as a source identifier rather "
    "than normalized as a geographic FIPS code.",
    "Protective orders, civil commitments, medical emergency custody, and "
    "temporary detention matters are not published in this system; absence "
    "from a result is not evidence that no such proceeding exists.",
    "Service/process and report information appears only when entered by the "
    "individual court.",
    "Name and service/process results are source-returned candidates. A live "
    "service/process query returned a name sharing only the entered prefix, so "
    "the person-served value should be checked before resolving an identity.",
    "This case-information system publishes metadata, not a general filing-"
    "image repository; local clerks and other official systems add distinct "
    "records.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Virginia General District Court Online Case Information System",
    source_role=(
        "state_locality_general_district_civil_traffic_criminal_case_metadata"
    ),
    base_url=LANDING_URL,
    dataset_id="virginia-general-district-court-case-information",
    metadata={
        "authority": (
            "Office of the Executive Secretary of the Supreme Court of Virginia"
        ),
        "state_code": STATE_CODE,
        "authentication": "none",
        "session_model": "terms_acceptance_and_cookie_backed_server_state",
        "court_scope": "one_source_published_court_component_per_query",
        "native_page_size": NATIVE_PAGE_SIZE,
        "native_reported_total": None,
        "divisions": DIVISION_NAMES,
        "query_roles": [
            "name",
            "exact_case_number",
            "hearing_date",
            "service_process_name",
        ],
        "name_search_syntax": {
            "wildcard": "*",
            "minimum_non_wildcard_characters": 2,
            "source_guidance": (
                "Enter the name as it appears on the summons, warrant, or "
                "civil pleading."
            ),
        },
        "data_status_definitions": {
            "A": "Current: cases entered or heard after January 2007",
            "I": "Archived: cases entered or heard before January 2007",
            "O": "All",
        },
        "excluded_case_categories_stated_by_source": [
            "protective_orders",
            "civil_commitments",
            "medical_emergency_custody",
            "medical_temporary_detention",
        ],
        "complementary_sources": list(COMPLEMENTARY_SOURCES),
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Virginia",
    state_code=STATE_CODE,
)


class VAGeneralDistrictError(RuntimeError):
    """Source, transport, or query error with result-envelope semantics."""

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


class VAGDCSelectionError(VAGeneralDistrictError):
    """A caller selector does not match the source's native contract."""

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


class VAGDCSourceChangedError(VAGeneralDistrictError):
    """The official HTML no longer matches the verified source contract."""

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


@dataclass(frozen=True)
class CourtOption:
    """One court component exactly as published by the application."""

    name: str
    source_code: str

    @property
    def court_id(self) -> str:
        return f"va-gdc-{self.source_code}"

    def to_record(self, *, source_url: str = LANDING_URL) -> dict[str, Any]:
        return {
            "canonical_ref": f"VA-GDC:COURT:{self.source_code}",
            "source_id": SOURCE_ID,
            "record_kind": "court_component",
            "court_id": self.court_id,
            "court_name": self.name,
            "court_source_code": self.source_code,
            "court_source_code_semantics": (
                "source-published application court-component identifier"
            ),
            "state_code": STATE_CODE,
            "source_url": source_url,
        }


@dataclass(frozen=True)
class SearchPage:
    """One parsed native search-result page."""

    records: tuple[Mapping[str, Any], ...]
    headers: tuple[str, ...]
    has_next: bool
    has_previous: bool
    authoritative_empty: bool
    native_page: int
    schema_fingerprint: str
    boundary: Mapping[str, Any]
    next_action_url: str | None
    next_payload: tuple[tuple[str, str], ...]
    source_url: str


@dataclass(frozen=True)
class SearchFetch:
    """Returned records plus source-native paging/completeness state."""

    records: tuple[Mapping[str, Any], ...]
    pages_fetched: int
    replay_pages_fetched: int
    start_native_page: int
    end_native_page: int
    source_exhausted: bool
    next_cursor: str | None
    reported_total: None
    schema_fingerprints: tuple[str, ...]
    source_url: str
    error: VAGeneralDistrictError | None = None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(
        str(value).replace("\x00", "").replace("\xa0", " ").split()
    ).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise VAGDCSelectionError(
            "required_selector_missing",
            f"{field_name} must not be blank",
            details={"field": field_name},
        )
    return normalized


def _key(value: Any) -> str:
    normalized = (_text(value) or "").casefold()
    key = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    return key or "unnamed"


def _schema_fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _response_url(
    response: Any,
    fallback_url: str,
    params: Mapping[str, Any] | None = None,
) -> str:
    value = _text(getattr(response, "url", None))
    if value:
        return value
    if not params:
        return fallback_url
    separator = "&" if "?" in fallback_url else "?"
    return f"{fallback_url}{separator}{urlencode(params, doseq=True)}"


def _same_origin(first: str, second: str) -> bool:
    first_url = urlparse(first)
    second_url = urlparse(second)
    return (
        first_url.scheme.casefold(),
        first_url.netloc.casefold(),
    ) == (
        second_url.scheme.casefold(),
        second_url.netloc.casefold(),
    )


def _retry_after_seconds(value: Any) -> float | None:
    normalized = _text(value)
    if normalized is None:
        return None
    try:
        return max(0.0, float(normalized))
    except ValueError:
        return None


def _division_code(value: Any) -> str:
    normalized = _required_text(value, "division").casefold().replace(" ", "-")
    if normalized in {"v", "civil"}:
        return "V"
    if normalized in {"t", "traffic-criminal", "traffic", "criminal"}:
        return "T"
    raise VAGDCSelectionError(
        "invalid_division",
        "division must be civil or traffic-criminal",
        details={"value": value},
    )


def _status_code(value: Any) -> str:
    normalized = _required_text(value, "status").casefold()
    if normalized in STATUS_CODES:
        return STATUS_CODES[normalized]
    if normalized.upper() in STATUS_NAMES:
        return normalized.upper()
    raise VAGDCSelectionError(
        "invalid_status",
        "status must be current, archived, or all",
        details={"value": value},
    )


def _source_date(value: Any) -> str:
    normalized = _required_text(value, "hearing_date")
    for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(normalized, date_format).strftime("%m/%d/%Y")
        except ValueError:
            continue
    raise VAGDCSelectionError(
        "invalid_hearing_date",
        "hearing_date must be YYYY-MM-DD or MM/DD/YYYY",
        details={"value": normalized},
    )


def _parse_date(value: Any) -> str | None:
    normalized = _text(value)
    if normalized is None or "*" in normalized:
        return None
    for date_format in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(normalized, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _page_text(soup: BeautifulSoup) -> str:
    return _text(soup.get_text(" ", strip=True)) or ""


def _verification_input(soup: BeautifulSoup) -> Tag | None:
    for field in soup.select("input[name]"):
        if not isinstance(field, Tag):
            continue
        field_type = str(field.get("type", "text")).casefold()
        if field_type in {"hidden", "submit", "button", "reset"}:
            continue
        name = str(field.get("name", "")).casefold()
        identifier = str(field.get("id", "")).casefold()
        if any(
            marker in f"{name} {identifier}"
            for marker in ("captcha", "verification", "securitycode")
        ):
            return field
    return None


def _is_terms_page(soup: BeautifulSoup) -> bool:
    return (
        soup.find("input", attrs={"name": "accept"}) is not None
        and "terms and conditions" in _page_text(soup).casefold()
    )


def _raise_page_failure(
    html: str,
    *,
    source_url: str,
    allow_terms: bool = False,
) -> None:
    soup = BeautifulSoup(html, "html.parser")
    page_text = _page_text(soup)
    lowered = page_text.casefold()
    if "you have exceeded the rate limit" in lowered:
        raise VAGeneralDistrictError(
            "rate_limited",
            "Virginia GDC returned its rate-limit page",
            status=ResultStatus.RATE_LIMITED,
            category="rate_limit",
            retryable=True,
            details={"source_url": source_url},
        )
    verification = _verification_input(soup)
    if verification is not None:
        raise VAGeneralDistrictError(
            "verification_required",
            "Virginia GDC requires an interactive verification value",
            status=ResultStatus.HUMAN_REQUIRED,
            category="access",
            details={
                "source_url": source_url,
                "field_name": verification.get("name"),
            },
        )
    if _is_terms_page(soup) and not allow_terms:
        raise VAGeneralDistrictError(
            "session_terms_returned",
            "Virginia GDC returned to its terms page during an active query",
            status=ResultStatus.TERMS_BLOCKED,
            category="session",
            retryable=True,
            details={"source_url": source_url},
        )


def _error_message(soup: BeautifulSoup) -> str | None:
    for selector in (
        "#error",
        "#searchError",
        ".errorFont",
        "[role=alert]",
    ):
        for node in soup.select(selector):
            message = _text(node.get_text(" ", strip=True))
            if message:
                return message
    return None


def _is_authoritative_empty(message: str | None) -> bool:
    if message is None:
        return False
    lowered = message.casefold()
    return any(
        marker in lowered
        for marker in (
            "no results found for the search criteria",
            "no cases found",
            "no records found",
        )
    )


def _raise_query_error(soup: BeautifulSoup, *, source_url: str) -> None:
    message = _error_message(soup)
    if message is None or _is_authoritative_empty(message):
        return
    lowered = message.casefold()
    if any(
        marker in lowered
        for marker in (
            "please enter",
            "must correct",
            "invalid",
            "required",
        )
    ):
        raise VAGDCSelectionError(
            "invalid_search_criteria",
            message,
            details={"source_url": source_url},
        )
    raise VAGeneralDistrictError(
        "source_query_error",
        message,
        category="source_query",
        details={"source_url": source_url},
    )


def parse_courts_page(
    html: str,
    *,
    source_url: str = LANDING_URL,
) -> tuple[CourtOption, ...]:
    """Parse source-published court-component names and identifiers."""

    _raise_page_failure(html, source_url=source_url, allow_terms=True)
    soup = BeautifulSoup(html, "html.parser")
    names = [
        _text(field.get("value"))
        for field in soup.select('input[name="courtName"]')
        if isinstance(field, Tag)
    ]
    codes = [
        _text(field.get("value"))
        for field in soup.select('input[name="courtFips"]')
        if isinstance(field, Tag)
    ]
    if not names and _is_terms_page(soup):
        return ()
    if not names or len(names) != len(codes):
        raise VAGDCSourceChangedError(
            "court_options_missing",
            "Virginia GDC did not publish paired court names and codes",
            details={
                "source_url": source_url,
                "name_count": len(names),
                "code_count": len(codes),
            },
        )
    courts: list[CourtOption] = []
    seen_codes: set[str] = set()
    seen_names: set[str] = set()
    for index, (name, code) in enumerate(zip(names, codes, strict=True)):
        if name is None or code is None:
            raise VAGDCSourceChangedError(
                "court_option_blank",
                "Virginia GDC published a blank court name or code",
                details={"source_url": source_url, "index": index},
            )
        if code in seen_codes or name.casefold() in seen_names:
            raise VAGDCSourceChangedError(
                "court_option_duplicate",
                "Virginia GDC published a duplicate court name or code",
                details={
                    "source_url": source_url,
                    "court_name": name,
                    "court_source_code": code,
                },
            )
        seen_codes.add(code)
        seen_names.add(name.casefold())
        courts.append(CourtOption(name=name, source_code=code))
    return tuple(courts)


def resolve_court(
    courts: Sequence[CourtOption],
    selector: Any,
) -> CourtOption:
    """Resolve a source code, exact name, or unique name fragment."""

    requested = _required_text(selector, "court")
    by_code = [court for court in courts if court.source_code == requested]
    if len(by_code) == 1:
        return by_code[0]
    normalized = requested.casefold()
    exact = [court for court in courts if court.name.casefold() == normalized]
    if len(exact) == 1:
        return exact[0]
    partial = [court for court in courts if normalized in court.name.casefold()]
    if len(partial) == 1:
        return partial[0]
    if partial:
        raise VAGDCSelectionError(
            "ambiguous_court",
            f"court selector matches {len(partial)} source court components",
            details={
                "selector": requested,
                "matches": [
                    {
                        "court_name": court.name,
                        "court_source_code": court.source_code,
                    }
                    for court in partial
                ],
            },
        )
    raise VAGDCSelectionError(
        "unknown_court",
        "court selector does not match a source-published court component",
        details={"selector": requested},
    )


def _successful_controls(form: Tag) -> list[tuple[str, str]]:
    controls: list[tuple[str, str]] = []
    for field in form.find_all(["input", "select", "textarea"]):
        if not isinstance(field, Tag) or field.has_attr("disabled"):
            continue
        name = _text(field.get("name"))
        if name is None:
            continue
        if field.name == "input":
            field_type = str(field.get("type", "text")).casefold()
            if field_type in {"submit", "reset", "button", "image", "file"}:
                continue
            if field_type in {"checkbox", "radio"} and not field.has_attr("checked"):
                continue
            controls.append((name, str(field.get("value", ""))))
        elif field.name == "select":
            selected = field.find_all("option", selected=True)
            if not selected:
                first = field.find("option")
                selected = [first] if isinstance(first, Tag) else []
            for option in selected:
                if isinstance(option, Tag):
                    controls.append(
                        (
                            name,
                            str(
                                option.get(
                                    "value",
                                    _text(option.get_text(" ", strip=True)) or "",
                                )
                            ),
                        )
                    )
        else:
            controls.append((name, field.get_text()))
    return controls


def _replace_controls(
    controls: Sequence[tuple[str, str]],
    overrides: Mapping[str, Any],
) -> tuple[tuple[str, str], ...]:
    names = set(overrides)
    payload = [(name, value) for name, value in controls if name not in names]
    payload.extend((name, str(value)) for name, value in overrides.items())
    return tuple(payload)


def _result_table(soup: BeautifulSoup) -> tuple[Tag, list[str]] | None:
    for table in soup.select("table.tableborder"):
        if not isinstance(table, Tag):
            continue
        first_row = table.find("tr")
        if not isinstance(first_row, Tag):
            continue
        header_cells = first_row.find_all(
            ["td", "th"],
            recursive=False,
        )
        headers = [
            _text(cell.get_text(" ", strip=True)) or ""
            for cell in header_cells
            if isinstance(cell, Tag)
        ]
        if "case" in {_key(header) for header in headers}:
            return table, headers
    return None


def _detail_locator(cell: Tag, source_url: str) -> dict[str, Any] | None:
    link = cell.find("a", href=True)
    if not isinstance(link, Tag):
        return None
    detail_url = urljoin(source_url, str(link["href"]))
    parsed = urlparse(detail_url)
    query = {
        key: values[-1] if values else ""
        for key, values in parse_qs(
            parsed.query,
            keep_blank_values=True,
        ).items()
    }
    session_values: dict[str, str] = {}
    for key in ("clientSearchCounter", "caseActive"):
        if key in query:
            session_values[key] = query.pop(key)
    return {
        "path": parsed.path,
        "parameters": query,
        "session_values": session_values,
        "session_bound": True,
    }


def _next_control(soup: BeautifulSoup) -> Tag | None:
    for field in soup.select('input[type="submit"]'):
        if not isinstance(field, Tag) or field.has_attr("disabled"):
            continue
        value = (_text(field.get("value")) or "").casefold()
        onclick = str(field.get("onclick", "")).casefold()
        name = str(field.get("name", "")).casefold()
        if value == "next" and (name == "caseinfoscrollforward" or "next" in onclick):
            return field
    return None


def _previous_control(soup: BeautifulSoup) -> Tag | None:
    for field in soup.select('input[type="submit"]'):
        if not isinstance(field, Tag) or field.has_attr("disabled"):
            continue
        value = (_text(field.get("value")) or "").casefold()
        onclick = str(field.get("onclick", "")).casefold()
        name = str(field.get("name", "")).casefold()
        if value in {"previous", "back"} and (
            name == "caseinfoscrollback" or "back" in onclick
        ):
            return field
    return None


def _boundary_payload(
    soup: BeautifulSoup,
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    hidden: dict[str, str] = {}
    for name in (
        "firstRowName",
        "firstRowCaseNumber",
        "lastRowName",
        "lastRowCaseNumber",
    ):
        field = soup.find("input", attrs={"name": name})
        if isinstance(field, Tag):
            hidden[name] = str(field.get("value", ""))
    first_case = records[0].get("raw_case_number") if records else None
    last_case = records[-1].get("raw_case_number") if records else None
    return {
        "first_case_number": first_case,
        "last_case_number": last_case,
        "source_boundary_fields": hidden,
        "row_count": len(records),
    }


def parse_search_page(
    html: str,
    *,
    operation: str,
    division: str,
    court: CourtOption,
    native_page: int,
    source_url: str,
) -> SearchPage:
    """Parse one native name, hearing, or service/process result page."""

    _raise_page_failure(html, source_url=source_url)
    soup = BeautifulSoup(html, "html.parser")
    _raise_query_error(soup, source_url=source_url)
    message = _error_message(soup)
    if _is_authoritative_empty(message):
        schema = _schema_fingerprint(
            {
                "operation": operation,
                "division": division,
                "state": "authoritative_empty",
            }
        )
        return SearchPage(
            records=(),
            headers=(),
            has_next=False,
            has_previous=False,
            authoritative_empty=True,
            native_page=native_page,
            schema_fingerprint=schema,
            boundary={"row_count": 0},
            next_action_url=None,
            next_payload=(),
            source_url=source_url,
        )

    found = _result_table(soup)
    if found is None:
        raise VAGDCSourceChangedError(
            "result_table_missing",
            "Virginia GDC result page lacks a case table",
            details={
                "operation": operation,
                "division": division,
                "source_url": source_url,
            },
        )
    table, headers = found
    normalized_headers = [
        "selection" if not _text(header) else _key(header) for header in headers
    ]
    records: list[dict[str, Any]] = []
    for row_index, row in enumerate(table.find_all("tr")[1:], start=1):
        if not isinstance(row, Tag):
            continue
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) != len(headers):
            continue
        values = [
            _text(cell.get_text(" ", strip=True))
            for cell in cells
            if isinstance(cell, Tag)
        ]
        if len(values) != len(headers):
            continue
        row_values = dict(zip(normalized_headers, values, strict=True))
        case_cell_index = normalized_headers.index("case")
        case_cell = cells[case_cell_index]
        raw_case_number = _text(row_values.get("case")) or _text(
            (
                case_cell.find(
                    "input",
                    attrs={"name": "checkedCases"},
                )
                or {}
            ).get("value")
        )
        if raw_case_number is None:
            continue
        source_values = {
            header or "Selection": value
            for header, value in zip(headers, values, strict=True)
        }
        semantic_values = {
            key: value for key, value in row_values.items() if key != "selection"
        }
        for key, value in list(semantic_values.items()):
            if "date" in key:
                parsed = _parse_date(value)
                if parsed is not None:
                    semantic_values[f"{key}_iso"] = parsed
        record = {
            "canonical_ref": canonical_court_ref(
                SOURCE_ID,
                court.court_id,
                raw_case_number,
                "case_search_hit",
            ),
            "source_id": SOURCE_ID,
            "record_kind": "case_search_hit",
            "query_role": operation,
            "division_code": division,
            "division_name": DIVISION_NAMES[division],
            "court_id": court.court_id,
            "court_name": court.name,
            "court_source_code": court.source_code,
            "raw_case_number": raw_case_number,
            "source_values": source_values,
            "values": semantic_values,
            "source_detail_locator": _detail_locator(
                case_cell,
                source_url,
            ),
            "source_native_page": native_page,
            "source_native_row": row_index,
            "source_url": source_url,
        }
        records.append(record)

    if not records:
        raise VAGDCSourceChangedError(
            "result_rows_missing",
            "Virginia GDC case table contains no parseable case rows",
            details={
                "operation": operation,
                "division": division,
                "headers": headers,
                "source_url": source_url,
            },
        )

    next_control = _next_control(soup)
    next_action_url: str | None = None
    next_payload: tuple[tuple[str, str], ...] = ()
    if next_control is not None:
        form = next_control.find_parent("form")
        if not isinstance(form, Tag):
            raise VAGDCSourceChangedError(
                "pagination_form_missing",
                "Virginia GDC Next control is not inside a form",
                details={"source_url": source_url},
            )
        next_action_url = urljoin(source_url, str(form.get("action", "")))
        if operation == "name":
            overrides = {"formAction": "next"}
        else:
            overrides = {"caseInfoScrollForward": "Next"}
        next_payload = _replace_controls(
            _successful_controls(form),
            overrides,
        )
    boundary = _boundary_payload(soup, records)
    schema = _schema_fingerprint(
        {
            "operation": operation,
            "division": division,
            "headers": headers,
        }
    )
    return SearchPage(
        records=tuple(records),
        headers=tuple(headers),
        has_next=next_control is not None,
        has_previous=_previous_control(soup) is not None,
        authoritative_empty=False,
        native_page=native_page,
        schema_fingerprint=schema,
        boundary=boundary,
        next_action_url=next_action_url,
        next_payload=next_payload,
        source_url=source_url,
    )


def _section_title(toggle: Tag) -> str:
    header = toggle.find_previous_sibling("tr")
    if isinstance(header, Tag):
        target = header.select_one(".subheader")
        if isinstance(target, Tag):
            spans = target.find_all("span")
            if spans:
                value = _text(spans[-1].get_text(" ", strip=True))
                if value:
                    return value
            value = _text(target.get_text(" ", strip=True))
            if value:
                return value
    return str(toggle.get("id", "section"))


def _parse_grid_table(table: Tag) -> tuple[list[str], list[dict[str, Any]]]:
    header_row = table.find("tr", class_="gridheader")
    if not isinstance(header_row, Tag):
        return [], []
    header_cells = header_row.find_all(["td", "th"], recursive=False)
    labels = [
        _text(cell.get_text(" ", strip=True)) or ""
        for cell in header_cells
        if isinstance(cell, Tag)
    ]
    keys = [_key(label) for label in labels]
    rows: list[dict[str, Any]] = []
    for row in header_row.find_all_next("tr"):
        if not isinstance(row, Tag) or row.find_parent("table") is not table:
            continue
        classes = {str(value).casefold() for value in row.get("class", [])}
        if not classes.intersection(
            {"gridrow", "gridalternaterow", "evenrow", "oddrow"}
        ):
            continue
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) != len(labels):
            continue
        raw_values = [
            _text(cell.get_text(" ", strip=True))
            for cell in cells
            if isinstance(cell, Tag)
        ]
        values = dict(zip(keys, raw_values, strict=True))
        source_values = dict(zip(labels, raw_values, strict=True))
        for key, value in list(values.items()):
            if "date" in key:
                parsed = _parse_date(value)
                if parsed is not None:
                    values[f"{key}_iso"] = parsed
        rows.append(
            {
                "source_values": source_values,
                "values": values,
            }
        )
    return labels, rows


def _parse_scalar_section(toggle: Tag) -> tuple[list[str], dict[str, Any]]:
    labels: list[str] = []
    source_values: dict[str, str | None] = {}
    values: dict[str, Any] = {}
    links: list[dict[str, str]] = []
    for label_cell in toggle.find_all("td"):
        if not isinstance(label_cell, Tag):
            continue
        classes = [str(value).casefold() for value in label_cell.get("class", [])]
        if not any(class_name.startswith("labelgrid") for class_name in classes):
            continue
        if any("labelvalue" in class_name for class_name in classes):
            continue
        label = _text(label_cell.get_text(" ", strip=True))
        if label is None:
            continue
        label = label.rstrip(":").strip()
        if not label:
            continue
        value_cell = label_cell.find_next_sibling("td")
        if not isinstance(value_cell, Tag):
            continue
        value_classes = [str(value).casefold() for value in value_cell.get("class", [])]
        if not any("labelvalue" in class_name for class_name in value_classes):
            continue
        raw_value = _text(value_cell.get_text(" ", strip=True))
        key = _key(label)
        labels.append(label)
        source_values[label] = raw_value
        values[key] = raw_value
        if "date" in key:
            parsed = _parse_date(raw_value)
            if parsed is not None:
                values[f"{key}_iso"] = parsed
        for link in value_cell.find_all("a", href=True):
            if isinstance(link, Tag):
                links.append(
                    {
                        "label": _text(link.get_text(" ", strip=True)) or label,
                        "href": str(link["href"]),
                    }
                )
    return labels, {
        "source_values": source_values,
        "values": values,
        "links": links,
    }


def _expected_sections(division: str) -> tuple[str, ...]:
    if division == "V":
        return (
            "case_information",
            "plaintiff_information",
            "defendant_information",
            "hearing_information",
            "service_process",
            "reports",
            "judgment_information",
            "garnishment_information",
            "appeal_information",
        )
    return (
        "case_defendant_information",
        "charge_information",
        "hearing_information",
        "service_process",
        "disposition_information",
    )


def parse_case_detail(
    html: str,
    *,
    division: str,
    court: CourtOption,
    source_url: str,
    requested_case_number: str | None = None,
) -> dict[str, Any] | None:
    """Parse a civil or traffic/criminal case-detail page."""

    _raise_page_failure(html, source_url=source_url)
    soup = BeautifulSoup(html, "html.parser")
    _raise_query_error(soup, source_url=source_url)
    if _is_authoritative_empty(_error_message(soup)):
        return None

    sections: list[dict[str, Any]] = []
    section_by_key: dict[str, dict[str, Any]] = {}
    for toggle in soup.select('tr[id^="toggle"]'):
        if not isinstance(toggle, Tag):
            continue
        title = _section_title(toggle)
        section_key = _key(title.replace("/", " "))
        grid_table = None
        for table in toggle.select("table.tableborder"):
            if isinstance(table, Tag) and table.select_one(".subgridheader"):
                grid_table = table
                break
        if grid_table is not None:
            labels, rows = _parse_grid_table(grid_table)
            state = "published" if rows else "published_empty"
            section = {
                "section_key": section_key,
                "source_title": title,
                "state": state,
                "kind": "table",
                "source_columns": labels,
                "rows": rows,
            }
        else:
            labels, scalar = _parse_scalar_section(toggle)
            if not labels:
                continue
            state = (
                "published"
                if any(value is not None for value in scalar["values"].values())
                else "published_empty"
            )
            section = {
                "section_key": section_key,
                "source_title": title,
                "state": state,
                "kind": "fields",
                "source_fields": labels,
                **scalar,
            }
        sections.append(section)
        section_by_key[section_key] = section

    if not sections:
        raise VAGDCSourceChangedError(
            "case_sections_missing",
            "Virginia GDC case detail lacks source sections",
            details={"division": division, "source_url": source_url},
        )

    case_section_key = (
        "case_information" if division == "V" else "case_defendant_information"
    )
    case_section = section_by_key.get(case_section_key)
    case_values = (
        case_section.get("values", {}) if isinstance(case_section, Mapping) else {}
    )
    raw_case_number = _text(case_values.get("case_number"))
    if raw_case_number is None:
        raise VAGDCSourceChangedError(
            "case_number_missing",
            "Virginia GDC detail lacks its source case number",
            details={"division": division, "source_url": source_url},
        )
    if (
        requested_case_number is not None
        and raw_case_number.casefold()
        != _required_text(requested_case_number, "case_number").casefold()
    ):
        raise VAGDCSourceChangedError(
            "case_number_mismatch",
            "Virginia GDC returned a different case than requested",
            details={
                "requested_case_number": requested_case_number,
                "returned_case_number": raw_case_number,
                "source_url": source_url,
            },
        )

    section_states = {
        key: (section_by_key[key]["state"] if key in section_by_key else "not_present")
        for key in _expected_sections(division)
    }
    all_links: list[dict[str, Any]] = []
    for link in soup.find_all("a", href=True):
        if not isinstance(link, Tag):
            continue
        label = _text(link.get_text(" ", strip=True))
        href = urljoin(source_url, str(link["href"]))
        if label and "pay" in label.casefold():
            all_links.append({"label": label, "url": href})

    record: dict[str, Any] = {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            court.court_id,
            raw_case_number,
            "case",
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "division_code": division,
        "division_name": DIVISION_NAMES[division],
        "court_id": court.court_id,
        "court_name": court.name,
        "court_source_code": court.source_code,
        "raw_case_number": raw_case_number,
        "case_data_status_code": "O",
        "case_data_status": STATUS_NAMES["O"],
        "sections": sections,
        "section_states": section_states,
        "source_url": source_url,
        "document_access": {
            "state": "not_published_by_case_information_source",
            "filing_index_present": False,
            "filing_images_present": False,
            "official_copy_route": "individual_court_clerk",
            "official_copy_guidance_url": PUBLIC_RECORDS_REQUEST_URL,
        },
        "payment_links": all_links,
        "payment_access": {
            "state": ("published" if all_links else "not_present_on_returned_case"),
            "links": all_links,
        },
    }
    if division == "V":
        record.update(
            {
                "filed_date": case_values.get("filed_date"),
                "filed_date_iso": case_values.get("filed_date_iso"),
                "case_type": case_values.get("case_type"),
                "debt_type": case_values.get("debt_type"),
                "plaintiffs": (
                    section_by_key.get("plaintiff_information", {}).get("rows", [])
                ),
                "defendants": (
                    section_by_key.get("defendant_information", {}).get("rows", [])
                ),
                "hearings": (
                    section_by_key.get("hearing_information", {}).get("rows", [])
                ),
                "service_process": (
                    section_by_key.get("service_process", {}).get("rows", [])
                ),
                "reports": section_by_key.get("reports", {}).get("rows", []),
                "judgment": (
                    section_by_key.get("judgment_information", {}).get("values")
                ),
                "garnishment": (
                    section_by_key.get("garnishment_information", {}).get("values")
                ),
                "appeal": (section_by_key.get("appeal_information", {}).get("values")),
            }
        )
    else:
        dob_raw = _text(case_values.get("dob"))
        dob_state = None
        if dob_raw is not None:
            dob_state = "year_redacted" if "*" in dob_raw else "published"
        record.update(
            {
                "filed_date": case_values.get("filed_date"),
                "filed_date_iso": case_values.get("filed_date_iso"),
                "defendant": dict(case_values),
                "date_of_birth_at_source": dob_raw,
                "date_of_birth_state": dob_state,
                "charge": (section_by_key.get("charge_information", {}).get("values")),
                "hearings": (
                    section_by_key.get("hearing_information", {}).get("rows", [])
                ),
                "service_process": (
                    section_by_key.get("service_process", {}).get("rows", [])
                ),
                "disposition": (
                    section_by_key.get("disposition_information", {}).get("values")
                ),
            }
        )
    return record


def _encode_cursor(payload: Mapping[str, Any]) -> str:
    encoded = base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8")).decode(
        "ascii"
    )
    return f"{CURSOR_PREFIX}{encoded.rstrip('=')}"


def _decode_cursor(cursor: Any) -> dict[str, Any]:
    normalized = _required_text(cursor, "cursor")
    if not normalized.startswith(CURSOR_PREFIX):
        raise VAGDCSelectionError(
            "invalid_cursor",
            "cursor does not belong to the Virginia GDC adapter",
        )
    token = normalized[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(token) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(f"{token}{padding}").decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VAGDCSelectionError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise VAGDCSelectionError(
            "invalid_cursor",
            "cursor version is not supported",
        )
    return payload


def _criteria_fingerprint(criteria: Mapping[str, Any]) -> str:
    return _schema_fingerprint(criteria)


def _build_cursor(
    *,
    criteria: Mapping[str, Any],
    resume_page: int,
    row_offset: int,
    anchor_page: SearchPage,
) -> str:
    return _encode_cursor(
        {
            "version": 1,
            "source_id": SOURCE_ID,
            "operation": criteria["operation"],
            "criteria_fingerprint": _criteria_fingerprint(criteria),
            "resume_page": resume_page,
            "row_offset": row_offset,
            "anchor_page": anchor_page.native_page,
            "anchor_schema_fingerprint": anchor_page.schema_fingerprint,
            "anchor_boundary": anchor_page.boundary,
        }
    )


def _validate_cursor(
    cursor: Mapping[str, Any],
    criteria: Mapping[str, Any],
) -> tuple[int, int, int]:
    if cursor.get("source_id") != SOURCE_ID:
        raise VAGDCSelectionError(
            "invalid_cursor",
            "cursor source does not match Virginia GDC",
        )
    if cursor.get("operation") != criteria.get("operation"):
        raise VAGDCSelectionError(
            "cursor_query_mismatch",
            "cursor operation does not match the requested search",
        )
    if cursor.get("criteria_fingerprint") != _criteria_fingerprint(criteria):
        raise VAGDCSelectionError(
            "cursor_query_mismatch",
            "cursor criteria do not match the requested search",
        )
    try:
        resume_page = int(cursor["resume_page"])
        row_offset = int(cursor["row_offset"])
        anchor_page = int(cursor["anchor_page"])
    except (KeyError, TypeError, ValueError) as error:
        raise VAGDCSelectionError(
            "invalid_cursor",
            "cursor paging values are malformed",
        ) from error
    if (
        resume_page < 1
        or row_offset < 0
        or anchor_page < 1
        or anchor_page > resume_page
        or resume_page - anchor_page > 1
    ):
        raise VAGDCSelectionError(
            "invalid_cursor",
            "cursor paging values are outside the supported replay state",
        )
    return resume_page, row_offset, anchor_page


def _assert_cursor_anchor(
    cursor: Mapping[str, Any],
    page: SearchPage,
) -> None:
    if (
        cursor.get("anchor_schema_fingerprint") != page.schema_fingerprint
        or cursor.get("anchor_boundary") != page.boundary
    ):
        raise VAGDCSourceChangedError(
            "stale_cursor",
            "Virginia GDC result ordering changed at the cursor boundary",
            details={
                "native_page": page.native_page,
                "expected_boundary": cursor.get("anchor_boundary"),
                "observed_boundary": page.boundary,
                "expected_schema": cursor.get("anchor_schema_fingerprint"),
                "observed_schema": page.schema_fingerprint,
            },
        )


class VAGeneralDistrictClient:
    """Transport-injectable client for the official Virginia GDC application."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: RetryPolicy | None = None,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        sleeper: Callable[[float], None] = time.sleep,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleeper = sleeper
        self._rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.user_agent = user_agent
        self.request_count = 0
        self._started = False
        self._courts: tuple[CourtOption, ...] = ()
        self._welcome_html: str | None = None
        self._welcome_url: str = LANDING_URL
        self._selected_court: CourtOption | None = None
        self.terms_state: str | None = None

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | Sequence[tuple[str, str]] | None = None,
        referer: str | None = None,
    ) -> Any:
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": self.user_agent,
        }
        if referer is not None:
            headers["Referer"] = referer
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt))
                    continue
                raise VAGeneralDistrictError(
                    "transport_error",
                    (f"Virginia GDC request failed after {attempt} attempts: {error}"),
                    category="transport",
                    retryable=True,
                    details={"attempts": attempt, "url": url},
                ) from error
            status_code = int(response.status_code)
            if status_code in self.retry_policy.retry_statuses:
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(
                        self.retry_policy.delay(
                            attempt,
                            _retry_after_seconds(response.headers.get("Retry-After")),
                        )
                    )
                    continue
                rate_limited = status_code == 429
                raise VAGeneralDistrictError(
                    ("rate_limited" if rate_limited else "http_status_error"),
                    f"Virginia GDC returned HTTP {status_code}",
                    status=(
                        ResultStatus.RATE_LIMITED
                        if rate_limited
                        else ResultStatus.UNAVAILABLE
                    ),
                    category=("rate_limit" if rate_limited else "transport"),
                    retryable=True,
                    details={"status_code": status_code, "url": url},
                )
            if status_code in {401, 403}:
                raise VAGeneralDistrictError(
                    "source_access_failed",
                    f"Virginia GDC returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"status_code": status_code, "url": url},
                )
            if status_code >= 400:
                raise VAGeneralDistrictError(
                    "http_status_error",
                    f"Virginia GDC returned HTTP {status_code}",
                    category="transport",
                    details={"status_code": status_code, "url": url},
                )
            response_url = _response_url(response, url, params)
            _raise_page_failure(
                response.text,
                source_url=response_url,
                allow_terms=url in {LANDING_URL, LANDING_POST_URL},
            )
            return response
        raise AssertionError("retry loop exhausted without returning or raising")

    def start(self) -> tuple[CourtOption, ...]:
        """Accept the source terms for this session and load court options."""

        if self._started:
            return self._courts
        landing = self._request("GET", LANDING_URL)
        landing_url = _response_url(landing, LANDING_URL)
        soup = BeautifulSoup(landing.text, "html.parser")
        verification = _verification_input(soup)
        if verification is not None:
            _raise_page_failure(
                landing.text,
                source_url=landing_url,
                allow_terms=True,
            )
        courts = parse_courts_page(landing.text, source_url=landing_url)
        if courts:
            self.terms_state = "accepted_in_existing_session"
            welcome = landing
            welcome_url = landing_url
        else:
            accept = soup.find("input", attrs={"name": "accept"})
            form = accept.find_parent("form") if isinstance(accept, Tag) else None
            if not isinstance(form, Tag):
                raise VAGDCSourceChangedError(
                    "terms_accept_form_missing",
                    "Virginia GDC landing page lacks its Accept form",
                    details={"source_url": landing_url},
                )
            action_url = urljoin(landing_url, str(form.get("action", "")))
            welcome = self._request(
                "POST",
                action_url,
                data={"accept": str(accept.get("value", "Accept"))},
                referer=landing_url,
            )
            welcome_url = _response_url(welcome, action_url)
            courts = parse_courts_page(
                welcome.text,
                source_url=welcome_url,
            )
            self.terms_state = "accepted_by_adapter"
        if not courts:
            raise VAGDCSourceChangedError(
                "welcome_page_missing",
                "Virginia GDC did not return its court-selection page",
                details={"source_url": welcome_url},
            )
        self._courts = courts
        self._welcome_html = welcome.text
        self._welcome_url = welcome_url
        self._started = True
        return courts

    def courts(self) -> tuple[Mapping[str, Any], ...]:
        courts = self.start()
        return tuple(court.to_record(source_url=self._welcome_url) for court in courts)

    def _select_court(self, selector: Any) -> CourtOption:
        courts = self.start()
        court = resolve_court(courts, selector)
        if (
            self._selected_court is not None
            and self._selected_court.source_code == court.source_code
        ):
            return court
        response = self._request(
            "POST",
            CHANGE_COURT_URL,
            data={
                "selectedCourtsName": court.name,
                "selectedCourtsFipCode": court.source_code,
                "sessionCourtsFipCode": (
                    self._selected_court.source_code
                    if self._selected_court is not None
                    else ""
                ),
            },
            referer=self._welcome_url,
        )
        response_url = _response_url(response, CHANGE_COURT_URL)
        soup = BeautifulSoup(response.text, "html.parser")
        selected = _text(
            (soup.find("input", attrs={"name": "selectedCourtName"}) or {}).get("value")
        )
        link = soup.find(
            "a",
            href=re.compile(
                rf"(?:searchFipsCode|localFipsCode)={re.escape(court.source_code)}"
            ),
        )
        if selected != court.name or not isinstance(link, Tag):
            raise VAGDCSourceChangedError(
                "court_selection_failed",
                "Virginia GDC did not confirm the selected court component",
                details={
                    "requested_court_name": court.name,
                    "requested_court_source_code": court.source_code,
                    "observed_court_name": selected,
                    "source_url": response_url,
                },
            )
        self._selected_court = court
        self._welcome_html = response.text
        self._welcome_url = response_url
        return court

    def _open_search_form(
        self,
        operation: str,
        division: str,
        court: CourtOption,
    ) -> Any:
        if operation == "name":
            url = NAME_SEARCH_URL
            params = {
                "fromSidebar": "true",
                "formAction": "searchLanding",
                "searchDivision": division,
                "searchFipsCode": court.source_code,
                "localFipsCode": court.source_code,
            }
            form_name = "nameSearchForm"
        elif operation in {"hearing", "service"}:
            url = CASE_SEARCH_URL
            params = {
                "fromSidebar": "true",
                "searchLanding": "searchLanding",
                "searchType": (
                    "hearingDate" if operation == "hearing" else "servicesName"
                ),
                "searchDivision": division,
                "searchFipsCode": court.source_code,
                "curentFipsCode": court.source_code,
            }
            form_name = "caseSearchForm"
        elif operation == "case":
            url = CASE_NUMBER_SEARCH_URL
            params = {
                "fromSidebar": "true",
                "formAction": "searchLanding",
                "searchDivision": division,
                "searchFipsCode": court.source_code,
                "curentFipsCode": court.source_code,
            }
            form_name = "criminalCivilCaseSearchForm"
        else:
            raise ValueError(f"unsupported operation: {operation}")
        response = self._request(
            "GET",
            url,
            params=params,
            referer=self._welcome_url,
        )
        response_url = _response_url(response, url, params)
        soup = BeautifulSoup(response.text, "html.parser")
        form = soup.find("form", attrs={"name": form_name})
        if not isinstance(form, Tag):
            raise VAGDCSourceChangedError(
                "search_form_missing",
                f"Virginia GDC lacks its {operation} search form",
                details={
                    "operation": operation,
                    "division": division,
                    "source_url": response_url,
                },
            )
        return response

    @staticmethod
    def _name_payload(
        *,
        court: CourtOption,
        division: str,
        last_name: str,
        first_name: str | None,
        middle_name: str | None,
        suffix: str | None,
        status: str,
    ) -> dict[str, str]:
        first = _text(first_name) or ""
        middle = _text(middle_name) or ""
        suffix_value = _text(suffix) or ""
        return {
            "formAction": "newSearch",
            "displayCaseNumber": "",
            "formBean": "",
            "localFipsCode": court.source_code,
            "caseActive": "",
            "localLastName": "",
            "forward": "",
            "back": "",
            "localnamesearchlastName": last_name,
            "lastName": last_name,
            "localnamesearchfirstName": first,
            "firstName": first,
            "localnamesearchmiddleName": middle,
            "middleName": middle,
            "localnamesearchsuffix": suffix_value,
            "suffix": suffix_value,
            "localnamesearchsearchCategory": status,
            "searchCategory": status,
            "searchFipsCode": court.source_code,
            "searchDivision": division,
            "searchType": "name",
        }

    @staticmethod
    def _hearing_payload(
        *,
        court: CourtOption,
        division: str,
        hearing_date: str,
        hearing_time: str | None,
        courtroom: str | None,
        hearing_type: str | None,
    ) -> dict[str, str]:
        return {
            "formAction": "",
            "curentFipsCode": court.source_code,
            "searchTerm": hearing_date,
            "searchHearingTime": _text(hearing_time) or "",
            "searchCourtroom": _text(courtroom) or "",
            "searchHearingType": _text(hearing_type) or "",
            "caseSearch": "Search",
            "searchFipsCode": court.source_code,
            "searchDivision": division,
            "searchType": "hearingDate",
        }

    @staticmethod
    def _service_payload(
        *,
        court: CourtOption,
        division: str,
        last_name: str,
        first_name: str | None,
        middle_name: str | None,
        suffix: str | None,
    ) -> dict[str, str]:
        return {
            "formAction": "caseDetails",
            "lastName": last_name,
            "firstName": _text(first_name) or "",
            "middleName": _text(middle_name) or "",
            "suffix": _text(suffix) or "",
            "curentFipsCode": court.source_code,
            "searchCategory": "S",
            "searchFipsCode": court.source_code,
            "searchDivision": division,
            "searchType": "servicesName",
            "caseSearch": "Search",
        }

    def _initial_search(
        self,
        criteria: Mapping[str, Any],
    ) -> tuple[SearchPage, CourtOption]:
        division = str(criteria["division_code"])
        operation = str(criteria["operation"])
        court = self._select_court(criteria["court_selector"])
        form = self._open_search_form(operation, division, court)
        form_url = _response_url(
            form,
            (NAME_SEARCH_URL if operation == "name" else CASE_SEARCH_URL),
        )
        if operation == "name":
            payload = self._name_payload(
                court=court,
                division=division,
                last_name=str(criteria["last_name"]),
                first_name=criteria.get("first_name"),
                middle_name=criteria.get("middle_name"),
                suffix=criteria.get("suffix"),
                status=str(criteria["status_code"]),
            )
            action_url = NAME_SEARCH_URL
        elif operation == "hearing":
            payload = self._hearing_payload(
                court=court,
                division=division,
                hearing_date=str(criteria["hearing_date_source"]),
                hearing_time=criteria.get("hearing_time"),
                courtroom=criteria.get("courtroom"),
                hearing_type=criteria.get("hearing_type"),
            )
            action_url = CASE_SEARCH_URL
        else:
            payload = self._service_payload(
                court=court,
                division=division,
                last_name=str(criteria["last_name"]),
                first_name=criteria.get("first_name"),
                middle_name=criteria.get("middle_name"),
                suffix=criteria.get("suffix"),
            )
            action_url = CASE_SEARCH_URL
        response = self._request(
            "POST",
            action_url,
            data=payload,
            referer=form_url,
        )
        response_url = _response_url(response, action_url)
        return (
            parse_search_page(
                response.text,
                operation=operation,
                division=division,
                court=court,
                native_page=1,
                source_url=response_url,
            ),
            court,
        )

    def _next_page(
        self,
        page: SearchPage,
        *,
        criteria: Mapping[str, Any],
        court: CourtOption,
    ) -> SearchPage:
        if not page.has_next or page.next_action_url is None or not page.next_payload:
            raise VAGDCSourceChangedError(
                "pagination_state_missing",
                "Virginia GDC page says Next is available without form state",
                details={"native_page": page.native_page},
            )
        if not _same_origin(BASE_URL, page.next_action_url):
            raise VAGDCSourceChangedError(
                "pagination_origin_changed",
                "Virginia GDC pagination points outside the official host",
                details={"next_action_url": page.next_action_url},
            )
        response = self._request(
            "POST",
            page.next_action_url,
            data=page.next_payload,
            referer=page.source_url,
        )
        response_url = _response_url(response, page.next_action_url)
        return parse_search_page(
            response.text,
            operation=str(criteria["operation"]),
            division=str(criteria["division_code"]),
            court=court,
            native_page=page.native_page + 1,
            source_url=response_url,
        )

    def _search(
        self,
        criteria: Mapping[str, Any],
        *,
        limit: int | None,
        cursor: str | None,
        max_pages: int | None,
    ) -> SearchFetch:
        if limit is not None and limit <= 0:
            raise VAGDCSelectionError(
                "invalid_limit",
                "limit must be positive",
            )
        if max_pages is not None and max_pages <= 0:
            raise VAGDCSelectionError(
                "invalid_max_pages",
                "max_pages must be positive",
            )
        cursor_payload = _decode_cursor(cursor) if cursor else None
        if cursor_payload is None:
            resume_page, row_offset, anchor_page_number = 1, 0, 1
        else:
            resume_page, row_offset, anchor_page_number = _validate_cursor(
                cursor_payload,
                criteria,
            )

        page, court = self._initial_search(criteria)
        total_native_pages_requested = 1
        if page.authoritative_empty:
            if cursor_payload is not None:
                raise VAGDCSourceChangedError(
                    "stale_cursor",
                    "Virginia GDC returned no results while replaying a cursor",
                    details={
                        "cursor_resume_page": resume_page,
                        "operation": criteria["operation"],
                    },
                )
            return SearchFetch(
                records=(),
                pages_fetched=1,
                replay_pages_fetched=0,
                start_native_page=1,
                end_native_page=1,
                source_exhausted=True,
                next_cursor=None,
                reported_total=None,
                schema_fingerprints=(page.schema_fingerprint,),
                source_url=page.source_url,
            )

        seen_boundaries = {_schema_fingerprint(page.boundary)}
        while page.native_page < resume_page:
            if cursor_payload is not None and page.native_page == anchor_page_number:
                _assert_cursor_anchor(cursor_payload, page)
            if not page.has_next:
                raise VAGDCSourceChangedError(
                    "stale_cursor",
                    "Virginia GDC result set ended before the cursor page",
                    details={
                        "cursor_resume_page": resume_page,
                        "last_native_page": page.native_page,
                    },
                )
            page = self._next_page(page, criteria=criteria, court=court)
            total_native_pages_requested += 1
            boundary_hash = _schema_fingerprint(page.boundary)
            if boundary_hash in seen_boundaries:
                raise VAGDCSourceChangedError(
                    "pagination_loop",
                    "Virginia GDC returned a repeated page boundary",
                    details={"native_page": page.native_page},
                )
            seen_boundaries.add(boundary_hash)
        if cursor_payload is not None and page.native_page == anchor_page_number:
            _assert_cursor_anchor(cursor_payload, page)
        if row_offset > len(page.records):
            raise VAGDCSourceChangedError(
                "stale_cursor",
                "Virginia GDC cursor row offset exceeds the replayed page",
                details={
                    "native_page": page.native_page,
                    "row_offset": row_offset,
                    "row_count": len(page.records),
                },
            )

        output: list[Mapping[str, Any]] = []
        schema_fingerprints: set[str] = set()
        pages_scanned = 0
        start_page = page.native_page
        next_cursor: str | None = None
        source_exhausted = False
        current_offset = row_offset

        while True:
            pages_scanned += 1
            schema_fingerprints.add(page.schema_fingerprint)
            for record in page.records[current_offset:]:
                output.append(record)
                if limit is not None and len(output) >= limit:
                    next_offset = current_offset + (
                        len(output)
                        - sum(
                            1
                            for existing in output
                            if existing.get("source_native_page") != page.native_page
                        )
                    )
                    if next_offset < len(page.records):
                        next_cursor = _build_cursor(
                            criteria=criteria,
                            resume_page=page.native_page,
                            row_offset=next_offset,
                            anchor_page=page,
                        )
                    elif page.has_next:
                        next_cursor = _build_cursor(
                            criteria=criteria,
                            resume_page=page.native_page + 1,
                            row_offset=0,
                            anchor_page=page,
                        )
                    else:
                        source_exhausted = True
                    return SearchFetch(
                        records=tuple(output),
                        pages_fetched=total_native_pages_requested,
                        replay_pages_fetched=max(0, start_page - 1),
                        start_native_page=start_page,
                        end_native_page=page.native_page,
                        source_exhausted=source_exhausted,
                        next_cursor=next_cursor,
                        reported_total=None,
                        schema_fingerprints=tuple(sorted(schema_fingerprints)),
                        source_url=page.source_url,
                    )
            if not page.has_next:
                source_exhausted = True
                break
            if max_pages is not None and pages_scanned >= max_pages:
                next_cursor = _build_cursor(
                    criteria=criteria,
                    resume_page=page.native_page + 1,
                    row_offset=0,
                    anchor_page=page,
                )
                break
            try:
                page = self._next_page(page, criteria=criteria, court=court)
            except VAGeneralDistrictError as error:
                next_cursor = _build_cursor(
                    criteria=criteria,
                    resume_page=page.native_page + 1,
                    row_offset=0,
                    anchor_page=page,
                )
                return SearchFetch(
                    records=tuple(output),
                    pages_fetched=total_native_pages_requested,
                    replay_pages_fetched=max(0, start_page - 1),
                    start_native_page=start_page,
                    end_native_page=page.native_page,
                    source_exhausted=False,
                    next_cursor=next_cursor,
                    reported_total=None,
                    schema_fingerprints=tuple(sorted(schema_fingerprints)),
                    source_url=page.source_url,
                    error=error,
                )
            total_native_pages_requested += 1
            boundary_hash = _schema_fingerprint(page.boundary)
            if boundary_hash in seen_boundaries:
                raise VAGDCSourceChangedError(
                    "pagination_loop",
                    "Virginia GDC returned a repeated page boundary",
                    details={"native_page": page.native_page},
                )
            seen_boundaries.add(boundary_hash)
            current_offset = 0

        return SearchFetch(
            records=tuple(output),
            pages_fetched=total_native_pages_requested,
            replay_pages_fetched=max(0, start_page - 1),
            start_native_page=start_page,
            end_native_page=page.native_page,
            source_exhausted=source_exhausted,
            next_cursor=next_cursor,
            reported_total=None,
            schema_fingerprints=tuple(sorted(schema_fingerprints)),
            source_url=page.source_url,
        )

    def search_name(
        self,
        court: Any,
        last_name_or_business: Any,
        *,
        division: Any = "civil",
        first_name: Any = None,
        middle_name: Any = None,
        suffix: Any = None,
        status: Any = "current",
        limit: int | None = None,
        cursor: str | None = None,
        max_pages: int | None = None,
    ) -> SearchFetch:
        division_code = _division_code(division)
        status_code = _status_code(status)
        criteria = {
            "source_id": SOURCE_ID,
            "operation": "name",
            "court_selector": _required_text(court, "court"),
            "division_code": division_code,
            "last_name": _required_text(
                last_name_or_business,
                "last_name_or_business",
            ),
            "first_name": _text(first_name),
            "middle_name": _text(middle_name),
            "suffix": _text(suffix),
            "status_code": status_code,
        }
        return self._search(
            criteria,
            limit=limit,
            cursor=cursor,
            max_pages=max_pages,
        )

    def search_hearing(
        self,
        court: Any,
        hearing_date: Any,
        *,
        division: Any = "civil",
        hearing_time: Any = None,
        courtroom: Any = None,
        hearing_type: Any = None,
        limit: int | None = None,
        cursor: str | None = None,
        max_pages: int | None = None,
    ) -> SearchFetch:
        division_code = _division_code(division)
        source_hearing_date = _source_date(hearing_date)
        hearing_type_code = _text(hearing_type) or ""
        if hearing_type_code not in HEARING_TYPE_LABELS:
            raise VAGDCSelectionError(
                "invalid_hearing_type",
                "hearing_type is not a source-published hearing code",
                details={
                    "value": hearing_type_code,
                    "available_codes": list(HEARING_TYPE_LABELS),
                },
            )
        criteria = {
            "source_id": SOURCE_ID,
            "operation": "hearing",
            "court_selector": _required_text(court, "court"),
            "division_code": division_code,
            "hearing_date_source": source_hearing_date,
            "hearing_time": _text(hearing_time),
            "courtroom": _text(courtroom),
            "hearing_type": hearing_type_code,
            "status_code": "A",
        }
        return self._search(
            criteria,
            limit=limit,
            cursor=cursor,
            max_pages=max_pages,
        )

    def search_service(
        self,
        court: Any,
        last_name: Any,
        *,
        division: Any = "civil",
        first_name: Any = None,
        middle_name: Any = None,
        suffix: Any = None,
        limit: int | None = None,
        cursor: str | None = None,
        max_pages: int | None = None,
    ) -> SearchFetch:
        division_code = _division_code(division)
        criteria = {
            "source_id": SOURCE_ID,
            "operation": "service",
            "court_selector": _required_text(court, "court"),
            "division_code": division_code,
            "last_name": _required_text(last_name, "last_name"),
            "first_name": _text(first_name),
            "middle_name": _text(middle_name),
            "suffix": _text(suffix),
            "status_code": "S",
        }
        return self._search(
            criteria,
            limit=limit,
            cursor=cursor,
            max_pages=max_pages,
        )

    def get_case(
        self,
        court: Any,
        case_number: Any,
        *,
        division: Any = "civil",
    ) -> Mapping[str, Any] | None:
        division_code = _division_code(division)
        raw_case_number = _required_text(case_number, "case_number")
        court_option = self._select_court(court)
        form = self._open_search_form(
            "case",
            division_code,
            court_option,
        )
        form_url = _response_url(form, CASE_NUMBER_SEARCH_URL)
        response = self._request(
            "POST",
            CASE_NUMBER_SEARCH_URL,
            data={
                "formAction": "submitCase",
                "searchFipsCode": court_option.source_code,
                "searchDivision": division_code,
                "searchType": "caseNumber",
                "displayCaseNumber": raw_case_number,
                "localFipsCode": court_option.source_code,
            },
            referer=form_url,
        )
        response_url = _response_url(response, CASE_NUMBER_SEARCH_URL)
        return parse_case_detail(
            response.text,
            division=division_code,
            court=court_option,
            source_url=response_url,
            requested_case_number=raw_case_number,
        )

    def probe(self, court: Any = "013") -> tuple[Mapping[str, Any], ...]:
        """Verify terms, court options, selected-court routes, and both forms."""

        courts = self.start()
        court_option = self._select_court(court)
        selected_soup = BeautifulSoup(
            self._welcome_html or "",
            "html.parser",
        )
        route_labels: list[str] = []
        route_hrefs: list[str] = []
        for link in selected_soup.select('a[name="moduleLink"][href]'):
            if not isinstance(link, Tag):
                continue
            route_labels.append(
                _text(link.get("aria-label"))
                or _text(link.get_text(" ", strip=True))
                or ""
            )
            route_hrefs.append(str(link["href"]))
        civil_case_form = self._open_search_form(
            "case",
            "V",
            court_option,
        )
        traffic_case_form = self._open_search_form(
            "case",
            "T",
            court_option,
        )
        hearing_form = self._open_search_form(
            "hearing",
            "V",
            court_option,
        )
        hearing_soup = BeautifulSoup(hearing_form.text, "html.parser")
        hearing_options: list[dict[str, str]] = []
        for option in hearing_soup.select('select[name="searchHearingType"] option'):
            if not isinstance(option, Tag):
                continue
            code = str(option.get("value", ""))
            label = _text(option.get_text(" ", strip=True)) or ""
            if code:
                hearing_options.append({"code": code, "source_label": label})
        build_match = re.search(
            r"Build\s*#:\s*([0-9.]+)",
            _page_text(selected_soup),
            flags=re.IGNORECASE,
        )
        return (
            {
                "canonical_ref": f"VA-GDC:PROBE:{court_option.source_code}",
                "source_id": SOURCE_ID,
                "record_kind": "source_probe",
                "status": "ok",
                "terms_state": self.terms_state,
                "verification_required": False,
                "court_component_count": len(courts),
                "selected_court": court_option.to_record(source_url=self._welcome_url),
                "selected_court_route_labels": route_labels,
                "selected_court_route_hrefs": route_hrefs,
                "civil_case_form_present": (
                    "criminalCivilCaseSearchForm" in civil_case_form.text
                ),
                "traffic_criminal_case_form_present": (
                    "criminalCivilCaseSearchForm" in traffic_case_form.text
                ),
                "source_native_hearing_types": hearing_options,
                "application_build": (build_match.group(1) if build_match else None),
                "request_count": self.request_count,
                "native_page_size": NATIVE_PAGE_SIZE,
                "reported_total": None,
                "source_url": self._welcome_url,
            },
        )


def _route_record() -> dict[str, Any]:
    return {
        "canonical_ref": "VA-GDC:ROUTES",
        "source_id": SOURCE_ID,
        "record_kind": "source_route_manifest",
        "primary_route": {
            "url": LANDING_URL,
            "roles": [
                "court_component_listing",
                "civil_name_search",
                "traffic_criminal_name_search",
                "exact_case_number_search",
                "hearing_date_search",
                "service_process_name_search",
                "case_detail_metadata",
            ],
            "native_page_size": NATIVE_PAGE_SIZE,
            "reported_total": None,
            "completeness_basis": "Next control absent on final native page",
            "session_state": (
                "terms acceptance, cookie, selected court, and native paging"
            ),
            "filing_document_state": ("not published by this case-information source"),
            "help_url": HELP_URL,
            "name_search_syntax": {
                "wildcard": "*",
                "minimum_non_wildcard_characters": 2,
                "source_guidance": (
                    "Enter the name as it appears on the summons, warrant, or "
                    "civil pleading."
                ),
            },
        },
        "source_native_divisions": [
            {"code": code, "label": label} for code, label in DIVISION_NAMES.items()
        ],
        "source_native_name_statuses": [
            {
                "code": code,
                "label": label,
                "source_definition": {
                    "A": "Cases entered or heard after January 2007",
                    "I": "Cases entered or heard before January 2007",
                    "O": "Current and archived data",
                }[code],
            }
            for code, label in STATUS_NAMES.items()
            if code in {"A", "I", "O"}
        ],
        "source_native_hearing_types": [
            {"code": code, "label": label} for code, label in HEARING_TYPES if code
        ],
        "complementary_sources": list(COMPLEMENTARY_SOURCES),
        "official_methodology_sources": [
            {
                "name": "General District Court home",
                "url": GDC_HOME_URL,
            },
            {
                "name": "General District Court Manual",
                "url": GDC_MANUAL_URL,
            },
        ],
    }


def _search_record(
    record: Mapping[str, Any],
    *,
    fetched: SearchFetch,
    args: argparse.Namespace,
) -> dict[str, Any]:
    payload = dict(record)
    payload["search_metadata"] = {
        "native_page_size": NATIVE_PAGE_SIZE,
        "native_pages_fetched": fetched.pages_fetched,
        "replay_pages_fetched": fetched.replay_pages_fetched,
        "start_native_page": fetched.start_native_page,
        "end_native_page": fetched.end_native_page,
        "reported_total": None,
        "source_exhausted": fetched.source_exhausted,
        "completeness_basis": (
            "Next control absent"
            if fetched.source_exhausted
            else "continuation cursor returned"
        ),
        "schema_fingerprints": list(fetched.schema_fingerprints),
        "query_status_code": (
            STATUS_CODES[args.status]
            if args.command == "name"
            else ("A" if args.command == "hearing" else "S")
        ),
        "query_status_label": (
            STATUS_NAMES[STATUS_CODES[args.status]]
            if args.command == "name"
            else (STATUS_NAMES["A"] if args.command == "hearing" else STATUS_NAMES["S"])
        ),
    }
    return payload


def _search_result(
    query: PublicRecordsQuery,
    fetched: SearchFetch,
    args: argparse.Namespace,
) -> PublicRecordsResult:
    records = [
        _search_record(row, fetched=fetched, args=args) for row in fetched.records
    ]
    if fetched.error is not None:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [fetched.error.to_contract_error()],
            records=records,
            next_cursor=fetched.next_cursor,
            warnings=(
                *SOURCE_WARNINGS,
                "The source stopped before native paging was exhausted; "
                "returned records and the continuation cursor are preserved.",
            ),
        )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=fetched.next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    """Build the shared public-record query envelope."""

    command = args.command
    parameters: dict[str, Any]
    requested_limit: int | None = None
    cursor: str | None = None
    if command == "name":
        parameters = {
            "court": args.court,
            "division": args.division,
            "last_name_or_business": args.last_name_or_business,
            "first_name": args.first_name,
            "middle_name": args.middle_name,
            "suffix": args.suffix,
            "status": args.status,
            "max_pages": args.max_pages,
        }
        requested_limit = args.limit
        cursor = args.cursor
    elif command == "hearing":
        parameters = {
            "court": args.court,
            "division": args.division,
            "hearing_date": args.hearing_date,
            "hearing_time": args.hearing_time,
            "courtroom": args.courtroom,
            "hearing_type": args.hearing_type,
            "status": "current",
            "max_pages": args.max_pages,
        }
        requested_limit = args.limit
        cursor = args.cursor
    elif command == "service":
        parameters = {
            "court": args.court,
            "division": args.division,
            "last_name": args.last_name,
            "first_name": args.first_name,
            "middle_name": args.middle_name,
            "suffix": args.suffix,
            "source_status": "S",
            "max_pages": args.max_pages,
        }
        requested_limit = args.limit
        cursor = args.cursor
    elif command == "case":
        parameters = {
            "court": args.court,
            "division": args.division,
            "case_number": args.case_number,
            "status": "all",
        }
    elif command == "probe":
        parameters = {"court": args.court}
    else:
        parameters = {}
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _make_client(args: argparse.Namespace) -> VAGeneralDistrictClient:
    return VAGeneralDistrictClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        minimum_interval=args.minimum_interval,
    )


def _failure_result(
    query: PublicRecordsQuery,
    error: VAGeneralDistrictError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: VAGeneralDistrictClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one source-specific Virginia GDC operation."""

    query = build_query(args)
    source_client = client or _make_client(args)
    owns_client = client is None
    try:
        if args.command == "routes":
            result = PublicRecordsResult.success(
                query,
                [_route_record()],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "courts":
            result = PublicRecordsResult.success(
                query,
                source_client.courts(),
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "name":
            fetched = source_client.search_name(
                args.court,
                args.last_name_or_business,
                division=args.division,
                first_name=args.first_name,
                middle_name=args.middle_name,
                suffix=args.suffix,
                status=args.status,
                limit=args.limit,
                cursor=args.cursor,
                max_pages=args.max_pages,
            )
            result = _search_result(query, fetched, args)
        elif args.command == "hearing":
            fetched = source_client.search_hearing(
                args.court,
                args.hearing_date,
                division=args.division,
                hearing_time=args.hearing_time,
                courtroom=args.courtroom,
                hearing_type=args.hearing_type,
                limit=args.limit,
                cursor=args.cursor,
                max_pages=args.max_pages,
            )
            result = _search_result(query, fetched, args)
        elif args.command == "service":
            fetched = source_client.search_service(
                args.court,
                args.last_name,
                division=args.division,
                first_name=args.first_name,
                middle_name=args.middle_name,
                suffix=args.suffix,
                limit=args.limit,
                cursor=args.cursor,
                max_pages=args.max_pages,
            )
            result = _search_result(query, fetched, args)
        elif args.command == "case":
            record = source_client.get_case(
                args.court,
                args.case_number,
                division=args.division,
            )
            result = PublicRecordsResult.success(
                query,
                [] if record is None else [record],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            result = PublicRecordsResult.success(
                query,
                source_client.probe(args.court),
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise VAGDCSelectionError(
                "unsupported_command",
                f"unsupported Virginia GDC command: {args.command}",
            )
    except VAGeneralDistrictError as error:
        result = _failure_result(query, error)
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
            warnings=SOURCE_WARNINGS,
        )
    finally:
        if owns_client:
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
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Virginia GDC {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Virginia GDC {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        label = (
            record.get("raw_case_number")
            or record.get("court_name")
            or record.get("record_kind")
        )
        print(f"  {label}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Per-request timeout in seconds",
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
        help="Minimum seconds between source requests",
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_int,
        default=3,
        help="Maximum attempts for transient source failures",
    )
    add_output_args(parser)


def _add_division(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--division",
        choices=("civil", "traffic-criminal"),
        default="civil",
        help="Source division",
    )


def _add_name_parts(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--first-name")
    parser.add_argument("--middle-name")
    parser.add_argument("--suffix")


def _add_paging(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=None,
        help="Maximum records to return; omitted means exhaust native pages",
    )
    parser.add_argument(
        "--cursor",
        help="Replayable continuation cursor returned by a prior query",
    )
    parser.add_argument(
        "--max-pages",
        type=_positive_int,
        default=None,
        help=(
            "Optional native-page bound for this invocation; a continuation "
            "cursor is returned when more pages exist"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Virginia General District Court civil, traffic, and "
            "criminal case information"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    routes = subparsers.add_parser(
        "routes",
        help="Show primary and distinct complementary official sources",
    )
    _add_runtime_and_output(routes)

    courts = subparsers.add_parser(
        "courts",
        help="List live source-published court components and codes",
    )
    _add_runtime_and_output(courts)

    name = subparsers.add_parser(
        "name",
        help="Search cases by party or business name",
    )
    name.add_argument("court", help="Court source code, name, or unique fragment")
    name.add_argument("last_name_or_business")
    _add_division(name)
    _add_name_parts(name)
    name.add_argument(
        "--status",
        choices=tuple(STATUS_CODES),
        default="current",
        help="Source-native data status",
    )
    _add_paging(name)
    _add_runtime_and_output(name)

    hearing = subparsers.add_parser(
        "hearing",
        help="Search current cases by hearing date",
    )
    hearing.add_argument(
        "court",
        help="Court source code, name, or unique fragment",
    )
    hearing.add_argument("hearing_date", help="YYYY-MM-DD or MM/DD/YYYY")
    _add_division(hearing)
    hearing.add_argument("--hearing-time", help="Source format, e.g. 0930AM")
    hearing.add_argument("--courtroom")
    hearing.add_argument(
        "--hearing-type",
        choices=tuple(code for code, _label in HEARING_TYPES if code),
    )
    _add_paging(hearing)
    _add_runtime_and_output(hearing)

    service = subparsers.add_parser(
        "service",
        help="Search service/process records by person name",
    )
    service.add_argument(
        "court",
        help="Court source code, name, or unique fragment",
    )
    service.add_argument("last_name")
    _add_division(service)
    _add_name_parts(service)
    _add_paging(service)
    _add_runtime_and_output(service)

    case = subparsers.add_parser(
        "case",
        help="Fetch one full case-detail record by exact case number",
    )
    case.add_argument(
        "court",
        help="Court source code, name, or unique fragment",
    )
    case.add_argument("case_number")
    _add_division(case)
    _add_runtime_and_output(case)

    probe = subparsers.add_parser(
        "probe",
        help="Verify terms, court options, routes, and both case forms",
    )
    probe.add_argument(
        "--court",
        default="013",
        help="Court source code, name, or unique fragment",
    )
    _add_runtime_and_output(probe)
    return parser


def main() -> int:
    args = build_parser().parse_args()
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
