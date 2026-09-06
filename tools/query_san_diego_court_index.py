#!/usr/bin/env python3
"""Query San Diego Superior Court's Court Index and new-filing lists.

The official Court Index exposes party-name search, exact case-number search,
and case-detail pages.  Cloudflare currently challenges direct HTTP and
headless Chromium, while ordinary headed Chrome works anonymously; the default
transport therefore follows the public forms in headed Chrome.

The court also publishes static lists of newly filed civil, criminal,
domestic, mental-health, and probate cases.  Those lists retain party names for
five court days and are split into native alphabet partitions.

Examples:
    uv run python tools/query_san_diego_court_index.py party-search \
        --case-type civil --last-name Epstein --first-name Jeffrey --json
    uv run python tools/query_san_diego_court_index.py case-search IC810023
    uv run python tools/query_san_diego_court_index.py case-detail \
        'https://courtindex.sdcourt.ca.gov/CISPublic/casedetail?casenum=IC810023&casesite=SD&applcode=C'
    uv run python tools/query_san_diego_court_index.py new-filings \
        --case-type all --output san-diego-new-filings.json
    uv run python tools/query_san_diego_court_index.py alternatives --json
    uv run python tools/query_san_diego_court_index.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urljoin, urlparse

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
        inferred_schema,
        schema_fingerprint,
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
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-ca-san-diego-superior-court-index"
STATE_CODE = "CA"
COUNTY_GEOID = "06073"
COURT_ID = "ca-san-diego-superior-court"
COURT_NAME = "Superior Court of California, County of San Diego"
COURT_OFFICIAL_URL = "https://www.sdcourt.ca.gov/"
INDEX_BASE_URL = "https://courtindex.sdcourt.ca.gov"
INDEX_HOME_URL = f"{INDEX_BASE_URL}/CISPublic/enter"
PARTY_SEARCH_URL = f"{INDEX_BASE_URL}/CISPublic/namesearch"
CASE_SEARCH_URL = f"{INDEX_BASE_URL}/CISPublic/casesearch"
CASE_DETAIL_PATH = "/CISPublic/casedetail"
NEW_FILINGS_BASE_URL = (
    "https://www.sandiego.courts.ca.gov/portal/online/newfiles/"
)
NEW_FILINGS_LANDING_URL = urljoin(NEW_FILINGS_BASE_URL, "newfile.html")
ACCESS_RECORDS_URL = (
    "https://www.sdcourt.ca.gov/sdcourt/generalinformation/"
    "accesscourtrecords"
)
FAMILY_ROA_URL = "https://roasearch.sdcourt.ca.gov/"
ODYSSEY_ROA_URL = "https://odyroa.sdcourt.ca.gov/"
CALENDAR_URL = (
    "https://www.sandiego.courts.ca.gov/portal/online/calendar/"
)
DA_SEARCH_URL = f"{INDEX_BASE_URL}/CISPublic/dasearch"
APPELLATE_SEARCH_URL = (
    "https://appellatecases.courtinfo.ca.gov/search.cfm?dist=41"
)
PROBE_CASE_NUMBER = "IC810023"
PROBE_DETAIL_URL = (
    f"{INDEX_BASE_URL}{CASE_DETAIL_PATH}"
    "?casenum=IC810023&casesite=SD&applcode=C"
)
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)
BROWSER_HELPER_PATH = Path(__file__).with_name(
    "_san_diego_court_index_browser_helper.js"
)

CASE_TYPE_VALUES = {
    "civil": "C",
    "criminal": "R",
    "domestic": "D",
    "mental-health": "M",
    "probate": "P",
}
CASE_SEARCH_TYPE_VALUES = {"all": "A", **CASE_TYPE_VALUES}
SITE_VALUES = {
    "all": "A",
    "east-county": "EC",
    "kearny-mesa": "KM",
    "north-county": "NC",
    "ramona": "RM",
    "san-diego": "SD",
    "south-county": "SB",
}
PARTY_TYPE_VALUES = {
    "all": "A",
    "defendant-respondent": "D",
    "plaintiff-petitioner": "P",
}
NEW_FILING_TYPE_CODES = {
    "civil": "cv",
    "criminal": "cr",
    "domestic": "dm",
    "mental-health": "mh",
    "probate": "pb",
}

SOURCE_WARNINGS = (
    "The Court Index is an index, not the official court record.",
    "The court states that the number of selections returned is limited but "
    "does not publish the numeric result ceiling.",
    "Juvenile cases and infractions are not in the index; civil limited and "
    "misdemeanor records may only be available for ten years at some locations.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="San Diego Superior Court Index and New Case Filings",
    source_role="county_superior_court_case_party_index_and_recent_filings",
    base_url=INDEX_HOME_URL,
    dataset_id="san-diego-superior-court-index",
    metadata={
        "authority": COURT_NAME,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "court_id": COURT_ID,
        "authentication": "none",
        "platform_family": "san_diego_cispublic",
        "coverage_start_year": 1974,
        "coverage": [
            "civil",
            "criminal",
            "domestic_family",
            "mental_health",
            "probate",
        ],
        "excluded_from_index": ["juvenile", "infractions"],
        "native_result_page_size_observed": 50,
        "native_result_ceiling_disclosed": True,
        "native_result_ceiling_value": None,
        "new_filing_retention": "five_court_days",
        "new_filings_url": NEW_FILINGS_LANDING_URL,
        "access_records_url": ACCESS_RECORDS_URL,
    },
)


class SanDiegoCourtError(RuntimeError):
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


class SanDiegoSelectionError(SanDiegoCourtError):
    """A selector does not match a verified native source operation."""

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


class SanDiegoSourceChangedError(SanDiegoCourtError):
    """The official page no longer matches the verified source contract."""

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
class IndexRow:
    case_number: str
    case_location: str | None
    case_type: str | None
    filing_date: str | None
    filing_date_raw: str | None
    detail_url: str
    matched_party: str | None = None
    opposing_party: str | None = None
    plaintiff_petitioner: str | None = None
    defendant_respondent_party: str | None = None
    source_url: str = INDEX_HOME_URL
    raw: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_number": self.case_number,
            "case_location": self.case_location,
            "case_type": self.case_type,
            "filing_date": self.filing_date,
            "filing_date_raw": self.filing_date_raw,
            "detail_url": self.detail_url,
            "matched_party": self.matched_party,
            "opposing_party": self.opposing_party,
            "plaintiff_petitioner": self.plaintiff_petitioner,
            "defendant_respondent_party": self.defendant_respondent_party,
            "source_url": self.source_url,
            "raw": dict(self.raw or {}),
        }


@dataclass(frozen=True)
class IndexPage:
    rows: tuple[IndexRow, ...]
    current_page: int
    total_pages: int
    page_urls: tuple[str, ...]
    authoritative_empty: bool
    schema_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class IndexSearchResult:
    rows: tuple[IndexRow, ...]
    native_rows_observed: int
    pages_fetched: int
    native_pages_discovered: int
    native_pages_exhausted: bool
    max_rows_on_page: int
    caller_limit: int | None
    caller_offset: int
    schema_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class CaseParty:
    section: str
    last_or_business_name: str
    first_name: str | None
    primary_marker: str | None

    @property
    def display_name(self) -> str:
        if self.first_name:
            return f"{self.last_or_business_name}, {self.first_name}"
        return self.last_or_business_name

    def to_dict(self) -> dict[str, Any]:
        return {
            "section": self.section,
            "last_or_business_name": self.last_or_business_name,
            "first_name": self.first_name,
            "primary_marker": self.primary_marker,
            "display_name": self.display_name,
        }


@dataclass(frozen=True)
class CaseDetail:
    case_number: str
    case_title: str | None
    case_location: str | None
    case_type: str | None
    filing_date: str | None
    filing_date_raw: str | None
    category_code: str | None
    category_label: str | None
    parties: tuple[CaseParty, ...]
    image_status: str | None
    file_location_available: bool
    microfilm: tuple[Mapping[str, Any], ...]
    microfilm_status: str | None
    schema_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class NewFilingParty:
    name: str
    party_type: str | None
    case_number: str
    source_url: str


@dataclass(frozen=True)
class NewFilingCase:
    case_number: str
    filing_date: str | None
    filing_date_raw: str | None
    category: str | None
    location: str | None
    source_url: str


@dataclass(frozen=True)
class NewFilingsPage:
    case_type: str
    partition: str
    last_updated: str | None
    parties: tuple[NewFilingParty, ...]
    cases: tuple[NewFilingCase, ...]
    partition_urls: tuple[str, ...]
    authoritative_empty: bool
    schema_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class NewFilingsResult:
    pages: tuple[NewFilingsPage, ...]
    pages_discovered: int
    pages_fetched: int
    native_partitions_exhausted: bool
    caller_limit: int | None
    caller_offset: int
    schema_fingerprint: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise SanDiegoSourceChangedError(
            "required_field_missing",
            f"San Diego court result lacks {field_name}",
            details={"field": field_name},
        )
    return normalized


def _iso_date(value: Any) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    for date_format in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, date_format).date().isoformat()
        except ValueError:
            continue
    raise SanDiegoSourceChangedError(
        "filing_date_format_changed",
        f"San Diego court returned an unrecognized filing date: {normalized}",
        details={"value": normalized},
    )


def _header_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", (_text(value) or "").casefold())


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


def _challenge_present(html: str) -> bool:
    lowered = html.casefold()
    return (
        "performing security verification" in lowered
        or "enable javascript and cookies to continue" in lowered
        or "<title>just a moment...</title>" in lowered
    )


def _table_with_headers(
    soup: BeautifulSoup,
    required_headers: set[str],
) -> tuple[Tag, Tag, list[str]] | None:
    for table in soup.find_all("table"):
        if not isinstance(table, Tag):
            continue
        for row in table.find_all("tr"):
            if not isinstance(row, Tag):
                continue
            cells = row.find_all(["th", "td"], recursive=False)
            headers = [_header_key(cell.get_text(" ", strip=True)) for cell in cells]
            if required_headers.issubset(headers):
                return table, row, headers
    return None


def _rows_after_document_header(
    soup: BeautifulSoup,
    required_headers: set[str],
) -> tuple[list[str], list[Tag]] | None:
    """Return document-order rows after a legacy table header.

    The new-filings HTML omits several closing ``table`` tags, so parsers may
    nest the second logical table inside the first.  Document-order ``tr``
    traversal preserves the two native row groups without relying on repaired
    table ancestry.
    """

    rows = [
        row for row in soup.find_all("tr") if isinstance(row, Tag)
    ]
    for header_index, row in enumerate(rows):
        cells = row.find_all(["th", "td"], recursive=False)
        headers = [_header_key(cell.get_text(" ", strip=True)) for cell in cells]
        if not required_headers.issubset(headers):
            continue
        data_rows: list[Tag] = []
        for candidate in rows[header_index + 1 :]:
            candidate_cells = candidate.find_all(
                ["th", "td"],
                recursive=False,
            )
            if not candidate_cells:
                continue
            if any(cell.name == "th" for cell in candidate_cells):
                break
            candidate_headers = {
                _header_key(cell.get_text(" ", strip=True))
                for cell in candidate_cells
            }
            if (
                {"name", "partytype", "casenumber"}.issubset(
                    candidate_headers
                )
                or {
                    "casenumber",
                    "filedate",
                    "category",
                    "location",
                }.issubset(candidate_headers)
            ):
                break
            data_rows.append(candidate)
        return headers, data_rows
    return None


def _result_page_links(
    soup: BeautifulSoup,
    *,
    source_url: str,
    result_path: str,
) -> tuple[str, ...]:
    page_urls: dict[int, str] = {}
    for link in soup.find_all("a", href=True):
        if not isinstance(link, Tag):
            continue
        target = urljoin(source_url, str(link.get("href")))
        parsed = urlparse(target)
        if parsed.path != result_path or not _same_origin(INDEX_HOME_URL, target):
            continue
        values = parse_qs(parsed.query).get("page")
        if not values or not values[0].isdigit():
            continue
        page_urls[int(values[0])] = target
    return tuple(page_urls[number] for number in sorted(page_urls))


_INDEX_HEADER_ALIASES = {
    "casenumber": "case_number",
    "casenumbermatches": "case_number",
    "partynamematches": "matched_party",
    "opposingparty": "opposing_party",
    "caselocation": "case_location",
    "casetype": "case_type",
    "datefiled": "filing_date",
    "plaintiffpetitioner": "plaintiff_petitioner",
    "defendantrespondentpartyname": "defendant_respondent_party",
}


def parse_index_results_page(
    html: str,
    *,
    source_url: str,
    search_kind: str,
) -> IndexPage:
    """Parse one party-name or case-number result page."""

    if _challenge_present(html):
        raise SanDiegoCourtError(
            "human_verification_required",
            "San Diego Court Index presented a browser verification challenge",
            status=ResultStatus.HUMAN_REQUIRED,
            category="access",
        )
    if search_kind not in {"party", "case"}:
        raise ValueError("search_kind must be party or case")
    soup = BeautifulSoup(html, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True)) or ""
    no_results = bool(
        re.search(
            r"\b(?:no\s+(?:matching\s+)?(?:case|record|selection)s?"
            r"(?:\s+were)?\s+found|your\s+search\s+returned\s+no)",
            page_text,
            flags=re.IGNORECASE,
        )
    )
    expected = (
        {"casenumber", "partynamematches", "datefiled"}
        if search_kind == "party"
        else {"casenumbermatches", "datefiled", "plaintiffpetitioner"}
    )
    located = _table_with_headers(soup, expected)
    result_path = (
        "/CISPublic/viewname" if search_kind == "party" else "/CISPublic/viewcase"
    )
    page_urls = _result_page_links(
        soup,
        source_url=source_url,
        result_path=result_path,
    )
    current_match = re.search(
        r"Search\s+Result\s+Page:\s*(\d+)",
        page_text,
        flags=re.IGNORECASE,
    )
    current_page = (
        int(current_match.group(1))
        if current_match
        else int(parse_qs(urlparse(source_url).query).get("page", ["1"])[0])
    )
    page_numbers = [
        int(parse_qs(urlparse(url).query)["page"][0]) for url in page_urls
    ]
    total_pages = max([current_page, *page_numbers])
    if located is None:
        if no_results:
            return IndexPage(
                rows=(),
                current_page=current_page,
                total_pages=total_pages,
                page_urls=page_urls,
                authoritative_empty=True,
                schema_fingerprint=schema_fingerprint({"headers": []}),
                source_url=source_url,
            )
        raise SanDiegoSourceChangedError(
            "result_table_missing",
            "San Diego Court Index result table was not found",
            details={"search_kind": search_kind},
        )

    table, header_row, headers = located
    canonical_headers = [
        _INDEX_HEADER_ALIASES.get(header, header or f"column_{index}")
        for index, header in enumerate(headers)
    ]
    rows: list[IndexRow] = []
    for row_tag in table.find_all("tr"):
        if not isinstance(row_tag, Tag) or row_tag is header_row:
            continue
        cells = row_tag.find_all("td", recursive=False)
        if not cells:
            continue
        values: dict[str, str | None] = {}
        raw_values: dict[str, str | None] = {}
        for index, header in enumerate(canonical_headers):
            cell = cells[index] if index < len(cells) else None
            value = (
                _text(cell.get_text(" ", strip=True))
                if isinstance(cell, Tag)
                else None
            )
            values[header] = value
            raw_values[headers[index]] = value
        case_index = canonical_headers.index("case_number")
        case_link = cells[case_index].find("a", href=True)
        if not isinstance(case_link, Tag):
            raise SanDiegoSourceChangedError(
                "case_detail_link_missing",
                "San Diego Court Index row lacks its case-detail link",
            )
        detail_url = urljoin(source_url, str(case_link.get("href")))
        if (
            not _same_origin(INDEX_HOME_URL, detail_url)
            or urlparse(detail_url).path != CASE_DETAIL_PATH
        ):
            raise SanDiegoSourceChangedError(
                "case_detail_link_changed",
                "San Diego Court Index returned an unexpected case-detail URL",
                details={"detail_url": detail_url},
            )
        filing_date_raw = _text(values.get("filing_date"))
        rows.append(
            IndexRow(
                case_number=_required_text(
                    values.get("case_number"),
                    "case number",
                ),
                case_location=_text(values.get("case_location")),
                case_type=_text(values.get("case_type")),
                filing_date=_iso_date(filing_date_raw),
                filing_date_raw=filing_date_raw,
                detail_url=detail_url,
                matched_party=_text(values.get("matched_party")),
                opposing_party=_text(values.get("opposing_party")),
                plaintiff_petitioner=_text(values.get("plaintiff_petitioner")),
                defendant_respondent_party=_text(
                    values.get("defendant_respondent_party")
                ),
                source_url=source_url,
                raw=raw_values,
            )
        )
    if not rows and not no_results:
        raise SanDiegoSourceChangedError(
            "result_rows_missing",
            "San Diego Court Index table contains no parseable rows",
        )
    row_schema = inferred_schema([row.to_dict() for row in rows])
    return IndexPage(
        rows=tuple(rows),
        current_page=current_page,
        total_pages=total_pages,
        page_urls=page_urls,
        authoritative_empty=not rows and no_results,
        schema_fingerprint=schema_fingerprint(row_schema),
        source_url=source_url,
    )


def _labeled_value(soup: BeautifulSoup, label: str) -> str | None:
    target = _header_key(label)
    for cell in soup.find_all(["td", "th"]):
        if not isinstance(cell, Tag):
            continue
        if _header_key(cell.get_text(" ", strip=True)) != target:
            continue
        sibling = cell.find_next_sibling(["td", "th"])
        if isinstance(sibling, Tag):
            return _text(sibling.get_text(" ", strip=True))
    return None


def parse_case_detail(
    html: str,
    *,
    source_url: str,
) -> CaseDetail:
    """Parse a Court Index case-detail page."""

    if _challenge_present(html):
        raise SanDiegoCourtError(
            "human_verification_required",
            "San Diego Court Index presented a browser verification challenge",
            status=ResultStatus.HUMAN_REQUIRED,
            category="access",
        )
    soup = BeautifulSoup(html, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True)) or ""
    if "View Case Detail" not in page_text:
        raise SanDiegoSourceChangedError(
            "case_detail_marker_missing",
            "San Diego case-detail page lacks its expected heading",
        )
    case_number = _required_text(
        _labeled_value(soup, "Case Number"),
        "case number",
    )
    filing_date_raw = _labeled_value(soup, "Date Filed")
    category_code: str | None = None
    category_label: str | None = None
    for row in soup.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        cells = row.find_all(["td", "th"], recursive=False)
        if cells and _header_key(cells[0].get_text(" ", strip=True)) == "category":
            category_code = (
                _text(cells[1].get_text(" ", strip=True))
                if len(cells) > 1
                else None
            )
            category_label = (
                _text(cells[2].get_text(" ", strip=True))
                if len(cells) > 2
                else None
            )
            break

    parties: list[CaseParty] = []
    for table in soup.find_all("table"):
        if not isinstance(table, Tag):
            continue
        table_text = _text(table.get_text(" ", strip=True)) or ""
        section: str | None = None
        if table_text.startswith("Plaintiff/Petitioner"):
            section = "plaintiff_petitioner"
        elif table_text.startswith("Defendant/Respondent"):
            section = "defendant_respondent"
        if section is None or "No party was found." in table_text:
            continue
        rows = table.find_all("tr")
        header_index: int | None = None
        for index, row in enumerate(rows):
            headers = [
                _header_key(cell.get_text(" ", strip=True))
                for cell in row.find_all(["td", "th"], recursive=False)
            ]
            if "lastnameorbusinessname" in headers and "firstname" in headers:
                header_index = index
                break
        if header_index is None:
            continue
        for row in rows[header_index + 1 :]:
            cells = row.find_all("td", recursive=False)
            if not cells:
                continue
            last_or_business = _text(cells[0].get_text(" ", strip=True))
            if last_or_business is None:
                continue
            parties.append(
                CaseParty(
                    section=section,
                    last_or_business_name=last_or_business,
                    first_name=(
                        _text(cells[1].get_text(" ", strip=True))
                        if len(cells) > 1
                        else None
                    ),
                    primary_marker=(
                        _text(cells[2].get_text(" ", strip=True))
                        if len(cells) > 2
                        else None
                    ),
                )
            )

    image_status: str | None = None
    microfilm_status: str | None = None
    microfilm: list[Mapping[str, Any]] = []
    for table in soup.find_all("table"):
        if not isinstance(table, Tag):
            continue
        table_text = _text(table.get_text(" ", strip=True)) or ""
        if table_text.startswith("Imaged Case"):
            image_status = _text(
                re.sub(r"^Imaged Case\s*", "", table_text, flags=re.IGNORECASE)
            )
        if not table_text.startswith("Microfilm"):
            continue
        if "not been microfilmed" in table_text.casefold():
            microfilm_status = _text(
                re.sub(r"^Microfilm\s*", "", table_text, flags=re.IGNORECASE)
            )
            continue
        header_row: Tag | None = None
        headers: list[str] = []
        for candidate in table.find_all("tr"):
            candidate_headers = [
                _header_key(cell.get_text(" ", strip=True))
                for cell in candidate.find_all(
                    ["td", "th"],
                    recursive=False,
                )
            ]
            if {
                "microfilmid",
                "location",
                "reelnumber",
                "framenumber",
            }.issubset(candidate_headers):
                header_row = candidate
                headers = candidate_headers
                break
        if header_row is None:
            continue
        for row in table.find_all("tr"):
            if row is header_row:
                continue
            cells = row.find_all("td", recursive=False)
            if len(cells) < len(headers):
                continue
            values = {
                headers[index]: _text(cells[index].get_text(" ", strip=True))
                for index in range(len(headers))
            }
            if values.get("microfilmid"):
                microfilm.append(values)

    parsed = {
        "case_number": case_number,
        "case_title": _labeled_value(soup, "Case Title"),
        "case_location": _labeled_value(soup, "Case Location"),
        "case_type": _labeled_value(soup, "Case Type"),
        "filing_date": _iso_date(filing_date_raw),
        "category_code": category_code,
        "category_label": category_label,
        "parties": [party.to_dict() for party in parties],
        "image_status": image_status,
        "microfilm": microfilm,
    }
    return CaseDetail(
        case_number=case_number,
        case_title=parsed["case_title"],
        case_location=parsed["case_location"],
        case_type=parsed["case_type"],
        filing_date=parsed["filing_date"],
        filing_date_raw=filing_date_raw,
        category_code=category_code,
        category_label=category_label,
        parties=tuple(parties),
        image_status=image_status,
        file_location_available=soup.find(
            ["button", "input"],
            string=re.compile(r"File Location", re.I),
        )
        is not None
        or soup.find(
            "input",
            attrs={"value": re.compile(r"File Location", re.I)},
        )
        is not None,
        microfilm=tuple(microfilm),
        microfilm_status=microfilm_status,
        schema_fingerprint=schema_fingerprint(inferred_schema([parsed])),
        source_url=source_url,
    )


def _new_filing_partition(value: str) -> str:
    stem = Path(urlparse(value).path).stem
    return stem.rsplit("_", 1)[-1].casefold()


def _new_filing_case_type(value: str) -> str | None:
    stem = Path(urlparse(value).path).stem
    match = re.match(r"nf_([a-z]{2})_", stem, flags=re.IGNORECASE)
    if match is None:
        return None
    code = match.group(1).casefold()
    return next(
        (
            name
            for name, candidate in NEW_FILING_TYPE_CODES.items()
            if candidate == code
        ),
        None,
    )


def parse_new_filings_landing(
    html: str,
    *,
    source_url: str = NEW_FILINGS_LANDING_URL,
) -> Mapping[str, str]:
    """Parse the official links to each new-filing case-type list."""

    soup = BeautifulSoup(html, "html.parser")
    routes: dict[str, str] = {}
    for link in soup.find_all("a", href=True):
        if not isinstance(link, Tag):
            continue
        target = urljoin(source_url, str(link.get("href")))
        case_type = _new_filing_case_type(target)
        if (
            case_type is None
            or not _same_origin(NEW_FILINGS_LANDING_URL, target)
        ):
            continue
        routes[case_type] = target
    missing = sorted(set(NEW_FILING_TYPE_CODES) - set(routes))
    if missing:
        raise SanDiegoSourceChangedError(
            "new_filing_routes_missing",
            "San Diego new-filings landing page lacks native case-type routes",
            details={"missing_case_types": missing},
        )
    return routes


def parse_new_filings_page(
    html: str,
    *,
    source_url: str,
    case_type: str | None = None,
) -> NewFilingsPage:
    """Parse one native alphabet partition of a new-filing list."""

    soup = BeautifulSoup(html, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True)) or ""
    detected_type = _new_filing_case_type(source_url)
    resolved_type = case_type or detected_type
    if resolved_type not in NEW_FILING_TYPE_CODES:
        raise SanDiegoSourceChangedError(
            "new_filing_case_type_missing",
            "Could not identify the new-filing case type",
            details={"source_url": source_url},
        )
    if detected_type is not None and detected_type != resolved_type:
        raise SanDiegoSourceChangedError(
            "new_filing_case_type_changed",
            "New-filing URL does not match the selected case type",
            details={
                "source_url": source_url,
                "selected_case_type": resolved_type,
                "detected_case_type": detected_type,
            },
        )
    updated_match = re.search(
        r"Last\s+updated\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        page_text,
        flags=re.IGNORECASE,
    )
    last_updated = _text(updated_match.group(1)) if updated_match else None

    partition_urls: set[str] = set()
    expected_code = NEW_FILING_TYPE_CODES[resolved_type]
    expected_prefix = f"nf_{expected_code}_"
    for link in soup.find_all("a", href=True):
        if not isinstance(link, Tag):
            continue
        target = urljoin(source_url, str(link.get("href"))).split("#", 1)[0]
        stem = Path(urlparse(target).path).stem.casefold()
        if (
            stem.startswith(expected_prefix)
            and _same_origin(NEW_FILINGS_LANDING_URL, target)
        ):
            partition_urls.add(target)

    party_rows = _rows_after_document_header(
        soup,
        {"name", "partytype", "casenumber"},
    )
    case_rows = _rows_after_document_header(
        soup,
        {"casenumber", "filedate", "category", "location"},
    )
    parties: list[NewFilingParty] = []
    cases: list[NewFilingCase] = []
    if party_rows is not None:
        headers, rows = party_rows
        for row in rows:
            cells = row.find_all("td", recursive=False)
            if not cells:
                continue
            values = {
                headers[index]: (
                    _text(cells[index].get_text(" ", strip=True))
                    if index < len(cells)
                    else None
                )
                for index in range(len(headers))
            }
            case_number = _text(values.get("casenumber"))
            name = _text(values.get("name"))
            if case_number is None or name is None:
                continue
            parties.append(
                NewFilingParty(
                    name=name,
                    party_type=_text(values.get("partytype")),
                    case_number=case_number,
                    source_url=source_url,
                )
            )
    if case_rows is not None:
        headers, rows = case_rows
        for row in rows:
            cells = row.find_all("td", recursive=False)
            if not cells:
                continue
            values = {
                headers[index]: (
                    _text(cells[index].get_text(" ", strip=True))
                    if index < len(cells)
                    else None
                )
                for index in range(len(headers))
            }
            case_number = _text(values.get("casenumber"))
            if case_number is None:
                continue
            filing_date_raw = _text(values.get("filedate"))
            cases.append(
                NewFilingCase(
                    case_number=case_number,
                    filing_date=_iso_date(filing_date_raw),
                    filing_date_raw=filing_date_raw,
                    category=_text(values.get("category")),
                    location=_text(values.get("location")),
                    source_url=source_url,
                )
            )
    authoritative_empty = not parties and not cases and last_updated is not None
    if not parties and not cases and not authoritative_empty:
        raise SanDiegoSourceChangedError(
            "new_filing_tables_missing",
            "New-filing page lacks its expected party and case tables",
            details={"source_url": source_url},
        )
    parsed = {
        "case_type": resolved_type,
        "partition": _new_filing_partition(source_url),
        "last_updated": last_updated,
        "parties": [party.__dict__ for party in parties],
        "cases": [case.__dict__ for case in cases],
    }
    return NewFilingsPage(
        case_type=resolved_type,
        partition=_new_filing_partition(source_url),
        last_updated=last_updated,
        parties=tuple(parties),
        cases=tuple(cases),
        partition_urls=tuple(
            sorted(
                partition_urls,
                key=lambda value: (_new_filing_partition(value), value),
            )
        ),
        authoritative_empty=authoritative_empty,
        schema_fingerprint=schema_fingerprint(inferred_schema([parsed])),
        source_url=source_url,
    )


def _run_browser_helper(
    selection: Mapping[str, Any],
    *,
    timeout: float,
    minimum_interval: float,
    max_attempts: int,
) -> Mapping[str, Any]:
    node = shutil.which("node")
    if node is None:
        raise SanDiegoCourtError(
            "browser_runtime_missing",
            "Node.js is required for the San Diego Court Index browser transport",
            category="runtime",
        )
    if not BROWSER_HELPER_PATH.is_file():
        raise SanDiegoCourtError(
            "browser_helper_missing",
            f"San Diego browser helper not found: {BROWSER_HELPER_PATH}",
            category="runtime",
        )
    command = [
        node,
        str(BROWSER_HELPER_PATH),
        canonical_json(selection),
        str(timeout),
        str(minimum_interval),
        str(max_attempts),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise SanDiegoCourtError(
            "browser_helper_timeout",
            "San Diego Court Index browser acquisition did not complete",
            category="transport",
            retryable=True,
            details={
                "execution_timeout_seconds": 900,
                "collection_bound": False,
            },
        ) from error
    except OSError as error:
        raise SanDiegoCourtError(
            "browser_helper_failed",
            f"Could not start the San Diego browser helper: {error}",
            category="runtime",
        ) from error
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise SanDiegoCourtError(
            "browser_helper_invalid",
            "San Diego browser helper did not return JSON",
            category="runtime",
            details={
                "return_code": completed.returncode,
                "stderr": completed.stderr[-1000:],
            },
        ) from error
    if not isinstance(payload, Mapping):
        raise SanDiegoCourtError(
            "browser_helper_invalid",
            "San Diego browser helper returned a non-object payload",
            category="runtime",
        )
    if payload.get("ok") is not True:
        error_payload = payload.get("error")
        details = (
            dict(error_payload)
            if isinstance(error_payload, Mapping)
            else {}
        )
        status_value = details.pop("status", ResultStatus.UNAVAILABLE.value)
        try:
            status = ResultStatus(str(status_value))
        except ValueError:
            status = ResultStatus.UNAVAILABLE
        raise SanDiegoCourtError(
            str(details.pop("code", "browser_helper_failed")),
            str(
                details.pop(
                    "message",
                    "San Diego Court Index browser acquisition failed",
                )
            ),
            status=status,
            category=str(details.pop("category", "transport")),
            retryable=bool(details.pop("retryable", False)),
            details=details,
        )
    return payload


class SanDiegoCourtIndexClient:
    """Browser-backed client for the official Court Index."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: RetryPolicy | None = None,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        browser_runner: Any | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.minimum_interval = minimum_interval
        self._browser_runner = browser_runner or _run_browser_helper

    def close(self) -> None:
        return None

    def _run(self, selection: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._browser_runner(
            selection,
            timeout=self.timeout,
            minimum_interval=self.minimum_interval,
            max_attempts=self.retry_policy.max_attempts,
        )

    @staticmethod
    def _search_result(
        payload: Mapping[str, Any],
        *,
        search_kind: str,
        limit: int | None,
        offset: int,
    ) -> IndexSearchResult:
        raw_pages = payload.get("pages")
        if not isinstance(raw_pages, list):
            raise SanDiegoSourceChangedError(
                "browser_pages_missing",
                "San Diego browser result lacks its page array",
            )
        pages_by_number: dict[int, IndexPage] = {}
        for raw_page in raw_pages:
            if not isinstance(raw_page, Mapping):
                raise SanDiegoSourceChangedError(
                    "browser_page_invalid",
                    "San Diego browser result contains a non-object page",
                )
            html = raw_page.get("html")
            source_url = _text(raw_page.get("url"))
            if not isinstance(html, str) or source_url is None:
                raise SanDiegoSourceChangedError(
                    "browser_page_invalid",
                    "San Diego browser page lacks HTML or source URL",
                )
            parsed_page = parse_index_results_page(
                html,
                source_url=source_url,
                search_kind=search_kind,
            )
            previous = pages_by_number.get(parsed_page.current_page)
            if (
                previous is not None
                and previous.schema_fingerprint
                != parsed_page.schema_fingerprint
            ):
                raise SanDiegoSourceChangedError(
                    "duplicate_page_changed",
                    "San Diego returned conflicting content for one result page",
                    details={"page": parsed_page.current_page},
                )
            pages_by_number[parsed_page.current_page] = parsed_page
        pages = list(pages_by_number.values())
        if not pages:
            raise SanDiegoSourceChangedError(
                "browser_pages_empty",
                "San Diego browser returned no result pages",
            )
        pages.sort(key=lambda page: page.current_page)
        collected = [row for page in pages for row in page.rows]
        selected = (
            collected[offset:]
            if limit is None
            else collected[offset : offset + limit]
        )
        native_pages_discovered = max(
            page.total_pages for page in pages
        )
        expected_page_numbers = set(
            range(1, native_pages_discovered + 1)
        )
        page_fingerprints = sorted(
            {page.schema_fingerprint for page in pages}
        )
        return IndexSearchResult(
            rows=tuple(selected),
            native_rows_observed=len(collected),
            pages_fetched=len(pages),
            native_pages_discovered=native_pages_discovered,
            native_pages_exhausted=(
                set(pages_by_number) == expected_page_numbers
            ),
            max_rows_on_page=max(len(page.rows) for page in pages),
            caller_limit=limit,
            caller_offset=offset,
            schema_fingerprint=schema_fingerprint(
                {
                    "transport": "headed_chromium",
                    "result_pages": page_fingerprints,
                }
            ),
            source_url=pages[-1].source_url,
        )

    def party_search(
        self,
        selection: Mapping[str, Any],
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> IndexSearchResult:
        payload = self._run({"operation": "party_search", **selection})
        return self._search_result(
            payload,
            search_kind="party",
            limit=limit,
            offset=offset,
        )

    def case_search(
        self,
        selection: Mapping[str, Any],
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> IndexSearchResult:
        payload = self._run({"operation": "case_search", **selection})
        return self._search_result(
            payload,
            search_kind="case",
            limit=limit,
            offset=offset,
        )

    def case_detail(self, detail_url: str) -> CaseDetail:
        payload = self._run(
            {"operation": "case_detail", "detail_url": detail_url}
        )
        html = payload.get("html")
        source_url = _text(payload.get("url"))
        if not isinstance(html, str) or source_url is None:
            raise SanDiegoSourceChangedError(
                "browser_detail_missing",
                "San Diego browser result lacks case-detail HTML",
            )
        return parse_case_detail(html, source_url=source_url)

    def probe(self) -> tuple[IndexSearchResult, IndexSearchResult, CaseDetail]:
        payload = self._run(
            {
                "operation": "probe",
                "case_type": "C",
                "site": "A",
                "party_type": "A",
                "begin_year": 1974,
                "end_year": date.today().year,
                "last_name": "Epstein",
                "first_name": "Jeffrey",
                "case_number": PROBE_CASE_NUMBER,
                "detail_url": PROBE_DETAIL_URL,
            }
        )
        party_payload = payload.get("party_search")
        case_payload = payload.get("case_search")
        detail_payload = payload.get("case_detail")
        if not all(
            isinstance(value, Mapping)
            for value in (party_payload, case_payload, detail_payload)
        ):
            raise SanDiegoSourceChangedError(
                "probe_payload_changed",
                "San Diego browser probe lacks one or more operation payloads",
            )
        party_result = self._search_result(
            party_payload,
            search_kind="party",
            limit=None,
            offset=0,
        )
        case_result = self._search_result(
            case_payload,
            search_kind="case",
            limit=None,
            offset=0,
        )
        detail_html = detail_payload.get("html")
        detail_url = _text(detail_payload.get("url"))
        if not isinstance(detail_html, str) or detail_url is None:
            raise SanDiegoSourceChangedError(
                "probe_detail_changed",
                "San Diego probe lacks case-detail HTML",
            )
        return (
            party_result,
            case_result,
            parse_case_detail(detail_html, source_url=detail_url),
        )


def _retry_after_seconds(value: Any) -> float | None:
    normalized = _text(value)
    if normalized is None:
        return None
    try:
        return max(0.0, float(normalized))
    except ValueError:
        return None


class NewFilingsClient:
    """HTTP client for the court's static five-court-day filing lists."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: RetryPolicy | None = None,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        sleeper: Any = time.sleep,
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

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def _get(self, url: str) -> Any:
        if not _same_origin(NEW_FILINGS_LANDING_URL, url):
            raise SanDiegoSourceChangedError(
                "new_filing_origin_changed",
                "New-filing link points outside the official host",
                details={"url": url},
            )
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": self.user_agent,
        }
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt))
                    continue
                raise SanDiegoCourtError(
                    "transport_error",
                    f"San Diego new-filings request failed: {error}",
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
                            _retry_after_seconds(
                                response.headers.get("Retry-After")
                            ),
                        )
                    )
                    continue
                raise SanDiegoCourtError(
                    (
                        "rate_limited"
                        if status_code == 429
                        else "http_status_error"
                    ),
                    f"San Diego new-filings host returned HTTP {status_code}",
                    status=(
                        ResultStatus.RATE_LIMITED
                        if status_code == 429
                        else ResultStatus.UNAVAILABLE
                    ),
                    category=(
                        "rate_limit" if status_code == 429 else "transport"
                    ),
                    retryable=True,
                    details={"status_code": status_code, "url": url},
                )
            if status_code != 200:
                raise SanDiegoCourtError(
                    "http_status_error",
                    f"San Diego new-filings host returned HTTP {status_code}",
                    category="transport",
                    details={"status_code": status_code, "url": url},
                )
            return response
        raise AssertionError("retry loop did not return or raise")

    def landing(self) -> Mapping[str, str]:
        response = self._get(NEW_FILINGS_LANDING_URL)
        response_url = _text(getattr(response, "url", None))
        return parse_new_filings_landing(
            response.text,
            source_url=response_url or NEW_FILINGS_LANDING_URL,
        )

    def collect(
        self,
        case_types: Sequence[str],
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> NewFilingsResult:
        routes = self.landing()
        selected_types = tuple(dict.fromkeys(case_types))
        unknown = sorted(set(selected_types) - set(routes))
        if unknown:
            raise SanDiegoSelectionError(
                "new_filing_case_type_unknown",
                "Unknown San Diego new-filing case type",
                details={"case_types": unknown},
            )
        queue: list[tuple[str, str]] = [
            (case_type, routes[case_type]) for case_type in selected_types
        ]
        queued = {url for _, url in queue}
        seen: set[str] = set()
        pages: list[NewFilingsPage] = []
        while queue:
            case_type, url = queue.pop(0)
            if url in seen:
                continue
            response = self._get(url)
            response_url = _text(getattr(response, "url", None)) or url
            page = parse_new_filings_page(
                response.text,
                source_url=response_url,
                case_type=case_type,
            )
            seen.add(url)
            pages.append(page)
            for partition_url in page.partition_urls:
                if partition_url not in queued:
                    queued.add(partition_url)
                    queue.append((case_type, partition_url))
        pages.sort(
            key=lambda page: (
                list(NEW_FILING_TYPE_CODES).index(page.case_type),
                page.partition,
                page.source_url,
            )
        )
        return NewFilingsResult(
            pages=tuple(pages),
            pages_discovered=len(queued),
            pages_fetched=len(pages),
            native_partitions_exhausted=seen == queued,
            caller_limit=limit,
            caller_offset=offset,
            schema_fingerprint=schema_fingerprint(
                {
                    "landing_case_types": sorted(routes),
                    "pages": sorted(
                        {page.schema_fingerprint for page in pages}
                    ),
                }
            ),
        )

    def probe(self) -> Mapping[str, NewFilingsPage]:
        routes = self.landing()
        pages: dict[str, NewFilingsPage] = {}
        for case_type in NEW_FILING_TYPE_CODES:
            url = routes[case_type]
            response = self._get(url)
            pages[case_type] = parse_new_filings_page(
                response.text,
                source_url=_text(getattr(response, "url", None)) or url,
                case_type=case_type,
            )
        return pages


def _court_payload() -> dict[str, Any]:
    return {
        "court_id": COURT_ID,
        "native_court_id": "san-diego-superior-court",
        "name": COURT_NAME,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "court_level": "county_superior",
        "official_url": COURT_OFFICIAL_URL,
    }


def _source_scope(record_type: str) -> dict[str, Any]:
    if record_type == "case_detail":
        return {
            "record_type": "case_detail_index_metadata",
            "fields": [
                "case_title",
                "case_number",
                "case_location",
                "case_type",
                "filing_date",
                "category",
                "parties",
                "image_status",
                "microfilm",
            ],
            "charges_available": False,
            "disposition_available": False,
            "docket_available": False,
            "documents_available": False,
            "official_record": False,
            "register_of_actions_url": ODYSSEY_ROA_URL,
        }
    if record_type == "new_filing":
        return {
            "record_type": "five_court_day_new_filing_list",
            "fields": [
                "case_number",
                "filing_date",
                "case_type",
                "category",
                "location",
                "parties",
            ],
            "retention_window": "five_court_days",
            "historical_archive_available": False,
            "official_record": False,
        }
    return {
        "record_type": "case_party_index",
        "fields": [
            "case_number",
            "party_match_or_named_side",
            "opposing_party_or_named_side",
            "case_location",
            "case_type",
            "filing_date",
            "case_detail_url",
        ],
        "charges_available": False,
        "disposition_available": False,
        "docket_available": False,
        "documents_available": False,
        "official_record": False,
    }


def _party_record(
    *,
    case_number: str,
    name: str,
    role: str,
    native_role: str | None,
    sequence_no: int,
    identity_context: Mapping[str, Any],
) -> dict[str, Any]:
    identity_basis = {
        "case_number": case_number.casefold(),
        "name": name.casefold(),
        "role": role,
        "native_role": native_role,
        **dict(identity_context),
    }
    digest = hashlib.sha256(
        canonical_json(identity_basis).encode("utf-8")
    ).hexdigest()
    return {
        "native_party_id": f"sd-court-party:{digest}",
        "sequence_no": sequence_no,
        "raw_name": name,
        "normalized_name": None,
        "role": role,
        "native_role": native_role,
        "access_state": "public",
        "identity_kind": "source_fields_sha256",
        "identity_basis": identity_basis,
    }


def normalize_index_records(
    result: IndexSearchResult,
    *,
    operation: str,
    selection: Mapping[str, Any],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[IndexRow]] = {}
    for row in result.rows:
        grouped.setdefault(row.case_number.casefold(), []).append(row)
    records: list[dict[str, Any]] = []
    for key in sorted(grouped):
        rows = grouped[key]
        case_number = sorted(
            {row.case_number for row in rows},
            key=lambda value: (value.casefold(), value),
        )[0]
        party_candidates: list[tuple[str, str, str | None, Mapping[str, Any]]] = []
        for row_index, row in enumerate(rows):
            if row.matched_party and row.matched_party != "N/A":
                party_candidates.append(
                    (
                        row.matched_party,
                        "matched_party",
                        None,
                        {"row_index": row_index, "side": "matched"},
                    )
                )
            if row.opposing_party and row.opposing_party != "N/A":
                party_candidates.append(
                    (
                        row.opposing_party,
                        "opposing_party",
                        None,
                        {"row_index": row_index, "side": "opposing"},
                    )
                )
            if row.plaintiff_petitioner and row.plaintiff_petitioner != "N/A":
                party_candidates.append(
                    (
                        row.plaintiff_petitioner,
                        "plaintiff_petitioner",
                        "Plaintiff/Petitioner",
                        {"row_index": row_index, "side": "plaintiff"},
                    )
                )
            if (
                row.defendant_respondent_party
                and row.defendant_respondent_party != "N/A"
            ):
                party_candidates.append(
                    (
                        row.defendant_respondent_party,
                        "defendant_respondent",
                        "Defendant/Respondent/Party Name",
                        {"row_index": row_index, "side": "defendant"},
                    )
                )
        parties = [
            _party_record(
                case_number=case_number,
                name=name,
                role=role,
                native_role=native_role,
                sequence_no=index,
                identity_context=context,
            )
            for index, (name, role, native_role, context) in enumerate(
                party_candidates
            )
        ]
        filing_dates = sorted(
            {row.filing_date for row in rows if row.filing_date}
        )
        locations = sorted(
            {row.case_location for row in rows if row.case_location}
        )
        case_types = sorted({row.case_type for row in rows if row.case_type})
        detail_urls = sorted({row.detail_url for row in rows})
        records.append(
            {
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    case_number,
                ),
                "source_id": SOURCE_ID,
                "record_kind": "case",
                "court": _court_payload(),
                "raw_case_number": case_number,
                "display_case_number": case_number,
                "source_internal_id": None,
                "caption": None,
                "case_type": case_types[0] if len(case_types) == 1 else None,
                "filing_date": (
                    filing_dates[0] if len(filing_dates) == 1 else None
                ),
                "filing_date_variants": filing_dates,
                "status": None,
                "access_state": "public",
                "certified_record": False,
                "source_url": rows[0].source_url,
                "case_location": (
                    locations[0] if len(locations) == 1 else None
                ),
                "case_location_variants": locations,
                "parties": parties,
                "docket_entries": [],
                "documents": [],
                "case_detail_urls": detail_urls,
                "source_scope": _source_scope("index"),
                "search_metadata": {
                    "operation": operation,
                    "selection": dict(selection),
                    "native_rows_observed": result.native_rows_observed,
                    "native_pages_discovered": result.native_pages_discovered,
                    "pages_fetched": result.pages_fetched,
                    "native_pages_exhausted": result.native_pages_exhausted,
                    "max_rows_on_page": result.max_rows_on_page,
                    "caller_limit": result.caller_limit,
                    "caller_offset": result.caller_offset,
                    "caller_limit_applied_after_native_page_collection": True,
                    "server_result_ceiling_disclosed": True,
                    "server_result_ceiling_value": None,
                    "server_result_ceiling_reached": None,
                    "transport_batching": (
                        "one rendered native result page per browser navigation"
                    ),
                    "bounded_probe": False,
                },
                "schema_fingerprint": result.schema_fingerprint,
                "raw": {"index_rows": [row.to_dict() for row in rows]},
            }
        )
    return records


def normalize_case_detail(detail: CaseDetail) -> dict[str, Any]:
    parties = [
        _party_record(
            case_number=detail.case_number,
            name=party.display_name,
            role=party.section,
            native_role=party.section,
            sequence_no=index,
            identity_context={
                "primary_marker": party.primary_marker,
                "last_or_business_name": party.last_or_business_name,
                "first_name": party.first_name,
            },
        )
        for index, party in enumerate(detail.parties)
    ]
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            detail.case_number,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "court": _court_payload(),
        "raw_case_number": detail.case_number,
        "display_case_number": detail.case_number,
        "source_internal_id": None,
        "caption": detail.case_title,
        "case_type": detail.case_type,
        "filing_date": detail.filing_date,
        "status": None,
        "access_state": "public",
        "certified_record": False,
        "source_url": detail.source_url,
        "case_location": detail.case_location,
        "category_code": detail.category_code,
        "category": detail.category_label,
        "parties": parties,
        "docket_entries": [],
        "documents": [],
        "image_status": detail.image_status,
        "file_location_available": detail.file_location_available,
        "microfilm": [dict(item) for item in detail.microfilm],
        "microfilm_status": detail.microfilm_status,
        "source_scope": _source_scope("case_detail"),
        "schema_fingerprint": detail.schema_fingerprint,
        "raw": {
            "parties": [party.to_dict() for party in detail.parties],
            "filing_date_raw": detail.filing_date_raw,
        },
    }


def normalize_new_filings(
    result: NewFilingsResult,
) -> list[dict[str, Any]]:
    case_rows: dict[str, list[NewFilingCase]] = {}
    party_rows: dict[str, list[NewFilingParty]] = {}
    case_types: dict[str, set[str]] = {}
    last_updated: dict[str, set[str]] = {}
    for page in result.pages:
        for case in page.cases:
            key = case.case_number.casefold()
            case_rows.setdefault(key, []).append(case)
            case_types.setdefault(key, set()).add(page.case_type)
            if page.last_updated:
                last_updated.setdefault(key, set()).add(page.last_updated)
        for party in page.parties:
            key = party.case_number.casefold()
            party_rows.setdefault(key, []).append(party)
            case_types.setdefault(key, set()).add(page.case_type)
            if page.last_updated:
                last_updated.setdefault(key, set()).add(page.last_updated)
    keys = sorted(set(case_rows) | set(party_rows))
    selected_keys = (
        keys[result.caller_offset :]
        if result.caller_limit is None
        else keys[
            result.caller_offset : result.caller_offset + result.caller_limit
        ]
    )
    records: list[dict[str, Any]] = []
    for key in selected_keys:
        cases = case_rows.get(key, [])
        parties_raw = party_rows.get(key, [])
        case_number = (
            cases[0].case_number
            if cases
            else parties_raw[0].case_number
        )
        parties = [
            _party_record(
                case_number=case_number,
                name=party.name,
                role="unknown",
                native_role=party.party_type,
                sequence_no=index,
                identity_context={
                    "source_url": party.source_url,
                    "row_index": index,
                },
            )
            for index, party in enumerate(parties_raw)
        ]
        filing_dates = sorted(
            {case.filing_date for case in cases if case.filing_date}
        )
        categories = sorted(
            {case.category for case in cases if case.category}
        )
        locations = sorted({case.location for case in cases if case.location})
        types = sorted(case_types.get(key, set()))
        source_urls = sorted(
            {
                *[case.source_url for case in cases],
                *[party.source_url for party in parties_raw],
            }
        )
        records.append(
            {
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    case_number,
                ),
                "source_id": SOURCE_ID,
                "record_kind": "case",
                "court": _court_payload(),
                "raw_case_number": case_number,
                "display_case_number": case_number,
                "source_internal_id": None,
                "caption": None,
                "case_type": types[0] if len(types) == 1 else None,
                "filing_date": (
                    filing_dates[0] if len(filing_dates) == 1 else None
                ),
                "filing_date_variants": filing_dates,
                "status": None,
                "access_state": "public",
                "certified_record": False,
                "source_url": source_urls[0],
                "source_urls": source_urls,
                "case_location": (
                    locations[0] if len(locations) == 1 else None
                ),
                "case_location_variants": locations,
                "category": (
                    categories[0] if len(categories) == 1 else None
                ),
                "category_variants": categories,
                "parties": parties,
                "docket_entries": [],
                "documents": [],
                "source_scope": _source_scope("new_filing"),
                "search_metadata": {
                    "last_updated_values": sorted(
                        last_updated.get(key, set())
                    ),
                    "native_partitions_discovered": result.pages_discovered,
                    "native_partitions_fetched": result.pages_fetched,
                    "native_partitions_exhausted": (
                        result.native_partitions_exhausted
                    ),
                    "caller_limit": result.caller_limit,
                    "caller_offset": result.caller_offset,
                    "caller_limit_applied_after_native_partition_collection": True,
                    "server_result_ceiling_disclosed": False,
                    "transport_batching": (
                        "one static native alphabet partition per HTTP request"
                    ),
                    "retention_window": "five_court_days",
                    "bounded_probe": False,
                },
                "schema_fingerprint": result.schema_fingerprint,
                "raw": {
                    "case_rows": [case.__dict__ for case in cases],
                    "party_rows": [party.__dict__ for party in parties_raw],
                },
            }
        )
    return records


def _alternatives() -> list[dict[str, Any]]:
    return [
        {
            "route_id": "court-index-da-number",
            "authority": COURT_NAME,
            "official": True,
            "url": DA_SEARCH_URL,
            "scope": "District Attorney case-number to Superior Court case index",
            "access_state": "anonymous_form_confirmed",
            "integration_state": "cataloged_not_yet_fixture_verified",
        },
        {
            "route_id": "family-register-of-actions",
            "authority": COURT_NAME,
            "official": True,
            "url": FAMILY_ROA_URL,
            "scope": (
                "Family Law register of actions; some documents may be "
                "purchased online and mailed"
            ),
            "access_state": "http_403_observed_2026-07-30",
            "integration_state": "alternative_route",
        },
        {
            "route_id": "odyssey-register-of-actions",
            "authority": COURT_NAME,
            "official": True,
            "url": ODYSSEY_ROA_URL,
            "scope": (
                "Civil, Small Claims, Probate, and Criminal registers of "
                "actions; most noncriminal documents have first-page previews "
                "and paid downloads, while criminal copies are mailed"
            ),
            "access_state": "cloudflare_verification_observed_2026-07-30",
            "integration_state": "alternative_route",
        },
        {
            "route_id": "pre-1974-indexes",
            "authority": COURT_NAME,
            "official": True,
            "url": ACCESS_RECORDS_URL,
            "scope": (
                "Central Division Older Records indexes from 1880 to mid-1974; "
                "1880-1964 hardbound books and later computer-generated indexes"
            ),
            "access_state": "in_person",
            "integration_state": "research_route",
        },
        {
            "route_id": "official-file-inspection-and-copy",
            "authority": COURT_NAME,
            "official": True,
            "url": ACCESS_RECORDS_URL,
            "scope": (
                "Official case-file inspection, certified records, copies, "
                "and off-site retrieval through the responsible court location"
            ),
            "access_state": "in_person_or_written_request",
            "integration_state": "research_route",
        },
        {
            "route_id": "traffic-and-minor-offense-files",
            "authority": COURT_NAME,
            "official": True,
            "url": ACCESS_RECORDS_URL,
            "scope": (
                "Traffic, local ordinance, and infraction records omitted from "
                "the online index"
            ),
            "access_state": "court_facility_only",
            "integration_state": "research_route",
        },
        {
            "route_id": "five-day-court-calendar",
            "authority": COURT_NAME,
            "official": True,
            "url": CALENDAR_URL,
            "scope": "Court calendar complement",
            "access_state": "stale_2020_closure_page_observed_2026-07-30",
            "integration_state": "alternative_route_currently_degraded",
        },
        {
            "route_id": "fourth-district-division-one-appellate-case-search",
            "authority": "California Courts",
            "official": True,
            "url": APPELLATE_SEARCH_URL,
            "scope": (
                "Appellate case information for Fourth District, Division One; "
                "useful when a San Diego Superior Court matter is appealed"
            ),
            "access_state": "public_web_search",
            "integration_state": "credible_complement",
        },
        {
            "route_id": "commercial-state-court-aggregators",
            "authority": "Trellis / UniCourt / legal research services",
            "official": False,
            "url": None,
            "scope": (
                "Potential historical docket and document coverage when an "
                "official online route is challenged or no longer retains a list"
            ),
            "access_state": "commercial_login_or_subscription",
            "integration_state": "secondary_discovery_only_verify_officially",
        },
    ]


def _validated_detail_url(value: str) -> str:
    normalized = _required_text(value, "case-detail URL")
    parsed = urlparse(normalized)
    if (
        not _same_origin(INDEX_HOME_URL, normalized)
        or parsed.path != CASE_DETAIL_PATH
    ):
        raise SanDiegoSelectionError(
            "invalid_case_detail_url",
            "case-detail URL must be an official San Diego Court Index detail URL",
            details={"url": normalized},
        )
    query = parse_qs(parsed.query)
    missing = [
        field
        for field in ("casenum", "casesite", "applcode")
        if not query.get(field)
    ]
    if missing:
        raise SanDiegoSelectionError(
            "incomplete_case_detail_url",
            "case-detail URL lacks required native parameters",
            details={"missing_parameters": missing},
        )
    return normalized


def _party_selection(args: argparse.Namespace) -> dict[str, Any]:
    begin_year = args.begin_year
    end_year = args.end_year
    current_year = date.today().year
    if begin_year < 1974:
        raise SanDiegoSelectionError(
            "begin_year_too_early",
            "Court Index party search begins in 1974",
        )
    if end_year > current_year:
        raise SanDiegoSelectionError(
            "end_year_in_future",
            "Court Index ending year cannot exceed the current year",
        )
    if end_year < begin_year:
        raise SanDiegoSelectionError(
            "invalid_year_range",
            "--end-year must not be earlier than --begin-year",
        )
    last_name = _required_text(args.last_name, "last name or business name")
    return {
        "case_type": CASE_TYPE_VALUES[args.case_type],
        "site": SITE_VALUES[args.site],
        "party_type": PARTY_TYPE_VALUES[args.party_type],
        "begin_year": begin_year,
        "end_year": end_year,
        "last_name": last_name,
        "first_name": _text(args.first_name) or "",
        "date_of_birth": _text(args.date_of_birth),
    }


def _case_selection(args: argparse.Namespace) -> dict[str, Any]:
    case_number = _required_text(args.case_number, "case number")
    if len(re.sub(r"[^A-Za-z0-9]", "", case_number)) < 5:
        raise SanDiegoSelectionError(
            "case_number_too_short",
            "Court Index case-number search requires at least five characters",
        )
    return {
        "case_type": CASE_SEARCH_TYPE_VALUES[args.case_type],
        "site": SITE_VALUES[args.site],
        "case_number": case_number,
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any]
    requested_limit: int | None = getattr(args, "limit", None)
    cursor: str | None = None
    if args.command == "party-search":
        parameters = {
            "case_type": args.case_type,
            "site": args.site,
            "party_type": args.party_type,
            "begin_year": args.begin_year,
            "end_year": args.end_year,
            "last_name": args.last_name,
            "first_name": args.first_name,
            "date_of_birth": args.date_of_birth,
            "offset": args.offset,
        }
        cursor = f"sd-index:party-row-offset:{args.offset}"
    elif args.command == "case-search":
        parameters = {
            "case_number": args.case_number,
            "case_type": args.case_type,
            "site": args.site,
            "offset": args.offset,
        }
        cursor = f"sd-index:case-row-offset:{args.offset}"
    elif args.command == "case-detail":
        parameters = {"detail_url": args.detail_url}
        requested_limit = None
    elif args.command == "new-filings":
        parameters = {
            "case_type": args.case_type,
            "offset": args.offset,
        }
        cursor = f"sd-new-filings:case-offset:{args.offset}"
    elif args.command == "probe":
        parameters = {
            "bounded_probe": True,
            "party_sentinel": "Epstein, Jeffrey",
            "case_sentinel": PROBE_CASE_NUMBER,
            "new_filing_partition": "civil/a",
        }
        requested_limit = None
    else:
        parameters = {"inventory_as_of": "2026-07-30"}
        requested_limit = None
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=COUNTY_GEOID,
            name="San Diego County, California",
            state_code=STATE_CODE,
            county_fips=COUNTY_GEOID,
            locality="San Diego County",
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _make_index_client(args: argparse.Namespace) -> SanDiegoCourtIndexClient:
    return SanDiegoCourtIndexClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        minimum_interval=args.minimum_interval,
    )


def _make_new_filings_client(args: argparse.Namespace) -> NewFilingsClient:
    return NewFilingsClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        minimum_interval=args.minimum_interval,
    )


def _failure_result(
    query: PublicRecordsQuery,
    error: SanDiegoCourtError,
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


def execute(
    args: argparse.Namespace,
    *,
    index_client: SanDiegoCourtIndexClient | Any | None = None,
    new_filings_client: NewFilingsClient | Any | None = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one verified San Diego court operation."""

    del access_decision
    query = build_query(args)
    owned_clients: list[Any] = []
    try:
        if args.command == "party-search":
            selection = _party_selection(args)
            client = index_client or _make_index_client(args)
            if index_client is None:
                owned_clients.append(client)
            search_result = client.party_search(
                selection,
                limit=args.limit,
                offset=args.offset,
            )
            records = normalize_index_records(
                search_result,
                operation=args.command,
                selection=selection,
            )
            next_cursor = (
                f"sd-index:party-row-offset:{args.offset + len(search_result.rows)}"
                if args.limit is not None
                and args.offset + len(search_result.rows)
                < search_result.native_rows_observed
                else None
            )
        elif args.command == "case-search":
            selection = _case_selection(args)
            client = index_client or _make_index_client(args)
            if index_client is None:
                owned_clients.append(client)
            search_result = client.case_search(
                selection,
                limit=args.limit,
                offset=args.offset,
            )
            records = normalize_index_records(
                search_result,
                operation=args.command,
                selection=selection,
            )
            next_cursor = (
                f"sd-index:case-row-offset:{args.offset + len(search_result.rows)}"
                if args.limit is not None
                and args.offset + len(search_result.rows)
                < search_result.native_rows_observed
                else None
            )
        elif args.command == "case-detail":
            detail_url = _validated_detail_url(args.detail_url)
            client = index_client or _make_index_client(args)
            if index_client is None:
                owned_clients.append(client)
            records = [normalize_case_detail(client.case_detail(detail_url))]
            next_cursor = None
        elif args.command == "new-filings":
            selected_types = (
                tuple(NEW_FILING_TYPE_CODES)
                if args.case_type == "all"
                else (args.case_type,)
            )
            client = new_filings_client or _make_new_filings_client(args)
            if new_filings_client is None:
                owned_clients.append(client)
            filing_result = client.collect(
                selected_types,
                limit=args.limit,
                offset=args.offset,
            )
            records = normalize_new_filings(filing_result)
            unique_case_count = len(
                {
                    case.case_number.casefold()
                    for page in filing_result.pages
                    for case in page.cases
                }
                | {
                    party.case_number.casefold()
                    for page in filing_result.pages
                    for party in page.parties
                }
            )
            next_cursor = (
                f"sd-new-filings:case-offset:{args.offset + len(records)}"
                if args.limit is not None
                and args.offset + len(records) < unique_case_count
                else None
            )
        elif args.command == "alternatives":
            records = _alternatives()
            next_cursor = None
        elif args.command == "probe":
            browser = index_client or _make_index_client(args)
            filings = new_filings_client or _make_new_filings_client(args)
            if index_client is None:
                owned_clients.append(browser)
            if new_filings_client is None:
                owned_clients.append(filings)
            party_result, case_result, detail = browser.probe()
            filing_pages = filings.probe()
            records = [
                {
                    "record_kind": "source_probe",
                    "source_id": SOURCE_ID,
                    "bounded_probe": True,
                    "probe_bounds": {
                        "party_search": (
                            "exact Epstein/Jeffrey Civil 1974-current"
                        ),
                        "case_search": f"exact {PROBE_CASE_NUMBER}",
                        "case_detail": f"exact {PROBE_CASE_NUMBER}",
                        "new_filings": (
                            "initial alphabet partition for each of the five "
                            "native case types"
                        ),
                    },
                    "party_search": {
                        "native_rows_observed": (
                            party_result.native_rows_observed
                        ),
                        "case_numbers": sorted(
                            {row.case_number for row in party_result.rows}
                        ),
                        "native_pages_exhausted": (
                            party_result.native_pages_exhausted
                        ),
                    },
                    "case_search": {
                        "native_rows_observed": case_result.native_rows_observed,
                        "case_numbers": sorted(
                            {row.case_number for row in case_result.rows}
                        ),
                        "native_pages_exhausted": (
                            case_result.native_pages_exhausted
                        ),
                    },
                    "case_detail": {
                        "case_number": detail.case_number,
                        "case_title": detail.case_title,
                        "category_code": detail.category_code,
                        "category": detail.category_label,
                        "party_count": len(detail.parties),
                    },
                    "new_filings": {
                        "probe_bound": (
                            "initial alphabet partition for each native "
                            "case type"
                        ),
                        "case_types": {
                            case_type: {
                                "partition": page.partition,
                                "last_updated": page.last_updated,
                                "case_count": len(page.cases),
                                "party_count": len(page.parties),
                                "native_partitions_discovered": len(
                                    page.partition_urls
                                ),
                            }
                            for case_type, page in filing_pages.items()
                        },
                    },
                    "transport": {
                        "court_index": "headed_chromium",
                        "new_filings": "static_html_http",
                        "browser_execution_timeout_seconds": 900,
                        "browser_execution_timeout_is_collection_bound": False,
                    },
                    "server_result_ceiling_disclosed": True,
                    "server_result_ceiling_value": None,
                }
            ]
            next_cursor = None
        else:
            raise SanDiegoSelectionError(
                "unsupported_command",
                f"unsupported San Diego court command: {args.command}",
            )
        result = PublicRecordsResult.success(
            query,
            records,
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    except SanDiegoCourtError as error:
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
        for client in owned_clients:
            client.close()

    if log_results:
        count = (
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"San Diego Superior Court {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"San Diego Superior Court {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        if "raw_case_number" in record:
            print(
                f"  {record.get('raw_case_number')} | "
                f"{record.get('filing_date') or '?'} | "
                f"{record.get('case_type') or '?'}"
            )
        elif "route_id" in record:
            print(
                f"  {record.get('route_id')} | "
                f"{record.get('access_state')}"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _year(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("year must be positive")
    return parsed


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Per-request or per-navigation timeout in seconds",
    )
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
        help="Minimum seconds between native page acquisitions",
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_int,
        default=3,
        help="Maximum attempts for transient navigation or HTTP failures",
    )
    add_output_args(parser)


def _add_limit_and_offset(parser: argparse.ArgumentParser, noun: str) -> None:
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=None,
        help=(
            f"Caller limit on returned {noun}; omitted means all native "
            "pages or partitions returned by the selected source operation"
        ),
    )
    parser.add_argument(
        "--offset",
        type=_nonnegative_int,
        default=0,
        help=f"Returned {noun} to skip after native collection",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query San Diego Superior Court's official Court Index and "
            "five-court-day new-filing lists"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    party = subparsers.add_parser(
        "party-search",
        help="Search the Court Index by party or organization name",
    )
    party.add_argument(
        "--case-type",
        choices=tuple(CASE_TYPE_VALUES),
        required=True,
        help="One native Court Index case type",
    )
    party.add_argument(
        "--site",
        choices=tuple(SITE_VALUES),
        default="all",
    )
    party.add_argument(
        "--party-type",
        choices=tuple(PARTY_TYPE_VALUES),
        default="all",
    )
    party.add_argument(
        "--begin-year",
        type=_year,
        default=1974,
        help="Native filing-year lower bound (source coverage begins in 1974)",
    )
    party.add_argument(
        "--end-year",
        type=_year,
        default=date.today().year,
        help="Native filing-year upper bound (defaults to current year)",
    )
    party.add_argument("--last-name", required=True)
    party.add_argument("--first-name")
    party.add_argument(
        "--date-of-birth",
        help="Optional native date-of-birth field when the form exposes it",
    )
    _add_limit_and_offset(party, "native index rows")
    _add_runtime_and_output(party)

    case = subparsers.add_parser(
        "case-search",
        help="Search the Court Index by case number",
    )
    case.add_argument("case_number")
    case.add_argument(
        "--case-type",
        choices=tuple(CASE_SEARCH_TYPE_VALUES),
        default="all",
    )
    case.add_argument(
        "--site",
        choices=tuple(SITE_VALUES),
        default="all",
    )
    _add_limit_and_offset(case, "native index rows")
    _add_runtime_and_output(case)

    detail = subparsers.add_parser(
        "case-detail",
        help="Fetch one official Court Index case-detail URL",
    )
    detail.add_argument("detail_url")
    _add_runtime_and_output(detail)

    filings = subparsers.add_parser(
        "new-filings",
        help="Collect native five-court-day new-filing alphabet partitions",
    )
    filings.add_argument(
        "--case-type",
        choices=("all", *tuple(NEW_FILING_TYPE_CODES)),
        default="all",
    )
    _add_limit_and_offset(filings, "unique cases")
    _add_runtime_and_output(filings)

    alternatives = subparsers.add_parser(
        "alternatives",
        help="Inventory official and credible complementary record routes",
    )
    _add_runtime_and_output(alternatives)

    probe = subparsers.add_parser(
        "probe",
        help="Run explicit bounded sentinels across all implemented transports",
    )
    _add_runtime_and_output(probe)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
