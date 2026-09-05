#!/usr/bin/env python3
"""Query and acquire DOJ's consolidated Epstein court-record releases.

The official DOJ index links to one page per case. Case pages use native HTML
pagination and link to current EFTA PDFs. Reads follow every native page unless
the caller supplies ``--limit``. The bounded probe reads only the index, the
first page of one stable case, and five PDF magic bytes.

When an indexed PDF returns HTML or an HTTP error, ``download`` checks the
current consolidated case listing for an exact EFTA replacement. If DOJ no
longer publishes an exact mapping, the result reports that access gap and
preserves useful docket, archive, and local-corpus alternatives.

Examples:
    uv run python tools/query_doj_court_records.py index --json
    uv run python tools/query_doj_court_records.py index \
        --query "United States v. Epstein" --output /tmp/doj-cases.json
    uv run python tools/query_doj_court_records.py case \
        DOJ_CASE_PAGE_URL \
        --output /tmp/doj-documents.json
    uv run python tools/query_doj_court_records.py download URL DESTINATION \
        --output /tmp/download-receipt.json
    uv run python tools/query_doj_court_records.py recover LEGACY_URL --json
    uv run python tools/query_doj_court_records.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import re
import sys
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import (
    parse_qs,
    unquote,
    urlencode,
    urljoin,
    urlparse,
    urlunparse,
)
from urllib.request import Request, urlopen

import requests

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
    from tools.query_doj import download_epstein_pdf
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
    from query_doj import download_epstein_pdf


SOURCE_ID = "us-doj-epstein-court-records"
INDEX_URL = "https://www.justice.gov/epstein/doj-disclosures"
CASE_PATH_PREFIX = "/epstein/doj-disclosures/court-records-"
CURRENT_PDF_PATH_PREFIX = "/epstein/files/court records/"
LEGACY_PDF_PATH_PREFIX = "/multimedia/court records/"
DOJ_HOSTS = {"justice.gov", "www.justice.gov"}
AGE_COOKIE = "justiceGovAgeVerified=true"
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)
CURSOR_PREFIX = "doj-epstein-court-records:v2:"
CURSOR_VERSION = 2

SENTINEL_CASE_URL = (
    "https://www.justice.gov/epstein/doj-disclosures/"
    "court-records-united-states-v-epstein-no-119-cr-00490-sdny-2019"
)
SENTINEL_EFTA = "EFTA02824136"
SENTINEL_PDF_URL = (
    "https://www.justice.gov/epstein/files/Court%20Records/"
    "United%20States%20v.%20Epstein%2C%20No.%20119-cr-00490%20"
    "%28S.D.N.Y.%202019%29/EFTA02824136.pdf"
)

PACER_URL = "https://pacer.uscourts.gov/"
PACER_CASE_LOCATOR_URL = "https://pcl.uscourts.gov/"
COURTLISTENER_URL = "https://www.courtlistener.com/"
WAYBACK_CDX_URL = "https://web.archive.org/cdx/search/cdx"

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="DOJ Epstein Court Records",
    source_role="official_released_court_record_copy_index_and_documents",
    base_url=INDEX_URL,
    dataset_id="doj-epstein-court-records",
    metadata={
        "authority": "United States Department of Justice",
        "coverage": "DOJ-published copies grouped by underlying court case",
        "authentication": "none",
        "age_verification_cookie": "justiceGovAgeVerified",
        "native_pagination": "zero_based_page_query",
        "document_identity": "EFTA identifier when published",
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-multi-court-doj-release",
    name="United States federal, state, territorial, and appellate courts",
    metadata={
        "publisher": "United States Department of Justice",
        "underlying_courts": "multiple",
    },
)

SOURCE_WARNINGS = (
    "DOJ's Court Records collection is a release corpus, not a complete docket "
    "for every listed case.",
    "Repeated copies across DOJ, PACER, and RECAP are retrieval redundancy "
    "unless their content supplies independent evidence.",
)

_EFTA_RE = re.compile(r"\b(EFTA\d{8})\b", re.IGNORECASE)
_DOCKET_RE = re.compile(
    r"(?:,\s+No\.\s+|,\s+)"
    r"(?P<docket>(?:\d{1,2}:)?\d{2,4}-(?:cv|cr|mc|mj)-[\w-]+|"
    r"\d{2}-\d{4}|SC\d{2}-\d+|ST-\d{2}-[A-Z]{2}-\d+|"
    r"50-\d{4}-[A-Z]{2}-[\w-]+)"
    r"(?:\s+\(|\s*$)",
    re.IGNORECASE,
)


class DOJCourtRecordsError(RuntimeError):
    """Source, transport, or schema error with result-envelope semantics."""

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


class SourceChangedError(DOJCourtRecordsError):
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
class Anchor:
    href: str
    text: str
    title: str | None
    aria_label: str | None
    classes: tuple[str, ...]


@dataclass(frozen=True)
class ParsedPage:
    heading: str | None
    anchors: tuple[Anchor, ...]


@dataclass(frozen=True)
class CaseDocumentPage:
    case_title: str
    documents: tuple[dict[str, Any], ...]
    next_url: str | None
    source_url: str


@dataclass(frozen=True)
class DocumentCollection:
    case_title: str
    documents: tuple[dict[str, Any], ...]
    pages_fetched: int
    source_urls: tuple[str, ...]
    next_cursor: str | None
    incomplete_error: DOJCourtRecordsError | None = None


@dataclass(frozen=True)
class CursorState:
    page_url: str
    offset: int
    criteria_fingerprint: str
    page_fingerprint: str | None


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.heading: str | None = None
        self._heading_depth = 0
        self._heading_parts: list[str] = []
        self._anchor: dict[str, str | None] | None = None
        self._anchor_parts: list[str] = []
        self.anchors: list[Anchor] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = {key.lower(): value for key, value in attrs}
        if tag.lower() == "h1" and self.heading is None:
            self._heading_depth = 1
            self._heading_parts = []
        elif self._heading_depth:
            self._heading_depth += 1

        if tag.lower() == "a":
            self._anchor = attributes
            self._anchor_parts = []

    def handle_endtag(self, tag: str) -> None:
        if self._heading_depth:
            self._heading_depth -= 1
            if self._heading_depth == 0:
                self.heading = " ".join(
                    " ".join(self._heading_parts).split()
                )

        if tag.lower() == "a" and self._anchor is not None:
            href = self._anchor.get("href")
            if href:
                class_value = self._anchor.get("class") or ""
                self.anchors.append(
                    Anchor(
                        href=href,
                        text=" ".join(" ".join(self._anchor_parts).split()),
                        title=self._anchor.get("title"),
                        aria_label=self._anchor.get("aria-label"),
                        classes=tuple(class_value.split()),
                    )
                )
            self._anchor = None
            self._anchor_parts = []

    def handle_data(self, data: str) -> None:
        if self._heading_depth:
            self._heading_parts.append(data)
        if self._anchor is not None:
            self._anchor_parts.append(data)


def parse_html(html: str) -> ParsedPage:
    parser = _LinkParser()
    parser.feed(html)
    parser.close()
    return ParsedPage(parser.heading, tuple(parser.anchors))


def _official_url(url: str, *, base_url: str = INDEX_URL) -> str:
    absolute = urljoin(base_url, url)
    parsed = urlparse(absolute)
    if parsed.scheme != "https" or parsed.hostname not in DOJ_HOSTS:
        raise DOJCourtRecordsError(
            "unofficial_url",
            "URL does not identify an HTTPS justice.gov resource",
            category="query_selection",
            details={"url": absolute},
        )
    return absolute


def _is_case_url(url: str) -> bool:
    parsed = urlparse(urljoin(INDEX_URL, url))
    return (
        parsed.hostname in DOJ_HOSTS
        and unquote(parsed.path).casefold().startswith(CASE_PATH_PREFIX)
    )


def _is_pdf_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in DOJ_HOSTS:
        return False
    path = unquote(parsed.path).casefold()
    return path.endswith(".pdf") and path.startswith(
        (CURRENT_PDF_PATH_PREFIX, LEGACY_PDF_PATH_PREFIX)
    )


def _case_slug(case_url: str) -> str:
    return urlparse(case_url).path.rstrip("/").rsplit("/", 1)[-1]


def _case_title(value: str) -> str:
    title = " ".join(value.split())
    if title.casefold().startswith("court records:"):
        title = title.split(":", 1)[1].strip()
    return title


def _docket_number(case_title: str) -> str | None:
    match = _DOCKET_RE.search(case_title)
    return match.group("docket") if match else None


def parse_index_html(
    html: str,
    *,
    source_url: str = INDEX_URL,
) -> tuple[dict[str, Any], ...]:
    parsed = parse_html(html)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in parsed.anchors:
        if not _is_case_url(anchor.href):
            continue
        case_url = _canonical_case_url(
            _official_url(anchor.href, base_url=source_url)
        )
        if case_url in seen:
            continue
        raw_title = anchor.title or anchor.text
        title = _case_title(raw_title)
        if not title:
            continue
        seen.add(case_url)
        slug = _case_slug(case_url)
        records.append(
            {
                "record_kind": "doj_court_case_listing",
                "canonical_ref": f"DOJ-COURT-CASE:{slug}",
                "case_title": title,
                "docket_number": _docket_number(title),
                "case_page_url": case_url,
                "index_url": source_url,
                "publisher": "United States Department of Justice",
                "coverage_role": "official_release_case_group",
            }
        )
    if not records:
        raise SourceChangedError(
            "court_index_links_missing",
            "DOJ disclosures page contains no recognizable court-record case links",
            details={"source_url": source_url, "heading": parsed.heading},
        )
    return tuple(records)


def _page_number(source_url: str) -> int:
    values = parse_qs(urlparse(source_url).query).get("page")
    if not values:
        return 0
    try:
        return int(values[0])
    except ValueError:
        return 0


def parse_case_html(
    html: str,
    *,
    source_url: str,
) -> CaseDocumentPage:
    parsed = parse_html(html)
    if not parsed.heading or not parsed.heading.casefold().startswith(
        "court records:"
    ):
        raise SourceChangedError(
            "case_heading_changed",
            "DOJ case page is missing its Court Records heading",
            details={"source_url": source_url, "heading": parsed.heading},
        )
    case_title = _case_title(parsed.heading)
    case_slug = _case_slug(source_url)
    page_number = _page_number(source_url)
    documents: list[dict[str, Any]] = []
    seen: set[str] = set()
    next_url: str | None = None

    for anchor in parsed.anchors:
        absolute = urljoin(source_url, anchor.href)
        if _is_pdf_url(absolute) and absolute not in seen:
            seen.add(absolute)
            filename = unquote(urlparse(absolute).path.rsplit("/", 1)[-1])
            efta_match = _EFTA_RE.search(filename)
            efta_id = efta_match.group(1).upper() if efta_match else None
            documents.append(
                {
                    "record_kind": "doj_released_court_document",
                    "canonical_ref": (
                        efta_id
                        if efta_id
                        else f"DOJ-COURT-DOC:{case_slug}:{filename}"
                    ),
                    "efta_id": efta_id,
                    "filename": filename,
                    "case_title": case_title,
                    "docket_number": _docket_number(case_title),
                    "case_page_url": _canonical_case_url(source_url),
                    "indexed_source_url": absolute,
                    "listing_page_url": source_url,
                    "native_page": page_number,
                    "publisher": "United States Department of Justice",
                    "coverage_role": "official_released_copy",
                }
            )
        if anchor.aria_label == "Next page":
            next_url = _official_url(anchor.href, base_url=source_url)

    return CaseDocumentPage(
        case_title=case_title,
        documents=tuple(documents),
        next_url=next_url,
        source_url=source_url,
    )


def _canonical_case_url(url: str) -> str:
    official = _official_url(url)
    if not _is_case_url(official):
        raise DOJCourtRecordsError(
            "invalid_case_url",
            "Case URL must be a DOJ court-record case page",
            category="query_selection",
            details={"url": official},
        )
    parsed = urlparse(official)
    return urlunparse(
        (
            "https",
            "www.justice.gov",
            parsed.path.rstrip("/"),
            "",
            "",
            "",
        )
    )


def _cursor_criteria_fingerprint(case_url: str) -> str:
    return sha256_fingerprint(
        {
            "source_id": SOURCE_ID,
            "case_url": _canonical_case_url(case_url),
        }
    )


def _case_page_fingerprint(page: CaseDocumentPage) -> str:
    return sha256_fingerprint(
        {
            "case_title": page.case_title,
            "documents": page.documents,
            "next_url": page.next_url,
        }
    )


def _encode_cursor(
    url: str,
    *,
    criteria_fingerprint: str,
    offset: int = 0,
    page_fingerprint: str | None = None,
) -> str:
    payload = {
        "version": CURSOR_VERSION,
        "page_url": _official_url(url),
        "offset": offset,
        "criteria_fingerprint": criteria_fingerprint,
        "page_fingerprint": page_fingerprint,
    }
    payload["check"] = sha256_fingerprint(payload)[:16]
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii")
    return CURSOR_PREFIX + encoded.rstrip("=")


def _decode_cursor(
    cursor: str,
    *,
    expected_case_url: str,
    expected_criteria_fingerprint: str,
) -> CursorState:
    if not cursor.startswith(CURSOR_PREFIX):
        raise DOJCourtRecordsError(
            "invalid_cursor",
            "The supplied cursor was not emitted by this adapter",
            category="query_selection",
        )
    try:
        encoded = cursor[len(CURSOR_PREFIX) :]
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
        supplied_check = str(payload.pop("check"))
        expected_check = sha256_fingerprint(payload)[:16]
        version = payload["version"]
        page_url = _official_url(str(payload["page_url"]))
        offset = payload["offset"]
        criteria_fingerprint = str(payload["criteria_fingerprint"])
        page_fingerprint = payload.get("page_fingerprint")
    except (
        binascii.Error,
        DOJCourtRecordsError,
        KeyError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise DOJCourtRecordsError(
            "invalid_cursor",
            "The supplied cursor was not emitted by this adapter",
            category="query_selection",
        ) from exc
    page_parts = urlparse(page_url)
    expected_parts = urlparse(_canonical_case_url(expected_case_url))
    if (
        version != CURSOR_VERSION
        or supplied_check != expected_check
        or criteria_fingerprint != expected_criteria_fingerprint
        or not isinstance(offset, int)
        or isinstance(offset, bool)
        or offset < 0
        or not re.fullmatch(r"[0-9a-f]{64}", criteria_fingerprint)
        or (
            page_fingerprint is not None
            and (
                not isinstance(page_fingerprint, str)
                or not re.fullmatch(r"[0-9a-f]{64}", page_fingerprint)
            )
        )
        or not _is_case_url(page_url)
        or page_parts.path.rstrip("/") != expected_parts.path.rstrip("/")
    ):
        raise DOJCourtRecordsError(
            "invalid_cursor",
            "The supplied cursor does not match this DOJ court-record case",
            category="query_selection",
        )
    return CursorState(
        page_url=page_url,
        offset=offset,
        criteria_fingerprint=criteria_fingerprint,
        page_fingerprint=page_fingerprint,
    )


class DOJCourtRecordsClient:
    """Rate-limited, retrying client for DOJ court-record HTML."""

    def __init__(
        self,
        *,
        session: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml",
            "Cookie": AGE_COOKIE,
            "User-Agent": DEFAULT_USER_AGENT,
        }

    def get_html(self, url: str) -> tuple[str, str]:
        official = _official_url(url)
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    "GET",
                    official,
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise DOJCourtRecordsError(
                    "transport_error",
                    f"DOJ request failed: {exc}",
                    category="transport",
                    retryable=True,
                    details={"url": official},
                ) from exc

            response_url = str(getattr(response, "url", official))
            status_code = int(getattr(response, "status_code", 0))
            if status_code in self.retry_policy.retry_statuses:
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                status = (
                    ResultStatus.RATE_LIMITED
                    if status_code == 429
                    else ResultStatus.UNAVAILABLE
                )
                raise DOJCourtRecordsError(
                    "rate_limited" if status_code == 429 else "http_status",
                    f"DOJ returned HTTP {status_code}",
                    status=status,
                    category="http",
                    retryable=True,
                    details={"url": response_url, "status_code": status_code},
                )
            if status_code == 403:
                raise DOJCourtRecordsError(
                    "edge_access_denied",
                    "DOJ's edge returned HTTP 403 for this page",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"url": response_url, "status_code": status_code},
                )
            if status_code == 404:
                raise DOJCourtRecordsError(
                    "indexed_link_not_found",
                    "DOJ returned HTTP 404 for this page",
                    category="http",
                    details={"url": response_url, "status_code": status_code},
                )
            if status_code < 200 or status_code >= 300:
                raise DOJCourtRecordsError(
                    "http_status",
                    f"DOJ returned HTTP {status_code}",
                    category="http",
                    retryable=status_code >= 500,
                    details={"url": response_url, "status_code": status_code},
                )
            text = str(getattr(response, "text", ""))
            lowered = text.casefold()
            if (
                "/age-verify" in urlparse(response_url).path
                or "<title>age verification" in lowered
            ):
                raise DOJCourtRecordsError(
                    "age_gate_html",
                    "DOJ returned the age-verification interstitial",
                    status=ResultStatus.HUMAN_REQUIRED,
                    category="access",
                    details={"url": response_url},
                )
            if "<html" not in lowered and "<!doctype html" not in lowered:
                raise SourceChangedError(
                    "non_html_page",
                    "DOJ returned a non-HTML case or index response",
                    details={"url": response_url},
                )
            return text, response_url
        raise AssertionError("retry loop exhausted")

    def fetch_index(self) -> tuple[dict[str, Any], ...]:
        html, source_url = self.get_html(INDEX_URL)
        return parse_index_html(html, source_url=source_url)

    def fetch_case_page(self, url: str) -> CaseDocumentPage:
        html, source_url = self.get_html(url)
        return parse_case_html(html, source_url=source_url)

    def fetch_case(
        self,
        case_url: str,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        one_page: bool = False,
    ) -> DocumentCollection:
        if limit is not None and limit <= 0:
            raise DOJCourtRecordsError(
                "invalid_limit",
                "--limit must be a positive integer",
                category="query_selection",
            )
        selected_url = _official_url(case_url)
        case_identity_url = _canonical_case_url(selected_url)
        current_url = case_identity_url
        criteria_fingerprint = _cursor_criteria_fingerprint(case_identity_url)
        offset = 0
        cursor_page_fingerprint: str | None = None
        if cursor:
            cursor_state = _decode_cursor(
                cursor,
                expected_case_url=case_identity_url,
                expected_criteria_fingerprint=criteria_fingerprint,
            )
            current_url = cursor_state.page_url
            offset = cursor_state.offset
            cursor_page_fingerprint = cursor_state.page_fingerprint

        documents: list[dict[str, Any]] = []
        source_urls: list[str] = []
        seen: set[tuple[str, int]] = set()
        pages_fetched = 0
        case_title = ""
        next_cursor: str | None = None
        incomplete_error: DOJCourtRecordsError | None = None

        while current_url:
            key = (current_url, offset)
            if key in seen:
                incomplete_error = SourceChangedError(
                    "pagination_cycle",
                    "DOJ case pagination repeated the same page",
                    details={"url": current_url, "offset": offset},
                )
                break
            seen.add(key)
            try:
                page = self.fetch_case_page(current_url)
            except DOJCourtRecordsError as exc:
                if pages_fetched:
                    incomplete_error = exc
                    next_cursor = _encode_cursor(
                        current_url,
                        criteria_fingerprint=criteria_fingerprint,
                        offset=offset,
                    )
                    break
                raise
            pages_fetched += 1
            source_urls.append(page.source_url)
            page_fingerprint = _case_page_fingerprint(page)
            if (
                cursor_page_fingerprint is not None
                and page_fingerprint != cursor_page_fingerprint
            ):
                raise SourceChangedError(
                    "cursor_page_changed",
                    "DOJ page contents changed before cursor resumption",
                    details={
                        "url": page.source_url,
                        "cursor_page_fingerprint": cursor_page_fingerprint,
                        "observed_page_fingerprint": page_fingerprint,
                    },
                )
            cursor_page_fingerprint = None
            case_title = case_title or page.case_title
            if page.case_title != case_title:
                incomplete_error = SourceChangedError(
                    "case_title_changed",
                    "DOJ pagination moved to a different court-record case",
                    details={
                        "expected": case_title,
                        "observed": page.case_title,
                        "url": page.source_url,
                    },
                )
                break
            if offset > len(page.documents):
                raise SourceChangedError(
                    "cursor_offset_changed",
                    "Cursor offset exceeds the returned DOJ page",
                    details={
                        "url": page.source_url,
                        "offset": offset,
                        "page_records": len(page.documents),
                    },
                )
            for index in range(offset, len(page.documents)):
                if limit is not None and len(documents) >= limit:
                    next_cursor = _encode_cursor(
                        page.source_url,
                        criteria_fingerprint=criteria_fingerprint,
                        offset=index,
                        page_fingerprint=page_fingerprint,
                    )
                    return DocumentCollection(
                        case_title=case_title,
                        documents=tuple(documents),
                        pages_fetched=pages_fetched,
                        source_urls=tuple(source_urls),
                        next_cursor=next_cursor,
                    )
                documents.append(page.documents[index])
            offset = 0
            if one_page:
                if page.next_url:
                    next_cursor = _encode_cursor(
                        page.next_url,
                        criteria_fingerprint=criteria_fingerprint,
                    )
                break
            if limit is not None and len(documents) >= limit and page.next_url:
                next_cursor = _encode_cursor(
                    page.next_url,
                    criteria_fingerprint=criteria_fingerprint,
                )
                break
            current_url = page.next_url or ""

        return DocumentCollection(
            case_title=case_title,
            documents=tuple(documents),
            pages_fetched=pages_fetched,
            source_urls=tuple(source_urls),
            next_cursor=next_cursor,
            incomplete_error=incomplete_error,
        )


def probe_pdf_magic(
    url: str,
    *,
    opener: Callable[..., Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    official = _official_url(url)
    if not _is_pdf_url(official):
        raise DOJCourtRecordsError(
            "invalid_pdf_url",
            "Probe URL must be an indexed DOJ court-record PDF",
            category="query_selection",
            details={"url": official},
        )
    request = Request(
        official,
        headers={
            "Accept": "application/pdf",
            "Cookie": AGE_COOKIE,
            "Range": "bytes=0-4",
            "User-Agent": DEFAULT_USER_AGENT,
        },
    )
    active_opener = opener or urlopen
    try:
        with active_opener(request, timeout=timeout) as response:
            prefix = response.read(5)
            content_type = response.headers.get("Content-Type", "")
            geturl = getattr(response, "geturl", None)
            retrieved_url = geturl() if callable(geturl) else official
            status = getattr(response, "status", None)
            if status is None:
                getcode = getattr(response, "getcode", None)
                status = getcode() if callable(getcode) else None
    except HTTPError as exc:
        raise DOJCourtRecordsError(
            "pdf_probe_http_error",
            f"DOJ PDF probe returned HTTP {exc.code}",
            category="http",
            details={"url": official, "status_code": exc.code},
        ) from exc
    except (URLError, OSError) as exc:
        raise DOJCourtRecordsError(
            "pdf_probe_transport_error",
            f"DOJ PDF probe failed: {exc}",
            category="transport",
            retryable=True,
            details={"url": official},
        ) from exc
    if prefix != b"%PDF-" or "pdf" not in content_type.casefold():
        raise DOJCourtRecordsError(
            "pdf_magic_mismatch",
            "DOJ PDF probe returned HTML or non-PDF bytes",
            category="source_content",
            details={
                "url": retrieved_url,
                "content_type": content_type,
                "prefix_hex": prefix.hex(),
            },
        )
    return {
        "source_url": official,
        "retrieved_url": retrieved_url,
        "http_status": status,
        "content_type": content_type,
        "magic": "%PDF-",
        "bytes_read": len(prefix),
    }


def _query(
    operation: str,
    parameters: Mapping[str, Any] | None = None,
    *,
    requested_limit: int | None = None,
    cursor: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=dict(parameters or {}),
            requested_limit=requested_limit,
            cursor=cursor,
            metadata=dict(metadata or {}),
        ),
    )


def _failure(
    query: PublicRecordsQuery,
    error: DOJCourtRecordsError,
    *,
    records: Sequence[Mapping[str, Any]] = (),
    next_cursor: str | None = None,
    warnings: Sequence[str] = SOURCE_WARNINGS,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.PARTIAL if records else error.status,
        [error.to_contract_error()],
        records=records,
        next_cursor=next_cursor,
        warnings=warnings,
    )


def _index_result(
    args: argparse.Namespace,
    client: DOJCourtRecordsClient,
) -> PublicRecordsResult:
    requested_limit = (
        args.limit
        if args.limit is not None and args.limit > 0
        else None
    )
    query = _query(
        "index",
        {"text_query": args.query},
        requested_limit=requested_limit,
        metadata={
            "source_pages": 1,
            "caller_bound": args.limit is not None,
        },
    )
    if args.limit is not None and args.limit <= 0:
        return _failure(
            query,
            DOJCourtRecordsError(
                "invalid_limit",
                "--limit must be a positive integer",
                category="query_selection",
            ),
        )
    try:
        records = list(client.fetch_index())
        if args.query:
            needle = args.query.casefold()
            records = [
                record
                for record in records
                if needle
                in " ".join(
                    [
                        str(record.get("case_title") or ""),
                        str(record.get("docket_number") or ""),
                    ]
                ).casefold()
            ]
        warnings = list(SOURCE_WARNINGS)
        if args.limit is not None and len(records) > args.limit:
            records = records[: args.limit]
            warnings.append(
                "Results were truncated by the caller-selected --limit."
            )
        return PublicRecordsResult.success(
            query,
            records,
            warnings=warnings,
        )
    except DOJCourtRecordsError as exc:
        return _failure(query, exc)


def _case_result(
    args: argparse.Namespace,
    client: DOJCourtRecordsClient,
) -> PublicRecordsResult:
    requested_limit = (
        args.limit
        if args.limit is not None and args.limit > 0
        else None
    )
    query = _query(
        "case",
        {"case_page_url": args.case_url},
        requested_limit=requested_limit,
        cursor=args.cursor,
        metadata={
            "pagination": (
                "caller_bound"
                if args.limit is not None
                else "exhaustive"
            ),
        },
    )
    if args.limit is not None and args.limit <= 0:
        return _failure(
            query,
            DOJCourtRecordsError(
                "invalid_limit",
                "--limit must be a positive integer",
                category="query_selection",
            ),
        )
    try:
        collection = client.fetch_case(
            args.case_url,
            limit=args.limit,
            cursor=args.cursor,
        )
        retrieval = {
            "transport_pages_fetched": collection.pages_fetched,
            "caller_limit": args.limit,
            "caller_bound_reached": (
                collection.next_cursor is not None
                and collection.incomplete_error is None
            ),
            "source_pagination_complete": (
                collection.next_cursor is None
                and collection.incomplete_error is None
            ),
            "source_page_failure": (
                collection.incomplete_error.code
                if collection.incomplete_error
                else None
            ),
        }
        records = [
            {**dict(document), "retrieval": retrieval}
            for document in collection.documents
        ]
        if collection.incomplete_error:
            return _failure(
                query,
                collection.incomplete_error,
                records=records,
                next_cursor=collection.next_cursor,
            )
        warnings = list(SOURCE_WARNINGS)
        if collection.next_cursor:
            warnings.append(
                "Traversal stopped at the caller-selected --limit; "
                "next_cursor resumes without dropping rows."
            )
        return PublicRecordsResult.success(
            query,
            records,
            next_cursor=collection.next_cursor,
            warnings=warnings,
        )
    except DOJCourtRecordsError as exc:
        return _failure(query, exc)


def _normalize_match_text(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _legacy_case_directory(url: str) -> str | None:
    parts = [unquote(part) for part in urlparse(url).path.split("/") if part]
    if len(parts) < 2:
        return None
    return parts[-2]


def _wayback_url(source_url: str) -> str:
    parameters = {
        "url": source_url,
        "output": "json",
        "filter": "statuscode:200",
        "fl": "timestamp,original,statuscode,mimetype",
    }
    return f"{WAYBACK_CDX_URL}?{urlencode(parameters)}"


def source_alternatives(
    *,
    source_url: str | None = None,
    docket_number: str | None = None,
) -> list[dict[str, Any]]:
    alternatives: list[dict[str, Any]] = [
        {
            "route_id": "doj_current_case_listing",
            "role": "official_released_copy_and_current_efta_identity",
            "url": INDEX_URL,
            "coverage_note": "Case-grouped DOJ release corpus, not a complete docket.",
        },
        {
            "route_id": "pacer_cm_ecf",
            "role": "official_federal_docket_and_document_source",
            "url": PACER_URL,
            "case_locator_url": PACER_CASE_LOCATOR_URL,
            "docket_number": docket_number,
        },
        {
            "route_id": "courtlistener_recap",
            "role": "free_federal_docket_metadata_and_contributed_documents",
            "url": COURTLISTENER_URL,
            "docket_number": docket_number,
        },
        {
            "route_id": "court_clerk",
            "role": "official_state_territorial_or_federal_copy_request",
            "url": None,
            "coverage_note": "Use the court named by the DOJ case listing.",
        },
        {
            "route_id": "local_efta_corpus",
            "role": "locally_ingested_doj_release_copy_and_ocr",
            "tool": "tools/query_doj.py",
            "operation": "efta",
        },
    ]
    if source_url:
        alternatives.append(
            {
                "route_id": "wayback_exact_url",
                "role": "historic_snapshot_of_the_exact_former_doj_url",
                "url": _wayback_url(source_url),
                "coverage_note": (
                    "Archive copy; retain the former DOJ URL as provenance."
                ),
            }
        )
    return alternatives


def resolve_recovery(
    source_url: str,
    *,
    client: DOJCourtRecordsClient,
) -> dict[str, Any]:
    official = _official_url(source_url)
    if not _is_pdf_url(official):
        raise DOJCourtRecordsError(
            "invalid_pdf_url",
            "Recovery URL must be an indexed DOJ court-record PDF",
            category="query_selection",
            details={"url": official},
        )
    filename = unquote(urlparse(official).path.rsplit("/", 1)[-1])
    efta_match = _EFTA_RE.search(filename)
    efta_id = efta_match.group(1).upper() if efta_match else None
    directory = _legacy_case_directory(official)
    normalized_directory = _normalize_match_text(directory or "")

    cases = client.fetch_index()
    matched_case: Mapping[str, Any] | None = None
    for case in cases:
        if _normalize_match_text(str(case["case_title"])) == normalized_directory:
            matched_case = case
            break
    if matched_case is None and directory:
        docket = _docket_number(directory)
        docket_matches = [
            case for case in cases if docket and case.get("docket_number") == docket
        ]
        if len(docket_matches) == 1:
            matched_case = docket_matches[0]

    collection: DocumentCollection | None = None
    exact_current_url: str | None = None
    if matched_case is not None:
        collection = client.fetch_case(str(matched_case["case_page_url"]))
        for document in collection.documents:
            if efta_id and document.get("efta_id") == efta_id:
                exact_current_url = str(document["indexed_source_url"])
                break
            if document.get("filename", "").casefold() == filename.casefold():
                exact_current_url = str(document["indexed_source_url"])
                break

    case_title = (
        str(matched_case["case_title"]) if matched_case is not None else directory
    )
    docket_number = _docket_number(case_title or "")
    return {
        "record_kind": "doj_court_document_recovery",
        "requested_url": official,
        "requested_filename": filename,
        "requested_efta_id": efta_id,
        "legacy_case_directory": directory,
        "current_case_page_url": (
            matched_case.get("case_page_url") if matched_case else None
        ),
        "matched_case_title": (
            matched_case.get("case_title") if matched_case else None
        ),
        "docket_number": docket_number,
        "exact_current_url": exact_current_url,
        "case_documents_observed": (
            len(collection.documents) if collection else 0
        ),
        "case_listing_pages_fetched": (
            collection.pages_fetched if collection else 0
        ),
        "case_listing_complete": (
            collection is not None
            and collection.next_cursor is None
            and collection.incomplete_error is None
        ),
        "case_listing_next_cursor": (
            collection.next_cursor if collection else None
        ),
        "case_listing_error": (
            collection.incomplete_error.to_contract_error().to_dict()
            if collection and collection.incomplete_error
            else None
        ),
        "resolution": (
            "exact_current_document_found"
            if exact_current_url
            else "current_case_found_without_exact_document_mapping"
            if matched_case
            else "current_case_not_identified"
        ),
        "alternatives": source_alternatives(
            source_url=official,
            docket_number=docket_number,
        ),
    }


def _download_error(error: Exception, url: str) -> DOJCourtRecordsError:
    if isinstance(error, HTTPError):
        return DOJCourtRecordsError(
            "indexed_link_not_found"
            if error.code == 404
            else "download_http_error",
            f"DOJ download returned HTTP {error.code}",
            category="http",
            retryable=error.code >= 500,
            details={"url": url, "status_code": error.code},
        )
    if isinstance(error, URLError):
        return DOJCourtRecordsError(
            "download_transport_error",
            f"DOJ download failed: {error}",
            category="transport",
            retryable=True,
            details={"url": url},
        )
    message = str(error)
    return DOJCourtRecordsError(
        "non_pdf_response"
        if "non-PDF response" in message
        else "download_error",
        message or "DOJ download failed",
        category="source_content" if "non-PDF" in message else "download",
        details={"url": url},
    )


def _download_result(
    args: argparse.Namespace,
    client: DOJCourtRecordsClient,
    downloader: Callable[..., Mapping[str, Any]],
) -> PublicRecordsResult:
    query = _query(
        "download",
        {
            "indexed_source_url": args.url,
            "destination": str(args.destination),
            "recovery_enabled": not args.no_recovery,
        },
        metadata={
            "max_bytes": args.max_bytes,
            "max_bytes_kind": (
                "caller_selected" if args.max_bytes is not None else None
            ),
        },
    )
    if args.max_bytes is not None and args.max_bytes <= 0:
        return _failure(
            query,
            DOJCourtRecordsError(
                "invalid_max_bytes",
                "--max-bytes must be a positive integer",
                category="query_selection",
            ),
        )
    try:
        requested_url = _official_url(args.url)
        if not _is_pdf_url(requested_url):
            raise DOJCourtRecordsError(
                "invalid_pdf_url",
                "Download URL must identify a DOJ court-record release PDF",
                category="query_selection",
                details={"url": requested_url},
            )
    except DOJCourtRecordsError as exc:
        return _failure(query, exc)
    try:
        receipt = dict(
            downloader(
                requested_url,
                args.destination,
                max_bytes=args.max_bytes,
            )
        )
        receipt.update(
            {
                "record_kind": "doj_court_document_download",
                "requested_url": requested_url,
                "indexed_source_url": requested_url,
                "recovered_from": None,
            }
        )
        return PublicRecordsResult.success(
            query,
            [receipt],
            warnings=SOURCE_WARNINGS,
        )
    except (HTTPError, URLError, OSError, ValueError) as exc:
        initial_error = _download_error(exc, requested_url)

    recovery: dict[str, Any] | None = None
    if not args.no_recovery:
        try:
            recovery = resolve_recovery(requested_url, client=client)
        except DOJCourtRecordsError as recovery_error:
            details = {
                **initial_error.details,
                "recovery_error": recovery_error.to_contract_error().to_dict(),
                "alternatives": source_alternatives(source_url=requested_url),
            }
            initial_error = DOJCourtRecordsError(
                initial_error.code,
                str(initial_error),
                status=initial_error.status,
                category=initial_error.category,
                retryable=initial_error.retryable,
                details=details,
            )
        else:
            replacement = recovery.get("exact_current_url")
            if replacement and replacement != requested_url:
                try:
                    receipt = dict(
                        downloader(
                            replacement,
                            args.destination,
                            max_bytes=args.max_bytes,
                        )
                    )
                except (HTTPError, URLError, OSError, ValueError) as retry_error:
                    retry_structured = _download_error(
                        retry_error,
                        str(replacement),
                    )
                    initial_error = DOJCourtRecordsError(
                        initial_error.code,
                        str(initial_error),
                        status=initial_error.status,
                        category=initial_error.category,
                        retryable=initial_error.retryable,
                        details={
                            **initial_error.details,
                            "recovery": recovery,
                            "replacement_download_error": (
                                retry_structured.to_contract_error().to_dict()
                            ),
                        },
                    )
                else:
                    receipt.update(
                        {
                            "record_kind": "doj_court_document_download",
                            "requested_url": requested_url,
                            "indexed_source_url": replacement,
                            "recovered_from": requested_url,
                            "recovery": recovery,
                        }
                    )
                    return PublicRecordsResult.success(
                        query,
                        [receipt],
                        warnings=SOURCE_WARNINGS,
                    )
            else:
                initial_error = DOJCourtRecordsError(
                    initial_error.code,
                    str(initial_error),
                    status=initial_error.status,
                    category=initial_error.category,
                    retryable=initial_error.retryable,
                    details={
                        **initial_error.details,
                        "recovery": recovery,
                    },
                )
    return _failure(query, initial_error)


def _recover_result(
    args: argparse.Namespace,
    client: DOJCourtRecordsClient,
) -> PublicRecordsResult:
    query = _query("recover", {"indexed_source_url": args.url})
    try:
        report = resolve_recovery(args.url, client=client)
        return PublicRecordsResult.success(
            query,
            [report],
            warnings=SOURCE_WARNINGS,
        )
    except DOJCourtRecordsError as exc:
        return _failure(query, exc)


def _sources_result() -> PublicRecordsResult:
    record = {
        "record_kind": "doj_court_record_source_inventory",
        "primary_index_url": INDEX_URL,
        "routes": source_alternatives(),
        "coverage_distinctions": {
            "doj": "released copies selected and published by DOJ",
            "pacer": "official federal docket and document system",
            "recap": "free contributed federal docket archive",
            "court_clerk": "official copy route for the named court",
            "wayback": "historic snapshot of a former DOJ URL",
            "local_efta_corpus": "local DOJ release copy and OCR",
        },
    }
    return PublicRecordsResult.success(
        _query("sources"),
        [record],
        warnings=SOURCE_WARNINGS,
    )


def _probe_result(
    client: DOJCourtRecordsClient,
    *,
    pdf_probe: Callable[..., Mapping[str, Any]] = probe_pdf_magic,
) -> PublicRecordsResult:
    query = _query(
        "probe",
        metadata={
            "scope": "bounded_source_health_check",
            "index_pages": 1,
            "case_pages": 1,
            "pdf_bytes": 5,
            "coverage_inference": False,
        },
    )
    try:
        cases = client.fetch_index()
        page = client.fetch_case(
            SENTINEL_CASE_URL,
            one_page=True,
        )
        magic = dict(pdf_probe(SENTINEL_PDF_URL))
        sentinel_cases = [
            case
            for case in cases
            if case.get("case_page_url") == SENTINEL_CASE_URL
        ]
        sentinel_documents = [
            document
            for document in page.documents
            if document.get("efta_id") == SENTINEL_EFTA
        ]
        request_breakdown = {
            "release_index": 1,
            "sentinel_case_page": 1,
            "sentinel_pdf_range": 1,
        }
        record = {
            "record_kind": "doj_court_records_probe",
            "probe_scope": {
                "bounded": True,
                "index_pages": 1,
                "case_pages": 1,
                "pdf_bytes": 5,
                "coverage_inference": False,
            },
            "case_count_on_index": len(cases),
            "sentinel_case_present": len(sentinel_cases) == 1,
            "sentinel_first_page_document_count": len(page.documents),
            "sentinel_document_present": len(sentinel_documents) == 1,
            "sentinel_has_native_next_page": page.next_cursor is not None,
            "pdf_magic": magic,
            "requests_made": sum(request_breakdown.values()),
            "request_breakdown": request_breakdown,
            "healthy": (
                len(sentinel_cases) == 1
                and len(sentinel_documents) == 1
                and magic.get("magic") == "%PDF-"
            ),
        }
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )
    except DOJCourtRecordsError as exc:
        return _failure(query, exc)


def execute(
    args: argparse.Namespace,
    *,
    client: DOJCourtRecordsClient | None = None,
    downloader: Callable[..., Mapping[str, Any]] = download_epstein_pdf,
    pdf_probe: Callable[..., Mapping[str, Any]] = probe_pdf_magic,
    log_results: bool = True,
) -> PublicRecordsResult:
    owns_client = client is None
    active_client = client or DOJCourtRecordsClient()
    try:
        if args.command == "index":
            result = _index_result(args, active_client)
        elif args.command == "case":
            result = _case_result(args, active_client)
        elif args.command == "download":
            result = _download_result(args, active_client, downloader)
        elif args.command == "recover":
            result = _recover_result(args, active_client)
        elif args.command == "sources":
            result = _sources_result()
        elif args.command == "probe":
            result = _probe_result(active_client, pdf_probe=pdf_probe)
        else:
            raise AssertionError(f"unknown command: {args.command}")
    finally:
        if owns_client:
            active_client.close()

    if log_results:
        count = (
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        try:
            log_search(
                canonical_json(result.query.to_dict()),
                SOURCE_ID,
                count,
            )
        except Exception:
            pass
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    index = subparsers.add_parser(
        "index",
        help="List DOJ's current court-record case groups",
    )
    index.add_argument("--query", help="Filter case title or docket number")
    index.add_argument(
        "--limit",
        type=int,
        help="Caller-selected maximum cases; omitted returns every match",
    )
    add_output_args(index)

    case = subparsers.add_parser(
        "case",
        help="List every indexed document for one DOJ case page",
    )
    case.add_argument("case_url")
    case.add_argument(
        "--limit",
        type=int,
        help="Caller-selected maximum documents; omitted exhausts native pages",
    )
    case.add_argument(
        "--cursor",
        help="Resume from next_cursor emitted by an earlier bounded/partial result",
    )
    add_output_args(case)

    download = subparsers.add_parser(
        "download",
        help="Download and validate an indexed PDF, with exact-link recovery",
    )
    download.add_argument("url")
    download.add_argument("destination", type=Path)
    download.add_argument(
        "--max-bytes",
        type=int,
        help="Optional caller-selected maximum download size",
    )
    download.add_argument(
        "--no-recovery",
        action="store_true",
        help="Skip lookup of an exact current DOJ replacement after failure",
    )
    add_output_args(download)

    recover = subparsers.add_parser(
        "recover",
        help="Resolve a former DOJ PDF URL against the current case listing",
    )
    recover.add_argument("url")
    add_output_args(recover)

    sources = subparsers.add_parser(
        "sources",
        help="Show complementary official, archive, and local retrieval routes",
    )
    add_output_args(sources)

    probe = subparsers.add_parser(
        "probe",
        help="Run a bounded read-only index, case, and PDF-magic check",
    )
    add_output_args(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"{SOURCE_ID} {args.command}",
        result_count=len(result.records),
    ):
        return
    print(json.dumps(payload, indent=2))


def main() -> None:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)
    if result.status not in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    }:
        sys.exit(1)


if __name__ == "__main__":
    main()
