#!/usr/bin/env python3
"""Query Maryland's official reported and unreported appellate opinions.

The Maryland Judiciary publishes two distinct anonymous collections:

* a legacy CGI index for reported Supreme Court and Appellate Court opinions
  and orders; and
* a Drupal directory of monthly unreported-opinion indexes.

The reported CGI intentionally uses old HTML with omitted closing ``TD`` tags,
so it is parsed as source-delimited rows rather than repaired into a DOM.  The
monthly unreported indexes use a conventional, header-validated table.

Examples:
    uv run python tools/query_md_opinions.py reported --year 2026 \
        --query "Baltimore" --output /tmp/md-reported.json
    uv run python tools/query_md_opinions.py unreported --month 2026-07 \
        --query "Properties" --output /tmp/md-unreported.json
    uv run python tools/query_md_opinions.py unreported \
        --date-from 2026-01-01 --date-to 2026-07-31 --limit 100 \
        --output /tmp/md-unreported-range.json
    uv run python tools/query_md_opinions.py routes --json
    uv run python tools/query_md_opinions.py download URL DESTINATION --json
    uv run python tools/query_md_opinions.py probe --json
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
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
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


SOURCE_ID = "us-md-appellate-opinions"
STATE_CODE = "MD"
STATE_GEOID = "24"
BASE_URL = "https://www.mdcourts.gov"
REPORTED_INDEX_URL = f"{BASE_URL}/opinions/opinions"
REPORTED_RESULTS_URL = f"{BASE_URL}/cgi-bin/indexlist.pl"
UNREPORTED_INDEX_URL = f"{BASE_URL}/appellate/unreportedopinions"
UNREPORTED_MONTH_PREFIX = f"{UNREPORTED_INDEX_URL}/list"
CASE_SEARCH_URL = "https://casesearch.mdcourts.gov/casesearch/"
MDEC_REPORTS_URL = f"{BASE_URL}/mdec/publiccases"
JUDGMENT_LIENS_URL = "https://jportal.mdcourts.gov/judgment/judgementSearch.jsf"
ESTATE_SEARCH_URL = "https://registers.maryland.gov/main/search.html"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)
OUTPUT_SCHEMA_VERSION = "maryland-appellate-opinions/1.0"
CURSOR_VERSION = 1

COURTS: dict[str, dict[str, str]] = {
    "supreme": {
        "native": "coa",
        "court_id": "md-supreme-court",
        "current_name": "Supreme Court of Maryland",
        "former_name": "Court of Appeals of Maryland",
        "path_component": "coa",
    },
    "appellate": {
        "native": "cosa",
        "court_id": "md-appellate-court",
        "current_name": "Appellate Court of Maryland",
        "former_name": "Court of Special Appeals of Maryland",
        "path_component": "cosa",
    },
}
COURT_FROM_NATIVE = {spec["native"]: key for key, spec in COURTS.items()}
COURT_FROM_NAME = {
    "supreme court of maryland": "supreme",
    "court of appeals": "supreme",
    "court of appeals of maryland": "supreme",
    "appellate court of maryland": "appellate",
    "court of special appeals": "appellate",
    "court of special appeals of maryland": "appellate",
}
REPORTED_COURTS = {
    "both": "both",
    "supreme": "coa",
    "appellate": "cosa",
}
REPORTED_ORDERS = {
    "date": "bydate",
    "case": "bycase",
    "citation": "bycite",
    "judge": "byjudge",
    "party": "bytitle",
}
REPORTED_HEADERS = (
    "CASE PDF docket/term",
    "CITATION",
    "FILED",
    "JUDGE",
    "PARTIES",
    "Line",
)
UNREPORTED_HEADERS = (
    "Court",
    "Filed",
    "Docket File",
    "Term",
    "Judge",
    "Appellant",
    "Appellee",
)

_REPORTED_HEADER_RE = re.compile(r"(?is)<TR\s+SCOPE\s*=\s*row[^>]*>(.*?)</TR>")
_REPORTED_ROW_RE = re.compile(r"(?is)<TR\s+bgcolor\s*=\s*[^>]*>(.*?)(?=<TR\b|</TABLE>)")
_CELL_SPLIT_RE = re.compile(r"(?is)<T[DH]\b[^>]*>")
_ISO_DATE_RE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")
_MONTH_ROUTE_RE = re.compile(r"^/appellate/unreportedopinions/list/((?:19|20)\d{4})/?$")
_REPORTED_PDF_RE = re.compile(
    r"^/data/opinions/(coa|cosa)/((?:19|20)\d{2})/"
    r"([^/?#]+\.pdf)$",
    re.IGNORECASE,
)
_UNREPORTED_PDF_RE = re.compile(
    r"^/sites/default/files/unreported-opinions/([^/?#]+\.pdf)$",
    re.IGNORECASE,
)
_CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "challenges.cloudflare.com",
    "cf-chl-",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Maryland Appellate Court Opinions",
    source_role="official_reported_and_unreported_appellate_decisions",
    base_url=REPORTED_INDEX_URL,
    dataset_id="maryland-appellate-opinions",
    metadata={
        "authority": "Maryland Judiciary",
        "operator": "Administrative Office of the Courts",
        "authentication": "none",
        "reported_component": {
            "index_url": REPORTED_INDEX_URL,
            "results_url": REPORTED_RESULTS_URL,
            "native_pagination": "complete_year_index",
            "coverage_start_year": 1995,
        },
        "unreported_component": {
            "index_url": UNREPORTED_INDEX_URL,
            "native_pagination": "complete_month_index",
            "metadata_coverage_start": "2001-02",
            "linked_full_text_coverage_start": "2015-05",
        },
        "evidentiary_role": "official_appellate_decision_publication",
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Maryland",
    state_code=STATE_CODE,
)

SOURCE_WARNINGS = (
    "This is an appellate decision-publication source, not a complete case "
    "docket or a collection of the parties' underlying filings.",
    "Reported and unreported decisions are separate official collections with "
    "different coverage and publication metadata.",
    "The reported index's filed/correction text is preserved verbatim because "
    "some source rows contain non-chronological correction annotations.",
)


class MarylandOpinionsError(RuntimeError):
    """Source error with public-record result semantics."""

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


class MarylandOpinionsSelectionError(MarylandOpinionsError):
    """The caller supplied an invalid source selection."""

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


class MarylandOpinionsSourceChangedError(MarylandOpinionsError):
    """The source no longer matches its verified schema."""

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
class MarylandReportedLanding:
    years: tuple[int, ...]
    native_courts: tuple[str, ...]
    native_orders: tuple[str, ...]
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class MarylandUnreportedDirectory:
    months: tuple[str, ...]
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class MarylandOpinionIndex:
    records: tuple[Mapping[str, Any], ...]
    source_url: str
    schema_fingerprint: str
    collection: str
    native_count: int


@dataclass(frozen=True)
class MarylandOpinionPDF:
    source_url: str
    content: bytes
    media_type: str
    sha256: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", str(value)).strip()
    return normalized or None


def _fragment_text(fragment: str) -> str:
    return _text(BeautifulSoup(fragment, "html.parser").get_text(" ", strip=True)) or ""


def _schema_fingerprint(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _parse_iso_date(value: str, field_name: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as error:
        raise MarylandOpinionsSourceChangedError(
            "source_date_invalid",
            f"Maryland opinions returned an invalid {field_name}",
            details={"field": field_name, "value": value},
        ) from error


def _parse_user_date(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise MarylandOpinionsSelectionError(
            "invalid_date",
            f"{field_name} must be YYYY-MM-DD",
            details={"field": field_name, "value": value},
        ) from error


def _parse_month(value: str, field_name: str = "--month") -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError as error:
        raise MarylandOpinionsSelectionError(
            "invalid_month",
            f"{field_name} must be YYYY-MM",
            details={"field": field_name, "value": value},
        ) from error
    return parsed.strftime("%Y%m")


def _month_label(value: str) -> str:
    return f"{value[:4]}-{value[4:]}"


def _official_pdf_url(value: str) -> str:
    absolute = urljoin(BASE_URL, value)
    split = urlsplit(absolute)
    if (
        split.scheme.lower() != "https"
        or (split.hostname or "").lower() not in {"www.mdcourts.gov", "mdcourts.gov"}
        or not (
            _REPORTED_PDF_RE.fullmatch(split.path)
            or _UNREPORTED_PDF_RE.fullmatch(split.path)
        )
    ):
        raise MarylandOpinionsSelectionError(
            "unsupported_document_url",
            "Document URL is not an official Maryland appellate-opinion PDF",
            details={"url": value},
        )
    return absolute


def _court_identity(
    court_key: str,
    *,
    filed_date: str,
    source_name: str | None = None,
) -> dict[str, Any]:
    spec = COURTS[court_key]
    rename_date = "2022-12-14"
    name_at_filing = source_name or (
        spec["current_name"] if filed_date >= rename_date else spec["former_name"]
    )
    return {
        "court_id": spec["court_id"],
        "court_key": court_key,
        "name": spec["current_name"],
        "name_at_filing": name_at_filing,
        "former_name": spec["former_name"],
        "state_code": STATE_CODE,
        "court_level": "appellate",
        "official_url": REPORTED_INDEX_URL,
    }


def _court_from_reported_pdf(pdf_url: str) -> tuple[str, str]:
    match = _REPORTED_PDF_RE.fullmatch(urlsplit(pdf_url).path)
    if match is None:
        raise MarylandOpinionsSourceChangedError(
            "reported_pdf_path_changed",
            "Reported-opinion link no longer carries a recognized court path",
            details={"url": pdf_url},
        )
    native_court, year, filename = match.groups()
    court_key = COURT_FROM_NATIVE[native_court.lower()]
    return court_key, f"{native_court.lower()}/{year}/{filename.lower()}"


def _court_from_unreported_name(value: str) -> str:
    key = COURT_FROM_NAME.get(value.casefold())
    if key is None:
        raise MarylandOpinionsSourceChangedError(
            "unreported_court_changed",
            "Unreported-opinion index returned an unknown appellate court",
            details={"court": value},
        )
    return key


def _entry_ref(
    *,
    court_key: str,
    case_number: str,
    document_type: str,
    native_entry_id: str,
) -> tuple[str, str]:
    court_id = COURTS[court_key]["court_id"]
    case_ref = canonical_court_ref(
        SOURCE_ID,
        court_id,
        case_number,
    )
    entry_ref = canonical_court_ref(
        SOURCE_ID,
        court_id,
        case_number,
        record_kind=document_type,
        native_id=native_entry_id,
    )
    return case_ref, entry_ref


def parse_reported_landing(
    html_text: str,
    *,
    source_url: str = REPORTED_INDEX_URL,
) -> MarylandReportedLanding:
    """Parse the official reported-opinion selector and validate its routes."""

    soup = BeautifulSoup(html_text, "html.parser")
    form = soup.select_one('form[action="/cgi-bin/indexlist.pl"]')
    if form is None:
        raise MarylandOpinionsSourceChangedError(
            "reported_selector_missing",
            "Reported-opinion page lacks its official CGI selector",
        )
    years = sorted(
        {
            int(node["value"])
            for node in form.select('input[name="year"][value]')
            if str(node["value"]).isdigit()
        },
        reverse=True,
    )
    courts = tuple(
        sorted(
            {str(node["value"]) for node in form.select('input[name="court"][value]')}
        )
    )
    orders = tuple(
        sorted(
            {str(node["value"]) for node in form.select('input[name="order"][value]')}
        )
    )
    if (
        not years
        or not {"both", "coa", "cosa"}.issubset(courts)
        or not set(REPORTED_ORDERS.values()).issubset(orders)
    ):
        raise MarylandOpinionsSourceChangedError(
            "reported_selector_changed",
            "Reported-opinion selector values changed",
            details={
                "year_count": len(years),
                "courts": list(courts),
                "orders": list(orders),
            },
        )
    fingerprint = _schema_fingerprint(
        {
            "form_action": "/cgi-bin/indexlist.pl",
            "fields": ["court", "year", "order"],
            "courts": courts,
            "orders": orders,
        }
    )
    return MarylandReportedLanding(
        years=tuple(years),
        native_courts=courts,
        native_orders=orders,
        source_url=source_url,
        schema_fingerprint=fingerprint,
    )


def parse_unreported_directory(
    html_text: str,
    *,
    source_url: str = UNREPORTED_INDEX_URL,
) -> MarylandUnreportedDirectory:
    """Discover every source-published monthly unreported-opinion route."""

    soup = BeautifulSoup(html_text, "html.parser")
    months: set[str] = set()
    for link in soup.select("a[href]"):
        split = urlsplit(urljoin(source_url, str(link["href"])))
        if (split.hostname or "").lower() not in {
            "www.mdcourts.gov",
            "mdcourts.gov",
        }:
            continue
        match = _MONTH_ROUTE_RE.fullmatch(split.path)
        if match is None:
            continue
        month = match.group(1)
        try:
            datetime.strptime(month, "%Y%m")
        except ValueError as error:
            raise MarylandOpinionsSourceChangedError(
                "unreported_month_invalid",
                "Unreported-opinion directory contains an invalid month route",
                details={"month": month},
            ) from error
        months.add(month)
    if not months:
        raise MarylandOpinionsSourceChangedError(
            "unreported_months_missing",
            "Unreported-opinion directory exposes no monthly indexes",
        )
    ordered = tuple(sorted(months, reverse=True))
    fingerprint = _schema_fingerprint(
        {
            "route_pattern": "/appellate/unreportedopinions/list/YYYYMM",
            "first_month": ordered[-1],
            "month_count": len(ordered),
        }
    )
    return MarylandUnreportedDirectory(
        months=ordered,
        source_url=source_url,
        schema_fingerprint=fingerprint,
    )


def _reported_date_fields(raw_value: str) -> tuple[str, list[str], str | None]:
    dates = _ISO_DATE_RE.findall(raw_value)
    if not dates:
        raise MarylandOpinionsSourceChangedError(
            "reported_filed_date_missing",
            "Reported-opinion row lacks a filed date",
            details={"filed": raw_value},
        )
    filed_date = _parse_iso_date(dates[0], "reported filed date")
    correction_dates = [
        _parse_iso_date(value, "reported correction date") for value in dates[1:]
    ]
    first_end = raw_value.find(dates[0]) + len(dates[0])
    note = _text(raw_value[first_end:])
    return filed_date, correction_dates, note


def _electronic_text_status(filed_date: str) -> str:
    if filed_date >= "2018-07-01":
        return "official_and_authentic_electronic_text"
    return "online_reported_copy_bound_reporter_controls"


def _reported_record(
    cells: Sequence[str],
    *,
    source_url: str,
    schema_fingerprint: str,
    native_court_filter: str,
) -> dict[str, Any]:
    if len(cells) != len(REPORTED_HEADERS):
        raise MarylandOpinionsSourceChangedError(
            "reported_row_width_changed",
            "Reported-opinion row no longer has six source columns",
            details={"observed_columns": len(cells)},
        )
    case_number, citation, raw_filed, judge, caption, raw_line = cells
    if not all((case_number, raw_filed, judge, caption, raw_line)):
        raise MarylandOpinionsSourceChangedError(
            "reported_required_field_missing",
            "Reported-opinion row lacks a required field",
            details={"cells": list(cells)},
        )
    link_match = re.search(
        r"""(?is)<a\b[^>]*href\s*=\s*["']([^"']+)["']""",
        cells[0],
    )
    if link_match is None:
        raise MarylandOpinionsSourceChangedError(
            "reported_pdf_missing",
            "Reported-opinion row lacks its official PDF link",
            details={"case_number": _fragment_text(case_number)},
        )
    values = [_fragment_text(cell) for cell in cells]
    (
        display_case_number,
        citation,
        raw_filed,
        judge,
        caption,
        line_text,
    ) = values
    try:
        line_number = int(line_text)
    except ValueError as error:
        raise MarylandOpinionsSourceChangedError(
            "reported_line_number_invalid",
            "Reported-opinion row has a non-numeric line marker",
            details={"line": line_text},
        ) from error
    pdf_url = _official_pdf_url(link_match.group(1))
    court_key, native_document_id = _court_from_reported_pdf(pdf_url)
    if native_court_filter != "both":
        expected_key = COURT_FROM_NATIVE[native_court_filter]
        if court_key != expected_key:
            raise MarylandOpinionsSourceChangedError(
                "reported_court_filter_mismatch",
                "Reported-opinion CGI returned a row for another court",
                details={
                    "expected": expected_key,
                    "observed": court_key,
                    "case_number": display_case_number,
                },
            )
    filed_date, correction_dates, filing_note = _reported_date_fields(raw_filed)
    document_type = (
        "appellate_order" if "order" in judge.casefold() else "appellate_opinion"
    )
    native_entry_id = f"reported:{native_document_id}"
    case_ref, entry_ref = _entry_ref(
        court_key=court_key,
        case_number=display_case_number,
        document_type=document_type,
        native_entry_id=native_entry_id,
    )
    docket_file, separator, term = display_case_number.rpartition("/")
    if not separator or not docket_file or not term:
        docket_file = display_case_number
        term = None
    citation_status = (
        "slip_opinion" if "slip" in citation.casefold() else "reported_citation"
    )
    court = _court_identity(court_key, filed_date=filed_date)
    return {
        "canonical_ref": entry_ref,
        "evidence_ref": entry_ref,
        "case_canonical_ref": case_ref,
        "source_id": SOURCE_ID,
        "record_kind": "appellate_disposition",
        "native_entry_id": native_entry_id,
        "native_document_id": native_document_id,
        "raw_case_number": display_case_number,
        "display_case_number": display_case_number,
        "appeal_numbers": [display_case_number],
        "docket_file": docket_file,
        "term": term,
        "caption": caption,
        "parties_text": caption,
        "decision_date": filed_date,
        "filed_date": filed_date,
        "source_date_raw": raw_filed,
        "correction_dates": correction_dates,
        "filing_note": filing_note,
        "judge": judge,
        "citation": citation,
        "citation_status": citation_status,
        "publication_status": "reported",
        "publication_kind": document_type,
        "electronic_text_status": _electronic_text_status(filed_date),
        "full_text_status": "available",
        "pdf_url": pdf_url,
        "document": {
            "record_kind": "document_artifact",
            "native_document_id": native_document_id,
            "document_type": document_type,
            "filed_date": filed_date,
            "source_url": pdf_url,
            "mime_type": "application/pdf",
            "access_state": "public",
        },
        "court": court,
        "source_url": pdf_url,
        "index_url": source_url,
        "source_scope": {
            "reported_decision_index": True,
            "complete_case_docket": False,
            "underlying_party_filings": False,
        },
        "provenance": {
            "source_id": SOURCE_ID,
            "source_url": source_url,
            "native_collection": "reported",
            "native_line_number": line_number,
            "native_court_filter": native_court_filter,
            "response_schema_fingerprint": schema_fingerprint,
        },
    }


def parse_reported_results(
    html_text: str,
    *,
    source_url: str,
    native_court_filter: str,
) -> MarylandOpinionIndex:
    """Parse a complete reported-opinion CGI result.

    The source omits closing ``TH`` and ``TD`` tags.  Splitting on the explicit
    row and cell starts preserves the exact record boundaries visible in the
    source instead of relying on parser-specific DOM repair.
    """

    header_match = _REPORTED_HEADER_RE.search(html_text)
    if header_match is None:
        raise MarylandOpinionsSourceChangedError(
            "reported_header_missing",
            "Reported-opinion result lacks its source header row",
        )
    headers = tuple(
        _fragment_text(fragment)
        for fragment in _CELL_SPLIT_RE.split(header_match.group(1))[1:]
    )
    if headers != REPORTED_HEADERS:
        raise MarylandOpinionsSourceChangedError(
            "reported_headers_changed",
            "Reported-opinion result headers changed",
            details={
                "expected": list(REPORTED_HEADERS),
                "observed": list(headers),
            },
        )
    fingerprint = _schema_fingerprint(
        {
            "headers": headers,
            "row_delimiter": "TR bgcolor",
            "cell_delimiter": "TD",
        }
    )
    records: list[Mapping[str, Any]] = []
    for row_html in _REPORTED_ROW_RE.findall(html_text):
        cells = _CELL_SPLIT_RE.split(row_html)[1:]
        record = _reported_record(
            cells,
            source_url=source_url,
            schema_fingerprint=fingerprint,
            native_court_filter=native_court_filter,
        )
        expected_line = len(records) + 1
        observed_line = record["provenance"]["native_line_number"]
        if observed_line != expected_line:
            raise MarylandOpinionsSourceChangedError(
                "reported_line_sequence_changed",
                "Reported-opinion line markers are not complete and sequential",
                details={
                    "expected_line": expected_line,
                    "observed_line": observed_line,
                },
            )
        records.append(record)
    return MarylandOpinionIndex(
        records=tuple(records),
        source_url=source_url,
        schema_fingerprint=fingerprint,
        collection="reported",
        native_count=len(records),
    )


def _unreported_record(
    cells: Sequence[Any],
    *,
    month: str,
    source_url: str,
    schema_fingerprint: str,
) -> dict[str, Any]:
    if len(cells) != len(UNREPORTED_HEADERS):
        raise MarylandOpinionsSourceChangedError(
            "unreported_row_width_changed",
            "Unreported-opinion row no longer has seven source columns",
            details={"observed_columns": len(cells), "month": month},
        )
    values = [_text(cell.get_text(" ", strip=True)) or "" for cell in cells]
    (
        source_court_name,
        raw_filed,
        docket_file,
        term,
        judge,
        appellant,
        appellee,
    ) = values
    if not all(
        (
            source_court_name,
            raw_filed,
            docket_file,
            term,
            judge,
            appellant,
        )
    ):
        raise MarylandOpinionsSourceChangedError(
            "unreported_required_field_missing",
            "Unreported-opinion row lacks a required source field",
            details={"month": month, "cells": values},
        )
    try:
        filed_date = datetime.strptime(raw_filed, "%m-%d-%Y").date().isoformat()
    except ValueError as error:
        raise MarylandOpinionsSourceChangedError(
            "unreported_filed_date_invalid",
            "Unreported-opinion row has an invalid filed date",
            details={"month": month, "value": raw_filed},
        ) from error
    if filed_date[:7].replace("-", "") != month:
        raise MarylandOpinionsSourceChangedError(
            "unreported_month_mismatch",
            "Unreported-opinion row falls outside its monthly index",
            details={"month": month, "filed_date": filed_date},
        )
    court_key = _court_from_unreported_name(source_court_name)
    case_number = f"{docket_file}/{term}"
    link = cells[2].find("a", href=True)
    pdf_url = _official_pdf_url(str(link["href"])) if link is not None else None
    if pdf_url is not None:
        path_match = _UNREPORTED_PDF_RE.fullmatch(urlsplit(pdf_url).path)
        if path_match is None:
            raise MarylandOpinionsSourceChangedError(
                "unreported_pdf_path_changed",
                "Unreported-opinion PDF path changed",
                details={"url": pdf_url},
            )
        native_document_id = f"unreported-opinions/{path_match.group(1).lower()}"
    else:
        native_document_id = f"metadata/{court_key}/{case_number}/{filed_date}"
    native_entry_id = f"unreported:{native_document_id}"
    case_ref, entry_ref = _entry_ref(
        court_key=court_key,
        case_number=case_number,
        document_type="appellate_opinion",
        native_entry_id=native_entry_id,
    )
    caption = f"{appellant} v. {appellee}" if appellee else appellant
    parties = [
        {
            "raw_name": appellant,
            "name": appellant,
            "role": "appellant_or_first_party",
        }
    ]
    if appellee:
        parties.append(
            {
                "raw_name": appellee,
                "name": appellee,
                "role": "appellee_or_second_party",
            }
        )
    document = None
    if pdf_url is not None:
        document = {
            "record_kind": "document_artifact",
            "native_document_id": native_document_id,
            "document_type": "appellate_opinion",
            "filed_date": filed_date,
            "source_url": pdf_url,
            "mime_type": "application/pdf",
            "access_state": "public",
        }
    court = _court_identity(
        court_key,
        filed_date=filed_date,
        source_name=source_court_name,
    )
    return {
        "canonical_ref": entry_ref,
        "evidence_ref": entry_ref,
        "case_canonical_ref": case_ref,
        "source_id": SOURCE_ID,
        "record_kind": "appellate_disposition",
        "native_entry_id": native_entry_id,
        "native_document_id": native_document_id,
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "appeal_numbers": [case_number],
        "docket_file": docket_file,
        "term": term,
        "caption": caption,
        "appellant": appellant,
        "appellee": appellee or None,
        "parties": parties,
        "decision_date": filed_date,
        "filed_date": filed_date,
        "source_date_raw": raw_filed,
        "judge": judge,
        "publication_status": "unreported",
        "publication_kind": "appellate_opinion",
        "full_text_status": ("available" if pdf_url is not None else "metadata_only"),
        "pdf_url": pdf_url,
        "document": document,
        "court": court,
        "source_month": _month_label(month),
        "source_url": pdf_url or source_url,
        "index_url": source_url,
        "source_scope": {
            "unreported_decision_index": True,
            "complete_case_docket": False,
            "underlying_party_filings": False,
        },
        "provenance": {
            "source_id": SOURCE_ID,
            "source_url": source_url,
            "native_collection": "unreported",
            "native_month": month,
            "response_schema_fingerprint": schema_fingerprint,
        },
    }


def parse_unreported_month(
    html_text: str,
    *,
    month: str,
    source_url: str,
) -> MarylandOpinionIndex:
    """Parse one source-published monthly unreported-opinion index."""

    soup = BeautifulSoup(html_text, "html.parser")
    table = None
    observed_headers: tuple[str, ...] = ()
    for candidate in soup.select("table"):
        headers = tuple(
            _text(node.get_text(" ", strip=True)) or ""
            for node in candidate.select("thead th")
        )
        if headers == UNREPORTED_HEADERS:
            table = candidate
            observed_headers = headers
            break
    if table is None:
        all_headers = [
            [
                _text(node.get_text(" ", strip=True)) or ""
                for node in candidate.select("thead th")
            ]
            for candidate in soup.select("table")
            if candidate.select("thead th")
        ]
        raise MarylandOpinionsSourceChangedError(
            "unreported_headers_changed",
            "Monthly unreported-opinion table headers changed or disappeared",
            details={
                "expected": list(UNREPORTED_HEADERS),
                "observed": all_headers,
                "month": month,
            },
        )
    fingerprint = _schema_fingerprint(
        {
            "headers": observed_headers,
            "table_classes": sorted(table.get("class", [])),
        }
    )
    records = tuple(
        _unreported_record(
            row.find_all("td", recursive=False),
            month=month,
            source_url=source_url,
            schema_fingerprint=fingerprint,
        )
        for row in table.select("tbody tr")
    )
    return MarylandOpinionIndex(
        records=records,
        source_url=source_url,
        schema_fingerprint=fingerprint,
        collection="unreported",
        native_count=len(records),
    )


class MarylandOpinionsClient:
    """Paced, retrying client for the two official collections and PDFs."""

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

    def _get(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> Any:
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise MarylandOpinionsError(
                        "transport_error",
                        f"Maryland Judiciary request failed: {error}",
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
                raise MarylandOpinionsError(
                    "source_rate_limited",
                    "Maryland Judiciary rate-limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="http",
                    retryable=True,
                    details={"url": url, "http_status": status_code},
                )
            if status_code in {401, 403}:
                raise MarylandOpinionsError(
                    "source_access_challenge",
                    "Maryland Judiciary returned an access challenge",
                    status=ResultStatus.HUMAN_REQUIRED,
                    category="source_access",
                    retryable=False,
                    details={"url": url, "http_status": status_code},
                )
            if status_code != 200:
                raise MarylandOpinionsError(
                    "source_http_error",
                    f"Maryland Judiciary returned HTTP {status_code}",
                    category="http",
                    retryable=status_code >= 500,
                    details={"url": url, "http_status": status_code},
                )
            content = bytes(getattr(response, "content", b""))
            text = str(getattr(response, "text", ""))
            lowered = (
                text.casefold()
                if text
                else content[:200_000].decode("utf-8", errors="ignore").casefold()
            )
            if any(marker in lowered for marker in _CHALLENGE_MARKERS):
                raise MarylandOpinionsError(
                    "source_access_challenge",
                    "Maryland Judiciary returned a browser-verification page",
                    status=ResultStatus.HUMAN_REQUIRED,
                    category="source_access",
                    details={"url": url},
                )
            return response
        raise AssertionError("retry loop exhausted")

    def fetch_reported_landing(self) -> MarylandReportedLanding:
        response = self._get(REPORTED_INDEX_URL)
        return parse_reported_landing(
            str(response.text),
            source_url=str(getattr(response, "url", REPORTED_INDEX_URL)),
        )

    def fetch_unreported_directory(self) -> MarylandUnreportedDirectory:
        response = self._get(UNREPORTED_INDEX_URL)
        return parse_unreported_directory(
            str(response.text),
            source_url=str(getattr(response, "url", UNREPORTED_INDEX_URL)),
        )

    def fetch_reported(
        self,
        *,
        native_court: str,
        year: str,
        native_order: str,
    ) -> MarylandOpinionIndex:
        params = {
            "court": native_court,
            "year": year,
            "order": native_order,
            "submit": "Submit",
        }
        response = self._get(REPORTED_RESULTS_URL, params=params)
        return parse_reported_results(
            str(response.text),
            source_url=str(getattr(response, "url", REPORTED_RESULTS_URL)),
            native_court_filter=native_court,
        )

    def fetch_unreported_month(
        self,
        month: str,
    ) -> MarylandOpinionIndex:
        if not re.fullmatch(r"(?:19|20)\d{4}", month):
            raise MarylandOpinionsSelectionError(
                "invalid_month",
                "Unreported month must be YYYYMM",
                details={"month": month},
            )
        source_url = f"{UNREPORTED_MONTH_PREFIX}/{month}"
        response = self._get(source_url)
        return parse_unreported_month(
            str(response.text),
            month=month,
            source_url=str(getattr(response, "url", source_url)),
        )

    def fetch_pdf(self, source_url: str) -> MarylandOpinionPDF:
        safe_url = _official_pdf_url(source_url)
        response = self._get(safe_url)
        final_url = _official_pdf_url(str(getattr(response, "url", safe_url)))
        content = bytes(response.content)
        media_type = (
            str(
                getattr(response, "headers", {}).get(
                    "Content-Type",
                    "application/pdf",
                )
            )
            .split(";", 1)[0]
            .strip()
            .lower()
        )
        if not content.startswith(b"%PDF-"):
            raise MarylandOpinionsSourceChangedError(
                "pdf_signature_missing",
                "Maryland appellate-opinion download is not a PDF",
                details={
                    "url": final_url,
                    "content_type": media_type,
                    "size": len(content),
                },
            )
        return MarylandOpinionPDF(
            source_url=final_url,
            content=content,
            media_type=media_type,
            sha256=hashlib.sha256(content).hexdigest(),
        )

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()


def _selection_fingerprint(
    operation: str,
    selection: Mapping[str, Any],
) -> str:
    return _schema_fingerprint(
        {
            "cursor_version": CURSOR_VERSION,
            "source_id": SOURCE_ID,
            "operation": operation,
            "selection": selection,
        }
    )[:24]


def _encode_cursor(
    *,
    operation: str,
    selection_fingerprint: str,
    scope: str,
    anchor: str,
) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "source": SOURCE_ID,
        "operation": operation,
        "selection": selection_fingerprint,
        "scope": scope,
        "anchor": anchor,
    }
    raw = canonical_json(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(
    token: str | None,
    *,
    operation: str,
    selection_fingerprint: str,
) -> dict[str, str] | None:
    if token is None:
        return None
    try:
        padded = token + "=" * (-len(token) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MarylandOpinionsSelectionError(
            "cursor_invalid",
            "Cursor is not a valid Maryland-opinions continuation",
        ) from error
    expected = {
        "v": CURSOR_VERSION,
        "source": SOURCE_ID,
        "operation": operation,
        "selection": selection_fingerprint,
    }
    if not isinstance(payload, dict) or any(
        payload.get(key) != value for key, value in expected.items()
    ):
        raise MarylandOpinionsSelectionError(
            "cursor_query_mismatch",
            "Cursor belongs to a different Maryland-opinions query",
        )
    scope = payload.get("scope")
    anchor = payload.get("anchor")
    if not isinstance(scope, str) or not scope:
        raise MarylandOpinionsSelectionError(
            "cursor_invalid",
            "Cursor scope is missing",
        )
    if not isinstance(anchor, str) or not anchor:
        raise MarylandOpinionsSelectionError(
            "cursor_invalid",
            "Cursor anchor is missing",
        )
    return {"scope": scope, "anchor": anchor}


def _record_matches(
    record: Mapping[str, Any],
    *,
    query_text: str | None,
    court: str,
    date_from: str | None = None,
    date_to: str | None = None,
    match_mode: str = "text",
) -> bool:
    court_data = record.get("court")
    if (
        court != "both"
        and isinstance(court_data, Mapping)
        and court_data.get("court_key") != court
    ):
        return False
    filed_date = str(record.get("filed_date") or "")
    if date_from is not None and filed_date < date_from:
        return False
    if date_to is not None and filed_date > date_to:
        return False
    if query_text is None:
        return True
    if match_mode == "case_number":
        case_numbers = {
            str(value).strip().casefold()
            for value in (
                record.get("raw_case_number"),
                record.get("display_case_number"),
                *(record.get("appeal_numbers") or ()),
            )
            if value is not None and str(value).strip()
        }
        return query_text.strip().casefold() in case_numbers
    if match_mode != "text":
        raise MarylandOpinionsSelectionError(
            "invalid_match_mode",
            "Maryland opinion match mode must be text or case_number",
        )
    searchable = {
        key: record.get(key)
        for key in (
            "raw_case_number",
            "display_case_number",
            "appeal_numbers",
            "docket_file",
            "term",
            "caption",
            "parties_text",
            "appellant",
            "appellee",
            "parties",
            "decision_date",
            "filed_date",
            "source_date_raw",
            "correction_dates",
            "filing_note",
            "judge",
            "citation",
            "citation_status",
            "publication_status",
            "publication_kind",
            "full_text_status",
            "source_month",
            "court",
        )
    }
    return query_text.casefold() in canonical_json(searchable).casefold()


def _records_after_anchor(
    records: Sequence[Mapping[str, Any]],
    anchor: str | None,
) -> Sequence[Mapping[str, Any]]:
    if anchor is None:
        return records
    for index, record in enumerate(records):
        if record.get("canonical_ref") == anchor:
            return records[index + 1 :]
    raise MarylandOpinionsSelectionError(
        "cursor_anchor_missing",
        "Cursor anchor is no longer present in the source index",
        details={"anchor": anchor},
    )


def _page_reported_records(
    index: MarylandOpinionIndex,
    *,
    selection: Mapping[str, Any],
    cursor: dict[str, str] | None,
    limit: int | None,
    selection_fingerprint: str,
) -> tuple[tuple[Mapping[str, Any], ...], str | None]:
    scope = f"reported:{selection['native_court']}:{selection['year']}"
    if cursor is not None and cursor["scope"] != scope:
        raise MarylandOpinionsSelectionError(
            "cursor_scope_mismatch",
            "Cursor does not match the selected reported-opinion index",
        )
    candidates = _records_after_anchor(
        index.records,
        cursor["anchor"] if cursor is not None else None,
    )
    matches = tuple(
        record
        for record in candidates
        if _record_matches(
            record,
            query_text=selection.get("query"),
            court=selection["court"],
            match_mode=selection.get("match_mode", "text"),
        )
    )
    if limit is None or len(matches) <= limit:
        return matches, None
    selected = matches[:limit]
    next_cursor = _encode_cursor(
        operation="reported",
        selection_fingerprint=selection_fingerprint,
        scope=scope,
        anchor=str(selected[-1]["canonical_ref"]),
    )
    return selected, next_cursor


def _reported_selection(args: argparse.Namespace) -> dict[str, Any]:
    year = str(args.year).strip().lower()
    if year != "all":
        try:
            parsed_year = int(year)
        except ValueError as error:
            raise MarylandOpinionsSelectionError(
                "invalid_year",
                "--year must be a four-digit year or all",
                details={"year": year},
            ) from error
        if parsed_year < 1995 or parsed_year > date.today().year:
            raise MarylandOpinionsSelectionError(
                "year_outside_reported_coverage",
                "Requested year is outside the source-published reported index",
                details={"year": parsed_year, "coverage_start": 1995},
            )
        year = str(parsed_year)
    return {
        "collection": "reported",
        "court": args.court,
        "native_court": REPORTED_COURTS[args.court],
        "year": year,
        "order": args.order,
        "native_order": REPORTED_ORDERS[args.order],
        "query": _text(args.query),
        "match_mode": getattr(args, "match_mode", "text"),
    }


def _unreported_date_selection(
    args: argparse.Namespace,
) -> tuple[str | None, str | None]:
    date_from = _parse_user_date(args.date_from, "--date-from")
    date_to = _parse_user_date(args.date_to, "--date-to")
    if date_from and date_to and date_from > date_to:
        raise MarylandOpinionsSelectionError(
            "invalid_date_range",
            "--date-from must not be later than --date-to",
        )
    return date_from, date_to


def _select_unreported_months(
    args: argparse.Namespace,
    directory: MarylandUnreportedDirectory,
    *,
    date_from: str | None,
    date_to: str | None,
) -> tuple[str, ...]:
    if args.month and (
        args.year is not None
        or args.all_months
        or date_from is not None
        or date_to is not None
    ):
        raise MarylandOpinionsSelectionError(
            "month_selectors_conflict",
            "--month cannot be combined with year, all-months, or date bounds",
        )
    if args.year is not None and (
        args.all_months or date_from is not None or date_to is not None
    ):
        raise MarylandOpinionsSelectionError(
            "year_selectors_conflict",
            "--year cannot be combined with all-months or date bounds",
        )
    if args.all_months and (date_from is not None or date_to is not None):
        raise MarylandOpinionsSelectionError(
            "all_months_selectors_conflict",
            "--all-months cannot be combined with date bounds",
        )
    available = directory.months
    if args.month:
        requested = _parse_month(args.month)
        return (requested,) if requested in available else ()
    if args.year is not None:
        year = str(args.year)
        return tuple(month for month in available if month.startswith(year))
    if args.all_months:
        return available
    if date_from is not None or date_to is not None:
        selected: list[str] = []
        for month in available:
            month_start = f"{month[:4]}-{month[4:]}-01"
            year = int(month[:4])
            month_number = int(month[4:])
            if month_number == 12:
                next_month = date(year + 1, 1, 1)
            else:
                next_month = date(year, month_number + 1, 1)
            month_end = next_month.fromordinal(next_month.toordinal() - 1).isoformat()
            if date_from is not None and month_end < date_from:
                continue
            if date_to is not None and month_start > date_to:
                continue
            selected.append(month)
        return tuple(selected)
    return available[:1]


def _unreported_selection(
    args: argparse.Namespace,
    *,
    months: Sequence[str],
    date_from: str | None,
    date_to: str | None,
) -> dict[str, Any]:
    return {
        "collection": "unreported",
        "court": args.court,
        "months": list(months),
        "date_from": date_from,
        "date_to": date_to,
        "query": _text(args.query),
        "match_mode": getattr(args, "match_mode", "text"),
    }


def _collect_unreported(
    client: MarylandOpinionsClient | Any,
    *,
    months: Sequence[str],
    selection: Mapping[str, Any],
    cursor: dict[str, str] | None,
    limit: int | None,
    selection_fingerprint: str,
) -> tuple[
    tuple[Mapping[str, Any], ...],
    str | None,
    tuple[str, ...],
    tuple[str, ...],
]:
    start_month_index = 0
    anchor: str | None = None
    if cursor is not None:
        if not cursor["scope"].startswith("unreported:"):
            raise MarylandOpinionsSelectionError(
                "cursor_scope_mismatch",
                "Cursor does not match an unreported-opinion month",
            )
        cursor_month = cursor["scope"].split(":", 1)[1]
        try:
            start_month_index = list(months).index(cursor_month)
        except ValueError as error:
            raise MarylandOpinionsSelectionError(
                "cursor_month_missing",
                "Cursor month is outside the selected unreported indexes",
                details={"month": cursor_month},
            ) from error
        anchor = cursor["anchor"]

    records: list[Mapping[str, Any]] = []
    source_urls: list[str] = []
    schema_fingerprints: list[str] = []
    for month_index in range(start_month_index, len(months)):
        month = months[month_index]
        page = client.fetch_unreported_month(month)
        source_urls.append(page.source_url)
        schema_fingerprints.append(page.schema_fingerprint)
        candidates = page.records
        if month_index == start_month_index and anchor is not None:
            candidates = tuple(_records_after_anchor(candidates, anchor))
        for raw_index, record in enumerate(candidates):
            if not _record_matches(
                record,
                query_text=selection.get("query"),
                court=selection["court"],
                date_from=selection.get("date_from"),
                date_to=selection.get("date_to"),
                match_mode=selection.get("match_mode", "text"),
            ):
                continue
            records.append(record)
            if limit is None or len(records) < limit:
                continue
            has_matching_in_month = any(
                _record_matches(
                    remaining,
                    query_text=selection.get("query"),
                    court=selection["court"],
                    date_from=selection.get("date_from"),
                    date_to=selection.get("date_to"),
                    match_mode=selection.get("match_mode", "text"),
                )
                for remaining in candidates[raw_index + 1 :]
            )
            has_more = has_matching_in_month or month_index < len(months) - 1
            next_cursor = None
            if has_more:
                next_cursor = _encode_cursor(
                    operation="unreported",
                    selection_fingerprint=selection_fingerprint,
                    scope=f"unreported:{month}",
                    anchor=str(record["canonical_ref"]),
                )
            return (
                tuple(records),
                next_cursor,
                tuple(source_urls),
                tuple(schema_fingerprints),
            )
        anchor = None
    return (
        tuple(records),
        None,
        tuple(source_urls),
        tuple(schema_fingerprints),
    )


def _source_manifest() -> dict[str, Any]:
    return {
        "source": SOURCE_METADATA.to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "operations": {
            "reported": (
                "query one complete source-native court/year index, then "
                "filter and continue with an anchor cursor"
            ),
            "unreported": ("discover and traverse source-published monthly indexes"),
            "routes": "discover current reported years and unreported months",
            "download": "download and hash one source-listed opinion PDF",
            "probe": "verify both index schemas and one linked PDF",
        },
        "identity": {
            "case": "court plus docket-file/term",
            "reported_document": "court/year/PDF filename",
            "unreported_document": (
                "source PDF filename when linked; otherwise court, case, "
                "and filing date metadata identity"
            ),
            "corrections": (
                "retain document identity while preserving every source "
                "correction annotation and changed PDF hash"
            ),
        },
        "coverage": {
            "reported": "1995-present by filing year",
            "unreported_metadata": "2001-02-present monthly indexes",
            "unreported_linked_full_text": "2015-05-present",
        },
        "related_source_routes": [
            {
                "source_id": "us-md-case-search",
                "name": "Maryland Judiciary Case Search",
                "url": CASE_SEARCH_URL,
                "role": "statewide_case_and_docket_detail",
                "operation_state": "interactive_captcha",
                "join_keys": ["case_number", "party_name", "court"],
            },
            {
                "source_id": "us-md-mdec-public-cases",
                "name": "Maryland MDEC Cases Filed reports",
                "url": MDEC_REPORTS_URL,
                "role": "rolling_recent_case_creation_feed",
                "join_keys": ["case_number", "party_name", "court"],
            },
            {
                "source_id": "us-md-judgment-liens",
                "name": "Maryland Judgment and Liens Search",
                "url": JUDGMENT_LIENS_URL,
                "role": "circuit_court_judgment_and_lien_index",
                "join_keys": ["case_number", "party_name", "court"],
            },
            {
                "source_id": "us-md-estate-search",
                "name": "Maryland Register of Wills Estate Search",
                "url": ESTATE_SEARCH_URL,
                "role": "estate_case_parties_status_and_docket",
                "join_keys": ["estate_number", "party_name", "county"],
            },
        ],
    }


def _query(
    args: argparse.Namespace,
    *,
    selection: Mapping[str, Any],
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=selection,
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
            metadata={"adapter_schema": OUTPUT_SCHEMA_VERSION},
        ),
    )


def _failure(
    query: PublicRecordsQuery,
    error: MarylandOpinionsError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def _client_from_args(args: argparse.Namespace) -> MarylandOpinionsClient:
    return MarylandOpinionsClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )


def execute(
    args: argparse.Namespace,
    *,
    client: MarylandOpinionsClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one CLI operation and return the shared result envelope."""

    query: PublicRecordsQuery | None = None
    own_client = client is None
    source_client = client
    result: PublicRecordsResult
    try:
        if args.command == "manifest":
            query = _query(args, selection={})
            result = PublicRecordsResult.success(
                query,
                [_source_manifest()],
                warnings=SOURCE_WARNINGS,
            )
        else:
            source_client = source_client or _client_from_args(args)
            if args.command == "routes":
                query = _query(args, selection={})
                reported = source_client.fetch_reported_landing()
                unreported = source_client.fetch_unreported_directory()
                record = {
                    "source_id": SOURCE_ID,
                    "record_kind": "source_routes",
                    "reported": {
                        "years": list(reported.years),
                        "native_courts": list(reported.native_courts),
                        "native_orders": list(reported.native_orders),
                        "source_url": reported.source_url,
                        "schema_fingerprint": (reported.schema_fingerprint),
                    },
                    "unreported": {
                        "months": [_month_label(month) for month in unreported.months],
                        "source_url": unreported.source_url,
                        "schema_fingerprint": (unreported.schema_fingerprint),
                    },
                }
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    raw_artifact_refs=[
                        reported.source_url,
                        unreported.source_url,
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "reported":
                selection = _reported_selection(args)
                query = _query(args, selection=selection)
                fingerprint = _selection_fingerprint("reported", selection)
                cursor = _decode_cursor(
                    args.cursor,
                    operation="reported",
                    selection_fingerprint=fingerprint,
                )
                index = source_client.fetch_reported(
                    native_court=selection["native_court"],
                    year=selection["year"],
                    native_order=selection["native_order"],
                )
                records, next_cursor = _page_reported_records(
                    index,
                    selection=selection,
                    cursor=cursor,
                    limit=args.limit,
                    selection_fingerprint=fingerprint,
                )
                result = PublicRecordsResult.success(
                    query,
                    records,
                    next_cursor=next_cursor,
                    raw_artifact_refs=[index.source_url],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "unreported":
                date_from, date_to = _unreported_date_selection(args)
                directory = source_client.fetch_unreported_directory()
                months = _select_unreported_months(
                    args,
                    directory,
                    date_from=date_from,
                    date_to=date_to,
                )
                selection = _unreported_selection(
                    args,
                    months=months,
                    date_from=date_from,
                    date_to=date_to,
                )
                query = _query(args, selection=selection)
                if not months:
                    result = PublicRecordsResult.success(
                        query,
                        [],
                        raw_artifact_refs=[directory.source_url],
                        warnings=SOURCE_WARNINGS,
                    )
                else:
                    fingerprint = _selection_fingerprint("unreported", selection)
                    cursor = _decode_cursor(
                        args.cursor,
                        operation="unreported",
                        selection_fingerprint=fingerprint,
                    )
                    (
                        records,
                        next_cursor,
                        source_urls,
                        _schema_fingerprints,
                    ) = _collect_unreported(
                        source_client,
                        months=months,
                        selection=selection,
                        cursor=cursor,
                        limit=args.limit,
                        selection_fingerprint=fingerprint,
                    )
                    result = PublicRecordsResult.success(
                        query,
                        records,
                        next_cursor=next_cursor,
                        raw_artifact_refs=[
                            directory.source_url,
                            *source_urls,
                        ],
                        warnings=SOURCE_WARNINGS,
                    )
            elif args.command == "download":
                safe_url = _official_pdf_url(args.url)
                selection = {
                    "url": safe_url,
                    "destination": str(args.destination),
                }
                query = _query(args, selection=selection)
                pdf = source_client.fetch_pdf(safe_url)
                args.destination.parent.mkdir(parents=True, exist_ok=True)
                args.destination.write_bytes(pdf.content)
                record = {
                    "canonical_ref": f"MDAPPOPINIONPDF:{pdf.sha256}",
                    "source_id": SOURCE_ID,
                    "record_kind": "document_artifact",
                    "document_type": "appellate_decision",
                    "source_url": pdf.source_url,
                    "local_path": str(args.destination),
                    "mime_type": pdf.media_type,
                    "size_bytes": len(pdf.content),
                    "sha256": pdf.sha256,
                    "access_state": "public",
                }
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    raw_artifact_refs=[str(args.destination)],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "probe":
                query = _query(args, selection={})
                reported_landing = source_client.fetch_reported_landing()
                directory = source_client.fetch_unreported_directory()
                reported_index = None
                for year in reported_landing.years:
                    candidate = source_client.fetch_reported(
                        native_court="both",
                        year=str(year),
                        native_order="bydate",
                    )
                    if candidate.records:
                        reported_index = candidate
                        break
                if reported_index is None:
                    raise MarylandOpinionsSourceChangedError(
                        "reported_probe_empty",
                        "No reported opinions were found in published years",
                    )
                unreported_index = None
                for month in directory.months:
                    candidate = source_client.fetch_unreported_month(month)
                    if candidate.records:
                        unreported_index = candidate
                        break
                if unreported_index is None:
                    raise MarylandOpinionsSourceChangedError(
                        "unreported_probe_empty",
                        "No unreported opinions were found in published months",
                    )
                downloadable = next(
                    (
                        record
                        for record in (
                            *unreported_index.records,
                            *reported_index.records,
                        )
                        if record.get("pdf_url")
                    ),
                    None,
                )
                if downloadable is None:
                    raise MarylandOpinionsSourceChangedError(
                        "probe_pdf_missing",
                        "Current opinion indexes contain no downloadable PDF",
                    )
                pdf = source_client.fetch_pdf(str(downloadable["pdf_url"]))
                record = {
                    "source_id": SOURCE_ID,
                    "record_kind": "source_probe",
                    "reported_year_count": len(reported_landing.years),
                    "reported_sample_count": reported_index.native_count,
                    "reported_schema_fingerprint": (reported_index.schema_fingerprint),
                    "unreported_month_count": len(directory.months),
                    "unreported_sample_month": (
                        unreported_index.records[0]["source_month"]
                    ),
                    "unreported_sample_count": (unreported_index.native_count),
                    "unreported_schema_fingerprint": (
                        unreported_index.schema_fingerprint
                    ),
                    "pdf_url": pdf.source_url,
                    "pdf_sha256": pdf.sha256,
                    "pdf_size_bytes": len(pdf.content),
                    "pdf_media_type": pdf.media_type,
                }
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    raw_artifact_refs=[
                        reported_landing.source_url,
                        reported_index.source_url,
                        directory.source_url,
                        unreported_index.source_url,
                        pdf.source_url,
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                raise AssertionError(f"unknown command: {args.command}")
    except MarylandOpinionsError as error:
        query = query or _query(
            args,
            selection={"command": args.command},
        )
        result = _failure(query, error)
    finally:
        if own_client and source_client is not None:
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


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--max-attempts", type=_positive_int, default=3)
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Maryland reported and unreported appellate opinions"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest = subparsers.add_parser(
        "manifest",
        help="Show source roles, coverage, identity, and related routes",
    )
    _add_runtime_and_output(manifest)

    routes = subparsers.add_parser(
        "routes",
        help="Discover source-published reported years and unreported months",
    )
    _add_runtime_and_output(routes)

    reported = subparsers.add_parser(
        "reported",
        help="Query one complete reported-opinion court/year index",
    )
    reported.add_argument(
        "--court",
        choices=tuple(REPORTED_COURTS),
        default="both",
    )
    reported.add_argument("--year", default=str(date.today().year))
    reported.add_argument(
        "--order",
        choices=tuple(REPORTED_ORDERS),
        default="date",
    )
    reported.add_argument(
        "--query",
        help="Filter returned index metadata by text",
    )
    reported.add_argument("--limit", type=_positive_int)
    reported.add_argument("--cursor")
    _add_runtime_and_output(reported)

    unreported = subparsers.add_parser(
        "unreported",
        help="Discover and query monthly unreported-opinion indexes",
    )
    unreported.add_argument("--month", help="One month in YYYY-MM form")
    unreported.add_argument("--year", type=int)
    unreported.add_argument(
        "--all-months",
        action="store_true",
        help="Traverse every source-published monthly index",
    )
    unreported.add_argument("--date-from")
    unreported.add_argument("--date-to")
    unreported.add_argument(
        "--court",
        choices=tuple(REPORTED_COURTS),
        default="both",
    )
    unreported.add_argument(
        "--query",
        help="Filter returned index metadata by text",
    )
    unreported.add_argument("--limit", type=_positive_int)
    unreported.add_argument("--cursor")
    _add_runtime_and_output(unreported)

    download = subparsers.add_parser(
        "download",
        help="Download and hash one source-listed decision PDF",
    )
    download.add_argument("url")
    download.add_argument("destination", type=Path)
    _add_runtime_and_output(download)

    probe = subparsers.add_parser(
        "probe",
        help="Verify both index schemas and one linked PDF",
    )
    _add_runtime_and_output(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(f"Maryland appellate opinions {args.command} ({result.status.value})"),
        result_count=len(result.records),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2))
        return
    print(
        f"Maryland appellate opinions {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    args = build_parser().parse_args()
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.minimum_interval < 0:
        raise SystemExit("--minimum-interval must not be negative")
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
