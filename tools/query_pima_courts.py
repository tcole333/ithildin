#!/usr/bin/env python3
"""Query Pima County Superior Court's public Agave case-record portal.

The clerk's PublicDocs application is a legacy ASP.NET frame set.  Its
search form posts to one stable route, while result, case-detail, party, and
PDF links are generated for the current session.  This adapter resolves
those links in memory and emits stable case-number and case-scoped docket
identities.

Examples:
    uv run python tools/query_pima_courts.py search CHOMSKY
    uv run python tools/query_pima_courts.py case C20256501 --json
    uv run python tools/query_pima_courts.py document \
        C20256501 pima:document-row:0123456789abcdef01234567 filing.pdf
    uv run python tools/query_pima_courts.py probe --json
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
from dataclasses import dataclass
from datetime import datetime
from email.message import Message
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, Tag

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import acquisition_result_status
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
    from public_records_catalog import acquisition_result_status
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


SOURCE_ID = "us-az-pima-superior-agave"
STATE_CODE = "AZ"
COUNTY_FIPS = "04019"
COURT_ID = "az-pima-superior-court"
COURT_NAME = "Superior Court of Arizona in Pima County"
OFFICIAL_LINKING_PAGE = "https://www.cosc.pima.gov/services/case-records/"
BASE_URL = "https://wwww.cosc.pima.gov/PublicDocs/"
SEARCH_URL = urljoin(BASE_URL, "search2a.aspx")
PLATFORM_FAMILY = "pima_agave_aspnet_publicdocs"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.5
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Pima County Superior Court Agave Public Record Search",
    source_role="county_superior_court_case_docket_and_public_documents",
    base_url=BASE_URL,
    dataset_id="pima-agave-publicdocs",
    metadata={
        "authority": "Pima County Clerk of the Superior Court",
        "county_fips": COUNTY_FIPS,
        "platform_family": PLATFORM_FAMILY,
        "official_linking_page": OFFICIAL_LINKING_PAGE,
        "authentication": "none",
    },
)

SOURCE_WARNINGS = (
    "Result, detail, and document routes are session-bound and are omitted "
    "from emitted records.",
    "Agave does not expose native docket or document IDs; case-scoped row "
    "keys are derived from displayed source fields and duplicate occurrence.",
)

_MAIN_TOKEN_RE = re.compile(
    r"window\.open\(\s*['\"]([^'\"]+)['\"]\s*,\s*"
    r"['\"]main['\"]\s*\)",
    re.IGNORECASE,
)
_CASE_INTERNAL_ID_RE = re.compile(r"^\d+$")
_CASE_NUMBER_RE = re.compile(r"^[A-Z0-9]+$")

_SEARCH_HEADERS = (
    "Party Name",
    "Case Number",
    "Case Caption",
    "Filing Date",
)
_PARTY_HEADERS = (
    "Party Full Name",
    "Party Role",
    "Name Type",
    "DOB",
)
_CHARGE_HEADERS = (
    "Party Full Name",
    "Count",
    "Prep Offense",
    "ARS",
    "Desc",
    "Class",
    "Disp Date",
    "Disposition",
    "",
)
_DOCUMENT_HEADERS = (
    "Document Type",
    "Document SubType",
    "Document Caption",
    "File Date",
    "Image",
)
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class PimaCourtError(RuntimeError):
    """Base error for the Pima Agave source."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "pima_court_error",
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


class PimaCourtSourceChangedError(PimaCourtError):
    """The live source no longer matches the verified HTML contract."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "pima_source_changed",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            retryable=False,
            details=details,
        )


class PimaCourtNotFoundError(PimaCourtError):
    """An exact case-number query returned the source's not-found state."""

    def __init__(self, case_number: str) -> None:
        super().__init__(
            f"Pima County case not found: {case_number}",
            code="case_not_found",
            status=ResultStatus.NO_RESULTS,
            category="not_found",
            details={"case_number": case_number},
        )


class PimaCourtSelectionError(PimaCourtError):
    """A case-scoped docket or document selector was not usable."""

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
            retryable=False,
            details=details,
        )


@dataclass(frozen=True)
class PimaSearchForm:
    """One fresh ASP.NET search form and its session-bound navigation URL."""

    menu_url: str
    search_url: str
    hidden_fields: Mapping[str, str]


@dataclass(frozen=True)
class PimaSearchHit:
    """One source row from the party-name result grid."""

    matched_party_name: str
    raw_case_number: str
    display_case_number: str
    caption: str | None
    filing_date_raw: str | None
    filing_date: str | None
    detail_url: str


@dataclass(frozen=True)
class PimaSearchPage:
    """A complete, non-paginated Agave name-search response."""

    hits: Sequence[PimaSearchHit]


@dataclass(frozen=True)
class PimaCasePage:
    """A normalized case plus in-session PDF routes keyed by docket identity."""

    record: Mapping[str, Any]
    document_urls: Mapping[str, str]


@dataclass(frozen=True)
class PimaPDF:
    """A validated public PDF response."""

    content: bytes
    media_type: str
    filename: str
    sha256: str
    etag: str | None


@dataclass(frozen=True)
class PimaDocumentFetch:
    """A case page and one PDF selected from its current session."""

    case_page: PimaCasePage
    entry_id: str
    pdf: PimaPDF


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\x00", "").split())
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise PimaCourtSourceChangedError(
            f"Pima Agave response lacks {field_name}",
            code="required_field_missing",
            details={"field": field_name},
        )
    return normalized


def normalize_case_number(value: str) -> str:
    """Return the stable compact case-number spelling accepted by Agave."""

    normalized = re.sub(r"[\s-]+", "", value).upper()
    if not normalized or not _CASE_NUMBER_RE.fullmatch(normalized):
        raise ValueError(
            "case number must contain letters and digits without punctuation"
        )
    return normalized


def _source_date(value: Any, field_name: str) -> tuple[str | None, str | None]:
    raw = _text(value)
    if raw is None:
        return None, None
    try:
        normalized = datetime.strptime(raw, "%m/%d/%Y").date().isoformat()
    except ValueError as error:
        raise PimaCourtSourceChangedError(
            f"Pima Agave returned an unparseable {field_name}: {raw!r}",
            code="date_parse_failed",
            details={"field": field_name, "value": raw},
        ) from error
    return raw, normalized


def _birth_date(value: Any) -> dict[str, Any]:
    raw = _text(value)
    if raw is None:
        return {
            "dob_raw": None,
            "dob_iso": None,
            "dob_precision": None,
        }
    for date_format, precision, output_format in (
        ("%m/%d/%Y", "day", "%Y-%m-%d"),
        ("%m/%Y", "month", "%Y-%m"),
        ("%Y", "year", "%Y"),
    ):
        try:
            parsed = datetime.strptime(raw, date_format)
        except ValueError:
            continue
        return {
            "dob_raw": raw,
            "dob_iso": parsed.strftime(output_format),
            "dob_precision": precision,
        }
    return {
        "dob_raw": raw,
        "dob_iso": None,
        "dob_precision": "unknown",
    }


def _court_payload() -> dict[str, Any]:
    return {
        "court_id": COURT_ID,
        "native_court_id": "pima-superior",
        "name": COURT_NAME,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_FIPS,
        "court_level": "superior",
        "division": None,
        "official_url": OFFICIAL_LINKING_PAGE,
    }


def _element_text(element: Tag | None) -> str | None:
    if element is None:
        return None
    return _text(element.get_text(" ", strip=True))


def _input_value(soup: BeautifulSoup, selector: str) -> str | None:
    element = soup.select_one(selector)
    if not isinstance(element, Tag):
        return None
    return _text(element.get("value"))


def _textarea_value(soup: BeautifulSoup, selector: str) -> str | None:
    element = soup.select_one(selector)
    return _element_text(element if isinstance(element, Tag) else None)


def _table_rows(
    soup: BeautifulSoup,
    table_id: str,
    expected_headers: Sequence[str],
    *,
    required: bool,
) -> list[tuple[list[str | None], list[Tag]]]:
    table = soup.find("table", id=table_id)
    if not isinstance(table, Tag):
        if required:
            raise PimaCourtSourceChangedError(
                f"Pima Agave response lacks #{table_id}",
                code="table_missing",
                details={"table_id": table_id},
            )
        return []

    rows = table.find_all("tr", recursive=False)
    if not rows:
        rows = table.find_all("tr")
    if not rows:
        raise PimaCourtSourceChangedError(
            f"Pima Agave table #{table_id} has no header",
            code="table_header_missing",
            details={"table_id": table_id},
        )

    header_cells = rows[0].find_all(["th", "td"], recursive=False)
    if not header_cells:
        header_cells = rows[0].find_all(["th", "td"])
    actual_headers = tuple(_element_text(cell) or "" for cell in header_cells)
    if actual_headers != tuple(expected_headers):
        raise PimaCourtSourceChangedError(
            f"Pima Agave table #{table_id} header changed",
            code="table_header_changed",
            details={
                "table_id": table_id,
                "expected": list(expected_headers),
                "actual": list(actual_headers),
            },
        )

    parsed: list[tuple[list[str | None], list[Tag]]] = []
    for row in rows[1:]:
        cells = row.find_all("td", recursive=False)
        if not cells:
            cells = row.find_all("td")
        if not cells:
            continue
        if len(cells) != len(expected_headers):
            raise PimaCourtSourceChangedError(
                f"Pima Agave table #{table_id} row width changed",
                code="table_row_width_changed",
                details={
                    "table_id": table_id,
                    "expected": len(expected_headers),
                    "actual": len(cells),
                },
            )
        parsed.append(([_element_text(cell) for cell in cells], cells))
    return parsed


def parse_landing_menu_url(html: str, *, response_url: str = BASE_URL) -> str:
    """Return the session-bound navigation-frame URL from PublicDocs."""

    soup = BeautifulSoup(html, "html.parser")
    frame = soup.find("frame", attrs={"name": "contents"})
    if not isinstance(frame, Tag):
        frames = soup.find_all("frame")
        frame = frames[0] if frames else None
    if not isinstance(frame, Tag) or _text(frame.get("src")) is None:
        raise PimaCourtSourceChangedError(
            "Pima Agave landing page lacks its navigation frame",
            code="navigation_frame_missing",
        )
    return urljoin(response_url, str(frame["src"]))


def parse_search_form(
    html: str,
    *,
    menu_url: str,
) -> PimaSearchForm:
    """Parse the stable ASP.NET search action and per-session hidden fields."""

    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if not isinstance(form, Tag):
        raise PimaCourtSourceChangedError(
            "Pima Agave navigation frame lacks a search form",
            code="search_form_missing",
        )
    action = _text(form.get("action"))
    if action is None:
        raise PimaCourtSourceChangedError(
            "Pima Agave search form lacks an action",
            code="search_action_missing",
        )
    search_url = urljoin(menu_url, action)
    if urlsplit(search_url).path.rstrip("/").split("/")[-1].lower() != (
        "search2a.aspx"
    ):
        raise PimaCourtSourceChangedError(
            "Pima Agave search action changed",
            code="search_action_changed",
            details={"action": search_url},
        )

    hidden_fields: dict[str, str] = {}
    for element in form.find_all("input"):
        if not isinstance(element, Tag):
            continue
        if str(element.get("type", "")).lower() != "hidden":
            continue
        name = _text(element.get("name"))
        if name:
            hidden_fields[name] = str(element.get("value", ""))

    required_hidden = {
        "__VIEWSTATE",
        "__VIEWSTATEGENERATOR",
        "__EVENTVALIDATION",
    }
    missing = sorted(required_hidden.difference(hidden_fields))
    if missing:
        raise PimaCourtSourceChangedError(
            "Pima Agave search form lacks required ASP.NET state",
            code="aspnet_state_missing",
            details={"missing": missing},
        )
    return PimaSearchForm(
        menu_url=menu_url,
        search_url=search_url,
        hidden_fields=hidden_fields,
    )


def parse_main_frame_url(html: str, *, response_url: str = SEARCH_URL) -> str:
    """Resolve the session-bound main-frame route returned by a search POST."""

    match = _MAIN_TOKEN_RE.search(html)
    if match is None:
        raise PimaCourtSourceChangedError(
            "Pima Agave search response lacks a main-frame route",
            code="main_frame_token_missing",
        )
    return urljoin(response_url, match.group(1))


def parse_search_notice(html: str) -> str | None:
    """Return the source's case/name search notice, when present."""

    soup = BeautifulSoup(html, "html.parser")
    for selector in ("#lblInfo", "#lblSearchInfo"):
        notice = _element_text(soup.select_one(selector))
        if notice:
            return notice.lstrip("> ").strip()
    return None


def is_empty_main_frame(html: str) -> bool:
    """Return whether Agave served its default ContentBanner empty state."""

    soup = BeautifulSoup(html, "html.parser")
    title = _element_text(soup.title)
    return title == "ContentBanner" and soup.select_one("#txtCaseNumber") is None


def parse_name_results(
    html: str,
    *,
    response_url: str,
) -> list[PimaSearchHit]:
    """Parse source rows from Agave's ``NameResults1`` grid."""

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="grdCases")
    if not isinstance(table, Tag):
        page_text = _text(soup.get_text(" ", strip=True)) or ""
        if "not found" in page_text.lower() or "no record" in page_text.lower():
            return []
        raise PimaCourtSourceChangedError(
            "Pima Agave name-result page lacks #grdCases",
            code="search_results_missing",
        )

    parsed_rows = _table_rows(
        soup,
        "grdCases",
        _SEARCH_HEADERS,
        required=True,
    )
    hits: list[PimaSearchHit] = []
    for values, cells in parsed_rows:
        party_name = _required_text(values[0], "matched party name")
        display_case_number = _required_text(values[1], "case number")
        case_number = normalize_case_number(display_case_number)
        filing_date_raw, filing_date = _source_date(
            values[3],
            "filing date",
        )
        link = cells[1].find("a", href=True)
        if not isinstance(link, Tag):
            raise PimaCourtSourceChangedError(
                "Pima Agave case result lacks a detail link",
                code="case_detail_link_missing",
                details={"case_number": case_number},
            )
        hits.append(
            PimaSearchHit(
                matched_party_name=party_name,
                raw_case_number=case_number,
                display_case_number=display_case_number,
                caption=_text(values[2]),
                filing_date_raw=filing_date_raw,
                filing_date=filing_date,
                detail_url=urljoin(response_url, str(link["href"])),
            )
        )
    return hits


def _internal_case_id(soup: BeautifulSoup) -> str | None:
    form = soup.find("form")
    if not isinstance(form, Tag):
        return None
    action = _text(form.get("action"))
    if action is None:
        return None
    values = parse_qs(urlsplit(action).query).get("ID", [])
    if not values:
        return None
    identifier = _text(values[0])
    if identifier is None or not _CASE_INTERNAL_ID_RE.fullmatch(identifier):
        raise PimaCourtSourceChangedError(
            "Pima Agave detail page returned an invalid internal case ID",
            code="case_internal_id_invalid",
            details={"value": identifier},
        )
    return identifier


def _parse_parties(soup: BeautifulSoup) -> list[dict[str, Any]]:
    parties: list[dict[str, Any]] = []
    for sequence, (values, _cells) in enumerate(
        _table_rows(
            soup,
            "grdParty",
            _PARTY_HEADERS,
            required=True,
        ),
        start=1,
    ):
        party = {
            "sequence_no": sequence,
            "raw_name": _required_text(values[0], "party name"),
            "role": _required_text(values[1], "party role"),
            "native_name_type": _text(values[2]),
            **_birth_date(values[3]),
            "access_state": "public",
            "native_access_state": "PublicDocs party grid",
        }
        parties.append(party)
    return parties


def _parse_charges(soup: BeautifulSoup) -> list[dict[str, Any]]:
    charges: list[dict[str, Any]] = []
    current_party: str | None = None
    for sequence, (values, _cells) in enumerate(
        _table_rows(
            soup,
            "grdCharges",
            _CHARGE_HEADERS,
            required=False,
        ),
        start=1,
    ):
        current_party = _text(values[0]) or current_party
        disposition_date_raw, disposition_date = _source_date(
            values[6],
            "disposition date",
        )
        count_text = _text(values[1])
        count: int | str | None
        if count_text is None:
            count = None
        else:
            try:
                count = int(count_text)
            except ValueError:
                count = count_text
        charges.append(
            {
                "sequence_no": sequence,
                "party_name": current_party,
                "count": count,
                "preparatory_offense": _text(values[2]),
                "statute": _text(values[3]),
                "description": _text(values[4]),
                "classification": _text(values[5]),
                "disposition_date_raw": disposition_date_raw,
                "disposition_date": disposition_date,
                "disposition": _text(values[7]),
            }
        )
    return charges


def _derived_document_row_id(
    *,
    case_number: str,
    document_type: str | None,
    document_subtype: str | None,
    caption: str | None,
    filed_date_raw: str | None,
    occurrence: int,
) -> str:
    payload = {
        "source_id": SOURCE_ID,
        "case_number": case_number,
        "document_type": document_type,
        "document_subtype": document_subtype,
        "caption": caption,
        "filed_date_raw": filed_date_raw,
        "duplicate_occurrence": occurrence,
    }
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"pima:document-row:{digest[:24]}"


def _parse_docket(
    soup: BeautifulSoup,
    *,
    case_number: str,
    detail_url: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    entries: list[dict[str, Any]] = []
    document_urls: dict[str, str] = {}
    duplicate_counts: defaultdict[str, int] = defaultdict(int)
    rows = _table_rows(
        soup,
        "grdDocuments",
        _DOCUMENT_HEADERS,
        required=False,
    )
    for sequence, (values, cells) in enumerate(rows, start=1):
        document_type = _text(values[0])
        document_subtype = _text(values[1])
        caption = _text(values[2])
        filed_date_raw, filed_date = _source_date(
            values[3],
            "document file date",
        )
        base_identity = canonical_json(
            {
                "document_type": document_type,
                "document_subtype": document_subtype,
                "caption": caption,
                "filed_date_raw": filed_date_raw,
            }
        )
        duplicate_counts[base_identity] += 1
        occurrence = duplicate_counts[base_identity]
        entry_id = _derived_document_row_id(
            case_number=case_number,
            document_type=document_type,
            document_subtype=document_subtype,
            caption=caption,
            filed_date_raw=filed_date_raw,
            occurrence=occurrence,
        )

        image_cell = cells[4]
        image_status = _element_text(image_cell)
        link = image_cell.find("a", href=True)
        document_available = isinstance(link, Tag)
        documents: list[dict[str, Any]] = []
        if isinstance(link, Tag):
            document_urls[entry_id] = urljoin(
                detail_url,
                str(link["href"]),
            )
            documents.append(
                {
                    "native_document_id": f"{entry_id}:pdf",
                    "native_document_id_source": (
                        "derived_case_number_displayed_fields_occurrence"
                    ),
                    "document_type": document_subtype or document_type,
                    "filed_date": filed_date,
                    "source_url": BASE_URL,
                    "mime_type": "application/pdf",
                    "certification_status": "uncertified",
                    "access_state": "public",
                    "native_access_state": image_status or "Available",
                }
            )

        entries.append(
            {
                "native_entry_id": entry_id,
                "native_entry_id_source": (
                    "derived_case_number_displayed_fields_occurrence"
                ),
                "sequence_no": sequence,
                "duplicate_occurrence": occurrence,
                "entry_type": document_type,
                "entry_subtype": document_subtype,
                "description": caption,
                "filed_date_raw": filed_date_raw,
                "filed_date": filed_date,
                "document_available": document_available,
                "native_document_access": image_status,
                "access_state": "public",
                "native_access_state": "PublicDocs docket grid",
                "documents": documents,
            }
        )
    return entries, document_urls


def parse_case_detail(
    html: str,
    *,
    response_url: str,
) -> PimaCasePage:
    """Parse one Agave case-detail page and retain PDF routes in memory."""

    soup = BeautifulSoup(html, "html.parser")
    display_case_number = _required_text(
        _input_value(soup, "#txtCaseNumber"),
        "case number",
    )
    case_number = normalize_case_number(display_case_number)
    filing_date_raw, filing_date = _source_date(
        _input_value(soup, "#txtCaseDate"),
        "case filing date",
    )
    caption = _textarea_value(soup, "#txtCaseCaption")
    judge_raw = _input_value(soup, "#txtJudge")
    judge = None if judge_raw == "No Judge Info" else judge_raw
    source_internal_case_id = _internal_case_id(soup)
    parties = _parse_parties(soup)
    charges = _parse_charges(soup)
    docket_entries, document_urls = _parse_docket(
        soup,
        case_number=case_number,
        detail_url=response_url,
    )
    prefix_match = re.match(r"^[A-Z]+", case_number)
    case_number_prefix = prefix_match.group(0) if prefix_match else None

    record = {
        "record_kind": "case",
        "source_id": SOURCE_ID,
        "court": _court_payload(),
        "raw_case_number": case_number,
        "display_case_number": display_case_number,
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case_number,
        ),
        "source_internal_id": source_internal_case_id,
        "source_internal_case_id": source_internal_case_id,
        "caption": caption,
        "filing_date_raw": filing_date_raw,
        "filing_date": filing_date,
        "case_number_prefix": case_number_prefix,
        "judge": judge,
        "judge_raw": judge_raw,
        "parties": parties,
        "charges": charges,
        "docket_entries": docket_entries,
        "source_url": BASE_URL,
        "access_state": "public",
        "native_access_state": "anonymous PublicDocs case detail",
        "certified_record": False,
    }
    return PimaCasePage(record=record, document_urls=document_urls)


def normalize_name_search_records(
    hits: Sequence[PimaSearchHit],
    *,
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Collapse party-result rows onto stable case-number identities."""

    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for hit in hits:
        existing = grouped.get(hit.raw_case_number)
        if existing is None:
            grouped[hit.raw_case_number] = {
                "record_kind": "case",
                "source_id": SOURCE_ID,
                "court": _court_payload(),
                "raw_case_number": hit.raw_case_number,
                "display_case_number": hit.display_case_number,
                "canonical_ref": canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    hit.raw_case_number,
                ),
                "caption": hit.caption,
                "filing_date_raw": hit.filing_date_raw,
                "filing_date": hit.filing_date,
                "matched_party_names": [hit.matched_party_name],
                "source_result_row_count": 1,
                "source_url": BASE_URL,
                "access_state": "public",
                "native_access_state": "anonymous PublicDocs name search",
                "certified_record": False,
            }
            continue
        if (
            existing["caption"],
            existing["filing_date_raw"],
        ) != (
            hit.caption,
            hit.filing_date_raw,
        ):
            raise PimaCourtSourceChangedError(
                "Pima Agave returned conflicting rows for one case number",
                code="case_result_conflict",
                details={"case_number": hit.raw_case_number},
            )
        if hit.matched_party_name not in existing["matched_party_names"]:
            existing["matched_party_names"].append(hit.matched_party_name)
        existing["source_result_row_count"] += 1

    records = list(grouped.values())
    source_unique_count = len(records)
    if limit is not None:
        records = records[:limit]
    return records, source_unique_count


class PimaCourtClient:
    """Session-aware client for the official Pima Agave portal."""

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

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
    ) -> Any:
        request_headers = {
            "Accept": "text/html,application/xhtml+xml,application/pdf",
            "User-Agent": self.user_agent,
            **dict(headers or {}),
        }
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=request_headers,
                    data=data,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt >= self.retry_policy.max_attempts:
                    raise PimaCourtError(
                        f"Pima Agave request failed after {attempt} "
                        f"attempts: {error}",
                        code="transport_error",
                        category="transport",
                        retryable=True,
                        details={"attempts": attempt},
                    ) from error
                self._sleeper(self.retry_policy.delay(attempt))
                continue

            status_code = int(response.status_code)
            if status_code in _RETRYABLE_STATUS_CODES:
                retry_after: float | None = None
                raw_retry_after = response.headers.get("Retry-After")
                if raw_retry_after:
                    try:
                        retry_after = max(0.0, float(raw_retry_after))
                    except ValueError:
                        retry_after = None
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(
                        self.retry_policy.delay(attempt, retry_after)
                    )
                    continue
                status = (
                    ResultStatus.RATE_LIMITED
                    if status_code == 429
                    else ResultStatus.UNAVAILABLE
                )
                raise PimaCourtError(
                    f"Pima Agave returned HTTP {status_code}",
                    code=(
                        "rate_limited"
                        if status_code == 429
                        else "http_status_error"
                    ),
                    status=status,
                    category=(
                        "rate_limit"
                        if status_code == 429
                        else "transport"
                    ),
                    retryable=True,
                    details={"status_code": status_code},
                )
            if status_code in {401, 403}:
                raise PimaCourtError(
                    f"Pima Agave returned HTTP {status_code}",
                    code="source_access_failed",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"status_code": status_code},
                )
            if status_code in {404, 410}:
                raise PimaCourtSourceChangedError(
                    f"Pima Agave route returned HTTP {status_code}",
                    code="source_route_missing",
                    details={"status_code": status_code},
                )
            if status_code < 200 or status_code >= 300:
                raise PimaCourtError(
                    f"Pima Agave returned HTTP {status_code}",
                    code="http_status_error",
                    category="transport",
                    details={"status_code": status_code},
                )
            return response

        raise PimaCourtError(
            f"Pima Agave request failed: {last_error}",
            code="transport_error",
            category="transport",
            retryable=True,
        )

    def bootstrap(self) -> PimaSearchForm:
        landing = self._request("GET", BASE_URL)
        menu_url = parse_landing_menu_url(
            landing.text,
            response_url=landing.url,
        )
        menu = self._request(
            "GET",
            menu_url,
            headers={"Referer": landing.url},
        )
        return parse_search_form(menu.text, menu_url=menu.url)

    def _submit_search(
        self,
        *,
        search_group: str,
        last_name: str = "",
        first_name: str = "",
        case_number: str = "",
    ) -> tuple[str, str | None, str | None]:
        form = self.bootstrap()
        payload = dict(form.hidden_fields)
        payload.update(
            {
                "txtLastName": last_name,
                "txtFirstName": first_name,
                "txtCaseNumber": case_number,
                "SearchGroup": search_group,
                "btnSearch": "Search",
            }
        )
        origin = (
            f"{urlsplit(form.search_url).scheme}://"
            f"{urlsplit(form.search_url).netloc}"
        )
        search = self._request(
            "POST",
            form.search_url,
            headers={"Referer": form.menu_url, "Origin": origin},
            data=payload,
        )
        notice = parse_search_notice(search.text)
        if notice and "not found" in notice.lower():
            return search.text, notice, None
        main_url = parse_main_frame_url(
            search.text,
            response_url=search.url,
        )
        main = self._request(
            "GET",
            main_url,
            headers={"Referer": search.url},
        )
        return search.text, notice, main.text

    def search_name(
        self,
        last_name: str,
        *,
        first_name: str | None = None,
    ) -> PimaSearchPage:
        normalized_last = _text(last_name)
        if normalized_last is None:
            raise ValueError("last or business name must not be blank")
        _post_html, _notice, main_html = self._submit_search(
            search_group="rdoName",
            last_name=normalized_last,
            first_name=_text(first_name) or "",
        )
        if main_html is None:
            return PimaSearchPage(hits=())
        hits = parse_name_results(main_html, response_url=BASE_URL)
        return PimaSearchPage(hits=tuple(hits))

    def _fetch_case_exact(self, case_number: str) -> PimaCasePage:
        normalized_case_number = normalize_case_number(case_number)
        _post_html, notice, main_html = self._submit_search(
            search_group="rdoCase",
            case_number=normalized_case_number,
        )
        if main_html is None:
            raise PimaCourtNotFoundError(normalized_case_number)
        if is_empty_main_frame(main_html):
            raise PimaCourtNotFoundError(normalized_case_number)
        page = parse_case_detail(main_html, response_url=BASE_URL)
        returned_number = str(page.record["raw_case_number"])
        if returned_number != normalized_case_number:
            raise PimaCourtSourceChangedError(
                "Pima Agave exact-case search returned a different case",
                code="case_number_mismatch",
                details={
                    "requested": normalized_case_number,
                    "returned": returned_number,
                    "notice": notice,
                },
            )
        return page

    def fetch_case(
        self,
        case_number: str,
        *,
        last_name: str | None = None,
        first_name: str | None = None,
    ) -> PimaCasePage:
        """Fetch a case exactly, with an optional party-index fallback."""

        normalized_case_number = normalize_case_number(case_number)
        try:
            return self._fetch_case_exact(normalized_case_number)
        except PimaCourtNotFoundError:
            if _text(last_name) is None:
                raise

        search_page = self.search_name(
            _required_text(last_name, "fallback last or business name"),
            first_name=first_name,
        )
        matching_hit = next(
            (
                hit
                for hit in search_page.hits
                if hit.raw_case_number == normalized_case_number
            ),
            None,
        )
        if matching_hit is None:
            raise PimaCourtNotFoundError(normalized_case_number)
        response = self._request(
            "GET",
            matching_hit.detail_url,
            headers={"Referer": BASE_URL},
        )
        page = parse_case_detail(response.text, response_url=response.url)
        returned_number = str(page.record["raw_case_number"])
        if returned_number != normalized_case_number:
            raise PimaCourtSourceChangedError(
                "Pima Agave party-index fallback returned a different case",
                code="case_number_mismatch",
                details={
                    "requested": normalized_case_number,
                    "returned": returned_number,
                },
            )
        return page

    def fetch_document(
        self,
        case_number: str,
        entry_id: str,
        *,
        last_name: str | None = None,
        first_name: str | None = None,
    ) -> PimaDocumentFetch:
        case_page = self.fetch_case(
            case_number,
            last_name=last_name,
            first_name=first_name,
        )
        document_url = case_page.document_urls.get(entry_id)
        if document_url is None:
            known_entry = next(
                (
                    entry
                    for entry in case_page.record["docket_entries"]
                    if entry["native_entry_id"] == entry_id
                ),
                None,
            )
            if known_entry is not None:
                raise PimaCourtSelectionError(
                    "document_not_public",
                    "The selected docket row has no public PDF link",
                    details={
                        "case_number": normalize_case_number(case_number),
                        "entry_id": entry_id,
                        "native_document_access": known_entry.get(
                            "native_document_access"
                        ),
                    },
                )
            raise PimaCourtSelectionError(
                "docket_entry_not_found",
                "The case does not contain the requested docket entry",
                details={
                    "case_number": normalize_case_number(case_number),
                    "entry_id": entry_id,
                },
            )

        response = self._request(
            "GET",
            document_url,
            headers={"Referer": BASE_URL},
        )
        content_type = str(response.headers.get("Content-Type", "")).split(
            ";",
            1,
        )[0].strip().lower()
        content = bytes(response.content)
        if content_type != "application/pdf" or not content.startswith(b"%PDF-"):
            raise PimaCourtSourceChangedError(
                "Pima Agave public document did not return a PDF",
                code="document_response_invalid",
                details={
                    "content_type": content_type,
                    "magic_hex": content[:8].hex(),
                },
            )
        disposition = Message()
        disposition["content-disposition"] = str(
            response.headers.get("Content-Disposition", "")
        )
        filename = disposition.get_filename()
        if not filename:
            filename = (
                f"{normalize_case_number(case_number)}-"
                f"{entry_id.rsplit(':', 1)[-1]}.pdf"
            )
        pdf = PimaPDF(
            content=content,
            media_type=content_type,
            filename=filename,
            sha256=hashlib.sha256(content).hexdigest(),
            etag=_text(response.headers.get("ETag")),
        )
        return PimaDocumentFetch(
            case_page=case_page,
            entry_id=entry_id,
            pdf=pdf,
        )


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    requested_limit: int | None = None
    if args.command == "search":
        parameters = {
            "last_or_business_name": args.last_name,
            "first_name": args.first_name,
        }
        requested_limit = args.limit
    elif args.command == "case":
        parameters = {
            "case_number": normalize_case_number(args.case_number),
            "fallback_last_or_business_name": args.last_name,
            "fallback_first_name": args.first_name,
        }
    elif args.command == "document":
        parameters = {
            "case_number": normalize_case_number(args.case_number),
            "entry_id": args.entry_id,
            "destination": str(args.destination),
            "fallback_last_or_business_name": args.last_name,
            "fallback_first_name": args.first_name,
        }
    elif args.command == "probe":
        parameters = {"contract": "landing-frame-search-form"}
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=COUNTY_FIPS,
            name="Pima County, Arizona",
            state_code=STATE_CODE,
            county_fips=COUNTY_FIPS,
            locality="Pima County",
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
        ),
    )


def _make_client(args: argparse.Namespace) -> PimaCourtClient:
    return PimaCourtClient(
        timeout=args.timeout,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
        minimum_interval=args.minimum_interval,
    )


def _failure_result(
    query: PublicRecordsQuery,
    error: PimaCourtError,
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


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus(acquisition_result_status(decision)),
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
        warnings=SOURCE_WARNINGS,
    )


def _execute_command(
    args: argparse.Namespace,
    client: PimaCourtClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command == "search":
        page = client.search_name(
            args.last_name,
            first_name=args.first_name,
        )
        records, source_unique_count = normalize_name_search_records(
            page.hits,
            limit=args.limit,
        )
        warnings = list(SOURCE_WARNINGS)
        if len(records) < source_unique_count:
            warnings.append(
                f"Caller limit returned {len(records)} of "
                f"{source_unique_count} unique source cases."
            )
        return PublicRecordsResult.success(
            query,
            records,
            warnings=warnings,
        )

    if args.command == "case":
        page = client.fetch_case(
            args.case_number,
            last_name=args.last_name,
            first_name=args.first_name,
        )
        return PublicRecordsResult.success(
            query,
            [page.record],
            warnings=SOURCE_WARNINGS,
        )

    if args.command == "document":
        fetch = client.fetch_document(
            args.case_number,
            args.entry_id,
            last_name=args.last_name,
            first_name=args.first_name,
        )
        destination = Path(args.destination).expanduser()
        if destination.exists() and not args.overwrite:
            raise OSError(
                f"destination exists; pass --overwrite: {destination}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(fetch.pdf.content)

        record = copy.deepcopy(dict(fetch.case_page.record))
        selected_entry: dict[str, Any] | None = None
        for entry in record["docket_entries"]:
            if entry["native_entry_id"] == fetch.entry_id:
                selected_entry = entry
                break
        if selected_entry is None:
            raise PimaCourtSourceChangedError(
                "Downloaded docket entry disappeared during normalization",
                code="download_entry_missing",
            )
        document = selected_entry["documents"][0]
        document.update(
            {
                "sha256": fetch.pdf.sha256,
                "mime_type": fetch.pdf.media_type,
                "storage_path": str(destination.resolve()),
                "filename": fetch.pdf.filename,
                "size_bytes": len(fetch.pdf.content),
                "etag": fetch.pdf.etag,
                "acquired": True,
            }
        )
        record["docket_entries"] = [selected_entry]
        record["document_download"] = {
            "entry_id": fetch.entry_id,
            "filename": fetch.pdf.filename,
            "size_bytes": len(fetch.pdf.content),
            "sha256": fetch.pdf.sha256,
            "mime_type": fetch.pdf.media_type,
            "etag": fetch.pdf.etag,
            "storage_path": str(destination.resolve()),
        }
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=[str(destination.resolve())],
            warnings=SOURCE_WARNINGS,
        )

    if args.command == "probe":
        form = client.bootstrap()
        record = {
            "record_kind": "source_probe",
            "source_id": SOURCE_ID,
            "official_linking_page": OFFICIAL_LINKING_PAGE,
            "base_url": BASE_URL,
            "search_method": "POST",
            "search_path": urlsplit(form.search_url).path,
            "aspnet_hidden_fields": sorted(form.hidden_fields),
            "session_bound_navigation": True,
            "platform_family": PLATFORM_FAMILY,
        }
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )

    raise ValueError(f"unsupported Pima court command: {args.command}")


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: PimaCourtClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute one Pima County court operation."""

    query = build_query(args)
    if access_decision is not None and not access_decision.get(
        "allowed", False
    ):
        result = _decision_failure(query, access_decision)
        log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result
    source_client = client or _make_client(args)
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except PimaCourtNotFoundError:
        result = PublicRecordsResult.success(
            query,
            [],
            warnings=SOURCE_WARNINGS,
        )
    except PimaCourtError as error:
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
        summary=f"Pima County courts {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Pima County courts {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        if record.get("record_kind") == "case":
            print(
                f"  {record.get('raw_case_number') or '?'} | "
                f"{record.get('filing_date') or '?'} | "
                f"{record.get('caption') or '?'}"
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
        help="Maximum attempts for transient source failures",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query the official Pima County Superior Court Agave "
            "Public Record Search"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Search cases by party last name or business name",
    )
    search.add_argument("last_name", help="Last name or business name")
    search.add_argument("--first-name", help="Optional party first name")
    search.add_argument(
        "--limit",
        type=_positive_int,
        default=100,
        help="Maximum unique cases to return",
    )
    _add_runtime_and_output(search)

    case = subparsers.add_parser(
        "case",
        help="Fetch one case by exact case number",
    )
    case.add_argument("case_number")
    case.add_argument(
        "--last-name",
        help=(
            "Party last or business name used only if Agave's exact-case "
            "index does not resolve the case"
        ),
    )
    case.add_argument(
        "--first-name",
        help="Optional first name for the party-index fallback",
    )
    _add_runtime_and_output(case)

    document = subparsers.add_parser(
        "document",
        help="Fetch a public PDF by case number and emitted docket entry ID",
    )
    document.add_argument("case_number")
    document.add_argument("entry_id")
    document.add_argument("destination")
    document.add_argument(
        "--last-name",
        help=(
            "Party last or business name used only if Agave's exact-case "
            "index does not resolve the case"
        ),
    )
    document.add_argument(
        "--first-name",
        help="Optional first name for the party-index fallback",
    )
    document.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing destination",
    )
    _add_runtime_and_output(document)

    probe = subparsers.add_parser(
        "probe",
        help="Verify the landing frame and stable search-form contract",
    )
    _add_runtime_and_output(probe)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
