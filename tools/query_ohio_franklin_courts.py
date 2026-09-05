#!/usr/bin/env python3
"""Query Franklin County, Ohio Case Information Online (CIO).

CIO is the official Franklin County Clerk of Courts public case portal.  An
exact case-number lookup returns case summary, parties, schedule, docket
chronology, and links to public filing PDFs.  The docket uses a source-native
next-key protocol; this adapter follows it until the source reports no next
page.

Examples:
    uv run python tools/query_ohio_franklin_courts.py source --json
    uv run python tools/query_ohio_franklin_courts.py name WEXNER \
        --court civil --filed-from 2020-01-01 --filed-to 2022-12-31 \
        --exhaustive --output /tmp/franklin-party.json
    uv run python tools/query_ohio_franklin_courts.py case 22CV3098 \
        --output /tmp/franklin-case.json
    uv run python tools/query_ohio_franklin_courts.py document \
        22CV3098 franklin:document:0123456789abcdef01234567 \
        /tmp/franklin-filing.pdf --output /tmp/franklin-document.json
    uv run python tools/query_ohio_franklin_courts.py probe --json
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import time
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from email.message import Message
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urljoin, urlsplit

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


OBSERVED_AT = "2026-07-30"
SOURCE_ID = "us-oh-franklin-common-pleas-cio"
COURT_ID = "oh-franklin-common-pleas"
COURT_NAME = "Franklin County Court of Common Pleas"
STATE_CODE = "OH"
COUNTY_FIPS = "39049"
BASE_URL = "https://fcdcfcjs.co.franklin.oh.us/CaseInformationOnline/"
OFFICIAL_HOST = "fcdcfcjs.co.franklin.oh.us"
CASE_SEARCH_URL = urljoin(BASE_URL, "caseSearch?exactCaseLookup")
NAME_SEARCH_URL = urljoin(BASE_URL, "nameSearch")
DOCKET_URL = urljoin(BASE_URL, "docket")
DOCUMENT_URL = urljoin(BASE_URL, "imageLinkProcessor.pdf")
COURT_SCHEDULE_URL = urljoin(BASE_URL, "CourtScheduleInquiry.jsp")
PLATFORM_FAMILY = "franklin_cio_ibm_jsp_servlet"
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)
PROBE_CASE_NUMBER = "22CV3098"
PROBE_PARTY_LAST_NAME = "WEXNER"
PROBE_PARTY_CASE_NUMBER = "20CV003259"
PROBE_PARTY_COURT = "civil"
PROBE_PARTY_FILED_DATE = date(2020, 5, 19)
PROBE_PARTY_NATIVE_ROW_COUNT = 25

NATIVE_ROW_COUNTS = (25, 50, 100, 150, 200, 250, 300, 350)
DEFAULT_NATIVE_ROW_COUNT = 250
COURT_CATEGORY_VALUES = {
    "all": " ",
    "appeals": "Appeals",
    "civil": "Civil",
    "criminal": "Criminal",
    "domestic": "Domestic",
}
PARTY_RESULT_COLUMNS = (
    "CASE",
    "CASE TYPE",
    "NAME",
    "ITN",
    "MALE/FEMALE",
    "PLAINTIFF/DEFENDANT",
    "DATE OF BIRTH",
    "DESCRIPTION",
    "FILED",
    "STATUS",
    "SUBSCRIBE",
)

_CASE_NUMBER_RE = re.compile(
    r"^(?P<year>\d{2}|\d{4})(?P<case_type>[A-Za-z]{2})(?P<sequence>\d+)$"
)
_IMAGE_DECLARATION_RE = re.compile(
    r"images\[['\"](?P<key>[^'\"]+)['\"]\]\s*=\s*"
    r"encodeURIComponent\(['\"](?P<value>[^'\"]+)['\"]\)\s*;"
)
_IMAGE_LINK_RE = re.compile(
    r"openImageLink\(\s*['\"](?P<key>[^'\"]+)['\"]\s*\)"
)

CASE_TYPE_LABELS = {
    "AP": "appeals",
    "CV": "civil",
    "EX": "certificate_of_judgment_execution",
    "JG": "judgment",
    "LP": "lien_or_miscellaneous_civil",
    "MS": "miscellaneous",
    "CR": "criminal",
    "EP": "expungement_or_sealing",
    "MI": "miscellaneous",
    "DM": "domestic",
    "DR": "domestic_relations",
    "MC": "municipal_appeal_or_miscellaneous",
}

DOCKET_CATEGORY_LABELS = {
    "A": "attorney_appearances_appointments_withdrawals",
    "B": "bonds",
    "C": "continuances_scheduled_hearings",
    "D": "decisions_orders",
    "E": "foreclosures",
    "F": "financials",
    "G": "garnishments",
    "H": "complaints",
    "J": "judge_assignments_transfers",
    "M": "motions",
    "N": "answers",
    "O": "administrative_appeals",
    "P": "miscellaneous_papers",
    "S": "service",
    "T": "terminations_dismissals_stay",
    "W": "writs",
    "X": "arbitration",
    "Y": "temporary_restraining_orders",
    "Z": "conversion_costs_deposits",
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Franklin County Clerk of Courts Case Information Online",
    source_role="county_common_pleas_case_docket_schedule_and_public_filings",
    base_url=BASE_URL,
    dataset_id="franklin-cio",
    metadata={
        "authority": "Franklin County Clerk of Courts",
        "county_fips": COUNTY_FIPS,
        "platform_family": PLATFORM_FAMILY,
        "authentication": "none",
        "disclaimer_session": True,
        "party_name_lookup": True,
        "party_name_semantics": "ordered_lower_bound_index_window",
        "exact_case_lookup": True,
        "native_docket_pagination": "next_key_post",
        "observed_at": OBSERVED_AT,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_FIPS,
    name="Franklin County, Ohio",
    state_code=STATE_CODE,
    county_fips=COUNTY_FIPS,
    locality="Franklin County",
)

SOURCE_WARNINGS = (
    "CIO describes its online material as a copy rather than the official "
    "court file; certified or official copies remain a Clerk function.",
    "CIO name results are an ordered lower-bound index window rather than an "
    "exact-match set; each emitted occurrence identifies whether it matches "
    "the requested prefix.",
    "A court confirmation-of-sale filing can corroborate a sheriff auction, "
    "but a recorded deed is the stronger source for a completed title transfer.",
)

SOURCE_CAPABILITIES: Mapping[str, Any] = {
    "record_kind": "source_capabilities",
    "source_id": SOURCE_ID,
    "platform_family": PLATFORM_FAMILY,
    "observed_at": OBSERVED_AT,
    "routes": [
        {
            "role": "party_name_index",
            "method": "POST",
            "path": "/CaseInformationOnline/nameSearch",
            "matching": "ordered_lower_bound_index_window",
            "pagination": None,
            "native_row_counts": list(NATIVE_ROW_COUNTS),
            "implemented": True,
        },
        {
            "role": "case_index_and_detail",
            "method": "POST",
            "path": "/CaseInformationOnline/caseSearch",
            "join_key": "normalized_case_number",
            "implemented": True,
        },
        {
            "role": "docket_chronology",
            "method": "POST",
            "path": "/CaseInformationOnline/docket",
            "pagination": "source_next_key_until_empty",
            "implemented": True,
        },
        {
            "role": "filed_document_copy",
            "method": "GET",
            "path": "/CaseInformationOnline/imageLinkProcessor.pdf",
            "selector": "session_document_coordinates",
            "implemented": True,
        },
        {
            "role": "court_calendar",
            "method": "POST",
            "path": "/CaseInformationOnline/courtSchedule",
            "landing_path": "/CaseInformationOnline/CourtScheduleInquiry.jsp",
            "implemented": False,
        },
        {
            "role": "case_email_updates",
            "method": "GET",
            "path": "/CaseInformationOnline/caseWatch",
            "implemented": False,
            "note": "notification signup, not an observed data feed",
        },
        {
            "role": "official_or_certified_copy",
            "method": "request",
            "url": (
                "https://clerk.franklincountyohio.gov/"
                "Public-Records/Public-Records-Request-Form"
            ),
            "implemented": False,
        },
    ],
    "cross_source_joins": [
        {
            "source": "Franklin County Sheriff RealAuction",
            "key": "case_number",
            "normalization_example": {
                "auction_raw": "22CV3098",
                "cio_normalized": "22CV003098",
            },
        },
        {
            "source": "Franklin County Recorder",
            "keys": [
                "parcel_number",
                "property_address",
                "purchaser_or_grantee",
                "legal_description",
                "court_case_number_when_carried_forward",
            ],
            "note": (
                "The court case number is not itself a recorder instrument "
                "number; the sheriff deed creates the recorder-side identity."
            ),
        },
    ],
}


class FranklinCourtError(RuntimeError):
    """Base error with public-record result semantics."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "franklin_court_error",
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


class FranklinSourceChangedError(FranklinCourtError):
    """CIO no longer matches its verified response contract."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "franklin_source_changed",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details=details,
        )


class FranklinCaseNotFoundError(FranklinCourtError):
    """An exact case-number query returned the source's empty state."""

    def __init__(self, case_number: str) -> None:
        super().__init__(
            f"Franklin County case not found: {case_number}",
            code="case_not_found",
            status=ResultStatus.NO_RESULTS,
            category="not_found",
            details={"case_number": case_number},
        )


class FranklinSelectionError(FranklinCourtError):
    """A requested document identity does not resolve in the current case."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status=ResultStatus.UNAVAILABLE,
            category="query_selection",
            details=details,
        )


@dataclass(frozen=True)
class FranklinCaseNumber:
    """Source-native case-number components plus caller spelling."""

    input_raw: str
    year: str
    case_type: str
    sequence_raw: str
    sequence_normalized: str
    normalized: str


@dataclass(frozen=True)
class FranklinPartySearchSpec:
    """Normalized caller selectors for one CIO party-index search."""

    last_name: str
    first_name: str | None
    middle_initial: str | None
    court_category: str
    filed_from: date | None
    filed_to: date | None
    native_row_count: int
    exhaustive: bool


@dataclass(frozen=True)
class FranklinPartyWindowSpec:
    """One non-overlapping native party-index window."""

    last_name: str
    first_name: str | None
    middle_initial: str | None
    court_category: str
    filed_from: date | None
    filed_to: date | None
    native_row_count: int


@dataclass(frozen=True)
class ParsedPartySearchWindow:
    """Parsed party rows and completeness signals for one response."""

    records: Sequence[Mapping[str, Any]]
    query_fingerprint: str
    requested_native_row_count: int
    source_row_count: int
    complete_row_count: int
    incomplete_row_count: int
    matched_row_count: int
    coverage_complete: bool
    completion_reason: str | None
    ended_in_matching_rows: bool
    source_buffer_truncated: bool
    result_field_names: tuple[str, ...]
    window: Mapping[str, Any]


@dataclass(frozen=True)
class FranklinPartySearch:
    """Terminal name-index windows and their raw row observations."""

    records: Sequence[Mapping[str, Any]]
    windows: Sequence[ParsedPartySearchWindow]
    coverage_complete: bool
    unresolved_windows: Sequence[Mapping[str, Any]]
    source_buffer_truncated: bool


@dataclass(frozen=True)
class ParsedCaseDetail:
    """Initial CIO case response before subsequent docket pages are fetched."""

    record: Mapping[str, Any]
    docket_rows: Sequence[Mapping[str, Any]]
    next_docket_key: str | None


@dataclass(frozen=True)
class FranklinCasePage:
    """Normalized case plus in-session document coordinates."""

    record: Mapping[str, Any]
    document_coordinates: Mapping[str, str]


@dataclass(frozen=True)
class FranklinPDF:
    """A filing response validated as an official-host PDF."""

    content: bytes
    media_type: str
    filename: str
    sha256: str
    final_host: str
    resolved_path: str


@dataclass(frozen=True)
class FranklinDocumentFetch:
    """Case context and one selected public document."""

    case_page: FranklinCasePage
    document_id: str
    pdf: FranklinPDF


@dataclass(frozen=True)
class FranklinProbeSnapshot:
    """Fixed-cost source contract sample without transport secrets."""

    record: Mapping[str, Any]
    disclaimer_path: str
    disclaimer_method: str
    disclaimer_field_names: tuple[str, ...]
    party_search_field_names: tuple[str, ...]
    party_result_field_names: tuple[str, ...]
    party_sentinel_case_number: str
    party_matching_count: int
    party_coverage_complete: bool
    case_search_field_names: tuple[str, ...]
    docket_request_field_names: tuple[str, ...]
    docket_response_field_names: tuple[str, ...]
    initial_next_key_present: bool
    continuation_next_key_present: bool
    request_count: int


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\x00", "").split())
    return normalized or None


def _element_text(element: Tag | None) -> str | None:
    if element is None:
        return None
    return _text(element.get_text(" ", strip=True))


def _multiline_element_text(element: Tag | None) -> str | None:
    if element is None:
        return None
    lines = [
        _text(line)
        for line in element.get_text("\n", strip=True).splitlines()
    ]
    return " | ".join(line for line in lines if line) or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise FranklinSourceChangedError(
            f"Franklin CIO response lacks {field_name}",
            code="required_field_missing",
            details={"field": field_name},
        )
    return normalized


def parse_case_number(value: str) -> FranklinCaseNumber:
    """Parse a Franklin case selector without discarding caller spelling."""

    input_raw = str(value).strip()
    compact = re.sub(r"[\s._/-]+", "", input_raw)
    match = _CASE_NUMBER_RE.fullmatch(compact)
    if match is None:
        raise ValueError(
            "Franklin case number must contain a 2- or 4-digit year, "
            "2-letter case type, and numeric sequence"
        )

    year = match.group("year")
    if len(year) == 4:
        full_year = int(year)
        if full_year < 2000 or full_year > 2099:
            raise ValueError(
                "Franklin CIO's two-digit year field can map four-digit "
                "selectors only within 2000-2099"
            )
        year = year[-2:]
    case_type = match.group("case_type").upper()
    sequence_raw = match.group("sequence")
    sequence_normalized = sequence_raw.lstrip("0") or "0"
    sequence_normalized = sequence_normalized.zfill(6)
    return FranklinCaseNumber(
        input_raw=input_raw,
        year=year,
        case_type=case_type,
        sequence_raw=sequence_raw,
        sequence_normalized=sequence_normalized,
        normalized=f"{year}{case_type}{sequence_normalized}",
    )


def _party_selector(
    value: Any,
    *,
    field_name: str,
    maximum_length: int,
    required: bool = False,
) -> str | None:
    normalized = _text(value)
    if normalized is None:
        if required:
            raise FranklinSelectionError(
                "party_selector_required",
                f"Franklin CIO party search requires {field_name}",
                details={"field": field_name},
            )
        return None
    normalized = normalized.upper()
    if len(normalized) > maximum_length:
        raise FranklinSelectionError(
            "party_selector_too_long",
            f"Franklin CIO {field_name} exceeds its native field length",
            details={
                "field": field_name,
                "maximum_length": maximum_length,
            },
        )
    return normalized


def _party_date_bound(value: date | datetime | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = _text(value)
    if raw is None:
        return None
    for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, date_format).date()
        except ValueError:
            continue
    raise FranklinSelectionError(
        "party_date_invalid",
        "Franklin CIO filed dates must use YYYY-MM-DD or MM/DD/YYYY",
        details={"value": raw},
    )


def build_party_search_spec(
    *,
    last_name: str,
    first_name: str | None = None,
    middle_initial: str | None = None,
    court_category: str = "all",
    filed_from: date | datetime | str | None = None,
    filed_to: date | datetime | str | None = None,
    native_row_count: int = DEFAULT_NATIVE_ROW_COUNT,
    exhaustive: bool = False,
) -> FranklinPartySearchSpec:
    """Validate and normalize one public CIO party search."""

    normalized_last = _party_selector(
        last_name,
        field_name="last name",
        maximum_length=25,
        required=True,
    )
    normalized_first = _party_selector(
        first_name,
        field_name="first name",
        maximum_length=14,
    )
    normalized_middle = _party_selector(
        middle_initial,
        field_name="middle initial",
        maximum_length=1,
    )
    if normalized_middle is not None and normalized_first is None:
        raise FranklinSelectionError(
            "party_middle_requires_first",
            "Franklin CIO middle initial requires a first-name selector",
        )
    normalized_court = (_text(court_category) or "all").lower()
    if normalized_court not in COURT_CATEGORY_VALUES:
        raise FranklinSelectionError(
            "party_court_invalid",
            "Franklin CIO court category is not recognized",
            details={
                "court_category": normalized_court,
                "choices": sorted(COURT_CATEGORY_VALUES),
            },
        )
    if native_row_count not in NATIVE_ROW_COUNTS:
        raise FranklinSelectionError(
            "party_native_row_count_invalid",
            "Franklin CIO native row count is not one of the published options",
            details={
                "native_row_count": native_row_count,
                "choices": list(NATIVE_ROW_COUNTS),
            },
        )
    normalized_from = _party_date_bound(filed_from)
    normalized_to = _party_date_bound(filed_to)
    if (
        normalized_from is not None
        and normalized_to is not None
        and normalized_from > normalized_to
    ):
        raise FranklinSelectionError(
            "party_date_range_invalid",
            "Franklin CIO filed-from date must not follow filed-to date",
            details={
                "filed_from": normalized_from.isoformat(),
                "filed_to": normalized_to.isoformat(),
            },
        )
    return FranklinPartySearchSpec(
        last_name=normalized_last or "",
        first_name=normalized_first,
        middle_initial=normalized_middle,
        court_category=normalized_court,
        filed_from=normalized_from,
        filed_to=normalized_to,
        native_row_count=native_row_count,
        exhaustive=bool(exhaustive),
    )


def _party_window_from_spec(
    spec: FranklinPartySearchSpec,
) -> FranklinPartyWindowSpec:
    return FranklinPartyWindowSpec(
        last_name=spec.last_name,
        first_name=spec.first_name,
        middle_initial=spec.middle_initial,
        court_category=spec.court_category,
        filed_from=spec.filed_from,
        filed_to=spec.filed_to,
        native_row_count=spec.native_row_count,
    )


def _party_window_payload(
    window: FranklinPartyWindowSpec,
) -> dict[str, Any]:
    return {
        "last_name": window.last_name,
        "first_name": window.first_name,
        "middle_initial": window.middle_initial,
        "court_category": window.court_category,
        "filed_from": (
            window.filed_from.isoformat()
            if window.filed_from is not None
            else None
        ),
        "filed_to": (
            window.filed_to.isoformat()
            if window.filed_to is not None
            else None
        ),
        "native_row_count": window.native_row_count,
    }


def _party_query_prefix(window: FranklinPartyWindowSpec) -> str:
    prefix = window.last_name
    if window.first_name is not None:
        prefix = f"{prefix}, {window.first_name}"
    if window.middle_initial is not None:
        prefix = f"{prefix} {window.middle_initial}"
    return prefix


def _source_date(
    value: Any,
    *,
    field_name: str,
    date_format: str,
    required: bool = False,
) -> tuple[str | None, str | None]:
    raw = _text(value)
    if raw is None:
        if required:
            raise FranklinSourceChangedError(
                f"Franklin CIO response lacks {field_name}",
                code="required_field_missing",
                details={"field": field_name},
            )
        return None, None
    try:
        normalized = datetime.strptime(raw, date_format).date().isoformat()
    except ValueError as error:
        raise FranklinSourceChangedError(
            f"Franklin CIO returned an unparseable {field_name}: {raw!r}",
            code="date_parse_failed",
            details={"field": field_name, "value": raw},
        ) from error
    return raw, normalized


def _court_payload() -> dict[str, Any]:
    return {
        "court_id": COURT_ID,
        "native_court_id": "franklin-common-pleas",
        "name": COURT_NAME,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_FIPS,
        "court_level": "common_pleas",
        "official_url": BASE_URL,
    }


def parse_disclaimer_action(
    html: str,
    *,
    response_url: str = BASE_URL,
) -> str:
    """Resolve CIO's per-session disclaimer acceptance action."""

    soup = BeautifulSoup(html, "html.parser")
    form = soup.find(
        "form",
        action=lambda value: bool(
            value and "/CaseInformationOnline/acceptDisclaimer" in value
        ),
    )
    if not isinstance(form, Tag):
        raise FranklinSourceChangedError(
            "Franklin CIO landing page lacks its disclaimer form",
            code="disclaimer_form_missing",
        )
    action = _required_text(form.get("action"), "disclaimer action")
    resolved = urljoin(response_url, action)
    parsed = urlsplit(resolved)
    if (
        parsed.scheme != "https"
        or parsed.hostname != OFFICIAL_HOST
        or parsed.path
        != "/CaseInformationOnline/acceptDisclaimer"
    ):
        raise FranklinSourceChangedError(
            "Franklin CIO disclaimer action resolved outside its verified route",
            code="disclaimer_action_changed",
            details={
                "scheme": parsed.scheme,
                "host": parsed.hostname,
                "path": parsed.path,
            },
        )
    return resolved


def _party_result_table(
    soup: BeautifulSoup,
) -> tuple[Tag | None, tuple[str, ...]]:
    for table in soup.find_all("table"):
        headers = tuple(
            _element_text(header) or ""
            for header in table.find_all("th")
        )
        if headers == PARTY_RESULT_COLUMNS:
            return table, headers
    return None, ()


def parse_party_search_results(
    html: str,
    *,
    window: FranklinPartyWindowSpec,
) -> ParsedPartySearchWindow:
    """Parse a native lower-bound party-index window without deduplication."""

    window_payload = _party_window_payload(window)
    query_fingerprint = hashlib.sha256(
        canonical_json(window_payload).encode("utf-8")
    ).hexdigest()
    soup = BeautifulSoup(html, "html.parser")
    table, result_fields = _party_result_table(soup)
    page_text = (_text(soup.get_text(" ", strip=True)) or "").lower()
    if table is None:
        disclaimer_form = soup.find(
            "form",
            action=lambda value: bool(
                value
                and "/CaseInformationOnline/acceptDisclaimer" in value
            ),
        )
        if isinstance(disclaimer_form, Tag):
            raise FranklinCourtError(
                "Franklin CIO party session returned to its disclaimer",
                code="party_session_expired",
                status=ResultStatus.RESTRICTED,
                category="access",
            )
        if any(
            marker in page_text
            for marker in (
                "no case matched the search criteria",
                "no cases found",
                "no records found",
                "no matches found",
            )
        ):
            return ParsedPartySearchWindow(
                records=(),
                query_fingerprint=query_fingerprint,
                requested_native_row_count=window.native_row_count,
                source_row_count=0,
                complete_row_count=0,
                incomplete_row_count=0,
                matched_row_count=0,
                coverage_complete=True,
                completion_reason="authoritative_empty_state",
                ended_in_matching_rows=False,
                source_buffer_truncated=False,
                result_field_names=(),
                window=window_payload,
            )
        raise FranklinSourceChangedError(
            "Franklin CIO party response lacks its verified case-listing table",
            code="party_result_table_missing",
        )

    body = table.find("tbody")
    if not isinstance(body, Tag):
        raise FranklinSourceChangedError(
            "Franklin CIO party result table lacks a tbody",
            code="party_result_body_missing",
        )

    query_prefix = _party_query_prefix(window)
    rows = body.find_all("tr", recursive=False)
    records: list[dict[str, Any]] = []
    incomplete_row_count = 0
    later_nonmatching_seen = False
    matching_seen = False
    for response_ordinal, row in enumerate(rows, start=1):
        cells = row.find_all("td", recursive=False)
        if len(cells) != len(PARTY_RESULT_COLUMNS):
            incomplete_row_count += 1
            continue
        case_submit = row.find("input", attrs={"name": "alinkvalue"})
        if not isinstance(case_submit, Tag):
            incomplete_row_count += 1
            continue
        display_case_number = _required_text(
            case_submit.get("value"),
            "party result case number",
        )
        parsed_case = parse_case_number(display_case_number)
        checkbox = row.find("input", attrs={"name": "caseNumber"})
        source_case_number = (
            _text(checkbox.get("value"))
            if isinstance(checkbox, Tag)
            else None
        )
        if source_case_number is not None:
            checkbox_case = parse_case_number(source_case_number)
            if checkbox_case.normalized != parsed_case.normalized:
                raise FranklinSourceChangedError(
                    "Franklin CIO party row case selectors disagree",
                    code="party_case_number_conflict",
                    details={
                        "display": display_case_number,
                        "checkbox": source_case_number,
                    },
                )

        raw_values = [
            _element_text(cell)
            for cell in cells
        ]
        raw_name = _required_text(raw_values[2], "party result name")
        normalized_name = raw_name.upper()
        matched_query = normalized_name.startswith(query_prefix)
        if matched_query:
            matching_seen = True
        elif normalized_name > query_prefix and (
            matching_seen or not records
        ):
            later_nonmatching_seen = True
        filing_date_raw, filing_date = _source_date(
            raw_values[8],
            field_name="party result filed date",
            date_format="%m/%d/%Y",
            required=True,
        )
        native_occurrence_id = (
            "franklin:party-index:"
            f"{query_fingerprint[:24]}:{response_ordinal:06d}"
        )
        raw_row = {
            "case": display_case_number,
            "case_type": raw_values[1],
            "name": raw_name,
            "itn": raw_values[3],
            "sex": raw_values[4],
            "party_role": raw_values[5],
            "date_of_birth": raw_values[6],
            "description": raw_values[7],
            "filed": filing_date_raw,
            "status": raw_values[9],
            "subscribe_case_number": source_case_number,
        }
        records.append(
            {
                "record_kind": "case_index_occurrence",
                "source_id": SOURCE_ID,
                "court": _court_payload(),
                "normalized_case_number": parsed_case.normalized,
                "display_case_number": display_case_number,
                "native_occurrence_id": native_occurrence_id,
                "raw_name": raw_name,
                "party_role": raw_values[5],
                "filing_date_raw": filing_date_raw,
                "filing_date": filing_date,
                "status": raw_values[9],
                "case_type": raw_values[1],
                "case_type_code": parsed_case.case_type,
                "case_type_family": CASE_TYPE_LABELS.get(
                    parsed_case.case_type
                ),
                "case_description": raw_values[7],
                "itn": raw_values[3],
                "sex": raw_values[4],
                "date_of_birth_raw": raw_values[6],
                "matched_query": matched_query,
                "response_ordinal": response_ordinal,
                "query_fingerprint": query_fingerprint,
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    parsed_case.normalized,
                ),
                "source_url": NAME_SEARCH_URL,
                "access_state": "public",
                "native_access_state": (
                    "anonymous CIO ordered party-index observation"
                ),
                "raw": raw_row,
                "source_metadata": {
                    "matching_semantics": (
                        "ordered_lower_bound_index_window"
                    ),
                    "native_row_id_published": False,
                    "observation_identity": (
                        "query_fingerprint_plus_response_ordinal"
                    ),
                    "window": window_payload,
                },
            }
        )

    matched_row_count = sum(
        1 for record in records if record["matched_query"]
    )
    ended_in_matching_rows = bool(records) and bool(
        records[-1]["matched_query"]
    )
    if not rows:
        coverage_complete = True
        completion_reason = "authoritative_empty_table"
    elif later_nonmatching_seen:
        coverage_complete = True
        completion_reason = "ordered_spillover"
    else:
        coverage_complete = False
        completion_reason = None
    return ParsedPartySearchWindow(
        records=tuple(records),
        query_fingerprint=query_fingerprint,
        requested_native_row_count=window.native_row_count,
        source_row_count=len(rows),
        complete_row_count=len(records),
        incomplete_row_count=incomplete_row_count,
        matched_row_count=matched_row_count,
        coverage_complete=coverage_complete,
        completion_reason=completion_reason,
        ended_in_matching_rows=ended_in_matching_rows,
        source_buffer_truncated=incomplete_row_count > 0,
        result_field_names=result_fields,
        window=window_payload,
    )


def parse_image_coordinates(html: str) -> dict[str, str]:
    """Extract document-slot coordinates from CIO's page-local JavaScript."""

    coordinates: dict[str, str] = {}
    for match in _IMAGE_DECLARATION_RE.finditer(html):
        key = match.group("key")
        value = match.group("value")
        prior = coordinates.get(key)
        if prior is not None and prior != value:
            raise FranklinSourceChangedError(
                "Franklin CIO reused a document slot with conflicting values",
                code="document_slot_conflict",
                details={"slot": key},
            )
        coordinates[key] = value
    return coordinates


def _detail_payload(detail_row: Tag | None) -> dict[str, Any]:
    if not isinstance(detail_row, Tag):
        return {"fields": [], "text": None}
    fields: list[dict[str, str | None]] = []
    table = detail_row.find("table")
    if isinstance(table, Tag):
        for row in table.find_all("tr", recursive=False):
            cells = row.find_all("td", recursive=False)
            if len(cells) < 2:
                continue
            fields.append(
                {
                    "label": (_element_text(cells[0]) or "").rstrip(":") or None,
                    "value": _multiline_element_text(cells[1]),
                }
            )
    text = _multiline_element_text(detail_row)
    return {"fields": fields, "text": text}


def parse_docket_rows(
    fragment_html: str,
    *,
    image_coordinates: Mapping[str, str],
    source_page_no: int,
) -> list[dict[str, Any]]:
    """Parse one CIO docket tbody fragment without assigning identities."""

    soup = BeautifulSoup(
        f"<table><tbody>{fragment_html}</tbody></table>",
        "html.parser",
    )
    body = soup.find("tbody")
    if not isinstance(body, Tag):
        raise FranklinSourceChangedError(
            "Franklin CIO docket response lacks a tbody",
            code="docket_body_missing",
        )
    rows = body.find_all("tr", recursive=False)
    parsed: list[dict[str, Any]] = []
    main_sequence = 0
    for index, row in enumerate(rows):
        classes = [str(value) for value in (row.get("class") or [])]
        if "detail" in classes:
            continue
        cells = row.find_all("td", recursive=False)
        if len(cells) != 7:
            raise FranklinSourceChangedError(
                "Franklin CIO docket row width changed",
                code="docket_row_width_changed",
                details={"expected": 7, "actual": len(cells)},
            )
        main_sequence += 1
        date_raw, filed_date = _source_date(
            _element_text(cells[1]),
            field_name="docket date",
            date_format="%m/%d/%y",
            required=True,
        )
        category = next(
            (value for value in classes if value != "alt"),
            None,
        )
        image_slot: str | None = None
        anchor = cells[3].find("a")
        if isinstance(anchor, Tag):
            href = str(anchor.get("href", ""))
            match = _IMAGE_LINK_RE.search(href)
            if match is None:
                raise FranklinSourceChangedError(
                    "Franklin CIO document link no longer uses a page slot",
                    code="document_slot_link_changed",
                )
            image_slot = match.group("key")
        document_coordinate = (
            image_coordinates.get(image_slot)
            if image_slot is not None
            else None
        )
        if image_slot is not None and document_coordinate is None:
            raise FranklinSourceChangedError(
                "Franklin CIO docket row refers to a missing document slot",
                code="document_slot_missing",
                details={"slot": image_slot},
            )

        detail_row: Tag | None = None
        for candidate in rows[index + 1 : index + 2]:
            if "detail" in [str(v) for v in (candidate.get("class") or [])]:
                detail_row = candidate
        detail = _detail_payload(detail_row)
        parsed.append(
            {
                "category_code": category,
                "category": DOCKET_CATEGORY_LABELS.get(category or ""),
                "filed_date_raw": date_raw,
                "filed_date": filed_date,
                "description": _required_text(
                    _element_text(cells[2]),
                    "docket description",
                ),
                "fiche": _element_text(cells[4]),
                "frame": _element_text(cells[5]),
                "pages_raw": _element_text(cells[6]),
                "detail_fields": detail["fields"],
                "detail_text": detail["text"],
                "document_coordinate": document_coordinate,
                "source_page_no": source_page_no,
                "source_page_sequence_no": main_sequence,
            }
        )
    return parsed


def parse_docket_ajax(
    payload: Mapping[str, Any],
    *,
    source_page_no: int,
) -> tuple[list[dict[str, Any]], str | None]:
    """Parse one source-native docket JSON page."""

    data = payload.get("data")
    image_array = payload.get("imageArray")
    if not isinstance(data, str) or not isinstance(image_array, Mapping):
        raise FranklinSourceChangedError(
            "Franklin CIO docket JSON schema changed",
            code="docket_json_schema_changed",
            details={"keys": sorted(str(key) for key in payload)},
        )
    images: dict[str, str] = {}
    for key, value in image_array.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise FranklinSourceChangedError(
                "Franklin CIO docket image map changed",
                code="docket_image_map_changed",
            )
        images[key] = value
    rows = parse_docket_rows(
        data,
        image_coordinates=images,
        source_page_no=source_page_no,
    )
    next_key = _text(payload.get("nextKey"))
    return rows, next_key


def _parse_parties(soup: BeautifulSoup) -> list[dict[str, Any]]:
    parties: list[dict[str, Any]] = []
    for body_id, role in (
        ("plaintiff-body", "plaintiff"),
        ("defendant-body", "defendant"),
        ("general-party-body", "general_party"),
    ):
        body = soup.find("tbody", id=body_id)
        if not isinstance(body, Tag):
            if role == "general_party":
                continue
            raise FranklinSourceChangedError(
                f"Franklin CIO response lacks #{body_id}",
                code="party_table_missing",
                details={"table_body_id": body_id},
            )
        rows = body.find_all("tr", recursive=False)
        role_sequence = 0
        for index, row in enumerate(rows):
            if row.get("id"):
                continue
            cells = row.find_all("td", recursive=False)
            if len(cells) < 2:
                continue
            role_sequence += 1
            detail_cells: list[Tag] = []
            if index + 1 < len(rows) and rows[index + 1].get("id"):
                detail_cells = rows[index + 1].find_all(
                    "td",
                    recursive=False,
                )
            address = (
                _multiline_element_text(detail_cells[1])
                if len(detail_cells) > 1
                else None
            )
            attorney_detail = (
                _multiline_element_text(detail_cells[2])
                if len(detail_cells) > 2
                else None
            )
            attorney_summary = (
                _element_text(cells[2])
                if len(cells) > 2
                else None
            )
            parties.append(
                {
                    "sequence_no": len(parties) + 1,
                    "role_sequence_no": role_sequence,
                    "role": role,
                    "raw_name": _required_text(
                        _element_text(cells[1]),
                        f"{role} name",
                    ),
                    "address_raw": address,
                    "attorney_summary": attorney_summary,
                    "attorney_detail_raw": attorney_detail,
                    "access_state": "public",
                }
            )
    return parties


def _parse_case_schedule(soup: BeautifulSoup) -> list[dict[str, Any]]:
    body = soup.find("tbody", id="caseschedule")
    if not isinstance(body, Tag):
        return []
    events: list[dict[str, Any]] = []
    for sequence, row in enumerate(
        body.find_all("tr", recursive=False),
        start=1,
    ):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        date_raw = _element_text(cells[0])
        date_iso: str | None = None
        if date_raw and re.fullmatch(r"\d{2}/\d{2}/\d{2}", date_raw):
            _raw, date_iso = _source_date(
                date_raw,
                field_name="case schedule date",
                date_format="%m/%d/%y",
            )
        events.append(
            {
                "sequence_no": sequence,
                "date_raw": date_raw,
                "date": date_iso,
                "description": _required_text(
                    _element_text(cells[1]),
                    "case schedule description",
                ),
            }
        )
    return events


def parse_case_detail_initial(
    html: str,
    *,
    requested_case: FranklinCaseNumber,
) -> ParsedCaseDetail:
    """Parse the initial case page and its first native docket page."""

    soup = BeautifulSoup(html, "html.parser")
    summary_table = soup.find("table", id="main")
    if not isinstance(summary_table, Tag):
        page_text = (_text(soup.get_text(" ", strip=True)) or "").lower()
        if any(
            marker in page_text
            for marker in (
                "case not found",
                "no case found",
                "no case matched the search criteria",
                "no cases found",
                "no records found",
            )
        ):
            raise FranklinCaseNotFoundError(requested_case.normalized)
        raise FranklinSourceChangedError(
            "Franklin CIO exact-case response lacks its case summary",
            code="case_summary_missing",
        )

    summary_row = summary_table.find("tbody")
    summary_row = (
        summary_row.find("tr")
        if isinstance(summary_row, Tag)
        else None
    )
    summary_cells = (
        summary_row.find_all("td", recursive=False)
        if isinstance(summary_row, Tag)
        else []
    )
    if len(summary_cells) < 4:
        raise FranklinSourceChangedError(
            "Franklin CIO case summary row changed",
            code="case_summary_row_changed",
            details={"cell_count": len(summary_cells)},
        )
    summary_values = [_element_text(cell) for cell in summary_cells]
    display_case_number = _required_text(
        summary_values[-4],
        "display case number",
    )
    returned_case = parse_case_number(display_case_number)
    if returned_case.normalized != requested_case.normalized:
        raise FranklinSourceChangedError(
            "Franklin CIO exact-case search returned a different case",
            code="case_number_mismatch",
            details={
                "requested": requested_case.normalized,
                "returned": returned_case.normalized,
            },
        )

    source_year = _required_text(
        (soup.find("input", id="caseYear") or {}).get("value"),
        "source case year",
    )
    source_type = _required_text(
        (soup.find("input", id="caseType") or {}).get("value"),
        "source case type",
    )
    source_sequence = _required_text(
        (soup.find("input", id="caseSeq") or {}).get("value"),
        "source case sequence",
    )
    source_compact = f"{source_year}{source_type}{source_sequence}"
    source_case = parse_case_number(source_compact)
    if source_case.normalized != returned_case.normalized:
        raise FranklinSourceChangedError(
            "Franklin CIO summary and hidden case fields disagree",
            code="case_number_fields_conflict",
            details={
                "summary": returned_case.normalized,
                "hidden": source_case.normalized,
            },
        )

    filing_date_raw, filing_date = _source_date(
        summary_values[-1],
        field_name="case filing date",
        date_format="%m/%d/%Y",
        required=True,
    )
    judge_section = soup.find("section", id="judge-container")
    judge_cells: list[Tag] = []
    if isinstance(judge_section, Tag):
        judge_row = judge_section.find("tbody")
        judge_row = (
            judge_row.find("tr")
            if isinstance(judge_row, Tag)
            else None
        )
        judge_cells = (
            judge_row.find_all("td", recursive=False)
            if isinstance(judge_row, Tag)
            else []
        )
    judge = (
        _element_text(judge_cells[-2])
        if len(judge_cells) >= 2
        else None
    )
    courtroom = (
        _multiline_element_text(judge_cells[-1])
        if judge_cells
        else None
    )
    parties = _parse_parties(soup)

    docket_body = soup.find("tbody", id="docket-body")
    if not isinstance(docket_body, Tag):
        raise FranklinSourceChangedError(
            "Franklin CIO response lacks #docket-body",
            code="docket_body_missing",
        )
    initial_images = parse_image_coordinates(html)
    docket_rows = parse_docket_rows(
        docket_body.decode_contents(),
        image_coordinates=initial_images,
        source_page_no=1,
    )
    next_input = soup.find("input", id="next-docket-key")
    next_key = (
        _text(next_input.get("value"))
        if isinstance(next_input, Tag)
        else None
    )

    record = {
        "record_kind": "case",
        "source_id": SOURCE_ID,
        "court": _court_payload(),
        "query_case_number_raw": requested_case.input_raw,
        "source_case_number_raw": source_compact,
        "display_case_number": display_case_number,
        "normalized_case_number": returned_case.normalized,
        "case_year": returned_case.year,
        "case_type_code": returned_case.case_type,
        "case_type_family": CASE_TYPE_LABELS.get(returned_case.case_type),
        "case_sequence_raw": source_sequence,
        "case_sequence_normalized": returned_case.sequence_normalized,
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            returned_case.normalized,
        ),
        "case_description": _text(summary_values[-3]),
        "status": _text(summary_values[-2]),
        "filing_date_raw": filing_date_raw,
        "filing_date": filing_date,
        "judge": judge,
        "courtroom_raw": courtroom,
        "parties": parties,
        "case_schedule": _parse_case_schedule(soup),
        "source_url": BASE_URL,
        "access_state": "public",
        "native_access_state": "anonymous CIO exact-case detail",
        "certified_record": False,
    }
    return ParsedCaseDetail(
        record=record,
        docket_rows=tuple(docket_rows),
        next_docket_key=next_key,
    )


def _docket_base_identity(
    case_number: str,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "case_number": case_number,
        "category_code": row.get("category_code"),
        "filed_date_raw": row.get("filed_date_raw"),
        "description": row.get("description"),
        "fiche": row.get("fiche"),
        "frame": row.get("frame"),
        "pages_raw": row.get("pages_raw"),
        "detail_fields": row.get("detail_fields"),
        "detail_text": row.get("detail_text"),
    }


def _document_identity(
    *,
    case_number: str,
    entry_id: str,
    row: Mapping[str, Any],
) -> tuple[str, str]:
    fiche = _text(row.get("fiche"))
    frame = _text(row.get("frame"))
    pages = _text(row.get("pages_raw"))
    if fiche or frame:
        identity = {
            "source_id": SOURCE_ID,
            "case_number": case_number,
            "fiche": fiche,
            "frame": frame,
            "pages_raw": pages,
        }
        source = "derived_case_fiche_frame_pages"
    else:
        identity = {
            "source_id": SOURCE_ID,
            "case_number": case_number,
            "docket_entry_id": entry_id,
            "document_role": "public_pdf",
        }
        source = "derived_case_docket_identity_public_pdf"
    digest = hashlib.sha256(
        canonical_json(identity).encode("utf-8")
    ).hexdigest()
    return f"franklin:document:{digest[:24]}", source


def finalize_case_page(
    parsed: ParsedCaseDetail,
    *,
    all_docket_rows: Sequence[Mapping[str, Any]],
    native_page_count: int,
    docket_exhausted: bool = True,
) -> FranklinCasePage:
    """Assign stable case-scoped docket and document identities."""

    record = copy.deepcopy(dict(parsed.record))
    case_number = str(record["normalized_case_number"])
    duplicate_counts: defaultdict[str, int] = defaultdict(int)
    entries: list[dict[str, Any]] = []
    document_records: OrderedDict[str, dict[str, Any]] = OrderedDict()
    document_coordinates: dict[str, str] = {}

    for sequence, raw_row in enumerate(all_docket_rows, start=1):
        row = copy.deepcopy(dict(raw_row))
        coordinate = row.pop("document_coordinate", None)
        base_identity = _docket_base_identity(case_number, row)
        base_fingerprint = hashlib.sha256(
            canonical_json(base_identity).encode("utf-8")
        ).hexdigest()
        duplicate_counts[base_fingerprint] += 1
        occurrence = duplicate_counts[base_fingerprint]
        entry_identity = {
            **base_identity,
            "duplicate_occurrence": occurrence,
        }
        entry_digest = hashlib.sha256(
            canonical_json(entry_identity).encode("utf-8")
        ).hexdigest()
        entry_id = f"franklin:docket:{entry_digest[:24]}"
        entry = {
            "record_kind": "docket_entry",
            "source_id": SOURCE_ID,
            "native_entry_id": entry_id,
            "native_entry_id_source": (
                "derived_case_displayed_fields_detail_duplicate_occurrence"
            ),
            "native_entry_fingerprint": base_fingerprint,
            "canonical_ref": canonical_court_ref(
                SOURCE_ID,
                COURT_ID,
                case_number,
                "docket_entry",
                entry_id,
            ),
            "sequence_no": sequence,
            "duplicate_occurrence": occurrence,
            **row,
            "document_available": coordinate is not None,
            "document_ids": [],
            "documents": [],
            "access_state": "public",
            "native_access_state": "CIO docket chronology",
        }

        if isinstance(coordinate, str):
            document_id, identity_source = _document_identity(
                case_number=case_number,
                entry_id=entry_id,
                row=row,
            )
            if document_id == entry_id:
                raise FranklinSourceChangedError(
                    "Franklin docket and document identities collided",
                    code="record_identity_collision",
                )
            document = document_records.get(document_id)
            if document is None:
                document = {
                    "record_kind": "document",
                    "source_id": SOURCE_ID,
                    "native_document_id": document_id,
                    "native_document_id_source": identity_source,
                    "canonical_ref": canonical_court_ref(
                        SOURCE_ID,
                        COURT_ID,
                        case_number,
                        "document",
                        document_id,
                    ),
                    "case_number": case_number,
                    "document_type": row.get("description"),
                    "filed_date": row.get("filed_date"),
                    "fiche": row.get("fiche"),
                    "frame": row.get("frame"),
                    "pages_raw": row.get("pages_raw"),
                    "mime_type": "application/pdf",
                    "docket_entry_ids": [],
                    "source_url": DOCUMENT_URL,
                    "access_state": "public",
                    "native_access_state": "CIO document image link",
                    "certification_status": "uncertified_copy",
                }
                document_records[document_id] = document
            if entry_id not in document["docket_entry_ids"]:
                document["docket_entry_ids"].append(entry_id)
            entry["document_ids"].append(document_id)
            document_coordinates.setdefault(document_id, coordinate)
        entries.append(entry)

    for entry in entries:
        entry["documents"] = [
            copy.deepcopy(document_records[document_id])
            for document_id in entry["document_ids"]
        ]
    record["docket_entries"] = entries
    record["documents"] = list(document_records.values())
    record["docket_retrieval"] = {
        "pagination": "source_next_key_until_empty",
        "native_page_count": native_page_count,
        "entry_count": len(entries),
        "document_count": len(document_records),
        "exhausted": docket_exhausted,
    }
    return FranklinCasePage(
        record=record,
        document_coordinates=document_coordinates,
    )


class FranklinCourtClient:
    """Session-aware client for the official Franklin CIO portal."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: RetryPolicy | None = None,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        sleeper: Any = time.sleep,
        user_agent: str = DEFAULT_USER_AGENT,
        request_budget: int | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if request_budget is not None and request_budget <= 0:
            raise ValueError("request_budget must be positive")
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
        self.request_budget = request_budget

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _validate_official_url(url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != OFFICIAL_HOST:
            raise FranklinSourceChangedError(
                "Franklin CIO response resolved outside the official host",
                code="response_host_changed",
                details={
                    "scheme": parsed.scheme,
                    "host": parsed.hostname,
                    "path": parsed.path,
                },
            )

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
    ) -> Any:
        self._validate_official_url(url)
        request_headers = {
            "Accept": (
                "text/html,application/xhtml+xml,application/json,"
                "application/pdf"
            ),
            "User-Agent": self.user_agent,
            **dict(headers or {}),
        }
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            if (
                self.request_budget is not None
                and self.request_count >= self.request_budget
            ):
                raise FranklinCourtError(
                    "Franklin CIO request budget exhausted",
                    code="request_budget_exhausted",
                    category="request_budget",
                    details={
                        "request_budget": self.request_budget,
                        "requests_made": self.request_count,
                    },
                )
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=request_headers,
                    data=data,
                    params=params,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt))
                    continue
                raise FranklinCourtError(
                    f"Franklin CIO request failed: {error}",
                    code="transport_error",
                    category="transport",
                    retryable=True,
                    details={"attempts": attempt},
                ) from error

            response_url = str(getattr(response, "url", url) or url)
            self._validate_official_url(response_url)
            status_code = int(response.status_code)
            if status_code in self.retry_policy.retry_statuses:
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt))
                    continue
                raise FranklinCourtError(
                    f"Franklin CIO returned HTTP {status_code}",
                    code=(
                        "rate_limited"
                        if status_code == 429
                        else "http_status_error"
                    ),
                    status=(
                        ResultStatus.RATE_LIMITED
                        if status_code == 429
                        else ResultStatus.UNAVAILABLE
                    ),
                    category=(
                        "rate_limit"
                        if status_code == 429
                        else "transport"
                    ),
                    retryable=True,
                    details={"status_code": status_code},
                )
            if status_code in {401, 403}:
                raise FranklinCourtError(
                    f"Franklin CIO returned HTTP {status_code}",
                    code="source_access_failed",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"status_code": status_code},
                )
            if status_code in {404, 410}:
                raise FranklinSourceChangedError(
                    f"Franklin CIO route returned HTTP {status_code}",
                    code="source_route_missing",
                    details={"status_code": status_code},
                )
            if status_code < 200 or status_code >= 300:
                raise FranklinCourtError(
                    f"Franklin CIO returned HTTP {status_code}",
                    code="http_status_error",
                    category="transport",
                    details={"status_code": status_code},
                )
            return response

        raise FranklinCourtError(
            f"Franklin CIO request failed: {last_error}",
            code="transport_error",
            category="transport",
            retryable=True,
        )

    def _bootstrap_contract(
        self,
    ) -> tuple[str, str, str, tuple[str, ...]]:
        """Accept the disclaimer and return its non-secret form contract."""
        landing = self._request("GET", BASE_URL)
        landing_url = str(getattr(landing, "url", BASE_URL) or BASE_URL)
        action = parse_disclaimer_action(
            landing.text,
            response_url=landing_url,
        )
        soup = BeautifulSoup(landing.text, "html.parser")
        form = soup.find(
            "form",
            action=lambda value: bool(
                value
                and "/CaseInformationOnline/acceptDisclaimer" in value
            ),
        )
        if not isinstance(form, Tag):
            raise FranklinSourceChangedError(
                "Franklin CIO landing page lacks its disclaimer form",
                code="disclaimer_form_missing",
            )
        method = str(form.get("method") or "GET").strip().upper()
        if method != "POST":
            raise FranklinSourceChangedError(
                "Franklin CIO disclaimer form method changed",
                code="disclaimer_method_changed",
                details={"method": method},
            )
        field_names = tuple(
            sorted(
                {
                    name
                    for element in form.find_all(
                        ["input", "select", "textarea"]
                    )
                    if (name := _text(element.get("name"))) is not None
                }
            )
        )
        accepted = self._request(
            "POST",
            action,
            headers={"Referer": landing_url},
            data={"fromPage": "index", "Accept": "ACCEPT"},
        )
        accepted_url = str(getattr(accepted, "url", BASE_URL) or BASE_URL)
        if "Case Information Online" not in str(accepted.text):
            raise FranklinSourceChangedError(
                "Franklin CIO disclaimer acceptance did not return its search page",
                code="disclaimer_acceptance_changed",
            )
        return (
            accepted_url,
            urlsplit(action).path,
            method,
            field_names,
        )

    def bootstrap(self) -> str:
        """Create a CIO session by accepting its dynamic disclaimer form."""

        accepted_url, _path, _method, _fields = self._bootstrap_contract()
        return accepted_url

    @staticmethod
    def _case_search_payload(
        requested: FranklinCaseNumber,
    ) -> dict[str, str]:
        return {
            "lname": "",
            "fname": "",
            "mint": "",
            "selType": " ",
            "caseYear": requested.year,
            "caseYear_h": requested.year,
            "caseType": requested.case_type,
            "caseType_h": requested.case_type,
            "caseSeq": requested.sequence_normalized,
            "caseSeq_h": requested.sequence_normalized,
            "personType": "P",
            "attyNum": "",
            "txtCalendar1": "",
            "txtCalendar2": "",
            "advFlag": "",
            "reallySubmit": "true",
        }

    @staticmethod
    def _party_search_payload(
        window: FranklinPartyWindowSpec,
    ) -> dict[str, str]:
        return {
            "lname": window.last_name,
            "fname": window.first_name or "",
            "mint": window.middle_initial or "",
            "selType": COURT_CATEGORY_VALUES[window.court_category],
            "caseYear": "",
            "caseYear_h": "",
            "caseType": "AP",
            "caseType_h": "",
            "caseSeq": "",
            "caseSeq_h": "",
            "attyIdx": "",
            "advFlag": "show",
            "reallySubmit": "true",
            "personType": "P",
            "attyNum": "",
            "txtCalendar1": (
                window.filed_from.strftime("%m/%d/%Y")
                if window.filed_from is not None
                else ""
            ),
            "txtCalendar2": (
                window.filed_to.strftime("%m/%d/%Y")
                if window.filed_to is not None
                else ""
            ),
            "recs": str(window.native_row_count),
        }

    def _fetch_party_window(
        self,
        *,
        window: FranklinPartyWindowSpec,
        referer: str,
    ) -> tuple[ParsedPartySearchWindow, tuple[str, ...]]:
        payload = self._party_search_payload(window)
        response = self._request(
            "POST",
            NAME_SEARCH_URL,
            headers={"Referer": referer},
            data=payload,
        )
        parsed = parse_party_search_results(
            response.text,
            window=window,
        )
        return parsed, tuple(sorted(payload))

    @staticmethod
    def _partition_party_window(
        window: FranklinPartyWindowSpec,
    ) -> tuple[FranklinPartyWindowSpec, ...]:
        if window.filed_from is not None and window.filed_to is not None:
            if window.filed_from < window.filed_to:
                span_days = (window.filed_to - window.filed_from).days
                midpoint = window.filed_from + timedelta(
                    days=span_days // 2
                )
                return (
                    replace(window, filed_to=midpoint),
                    replace(
                        window,
                        filed_from=midpoint + timedelta(days=1),
                    ),
                )
            if window.court_category == "all":
                return tuple(
                    replace(window, court_category=court_category)
                    for court_category in (
                        "appeals",
                        "civil",
                        "criminal",
                        "domestic",
                    )
                )
        return ()

    def search_parties(
        self,
        *,
        last_name: str,
        first_name: str | None = None,
        middle_initial: str | None = None,
        court_category: str = "all",
        filed_from: date | datetime | str | None = None,
        filed_to: date | datetime | str | None = None,
        native_row_count: int = DEFAULT_NATIVE_ROW_COUNT,
        exhaustive: bool = False,
    ) -> FranklinPartySearch:
        """Search the native lower-bound name index and preserve its rows."""

        spec = build_party_search_spec(
            last_name=last_name,
            first_name=first_name,
            middle_initial=middle_initial,
            court_category=court_category,
            filed_from=filed_from,
            filed_to=filed_to,
            native_row_count=native_row_count,
            exhaustive=exhaustive,
        )
        referer = self.bootstrap()
        pending = [_party_window_from_spec(spec)]
        terminal: list[ParsedPartySearchWindow] = []
        while pending:
            window = pending.pop(0)
            parsed, _field_names = self._fetch_party_window(
                window=window,
                referer=referer,
            )
            if spec.exhaustive and not parsed.coverage_complete:
                children = self._partition_party_window(window)
                if children:
                    pending[0:0] = list(children)
                    continue
            terminal.append(parsed)

        records = tuple(
            record
            for window in terminal
            for record in window.records
        )
        unresolved = tuple(
            {
                **dict(window.window),
                "reason": (
                    "source_buffer_boundary"
                    if window.source_buffer_truncated
                    else "matching_prefix_reaches_native_window_end"
                ),
                "source_row_count": window.source_row_count,
                "complete_row_count": window.complete_row_count,
                "incomplete_row_count": window.incomplete_row_count,
                "matched_row_count": window.matched_row_count,
                "verified_continuation": False,
            }
            for window in terminal
            if not window.coverage_complete
        )
        return FranklinPartySearch(
            records=records,
            windows=tuple(terminal),
            coverage_complete=not unresolved,
            unresolved_windows=unresolved,
            source_buffer_truncated=any(
                window.source_buffer_truncated for window in terminal
            ),
        )

    @staticmethod
    def _docket_payload(
        requested: FranklinCaseNumber,
        next_key: str,
    ) -> dict[str, str]:
        return {
            "caseYear": requested.year,
            "caseType": requested.case_type,
            "caseSeq": requested.sequence_normalized,
            "docketdatekey": next_key,
            "docketdir": "3",
        }

    def _fetch_docket_page(
        self,
        *,
        requested: FranklinCaseNumber,
        next_key: str,
        referer: str,
        source_page_no: int,
    ) -> tuple[
        list[dict[str, Any]],
        str | None,
        tuple[str, ...],
    ]:
        docket_response = self._request(
            "POST",
            DOCKET_URL,
            headers={
                "Referer": referer,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
            data=self._docket_payload(requested, next_key),
        )
        try:
            docket_payload = docket_response.json()
        except (TypeError, ValueError) as error:
            raise FranklinSourceChangedError(
                "Franklin CIO docket route returned non-JSON content",
                code="docket_json_invalid",
            ) from error
        if not isinstance(docket_payload, Mapping):
            raise FranklinSourceChangedError(
                "Franklin CIO docket route returned a non-object JSON value",
                code="docket_json_schema_changed",
            )
        response_field_names = tuple(
            sorted(str(key) for key in docket_payload)
        )
        page_rows, returned_next_key = parse_docket_ajax(
            docket_payload,
            source_page_no=source_page_no,
        )
        return page_rows, returned_next_key, response_field_names

    def fetch_case(self, case_number: str) -> FranklinCasePage:
        """Fetch one exact case and exhaust every source-native docket page."""

        requested = parse_case_number(case_number)
        referer = self.bootstrap()
        response = self._request(
            "POST",
            CASE_SEARCH_URL,
            headers={"Referer": referer},
            data=self._case_search_payload(requested),
        )
        parsed = parse_case_detail_initial(
            response.text,
            requested_case=requested,
        )
        all_rows = list(parsed.docket_rows)
        next_key = parsed.next_docket_key
        seen_keys: set[str] = set()
        page_no = 1
        while next_key:
            if next_key in seen_keys:
                raise FranklinSourceChangedError(
                    "Franklin CIO docket pagination repeated a next key",
                    code="docket_pagination_cycle",
                    details={"next_key": next_key, "page_no": page_no},
                )
            seen_keys.add(next_key)
            page_no += 1
            page_rows, returned_next_key, _response_fields = (
                self._fetch_docket_page(
                    requested=requested,
                    next_key=next_key,
                    referer=str(
                        getattr(response, "url", CASE_SEARCH_URL)
                        or CASE_SEARCH_URL
                    ),
                    source_page_no=page_no,
                )
            )
            all_rows.extend(page_rows)
            next_key = returned_next_key

        return finalize_case_page(
            parsed,
            all_docket_rows=all_rows,
            native_page_count=page_no,
        )

    def probe_contract(
        self,
        case_number: str = PROBE_CASE_NUMBER,
    ) -> FranklinProbeSnapshot:
        """Sample the fixed five-request party, case, and docket contract."""

        started_count = self.request_count
        requested = parse_case_number(case_number)
        (
            referer,
            disclaimer_path,
            disclaimer_method,
            disclaimer_fields,
        ) = self._bootstrap_contract()
        party_spec = build_party_search_spec(
            last_name=PROBE_PARTY_LAST_NAME,
            court_category=PROBE_PARTY_COURT,
            filed_from=PROBE_PARTY_FILED_DATE,
            filed_to=PROBE_PARTY_FILED_DATE,
            native_row_count=PROBE_PARTY_NATIVE_ROW_COUNT,
        )
        party_window = _party_window_from_spec(party_spec)
        party_page, party_field_names = self._fetch_party_window(
            window=party_window,
            referer=referer,
        )
        party_matches = [
            record
            for record in party_page.records
            if record["matched_query"]
        ]
        if not party_page.coverage_complete:
            raise FranklinSourceChangedError(
                "Franklin CIO party sentinel no longer reaches ordered spillover",
                code="probe_party_coverage_unresolved",
            )
        if not any(
            record["normalized_case_number"]
            == PROBE_PARTY_CASE_NUMBER
            for record in party_matches
        ):
            raise FranklinSourceChangedError(
                "Franklin CIO party sentinel case is missing",
                code="probe_party_case_missing",
                details={
                    "expected_case_number": PROBE_PARTY_CASE_NUMBER,
                },
            )
        case_payload = self._case_search_payload(requested)
        response = self._request(
            "POST",
            CASE_SEARCH_URL,
            headers={"Referer": referer},
            data=case_payload,
        )
        parsed = parse_case_detail_initial(
            response.text,
            requested_case=requested,
        )
        next_key = parsed.next_docket_key
        if next_key is None:
            raise FranklinSourceChangedError(
                "Franklin CIO sentinel no longer exposes its known continuation",
                code="probe_continuation_missing",
            )
        docket_payload = self._docket_payload(requested, next_key)
        page_rows, returned_next_key, response_fields = (
            self._fetch_docket_page(
                requested=requested,
                next_key=next_key,
                referer=str(
                    getattr(response, "url", CASE_SEARCH_URL)
                    or CASE_SEARCH_URL
                ),
                source_page_no=2,
            )
        )
        page = finalize_case_page(
            parsed,
            all_docket_rows=[*parsed.docket_rows, *page_rows],
            native_page_count=2,
            docket_exhausted=returned_next_key is None,
        )
        request_count = self.request_count - started_count
        if request_count != 5:
            raise FranklinCourtError(
                "Franklin CIO fixed probe exceeded its request contract",
                code="probe_request_contract_changed",
                category="request_budget",
                details={
                    "expected_requests": 5,
                    "requests_made": request_count,
                },
            )
        required_response_fields = {
            "priorKey",
            "nextKey",
            "data",
            "imageArray",
        }
        if not required_response_fields.issubset(response_fields):
            raise FranklinSourceChangedError(
                "Franklin CIO sentinel docket response fields changed",
                code="docket_json_schema_changed",
                details={"fields": list(response_fields)},
            )
        return FranklinProbeSnapshot(
            record=page.record,
            disclaimer_path=disclaimer_path,
            disclaimer_method=disclaimer_method,
            disclaimer_field_names=disclaimer_fields,
            party_search_field_names=party_field_names,
            party_result_field_names=party_page.result_field_names,
            party_sentinel_case_number=PROBE_PARTY_CASE_NUMBER,
            party_matching_count=len(party_matches),
            party_coverage_complete=party_page.coverage_complete,
            case_search_field_names=tuple(sorted(case_payload)),
            docket_request_field_names=tuple(sorted(docket_payload)),
            docket_response_field_names=response_fields,
            initial_next_key_present=True,
            continuation_next_key_present=returned_next_key is not None,
            request_count=request_count,
        )

    def fetch_document(
        self,
        case_number: str,
        document_id: str,
    ) -> FranklinDocumentFetch:
        """Refetch case context, resolve one document identity, and validate PDF."""

        case_page = self.fetch_case(case_number)
        coordinate = case_page.document_coordinates.get(document_id)
        if coordinate is None:
            known = next(
                (
                    document
                    for document in case_page.record["documents"]
                    if document["native_document_id"] == document_id
                ),
                None,
            )
            if known is not None:
                raise FranklinSelectionError(
                    "document_not_public",
                    "The selected CIO document has no current public PDF route",
                    details={"document_id": document_id},
                )
            raise FranklinSelectionError(
                "document_not_found",
                "The case does not contain the requested document identity",
                details={
                    "case_number": parse_case_number(case_number).normalized,
                    "document_id": document_id,
                },
            )

        response = self._request(
            "GET",
            DOCUMENT_URL,
            headers={"Referer": CASE_SEARCH_URL, "Accept": "application/pdf"},
            params={"coords": coordinate},
        )
        content_type = str(response.headers.get("Content-Type", "")).split(
            ";",
            1,
        )[0].strip().lower()
        content = bytes(response.content)
        if content_type != "application/pdf":
            raise FranklinSourceChangedError(
                "Franklin CIO document response has a non-PDF media type",
                code="document_media_type_invalid",
                details={"content_type": content_type},
            )
        if not content.startswith(b"%PDF-"):
            raise FranklinSourceChangedError(
                "Franklin CIO document response lacks a PDF signature",
                code="document_signature_invalid",
                details={"magic_hex": content[:8].hex()},
            )
        final_url = str(getattr(response, "url", DOCUMENT_URL) or DOCUMENT_URL)
        self._validate_official_url(final_url)
        parsed_final = urlsplit(final_url)
        disposition = Message()
        disposition["content-disposition"] = str(
            response.headers.get("Content-Disposition", "")
        )
        filename = disposition.get_filename()
        if not filename:
            suffix = document_id.rsplit(":", 1)[-1]
            normalized_case = parse_case_number(case_number).normalized
            filename = f"{normalized_case}-{suffix}.pdf"
        pdf = FranklinPDF(
            content=content,
            media_type=content_type,
            filename=filename,
            sha256=hashlib.sha256(content).hexdigest(),
            final_host=parsed_final.hostname or "",
            resolved_path=parsed_final.path,
        )
        return FranklinDocumentFetch(
            case_page=case_page,
            document_id=document_id,
            pdf=pdf,
        )


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    operation = args.command
    if args.command in {"name", "search"}:
        operation = "name"
        parameters = {
            "last_name": args.last_name,
            "first_name": args.first_name,
            "middle_initial": args.middle_initial,
            "court_category": args.court,
            "filed_from": args.filed_from,
            "filed_to": args.filed_to,
            "native_row_count": args.native_row_count,
            "exhaustive": args.exhaustive,
            "matching_semantics": "ordered_lower_bound_index_window",
        }
    elif args.command == "case":
        parsed = parse_case_number(args.case_number)
        parameters = {
            "case_number_raw": parsed.input_raw,
            "normalized_case_number": parsed.normalized,
            "docket_pagination": "exhaustive",
        }
    elif args.command == "document":
        parsed = parse_case_number(args.case_number)
        parameters = {
            "case_number_raw": parsed.input_raw,
            "normalized_case_number": parsed.normalized,
            "document_id": args.document_id,
            "destination": str(args.destination),
        }
    elif args.command == "probe":
        parsed = parse_case_number(args.case_number)
        parameters = {
            "sentinel_case_number": parsed.normalized,
            "checks": [
                "disclaimer_session",
                "exact_case",
                "exhaustive_docket",
                "document_locators",
            ],
        }
    elif args.command == "source":
        parameters = {"observed_at": OBSERVED_AT}
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
        ),
    )


def _make_client(args: argparse.Namespace) -> FranklinCourtClient:
    return FranklinCourtClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        minimum_interval=args.minimum_interval,
    )


def _failure_result(
    query: PublicRecordsQuery,
    error: FranklinCourtError,
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
        warnings=SOURCE_WARNINGS,
    )


def _execute_command(
    args: argparse.Namespace,
    client: FranklinCourtClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command == "source":
        return PublicRecordsResult.success(
            query,
            [SOURCE_CAPABILITIES],
            warnings=SOURCE_WARNINGS,
        )
    if args.command in {"name", "search"}:
        search = client.search_parties(
            last_name=args.last_name,
            first_name=args.first_name,
            middle_initial=args.middle_initial,
            court_category=args.court,
            filed_from=args.filed_from,
            filed_to=args.filed_to,
            native_row_count=args.native_row_count,
            exhaustive=args.exhaustive,
        )
        errors: list[PublicRecordsError] = []
        if search.unresolved_windows:
            errors.append(
                PublicRecordsError(
                    code="party_coverage_unresolved",
                    message=(
                        "Franklin CIO exposes no verified continuation for "
                        "one or more terminal party-index windows"
                    ),
                    category="native_boundary",
                    retryable=False,
                    details={
                        "unresolved_windows": list(
                            search.unresolved_windows
                        ),
                        "next_cursor": None,
                    },
                )
            )
        if search.source_buffer_truncated:
            errors.append(
                PublicRecordsError(
                    code="party_source_buffer_truncated",
                    message=(
                        "Franklin CIO ended at least one party response "
                        "inside a native result row"
                    ),
                    category="source_boundary",
                    retryable=False,
                    details={
                        "matching_prefix_coverage_complete": (
                            search.coverage_complete
                        ),
                        "affected_windows": [
                            dict(window.window)
                            for window in search.windows
                            if window.source_buffer_truncated
                        ],
                        "next_cursor": None,
                    },
                )
            )
        if errors:
            return PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                errors,
                records=search.records,
                warnings=SOURCE_WARNINGS,
            )
        return PublicRecordsResult.success(
            query,
            search.records,
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "case":
        page = client.fetch_case(args.case_number)
        return PublicRecordsResult.success(
            query,
            [page.record],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "document":
        fetch = client.fetch_document(
            args.case_number,
            args.document_id,
        )
        destination = Path(args.destination).expanduser()
        if destination.exists() and not args.overwrite:
            raise OSError(
                f"destination exists; pass --overwrite: {destination}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(fetch.pdf.content)

        selected = next(
            copy.deepcopy(document)
            for document in fetch.case_page.record["documents"]
            if document["native_document_id"] == fetch.document_id
        )
        selected.update(
            {
                "sha256": fetch.pdf.sha256,
                "mime_type": fetch.pdf.media_type,
                "filename": fetch.pdf.filename,
                "size_bytes": len(fetch.pdf.content),
                "storage_path": str(destination.resolve()),
                "final_host": fetch.pdf.final_host,
                "resolved_path": fetch.pdf.resolved_path,
                "acquired": True,
            }
        )
        record = {
            "record_kind": "document_download",
            "source_id": SOURCE_ID,
            "normalized_case_number": parse_case_number(
                args.case_number
            ).normalized,
            "document": selected,
        }
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=[str(destination.resolve())],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "probe":
        snapshot = client.probe_contract(args.case_number)
        page_record = snapshot.record
        record = {
            "record_kind": "source_probe",
            "source_id": SOURCE_ID,
            "platform_family": PLATFORM_FAMILY,
            "case_number": page_record["normalized_case_number"],
            "party_sentinel_case_number": (
                snapshot.party_sentinel_case_number
            ),
            "party_matching_count": snapshot.party_matching_count,
            "party_coverage_complete": snapshot.party_coverage_complete,
            "docket_entry_count": len(page_record["docket_entries"]),
            "document_count": len(page_record["documents"]),
            "native_docket_page_count": page_record["docket_retrieval"][
                "native_page_count"
            ],
            "docket_exhausted": page_record["docket_retrieval"][
                "exhausted"
            ],
            "request_count": snapshot.request_count,
            "official_host": OFFICIAL_HOST,
        }
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )
    raise ValueError(f"unsupported Franklin court command: {args.command}")


def execute(
    args: argparse.Namespace,
    *,
    client: FranklinCourtClient | Any | None = None,
    record_search: bool = True,
) -> PublicRecordsResult:
    """Execute one Franklin CIO operation."""

    query = build_query(args)
    source_client = client or _make_client(args)
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except FranklinCaseNotFoundError:
        result = PublicRecordsResult.success(
            query,
            [],
            warnings=SOURCE_WARNINGS,
        )
    except FranklinCourtError as error:
        result = _failure_result(query, error)
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="document_write_failed",
                    message=str(error),
                    category="local_io",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
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

    if record_search:
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
        summary=f"Franklin County CIO {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Franklin County CIO {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        if record.get("record_kind") == "case":
            print(
                f"  {record.get('normalized_case_number') or '?'} | "
                f"{record.get('filing_date') or '?'} | "
                f"{record.get('case_description') or '?'} | "
                f"{len(record.get('docket_entries', []))} docket entries"
            )
        elif record.get("record_kind") == "case_index_occurrence":
            match_label = "match" if record.get("matched_query") else "spillover"
            print(
                f"  {record.get('normalized_case_number') or '?'} | "
                f"{record.get('raw_name') or '?'} | "
                f"{record.get('filing_date') or '?'} | {match_label}"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


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
        help="Attempts for transient source failures",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Franklin County Clerk of Courts Case Information Online"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser(
        "source",
        help="Show verified route roles and cross-source joins",
    )
    _add_runtime_and_output(source)

    name = subparsers.add_parser(
        "name",
        aliases=["search"],
        help="Search the ordered CIO party-name index",
    )
    name.add_argument("last_name")
    name.add_argument("--first-name")
    name.add_argument("--middle-initial")
    name.add_argument(
        "--court",
        choices=sorted(COURT_CATEGORY_VALUES),
        default="all",
        help="Native CIO court category",
    )
    name.add_argument(
        "--filed-from",
        help="Inclusive filed-date lower bound (YYYY-MM-DD or MM/DD/YYYY)",
    )
    name.add_argument(
        "--filed-to",
        help="Inclusive filed-date upper bound (YYYY-MM-DD or MM/DD/YYYY)",
    )
    name.add_argument(
        "--native-row-count",
        type=int,
        choices=NATIVE_ROW_COUNTS,
        default=DEFAULT_NATIVE_ROW_COUNT,
        help="CIO Records Per Page value",
    )
    name.add_argument(
        "--exhaustive",
        action="store_true",
        help=(
            "Adaptively partition supplied filed dates when a matching-prefix "
            "window reaches the native boundary"
        ),
    )
    _add_runtime_and_output(name)

    case = subparsers.add_parser(
        "case",
        help="Fetch one exact case and its complete public docket",
    )
    case.add_argument("case_number")
    _add_runtime_and_output(case)

    document = subparsers.add_parser(
        "document",
        help="Download a public PDF by emitted document identity",
    )
    document.add_argument("case_number")
    document.add_argument("document_id")
    document.add_argument("destination")
    document.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing destination",
    )
    _add_runtime_and_output(document)

    probe = subparsers.add_parser(
        "probe",
        help=(
            "Verify party search, exact-case, docket pagination, and "
            "document locators"
        ),
    )
    probe.add_argument(
        "--case-number",
        default=PROBE_CASE_NUMBER,
        help="Public sentinel case number",
    )
    _add_runtime_and_output(probe)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)
    if result.status not in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    }:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
