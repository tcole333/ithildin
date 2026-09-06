#!/usr/bin/env python3
"""Query Ohio's official Reporter of Decisions publication index.

The Reporter of Decisions search publishes opinions and case announcements
from the Supreme Court of Ohio, the twelve district courts of appeals, the
Court of Claims, and miscellaneous Reporter material.  It is a publication
index rather than a statewide docket.  This adapter submits the source's
ASP.NET WebForms search, exhausts its native GridView pages, and keeps a
publication's WebCite identity separate from its optional case number and PDF
representation.

Examples:
    uv run python tools/query_ohio_reporter_decisions.py source --json
    uv run python tools/query_ohio_reporter_decisions.py search \
        --source supreme --year 2026 --output /tmp/ohio-rod.json
    uv run python tools/query_ohio_reporter_decisions.py search \
        --source district-1 --case-number C-250425 --json
    uv run python tools/query_ohio_reporter_decisions.py publication \
        2018-Ohio-723 --json
    uv run python tools/query_ohio_reporter_decisions.py document \
        2018-Ohio-723 /tmp/2018-Ohio-723.pdf --json
    uv run python tools/query_ohio_reporter_decisions.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin, urlsplit

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


SOURCE_ID = "us-oh-reporter-of-decisions"
SOURCE_NAME = "Ohio Reporter of Decisions Opinions and Announcements"
STATE_CODE = "OH"
STATE_GEOID = "39"
OBSERVED_AT = "2026-07-30"

BASE_URL = "https://www.supremecourt.ohio.gov/ROD/docs/Default.aspx"
HELP_URL = "https://www.supremecourt.ohio.gov/ROD/docs/Help.aspx"
EXPECTED_HOST = "www.supremecourt.ohio.gov"
EXPECTED_SEARCH_PATH = "/rod/docs/default.aspx"
EXPECTED_PDF_PREFIX = "/rod/docs/pdf/"
PLATFORM_FAMILY = "aspnet_webforms_gridview"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_MAX_RETRIES = 2
NATIVE_PAGE_SIZE = 200
FULL_TEXT_RESULT_BOUNDARY = 1000
PAGER_EVENT_TARGET = "ctl00$MainContent$gvResults"
FIELD_PREFIX = "ctl00$MainContent$"
CURSOR_PREFIX = "ohio-reporter-decisions:v1:"

PROBE_WEBCITE = "2018-Ohio-723"
PROBE_YEAR = 2026

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)

_ROW_COUNT_RE = re.compile(
    r"^This search returned (?P<count>\d[\d,]*) rows?\.$"
)
_WEBCITE_RE = re.compile(
    r"^(?P<year>\d{4})-Ohio-(?P<number>\d{1,4})$",
    re.IGNORECASE,
)
_PDF_PATH_RE = re.compile(
    r"^/rod/docs/pdf/(?P<source>\d{1,3})/(?P<year>\d{4})/"
    r"(?P<webcite>\d{4}-Ohio-\d{1,4})\.pdf$",
    re.IGNORECASE,
)
_PAGE_ARGUMENT_RE = re.compile(r"Page\$(?P<page>\d+|Last)")

_FORM_FIELDS = {
    "query_text": f"{FIELD_PREFIX}tbQueryText",
    "court": f"{FIELD_PREFIX}ddlCourt",
    "year_from": f"{FIELD_PREFIX}ddlDecidedYearMin",
    "year_to": f"{FIELD_PREFIX}ddlDecidedYearMax",
    "county": f"{FIELD_PREFIX}ddlCounty",
    "case_number": f"{FIELD_PREFIX}tbCaseNumber",
    "author": f"{FIELD_PREFIX}tbAuthor",
    "topics": f"{FIELD_PREFIX}tbTopics",
    "webcite_year": f"{FIELD_PREFIX}tbWebCiteYear",
    "webcite_number": f"{FIELD_PREFIX}tbWebCiteNumber",
    "citation": f"{FIELD_PREFIX}tbCitation",
    "rows_per_page": f"{FIELD_PREFIX}ddlRowsPerPage",
}
_SELECT_FIELDS = frozenset(
    {
        _FORM_FIELDS["court"],
        _FORM_FIELDS["year_from"],
        _FORM_FIELDS["year_to"],
        _FORM_FIELDS["county"],
        _FORM_FIELDS["rows_per_page"],
    }
)
_TEXT_FIELDS = frozenset(
    {
        _FORM_FIELDS["query_text"],
        _FORM_FIELDS["case_number"],
        _FORM_FIELDS["author"],
        _FORM_FIELDS["topics"],
        _FORM_FIELDS["webcite_year"],
        _FORM_FIELDS["webcite_number"],
        _FORM_FIELDS["citation"],
    }
)
_EXPECTED_HEADERS = (
    "Case Caption",
    "Case No.",
    "Topics and Issues",
    "Author",
    "Citation / County",
    "Decided",
    "Posted",
    "WebCite",
)


COURT_SOURCES: dict[str, dict[str, str]] = {
    "0": {
        "slug": "supreme",
        "court_id": "oh-supreme-court",
        "name": "Supreme Court of Ohio",
    },
    **{
        str(number): {
            "slug": f"district-{number}",
            "court_id": f"oh-court-of-appeals-district-{number}",
            "name": (
                f"{ordinal} District Court of Appeals"
            ),
        }
        for number, ordinal in (
            (1, "First"),
            (2, "Second"),
            (3, "Third"),
            (4, "Fourth"),
            (5, "Fifth"),
            (6, "Sixth"),
            (7, "Seventh"),
            (8, "Eighth"),
            (9, "Ninth"),
            (10, "Tenth"),
            (11, "Eleventh"),
            (12, "Twelfth"),
        )
    },
    "13": {
        "slug": "court-of-claims",
        "court_id": "oh-court-of-claims",
        "name": "Court of Claims",
    },
    "98": {
        "slug": "miscellaneous",
        "court_id": "oh-reporter-miscellaneous",
        "name": "Miscellaneous",
    },
}

QUERY_SOURCES: dict[str, dict[str, str]] = {
    **COURT_SOURCES,
    "99": {
        "slug": "all",
        "court_id": "oh-all-reporter-sources",
        "name": "All Sources",
    },
    "100": {
        "slug": "all-districts",
        "court_id": "oh-all-appellate-districts",
        "name": "All District Courts",
    },
}
SOURCE_CODE_BY_SLUG = {
    details["slug"]: code for code, details in QUERY_SOURCES.items()
}

SOURCE_WARNINGS = (
    "This is the official Ohio judicial publication index for opinions and "
    "case announcements, not a statewide docket or a repository of every "
    "party filing.",
    "WebCite identifies the posted decision or announcement. Case number is "
    "an optional join key and the linked PDF is a separate document "
    "representation.",
    "Reporter publications, eCMS docket entries, Clerk's Journal orders, and "
    "district-court copies can describe the same judicial act; those "
    "representations are complementary access paths rather than independent "
    "corroboration.",
)


class OhioReporterError(RuntimeError):
    """Source, transport, or selection error with result semantics."""

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


class OhioReporterSelectionError(OhioReporterError):
    """The caller supplied an unsupported source-native selector."""

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


class OhioReporterTransportError(OhioReporterError):
    """The official source could not be reached after bounded retries."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "transport_error",
            message,
            category="transport",
            retryable=True,
        )


class OhioReporterHTTPError(OhioReporterError):
    """The official source returned a non-success status."""

    def __init__(self, status_code: int, url: str) -> None:
        status = (
            ResultStatus.RESTRICTED
            if status_code in {401, 403}
            else ResultStatus.RATE_LIMITED
            if status_code == 429
            else ResultStatus.UNAVAILABLE
        )
        super().__init__(
            f"http_{status_code}",
            f"Ohio Reporter of Decisions returned HTTP {status_code}",
            status=status,
            category="http",
            retryable=status_code == 429 or status_code >= 500,
            details={
                "status_code": status_code,
                "url": url,
                "access_characterization": "observed_response_not_policy",
            },
        )


class OhioReporterSourceChanged(OhioReporterError):
    """A verified host, route, media type, form, or result shape changed."""

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


class OhioReporterRefinementRequired(OhioReporterError):
    """The source rejected a selector combination and displayed guidance."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "source_requires_refinement",
            message,
            category="source_validation",
            details={
                "source_response": message,
                "authoritative_empty": False,
            },
        )


class OhioReporterPaginationError(OhioReporterError):
    """Native pagination became incomplete after at least one page."""

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "native_pagination_incomplete",
            message,
            status=ResultStatus.PARTIAL,
            category="source_pagination",
            details=details,
        )


@dataclass(frozen=True)
class ReporterPage:
    """One parsed native GridView page and its postback state."""

    records: tuple[dict[str, Any], ...]
    total_rows: int
    page_number: int
    page_size: int
    total_pages: int
    selected_values: Mapping[str, str]
    selected_labels: Mapping[str, str]
    options: Mapping[str, Mapping[str, str]]
    postback_values: Mapping[str, str]
    selection_snapshot: Mapping[str, str]
    schema_fingerprint: str
    state_fingerprint: str
    source_url: str


@dataclass(frozen=True)
class ReporterCollection:
    """An exhaustive or explicitly partial WebForms traversal."""

    records: tuple[dict[str, Any], ...]
    total_rows: int
    page_size: int
    total_pages: int
    pages_fetched: int
    selected_values: Mapping[str, str]
    selected_labels: Mapping[str, str]
    source_urls: tuple[str, ...]
    schema_fingerprints: tuple[str, ...]
    incomplete_error: OhioReporterError | None = None


@dataclass(frozen=True)
class ReporterPDF:
    """Validated bytes for one official publication PDF."""

    content: bytes
    source_url: str
    final_url: str
    webcite: str
    source_code: str
    court_id: str
    court_name: str
    media_type: str
    sha256: str


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _nonblank(value: str) -> str:
    normalized = _clean(value)
    if not normalized:
        raise argparse.ArgumentTypeError("value must not be blank")
    return normalized


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be an integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _nonnegative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be an integer") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def normalize_webcite(value: str) -> str:
    """Return the source's canonical ``YYYY-Ohio-N`` publication identity."""

    candidate = _clean(value)
    match = _WEBCITE_RE.fullmatch(candidate)
    if not match:
        raise OhioReporterSelectionError(
            "invalid_webcite",
            "WebCite must use the form YYYY-Ohio-N",
            details={"value": candidate},
        )
    return f"{match.group('year')}-Ohio-{int(match.group('number'))}"


def _iso_date(value: str) -> str | None:
    candidate = _clean(value)
    if not candidate:
        return None
    try:
        return datetime.strptime(candidate, "%m/%d/%Y").date().isoformat()
    except ValueError as error:
        raise OhioReporterSourceChanged(
            "publication_date_changed",
            "Ohio Reporter publication date changed format",
            details={"value": candidate},
        ) from error


def _validate_https_host(value: str, *, label: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme.casefold() != "https"
        or (parsed.hostname or "").casefold() != EXPECTED_HOST
    ):
        raise OhioReporterSourceChanged(
            "official_host_changed",
            f"{label} resolved outside the verified official HTTPS host",
            details={"url": value},
        )
    return value


def _parse_pdf_url(
    value: str,
    *,
    expected_webcite: str | None = None,
    expected_source_code: str | None = None,
) -> dict[str, str]:
    url = _validate_https_host(value, label="Publication PDF")
    parsed = urlsplit(url)
    match = _PDF_PATH_RE.fullmatch(parsed.path)
    if not match or parsed.query or parsed.fragment:
        raise OhioReporterSourceChanged(
            "publication_pdf_route_changed",
            "Ohio Reporter result no longer links the verified PDF route",
            details={"url": value},
        )
    source_code = match.group("source")
    if source_code not in COURT_SOURCES:
        raise OhioReporterSourceChanged(
            "publication_source_code_changed",
            "Ohio Reporter PDF uses an unknown source code",
            details={"source_code": source_code, "url": value},
        )
    webcite = normalize_webcite(match.group("webcite"))
    if match.group("year") != webcite[:4]:
        raise OhioReporterSourceChanged(
            "publication_pdf_year_mismatch",
            "Ohio Reporter PDF directory and WebCite years differ",
            details={"url": value, "webcite": webcite},
        )
    if expected_webcite and webcite != normalize_webcite(expected_webcite):
        raise OhioReporterSourceChanged(
            "publication_pdf_identity_mismatch",
            "Ohio Reporter PDF route identifies another publication",
            details={
                "expected_webcite": normalize_webcite(expected_webcite),
                "observed_webcite": webcite,
                "url": value,
            },
        )
    if expected_source_code and source_code != expected_source_code:
        raise OhioReporterSourceChanged(
            "publication_pdf_source_mismatch",
            "Ohio Reporter PDF route identifies another deciding source",
            details={
                "expected_source_code": expected_source_code,
                "observed_source_code": source_code,
                "url": value,
            },
        )
    return {
        "source_code": source_code,
        "year": match.group("year"),
        "webcite": webcite,
        "path": parsed.path,
    }


def _document_ref(court_id: str, webcite: str) -> str:
    return canonical_court_ref(
        SOURCE_ID,
        court_id,
        webcite,
        "document",
        native_id=f"{webcite}.pdf",
    )


def _normalize_row(cells: Sequence[Any], *, search_url: str) -> dict[str, Any]:
    if len(cells) != len(_EXPECTED_HEADERS):
        raise OhioReporterSourceChanged(
            "result_column_count_changed",
            "Ohio Reporter result row changed column count",
            details={"observed": len(cells)},
        )
    anchor = cells[0].find("a", href=True)
    if anchor is None:
        raise OhioReporterSourceChanged(
            "publication_link_missing",
            "Ohio Reporter result row lacks its publication PDF link",
        )
    pdf_url = urljoin(search_url, str(anchor.get("href")))
    pdf_identity = _parse_pdf_url(pdf_url)
    webcite = normalize_webcite(cells[7].get_text(" ", strip=True))
    if webcite != pdf_identity["webcite"]:
        raise OhioReporterSourceChanged(
            "result_webcite_mismatch",
            "Ohio Reporter WebCite cell and PDF link disagree",
            details={
                "cell_webcite": webcite,
                "pdf_webcite": pdf_identity["webcite"],
            },
        )

    source_code = pdf_identity["source_code"]
    court = COURT_SOURCES[source_code]
    caption = _clean(cells[0].get_text(" ", strip=True))
    case_number = _clean(cells[1].get_text(" ", strip=True)) or None
    topics = _clean(cells[2].get_text(" ", strip=True)) or None
    author = _clean(cells[3].get_text(" ", strip=True)) or None
    citation_or_county = _clean(cells[4].get_text(" ", strip=True)) or None
    decided_raw = _clean(cells[5].get_text(" ", strip=True))
    posted_raw = _clean(cells[6].get_text(" ", strip=True))
    publication_ref = canonical_court_ref(
        SOURCE_ID,
        court["court_id"],
        webcite,
        "publication",
    )
    record: dict[str, Any] = {
        "canonical_ref": publication_ref,
        "source_id": SOURCE_ID,
        "record_kind": "judicial_publication",
        "publication_identity": webcite,
        "webcite": webcite,
        "court_id": court["court_id"],
        "court_name": court["name"],
        "source_native_court_code": source_code,
        "source_native_court_label": court["name"],
        "caption": caption,
        "case_number": case_number,
        "topics_and_issues": topics,
        "author": author,
        "citation_or_county": citation_or_county,
        "decided_date": _iso_date(decided_raw),
        "decided_date_raw": decided_raw or None,
        "posted_date": _iso_date(posted_raw),
        "posted_date_raw": posted_raw or None,
        "document_ref": _document_ref(court["court_id"], webcite),
        "native_document_id": f"{webcite}.pdf",
        "document_url": pdf_url,
        "document_media_type": "application/pdf",
        "search_url": search_url,
        "identity": {
            "publication": "WebCite",
            "case_number_role": "optional_case_join",
            "document": "WebCite plus official PDF representation",
        },
    }
    if source_code == "0":
        record["print_citation"] = citation_or_county
    elif source_code in {str(number) for number in range(1, 13)}:
        record["county"] = citation_or_county
    return record


def _selected_option(select: Any) -> Any:
    return select.find("option", selected=True) or select.find("option")


def _form_contract(soup: BeautifulSoup, *, source_url: str) -> tuple[
    dict[str, str],
    dict[str, str],
    dict[str, dict[str, str]],
    dict[str, str],
]:
    form = soup.select_one("form#Form1")
    if form is None:
        raise OhioReporterSourceChanged(
            "search_form_missing",
            "Ohio Reporter response lacks the verified search form",
        )
    method = _clean(form.get("method")).casefold()
    action = urljoin(source_url, str(form.get("action") or ""))
    if method != "post" or urlsplit(action).path.casefold() != (
        EXPECTED_SEARCH_PATH
    ):
        raise OhioReporterSourceChanged(
            "search_form_action_changed",
            "Ohio Reporter search form action or method changed",
            details={"method": method, "action": action},
        )

    hidden = {
        str(node.get("name")): str(node.get("value") or "")
        for node in form.select("input[type=hidden][name]")
    }
    if not hidden.get("__VIEWSTATE") or not hidden.get(
        "__VIEWSTATEGENERATOR"
    ):
        raise OhioReporterSourceChanged(
            "webforms_state_missing",
            "Ohio Reporter response lacks required WebForms state",
        )

    selected_values: dict[str, str] = {}
    selected_labels: dict[str, str] = {}
    options: dict[str, dict[str, str]] = {}
    for field_name in _SELECT_FIELDS:
        select = form.find("select", attrs={"name": field_name})
        if select is None:
            raise OhioReporterSourceChanged(
                "search_control_missing",
                "Ohio Reporter response lacks a verified select control",
                details={"field": field_name},
            )
        field_options = {
            str(option.get("value") or ""): _clean(option.get_text(" "))
            for option in select.find_all("option")
        }
        chosen = _selected_option(select)
        if chosen is None:
            raise OhioReporterSourceChanged(
                "search_control_selection_missing",
                "Ohio Reporter select control has no option",
                details={"field": field_name},
            )
        selected_values[field_name] = str(chosen.get("value") or "")
        selected_labels[field_name] = _clean(chosen.get_text(" "))
        options[field_name] = field_options

    text_values: dict[str, str] = {}
    for field_name in _TEXT_FIELDS:
        node = form.find("input", attrs={"name": field_name})
        if node is None:
            raise OhioReporterSourceChanged(
                "search_control_missing",
                "Ohio Reporter response lacks a verified text control",
                details={"field": field_name},
            )
        text_values[field_name] = str(node.get("value") or "")

    postback_values = dict(hidden)
    postback_values.update(selected_values)
    postback_values.update(text_values)
    for checkbox in form.select(
        "input[type=checkbox][name][checked],"
        "input[type=radio][name][checked]"
    ):
        postback_values[str(checkbox.get("name"))] = str(
            checkbox.get("value") or "on"
        )
    for textarea in form.select("textarea[name]"):
        postback_values[str(textarea.get("name"))] = textarea.get_text()

    return (
        selected_values,
        selected_labels,
        options,
        postback_values,
    )


def _validate_source_options(options: Mapping[str, Mapping[str, str]]) -> None:
    court_options = options[_FORM_FIELDS["court"]]
    for code, details in QUERY_SOURCES.items():
        if court_options.get(code) != details["name"]:
            raise OhioReporterSourceChanged(
                "court_source_vocabulary_changed",
                "Ohio Reporter court-source vocabulary changed",
                details={
                    "source_code": code,
                    "expected": details["name"],
                    "observed": court_options.get(code),
                },
            )
    rows_options = options[_FORM_FIELDS["rows_per_page"]]
    if rows_options.get(str(NATIVE_PAGE_SIZE)) != str(NATIVE_PAGE_SIZE):
        raise OhioReporterSourceChanged(
            "native_page_size_changed",
            "Ohio Reporter no longer offers its verified 200-row page size",
            details={"options": dict(rows_options)},
        )
    county_options = options[_FORM_FIELDS["county"]]
    if county_options.get("0") != "All counties":
        raise OhioReporterSourceChanged(
            "county_vocabulary_changed",
            "Ohio Reporter all-counties selector changed",
            details={"observed": county_options.get("0")},
        )
    for field_name in (
        _FORM_FIELDS["year_from"],
        _FORM_FIELDS["year_to"],
    ):
        values = options[field_name]
        if not values or any(
            not value.isdigit() or len(value) != 4 for value in values
        ):
            raise OhioReporterSourceChanged(
                "year_vocabulary_changed",
                "Ohio Reporter decision-year vocabulary changed",
                details={"field": field_name, "values": list(values)},
            )


def _visible_year_warning(soup: BeautifulSoup) -> str | None:
    warning = soup.select_one("#MainContent_tbYearRangeWarnContent")
    if warning is None:
        raise OhioReporterSourceChanged(
            "year_validation_control_missing",
            "Ohio Reporter response lacks its year-range validation control",
        )
    classes = {str(value) for value in (warning.get("class") or [])}
    if "noShow" in classes:
        return None
    return _clean(warning.get_text(" "))


def parse_search_page(
    html: str,
    *,
    source_url: str = BASE_URL,
    expected_page: int = 1,
) -> ReporterPage:
    """Parse and validate one official WebForms result page."""

    _validate_https_host(source_url, label="Search response")
    if urlsplit(source_url).path.casefold() != EXPECTED_SEARCH_PATH:
        raise OhioReporterSourceChanged(
            "search_response_route_changed",
            "Ohio Reporter search response resolved outside Default.aspx",
            details={"source_url": source_url},
        )
    soup = BeautifulSoup(html, "html.parser")
    title = _clean(soup.title.get_text(" ") if soup.title else "")
    if title != "Opinion Search":
        raise OhioReporterSourceChanged(
            "search_page_title_changed",
            "Ohio Reporter response is not the verified opinion-search page",
            details={"title": title},
        )
    (
        selected_values,
        selected_labels,
        options,
        postback_values,
    ) = _form_contract(soup, source_url=source_url)
    _validate_source_options(options)

    warning = _visible_year_warning(soup)
    if warning:
        raise OhioReporterRefinementRequired(warning)

    row_count = soup.select_one("#MainContent_lblRowCount")
    row_count_text = _clean(
        row_count.get_text(" ") if row_count is not None else ""
    )
    match = _ROW_COUNT_RE.fullmatch(row_count_text)
    if not match:
        raise OhioReporterSourceChanged(
            "result_count_changed",
            "Ohio Reporter response lacks its verified result count",
            details={"text": row_count_text},
        )
    total_rows = int(match.group("count").replace(",", ""))
    try:
        page_size = int(selected_values[_FORM_FIELDS["rows_per_page"]])
    except (KeyError, ValueError) as error:
        raise OhioReporterSourceChanged(
            "native_page_size_invalid",
            "Ohio Reporter selected page size is not an integer",
        ) from error
    if page_size <= 0:
        raise OhioReporterSourceChanged(
            "native_page_size_invalid",
            "Ohio Reporter selected page size is not positive",
        )
    total_pages = math.ceil(total_rows / page_size) if total_rows else 0
    if expected_page < 1 or (
        total_pages and expected_page > total_pages
    ):
        raise OhioReporterSourceChanged(
            "requested_page_out_of_range",
            "Ohio Reporter page traversal requested an invalid native page",
            details={
                "expected_page": expected_page,
                "total_pages": total_pages,
            },
        )

    table = soup.select_one("#MainContent_gvResults")
    records: list[dict[str, Any]] = []
    observed_headers: tuple[str, ...] | None = None
    active_pages: set[int] = set()
    page_arguments: set[str] = set()
    if table is not None:
        for header_row in table.find_all("tr", recursive=False):
            headers = header_row.find_all("th", recursive=False)
            if headers:
                observed_headers = tuple(
                    _clean(header.get_text(" ")) for header in headers
                )
                break
        for row in table.find_all("tr", recursive=False):
            cells = row.find_all("td", recursive=False)
            if len(cells) == len(_EXPECTED_HEADERS):
                records.append(
                    _normalize_row(cells, search_url=source_url)
                )
            if (
                len(cells) == 1
                and str(cells[0].get("colspan") or "") == "8"
            ):
                for span in cells[0].find_all("span"):
                    value = _clean(span.get_text(" "))
                    if value.isdigit():
                        active_pages.add(int(value))
                for anchor in cells[0].find_all("a", href=True):
                    pager_match = _PAGE_ARGUMENT_RE.search(
                        str(anchor.get("href"))
                    )
                    if pager_match:
                        page_arguments.add(pager_match.group("page"))

    if total_rows:
        if observed_headers != _EXPECTED_HEADERS:
            raise OhioReporterSourceChanged(
                "result_headers_changed",
                "Ohio Reporter result headers changed",
                details={
                    "expected": list(_EXPECTED_HEADERS),
                    "observed": list(observed_headers or ()),
                },
            )
    elif records:
        raise OhioReporterSourceChanged(
            "empty_result_contains_rows",
            "Ohio Reporter reported zero rows but returned result records",
        )

    expected_count = (
        min(
            page_size,
            total_rows - ((expected_page - 1) * page_size),
        )
        if total_rows
        else 0
    )
    if len(records) != expected_count:
        raise OhioReporterSourceChanged(
            "native_page_row_count_mismatch",
            "Ohio Reporter native page did not contain the expected rows",
            details={
                "page": expected_page,
                "expected_rows": expected_count,
                "observed_rows": len(records),
                "total_rows": total_rows,
                "page_size": page_size,
            },
        )
    if total_pages > 1:
        if active_pages != {expected_page}:
            raise OhioReporterSourceChanged(
                "native_page_position_changed",
                "Ohio Reporter pager does not identify the requested page",
                details={
                    "expected_page": expected_page,
                    "observed_active_pages": sorted(active_pages),
                },
            )
        if expected_page < total_pages and not page_arguments:
            raise OhioReporterSourceChanged(
                "native_pager_missing",
                "Ohio Reporter omitted native pagination links",
                details={"page": expected_page, "total_pages": total_pages},
            )

    identities = [record["webcite"] for record in records]
    if len(set(identities)) != len(identities):
        raise OhioReporterSourceChanged(
            "duplicate_publication_on_page",
            "Ohio Reporter repeated a WebCite on one native page",
        )

    selection_snapshot = {
        field_name: (
            selected_values.get(field_name)
            if field_name in _SELECT_FIELDS
            else postback_values.get(field_name, "")
        )
        for field_name in (*sorted(_SELECT_FIELDS), *sorted(_TEXT_FIELDS))
    }
    schema_fingerprint = hashlib.sha256(
        canonical_json(
            {
                "headers": _EXPECTED_HEADERS,
                "court_options": options[_FORM_FIELDS["court"]],
                "form_fields": sorted(_FORM_FIELDS.values()),
            }
        ).encode("utf-8")
    ).hexdigest()
    state_fingerprint = hashlib.sha256(
        canonical_json(
            {
                key: value
                for key, value in postback_values.items()
                if key.startswith("__")
            }
        ).encode("utf-8")
    ).hexdigest()
    return ReporterPage(
        records=tuple(records),
        total_rows=total_rows,
        page_number=expected_page,
        page_size=page_size,
        total_pages=total_pages,
        selected_values=selected_values,
        selected_labels=selected_labels,
        options=options,
        postback_values=postback_values,
        selection_snapshot=selection_snapshot,
        schema_fingerprint=schema_fingerprint,
        state_fingerprint=state_fingerprint,
        source_url=source_url,
    )


def _option_value(
    options: Mapping[str, str],
    requested: str,
    *,
    label: str,
) -> str:
    candidate = _clean(requested)
    if candidate in options:
        return candidate
    matches = [
        value
        for value, name in options.items()
        if _clean(name).casefold() == candidate.casefold()
    ]
    if len(matches) == 1:
        return matches[0]
    raise OhioReporterSelectionError(
        f"invalid_{label}",
        f"Ohio Reporter does not publish a {label} option matching {candidate!r}",
        details={
            "requested": candidate,
            "available": dict(options),
        },
    )


def _resolved_search_values(
    landing: ReporterPage,
    selection: Mapping[str, Any],
) -> dict[str, str]:
    court_code = str(selection.get("court_code") or "0")
    court_options = landing.options[_FORM_FIELDS["court"]]
    if court_code not in court_options:
        raise OhioReporterSelectionError(
            "invalid_source",
            "Ohio Reporter does not publish the requested source option",
            details={"source_code": court_code},
        )

    from_options = landing.options[_FORM_FIELDS["year_from"]]
    to_options = landing.options[_FORM_FIELDS["year_to"]]
    year = selection.get("year")
    year_from = selection.get("year_from")
    year_to = selection.get("year_to")
    if year is not None:
        if year_from is not None or year_to is not None:
            raise OhioReporterSelectionError(
                "conflicting_year_selectors",
                "--year cannot be combined with --year-from or --year-to",
            )
        year_from = year
        year_to = year
    if year_from is None and year_to is not None:
        year_from = min(from_options, key=int)
    if year_to is None and year_from is not None:
        year_to = max(to_options, key=int)
    resolved_from = str(
        year_from
        if year_from is not None
        else landing.selected_values[_FORM_FIELDS["year_from"]]
    )
    resolved_to = str(
        year_to
        if year_to is not None
        else landing.selected_values[_FORM_FIELDS["year_to"]]
    )
    if resolved_from not in from_options or resolved_to not in to_options:
        raise OhioReporterSelectionError(
            "invalid_decision_year",
            "Requested decision year is outside the source vocabulary",
            details={
                "year_from": resolved_from,
                "year_to": resolved_to,
                "available_from": list(from_options),
                "available_to": list(to_options),
            },
        )
    if int(resolved_to) < int(resolved_from):
        raise OhioReporterSelectionError(
            "invalid_year_range",
            "Decision-year end precedes decision-year start",
            details={
                "year_from": resolved_from,
                "year_to": resolved_to,
            },
        )

    county = str(selection.get("county") or "0")
    county_value = _option_value(
        landing.options[_FORM_FIELDS["county"]],
        county,
        label="county",
    )
    return {
        _FORM_FIELDS["query_text"]: _clean(selection.get("query_text")),
        _FORM_FIELDS["court"]: court_code,
        _FORM_FIELDS["year_from"]: resolved_from,
        _FORM_FIELDS["year_to"]: resolved_to,
        _FORM_FIELDS["county"]: county_value,
        _FORM_FIELDS["case_number"]: _clean(selection.get("case_number")),
        _FORM_FIELDS["author"]: _clean(selection.get("author")),
        _FORM_FIELDS["topics"]: _clean(selection.get("topics")),
        _FORM_FIELDS["webcite_year"]: _clean(
            selection.get("webcite_year")
        ),
        _FORM_FIELDS["webcite_number"]: _clean(
            selection.get("webcite_number")
        ),
        _FORM_FIELDS["citation"]: _clean(selection.get("citation")),
        _FORM_FIELDS["rows_per_page"]: str(NATIVE_PAGE_SIZE),
    }


class OhioReporterClient:
    """Requests-compatible client for the verified WebForms source."""

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
        """Close only a session created by this client."""

        if self._owns_session and hasattr(self.session, "close"):
            self.session.close()

    def __enter__(self) -> OhioReporterClient:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        for attempt in range(self.max_retries + 1):
            if (
                self.request_budget is not None
                and self.request_count >= self.request_budget
            ):
                raise OhioReporterSelectionError(
                    "request_budget_exhausted",
                    "Ohio Reporter request budget was exhausted",
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
                raise OhioReporterTransportError(
                    f"Ohio Reporter request failed: {error}"
                ) from error

            final_url = str(getattr(response, "url", url))
            _validate_https_host(final_url, label="Ohio Reporter response")
            status_code = int(response.status_code)
            if (
                status_code == 429 or status_code >= 500
            ) and attempt < self.max_retries:
                self._sleeper(0.5 * (2**attempt))
                continue
            if status_code < 200 or status_code >= 300:
                raise OhioReporterHTTPError(status_code, final_url)
            return response
        raise OhioReporterTransportError(
            "Ohio Reporter request exhausted retries"
        )

    def _html_page(
        self,
        response: Any,
        *,
        expected_page: int,
    ) -> ReporterPage:
        media_type = (
            str(response.headers.get("Content-Type", ""))
            .split(";", 1)[0]
            .strip()
            .casefold()
        )
        if media_type != "text/html":
            raise OhioReporterSourceChanged(
                "search_media_type_changed",
                "Ohio Reporter search did not return HTML",
                details={"content_type": media_type},
            )
        return parse_search_page(
            str(response.text),
            source_url=str(response.url),
            expected_page=expected_page,
        )

    def landing(self) -> ReporterPage:
        response = self._request(
            "GET",
            BASE_URL,
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        return self._html_page(response, expected_page=1)

    def _submit_first(
        self,
        selection: Mapping[str, Any],
    ) -> ReporterPage:
        landing = self.landing()
        values = _resolved_search_values(landing, selection)
        payload = dict(landing.postback_values)
        payload.update(values)
        payload["__EVENTTARGET"] = ""
        payload["__EVENTARGUMENT"] = ""
        payload[f"{FIELD_PREFIX}btnSubmit"] = "Submit"
        response = self._request(
            "POST",
            BASE_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://www.supremecourt.ohio.gov",
                "Referer": BASE_URL,
            },
            data=payload,
        )
        page = self._html_page(response, expected_page=1)
        for field_name, expected_value in values.items():
            observed = page.selection_snapshot.get(field_name)
            if observed != expected_value:
                raise OhioReporterSourceChanged(
                    "search_selection_not_preserved",
                    "Ohio Reporter response did not preserve a submitted selector",
                    details={
                        "field": field_name,
                        "expected": expected_value,
                        "observed": observed,
                    },
                )
        return page

    def _postback_page(
        self,
        previous: ReporterPage,
        page_number: int,
    ) -> ReporterPage:
        payload = dict(previous.postback_values)
        payload.pop(f"{FIELD_PREFIX}btnSubmit", None)
        payload["__EVENTTARGET"] = PAGER_EVENT_TARGET
        payload["__EVENTARGUMENT"] = f"Page${page_number}"
        response = self._request(
            "POST",
            BASE_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://www.supremecourt.ohio.gov",
                "Referer": BASE_URL,
            },
            data=payload,
        )
        return self._html_page(response, expected_page=page_number)

    def fetch_all(
        self,
        selection: Mapping[str, Any],
    ) -> ReporterCollection:
        first = self._submit_first(selection)
        pages = [first]
        state_fingerprints = {first.state_fingerprint}
        incomplete_error: OhioReporterError | None = None
        previous = first
        for page_number in range(2, first.total_pages + 1):
            try:
                page = self._postback_page(previous, page_number)
            except OhioReporterError as error:
                incomplete_error = OhioReporterPaginationError(
                    "Ohio Reporter native pagination stopped before all "
                    "pages were collected",
                    details={
                        "failed_page": page_number,
                        "underlying_code": error.code,
                        "underlying_message": str(error),
                    },
                )
                break
            if (
                page.total_rows != first.total_rows
                or page.page_size != first.page_size
                or page.total_pages != first.total_pages
                or page.selection_snapshot != first.selection_snapshot
                or page.schema_fingerprint != first.schema_fingerprint
            ):
                incomplete_error = OhioReporterPaginationError(
                    "Ohio Reporter totals, selectors, or schema changed "
                    "during native pagination",
                    details={
                        "page": page_number,
                        "first_total_rows": first.total_rows,
                        "observed_total_rows": page.total_rows,
                        "first_page_size": first.page_size,
                        "observed_page_size": page.page_size,
                    },
                )
                break
            if page.state_fingerprint in state_fingerprints:
                incomplete_error = OhioReporterPaginationError(
                    "Ohio Reporter repeated WebForms state during pagination",
                    details={"page": page_number},
                )
                break
            state_fingerprints.add(page.state_fingerprint)
            pages.append(page)
            previous = page

        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in pages:
            for record in page.records:
                webcite = str(record["webcite"])
                if webcite in seen:
                    if incomplete_error is None:
                        incomplete_error = OhioReporterPaginationError(
                            "Ohio Reporter repeated a WebCite across native pages",
                            details={"webcite": webcite},
                        )
                    continue
                seen.add(webcite)
                records.append(record)
        if (
            incomplete_error is None
            and len(records) != first.total_rows
        ):
            incomplete_error = OhioReporterPaginationError(
                "Ohio Reporter traversal did not yield its published row count",
                details={
                    "expected": first.total_rows,
                    "observed": len(records),
                },
            )

        return ReporterCollection(
            records=tuple(records),
            total_rows=first.total_rows,
            page_size=first.page_size,
            total_pages=first.total_pages,
            pages_fetched=len(pages),
            selected_values=first.selected_values,
            selected_labels=first.selected_labels,
            source_urls=tuple(page.source_url for page in pages),
            schema_fingerprints=tuple(
                page.schema_fingerprint for page in pages
            ),
            incomplete_error=incomplete_error,
        )

    def publication(self, webcite: str) -> ReporterCollection:
        normalized = normalize_webcite(webcite)
        collection = self.fetch_all(
            {
                "webcite_year": normalized[:4],
                "webcite_number": normalized.rsplit("-", 1)[1],
            }
        )
        if collection.incomplete_error is not None:
            return collection
        if collection.total_rows > 1:
            raise OhioReporterSourceChanged(
                "webcite_not_unique",
                "Ohio Reporter returned multiple rows for a unique WebCite",
                details={
                    "webcite": normalized,
                    "row_count": collection.total_rows,
                },
            )
        if collection.records and (
            collection.records[0]["webcite"] != normalized
        ):
            raise OhioReporterSourceChanged(
                "webcite_result_mismatch",
                "Ohio Reporter exact WebCite search returned another publication",
                details={
                    "requested": normalized,
                    "observed": collection.records[0]["webcite"],
                },
            )
        return collection

    def fetch_pdf(
        self,
        source_url: str,
        *,
        expected_webcite: str,
        expected_source_code: str,
    ) -> ReporterPDF:
        requested = _parse_pdf_url(
            source_url,
            expected_webcite=expected_webcite,
            expected_source_code=expected_source_code,
        )
        response = self._request(
            "GET",
            source_url,
            headers={
                "Accept": "application/pdf",
                "Referer": BASE_URL,
            },
        )
        final_url = str(response.url)
        final_identity = _parse_pdf_url(
            final_url,
            expected_webcite=requested["webcite"],
            expected_source_code=requested["source_code"],
        )
        media_type = (
            str(response.headers.get("Content-Type", ""))
            .split(";", 1)[0]
            .strip()
            .casefold()
        )
        content = bytes(response.content)
        if media_type != "application/pdf" or not content.startswith(b"%PDF-"):
            raise OhioReporterSourceChanged(
                "publication_pdf_response_invalid",
                "Ohio Reporter publication route did not return a PDF",
                details={
                    "content_type": media_type,
                    "byte_size": len(content),
                    "final_url": final_url,
                },
            )
        court = COURT_SOURCES[final_identity["source_code"]]
        return ReporterPDF(
            content=content,
            source_url=source_url,
            final_url=final_url,
            webcite=final_identity["webcite"],
            source_code=final_identity["source_code"],
            court_id=court["court_id"],
            court_name=court["name"],
            media_type=media_type,
            sha256=hashlib.sha256(content).hexdigest(),
        )


def _source_metadata() -> SourceMetadata:
    return SourceMetadata(
        source_id=SOURCE_ID,
        name=SOURCE_NAME,
        source_role="official_statewide_judicial_publication_index",
        base_url=BASE_URL,
        dataset_id="ohio-reporter-decisions",
        metadata={
            "authority": "Supreme Court of Ohio, Reporter of Decisions",
            "state_code": STATE_CODE,
            "authentication": "none",
            "platform_family": PLATFORM_FAMILY,
            "native_pagination": "aspnet_gridview_postback",
            "native_page_size": NATIVE_PAGE_SIZE,
            "full_text_result_boundary": FULL_TEXT_RESULT_BOUNDARY,
            "observed_at": OBSERVED_AT,
            "evidentiary_role": "official_opinion_and_announcement_publication",
        },
    )


def _jurisdiction() -> JurisdictionMetadata:
    return JurisdictionMetadata(
        jurisdiction_id=STATE_GEOID,
        name="Ohio",
        state_code=STATE_CODE,
        metadata={
            "publisher": "Supreme Court of Ohio",
            "included_deciding_sources": [
                details["name"] for details in COURT_SOURCES.values()
            ],
        },
    )


def _query(
    operation: str,
    *,
    parameters: Mapping[str, Any],
    limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=_source_metadata(),
        jurisdiction=_jurisdiction(),
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
            metadata={
                "native_pagination": "exhausted_before_caller_window",
                "default_result_cap": None,
                "full_text_source_boundary": FULL_TEXT_RESULT_BOUNDARY,
            },
        ),
    )


def _source_record() -> dict[str, Any]:
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            "oh-reporter-of-decisions",
            "source-contract",
            "source_contract",
        ),
        "source_id": SOURCE_ID,
        "record_kind": "source_contract",
        "publisher": "Supreme Court of Ohio, Reporter of Decisions",
        "observed_at": OBSERVED_AT,
        "access": {
            "authentication": "none",
            "search_method": "aspnet_webforms_post",
            "native_pagination": "gridview_postback",
            "native_page_size": NATIVE_PAGE_SIZE,
            "publication_document": "anonymous_pdf",
            "resolved_host": EXPECTED_HOST,
        },
        "coverage": {
            "publication_types": ["opinions", "case announcements"],
            "deciding_sources": [
                {
                    "source_code": code,
                    "slug": details["slug"],
                    "court_id": details["court_id"],
                    "name": details["name"],
                }
                for code, details in COURT_SOURCES.items()
            ],
            "observed_decision_year_vocabulary": {
                "minimum": 1992,
                "maximum": 2026,
                "dynamic": True,
            },
        },
        "search_fields": [
            "full_text",
            "source",
            "decision_year_range",
            "county",
            "exact_case_number",
            "author",
            "topics_and_issues",
            "exact_webcite",
            "exact_print_citation",
        ],
        "source_semantics": {
            "full_text_logic": (
                "space means AND; OR is supported; quoted phrases are exact"
            ),
            "case_number": "exact source-native match including punctuation",
            "webcite": (
                "unique publication lookup; overrides every other filter"
            ),
            "citation": (
                "unique Supreme Court print-citation lookup; ignored when "
                "WebCite is also supplied"
            ),
            "full_text_result_boundary": FULL_TEXT_RESULT_BOUNDARY,
            "full_text_boundary_provenance": HELP_URL,
        },
        "identities": {
            "publication": "WebCite",
            "case": "optional deciding-court case number",
            "document": "WebCite plus official PDF representation",
            "source_attribution": "PDF path source code",
        },
        "complementary_sources": {
            "supreme_court_ecms": (
                "case docket, parties, entries, and filed documents"
            ),
            "clerks_journal": "Supreme Court order/journal publication",
            "district_sources": (
                "court-specific dockets and alternative opinion copies"
            ),
            "relationship": (
                "shared representations may join but do not independently "
                "corroborate the same judicial act"
            ),
        },
    }


def _search_parameters(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "query_text": args.text or "",
        "court_code": SOURCE_CODE_BY_SLUG[args.source],
        "source": args.source,
        "year": args.year,
        "year_from": args.year_from,
        "year_to": args.year_to,
        "county": args.county or "0",
        "case_number": args.case_number or "",
        "author": args.author or "",
        "topics": args.topics or "",
        "citation": args.citation or "",
    }


def _effective_source_selection(
    collection: ReporterCollection,
) -> dict[str, dict[str, str | None]]:
    """Expose the selectors the source actually retained for this response."""

    return {
        name: {
            "value": collection.selected_values.get(field_name),
            "label": collection.selected_labels.get(field_name),
        }
        for name, field_name in (
            ("source", _FORM_FIELDS["court"]),
            ("year_from", _FORM_FIELDS["year_from"]),
            ("year_to", _FORM_FIELDS["year_to"]),
            ("county", _FORM_FIELDS["county"]),
            ("native_page_size", _FORM_FIELDS["rows_per_page"]),
        )
    }


def _selection_fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _membership_fingerprint(
    records: Sequence[Mapping[str, Any]],
) -> str:
    return hashlib.sha256(
        canonical_json(
            [str(record.get("webcite") or "") for record in records]
        ).encode("utf-8")
    ).hexdigest()


def _cursor_encode(payload: Mapping[str, Any]) -> str:
    token = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{CURSOR_PREFIX}{token}"


def _cursor_decode(value: str) -> Mapping[str, Any]:
    if not value.startswith(CURSOR_PREFIX):
        raise OhioReporterSelectionError(
            "invalid_cursor",
            "cursor is not an Ohio Reporter continuation",
        )
    token = value.removeprefix(CURSOR_PREFIX)
    try:
        decoded = base64.urlsafe_b64decode(
            token + "=" * (-len(token) % 4)
        )
        payload = json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as error:
        raise OhioReporterSelectionError(
            "invalid_cursor",
            "cursor payload is malformed",
        ) from error
    if not isinstance(payload, Mapping):
        raise OhioReporterSelectionError(
            "invalid_cursor",
            "cursor payload changed type",
        )
    return payload


def _window_records(
    records: Sequence[Mapping[str, Any]],
    *,
    selection: Mapping[str, Any],
    limit: int | None,
    cursor: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    if cursor and limit is None:
        raise OhioReporterSelectionError(
            "cursor_requires_limit",
            "continuing a caller window requires --limit",
        )
    selection_hash = _selection_fingerprint(selection)
    membership_hash = _membership_fingerprint(records)
    offset = 0
    if cursor:
        payload = _cursor_decode(cursor)
        if payload.get("source_id") != SOURCE_ID:
            raise OhioReporterSelectionError(
                "cursor_source_mismatch",
                "cursor belongs to another source",
            )
        if payload.get("selection_fingerprint") != selection_hash:
            raise OhioReporterSelectionError(
                "cursor_query_mismatch",
                "cursor belongs to another selector set",
            )
        if (
            payload.get("membership_fingerprint") != membership_hash
            or payload.get("total") != len(records)
        ):
            raise OhioReporterSelectionError(
                "cursor_membership_changed",
                "ordered source-response membership changed",
            )
        try:
            offset = int(payload["offset"])
        except (KeyError, TypeError, ValueError) as error:
            raise OhioReporterSelectionError(
                "invalid_cursor",
                "cursor offset is invalid",
            ) from error
        if offset < 0 or offset > len(records):
            raise OhioReporterSelectionError(
                "invalid_cursor",
                "cursor offset is outside the source response",
            )

    end = len(records) if limit is None else min(offset + limit, len(records))
    window = [dict(record) for record in records[offset:end]]
    next_cursor = None
    if end < len(records):
        next_cursor = _cursor_encode(
            {
                "source_id": SOURCE_ID,
                "selection_fingerprint": selection_hash,
                "membership_fingerprint": membership_hash,
                "offset": end,
                "total": len(records),
            }
        )
    return window, next_cursor


def _public_error(error: OhioReporterError) -> PublicRecordsError:
    return PublicRecordsError(
        code=error.code,
        message=str(error),
        category=error.category,
        retryable=error.retryable,
        details=error.details,
    )


def _failure(
    query: PublicRecordsQuery,
    error: OhioReporterError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [_public_error(error)],
        warnings=SOURCE_WARNINGS,
    )


def _full_text_boundary_error() -> PublicRecordsError:
    return PublicRecordsError(
        code="documented_full_text_result_boundary",
        message=(
            "The full-text appliance returned exactly its documented "
            "1,000 most-relevant-result boundary; additional matches may exist."
        ),
        category="source_response",
        retryable=False,
        details={
            "returned_count": FULL_TEXT_RESULT_BOUNDARY,
            "source_response_preserved": True,
            "boundary_documentation": HELP_URL,
            "suggested_action": "add source-native filters",
        },
    )


def _collection_result(
    query: PublicRecordsQuery,
    collection: ReporterCollection,
    *,
    selection: Mapping[str, Any],
    limit: int | None,
    cursor: str | None,
) -> PublicRecordsResult:
    window, next_cursor = _window_records(
        collection.records,
        selection=selection,
        limit=limit,
        cursor=cursor,
    )
    native_selection = selection.get("parameters")
    if not isinstance(native_selection, Mapping):
        native_selection = selection
    source_boundary = (
        bool(_clean(native_selection.get("query_text")))
        and collection.total_rows == FULL_TEXT_RESULT_BOUNDARY
    )
    for record in window:
        record["retrieval"] = {
            "source_response_count": collection.total_rows,
            "native_page_size": collection.page_size,
            "native_pages_expected": collection.total_pages,
            "native_pages_fetched": collection.pages_fetched,
            "native_pagination_complete": (
                collection.incomplete_error is None
            ),
            "documented_full_text_boundary_reached": source_boundary,
            "caller_window_applied": limit is not None,
        }
    warnings = list(SOURCE_WARNINGS)
    if limit is not None and len(window) < len(collection.records):
        warnings.append(
            f"Caller window returned {len(window)} of "
            f"{len(collection.records)} collected publications."
        )
    errors: list[PublicRecordsError] = []
    if collection.incomplete_error is not None:
        errors.append(_public_error(collection.incomplete_error))
    if source_boundary:
        errors.append(_full_text_boundary_error())
    if errors:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            errors,
            records=window,
            next_cursor=next_cursor,
            warnings=warnings,
        )
    return PublicRecordsResult.success(
        query,
        window,
        next_cursor=next_cursor,
        warnings=warnings,
    )


def _document_record(
    publication: Mapping[str, Any],
    artifact: ReporterPDF,
    destination: Path,
) -> dict[str, Any]:
    return {
        "canonical_ref": _document_ref(
            artifact.court_id,
            artifact.webcite,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "judicial_publication_document",
        "publication_ref": publication["canonical_ref"],
        "publication_identity": artifact.webcite,
        "webcite": artifact.webcite,
        "case_number": publication.get("case_number"),
        "court_id": artifact.court_id,
        "court_name": artifact.court_name,
        "source_native_court_code": artifact.source_code,
        "native_document_id": f"{artifact.webcite}.pdf",
        "source_url": artifact.source_url,
        "final_url": artifact.final_url,
        "media_type": artifact.media_type,
        "signature": "%PDF-",
        "byte_size": len(artifact.content),
        "sha256": artifact.sha256,
        "local_path": str(destination.resolve()),
    }


def _log(query: PublicRecordsQuery, count: int | None) -> None:
    try:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    except Exception as error:
        print(f"Warning: could not log search: {error}", file=sys.stderr)


def execute(
    args: argparse.Namespace,
    *,
    client: OhioReporterClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one standalone Reporter of Decisions operation."""

    operation = args.command
    limit = getattr(args, "limit", None)
    cursor = getattr(args, "cursor", None)
    selection: dict[str, Any] = {}
    try:
        if operation == "search":
            selection = _search_parameters(args)
            parameters = dict(selection)
        elif operation in {"publication", "document"}:
            webcite = normalize_webcite(args.webcite)
            parameters = {"webcite": webcite}
            if operation == "document":
                parameters["destination"] = str(args.destination)
        elif operation == "probe":
            parameters = {
                "sentinel_webcite": PROBE_WEBCITE,
                "pagination_year": PROBE_YEAR,
                "routes": [
                    "webforms_search",
                    "native_pagination",
                    "exact_webcite",
                    "publication_pdf",
                ],
            }
        else:
            parameters = {}
    except OhioReporterError as error:
        query = _query(
            operation,
            parameters={"invalid_selection": True},
            limit=limit,
            cursor=cursor,
        )
        return _failure(query, error)

    query = _query(
        operation,
        parameters=parameters,
        limit=limit,
        cursor=cursor,
    )
    source_client = client or OhioReporterClient(
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
            collection = source_client.fetch_all(selection)
            parameters = {
                **selection,
                "effective_source_selection": _effective_source_selection(
                    collection
                ),
            }
            query = _query(
                operation,
                parameters=parameters,
                limit=limit,
                cursor=cursor,
            )
            result = _collection_result(
                query,
                collection,
                selection={
                    "operation": "search",
                    "parameters": selection,
                },
                limit=limit,
                cursor=cursor,
            )
        elif operation == "publication":
            collection = source_client.publication(webcite)
            if collection.incomplete_error is not None:
                result = PublicRecordsResult.failure(
                    query,
                    ResultStatus.PARTIAL,
                    [_public_error(collection.incomplete_error)],
                    records=collection.records,
                    warnings=SOURCE_WARNINGS,
                )
            else:
                result = PublicRecordsResult.success(
                    query,
                    collection.records,
                    warnings=SOURCE_WARNINGS,
                )
        elif operation == "document":
            destination = Path(args.destination)
            if destination.exists() and not args.overwrite:
                raise OhioReporterSelectionError(
                    "destination_exists",
                    "destination already exists; use --overwrite to replace it",
                    details={"destination": str(destination)},
                )
            collection = source_client.publication(webcite)
            if collection.incomplete_error is not None:
                raise collection.incomplete_error
            if not collection.records:
                result = PublicRecordsResult.success(
                    query,
                    [],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                publication = collection.records[0]
                artifact = source_client.fetch_pdf(
                    str(publication["document_url"]),
                    expected_webcite=webcite,
                    expected_source_code=str(
                        publication["source_native_court_code"]
                    ),
                )
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(artifact.content)
                record = _document_record(
                    publication,
                    artifact,
                    destination,
                )
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    raw_artifact_refs=[str(destination.resolve())],
                    warnings=SOURCE_WARNINGS,
                )
        else:
            pagination_collection = source_client.fetch_all(
                {
                    "court_code": "0",
                    "year": PROBE_YEAR,
                }
            )
            if pagination_collection.incomplete_error is not None:
                raise pagination_collection.incomplete_error
            exact = source_client.publication(PROBE_WEBCITE)
            if len(exact.records) != 1:
                raise OhioReporterSourceChanged(
                    "probe_publication_missing",
                    "Historical Reporter probe publication is unavailable",
                    details={"webcite": PROBE_WEBCITE},
                )
            publication = exact.records[0]
            artifact = source_client.fetch_pdf(
                str(publication["document_url"]),
                expected_webcite=PROBE_WEBCITE,
                expected_source_code=str(
                    publication["source_native_court_code"]
                ),
            )
            probe = _source_record()
            probe["record_kind"] = "source_probe"
            probe["probe"] = {
                "status": "available",
                "routes_exercised": [
                    "webforms_search",
                    "native_pagination",
                    "exact_webcite",
                    "publication_pdf",
                ],
                "request_count": source_client.request_count,
                "pagination_year": PROBE_YEAR,
                "pagination_publication_count": (
                    pagination_collection.total_rows
                ),
                "pagination_pages_fetched": (
                    pagination_collection.pages_fetched
                ),
                "sentinel_webcite": artifact.webcite,
                "sentinel_caption": publication["caption"],
                "sentinel_pdf_media_type": artifact.media_type,
                "sentinel_pdf_signature": "%PDF-",
                "sentinel_pdf_byte_size": len(artifact.content),
                "sentinel_pdf_sha256": artifact.sha256,
                "sentinel_pdf_final_host": urlsplit(
                    artifact.final_url
                ).hostname,
            }
            result = PublicRecordsResult.success(
                query,
                [probe],
                warnings=SOURCE_WARNINGS,
            )
    except OhioReporterError as error:
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


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Ohio Reporter of Decisions {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2))
        return
    print(
        f"Ohio Reporter of Decisions {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    for record in result.records:
        if record.get("record_kind") == "judicial_publication":
            print(
                f"- {record['webcite']} | {record['court_name']} | "
                f"{record['caption']}"
            )
        elif record.get("record_kind") == (
            "judicial_publication_document"
        ):
            print(
                f"- {record['webcite']} | {record['media_type']} | "
                f"{record['byte_size']} bytes"
            )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


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


def _add_window_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=_positive_int,
        help=(
            "Return a caller-sized window after exhausting native pagination"
        ),
    )
    parser.add_argument(
        "--cursor",
        help="Resume a prior caller window over unchanged source membership",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Ohio Reporter of Decisions publications"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser(
        "source",
        help="Show verified routes, fields, identities, and boundaries",
    )
    add_output_args(source)

    search = subparsers.add_parser(
        "search",
        help="Search opinions and announcements using source-native fields",
    )
    search.add_argument("--text", type=_nonblank)
    search.add_argument(
        "--source",
        choices=sorted(SOURCE_CODE_BY_SLUG),
        default="supreme",
    )
    search.add_argument("--year", type=int)
    search.add_argument("--year-from", type=int)
    search.add_argument("--year-to", type=int)
    search.add_argument("--county", type=_nonblank)
    search.add_argument("--case-number", type=_nonblank)
    search.add_argument("--author", type=_nonblank)
    search.add_argument("--topics", type=_nonblank)
    search.add_argument("--citation", type=_nonblank)
    _add_window_args(search)
    add_output_args(search)

    publication = subparsers.add_parser(
        "publication",
        help="Look up one publication by its unique WebCite",
    )
    publication.add_argument("webcite", type=_nonblank)
    add_output_args(publication)

    document = subparsers.add_parser(
        "document",
        help="Resolve, download, and verify one official publication PDF",
    )
    document.add_argument("webcite", type=_nonblank)
    document.add_argument("destination", type=Path)
    document.add_argument("--overwrite", action="store_true")
    add_output_args(document)

    probe = subparsers.add_parser(
        "probe",
        help="Exercise native paging, exact WebCite, and a historical PDF",
    )
    add_output_args(probe)

    for command in subparsers.choices.values():
        _add_transport_args(command)
    return parser


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
