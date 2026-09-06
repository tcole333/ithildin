#!/usr/bin/env python3
"""Query D.C. Court of Appeals opinions and MOJ index entries.

The official D.C. Courts page exposes a GET-filtered, zero-based HTML pager.
Published opinions link to court-hosted PDFs. Memorandum Opinion and Judgment
(MOJ) entries intentionally expose index metadata without full text.

Examples:
    uv run python tools/query_dc_opinions.py list --type opinions --page 0 --json
    uv run python tools/query_dc_opinions.py list --query "24-BG-1045" --json
    uv run python tools/query_dc_opinions.py list \
        --date-from 2026-07-01 --date-to 2026-07-31 --all-pages \
        --output /tmp/dc-opinions.json
    uv run python tools/query_dc_opinions.py download \
        "https://www.dccourts.gov/sites/default/files/2026-07/example.pdf" \
        /tmp/example.pdf --json
    uv run python tools/query_dc_opinions.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urljoin, urlparse

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


SOURCE_ID = "us-dc-court-of-appeals-opinions-mojs"
COURT_ID = "us-dc-court-of-appeals"
STATE_CODE = "DC"
STATE_GEOID = "11"
BASE_URL = "https://www.dccourts.gov"
INDEX_PATH = (
    "/court-of-appeals/opinions-and-memorandum-of-judgments"
)
INDEX_URL = f"{BASE_URL}{INDEX_PATH}"
CASE_SEARCH_PAGE = (
    f"{BASE_URL}/court-of-appeals/"
    "court-of-appeals-case-search-and-efiling"
)
SUPERIOR_CASE_SEARCH_PAGE = (
    f"{BASE_URL}/superior-court/superior-court-case-search"
)
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)
ROWS_PER_PAGE = 10
PROBE_APPEAL_NUMBER = "24-BG-1045"
PROBE_CAPTION = "In re Alpert"

NATIVE_TYPES = {
    "all": "All",
    "opinions": "Opinions",
    "mojs": "Memorandums",
}
NATIVE_ORDERS = {
    "date": "field_date",
    "appeal": "title",
    "case": "body",
    "disposition": "field_disposition",
    "judge": "field_judge",
}
EXPECTED_HEADERS = (
    "Appeal Number",
    "Case",
    "Date",
    "Disposition",
    "Judge",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="D.C. Court of Appeals Opinions and MOJs",
    source_role="official_appellate_opinion_and_moj_index",
    base_url=INDEX_URL,
    dataset_id="dccourts-opinions-and-memorandum-of-judgments",
    metadata={
        "authority": "District of Columbia Court of Appeals",
        "operator": "District of Columbia Courts",
        "authentication": "none",
        "native_pagination": "zero_based_page",
        "observed_page_size": ROWS_PER_PAGE,
        "native_filters": [
            "search",
            "date",
            "date_range",
            "type",
            "order",
            "sort",
        ],
        "case_search_complement": CASE_SEARCH_PAGE,
        "superior_court_complement": SUPERIOR_CASE_SEARCH_PAGE,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="District of Columbia",
    state_code=STATE_CODE,
    locality="Washington",
)

SOURCE_WARNINGS = (
    "The official page is an appellate disposition index, not a complete case docket.",
    "The court publishes full-text PDFs for opinions; MOJ entries are listed by case name and appeal number without full text.",
    "Superior Court trial-case records are served through separate court systems.",
)

_APPEAL_RE = re.compile(
    r"\b(?:\d{2}|\d{4})-[A-Z]{2,5}-\d{3,6}(?:-[A-Z]+)?\b",
    flags=re.IGNORECASE,
)
_TOTAL_RE = re.compile(r"\bTotal\s+([\d,]+)\s+items?\b", flags=re.IGNORECASE)
_CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "challenges.cloudflare.com",
)


class DCOpinionsError(RuntimeError):
    """Source error with a public-record result status."""

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


class DCOpinionsSelectionError(DCOpinionsError):
    """The caller supplied an invalid source-native selection."""

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


class DCOpinionsSourceChangedError(DCOpinionsError):
    """The official source no longer matches its observed schema."""

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
class DCOpinionsPage:
    """One native page from the official disposition index."""

    records: tuple[Mapping[str, Any], ...]
    page_number: int
    total_items: int
    total_pages: int
    next_page: int | None
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class DCOpinionsCollection:
    """An exhaustive traversal, or the records fetched before an error."""

    records: tuple[Mapping[str, Any], ...]
    pages_fetched: int
    total_items: int
    total_pages: int
    source_urls: tuple[str, ...]
    schema_fingerprints: tuple[str, ...]
    incomplete_error: DCOpinionsError | None = None


@dataclass(frozen=True)
class DCOpinionPDF:
    """Validated bytes from one official court-hosted opinion PDF."""

    source_url: str
    content: bytes
    media_type: str
    sha256: str


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").split()).strip()
    return normalized or None


def _iso_and_native_date(value: str, field_name: str) -> tuple[str, str]:
    raw = value.strip()
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as error:
        raise DCOpinionsSelectionError(
            "invalid_date",
            f"{field_name} must be an ISO calendar date",
            details={"field": field_name, "value": value},
        ) from error
    return parsed.isoformat(), parsed.strftime("%m/%d/%Y")


def _parse_source_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%b %d, %Y").date().isoformat()
    except ValueError as error:
        raise DCOpinionsSourceChangedError(
            "decision_date_changed",
            f"D.C. opinion row has an unparseable decision date: {value!r}",
            details={"value": value},
        ) from error


def _official_pdf_url(value: str) -> str:
    url = urljoin(BASE_URL, value.strip())
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.dccourts.gov"
        or not parsed.path.startswith("/sites/default/files/")
        or not parsed.path.lower().endswith(".pdf")
    ):
        raise DCOpinionsSelectionError(
            "invalid_pdf_url",
            "PDF URL must identify an official dccourts.gov file",
            details={"url": value},
        )
    return url


def _page_from_url(value: str) -> int | None:
    parsed = urlparse(value)
    values = parse_qs(parsed.query).get("page")
    if not values:
        return None
    try:
        page_number = int(values[0])
    except ValueError:
        return None
    return page_number if page_number >= 0 else None


def _record_type(
    selected_type: str,
    *,
    pdf_url: str | None,
) -> tuple[str, str, str]:
    if selected_type == "Opinions":
        return (
            "published_opinion",
            "source_type_filter",
            "available" if pdf_url else "not_linked",
        )
    if selected_type == "Memorandums":
        return (
            "memorandum_opinion_and_judgment_index",
            "source_type_filter",
            "not_published_by_court",
        )
    if pdf_url:
        return (
            "published_opinion",
            "official_pdf_link",
            "available",
        )
    return (
        "moj_or_unclassified_index_entry",
        "all_filter_without_type_field",
        "not_linked",
    )


def _normalize_row(
    cells: list[Any],
    *,
    selected_type: str,
    source_url: str,
    page_number: int,
    schema_fingerprint: str,
) -> dict[str, Any]:
    if len(cells) != len(EXPECTED_HEADERS):
        raise DCOpinionsSourceChangedError(
            "row_width_changed",
            "D.C. opinions row does not contain five expected columns",
            details={"observed_columns": len(cells)},
        )
    appeal_number = _text(cells[0].get_text(" ", strip=True))
    caption = _text(cells[1].get_text(" ", strip=True))
    raw_date = _text(cells[2].get_text(" ", strip=True))
    if appeal_number is None or caption is None or raw_date is None:
        raise DCOpinionsSourceChangedError(
            "required_field_missing",
            "D.C. opinions row lacks appeal number, caption, or date",
        )
    disposition = _text(cells[3].get_text(" ", strip=True))
    judge = _text(cells[4].get_text(" ", strip=True))
    link = cells[0].find("a", href=True)
    pdf_url = _official_pdf_url(link["href"]) if link is not None else None
    decision_date = _parse_source_date(raw_date)
    appeal_numbers = _APPEAL_RE.findall(appeal_number.upper())
    if not appeal_numbers:
        appeal_numbers = [appeal_number]
    publication_kind, kind_basis, full_text_status = _record_type(
        selected_type,
        pdf_url=pdf_url,
    )
    identity_payload = {
        "appeal_number": appeal_number,
        "caption": caption,
        "decision_date": decision_date,
        "disposition": disposition,
        "judge": judge,
        "pdf_url": pdf_url,
    }
    native_entry_id = hashlib.sha256(
        canonical_json(identity_payload).encode("utf-8")
    ).hexdigest()[:24]
    case_ref = canonical_court_ref(
        SOURCE_ID,
        COURT_ID,
        appeal_number,
    )
    canonical_ref = canonical_court_ref(
        SOURCE_ID,
        COURT_ID,
        appeal_number,
        record_kind="appellate_disposition",
        native_id=native_entry_id,
    )
    document = None
    if pdf_url is not None:
        document = {
            "record_kind": "document_artifact",
            "native_document_id": native_entry_id,
            "document_type": "appellate_opinion",
            "filed_date": decision_date,
            "source_url": pdf_url,
            "mime_type": "application/pdf",
            "access_state": "public",
        }
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "case_canonical_ref": case_ref,
        "source_id": SOURCE_ID,
        "record_kind": "appellate_disposition",
        "native_entry_id": native_entry_id,
        "raw_case_number": appeal_number,
        "display_case_number": appeal_number,
        "appeal_numbers": appeal_numbers,
        "caption": caption,
        "decision_date": decision_date,
        "source_date_raw": raw_date,
        "disposition": disposition,
        "judge": judge,
        "publication_kind": publication_kind,
        "publication_kind_basis": kind_basis,
        "full_text_status": full_text_status,
        "pdf_url": pdf_url,
        "document": document,
        "source_url": pdf_url or source_url,
        "index_url": source_url,
        "court": {
            "court_id": COURT_ID,
            "name": "District of Columbia Court of Appeals",
            "state_code": STATE_CODE,
            "court_level": "appellate",
            "official_url": f"{BASE_URL}/court-of-appeals",
            "case_search_url": CASE_SEARCH_PAGE,
        },
        "source_scope": {
            "appellate_disposition_index": True,
            "complete_case_docket": False,
            "underlying_party_filings": False,
        },
        "provenance": {
            "source_id": SOURCE_ID,
            "source_url": source_url,
            "native_page": page_number,
            "native_type_filter": selected_type,
            "response_schema_fingerprint": schema_fingerprint,
        },
    }


def parse_page(
    html_text: str,
    *,
    source_url: str,
    requested_page: int,
    selected_type: str,
) -> DCOpinionsPage:
    """Parse one official HTML page and validate its table/pager shape."""

    soup = BeautifulSoup(html_text, "html.parser")
    view = soup.select_one(
        ".view-opinions-and-memorandum-of-judgments"
    )
    if view is None:
        raise DCOpinionsSourceChangedError(
            "opinions_view_missing",
            "D.C. Courts page lacks the opinions and MOJ view",
        )
    table = view.find("table")
    empty = view.select_one(".empty-response")
    if table is None:
        if empty is not None:
            return DCOpinionsPage(
                records=(),
                page_number=requested_page,
                total_items=0,
                total_pages=0,
                next_page=None,
                source_url=source_url,
                schema_fingerprint=hashlib.sha256(
                    b"dccourts-opinions-empty-v1"
                ).hexdigest(),
            )
        raise DCOpinionsSourceChangedError(
            "opinions_table_missing",
            "D.C. Courts opinions view lacks both a table and empty state",
        )
    headers = tuple(
        _text(cell.get_text(" ", strip=True)) or ""
        for cell in table.select("thead th")
    )
    if headers != EXPECTED_HEADERS:
        raise DCOpinionsSourceChangedError(
            "table_headers_changed",
            "D.C. Courts opinions table headers changed",
            details={
                "expected": list(EXPECTED_HEADERS),
                "observed": list(headers),
            },
        )
    schema_fingerprint = hashlib.sha256(
        canonical_json(
            {
                "headers": headers,
                "table_classes": sorted(table.get("class", [])),
                "view_classes": sorted(view.get("class", [])),
            }
        ).encode("utf-8")
    ).hexdigest()
    rows = table.select("tbody tr")
    records = tuple(
        _normalize_row(
            row.find_all("td", recursive=False),
            selected_type=selected_type,
            source_url=source_url,
            page_number=requested_page,
            schema_fingerprint=schema_fingerprint,
        )
        for row in rows
    )
    total_node = view.select_one(".pagination-total")
    total_match = (
        _TOTAL_RE.search(total_node.get_text(" ", strip=True))
        if total_node is not None
        else None
    )
    total_items = (
        int(total_match.group(1).replace(",", ""))
        if total_match is not None
        else len(records)
    )
    next_link = view.select_one(".pager__item--next a[href]")
    next_page = (
        _page_from_url(str(next_link["href"]))
        if next_link is not None
        else None
    )
    last_link = view.select_one(".pager__item--last a[href]")
    last_page = (
        _page_from_url(str(last_link["href"]))
        if last_link is not None
        else None
    )
    if last_page is not None:
        total_pages = last_page + 1
    elif total_items:
        total_pages = max(
            requested_page + 1,
            math.ceil(total_items / max(1, len(records))),
        )
    else:
        total_pages = 0
    if next_page is not None and next_page <= requested_page:
        raise DCOpinionsSourceChangedError(
            "pagination_did_not_advance",
            "D.C. Courts next-page link did not advance",
            details={
                "requested_page": requested_page,
                "next_page": next_page,
            },
        )
    return DCOpinionsPage(
        records=records,
        page_number=requested_page,
        total_items=total_items,
        total_pages=total_pages,
        next_page=next_page,
        source_url=source_url,
        schema_fingerprint=schema_fingerprint,
    )


class DCOpinionsClient:
    """Paced, retrying client for the official HTML index and PDFs."""

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
        params: Mapping[str, str | int] | None = None,
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
                    raise DCOpinionsError(
                        "transport_error",
                        f"D.C. Courts request failed: {error}",
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
                raise DCOpinionsError(
                    "source_rate_limited",
                    "D.C. Courts rate-limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="http",
                    retryable=True,
                    details={"url": url, "http_status": status_code},
                )
            if status_code != 200:
                raise DCOpinionsError(
                    "source_http_error",
                    f"D.C. Courts returned HTTP {status_code}",
                    category="http",
                    retryable=status_code >= 500,
                    details={"url": url, "http_status": status_code},
                )
            return response
        raise AssertionError("retry loop exhausted")

    def fetch_page(
        self,
        selection: Mapping[str, str],
        *,
        page_number: int,
    ) -> DCOpinionsPage:
        params: dict[str, str | int] = {
            key: value for key, value in selection.items() if value
        }
        if page_number:
            params["page"] = page_number
        response = self._get(INDEX_URL, params=params)
        text = str(response.text)
        lowered = text.lower()
        if any(marker in lowered for marker in _CHALLENGE_MARKERS):
            raise DCOpinionsError(
                "source_access_challenge",
                "D.C. Courts returned a browser verification page",
                status=ResultStatus.HUMAN_REQUIRED,
                category="source_access",
                retryable=True,
                details={"url": INDEX_URL},
            )
        final_url = str(getattr(response, "url", INDEX_URL))
        parsed = urlparse(final_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "www.dccourts.gov"
            or parsed.path != INDEX_PATH
        ):
            raise DCOpinionsSourceChangedError(
                "unexpected_redirect",
                "D.C. Courts redirected the opinions query outside its index",
                details={"url": final_url},
            )
        return parse_page(
            text,
            source_url=final_url,
            requested_page=page_number,
            selected_type=selection.get("type", "All"),
        )

    def fetch_all(
        self,
        selection: Mapping[str, str],
        *,
        start_page: int = 0,
    ) -> DCOpinionsCollection:
        pages: list[DCOpinionsPage] = []
        page_number = start_page
        seen: set[int] = set()
        incomplete_error: DCOpinionsError | None = None
        while page_number not in seen:
            seen.add(page_number)
            try:
                page = self.fetch_page(
                    selection,
                    page_number=page_number,
                )
            except DCOpinionsError as error:
                if not pages:
                    raise
                incomplete_error = error
                break
            pages.append(page)
            if page.next_page is None:
                break
            page_number = page.next_page
        if not pages:
            raise AssertionError("fetch_all returned without a page or error")
        first = pages[0]
        return DCOpinionsCollection(
            records=tuple(
                record for page in pages for record in page.records
            ),
            pages_fetched=len(pages),
            total_items=first.total_items,
            total_pages=first.total_pages,
            source_urls=tuple(page.source_url for page in pages),
            schema_fingerprints=tuple(
                page.schema_fingerprint for page in pages
            ),
            incomplete_error=incomplete_error,
        )

    def fetch_pdf(self, source_url: str) -> DCOpinionPDF:
        safe_url = _official_pdf_url(source_url)
        response = self._get(safe_url)
        final_url = _official_pdf_url(
            str(getattr(response, "url", safe_url))
        )
        content = bytes(response.content)
        media_type = str(
            getattr(response, "headers", {}).get(
                "Content-Type",
                "application/pdf",
            )
        ).split(";", 1)[0].strip().lower()
        if not content.startswith(b"%PDF-"):
            raise DCOpinionsSourceChangedError(
                "pdf_signature_missing",
                "D.C. Courts opinion download is not a PDF",
                details={
                    "url": final_url,
                    "content_type": media_type,
                    "size": len(content),
                },
            )
        return DCOpinionPDF(
            source_url=final_url,
            content=content,
            media_type=media_type,
            sha256=hashlib.sha256(content).hexdigest(),
        )

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()


def _selection(args: argparse.Namespace) -> dict[str, str]:
    query_text = _text(getattr(args, "query", None))
    if query_text is not None and len(query_text) > 128:
        raise DCOpinionsSelectionError(
            "query_too_long",
            "D.C. Courts search text cannot exceed 128 characters",
            details={"length": len(query_text), "maximum": 128},
        )
    exact_date = getattr(args, "date", None)
    date_from = getattr(args, "date_from", None)
    date_to = getattr(args, "date_to", None)
    if exact_date and (date_from or date_to):
        raise DCOpinionsSelectionError(
            "date_selectors_conflict",
            "--date cannot be combined with --date-from or --date-to",
        )
    if bool(date_from) != bool(date_to):
        raise DCOpinionsSelectionError(
            "incomplete_date_range",
            "--date-from and --date-to must be supplied together",
        )
    native_start = ""
    native_end = ""
    if exact_date:
        _iso, native_start = _iso_and_native_date(exact_date, "--date")
    elif date_from and date_to:
        start_iso, native_start = _iso_and_native_date(
            date_from,
            "--date-from",
        )
        end_iso, native_end = _iso_and_native_date(
            date_to,
            "--date-to",
        )
        if start_iso > end_iso:
            raise DCOpinionsSelectionError(
                "invalid_date_range",
                "--date-from must not be later than --date-to",
            )
    return {
        "search": query_text or "",
        "date": native_start,
        "date_range": native_end,
        "type": NATIVE_TYPES[getattr(args, "type", "all")],
        "order": NATIVE_ORDERS[getattr(args, "order", "date")],
        "sort": getattr(args, "sort", "desc"),
    }


def _query(
    args: argparse.Namespace,
    *,
    selection: Mapping[str, Any],
) -> PublicRecordsQuery:
    operation = args.command
    parameters = dict(selection)
    if operation == "list":
        parameters["page"] = args.page
        parameters["all_pages"] = args.all_pages
    elif operation == "download":
        parameters["destination"] = str(args.destination)
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            cursor=(
                f"page:{args.page}"
                if operation == "list" and args.page
                else None
            ),
        ),
    )


def _failure(
    query: PublicRecordsQuery,
    error: DCOpinionsError,
    *,
    records: tuple[Mapping[str, Any], ...] = (),
    next_cursor: str | None = None,
) -> PublicRecordsResult:
    status = error.status
    if records and status not in {
        ResultStatus.PARTIAL,
        ResultStatus.SOURCE_CHANGED,
    }:
        status = ResultStatus.PARTIAL
    return PublicRecordsResult.failure(
        query,
        status,
        [error.to_contract_error()],
        records=records,
        next_cursor=next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: DCOpinionsClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    own_client = client is None
    source_client = client or DCOpinionsClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )
    result: PublicRecordsResult
    try:
        if args.command == "download":
            safe_url = _official_pdf_url(args.url)
            query = _query(
                args,
                selection={"url": safe_url},
            )
            pdf = source_client.fetch_pdf(safe_url)
            args.destination.parent.mkdir(parents=True, exist_ok=True)
            args.destination.write_bytes(pdf.content)
            record = {
                "canonical_ref": (
                    f"DCCOURTS-PDF:{pdf.sha256}"
                ),
                "source_id": SOURCE_ID,
                "record_kind": "document_artifact",
                "document_type": "appellate_opinion",
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
        else:
            selection = (
                {
                    "search": PROBE_APPEAL_NUMBER,
                    "date": "",
                    "date_range": "",
                    "type": "Opinions",
                    "order": "field_date",
                    "sort": "desc",
                }
                if args.command == "probe"
                else _selection(args)
            )
            query = _query(args, selection=selection)
            if args.command == "probe":
                page = source_client.fetch_page(
                    selection,
                    page_number=0,
                )
                matching = [
                    record
                    for record in page.records
                    if PROBE_APPEAL_NUMBER
                    in record.get("appeal_numbers", ())
                ]
                if (
                    not matching
                    or matching[0].get("caption") != PROBE_CAPTION
                    or not matching[0].get("pdf_url")
                ):
                    raise DCOpinionsSourceChangedError(
                        "probe_sentinel_changed",
                        "D.C. Courts opinion sentinel did not match",
                        details={
                            "appeal_number": PROBE_APPEAL_NUMBER,
                            "records_returned": len(page.records),
                        },
                    )
                pdf = source_client.fetch_pdf(matching[0]["pdf_url"])
                probe_record = {
                    **matching[0],
                    "probe": {
                        "page_total_items": page.total_items,
                        "page_total_pages": page.total_pages,
                        "pdf_sha256": pdf.sha256,
                        "pdf_size_bytes": len(pdf.content),
                        "pdf_media_type": pdf.media_type,
                    },
                }
                result = PublicRecordsResult.success(
                    query,
                    [probe_record],
                    raw_artifact_refs=[
                        page.source_url,
                        pdf.source_url,
                    ],
                    warnings=SOURCE_WARNINGS,
                )
            elif args.all_pages:
                collection = source_client.fetch_all(
                    selection,
                    start_page=args.page,
                )
                if collection.incomplete_error is not None:
                    result = _failure(
                        query,
                        collection.incomplete_error,
                        records=collection.records,
                    )
                else:
                    result = PublicRecordsResult.success(
                        query,
                        collection.records,
                        raw_artifact_refs=collection.source_urls,
                        warnings=SOURCE_WARNINGS,
                    )
            else:
                page = source_client.fetch_page(
                    selection,
                    page_number=args.page,
                )
                result = PublicRecordsResult.success(
                    query,
                    page.records,
                    next_cursor=(
                        f"page:{page.next_page}"
                        if page.next_page is not None
                        else None
                    ),
                    raw_artifact_refs=[page.source_url],
                    warnings=SOURCE_WARNINGS,
                )
    except DCOpinionsError as error:
        selection = (
            {"url": getattr(args, "url", "")}
            if args.command == "download"
            else (
                {
                    "search": PROBE_APPEAL_NUMBER,
                    "type": "Opinions",
                }
                if args.command == "probe"
                else {}
            )
        )
        query = _query(args, selection=selection)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query official D.C. Court of Appeals opinions and MOJs"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    listing = subparsers.add_parser(
        "list",
        help="Query one native page or exhaust the matching page set",
    )
    listing.add_argument("--query")
    listing.add_argument(
        "--type",
        choices=tuple(NATIVE_TYPES),
        default="all",
    )
    listing.add_argument("--date")
    listing.add_argument("--date-from")
    listing.add_argument("--date-to")
    listing.add_argument("--page", type=int, default=0)
    paging = listing.add_mutually_exclusive_group()
    paging.add_argument(
        "--all-pages",
        dest="all_pages",
        action="store_true",
        default=True,
        help="Exhaust the matching native page set (default)",
    )
    paging.add_argument(
        "--page-only",
        dest="all_pages",
        action="store_false",
        help="Return only the selected native page and a continuation cursor",
    )
    listing.add_argument(
        "--order",
        choices=tuple(NATIVE_ORDERS),
        default="date",
    )
    listing.add_argument("--sort", choices=("asc", "desc"), default="desc")
    _add_runtime_and_output(listing)

    download = subparsers.add_parser(
        "download",
        help="Download and hash one court-hosted opinion PDF",
    )
    download.add_argument("url")
    download.add_argument("destination", type=Path)
    _add_runtime_and_output(download)

    probe = subparsers.add_parser(
        "probe",
        help="Run a bounded index-and-PDF sentinel probe",
    )
    _add_runtime_and_output(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"D.C. appellate {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"D.C. appellate {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            f"  {record.get('raw_case_number') or '?'} | "
            f"{record.get('decision_date') or '?'} | "
            f"{record.get('caption') or record.get('source_url') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    args = build_parser().parse_args()
    if getattr(args, "page", 0) < 0:
        raise SystemExit("--page must not be negative")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.minimum_interval < 0:
        raise SystemExit("--minimum-interval must not be negative")
    if args.max_attempts <= 0:
        raise SystemExit("--max-attempts must be positive")
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
