#!/usr/bin/env python3
"""Query Franklin County Municipal Court Clerk public case records.

The Clerk's search is a server-rendered session form. Search responses contain
case-party occurrences and an encrypted transport handle for opening a case.
The handle is deliberately kept in memory only: the court and normalized case
number provide the stable case identity, while search occurrences use the
query fingerprint plus their response ordinal.

Examples:
    uv run python tools/query_ohio_franklin_municipal.py source --json
    uv run python tools/query_ohio_franklin_municipal.py person BURKHALTER ERIKA \
        --output /tmp/franklin-municipal-person.json
    uv run python tools/query_ohio_franklin_municipal.py company "L BRANDS" \
        --year 2022 --output /tmp/franklin-municipal-company.json
    uv run python tools/query_ohio_franklin_municipal.py case-search \
        "2022 CVF 020731" --json
    uv run python tools/query_ohio_franklin_municipal.py case \
        "2022 CVF 020731" --output /tmp/franklin-municipal-case.json
    uv run python tools/query_ohio_franklin_municipal.py summary-pdf \
        "2022 CVF 020731" /tmp/franklin-municipal-summary.pdf --json
    uv run python tools/query_ohio_franklin_municipal.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from email.message import Message
from pathlib import Path
from typing import Any, Mapping
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


OBSERVED_AT = "2026-08-03"
SOURCE_ID = "us-oh-franklin-municipal-court-records"
SOURCE_NAME = "Franklin County Municipal Court Clerk Records Search"
COURT_ID = "oh-franklin-municipal-court"
COURT_NAME = "Franklin County Municipal Court"
COUNTY_FIPS = "39049"
STATE_CODE = "OH"

ROOT_URL = "https://www.fcmcclerk.com/"
OFFICIAL_HOST = "www.fcmcclerk.com"
SEARCH_URL = urljoin(ROOT_URL, "case/search/")
SEARCH_RESULTS_URL = urljoin(ROOT_URL, "case/search/results")
SEARCH_MODIFY_URL = urljoin(ROOT_URL, "case/search/modify")
SEARCH_PRINT_URL = urljoin(ROOT_URL, "case/search/results/print")
SEARCH_PDF_URL = urljoin(ROOT_URL, "case/search/results/pdf")
CASE_VIEW_URL = urljoin(ROOT_URL, "case/view")
CASE_PRINT_URL = urljoin(ROOT_URL, "case/view/print")
CASE_PDF_URL = urljoin(ROOT_URL, "case/view/pdf")

PUBLIC_RECORDS_POLICY_URL = urljoin(
    ROOT_URL,
    "documents/clerk/FCMC_Clerk_Public_Records_Policy.pdf",
)
RETENTION_SCHEDULE_URL = urljoin(
    ROOT_URL,
    "documents/clerk/FCMC_Clerk_Retention_Schedule.pdf",
)
CONTACT_URL = urljoin(ROOT_URL, "clerk/contact-information")
ARRAIGNMENT_URL = urljoin(ROOT_URL, "reports/daily-arraignment")
EVICTION_CSV_URL = urljoin(ROOT_URL, "reports/evictions")
DROP_LIST_URL = urljoin(ROOT_URL, "reports/drop-list")
COMMON_PLEAS_URL = (
    "https://fcdcfcjs.co.franklin.oh.us/CaseInformationOnline/"
)
COMMON_PLEAS_REQUEST_URL = "https://www.fccourts.org/167/Public-Record-Requests"

PLATFORM_FAMILY = "fcmc_clerk_laravel_server_rendered"
NATIVE_RESULT_LIMIT = 250
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.3
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

PROBE_FIRST_NAME = "ERIKA"
PROBE_LAST_NAME = "BURKHALTER"
PROBE_CASE_NUMBER = "2022 CVF 020731"
PROBE_REQUEST_COUNT = 5

REQUIRED_SEARCH_FIELDS = frozenset(
    {
        "_token",
        "last_name",
        "first_name",
        "middle_name",
        "date_of_birth",
        "company_name",
        "party_code",
        "case_number",
        "ticket_number",
        "case_type",
        "case_year",
        "case_status",
    }
)

OBSERVED_PARTY_TYPES = (
    "ALIAS",
    "APPELLANT",
    "APPELLEE",
    "BOND DEPOSITOR",
    "CITY SOLICITOR",
    "CREDITOR",
    "DEBTOR",
    "DEFENDANT",
    "DEPOSITOR FOR BOND",
    "GARNISHEE",
    "LANDLORD",
    "NON DEFENDANT VEH. OWNER",
    "OFFICER",
    "OFFICER COMPLAINANT",
    "OUT OF COUNTY CASE",
    "PARTY COMPLAINANT",
    "PLAINTIFF",
    "PROSECUTOR",
    "TENANT",
    "THIRD PARTY CLAIMANT",
    "THIRD PARTY DEFENDANT",
    "THIRD PARTY PLAINTIFF",
)

OBSERVED_CASE_STATUSES = (
    "(CIV)INDIV ASSIGN",
    "CLOSED",
    "CONVERSION STATUS CODE",
    "DIVERSION",
    "DUPLICATED",
    "IND ASSIGNMENT",
    "JAIL",
    "NONREPORTING LICENSE CONDITION",
    "NRPC",
    "OIRH",
    "OPEN",
    "POST SENTENCE HEARING",
    "PROVIDED NO CONVICTIONS",
    "REOPEN (RO)",
    "SUBMITTED TO JUDGE",
    "SUBMITTED TO MAGISTRATE",
)

SOURCE_WARNINGS = (
    "Search results are case-party occurrences. The same case can appear once "
    "for each matching party.",
    "The source returns at most 250 occurrences and publishes no continuation. "
    "A capped query or caller-supplied year shard remains unresolved.",
    "The case PDF is a generated docket summary, not an underlying filed image. "
    "Individual filings use the Clerk's inspection and copy route.",
    "Online index visibility and retained case-file availability differ by "
    "record series; the Clerk publishes a separate retention schedule.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name=SOURCE_NAME,
    source_role="municipal_court_case_party_index_detail_and_docket",
    base_url=SEARCH_URL,
    dataset_id="franklin-municipal-clerk-record-search",
    metadata={
        "authority": "Franklin County Municipal Court Clerk",
        "county_fips": COUNTY_FIPS,
        "platform_family": PLATFORM_FAMILY,
        "authentication": "none",
        "session_and_csrf": True,
        "captcha_observed": False,
        "native_result_limit": NATIVE_RESULT_LIMIT,
        "native_pagination": "none",
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


class FranklinMunicipalError(RuntimeError):
    """Transport, selection, or verified-source contract failure."""

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


class FranklinMunicipalSourceChanged(FranklinMunicipalError):
    """The official HTML or response no longer matches the probed contract."""

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


class FranklinMunicipalSelectionError(FranklinMunicipalError):
    """A caller selector cannot be represented by the official form."""

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
            category="selection",
            details=details,
        )


class FranklinMunicipalNotFound(FranklinMunicipalError):
    """An exact case query returned an authoritative empty result."""

    def __init__(self, case_number: str) -> None:
        super().__init__(
            "case_not_found",
            f"Franklin Municipal Court case not found: {case_number}",
            status=ResultStatus.NO_RESULTS,
            category="not_found",
            details={"case_number": case_number},
        )


@dataclass(frozen=True)
class SearchForm:
    """Verified search form fields and in-session CSRF value."""

    action_url: str
    csrf_token: str
    field_names: tuple[str, ...]
    party_types: tuple[str, ...]
    case_types: tuple[str, ...]
    case_statuses: tuple[str, ...]


@dataclass(frozen=True)
class SearchOccurrence:
    """One public occurrence plus its private in-session case handle."""

    record: Mapping[str, Any]
    transport_handle: str


@dataclass(frozen=True)
class SearchPage:
    """One native result set; the source has no next-page operation."""

    occurrences: tuple[SearchOccurrence, ...]
    reported_count: int
    truncated: bool
    query_fingerprint: str
    source_url: str

    @property
    def records(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(occurrence.record for occurrence in self.occurrences)


@dataclass(frozen=True)
class ResolvedCase:
    """Exact case detail plus the private handle needed for summary output."""

    record: Mapping[str, Any]
    transport_handle: str
    search_page: SearchPage


@dataclass(frozen=True)
class SummaryPDF:
    """Validated generated case-summary PDF."""

    content: bytes
    media_type: str
    filename: str
    sha256: str
    source_url: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\x00", "").split())
    return normalized or None


def _tag_text(node: Tag | None) -> str | None:
    if node is None:
        return None
    return _text(node.get_text(" ", strip=True))


def _raw_tag_text(node: Tag | None) -> str | None:
    if node is None:
        return None
    candidate = node.get_text(" ", strip=True).strip()
    return candidate or None


def _multiline_text(node: Tag | None) -> str | None:
    if node is None:
        return None
    lines = [_text(line) for line in node.get_text("\n", strip=True).splitlines()]
    return "\n".join(line for line in lines if line) or None


def _visible_text(node: Tag) -> str | None:
    fragment = BeautifulSoup(str(node), "html.parser")
    for hidden in fragment.select(".hidden"):
        hidden.decompose()
    return _tag_text(fragment)


def _pending_events_text(node: Tag) -> str | None:
    fragment = BeautifulSoup(str(node), "html.parser")
    for excluded in fragment.select(".hidden, .badge"):
        excluded.decompose()
    return _tag_text(fragment)


def _nonblank(value: str) -> str:
    candidate = _text(value)
    if candidate is None:
        raise argparse.ArgumentTypeError("value must not be blank")
    return candidate


def _year(value: str) -> str:
    candidate = value.strip()
    if not re.fullmatch(r"\d{4}", candidate):
        raise argparse.ArgumentTypeError("case year must contain four digits")
    return candidate


def _date_of_birth(value: str) -> str:
    candidate = value.strip()
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", candidate):
        raise argparse.ArgumentTypeError("date of birth must use MM/DD/YYYY")
    return candidate


def normalize_case_number(value: str) -> str:
    """Return the stable compact spelling used for joins."""

    normalized = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    if not re.fullmatch(r"\d{4}[A-Z]{2,5}\d{6}", normalized):
        raise FranklinMunicipalSelectionError(
            "invalid_case_number",
            "Franklin Municipal case numbers require a four-digit year, "
            "case code, and six-digit sequence",
            details={"case_number": value},
        )
    return normalized


def _case_type(display_case_number: str) -> str | None:
    normalized = normalize_case_number(display_case_number)
    match = re.fullmatch(r"\d{4}(?P<case_type>[A-Z]{2,5})\d{6}", normalized)
    return match.group("case_type") if match else None


def _native_query_fingerprint(parameters: Mapping[str, Any]) -> str:
    payload = {
        "source_id": SOURCE_ID,
        "operation": "native_search",
        "parameters": dict(parameters),
    }
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def _occurrence_id(query_fingerprint: str, ordinal: int) -> str:
    return (
        "franklin-municipal:occurrence:"
        f"{query_fingerprint}:ordinal:{ordinal}"
    )


def _docket_id(
    normalized_case_number: str,
    ordinal: int,
    payload: Mapping[str, Any],
) -> str:
    digest = hashlib.sha256(canonical_json(payload).encode()).hexdigest()[:20]
    return (
        f"franklin-municipal:docket:{normalized_case_number}:"
        f"ordinal:{ordinal}:{digest}"
    )


def parse_search_form(html: str, *, response_url: str = SEARCH_URL) -> SearchForm:
    """Parse and validate the official search form without exposing its token."""

    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one("form#searchForm")
    if not isinstance(form, Tag):
        raise FranklinMunicipalSourceChanged(
            "search_form_missing",
            "Franklin Municipal search form is missing",
        )
    action_url = urljoin(response_url, str(form.get("action") or ""))
    if action_url.rstrip("/") != SEARCH_RESULTS_URL.rstrip("/"):
        raise FranklinMunicipalSourceChanged(
            "search_action_changed",
            "Franklin Municipal search action changed",
            details={"action_url": action_url},
        )
    token_input = form.select_one('input[name="_token"]')
    csrf_token = (
        str(token_input.get("value") or "").strip()
        if isinstance(token_input, Tag)
        else ""
    )
    if not csrf_token:
        raise FranklinMunicipalSourceChanged(
            "csrf_token_missing",
            "Franklin Municipal search form lacks its CSRF value",
        )
    field_names = tuple(
        dict.fromkeys(
            str(node.get("name"))
            for node in form.select("input[name], select[name]")
            if node.get("name")
        )
    )
    missing = sorted(REQUIRED_SEARCH_FIELDS.difference(field_names))
    if missing:
        raise FranklinMunicipalSourceChanged(
            "search_fields_changed",
            "Franklin Municipal search fields changed",
            details={"missing_fields": missing},
        )

    def options(selector: str) -> tuple[str, ...]:
        select = form.select_one(selector)
        if not isinstance(select, Tag):
            return ()
        return tuple(
            value
            for option in select.find_all("option")
            if (value := str(option.get("value") or "").strip())
        )

    return SearchForm(
        action_url=action_url,
        csrf_token=csrf_token,
        field_names=field_names,
        party_types=options('select[name="party_code"]'),
        case_types=options('select[name="case_type"]'),
        case_statuses=options('select[name="case_status"]'),
    )


def _reported_result_count(soup: BeautifulSoup) -> int | None:
    text = soup.get_text(" ", strip=True)
    match = re.search(r"\bResults:\s*([0-9,]+)\b", text)
    return int(match.group(1).replace(",", "")) if match else None


def parse_search_results(
    html: str,
    *,
    query_fingerprint: str,
    matched_query: Mapping[str, Any],
    source_url: str = SEARCH_RESULTS_URL,
) -> SearchPage:
    """Parse only the canonical desktop result table.

    The response also contains a hidden mobile rendering with independently
    encrypted handles. Parsing ``#datatable tbody`` avoids doubling every
    source occurrence.
    """

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table#datatable")
    reported_count = _reported_result_count(soup)
    limited = "Results Limited!" in soup.get_text(" ", strip=True)
    if soup.select_one(".pagination, a[rel='next']") is not None:
        raise FranklinMunicipalSourceChanged(
            "unexpected_pagination",
            "Franklin Municipal results now expose an unimplemented paginator",
        )
    if not isinstance(table, Tag):
        alert = _tag_text(soup.select_one(".alert-danger")) or ""
        empty_markers = (
            "No records",
            "no records",
            "Try removing",
            "different case year",
        )
        if reported_count == 0 or any(marker in alert for marker in empty_markers):
            return SearchPage(
                occurrences=(),
                reported_count=0,
                truncated=False,
                query_fingerprint=query_fingerprint,
                source_url=source_url,
            )
        raise FranklinMunicipalSourceChanged(
            "results_table_missing",
            "Franklin Municipal response lacks its canonical results table",
            details={"alert": alert or None},
        )

    tbody = table.find("tbody")
    rows = tbody.find_all("tr", recursive=False) if isinstance(tbody, Tag) else []
    occurrences: list[SearchOccurrence] = []
    for ordinal, row in enumerate(rows, start=1):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 7:
            raise FranklinMunicipalSourceChanged(
                "result_columns_changed",
                "Franklin Municipal result row has fewer than seven columns",
                details={"response_ordinal": ordinal, "column_count": len(cells)},
            )
        case_handle_input = cells[0].select_one('input[name="case_id"]')
        case_handle = (
            str(case_handle_input.get("value") or "").strip()
            if isinstance(case_handle_input, Tag)
            else ""
        )
        if not case_handle:
            raise FranklinMunicipalSourceChanged(
                "case_handle_missing",
                "Franklin Municipal result row lacks its case-view handle",
                details={"response_ordinal": ordinal},
            )
        display_case_number = _tag_text(cells[1])
        if display_case_number is None:
            raise FranklinMunicipalSourceChanged(
                "case_number_missing",
                "Franklin Municipal result row lacks a case number",
                details={"response_ordinal": ordinal},
            )
        normalized_case_number = normalize_case_number(display_case_number)
        raw_name = _raw_tag_text(cells[2])
        party_role = _tag_text(cells[3])
        hidden_dob = cells[4].select_one(".hidden")
        raw_dob_sort = _tag_text(hidden_dob)
        dob_display = _visible_text(cells[4])
        dob_normalized = None
        if raw_dob_sort and raw_dob_sort != "00000000":
            if re.fullmatch(r"\d{8}", raw_dob_sort):
                dob_normalized = (
                    f"{raw_dob_sort[:4]}-{raw_dob_sort[4:6]}-"
                    f"{raw_dob_sort[6:]}"
                )
            else:
                dob_normalized = dob_display
        badge = cells[5].select_one(".badge")
        alerts_raw = _tag_text(badge)
        alerts = int(alerts_raw) if alerts_raw and alerts_raw.isdigit() else None
        pending_events = _pending_events_text(cells[5])
        status = _tag_text(cells[6])
        native_occurrence_id = _occurrence_id(query_fingerprint, ordinal)
        case_ref = canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            normalized_case_number,
        )
        record = {
            "record_kind": "case_index_occurrence",
            "source_id": SOURCE_ID,
            "court": {
                "court_id": COURT_ID,
                "name": COURT_NAME,
                "jurisdiction_id": COUNTY_FIPS,
            },
            "display_case_number": display_case_number,
            "normalized_case_number": normalized_case_number,
            "canonical_case_ref": case_ref,
            "case_type": _case_type(display_case_number),
            "case_year": normalized_case_number[:4],
            "filing_date": None,
            "status": status,
            "raw_name": raw_name,
            "name": _text(raw_name),
            "party_role": party_role,
            "date_of_birth": dob_normalized,
            "date_of_birth_display": dob_display,
            "raw_date_of_birth_sort": raw_dob_sort,
            "alerts": alerts,
            "pending_events": pending_events,
            "native_occurrence_id": native_occurrence_id,
            "canonical_ref": canonical_court_ref(
                SOURCE_ID,
                COURT_ID,
                normalized_case_number,
                "case_index_occurrence",
                native_occurrence_id,
            ),
            "matched_query": dict(matched_query),
            "query_fingerprint": query_fingerprint,
            "response_ordinal": ordinal,
            "occurrence_identity_basis": "query_fingerprint_and_response_ordinal",
            "source_metadata": {
                "source_url": source_url,
                "result_table": "#datatable tbody",
                "native_result_limit": NATIVE_RESULT_LIMIT,
                "native_pagination": "none",
            },
            "raw": {
                "case_number": display_case_number,
                "name": raw_name,
                "party_role": party_role,
                "date_of_birth_sort": raw_dob_sort,
                "date_of_birth_display": dob_display,
                "alerts": alerts_raw,
                "pending_events": pending_events,
                "status": status,
            },
        }
        occurrences.append(
            SearchOccurrence(record=record, transport_handle=case_handle)
        )

    if reported_count is None:
        raise FranklinMunicipalSourceChanged(
            "result_count_missing",
            "Franklin Municipal results lack their reported count",
        )
    parsed_count = len(occurrences)
    boundary = {
        "native_result_limit": NATIVE_RESULT_LIMIT,
        "reported_count": reported_count,
        "parsed_occurrence_count": parsed_count,
        "truncated": limited,
        "complete": not limited,
        "pagination": "none",
        "next_cursor": None,
        "unresolved_reason": "native_result_limit_reached" if limited else None,
    }
    occurrences = [
        SearchOccurrence(
            record={**dict(item.record), "search_boundary": boundary},
            transport_handle=item.transport_handle,
        )
        for item in occurrences
    ]
    return SearchPage(
        occurrences=tuple(occurrences),
        reported_count=reported_count,
        truncated=limited,
        query_fingerprint=query_fingerprint,
        source_url=source_url,
    )


def _field_key(value: str | None) -> str:
    candidate = (value or "").strip().rstrip(":")
    candidate = candidate.replace("D.O.B.", "Date of Birth")
    candidate = candidate.replace("Ct.Rm.", "Courtroom")
    candidate = candidate.replace("St/Zip", "State Zip")
    return re.sub(r"[^a-z0-9]+", "_", candidate.casefold()).strip("_")


def _label_value_pairs(row: Tag) -> dict[str, Any]:
    cells = row.find_all("td", recursive=False)
    pairs: dict[str, Any] = {}
    for index, cell in enumerate(cells):
        classes = set(cell.get("class") or [])
        if "title" not in classes:
            continue
        for value_cell in cells[index + 1 :]:
            if "data" not in set(value_cell.get("class") or []):
                continue
            key = _field_key(_tag_text(cell))
            if key:
                pairs[key] = _multiline_text(value_cell)
            break
    return pairs


def _section_table(soup: BeautifulSoup, section_id: str) -> Tag | None:
    anchor = soup.find(id=section_id)
    if not isinstance(anchor, Tag):
        return None
    table = anchor.find_next("table")
    return table if isinstance(table, Tag) else None


def _single_pairs(table: Tag | None) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if table is None:
        return values
    for row in table.find_all("tr", recursive=False):
        values.update(_label_value_pairs(row))
    return values


def _block_records(table: Tag | None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    if table is None:
        return records
    for row in table.find_all("tr", recursive=False):
        ordinal_node = row.find("b")
        ordinal_text = _tag_text(ordinal_node) if isinstance(ordinal_node, Tag) else None
        pairs = _label_value_pairs(row)
        if ordinal_text and ordinal_text.isdigit():
            if current is not None:
                records.append(current)
            current = {"source_ordinal": int(ordinal_text)}
        if current is None and pairs:
            current = {"source_ordinal": len(records) + 1}
        if current is not None:
            current.update(pairs)
    if current is not None:
        records.append(current)
    return records


def _grouped_pair_records(
    table: Tag | None,
    *,
    start_key: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    if table is None:
        return records
    for row in table.find_all("tr", recursive=False):
        pairs = _label_value_pairs(row)
        if start_key in pairs and current:
            current["source_ordinal"] = len(records) + 1
            records.append(current)
            current = {}
        current.update(pairs)
    if current:
        current["source_ordinal"] = len(records) + 1
        records.append(current)
    return records


def _header_records(table: Tag | None) -> list[dict[str, Any]]:
    if table is None:
        return []
    rows = table.find_all("tr", recursive=False)
    header_index = None
    headers: list[str] = []
    for index, row in enumerate(rows):
        title_cells = row.select("td.title")
        if len(title_cells) >= 2 and not row.select("td.data"):
            headers = [_field_key(_tag_text(cell)) for cell in title_cells]
            header_index = index
            break
    if header_index is None:
        return []
    records: list[dict[str, Any]] = []
    for row in rows[header_index + 1 :]:
        cells = row.select("td.data")
        if not cells:
            continue
        values = [_multiline_text(cell) for cell in cells]
        record = {
            header: values[index] if index < len(values) else None
            for index, header in enumerate(headers)
        }
        record["source_ordinal"] = len(records) + 1
        records.append(record)
    return records


def _titled_table(soup: BeautifulSoup, title: str) -> Tag | None:
    container = soup.find(attrs={"title": title})
    if not isinstance(container, Tag):
        return None
    table = container.find("table")
    return table if isinstance(table, Tag) else None


def _parse_docket(
    table: Tag | None,
    *,
    normalized_case_number: str,
) -> list[dict[str, Any]]:
    if table is None:
        return []
    entries: list[dict[str, Any]] = []
    for row in table.find_all("tr", recursive=False):
        cells = row.select("td.data")
        if not cells:
            continue
        date = _tag_text(cells[0])
        if date:
            title_cell = cells[1] if len(cells) > 1 else None
            title_node = title_cell.find("strong") if isinstance(title_cell, Tag) else None
            title = (
                _tag_text(title_node)
                if isinstance(title_node, Tag)
                else _tag_text(title_cell)
            )
            entry: dict[str, Any] = {
                "source_ordinal": len(entries) + 1,
                "date": date,
                "title": title,
                "detail": None,
                "amount": _tag_text(cells[2]) if len(cells) > 2 else None,
                "balance": _tag_text(cells[3]) if len(cells) > 3 else None,
                "online_filing_link": None,
                "filed_document_access": "not_linked_online",
            }
            entries.append(entry)
            continue
        if entries:
            detail_cell = next(
                (
                    cell
                    for cell in cells[1:]
                    if cell.get("colspan") or _multiline_text(cell)
                ),
                cells[-1],
            )
            detail = _multiline_text(detail_cell)
            if detail:
                existing = entries[-1].get("detail")
                entries[-1]["detail"] = (
                    f"{existing}\n{detail}" if existing else detail
                )
    for entry in entries:
        identity_payload = {
            "date": entry.get("date"),
            "title": entry.get("title"),
            "detail": entry.get("detail"),
            "amount": entry.get("amount"),
            "balance": entry.get("balance"),
        }
        entry["native_entry_id"] = _docket_id(
            normalized_case_number,
            int(entry["source_ordinal"]),
            identity_payload,
        )
        entry["identity_basis"] = "case_number_source_ordinal_and_content"
        entry["canonical_ref"] = canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            normalized_case_number,
            "docket_entry",
            str(entry["native_entry_id"]),
        )
    return entries


def parse_case_detail(
    html: str,
    *,
    requested_case_number: str,
    source_url: str = CASE_VIEW_URL,
    discovery: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse conditional civil or criminal detail sections conservatively."""

    soup = BeautifulSoup(html, "html.parser")
    header_cells = soup.select("td.page_header")
    if len(header_cells) < 2:
        raise FranklinMunicipalSourceChanged(
            "case_overview_missing",
            "Franklin Municipal case overview header is missing",
        )
    caption = _multiline_text(header_cells[0])
    overview = _tag_text(header_cells[1]) or ""
    match = re.search(
        r"Case No\.\s*(?P<number>.*?)\s+Status:\s*(?P<status>.*?)\s+"
        r"Filed:\s*(?P<filed>\d{2}/\d{2}/\d{4})",
        overview,
    )
    if not match:
        raise FranklinMunicipalSourceChanged(
            "case_overview_changed",
            "Franklin Municipal case overview fields changed",
            details={"overview": overview},
        )
    display_case_number = _text(match.group("number")) or ""
    normalized_case_number = normalize_case_number(display_case_number)
    requested_normalized = normalize_case_number(requested_case_number)
    if normalized_case_number != requested_normalized:
        raise FranklinMunicipalSourceChanged(
            "case_identity_mismatch",
            "Franklin Municipal case detail does not match the exact query",
            details={
                "requested": requested_normalized,
                "returned": normalized_case_number,
            },
        )

    parties = _block_records(_section_table(soup, "parties"))
    attorneys = _grouped_pair_records(
        _section_table(soup, "attorneys"),
        start_key="name",
    )
    charges = _block_records(_section_table(soup, "charges"))
    dispositions = _header_records(_section_table(soup, "disposition"))
    financial = _header_records(_section_table(soup, "financial-summary"))
    receipts = _header_records(_section_table(soup, "receipts"))
    events = _header_records(_section_table(soup, "events"))
    docket = _parse_docket(
        _section_table(soup, "docket"),
        normalized_case_number=normalized_case_number,
    )
    defendant_information = _single_pairs(
        _section_table(soup, "defendant-information")
    )
    case_details = _single_pairs(_titled_table(soup, "CASE DETAILS"))
    sections = [
        section_id
        for section_id in (
            "overview",
            "defendant-information",
            "parties",
            "attorneys",
            "charges",
            "disposition",
            "financial-summary",
            "receipts",
            "events",
            "docket",
        )
        if soup.find(id=section_id) is not None
    ]
    case_ref = canonical_court_ref(
        SOURCE_ID,
        COURT_ID,
        normalized_case_number,
    )
    return {
        "record_kind": "case",
        "source_id": SOURCE_ID,
        "court": {
            "court_id": COURT_ID,
            "name": COURT_NAME,
            "jurisdiction_id": COUNTY_FIPS,
        },
        "display_case_number": display_case_number,
        "normalized_case_number": normalized_case_number,
        "canonical_case_ref": case_ref,
        "canonical_ref": case_ref,
        "case_type": _case_type(display_case_number),
        "case_year": normalized_case_number[:4],
        "caption": caption,
        "status": _text(match.group("status")),
        "filing_date": match.group("filed"),
        "sections_present": sections,
        "defendant_information": defendant_information,
        "case_details": case_details,
        "parties": parties,
        "attorneys": attorneys,
        "charges": charges,
        "dispositions": dispositions,
        "financial_summary": financial,
        "receipts": receipts,
        "events": events,
        "docket_entries": docket,
        "documents": [],
        "document_access": {
            "generated_case_summary": {
                "availability": "online_case_summary",
                "method": "POST",
                "url": CASE_PDF_URL,
                "document_kind": "generated_case_summary",
                "is_filed_document": False,
            },
            "filed_documents": {
                "availability": "not_linked_online",
                "request_url": PUBLIC_RECORDS_POLICY_URL,
                "contact_url": CONTACT_URL,
                "civil_phone": "614-645-7220",
                "criminal_traffic_phone": "614-645-8186",
            },
        },
        "complementary_sources": _complements(),
        "discovery": dict(discovery or {}),
        "source_metadata": {
            "source_url": source_url,
            "platform_family": PLATFORM_FAMILY,
            "encrypted_case_handle_persisted": False,
        },
        "raw": {"overview": overview, "caption": caption},
    }


def parse_summary_pdf(
    content: bytes,
    *,
    headers: Mapping[str, Any],
    response_url: str,
) -> SummaryPDF:
    """Validate the generated case-summary response."""

    host = (urlsplit(response_url).hostname or "").casefold()
    if host != OFFICIAL_HOST:
        raise FranklinMunicipalSourceChanged(
            "summary_redirect_changed",
            "Franklin Municipal case summary left the official host",
            details={"response_url": response_url},
        )
    media_type = str(headers.get("Content-Type") or "").split(";", 1)[0].strip()
    if media_type.casefold() != "application/pdf" or not content.startswith(b"%PDF"):
        raise FranklinMunicipalSourceChanged(
            "summary_not_pdf",
            "Franklin Municipal case summary did not return a PDF",
            details={"media_type": media_type, "size": len(content)},
        )
    message = Message()
    message["content-disposition"] = str(headers.get("Content-Disposition") or "")
    filename = message.get_filename() or "franklin-municipal-case-summary.pdf"
    return SummaryPDF(
        content=content,
        media_type=media_type,
        filename=filename,
        sha256=hashlib.sha256(content).hexdigest(),
        source_url=response_url,
    )


def _complements() -> list[dict[str, Any]]:
    return [
        {
            "role": "individual_filing_inspection_and_copy",
            "url": PUBLIC_RECORDS_POLICY_URL,
            "contact_url": CONTACT_URL,
            "adds": ["underlying pleadings", "entries", "certified copies"],
            "access": "request_or_in_person_inspection",
        },
        {
            "role": "retention_schedule",
            "url": RETENTION_SCHEDULE_URL,
            "adds": ["record-series retention periods"],
        },
        {
            "role": "daily_arraignment_reports",
            "url": ARRAIGNMENT_URL,
            "adds": [
                "event time",
                "courtroom",
                "jurisdiction",
                "charges",
                "defendant sheet",
            ],
        },
        {
            "role": "monthly_eviction_csv",
            "url": EVICTION_CSV_URL,
            "adds": [
                "bounded monthly bulk rows",
                "first plaintiff and defendant addresses",
                "last disposition",
            ],
            "published_window": "current_month_and_previous_12_months",
        },
        {
            "role": "civil_drop_list",
            "url": DROP_LIST_URL,
            "adds": ["cases pending over one year and scheduled for dismissal"],
        },
        {
            "role": "common_pleas_and_tenth_district",
            "url": COMMON_PLEAS_URL,
            "request_url": COMMON_PLEAS_REQUEST_URL,
            "adds": [
                "bound-over or transferred cases",
                "larger civil matters",
                "appellate dockets and public filings",
            ],
        },
    ]


def _source_record() -> dict[str, Any]:
    return {
        "record_kind": "source_capabilities",
        "source_id": SOURCE_ID,
        "name": SOURCE_NAME,
        "authority": "Franklin County Municipal Court Clerk",
        "court": {"court_id": COURT_ID, "name": COURT_NAME},
        "platform_family": PLATFORM_FAMILY,
        "observed_at": OBSERVED_AT,
        "access": {
            "authentication": "none",
            "captcha_observed": False,
            "session_cookie": True,
            "csrf_form_token": True,
            "declared_rate_limit": 25,
            "declared_rate_period": None,
        },
        "search": {
            "url": SEARCH_URL,
            "method": "POST",
            "results_url": SEARCH_RESULTS_URL,
            "required_selector_groups": [
                ["case_number"],
                ["ticket_number"],
                ["last_name", "first_name"],
                ["company_name"],
            ],
            "optional_filters": [
                "middle_name",
                "date_of_birth",
                "party_code",
                "case_type",
                "case_year",
                "case_status",
            ],
            "observed_party_types": list(OBSERVED_PARTY_TYPES),
            "observed_case_types": ["CIVIL", "CRIMINAL/TRAFFIC"],
            "observed_case_statuses": list(OBSERVED_CASE_STATUSES),
            "record_grain": "case_party_occurrence",
            "native_result_limit": NATIVE_RESULT_LIMIT,
            "native_pagination": "none",
            "broad_search_exhaustive": False,
        },
        "case_detail": {
            "url": CASE_VIEW_URL,
            "method": "POST",
            "selector": "fresh_encrypted_handle_from_search",
            "stable_identity": "court_id_and_normalized_case_number",
            "transport_handle_persisted": False,
            "conditional_sections": [
                "overview",
                "defendant_information",
                "case_details",
                "parties",
                "attorneys",
                "charges",
                "disposition",
                "financial_summary",
                "receipts",
                "events",
                "docket",
            ],
        },
        "case_summary": {
            "url": CASE_PDF_URL,
            "method": "POST",
            "document_kind": "generated_case_summary",
            "is_filed_document": False,
        },
        "individual_filing_images": {
            "availability": "not_linked_online",
            "copy_policy_url": PUBLIC_RECORDS_POLICY_URL,
        },
        "complementary_sources": _complements(),
        "probe": {
            "request_count": PROBE_REQUEST_COUNT,
            "routes": [
                "search_form",
                "person_search",
                "exact_case_search",
                "case_detail",
                "case_summary_pdf",
            ],
        },
    }


class FranklinMunicipalClient:
    """Stateful HTTP client for the official session-and-CSRF workflow."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
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
        self.rate_limiter = MinimumIntervalRateLimiter(minimum_interval)
        self.sleeper = sleeper
        self.form: SearchForm | None = None
        self.request_count = 0
        self.rate_limit_headers: dict[str, str] = {}

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        fixed_cost: bool = False,
        **kwargs: Any,
    ) -> Any:
        attempts = 1 if fixed_cost else self.retry_policy.max_attempts
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/pdf",
            **dict(kwargs.pop("headers", {}) or {}),
        }
        for attempt in range(1, attempts + 1):
            self.rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=self.timeout,
                    headers=headers,
                    allow_redirects=True,
                    **kwargs,
                )
            except requests.RequestException as error:
                if attempt >= attempts:
                    raise FranklinMunicipalError(
                        "transport_error",
                        str(error),
                        category="transport",
                        retryable=True,
                        details={"url": url},
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            response_headers = dict(getattr(response, "headers", {}) or {})
            self.rate_limit_headers = {
                key: str(response_headers[key])
                for key in ("X-RateLimit-Limit", "X-RateLimit-Remaining")
                if key in response_headers
            }
            status_code = int(getattr(response, "status_code", 0))
            if status_code in self.retry_policy.retry_statuses and attempt < attempts:
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status_code == 429:
                raise FranklinMunicipalError(
                    "rate_limited",
                    "Franklin Municipal Court portal rate limit reached",
                    status=ResultStatus.RATE_LIMITED,
                    category="rate_limit",
                    retryable=True,
                    details={"url": url, **self.rate_limit_headers},
                )
            if status_code < 200 or status_code >= 400:
                raise FranklinMunicipalError(
                    "http_status",
                    f"HTTP {status_code} from Franklin Municipal Court portal",
                    category="http",
                    retryable=status_code >= 500,
                    details={"url": url, "status_code": status_code},
                )
            response_url = str(getattr(response, "url", url))
            if (urlsplit(response_url).hostname or "").casefold() != OFFICIAL_HOST:
                raise FranklinMunicipalSourceChanged(
                    "official_host_changed",
                    "Franklin Municipal response left the official host",
                    details={"response_url": response_url},
                )
            return response
        raise AssertionError("unreachable request retry state")

    def bootstrap(self, *, fixed_cost: bool = False) -> SearchForm:
        if self.form is not None:
            return self.form
        response = self._request("GET", SEARCH_URL, fixed_cost=fixed_cost)
        self.form = parse_search_form(
            str(response.text),
            response_url=str(getattr(response, "url", SEARCH_URL)),
        )
        return self.form

    def search(
        self,
        parameters: Mapping[str, Any],
        *,
        query_fingerprint: str | None = None,
        fixed_cost: bool = False,
    ) -> SearchPage:
        form = self.bootstrap(fixed_cost=fixed_cost)
        clean_parameters = {
            key: str(value)
            for key, value in parameters.items()
            if value is not None and str(value).strip()
        }
        fingerprint = query_fingerprint or _native_query_fingerprint(
            clean_parameters
        )
        response = self._request(
            "POST",
            form.action_url,
            fixed_cost=fixed_cost,
            headers={"Referer": SEARCH_URL},
            data={
                "_token": form.csrf_token,
                **clean_parameters,
                "desktop_view": "on",
            },
        )
        return parse_search_results(
            str(response.text),
            query_fingerprint=fingerprint,
            matched_query=clean_parameters,
            source_url=str(getattr(response, "url", SEARCH_RESULTS_URL)),
        )

    def resolve_case(
        self,
        case_number: str,
        *,
        fixed_cost: bool = False,
    ) -> ResolvedCase:
        normalized = normalize_case_number(case_number)
        parameters = {"case_number": case_number}
        search_page = self.search(parameters, fixed_cost=fixed_cost)
        matches = [
            occurrence
            for occurrence in search_page.occurrences
            if occurrence.record.get("normalized_case_number") == normalized
        ]
        if not matches:
            raise FranklinMunicipalNotFound(case_number)
        response = self._request(
            "POST",
            CASE_VIEW_URL,
            fixed_cost=fixed_cost,
            headers={"Referer": SEARCH_RESULTS_URL},
            data={
                "_token": self.bootstrap().csrf_token,
                "case_id": matches[0].transport_handle,
            },
        )
        detail = parse_case_detail(
            str(response.text),
            requested_case_number=case_number,
            source_url=str(getattr(response, "url", CASE_VIEW_URL)),
            discovery={
                "exact_search_reported_count": search_page.reported_count,
                "exact_search_party_occurrences": len(search_page.occurrences),
                "exact_search_truncated": search_page.truncated,
                "query_fingerprint": search_page.query_fingerprint,
            },
        )
        return ResolvedCase(
            record=detail,
            transport_handle=matches[0].transport_handle,
            search_page=search_page,
        )

    def summary_pdf(
        self,
        resolved: ResolvedCase,
        *,
        fixed_cost: bool = False,
    ) -> SummaryPDF:
        response = self._request(
            "POST",
            CASE_PDF_URL,
            fixed_cost=fixed_cost,
            headers={"Referer": CASE_VIEW_URL},
            data={
                "_token": self.bootstrap().csrf_token,
                "case_id": resolved.transport_handle,
            },
        )
        return parse_summary_pdf(
            bytes(response.content),
            headers=dict(response.headers),
            response_url=str(getattr(response, "url", CASE_PDF_URL)),
        )

    def resolve_for_summary(
        self,
        case_number: str,
        *,
        fixed_cost: bool = False,
    ) -> tuple[ResolvedCase, SummaryPDF]:
        resolved = self.resolve_case(case_number, fixed_cost=fixed_cost)
        return resolved, self.summary_pdf(resolved, fixed_cost=fixed_cost)

    def probe(self) -> dict[str, Any]:
        start_count = self.request_count
        form = self.bootstrap(fixed_cost=True)
        person_page = self.search(
            {"last_name": PROBE_LAST_NAME, "first_name": PROBE_FIRST_NAME},
            fixed_cost=True,
        )
        exact_page = self.search(
            {"case_number": PROBE_CASE_NUMBER},
            fixed_cost=True,
        )
        normalized = normalize_case_number(PROBE_CASE_NUMBER)
        matches = [
            occurrence
            for occurrence in exact_page.occurrences
            if occurrence.record.get("normalized_case_number") == normalized
        ]
        if not matches:
            raise FranklinMunicipalSourceChanged(
                "probe_case_missing",
                "Franklin Municipal sentinel case is absent from exact search",
            )
        detail_response = self._request(
            "POST",
            CASE_VIEW_URL,
            fixed_cost=True,
            headers={"Referer": SEARCH_RESULTS_URL},
            data={"_token": form.csrf_token, "case_id": matches[0].transport_handle},
        )
        detail = parse_case_detail(
            str(detail_response.text),
            requested_case_number=PROBE_CASE_NUMBER,
            source_url=str(getattr(detail_response, "url", CASE_VIEW_URL)),
        )
        resolved = ResolvedCase(
            record=detail,
            transport_handle=matches[0].transport_handle,
            search_page=exact_page,
        )
        summary = self.summary_pdf(resolved, fixed_cost=True)
        request_count = self.request_count - start_count
        if request_count != PROBE_REQUEST_COUNT:
            raise FranklinMunicipalSourceChanged(
                "probe_request_budget_changed",
                "Franklin Municipal probe exceeded its fixed request budget",
                details={
                    "expected": PROBE_REQUEST_COUNT,
                    "observed": request_count,
                },
            )
        return {
            "record_kind": "source_probe",
            "source_id": SOURCE_ID,
            "status": "available",
            "request_count": request_count,
            "csrf_present": bool(form.csrf_token),
            "search_field_names": list(form.field_names),
            "person_search_occurrences": len(person_page.occurrences),
            "person_search_truncated": person_page.truncated,
            "sentinel_case_number": detail["normalized_case_number"],
            "sentinel_party_occurrences": len(exact_page.occurrences),
            "sentinel_sections": list(detail["sections_present"]),
            "sentinel_docket_entries": len(detail["docket_entries"]),
            "summary_media_type": summary.media_type,
            "summary_sha256": summary.sha256,
            "summary_document_kind": "generated_case_summary",
            "summary_is_filed_document": False,
            "native_result_limit": NATIVE_RESULT_LIMIT,
            "native_pagination": "none",
            "rate_limit_headers": dict(self.rate_limit_headers),
            "transport_secrets_persisted": False,
        }


def _query(
    operation: str,
    parameters: Mapping[str, Any],
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(operation=operation, parameters=parameters),
    )


def _optional_filters(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "middle_name": getattr(args, "middle_name", None),
        "date_of_birth": getattr(args, "date_of_birth", None),
        "party_code": getattr(args, "party_type", None),
        "case_type": getattr(args, "case_type", None),
        "case_year": getattr(args, "year", None),
        "case_status": getattr(args, "status", None),
    }


def _command_parameters(args: argparse.Namespace) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    if args.command == "person":
        parameters = {
            "last_name": args.last_name,
            "first_name": args.first_name,
            **_optional_filters(args),
        }
    elif args.command == "company":
        parameters = {"company_name": args.company_name, **_optional_filters(args)}
    elif args.command == "case-search":
        parameters = {"case_number": args.case_number, **_optional_filters(args)}
    elif args.command == "ticket":
        parameters = {"ticket_number": args.ticket_number, **_optional_filters(args)}
    elif args.command in {"case", "summary-pdf"}:
        parameters = {"case_number": args.case_number}
    elif args.command == "probe":
        parameters = {
            "sentinel_person": f"{PROBE_LAST_NAME}, {PROBE_FIRST_NAME}",
            "sentinel_case_number": PROBE_CASE_NUMBER,
            "request_count": PROBE_REQUEST_COUNT,
        }
    return {key: value for key, value in parameters.items() if value is not None}


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    return _query(args.command, _command_parameters(args))


def _partial_search_result(
    query: PublicRecordsQuery,
    page: SearchPage,
) -> PublicRecordsResult:
    if page.truncated:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [
                PublicRecordsError(
                    code="native_result_limit_reached",
                    message=(
                        "Franklin Municipal search reached the source's "
                        f"{NATIVE_RESULT_LIMIT}-occurrence limit"
                    ),
                    category="native_boundary",
                    retryable=False,
                    details={
                        "native_result_limit": NATIVE_RESULT_LIMIT,
                        "reported_count": page.reported_count,
                        "pagination": "none",
                        "next_cursor": None,
                    },
                )
            ],
            records=page.records,
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        page.records,
        warnings=SOURCE_WARNINGS,
    )


def _execute_command(
    args: argparse.Namespace,
    client: FranklinMunicipalClient,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command in {"person", "company", "case-search", "ticket"}:
        parameters = _command_parameters(args)
        page = client.search(parameters, query_fingerprint=query.fingerprint)
        return _partial_search_result(query, page)
    if args.command == "case":
        resolved = client.resolve_case(args.case_number)
        return PublicRecordsResult.success(
            query,
            [resolved.record],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "summary-pdf":
        resolved, summary = client.resolve_for_summary(args.case_number)
        destination = Path(args.destination).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(summary.content)
        normalized = str(resolved.record["normalized_case_number"])
        record = {
            "record_kind": "case_summary_artifact",
            "source_id": SOURCE_ID,
            "court": {"court_id": COURT_ID, "name": COURT_NAME},
            "display_case_number": resolved.record["display_case_number"],
            "normalized_case_number": normalized,
            "canonical_case_ref": resolved.record["canonical_case_ref"],
            "document_kind": "generated_case_summary",
            "is_filed_document": False,
            "availability": "online_case_summary",
            "media_type": summary.media_type,
            "filename": summary.filename,
            "sha256": summary.sha256,
            "size_bytes": len(summary.content),
            "destination": str(destination),
            "source_url": summary.source_url,
            "filed_document_copy_route": PUBLIC_RECORDS_POLICY_URL,
            "canonical_ref": canonical_court_ref(
                SOURCE_ID,
                COURT_ID,
                normalized,
                "generated_case_summary",
                summary.sha256,
            ),
        }
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "probe":
        return PublicRecordsResult.success(
            query,
            [client.probe()],
            warnings=SOURCE_WARNINGS,
        )
    raise FranklinMunicipalSelectionError(
        "unsupported_command",
        f"Unsupported Franklin Municipal command: {args.command}",
    )


def execute(
    args: argparse.Namespace,
    *,
    client: FranklinMunicipalClient | Any | None = None,
    record_search: bool = True,
) -> PublicRecordsResult:
    """Execute one command and return the shared public-record envelope."""

    query = build_query(args)
    if args.command == "source":
        result = PublicRecordsResult.success(
            query,
            [_source_record()],
            warnings=SOURCE_WARNINGS,
        )
        if record_search:
            log_search(canonical_json(query.to_dict()), SOURCE_ID, 1)
        return result

    source_client = client or FranklinMunicipalClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
    )
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except FranklinMunicipalNotFound:
        result = PublicRecordsResult.success(
            query,
            [],
            warnings=SOURCE_WARNINGS,
        )
    except FranklinMunicipalError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=SOURCE_WARNINGS,
        )
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="summary_write_failed",
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
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _add_filters(parser: argparse.ArgumentParser, *, person: bool = False) -> None:
    if person:
        parser.add_argument("--middle-name")
        parser.add_argument("--date-of-birth", type=_date_of_birth)
    parser.add_argument("--party-type")
    parser.add_argument("--case-type")
    parser.add_argument("--year", type=_year)
    parser.add_argument("--status")


def _add_transport(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Franklin County Municipal Court Clerk records"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser(
        "source",
        help="Show verified routes, boundaries, document states, and complements",
    )
    add_output_args(source)

    person = subparsers.add_parser(
        "person",
        help="Search case-party occurrences by required last and first name",
    )
    person.add_argument("last_name", type=_nonblank)
    person.add_argument("first_name", type=_nonblank)
    _add_filters(person, person=True)
    add_output_args(person)

    company = subparsers.add_parser(
        "company",
        help="Search case-party occurrences by company name",
    )
    company.add_argument("company_name", type=_nonblank)
    _add_filters(company)
    add_output_args(company)

    case_search = subparsers.add_parser(
        "case-search",
        help="Return the party occurrences for an exact case-number search",
    )
    case_search.add_argument("case_number", type=_nonblank)
    _add_filters(case_search)
    add_output_args(case_search)

    ticket = subparsers.add_parser(
        "ticket",
        help="Search case-party occurrences by ticket number",
    )
    ticket.add_argument("ticket_number", type=_nonblank)
    _add_filters(ticket)
    add_output_args(ticket)

    case = subparsers.add_parser(
        "case",
        help="Resolve an exact case number to full public case detail and docket",
    )
    case.add_argument("case_number", type=_nonblank)
    add_output_args(case)

    summary = subparsers.add_parser(
        "summary-pdf",
        help="Acquire the generated case-summary PDF and emit artifact metadata",
    )
    summary.add_argument("case_number", type=_nonblank)
    summary.add_argument("destination")
    add_output_args(summary)

    probe = subparsers.add_parser(
        "probe",
        help="Run the fixed five-request search/detail/summary contract probe",
    )
    add_output_args(probe)

    for child in subparsers.choices.values():
        _add_transport(child)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Franklin Municipal {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Franklin Municipal {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        case_number = record.get("display_case_number")
        name = record.get("name") or record.get("caption")
        label = case_number or record.get("record_kind")
        print(f"- {label}" + (f" | {name}" if name else ""))
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    args = build_parser().parse_args()
    if args.retry_attempts < 1:
        raise SystemExit("--retry-attempts must be at least 1")
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
