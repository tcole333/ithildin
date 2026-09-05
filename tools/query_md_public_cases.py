#!/usr/bin/env python3
"""Discover and search Maryland Judiciary daily public-case reports.

The Maryland Judiciary publishes a rolling directory of daily "Cases Filed"
PDFs for public cases created by MDEC courts.  This adapter discovers the
directory from the official landing page, lists and downloads only
source-published artifacts, and parses their layout-preserving text.

Examples:
    uv run python tools/query_md_public_cases.py reports \
        --output /tmp/md-public-case-reports.json
    uv run python tools/query_md_public_cases.py search \
        --name "Example LLC" --all-current \
        --output /tmp/md-recent-cases.json
    uv run python tools/query_md_public_cases.py download 2026-07-30 \
        /tmp/file2026-07-30.pdf --output /tmp/md-download.json
    uv run python tools/query_md_public_cases.py parse \
        /tmp/file2026-07-30.pdf --case-number D-121-CV-26-008260 \
        --output /tmp/md-case.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html as html_lib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

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


SOURCE_ID = "us-md-mdec-public-cases"
STATE_CODE = "MD"
STATE_GEOID = "24"

LANDING_URL = "https://www.mdcourts.gov/mdec/publiccases"
VERIFIED_DIRECTORY_URL = "https://www.mdcourts.gov/data/case/?O=D"
CASE_SEARCH_URL = "https://casesearch.mdcourts.gov/casesearch/"
CASE_SEARCH_FAQ_URL = "https://www.mdcourts.gov/casesearch2/faq"
COURT_RECORDS_URL = "https://www.mdcourts.gov/courts/courtrecords"
JUDICIAL_RECORDS_URL = "https://www.mdcourts.gov/judicialrecords/recordsrequests"
JUDGMENT_LIENS_URL = (
    "https://jportal.mdcourts.gov/judgment/judgementSearch.jsf"
)
ESTATE_SEARCH_URL = "https://registers.maryland.gov/main/search.html"
APPELLATE_OPINIONS_URL = "https://www.mdcourts.gov/opinions/opinions"
LAND_RECORDS_GUIDE_URL = "https://www.mdcourts.gov/legalhelp/landrecords"
MDLANDREC_URL = "https://landrec.msa.maryland.gov/Pages/Login.aspx"
PLATS_URL = "https://plats.msa.maryland.gov/pages/index.aspx"
SDAT_DATASET_URL = (
    "https://opendata.maryland.gov/Business-and-Economy/"
    "Maryland-Real-Property-Assessments_Hidden-Property/ed4q-f8tm"
)

OUTPUT_SCHEMA_VERSION = "maryland-mdec-public-cases/1.0"
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_MAX_PAGE_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_DOCUMENT_BYTES = 64 * 1024 * 1024
DEFAULT_LIMIT = 100
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

REPORT_FILENAME_RE = re.compile(
    r"^file(?P<report_date>\d{4}-\d{2}-\d{2})\.pdf$",
    re.IGNORECASE,
)
REPORTING_PERIOD_RE = re.compile(
    r"Reporting\s+Period:\s*(?P<start>\d{1,2}/\d{1,2}/\d{4})"
    r"\s+to\s+(?P<end>\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE,
)
RUN_DATE_RE = re.compile(
    r"Run\s+Date:\s*(?P<run_date>\d{1,2}/\d{1,2}/\d{4})"
    r"\s+(?P<run_time>\d{1,2}:\d{2}\s+[AP]M)",
    re.IGNORECASE,
)
FILE_DATE_AT_END_RE = re.compile(
    r"(?P<file_date>\d{1,2}/\d{1,2}/\d{4})\s*$"
)
RECORD_ROW_RE = re.compile(
    r"^\s*(?P<case_number>\S+)\s{2,}"
    r"(?P<caption>.*?)\s{2,}"
    r"(?P<case_type>.*?)\s{2,}"
    r"(?P<file_date>\d{1,2}/\d{1,2}/\d{4})\s*$"
)
ADDRESS_LABEL_RE = re.compile(
    r"(?P<role>Plaintiff|Defendant)\s+Address:",
    re.IGNORECASE,
)
CHARGE_LINE_RE = re.compile(r"^\s*(?P<number>\d+)\s*-\s*(?P<text>.*)$")
CURSOR_RE = re.compile(
    r"^md-mdec:v1:(?P<key>[0-9a-f]{16}):offset:(?P<offset>\d+)$"
)


SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Maryland MDEC Public Cases Created by Courts",
    source_role="official_recent_statewide_case_filing_reports",
    base_url=LANDING_URL,
    dataset_id="maryland-mdec-cases-filed-reports",
    metadata={
        "authority": "Maryland Judiciary",
        "operator": "Maryland Administrative Office of the Courts",
        "coverage": "Public cases created by MDEC courts in the rolling five-day directory",
        "directory_url": VERIFIED_DIRECTORY_URL,
        "artifact_format": "PDF",
        "report_name": "CBS721 - Cases Filed Report",
        "stable_join_keys": [
            "case_number",
            "party_name",
            "published_address",
            "court_name",
        ],
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Maryland",
    state_code=STATE_CODE,
)

SOURCE_WARNINGS = (
    "The official directory is a rolling recent-case feed, not a historical "
    "case index or docket-detail system.",
    "The Judiciary states that cases secured at initiation and later made "
    "public do not appear in these reports.",
    "Report filename date, report run time, reporting period, and case filing "
    "date are distinct source fields and are preserved separately.",
    "Additional case detail remains in Maryland Case Search or the relevant "
    "court clerk's official file.",
)


class MarylandPublicCasesError(RuntimeError):
    """Source error with explicit public-record result semantics."""

    status = ResultStatus.UNAVAILABLE
    category = "source"
    retryable = False
    code = "maryland_public_cases_error"

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        details = dict(self.details)
        if self.url:
            details["url"] = self.url
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=details,
        )


class MarylandSelectionError(MarylandPublicCasesError):
    """Caller selection cannot be represented by the source."""

    category = "query"
    code = "invalid_selection"


class MarylandTransportError(MarylandPublicCasesError):
    """The official source could not be reached."""

    category = "transport"
    retryable = True
    code = "transport_error"


class MarylandRestrictedError(MarylandPublicCasesError):
    """The official report source denied this request."""

    status = ResultStatus.RESTRICTED
    category = "access"
    code = "access_restricted"


class MarylandSourceChangedError(MarylandPublicCasesError):
    """The official representation no longer matches the verified contract."""

    status = ResultStatus.SOURCE_CHANGED
    category = "schema"
    code = "source_changed"


class MarylandPDFExtractionError(MarylandPublicCasesError):
    """The PDF exists but local layout-preserving extraction is unavailable."""

    status = ResultStatus.HUMAN_REQUIRED
    category = "document_extraction"
    code = "pdf_text_extraction_unavailable"


@dataclass(frozen=True)
class ReportRoute:
    """One source-published daily report."""

    report_date: str
    filename: str
    source_url: str
    last_modified_local: str | None
    size_raw: str | None
    size_bytes_approximate: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_kind": "daily_case_report_route",
            "source_id": SOURCE_ID,
            "report_date": self.report_date,
            "filename": self.filename,
            "source_url": self.source_url,
            "last_modified_local": self.last_modified_local,
            "last_modified_timezone": (
                "America/New_York" if self.last_modified_local else None
            ),
            "size_raw": self.size_raw,
            "size_bytes_approximate": self.size_bytes_approximate,
            "access_state": "public_download",
        }


@dataclass(frozen=True)
class DownloadedReport:
    """Verified bytes and provenance for one downloaded report."""

    route: ReportRoute
    content: bytes
    media_type: str | None
    sha256: str


@dataclass
class _CaseDraft:
    """Mutable parser state for a case that may span report pages."""

    court_name: str
    page_numbers: list[int]
    case_number_parts: list[str]
    caption_parts: list[str]
    case_type_parts: list[str]
    file_date_raw: str
    raw_detail_lines: list[str] = field(default_factory=list)
    party_streams: dict[str, list[str | None]] = field(default_factory=dict)
    charges: list[dict[str, Any]] = field(default_factory=list)
    mode: str = "header"
    role_layout: list[tuple[str, int, int | None]] = field(default_factory=list)
    word_role_layout: list[tuple[str, float, float | None]] = field(
        default_factory=list
    )
    party_positions: dict[str, tuple[int, float]] = field(default_factory=dict)


@dataclass(frozen=True)
class _PDFWord:
    """One word and its page coordinates from ``pdftotext -tsv``."""

    page_number: int
    left: float
    top: float
    width: float
    height: float
    text: str


@dataclass(frozen=True)
class _VisualLine:
    """Words sharing one rendered baseline."""

    page_number: int
    top: float
    words: tuple[_PDFWord, ...]

    @property
    def text(self) -> str:
        return _clean(" ".join(word.text for word in self.words))


def _clean(value: str | None) -> str:
    return " ".join(str(value or "").split())


def _iso_date(value: str | None) -> str | None:
    if not value:
        return None
    for form in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), form).date().isoformat()
        except ValueError:
            continue
    return None


def _size_bytes_approximate(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"\s*([\d.]+)\s*([KMG]?)\s*", value, re.IGNORECASE)
    if match is None:
        return None
    multiplier = {
        "": 1,
        "K": 1024,
        "M": 1024 * 1024,
        "G": 1024 * 1024 * 1024,
    }[match.group(2).upper()]
    return round(float(match.group(1)) * multiplier)


def _validate_official_directory_url(url: str) -> str:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"www.mdcourts.gov", "mdcourts.gov"}
        or parsed.path.rstrip("/") != "/data/case"
    ):
        raise MarylandSourceChangedError(
            "Landing page pointed outside the verified Maryland case-report directory",
            url=url,
        )
    return url


def _validate_report_url(url: str) -> str:
    parsed = urlparse(url)
    filename = Path(parsed.path).name
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"www.mdcourts.gov", "mdcourts.gov"}
        or not parsed.path.startswith("/data/case/")
        or REPORT_FILENAME_RE.fullmatch(filename) is None
    ):
        raise MarylandSourceChangedError(
            "Report link does not match the verified official PDF route",
            url=url,
        )
    return url


def discover_directory_url(
    landing_html: str,
    *,
    landing_url: str = LANDING_URL,
) -> str:
    """Extract the report-directory route used by the landing page iframe."""

    soup = BeautifulSoup(landing_html, "html.parser")
    candidates: list[str] = []
    iframe = soup.find("iframe", id="case_reports")
    if iframe is not None and iframe.get("src"):
        candidates.append(str(iframe["src"]))
    for script in soup.find_all("script"):
        content = script.string or script.get_text(" ", strip=False)
        match = re.search(
            r"""getElementById\(\s*["']case_reports["']\s*\)"""
            r"""\.src\s*=\s*["'](?P<url>[^"']+)["']""",
            content,
            re.IGNORECASE,
        )
        if match:
            candidates.append(match.group("url"))
    for candidate in candidates:
        decoded = html_lib.unescape(candidate).strip()
        if decoded:
            return _validate_official_directory_url(
                urljoin(landing_url, decoded)
            )
    raise MarylandSourceChangedError(
        "Could not discover the case-report directory from the official landing page",
        url=landing_url,
    )


def parse_report_directory(
    directory_html: str,
    *,
    directory_url: str = VERIFIED_DIRECTORY_URL,
) -> list[ReportRoute]:
    """Parse the official Apache-style rolling directory."""

    soup = BeautifulSoup(directory_html, "html.parser")
    reports: dict[str, ReportRoute] = {}
    for anchor in soup.find_all("a", href=True):
        filename = Path(urlparse(str(anchor["href"])).path).name
        match = REPORT_FILENAME_RE.fullmatch(filename)
        if match is None:
            continue
        report_date = match.group("report_date")
        try:
            date.fromisoformat(report_date)
        except ValueError as exc:
            raise MarylandSourceChangedError(
                "Report directory contains an invalid filename date",
                url=urljoin(directory_url, str(anchor["href"])),
                details={"filename": filename},
            ) from exc
        row = anchor.find_parent("tr")
        cells = row.find_all(["td", "th"]) if row else []
        last_modified = _clean(cells[1].get_text(" ", strip=True)) if len(cells) > 1 else ""
        size_raw = _clean(cells[2].get_text(" ", strip=True)) if len(cells) > 2 else ""
        source_url = _validate_report_url(
            urljoin(directory_url, str(anchor["href"]))
        )
        route = ReportRoute(
            report_date=report_date,
            filename=filename,
            source_url=source_url,
            last_modified_local=last_modified or None,
            size_raw=size_raw or None,
            size_bytes_approximate=_size_bytes_approximate(size_raw),
        )
        existing = reports.get(report_date)
        if existing is not None and existing.source_url != route.source_url:
            raise MarylandSourceChangedError(
                "Report directory contains duplicate dates with different URLs",
                url=directory_url,
                details={"report_date": report_date},
            )
        reports[report_date] = route
    if not reports:
        raise MarylandSourceChangedError(
            "Official case-report directory contained no dated PDF links",
            url=directory_url,
        )
    return sorted(reports.values(), key=lambda item: item.report_date, reverse=True)


class MarylandPublicCasesClient:
    """Bounded client for the landing page, directory, and report PDFs."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        self._owns_session = session is None
        self.session = session or system_trust_session()
        if hasattr(self.session, "headers"):
            self.session.headers.setdefault("User-Agent", DEFAULT_USER_AGENT)
        self.timeout = timeout
        self.rate_limiter = MinimumIntervalRateLimiter(minimum_interval)
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper

    def close(self) -> None:
        if self._owns_session and hasattr(self.session, "close"):
            self.session.close()

    def _get(
        self,
        url: str,
        *,
        max_bytes: int,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.get(
                    url,
                    headers=dict(headers or {}),
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self.retry_policy.max_attempts:
                    break
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            status_code = int(response.status_code)
            if status_code in self.retry_policy.retry_statuses:
                if attempt == self.retry_policy.max_attempts:
                    last_error = MarylandTransportError(
                        f"HTTP {status_code} from Maryland report source",
                        url=url,
                        details={"status_code": status_code},
                    )
                    break
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status_code in {401, 403}:
                raise MarylandRestrictedError(
                    f"HTTP {status_code} from Maryland report source",
                    url=url,
                    details={"status_code": status_code},
                )
            if status_code >= 400:
                raise MarylandTransportError(
                    f"HTTP {status_code} from Maryland report source",
                    url=url,
                    details={"status_code": status_code},
                )
            length = response.headers.get("Content-Length")
            if length:
                try:
                    if int(length) > max_bytes:
                        raise MarylandSourceChangedError(
                            "Official response exceeded the configured artifact bound",
                            url=url,
                            details={
                                "content_length": int(length),
                                "max_bytes": max_bytes,
                            },
                        )
                except ValueError:
                    pass
            content = response.content
            if len(content) > max_bytes:
                raise MarylandSourceChangedError(
                    "Official response exceeded the configured artifact bound",
                    url=url,
                    details={"size_bytes": len(content), "max_bytes": max_bytes},
                )
            return response
        if isinstance(last_error, MarylandPublicCasesError):
            raise last_error
        raise MarylandTransportError(
            "Could not reach the Maryland report source",
            url=url,
            details={"reason": str(last_error or "request failed")},
        ) from last_error

    def report_routes(self) -> tuple[str, list[ReportRoute]]:
        landing = self._get(LANDING_URL, max_bytes=DEFAULT_MAX_PAGE_BYTES)
        directory_url = discover_directory_url(
            landing.content.decode("utf-8", errors="replace")
        )
        directory = self._get(directory_url, max_bytes=DEFAULT_MAX_PAGE_BYTES)
        reports = parse_report_directory(
            directory.content.decode("utf-8", errors="replace"),
            directory_url=directory_url,
        )
        return directory_url, reports

    def download(self, route: ReportRoute) -> DownloadedReport:
        response = self._get(
            _validate_report_url(route.source_url),
            max_bytes=DEFAULT_MAX_DOCUMENT_BYTES,
        )
        content = bytes(response.content)
        if not content.lstrip().startswith(b"%PDF"):
            raise MarylandSourceChangedError(
                "Source-published report did not contain PDF bytes",
                url=route.source_url,
                details={
                    "content_type": response.headers.get("Content-Type"),
                    "size_bytes": len(content),
                },
            )
        return DownloadedReport(
            route=route,
            content=content,
            media_type=response.headers.get("Content-Type"),
            sha256=hashlib.sha256(content).hexdigest(),
        )


def extract_pdf_text(
    pdf_path: Path,
    *,
    executable: str | None = None,
) -> str:
    """Extract report text with the layout columns retained."""

    resolved = pdf_path.expanduser().resolve()
    if not resolved.is_file():
        raise MarylandSelectionError(
            "PDF artifact does not exist",
            details={"path": str(resolved)},
        )
    with resolved.open("rb") as stream:
        if stream.read(8).lstrip().startswith(b"%PDF") is False:
            raise MarylandSelectionError(
                "Artifact is not a PDF",
                details={"path": str(resolved)},
            )
    command = executable or shutil.which("pdftotext")
    if not command:
        raise MarylandPDFExtractionError(
            "pdftotext is needed to preserve the report's column layout",
            details={"path": str(resolved)},
        )
    completed = subprocess.run(
        [command, "-layout", str(resolved), "-"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise MarylandPDFExtractionError(
            "pdftotext could not extract the official report",
            details={
                "path": str(resolved),
                "exit_code": completed.returncode,
                "stderr": completed.stderr.decode(
                    "utf-8", errors="replace"
                )[:500],
            },
        )
    text = completed.stdout.decode("utf-8", errors="replace")
    if "AOC - Cases Filed Report" not in text or "Case Number" not in text:
        raise MarylandSourceChangedError(
            "Extracted PDF text did not match the Cases Filed report",
            details={"path": str(resolved)},
        )
    return text


def extract_pdf_tsv(
    pdf_path: Path,
    *,
    executable: str | None = None,
) -> str:
    """Extract word coordinates used to separate overlapping report columns."""

    resolved = pdf_path.expanduser().resolve()
    if not resolved.is_file():
        raise MarylandSelectionError(
            "PDF artifact does not exist",
            details={"path": str(resolved)},
        )
    with resolved.open("rb") as stream:
        if stream.read(8).lstrip().startswith(b"%PDF") is False:
            raise MarylandSelectionError(
                "Artifact is not a PDF",
                details={"path": str(resolved)},
            )
    command = executable or shutil.which("pdftotext")
    if not command:
        raise MarylandPDFExtractionError(
            "pdftotext is needed to preserve the report's word coordinates",
            details={"path": str(resolved)},
        )
    completed = subprocess.run(
        [command, "-tsv", str(resolved), "-"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise MarylandPDFExtractionError(
            "pdftotext could not extract word coordinates from the report",
            details={
                "path": str(resolved),
                "exit_code": completed.returncode,
                "stderr": completed.stderr.decode(
                    "utf-8", errors="replace"
                )[:500],
            },
        )
    text = completed.stdout.decode("utf-8", errors="replace")
    if not text.startswith("level\tpage_num\t"):
        raise MarylandSourceChangedError(
            "Coordinate extraction did not return the expected TSV header",
            details={"path": str(resolved)},
        )
    return text


def _visual_lines(tsv_text: str) -> list[_VisualLine]:
    """Parse and group the deliberate ``pdftotext -tsv`` schema."""

    csv.field_size_limit(1_000_000)
    reader = csv.reader(io.StringIO(tsv_text), delimiter="\t")
    try:
        header = next(reader)
    except StopIteration as exc:
        raise MarylandSourceChangedError(
            "Coordinate extraction returned an empty artifact"
        ) from exc
    expected = [
        "level",
        "page_num",
        "par_num",
        "block_num",
        "line_num",
        "word_num",
        "left",
        "top",
        "width",
        "height",
        "conf",
        "text",
    ]
    if header != expected:
        raise MarylandSourceChangedError(
            "Coordinate extraction TSV schema changed",
            details={"expected_header": expected, "actual_header": header},
        )
    grouped: dict[tuple[int, float], list[_PDFWord]] = {}
    for row in reader:
        if len(row) != len(expected) or row[0] != "5":
            continue
        try:
            word = _PDFWord(
                page_number=int(row[1]),
                left=float(row[6]),
                top=float(row[7]),
                width=float(row[8]),
                height=float(row[9]),
                text=row[11],
            )
        except ValueError as exc:
            raise MarylandSourceChangedError(
                "Coordinate extraction contains an invalid word row",
                details={"row": row[:11]},
            ) from exc
        grouped.setdefault(
            (word.page_number, round(word.top, 2)),
            [],
        ).append(word)
    lines = [
        _VisualLine(
            page_number=page_number,
            top=top,
            words=tuple(sorted(words, key=lambda item: item.left)),
        )
        for (page_number, top), words in grouped.items()
    ]
    lines.sort(key=lambda item: (item.page_number, item.top))
    return lines


def _words_text(
    words: Sequence[_PDFWord],
    *,
    start: float | None = None,
    end: float | None = None,
) -> str:
    selected = [
        word.text
        for word in words
        if (start is None or word.left >= start)
        and (end is None or word.left < end)
    ]
    return _clean(" ".join(selected))


def _coordinate_header(
    lines: Sequence[_VisualLine],
) -> tuple[int, float, float, float] | None:
    for index, line in enumerate(lines):
        values = [word.text.casefold() for word in line.words]
        if not {"case", "number", "style", "type", "file", "date"} <= set(
            values
        ):
            continue
        style_word = next(
            word for word in line.words if word.text.casefold() == "style"
        )
        case_words = [
            word
            for word in line.words
            if word.text.casefold() == "case" and word.left > style_word.left
        ]
        file_words = [
            word for word in line.words if word.text.casefold() == "file"
        ]
        if not case_words or not file_words:
            continue
        return (
            index,
            style_word.left,
            case_words[0].left,
            file_words[-1].left,
        )
    return None


def _coordinate_court_name(
    lines: Sequence[_VisualLine],
    header_index: int,
) -> str:
    values = [line.text for line in lines[:header_index]]
    return _court_name(values, len(values))


def _coordinate_new_case(
    line: _VisualLine,
    *,
    court_name: str,
    style_x: float,
    type_x: float,
    file_x: float,
) -> _CaseDraft | None:
    date_words = [
        word
        for word in line.words
        if word.left >= file_x - 5
        and re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", word.text)
    ]
    case_words = [
        word
        for word in line.words
        if word.left < style_x - 5
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.'/-]*", word.text)
    ]
    if not date_words or not case_words:
        return None
    case_number = "".join(word.text for word in case_words)
    caption = _words_text(
        line.words,
        start=style_x - 5,
        end=type_x - 3,
    )
    case_type = _words_text(
        line.words,
        start=type_x - 3,
        end=file_x - 3,
    )
    return _CaseDraft(
        court_name=court_name,
        page_numbers=[line.page_number],
        case_number_parts=[case_number],
        caption_parts=[caption] if caption else [],
        case_type_parts=[case_type] if case_type else [],
        file_date_raw=date_words[-1].text,
    )


def _coordinate_role_layout(
    line: _VisualLine,
) -> list[tuple[str, float, float | None]]:
    matches = [
        word
        for word in line.words
        if word.text.casefold() in {"plaintiff", "defendant"}
    ]
    layout: list[tuple[str, float, float | None]] = []
    for index, word in enumerate(matches):
        following = [
            candidate
            for candidate in line.words
            if candidate.left > word.left
            and candidate.text.casefold().startswith("address:")
        ]
        if not following:
            continue
        end = matches[index + 1].left if index + 1 < len(matches) else None
        layout.append((word.text.casefold(), word.left, end))
    return layout


def _append_coordinate_party_line(
    draft: _CaseDraft,
    line: _VisualLine,
) -> None:
    for role, start, end in draft.word_role_layout:
        value = _words_text(line.words, start=start - 3, end=end)
        if not value:
            continue
        stream = draft.party_streams.setdefault(role, [])
        previous = draft.party_positions.get(role)
        if (
            previous is not None
            and previous[0] == line.page_number
            and line.top - previous[1] > 15
            and stream
            and stream[-1] is not None
        ):
            stream.append(None)
        stream.append(value)
        draft.party_positions[role] = (line.page_number, line.top)


def parse_cases_filed_tsv(
    tsv_text: str,
    *,
    report_publication_date: str | None = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Parse a report using source word coordinates as column boundaries."""

    lines = _visual_lines(tsv_text)
    if not lines:
        raise MarylandSourceChangedError(
            "Coordinate extraction contained no words",
            url=source_url,
        )
    metadata_text = "\n".join(line.text for line in lines)
    if "AOC - Cases Filed Report" not in metadata_text:
        raise MarylandSourceChangedError(
            "Coordinate extraction does not identify an AOC Cases Filed Report",
            url=source_url,
        )
    metadata = _report_metadata(
        metadata_text,
        report_publication_date=report_publication_date,
        source_url=source_url,
    )
    pages: dict[int, list[_VisualLine]] = {}
    for line in lines:
        pages.setdefault(line.page_number, []).append(line)

    records: list[dict[str, Any]] = []
    current: _CaseDraft | None = None
    for page_number in sorted(pages):
        page_lines = pages[page_number]
        header = _coordinate_header(page_lines)
        if header is None:
            continue
        header_index, style_x, type_x, file_x = header
        court_name = _coordinate_court_name(page_lines, header_index)
        for line in page_lines[header_index + 1 :]:
            if line.top >= 750:
                continue
            value = line.text
            if (
                value.startswith("Page:")
                and "Report Name: CBS721 - Cases Filed Report" in value
            ):
                continue
            new_case = _coordinate_new_case(
                line,
                court_name=court_name,
                style_x=style_x,
                type_x=type_x,
                file_x=file_x,
            )
            if new_case is not None:
                if current is not None:
                    records.append(
                        _finalize_case(
                            current,
                            report_metadata=metadata,
                            source_url=source_url,
                        )
                    )
                current = new_case
                continue
            if current is None:
                continue
            if value and page_number not in current.page_numbers:
                current.page_numbers.append(page_number)
            if value:
                current.raw_detail_lines.append(value)
            role_layout = _coordinate_role_layout(line)
            if role_layout:
                current.mode = "parties"
                current.word_role_layout = role_layout
                for role, _start, _end in role_layout:
                    current.party_streams.setdefault(role, [])
                continue
            if value.casefold() == "charges:":
                current.mode = "charges"
                current.word_role_layout = []
                continue
            if current.mode == "parties":
                _append_coordinate_party_line(current, line)
                continue
            if current.mode == "charges":
                _append_charge_line(current, value)
                continue
            case_fragment = _words_text(line.words, end=style_x - 5)
            caption_fragment = _words_text(
                line.words,
                start=style_x - 5,
                end=type_x - 3,
            )
            case_type_fragment = _words_text(
                line.words,
                start=type_x - 3,
                end=file_x - 3,
            )
            if (
                case_fragment
                and current.case_number_parts[-1].endswith("-")
                and re.fullmatch(r"[A-Za-z0-9-]+", case_fragment)
            ):
                current.case_number_parts.append(case_fragment)
            if caption_fragment:
                current.caption_parts.append(caption_fragment)
            if case_type_fragment:
                current.case_type_parts.append(case_type_fragment)
    if current is not None:
        records.append(
            _finalize_case(
                current,
                report_metadata=metadata,
                source_url=source_url,
            )
        )
    if not records:
        raise MarylandSourceChangedError(
            "Cases Filed coordinates contained no parseable case rows",
            url=source_url,
        )
    metadata["page_count"] = len(pages)
    metadata["case_count"] = len(records)
    metadata["courts"] = sorted(
        {str(record["court_name"]) for record in records}
    )
    metadata["extraction_method"] = "pdftotext-tsv-coordinate"
    return {"report": metadata, "records": records}


def _header_positions(lines: Sequence[str]) -> tuple[int, int, int, int] | None:
    for index, line in enumerate(lines):
        case_pos = line.find("Case Number")
        style_pos = line.find("Style", max(case_pos + 1, 0))
        type_pos = line.find("Case Type", max(style_pos + 1, 0))
        date_pos = line.find("File Date", max(type_pos + 1, 0))
        if min(case_pos, style_pos, type_pos, date_pos) >= 0:
            for candidate in lines[index + 1 :]:
                row = RECORD_ROW_RE.match(candidate)
                if row:
                    style_pos = row.start("caption")
                    type_pos = row.start("case_type")
                    date_pos = row.start("file_date")
                    break
            return index, style_pos, type_pos, date_pos
    return None


def _court_name(lines: Sequence[str], header_index: int) -> str:
    for line in reversed(lines[:header_index]):
        value = _clean(line)
        if not value:
            continue
        lowered = value.casefold()
        if (
            lowered == "aoc - cases filed report"
            or lowered.startswith("disclaimer:")
            or lowered.startswith("reporting period:")
        ):
            continue
        return value
    return "Maryland MDEC court"


def _new_case(
    line: str,
    *,
    court_name: str,
    page_number: int,
    style_pos: int,
    type_pos: int,
    date_pos: int,
) -> _CaseDraft | None:
    row_match = RECORD_ROW_RE.match(line)
    if row_match:
        return _CaseDraft(
            court_name=court_name,
            page_numbers=[page_number],
            case_number_parts=[_clean(row_match.group("case_number"))],
            caption_parts=(
                [_clean(row_match.group("caption"))]
                if _clean(row_match.group("caption"))
                else []
            ),
            case_type_parts=(
                [_clean(row_match.group("case_type"))]
                if _clean(row_match.group("case_type"))
                else []
            ),
            file_date_raw=row_match.group("file_date"),
        )
    date_match = FILE_DATE_AT_END_RE.search(line)
    if date_match is None:
        return None
    case_number = _clean(line[:style_pos])
    if not case_number or re.search(r"\s", case_number):
        return None
    caption = _clean(line[style_pos:type_pos])
    case_type = _clean(line[type_pos : max(date_pos, date_match.start())])
    if date_match.start() > date_pos:
        case_type = _clean(line[type_pos : date_match.start()])
    return _CaseDraft(
        court_name=court_name,
        page_numbers=[page_number],
        case_number_parts=[case_number],
        caption_parts=[caption] if caption else [],
        case_type_parts=[case_type] if case_type else [],
        file_date_raw=date_match.group("file_date"),
    )


def _role_layout(line: str) -> list[tuple[str, int, int | None]]:
    matches = list(ADDRESS_LABEL_RE.finditer(line))
    layout: list[tuple[str, int, int | None]] = []
    for index, match in enumerate(matches):
        role = match.group("role").casefold()
        end = matches[index + 1].start() if index + 1 < len(matches) else None
        layout.append((role, match.start(), end))
    return layout


def _append_party_line(draft: _CaseDraft, line: str) -> None:
    values: list[str] = []
    for role, start, end in draft.role_layout:
        value = _clean(line[start:end])
        values.append(value)
        stream = draft.party_streams.setdefault(role, [])
        stream.append(value or None)
    if not any(values):
        for role, _start, _end in draft.role_layout:
            stream = draft.party_streams.setdefault(role, [])
            if stream and stream[-1] is not None:
                stream.append(None)


def _append_charge_line(draft: _CaseDraft, line: str) -> None:
    value = _clean(line)
    if not value:
        return
    match = CHARGE_LINE_RE.match(line)
    if match:
        draft.charges.append(
            {
                "charge_number": int(match.group("number")),
                "description": _clean(match.group("text")),
            }
        )
        return
    if draft.charges:
        draft.charges[-1]["description"] = _clean(
            f"{draft.charges[-1]['description']} {value}"
        )


def _party_groups(stream: Sequence[str | None]) -> list[list[str]]:
    groups: list[list[str]] = []
    current: list[str] = []
    for value in stream:
        if value is None:
            if current:
                groups.append(current)
                current = []
            continue
        if not current or value != current[-1]:
            current.append(value)
    if current:
        groups.append(current)
    return groups


def _party_record(role: str, lines: Sequence[str]) -> dict[str, Any]:
    address_start: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if re.match(
            r"^(?:c/o\b|care\s+of\b|P\.?\s*O\.?\s+BOX\b|"
            r"\d+[A-Z]?(?:-\d+)?\s+\S+)",
            line,
            re.IGNORECASE,
        ):
            address_start = index
            break
    if address_start is None:
        name_lines = list(lines[:1])
        address_lines = list(lines[1:])
    else:
        name_lines = list(lines[:address_start])
        address_lines = list(lines[address_start:])
    return {
        "role": role,
        "published_name": _clean(" ".join(name_lines)) or None,
        "published_name_lines": name_lines,
        "published_address": _clean(" ".join(address_lines)) or None,
        "published_address_lines": address_lines,
        "published_lines": list(lines),
    }


def _court_id(court_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", court_name.casefold()).strip("-")
    return f"us-md-{slug or 'mdec-court'}"


def _finalize_case(
    draft: _CaseDraft,
    *,
    report_metadata: Mapping[str, Any],
    source_url: str | None,
) -> dict[str, Any]:
    case_number = "".join(draft.case_number_parts)
    caption = _clean(" ".join(draft.caption_parts)) or None
    case_type = _clean(" ".join(draft.case_type_parts)) or None
    court_id = _court_id(draft.court_name)
    parties = [
        _party_record(role, group)
        for role, stream in draft.party_streams.items()
        for group in _party_groups(stream)
        if group
    ]
    party_names = [
        str(party["published_name"])
        for party in parties
        if party.get("published_name")
    ]
    addresses = [
        str(party["published_address"])
        for party in parties
        if party.get("published_address")
    ]
    return {
        "record_kind": "recent_case_filing",
        "source_id": SOURCE_ID,
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            court_id,
            case_number,
        ),
        "court_id": court_id,
        "court_name": draft.court_name,
        "case_number": case_number,
        "case_caption": caption,
        "case_type": case_type,
        "filing_date": _iso_date(draft.file_date_raw),
        "filing_date_raw": draft.file_date_raw,
        "parties": parties,
        "charges": draft.charges,
        "report_publication_date": report_metadata.get(
            "report_publication_date"
        ),
        "reporting_period_start": report_metadata.get(
            "reporting_period_start"
        ),
        "reporting_period_end": report_metadata.get("reporting_period_end"),
        "report_run_at": report_metadata.get("report_run_at"),
        "report_run_at_raw": report_metadata.get("report_run_at_raw"),
        "source_page_numbers": sorted(set(draft.page_numbers)),
        "source_document_url": source_url,
        "join_keys": {
            "case_number": case_number,
            "party_names": party_names,
            "published_addresses": addresses,
            "court_name": draft.court_name,
        },
        "raw": {
            "case_number_parts": draft.case_number_parts,
            "caption_parts": draft.caption_parts,
            "case_type_parts": draft.case_type_parts,
            "detail_lines": draft.raw_detail_lines,
        },
    }


def _report_metadata(
    text: str,
    *,
    report_publication_date: str | None,
    source_url: str | None,
) -> dict[str, Any]:
    period = REPORTING_PERIOD_RE.search(text)
    run = RUN_DATE_RE.search(text)
    run_at: str | None = None
    run_raw: str | None = None
    if run:
        run_raw = f"{run.group('run_date')} {run.group('run_time')}"
        try:
            parsed = datetime.strptime(run_raw, "%m/%d/%Y %I:%M %p")
            run_at = parsed.replace(
                tzinfo=ZoneInfo("America/New_York")
            ).isoformat()
        except ValueError:
            run_at = None
    return {
        "record_kind": "daily_case_report",
        "source_id": SOURCE_ID,
        "report_name": "CBS721 - Cases Filed Report",
        "report_publication_date": report_publication_date,
        "reporting_period_start": (
            _iso_date(period.group("start")) if period else None
        ),
        "reporting_period_end": (
            _iso_date(period.group("end")) if period else None
        ),
        "report_run_at": run_at,
        "report_run_at_raw": run_raw,
        "source_document_url": source_url,
    }


def parse_cases_filed_text(
    text: str,
    *,
    report_publication_date: str | None = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Parse layout-preserving text from one CBS721 report."""

    if "AOC - Cases Filed Report" not in text:
        raise MarylandSourceChangedError(
            "Text does not identify an AOC Cases Filed Report",
            url=source_url,
        )
    metadata = _report_metadata(
        text,
        report_publication_date=report_publication_date,
        source_url=source_url,
    )
    records: list[dict[str, Any]] = []
    current: _CaseDraft | None = None
    page_count = 0
    for page_number, page in enumerate(text.split("\f"), start=1):
        if not page.strip():
            continue
        page_count += 1
        lines = page.splitlines()
        positions = _header_positions(lines)
        if positions is None:
            continue
        header_index, style_pos, type_pos, date_pos = positions
        court_name = _court_name(lines, header_index)
        for line in lines[header_index + 1 :]:
            stripped = _clean(line)
            if (
                stripped.startswith("Page:")
                and "Report Name: CBS721 - Cases Filed Report" in stripped
            ):
                continue
            new_case = _new_case(
                line,
                court_name=court_name,
                page_number=page_number,
                style_pos=style_pos,
                type_pos=type_pos,
                date_pos=date_pos,
            )
            if new_case is not None:
                if current is not None:
                    records.append(
                        _finalize_case(
                            current,
                            report_metadata=metadata,
                            source_url=source_url,
                        )
                    )
                current = new_case
                continue
            if current is None:
                continue
            if stripped and page_number not in current.page_numbers:
                current.page_numbers.append(page_number)
            if stripped:
                current.raw_detail_lines.append(stripped)
            layout = _role_layout(line)
            if layout:
                current.mode = "parties"
                current.role_layout = layout
                for role, _start, _end in layout:
                    current.party_streams.setdefault(role, [])
                continue
            if re.match(r"^\s*Charges:\s*$", line, re.IGNORECASE):
                current.mode = "charges"
                current.role_layout = []
                continue
            if current.mode == "parties":
                _append_party_line(current, line)
                continue
            if current.mode == "charges":
                _append_charge_line(current, line)
                continue
            if not stripped:
                continue
            case_fragment = _clean(line[:style_pos])
            caption_fragment = _clean(line[style_pos:type_pos])
            case_type_fragment = _clean(line[type_pos:date_pos])
            if (
                case_fragment
                and current.case_number_parts[-1].endswith("-")
                and re.fullmatch(r"[A-Za-z0-9-]+", case_fragment)
            ):
                current.case_number_parts.append(case_fragment)
            if caption_fragment:
                current.caption_parts.append(caption_fragment)
            if case_type_fragment:
                current.case_type_parts.append(case_type_fragment)
    if current is not None:
        records.append(
            _finalize_case(
                current,
                report_metadata=metadata,
                source_url=source_url,
            )
        )
    if not records:
        raise MarylandSourceChangedError(
            "Cases Filed text contained no parseable case rows",
            url=source_url,
        )
    metadata["page_count"] = page_count
    metadata["case_count"] = len(records)
    metadata["courts"] = sorted(
        {str(record["court_name"]) for record in records}
    )
    return {"report": metadata, "records": records}


def _source_manifest() -> dict[str, Any]:
    return {
        "source": SOURCE_METADATA.to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "operations": {
            "reports": "discover current source-published report routes",
            "download": "download and hash one discovered report",
            "parse": "parse and filter a local report PDF",
            "search": "download and search the latest or all current reports",
            "probe": "verify landing-page discovery, directory, PDF, and parser",
        },
        "coverage": {
            "window": "rolling five daily reports",
            "included": "public cases created by MDEC courts",
            "source_stated_omission": (
                "cases secured at initiation and subsequently made public"
            ),
            "non_mdec_state": (
                "landing page states non-MDEC case details will be provided "
                "in the future"
            ),
        },
        "related_source_routes": [
            {
                "source_id": "us-md-case-search",
                "name": "Maryland Judiciary Case Search & Record Portal",
                "url": CASE_SEARCH_URL,
                "role": "statewide_case_discovery_and_case_detail",
                "operation_state": "interactive_agreement_and_captcha",
                "join_keys": ["case_number", "party_name", "court_name"],
            },
            {
                "source_id": "us-md-judgment-liens",
                "name": "Maryland Judiciary Judgment and Liens Search",
                "url": JUDGMENT_LIENS_URL,
                "role": "circuit_court_judgment_and_lien_index",
                "join_keys": ["case_number", "party_name", "court_name"],
            },
            {
                "source_id": "us-md-estate-search",
                "name": "Maryland Register of Wills Estate Search",
                "url": ESTATE_SEARCH_URL,
                "role": "estate_case_parties_status_and_docket",
                "join_keys": ["estate_number", "party_name", "county"],
            },
            {
                "source_id": "us-md-appellate-opinions",
                "name": "Maryland Appellate Court Opinions",
                "url": APPELLATE_OPINIONS_URL,
                "role": "published_appellate_opinions",
                "join_keys": ["case_number", "party_name"],
            },
            {
                "source_id": "us-md-aoc-court-data",
                "name": "Maryland Judicial Records Requests",
                "url": JUDICIAL_RECORDS_URL,
                "role": "clerk_and_aoc_record_or_data_request_routes",
                "join_keys": ["case_number", "court_name", "jurisdiction"],
            },
            {
                "source_id": "us-md-sdat-property-hidden",
                "name": "Maryland Real Property Assessments",
                "url": SDAT_DATASET_URL,
                "role": "parcel_assessment_situs_deed_reference",
                "join_keys": ["published_address", "county", "account_id"],
            },
            {
                "source_id": "us-md-land-records",
                "name": "Maryland Land Records",
                "url": MDLANDREC_URL,
                "information_url": LAND_RECORDS_GUIDE_URL,
                "role": "deeds_mortgages_recorded_liens_and_instruments",
                "operation_state": "free_account_required",
                "join_keys": [
                    "party_name",
                    "published_address",
                    "deed_liber",
                    "deed_folio",
                ],
            },
            {
                "source_id": "us-md-plats",
                "name": "Maryland State Archives Plats.net",
                "url": PLATS_URL,
                "role": "land_record_plats",
                "join_keys": ["county", "plat_reference", "published_address"],
            },
        ],
        "official_information_urls": [
            LANDING_URL,
            CASE_SEARCH_FAQ_URL,
            COURT_RECORDS_URL,
        ],
    }


def _record_haystack(record: Mapping[str, Any]) -> str:
    return canonical_json(record).casefold()


def _matches(record: Mapping[str, Any], filters: Mapping[str, str | None]) -> bool:
    case_number = filters.get("case_number")
    if case_number and str(record.get("case_number", "")).casefold() != case_number.casefold():
        return False
    court = filters.get("court")
    if court and court.casefold() not in str(record.get("court_name", "")).casefold():
        return False
    case_type = filters.get("case_type")
    if case_type and case_type.casefold() not in str(record.get("case_type", "")).casefold():
        return False
    filing_date = filters.get("filing_date")
    if filing_date and record.get("filing_date") != filing_date:
        return False
    filing_date_from = filters.get("filing_date_from")
    if (
        filing_date_from
        and str(record.get("filing_date") or "") < filing_date_from
    ):
        return False
    filing_date_to = filters.get("filing_date_to")
    if (
        filing_date_to
        and str(record.get("filing_date") or "") > filing_date_to
    ):
        return False
    name = filters.get("name")
    if name:
        names = " ".join(
            str(party.get("published_name") or "")
            for party in record.get("parties", ())
        )
        names = f"{record.get('case_caption') or ''} {names}"
        if name.casefold() not in names.casefold():
            return False
    address = filters.get("address")
    if address:
        addresses = " ".join(
            str(party.get("published_address") or "")
            for party in record.get("parties", ())
        )
        if address.casefold() not in addresses.casefold():
            return False
    charge = filters.get("charge")
    if charge:
        charges = " ".join(
            str(item.get("description") or "")
            for item in record.get("charges", ())
        )
        if charge.casefold() not in charges.casefold():
            return False
    query = filters.get("query")
    return not query or query.casefold() in _record_haystack(record)


def _query_iso_date(value: Any, field_name: str) -> str | None:
    normalized = _clean(value)
    if not normalized:
        return None
    try:
        return date.fromisoformat(normalized).isoformat()
    except ValueError as error:
        raise MarylandSelectionError(
            f"{field_name} must be an ISO date (YYYY-MM-DD)"
        ) from error


def _filters(args: argparse.Namespace) -> dict[str, str | None]:
    filters = {
        "query": _clean(getattr(args, "query", None)) or None,
        "case_number": _clean(getattr(args, "case_number", None)) or None,
        "name": _clean(getattr(args, "name", None)) or None,
        "address": _clean(getattr(args, "address", None)) or None,
        "court": _clean(getattr(args, "court", None)) or None,
        "case_type": _clean(getattr(args, "case_type", None)) or None,
        "charge": _clean(getattr(args, "charge", None)) or None,
        "filing_date": _query_iso_date(
            getattr(args, "filing_date", None),
            "--filing-date",
        ),
        "filing_date_from": _query_iso_date(
            getattr(args, "filing_date_from", None),
            "--filing-date-from",
        ),
        "filing_date_to": _query_iso_date(
            getattr(args, "filing_date_to", None),
            "--filing-date-to",
        ),
    }
    if (
        filters["filing_date_from"]
        and filters["filing_date_to"]
        and filters["filing_date_from"] > filters["filing_date_to"]
    ):
        raise MarylandSelectionError(
            "--filing-date-from must not follow --filing-date-to"
        )
    return filters


def _cursor_key(selection: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(selection).encode()).hexdigest()[:16]


def _page_records(
    records: Sequence[Mapping[str, Any]],
    *,
    selection: Mapping[str, Any],
    cursor: str | None,
    limit: int | None,
) -> tuple[list[Mapping[str, Any]], str | None]:
    offset = 0
    key = _cursor_key(selection)
    if cursor:
        match = CURSOR_RE.fullmatch(cursor)
        if match is None:
            raise MarylandSelectionError("Cursor format is invalid")
        if match.group("key") != key:
            raise MarylandSelectionError(
                "Cursor belongs to a different Maryland report query"
            )
        offset = int(match.group("offset"))
    if limit is None:
        return list(records[offset:]), None
    page = list(records[offset : offset + limit])
    next_offset = offset + len(page)
    next_cursor = (
        f"md-mdec:v1:{key}:offset:{next_offset}"
        if next_offset < len(records)
        else None
    )
    return page, next_cursor


def _query(
    operation: str,
    parameters: Mapping[str, Any],
    *,
    cursor: str | None = None,
    requested_limit: int | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            cursor=cursor,
            requested_limit=requested_limit,
        ),
    )


def _failure(
    query: PublicRecordsQuery,
    error: MarylandPublicCasesError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def _select_routes(
    routes: Sequence[ReportRoute],
    *,
    requested_dates: Sequence[str],
    all_current: bool,
) -> list[ReportRoute]:
    by_date = {route.report_date: route for route in routes}
    if requested_dates:
        missing = sorted(set(requested_dates) - set(by_date))
        if missing:
            raise MarylandSelectionError(
                "Requested report date is not in the current source-published directory",
                details={
                    "missing_dates": missing,
                    "available_dates": sorted(by_date, reverse=True),
                },
            )
        return [by_date[value] for value in dict.fromkeys(requested_dates)]
    return list(routes) if all_current else list(routes[:1])


def _save_download(report: DownloadedReport, destination: Path) -> None:
    destination = destination.expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(report.content)


def _download_record(
    report: DownloadedReport,
    *,
    local_path: Path | None = None,
) -> dict[str, Any]:
    return {
        **report.route.to_dict(),
        "record_kind": "daily_case_report_artifact",
        "local_path": str(local_path) if local_path else None,
        "mime_type": "application/pdf",
        "source_media_type": report.media_type,
        "size_bytes": len(report.content),
        "sha256": report.sha256,
    }


def _parse_and_filter(
    pdf_path: Path,
    *,
    route: ReportRoute | None,
    filters: Mapping[str, str | None],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    text = extract_pdf_tsv(pdf_path)
    publication_date = route.report_date if route else None
    if publication_date is None:
        filename_match = REPORT_FILENAME_RE.fullmatch(pdf_path.name)
        publication_date = (
            filename_match.group("report_date") if filename_match else None
        )
    parsed = parse_cases_filed_tsv(
        text,
        report_publication_date=publication_date,
        source_url=route.source_url if route else None,
    )
    records = [
        record for record in parsed["records"] if _matches(record, filters)
    ]
    return parsed["report"], records


def execute(
    args: argparse.Namespace,
    *,
    client: MarylandPublicCasesClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one adapter operation."""

    own_client = client is None
    source_client = client or MarylandPublicCasesClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )
    query = _query(args.command, {})
    try:
        if args.command == "routes":
            query = _query("routes", {})
            result = PublicRecordsResult.success(
                query,
                [_source_manifest()],
                raw_artifact_refs=[LANDING_URL],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "reports":
            directory_url, routes = source_client.report_routes()
            query = _query("reports", {"directory_url": directory_url})
            result = PublicRecordsResult.success(
                query,
                [route.to_dict() for route in routes],
                raw_artifact_refs=[LANDING_URL, directory_url],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "download":
            directory_url, routes = source_client.report_routes()
            selected = _select_routes(
                routes,
                requested_dates=[args.report_date],
                all_current=False,
            )[0]
            query = _query(
                "download",
                {
                    "report_date": selected.report_date,
                    "destination": str(args.destination),
                },
            )
            downloaded = source_client.download(selected)
            _save_download(downloaded, args.destination)
            result = PublicRecordsResult.success(
                query,
                [_download_record(downloaded, local_path=args.destination)],
                raw_artifact_refs=[
                    directory_url,
                    selected.source_url,
                    str(args.destination),
                ],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "parse":
            filters = _filters(args)
            selection = {
                "artifact": str(args.artifact.expanduser().resolve()),
                "filters": filters,
            }
            limit = None if args.all_results else args.limit
            query = _query(
                "parse",
                selection,
                cursor=args.cursor,
                requested_limit=limit,
            )
            report, records = _parse_and_filter(
                args.artifact,
                route=None,
                filters=filters,
            )
            page, next_cursor = _page_records(
                records,
                selection=selection,
                cursor=args.cursor,
                limit=limit,
            )
            result = PublicRecordsResult.success(
                query,
                page,
                next_cursor=next_cursor,
                raw_artifact_refs=[str(args.artifact.expanduser().resolve())],
                warnings=(
                    *SOURCE_WARNINGS,
                    f"Parsed report contains {report['case_count']} cases before filtering.",
                ),
            )
        elif args.command in {"search", "probe"}:
            directory_url, routes = source_client.report_routes()
            selected = _select_routes(
                routes,
                requested_dates=(
                    list(args.report_date)
                    if args.command == "search"
                    else []
                ),
                all_current=(
                    args.all_current if args.command == "search" else False
                ),
            )
            filters = _filters(args) if args.command == "search" else {
                key: None
                for key in (
                    "query",
                    "case_number",
                    "name",
                    "address",
                    "court",
                    "case_type",
                    "charge",
                    "filing_date",
                )
            }
            selection = {
                "report_dates": [route.report_date for route in selected],
                "filters": filters,
            }
            limit = (
                None
                if args.command == "probe" or args.all_results
                else args.limit
            )
            query = _query(
                args.command,
                selection,
                cursor=getattr(args, "cursor", None),
                requested_limit=limit,
            )
            records: list[dict[str, Any]] = []
            artifacts: list[str] = [LANDING_URL, directory_url]
            probe_reports: list[dict[str, Any]] = []
            with tempfile.TemporaryDirectory(prefix="md-mdec-public-cases-") as temporary:
                temporary_path = Path(temporary)
                for route in selected:
                    downloaded = source_client.download(route)
                    pdf_path = temporary_path / route.filename
                    pdf_path.write_bytes(downloaded.content)
                    parsed_report, matches = _parse_and_filter(
                        pdf_path,
                        route=route,
                        filters=filters,
                    )
                    records.extend(matches)
                    artifacts.append(route.source_url)
                    probe_reports.append(
                        {
                            **_download_record(downloaded),
                            "parsed_report": parsed_report,
                        }
                    )
            if args.command == "probe":
                result = PublicRecordsResult.success(
                    query,
                    [
                        {
                            "record_kind": "source_probe",
                            "directory_url": directory_url,
                            "available_report_dates": [
                                route.report_date for route in routes
                            ],
                            "latest_report": probe_reports[0],
                            "operation_states": {
                                "landing_page": "available",
                                "report_directory": "available",
                                "pdf_download": "available",
                                "coordinate_text_parse": "available",
                            },
                        }
                    ],
                    raw_artifact_refs=artifacts,
                    warnings=SOURCE_WARNINGS,
                )
            else:
                records.sort(
                    key=lambda record: (
                        str(record.get("filing_date") or ""),
                        str(record.get("court_name") or ""),
                        str(record.get("case_number") or ""),
                    ),
                    reverse=True,
                )
                page, next_cursor = _page_records(
                    records,
                    selection=selection,
                    cursor=args.cursor,
                    limit=limit,
                )
                result = PublicRecordsResult.success(
                    query,
                    page,
                    next_cursor=next_cursor,
                    raw_artifact_refs=artifacts,
                    warnings=SOURCE_WARNINGS,
                )
        else:
            raise MarylandSelectionError(
                f"Unsupported operation: {args.command}"
            )
    except MarylandPublicCasesError as error:
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


def _add_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--query", help="Case-insensitive search across the record")
    parser.add_argument("--case-number", help="Exact source-published case number")
    parser.add_argument("--name", help="Party or caption substring")
    parser.add_argument("--address", help="Published party-address substring")
    parser.add_argument("--court", help="Court/location substring")
    parser.add_argument("--case-type", help="Case-type substring")
    parser.add_argument("--charge", help="Charge-description substring")
    parser.add_argument("--filing-date", help="Exact filing date (YYYY-MM-DD)")
    parser.add_argument(
        "--filing-date-from",
        help="Include filings on or after this ISO date",
    )
    parser.add_argument(
        "--filing-date-to",
        help="Include filings on or before this ISO date",
    )
    parser.add_argument("--cursor")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument(
        "--all-results",
        action="store_true",
        help="Return all matching records without result pagination",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Maryland Judiciary daily public-case reports"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    routes = subparsers.add_parser(
        "routes",
        help="Show report coverage and related official record routes",
    )
    _add_runtime_and_output(routes)

    reports = subparsers.add_parser(
        "reports",
        help="List reports currently published in the rolling directory",
    )
    _add_runtime_and_output(reports)

    download = subparsers.add_parser(
        "download",
        help="Download one report discovered in the current directory",
    )
    download.add_argument("report_date", help="Report filename date (YYYY-MM-DD)")
    download.add_argument("destination", type=Path)
    _add_runtime_and_output(download)

    parse = subparsers.add_parser(
        "parse",
        help="Parse and filter a local Cases Filed PDF",
    )
    parse.add_argument("artifact", type=Path)
    _add_filters(parse)
    _add_runtime_and_output(parse)

    search = subparsers.add_parser(
        "search",
        help="Search the latest or all current source-published reports",
    )
    report_selection = search.add_mutually_exclusive_group()
    report_selection.add_argument(
        "--report-date",
        action="append",
        default=[],
        help="Search a current report date; repeat to select several",
    )
    report_selection.add_argument(
        "--all-current",
        action="store_true",
        help="Search every report in the current rolling directory",
    )
    _add_filters(search)
    _add_runtime_and_output(search)

    probe = subparsers.add_parser(
        "probe",
        help="Verify report discovery, download, and layout parsing",
    )
    probe.set_defaults(
        report_date=[],
        all_current=False,
        all_results=True,
        limit=DEFAULT_LIMIT,
        cursor=None,
    )
    _add_runtime_and_output(probe)
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.minimum_interval < 0:
        raise SystemExit("--minimum-interval must not be negative")
    if args.max_attempts <= 0:
        raise SystemExit("--max-attempts must be positive")
    if args.retry_backoff < 0:
        raise SystemExit("--retry-backoff must not be negative")
    if hasattr(args, "limit") and args.limit <= 0:
        raise SystemExit("--limit must be positive")
    if getattr(args, "filing_date", None):
        try:
            date.fromisoformat(args.filing_date)
        except ValueError as exc:
            raise SystemExit("--filing-date must use YYYY-MM-DD") from exc
    report_dates: list[str] = []
    if args.command == "download":
        report_dates = [args.report_date]
    elif args.command == "search":
        report_dates = list(args.report_date)
    for report_date in report_dates:
        try:
            date.fromisoformat(report_date)
        except ValueError as exc:
            raise SystemExit("--report-date must use YYYY-MM-DD") from exc


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Maryland MDEC public cases {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Maryland MDEC public cases {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            f"  {record.get('case_number') or record.get('report_date') or '?'}"
            f" | {record.get('court_name') or record.get('filename') or '?'}"
            f" | {record.get('case_caption') or record.get('source_url') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    args = build_parser().parse_args()
    _validate_args(args)
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
