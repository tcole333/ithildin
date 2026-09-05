#!/usr/bin/env python3
"""Query the D.C. Court of Appeals public C-Track case system.

The official public site supports case searches, participant searches, case
detail with party and event history, source-resolved filing links, and direct
document downloads.  The originating Superior Court or agency case number is
preserved as a first-class pivot to related trial-court sources.

Examples:
    uv run python tools/query_dc_appellate_cases.py search \
        --appellate-case-number 24-BG-1045 --output /tmp/dc-case.json
    uv run python tools/query_dc_appellate_cases.py search \
        --originating-case-number 2022-CA-002124-M \
        --output /tmp/dc-originating-case.json
    uv run python tools/query_dc_appellate_cases.py participant \
        --last-name Alpert --output /tmp/dc-participant.json
    uv run python tools/query_dc_appellate_cases.py case 24-BG-1045 \
        --output /tmp/dc-case-detail.json
    uv run python tools/query_dc_appellate_cases.py probe \
        --output /tmp/dc-ctrack-probe.json
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import secrets
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urljoin, urlparse

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


SOURCE_ID = "us-dc-court-of-appeals-case-search"
COURT_ID = "us-dc-court-of-appeals"
STATE_CODE = "DC"
STATE_GEOID = "11"

BASE_URL = "https://efile.dcappeals.gov"
CASE_SEARCH_PATH = "/public/caseSearch.do"
PARTICIPANT_SEARCH_PATH = "/public/publicActorSearch.do"
CASE_VIEW_PATH = "/public/caseView.do"
DOCUMENT_VIEW_PATH = "/document/view.do"
DOCUMENT_RESOLVER_PATH = (
    "/dwr/call/plaincall/AJAX.getViewDocumentLinks.dwr"
)
CASE_SEARCH_URL = f"{BASE_URL}{CASE_SEARCH_PATH}"
PARTICIPANT_SEARCH_URL = f"{BASE_URL}{PARTICIPANT_SEARCH_PATH}"
DOCUMENT_RESOLVER_URL = f"{BASE_URL}{DOCUMENT_RESOLVER_PATH}"

COURT_INFO_URL = (
    "https://www.dccourts.gov/court-of-appeals/"
    "court-of-appeals-case-search-and-efiling"
)
SUPERIOR_SEARCH_URL = (
    "https://www.dccourts.gov/superior-court/"
    "superior-court-case-search"
)
SUPERIOR_PORTAL_URL = "https://portal-dc.tylertech.cloud/Portal"
SUPERIOR_EACCESS_URL = (
    "https://eaccess.dccourts.gov/eaccess/home.page.2"
)

NATIVE_PAGE_SIZE = 50
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

PROBE_CASE_NUMBER = "24-BG-1045"
PROBE_CASE_INTERNAL_ID = "69335"
PROBE_ORIGINATING_CASE_NUMBER = "DDN 2024-D175"

CASE_RESULT_HEADERS = (
    "Case No.",
    "Short Caption",
    "Group",
    "Type",
    "Subtype",
    "Status",
    "Superior Court or Agency Case Number",
)
PARTICIPANT_RESULT_HEADERS = (
    "Case No.",
    "Participant",
    "Appellate Role",
    "Short Caption",
    "Appeal Filed Date",
    "Case Subtype",
)
EVENT_HEADERS = ("Event Date", "Status", "Description", "Result", "PDF")
PARTY_HEADERS = (
    "Appellate Role",
    "Party Name",
    "IFP",
    "Attorney(s)",
    "Arguing Attorney",
    "E-Filer",
)

_CASE_VIEW_RE = re.compile(r"^/public/caseView\.do$")
_RANGE_RE = re.compile(
    r"(\d[\d,]*)\s+to\s+(\d[\d,]*)\s+of\s+"
    r"(\d[\d,]*)\s+rows?\s+are\s+displayed",
    re.IGNORECASE,
)
_CASE_HEADING_RE = re.compile(r"^Case Information:\s*(.+)$", re.IGNORECASE)
_DOCUMENT_LOCATOR_RE = re.compile(
    r"^(?P<method_code>\d+):(?P<event_id>\d+):(?P<case_id>\d+)$"
)
_DWR_CALLBACK_RE = re.compile(
    r"_remoteHandleCallback\(\s*['\"]0['\"]\s*,\s*['\"]0['\"]\s*,"
    r"\s*(?P<payload>\"(?:\\.|[^\"\\])*\")\s*\)",
    re.DOTALL,
)
_CHALLENGE_MARKERS = (
    "let's confirm you are human",
    "complete the security check before continuing",
    "captcha challenge",
)


SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="D.C. Court of Appeals C-Track Public Case Search",
    source_role=(
        "official_appellate_case_participant_docket_and_document_system"
    ),
    base_url=CASE_SEARCH_URL,
    dataset_id="dc-court-of-appeals-ctrack-public",
    metadata={
        "authority": "District of Columbia Court of Appeals",
        "operator": "District of Columbia Courts",
        "authentication": "none",
        "native_page_size": NATIVE_PAGE_SIZE,
        "native_pagination": "one_based_start_row_post",
        "case_search_fields": [
            "appellate_case_number",
            "caption",
            "originating_superior_or_agency_case_number",
            "filed_date_range",
            "open_cases_only",
        ],
        "participant_search_fields": [
            "last_or_organization_name",
            "first_name",
            "middle_name",
        ],
        "originating_case_number_is_first_class": True,
        "court_information_url": COURT_INFO_URL,
        "superior_court_search_url": SUPERIOR_SEARCH_URL,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="District of Columbia",
    state_code=STATE_CODE,
    locality="Washington",
)

SOURCE_WARNINGS = (
    "C-Track contains appellate matters; an originating trial matter appears "
    "only when it reached the Court of Appeals.",
    "The source exposes public filing links on individual docket events; "
    "availability varies by event and case.",
    "Superior Court case lookup remains split between Portal and eAccess by "
    "case type, while calendars and appellate publications are separate "
    "official sources.",
)


class DCAppellateCasesError(RuntimeError):
    """Source error carrying public-record result semantics."""

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


class DCAppellateSelectionError(DCAppellateCasesError):
    """Caller selection cannot be represented by the source."""

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
            status=ResultStatus.UNAVAILABLE,
            category="selection",
            details=details,
        )


class DCAppellateSourceChangedError(DCAppellateCasesError):
    """The source no longer matches the verified public interface."""

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
class DCAppellatePage:
    """One native 50-row C-Track result page."""

    operation: str
    records: tuple[Mapping[str, Any], ...]
    start_row: int
    end_row: int
    total_rows: int
    next_start_row: int | None
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class DCAppellateCollection:
    """Exhaustive traversal, or records collected before a later error."""

    records: tuple[Mapping[str, Any], ...]
    pages_fetched: int
    total_rows: int
    source_urls: tuple[str, ...]
    schema_fingerprints: tuple[str, ...]
    incomplete_error: DCAppellateCasesError | None = None


@dataclass(frozen=True)
class DCAppellateDocument:
    """Validated bytes returned by the court document endpoint."""

    source_url: str
    content: bytes
    media_type: str
    filename: str | None
    sha256: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _direct_cells(row: Any) -> list[Any]:
    return row.find_all(["th", "td"], recursive=False)


def _source_date(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError as error:
        raise DCAppellateSourceChangedError(
            "source_date_changed",
            f"C-Track {field_name} is not MM/DD/YYYY: {value!r}",
            details={"field": field_name, "value": value},
        ) from error


def _native_query_date(value: str | None, *, field_name: str) -> str:
    if value is None:
        return ""
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise DCAppellateSelectionError(
            "invalid_date",
            f"{field_name} must be an ISO calendar date",
            details={"field": field_name, "value": value},
        ) from error
    return parsed.strftime("%m/%d/%Y")


def _schema_fingerprint(headers: Sequence[str]) -> str:
    return hashlib.sha256(canonical_json(list(headers)).encode()).hexdigest()


def _native_case_id(value: str) -> str:
    parsed = urlparse(urljoin(BASE_URL, value))
    if (
        parsed.scheme != "https"
        or parsed.hostname != "efile.dcappeals.gov"
        or not _CASE_VIEW_RE.fullmatch(parsed.path)
    ):
        raise DCAppellateSourceChangedError(
            "unexpected_case_link",
            "C-Track result points outside the public case-view route",
            details={"url": value},
        )
    identifiers = parse_qs(parsed.query).get("csIID", [])
    if len(identifiers) != 1 or not identifiers[0].isdigit():
        raise DCAppellateSourceChangedError(
            "invalid_case_link",
            "C-Track case-view link lacks one numeric csIID",
            details={"url": value},
        )
    return identifiers[0]


def _case_url(case_internal_id: str) -> str:
    if not str(case_internal_id).isdigit():
        raise DCAppellateSelectionError(
            "invalid_case_internal_id",
            "C-Track case internal ID must be numeric",
            details={"case_internal_id": case_internal_id},
        )
    return f"{BASE_URL}{CASE_VIEW_PATH}?csIID={case_internal_id}"


def _official_document_url(
    value: str,
    *,
    expected_case_internal_id: str | None = None,
) -> str:
    parsed = urlparse(urljoin(BASE_URL, value))
    if (
        parsed.scheme != "https"
        or parsed.hostname != "efile.dcappeals.gov"
        or parsed.path != DOCUMENT_VIEW_PATH
    ):
        raise DCAppellateSelectionError(
            "invalid_document_url",
            "Document URL must identify the official C-Track document route",
            details={"url": value},
        )
    query = parse_qs(parsed.query)
    document_ids = query.get("documentID", [])
    case_ids = query.get("csIID", [])
    if (
        len(document_ids) != 1
        or not document_ids[0].isdigit()
        or len(case_ids) != 1
        or not case_ids[0].isdigit()
    ):
        raise DCAppellateSelectionError(
            "invalid_document_url",
            "C-Track document URL needs numeric documentID and csIID",
            details={"url": value},
        )
    if (
        expected_case_internal_id is not None
        and case_ids[0] != expected_case_internal_id
    ):
        raise DCAppellateSourceChangedError(
            "document_case_mismatch",
            "Resolved C-Track document belongs to a different case",
            details={
                "url": value,
                "expected_case_internal_id": expected_case_internal_id,
            },
        )
    return parsed.geturl()


def _range(soup: BeautifulSoup) -> tuple[int, int, int] | None:
    match = _RANGE_RE.search(soup.get_text(" ", strip=True))
    if match is None:
        return None
    return tuple(int(value.replace(",", "")) for value in match.groups())


def _result_table(
    soup: BeautifulSoup,
    *,
    expected_headers: Sequence[str],
) -> Any | None:
    expected = tuple(expected_headers)
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            classes = set(row.get("class", ()))
            if "TableSubHeading" not in classes:
                continue
            headers = tuple(
                _text(cell.get_text(" ", strip=True)) or ""
                for cell in _direct_cells(row)
            )
            if headers == expected:
                return table
    return None


def _search_hit(
    cells: Sequence[Any],
    *,
    source_url: str,
    schema_fingerprint: str,
) -> dict[str, Any]:
    if len(cells) != len(CASE_RESULT_HEADERS):
        raise DCAppellateSourceChangedError(
            "case_result_width_changed",
            "C-Track case result does not contain seven columns",
            details={"observed_columns": len(cells)},
        )
    link = cells[0].find("a", href=True)
    if link is None:
        raise DCAppellateSourceChangedError(
            "case_result_link_missing",
            "C-Track case result lacks its case-view link",
        )
    case_number = _text(cells[0].get_text(" ", strip=True))
    caption = _text(cells[1].get_text(" ", strip=True))
    if case_number is None or caption is None:
        raise DCAppellateSourceChangedError(
            "case_result_identity_missing",
            "C-Track case result lacks case number or caption",
        )
    case_internal_id = _native_case_id(str(link["href"]))
    originating_case_number = _text(cells[6].get_text(" ", strip=True))
    if (
        originating_case_number is not None
        and originating_case_number.casefold() == "not specified"
    ):
        originating_case_number = None
    record = {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case_number,
            native_id=case_internal_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case_search_hit",
        "court_id": COURT_ID,
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "appellate_case_number": case_number,
        "source_internal_id": case_internal_id,
        "caption": caption,
        "case_group": _text(cells[2].get_text(" ", strip=True)),
        "case_type": _text(cells[3].get_text(" ", strip=True)),
        "case_subtype": _text(cells[4].get_text(" ", strip=True)),
        "status": _text(cells[5].get_text(" ", strip=True)),
        "originating_case_number": originating_case_number,
        "originating_case_number_label": (
            "Superior Court or Agency Case Number"
        ),
        "source_url": _case_url(case_internal_id),
        "search_result_url": source_url,
        "access_state": "public",
        "schema_fingerprint": schema_fingerprint,
    }
    record["related_source_routes"] = related_source_routes(
        appellate_case_number=case_number,
        originating_case_number=originating_case_number,
    )
    return record


def _participant_hit(
    cells: Sequence[Any],
    *,
    source_url: str,
    schema_fingerprint: str,
) -> dict[str, Any]:
    if len(cells) != len(PARTICIPANT_RESULT_HEADERS):
        raise DCAppellateSourceChangedError(
            "participant_result_width_changed",
            "C-Track participant result does not contain six columns",
            details={"observed_columns": len(cells)},
        )
    link = cells[0].find("a", href=True)
    if link is None:
        raise DCAppellateSourceChangedError(
            "participant_result_link_missing",
            "C-Track participant result lacks its case-view link",
        )
    case_number = _text(cells[0].get_text(" ", strip=True))
    participant = _text(cells[1].get_text(" ", strip=True))
    if case_number is None or participant is None:
        raise DCAppellateSourceChangedError(
            "participant_result_identity_missing",
            "C-Track participant result lacks case number or participant",
        )
    case_internal_id = _native_case_id(str(link["href"]))
    native_entry_id = hashlib.sha256(
        canonical_json(
            {
                "case_internal_id": case_internal_id,
                "participant": participant,
                "role": _text(cells[2].get_text(" ", strip=True)),
            }
        ).encode()
    ).hexdigest()[:24]
    record = {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case_number,
            record_kind="participant_search_hit",
            native_id=native_entry_id,
        ),
        "case_canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case_number,
            native_id=case_internal_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "participant_search_hit",
        "court_id": COURT_ID,
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "appellate_case_number": case_number,
        "source_internal_id": case_internal_id,
        "native_entry_id": native_entry_id,
        "participant_name": participant,
        "appellate_role": _text(cells[2].get_text(" ", strip=True)),
        "caption": _text(cells[3].get_text(" ", strip=True)),
        "appeal_filed_date": _source_date(
            _text(cells[4].get_text(" ", strip=True)),
            field_name="participant appeal filed date",
        ),
        "case_subtype": _text(cells[5].get_text(" ", strip=True)),
        "source_url": _case_url(case_internal_id),
        "search_result_url": source_url,
        "access_state": "public",
        "schema_fingerprint": schema_fingerprint,
    }
    record["related_source_routes"] = related_source_routes(
        appellate_case_number=case_number,
    )
    return record


def parse_search_results(
    html: str,
    *,
    operation: str,
    source_url: str,
    requested_start_row: int,
) -> DCAppellatePage:
    """Parse one case-search or participant-search result page."""

    if operation not in {"search", "participant"}:
        raise ValueError(f"unknown C-Track result operation: {operation}")
    soup = BeautifulSoup(str(html), "html.parser")
    lowered = soup.get_text(" ", strip=True).casefold()
    if any(marker in lowered for marker in _CHALLENGE_MARKERS):
        raise DCAppellateCasesError(
            "source_access_challenge",
            "C-Track returned an interactive verification page",
            status=ResultStatus.HUMAN_REQUIRED,
            category="source_access",
            retryable=True,
            details={"url": source_url},
        )
    expected_headers = (
        CASE_RESULT_HEADERS
        if operation == "search"
        else PARTICIPANT_RESULT_HEADERS
    )
    form = soup.select_one("form#paginatedSearchForm")
    if form is None:
        raise DCAppellateSourceChangedError(
            "search_form_missing",
            f"C-Track {operation} page lacks its paginated search form",
            details={"url": source_url},
        )
    required_names = (
        {"csNumber", "shortTitle", "lcCsNumber", "startRow", "displayRows"}
        if operation == "search"
        else {"lastNm", "firstNm", "middleNm", "startRow", "displayRows"}
    )
    observed_names = {
        str(field.get("name"))
        for field in form.find_all(["input", "select"])
        if field.get("name")
    }
    missing_names = sorted(required_names - observed_names)
    if missing_names:
        raise DCAppellateSourceChangedError(
            "search_fields_changed",
            f"C-Track {operation} form fields changed",
            details={"missing_fields": missing_names},
        )
    result_table = _result_table(soup, expected_headers=expected_headers)
    page_range = _range(soup)
    if result_table is None:
        if page_range is not None and page_range[2] > 0:
            raise DCAppellateSourceChangedError(
                "results_table_missing",
                f"C-Track {operation} reports rows without its result table",
                details={"range": page_range},
            )
        return DCAppellatePage(
            operation=operation,
            records=(),
            start_row=requested_start_row,
            end_row=0,
            total_rows=0,
            next_start_row=None,
            source_url=source_url,
            schema_fingerprint=_schema_fingerprint(expected_headers),
        )
    if page_range is None:
        raise DCAppellateSourceChangedError(
            "result_range_missing",
            f"C-Track {operation} results lack the native row range",
        )
    start_row, end_row, total_rows = page_range
    if start_row != requested_start_row:
        raise DCAppellateSourceChangedError(
            "result_start_mismatch",
            "C-Track returned a different start row than requested",
            details={
                "requested_start_row": requested_start_row,
                "observed_start_row": start_row,
            },
        )
    schema = _schema_fingerprint(expected_headers)
    records: list[Mapping[str, Any]] = []
    for row in result_table.find_all("tr"):
        if not ({"OddRow", "EvenRow"} & set(row.get("class", ()))):
            continue
        cells = _direct_cells(row)
        record = (
            _search_hit(
                cells,
                source_url=source_url,
                schema_fingerprint=schema,
            )
            if operation == "search"
            else _participant_hit(
                cells,
                source_url=source_url,
                schema_fingerprint=schema,
            )
        )
        records.append(record)
    expected_count = end_row - start_row + 1
    if len(records) != expected_count:
        raise DCAppellateSourceChangedError(
            "result_count_mismatch",
            "C-Track result rows do not match the reported page range",
            details={
                "reported_count": expected_count,
                "parsed_count": len(records),
            },
        )
    next_start = end_row + 1 if end_row < total_rows else None
    return DCAppellatePage(
        operation=operation,
        records=tuple(records),
        start_row=start_row,
        end_row=end_row,
        total_rows=total_rows,
        next_start_row=next_start,
        source_url=source_url,
        schema_fingerprint=schema,
    )


def _case_information(soup: BeautifulSoup) -> tuple[Any, str]:
    for table in soup.select("table.FormTable"):
        heading = table.find("tr", class_="TableHeading")
        if heading is None:
            continue
        heading_text = _text(heading.get_text(" ", strip=True))
        if heading_text is None:
            continue
        match = _CASE_HEADING_RE.fullmatch(heading_text)
        if match:
            return table, match.group(1).strip()
    raise DCAppellateSourceChangedError(
        "case_information_missing",
        "C-Track case view lacks the case-information table",
    )


def _case_fields(table: Any) -> dict[str, str | None]:
    fields: dict[str, str | None] = {}
    for row in table.find_all("tr", recursive=False):
        cells = _direct_cells(row)
        for index, cell in enumerate(cells[:-1]):
            if "label" not in set(cell.get("class", ())):
                continue
            label = (_text(cell.get_text(" ", strip=True)) or "").rstrip(":")
            if label:
                fields[label] = _text(
                    cells[index + 1].get_text(" ", strip=True)
                )
    return fields


def _party_records(
    soup: BeautifulSoup,
    *,
    case_number: str,
    case_internal_id: str,
) -> list[dict[str, Any]]:
    table = soup.select_one("table#partyInfo")
    if table is None:
        return []
    header_row = table.find("tr", class_="TableSubHeading")
    headers = (
        tuple(
            _text(cell.get_text(" ", strip=True)) or ""
            for cell in _direct_cells(header_row)
        )
        if header_row is not None
        else ()
    )
    if headers != PARTY_HEADERS:
        raise DCAppellateSourceChangedError(
            "party_headers_changed",
            "C-Track party table headers changed",
            details={"observed_headers": headers},
        )
    records: list[dict[str, Any]] = []
    for row_index, row in enumerate(table.find_all("tr", recursive=False)):
        if not ({"OddRow", "EvenRow"} & set(row.get("class", ()))):
            continue
        cells = _direct_cells(row)
        if len(cells) < 4:
            raise DCAppellateSourceChangedError(
                "party_row_width_changed",
                "C-Track party row has fewer than four cells",
                details={"observed_columns": len(cells)},
            )
        role = _text(cells[0].get_text(" ", strip=True))
        party_name = _text(cells[1].get_text(" ", strip=True))
        if role is None or party_name is None:
            raise DCAppellateSourceChangedError(
                "party_identity_missing",
                "C-Track party row lacks role or party name",
            )
        ifp = _text(cells[2].get_text(" ", strip=True))
        attorneys: list[dict[str, Any]] = []
        nested = cells[3].find("table")
        representation = None
        if nested is not None:
            for attorney_row in nested.find_all("tr"):
                attorney_cells = _direct_cells(attorney_row)
                if not attorney_cells:
                    continue
                attorney_name = _text(
                    attorney_cells[0].get_text(" ", strip=True)
                )
                if attorney_name is None:
                    continue
                attorneys.append(
                    {
                        "name": attorney_name,
                        "arguing_attorney": (
                            _text(
                                attorney_cells[1].get_text(" ", strip=True)
                            )
                            if len(attorney_cells) > 1
                            else None
                        ),
                        "e_filer": (
                            _text(
                                attorney_cells[2].get_text(" ", strip=True)
                            )
                            if len(attorney_cells) > 2
                            else None
                        ),
                    }
                )
        else:
            representation = _text(cells[3].get_text(" ", strip=True))
            if representation and representation.casefold() != "pro se":
                attorneys.append(
                    {
                        "name": representation,
                        "arguing_attorney": (
                            _text(cells[4].get_text(" ", strip=True))
                            if len(cells) > 4
                            else None
                        ),
                        "e_filer": (
                            _text(cells[5].get_text(" ", strip=True))
                            if len(cells) > 5
                            else None
                        ),
                    }
                )
        native_party_id = hashlib.sha256(
            canonical_json(
                {
                    "case_internal_id": case_internal_id,
                    "row_index": row_index,
                    "role": role,
                    "party_name": party_name,
                }
            ).encode()
        ).hexdigest()[:24]
        records.append(
            {
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    case_number,
                    record_kind="party",
                    native_id=native_party_id,
                ),
                "source_id": SOURCE_ID,
                "record_kind": "party",
                "native_party_id": native_party_id,
                "appellate_role": role,
                "party_name": party_name,
                "ifp": ifp,
                "representation": representation,
                "attorneys": attorneys,
                "access_state": "public",
            }
        )
    return records


def _events_table(soup: BeautifulSoup) -> Any | None:
    for table in soup.select("table.FormTable"):
        heading = table.find("tr", class_="TableHeading")
        if (
            heading is not None
            and _text(heading.get_text(" ", strip=True)) == "Events"
        ):
            return table
    return None


def _event_records(
    soup: BeautifulSoup,
    *,
    case_number: str,
    case_internal_id: str,
) -> list[dict[str, Any]]:
    table = _events_table(soup)
    if table is None:
        return []
    header_row = table.find("tr", class_="TableSubHeading")
    headers = (
        tuple(
            _text(cell.get_text(" ", strip=True)) or ""
            for cell in _direct_cells(header_row)
        )
        if header_row is not None
        else ()
    )
    if headers != EVENT_HEADERS:
        raise DCAppellateSourceChangedError(
            "event_headers_changed",
            "C-Track event table headers changed",
            details={"observed_headers": headers},
        )
    records: list[dict[str, Any]] = []
    for row_index, row in enumerate(table.find_all("tr", recursive=False)):
        if not ({"OddRow", "EvenRow"} & set(row.get("class", ()))):
            continue
        cells = _direct_cells(row)
        if len(cells) != len(EVENT_HEADERS):
            raise DCAppellateSourceChangedError(
                "event_row_width_changed",
                "C-Track event row does not contain five columns",
                details={"observed_columns": len(cells)},
            )
        event_date_raw = _text(cells[0].get_text(" ", strip=True))
        status = _text(cells[1].get_text(" ", strip=True))
        description = _text(cells[2].get_text(" ", strip=True))
        result = _text(cells[3].get_text(" ", strip=True))
        if event_date_raw is None or status is None or description is None:
            raise DCAppellateSourceChangedError(
                "event_identity_missing",
                "C-Track event lacks date, status, or description",
            )
        locator = None
        image = cells[4].select_one("img.documentLink[name]")
        if image is not None:
            match = _DOCUMENT_LOCATOR_RE.fullmatch(str(image["name"]))
            if match is None:
                raise DCAppellateSourceChangedError(
                    "document_locator_changed",
                    "C-Track event document locator has an unexpected shape",
                    details={"locator": image["name"]},
                )
            locator = match.groupdict()
            if locator["case_id"] != case_internal_id:
                raise DCAppellateSourceChangedError(
                    "document_locator_case_mismatch",
                    "C-Track event document locator belongs to another case",
                    details={
                        "locator_case_id": locator["case_id"],
                        "case_internal_id": case_internal_id,
                    },
                )
        native_event_id = (
            locator["event_id"]
            if locator is not None
            else hashlib.sha256(
                canonical_json(
                    {
                        "case_internal_id": case_internal_id,
                        "row_index": row_index,
                        "date": event_date_raw,
                        "status": status,
                        "description": description,
                        "result": result,
                    }
                ).encode()
            ).hexdigest()[:24]
        )
        records.append(
            {
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    case_number,
                    record_kind="docket_event",
                    native_id=native_event_id,
                ),
                "source_id": SOURCE_ID,
                "record_kind": "docket_event",
                "native_event_id": native_event_id,
                "event_date": _source_date(
                    event_date_raw,
                    field_name="event date",
                ),
                "source_date_raw": event_date_raw,
                "status": status,
                "description": description,
                "result": result,
                "document_state": (
                    "resolver_available"
                    if locator is not None
                    else "not_linked"
                ),
                "document_locator": locator,
                "documents": [],
                "access_state": "public",
            }
        )
    return records


def parse_case_view(html: str, *, source_url: str) -> dict[str, Any]:
    """Parse one official C-Track public case page."""

    soup = BeautifulSoup(str(html), "html.parser")
    lowered = soup.get_text(" ", strip=True).casefold()
    if any(marker in lowered for marker in _CHALLENGE_MARKERS):
        raise DCAppellateCasesError(
            "source_access_challenge",
            "C-Track returned an interactive verification page",
            status=ResultStatus.HUMAN_REQUIRED,
            category="source_access",
            retryable=True,
            details={"url": source_url},
        )
    form = soup.select_one("form#caseViewForm")
    if form is None:
        raise DCAppellateSourceChangedError(
            "case_view_form_missing",
            "C-Track case page lacks its case-view form",
            details={"url": source_url},
        )
    internal_input = form.select_one('input[name="csIID"]')
    if internal_input is None or not str(internal_input.get("value", "")).isdigit():
        raise DCAppellateSourceChangedError(
            "case_internal_id_missing",
            "C-Track case page lacks a numeric csIID",
        )
    case_internal_id = str(internal_input["value"])
    table, case_number = _case_information(soup)
    fields = _case_fields(table)
    caption = fields.get("Short Caption")
    classification = fields.get("Classification")
    if caption is None or classification is None:
        raise DCAppellateSourceChangedError(
            "case_required_fields_missing",
            "C-Track case page lacks caption or classification",
        )
    originating_case_number = fields.get(
        "Superior Court or Agency Case Number"
    )
    if (
        originating_case_number is not None
        and originating_case_number.casefold() == "not specified"
    ):
        originating_case_number = None
    parties = _party_records(
        soup,
        case_number=case_number,
        case_internal_id=case_internal_id,
    )
    events = _event_records(
        soup,
        case_number=case_number,
        case_internal_id=case_internal_id,
    )
    schema = _schema_fingerprint(
        (
            *sorted(fields),
            *PARTY_HEADERS,
            *EVENT_HEADERS,
        )
    )
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case_number,
            native_id=case_internal_id,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "court_id": COURT_ID,
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "appellate_case_number": case_number,
        "source_internal_id": case_internal_id,
        "caption": caption,
        "classification": classification,
        "originating_case_number": originating_case_number,
        "originating_case_number_label": (
            "Superior Court or Agency Case Number"
        ),
        "filed_date": _source_date(
            fields.get("Filed Date"),
            field_name="filed date",
        ),
        "opening_event_date": _source_date(
            fields.get("Opening Event Date"),
            field_name="opening event date",
        ),
        "status": fields.get("Case Status"),
        "record_completed_date": _source_date(
            fields.get("Record Completed"),
            field_name="record completed date",
        ),
        "post_decision_matter_pending": fields.get(
            "Post-Decision Matter Pending"
        ),
        "briefs_completed": fields.get("Briefs Completed"),
        "argued_or_submitted": fields.get("Argued/Submitted"),
        "disposition": fields.get("Disposition"),
        "next_scheduled_action": fields.get("Next Scheduled Action"),
        "mandate_issued_date": _source_date(
            fields.get("Mandate Issued"),
            field_name="mandate issued date",
        ),
        "parties": parties,
        "docket_events": events,
        "documents": [],
        "source_url": _case_url(case_internal_id),
        "access_state": "public",
        "schema_fingerprint": schema,
        "related_source_routes": related_source_routes(
            appellate_case_number=case_number,
            originating_case_number=originating_case_number,
        ),
    }


def parse_document_links(
    body: str,
    *,
    case_number: str,
    case_internal_id: str,
    event_id: str,
) -> list[dict[str, Any]]:
    """Parse the DWR fragment returned for one docket-event document icon."""

    match = _DWR_CALLBACK_RE.search(str(body))
    if match is None:
        raise DCAppellateSourceChangedError(
            "document_resolver_response_changed",
            "C-Track document resolver lacks its DWR callback",
            details={"event_id": event_id},
        )
    try:
        fragment = json.loads(match.group("payload"))
    except json.JSONDecodeError as error:
        raise DCAppellateSourceChangedError(
            "document_resolver_payload_invalid",
            "C-Track document resolver returned invalid escaped HTML",
            details={"event_id": event_id},
        ) from error
    soup = BeautifulSoup(html_lib.unescape(fragment), "html.parser")
    records: list[dict[str, Any]] = []
    for anchor in soup.find_all("a", href=True):
        document_url = _official_document_url(
            str(anchor["href"]),
            expected_case_internal_id=case_internal_id,
        )
        document_id = parse_qs(urlparse(document_url).query)["documentID"][0]
        title = _text(anchor.get_text(" ", strip=True)) or "Court filing"
        records.append(
            {
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    case_number,
                    record_kind="document",
                    native_id=document_id,
                ),
                "source_id": SOURCE_ID,
                "record_kind": "document_artifact",
                "native_document_id": document_id,
                "source_event_id": event_id,
                "case_internal_id": case_internal_id,
                "document_title": title,
                "source_url": document_url,
                "download_url": document_url,
                "mime_type": "application/pdf",
                "access_state": "public",
            }
        )
    if not records:
        raise DCAppellateSourceChangedError(
            "document_resolver_empty",
            "C-Track document icon resolved without a public document link",
            details={"event_id": event_id},
        )
    return records


def related_source_routes(
    *,
    appellate_case_number: str | None = None,
    originating_case_number: str | None = None,
) -> list[dict[str, Any]]:
    """Return explicit official complements and their useful join keys."""

    trial_selector = (
        {"case_number": originating_case_number}
        if originating_case_number
        else None
    )
    appellate_selector = (
        {"appellate_case_number": appellate_case_number}
        if appellate_case_number
        else None
    )
    return [
        {
            "source_id": "us-dc-superior-court-portal",
            "relationship": "originating_trial_case_detail",
            "coverage": (
                "Civil including Landlord and Tenant and Small Claims, "
                "civil Tax, Auditor-Master, and Probate"
            ),
            "join_keys": ["originating_case_number", "party_name"],
            "selector": trial_selector,
            "url": SUPERIOR_PORTAL_URL,
            "operation": "smart_search",
            "operation_state": "human_verification_observed",
            "observed_on": "2026-07-30",
        },
        {
            "source_id": "us-dc-superior-eaccess",
            "relationship": "originating_trial_case_detail",
            "coverage": (
                "Criminal, criminal Tax, and Domestic Violence"
            ),
            "join_keys": ["originating_case_number", "party_name"],
            "selector": trial_selector,
            "url": SUPERIOR_EACCESS_URL,
            "operation": "case_search",
            "operation_state": "captcha_observed",
            "observed_on": "2026-07-30",
        },
        {
            "source_id": "us-dc-superior-court-today-calendar",
            "relationship": "current_trial_hearing_discovery",
            "join_keys": ["originating_case_number", "party_name"],
            "selector": trial_selector,
            "adapter_tool": "query_dc_superior_calendar.py",
            "adapter_command": "search",
            "operation_state": "direct_anonymous",
        },
        {
            "source_id": "us-dc-superior-court-criminal-calendar",
            "relationship": "current_criminal_hearing_discovery",
            "join_keys": ["originating_case_number", "party_name"],
            "selector": trial_selector,
            "adapter_tool": "query_dc_superior_calendar.py",
            "adapter_command": "criminal",
            "operation_state": "direct_anonymous",
        },
        {
            "source_id": "us-dc-court-of-appeals-opinions-mojs",
            "relationship": "appellate_disposition_and_publication",
            "join_keys": ["appellate_case_number", "caption"],
            "selector": appellate_selector,
            "adapter_tool": "query_dc_opinions.py",
            "adapter_command": "list",
            "operation_state": "direct_anonymous",
        },
        {
            "source_id": "us-dc-court-of-appeals-calendars",
            "relationship": "appellate_schedule_artifacts",
            "join_keys": ["appellate_case_number", "caption"],
            "selector": appellate_selector,
            "adapter_tool": "query_dc_superior_calendar.py",
            "adapter_command": "appeals",
            "operation_state": "direct_anonymous",
        },
        {
            "source_id": "us-dc-itspe-public-extract",
            "relationship": "property_context_for_case_addresses_or_square_lot",
            "join_keys": ["address", "square_lot_ssl"],
            "selector": None,
            "adapter_tool": "query_dc_property.py",
            "operation_state": "direct_anonymous",
        },
        {
            "source_id": "us-dc-recorder-of-deeds-public-records",
            "relationship": "recorded_instrument_context_for_case_property",
            "join_keys": [
                "party_name",
                "address",
                "square_lot_ssl",
                "instrument_number",
            ],
            "selector": None,
            "operation_state": "account_evaluation",
        },
    ]


def source_manifest() -> dict[str, Any]:
    """Return the source contract and explicit alternative-source graph."""

    return {
        "family": "District of Columbia appellate case records",
        "sources": [SOURCE_METADATA.to_dict()],
        "operations": {
            "search": {
                "representation": "html_post_result_or_exact_redirect",
                "native_page_size": NATIVE_PAGE_SIZE,
                "pagination": "one_based_start_row",
                "originating_case_number_field": "lcCsNumber",
            },
            "participant": {
                "representation": "html_post_results",
                "native_page_size": NATIVE_PAGE_SIZE,
                "pagination": "one_based_start_row",
            },
            "case": {
                "representation": "html_case_view",
                "includes": [
                    "case_metadata",
                    "originating_case_number",
                    "parties",
                    "attorneys",
                    "docket_events",
                    "document_locators",
                ],
            },
            "resolve_documents": {
                "representation": "dwr_html_fragment",
                "method": "AJAX.getViewDocumentLinks",
            },
            "download": {
                "representation": "source_attachment",
                "validated_artifact": "pdf",
            },
        },
        "component_access_outcomes": [
            route
            for route in related_source_routes()
            if route["source_id"]
            in {
                "us-dc-superior-court-portal",
                "us-dc-superior-eaccess",
            }
        ],
        "related_source_routes": related_source_routes(),
        "coverage_notes": list(SOURCE_WARNINGS),
    }


class DCAppellateCasesClient:
    """Paced, retrying client for the official public C-Track system."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self._primed_paths: set[str] = set()
        headers = getattr(self.session, "headers", None)
        if headers is not None:
            headers.update(
                {
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/pdf;q=0.9,*/*;q=0.5"
                    ),
                    "Accept-Language": "en-US,en;q=0.8",
                }
            )

    def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Any:
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    **kwargs,
                )
            except requests.RequestException as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise DCAppellateCasesError(
                        "transport_error",
                        f"C-Track request failed: {error}",
                        category="transport",
                        retryable=True,
                        details={"url": url},
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            status_code = int(response.status_code)
            if (
                status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status_code == 429:
                raise DCAppellateCasesError(
                    "source_rate_limited",
                    "C-Track rate-limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="http",
                    retryable=True,
                    details={"url": url, "http_status": status_code},
                )
            if status_code != 200:
                raise DCAppellateCasesError(
                    "source_http_error",
                    f"C-Track returned HTTP {status_code}",
                    category="http",
                    retryable=status_code >= 500,
                    details={"url": url, "http_status": status_code},
                )
            return response
        raise AssertionError("retry loop exhausted")

    def _prime(self, url: str) -> None:
        path = urlparse(url).path
        if path in self._primed_paths:
            return
        response = self._request("GET", url)
        final_url = str(getattr(response, "url", url))
        if urlparse(final_url).hostname != "efile.dcappeals.gov":
            raise DCAppellateSourceChangedError(
                "unexpected_prime_redirect",
                "C-Track search form redirected outside the official host",
                details={"url": final_url},
            )
        self._primed_paths.add(path)

    @staticmethod
    def _search_payload(
        selection: Mapping[str, Any],
        *,
        start_row: int,
    ) -> dict[str, str]:
        return {
            "action": "",
            "csNumber": str(selection.get("appellate_case_number") or ""),
            "shortTitle": str(selection.get("caption") or ""),
            "lcCsNumber": str(selection.get("originating_case_number") or ""),
            "fromDt": str(selection.get("date_from_native") or ""),
            "toDt": str(selection.get("date_to_native") or ""),
            "exclude": (
                "on" if selection.get("open_only") else ""
            ),
            "startRow": str(start_row),
            "displayRows": str(NATIVE_PAGE_SIZE),
            "orderBy": str(selection.get("order_by") or "CsNumber"),
            "orderDir": str(selection.get("order_direction") or "DESC"),
            "href": CASE_VIEW_PATH,
            "submitValue": "Search",
        }

    @staticmethod
    def _participant_payload(
        selection: Mapping[str, Any],
        *,
        start_row: int,
    ) -> dict[str, str]:
        return {
            "action": "",
            "lastNm": str(selection.get("last_name") or ""),
            "firstNm": str(selection.get("first_name") or ""),
            "middleNm": str(selection.get("middle_name") or ""),
            "startRow": str(start_row),
            "displayRows": str(NATIVE_PAGE_SIZE),
            "orderBy": str(selection.get("order_by") or "FileDt"),
            "orderDir": str(selection.get("order_direction") or "DESC"),
            "href": CASE_VIEW_PATH,
            "submitValue": "Search",
        }

    def fetch_page(
        self,
        operation: str,
        selection: Mapping[str, Any],
        *,
        start_row: int,
    ) -> DCAppellatePage:
        if start_row < 1:
            raise DCAppellateSelectionError(
                "invalid_start_row",
                "C-Track start row must be at least 1",
            )
        if (start_row - 1) % NATIVE_PAGE_SIZE:
            raise DCAppellateSelectionError(
                "invalid_start_row",
                "C-Track start row must align to its 50-row pages",
                details={"start_row": start_row},
            )
        if operation == "search":
            url = CASE_SEARCH_URL
            payload = self._search_payload(selection, start_row=start_row)
        elif operation == "participant":
            url = PARTICIPANT_SEARCH_URL
            payload = self._participant_payload(selection, start_row=start_row)
        else:
            raise ValueError(f"unknown C-Track operation: {operation}")
        self._prime(url)
        response = self._request(
            "POST",
            url,
            data=payload,
            headers={"Referer": url, "Origin": BASE_URL},
        )
        final_url = str(getattr(response, "url", url))
        parsed = urlparse(final_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "efile.dcappeals.gov"
        ):
            raise DCAppellateSourceChangedError(
                "unexpected_search_redirect",
                "C-Track search redirected outside the official host",
                details={"url": final_url},
            )
        if parsed.path == CASE_VIEW_PATH:
            if operation != "search":
                raise DCAppellateSourceChangedError(
                    "participant_redirect_changed",
                    "C-Track participant search redirected directly to a case",
                    details={"url": final_url},
                )
            record = parse_case_view(response.text, source_url=final_url)
            return DCAppellatePage(
                operation=operation,
                records=(record,),
                start_row=1,
                end_row=1,
                total_rows=1,
                next_start_row=None,
                source_url=final_url,
                schema_fingerprint=str(record["schema_fingerprint"]),
            )
        expected_path = (
            CASE_SEARCH_PATH
            if operation == "search"
            else PARTICIPANT_SEARCH_PATH
        )
        if parsed.path.rstrip(";").split(";", 1)[0] != expected_path:
            raise DCAppellateSourceChangedError(
                "unexpected_search_path",
                "C-Track returned an unexpected public-search path",
                details={"url": final_url},
            )
        return parse_search_results(
            response.text,
            operation=operation,
            source_url=final_url,
            requested_start_row=start_row,
        )

    def fetch_all(
        self,
        operation: str,
        selection: Mapping[str, Any],
        *,
        start_row: int = 1,
    ) -> DCAppellateCollection:
        pages: list[DCAppellatePage] = []
        next_start = start_row
        seen: set[int] = set()
        incomplete_error: DCAppellateCasesError | None = None
        while next_start not in seen:
            seen.add(next_start)
            try:
                page = self.fetch_page(
                    operation,
                    selection,
                    start_row=next_start,
                )
            except DCAppellateCasesError as error:
                if not pages:
                    raise
                incomplete_error = error
                break
            pages.append(page)
            if page.next_start_row is None:
                break
            next_start = page.next_start_row
        if not pages:
            raise AssertionError("fetch_all returned without a page or error")
        return DCAppellateCollection(
            records=tuple(
                record for page in pages for record in page.records
            ),
            pages_fetched=len(pages),
            total_rows=pages[0].total_rows,
            source_urls=tuple(page.source_url for page in pages),
            schema_fingerprints=tuple(
                page.schema_fingerprint for page in pages
            ),
            incomplete_error=incomplete_error,
        )

    def fetch_case(self, case_internal_id: str) -> dict[str, Any]:
        url = _case_url(case_internal_id)
        response = self._request("GET", url)
        final_url = str(getattr(response, "url", url))
        parsed = urlparse(final_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "efile.dcappeals.gov"
            or parsed.path != CASE_VIEW_PATH
        ):
            raise DCAppellateSourceChangedError(
                "unexpected_case_redirect",
                "C-Track case request returned an unexpected location",
                details={"url": final_url},
            )
        record = parse_case_view(response.text, source_url=final_url)
        if str(record["source_internal_id"]) != str(case_internal_id):
            raise DCAppellateSourceChangedError(
                "case_internal_id_mismatch",
                "C-Track returned a different case internal ID",
                details={
                    "requested": case_internal_id,
                    "observed": record["source_internal_id"],
                },
            )
        return record

    def find_case(self, case_number: str) -> dict[str, Any]:
        selection = {
            "appellate_case_number": case_number,
            "caption": "",
            "originating_case_number": "",
            "date_from_native": "",
            "date_to_native": "",
            "open_only": False,
            "order_by": "CsNumber",
            "order_direction": "DESC",
        }
        page = self.fetch_page("search", selection, start_row=1)
        exact = [
            record
            for record in page.records
            if str(record.get("appellate_case_number", "")).casefold()
            == case_number.strip().casefold()
        ]
        if not exact:
            raise DCAppellateCasesError(
                "case_not_found",
                f"C-Track returned no exact case for {case_number!r}",
                status=ResultStatus.NO_RESULTS,
                category="source",
                details={"case_number": case_number},
            )
        record = exact[0]
        if record.get("record_kind") == "case":
            return dict(record)
        return self.fetch_case(str(record["source_internal_id"]))

    def resolve_document_locator(
        self,
        *,
        case_number: str,
        locator: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        method_code = str(locator.get("method_code") or "")
        event_id = str(locator.get("event_id") or "")
        case_internal_id = str(locator.get("case_id") or "")
        if not (
            method_code.isdigit()
            and event_id.isdigit()
            and case_internal_id.isdigit()
        ):
            raise DCAppellateSelectionError(
                "invalid_document_locator",
                "C-Track document locator needs numeric method, event, and case IDs",
                details={"locator": dict(locator)},
            )
        payload = {
            "callCount": "1",
            "page": f"{CASE_VIEW_PATH}?csIID={case_internal_id}",
            "httpSessionId": "",
            "scriptSessionId": secrets.token_hex(20).upper(),
            "c0-scriptName": "AJAX",
            "c0-methodName": "getViewDocumentLinks",
            "c0-id": "0",
            "c0-param0": f"string:{method_code}",
            "c0-param1": f"string:{event_id}",
            "c0-param2": f"string:{case_internal_id}",
            "batchId": "0",
        }
        response = self._request(
            "POST",
            DOCUMENT_RESOLVER_URL,
            data=payload,
            headers={
                "Referer": _case_url(case_internal_id),
                "Origin": BASE_URL,
            },
        )
        return parse_document_links(
            response.text,
            case_number=case_number,
            case_internal_id=case_internal_id,
            event_id=event_id,
        )

    def resolve_case_documents(
        self,
        record: Mapping[str, Any],
    ) -> dict[str, Any]:
        case_number = str(record["appellate_case_number"])
        enriched_events: list[dict[str, Any]] = []
        documents: list[dict[str, Any]] = []
        for event in record.get("docket_events", ()):
            enriched = dict(event)
            locator = enriched.get("document_locator")
            if isinstance(locator, Mapping):
                resolved = self.resolve_document_locator(
                    case_number=case_number,
                    locator=locator,
                )
                enriched["documents"] = resolved
                enriched["document_state"] = "resolved"
                documents.extend(resolved)
            enriched_events.append(enriched)
        enriched_record = dict(record)
        enriched_record["docket_events"] = enriched_events
        enriched_record["documents"] = documents
        return enriched_record

    def fetch_document(self, source_url: str) -> DCAppellateDocument:
        safe_url = _official_document_url(source_url)
        response = self._request("GET", safe_url)
        final_url = _official_document_url(
            str(getattr(response, "url", safe_url))
        )
        content = bytes(response.content)
        if not content.startswith(b"%PDF-"):
            raise DCAppellateSourceChangedError(
                "document_not_pdf",
                "C-Track document response is not a PDF",
                details={"url": final_url},
            )
        media_type = str(
            getattr(response, "headers", {}).get(
                "Content-Type",
                "application/pdf",
            )
        ).split(";", 1)[0].strip().lower()
        disposition = str(
            getattr(response, "headers", {}).get(
                "Content-Disposition",
                "",
            )
        )
        filename_match = re.search(
            r'filename\s*=\s*"(?P<quoted>[^"]+)"|'
            r"filename\s*=\s*(?P<plain>[^;]+)",
            disposition,
            re.IGNORECASE,
        )
        filename = (
            _text(
                filename_match.group("quoted")
                or filename_match.group("plain")
            )
            if filename_match
            else None
        )
        return DCAppellateDocument(
            source_url=final_url,
            content=content,
            media_type=media_type,
            filename=filename,
            sha256=hashlib.sha256(content).hexdigest(),
        )

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()


def _selection(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "search":
        values = {
            "appellate_case_number": _text(args.appellate_case_number) or "",
            "caption": _text(args.caption) or "",
            "originating_case_number": (
                _text(args.originating_case_number) or ""
            ),
            "date_from": args.date_from,
            "date_to": args.date_to,
            "date_from_native": _native_query_date(
                args.date_from,
                field_name="date-from",
            ),
            "date_to_native": _native_query_date(
                args.date_to,
                field_name="date-to",
            ),
            "open_only": bool(args.open_only),
            "order_by": args.order_by,
            "order_direction": args.order_direction.upper(),
        }
        if not args.all_records and not any(
            (
                values["appellate_case_number"],
                values["caption"],
                values["originating_case_number"],
                values["date_from"],
                values["date_to"],
                values["open_only"],
            )
        ):
            raise DCAppellateSelectionError(
                "empty_search",
                "Select at least one case filter, or use --all-records",
            )
        if args.date_from and args.date_to and args.date_from > args.date_to:
            raise DCAppellateSelectionError(
                "invalid_date_range",
                "date-from must not be later than date-to",
            )
        return values
    if args.command == "participant":
        last_name = _text(args.last_name)
        if last_name is None:
            raise DCAppellateSelectionError(
                "participant_name_required",
                "Participant search needs a last or organization name",
            )
        return {
            "last_name": last_name,
            "first_name": _text(args.first_name) or "",
            "middle_name": _text(args.middle_name) or "",
            "order_by": args.order_by,
            "order_direction": args.order_direction.upper(),
        }
    return {}


def _cursor_key(operation: str, selection: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json(
            {"operation": operation, "selection": dict(selection)}
        ).encode()
    ).hexdigest()[:16]


def _encode_cursor(
    operation: str,
    selection: Mapping[str, Any],
    start_row: int,
) -> str:
    return (
        f"dccoa:v1:{operation}:{_cursor_key(operation, selection)}:"
        f"start:{start_row}"
    )


def _start_row(
    args: argparse.Namespace,
    *,
    operation: str,
    selection: Mapping[str, Any],
) -> int:
    cursor = getattr(args, "cursor", None)
    requested = getattr(args, "start_row", None)
    if cursor and requested is not None:
        raise DCAppellateSelectionError(
            "ambiguous_pagination",
            "Use either --cursor or --start-row",
        )
    if cursor is None:
        return 1 if requested is None else requested
    match = re.fullmatch(
        r"dccoa:v1:(search|participant):([0-9a-f]{16}):start:(\d+)",
        str(cursor),
    )
    if match is None:
        raise DCAppellateSelectionError(
            "invalid_cursor",
            "Cursor does not match the D.C. appellate cursor format",
        )
    if match.group(1) != operation:
        raise DCAppellateSelectionError(
            "cursor_operation_mismatch",
            "Cursor belongs to a different C-Track operation",
        )
    if match.group(2) != _cursor_key(operation, selection):
        raise DCAppellateSelectionError(
            "cursor_query_mismatch",
            "Cursor filters differ from this C-Track query",
        )
    return int(match.group(3))


def _query(
    args: argparse.Namespace,
    *,
    selection: Mapping[str, Any],
) -> PublicRecordsQuery:
    parameters = dict(selection)
    if args.command in {"search", "participant"}:
        parameters.update(
            {
                "start_row": getattr(args, "start_row", None),
                "all_pages": args.all_pages,
            }
        )
    elif args.command == "case":
        parameters = {
            "case_number": args.case_number,
            "source_internal_id": args.source_internal_id,
            "resolve_documents": args.resolve_documents,
        }
    elif args.command == "download":
        parameters = {
            "url": args.url,
            "destination": str(args.destination),
        }
    elif args.command == "probe":
        parameters = {"sentinel_case_number": PROBE_CASE_NUMBER}
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            cursor=getattr(args, "cursor", None),
        ),
    )


def _failure(
    query: PublicRecordsQuery,
    error: DCAppellateCasesError,
    *,
    records: Sequence[Mapping[str, Any]] = (),
    next_cursor: str | None = None,
) -> PublicRecordsResult:
    status = error.status
    if records and status not in {
        ResultStatus.PARTIAL,
        ResultStatus.SOURCE_CHANGED,
    }:
        status = ResultStatus.PARTIAL
    return PublicRecordsResult.failure(
        query,
        status,
        [error.to_contract_error()],
        records=records,
        next_cursor=next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: DCAppellateCasesClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one C-Track command and return the shared result contract."""

    own_client = client is None
    source_client = client or DCAppellateCasesClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )
    result: PublicRecordsResult
    try:
        if args.command == "routes":
            query = _query(args, selection={})
            result = PublicRecordsResult.success(
                query,
                [source_manifest()],
                raw_artifact_refs=[COURT_INFO_URL, SUPERIOR_SEARCH_URL],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "download":
            safe_url = _official_document_url(args.url)
            query = _query(args, selection={"url": safe_url})
            document = source_client.fetch_document(safe_url)
            args.destination.parent.mkdir(parents=True, exist_ok=True)
            args.destination.write_bytes(document.content)
            document_id = parse_qs(urlparse(safe_url).query)["documentID"][0]
            case_id = parse_qs(urlparse(safe_url).query)["csIID"][0]
            record = {
                "canonical_ref": f"DCCOA-PDF:{document.sha256}",
                "source_id": SOURCE_ID,
                "record_kind": "document_artifact",
                "native_document_id": document_id,
                "case_internal_id": case_id,
                "source_url": document.source_url,
                "local_path": str(args.destination),
                "filename": document.filename,
                "mime_type": "application/pdf",
                "source_media_type": document.media_type,
                "size_bytes": len(document.content),
                "sha256": document.sha256,
                "access_state": "public",
            }
            result = PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=[str(args.destination)],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "case":
            query = _query(args, selection={})
            record = (
                source_client.fetch_case(args.source_internal_id)
                if args.source_internal_id
                else source_client.find_case(args.case_number)
            )
            if args.resolve_documents:
                record = source_client.resolve_case_documents(record)
            result = PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=[
                    str(record["source_url"]),
                    *[
                        str(document["source_url"])
                        for document in record.get("documents", ())
                    ],
                ],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            query = _query(args, selection={})
            record = source_client.find_case(PROBE_CASE_NUMBER)
            if (
                record.get("source_internal_id") != PROBE_CASE_INTERNAL_ID
                or record.get("originating_case_number")
                != PROBE_ORIGINATING_CASE_NUMBER
            ):
                raise DCAppellateSourceChangedError(
                    "probe_sentinel_changed",
                    "C-Track sentinel case identity changed",
                    details={
                        "case_number": record.get("appellate_case_number"),
                        "source_internal_id": record.get(
                            "source_internal_id"
                        ),
                        "originating_case_number": record.get(
                            "originating_case_number"
                        ),
                    },
                )
            events_with_documents = [
                event
                for event in record.get("docket_events", ())
                if event.get("document_locator")
            ]
            if not events_with_documents:
                raise DCAppellateSourceChangedError(
                    "probe_document_locator_missing",
                    "C-Track sentinel no longer exposes a document locator",
                )
            first_event = dict(events_with_documents[0])
            documents = source_client.resolve_document_locator(
                case_number=PROBE_CASE_NUMBER,
                locator=first_event["document_locator"],
            )
            first_document = source_client.fetch_document(
                documents[0]["source_url"]
            )
            probe_record = {
                **record,
                "probe": {
                    "resolved_document": documents[0],
                    "document_sha256": first_document.sha256,
                    "document_size_bytes": len(first_document.content),
                    "document_media_type": first_document.media_type,
                    "component_access_outcomes": source_manifest()[
                        "component_access_outcomes"
                    ],
                },
            }
            result = PublicRecordsResult.success(
                query,
                [probe_record],
                raw_artifact_refs=[
                    str(record["source_url"]),
                    str(documents[0]["source_url"]),
                ],
                warnings=SOURCE_WARNINGS,
            )
        else:
            selection = _selection(args)
            query = _query(args, selection=selection)
            start_row = _start_row(
                args,
                operation=args.command,
                selection=selection,
            )
            if args.all_pages:
                collection = source_client.fetch_all(
                    args.command,
                    selection,
                    start_row=start_row,
                )
                if collection.incomplete_error is not None:
                    result = _failure(
                        query,
                        collection.incomplete_error,
                        records=collection.records,
                    )
                else:
                    result = PublicRecordsResult.success(
                        query,
                        collection.records,
                        raw_artifact_refs=collection.source_urls,
                        warnings=SOURCE_WARNINGS,
                    )
            else:
                page = source_client.fetch_page(
                    args.command,
                    selection,
                    start_row=start_row,
                )
                result = PublicRecordsResult.success(
                    query,
                    page.records,
                    next_cursor=(
                        _encode_cursor(
                            args.command,
                            selection,
                            page.next_start_row,
                        )
                        if page.next_start_row is not None
                        else None
                    ),
                    raw_artifact_refs=[page.source_url],
                    warnings=SOURCE_WARNINGS,
                )
    except DCAppellateCasesError as error:
        try:
            selection = (
                _selection(args)
                if args.command in {"search", "participant"}
                else {}
            )
        except DCAppellateCasesError:
            selection = {}
        query = _query(args, selection=selection)
        result = _failure(query, error)
    finally:
        if own_client:
            source_client.close()
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
            SOURCE_ID,
            result_count,
        )
    return result


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    add_output_args(parser)


def _add_pagination(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start-row", type=int)
    parser.add_argument("--cursor")
    paging = parser.add_mutually_exclusive_group()
    paging.add_argument(
        "--all-pages",
        dest="all_pages",
        action="store_true",
        default=True,
        help="Traverse all matching native pages (default)",
    )
    paging.add_argument(
        "--page-only",
        dest="all_pages",
        action="store_false",
        help="Return one native page and a continuation cursor",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the official D.C. Court of Appeals C-Track system"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    routes = subparsers.add_parser(
        "routes",
        help="Show source operations and trial/property alternatives",
    )
    _add_runtime_and_output(routes)

    search = subparsers.add_parser(
        "search",
        help="Search appellate cases, including by originating case number",
    )
    search.add_argument("--appellate-case-number")
    search.add_argument("--caption")
    search.add_argument("--originating-case-number")
    search.add_argument("--date-from")
    search.add_argument("--date-to")
    search.add_argument("--open-only", action="store_true")
    search.add_argument(
        "--all-records",
        action="store_true",
        help="Intentionally enumerate without another search filter",
    )
    search.add_argument(
        "--order-by",
        choices=(
            "CsNumber",
            "CsGroupNm",
            "CsTypeNm",
            "CsSubTypeNm",
            "CsStatusNm",
            "LcCsNumber",
        ),
        default="CsNumber",
    )
    search.add_argument(
        "--order-direction",
        choices=("asc", "desc"),
        default="desc",
    )
    _add_pagination(search)
    _add_runtime_and_output(search)

    participant = subparsers.add_parser(
        "participant",
        help="Search participants and pivot the matches to appellate cases",
    )
    participant.add_argument("--last-name", required=True)
    participant.add_argument("--first-name")
    participant.add_argument("--middle-name")
    participant.add_argument(
        "--order-by",
        choices=("CsNumber", "DisplayNm", "CsPrtpTypeNm", "FileDt"),
        default="FileDt",
    )
    participant.add_argument(
        "--order-direction",
        choices=("asc", "desc"),
        default="desc",
    )
    _add_pagination(participant)
    _add_runtime_and_output(participant)

    case = subparsers.add_parser(
        "case",
        help="Fetch one case, its parties, docket events, and filing links",
    )
    case.add_argument("case_number", nargs="?")
    case.add_argument("--source-internal-id")
    document_mode = case.add_mutually_exclusive_group()
    document_mode.add_argument(
        "--resolve-documents",
        dest="resolve_documents",
        action="store_true",
        default=True,
        help="Resolve every source-linked docket document (default)",
    )
    document_mode.add_argument(
        "--metadata-only",
        dest="resolve_documents",
        action="store_false",
        help="Return document locators without resolving their links",
    )
    _add_runtime_and_output(case)

    download = subparsers.add_parser(
        "download",
        help="Download and hash one source-returned filing PDF",
    )
    download.add_argument("url")
    download.add_argument("destination", type=Path)
    _add_runtime_and_output(download)

    probe = subparsers.add_parser(
        "probe",
        help="Run a bounded case, event-link, and PDF sentinel probe",
    )
    _add_runtime_and_output(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"D.C. C-Track {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"D.C. C-Track {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            f"  {record.get('appellate_case_number') or '?'} | "
            f"{record.get('originating_case_number') or '?'} | "
            f"{record.get('caption') or record.get('source_url') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "case":
        if bool(args.case_number) == bool(args.source_internal_id):
            raise SystemExit(
                "case requires either CASE_NUMBER or --source-internal-id"
            )
    if getattr(args, "start_row", None) is not None:
        if args.start_row < 1:
            raise SystemExit("--start-row must be at least 1")
        if (args.start_row - 1) % NATIVE_PAGE_SIZE:
            raise SystemExit("--start-row must align to a 50-row page")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.minimum_interval < 0:
        raise SystemExit("--minimum-interval must not be negative")
    if args.max_attempts <= 0:
        raise SystemExit("--max-attempts must be positive")
    if args.retry_backoff < 0:
        raise SystemExit("--retry-backoff must not be negative")
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
