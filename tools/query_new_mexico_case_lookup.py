#!/usr/bin/env python3
"""Query the New Mexico Judiciary's anonymous Case Lookup application.

Case Lookup publishes statewide case metadata, not filed documents.  Its
source-published acquisition grain is an individual electronic court record:
this adapter can search one targeted party on the first native result page or
retrieve one caller-selected exact case. Those two operations are the verified
public source contract; result locators remain transient session state.

Examples:
    uv run python tools/query_new_mexico_case_lookup.py source --json
    uv run python tools/query_new_mexico_case_lookup.py search \
        "Epstein Jeffrey" --output /tmp/nm-party-search.json
    uv run python tools/query_new_mexico_case_lookup.py case \
        D-101-CV-199602449 --output /tmp/nm-case.json
    uv run python tools/query_new_mexico_case_lookup.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence
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
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-nm-judiciary-case-lookup"
SOURCE_NAME = "New Mexico Judiciary Case Lookup"
STATE_CODE = "NM"
STATE_GEOID = "35"
OBSERVED_AT = "2026-07-31"

BASE_URL = "https://caselookup.nmcourts.gov/caselookup/app"
INFO_URL = (
    "https://selfrepresentation.nmcourts.gov/self-representation/"
    "public-access-and-researchnm/"
)
RESEARCH_NM_URL = "https://researchnm.tylerhost.net/"
IPRA_URL = "https://www.nmcourts.gov/public-records-request/"
EXPECTED_HOST = "caselookup.nmcourts.gov"
EXPECTED_PATH = "/caselookup/app"
PLATFORM_FAMILY = "apache_tapestry_4_case_lookup"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_MAX_RETRIES = 2
DEFAULT_NATIVE_PAGE_SIZE = 20
NATIVE_PAGE_SIZES = (10, 20, 30, 40, 50)
PROBE_CASE_NUMBER = "D-101-CV-199602449"
PROBE_PARTY_NAME = "Epstein Jeffrey"
PROBE_EXPECTED_REQUESTS = 4
DISCLAIMER_FORM_ID = "disclaimerForm"
NAME_SEARCH_FORM_ID = "nameSearchForm"
CASE_NUMBER_SEARCH_FORM_ID = "caseNumberSearchForm"
NAME_SEARCH_FIELDS = (
    "partyName",
    "driversLicense",
    "dlState",
    "dob",
    "yearOnlyDob",
    "caseNumberPartialSearch",
    "courtTypeSelection",
    "dol",
    "caseCategory",
    "dateSearch",
    "dateType",
    "monthFromSelection",
    "yearFrom",
    "monthToSelection",
    "yearTo",
    "results",
)
CASE_NUMBER_SEARCH_FIELDS = (
    "courtType",
    "courtLocation",
    "caseCategory",
    "caseNumber",
)

DISCLAIMER_TEXT = (
    "Use of this site for any purpose other than viewing individual "
    "electronic court records, or attempts to download multiple records per "
    "transaction, are strictly prohibited."
)
NO_RESULTS_TEXT = "No results found. Please try different search criteria."
SEARCH_HEADERS = (
    "Case Number",
    "Party Name",
    "dob",
    "Party Type",
    "Party #",
    "Case Title",
    "Case Judge",
    "Court",
    "Filing Date",
)
CASE_SUMMARY_HEADERS = (
    "Case Number",
    "Current Judge",
    "Filing Date",
    "Court",
)
PARTY_HEADERS = (
    "Party Type",
    "Party Description",
    "Party #",
    "Party Name",
)
REGISTER_HEADERS = (
    "Event Date",
    "Event Description",
    "Event Result",
    "Party Type",
    "Party #",
    "Amount",
)
JUDGE_HISTORY_HEADERS = (
    "Assignment Date",
    "Judge Name",
    "Sequence #",
    "Assignment Event Description",
)

CASE_NUMBER_RE = re.compile(
    r"^(?P<court_type>[A-Z])-(?P<court_location>\d{1,4})-"
    r"(?P<case_category>[A-Z0-9]{1,2})-(?P<case_number>\d{1,10})$"
)
TOTAL_RE = re.compile(r"^(?P<count>\d[\d,]*) records? retrieved$")

COURT_TYPES: dict[str, dict[str, str]] = {
    "S": {"slug": "supreme", "level": "supreme", "name": "Supreme Court"},
    "A": {
        "slug": "court-of-appeals",
        "level": "appellate",
        "name": "Court of Appeals",
    },
    "D": {"slug": "district", "level": "trial", "name": "District Court"},
    "M": {
        "slug": "magistrate",
        "level": "limited_jurisdiction",
        "name": "Magistrate Court",
    },
    "T": {
        "slug": "metropolitan",
        "level": "limited_jurisdiction",
        "name": "Metropolitan Court",
    },
    "U": {
        "slug": "municipal",
        "level": "municipal",
        "name": "Municipal Court",
    },
}

SOURCE_WARNINGS = (
    "Case Lookup publishes official case metadata but does not provide filed "
    "documents. re:SearchNM and judiciary public-records channels are "
    "complementary document-access paths.",
    "The public application describes its acquisition grain as viewing an "
    "individual electronic court record. Party search is used only as a "
    "first-page discovery index; exact case retrieval is caller-selected.",
    "A Case Lookup row, a re:SearchNM copy, and a clerk-provided copy may be "
    "representations of the same court record rather than independent "
    "corroboration.",
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)


class NewMexicoCaseLookupError(RuntimeError):
    """Source, transport, or caller-selection error."""

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


class NewMexicoCaseLookupSelectionError(NewMexicoCaseLookupError):
    """The caller supplied a selector the verified route cannot represent."""

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


class NewMexicoCaseLookupTransportError(NewMexicoCaseLookupError):
    """The verified host could not be reached."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "transport_error",
            message,
            status=ResultStatus.UNAVAILABLE,
            category="transport",
            retryable=True,
        )


class NewMexicoCaseLookupHTTPError(NewMexicoCaseLookupError):
    """The verified host returned an unexpected HTTP status."""

    def __init__(self, status_code: int, url: str) -> None:
        status = (
            ResultStatus.RATE_LIMITED
            if status_code == 429
            else ResultStatus.UNAVAILABLE
        )
        super().__init__(
            "http_error",
            f"New Mexico Case Lookup returned HTTP {status_code}",
            status=status,
            category="transport",
            retryable=status_code == 429 or status_code >= 500,
            details={"status_code": status_code, "url": url},
        )


class NewMexicoCaseLookupSourceChanged(NewMexicoCaseLookupError):
    """The live response no longer matches the verified source contract."""

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
            category="source_contract",
            details=details,
        )


@dataclass(frozen=True)
class CaseNumberParts:
    full_case_number: str
    court_type: str
    court_location: str
    case_category: str
    case_number: str


@dataclass(frozen=True)
class PartySearchPage:
    records: tuple[dict[str, Any], ...]
    total_records: int
    total_pages: int
    native_page_size: int
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class ExactCasePage:
    record: dict[str, Any] | None
    source_url: str
    schema_fingerprint: str | None
    authoritative_no_results: bool


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _optional(value: Any) -> str | None:
    text = _clean(value)
    return text or None


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return slug or "value"


def _hash_payload(value: Any, *, length: int = 24) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[
        :length
    ]


def _date_iso(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def normalize_case_number(value: str) -> CaseNumberParts:
    normalized = _clean(value).upper()
    match = CASE_NUMBER_RE.fullmatch(normalized)
    if match is None:
        raise NewMexicoCaseLookupSelectionError(
            "invalid_case_number",
            "case number must use the source format TYPE-LOCATION-CATEGORY-NUMBER",
            details={"case_number": normalized},
        )
    return CaseNumberParts(
        full_case_number=normalized,
        court_type=match.group("court_type"),
        court_location=match.group("court_location"),
        case_category=match.group("case_category"),
        case_number=match.group("case_number"),
    )


def _court_record(
    case_number: str,
    display_name: str | None,
) -> dict[str, Any]:
    parts = normalize_case_number(case_number)
    court_type = COURT_TYPES.get(
        parts.court_type,
        {
            "slug": f"type-{parts.court_type.casefold()}",
            "level": "unknown",
            "name": f"Court type {parts.court_type}",
        },
    )
    native_code = f"{parts.court_type}-{parts.court_location}"
    return {
        "court_id": f"nm-case-lookup-{native_code.casefold()}",
        "name": display_name or court_type["name"],
        "state_code": STATE_CODE,
        "level": court_type["level"],
        "source_native_court_code": native_code,
        "source_native_court_type": parts.court_type,
        "source_native_location_code": parts.court_location,
        "court_type_name": court_type["name"],
    }


def _case_ref(case_number: str, court_id: str) -> str:
    return canonical_court_ref(
        SOURCE_ID,
        court_id,
        case_number,
        "case",
    )


def _record_ref(
    case_number: str,
    court_id: str,
    kind: str,
    identity: str,
) -> str:
    return canonical_court_ref(
        SOURCE_ID,
        court_id,
        f"{case_number}:{identity}",
        kind,
    )


def _validate_source_url(url: str, *, label: str) -> None:
    parsed = urlsplit(url)
    expected_path = EXPECTED_PATH.rstrip("/")
    path = parsed.path.rstrip("/")
    valid_path = path.casefold() == expected_path.casefold()
    session_prefix = f"{expected_path};jsessionid="
    if not valid_path and path.casefold().startswith(
        session_prefix.casefold()
    ):
        session_locator = path[len(session_prefix) :]
        valid_path = bool(
            session_locator
            and re.fullmatch(r"[A-Za-z0-9._-]+", session_locator)
        )
    if (
        parsed.scheme.casefold() != "https"
        or (parsed.hostname or "").casefold() != EXPECTED_HOST
        or not valid_path
    ):
        raise NewMexicoCaseLookupSourceChanged(
            "unexpected_source_route",
            f"{label} left the verified New Mexico Case Lookup route",
            details={
                "scheme": parsed.scheme,
                "host": parsed.hostname,
                "path": parsed.path,
            },
        )


def _require_html(response: Any) -> BeautifulSoup:
    media_type = (
        str(response.headers.get("Content-Type", ""))
        .split(";", 1)[0]
        .strip()
        .casefold()
    )
    if media_type not in {"text/html", "application/xhtml+xml"}:
        raise NewMexicoCaseLookupSourceChanged(
            "response_media_type_changed",
            "New Mexico Case Lookup did not return HTML",
            details={"content_type": media_type},
        )
    return BeautifulSoup(str(response.text), "html.parser")


def _form_values(form: Tag) -> dict[str, str]:
    """Return browser-successful controls without fabricating empty selects."""

    values: dict[str, str] = {}
    for node in form.find_all(["input", "select", "textarea"]):
        name = _optional(node.get("name"))
        if name is None or node.has_attr("disabled"):
            continue
        if node.name == "select":
            options = node.find_all("option")
            if not options:
                continue
            option = node.find("option", selected=True) or options[0]
            values[name] = str(option.get("value") or "")
            continue
        if node.name == "textarea":
            values[name] = node.get_text()
            continue
        input_type = str(node.get("type") or "text").casefold()
        if input_type in {"submit", "button", "image", "file", "reset"}:
            continue
        if input_type in {"checkbox", "radio"} and not node.has_attr("checked"):
            continue
        values[name] = str(node.get("value") or "")
    return values


def _form(soup: BeautifulSoup, form_id: str) -> Tag:
    form = soup.select_one(f"form#{form_id}")
    if not isinstance(form, Tag):
        raise NewMexicoCaseLookupSourceChanged(
            "form_missing",
            f"New Mexico Case Lookup no longer exposes {form_id}",
            details={"form_id": form_id},
        )
    return form


def _select_value_for_label(form: Tag, name: str, label: str) -> str:
    select = form.find("select", attrs={"name": name})
    if not isinstance(select, Tag):
        raise NewMexicoCaseLookupSourceChanged(
            "select_missing",
            f"New Mexico Case Lookup no longer exposes {name}",
            details={"field": name},
        )
    for option in select.find_all("option"):
        option_label = _clean(option.get_text(" "))
        option_value = str(option.get("value") or "")
        if (
            option_label.casefold() == label.casefold()
            or option_value.casefold() == label.casefold()
        ):
            return option_value
    raise NewMexicoCaseLookupSelectionError(
        "native_option_unavailable",
        f"source-native option {label!r} is unavailable for {name}",
        details={"field": name, "label": label},
    )


def _table_rows(table: Tag) -> list[tuple[list[str], list[str]]]:
    rows: list[tuple[list[str], list[str]]] = []
    for row in table.find_all("tr"):
        if row.find_parent("table") is not table:
            continue
        if "caption" in (row.get("class") or []):
            continue
        headers = [
            _clean(cell.get_text(" "))
            for cell in row.find_all("th")
            if cell.find_parent("tr") is row
        ]
        values = [
            _clean(cell.get_text(" "))
            for cell in row.find_all("td")
            if cell.find_parent("tr") is row
        ]
        if headers or values:
            rows.append((headers, values))
    return rows


def _table_title(table: Tag) -> str | None:
    caption_row = table.find("tr", class_="caption")
    if isinstance(caption_row, Tag):
        return _optional(caption_row.get_text(" "))
    return None


def _find_detail_table(soup: BeautifulSoup, title: str) -> Tag | None:
    for table in soup.find_all("table", class_="details"):
        if _table_title(table) == title:
            return table
    return None


def _schema_fingerprint(
    *,
    search_headers: Sequence[str] = (),
    detail_sections: Sequence[Mapping[str, Any]] = (),
) -> str:
    return _hash_payload(
        {
            "search_headers": list(search_headers),
            "detail_sections": list(detail_sections),
        },
        length=64,
    )


def _total_records(soup: BeautifulSoup) -> int:
    totals: list[int] = []
    for node in soup.select("p.total"):
        match = TOTAL_RE.fullmatch(_clean(node.get_text(" ")))
        if match is not None:
            totals.append(int(match.group("count").replace(",", "")))
    if not totals:
        raise NewMexicoCaseLookupSourceChanged(
            "search_total_missing",
            "New Mexico Case Lookup search did not publish a result total",
        )
    if len(set(totals)) != 1:
        raise NewMexicoCaseLookupSourceChanged(
            "search_totals_disagree",
            "New Mexico Case Lookup published inconsistent result totals",
            details={"totals": totals},
        )
    return totals[0]


def _total_pages(soup: BeautifulSoup) -> int:
    page_numbers: list[int] = []
    paginator = soup.select_one("span.paginator")
    if paginator is None:
        return 1
    for node in paginator.find_all(["a", "b"]):
        text = _clean(node.get_text(" "))
        if text.isdigit():
            page_numbers.append(int(text))
    return max(page_numbers, default=1)


def parse_party_search_page(
    html: str,
    *,
    source_url: str = BASE_URL,
    native_page_size: int = DEFAULT_NATIVE_PAGE_SIZE,
) -> PartySearchPage:
    """Parse one source-native party-search result page."""

    soup = BeautifulSoup(html, "html.parser")
    title = _clean(soup.title.get_text(" ") if soup.title else "")
    if title != "Caselookup - Search Results":
        raise NewMexicoCaseLookupSourceChanged(
            "search_page_title_changed",
            "New Mexico Case Lookup party search returned an unexpected page",
            details={"title": title},
        )
    total_records = _total_records(soup)
    table = soup.find("table", id="cl")
    if table is None:
        if total_records == 0:
            return PartySearchPage(
                records=(),
                total_records=0,
                total_pages=1,
                native_page_size=native_page_size,
                source_url=source_url,
                schema_fingerprint=_schema_fingerprint(),
            )
        raise NewMexicoCaseLookupSourceChanged(
            "search_table_missing",
            "New Mexico Case Lookup returned records without its result table",
        )
    assert isinstance(table, Tag)
    headers = tuple(
        _clean(cell.get_text(" "))
        for cell in table.find_all("th", recursive=False)
    )
    if not headers:
        first_row = table.find("tr")
        if isinstance(first_row, Tag):
            headers = tuple(
                _clean(cell.get_text(" "))
                for cell in first_row.find_all("th", recursive=False)
            )
    if headers != SEARCH_HEADERS:
        raise NewMexicoCaseLookupSourceChanged(
            "search_schema_changed",
            "New Mexico Case Lookup party-search columns changed",
            details={"expected": list(SEARCH_HEADERS), "observed": list(headers)},
        )

    records: list[dict[str, Any]] = []
    duplicate_counts: dict[str, int] = {}
    for row in table.find_all("tr"):
        if row.find_parent("table") is not table:
            continue
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        if len(cells) != len(SEARCH_HEADERS):
            raise NewMexicoCaseLookupSourceChanged(
                "search_row_shape_changed",
                "New Mexico Case Lookup returned an unexpected search row",
                details={"cell_count": len(cells)},
            )
        values = [_clean(cell.get_text(" ")) for cell in cells]
        fields = dict(zip(SEARCH_HEADERS, values, strict=True))
        parts = normalize_case_number(fields["Case Number"])
        court = _court_record(parts.full_case_number, fields["Court"])
        locator = cells[0].find("a", href=True)
        if locator is None:
            raise NewMexicoCaseLookupSourceChanged(
                "case_locator_missing",
                "New Mexico Case Lookup search row lost its case-detail locator",
                details={"case_number": parts.full_case_number},
            )
        occurrence_payload = {
            "case_number": parts.full_case_number,
            "party_name": fields["Party Name"],
            "party_type": fields["Party Type"],
            "party_number": fields["Party #"],
            "date_of_birth": fields["dob"],
            "caption": fields["Case Title"],
            "current_judge": fields["Case Judge"],
            "court": fields["Court"],
            "filing_date": fields["Filing Date"],
        }
        payload_key = canonical_json(occurrence_payload)
        duplicate_counts[payload_key] = duplicate_counts.get(payload_key, 0) + 1
        duplicate_ordinal = duplicate_counts[payload_key]
        occurrence_id = _hash_payload(
            {
                **occurrence_payload,
                "duplicate_ordinal": duplicate_ordinal,
            }
        )
        records.append(
            {
                "canonical_ref": _record_ref(
                    parts.full_case_number,
                    court["court_id"],
                    "case_party_search_hit",
                    occurrence_id,
                ),
                "source_id": SOURCE_ID,
                "record_kind": "case_party_search_hit",
                "case_ref": _case_ref(
                    parts.full_case_number,
                    court["court_id"],
                ),
                "case_number": parts.full_case_number,
                "court": court,
                "caption": fields["Case Title"] or None,
                "filing_date_raw": fields["Filing Date"] or None,
                "filing_date": _date_iso(fields["Filing Date"] or None),
                "current_judge": fields["Case Judge"] or None,
                "matched_party": {
                    "name": fields["Party Name"],
                    "role": fields["Party Type"] or None,
                    "party_number": fields["Party #"] or None,
                    "date_of_birth_raw": fields["dob"] or None,
                },
                "source_occurrence_id": occurrence_id,
                "source_occurrence_id_kind": (
                    "derived_from_published_row_fields_and_duplicate_ordinal"
                ),
                "detail_locator_available": True,
                "detail_locator_persisted": False,
                "source_url": BASE_URL,
            }
        )
    if len(records) > total_records:
        raise NewMexicoCaseLookupSourceChanged(
            "search_row_count_exceeds_total",
            "New Mexico Case Lookup returned more rows than its published total",
            details={"rows": len(records), "total": total_records},
        )
    return PartySearchPage(
        records=tuple(records),
        total_records=total_records,
        total_pages=_total_pages(soup),
        native_page_size=native_page_size,
        source_url=source_url,
        schema_fingerprint=_schema_fingerprint(search_headers=headers),
    )


def _generic_detail_sections(
    soup: BeautifulSoup,
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    untitled = 0
    for table in soup.find_all("table", class_="details"):
        title = _table_title(table)
        if title is None:
            untitled += 1
            title = f"Untitled detail section {untitled}"
        groups: list[dict[str, Any]] = []
        active: dict[str, Any] | None = None
        for headers, values in _table_rows(table):
            if headers:
                active = {"headers": headers, "records": []}
                groups.append(active)
                continue
            if not values:
                continue
            if active is None:
                active = {"headers": [], "records": []}
                groups.append(active)
            active_headers = list(active["headers"])
            fields: dict[str, str] = {}
            for index, value in enumerate(values):
                label = (
                    active_headers[index]
                    if index < len(active_headers)
                    else f"Value {index + 1}"
                )
                key = _slug(label)
                if key in fields:
                    key = f"{key}_{index + 1}"
                fields[key] = value
            active["records"].append({"values": values, "fields": fields})
        sections.append({"title": title, "groups": groups})
    return sections


def _section(
    sections: Sequence[Mapping[str, Any]],
    title: str,
) -> Mapping[str, Any] | None:
    return next(
        (section for section in sections if section.get("title") == title),
        None,
    )


def _first_group_fields(
    section: Mapping[str, Any],
    expected_headers: Sequence[str],
) -> dict[str, str]:
    groups = section.get("groups")
    if not isinstance(groups, list) or not groups:
        raise NewMexicoCaseLookupSourceChanged(
            "detail_group_missing",
            "New Mexico Case Lookup detail section has no data group",
            details={"title": section.get("title")},
        )
    group = groups[0]
    headers = tuple(group.get("headers") or ())
    if headers != tuple(expected_headers):
        raise NewMexicoCaseLookupSourceChanged(
            "detail_schema_changed",
            "New Mexico Case Lookup detail-section columns changed",
            details={
                "title": section.get("title"),
                "expected": list(expected_headers),
                "observed": list(headers),
            },
        )
    records = group.get("records")
    if not isinstance(records, list) or len(records) != 1:
        raise NewMexicoCaseLookupSourceChanged(
            "detail_summary_shape_changed",
            "New Mexico Case Lookup case summary has an unexpected row count",
            details={"row_count": len(records or ())},
        )
    return dict(records[0]["fields"])


def _parse_parties(
    soup: BeautifulSoup,
    *,
    case_number: str,
    court_id: str,
) -> list[dict[str, Any]]:
    table = _find_detail_table(soup, "Parties to this Case")
    if table is None:
        return []
    rows = _table_rows(table)
    observed_headers = next((tuple(headers) for headers, _ in rows if headers), ())
    if observed_headers != PARTY_HEADERS:
        raise NewMexicoCaseLookupSourceChanged(
            "party_schema_changed",
            "New Mexico Case Lookup party columns changed",
            details={"observed": list(observed_headers)},
        )
    parties: list[dict[str, Any]] = []
    duplicate_counts: dict[str, int] = {}
    for _headers, values in rows:
        if len(values) == 4 and values[0]:
            identity_payload = {
                "case_number": case_number,
                "role_code": values[0],
                "role": values[1],
                "party_number": values[2],
                "name": values[3],
            }
            identity_key = canonical_json(identity_payload)
            duplicate_counts[identity_key] = (
                duplicate_counts.get(identity_key, 0) + 1
            )
            identity = _hash_payload(
                {
                    **identity_payload,
                    "duplicate_ordinal": duplicate_counts[identity_key],
                }
            )
            parties.append(
                {
                    "canonical_ref": _record_ref(
                        case_number,
                        court_id,
                        "case_party",
                        identity,
                    ),
                    "name": values[3],
                    "role_code": values[0],
                    "role": values[1],
                    "party_number": values[2] or None,
                    "attorneys": [],
                }
            )
        elif values and parties:
            attorney_text = next(
                (value for value in reversed(values) if value),
                "",
            )
            if attorney_text.upper().startswith("ATTORNEY:"):
                name = _clean(attorney_text.split(":", 1)[1])
                parties[-1]["attorneys"].append(
                    {
                        "name": name,
                        "source_text": attorney_text,
                    }
                )
    return parties


def _parse_register(
    soup: BeautifulSoup,
    *,
    case_number: str,
    court_id: str,
) -> list[dict[str, Any]]:
    table = _find_detail_table(soup, "Register of Actions Activity")
    if table is None:
        return []
    rows = _table_rows(table)
    observed_headers = next((tuple(headers) for headers, _ in rows if headers), ())
    if observed_headers != REGISTER_HEADERS:
        raise NewMexicoCaseLookupSourceChanged(
            "register_schema_changed",
            "New Mexico Case Lookup register columns changed",
            details={"observed": list(observed_headers)},
        )
    entries: list[dict[str, Any]] = []
    duplicate_counts: dict[str, int] = {}
    for _headers, values in rows:
        if len(values) == 6 and values[0]:
            payload = {
                "event_date_raw": values[0],
                "event_description": values[1],
                "event_result": values[2],
                "party_type": values[3],
                "party_number": values[4],
                "amount": values[5],
            }
            key = canonical_json(payload)
            duplicate_counts[key] = duplicate_counts.get(key, 0) + 1
            entry_id = _hash_payload(
                {
                    "case_number": case_number,
                    **payload,
                    "duplicate_ordinal": duplicate_counts[key],
                }
            )
            entries.append(
                {
                    "canonical_ref": _record_ref(
                        case_number,
                        court_id,
                        "docket_entry",
                        entry_id,
                    ),
                    "native_entry_id": f"derived:{entry_id}",
                    "native_entry_id_kind": (
                        "derived_from_published_row_fields_and_duplicate_ordinal"
                    ),
                    "event_date_raw": values[0],
                    "event_date": _date_iso(values[0]),
                    "event_description": values[1] or None,
                    "event_result": values[2] or None,
                    "party_type": values[3] or None,
                    "party_number": values[4] or None,
                    "amount_raw": values[5] or None,
                    "detail_text": None,
                }
            )
        elif entries and values and not values[0]:
            detail = next((value for value in values[1:] if value), None)
            if detail is not None:
                entries[-1]["detail_text"] = detail
    return entries


def _parse_judge_history(
    soup: BeautifulSoup,
    *,
    case_number: str,
    court_id: str,
) -> list[dict[str, Any]]:
    table = _find_detail_table(soup, "Judge Assignment History")
    if table is None:
        return []
    rows = _table_rows(table)
    observed_headers = next((tuple(headers) for headers, _ in rows if headers), ())
    if observed_headers != JUDGE_HISTORY_HEADERS:
        raise NewMexicoCaseLookupSourceChanged(
            "judge_history_schema_changed",
            "New Mexico Case Lookup judge-history columns changed",
            details={"observed": list(observed_headers)},
        )
    history: list[dict[str, Any]] = []
    duplicate_counts: dict[str, int] = {}
    for _headers, values in rows:
        if len(values) != 4 or not any(values):
            continue
        identity_payload = {
            "case_number": case_number,
            "assignment_date": values[0],
            "judge_name": values[1],
            "sequence_number": values[2],
            "description": values[3],
        }
        identity_key = canonical_json(identity_payload)
        duplicate_counts[identity_key] = (
            duplicate_counts.get(identity_key, 0) + 1
        )
        event_id = _hash_payload(
            {
                **identity_payload,
                "duplicate_ordinal": duplicate_counts[identity_key],
            }
        )
        history.append(
            {
                "canonical_ref": _record_ref(
                    case_number,
                    court_id,
                    "judge_assignment_event",
                    event_id,
                ),
                "assignment_event_id": f"derived:{event_id}",
                "assignment_event_id_kind": (
                    "derived_from_published_row_fields_and_duplicate_ordinal"
                ),
                "assignment_date_raw": values[0] or None,
                "assignment_date": _date_iso(values[0] or None),
                "judge_name": values[1] or None,
                "sequence_number": values[2] or None,
                "assignment_event_description": values[3] or None,
            }
        )
    return history


def _records_for_group(
    section: Mapping[str, Any] | None,
    first_header: str,
) -> list[dict[str, Any]]:
    if section is None:
        return []
    for group in section.get("groups") or []:
        headers = list(group.get("headers") or [])
        if headers and headers[0] == first_header:
            return [dict(record) for record in group.get("records") or []]
    return []


def _identified_group_records(
    records: Sequence[Mapping[str, Any]],
    *,
    case_number: str,
    child_kind: str,
) -> list[dict[str, Any]]:
    identified: list[dict[str, Any]] = []
    duplicate_counts: dict[str, int] = {}
    for record in records:
        copied = dict(record)
        fields = dict(
            copied.get("fields")
            if isinstance(copied.get("fields"), Mapping)
            else {}
        )
        values = list(copied.get("values") or [])
        identity_payload = {
            "case_number": case_number,
            "child_kind": child_kind,
            "fields": fields,
            "values": values,
        }
        identity_key = canonical_json(identity_payload)
        duplicate_counts[identity_key] = (
            duplicate_counts.get(identity_key, 0) + 1
        )
        child_id = _hash_payload(
            {
                **identity_payload,
                "duplicate_ordinal": duplicate_counts[identity_key],
            }
        )
        copied["source_child_id"] = f"derived:{child_id}"
        copied["source_child_id_kind"] = (
            "derived_from_published_fields_and_duplicate_ordinal"
        )
        identified.append(copied)
    return identified


def parse_case_detail_page(
    html: str,
    *,
    requested_case_number: str,
    source_url: str = BASE_URL,
) -> ExactCasePage:
    """Parse one exact Case Lookup response or authoritative empty page."""

    requested = normalize_case_number(requested_case_number)
    soup = BeautifulSoup(html, "html.parser")
    title = _clean(soup.title.get_text(" ") if soup.title else "")
    if title != "Caselookup - Case Detail":
        raise NewMexicoCaseLookupSourceChanged(
            "case_detail_title_changed",
            "New Mexico Case Lookup exact search returned an unexpected page",
            details={"title": title},
        )
    page_text = _clean(soup.get_text(" "))
    if NO_RESULTS_TEXT in page_text:
        return ExactCasePage(
            record=None,
            source_url=source_url,
            schema_fingerprint=None,
            authoritative_no_results=True,
        )

    sections = _generic_detail_sections(soup)
    summary_section = _section(sections, "Case Detail")
    if summary_section is None:
        raise NewMexicoCaseLookupSourceChanged(
            "case_summary_missing",
            "New Mexico Case Lookup exact response has no case summary",
        )
    summary = _first_group_fields(summary_section, CASE_SUMMARY_HEADERS)
    case_number = _clean(summary.get("case_number")).upper()
    if case_number != requested.full_case_number:
        raise NewMexicoCaseLookupSourceChanged(
            "case_number_mismatch",
            "New Mexico Case Lookup returned a different exact case",
            details={
                "requested": requested.full_case_number,
                "observed": case_number,
            },
        )
    court_name = _optional(summary.get("court"))
    court = _court_record(case_number, court_name)
    heading = soup.select_one("h2")
    caption = _optional(heading.get_text(" ") if heading else None)
    parties = _parse_parties(
        soup,
        case_number=case_number,
        court_id=court["court_id"],
    )
    register = _parse_register(
        soup,
        case_number=case_number,
        court_id=court["court_id"],
    )
    judge_history = _parse_judge_history(
        soup,
        case_number=case_number,
        court_id=court["court_id"],
    )
    complaint_section = _section(sections, "Civil Complaint Detail")
    complaint_records = _identified_group_records(
        _records_for_group(
            complaint_section,
            "Complaint Date",
        ),
        case_number=case_number,
        child_kind="complaint",
    )
    cause_records = _identified_group_records(
        _records_for_group(
            complaint_section,
            "COA Sequence #",
        ),
        case_number=case_number,
        child_kind="cause_of_action",
    )
    disposition_records = [
        record
        for record in complaint_records
        if _optional(record.get("fields", {}).get("disposition"))
        or _optional(record.get("fields", {}).get("disposition_date"))
    ]
    section_schema = [
        {
            "title": section["title"],
            "groups": [
                list(group.get("headers") or [])
                for group in section.get("groups") or []
            ],
        }
        for section in sections
    ]
    record = {
        "canonical_ref": _case_ref(case_number, court["court_id"]),
        "source_id": SOURCE_ID,
        "record_kind": "new_mexico_case_detail",
        "case_number": case_number,
        "court": court,
        "caption": caption,
        "current_judge": _optional(summary.get("current_judge")),
        "filing_date_raw": _optional(summary.get("filing_date")),
        "filing_date": _date_iso(_optional(summary.get("filing_date"))),
        "parties": parties,
        "complaint_records": complaint_records,
        "cause_records": cause_records,
        "disposition_records": disposition_records,
        "register_of_actions": register,
        "judge_assignment_history": judge_history,
        "case_detail_sections": sections,
        "documents_available": False,
        "document_access_complements": [
            {
                "name": "re:SearchNM",
                "url": RESEARCH_NM_URL,
                "authentication": "registration",
            },
            {
                "name": "New Mexico Judiciary public records request",
                "url": IPRA_URL,
            },
        ],
        "source_url": BASE_URL,
        "source_internal_case_locator": None,
        "retrieval": {
            "selection": "caller_selected_exact_case_number",
            "source_acquisition_grain": "one_individual_electronic_case_record",
            "ephemeral_tapestry_locators_persisted": False,
        },
    }
    return ExactCasePage(
        record=record,
        source_url=source_url,
        schema_fingerprint=_schema_fingerprint(
            detail_sections=section_schema,
        ),
        authoritative_no_results=False,
    )


class NewMexicoCaseLookupClient:
    """Requests-compatible client for the verified Tapestry lifecycle."""

    def __init__(
        self,
        session: Any | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        max_retries: int = DEFAULT_MAX_RETRIES,
        request_budget: int | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if request_budget is not None and request_budget <= 0:
            raise ValueError("request_budget must be positive when supplied")
        self._owns_session = session is None
        self.session = session or requests.Session()
        if hasattr(self.session, "headers"):
            self.session.headers.update(
                {
                    "User-Agent": USER_AGENT,
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
        self.timeout = timeout
        self.minimum_interval = minimum_interval
        self.max_retries = max_retries
        self.request_budget = request_budget
        self._sleeper = sleeper
        self._clock = clock
        self._last_request_at = 0.0
        self.request_count = 0

    def close(self) -> None:
        if self._owns_session and hasattr(self.session, "close"):
            self.session.close()

    def __enter__(self) -> NewMexicoCaseLookupClient:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        _validate_source_url(url, label="requested URL")
        for attempt in range(self.max_retries + 1):
            if (
                self.request_budget is not None
                and self.request_count >= self.request_budget
            ):
                raise NewMexicoCaseLookupSelectionError(
                    "request_budget_exhausted",
                    "New Mexico Case Lookup request budget was exhausted",
                    details={
                        "request_budget": self.request_budget,
                        "requests_made": self.request_count,
                    },
                )
            elapsed = self._clock() - self._last_request_at
            if elapsed < self.minimum_interval:
                self._sleeper(self.minimum_interval - elapsed)
            try:
                self._last_request_at = self._clock()
                self.request_count += 1
                response = self.session.request(
                    method,
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    **kwargs,
                )
            except requests.RequestException as error:
                if attempt < self.max_retries:
                    self._sleeper(0.5 * (2**attempt))
                    continue
                raise NewMexicoCaseLookupTransportError(
                    f"New Mexico Case Lookup request failed: {error}"
                ) from error
            final_url = str(getattr(response, "url", url))
            _validate_source_url(final_url, label="response URL")
            status_code = int(response.status_code)
            if (
                status_code == 429 or status_code >= 500
            ) and attempt < self.max_retries:
                self._sleeper(0.5 * (2**attempt))
                continue
            if status_code < 200 or status_code >= 300:
                raise NewMexicoCaseLookupHTTPError(status_code, final_url)
            return response
        raise NewMexicoCaseLookupTransportError(
            "New Mexico Case Lookup exhausted retries"
        )

    def _get_html(self, url: str) -> tuple[BeautifulSoup, str]:
        response = self._request(
            "GET",
            url,
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        return _require_html(response), str(response.url)

    def _post_form(
        self,
        soup: BeautifulSoup,
        form_id: str,
        updates: Mapping[str, str],
    ) -> tuple[BeautifulSoup, str]:
        form = _form(soup, form_id)
        payload = _form_values(form)
        payload.update(updates)
        action = urljoin(BASE_URL, str(form.get("action") or ""))
        _validate_source_url(action, label=f"{form_id} action")
        response = self._request(
            "POST",
            action,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://caselookup.nmcourts.gov",
                "Referer": BASE_URL,
            },
            data=payload,
        )
        return _require_html(response), str(response.url)

    def bootstrap(self) -> BeautifulSoup:
        landing, _source_url = self._get_html(BASE_URL)
        if DISCLAIMER_TEXT not in _clean(landing.get_text(" ")):
            raise NewMexicoCaseLookupSourceChanged(
                "disclaimer_changed",
                "New Mexico Case Lookup disclaimer contract changed",
            )
        accepted, _accepted_url = self._post_form(
            landing,
            DISCLAIMER_FORM_ID,
            {"Submit": "I Accept"},
        )
        title = _clean(
            accepted.title.get_text(" ") if accepted.title else ""
        )
        if (
            title != "Caselookup - Name Search"
            or accepted.select_one(f"form#{NAME_SEARCH_FORM_ID}") is None
        ):
            raise NewMexicoCaseLookupSourceChanged(
                "acceptance_route_changed",
                "New Mexico Case Lookup acceptance did not open name search",
                details={"title": title},
            )
        return accepted

    def search_party(
        self,
        party_name: str,
        *,
        date_of_birth: str | None = None,
        birth_year: str | None = None,
        drivers_license: str | None = None,
        drivers_license_state: str | None = None,
        native_page_size: int = DEFAULT_NATIVE_PAGE_SIZE,
    ) -> PartySearchPage:
        party_name = _clean(party_name)
        if not party_name:
            raise NewMexicoCaseLookupSelectionError(
                "party_name_required",
                "party name must not be empty",
            )
        if date_of_birth and birth_year:
            raise NewMexicoCaseLookupSelectionError(
                "birth_selector_conflict",
                "date_of_birth and birth_year are mutually exclusive",
            )
        if native_page_size not in NATIVE_PAGE_SIZES:
            raise NewMexicoCaseLookupSelectionError(
                "invalid_native_page_size",
                "native page size must match a source-published option",
                details={
                    "native_page_size": native_page_size,
                    "available": list(NATIVE_PAGE_SIZES),
                },
            )
        name_search = self.bootstrap()
        form = _form(name_search, NAME_SEARCH_FORM_ID)
        updates = {
            "partyName": party_name,
            "driversLicense": _clean(drivers_license),
            "dob": _clean(date_of_birth),
            "yearOnlyDob": _clean(birth_year),
            "caseCategory": "",
            "results": _select_value_for_label(
                form,
                "results",
                str(native_page_size),
            ),
            "Submit": "Name Search",
        }
        if drivers_license_state:
            updates["dlState"] = _select_value_for_label(
                form,
                "dlState",
                drivers_license_state.upper(),
            )
        result, source_url = self._post_form(
            name_search,
            NAME_SEARCH_FORM_ID,
            updates,
        )
        return parse_party_search_page(
            str(result),
            source_url=source_url,
            native_page_size=native_page_size,
        )

    def exact_case(self, case_number: str) -> ExactCasePage:
        parts = normalize_case_number(case_number)
        name_search = self.bootstrap()
        link = next(
            (
                anchor
                for anchor in name_search.find_all("a", href=True)
                if _clean(anchor.get_text(" ")) == "Case Number Search"
            ),
            None,
        )
        if link is None:
            raise NewMexicoCaseLookupSourceChanged(
                "case_search_link_missing",
                "New Mexico Case Lookup no longer links to case-number search",
            )
        case_search_url = urljoin(BASE_URL, str(link["href"]))
        case_search, _search_url = self._get_html(case_search_url)
        title = _clean(
            case_search.title.get_text(" ") if case_search.title else ""
        )
        if title != "Caselookup - Case Number Search":
            raise NewMexicoCaseLookupSourceChanged(
                "case_search_route_changed",
                "New Mexico Case Lookup returned an unexpected case-search page",
                details={"title": title},
            )
        result, source_url = self._post_form(
            case_search,
            CASE_NUMBER_SEARCH_FORM_ID,
            {
                "courtType": parts.court_type,
                "courtLocation": parts.court_location,
                "caseCategory": parts.case_category,
                "caseNumber": parts.case_number,
                "Submit": "Case Number Search",
            },
        )
        return parse_case_detail_page(
            str(result),
            requested_case_number=parts.full_case_number,
            source_url=source_url,
        )


def _source_metadata() -> SourceMetadata:
    return SourceMetadata(
        source_id=SOURCE_ID,
        name=SOURCE_NAME,
        source_role="official_statewide_case_metadata_lookup",
        base_url=BASE_URL,
        dataset_id="new-mexico-judiciary-case-lookup",
        metadata={
            "authority": "New Mexico Judiciary",
            "state_code": STATE_CODE,
            "authentication": "none",
            "platform_family": PLATFORM_FAMILY,
            "source_acquisition_grain": (
                "one_individual_electronic_case_record"
            ),
            "documents_available": False,
            "observed_at": OBSERVED_AT,
        },
    )


def _jurisdiction() -> JurisdictionMetadata:
    return JurisdictionMetadata(
        jurisdiction_id=STATE_GEOID,
        name="New Mexico",
        state_code=STATE_CODE,
        metadata={
            "publisher": "New Mexico Judiciary",
            "court_families": [
                "Supreme Court",
                "Court of Appeals",
                "District Court",
                "Magistrate Court",
                "Metropolitan Court",
                "Municipal Court",
            ],
        },
    )


def _query(
    operation: str,
    *,
    parameters: Mapping[str, Any],
    limit: int | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=_source_metadata(),
        jurisdiction=_jurisdiction(),
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            metadata={
                "discovery_index": "first_native_result_page_only",
                "exact_case_selection": "one_caller_selected_case",
                "technical_paging": "not_exposed_as_an_acquisition_loop",
                "default_result_cap": None,
            },
        ),
    )


def _source_record() -> dict[str, Any]:
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            "nm-judiciary",
            "source-contract",
            "source_contract",
        ),
        "source_id": SOURCE_ID,
        "record_kind": "source_contract",
        "publisher": "New Mexico Judiciary",
        "observed_at": OBSERVED_AT,
        "access": {
            "authentication": "none",
            "acceptance_form": DISCLAIMER_FORM_ID,
            "party_search_form": NAME_SEARCH_FORM_ID,
            "case_number_search_form": CASE_NUMBER_SEARCH_FORM_ID,
            "platform_family": PLATFORM_FAMILY,
            "source_acquisition_grain": (
                "one_individual_electronic_case_record"
            ),
            "party_discovery_index": "first_native_page_only",
            "exact_case_request_count": PROBE_EXPECTED_REQUESTS,
            "ephemeral_session_and_csrf_values_persisted": False,
        },
        "coverage": {
            "case_metadata": [
                "appellate",
                "district",
                "magistrate",
                "metropolitan",
                "municipal",
            ],
            "documents_available": False,
            "district_and_magistrate_freshness": "updated daily",
            "pre_1997_note": (
                "some cases may remain in separate court databases"
            ),
            "municipal_note": (
                "criminal domestic-violence and DWI historical convictions "
                "from September 1, 1991"
            ),
            "juvenile_cases_displayed": False,
            "juvenile_display_cutoff": "2007-07-01",
            "fvpa_orders_displayed": False,
            "fvpa_display_cutoff": "2008-07-01",
        },
        "record_fields": [
            "case identity",
            "caption",
            "court",
            "filing date",
            "parties",
            "counsel",
            "complaints and causes",
            "published dispositions",
            "register of actions",
            "current judge",
            "judge assignment history",
        ],
        "complements": [
            {
                "name": "re:SearchNM",
                "url": RESEARCH_NM_URL,
                "value": "registered case-information and document access",
            },
            {
                "name": "Judiciary public-records request",
                "url": IPRA_URL,
                "value": "records absent from the public web application",
            },
            {
                "name": "Individual court clerk",
                "url": "https://www.nmcourts.gov/find-a-court/",
                "value": "older or court-held records",
            },
        ],
        "source_urls": {
            "application": BASE_URL,
            "official_information": INFO_URL,
        },
    }


def _public_error(error: NewMexicoCaseLookupError) -> PublicRecordsError:
    return PublicRecordsError(
        code=error.code,
        message=str(error),
        category=error.category,
        retryable=error.retryable,
        details=error.details,
    )


def _failure(
    query: PublicRecordsQuery,
    error: NewMexicoCaseLookupError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [_public_error(error)],
        warnings=SOURCE_WARNINGS,
    )


def _log(query: PublicRecordsQuery, count: int | None) -> None:
    try:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    except Exception as error:
        print(f"Warning: could not log search: {error}", file=sys.stderr)


def execute(
    args: argparse.Namespace,
    *,
    client: NewMexicoCaseLookupClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute a standalone source, search, exact-case, or probe operation."""

    operation = args.command
    limit = getattr(args, "limit", None)
    try:
        if operation == "search":
            parameters = {
                "party_name": _clean(args.party_name),
                "date_of_birth": getattr(args, "date_of_birth", None),
                "birth_year": getattr(args, "birth_year", None),
                "drivers_license": getattr(args, "drivers_license", None),
                "drivers_license_state": getattr(
                    args,
                    "drivers_license_state",
                    None,
                ),
                "native_page_size": getattr(
                    args,
                    "native_page_size",
                    DEFAULT_NATIVE_PAGE_SIZE,
                ),
            }
        elif operation == "case":
            parameters = {
                "case_number": normalize_case_number(
                    args.case_number
                ).full_case_number
            }
        elif operation == "probe":
            parameters = {
                "sentinel_case_number": PROBE_CASE_NUMBER,
                "expected_requests": PROBE_EXPECTED_REQUESTS,
                "routes": [
                    "disclaimer",
                    "acceptance",
                    "case_number_search",
                    "exact_case_detail",
                ],
            }
        else:
            parameters = {}
    except NewMexicoCaseLookupError as error:
        return _failure(
            _query(
                operation,
                parameters={"invalid_selection": True},
                limit=limit,
            ),
            error,
        )

    query = _query(operation, parameters=parameters, limit=limit)
    source_client = client or NewMexicoCaseLookupClient(
        timeout=float(getattr(args, "timeout", DEFAULT_TIMEOUT)),
        minimum_interval=float(
            getattr(args, "minimum_interval", DEFAULT_MINIMUM_INTERVAL)
        ),
        max_retries=int(
            getattr(args, "retry_attempts", DEFAULT_MAX_RETRIES)
        ),
    )
    try:
        if operation == "source":
            result = PublicRecordsResult.success(
                query,
                [_source_record()],
                warnings=SOURCE_WARNINGS,
            )
        elif operation == "search":
            page = source_client.search_party(
                parameters["party_name"],
                date_of_birth=parameters["date_of_birth"],
                birth_year=parameters["birth_year"],
                drivers_license=parameters["drivers_license"],
                drivers_license_state=parameters["drivers_license_state"],
                native_page_size=parameters["native_page_size"],
            )
            records = list(page.records)
            if limit is not None:
                records = records[:limit]
            warnings = list(SOURCE_WARNINGS)
            warnings.append(
                f"Source reported {page.total_records} party occurrences "
                f"across {page.total_pages} native page(s); this response "
                f"contains {len(records)} first-page occurrence(s)."
            )
            if page.total_records > len(page.records):
                result = PublicRecordsResult.failure(
                    query,
                    ResultStatus.PARTIAL,
                    [
                        PublicRecordsError(
                            code=(
                                "additional_native_result_pages_not_traversed"
                            ),
                            message=(
                                "The source reports additional party-search "
                                "pages; no paging or result-following loop was "
                                "performed."
                            ),
                            category="source_acquisition_grain",
                            details={
                                "source_total_records": page.total_records,
                                "first_page_records": len(page.records),
                                "source_total_pages": page.total_pages,
                            },
                        )
                    ],
                    records=records,
                    warnings=warnings,
                )
            else:
                result = PublicRecordsResult.success(
                    query,
                    records,
                    warnings=warnings,
                )
        elif operation == "case":
            page = source_client.exact_case(parameters["case_number"])
            result = PublicRecordsResult.success(
                query,
                [page.record] if page.record is not None else [],
                warnings=SOURCE_WARNINGS,
            )
        else:
            page = source_client.exact_case(PROBE_CASE_NUMBER)
            if page.record is None:
                raise NewMexicoCaseLookupSourceChanged(
                    "probe_case_missing",
                    "New Mexico Case Lookup historical sentinel is unavailable",
                    details={"case_number": PROBE_CASE_NUMBER},
                )
            case = page.record
            probe = _source_record()
            probe["record_kind"] = "source_probe"
            probe["probe"] = {
                "status": "available",
                "request_count": source_client.request_count,
                "expected_request_count": PROBE_EXPECTED_REQUESTS,
                "routes_exercised": [
                    "disclaimer",
                    "acceptance",
                    "case_number_search",
                    "exact_case_detail",
                ],
                "sentinel_case_number": case["case_number"],
                "sentinel_caption": case["caption"],
                "sentinel_court_id": case["court"]["court_id"],
                "party_count": len(case["parties"]),
                "register_entry_count": len(case["register_of_actions"]),
                "judge_history_count": len(
                    case["judge_assignment_history"]
                ),
                "documents_available": case["documents_available"],
                "schema_fingerprint": page.schema_fingerprint,
            }
            result = PublicRecordsResult.success(
                query,
                [probe],
                warnings=SOURCE_WARNINGS,
            )
    except NewMexicoCaseLookupError as error:
        result = _failure(query, error)
    finally:
        if client is None:
            source_client.close()

    if log_results:
        count = (
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        _log(query, count)
    return result


def _nonblank(value: str) -> str:
    text = _clean(value)
    if not text:
        raise argparse.ArgumentTypeError("value must not be empty")
    return text


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be nonnegative")
    return parsed


def _add_transport_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--retry-attempts",
        type=_nonnegative_int,
        default=DEFAULT_MAX_RETRIES,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query New Mexico Judiciary Case Lookup"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser(
        "source",
        help="Show verified routes, fields, identities, and complements",
    )
    add_output_args(source)

    search = subparsers.add_parser(
        "search",
        help="Search one targeted party on the first native result page",
    )
    search.add_argument("party_name", type=_nonblank)
    birth = search.add_mutually_exclusive_group()
    birth.add_argument("--date-of-birth")
    birth.add_argument("--birth-year")
    search.add_argument("--drivers-license")
    search.add_argument("--drivers-license-state")
    search.add_argument(
        "--native-page-size",
        type=int,
        choices=NATIVE_PAGE_SIZES,
        default=DEFAULT_NATIVE_PAGE_SIZE,
    )
    search.add_argument(
        "--limit",
        type=_positive_int,
        help="Apply a caller-selected window to the returned first page",
    )
    add_output_args(search)

    case = subparsers.add_parser(
        "case",
        help="Retrieve one caller-selected exact case record",
    )
    case.add_argument("case_number", type=_nonblank)
    add_output_args(case)

    probe = subparsers.add_parser(
        "probe",
        help="Exercise the four-request exact historical-case lifecycle",
    )
    add_output_args(probe)

    for command in subparsers.choices.values():
        _add_transport_args(command)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"New Mexico Judiciary Case Lookup {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2))
        return
    print(
        f"New Mexico Judiciary Case Lookup {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    for record in result.records:
        case_number = record.get("case_number")
        if case_number:
            print(f"- {case_number} | {record.get('caption') or ''}")
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    args = build_parser().parse_args()
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
