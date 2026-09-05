#!/usr/bin/env python3
"""Query official Wisconsin appellate opinions, orders, full text, and feeds.

The Wisconsin Court System exposes four related metadata indexes, two
court-scoped full-text collections, direct court-hosted PDFs, and two RSS
feeds.  This adapter keeps those record roles distinct while preserving the
appellate case number and native PDF identifier needed to join them to WSCCA.

Examples:
    uv run python tools/query_wisconsin_opinions.py search \
        --collection appeals-opinions --case-number 2025AP000482 --json
    uv run python tools/query_wisconsin_opinions.py search \
        --collection appeals-opinions --party Alliance --county Dane --json
    uv run python tools/query_wisconsin_opinions.py keyword \
        '"Wisconsin Voter Alliance"' --court supreme --json
    uv run python tools/query_wisconsin_opinions.py feed --court appeals --json
    uv run python tools/query_wisconsin_opinions.py download \
        'https://www.wicourts.gov/ca/opinion/DisplayDocument.pdf?content=pdf&seqNo=1130001' \
        /tmp/wisconsin-opinion.pdf --json
    uv run python tools/query_wisconsin_opinions.py routes \
        --case-number 2025AP000482 --json
    uv run python tools/query_wisconsin_opinions.py probe --component all --json
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

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


SOURCE_ID = "us-wi-court-opinions"
STATE_CODE = "WI"
STATE_GEOID = "55"
BASE_URL = "https://www.wicourts.gov"
OPINIONS_HOME_URL = f"{BASE_URL}/opinions/"
SEARCH_URL = f"{BASE_URL}/SearchWicourts"

SUPREME_COURT_ID = "wi-supreme-court"
APPEALS_COURT_ID = "wi-court-of-appeals"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF = 0.5
MAXIMUM_HTML_BYTES = 24 * 1024 * 1024
MAXIMUM_FEED_BYTES = 8 * 1024 * 1024
MAXIMUM_PDF_BYTES = 256 * 1024 * 1024
FULLTEXT_PAGE_SIZE = 10
DEFAULT_USER_AGENT = (
    "IthildinOSINT/1.0 Wisconsin official appellate opinions client"
)

PROBE_SUPREME_CASE = "2023AP000036"
PROBE_SUPREME_CAPTION = "Wisconsin Voter Alliance v. Kristina Secord"
PROBE_APPEALS_CASE = "2025AP000482"
PROBE_APPEALS_CAPTION = "Wendy Treuthardt v. Connexus Credit Union"
PROBE_APPEALS_DOCUMENT_ID = "1130001"
PROBE_APPEALS_PDF_URL = (
    f"{BASE_URL}/ca/opinion/DisplayDocument.pdf"
    f"?content=pdf&seqNo={PROBE_APPEALS_DOCUMENT_ID}"
)


@dataclass(frozen=True)
class CollectionConfig:
    key: str
    name: str
    endpoint: str
    form_url: str
    court_id: str
    court_name: str
    court_level: str
    record_kind: str
    document_type: str
    expected_headers: tuple[str, ...]
    supported_parameters: frozenset[str]
    fixed_parameters: Mapping[str, str]


COLLECTIONS: dict[str, CollectionConfig] = {
    "supreme-opinions": CollectionConfig(
        key="supreme-opinions",
        name="Wisconsin Supreme Court opinions",
        endpoint=f"{BASE_URL}/supreme/scopin.jsp",
        form_url=f"{BASE_URL}/opinions/sopinion.htm",
        court_id=SUPREME_COURT_ID,
        court_name="Wisconsin Supreme Court",
        court_level="supreme",
        record_kind="appellate_opinion_index",
        document_type="supreme_court_opinion",
        expected_headers=(
            "Release date",
            "Case number",
            "Caption",
            "Select/view",
        ),
        supported_parameters=frozenset(
            {
                "docket_number",
                "begin_date",
                "end_date",
                "party_name",
                "disp_code",
                "cite_type",
                "cite_page",
                "cite_volume",
                "pdcNo",
                "sortBy",
            }
        ),
        fixed_parameters={},
    ),
    "supreme-orders": CollectionConfig(
        key="supreme-orders",
        name="Wisconsin Supreme Court orders",
        endpoint=f"{BASE_URL}/supreme/scorder.jsp",
        form_url=f"{BASE_URL}/opinions/sorders.htm",
        court_id=SUPREME_COURT_ID,
        court_name="Wisconsin Supreme Court",
        court_level="supreme",
        record_kind="appellate_order_index",
        document_type="supreme_court_order",
        expected_headers=(
            "Date issued",
            "Case number",
            "Caption",
            "Select/view",
        ),
        supported_parameters=frozenset(
            {
                "docket_number",
                "begin_date",
                "end_date",
                "party_name",
            }
        ),
        fixed_parameters={},
    ),
    "appeals-opinions": CollectionConfig(
        key="appeals-opinions",
        name="Wisconsin Court of Appeals opinions",
        endpoint=f"{BASE_URL}/other/appeals/caopin.jsp",
        form_url=f"{BASE_URL}/opinions/aopinion.htm",
        court_id=APPEALS_COURT_ID,
        court_name="Wisconsin Court of Appeals",
        court_level="appellate",
        record_kind="appellate_opinion_index",
        document_type="court_of_appeals_opinion",
        expected_headers=(
            "Release date",
            "Case number",
            "Caption",
            "District",
            "County",
            "Select/view",
        ),
        supported_parameters=frozenset(
            {
                "docket_number",
                "begin_date",
                "end_date",
                "fpb_beg_date",
                "fpb_end_date",
                "trial_judge_last",
                "party_name",
                "trial_county",
                "ca_district",
                "disp_code",
                "cite_type",
                "cite_page",
                "cite_volume",
                "pdcNo",
                "sortBy",
            }
        ),
        fixed_parameters={},
    ),
    "appeals-summary": CollectionConfig(
        key="appeals-summary",
        name="Wisconsin Court of Appeals summary dispositions",
        endpoint=f"{BASE_URL}/other/appeals/caopin.jsp",
        form_url=f"{BASE_URL}/opinions/summarydisposition.htm",
        court_id=APPEALS_COURT_ID,
        court_name="Wisconsin Court of Appeals",
        court_level="appellate",
        record_kind="summary_disposition_index",
        document_type="court_of_appeals_summary_disposition",
        expected_headers=(
            "Release date",
            "Case number",
            "Caption",
            "District",
            "County",
            "Select/view",
        ),
        supported_parameters=frozenset(
            {
                "docket_number",
                "begin_date",
                "end_date",
                "party_name",
                "ca_district",
            }
        ),
        fixed_parameters={"noticeTypeCode": "SMD"},
    ),
}


@dataclass(frozen=True)
class FullTextConfig:
    key: str
    name: str
    court_id: str
    court_name: str
    court_level: str
    native_collection: str
    native_filter: str


FULLTEXT_COLLECTIONS: dict[str, FullTextConfig] = {
    "supreme": FullTextConfig(
        key="supreme",
        name="Wisconsin Supreme Court opinion full-text search",
        court_id=SUPREME_COURT_ID,
        court_name="Wisconsin Supreme Court",
        court_level="supreme",
        native_collection="wicourts_scopinion",
        native_filter="+id:*/sc/opinion/*",
    ),
    "appeals": FullTextConfig(
        key="appeals",
        name="Wisconsin Court of Appeals opinion full-text search",
        court_id=APPEALS_COURT_ID,
        court_name="Wisconsin Court of Appeals",
        court_level="appellate",
        native_collection="wicourts_caopinion",
        native_filter="+id:*/ca/opinion/*",
    ),
}


FEED_URLS = {
    "supreme": f"{BASE_URL}/rss/scopin.jsp",
    "appeals": f"{BASE_URL}/rss/caopin.jsp",
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Wisconsin Court System Appellate Opinions",
    source_role=(
        "official_appellate_opinion_order_metadata_full_text_and_documents"
    ),
    base_url=OPINIONS_HOME_URL,
    dataset_id="wicourts-appellate-opinions",
    metadata={
        "authority": "Wisconsin Court System",
        "operator": "Clerk of the Supreme Court and Court of Appeals",
        "authentication": "none",
        "native_pagination": {
            "metadata": "one_based_page",
            "full_text": "ten_record_offset",
        },
        "collections": list(COLLECTIONS),
        "full_text_collections": list(FULLTEXT_COLLECTIONS),
        "incremental_feeds": dict(FEED_URLS),
        "primary_join_keys": [
            "normalized_appellate_case_number",
            "native_pdf_seq_no_or_doc_id",
        ],
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-wi",
    name="Wisconsin",
    state_code=STATE_CODE,
    metadata={"state_geoid": STATE_GEOID},
)

SOURCE_WARNINGS = (
    "Supreme Court opinions on the official site begin in September 1995; "
    "Court of Appeals opinions begin in June 1995.",
    "Published opinions may be edited before their final appearance in the "
    "bound official reports; source annotations and document identifiers are "
    "preserved.",
    "The opinion indexes are not case dockets. Use WSCCA for docket events, "
    "briefs, linked circuit cases, and case status.",
)

_CASE_RE = re.compile(r"\b\d{4}AP\d{6}(?:-[A-Z0-9]+)?\b", re.IGNORECASE)
_BASE_CASE_RE = re.compile(r"^\d{4}AP\d{6}", re.IGNORECASE)
_PAGE_RE = re.compile(r"\bPage\s+(\d+)\s+of\s+(\d+)\b", re.IGNORECASE)
_FULLTEXT_COUNT_RE = re.compile(
    r"(?:Search results\s*)?<b>([\d,]+)</b>\s*-\s*"
    r"<b>([\d,]+)</b>\s*of\s*<b>([\d,]+)</b>",
    re.IGNORECASE | re.DOTALL,
)
_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_ANNOTATION_RE = re.compile(r"\[([^\]]+)\]")
_DOCUMENT_ID_RE = re.compile(r"(?:seqNo|docId)=(\d+)", re.IGNORECASE)
_CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "challenges.cloudflare.com",
    "captcha",
)


class WisconsinOpinionsError(RuntimeError):
    """Source error carrying an explicit public-record result status."""

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


class WisconsinOpinionsSelectionError(WisconsinOpinionsError):
    """The requested native selector cannot be represented."""

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


class WisconsinOpinionsSourceChangedError(WisconsinOpinionsError):
    """The official page no longer matches its verified structure."""

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
class MetadataPage:
    records: tuple[dict[str, Any], ...]
    collection: str
    page_number: int
    total_pages: int
    next_page: int | None
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class FullTextPage:
    records: tuple[dict[str, Any], ...]
    court: str
    page_number: int
    offset: int
    total_items: int
    total_pages: int
    next_offset: int | None
    source_url: str
    schema_fingerprint: str


@dataclass(frozen=True)
class PageCollection:
    records: tuple[dict[str, Any], ...]
    pages_fetched: int
    source_urls: tuple[str, ...]
    next_cursor: str | None
    incomplete_error: WisconsinOpinionsError | None = None


@dataclass(frozen=True)
class OpinionPDF:
    source_url: str
    content: bytes
    media_type: str
    sha256: str
    native_document_id: str | None
    native_document_id_type: str | None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", str(value)).strip()
    return normalized or None


def _date_iso(value: Any) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    for date_format in ("%b %d, %Y", "%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def _native_date(value: str, label: str) -> tuple[str, str]:
    normalized = _text(value)
    if normalized is None:
        raise WisconsinOpinionsSelectionError(
            "missing_date",
            f"{label} must not be empty",
        )
    for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            parsed = datetime.strptime(normalized, date_format).date()
            return parsed.isoformat(), parsed.strftime("%m/%d/%Y")
        except ValueError:
            continue
    raise WisconsinOpinionsSelectionError(
        "invalid_date",
        f"{label} must be YYYY-MM-DD, MM/DD/YYYY, or MM-DD-YYYY",
        details={"value": normalized},
    )


def _normalized_case_number(value: Any) -> str | None:
    normalized = re.sub(r"\s+", "", str(value or "")).upper()
    if not normalized:
        return None
    matched = _BASE_CASE_RE.match(normalized)
    return matched.group(0).upper() if matched else normalized


def _case_number(value: Any) -> str:
    normalized = re.sub(r"\s+", "", str(value or "")).upper()
    if not normalized:
        raise WisconsinOpinionsSelectionError(
            "missing_case_number",
            "An appellate case number is required",
        )
    return normalized


def _document_identity(source_url: str) -> tuple[str | None, str | None]:
    parsed = urlsplit(source_url)
    query = parse_qs(parsed.query)
    for key, identity_type in (("seqNo", "seq_no"), ("docId", "doc_id")):
        values = query.get(key)
        if values and values[0].strip():
            return values[0].strip(), identity_type
    matched = _DOCUMENT_ID_RE.search(source_url)
    if matched:
        return matched.group(1), "native_document_id"
    return None, None


def _https_official_url(value: str, *, base_url: str = BASE_URL) -> str:
    absolute = urljoin(base_url, html.unescape(value).strip())
    parsed = urlsplit(absolute)
    if parsed.hostname != "www.wicourts.gov":
        raise WisconsinOpinionsSourceChangedError(
            "unexpected_document_host",
            "Wisconsin court record linked outside the official court host",
            details={"url": absolute},
        )
    return urlunsplit(
        (
            "https",
            "www.wicourts.gov",
            parsed.path,
            parsed.query,
            "",
        )
    )


def _official_pdf_url(value: str, *, source_link: bool = False) -> str:
    try:
        official = _https_official_url(value)
    except WisconsinOpinionsSourceChangedError as error:
        if source_link:
            raise
        raise WisconsinOpinionsSelectionError(
            "unsupported_pdf_url",
            "The URL is not on the official Wisconsin Court System host",
            details={"url": value},
        ) from error
    parsed = urlsplit(official)
    allowed_path = re.fullmatch(
        r"/(?:sc|ca)/(?:opinion|order)/(?:DisplayDocument|DisplayDocImage)\.pdf",
        parsed.path,
        flags=re.IGNORECASE,
    )
    if allowed_path is None:
        raise WisconsinOpinionsSelectionError(
            "unsupported_pdf_url",
            "The URL is not a Wisconsin appellate opinion or order PDF route",
            details={"url": official},
        )
    return official


def _caption_annotations(raw_caption: str) -> dict[str, Any]:
    annotations = [
        _text(item) for item in _ANNOTATION_RE.findall(raw_caption)
    ]
    annotations = [item for item in annotations if item is not None]
    caption = _text(_ANNOTATION_RE.sub(" ", raw_caption))
    publication_status = "not_stated"
    final_publication_date: str | None = None
    withdrawn_date: str | None = None
    is_errata = bool(re.match(r"^Errata:\s*", caption or "", re.IGNORECASE))
    for annotation in annotations:
        lowered = annotation.lower()
        found_date = _ISO_DATE_RE.search(annotation)
        if "recommended for publication" in lowered:
            publication_status = "recommended_for_publication"
        elif "final publication" in lowered:
            publication_status = "final_publication"
            if found_date:
                final_publication_date = found_date.group(1)
        elif "withdrawn" in lowered:
            publication_status = "withdrawn"
            if found_date:
                withdrawn_date = found_date.group(1)
    return {
        "caption": caption,
        "source_caption": _text(raw_caption),
        "source_annotations": annotations,
        "publication_status": publication_status,
        "final_publication_date": final_publication_date,
        "withdrawn_date": withdrawn_date,
        "is_errata": is_errata,
    }


def _court_payload(config: CollectionConfig | FullTextConfig) -> dict[str, Any]:
    return {
        "court_id": config.court_id,
        "name": config.court_name,
        "state_code": STATE_CODE,
        "court_level": config.court_level,
        "official_url": (
            f"{BASE_URL}/courts/supreme/index.htm"
            if config.court_id == SUPREME_COURT_ID
            else f"{BASE_URL}/courts/appeals/index.htm"
        ),
    }


def _metadata_record(
    cells: Sequence[Tag],
    *,
    config: CollectionConfig,
    source_url: str,
    page_number: int,
    schema_fingerprint: str,
) -> dict[str, Any]:
    expected_count = len(config.expected_headers)
    if len(cells) != expected_count:
        raise WisconsinOpinionsSourceChangedError(
            "table_row_width_changed",
            "Wisconsin appellate result row width changed",
            details={
                "collection": config.key,
                "expected": expected_count,
                "observed": len(cells),
            },
        )
    values = [_text(cell.get_text(" ", strip=True)) for cell in cells]
    raw_date = values[0]
    raw_case_number = _case_number(values[1])
    caption_fields = _caption_annotations(values[2] or "")
    link = cells[-1].find("a", href=True)
    if link is None:
        raise WisconsinOpinionsSourceChangedError(
            "document_link_missing",
            "Wisconsin appellate result row lacks its document link",
            details={
                "collection": config.key,
                "case_number": raw_case_number,
            },
        )
    pdf_url = _official_pdf_url(str(link["href"]), source_link=True)
    document_id, document_id_type = _document_identity(pdf_url)
    if document_id is None:
        raise WisconsinOpinionsSourceChangedError(
            "document_id_missing",
            "Wisconsin appellate document URL lacks seqNo or docId",
            details={"url": pdf_url},
        )
    normalized_case_number = _normalized_case_number(raw_case_number)
    if normalized_case_number is None:
        raise WisconsinOpinionsSourceChangedError(
            "case_number_missing",
            "Wisconsin appellate result row lacks a case number",
        )
    case_ref = canonical_court_ref(
        SOURCE_ID,
        config.court_id,
        normalized_case_number,
    )
    canonical_ref = canonical_court_ref(
        SOURCE_ID,
        config.court_id,
        normalized_case_number,
        config.record_kind,
        document_id,
    )
    district = values[3] if config.court_id == APPEALS_COURT_ID else None
    county = values[4] if config.court_id == APPEALS_COURT_ID else None
    issued_date = _date_iso(raw_date)
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "case_canonical_ref": case_ref,
        "source_id": SOURCE_ID,
        "record_kind": config.record_kind,
        "collection": config.key,
        "raw_case_number": raw_case_number,
        "normalized_appellate_case_number": normalized_case_number,
        **caption_fields,
        "decision_date": issued_date,
        "issued_date": issued_date,
        "source_date_raw": raw_date,
        "district": district,
        "county": county,
        "document": {
            "native_document_id": document_id,
            "native_document_id_type": document_id_type,
            "document_type": config.document_type,
            "filed_date": issued_date,
            "source_url": pdf_url,
            "mime_type": "application/pdf",
            "access_state": "public",
        },
        "pdf_url": pdf_url,
        "source_url": pdf_url,
        "index_url": source_url,
        "court": _court_payload(config),
        "join_keys": {
            "appellate_case_number": normalized_case_number,
            "native_document_id": document_id,
            "native_document_id_type": document_id_type,
        },
        "source_scope": {
            "official_document": True,
            "complete_case_docket": False,
            "briefs": False,
            "linked_circuit_case": False,
        },
        "provenance": {
            "source_id": SOURCE_ID,
            "source_url": source_url,
            "native_collection": config.key,
            "native_page": page_number,
            "response_schema_fingerprint": schema_fingerprint,
        },
    }


def parse_metadata_page(
    html_text: str,
    *,
    collection: str,
    source_url: str,
    requested_page: int,
) -> MetadataPage:
    """Parse one official metadata-index page."""

    config = COLLECTIONS[collection]
    soup = BeautifulSoup(html_text, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True)) or ""
    if "Sorry, no records found." in page_text:
        return MetadataPage(
            records=(),
            collection=collection,
            page_number=requested_page,
            total_pages=0,
            next_page=None,
            source_url=source_url,
            schema_fingerprint=sha256_fingerprint(
                {"collection": collection, "empty_state": "no_records_found"}
            ),
        )
    table = soup.find("table", id="scopinion")
    if table is None:
        raise WisconsinOpinionsSourceChangedError(
            "results_table_missing",
            "Wisconsin appellate search page lacks its result table",
            details={"collection": collection, "url": source_url},
        )
    headers = tuple(
        _text(cell.get_text(" ", strip=True)) or ""
        for cell in table.select("thead th")
    )
    if headers != config.expected_headers:
        raise WisconsinOpinionsSourceChangedError(
            "table_headers_changed",
            "Wisconsin appellate result headers changed",
            details={
                "collection": collection,
                "expected": list(config.expected_headers),
                "observed": list(headers),
            },
        )
    schema_fingerprint = sha256_fingerprint(
        {
            "collection": collection,
            "headers": headers,
            "table_id": table.get("id"),
            "table_classes": sorted(table.get("class", [])),
        }
    )
    page_match = _PAGE_RE.search(page_text)
    if page_match is None:
        raise WisconsinOpinionsSourceChangedError(
            "pagination_summary_missing",
            "Wisconsin appellate results lack the Page N of M summary",
            details={"collection": collection, "url": source_url},
        )
    actual_page = int(page_match.group(1))
    total_pages = int(page_match.group(2))
    if actual_page != requested_page:
        raise WisconsinOpinionsSourceChangedError(
            "unexpected_page_number",
            "Wisconsin appellate source returned a different native page",
            details={
                "collection": collection,
                "requested_page": requested_page,
                "actual_page": actual_page,
            },
        )
    body = table.find("tbody")
    rows = body.find_all("tr", recursive=False) if body is not None else []
    records = tuple(
        _metadata_record(
            row.find_all("td", recursive=False),
            config=config,
            source_url=source_url,
            page_number=actual_page,
            schema_fingerprint=schema_fingerprint,
        )
        for row in rows
    )
    next_page = actual_page + 1 if actual_page < total_pages else None
    return MetadataPage(
        records=records,
        collection=collection,
        page_number=actual_page,
        total_pages=total_pages,
        next_page=next_page,
        source_url=source_url,
        schema_fingerprint=schema_fingerprint,
    )


def _result_snippet(container: Tag) -> str | None:
    fragment = BeautifulSoup(str(container), "html.parser")
    for node in fragment.select(".docType, .resultUrl, .docPath"):
        node.decompose()
    return _text(fragment.get_text(" ", strip=True))


def _fulltext_record(
    container: Tag,
    *,
    config: FullTextConfig,
    source_url: str,
    page_number: int,
    schema_fingerprint: str,
) -> dict[str, Any]:
    result_link = container.select_one(".resultUrl a[href]")
    if result_link is None:
        raise WisconsinOpinionsSourceChangedError(
            "fulltext_result_link_missing",
            "Wisconsin opinion full-text hit lacks a result link",
            details={"court": config.key},
        )
    document_url = _https_official_url(str(result_link["href"]))
    document_id, document_id_type = _document_identity(document_url)
    native_title = _text(result_link.get_text(" ", strip=True))
    doc_type_node = container.select_one(".docType")
    native_document_type = (
        _text(doc_type_node.get_text(" ", strip=True))
        if doc_type_node is not None
        else None
    )
    doc_path = container.select_one(".docPath")
    indexed_date = None
    if doc_path is not None:
        date_match = _ISO_DATE_RE.search(doc_path.get_text(" ", strip=True))
        if date_match:
            indexed_date = date_match.group(1)
    snippet = _result_snippet(container)
    case_match = _CASE_RE.search(snippet or "")
    raw_case_number = case_match.group(0).upper() if case_match else None
    normalized_case_number = _normalized_case_number(raw_case_number)
    identity = (
        document_id
        or hashlib.sha256(document_url.encode("utf-8")).hexdigest()[:24]
    )
    representation = (
        "pdf"
        if urlsplit(document_url).path.lower().endswith(".pdf")
        else "html"
    )
    canonical_ref = canonical_court_ref(
        SOURCE_ID,
        config.court_id,
        normalized_case_number or f"fulltext-{identity}",
        "full_text_search_hit",
        f"{identity}-{representation}",
    )
    media_type = (
        "application/pdf"
        if representation == "pdf"
        else "text/html"
    )
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "case_canonical_ref": (
            canonical_court_ref(
                SOURCE_ID,
                config.court_id,
                normalized_case_number,
            )
            if normalized_case_number
            else None
        ),
        "source_id": SOURCE_ID,
        "record_kind": "full_text_search_hit",
        "full_text_collection": config.key,
        "raw_case_number": raw_case_number,
        "normalized_appellate_case_number": normalized_case_number,
        "native_title": native_title,
        "snippet": snippet,
        "native_document_type": native_document_type,
        "indexed_date": indexed_date,
        "native_document_id": document_id,
        "native_document_id_type": document_id_type,
        "document_url": document_url,
        "source_url": document_url,
        "search_url": source_url,
        "mime_type": media_type,
        "court": _court_payload(config),
        "join_keys": {
            "appellate_case_number": normalized_case_number,
            "native_document_id": document_id,
            "native_document_id_type": document_id_type,
        },
        "source_scope": {
            "full_text_hit": True,
            "metadata_index_entry": False,
            "complete_case_docket": False,
        },
        "provenance": {
            "source_id": SOURCE_ID,
            "source_url": source_url,
            "native_collection": config.native_collection,
            "native_filter": config.native_filter,
            "native_page": page_number,
            "response_schema_fingerprint": schema_fingerprint,
        },
    }


def parse_fulltext_page(
    html_text: str,
    *,
    court: str,
    query_text: str,
    source_url: str,
    requested_page: int,
) -> FullTextPage:
    """Parse one official ten-result full-text page."""

    config = FULLTEXT_COLLECTIONS[court]
    soup = BeautifulSoup(html_text, "html.parser")
    results = soup.select_one("div.results")
    page_html = str(soup)
    count_match = _FULLTEXT_COUNT_RE.search(page_html)
    page_text = _text(soup.get_text(" ", strip=True)) or ""
    no_results = (
        "did not match any documents" in page_text.lower()
        or "no results found." in page_text.lower()
        or re.search(r"\bof\s+0\s+for\b", page_text, re.IGNORECASE) is not None
    )
    if no_results:
        return FullTextPage(
            records=(),
            court=court,
            page_number=requested_page,
            offset=(requested_page - 1) * FULLTEXT_PAGE_SIZE,
            total_items=0,
            total_pages=0,
            next_offset=None,
            source_url=source_url,
            schema_fingerprint=sha256_fingerprint(
                {
                    "court": court,
                    "empty_state": "no_documents",
                    "query": query_text,
                }
            ),
        )
    if results is None or count_match is None:
        raise WisconsinOpinionsSourceChangedError(
            "fulltext_results_missing",
            "Wisconsin opinion full-text response lacks results or count summary",
            details={"court": court, "url": source_url},
        )
    first_item = int(count_match.group(1).replace(",", ""))
    last_item = int(count_match.group(2).replace(",", ""))
    total_items = int(count_match.group(3).replace(",", ""))
    expected_first = (requested_page - 1) * FULLTEXT_PAGE_SIZE + 1
    if total_items and first_item != expected_first:
        raise WisconsinOpinionsSourceChangedError(
            "fulltext_page_mismatch",
            "Wisconsin full-text search returned an unexpected result offset",
            details={
                "court": court,
                "requested_page": requested_page,
                "expected_first": expected_first,
                "actual_first": first_item,
            },
        )
    total_pages = (
        (total_items + FULLTEXT_PAGE_SIZE - 1) // FULLTEXT_PAGE_SIZE
        if total_items
        else 0
    )
    schema_fingerprint = sha256_fingerprint(
        {
            "court": court,
            "result_container_class": sorted(results.get("class", [])),
            "page_size": FULLTEXT_PAGE_SIZE,
            "has_result_url": bool(results.select_one(".resultUrl")),
            "has_doc_path": bool(results.select_one(".docPath")),
        }
    )
    containers = [
        node
        for node in results.find_all("div", recursive=False)
        if node.select_one(".resultUrl a[href]") is not None
    ]
    records = tuple(
        _fulltext_record(
            container,
            config=config,
            source_url=source_url,
            page_number=requested_page,
            schema_fingerprint=schema_fingerprint,
        )
        for container in containers
    )
    if total_items and len(records) != last_item - first_item + 1:
        raise WisconsinOpinionsSourceChangedError(
            "fulltext_result_count_mismatch",
            "Wisconsin full-text result count does not match its page summary",
            details={
                "court": court,
                "expected": last_item - first_item + 1,
                "observed": len(records),
            },
        )
    offset = (requested_page - 1) * FULLTEXT_PAGE_SIZE
    next_offset = (
        offset + FULLTEXT_PAGE_SIZE
        if requested_page < total_pages
        else None
    )
    return FullTextPage(
        records=records,
        court=court,
        page_number=requested_page,
        offset=offset,
        total_items=total_items,
        total_pages=total_pages,
        next_offset=next_offset,
        source_url=source_url,
        schema_fingerprint=schema_fingerprint,
    )


def _rss_date(value: str | None) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    parsed_date = _date_iso(normalized)
    if parsed_date:
        return parsed_date
    try:
        parsed = parsedate_to_datetime(normalized)
    except (TypeError, ValueError):
        return None
    return parsed.isoformat()


def _rss_title(value: str | None) -> str:
    decoded = html.unescape(value or "")
    return _text(BeautifulSoup(decoded, "html.parser").get_text(" ", strip=True)) or ""


def _normalized_feed_link(value: str | None) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    return _https_official_url(normalized)


def parse_feed(xml_bytes: bytes, *, court: str, source_url: str) -> list[dict[str, Any]]:
    """Parse a route-bound official Wisconsin opinion RSS feed."""

    if court not in FEED_URLS:
        raise WisconsinOpinionsSelectionError(
            "unknown_feed",
            f"Unknown Wisconsin opinion feed: {court}",
        )
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as error:
        raise WisconsinOpinionsSourceChangedError(
            "feed_xml_invalid",
            "Wisconsin opinion feed is not valid XML",
            details={"court": court, "error": str(error)},
        ) from error
    channel = root.find("channel")
    if channel is None:
        raise WisconsinOpinionsSourceChangedError(
            "feed_channel_missing",
            "Wisconsin opinion RSS response lacks a channel",
            details={"court": court},
        )
    court_config = FULLTEXT_COLLECTIONS[court]
    records: list[dict[str, Any]] = []
    for item in channel.findall("item"):
        source_title = _rss_title(item.findtext("title"))
        case_match = _CASE_RE.search(source_title)
        raw_case_number = case_match.group(0).upper() if case_match else None
        normalized_case_number = _normalized_case_number(raw_case_number)
        caption_raw = source_title
        if case_match:
            caption_raw = source_title[case_match.end() :]
            caption_raw = re.sub(r"^\s*-\s*", "", caption_raw)
        caption_fields = _caption_annotations(caption_raw)
        guid = _text(item.findtext("guid"))
        release_date = _rss_date(item.findtext("pubDate"))
        index_url = _normalized_feed_link(item.findtext("link"))
        identity = guid or sha256_fingerprint(
            {
                "court": court,
                "case_number": raw_case_number,
                "release_date": release_date,
                "title": source_title,
            }
        )
        canonical_ref = canonical_court_ref(
            SOURCE_ID,
            court_config.court_id,
            normalized_case_number or f"feed-{identity}",
            "opinion_release_notice",
            identity,
        )
        records.append(
            {
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "case_canonical_ref": (
                    canonical_court_ref(
                        SOURCE_ID,
                        court_config.court_id,
                        normalized_case_number,
                    )
                    if normalized_case_number
                    else None
                ),
                "source_id": SOURCE_ID,
                "record_kind": "opinion_release_notice",
                "feed": court,
                "native_guid": guid,
                "native_author": _text(item.findtext("author")),
                "source_title": source_title,
                "raw_case_number": raw_case_number,
                "normalized_appellate_case_number": normalized_case_number,
                **caption_fields,
                "release_date": release_date,
                "source_date_raw": _text(item.findtext("pubDate")),
                "index_url": index_url,
                "source_url": source_url,
                "court": _court_payload(court_config),
                "court_identity_basis": "feed_route",
                "join_keys": {
                    "appellate_case_number": normalized_case_number,
                    "native_guid": guid,
                },
                "source_scope": {
                    "incremental_release_notice": True,
                    "direct_pdf": False,
                    "complete_archive": False,
                },
                "provenance": {
                    "source_id": SOURCE_ID,
                    "source_url": source_url,
                    "native_feed": court,
                    "channel_title": _text(channel.findtext("title")),
                    "channel_published_at": _rss_date(
                        channel.findtext("pubDate")
                    ),
                },
            }
        )
    return records


def parse_taxonomy(
    html_text: str,
    *,
    collection: str,
    source_url: str,
) -> list[dict[str, Any]]:
    """Extract the source's current form fields and option values."""

    config = COLLECTIONS[collection]
    soup = BeautifulSoup(html_text, "html.parser")
    form = soup.find("form", id="SearchForm")
    if form is None:
        raise WisconsinOpinionsSourceChangedError(
            "search_form_missing",
            "Wisconsin appellate search page lacks SearchForm",
            details={"collection": collection, "url": source_url},
        )
    action = _https_official_url(str(form.get("action") or config.endpoint))
    records: list[dict[str, Any]] = []
    for field in form.find_all(["input", "select"]):
        name = _text(field.get("name"))
        if name is None or name in {"Submit", "Reset", "reset"}:
            continue
        record: dict[str, Any] = {
            "source_id": SOURCE_ID,
            "record_kind": "search_field_taxonomy",
            "collection": collection,
            "field_name": name,
            "field_type": field.name,
            "source_url": source_url,
            "form_action": action,
            "form_method": str(form.get("method") or "get").lower(),
        }
        if field.name == "select":
            record["options"] = [
                {
                    "value": str(option.get("value") or ""),
                    "label": _text(option.get_text(" ", strip=True)),
                }
                for option in field.find_all("option")
            ]
        else:
            record["input_type"] = str(field.get("type") or "text").lower()
            record["value"] = _text(field.get("value"))
            maximum = field.get("maxlength")
            record["maximum_length"] = (
                int(maximum) if str(maximum or "").isdigit() else None
            )
        records.append(record)
    if not records:
        raise WisconsinOpinionsSourceChangedError(
            "search_fields_missing",
            "Wisconsin appellate SearchForm has no query fields",
            details={"collection": collection},
        )
    return records


def _taxonomy_value(
    records: Sequence[Mapping[str, Any]],
    *,
    field_name: str,
    requested: str,
) -> str:
    requested_text = _text(requested) or ""
    for record in records:
        if record.get("field_name") != field_name:
            continue
        options = record.get("options")
        if not isinstance(options, Sequence):
            continue
        for option in options:
            if not isinstance(option, Mapping):
                continue
            value = _text(option.get("value")) or ""
            label = _text(option.get("label")) or ""
            if requested_text.casefold() in {value.casefold(), label.casefold()}:
                return value
    raise WisconsinOpinionsSelectionError(
        "taxonomy_value_not_found",
        f"No current {field_name} option matches {requested_text!r}",
        details={"field_name": field_name, "requested": requested_text},
    )


class WisconsinOpinionsClient:
    """Paced, retrying client for the official indexes, feeds, and PDFs."""

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
                        "text/html,application/xhtml+xml,application/rss+xml,"
                        "application/xml;q=0.9,application/pdf;q=0.9,*/*;q=0.5"
                    ),
                    "Accept-Language": "en-US,en;q=0.8",
                }
            )

    def _get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
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
                    raise WisconsinOpinionsError(
                        "transport_error",
                        f"Wisconsin Court System request failed: {error}",
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
                raise WisconsinOpinionsError(
                    "source_rate_limited",
                    "Wisconsin Court System rate-limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="http",
                    retryable=True,
                    details={"url": url, "http_status": status_code},
                )
            if status_code != 200:
                raise WisconsinOpinionsError(
                    "source_http_error",
                    f"Wisconsin Court System returned HTTP {status_code}",
                    category="http",
                    retryable=status_code >= 500,
                    details={"url": url, "http_status": status_code},
                )
            final_url = str(getattr(response, "url", url))
            if urlsplit(final_url).hostname != "www.wicourts.gov":
                raise WisconsinOpinionsSourceChangedError(
                    "unexpected_redirect",
                    "Wisconsin Court System redirected outside its official host",
                    details={"url": final_url},
                )
            return response
        raise AssertionError("retry loop exhausted")

    @staticmethod
    def _validate_text_response(
        response: Any,
        *,
        maximum_bytes: int,
        expected_path: str | None = None,
    ) -> str:
        content = bytes(getattr(response, "content", b""))
        text = str(getattr(response, "text", ""))
        observed_size = len(content) if content else len(text.encode("utf-8"))
        if observed_size > maximum_bytes:
            raise WisconsinOpinionsError(
                "response_too_large",
                "Wisconsin Court System response exceeded the adapter ceiling",
                category="response",
                details={
                    "url": str(getattr(response, "url", "")),
                    "size_bytes": observed_size,
                    "maximum_bytes": maximum_bytes,
                },
            )
        lowered = text.lower()
        if any(marker in lowered for marker in _CHALLENGE_MARKERS):
            raise WisconsinOpinionsError(
                "source_access_challenge",
                "Wisconsin Court System returned an access challenge",
                status=ResultStatus.HUMAN_REQUIRED,
                category="source_access",
                retryable=True,
                details={"url": str(getattr(response, "url", ""))},
            )
        if expected_path is not None:
            actual_path = urlsplit(str(getattr(response, "url", ""))).path
            if actual_path != expected_path:
                raise WisconsinOpinionsSourceChangedError(
                    "unexpected_response_path",
                    "Wisconsin Court System returned an unexpected page",
                    details={
                        "expected_path": expected_path,
                        "actual_path": actual_path,
                    },
                )
        return text

    def fetch_metadata_page(
        self,
        collection: str,
        selection: Mapping[str, str],
        *,
        page_number: int,
    ) -> MetadataPage:
        config = COLLECTIONS[collection]
        params: dict[str, Any] = {
            **config.fixed_parameters,
            **{key: value for key, value in selection.items() if value},
            "page": page_number,
        }
        response = self._get(config.endpoint, params=params)
        html_text = self._validate_text_response(
            response,
            maximum_bytes=MAXIMUM_HTML_BYTES,
            expected_path=urlsplit(config.endpoint).path,
        )
        return parse_metadata_page(
            html_text,
            collection=collection,
            source_url=str(response.url),
            requested_page=page_number,
        )

    def fetch_all_metadata(
        self,
        collection: str,
        selection: Mapping[str, str],
        *,
        start_page: int = 1,
        max_pages: int | None = None,
    ) -> PageCollection:
        pages: list[MetadataPage] = []
        page_number = start_page
        incomplete_error: WisconsinOpinionsError | None = None
        while True:
            if max_pages is not None and len(pages) >= max_pages:
                break
            try:
                page = self.fetch_metadata_page(
                    collection,
                    selection,
                    page_number=page_number,
                )
            except WisconsinOpinionsError as error:
                if not pages:
                    raise
                incomplete_error = error
                break
            pages.append(page)
            if page.next_page is None:
                break
            page_number = page.next_page
        next_page = pages[-1].next_page if pages else None
        return PageCollection(
            records=tuple(record for page in pages for record in page.records),
            pages_fetched=len(pages),
            source_urls=tuple(page.source_url for page in pages),
            next_cursor=(
                f"metadata:{collection}:page:{next_page}"
                if next_page is not None
                else None
            ),
            incomplete_error=incomplete_error,
        )

    def fetch_fulltext_page(
        self,
        court: str,
        query_text: str,
        *,
        page_number: int,
    ) -> FullTextPage:
        config = FULLTEXT_COLLECTIONS[court]
        offset = (page_number - 1) * FULLTEXT_PAGE_SIZE
        response = self._get(
            SEARCH_URL,
            params={
                "q": query_text,
                "fq": config.native_filter,
                "pager.offset": offset,
            },
        )
        html_text = self._validate_text_response(
            response,
            maximum_bytes=MAXIMUM_HTML_BYTES,
            expected_path="/SearchWicourts",
        )
        return parse_fulltext_page(
            html_text,
            court=court,
            query_text=query_text,
            source_url=str(response.url),
            requested_page=page_number,
        )

    def fetch_all_fulltext(
        self,
        court: str,
        query_text: str,
        *,
        start_page: int = 1,
        max_pages: int | None = None,
    ) -> PageCollection:
        pages: list[FullTextPage] = []
        page_number = start_page
        incomplete_error: WisconsinOpinionsError | None = None
        while True:
            if max_pages is not None and len(pages) >= max_pages:
                break
            try:
                page = self.fetch_fulltext_page(
                    court,
                    query_text,
                    page_number=page_number,
                )
            except WisconsinOpinionsError as error:
                if not pages:
                    raise
                incomplete_error = error
                break
            pages.append(page)
            if page.next_offset is None:
                break
            page_number += 1
        next_offset = pages[-1].next_offset if pages else None
        return PageCollection(
            records=tuple(record for page in pages for record in page.records),
            pages_fetched=len(pages),
            source_urls=tuple(page.source_url for page in pages),
            next_cursor=(
                f"fulltext:{court}:offset:{next_offset}"
                if next_offset is not None
                else None
            ),
            incomplete_error=incomplete_error,
        )

    def fetch_feed(self, court: str) -> tuple[list[dict[str, Any]], str]:
        source_url = FEED_URLS[court]
        response = self._get(source_url)
        content = bytes(response.content)
        if len(content) > MAXIMUM_FEED_BYTES:
            raise WisconsinOpinionsError(
                "feed_too_large",
                "Wisconsin opinion feed exceeded the adapter ceiling",
                category="response",
                details={
                    "url": str(response.url),
                    "size_bytes": len(content),
                    "maximum_bytes": MAXIMUM_FEED_BYTES,
                },
            )
        return (
            parse_feed(
                content,
                court=court,
                source_url=str(response.url),
            ),
            str(response.url),
        )

    def fetch_taxonomy(
        self,
        collection: str,
    ) -> tuple[list[dict[str, Any]], str]:
        config = COLLECTIONS[collection]
        response = self._get(config.form_url)
        html_text = self._validate_text_response(
            response,
            maximum_bytes=MAXIMUM_HTML_BYTES,
            expected_path=urlsplit(config.form_url).path,
        )
        return (
            parse_taxonomy(
                html_text,
                collection=collection,
                source_url=str(response.url),
            ),
            str(response.url),
        )

    def fetch_pdf(self, source_url: str) -> OpinionPDF:
        safe_url = _official_pdf_url(source_url)
        response = self._get(safe_url)
        final_url = _official_pdf_url(str(response.url))
        content = bytes(response.content)
        if len(content) > MAXIMUM_PDF_BYTES:
            raise WisconsinOpinionsError(
                "pdf_too_large",
                "Wisconsin appellate PDF exceeded the adapter ceiling",
                category="response",
                details={
                    "url": final_url,
                    "size_bytes": len(content),
                    "maximum_bytes": MAXIMUM_PDF_BYTES,
                },
            )
        media_type = str(
            getattr(response, "headers", {}).get(
                "Content-Type",
                "application/pdf",
            )
        ).split(";", 1)[0].strip().lower()
        if not content.startswith(b"%PDF-"):
            raise WisconsinOpinionsSourceChangedError(
                "pdf_signature_missing",
                "Wisconsin appellate document response is not a PDF",
                details={
                    "url": final_url,
                    "content_type": media_type,
                    "size_bytes": len(content),
                },
            )
        document_id, document_id_type = _document_identity(final_url)
        return OpinionPDF(
            source_url=final_url,
            content=content,
            media_type=media_type,
            sha256=hashlib.sha256(content).hexdigest(),
            native_document_id=document_id,
            native_document_id_type=document_id_type,
        )

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()


def _date_pair(
    start: str | None,
    end: str | None,
    *,
    start_label: str,
    end_label: str,
) -> tuple[str | None, str | None]:
    if bool(start) != bool(end):
        raise WisconsinOpinionsSelectionError(
            "incomplete_date_range",
            f"{start_label} and {end_label} must be supplied together",
        )
    if not start or not end:
        return None, None
    start_iso, native_start = _native_date(start, start_label)
    end_iso, native_end = _native_date(end, end_label)
    if start_iso > end_iso:
        raise WisconsinOpinionsSelectionError(
            "invalid_date_range",
            f"{start_label} must not be later than {end_label}",
        )
    return native_start, native_end


def _metadata_selection(
    args: argparse.Namespace,
    *,
    client: WisconsinOpinionsClient | Any,
) -> tuple[dict[str, str], tuple[str, ...]]:
    config = COLLECTIONS[args.collection]
    release_start, release_end = _date_pair(
        args.date_from,
        args.date_to,
        start_label="--date-from",
        end_label="--date-to",
    )
    publication_start, publication_end = _date_pair(
        args.final_publication_from,
        args.final_publication_to,
        start_label="--final-publication-from",
        end_label="--final-publication-to",
    )
    selection: dict[str, str] = {
        "docket_number": (
            _case_number(args.case_number) if args.case_number else ""
        ),
        "begin_date": release_start or "",
        "end_date": release_end or "",
        "fpb_beg_date": publication_start or "",
        "fpb_end_date": publication_end or "",
        "trial_judge_last": _text(args.judge) or "",
        "party_name": _text(args.party) or "",
        "ca_district": str(args.district or ""),
        "cite_type": {
            "none": "",
            "nw2d": "N.W.2d",
            "wis2d": "Wis. 2d",
        }[args.citation_type],
        "cite_page": _text(args.citation_page) or "",
        "cite_volume": _text(args.citation_volume) or "",
        "pdcNo": _text(args.public_domain_citation) or "",
        "sortBy": args.sort or "",
    }
    taxonomy_records: list[dict[str, Any]] | None = None
    taxonomy_url: str | None = None
    unavailable_dynamic_filters = []
    if args.county and "trial_county" not in config.supported_parameters:
        unavailable_dynamic_filters.append("trial_county")
    if args.disposition and "disp_code" not in config.supported_parameters:
        unavailable_dynamic_filters.append("disp_code")
    if unavailable_dynamic_filters:
        raise WisconsinOpinionsSelectionError(
            "unsupported_collection_filter",
            "One or more filters are not exposed by this collection",
            details={
                "collection": config.key,
                "unsupported_parameters": unavailable_dynamic_filters,
            },
        )
    if args.county or args.disposition:
        taxonomy_records, taxonomy_url = client.fetch_taxonomy(args.collection)
    if args.county:
        selection["trial_county"] = _taxonomy_value(
            taxonomy_records or (),
            field_name="trial_county",
            requested=args.county,
        )
    else:
        selection["trial_county"] = ""
    if args.disposition:
        selection["disp_code"] = _taxonomy_value(
            taxonomy_records or (),
            field_name="disp_code",
            requested=args.disposition,
        )
    else:
        selection["disp_code"] = ""
    unsupported = sorted(
        key
        for key, value in selection.items()
        if value and key not in config.supported_parameters
    )
    if unsupported:
        raise WisconsinOpinionsSelectionError(
            "unsupported_collection_filter",
            "One or more filters are not exposed by this collection",
            details={
                "collection": config.key,
                "unsupported_parameters": unsupported,
            },
        )
    selected = {
        key: value
        for key, value in selection.items()
        if key in config.supported_parameters and value
    }
    artifact_refs = (taxonomy_url,) if taxonomy_url else ()
    return selected, artifact_refs


def _keyword_query_text(args: argparse.Namespace) -> str:
    query_text = _text(args.query)
    if query_text is None:
        raise WisconsinOpinionsSelectionError(
            "missing_keyword_query",
            "A full-text search query is required",
        )
    if args.exact and not (
        query_text.startswith('"') and query_text.endswith('"')
    ):
        query_text = f'"{query_text}"'
    return query_text


def source_routes(case_number: str | None = None) -> list[dict[str, Any]]:
    normalized_case = (
        _normalized_case_number(_case_number(case_number))
        if case_number
        else None
    )
    encoded_case = (
        urlencode({"docket_number": normalized_case})
        if normalized_case
        else None
    )
    return [
        {
            "source_id": SOURCE_ID,
            "record_kind": "source_route",
            "name": "Wisconsin Court System appellate opinion indexes",
            "relationship": "authoritative_primary",
            "record_role": (
                "opinion and order metadata, full-text discovery, official PDFs, "
                "and incremental release feeds"
            ),
            "operations": [
                "search",
                "keyword",
                "feed",
                "taxonomy",
                "download",
            ],
            "coverage": (
                "Supreme Court opinions since September 1995 and Court of "
                "Appeals opinions since June 1995; separate Supreme orders and "
                "Court of Appeals summary dispositions"
            ),
            "join_keys": [
                "normalized_appellate_case_number",
                "native_pdf_seq_no_or_doc_id",
                "public_domain_citation",
            ],
            "source_url": OPINIONS_HOME_URL,
            "case_search_urls": (
                {
                    "supreme": (
                        f"{COLLECTIONS['supreme-opinions'].endpoint}?"
                        f"{encoded_case}"
                    ),
                    "appeals": (
                        f"{COLLECTIONS['appeals-opinions'].endpoint}?"
                        f"{encoded_case}"
                    ),
                }
                if encoded_case
                else None
            ),
        },
        {
            "source_id": "us-wi-wscca-public",
            "record_kind": "source_route",
            "name": "Wisconsin Supreme Court and Court of Appeals Case Access",
            "relationship": "official_complement",
            "record_role": (
                "appellate case identity, parties, counsel, docket events, "
                "linked circuit cases, briefs, and other available documents"
            ),
            "adds": (
                "Case lifecycle and filed-document context not present in the "
                "opinion indexes"
            ),
            "gaps": "Does not replace the official opinion publication index",
            "join_keys": [
                "normalized_appellate_case_number",
                "published_citation",
            ],
            "source_url": "https://wscca.wicourts.gov/",
            "case_url": (
                f"https://wscca.wicourts.gov/case/{normalized_case}"
                if normalized_case
                else None
            ),
            "rss_url": (
                f"https://wscca.wicourts.gov/rss/case/{normalized_case}"
                if normalized_case
                else None
            ),
        },
        {
            "source_id": "us-wi-wcca-public",
            "record_kind": "source_route",
            "name": "Wisconsin Circuit Court Access",
            "relationship": "official_lower_court_complement",
            "record_role": (
                "originating circuit-case metadata, docket entries, judgments, "
                "and calendars"
            ),
            "adds": "Trial-court chronology and judgment context",
            "join_keys": [
                "linked_circuit_case_number_from_wscca",
                "county",
                "party_name",
            ],
            "source_url": "https://wcca.wicourts.gov/",
        },
        {
            "source_id": "us-wi-state-law-library-briefs",
            "record_kind": "source_route",
            "name": "Wisconsin State Law Library briefs and document service",
            "relationship": "official_library_complement",
            "record_role": (
                "brief discovery and a copy/order route for appellate documents "
                "not available directly online"
            ),
            "join_keys": [
                "appellate_case_number",
                "published_citation",
                "party_name",
            ],
            "source_url": "https://wilawlibrary.gov/search/briefs.html",
            "request_url": "https://wilawlibrary.gov/services/order.html",
        },
        {
            "source_id": "us-wi-uw-law-historical-briefs",
            "record_kind": "source_route",
            "name": "UW Law historical Wisconsin briefs",
            "relationship": "institutional_repository_complement",
            "record_role": (
                "scanned briefs and appendices for decisions in 173 Wis. 2d "
                "through 317 Wis. 2d"
            ),
            "join_keys": [
                "wisconsin_reports_citation",
                "appellate_case_number",
                "party_name",
            ],
            "source_url": (
                "https://repository.law.wisc.edu/s/uwlaw/page/wisconsin-briefs"
            ),
        },
        {
            "source_id": "us-courtlistener-api",
            "record_kind": "source_route",
            "name": "CourtListener opinion collection",
            "relationship": "searchable_mirror",
            "record_role": (
                "cross-jurisdiction citation search, opinion text, and citation "
                "network pivots"
            ),
            "evidence_note": (
                "A mirrored copy of the same opinion is redundant retrieval, "
                "not independent corroboration"
            ),
            "join_keys": [
                "appellate_case_number",
                "public_domain_citation",
                "reporter_citation",
            ],
            "source_url": "https://www.courtlistener.com/",
        },
        {
            "source_id": "us-wi-appellate-clerk",
            "record_kind": "source_route",
            "name": "Clerk of the Supreme Court and Court of Appeals",
            "relationship": "official_request_complement",
            "record_role": (
                "verification and targeted record requests for documents not "
                "served by the public indexes or WSCCA"
            ),
            "join_keys": [
                "appellate_case_number",
                "document_description",
                "filing_or_issue_date",
            ],
            "source_url": (
                "https://www.wicourts.gov/courts/offices/clerkcontact.htm"
            ),
        },
    ]


def _query(
    operation: str,
    parameters: Mapping[str, Any],
    *,
    cursor: str | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            cursor=cursor,
        ),
    )


def _failure(
    query: PublicRecordsQuery,
    error: WisconsinOpinionsError,
    *,
    records: Sequence[Mapping[str, Any]] = (),
    next_cursor: str | None = None,
    raw_artifact_refs: Sequence[str] = (),
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
        raw_artifact_refs=raw_artifact_refs,
        warnings=SOURCE_WARNINGS,
    )


def _probe_records(
    client: WisconsinOpinionsClient | Any,
    *,
    component: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    artifacts: list[str] = []
    if component in {"all", "index"}:
        supreme_page = client.fetch_metadata_page(
            "supreme-opinions",
            {"docket_number": PROBE_SUPREME_CASE, "sortBy": "date"},
            page_number=1,
        )
        supreme_matches = [
            record
            for record in supreme_page.records
            if record["normalized_appellate_case_number"] == PROBE_SUPREME_CASE
            and record["caption"] == PROBE_SUPREME_CAPTION
        ]
        if not supreme_matches:
            raise WisconsinOpinionsSourceChangedError(
                "supreme_probe_sentinel_changed",
                "Wisconsin Supreme Court opinion sentinel did not match",
                details={
                    "case_number": PROBE_SUPREME_CASE,
                    "records_returned": len(supreme_page.records),
                },
            )
        appeals_page = client.fetch_metadata_page(
            "appeals-opinions",
            {"docket_number": PROBE_APPEALS_CASE, "sortBy": "date"},
            page_number=1,
        )
        appeals_matches = [
            record
            for record in appeals_page.records
            if record["normalized_appellate_case_number"] == PROBE_APPEALS_CASE
            and record["caption"] == PROBE_APPEALS_CAPTION
        ]
        if not appeals_matches:
            raise WisconsinOpinionsSourceChangedError(
                "appeals_probe_sentinel_changed",
                "Wisconsin Court of Appeals opinion sentinel did not match",
                details={
                    "case_number": PROBE_APPEALS_CASE,
                    "records_returned": len(appeals_page.records),
                },
            )
        records.extend(
            [
                {
                    **supreme_matches[0],
                    "probe_component": "supreme_metadata_index",
                },
                {
                    **appeals_matches[0],
                    "probe_component": "appeals_metadata_index",
                },
            ]
        )
        artifacts.extend([supreme_page.source_url, appeals_page.source_url])
    if component in {"all", "keyword"}:
        keyword_page = client.fetch_fulltext_page(
            "supreme",
            f'"{PROBE_SUPREME_CAPTION.split(" v. ", 1)[0]}"',
            page_number=1,
        )
        if not keyword_page.records:
            raise WisconsinOpinionsSourceChangedError(
                "keyword_probe_sentinel_changed",
                "Wisconsin Supreme Court full-text sentinel returned no hits",
            )
        records.append(
            {
                **keyword_page.records[0],
                "probe_component": "supreme_full_text",
                "probe_total_items": keyword_page.total_items,
            }
        )
        artifacts.append(keyword_page.source_url)
    if component in {"all", "feeds"}:
        for court in ("supreme", "appeals"):
            feed_records, feed_url = client.fetch_feed(court)
            if not feed_records:
                raise WisconsinOpinionsSourceChangedError(
                    "feed_probe_empty",
                    "Wisconsin opinion feed returned no current items",
                    details={"court": court},
                )
            records.append(
                {
                    "source_id": SOURCE_ID,
                    "record_kind": "source_probe",
                    "probe_component": f"{court}_rss",
                    "feed_url": feed_url,
                    "record_count": len(feed_records),
                    "newest_record": feed_records[0],
                }
            )
            artifacts.append(feed_url)
    if component in {"all", "pdf"}:
        pdf = client.fetch_pdf(PROBE_APPEALS_PDF_URL)
        if pdf.native_document_id != PROBE_APPEALS_DOCUMENT_ID:
            raise WisconsinOpinionsSourceChangedError(
                "pdf_probe_sentinel_changed",
                "Wisconsin Court of Appeals PDF sentinel changed identity",
                details={
                    "expected": PROBE_APPEALS_DOCUMENT_ID,
                    "observed": pdf.native_document_id,
                },
            )
        records.append(
            {
                "source_id": SOURCE_ID,
                "record_kind": "source_probe",
                "probe_component": "official_pdf",
                "source_url": pdf.source_url,
                "native_document_id": pdf.native_document_id,
                "native_document_id_type": pdf.native_document_id_type,
                "mime_type": pdf.media_type,
                "size_bytes": len(pdf.content),
                "sha256": pdf.sha256,
            }
        )
        artifacts.append(pdf.source_url)
    return records, artifacts


def execute(
    args: argparse.Namespace,
    *,
    client: WisconsinOpinionsClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    own_client = client is None
    source_client = client or WisconsinOpinionsClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )
    query = _query(args.command, {})
    result: PublicRecordsResult
    try:
        if args.command == "search":
            selection, taxonomy_refs = _metadata_selection(
                args,
                client=source_client,
            )
            parameters = {
                "collection": args.collection,
                **selection,
                "page": args.page,
                "all_pages": args.all_pages,
                "max_pages": args.max_pages,
            }
            query = _query(
                "search",
                parameters,
                cursor=(
                    f"metadata:{args.collection}:page:{args.page}"
                    if args.page > 1
                    else None
                ),
            )
            if args.all_pages:
                collection = source_client.fetch_all_metadata(
                    args.collection,
                    selection,
                    start_page=args.page,
                    max_pages=args.max_pages,
                )
                artifact_refs = [*taxonomy_refs, *collection.source_urls]
                if collection.incomplete_error is not None:
                    result = _failure(
                        query,
                        collection.incomplete_error,
                        records=collection.records,
                        next_cursor=collection.next_cursor,
                        raw_artifact_refs=artifact_refs,
                    )
                else:
                    result = PublicRecordsResult.success(
                        query,
                        collection.records,
                        next_cursor=collection.next_cursor,
                        raw_artifact_refs=artifact_refs,
                        warnings=SOURCE_WARNINGS,
                    )
            else:
                page = source_client.fetch_metadata_page(
                    args.collection,
                    selection,
                    page_number=args.page,
                )
                result = PublicRecordsResult.success(
                    query,
                    page.records,
                    next_cursor=(
                        f"metadata:{args.collection}:page:{page.next_page}"
                        if page.next_page is not None
                        else None
                    ),
                    raw_artifact_refs=[*taxonomy_refs, page.source_url],
                    warnings=SOURCE_WARNINGS,
                )
        elif args.command == "keyword":
            query_text = _keyword_query_text(args)
            parameters = {
                "court": args.court,
                "query": query_text,
                "page": args.page,
                "all_pages": args.all_pages,
                "max_pages": args.max_pages,
            }
            query = _query(
                "keyword",
                parameters,
                cursor=(
                    f"fulltext:{args.court}:offset:"
                    f"{(args.page - 1) * FULLTEXT_PAGE_SIZE}"
                    if args.page > 1
                    else None
                ),
            )
            if args.all_pages:
                collection = source_client.fetch_all_fulltext(
                    args.court,
                    query_text,
                    start_page=args.page,
                    max_pages=args.max_pages,
                )
                if collection.incomplete_error is not None:
                    result = _failure(
                        query,
                        collection.incomplete_error,
                        records=collection.records,
                        next_cursor=collection.next_cursor,
                        raw_artifact_refs=collection.source_urls,
                    )
                else:
                    result = PublicRecordsResult.success(
                        query,
                        collection.records,
                        next_cursor=collection.next_cursor,
                        raw_artifact_refs=collection.source_urls,
                        warnings=SOURCE_WARNINGS,
                    )
            else:
                page = source_client.fetch_fulltext_page(
                    args.court,
                    query_text,
                    page_number=args.page,
                )
                result = PublicRecordsResult.success(
                    query,
                    page.records,
                    next_cursor=(
                        f"fulltext:{args.court}:offset:{page.next_offset}"
                        if page.next_offset is not None
                        else None
                    ),
                    raw_artifact_refs=[page.source_url],
                    warnings=SOURCE_WARNINGS,
                )
        elif args.command == "feed":
            query = _query("feed", {"court": args.court})
            records, source_url = source_client.fetch_feed(args.court)
            result = PublicRecordsResult.success(
                query,
                records,
                raw_artifact_refs=[source_url],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "taxonomy":
            query = _query("taxonomy", {"collection": args.collection})
            records, source_url = source_client.fetch_taxonomy(args.collection)
            result = PublicRecordsResult.success(
                query,
                records,
                raw_artifact_refs=[source_url],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "download":
            safe_url = _official_pdf_url(args.url)
            query = _query(
                "download",
                {
                    "url": safe_url,
                    "destination": str(args.destination),
                },
            )
            pdf = source_client.fetch_pdf(safe_url)
            args.destination.parent.mkdir(parents=True, exist_ok=True)
            args.destination.write_bytes(pdf.content)
            record = {
                "canonical_ref": (
                    f"WICOURTS-PDF:{pdf.native_document_id or pdf.sha256}"
                ),
                "source_id": SOURCE_ID,
                "record_kind": "document_artifact",
                "document_type": "appellate_opinion_or_order",
                "native_document_id": pdf.native_document_id,
                "native_document_id_type": pdf.native_document_id_type,
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
                raw_artifact_refs=[str(args.destination), pdf.source_url],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "routes":
            parameters = {
                "case_number": (
                    _case_number(args.case_number)
                    if args.case_number
                    else None
                )
            }
            query = _query("routes", parameters)
            result = PublicRecordsResult.success(
                query,
                source_routes(args.case_number),
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            query = _query("probe", {"component": args.component})
            records, artifacts = _probe_records(
                source_client,
                component=args.component,
            )
            result = PublicRecordsResult.success(
                query,
                records,
                raw_artifact_refs=artifacts,
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise AssertionError(f"unknown command: {args.command}")
    except WisconsinOpinionsError as error:
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
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=DEFAULT_RETRY_BACKOFF,
    )
    add_output_args(parser)


def _add_paging(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--page",
        type=int,
        default=1,
        help="One-based native page number",
    )
    parser.add_argument(
        "--all-pages",
        action="store_true",
        help="Traverse every remaining matching native page",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Optional number of pages to fetch during --all-pages traversal",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Wisconsin appellate opinions, orders, full text, "
            "PDFs, and RSS feeds"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser(
        "search",
        help="Search a metadata index and return official PDF links",
    )
    search.add_argument(
        "--collection",
        choices=tuple(COLLECTIONS),
        default="appeals-opinions",
    )
    search.add_argument("--case-number")
    search.add_argument("--party")
    search.add_argument("--date-from")
    search.add_argument("--date-to")
    search.add_argument("--final-publication-from")
    search.add_argument("--final-publication-to")
    search.add_argument("--judge")
    search.add_argument(
        "--county",
        help="Current source county label or native numeric value",
    )
    search.add_argument("--district", choices=("1", "2", "3", "4"))
    search.add_argument(
        "--disposition",
        help="Current source disposition label or native code",
    )
    search.add_argument(
        "--citation-type",
        choices=("none", "nw2d", "wis2d"),
        default="none",
    )
    search.add_argument("--citation-page")
    search.add_argument("--citation-volume")
    search.add_argument("--public-domain-citation")
    search.add_argument("--sort", choices=("date", "docket"))
    _add_paging(search)
    _add_runtime_and_output(search)

    keyword = subparsers.add_parser(
        "keyword",
        help="Search the body of official Supreme Court or appellate opinions",
    )
    keyword.add_argument("query")
    keyword.add_argument(
        "--court",
        choices=tuple(FULLTEXT_COLLECTIONS),
        default="appeals",
    )
    keyword.add_argument(
        "--exact",
        action="store_true",
        help="Wrap an unquoted query as an exact phrase",
    )
    _add_paging(keyword)
    _add_runtime_and_output(keyword)

    feed = subparsers.add_parser(
        "feed",
        help="Read the official incremental opinion RSS feed",
    )
    feed.add_argument(
        "--court",
        choices=tuple(FEED_URLS),
        default="appeals",
    )
    _add_runtime_and_output(feed)

    taxonomy = subparsers.add_parser(
        "taxonomy",
        help="Read the current official form fields and option values",
    )
    taxonomy.add_argument(
        "--collection",
        choices=tuple(COLLECTIONS),
        default="appeals-opinions",
    )
    _add_runtime_and_output(taxonomy)

    download = subparsers.add_parser(
        "download",
        help="Download and hash one official opinion or order PDF",
    )
    download.add_argument("url")
    download.add_argument("destination", type=Path)
    _add_runtime_and_output(download)

    routes = subparsers.add_parser(
        "routes",
        help="Describe official complements and join keys by record role",
    )
    routes.add_argument("--case-number")
    _add_runtime_and_output(routes)

    probe = subparsers.add_parser(
        "probe",
        help="Run bounded source-schema and document sentinel probes",
    )
    probe.add_argument(
        "--component",
        choices=("all", "index", "keyword", "feeds", "pdf"),
        default="all",
    )
    _add_runtime_and_output(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Wisconsin appellate {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Wisconsin appellate {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        label = (
            record.get("raw_case_number")
            or record.get("field_name")
            or record.get("name")
            or record.get("probe_component")
            or record.get("source_url")
            or "record"
        )
        detail = (
            record.get("caption")
            or record.get("native_title")
            or record.get("record_role")
            or record.get("collection")
            or ""
        )
        print(f"  {label} | {detail}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    args = build_parser().parse_args()
    if getattr(args, "page", 1) < 1:
        raise SystemExit("--page must be at least 1")
    if (
        getattr(args, "max_pages", None) is not None
        and args.max_pages < 1
    ):
        raise SystemExit("--max-pages must be positive")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.minimum_interval < 0:
        raise SystemExit("--minimum-interval must not be negative")
    if args.max_attempts < 1:
        raise SystemExit("--max-attempts must be at least 1")
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
