#!/usr/bin/env python3
"""Query Maryland's official Business and Technology trial-court opinions.

The Maryland Judiciary publishes one current table (2009-present) and six
annual archive tables (2003-2008).  Each row is a source publication rather
than a complete docket: it may contain an opinion, order, synopsis, or several
formats of the same document.

Examples:
    uv run python tools/query_md_business_opinions.py search \
        --query "Lockheed Martin" --all-pages --output /tmp/md-bt.json
    uv run python tools/query_md_business_opinions.py search \
        --year 2008 --document-type order --output /tmp/md-bt-orders.json
    uv run python tools/query_md_business_opinions.py routes --json
    uv run python tools/query_md_business_opinions.py download URL DESTINATION --json
    uv run python tools/query_md_business_opinions.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import calendar
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote, urljoin, urlsplit

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


SOURCE_ID = "us-md-business-technology-opinions"
STATE_CODE = "MD"
STATE_GEOID = "24"
BASE_URL = "https://www.mdcourts.gov"
CURRENT_URL = f"{BASE_URL}/businesstech/opinions"
ARCHIVE_INDEX_URL = f"{BASE_URL}/businesstech/opinions_archive"
CASE_SEARCH_URL = "https://casesearch.mdcourts.gov/casesearch/"
MDEC_REPORTS_URL = f"{BASE_URL}/mdec/publiccases"
JUDGMENT_LIENS_URL = "https://jportal.mdcourts.gov/judgment/judgementSearch.jsf"
APPELLATE_OPINIONS_URL = f"{BASE_URL}/opinions/opinions"
COURT_RECORDS_URL = f"{BASE_URL}/courts/courtrecords"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)
OUTPUT_SCHEMA_VERSION = "maryland-business-technology-opinions/1.0"
CURSOR_VERSION = 1

EXPECTED_HEADERS = (
    "MDBT Opinion# / Court / Case# / Judge / Date Filed",
    "Parties / Counsel / Synopsis / Opinion",
)
_ARCHIVE_ROUTE_RE = re.compile(r"^/businesstech/opinions_archive(20(?:0[3-8]))/?$")
_PUBLICATION_RE = re.compile(
    r"^\s*(?:(?P<year>20\d{2})\s*(?:-\s*)?)?MDBT"
    r"(?:\s*-\s*|\s+)?(?P<number>\d+)?\s*$",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"^(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}[-/]\d{2,4})$")
_JUDGE_RE = re.compile(r"^(?:J\.|Judge\b)", re.IGNORECASE)
_COURT_RE = re.compile(r"^(?:Circuit Court|CC)\s+for\s+(.+)$", re.IGNORECASE)
_FILE_YEAR_FIRST_RE = re.compile(
    r"mdbt(?P<year>20\d{2})[-_]?0*(?P<number>\d{1,2})(?=[^0-9]|$)",
    re.IGNORECASE,
)
_FILE_NUMBER_YEAR_RE = re.compile(
    r"mdbt(?P<number>\d{1,2})[-_](?P<year>\d{2})(?=[^0-9]|$)",
    re.IGNORECASE,
)
_FILE_NUMBER_ONLY_RE = re.compile(
    r"mdbt(?P<number>\d{1,2})(?=[^0-9]|$)",
    re.IGNORECASE,
)
_CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "challenges.cloudflare.com",
    "cf-chl-",
)
_DOCUMENT_TYPES = ("opinion", "order", "synopsis")

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Maryland Business and Technology Published Opinions",
    source_role="official_selective_circuit_court_decision_publication",
    base_url=CURRENT_URL,
    dataset_id="maryland-business-technology-opinions",
    metadata={
        "authority": "Maryland Judiciary",
        "program": "Business and Technology Case Management Program",
        "authentication": "none",
        "current_index": {
            "url": CURRENT_URL,
            "coverage": "2009-present",
            "native_pagination": "complete_table",
        },
        "archive_index": {
            "url": ARCHIVE_INDEX_URL,
            "coverage": "2003-2008",
            "native_pagination": "annual_complete_tables",
        },
        "evidentiary_role": "official_trial_court_opinion_and_order_publication",
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Maryland",
    state_code=STATE_CODE,
)

SOURCE_WARNINGS = (
    "This is a selective publication archive for Maryland's Business and "
    "Technology Case Management Program, not a complete statewide docket.",
    "Source rows sometimes omit a filing date or case number; those omissions "
    "are retained as source state.",
    "Exact attachment URLs are retained because the official index contains "
    "occasional duplicated or designation-mismatched links.",
)


class MarylandBusinessOpinionsError(RuntimeError):
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


class MarylandBusinessOpinionsSelectionError(MarylandBusinessOpinionsError):
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


class MarylandBusinessOpinionsSourceChangedError(MarylandBusinessOpinionsError):
    """The official page no longer matches the verified source structure."""

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
class MarylandBusinessRoutes:
    archive_years: tuple[int, ...]
    archive_urls: Mapping[int, str]
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class MarylandBusinessOpinionIndex:
    records: tuple[Mapping[str, Any], ...]
    source_url: str
    schema_fingerprint: str
    publication_scope: str
    native_count: int


@dataclass(frozen=True)
class MarylandBusinessDocument:
    source_url: str
    content: bytes
    media_type: str
    sha256: str


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return normalized or "unknown"


def _schema_fingerprint(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _normalize_headers(table: Tag) -> tuple[str, ...]:
    header_row = table.find("thead")
    if header_row is None:
        return ()
    return tuple(
        _clean_text(cell.get_text(" ", strip=True))
        for cell in header_row.find_all("th")
    )


def _opinion_table(soup: BeautifulSoup) -> Tag:
    for table in soup.find_all("table"):
        headers = _normalize_headers(table)
        if headers == EXPECTED_HEADERS:
            return table
    found = [_normalize_headers(table) for table in soup.find_all("table")]
    raise MarylandBusinessOpinionsSourceChangedError(
        "opinion_table_schema_changed",
        "Maryland Business and Technology opinion table headers changed",
        details={
            "expected_headers": list(EXPECTED_HEADERS),
            "found_headers": [list(headers) for headers in found if headers],
        },
    )


def parse_archive_directory(
    html: str,
    *,
    source_url: str = ARCHIVE_INDEX_URL,
) -> MarylandBusinessRoutes:
    """Parse source-published annual archive routes."""

    soup = BeautifulSoup(html, "html.parser")
    routes: dict[int, str] = {}
    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(source_url, str(anchor["href"]))
        parsed = urlsplit(absolute)
        if parsed.scheme != "https" or parsed.netloc.casefold() not in {
            "www.mdcourts.gov",
            "mdcourts.gov",
        }:
            continue
        match = _ARCHIVE_ROUTE_RE.fullmatch(parsed.path)
        if match is None:
            continue
        year = int(match.group(1))
        routes[year] = absolute
    if not routes:
        raise MarylandBusinessOpinionsSourceChangedError(
            "archive_routes_missing",
            "Maryland Business and Technology archive directory has no annual routes",
            details={"url": source_url},
        )
    years = tuple(sorted(routes, reverse=True))
    return MarylandBusinessRoutes(
        archive_years=years,
        archive_urls={year: routes[year] for year in years},
        source_url=source_url,
        schema_fingerprint=_schema_fingerprint(
            {
                "route_pattern": _ARCHIVE_ROUTE_RE.pattern,
                "years": list(years),
            }
        ),
    )


def _parse_publication(
    value: str,
    *,
    expected_publication_year: int | None,
) -> tuple[int, int | None, str]:
    match = _PUBLICATION_RE.fullmatch(value)
    if match is None:
        raise MarylandBusinessOpinionsSourceChangedError(
            "publication_designation_changed",
            "Opinion row has an unrecognized MDBT publication designation",
            details={"designation": value},
        )
    year_text = match.group("year")
    if year_text is None and expected_publication_year is None:
        raise MarylandBusinessOpinionsSourceChangedError(
            "publication_year_missing",
            "Current opinion row omits its MDBT publication year",
            details={"designation": value},
        )
    year = int(year_text) if year_text is not None else int(expected_publication_year)
    number_text = match.group("number")
    number = int(number_text) if number_text else None
    normalized = f"{year} MDBT"
    if number is not None:
        normalized = f"{normalized}-{number}"
    return year, number, normalized


def _parse_date(value: str) -> tuple[str, str]:
    for date_format in ("%m-%d-%Y", "%m-%d-%y", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(value, date_format).date().isoformat(), "day"
        except ValueError:
            continue
    for date_format in ("%m-%Y", "%m-%y", "%m/%Y", "%m/%y"):
        try:
            parsed = datetime.strptime(value, date_format)
            return f"{parsed.year:04d}-{parsed.month:02d}", "month"
        except ValueError:
            continue
    raise MarylandBusinessOpinionsSourceChangedError(
        "filing_date_unrecognized",
        "Opinion row contains an unrecognized filing date",
        details={"date": value},
    )


def _parse_court(value: str) -> dict[str, Any]:
    match = _COURT_RE.fullmatch(value)
    if match is None:
        raise MarylandBusinessOpinionsSourceChangedError(
            "court_name_unrecognized",
            "Opinion row contains an unrecognized Maryland circuit court",
            details={"court": value},
        )
    locality = _clean_text(match.group(1))
    county = locality[:-7] if locality.casefold().endswith(" county") else locality
    if county.casefold() == "baltimore city":
        display_name = "Circuit Court for Baltimore City"
        locality_type = "independent_city"
    else:
        display_name = f"Circuit Court for {county} County"
        locality_type = "county"
    return {
        "court_id": f"md-circuit-{_slug(county)}",
        "name": display_name,
        "name_at_source": value,
        "county": county,
        "locality_type": locality_type,
        "state_code": STATE_CODE,
        "level": "trial",
    }


def _official_attachment_url(value: str, *, base_url: str = BASE_URL) -> str:
    candidate = urljoin(base_url, _clean_text(value))
    parsed = urlsplit(candidate)
    if parsed.scheme != "https" or parsed.netloc.casefold() not in {
        "www.mdcourts.gov",
        "mdcourts.gov",
    }:
        raise MarylandBusinessOpinionsSelectionError(
            "unofficial_document_url",
            "Document URL must be on the official Maryland Judiciary HTTPS host",
            details={"url": value},
        )
    path = parsed.path.casefold()
    if "/businesstech/" not in path:
        raise MarylandBusinessOpinionsSelectionError(
            "document_route_outside_source",
            "Document URL is outside the Business and Technology publication tree",
            details={"url": value},
        )
    return candidate


def _media_type_for_path(path: str) -> str:
    suffix = Path(urlsplit(path).path).suffix.casefold()
    return {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        ".wpd": "application/vnd.wordperfect",
    }.get(suffix, "application/octet-stream")


def _section_name(anchor: Tag) -> str:
    strong = anchor.find_previous("strong")
    if strong is None:
        return "document"
    label = _clean_text(strong.get_text(" ", strip=True)).rstrip(":").casefold()
    return label if label in _DOCUMENT_TYPES else "document"


def _right_cell_text(cell: Tag) -> tuple[str, str | None]:
    lines = [
        _clean_text(line)
        for line in cell.get_text("\n", strip=True).splitlines()
        if _clean_text(line)
    ]
    section_index = len(lines)
    for index, line in enumerate(lines):
        if re.match(
            r"^(?:Counsel|Synopsis|Opinion|Order)\s*:?\s*$",
            line,
            re.IGNORECASE,
        ) or re.match(r"^Counsel\s*:", line, re.IGNORECASE):
            section_index = index
            break
    caption = " / ".join(lines[:section_index])
    counsel: str | None = None
    for index, line in enumerate(lines):
        match = re.match(r"^Counsel\s*:\s*(.*)$", line, re.IGNORECASE)
        if match is None:
            continue
        parts: list[str] = []
        if match.group(1):
            parts.append(_clean_text(match.group(1)))
        for following in lines[index + 1 :]:
            if re.match(
                r"^(?:Synopsis|Opinion|Order)\s*:",
                following,
                re.IGNORECASE,
            ):
                break
            parts.append(following)
        counsel = " ".join(parts) or None
        break
    return caption, counsel


def _attachment_anomalies(
    document_url: str,
    *,
    publication_year: int,
    publication_number: int | None,
) -> list[dict[str, Any]]:
    parsed = urlsplit(document_url)
    anomalies: list[dict[str, Any]] = []
    if "/files/files/" in parsed.path.casefold():
        anomalies.append(
            {
                "code": "duplicated_path_segment_at_source",
                "detail": "Official attachment path contains /files/files/.",
            }
        )
    filename = Path(parsed.path).name
    year_first = _FILE_YEAR_FIRST_RE.search(filename)
    number_year = _FILE_NUMBER_YEAR_RE.search(filename)
    number_only = _FILE_NUMBER_ONLY_RE.search(filename)
    if year_first is not None:
        file_number = int(year_first.group("number"))
        file_year = int(year_first.group("year"))
    elif number_year is not None:
        file_number = int(number_year.group("number"))
        file_year = 2000 + int(number_year.group("year"))
    elif number_only is not None:
        file_number = int(number_only.group("number"))
        file_year = None
    else:
        return anomalies
    if publication_number is None:
        anomalies.append(
            {
                "code": "publication_number_omitted_at_source",
                "detail": (
                    "The publication row omits an MDBT number while its "
                    "attachment filename contains one."
                ),
                "filename": filename,
            }
        )
        return anomalies
    if file_number != publication_number or (
        file_year is not None and file_year != publication_year
    ):
        anomalies.append(
            {
                "code": "attachment_designation_mismatch_at_source",
                "detail": (
                    "Attachment filename designation differs from the publication row."
                ),
                "filename": filename,
                "publication_designation": (
                    f"{publication_year} MDBT-{publication_number}"
                ),
            }
        )
    return anomalies


def _publication_ref(
    *,
    court_id: str,
    case_number: str | None,
    publication_designation: str,
) -> str:
    if case_number:
        return canonical_court_ref(
            SOURCE_ID,
            court_id,
            case_number,
            "published_opinion",
            publication_designation,
        )
    parts = (
        SOURCE_ID,
        court_id,
        "published_opinion_without_source_case_number",
        publication_designation,
    )
    return "STATECOURT:" + "/".join(quote(part, safe=".-_") for part in parts)


def _parse_row(
    row: Tag,
    *,
    source_url: str,
    native_row_number: int,
    expected_publication_year: int | None,
) -> dict[str, Any]:
    cells = row.find_all("td", recursive=False)
    if len(cells) != 2:
        raise MarylandBusinessOpinionsSourceChangedError(
            "opinion_row_shape_changed",
            "Opinion table row no longer contains two source cells",
            details={
                "source_url": source_url,
                "native_row_number": native_row_number,
                "cell_count": len(cells),
            },
        )
    left_lines = [
        _clean_text(value) for value in cells[0].stripped_strings if _clean_text(value)
    ]
    if len(left_lines) < 3:
        raise MarylandBusinessOpinionsSourceChangedError(
            "opinion_metadata_missing",
            "Opinion row contains too few metadata lines",
            details={
                "source_url": source_url,
                "native_row_number": native_row_number,
                "lines": left_lines,
            },
        )
    publication_year, publication_number, designation = _parse_publication(
        left_lines[0],
        expected_publication_year=expected_publication_year,
    )
    if (
        expected_publication_year is not None
        and publication_year != expected_publication_year
    ):
        raise MarylandBusinessOpinionsSourceChangedError(
            "archive_year_mismatch",
            "Annual archive contains a different MDBT publication year",
            details={
                "source_url": source_url,
                "expected_year": expected_publication_year,
                "found_year": publication_year,
            },
        )
    court = _parse_court(left_lines[1])
    judge: str | None = None
    filed_date_raw: str | None = None
    filed_date: str | None = None
    date_precision: str | None = None
    case_numbers: list[str] = []
    source_notes: list[str] = []
    for value in left_lines[2:]:
        if _DATE_RE.fullmatch(value):
            if filed_date_raw is not None:
                source_notes.append(value)
                continue
            filed_date_raw = value
            filed_date, date_precision = _parse_date(value)
        elif _JUDGE_RE.match(value):
            if judge is None:
                judge = value
            else:
                source_notes.append(value)
        elif filed_date_raw is not None or re.match(
            r"^(?:aff'?d|rev'?d|vacated|appeal\b)",
            value,
            re.IGNORECASE,
        ):
            source_notes.append(value)
        else:
            case_numbers.append(value)
    case_number = case_numbers[0] if case_numbers else None

    caption, counsel = _right_cell_text(cells[1])
    if not caption:
        raise MarylandBusinessOpinionsSourceChangedError(
            "opinion_caption_missing",
            "Opinion row contains no party caption",
            details={
                "source_url": source_url,
                "native_row_number": native_row_number,
            },
        )
    documents: list[dict[str, Any]] = []
    record_anomalies: list[dict[str, Any]] = []
    for document_number, anchor in enumerate(cells[1].find_all("a", href=True), 1):
        document_url = _official_attachment_url(
            str(anchor["href"]),
            base_url=source_url,
        )
        document_type = _section_name(anchor)
        suffix = Path(urlsplit(document_url).path).suffix.casefold().lstrip(".")
        anomalies = _attachment_anomalies(
            document_url,
            publication_year=publication_year,
            publication_number=publication_number,
        )
        record_anomalies.extend(anomalies)
        documents.append(
            {
                "document_number": document_number,
                "document_type": document_type,
                "format_label": _clean_text(anchor.get_text(" ", strip=True)),
                "file_format": suffix or None,
                "media_type": _media_type_for_path(document_url),
                "source_url": document_url,
                "native_path": urlsplit(document_url).path,
                "source_link_state": "listed_by_source",
                "source_link_anomalies": anomalies,
            }
        )
    if not documents:
        raise MarylandBusinessOpinionsSourceChangedError(
            "opinion_documents_missing",
            "Opinion row contains no linked publication document",
            details={
                "source_url": source_url,
                "native_row_number": native_row_number,
            },
        )
    source_omissions = []
    if case_number is None:
        source_omissions.append("case_number")
    if filed_date is None:
        source_omissions.append("filed_date")
    if judge is None:
        source_omissions.append("judge")

    canonical_ref = _publication_ref(
        court_id=str(court["court_id"]),
        case_number=case_number,
        publication_designation=designation,
    )
    case_ref = (
        canonical_court_ref(
            SOURCE_ID,
            str(court["court_id"]),
            case_number,
            "case",
        )
        if case_number
        else None
    )
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "case_canonical_ref": case_ref,
        "source_id": SOURCE_ID,
        "record_kind": "published_trial_court_opinion",
        "native_publication_id": designation,
        "publication_designation": designation,
        "publication_designation_at_source": left_lines[0],
        "publication_year": publication_year,
        "publication_number": publication_number,
        "court": court,
        "case_number": case_number,
        "case_number_at_source": case_number,
        "case_numbers_at_source": case_numbers,
        "judge": judge,
        "filed_date": filed_date,
        "filed_date_at_source": filed_date_raw,
        "date_precision": date_precision,
        "caption": caption,
        "counsel": counsel,
        "source_notes": source_notes,
        "source_omissions": source_omissions,
        "documents": documents,
        "document_types": sorted(
            {str(document["document_type"]) for document in documents}
        ),
        "source_link_anomalies": record_anomalies,
        "provenance": {
            "source_url": source_url,
            "native_row_number": native_row_number,
            "access_state": "public",
        },
    }


def _mark_shared_urls(records: list[dict[str, Any]]) -> None:
    url_rows: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        for document in record["documents"]:
            url_rows.setdefault(str(document["source_url"]), []).append(record)
    for document_url, linked_records in url_rows.items():
        designations = sorted(
            {str(record["publication_designation"]) for record in linked_records}
        )
        if len(designations) < 2:
            continue
        anomaly = {
            "code": "attachment_url_shared_by_source_rows",
            "detail": "The official index lists this attachment URL on multiple rows.",
            "source_url": document_url,
            "publication_designations": designations,
        }
        for record in linked_records:
            record["source_link_anomalies"].append(anomaly)
            for document in record["documents"]:
                if document["source_url"] == document_url:
                    document["source_link_anomalies"].append(anomaly)


def parse_opinion_page(
    html: str,
    *,
    source_url: str,
    expected_publication_year: int | None = None,
) -> MarylandBusinessOpinionIndex:
    """Parse one current or annual source-native opinion table."""

    soup = BeautifulSoup(html, "html.parser")
    table = _opinion_table(soup)
    body = table.find("tbody")
    if body is None:
        raise MarylandBusinessOpinionsSourceChangedError(
            "opinion_table_body_missing",
            "Maryland opinion table has no body",
            details={"source_url": source_url},
        )
    rows = body.find_all("tr", recursive=False)
    if not rows:
        raise MarylandBusinessOpinionsSourceChangedError(
            "opinion_table_empty",
            "Maryland opinion table contains no publication rows",
            details={"source_url": source_url},
        )
    records = [
        _parse_row(
            row,
            source_url=source_url,
            native_row_number=index,
            expected_publication_year=expected_publication_year,
        )
        for index, row in enumerate(rows, 1)
    ]
    _mark_shared_urls(records)
    fingerprint = _schema_fingerprint(
        {
            "headers": list(EXPECTED_HEADERS),
            "column_counts": sorted(
                {len(row.find_all("td", recursive=False)) for row in rows}
            ),
            "metadata_parser": "line_classification_v1",
            "document_parser": "strong_label_predecessor_v1",
        }
    )
    for record in records:
        record["provenance"]["schema_fingerprint"] = fingerprint
    scope = (
        f"archive_{expected_publication_year}"
        if expected_publication_year is not None
        else "current_2009_present"
    )
    return MarylandBusinessOpinionIndex(
        records=tuple(records),
        source_url=source_url,
        schema_fingerprint=fingerprint,
        publication_scope=scope,
        native_count=len(records),
    )


class MarylandBusinessOpinionsClient:
    """Paced, retrying client for official index pages and documents."""

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

    def _get(self, url: str) -> Any:
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise MarylandBusinessOpinionsError(
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
                raise MarylandBusinessOpinionsError(
                    "source_rate_limited",
                    "Maryland Judiciary rate-limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="http",
                    retryable=True,
                    details={"url": url, "http_status": status_code},
                )
            if status_code in {401, 403}:
                raise MarylandBusinessOpinionsError(
                    "source_access_challenge",
                    "Maryland Judiciary returned an access challenge",
                    status=ResultStatus.HUMAN_REQUIRED,
                    category="source_access",
                    details={"url": url, "http_status": status_code},
                )
            if status_code != 200:
                raise MarylandBusinessOpinionsError(
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
                raise MarylandBusinessOpinionsError(
                    "source_access_challenge",
                    "Maryland Judiciary returned a browser-verification page",
                    status=ResultStatus.HUMAN_REQUIRED,
                    category="source_access",
                    details={"url": url},
                )
            return response
        raise AssertionError("retry loop exhausted")

    def fetch_archive_directory(self) -> MarylandBusinessRoutes:
        response = self._get(ARCHIVE_INDEX_URL)
        return parse_archive_directory(
            str(response.text),
            source_url=str(getattr(response, "url", ARCHIVE_INDEX_URL)),
        )

    def fetch_current(self) -> MarylandBusinessOpinionIndex:
        response = self._get(CURRENT_URL)
        return parse_opinion_page(
            str(response.text),
            source_url=str(getattr(response, "url", CURRENT_URL)),
        )

    def fetch_archive_year(
        self,
        year: int,
        *,
        source_url: str | None = None,
    ) -> MarylandBusinessOpinionIndex:
        url = source_url or f"{ARCHIVE_INDEX_URL}{year}"
        response = self._get(url)
        return parse_opinion_page(
            str(response.text),
            source_url=str(getattr(response, "url", url)),
            expected_publication_year=year,
        )

    def fetch_document(self, source_url: str) -> MarylandBusinessDocument:
        safe_url = _official_attachment_url(source_url)
        response = self._get(safe_url)
        final_url = _official_attachment_url(str(getattr(response, "url", safe_url)))
        content = bytes(response.content)
        media_type = (
            str(
                getattr(response, "headers", {}).get(
                    "Content-Type",
                    _media_type_for_path(final_url),
                )
            )
            .split(";", 1)[0]
            .strip()
            .casefold()
        )
        if final_url.casefold().endswith(".pdf") and not content.startswith(b"%PDF-"):
            raise MarylandBusinessOpinionsSourceChangedError(
                "pdf_signature_missing",
                "Maryland publication download is not a PDF",
                details={
                    "url": final_url,
                    "content_type": media_type,
                    "size": len(content),
                },
            )
        prefix = content[:2_000].lstrip().lower()
        if prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html"):
            raise MarylandBusinessOpinionsSourceChangedError(
                "document_returned_html",
                "Maryland publication download returned HTML",
                details={
                    "url": final_url,
                    "content_type": media_type,
                    "size": len(content),
                },
            )
        if not content:
            raise MarylandBusinessOpinionsSourceChangedError(
                "document_empty",
                "Maryland publication download was empty",
                details={"url": final_url},
            )
        return MarylandBusinessDocument(
            source_url=final_url,
            content=content,
            media_type=media_type or _media_type_for_path(final_url),
            sha256=hashlib.sha256(content).hexdigest(),
        )

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()


def _source_manifest() -> dict[str, Any]:
    return {
        "source": SOURCE_METADATA.to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "operations": {
            "routes": "discover the six source-published annual archive routes",
            "search": (
                "query the current table, one selected year, or all seven "
                "complete source tables; filter locally and paginate by anchor"
            ),
            "download": (
                "download and hash an exact source-listed opinion, order, "
                "or synopsis attachment"
            ),
            "probe": (
                "verify route, current-table, archive-table, and linked-PDF surfaces"
            ),
        },
        "identity": {
            "publication": (
                "court, source case number when supplied, and normalized MDBT "
                "publication designation"
            ),
            "case": "court and exact source case number when supplied",
            "document": "exact source-listed attachment URL",
            "source_inconsistencies": (
                "retain source omissions, filename mismatches, duplicated path "
                "segments, and URLs shared by multiple publication rows"
            ),
        },
        "coverage": {
            "current_table": "2009-present",
            "annual_archives": "2003-2008",
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
                "operation_state": "public_report",
                "join_keys": ["case_number", "party_name", "court"],
            },
            {
                "source_id": "us-md-judgment-liens",
                "name": "Maryland Judgment and Liens Search",
                "url": JUDGMENT_LIENS_URL,
                "role": "circuit_court_judgment_and_lien_index",
                "operation_state": "public_search",
                "join_keys": ["case_number", "party_name", "court"],
            },
            {
                "source_id": "us-md-appellate-opinions",
                "name": "Maryland Appellate Court Opinions",
                "url": APPELLATE_OPINIONS_URL,
                "role": "reported_and_unreported_appellate_decisions",
                "operation_state": "integrated",
                "join_keys": ["case_number", "party_name", "court"],
            },
            {
                "source_id": "us-md-circuit-clerk-records",
                "name": "Maryland Circuit Court clerk record-copy routes",
                "url": COURT_RECORDS_URL,
                "role": "underlying_filing_and_record_copy_request",
                "operation_state": "court_specific_request_route",
                "join_keys": ["case_number", "court"],
            },
        ],
    }


def _selection(args: argparse.Namespace) -> dict[str, Any]:
    if args.year is not None and args.all_pages:
        raise MarylandBusinessOpinionsSelectionError(
            "page_selectors_conflict",
            "--year cannot be combined with --all-pages",
        )
    if args.year is not None and args.year < 2003:
        raise MarylandBusinessOpinionsSelectionError(
            "year_outside_source_coverage",
            "Published MDBT opinion coverage begins in 2003",
            details={"year": args.year},
        )
    filed_from = _iso_date_bound(args.filed_from, "--filed-from")
    filed_to = _iso_date_bound(args.filed_to, "--filed-to")
    if filed_from is not None and filed_to is not None and filed_from > filed_to:
        raise MarylandBusinessOpinionsSelectionError(
            "filing_date_range_reversed",
            "--filed-from must not be after --filed-to",
        )
    return {
        "year": args.year,
        "all_pages": bool(args.all_pages),
        "query": _clean_text(args.query) or None,
        "case_number": _clean_text(args.case_number) or None,
        "county": _clean_text(args.county) or None,
        "judge": _clean_text(args.judge) or None,
        "document_type": args.document_type,
        "filed_from": filed_from,
        "filed_to": filed_to,
    }


def _iso_date_bound(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as error:
        raise MarylandBusinessOpinionsSelectionError(
            "filing_date_invalid",
            f"{field_name} must be an ISO date in YYYY-MM-DD form",
            details={"value": value},
        ) from error


def _selection_fingerprint(selection: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(selection).encode("utf-8")).hexdigest()


def _encode_cursor(
    *,
    selection_fingerprint: str,
    anchor: str,
) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "operation": "search",
        "selection": selection_fingerprint,
        "anchor": anchor,
    }
    raw = canonical_json(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(
    value: str | None,
    *,
    selection_fingerprint: str,
) -> str | None:
    if value is None:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(value + padding).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MarylandBusinessOpinionsSelectionError(
            "cursor_invalid",
            "Cursor is not a valid Maryland publication cursor",
        ) from error
    if (
        not isinstance(payload, dict)
        or payload.get("v") != CURSOR_VERSION
        or payload.get("operation") != "search"
        or not isinstance(payload.get("anchor"), str)
    ):
        raise MarylandBusinessOpinionsSelectionError(
            "cursor_invalid",
            "Cursor payload is not a supported Maryland publication cursor",
        )
    if payload.get("selection") != selection_fingerprint:
        raise MarylandBusinessOpinionsSelectionError(
            "cursor_selection_mismatch",
            "Cursor belongs to a different publication search",
        )
    return str(payload["anchor"])


def _case_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _record_filing_interval(
    record: Mapping[str, Any],
) -> tuple[str, str] | None:
    filed_date = record.get("filed_date")
    if not isinstance(filed_date, str) or not filed_date:
        return None
    if record.get("date_precision") == "month":
        parsed = datetime.strptime(filed_date, "%Y-%m")
        last_day = calendar.monthrange(parsed.year, parsed.month)[1]
        return f"{filed_date}-01", f"{filed_date}-{last_day:02d}"
    return filed_date, filed_date


def _record_matches(
    record: Mapping[str, Any],
    *,
    selection: Mapping[str, Any],
) -> bool:
    year = selection.get("year")
    if year is not None and record.get("publication_year") != year:
        return False
    query_text = selection.get("query")
    if query_text is not None:
        haystack = canonical_json(record).casefold()
        if str(query_text).casefold() not in haystack:
            return False
    case_number = selection.get("case_number")
    if case_number is not None and _case_token(case_number) != _case_token(
        record.get("case_number")
    ):
        return False
    county = selection.get("county")
    if county is not None and _case_token(county) not in _case_token(
        record["court"]["county"]
    ):
        return False
    judge = selection.get("judge")
    if (
        judge is not None
        and str(judge).casefold() not in str(record.get("judge") or "").casefold()
    ):
        return False
    document_type = selection.get("document_type")
    if document_type is not None and document_type not in record["document_types"]:
        return False
    filed_from = selection.get("filed_from")
    filed_to = selection.get("filed_to")
    if filed_from is not None or filed_to is not None:
        filing_interval = _record_filing_interval(record)
        if filing_interval is None:
            return False
        interval_start, interval_end = filing_interval
        if filed_from is not None and interval_end < filed_from:
            return False
        if filed_to is not None and interval_start > filed_to:
            return False
    return True


def _page_records(
    records: Sequence[Mapping[str, Any]],
    *,
    selection: Mapping[str, Any],
    cursor_anchor: str | None,
    limit: int | None,
    selection_fingerprint: str,
) -> tuple[tuple[Mapping[str, Any], ...], str | None]:
    matches = [
        record for record in records if _record_matches(record, selection=selection)
    ]
    start = 0
    if cursor_anchor is not None:
        anchors = [
            index
            for index, record in enumerate(matches)
            if record["canonical_ref"] == cursor_anchor
        ]
        if not anchors:
            raise MarylandBusinessOpinionsSelectionError(
                "cursor_anchor_missing",
                "Cursor anchor is not present in the selected source records",
            )
        start = anchors[0] + 1
    if limit is None:
        return tuple(matches[start:]), None
    page = matches[start : start + limit]
    next_cursor = None
    if start + len(page) < len(matches) and page:
        next_cursor = _encode_cursor(
            selection_fingerprint=selection_fingerprint,
            anchor=str(page[-1]["canonical_ref"]),
        )
    return tuple(page), next_cursor


def _collect_indexes(
    client: MarylandBusinessOpinionsClient | Any,
    *,
    selection: Mapping[str, Any],
) -> tuple[tuple[Mapping[str, Any], ...], tuple[str, ...]]:
    year = selection.get("year")
    if year is not None and int(year) <= 2008:
        routes = client.fetch_archive_directory()
        source_url = routes.archive_urls.get(int(year))
        if source_url is None:
            return (), (routes.source_url,)
        page = client.fetch_archive_year(int(year), source_url=source_url)
        return page.records, (routes.source_url, page.source_url)
    current = client.fetch_current()
    records: list[Mapping[str, Any]] = list(current.records)
    source_urls = [current.source_url]
    if selection.get("all_pages"):
        routes = client.fetch_archive_directory()
        source_urls.append(routes.source_url)
        for archive_year in routes.archive_years:
            page = client.fetch_archive_year(
                archive_year,
                source_url=routes.archive_urls[archive_year],
            )
            records.extend(page.records)
            source_urls.append(page.source_url)
    return tuple(records), tuple(source_urls)


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
    error: MarylandBusinessOpinionsError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def _client_from_args(args: argparse.Namespace) -> MarylandBusinessOpinionsClient:
    return MarylandBusinessOpinionsClient(
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
    client: MarylandBusinessOpinionsClient | Any | None = None,
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
                routes = source_client.fetch_archive_directory()
                record = {
                    "source_id": SOURCE_ID,
                    "record_kind": "source_routes",
                    "current": {
                        "coverage": "2009-present",
                        "source_url": CURRENT_URL,
                        "operation_state": "public_complete_table",
                    },
                    "archive": {
                        "years": list(routes.archive_years),
                        "urls": {
                            str(year): routes.archive_urls[year]
                            for year in routes.archive_years
                        },
                        "source_url": routes.source_url,
                        "schema_fingerprint": routes.schema_fingerprint,
                        "operation_state": "public_annual_complete_tables",
                    },
                }
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    raw_artifact_refs=[routes.source_url],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "search":
                selection = _selection(args)
                query = _query(args, selection=selection)
                fingerprint = _selection_fingerprint(selection)
                anchor = _decode_cursor(
                    args.cursor,
                    selection_fingerprint=fingerprint,
                )
                all_records, source_urls = _collect_indexes(
                    source_client,
                    selection=selection,
                )
                records, next_cursor = _page_records(
                    all_records,
                    selection=selection,
                    cursor_anchor=anchor,
                    limit=args.limit,
                    selection_fingerprint=fingerprint,
                )
                result = PublicRecordsResult.success(
                    query,
                    records,
                    next_cursor=next_cursor,
                    raw_artifact_refs=source_urls,
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "download":
                safe_url = _official_attachment_url(args.url)
                selection = {
                    "url": safe_url,
                    "destination": str(args.destination),
                }
                query = _query(args, selection=selection)
                document = source_client.fetch_document(safe_url)
                args.destination.parent.mkdir(parents=True, exist_ok=True)
                args.destination.write_bytes(document.content)
                record = {
                    "canonical_ref": f"MDBTPUBLICATION:{document.sha256}",
                    "source_id": SOURCE_ID,
                    "record_kind": "document_artifact",
                    "source_url": document.source_url,
                    "local_path": str(args.destination),
                    "media_type": document.media_type,
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
            elif args.command == "probe":
                query = _query(args, selection={})
                routes = source_client.fetch_archive_directory()
                current = source_client.fetch_current()
                oldest_year = min(routes.archive_years)
                archive = source_client.fetch_archive_year(
                    oldest_year,
                    source_url=routes.archive_urls[oldest_year],
                )
                sample_record = next(
                    (
                        record
                        for record in current.records
                        if any(
                            document["file_format"] == "pdf"
                            for document in record["documents"]
                        )
                    ),
                    None,
                )
                if sample_record is None:
                    raise MarylandBusinessOpinionsSourceChangedError(
                        "probe_pdf_missing",
                        "Current opinion table contains no linked PDF",
                    )
                sample_url = next(
                    document["source_url"]
                    for document in sample_record["documents"]
                    if document["file_format"] == "pdf"
                )
                document = source_client.fetch_document(str(sample_url))
                source_omission_count = sum(
                    bool(record["source_omissions"]) for record in current.records
                )
                source_anomaly_count = sum(
                    bool(record["source_link_anomalies"]) for record in current.records
                )
                record = {
                    "source_id": SOURCE_ID,
                    "record_kind": "source_probe",
                    "archive_years": list(routes.archive_years),
                    "current_publication_count": current.native_count,
                    "current_schema_fingerprint": current.schema_fingerprint,
                    "archive_sample_year": oldest_year,
                    "archive_sample_count": archive.native_count,
                    "archive_schema_fingerprint": archive.schema_fingerprint,
                    "current_rows_with_source_omissions": source_omission_count,
                    "current_rows_with_source_link_anomalies": (source_anomaly_count),
                    "pdf_url": document.source_url,
                    "pdf_sha256": document.sha256,
                    "pdf_size_bytes": len(document.content),
                    "pdf_media_type": document.media_type,
                }
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    raw_artifact_refs=[
                        routes.source_url,
                        current.source_url,
                        archive.source_url,
                        document.source_url,
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            else:
                raise AssertionError(f"unknown command: {args.command}")
    except MarylandBusinessOpinionsError as error:
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
            "Query official Maryland Business and Technology trial-court opinions"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest = subparsers.add_parser(
        "manifest",
        help="Show source coverage, identity, and complementary routes",
    )
    _add_runtime_and_output(manifest)

    routes = subparsers.add_parser(
        "routes",
        help="Discover source-published current and annual archive routes",
    )
    _add_runtime_and_output(routes)

    search = subparsers.add_parser(
        "search",
        help="Search current, annual, or all published-opinion tables",
    )
    search.add_argument("--year", type=int)
    search.add_argument(
        "--all-pages",
        action="store_true",
        help="Traverse the current table and every discovered archive table",
    )
    search.add_argument("--query", help="Filter all publication metadata by text")
    search.add_argument("--case-number")
    search.add_argument("--county")
    search.add_argument("--judge")
    search.add_argument("--document-type", choices=_DOCUMENT_TYPES)
    search.add_argument(
        "--filed-from",
        help="Include publications whose source filing interval reaches this date",
    )
    search.add_argument(
        "--filed-to",
        help="Include publications whose source filing interval begins by this date",
    )
    search.add_argument("--limit", type=_positive_int)
    search.add_argument("--cursor")
    _add_runtime_and_output(search)

    download = subparsers.add_parser(
        "download",
        help="Download and hash one exact source-listed attachment",
    )
    download.add_argument("url")
    download.add_argument("destination", type=Path)
    _add_runtime_and_output(download)

    probe = subparsers.add_parser(
        "probe",
        help="Verify routes, both table generations, and one linked PDF",
    )
    _add_runtime_and_output(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Maryland Business and Technology opinions "
            f"{args.command} ({result.status.value})"
        ),
        result_count=len(result.records),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2))
        return
    print(
        f"Maryland Business and Technology opinions {args.command}: "
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
