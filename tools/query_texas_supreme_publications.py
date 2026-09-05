#!/usr/bin/env python3
"""Query the Supreme Court of Texas official Orders & Opinions pages.

The source publishes an annual release-date index and one HTML hand-down page
per date.  Release pages contain the complete orders text, a print-order PDF,
optional editorial case summaries, and case-linked opinions or separate
writings.  The landing page also carries the distinct May 2020 outage files
and pre-October-2014 aggregate archives.

Examples:
    uv run python tools/query_texas_supreme_publications.py source --json
    uv run python tools/query_texas_supreme_publications.py years --json
    uv run python tools/query_texas_supreme_publications.py releases \
        --year 2026 --json
    uv run python tools/query_texas_supreme_publications.py release \
        2026-05-29 --json
    uv run python tools/query_texas_supreme_publications.py search Huffman \
        --year 2026 --json
    uv run python tools/query_texas_supreme_publications.py download \
        "https://www.txcourts.gov/media/1462796/240205.pdf" \
        /tmp/240205.pdf --json
    uv run python tools/query_texas_supreme_publications.py probe --json
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
from typing import Any, Mapping
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

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
        sha256_fingerprint,
    )
    from tools.public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
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
        sha256_fingerprint,
    )
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )


SOURCE_ID = "us-tx-supreme-orders-opinions"
RECORD_IDENTITY_SOURCE_ID = "us-tx-appellate-tames"
STATE_CODE = "TX"
STATE_GEOID = "48"
COURT_ID = "tx-appellate-cossup"
COURT_NAME = "Supreme Court of Texas"

BASE_URL = "https://www.txcourts.gov"
LANDING_URL = f"{BASE_URL}/supreme/orders-opinions/"
LEGACY_ARCHIVE_URL = "https://search.txcourts.gov/historical/recent.htm"
TAMES_CASE_URL = "https://search.txcourts.gov/Case.aspx"
TAMES_RELEASE_URL = "https://search.txcourts.gov/DocketSrch.aspx?coa=cossup"
ANNUAL_FIRST_YEAR = 2014
PROBE_YEAR = 2026
PROBE_RELEASE_DATE = "2026-05-29"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_USER_AGENT = (
    "IthildinOSINT/1.0 Texas Supreme Court official publications client"
)
MAXIMUM_HTML_BYTES = 12 * 1024 * 1024
MAXIMUM_PDF_BYTES = 150 * 1024 * 1024
OUTPUT_SCHEMA_VERSION = "texas-supreme-orders-opinions/1.0"
CURSOR_PREFIX = "tx-supreme-publications:v1:"

CASE_NUMBER_RE = re.compile(r"^\d{2}-\d{4}$")
CASE_NUMBER_SEARCH_RE = re.compile(r"\b\d{2}-\d{4}\b")
LOWER_DOCKET_RE = re.compile(r"\b\d{2}-\d{2}-\d{4,5}-(?:CV|CR)\b", re.I)
MEDIA_ID_RE = re.compile(r"/media/(\d+)/", re.I)
DATE_LABEL_FORMATS = ("%B %d, %Y", "%B %e, %Y", "%m/%d/%Y")
RELEASE_PATH_RE = re.compile(
    r"^/supreme/orders-opinions/(?P<year>\d{4})/"
    r"(?P<month>[a-z]+)/(?P<label>[a-z]+-\d{1,2}-\d{4})/$",
    re.I,
)
PDF_HOSTS = frozenset({"www.txcourts.gov", "txcourts.gov"})

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Supreme Court of Texas Orders and Opinions",
    source_role="official_supreme_court_release_pages_and_publications",
    base_url=LANDING_URL,
    dataset_id="texas-supreme-orders-opinions",
    metadata={
        "authority": COURT_NAME,
        "operator": "Texas Judicial Branch",
        "authentication": "none",
        "record_identity_source_id": RECORD_IDENTITY_SOURCE_ID,
        "current_site_coverage": "October 2014 to current annual pages",
        "legacy_archive": LEGACY_ARCHIVE_URL,
        "native_release_index": "one annual HTML page listing every release date",
        "release_body_selector": "#oReportDiv",
        "complementary_source_ids": [
            "us-tx-appellate-tames",
            "us-tx-appellate-released-orders-opinions",
        ],
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Texas",
    state_code=STATE_CODE,
)
COURT = {
    "court_id": COURT_ID,
    "native_court_id": "cossup",
    "name": COURT_NAME,
    "state_code": STATE_CODE,
    "court_level": "supreme",
    "official_url": "https://www.txcourts.gov/supreme/",
}
SOURCE_WARNINGS = (
    (
        "This source is the court's publication representation. TAMES case "
        "and release pages remain separately attributable representations; "
        "matching documents are retrieval redundancy, not corroboration."
    ),
    (
        "Editorial case summaries, print-order releases, case opinions, "
        "separate writings, outage files, and fiscal-year aggregates retain "
        "independent document identities."
    ),
    (
        "County and lower-appellate references are preserved as published "
        "locator candidates rather than treated as complete lower-court data."
    ),
)


class TexasSupremePublicationsError(RuntimeError):
    """Source error carrying public-record envelope semantics."""

    code = "texas_supreme_publications_error"
    status = ResultStatus.UNAVAILABLE
    category = "source"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.details = dict(details or {})

    def public_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


class SelectionError(TexasSupremePublicationsError):
    code = "invalid_selection"
    category = "query"


class TransportError(TexasSupremePublicationsError):
    code = "transport_error"
    category = "transport"
    retryable = True


class RestrictedError(TexasSupremePublicationsError):
    code = "access_restricted"
    status = ResultStatus.RESTRICTED
    category = "access"


class RateLimitedError(TexasSupremePublicationsError):
    code = "rate_limited"
    status = ResultStatus.RATE_LIMITED
    category = "rate_limit"
    retryable = True


class SourceChangedError(TexasSupremePublicationsError):
    code = "source_changed"
    status = ResultStatus.SOURCE_CHANGED
    category = "source_schema"


@dataclass(frozen=True)
class Artifact:
    content: bytes
    source_url: str
    media_type: str | None
    headers: Mapping[str, str]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True)
class AnnualIndex:
    year: int
    releases: tuple[Mapping[str, Any], ...]
    source_url: str
    source_document_sha256: str
    schema_fingerprint: str


@dataclass(frozen=True)
class ReleasePage:
    release_date: str
    records: tuple[Mapping[str, Any], ...]
    release_artifact: Mapping[str, Any]
    source_url: str
    source_document_sha256: str
    schema_fingerprint: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _date_text(value: str, *, field_name: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise SelectionError(
            f"{field_name} must use YYYY-MM-DD",
            details={"field": field_name, "value": value},
        ) from error


def _label_date(value: str) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    for format_string in DATE_LABEL_FORMATS:
        try:
            return datetime.strptime(normalized, format_string).date().isoformat()
        except ValueError:
            continue
    return None


def annual_url(year: int) -> str:
    if year < ANNUAL_FIRST_YEAR:
        raise SelectionError(
            "Annual release pages begin in 2014",
            details={"year": year, "first_year": ANNUAL_FIRST_YEAR},
        )
    return f"{LANDING_URL}{year}/"


def _official_html_url(value: str) -> str:
    url = urljoin(LANDING_URL, value)
    parsed = urlsplit(url)
    if (
        parsed.scheme.casefold() != "https"
        or parsed.netloc.casefold() not in PDF_HOSTS
        or not parsed.path.startswith("/supreme/orders-opinions/")
    ):
        raise SelectionError(
            "URL is not an official Texas Supreme Court publication page",
            details={"url": value},
        )
    return url


def _official_pdf_url(value: str) -> str:
    url = urljoin(LANDING_URL, value)
    parsed = urlsplit(url)
    if (
        parsed.scheme.casefold() != "https"
        or parsed.netloc.casefold() not in PDF_HOSTS
        or not parsed.path.casefold().endswith(".pdf")
    ):
        raise SelectionError(
            "URL is not an official Texas Judicial Branch PDF",
            details={"url": value},
        )
    return url


def _media_type(headers: Mapping[str, Any]) -> str | None:
    value = headers.get("content-type") or headers.get("Content-Type")
    return str(value).split(";", 1)[0].strip().casefold() or None if value else None


def _retry_after(response: Any) -> float | None:
    value = getattr(response, "headers", {}).get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


class TexasSupremePublicationsClient:
    """Bounded anonymous client for official HTML and PDF routes."""

    def __init__(
        self,
        *,
        session: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=DEFAULT_MAX_ATTEMPTS
        )
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.sleeper = sleeper
        self.request_count = 0
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def get(
        self,
        url: str,
        *,
        document: bool = False,
    ) -> Artifact:
        resolved = _official_pdf_url(url) if document else _official_html_url(url)
        maximum_bytes = MAXIMUM_PDF_BYTES if document else MAXIMUM_HTML_BYTES
        accept = "application/pdf" if document else "text/html,application/xhtml+xml"
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.session.get(
                    resolved,
                    headers={
                        "Accept": accept,
                        "Referer": LANDING_URL,
                    },
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise TransportError(
                    f"Texas Supreme publication request failed: {error}",
                    details={"url": resolved, "attempts": attempt},
                ) from error
            status_code = int(getattr(response, "status_code", 0))
            if status_code in self.retry_policy.retry_statuses:
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(
                        self.retry_policy.delay(attempt, _retry_after(response))
                    )
                    continue
                if status_code == 429:
                    raise RateLimitedError(
                        "Texas Supreme publication source rate limited the request",
                        details={"url": resolved, "status_code": status_code},
                    )
            if status_code in {401, 403}:
                raise RestrictedError(
                    f"Texas Supreme publication source returned HTTP {status_code}",
                    details={"url": resolved, "status_code": status_code},
                )
            if status_code < 200 or status_code >= 300:
                raise TransportError(
                    f"Texas Supreme publication source returned HTTP {status_code}",
                    details={"url": resolved, "status_code": status_code},
                )
            content = bytes(getattr(response, "content", b""))
            if len(content) > maximum_bytes:
                raise SourceChangedError(
                    "Texas Supreme publication response exceeded the size bound",
                    details={
                        "url": resolved,
                        "byte_length": len(content),
                        "maximum_bytes": maximum_bytes,
                    },
                )
            artifact = Artifact(
                content=content,
                source_url=str(getattr(response, "url", None) or resolved),
                media_type=_media_type(getattr(response, "headers", {})),
                headers={
                    str(key).casefold(): str(value)
                    for key, value in getattr(response, "headers", {}).items()
                },
            )
            if document and (
                artifact.media_type not in {None, "application/pdf"}
                or not artifact.content.startswith(b"%PDF-")
            ):
                raise SourceChangedError(
                    "Official Texas Supreme document did not return a PDF",
                    details={
                        "url": artifact.source_url,
                        "media_type": artifact.media_type,
                        "signature_hex": artifact.content[:8].hex(),
                    },
                )
            return artifact
        raise TransportError(
            f"Texas Supreme publication request failed: {last_error}",
            details={"url": resolved},
        )

    def landing(self) -> Artifact:
        return self.get(LANDING_URL)

    def annual(self, year: int) -> Artifact:
        return self.get(annual_url(year))

    def release(self, source_url: str) -> Artifact:
        return self.get(source_url)

    def document(self, source_url: str) -> Artifact:
        return self.get(source_url, document=True)


def _document(
    href: str,
    *,
    document_type: str,
    label: str | None,
    release_date: str | None,
    case_number: str | None = None,
    context: str | None = None,
) -> dict[str, Any]:
    source_url = _official_pdf_url(href)
    match = MEDIA_ID_RE.search(urlsplit(source_url).path)
    native_id = (
        f"TXSC-MEDIA:{match.group(1)}"
        if match
        else f"TXSC-URL:{hashlib.sha256(source_url.encode()).hexdigest()[:24]}"
    )
    return {
        "native_document_id": native_id,
        "document_type": document_type,
        "title": label,
        "source_url": source_url,
        "media_type": "application/pdf",
        "release_date": release_date,
        "case_number": case_number,
        "context_text": context,
        "access_state": "public",
        "certified_record": False,
    }


def _case_document_type(anchor_text: str, context: str) -> str:
    label = anchor_text.casefold()
    combined = f"{anchor_text} {context}".casefold()
    candidate = label or combined
    if "per curiam" in candidate:
        return "per_curiam_opinion"
    if "concurr" in candidate:
        return "concurring_opinion"
    if "dissent" in candidate:
        return "dissenting_opinion"
    if "opinion" in candidate:
        return "court_opinion"
    if "order" in candidate:
        return "court_order"
    if label and label != combined:
        return _case_document_type("", context)
    return "case_publication"


def _outage_document_type(
    group: str,
    label: str,
    *,
    anchor_index: int,
) -> str:
    combined = label.casefold()
    if group == "orders":
        if "special" in combined:
            return "network_outage_special_order"
        if "miscellaneous" in combined:
            return "network_outage_miscellaneous_orders"
        if "causes" in combined or "clauses" in combined:
            return "network_outage_orders_on_causes"
        return "network_outage_print_orders"
    if "concurr" in combined:
        return "network_outage_concurring_opinion"
    if "dissent" in combined:
        return "network_outage_dissenting_opinion"
    if "per curiam" in combined:
        return "network_outage_per_curiam_opinion"
    if anchor_index > 0 and not CASE_NUMBER_SEARCH_RE.search(label):
        return "network_outage_separate_opinion"
    return "network_outage_court_opinion"


def _main_content(soup: BeautifulSoup) -> Tag:
    main = soup.find(id="MainContent")
    if not isinstance(main, Tag):
        raise SourceChangedError("Official page no longer exposes #MainContent")
    return main


def parse_landing(artifact: Artifact) -> list[dict[str, Any]]:
    """Parse annual indexes plus separately typed outage and legacy artifacts."""

    soup = BeautifulSoup(artifact.content, "html.parser")
    main = _main_content(soup)
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for anchor in main.find_all("a", href=True):
        label = _text(anchor.get_text(" ", strip=True))
        if label is None:
            continue
        href = urljoin(artifact.source_url, str(anchor["href"]))
        path = urlsplit(href).path
        year_match = re.fullmatch(
            r"/supreme/orders-opinions/(\d{4})/",
            path,
            re.I,
        )
        if year_match and label.isdigit():
            year = int(year_match.group(1))
            key = ("annual_release_index", str(year))
            if key not in seen:
                seen.add(key)
                records.append(
                    {
                        "record_kind": "annual_release_index",
                        "source_id": SOURCE_ID,
                        "year": year,
                        "source_url": _official_html_url(href),
                        "coverage_type": "release_date_index",
                    }
                )
            continue
        if href == LEGACY_ARCHIVE_URL:
            key = ("pre_2014_archive", href)
            if key not in seen:
                seen.add(key)
                records.append(
                    {
                        "record_kind": "pre_2014_archive",
                        "source_id": SOURCE_ID,
                        "document_type": "pre_october_2014_html_archive",
                        "title": label,
                        "source_url": href,
                        "coverage_end": "2014-09-30",
                        "representation": "legacy_site_copy",
                    }
                )
            continue
        fiscal_match = re.fullmatch(
            r"FY\s+(\d{4})\s+(Orders|Opinions)",
            label,
            re.I,
        )
        if fiscal_match:
            fiscal_year = int(fiscal_match.group(1))
            collection = fiscal_match.group(2).casefold()
            document = _document(
                href,
                document_type=f"fiscal_year_{collection}_aggregate",
                label=label,
                release_date=None,
            )
            key = ("fiscal_year_aggregate", document["native_document_id"])
            if key not in seen:
                seen.add(key)
                records.append(
                    {
                        "record_kind": "fiscal_year_aggregate",
                        "source_id": SOURCE_ID,
                        "fiscal_year": fiscal_year,
                        "collection": collection,
                        "document": document,
                        "source_url": artifact.source_url,
                    }
                )

    outage_heading = next(
        (
            heading
            for heading in main.find_all(["h2", "h3"])
            if "network outage"
            in (_text(heading.get_text(" ", strip=True)) or "").casefold()
        ),
        None,
    )
    if isinstance(outage_heading, Tag):
        group: str | None = None
        release_date: str | None = None
        node = outage_heading.find_next()
        while isinstance(node, Tag):
            if node.name == "h2":
                break
            if node.name == "h3":
                value = (_text(node.get_text(" ", strip=True)) or "").casefold()
                if value in {"orders", "opinions"}:
                    group = value
            elif node.name == "h4":
                release_date = _label_date(
                    _text(node.get_text(" ", strip=True)) or ""
                )
            elif node.name == "li" and group and release_date:
                li_text = _text(node.get_text(" ", strip=True)) or ""
                case_match = CASE_NUMBER_SEARCH_RE.search(li_text)
                case_number = case_match.group(0) if case_match else None
                for anchor_index, anchor in enumerate(
                    node.find_all("a", href=True)
                ):
                    anchor_label = (
                        _text(anchor.get_text(" ", strip=True)) or li_text
                    )
                    document_type = _outage_document_type(
                        group,
                        anchor_label,
                        anchor_index=anchor_index,
                    )
                    document = _document(
                        str(anchor["href"]),
                        document_type=document_type,
                        label=anchor_label,
                        release_date=release_date,
                        case_number=case_number,
                        context=li_text,
                    )
                    key = ("network_outage_document", document["native_document_id"])
                    if key in seen:
                        continue
                    seen.add(key)
                    records.append(
                        {
                            "record_kind": "network_outage_document",
                            "source_id": SOURCE_ID,
                            "outage_group": group,
                            "release_date": release_date,
                            "case_number": case_number,
                            "document": document,
                            "raw_list_text": li_text,
                            "source_url": artifact.source_url,
                        }
                    )
            node = node.find_next()

    if not any(record["record_kind"] == "annual_release_index" for record in records):
        raise SourceChangedError("Landing page no longer lists annual release indexes")
    if not any(record["record_kind"] == "network_outage_document" for record in records):
        raise SourceChangedError("Landing page no longer lists May 2020 outage files")
    if not any(record["record_kind"] == "fiscal_year_aggregate" for record in records):
        raise SourceChangedError("Landing page no longer lists fiscal-year archives")
    return records


def parse_annual_index(artifact: Artifact, *, year: int) -> AnnualIndex:
    """Parse every release-date link on one source-reported annual page."""

    soup = BeautifulSoup(artifact.content, "html.parser")
    main = _main_content(soup)
    releases: list[dict[str, Any]] = []
    seen_dates: set[str] = set()
    for anchor in main.find_all("a", href=True):
        release_date = _label_date(_text(anchor.get_text(" ", strip=True)) or "")
        if release_date is None or int(release_date[:4]) != year:
            continue
        source_url = _official_html_url(
            urljoin(artifact.source_url, str(anchor["href"]))
        )
        path_match = RELEASE_PATH_RE.fullmatch(urlsplit(source_url).path)
        if path_match is None or int(path_match.group("year")) != year:
            continue
        if release_date in seen_dates:
            raise SourceChangedError(
                "Annual page repeats a release date",
                details={"year": year, "release_date": release_date},
            )
        seen_dates.add(release_date)
        releases.append(
            {
                "record_kind": "release_index_entry",
                "source_id": SOURCE_ID,
                "release_date": release_date,
                "year": year,
                "month": int(release_date[5:7]),
                "source_url": source_url,
                "annual_index_url": artifact.source_url,
            }
        )
    if not releases:
        raise SourceChangedError(
            "Annual page contains no release-date links",
            details={"year": year, "source_url": artifact.source_url},
        )
    releases.sort(key=lambda value: str(value["release_date"]))
    schema = {
        "record_fields": sorted(releases[0]),
        "path_shape": "/supreme/orders-opinions/YYYY/month/month-D-YYYY/",
        "release_count": len(releases),
    }
    return AnnualIndex(
        year=year,
        releases=tuple(releases),
        source_url=artifact.source_url,
        source_document_sha256=artifact.sha256,
        schema_fingerprint=sha256_fingerprint(schema),
    )


def _leaf_rows(report: Tag) -> list[Tag]:
    rows: list[Tag] = []
    for row in report.find_all("tr"):
        if row.find("tr") is not None:
            continue
        if row.find(["td", "th"], recursive=False) is not None:
            rows.append(row)
    return rows


def _row_cells(row: Tag) -> list[Tag]:
    return [
        value
        for value in row.find_all(["td", "th"], recursive=False)
        if isinstance(value, Tag)
    ]


def _heading_kind(text: str) -> str | None:
    if text != text.upper() or CASE_NUMBER_SEARCH_RE.search(text):
        return None
    if text in {"THE SUPREME COURT OF TEXAS"} or text.startswith(
        "ORDERS PRONOUNCED "
    ):
        return "masthead"
    if (
        text.startswith(("THE FOLLOWING", "THE MOTION", "THE MOTIONS", "A STAY"))
        or text.startswith("THE DECISION")
        or text.endswith(":")
    ):
        return "action"
    if len(text) <= 120:
        return "section"
    return None


def _case_context(raw_text: str) -> dict[str, Any]:
    county_match = re.search(r";\s*from\s+([^;()]+? County)\s*;", raw_text, re.I)
    appeals_match = re.search(
        r"(?P<label>\d+(?:st|nd|rd|th)\s+Court of Appeals District)"
        r"\s*(?P<parenthetical>\([^)]*\))?",
        raw_text,
        re.I,
    )
    marker = re.search(r";\s*(?:from\s+[^;]+;\s*)?\d+(?:st|nd|rd|th)\s+Court", raw_text, re.I)
    caption = raw_text[: marker.start()].rstrip(" ;") if marker else raw_text.split(";", 1)[0]
    lower_dockets = []
    if appeals_match:
        lower_dockets = LOWER_DOCKET_RE.findall(
            appeals_match.group("parenthetical") or ""
        )
    return {
        "caption": _text(caption),
        "originating_county_candidate": (
            _text(county_match.group(1)) if county_match else None
        ),
        "lower_court_candidate": (
            {
                "label": _text(appeals_match.group("label")),
                "case_number_candidates": [value.upper() for value in lower_dockets],
                "raw_parenthetical": _text(appeals_match.group("parenthetical")),
                "authoritative_assignment": False,
            }
            if appeals_match
            else None
        ),
    }


def _release_document_links(
    main: Tag,
    *,
    release_date: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    print_anchor = next(
        (
            anchor
            for anchor in main.find_all("a", href=True)
            if (_text(anchor.get_text(" ", strip=True)) or "").casefold()
            == "print-friendly"
        ),
        None,
    )
    if not isinstance(print_anchor, Tag):
        raise SourceChangedError("Release page lacks its print-friendly order PDF")
    release_artifact = _document(
        str(print_anchor["href"]),
        document_type="print_order_release",
        label=_text(print_anchor.get("title")) or "Print-Friendly",
        release_date=release_date,
    )
    supplemental: list[dict[str, Any]] = []
    for anchor in main.find_all("a", href=True):
        label = _text(anchor.get_text(" ", strip=True))
        if label and label.casefold() == "case summaries":
            supplemental.append(
                _document(
                    str(anchor["href"]),
                    document_type="editorial_case_summary",
                    label=label,
                    release_date=release_date,
                )
            )
    return release_artifact, supplemental


def parse_release_page(
    artifact: Artifact,
    *,
    expected_date: str | None = None,
) -> ReleasePage:
    """Parse a hand-down page by row meaning, independent of generated classes."""

    soup = BeautifulSoup(artifact.content, "html.parser")
    main = _main_content(soup)
    report = main.find(id="oReportDiv")
    if not isinstance(report, Tag):
        raise SourceChangedError("Release page no longer exposes #oReportDiv")
    heading = main.find("h1")
    release_date = _label_date(
        _text(heading.get_text(" ", strip=True)) if isinstance(heading, Tag) else ""
    )
    if release_date is None:
        pronounced = next(
            (
                value
                for value in report.stripped_strings
                if _text(value)
                and (_text(value) or "").casefold().startswith("orders pronounced ")
            ),
            None,
        )
        release_date = _label_date(
            (_text(pronounced) or "").removeprefix("Orders Pronounced ")
        )
    if release_date is None:
        raise SourceChangedError("Release page date could not be parsed")
    if expected_date and release_date != expected_date:
        raise SourceChangedError(
            "Release page date differs from the selected date",
            details={"expected": expected_date, "observed": release_date},
        )
    release_artifact, release_documents = _release_document_links(
        main,
        release_date=release_date,
    )

    records: list[dict[str, Any]] = []
    section: str | None = None
    action: str | None = None
    current: dict[str, Any] | None = None
    occurrences: dict[str, int] = {}
    row_shapes: set[tuple[int, str]] = set()

    for row_index, row in enumerate(_leaf_rows(report), start=1):
        cells = _row_cells(row)
        values = [_text(cell.get_text(" ", strip=True)) for cell in cells]
        values = [value for value in values if value is not None]
        if not values:
            continue
        combined = " ".join(values)
        first = values[0]
        row_shapes.add((len(cells), "case" if CASE_NUMBER_RE.fullmatch(first) else "text"))

        if CASE_NUMBER_RE.fullmatch(first):
            if len(values) < 2:
                raise SourceChangedError(
                    "Case row lacks published case text",
                    details={"row_index": row_index, "case_number": first},
                )
            raw_case_text = " ".join(values[1:])
            occurrences[first] = occurrences.get(first, 0) + 1
            occurrence = occurrences[first]
            context = _case_context(raw_case_text)
            current = {
                "record_kind": "supreme_court_release_case",
                "source_id": SOURCE_ID,
                "record_identity_source_id": RECORD_IDENTITY_SOURCE_ID,
                "court": dict(COURT),
                "raw_case_number": first,
                "display_case_number": first,
                "caption": context["caption"],
                "release_date": release_date,
                "release_year": int(release_date[:4]),
                "release_occurrence": occurrence,
                "release_occurrence_id": (
                    f"TXSC-RELEASE:{release_date}:{first}:{occurrence}"
                ),
                "section_heading_raw": section,
                "action_heading_raw": action,
                "raw_case_text": raw_case_text,
                "originating_county_candidate": context[
                    "originating_county_candidate"
                ],
                "lower_court_candidate": context["lower_court_candidate"],
                "detail_text": [],
                "participation_text": [],
                "case_documents": [],
                "release_artifact": dict(release_artifact),
                "release_documents": [dict(value) for value in release_documents],
                "related_links": [],
                "source_url": artifact.source_url,
                "annual_index_url": annual_url(int(release_date[:4])),
                "access_state": "public",
                "certified_record": False,
            }
            records.append(current)
            continue

        heading_text = re.sub(
            r"^Case Summaries\s+",
            "",
            combined,
            flags=re.I,
        )
        kind = _heading_kind(heading_text)
        if kind == "section":
            section = heading_text
            action = None
            current = None
            continue
        if kind == "action":
            action = heading_text
            current = None
            continue
        if kind == "masthead" or combined.casefold() == "case summaries":
            continue
        if current is None:
            continue

        participation = "justice" in combined.casefold() and (
            "participating" in combined.casefold()
            or "not participating" in combined.casefold()
            or "joined" in combined.casefold()
            or "delivered" in combined.casefold()
            or "filed" in combined.casefold()
        )
        if participation:
            current["participation_text"].append(combined)
        if not combined.lstrip().casefold().startswith("(justice"):
            current["detail_text"].append(combined)
        for anchor in row.find_all("a", href=True):
            href = urljoin(artifact.source_url, str(anchor["href"]))
            label = _text(anchor.get_text(" ", strip=True))
            if urlsplit(href).path.casefold().endswith(".pdf"):
                current["case_documents"].append(
                    _document(
                        href,
                        document_type=_case_document_type(label or "", combined),
                        label=label,
                        release_date=release_date,
                        case_number=str(current["raw_case_number"]),
                        context=combined,
                    )
                )
            else:
                current["related_links"].append(
                    {"label": label, "source_url": href}
                )

    if not records:
        raise SourceChangedError(
            "Release page contains no native Supreme Court case rows",
            details={"release_date": release_date},
        )
    for record in records:
        record["disposition_text"] = " ".join(
            value
            for value in [
                record["action_heading_raw"],
                *record["detail_text"],
            ]
            if value
        ) or None
        record["source_document_sha256"] = artifact.sha256
    schema = {
        "container": "#oReportDiv",
        "record_fields": sorted(records[0]),
        "row_shapes": sorted(row_shapes),
        "release_document_types": sorted(
            {
                release_artifact["document_type"],
                *(value["document_type"] for value in release_documents),
            }
        ),
        "case_document_types": sorted(
            {
                document["document_type"]
                for record in records
                for document in record["case_documents"]
            }
        ),
    }
    schema_fingerprint = sha256_fingerprint(schema)
    for record in records:
        record["source_schema_fingerprint"] = schema_fingerprint
    return ReleasePage(
        release_date=release_date,
        records=tuple(records),
        release_artifact=release_artifact,
        source_url=artifact.source_url,
        source_document_sha256=artifact.sha256,
        schema_fingerprint=schema_fingerprint,
    )


def source_record() -> dict[str, Any]:
    return {
        "record_kind": "source_manifest",
        "source_id": SOURCE_ID,
        "record_identity_source_id": RECORD_IDENTITY_SOURCE_ID,
        "court": dict(COURT),
        "source_url": LANDING_URL,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "commands": [
            "source",
            "years",
            "releases",
            "release",
            "search",
            "download",
            "probe",
        ],
        "coverage": {
            "annual_release_pages_first_year": ANNUAL_FIRST_YEAR,
            "annual_release_pages_end": "source_reported_current",
            "network_outage_documents": "May 2020 distinct landing-page set",
            "legacy_html_archive_end": "2014-09-30",
            "fiscal_year_aggregate_pdfs": [2009, 2010, 2011, 2012, 2013, 2014],
        },
        "document_types": [
            "print_order_release",
            "editorial_case_summary",
            "court_opinion",
            "per_curiam_opinion",
            "concurring_opinion",
            "dissenting_opinion",
            "court_order",
            "network_outage_document_family",
            "pre_october_2014_html_archive",
            "fiscal_year_orders_aggregate",
            "fiscal_year_opinions_aggregate",
        ],
        "identity": {
            "release_occurrence": [
                "release_date",
                "raw_case_number",
                "release_occurrence",
            ],
            "case": [
                "record_identity_source_id",
                "court.native_court_id",
                "raw_case_number",
            ],
            "document": ["native_document_id", "source_url"],
        },
        "complements": [
            {
                "source_id": "us-tx-appellate-tames",
                "role": "case_detail_docket_parties_and_public_documents",
                "independent_corroboration": False,
            },
            {
                "source_id": "us-tx-appellate-released-orders-opinions",
                "role": "legacy_TAMES_release_index_representation",
                "independent_corroboration": False,
            },
        ],
    }


def _years_from_args(args: argparse.Namespace) -> list[int]:
    years = sorted(set(getattr(args, "year", None) or []))
    date_from = (
        _date_text(args.date_from, field_name="--date-from")
        if getattr(args, "date_from", None)
        else None
    )
    date_to = (
        _date_text(args.date_to, field_name="--date-to")
        if getattr(args, "date_to", None)
        else None
    )
    if date_from and date_to and date_from > date_to:
        raise SelectionError("--date-from must not be later than --date-to")
    if date_from or date_to:
        first = int((date_from or f"{ANNUAL_FIRST_YEAR}-01-01")[:4])
        last = int((date_to or str(date.today()))[:4])
        years.extend(range(max(first, ANNUAL_FIRST_YEAR), last + 1))
    years = sorted(set(years))
    if not years:
        raise SelectionError(
            "Select at least one annual page with --year or a date range"
        )
    if min(years) < ANNUAL_FIRST_YEAR:
        raise SelectionError(
            "Annual release-page searches begin in 2014",
            details={"first_year": ANNUAL_FIRST_YEAR},
        )
    return years


def _selected_releases(
    args: argparse.Namespace,
    client: Any,
) -> tuple[list[dict[str, Any]], list[AnnualIndex]]:
    years = _years_from_args(args)
    date_from = getattr(args, "date_from", None)
    date_to = getattr(args, "date_to", None)
    releases: list[dict[str, Any]] = []
    indexes: list[AnnualIndex] = []
    for year in years:
        index = parse_annual_index(client.annual(year), year=year)
        indexes.append(index)
        releases.extend(dict(value) for value in index.releases)
    if date_from:
        releases = [
            value for value in releases if value["release_date"] >= date_from
        ]
    if date_to:
        releases = [
            value for value in releases if value["release_date"] <= date_to
        ]
    return releases, indexes


def _selection_fingerprint(args: argparse.Namespace) -> str:
    return sha256_fingerprint(
        {
            "command": args.command,
            "query": getattr(args, "query", None),
            "case_number": getattr(args, "case_number", None),
            "year": sorted(getattr(args, "year", None) or []),
            "date_from": getattr(args, "date_from", None),
            "date_to": getattr(args, "date_to", None),
            "document_type": sorted(getattr(args, "document_type", None) or []),
        }
    )


def _encode_cursor(
    *,
    offset: int,
    selection_fingerprint: str,
    release_set_fingerprint: str,
) -> str:
    payload = canonical_json(
        {
            "offset": offset,
            "selection": selection_fingerprint,
            "release_set": release_set_fingerprint,
        }
    ).encode()
    return CURSOR_PREFIX + base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(
    cursor: str | None,
    *,
    selection_fingerprint: str,
    release_set_fingerprint: str,
) -> int:
    if cursor is None:
        return 0
    if not cursor.startswith(CURSOR_PREFIX):
        raise SelectionError("Cursor does not belong to this source")
    encoded = cursor.removeprefix(CURSOR_PREFIX)
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode()
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SelectionError("Cursor is malformed") from error
    if (
        payload.get("selection") != selection_fingerprint
        or payload.get("release_set") != release_set_fingerprint
    ):
        raise SelectionError(
            "Cursor no longer matches the selected release-page set"
        )
    offset = payload.get("offset")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise SelectionError("Cursor offset is invalid")
    return offset


def _slice_records(
    records: list[dict[str, Any]],
    *,
    args: argparse.Namespace,
    release_set_fingerprint: str,
) -> tuple[list[dict[str, Any]], str | None]:
    selection = _selection_fingerprint(args)
    offset = _decode_cursor(
        getattr(args, "cursor", None),
        selection_fingerprint=selection,
        release_set_fingerprint=release_set_fingerprint,
    )
    if offset > len(records):
        raise SelectionError("Cursor offset exceeds the current result set")
    limit = getattr(args, "limit", None)
    if limit is None:
        return records[offset:], None
    selected = records[offset : offset + limit]
    next_offset = offset + len(selected)
    next_cursor = (
        _encode_cursor(
            offset=next_offset,
            selection_fingerprint=selection,
            release_set_fingerprint=release_set_fingerprint,
        )
        if next_offset < len(records)
        else None
    )
    return selected, next_cursor


def _record_matches(record: Mapping[str, Any], args: argparse.Namespace) -> bool:
    case_number = _text(getattr(args, "case_number", None))
    if case_number and str(record.get("raw_case_number", "")).casefold() != case_number.casefold():
        return False
    wanted_types = {
        value.casefold().replace("-", "_")
        for value in (getattr(args, "document_type", None) or [])
    }
    if wanted_types:
        observed = {
            str(document.get("document_type", "")).casefold()
            for key in ("case_documents", "release_documents")
            for document in record.get(key, [])
        }
        artifact = record.get("release_artifact")
        if isinstance(artifact, Mapping):
            observed.add(str(artifact.get("document_type", "")).casefold())
        if not observed.intersection(wanted_types):
            return False
    query = (_text(getattr(args, "query", None)) or "*").casefold()
    if query in {"*", "all"}:
        return True
    haystack = canonical_json(record).casefold()
    return query in haystack


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    def json_value(value: Any) -> Any:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, list):
            return [json_value(item) for item in value]
        return value

    parameters = {
        key: json_value(value)
        for key, value in vars(args).items()
        if key
        not in {
            "output",
            "json_out",
            "timeout",
            "minimum_interval",
            "max_attempts",
            "overwrite",
        }
        and value is not None
        and value is not False
        and not callable(value)
    }
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _execute(
    args: argparse.Namespace,
    client: Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command == "source":
        return PublicRecordsResult.success(
            query,
            [source_record()],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "years":
        artifact = client.landing()
        records = parse_landing(artifact)
        for record in records:
            record["source_document_sha256"] = artifact.sha256
        return PublicRecordsResult.success(
            query,
            records,
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "releases":
        releases, indexes = _selected_releases(args, client)
        release_fingerprint = sha256_fingerprint(releases)
        selected, next_cursor = _slice_records(
            releases,
            args=args,
            release_set_fingerprint=release_fingerprint,
        )
        for record in selected:
            index = next(
                value for value in indexes if value.year == record["year"]
            )
            record["annual_index_sha256"] = index.source_document_sha256
            record["source_schema_fingerprint"] = index.schema_fingerprint
        return PublicRecordsResult.success(
            query,
            selected,
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "release":
        selected_date = _date_text(args.release_date, field_name="release_date")
        index = parse_annual_index(
            client.annual(int(selected_date[:4])),
            year=int(selected_date[:4]),
        )
        release = next(
            (
                value
                for value in index.releases
                if value["release_date"] == selected_date
            ),
            None,
        )
        if release is None:
            return PublicRecordsResult.success(
                query,
                [],
                warnings=SOURCE_WARNINGS,
            )
        page = parse_release_page(
            client.release(str(release["source_url"])),
            expected_date=selected_date,
        )
        records = [dict(value) for value in page.records]
        return PublicRecordsResult.success(
            query,
            records,
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "search":
        releases, _indexes = _selected_releases(args, client)
        release_fingerprint = sha256_fingerprint(releases)
        records: list[dict[str, Any]] = []
        for release in releases:
            page = parse_release_page(
                client.release(str(release["source_url"])),
                expected_date=str(release["release_date"]),
            )
            records.extend(
                dict(value)
                for value in page.records
                if _record_matches(value, args)
            )
        selected, next_cursor = _slice_records(
            records,
            args=args,
            release_set_fingerprint=release_fingerprint,
        )
        return PublicRecordsResult.success(
            query,
            selected,
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "download":
        artifact = client.document(args.document_url)
        destination = Path(args.destination)
        if destination.exists() and not args.overwrite:
            raise SelectionError(
                "Destination exists; pass --overwrite",
                details={"destination": str(destination)},
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(artifact.content)
        document = _document(
            artifact.source_url,
            document_type="downloaded_official_publication",
            label=Path(unquote(urlsplit(artifact.source_url).path)).name,
            release_date=None,
        )
        return PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "download_receipt",
                    "source_id": SOURCE_ID,
                    "document": document,
                    "artifact_path": str(destination),
                    "byte_length": len(artifact.content),
                    "sha256": artifact.sha256,
                    "media_type": artifact.media_type,
                }
            ],
            raw_artifact_refs=[str(destination)],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "probe":
        landing = client.landing()
        landing_records = parse_landing(landing)
        annual = parse_annual_index(client.annual(PROBE_YEAR), year=PROBE_YEAR)
        release_entry = next(
            value
            for value in annual.releases
            if value["release_date"] == PROBE_RELEASE_DATE
        )
        release = parse_release_page(
            client.release(str(release_entry["source_url"])),
            expected_date=PROBE_RELEASE_DATE,
        )
        pdf = client.document(str(release.release_artifact["source_url"]))
        return PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "source_probe",
                    "source_id": SOURCE_ID,
                    "status": "ok",
                    "requests_made": 4,
                    "probe_year": PROBE_YEAR,
                    "probe_release_date": PROBE_RELEASE_DATE,
                    "annual_release_count": len(annual.releases),
                    "release_case_count": len(release.records),
                    "landing_record_kinds": sorted(
                        {value["record_kind"] for value in landing_records}
                    ),
                    "stable_contract": {
                        "source": SOURCE_METADATA.to_dict(),
                        "court": COURT,
                        "output_schema_version": OUTPUT_SCHEMA_VERSION,
                        "release_body_selector": "#oReportDiv",
                        "commands": source_record()["commands"],
                        "document_types": source_record()["document_types"],
                        "identity": source_record()["identity"],
                        "complements": source_record()["complements"],
                    },
                    "schema_fingerprints": {
                        "annual_index": annual.schema_fingerprint,
                        "release_page": release.schema_fingerprint,
                    },
                    "rolling_observation": {
                        "landing_sha256": landing.sha256,
                        "annual_index_sha256": annual.source_document_sha256,
                        "release_page_sha256": release.source_document_sha256,
                        "print_order_pdf_sha256": pdf.sha256,
                        "print_order_pdf_bytes": len(pdf.content),
                    },
                    "source_url": LANDING_URL,
                }
            ],
            warnings=SOURCE_WARNINGS,
        )
    raise SelectionError(f"Unsupported command: {args.command}")


def execute(
    args: argparse.Namespace,
    *,
    client: Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = build_query(args)
    source_client = client or TexasSupremePublicationsClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
    )
    owns_client = client is None
    try:
        result = _execute(args, source_client, query)
    except TexasSupremePublicationsError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.public_error()],
            warnings=SOURCE_WARNINGS,
        )
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="artifact_write_failed",
                    message=str(error),
                    category="local_io",
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    finally:
        if owns_client:
            source_client.close()
    if log_results:
        result_count = (
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        log_search(canonical_json(query.to_dict()), SOURCE_ID, result_count)
    return result


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


def _year(value: str) -> int:
    parsed = int(value)
    if parsed < ANNUAL_FIRST_YEAR:
        raise argparse.ArgumentTypeError(
            f"annual pages begin in {ANNUAL_FIRST_YEAR}"
        )
    return parsed


def _add_runtime(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_int,
        default=DEFAULT_MAX_ATTEMPTS,
    )
    add_output_args(parser)


def _add_scope(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--year", action="append", type=_year)
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--limit", type=_positive_int)
    parser.add_argument("--cursor")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Supreme Court of Texas Orders & Opinions pages"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser("source", help="Describe the source contract")
    _add_runtime(source)

    years = subparsers.add_parser(
        "years",
        help="List annual indexes, outage files, and historical aggregates",
    )
    _add_runtime(years)

    releases = subparsers.add_parser(
        "releases",
        help="Enumerate every release date in selected annual pages",
    )
    _add_scope(releases)
    _add_runtime(releases)

    release = subparsers.add_parser(
        "release",
        help="Fetch one exact release date",
    )
    release.add_argument("release_date")
    _add_runtime(release)

    search = subparsers.add_parser(
        "search",
        help="Search all case rows in selected annual release pages",
    )
    search.add_argument("query", nargs="?", default="*")
    search.add_argument("--case-number")
    search.add_argument("--document-type", action="append")
    _add_scope(search)
    _add_runtime(search)

    download = subparsers.add_parser(
        "download",
        help="Download one exact official PDF",
    )
    download.add_argument("document_url")
    download.add_argument("destination", type=Path)
    download.add_argument("--overwrite", action="store_true")
    _add_runtime(download)

    probe = subparsers.add_parser(
        "probe",
        help="Probe the landing, annual, release, and PDF contracts",
    )
    _add_runtime(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Texas Supreme publications {args.command}",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Texas Supreme publications {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    for record in result.records[:20]:
        print(
            "  "
            + " | ".join(
                str(value)
                for value in (
                    record.get("release_date"),
                    record.get("raw_case_number"),
                    record.get("record_kind"),
                )
                if value
            )
        )
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
