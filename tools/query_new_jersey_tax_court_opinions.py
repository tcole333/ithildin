#!/usr/bin/env python3
"""Query official New Jersey Tax Court opinion indexes and documents.

The New Jersey Judiciary publishes separate Drupal indexes for published and
unpublished Tax Court opinions.  Each index entry links to an official opinion
PDF.  The Judiciary edge currently presents an Incapsula/hCaptcha challenge to
direct requests from some environments, so this adapter keeps the publisher
and retrieval transport separate: it tries the official URL first and can fall
back to Jina Reader as a rendering/extraction transport while retaining the
official index and PDF URLs as the source records.

Examples:
    uv run python tools/query_new_jersey_tax_court_opinions.py manifest --json
    uv run python tools/query_new_jersey_tax_court_opinions.py search \
        "Freehold" --collection both --limit 50 --json
    uv run python tools/query_new_jersey_tax_court_opinions.py search \
        --docket 000052-2025 --collection published --json
    uv run python tools/query_new_jersey_tax_court_opinions.py document \
        https://www.njcourts.gov/system/files/court-opinions/2026/000052-2025.pdf \
        --json
    uv run python tools/query_new_jersey_tax_court_opinions.py probe --json
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
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

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
        sha256_fingerprint,
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
        sha256_fingerprint,
    )
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-nj-tax-court-opinions"
COURT_ID = "nj-tax-court"
STATE_CODE = "NJ"
STATE_GEOID = "34"
BASE_URL = "https://www.njcourts.gov"
PUBLISHED_INDEX_URL = f"{BASE_URL}/attorneys/opinions/published-tax"
UNPUBLISHED_INDEX_URL = f"{BASE_URL}/attorneys/opinions/unpublished-tax"
SITE_SEARCH_URL = f"{BASE_URL}/search"
CASE_PUBLIC_ACCESS_URL = f"{BASE_URL}/public/get-help/tax-case-public-access"
DOCKET_REPORTS_URL = f"{BASE_URL}/courts/tax/docketed-cases"
STATE_LIBRARY_TAX_COURT_URL = (
    "https://dspace.njstatelib.org/communities/e0d4b9ee-35be-4c30-8449-8caae2251a91"
)
RUTGERS_OPINIONS_URL = "https://njlaw.rutgers.edu/collections/courts/"
COURTLISTENER_URL = "https://www.courtlistener.com/"
READER_BASE_URL = "https://r.jina.ai/"

DEFAULT_TIMEOUT = 60.0
DEFAULT_MINIMUM_INTERVAL = 3.1
DEFAULT_LIMIT = 100
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)
READER_USER_AGENT = "Ithildin-Public-Records/1.0"
OUTPUT_SCHEMA_VERSION = "new-jersey-tax-court-opinions/1.0"
CURSOR_PREFIX = "nj-tax-opinions:v1:"
CURSOR_VERSION = 1
PAGE_SIZE = 20

COLLECTIONS: Mapping[str, Mapping[str, str]] = {
    "published": {
        "url": PUBLISHED_INDEX_URL,
        "source_label": "Published Tax",
        "precedential_status": "published",
        "description": (
            "Judiciary-selected published opinions identified by the source "
            "as precedential and citable"
        ),
    },
    "unpublished": {
        "url": UNPUBLISHED_INDEX_URL,
        "source_label": "Unpublished Tax",
        "precedential_status": "unpublished",
        "description": (
            "Judiciary-posted unpublished opinions identified by the source "
            "as nonprecedential"
        ),
    },
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Published and Unpublished New Jersey Tax Court Opinions",
    source_role="official_tax_court_opinion_indexes_and_documents",
    base_url=PUBLISHED_INDEX_URL,
    dataset_id="new-jersey-tax-court-opinions",
    metadata={
        "authority": "New Jersey Judiciary",
        "collections": {
            key: {
                "url": value["url"],
                "source_label": value["source_label"],
            }
            for key, value in COLLECTIONS.items()
        },
        "native_page_size": PAGE_SIZE,
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="New Jersey",
    state_code=STATE_CODE,
)

SOURCE_WARNINGS = (
    (
        "The opinion indexes are publication collections, not complete Tax "
        "Court dockets or case jackets."
    ),
    (
        "Index occurrences are preserved separately from documents and cases. "
        "The source can list one PDF more than once with different posted dates."
    ),
    (
        "Exact docket selection is applied across every source-visible docket "
        "on the selected index pages, including consolidated dockets that the "
        "native text filter does not return."
    ),
    (
        "When the official edge challenges a direct request, Reader transport "
        "returns a rendering or text extraction of the official URL; it does "
        "not provide the original PDF bytes or their file hash."
    ),
)

_CHALLENGE_MARKERS = (
    "incapsula incident id",
    "additional security check is required",
    "njcourts security check",
    "request unsuccessful",
    "pardon our interruption",
    "interstitialtimeout",
    "showblockpage",
    "hcaptcha",
    "cf-chl-",
)
_PAGER_RE = re.compile(
    r"Showing\s+(?P<start>\d+)\s+to\s+(?P<end>\d+)\s+of\s+"
    r"(?P<total>\d+)\s+items",
    re.IGNORECASE,
)
_NUMERIC_DOCKET_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<number>\d{1,7})\s*-\s*"
    r"(?P<year>\d{2,4})(?!\d)"
)
_LETTER_DOCKET_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<prefix>[A-Z]{2,4})-"
    r"(?P<division>[A-Z])-(?P<number>\d{1,7})-"
    r"(?P<year>\d{2,4})(?!\d)",
    re.IGNORECASE,
)
_SHARED_YEAR_RE = re.compile(
    r"(?<!\d)(?P<numbers>\d{1,6}(?:\s*/\s*\d{1,6})+)"
    r"\s*-\s*(?P<year>\d{2,4})(?!\d)"
)
_READER_TITLE_RE = re.compile(r"^Title:\s*(.+)$", re.MULTILINE)
_READER_URL_RE = re.compile(r"^URL Source:\s*(.+)$", re.MULTILINE)
_READER_PUBLISHED_RE = re.compile(
    r"^Published Time:\s*(.+)$",
    re.MULTILINE,
)
_READER_PAGES_RE = re.compile(
    r"^Number of Pages:\s*(\d+)\s*$",
    re.MULTILINE,
)
_READER_CONTENT_MARKER = "Markdown Content:\n"
_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


class NewJerseyTaxOpinionsError(RuntimeError):
    """Source-specific failure with shared result semantics."""

    code = "nj_tax_opinions_error"
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

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


class SelectionError(NewJerseyTaxOpinionsError):
    code = "nj_tax_opinions_selection_invalid"
    category = "query_selection"


class CursorError(SelectionError):
    code = "nj_tax_opinions_cursor_invalid"


class TransportError(NewJerseyTaxOpinionsError):
    code = "nj_tax_opinions_transport_error"
    category = "transport"
    retryable = True


class AccessChallengeError(NewJerseyTaxOpinionsError):
    code = "nj_tax_opinions_access_challenge"
    status = ResultStatus.HUMAN_REQUIRED
    category = "source_access"


class RateLimitError(NewJerseyTaxOpinionsError):
    code = "nj_tax_opinions_rate_limited"
    status = ResultStatus.RATE_LIMITED
    category = "rate_limit"
    retryable = True


class SourceChangedError(NewJerseyTaxOpinionsError):
    code = "nj_tax_opinions_source_changed"
    status = ResultStatus.SOURCE_CHANGED
    category = "source_schema"


@dataclass(frozen=True)
class FetchedResource:
    """One official resource retrieved through a named transport."""

    official_url: str
    request_url: str
    final_url: str
    status_code: int
    content_type: str
    body: bytes
    text: str
    transport: str
    transport_attempts: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class OpinionIndexPage:
    """Parsed source page plus pagination and transport provenance."""

    collection: str
    source_url: str
    page_number: int
    total_count: int
    total_pages: int
    showing_start: int
    showing_end: int
    records: tuple[Mapping[str, Any], ...]
    schema_fingerprint: str
    page_fingerprint: str
    reported_for_date: str | None
    retrieval_transport: str
    transport_attempts: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class OpinionDocument:
    """Original PDF bytes or a relay extraction of one official PDF."""

    source_url: str
    document_id: str
    retrieval_transport: str
    transport_attempts: tuple[Mapping[str, Any], ...]
    media_type: str
    original_bytes: bytes | None
    extracted_text: str | None
    content_sha256: str
    content_hash_scope: str
    title: str | None
    published_time_raw: str | None
    page_count: int | None
    docket_components: tuple[Mapping[str, str], ...]


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _normalized_year(value: str) -> int:
    year = int(value)
    return 2000 + year if len(value) == 2 else year


def _numeric_docket(number: str, year: str) -> str:
    return f"{int(number):06d}-{_normalized_year(year):04d}"


def _letter_docket(prefix: str, division: str, number: str, year: str) -> str:
    return (
        f"{prefix.upper()}-{division.upper()}-{int(number):06d}-"
        f"{_normalized_year(year):04d}"
    )


def _extract_dockets(
    value: str,
    *,
    provenance: str,
) -> list[dict[str, str]]:
    """Extract source-visible docket labels without discarding their raw form."""

    candidates: list[tuple[int, int, str, str, str]] = []
    occupied: list[tuple[int, int]] = []
    for match in _LETTER_DOCKET_RE.finditer(value):
        candidates.append(
            (
                match.start(),
                match.end(),
                match.group(0),
                _letter_docket(
                    match.group("prefix"),
                    match.group("division"),
                    match.group("number"),
                    match.group("year"),
                ),
                "prefixed",
            )
        )
        occupied.append(match.span())
    for match in _SHARED_YEAR_RE.finditer(value):
        year = match.group("year")
        for number in re.split(r"\s*/\s*", match.group("numbers")):
            candidates.append(
                (
                    match.start(),
                    match.end(),
                    f"{number}-{year}",
                    _numeric_docket(number, year),
                    "numeric_shared_year",
                )
            )
        occupied.append(match.span())
    for match in _NUMERIC_DOCKET_RE.finditer(value):
        if any(
            start <= match.start() and match.end() <= end for start, end in occupied
        ):
            continue
        candidates.append(
            (
                match.start(),
                match.end(),
                match.group(0),
                _numeric_docket(
                    match.group("number"),
                    match.group("year"),
                ),
                "numeric",
            )
        )
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for _, _, raw, normalized, docket_type in sorted(candidates):
        if normalized in seen:
            continue
        seen.add(normalized)
        records.append(
            {
                "raw": _clean_text(raw),
                "normalized": normalized,
                "type": docket_type,
                "provenance": provenance,
            }
        )
    return records


def _summary_dockets(value: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"\bDocket(?:\s+Numbers?|\s+Nos?\.?|\s+No\.?)\s*:?\s*",
        value,
        re.IGNORECASE,
    ):
        window = value[match.end() : match.end() + 500]
        stop = re.search(
            r"\b(?:opinion\s+by|decided|for\s+plaintiff|for\s+defendant|"
            r"attorneys?)\b",
            window,
            re.IGNORECASE,
        )
        if stop is not None:
            window = window[: stop.start()]
        for record in _extract_dockets(window, provenance="summary"):
            normalized = record["normalized"]
            if normalized in seen:
                continue
            seen.add(normalized)
            records.append(record)
    return records


def _all_index_dockets(
    docket_label: str,
    summary_text: str | None,
) -> list[dict[str, str]]:
    records = _extract_dockets(docket_label, provenance="index_label")
    seen = {record["normalized"] for record in records}
    if summary_text:
        for record in _summary_dockets(summary_text):
            if record["normalized"] in seen:
                continue
            seen.add(record["normalized"])
            records.append(record)
    return records


def _parse_posted_date(value: str) -> str:
    match = re.fullmatch(
        r"(?P<month>[A-Za-z]+)\.?\s+(?P<day>\d{1,2}),\s+"
        r"(?P<year>\d{4})",
        _clean_text(value),
    )
    if match is None:
        raise SourceChangedError(
            "Tax Court opinion index contains an unrecognized posted date",
            details={"posted_date_raw": value},
        )
    month = _MONTHS.get(match.group("month").casefold())
    if month is None:
        raise SourceChangedError(
            "Tax Court opinion index contains an unknown month",
            details={"posted_date_raw": value},
        )
    try:
        return date(
            int(match.group("year")),
            month,
            int(match.group("day")),
        ).isoformat()
    except ValueError as error:
        raise SourceChangedError(
            "Tax Court opinion index contains an invalid posted date",
            details={"posted_date_raw": value},
        ) from error


def _official_document_url(value: str) -> str:
    candidate = urljoin(BASE_URL, _clean_text(value))
    parsed = urlsplit(candidate)
    if parsed.scheme != "https" or parsed.netloc.casefold() not in {
        "www.njcourts.gov",
        "njcourts.gov",
    }:
        raise SelectionError(
            "Opinion document URL must use the official New Jersey Courts host",
            details={"url": value},
        )
    path = parsed.path.casefold()
    if not (
        path.startswith("/system/files/court-opinions/")
        or path.startswith("/attorneys/assets/opinions/tax/")
    ):
        raise SelectionError(
            "URL is outside the official Tax Court opinion document paths",
            details={"url": value},
        )
    return candidate


def _document_id(source_url: str) -> str:
    parsed = urlsplit(source_url)
    return f"njcourts:{parsed.path.lstrip('/')}"


def _page_number_from_url(source_url: str) -> int:
    page_values = parse_qs(urlsplit(source_url).query).get("page", ["0"])
    try:
        return max(0, int(page_values[0]))
    except (TypeError, ValueError):
        return 0


def _reported_for_date(view: Tag) -> str | None:
    heading = view.select_one(".view-header h2")
    if heading is None:
        return None
    text = _clean_text(heading.get_text(" ", strip=True))
    match = re.search(r"reported\s+for\s+(.+)$", text, re.IGNORECASE)
    return _clean_text(match.group(1)) if match else None


def _native_summary_id(article: Tag) -> str | None:
    for node in article.find_all(id=True):
        match = re.fullmatch(
            r"op-(\d+)-summary-arg-modal",
            str(node.get("id")),
        )
        if match:
            return match.group(1)
    return None


def _index_occurrence_identity(
    *,
    collection: str,
    native_summary_id: str | None,
    title: str,
    docket_label: str,
    posted_date: str,
    document_url: str,
    summary_text: str | None,
    duplicate_ordinal: int,
) -> tuple[str, str]:
    payload = (
        {
            "collection": collection,
            "native_summary_id": native_summary_id,
            "posted_date": posted_date,
            "document_url": document_url,
        }
        if native_summary_id is not None
        else {
            "collection": collection,
            "title": title,
            "docket_label": docket_label,
            "posted_date": posted_date,
            "document_url": document_url,
            "summary_text": summary_text,
        }
    )
    digest = sha256_fingerprint(payload)
    suffix = f":{duplicate_ordinal}" if duplicate_ordinal > 1 else ""
    return f"nj-tax-opinion-index:{collection}:{digest[:24]}{suffix}", digest


def parse_index_page(
    html: str,
    *,
    collection: str,
    source_url: str,
    retrieval_transport: str = "fixture",
    transport_attempts: Sequence[Mapping[str, Any]] = (),
) -> OpinionIndexPage:
    """Parse and validate one rendered official opinion-index page."""

    config = COLLECTIONS.get(collection)
    if config is None:
        raise SelectionError(
            "Unknown Tax Court opinion collection",
            details={"collection": collection},
        )
    soup = BeautifulSoup(html, "html.parser")
    view = soup.select_one(".view-court-opinions")
    if view is None:
        raise SourceChangedError(
            "Official page lacks the Tax Court opinion view",
            details={"collection": collection, "source_url": source_url},
        )
    form = view.select_one("form.views-exposed-form")
    if form is None:
        raise SourceChangedError(
            "Official opinion view lacks its search form",
            details={"collection": collection},
        )
    form_fields = {
        str(node.get("name")) for node in form.select("input[name]") if node.get("name")
    }
    expected_form_fields = {"start", "end", "search"}
    if not expected_form_fields.issubset(form_fields):
        raise SourceChangedError(
            "Official opinion search form fields changed",
            details={
                "collection": collection,
                "expected": sorted(expected_form_fields),
                "observed": sorted(form_fields),
            },
        )

    raw_records: list[dict[str, Any]] = []
    identity_counts: dict[str, int] = {}
    articles = view.select("article.w-100")
    for item_index, article in enumerate(articles, 1):
        link = article.select_one(".card-title a[href]")
        badges = article.select(".badge")
        posted_node = article.select_one(".small.text-muted")
        if link is None or len(badges) < 2 or posted_node is None:
            raise SourceChangedError(
                "Official opinion card lacks a title, docket, label, or date",
                details={
                    "collection": collection,
                    "item_index": item_index,
                },
            )
        title = _clean_text(link.get_text(" ", strip=True))
        docket_label = _clean_text(badges[0].get_text(" ", strip=True))
        source_label = _clean_text(badges[1].get_text(" ", strip=True))
        if source_label.casefold() != config["source_label"].casefold():
            raise SourceChangedError(
                "Opinion card collection label does not match its index",
                details={
                    "collection": collection,
                    "expected": config["source_label"],
                    "observed": source_label,
                },
            )
        posted_date_raw = _clean_text(posted_node.get_text(" ", strip=True))
        posted_date = _parse_posted_date(posted_date_raw)
        document_url = _official_document_url(str(link["href"]))
        summary_node = article.select_one(".modal-body")
        summary_text = (
            _clean_text(summary_node.get_text(" ", strip=True))
            if summary_node is not None
            else None
        )
        native_summary_id = _native_summary_id(article)
        docket_components = _all_index_dockets(
            docket_label,
            summary_text,
        )
        normalized_dockets = [record["normalized"] for record in docket_components]
        native_document_id = _document_id(document_url)
        identity_payload = {
            "collection": collection,
            "title": title,
            "docket_label": docket_label,
            "posted_date": posted_date,
            "document_url": document_url,
            "summary_text": summary_text,
        }
        identity_digest = sha256_fingerprint(identity_payload)
        identity_counts[identity_digest] = identity_counts.get(identity_digest, 0) + 1
        occurrence_id, occurrence_digest = _index_occurrence_identity(
            collection=collection,
            native_summary_id=native_summary_id,
            title=title,
            docket_label=docket_label,
            posted_date=posted_date,
            document_url=document_url,
            summary_text=summary_text,
            duplicate_ordinal=identity_counts[identity_digest],
        )
        primary_case_number = (
            normalized_dockets[0]
            if normalized_dockets
            else Path(urlsplit(document_url).path).stem
        )
        case_refs = [
            canonical_court_ref(
                SOURCE_ID,
                COURT_ID,
                docket_number,
            )
            for docket_number in normalized_dockets
        ]
        canonical_ref = canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            primary_case_number,
            "opinion-index-entry",
            occurrence_digest[:24],
        )
        raw_records.append(
            {
                "record_type": "tax_court_opinion_index_entry",
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "source_id": SOURCE_ID,
                "collection": collection,
                "publication_status": config["precedential_status"],
                "title": title,
                "docket_label_raw": docket_label,
                "docket_components": docket_components,
                "docket_numbers": normalized_dockets,
                "case_canonical_refs": case_refs,
                "posted_date": posted_date,
                "posted_date_raw": posted_date_raw,
                "index_entry": {
                    "occurrence_id": occurrence_id,
                    "identity_method": (
                        "native_summary_node_plus_occurrence_fields"
                        if native_summary_id
                        else "occurrence_field_fingerprint"
                    ),
                    "native_summary_node_id": native_summary_id,
                    "duplicate_ordinal_for_identical_visible_fields": (
                        identity_counts[identity_digest]
                    ),
                },
                "summary": {
                    "available_on_index": summary_text is not None,
                    "text": summary_text,
                },
                "document": {
                    "document_id": native_document_id,
                    "identity_method": "official_url_path",
                    "source_url": document_url,
                    "media_type": "application/pdf",
                    "access_observation": {
                        "observed_at": "2026-07-30",
                        "direct": "edge_challenge",
                        "reader_extraction": "available",
                    },
                },
                "court": {
                    "court_id": COURT_ID,
                    "name": "Tax Court of New Jersey",
                    "state_code": STATE_CODE,
                    "level": "trial",
                },
                "join_keys": {
                    "docket_numbers": normalized_dockets,
                    "title": title,
                    "posted_date": posted_date,
                    "official_document_path": urlsplit(document_url).path,
                },
                "source_scope": {
                    "official_index_entry": True,
                    "official_opinion_document": True,
                    "complete_case_docket": False,
                    "complete_filing_set": False,
                },
                "source_url": document_url,
                "index_url": source_url,
                "provenance": {
                    "index_url": source_url,
                    "native_page_number": _page_number_from_url(source_url),
                    "page_item_index": item_index,
                    "retrieval_transport": retrieval_transport,
                    "transport_attempts": list(transport_attempts),
                },
            }
        )

    pager = view.select_one(".pager-summary")
    pager_match = (
        _PAGER_RE.search(_clean_text(pager.get_text(" ", strip=True)))
        if pager is not None
        else None
    )
    if pager_match is not None:
        showing_start = int(pager_match.group("start"))
        showing_end = int(pager_match.group("end"))
        total_count = int(pager_match.group("total"))
        if showing_end - showing_start + 1 != len(raw_records):
            raise SourceChangedError(
                "Opinion pager count does not match visible cards",
                details={
                    "collection": collection,
                    "showing_start": showing_start,
                    "showing_end": showing_end,
                    "visible_cards": len(raw_records),
                },
            )
    else:
        total_count = len(raw_records)
        showing_start = 1 if raw_records else 0
        showing_end = len(raw_records)
    page_number = _page_number_from_url(source_url)
    total_pages = math.ceil(total_count / PAGE_SIZE) if total_count else 0
    schema_fingerprint = sha256_fingerprint(
        {
            "collection": collection,
            "form_fields": sorted(expected_form_fields),
            "card_selector": "article.w-100",
            "title_selector": ".card-title a[href]",
            "badge_selector": ".badge",
            "posted_date_selector": ".small.text-muted",
            "summary_selector": ".modal-body",
            "pager_pattern": _PAGER_RE.pattern,
            "record_schema": OUTPUT_SCHEMA_VERSION,
        }
    )
    page_fingerprint = sha256_fingerprint(
        {
            "collection": collection,
            "page_number": page_number,
            "total_count": total_count,
            "occurrence_ids": [
                record["index_entry"]["occurrence_id"] for record in raw_records
            ],
        }
    )
    for item_index, record in enumerate(raw_records):
        record["provenance"]["global_source_position"] = (
            showing_start + item_index if showing_start else item_index + 1
        )
        record["provenance"]["schema_fingerprint"] = schema_fingerprint
        record["provenance"]["page_fingerprint"] = page_fingerprint
    return OpinionIndexPage(
        collection=collection,
        source_url=source_url,
        page_number=page_number,
        total_count=total_count,
        total_pages=total_pages,
        showing_start=showing_start,
        showing_end=showing_end,
        records=tuple(raw_records),
        schema_fingerprint=schema_fingerprint,
        page_fingerprint=page_fingerprint,
        reported_for_date=_reported_for_date(view),
        retrieval_transport=retrieval_transport,
        transport_attempts=tuple(dict(item) for item in transport_attempts),
    )


def parse_reader_document(
    text: str,
    *,
    source_url: str,
    transport_attempts: Sequence[Mapping[str, Any]] = (),
) -> OpinionDocument:
    """Parse Jina Reader's text extraction for one official opinion PDF."""

    safe_url = _official_document_url(source_url)
    url_match = _READER_URL_RE.search(text)
    if url_match is None:
        raise SourceChangedError(
            "Reader extraction lacks its official source URL",
            details={"source_url": safe_url},
        )
    extracted_source_url = _official_document_url(_clean_text(url_match.group(1)))
    if urlsplit(extracted_source_url).path != urlsplit(safe_url).path:
        raise SourceChangedError(
            "Reader extraction identifies a different official document",
            details={
                "requested_url": safe_url,
                "extracted_url": extracted_source_url,
            },
        )
    marker_index = text.find(_READER_CONTENT_MARKER)
    if marker_index < 0:
        raise SourceChangedError(
            "Reader extraction lacks its Markdown content section",
            details={"source_url": safe_url},
        )
    content = text[marker_index + len(_READER_CONTENT_MARKER) :].strip()
    if not content:
        raise SourceChangedError(
            "Reader returned an empty opinion extraction",
            details={"source_url": safe_url},
        )
    title_match = _READER_TITLE_RE.search(text)
    published_match = _READER_PUBLISHED_RE.search(text)
    pages_match = _READER_PAGES_RE.search(text)
    dockets = _summary_dockets(content[:20_000])
    return OpinionDocument(
        source_url=safe_url,
        document_id=_document_id(safe_url),
        retrieval_transport="reader_relay",
        transport_attempts=tuple(dict(item) for item in transport_attempts),
        media_type="text/markdown",
        original_bytes=None,
        extracted_text=content,
        content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        content_hash_scope="reader_extracted_text",
        title=(_clean_text(title_match.group(1)) if title_match is not None else None),
        published_time_raw=(
            _clean_text(published_match.group(1))
            if published_match is not None
            else None
        ),
        page_count=int(pages_match.group(1)) if pages_match else None,
        docket_components=tuple(dockets),
    )


class NewJerseyTaxOpinionsClient:
    """Retrying, paced client with direct-first and relay retrieval modes."""

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
        self._direct_challenge_observed = False

    def _get_one(
        self,
        official_url: str,
        *,
        transport: str,
        reader_format: str,
    ) -> FetchedResource:
        if transport not in {"direct", "reader"}:
            raise ValueError("transport must be direct or reader")
        request_url = (
            official_url
            if transport == "direct"
            else f"{READER_BASE_URL}{official_url}"
        )
        if transport == "direct":
            headers = {
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept-Language": "en-US,en;q=0.8",
                "Accept": (
                    "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.5"
                ),
            }
        else:
            headers = {
                "User-Agent": READER_USER_AGENT,
                "Accept": "text/plain,*/*;q=0.5",
            }
            headers["X-Return-Format"] = reader_format
        response: Any = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.get(
                    request_url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    headers=headers,
                )
            except (requests.RequestException, OSError) as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise TransportError(
                        f"Tax Court opinion request failed: {error}",
                        details={
                            "official_url": official_url,
                            "request_url": request_url,
                            "transport": transport,
                        },
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            status_code = int(getattr(response, "status_code", 0))
            if (
                status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            break
        if response is None:
            raise AssertionError("request loop produced no response")
        status_code = int(getattr(response, "status_code", 0))
        text = str(getattr(response, "text", ""))
        content_value = getattr(response, "content", None)
        body = (
            bytes(content_value)
            if isinstance(content_value, (bytes, bytearray))
            else text.encode("utf-8")
        )
        lowered = (
            text.casefold()
            if text
            else body[:100_000].decode("utf-8", errors="ignore").casefold()
        )
        if status_code == 429:
            raise RateLimitError(
                "Opinion retrieval transport returned HTTP 429",
                details={
                    "official_url": official_url,
                    "request_url": request_url,
                    "transport": transport,
                    "http_status": status_code,
                },
            )
        if transport == "direct" and (
            status_code in {401, 403}
            or any(marker in lowered for marker in _CHALLENGE_MARKERS)
        ):
            raise AccessChallengeError(
                "New Jersey Courts returned its browser security challenge",
                details={
                    "official_url": official_url,
                    "request_url": request_url,
                    "transport": "official_direct",
                    "http_status": status_code,
                    "operation_state": "edge_challenge",
                },
            )
        if status_code < 200 or status_code >= 300:
            raise TransportError(
                f"Opinion retrieval transport returned HTTP {status_code}",
                details={
                    "official_url": official_url,
                    "request_url": request_url,
                    "transport": transport,
                    "http_status": status_code,
                },
            )
        return FetchedResource(
            official_url=official_url,
            request_url=request_url,
            final_url=str(getattr(response, "url", request_url)),
            status_code=status_code,
            content_type=str(getattr(response, "headers", {}).get("Content-Type", ""))
            .split(";", 1)[0]
            .casefold(),
            body=body,
            text=text,
            transport=("official_direct" if transport == "direct" else "reader_relay"),
            transport_attempts=(),
        )

    def _fetch(
        self,
        official_url: str,
        *,
        transport: str,
        reader_format: str,
    ) -> FetchedResource:
        if transport not in {"auto", "direct", "reader"}:
            raise SelectionError(
                "Transport must be auto, direct, or reader",
                details={"transport": transport},
            )
        attempts: list[dict[str, Any]] = []
        if transport in {"auto", "direct"}:
            if transport == "auto" and self._direct_challenge_observed:
                attempts.append(
                    {
                        "transport": "official_direct",
                        "operation_state": (
                            "edge_challenge_observed_earlier_in_client_session"
                        ),
                        "request_made": False,
                    }
                )
            else:
                try:
                    result = self._get_one(
                        official_url,
                        transport="direct",
                        reader_format=reader_format,
                    )
                    attempts.append(
                        {
                            "transport": "official_direct",
                            "operation_state": "available",
                            "http_status": result.status_code,
                            "request_made": True,
                        }
                    )
                    return FetchedResource(
                        **{
                            **result.__dict__,
                            "transport_attempts": tuple(attempts),
                        }
                    )
                except AccessChallengeError as error:
                    self._direct_challenge_observed = True
                    attempts.append(
                        {
                            "transport": "official_direct",
                            "operation_state": "edge_challenge",
                            "http_status": error.details.get("http_status"),
                            "request_made": True,
                        }
                    )
                    if transport == "direct":
                        raise
        if transport in {"auto", "reader"}:
            result = self._get_one(
                official_url,
                transport="reader",
                reader_format=reader_format,
            )
            attempts.append(
                {
                    "transport": "reader_relay",
                    "operation_state": "available",
                    "http_status": result.status_code,
                    "request_made": True,
                    "returned_format": reader_format,
                }
            )
            return FetchedResource(
                **{
                    **result.__dict__,
                    "transport_attempts": tuple(attempts),
                }
            )
        raise AssertionError("transport selection exhausted")

    def fetch_index_page(
        self,
        collection: str,
        *,
        page: int = 0,
        search: str | None = None,
        start: str | None = None,
        end: str | None = None,
        transport: str = "auto",
    ) -> OpinionIndexPage:
        source_url = build_index_url(
            collection,
            page=page,
            search=search,
            start=start,
            end=end,
        )
        resource = self._fetch(
            source_url,
            transport=transport,
            reader_format="html",
        )
        text = resource.text or resource.body.decode(
            "utf-8",
            errors="replace",
        )
        if "<html" not in text.casefold():
            raise SourceChangedError(
                "Opinion index transport did not return rendered HTML",
                details={
                    "source_url": source_url,
                    "transport": resource.transport,
                    "content_type": resource.content_type,
                },
            )
        return parse_index_page(
            text,
            collection=collection,
            source_url=source_url,
            retrieval_transport=resource.transport,
            transport_attempts=resource.transport_attempts,
        )

    def fetch_document(
        self,
        source_url: str,
        *,
        transport: str = "auto",
    ) -> OpinionDocument:
        safe_url = _official_document_url(source_url)
        resource = self._fetch(
            safe_url,
            transport=transport,
            reader_format="markdown",
        )
        if resource.transport == "reader_relay":
            return parse_reader_document(
                resource.text,
                source_url=safe_url,
                transport_attempts=resource.transport_attempts,
            )
        if not resource.body.startswith(b"%PDF-"):
            raise SourceChangedError(
                "Official opinion document response is not a PDF",
                details={
                    "source_url": safe_url,
                    "content_type": resource.content_type,
                    "size_bytes": len(resource.body),
                },
            )
        return OpinionDocument(
            source_url=safe_url,
            document_id=_document_id(safe_url),
            retrieval_transport="official_direct",
            transport_attempts=resource.transport_attempts,
            media_type="application/pdf",
            original_bytes=resource.body,
            extracted_text=None,
            content_sha256=hashlib.sha256(resource.body).hexdigest(),
            content_hash_scope="original_pdf_bytes",
            title=None,
            published_time_raw=None,
            page_count=None,
            docket_components=(),
        )

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()


def build_index_url(
    collection: str,
    *,
    page: int = 0,
    search: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> str:
    config = COLLECTIONS.get(collection)
    if config is None:
        raise SelectionError(
            "Unknown Tax Court opinion collection",
            details={"collection": collection},
        )
    if page < 0:
        raise SelectionError(
            "Native page must not be negative",
            details={"page": page},
        )
    parameters: list[tuple[str, str | int]] = []
    if start:
        parameters.append(("start", start))
    if end:
        parameters.append(("end", end))
    if search:
        parameters.append(("search", search))
    if page:
        parameters.append(("page", page))
    query = urlencode(parameters)
    return f"{config['url']}?{query}" if query else str(config["url"])


def _date_bound(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise SelectionError(
            f"{field_name} must be an ISO date in YYYY-MM-DD form",
            details={"value": value},
        ) from error


def _collection_sequence(value: str) -> tuple[str, ...]:
    return ("published", "unpublished") if value == "both" else (value,)


def _selection(args: argparse.Namespace) -> dict[str, Any]:
    start = _date_bound(args.after, "--after")
    end = _date_bound(args.before, "--before")
    if start and end and start > end:
        raise SelectionError("--after must not be later than --before")
    query = _clean_text(args.query) or None
    docket = _clean_text(args.docket) or None
    if query and docket:
        raise SelectionError("Use either the general query or --docket, not both")
    return {
        "collection": args.collection,
        "query": query,
        "docket": docket,
        "after": start,
        "before": end,
        "transport": args.transport,
    }


def _selection_fingerprint(selection: Mapping[str, Any]) -> str:
    cursor_selection = dict(selection)
    cursor_selection.pop("transport", None)
    return sha256_fingerprint(cursor_selection)


def _cursor_encode(
    *,
    selection_fingerprint: str,
    position: Mapping[str, int],
    snapshot: Mapping[str, Mapping[str, Any]],
    anchor: Mapping[str, Any],
) -> str:
    payload = {
        "version": CURSOR_VERSION,
        "selection": selection_fingerprint,
        "position": dict(position),
        "snapshot": {key: dict(value) for key, value in snapshot.items()},
        "anchor": dict(anchor),
    }
    encoded = base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8")).decode(
        "ascii"
    )
    return CURSOR_PREFIX + encoded.rstrip("=")


def _cursor_decode(
    value: str | None,
    *,
    selection_fingerprint: str,
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not value.startswith(CURSOR_PREFIX):
        raise CursorError("Cursor belongs to a different source")
    encoded = value[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CursorError("Cursor payload is not valid") from error
    if (
        not isinstance(payload, dict)
        or payload.get("version") != CURSOR_VERSION
        or payload.get("selection") != selection_fingerprint
        or not isinstance(payload.get("position"), dict)
        or not isinstance(payload.get("snapshot"), dict)
        or not isinstance(payload.get("anchor"), dict)
    ):
        raise CursorError("Cursor version, selection, or structure does not match")
    return payload


def _record_matches_docket(
    record: Mapping[str, Any],
    docket: str | None,
) -> bool:
    if docket is None:
        return True
    requested = _extract_dockets(docket, provenance="query")
    if requested:
        requested_values = {
            component["normalized"].casefold() for component in requested
        }
    else:
        requested_values = {_clean_text(docket).casefold()}
    record_values = {
        str(value).casefold() for value in record.get("docket_numbers", [])
    }
    record_values.add(_clean_text(record.get("docket_label_raw")).casefold())
    return bool(requested_values & record_values)


def _first_page_snapshot(
    page: OpinionIndexPage,
) -> dict[str, Any]:
    return {
        "total_count": page.total_count,
        "first_page_fingerprint": page.page_fingerprint,
    }


def _verify_snapshot(
    current: Mapping[str, Mapping[str, Any]],
    expected: Mapping[str, Mapping[str, Any]],
) -> None:
    if canonical_json(current) != canonical_json(expected):
        raise CursorError(
            "Opinion index changed after this cursor was issued",
            details={
                "expected_snapshot": expected,
                "current_snapshot": current,
            },
        )


def _query(
    args: argparse.Namespace,
    *,
    parameters: Mapping[str, Any],
) -> PublicRecordsQuery:
    requested_limit = getattr(args, "limit", None)
    if args.command == "search":
        requested_limit = (
            None
            if getattr(args, "all_pages", False)
            else requested_limit or DEFAULT_LIMIT
        )
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=getattr(args, "cursor", None),
            metadata={"adapter_schema": OUTPUT_SCHEMA_VERSION},
        ),
    )


def _search(
    args: argparse.Namespace,
    *,
    client: NewJerseyTaxOpinionsClient | Any,
    selection: Mapping[str, Any],
) -> tuple[
    tuple[Mapping[str, Any], ...],
    str | None,
    tuple[str, ...],
]:
    collections = _collection_sequence(str(selection["collection"]))
    # The source's text filter reliably finds visible titles and primary docket
    # badges, but live verification showed that it can omit consolidated
    # secondary dockets named only in an index summary.  Docket selection
    # therefore traverses the selected collection and applies the normalized
    # exact match locally; general text queries still use the native filter.
    native_search = selection.get("query")
    first_pages: dict[str, OpinionIndexPage] = {}
    raw_refs: list[str] = []
    for collection in collections:
        page = client.fetch_index_page(
            collection,
            page=0,
            search=native_search,
            start=selection.get("after"),
            end=selection.get("before"),
            transport=selection["transport"],
        )
        first_pages[collection] = page
        raw_refs.append(page.source_url)
    snapshot = {
        collection: _first_page_snapshot(first_pages[collection])
        for collection in collections
    }
    selection_fingerprint = _selection_fingerprint(selection)
    cursor_payload = _cursor_decode(
        args.cursor,
        selection_fingerprint=selection_fingerprint,
    )
    if cursor_payload is None:
        start_collection_index = 0
        start_page = 0
        start_offset = 0
    else:
        _verify_snapshot(snapshot, cursor_payload["snapshot"])
        position = cursor_payload["position"]
        try:
            start_collection_index = int(position["collection_index"])
            start_page = int(position["page"])
            start_offset = int(position["offset"])
        except (KeyError, TypeError, ValueError) as error:
            raise CursorError("Cursor position is malformed") from error
        anchor = cursor_payload["anchor"]
        try:
            anchor_collection = str(anchor["collection"])
            anchor_page_number = int(anchor["page"])
            anchor_fingerprint = str(anchor["page_fingerprint"])
        except (KeyError, TypeError, ValueError) as error:
            raise CursorError("Cursor anchor is malformed") from error
        if anchor_collection not in first_pages:
            raise CursorError("Cursor anchor collection is not selected")
        anchor_page = (
            first_pages[anchor_collection]
            if anchor_page_number == 0
            else client.fetch_index_page(
                anchor_collection,
                page=anchor_page_number,
                search=native_search,
                start=selection.get("after"),
                end=selection.get("before"),
                transport=selection["transport"],
            )
        )
        if anchor_page.source_url not in raw_refs:
            raw_refs.append(anchor_page.source_url)
        if anchor_page.page_fingerprint != anchor_fingerprint:
            raise CursorError("The cursor anchor page changed after it was issued")
    if (
        start_collection_index < 0
        or start_collection_index >= len(collections)
        or start_page < 0
        or start_offset < 0
    ):
        raise CursorError("Cursor position is outside the selected indexes")

    limit = None if args.all_pages else args.limit or DEFAULT_LIMIT
    output: list[Mapping[str, Any]] = []
    next_cursor: str | None = None
    last_page: OpinionIndexPage | None = None
    for collection_index in range(
        start_collection_index,
        len(collections),
    ):
        collection = collections[collection_index]
        first_page = first_pages[collection]
        page_number = start_page if collection_index == start_collection_index else 0
        offset = start_offset if collection_index == start_collection_index else 0
        while page_number < first_page.total_pages:
            page = (
                first_page
                if page_number == 0
                else client.fetch_index_page(
                    collection,
                    page=page_number,
                    search=native_search,
                    start=selection.get("after"),
                    end=selection.get("before"),
                    transport=selection["transport"],
                )
            )
            last_page = page
            if page.source_url not in raw_refs:
                raw_refs.append(page.source_url)
            if offset > len(page.records):
                raise CursorError("Cursor offset exceeds its source page")
            for record_index in range(offset, len(page.records)):
                record = page.records[record_index]
                if not _record_matches_docket(
                    record,
                    selection.get("docket"),
                ):
                    continue
                output.append(record)
                if limit is not None and len(output) >= limit:
                    next_collection_index = collection_index
                    next_page = page_number
                    next_offset = record_index + 1
                    if next_offset >= len(page.records):
                        next_page += 1
                        next_offset = 0
                        if next_page >= first_page.total_pages:
                            next_collection_index += 1
                            next_page = 0
                    if next_collection_index < len(collections):
                        next_cursor = _cursor_encode(
                            selection_fingerprint=selection_fingerprint,
                            position={
                                "collection_index": next_collection_index,
                                "page": next_page,
                                "offset": next_offset,
                            },
                            snapshot=snapshot,
                            anchor={
                                "collection": collection,
                                "page": page_number,
                                "page_fingerprint": page.page_fingerprint,
                            },
                        )
                    return tuple(output), next_cursor, tuple(raw_refs)
            page_number += 1
            offset = 0
        start_page = 0
        start_offset = 0
    if cursor_payload is not None and last_page is None:
        raise CursorError("Cursor points beyond the selected source records")
    return tuple(output), next_cursor, tuple(raw_refs)


def _alternative_routes() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "us-nj-courts-full-site-search",
            "name": "New Jersey Courts full-site search",
            "authority": "New Jersey Judiciary",
            "url": SITE_SEARCH_URL,
            "role": "full_text_official_opinion_and_pdf_discovery",
            "operation_state": {
                "direct_anonymous_http_observed": "edge_challenge",
                "reader_rendering_observed": "available",
            },
            "adds": [
                "PDF full-text snippets",
                "individual opinion aliases",
                "cross-court opinions",
            ],
            "gaps": ["not a Tax Court-only complete index"],
            "join_keys": ["docket number", "case title", "official PDF URL"],
        },
        {
            "source_id": "us-nj-tax-case-public-access",
            "name": "New Jersey Tax Case Public Access",
            "authority": "New Jersey Judiciary",
            "url": CASE_PUBLIC_ACCESS_URL,
            "role": "case_jacket_and_proceeding_detail",
            "operation_state": "registration_required",
            "adds": [
                "party and docket lookup",
                "block and lot lookup",
                "case-jacket detail",
            ],
            "gaps": ["interactive registered workflow"],
            "join_keys": ["docket number", "party", "block", "lot"],
        },
        {
            "source_id": "us-nj-tax-court-property-cases",
            "name": "New Jersey Tax Court docket and judgment reports",
            "authority": "New Jersey Judiciary",
            "url": DOCKET_REPORTS_URL,
            "role": "docket_disposition_and_property_context",
            "operation_state": {
                "current_report_s3_manifest": "anonymous_public",
                "historical_browser_archive": "edge_challenge_observed_direct",
            },
            "adds": [
                "current docketed and open cases",
                "historical monthly judgments",
                "county, block, lot, assessment year, judgment date",
            ],
            "gaps": [
                "current reports omit municipality",
                "reports do not contain judicial reasoning",
            ],
            "join_keys": ["docket number", "case title", "property fields"],
        },
        {
            "source_id": "us-nj-tax-court-reports",
            "name": "New Jersey Tax Court Reports and State Library holdings",
            "authority": "New Jersey Judiciary / New Jersey State Library",
            "url": STATE_LIBRARY_TAX_COURT_URL,
            "role": "reported_precedential_opinions_and_annual_context",
            "operation_state": "library_and_reporter_access",
            "adds": [
                "reported citation",
                "published precedential archive",
                "annual significant-case summaries",
            ],
            "gaps": ["does not replace the online unpublished-opinion collection"],
            "join_keys": ["case name", "docket number", "reported citation"],
        },
        {
            "source_id": "us-nj-local-property-assessment-sources",
            "name": "County tax boards, local assessors, MOD-IV, NJGIN, and SR1A",
            "authority": (
                "New Jersey Division of Taxation and local assessment offices"
            ),
            "url": "https://www.nj.gov/treasury/taxation/lpt/statdata.shtml",
            "role": "valuation_assessment_parcel_and_transfer_context",
            "operation_state": "source_specific_public_routes",
            "adds": [
                "assessment and class",
                "municipality",
                "parcel geometry",
                "sales and transfer context",
            ],
            "gaps": [
                "not court dispositions",
                "not independent copies of opinion reasoning",
            ],
            "join_keys": [
                "municipality",
                "block",
                "lot",
                "assessment year",
            ],
        },
        {
            "source_id": "us-nj-rutgers-court-opinions",
            "name": "Rutgers New Jersey Court Opinions",
            "authority": "Rutgers Law School",
            "url": RUTGERS_OPINIONS_URL,
            "role": "separately_attributable_opinion_discovery_copy",
            "operation_state": "public_search",
            "adds": ["historical reported-opinion discovery"],
            "gaps": [
                "not the Judiciary publisher",
                "coverage is not field-level equivalent to both Tax indexes",
            ],
            "join_keys": ["case name", "citation", "decision date"],
        },
        {
            "source_id": "us-courtlistener-opinions",
            "name": "CourtListener",
            "authority": "Free Law Project",
            "url": COURTLISTENER_URL,
            "role": "separately_attributable_search_and_citation_graph",
            "operation_state": "API_token_for_integrated_search",
            "adds": ["full-text search", "citations", "related opinions"],
            "gaps": [
                "not the Judiciary publisher",
                "Tax Court coverage must be checked per opinion",
            ],
            "join_keys": ["case name", "citation", "docket number"],
        },
    ]


def source_manifest_record() -> dict[str, Any]:
    """Return the network-free source and complementary-route manifest."""

    return {
        "record_type": "source_manifest",
        "source": SOURCE_METADATA.to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "collections": {
            key: {
                "url": value["url"],
                "source_label": value["source_label"],
                "description": value["description"],
                "native_page_size": PAGE_SIZE,
                "native_filters": ["start", "end", "search"],
            }
            for key, value in COLLECTIONS.items()
        },
        "identity": {
            "index_occurrence": (
                "collection plus source-visible title, docket label, posted "
                "date, official document URL, and summary; identical visible "
                "occurrences retain a duplicate ordinal"
            ),
            "document": "exact official New Jersey Courts document URL path",
            "case": "each normalized source-visible docket number",
            "one_document_multiple_occurrences": True,
            "one_opinion_multiple_cases": True,
        },
        "coverage_observation": {
            "observed_at": "2026-07-30",
            "published": {
                "entries": 104,
                "native_pages": 6,
                "earliest_posted_date_observed": "2017-05-26",
                "latest_posted_date_observed": "2026-06-18",
            },
            "unpublished": {
                "entries": 374,
                "native_pages": 19,
                "earliest_posted_date_observed": "2011-05-04",
                "latest_posted_date_observed": "2026-07-06",
            },
            "interpretation": (
                "rolling index observation, not a fixed schema or assertion "
                "of complete historical Tax Court output"
            ),
        },
        "operation_access_states": {
            "index_direct": {
                "observed_at": "2026-07-30",
                "state": "edge_challenge",
                "evidence": "Incapsula/hCaptcha in Playwright and HTTP 403",
            },
            "index_reader_relay": {
                "observed_at": "2026-07-30",
                "state": "available",
                "returned": "rendered official HTML",
                "authentication": "none observed",
            },
            "document_direct": {
                "observed_at": "2026-07-30",
                "state": "edge_challenge",
                "evidence": "official PDF URL returned HTTP 403 challenge",
            },
            "document_reader_relay": {
                "observed_at": "2026-07-30",
                "state": "available",
                "returned": "text extraction with page count and source URL",
                "original_pdf_bytes": False,
            },
        },
        "pagination": {
            "native_page_parameter": "page",
            "native_page_numbering": "zero_based_query_one_based_display",
            "native_page_size": PAGE_SIZE,
            "cursor_binding": [
                "selection fingerprint",
                "collection totals",
                "first-page fingerprints",
                "last-returned-page fingerprint",
            ],
        },
        "operations": {
            "search": (
                "traverse one or both official indexes using native filters "
                "and a snapshot-bound continuation cursor; exact docket "
                "selection scans source-visible docket components so "
                "consolidated secondary dockets are not missed"
            ),
            "document": (
                "retrieve original PDF bytes when direct access succeeds or "
                "return separately labeled Reader extraction text"
            ),
            "probe": ("test direct and Reader index/document operations independently"),
            "alternatives": "return the network-free complementary-route map",
        },
        "alternative_routes": _alternative_routes(),
    }


def _failure(
    query: PublicRecordsQuery,
    error: NewJerseyTaxOpinionsError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def _client_from_args(args: argparse.Namespace) -> NewJerseyTaxOpinionsClient:
    return NewJerseyTaxOpinionsClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )


def _probe_error_state(
    error: NewJerseyTaxOpinionsError,
) -> dict[str, Any]:
    return {
        "state": (
            "edge_challenge"
            if isinstance(error, AccessChallengeError)
            else error.status.value
        ),
        "error_code": error.code,
        "message": str(error),
        "details": error.details,
    }


def _probe(
    client: NewJerseyTaxOpinionsClient | Any,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    operations: dict[str, Any] = {}
    raw_refs: list[str] = []
    reader_pages: dict[str, OpinionIndexPage] = {}
    for collection in ("published", "unpublished"):
        for transport in ("direct", "reader"):
            key = f"{collection}_index_{transport}"
            try:
                page = client.fetch_index_page(
                    collection,
                    transport=transport,
                )
            except NewJerseyTaxOpinionsError as error:
                operations[key] = _probe_error_state(error)
            else:
                operations[key] = {
                    "state": "available",
                    "retrieval_transport": page.retrieval_transport,
                    "visible_count": len(page.records),
                    "total_count": page.total_count,
                    "total_pages": page.total_pages,
                    "schema_fingerprint": page.schema_fingerprint,
                    "page_fingerprint": page.page_fingerprint,
                    "source_url": page.source_url,
                }
                raw_refs.append(page.source_url)
                if transport == "reader":
                    reader_pages[collection] = page
    published = reader_pages.get("published")
    if published is not None and published.records:
        sample_url = str(published.records[0]["document"]["source_url"])
        for transport in ("direct", "reader"):
            key = f"sample_document_{transport}"
            try:
                document = client.fetch_document(
                    sample_url,
                    transport=transport,
                )
            except NewJerseyTaxOpinionsError as error:
                operations[key] = _probe_error_state(error)
            else:
                operations[key] = {
                    "state": "available",
                    "retrieval_transport": document.retrieval_transport,
                    "source_url": document.source_url,
                    "media_type": document.media_type,
                    "source_media_type": "application/pdf",
                    "page_count": document.page_count,
                    "content_hash_scope": document.content_hash_scope,
                    "content_sha256": document.content_sha256,
                    "content_size": (
                        len(document.original_bytes)
                        if document.original_bytes is not None
                        else len(document.extracted_text or "")
                    ),
                }
                raw_refs.append(document.source_url)
    record = {
        "record_type": "source_probe",
        "source_id": SOURCE_ID,
        "operations": operations,
        "usable_index_transport": (
            "reader_relay"
            if all(
                operations.get(f"{collection}_index_reader", {}).get("state")
                == "available"
                for collection in ("published", "unpublished")
            )
            else None
        ),
        "publisher_transport_separated": True,
    }
    return record, tuple(dict.fromkeys(raw_refs))


def execute(
    args: argparse.Namespace,
    *,
    client: NewJerseyTaxOpinionsClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one source operation and return the shared result envelope."""

    query: PublicRecordsQuery | None = None
    own_client = client is None
    source_client = client
    try:
        if args.command == "manifest":
            query = _query(args, parameters={})
            result = PublicRecordsResult.success(
                query,
                [source_manifest_record()],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "alternatives":
            query = _query(args, parameters={})
            result = PublicRecordsResult.success(
                query,
                [
                    {
                        "record_type": "alternative_route_manifest",
                        "source_id": SOURCE_ID,
                        "routes": _alternative_routes(),
                    }
                ],
                warnings=SOURCE_WARNINGS,
            )
        else:
            source_client = source_client or _client_from_args(args)
            if args.command == "search":
                selection = _selection(args)
                query = _query(args, parameters=selection)
                records, next_cursor, raw_refs = _search(
                    args,
                    client=source_client,
                    selection=selection,
                )
                result = PublicRecordsResult.success(
                    query,
                    records,
                    next_cursor=next_cursor,
                    raw_artifact_refs=raw_refs,
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "document":
                safe_url = _official_document_url(args.url)
                parameters = {
                    "url": safe_url,
                    "transport": args.transport,
                    "metadata_only": bool(args.metadata_only),
                    "save": str(args.save) if args.save else None,
                }
                query = _query(args, parameters=parameters)
                document = source_client.fetch_document(
                    safe_url,
                    transport=args.transport,
                )
                normalized_dockets = [
                    component["normalized"] for component in document.docket_components
                ]
                primary_case = (
                    normalized_dockets[0]
                    if normalized_dockets
                    else Path(urlsplit(safe_url).path).stem
                )
                document_digest = hashlib.sha256(
                    document.document_id.encode("utf-8")
                ).hexdigest()[:24]
                canonical_ref = canonical_court_ref(
                    SOURCE_ID,
                    COURT_ID,
                    primary_case,
                    "opinion-document",
                    document_digest,
                )
                saved_path: str | None = None
                if args.save is not None:
                    args.save.parent.mkdir(parents=True, exist_ok=True)
                    if document.original_bytes is not None:
                        args.save.write_bytes(document.original_bytes)
                    else:
                        args.save.write_text(
                            document.extracted_text or "",
                            encoding="utf-8",
                        )
                    saved_path = str(args.save)
                record = {
                    "record_type": "tax_court_opinion_document",
                    "canonical_ref": canonical_ref,
                    "evidence_ref": canonical_ref,
                    "source_id": SOURCE_ID,
                    "document_id": document.document_id,
                    "source_url": document.source_url,
                    "retrieval_transport": document.retrieval_transport,
                    "transport_attempts": list(document.transport_attempts),
                    "media_type": document.media_type,
                    "original_pdf_bytes_retrieved": (
                        document.original_bytes is not None
                    ),
                    "content_sha256": document.content_sha256,
                    "content_hash_scope": document.content_hash_scope,
                    "content_size": (
                        len(document.original_bytes)
                        if document.original_bytes is not None
                        else len(document.extracted_text or "")
                    ),
                    "title": document.title,
                    "published_time_raw": document.published_time_raw,
                    "page_count": document.page_count,
                    "docket_components": list(document.docket_components),
                    "docket_numbers": normalized_dockets,
                    "case_canonical_refs": [
                        canonical_court_ref(
                            SOURCE_ID,
                            COURT_ID,
                            docket_number,
                        )
                        for docket_number in normalized_dockets
                    ],
                    "extracted_text": (
                        None if args.metadata_only else document.extracted_text
                    ),
                    "saved_path": saved_path,
                }
                raw_refs = [document.source_url]
                if saved_path:
                    raw_refs.append(saved_path)
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    raw_artifact_refs=raw_refs,
                    warnings=SOURCE_WARNINGS,
                )
            elif args.command == "probe":
                query = _query(args, parameters={})
                record, raw_refs = _probe(source_client)
                result = PublicRecordsResult.success(
                    query,
                    [record],
                    raw_artifact_refs=raw_refs,
                    warnings=SOURCE_WARNINGS,
                )
            else:
                raise AssertionError(f"unknown command: {args.command}")
    except NewJerseyTaxOpinionsError as error:
        query = query or _query(
            args,
            parameters={"command": args.command},
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
            "Query official published and unpublished New Jersey Tax Court "
            "opinion indexes and documents"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest = subparsers.add_parser(
        "manifest",
        help="Show source, access, identity, coverage, and route metadata",
    )
    _add_runtime_and_output(manifest)

    alternatives = subparsers.add_parser(
        "alternatives",
        help="Show complementary routes for case and valuation detail",
    )
    _add_runtime_and_output(alternatives)

    search = subparsers.add_parser(
        "search",
        help="Search and traverse one or both official opinion indexes",
    )
    search.add_argument("query", nargs="?")
    search.add_argument(
        "--collection",
        choices=("published", "unpublished", "both"),
        default="both",
    )
    search.add_argument("--docket")
    search.add_argument("--after", help="Native posted-date start, YYYY-MM-DD")
    search.add_argument("--before", help="Native posted-date end, YYYY-MM-DD")
    search.add_argument(
        "--transport",
        choices=("auto", "direct", "reader"),
        default="auto",
    )
    limit_group = search.add_mutually_exclusive_group()
    limit_group.add_argument(
        "--limit",
        type=_positive_int,
    )
    limit_group.add_argument(
        "--all-pages",
        action="store_true",
        help="Traverse every native page matching the selection",
    )
    search.add_argument("--cursor")
    _add_runtime_and_output(search)

    document = subparsers.add_parser(
        "document",
        help="Retrieve one exact official opinion PDF or relay extraction",
    )
    document.add_argument("url")
    document.add_argument(
        "--transport",
        choices=("auto", "direct", "reader"),
        default="auto",
    )
    document.add_argument(
        "--metadata-only",
        action="store_true",
        help="Omit extracted opinion text from the JSON record",
    )
    document.add_argument(
        "--save",
        type=Path,
        help="Save original PDF bytes or relay-extracted UTF-8 text",
    )
    _add_runtime_and_output(document)

    probe = subparsers.add_parser(
        "probe",
        help="Test direct and relay index/document operations separately",
    )
    _add_runtime_and_output(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"New Jersey Tax Court opinions {args.command} ({result.status.value})"
        ),
        result_count=len(result.records),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2))
        return
    print(
        f"New Jersey Tax Court opinions {args.command}: "
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
