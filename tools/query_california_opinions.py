#!/usr/bin/env python3
"""Query current California appellate opinion publication pages.

The Judicial Branch publishes two server-rendered, anonymously accessible
collections:

* published/citable slip opinions from the last 120 days; and
* unpublished/non-citable opinions from the last 60 days.

The adapter preserves those publication states and does not treat a published
slip opinion as the corrected Official Reports version.  Older opinions remain
discoverable through Appellate Case Information, while the official no-fee
Lexis service supplies corrected Official Reports opinions from 1850 onward.

Examples:
    uv run python tools/query_california_opinions.py manifest --json
    uv run python tools/query_california_opinions.py search \
        --collection unpublished --case-number H052909 --json
    uv run python tools/query_california_opinions.py search \
        --collection published --court supreme --title Sanmiguel --json
    uv run python tools/query_california_opinions.py detail \
        https://courts.ca.gov/opinion/unpublished/2026-07-30/h052909 --json
    uv run python tools/query_california_opinions.py citings \
        https://courts.ca.gov/opinion/citings-archive/2026-07-30/s287786 --json
    uv run python tools/query_california_opinions.py download \
        https://www.courts.ca.gov/opinions/documents/S287786.PDF \
        /tmp/S287786.PDF --json
    uv run python tools/query_california_opinions.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, quote, urljoin, urlsplit

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


SOURCE_ID = "us-ca-judicial-branch-opinions"
STATE_CODE = "CA"
STATE_GEOID = "06"
BASE_URL = "https://courts.ca.gov"
PUBLISHED_URL = f"{BASE_URL}/opinions/publishedcitable-opinions"
UNPUBLISHED_URL = f"{BASE_URL}/opinions/unpublishednon-citable-opinions"
OPINIONS_HOME_URL = f"{BASE_URL}/opinions"
OFFICIAL_REPORTS_GUIDE_URL = f"{BASE_URL}/opinions/official-reports"
OFFICIAL_REPORTS_SEARCH_URL = "https://www.lexisnexis.com/clients/CACourts/"
APPELLATE_CASE_INFORMATION_URL = "https://appellatecases.courtinfo.ca.gov/"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.35
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_LIMIT = 50
DEFAULT_PAGE_SIZE = 50
PAGE_SIZE_CHOICES = (50, 100, 200)
MAXIMUM_HTML_BYTES = 16 * 1024 * 1024
MAXIMUM_DOCUMENT_BYTES = 160 * 1024 * 1024
OUTPUT_SCHEMA_VERSION = "california-judicial-branch-opinions/1.0"
CURSOR_PREFIX = "ca-opinions:v1:"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

COLLECTIONS: Mapping[str, Mapping[str, Any]] = {
    "published": {
        "url": PUBLISHED_URL,
        "publication_status": "published",
        "source_label": "Published Opinion",
        "window_days": 120,
        "document_version": "slip_opinion_as_filed",
        "citation_status": "citable",
        "pdf_path_prefix": "/opinions/documents/",
    },
    "unpublished": {
        "url": UNPUBLISHED_URL,
        "publication_status": "unpublished",
        "source_label": "Unpublished Opinion",
        "window_days": 60,
        "document_version": "unpublished_opinion_as_filed",
        "citation_status": "generally_non_citable_under_rule_8_1115",
        "pdf_path_prefix": "/opinions/nonpub/",
    },
}

COURTS: Mapping[str, Mapping[str, Any]] = {
    "103": {
        "slug": "supreme",
        "name": "Supreme Court",
        "court_id": "ca-supreme-court",
        "collections": ("published",),
    },
    "100": {
        "slug": "appeal-1",
        "name": "1st District Court of Appeal",
        "court_id": "ca-court-of-appeal-1",
        "collections": ("published", "unpublished"),
    },
    "102": {
        "slug": "appeal-2",
        "name": "2nd District Court of Appeal",
        "court_id": "ca-court-of-appeal-2",
        "collections": ("published", "unpublished"),
    },
    "107": {
        "slug": "appeal-3",
        "name": "3rd District Court of Appeal",
        "court_id": "ca-court-of-appeal-3",
        "collections": ("published", "unpublished"),
    },
    "106": {
        "slug": "appeal-4-1",
        "name": "4th District Court of Appeal, Division One",
        "court_id": "ca-court-of-appeal-4-division-1",
        "collections": ("published", "unpublished"),
    },
    "98": {
        "slug": "appeal-4-2",
        "name": "4th District Court of Appeal, Division Two",
        "court_id": "ca-court-of-appeal-4-division-2",
        "collections": ("published", "unpublished"),
    },
    "101": {
        "slug": "appeal-4-3",
        "name": "4th District Court of Appeal, Division Three",
        "court_id": "ca-court-of-appeal-4-division-3",
        "collections": ("published", "unpublished"),
    },
    "99": {
        "slug": "appeal-5",
        "name": "5th District Court of Appeal",
        "court_id": "ca-court-of-appeal-5",
        "collections": ("published", "unpublished"),
    },
    "105": {
        "slug": "appeal-6",
        "name": "6th District Court of Appeal",
        "court_id": "ca-court-of-appeal-6",
        "collections": ("published", "unpublished"),
    },
    "104": {
        "slug": "appellate-division",
        "name": "Appellate Division",
        "court_id": "ca-superior-court-appellate-division",
        "collections": ("published",),
    },
}
COURT_ID_BY_ALIAS = {
    alias.casefold(): native_id
    for native_id, spec in COURTS.items()
    for alias in (
        native_id,
        str(spec["slug"]),
        str(spec["name"]),
        str(spec["court_id"]),
    )
}
COURT_ID_BY_NAME = {
    str(spec["name"]).casefold(): native_id
    for native_id, spec in COURTS.items()
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="California Judicial Branch Opinions",
    source_role=(
        "official_current_published_slip_and_unpublished_appellate_opinion_index"
    ),
    base_url=OPINIONS_HOME_URL,
    dataset_id="california-judicial-branch-opinions",
    metadata={
        "authority": "Judicial Council of California",
        "operator": "Judicial Council of California",
        "state_code": STATE_CODE,
        "authentication": "none",
        "adapter_family": "california_judicial_branch_opinion_index",
        "native_page_sizes": list(PAGE_SIZE_CHOICES),
        "native_page_numbering": "zero_based_query_one_based_display",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="California",
    state_code=STATE_CODE,
)

SOURCE_WARNINGS = (
    "The published collection contains as-filed slip opinions from the last "
    "120 days; it does not contain the corrected Official Reports text.",
    "The unpublished collection contains opinions from the last 60 days and "
    "identifies them as generally non-citable under California Rule of Court "
    "8.1115.",
    "The two current collections are publication indexes, not complete "
    "appellate dockets or filing sets.",
    "Collection paging is mutable as new opinions are posted; continuation "
    "cursors verify the page fingerprint before resuming within a page.",
)

_COUNT_RE = re.compile(
    r"(?P<start>[\d,]+)\s*-\s*(?P<end>[\d,]+)\s+of\s+"
    r"(?P<total>[\d,]+)\s+results",
    re.IGNORECASE,
)
_NOTATION_RE = re.compile(
    r"^(?P<court>.+?)\s*[•·]\s*"
    r"(?P<label>Published|Unpublished)\s+Opinion$",
    re.IGNORECASE,
)
_DETAIL_PATH_RE = re.compile(
    r"^/opinion/(?P<collection>published|unpublished)/"
    r"(?P<date>\d{4}-\d{2}-\d{2})/(?P<case>[A-Za-z0-9.-]+)$",
    re.IGNORECASE,
)
_CITINGS_PATH_RE = re.compile(
    r"^/opinion/citings-archive/(?P<date>\d{4}-\d{2}-\d{2})/"
    r"(?P<case>[A-Za-z0-9.-]+)$",
    re.IGNORECASE,
)
_DOCUMENT_PATH_RE = re.compile(
    r"^/opinions/(?P<family>documents|nonpub)/"
    r"(?P<case>[A-Za-z0-9.-]+)\.(?P<format>PDF|DOCX)$",
    re.IGNORECASE,
)
_CITING_ARCHIVE_PATH_RE = re.compile(
    r"^/system/files/opinion-citing/[A-Za-z0-9._-]+\.pdf$",
    re.IGNORECASE,
)
_CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "challenges.cloudflare.com",
)


class CaliforniaOpinionsError(RuntimeError):
    """Source transport, schema, access, cursor, or selector failure."""

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


class SelectionError(CaliforniaOpinionsError):
    """The caller supplied a selector outside the verified source contract."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "invalid_selection",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            category="query_selection",
            details=details,
        )


class SourceChangedError(CaliforniaOpinionsError):
    """The official HTML no longer matches the verified source contract."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "source_schema_changed",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details=details,
        )


class CursorError(SelectionError):
    """A continuation cursor is malformed, mismatched, or stale."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "invalid_cursor",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


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
class OpinionPage:
    collection: str
    source_url: str
    page_index: int
    page_size: int
    total_count: int
    total_pages: int
    showing_start: int
    showing_end: int
    records: tuple[Mapping[str, Any], ...]
    source_taxonomy: Mapping[str, str]
    schema_fingerprint: str
    page_fingerprint: str
    source_document_sha256: str

    @property
    def has_next(self) -> bool:
        return self.page_index + 1 < self.total_pages


@dataclass(frozen=True)
class SearchOutcome:
    records: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    raw_artifact_refs: tuple[str, ...]


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    result = " ".join(str(value).replace("\x00", "").split()).strip()
    return result or None


def _required(value: Any, field_name: str) -> str:
    result = _clean(value)
    if result is None:
        raise SourceChangedError(
            f"California opinion {field_name} is blank",
            details={"field": field_name},
        )
    return result


def _parse_date(value: str, field_name: str) -> str:
    try:
        return datetime.strptime(value, "%B %d, %Y").date().isoformat()
    except ValueError as error:
        raise SourceChangedError(
            f"California opinion {field_name} has an unexpected date",
            details={"field": field_name, "value": value},
        ) from error


def _integer(value: str) -> int:
    return int(value.replace(",", ""))


def _media_type(response: Any) -> str | None:
    headers = getattr(response, "headers", {})
    raw = headers.get("Content-Type", headers.get("content-type"))
    if raw is None:
        return None
    return str(raw).split(";", 1)[0].strip().casefold() or None


def _retry_after(response: Any) -> float | None:
    headers = getattr(response, "headers", {})
    raw = headers.get("Retry-After", headers.get("retry-after"))
    try:
        return max(0.0, float(raw)) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _official_site_url(value: str) -> str:
    candidate = urljoin(BASE_URL, value)
    parsed = urlsplit(candidate)
    hostname = (parsed.hostname or "").casefold()
    if (
        parsed.scheme != "https"
        or not (
            hostname == "courts.ca.gov"
            or hostname.endswith(".courts.ca.gov")
        )
    ):
        raise SelectionError(
            "Opinion retrieval requires an official California Courts HTTPS URL",
            code="unrecognized_official_url",
            details={"url": value},
        )
    return candidate


def _detail_url_parts(value: str) -> tuple[str, str, str, str]:
    candidate = _official_site_url(value)
    parsed = urlsplit(candidate)
    match = _DETAIL_PATH_RE.fullmatch(parsed.path.rstrip("/"))
    if match is None:
        raise SelectionError(
            "Detail URL must be an official published or unpublished opinion route",
            code="unrecognized_detail_url",
            details={"url": value},
        )
    return (
        candidate,
        match.group("collection").casefold(),
        match.group("date"),
        match.group("case").upper(),
    )


def _citings_url_parts(value: str) -> tuple[str, str, str]:
    candidate = _official_site_url(value)
    parsed = urlsplit(candidate)
    match = _CITINGS_PATH_RE.fullmatch(parsed.path.rstrip("/"))
    if match is None:
        raise SelectionError(
            "Citings URL must use the official opinion citings-archive route",
            code="unrecognized_citings_url",
            details={"url": value},
        )
    return candidate, match.group("date"), match.group("case").upper()


def _document_url_parts(value: str) -> tuple[str, str, str, str]:
    candidate = _official_site_url(value)
    parsed = urlsplit(candidate)
    match = _DOCUMENT_PATH_RE.fullmatch(parsed.path)
    if match is None:
        raise SelectionError(
            "Document URL must use an official opinion PDF or DOCX path",
            code="unrecognized_document_url",
            details={"url": value},
        )
    family = match.group("family").casefold()
    collection = "published" if family == "documents" else "unpublished"
    return (
        candidate,
        collection,
        match.group("case").upper(),
        match.group("format").casefold(),
    )


def _case_information_url(
    value: str,
    opinion_identifier: str,
) -> tuple[str, str]:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "appellatecases.courtinfo.ca.gov"
    ):
        raise SourceChangedError(
            "Opinion card case link left Appellate Case Information",
            details={"url": value},
        )
    query_case = (
        _clean(
            parse_qs(parsed.query).get(
                "query_caseNumber",
                [None],
            )[0]
        )
        or ""
    ).upper()
    identifier = opinion_identifier.upper()
    same_case = query_case == identifier
    suffixed_artifact = bool(
        query_case
        and re.fullmatch(
            rf"{re.escape(query_case)}[A-Z]{{1,3}}",
            identifier,
        )
    )
    if not same_case and not suffixed_artifact:
        raise SourceChangedError(
            "Opinion card case link identifies a different case",
            details={
                "opinion_identifier": opinion_identifier,
                "observed_case_number": query_case,
            },
        )
    return value, query_case


def _court_native_id(value: str | None) -> str | None:
    if value is None:
        return None
    native_id = COURT_ID_BY_ALIAS.get(value.strip().casefold())
    if native_id is None:
        raise SelectionError(
            "Unknown California opinion source/court selector",
            details={
                "court": value,
                "accepted": sorted(
                    {
                        str(spec["slug"])
                        for spec in COURTS.values()
                    }
                    | set(COURTS)
                ),
            },
        )
    return native_id


def _collection_names(value: str, court_native_id: str | None) -> tuple[str, ...]:
    requested = (
        ("published", "unpublished")
        if value == "both"
        else (value,)
    )
    if court_native_id is None:
        return requested
    supported = set(COURTS[court_native_id]["collections"])
    selected = tuple(item for item in requested if item in supported)
    if not selected:
        raise SelectionError(
            "Selected court is not present in the selected opinion collection",
            details={
                "court": court_native_id,
                "collection": value,
                "supported_collections": sorted(supported),
            },
        )
    return selected


def _canonical_opinion_ref(
    *,
    court_id: str,
    case_number: str,
    decision_date: str,
) -> str:
    return canonical_court_ref(
        SOURCE_ID,
        court_id,
        case_number,
        "opinion",
        decision_date,
    )


def _canonical_document_ref(
    *,
    case_number: str,
    document_format: str,
) -> str:
    return (
        "CAOPINION:"
        f"{quote(SOURCE_ID, safe='.-_')}/"
        f"{quote(case_number, safe='.-_')}/"
        f"{quote(document_format, safe='.-_')}"
    )


class CaliforniaOpinionsClient:
    """Bounded, retrying client with an injectable requests-like session."""

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
        self._owns_session = session is None
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=DEFAULT_MAX_ATTEMPTS
        )
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        self.sleeper = sleeper

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        accept: str = "text/html,application/xhtml+xml",
        maximum_bytes: int = MAXIMUM_HTML_BYTES,
    ) -> Artifact:
        safe_url = _official_site_url(url)
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    "GET",
                    safe_url,
                    params=dict(params or {}),
                    headers={
                        "Accept": accept,
                        "Accept-Language": "en-US,en;q=0.9",
                        "User-Agent": DEFAULT_USER_AGENT,
                    },
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise CaliforniaOpinionsError(
                    "transport_error",
                    str(error),
                    category="transport",
                    retryable=True,
                    details={"url": safe_url},
                ) from error

            status_code = int(getattr(response, "status_code", 0))
            if (
                status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(
                    self.retry_policy.delay(attempt, _retry_after(response))
                )
                continue
            if status_code == 429:
                raise CaliforniaOpinionsError(
                    "rate_limited",
                    "California Courts rate limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="rate_limit",
                    retryable=True,
                    details={"url": safe_url, "status_code": status_code},
                )
            if status_code in {401, 403}:
                raise CaliforniaOpinionsError(
                    "access_restricted",
                    f"California Courts returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"url": safe_url, "status_code": status_code},
                )
            if status_code < 200 or status_code >= 300:
                raise CaliforniaOpinionsError(
                    "http_status",
                    f"California Courts returned HTTP {status_code}",
                    category="http",
                    retryable=status_code >= 500,
                    details={"url": safe_url, "status_code": status_code},
                )

            content = bytes(getattr(response, "content", b""))
            if not content and getattr(response, "text", None):
                content = str(response.text).encode("utf-8")
            if len(content) > maximum_bytes:
                raise CaliforniaOpinionsError(
                    "response_too_large",
                    "California Courts response exceeds the configured bound",
                    category="response_size",
                    details={
                        "url": safe_url,
                        "maximum_bytes": maximum_bytes,
                        "observed_bytes": len(content),
                    },
                )
            prepared_url = requests.Request(
                "GET",
                safe_url,
                params=dict(params or {}),
            ).prepare().url
            final_url = str(
                getattr(response, "url", None) or prepared_url or safe_url
            )
            _official_site_url(final_url)
            media_type = _media_type(response)
            lowered = content[:500_000].decode(
                "utf-8",
                errors="ignore",
            ).casefold()
            if any(marker in lowered for marker in _CHALLENGE_MARKERS):
                raise CaliforniaOpinionsError(
                    "human_verification",
                    "California Courts returned a verification page",
                    status=ResultStatus.HUMAN_REQUIRED,
                    category="access",
                    details={"url": final_url},
                )
            return Artifact(
                content=content,
                source_url=final_url,
                media_type=media_type,
                headers={
                    str(key): str(value)
                    for key, value in getattr(response, "headers", {}).items()
                },
            )
        raise CaliforniaOpinionsError(
            "transport_error",
            str(last_error or "request failed"),
            category="transport",
            retryable=True,
            details={"url": safe_url},
        )

    def listing(
        self,
        collection: str,
        *,
        page: int,
        page_size: int,
        court_native_id: str | None = None,
        case_number: str | None = None,
        title: str | None = None,
    ) -> Artifact:
        config = COLLECTIONS[collection]
        params: dict[str, str] = {
            "items_per_page": str(page_size),
            "page": str(page),
        }
        if court_native_id is not None:
            params["field_opinion_source_target_id"] = court_native_id
        if case_number:
            params["field_case_number_plain_value"] = case_number
        if title:
            params["title"] = title
        return self.get(str(config["url"]), params=params)

    def detail(self, url: str) -> Artifact:
        safe_url, _collection, _date, _case = _detail_url_parts(url)
        return self.get(safe_url)

    def citings(self, url: str) -> Artifact:
        safe_url, _date, _case = _citings_url_parts(url)
        return self.get(safe_url)

    def document(self, url: str) -> Artifact:
        safe_url, collection, case_number, document_format = (
            _document_url_parts(url)
        )
        artifact = self.get(
            safe_url,
            accept=(
                "application/pdf,"
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document,"
                "application/octet-stream"
            ),
            maximum_bytes=MAXIMUM_DOCUMENT_BYTES,
        )
        (
            _final_url,
            final_collection,
            final_case_number,
            final_document_format,
        ) = _document_url_parts(artifact.source_url)
        if (
            final_collection != collection
            or final_case_number != case_number
            or final_document_format != document_format
        ):
            raise SourceChangedError(
                "Opinion document redirect changed the requested artifact",
                details={
                    "requested_url": safe_url,
                    "final_url": artifact.source_url,
                },
            )
        return artifact


def _taxonomy(root: Tag, collection: str) -> dict[str, str]:
    select = root.select_one(
        'select[name="field_opinion_source_target_id"]'
    )
    if select is None:
        return {}
    observed = {
        str(option.get("value")): _required(
            option.get_text(" ", strip=True),
            "court filter label",
        )
        for option in select.select("option[value]")
        if str(option.get("value")) != "All"
    }
    expected = {
        native_id: str(spec["name"])
        for native_id, spec in COURTS.items()
        if collection in spec["collections"]
    }
    mismatches = {
        native_id: {
            "expected": expected.get(native_id),
            "observed": label,
        }
        for native_id, label in observed.items()
        if expected.get(native_id) != label
    }
    if mismatches:
        raise SourceChangedError(
            "California opinion source taxonomy changed",
            details={
                "collection": collection,
                "mismatches": mismatches,
                "observed": observed,
            },
        )
    return observed


def _card_link(
    card: Tag,
    *,
    text: str | None = None,
    path_pattern: re.Pattern[str] | None = None,
) -> str | None:
    for link in card.select("a[href]"):
        label = _clean(link.get_text(" ", strip=True))
        candidate = urljoin(BASE_URL, str(link["href"]))
        if text is not None and (label or "").casefold() != text.casefold():
            continue
        if (
            path_pattern is not None
            and path_pattern.fullmatch(urlsplit(candidate).path.rstrip("/"))
            is None
        ):
            continue
        return candidate
    return None


def _parse_listing_card(
    card: Tag,
    *,
    collection: str,
    source_url: str,
    page_index: int,
    page_item_index: int,
    source_document_sha256: str,
) -> dict[str, Any]:
    config = COLLECTIONS[collection]
    opinion_identifier = _required(
        (
            card.select_one(".result-excerpt__brow-primary").get_text(
                " ",
                strip=True,
            )
            if card.select_one(".result-excerpt__brow-primary")
            else None
        ),
        "case number",
    ).upper()
    decision_date_raw = _required(
        (
            card.select_one(".result-excerpt__brow-secondary").get_text(
                " ",
                strip=True,
            )
            if card.select_one(".result-excerpt__brow-secondary")
            else None
        ),
        "filing date",
    )
    decision_date = _parse_date(decision_date_raw, "filing date")
    notation = _required(
        (
            card.select_one(".result-excerpt__brow-notation").get_text(
                " ",
                strip=True,
            )
            if card.select_one(".result-excerpt__brow-notation")
            else None
        ),
        "court and publication label",
    )
    notation_match = _NOTATION_RE.fullmatch(notation)
    if notation_match is None:
        raise SourceChangedError(
            "California opinion court/publication notation changed",
            details={"notation": notation},
        )
    court_name = _clean(notation_match.group("court"))
    label = f"{notation_match.group('label').title()} Opinion"
    if label != config["source_label"]:
        raise SourceChangedError(
            "Opinion publication label does not match its collection",
            details={
                "collection": collection,
                "expected": config["source_label"],
                "observed": label,
            },
        )
    court_native_id = COURT_ID_BY_NAME.get((court_name or "").casefold())
    if court_native_id is None:
        raise SourceChangedError(
            "Opinion card contains an unknown court label",
            details={"collection": collection, "court_name": court_name},
        )
    court_spec = COURTS[court_native_id]
    if collection not in court_spec["collections"]:
        raise SourceChangedError(
            "Opinion card court is outside the collection taxonomy",
            details={
                "collection": collection,
                "court_native_id": court_native_id,
            },
        )

    title_link = card.select_one(".result-excerpt__heading a[href]")
    if title_link is None:
        raise SourceChangedError(
            "Opinion card lacks its case-information title link",
            details={"opinion_identifier": opinion_identifier},
        )
    title = _required(title_link.get_text(" ", strip=True), "title")
    case_information_url, appellate_case_number = _case_information_url(
        str(title_link["href"]),
        opinion_identifier,
    )

    pdf_url = _card_link(card, text="PDF")
    if pdf_url is None:
        raise SourceChangedError(
            "Opinion card lacks its PDF link",
            details={"opinion_identifier": opinion_identifier},
        )
    (
        pdf_url,
        pdf_collection,
        pdf_case_number,
        pdf_format,
    ) = _document_url_parts(pdf_url)
    if (
        pdf_collection != collection
        or pdf_case_number != opinion_identifier
        or pdf_format != "pdf"
    ):
        raise SourceChangedError(
            "Opinion PDF link disagrees with its index card",
            details={
                "collection": collection,
                "opinion_identifier": opinion_identifier,
                "pdf_url": pdf_url,
            },
        )

    detail_url = _card_link(card, path_pattern=_DETAIL_PATH_RE)
    if detail_url is None:
        raise SourceChangedError(
            "Opinion card lacks its other-formats detail link",
            details={"opinion_identifier": opinion_identifier},
        )
    (
        detail_url,
        detail_collection,
        detail_date,
        detail_case_number,
    ) = _detail_url_parts(detail_url)
    if (
        detail_collection != collection
        or detail_date != decision_date
        or detail_case_number != opinion_identifier
    ):
        raise SourceChangedError(
            "Opinion detail link disagrees with its index card",
            details={
                "collection": collection,
                "opinion_identifier": opinion_identifier,
                "decision_date": decision_date,
                "detail_url": detail_url,
            },
        )

    citings_archive_url = _card_link(
        card,
        path_pattern=_CITINGS_PATH_RE,
    )
    if citings_archive_url is not None:
        (
            citings_archive_url,
            citings_date,
            citings_case_number,
        ) = _citings_url_parts(citings_archive_url)
        if (
            citings_date != decision_date
            or citings_case_number != opinion_identifier
        ):
            raise SourceChangedError(
                "Opinion citings link disagrees with its index card",
                details={
                    "opinion_identifier": opinion_identifier,
                    "citings_archive_url": citings_archive_url,
                },
            )

    canonical_ref = _canonical_opinion_ref(
        court_id=str(court_spec["court_id"]),
        case_number=appellate_case_number,
        decision_date=decision_date,
    )
    return {
        "record_kind": "appellate_opinion_index_entry",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": SOURCE_ID,
        "case_number": appellate_case_number,
        "appellate_case_number": appellate_case_number,
        "opinion_identifier": opinion_identifier,
        "opinion_identifier_suffix": (
            opinion_identifier[len(appellate_case_number) :]
            if opinion_identifier != appellate_case_number
            else None
        ),
        "title": title,
        "decision_date": decision_date,
        "decision_date_raw": decision_date_raw,
        "collection": collection,
        "publication_status": config["publication_status"],
        "publication_label": config["source_label"],
        "document_version": config["document_version"],
        "citation_status": config["citation_status"],
        "court": {
            "court_id": court_spec["court_id"],
            "native_filter_id": court_native_id,
            "name": court_spec["name"],
            "state_code": STATE_CODE,
            "level": (
                "supreme"
                if court_native_id == "103"
                else "appellate"
            ),
        },
        "documents": [
            {
                "format": "pdf",
                "url": pdf_url,
                "media_type": "application/pdf",
                "version": config["document_version"],
            }
        ],
        "detail_url": detail_url,
        "case_information_url": case_information_url,
        "citings_archive_url": citings_archive_url,
        "corrected_official_reports_text_included": False,
        "official_reports_search_url": OFFICIAL_REPORTS_SEARCH_URL,
        "source_scope": {
            "current_window_days": config["window_days"],
            "complete_appellate_docket": False,
            "complete_filing_set": False,
            "opinion_publication": True,
        },
        "projection": {
            "projectable_as_case": False,
            "reason": "opinion_publication_is_not_a_complete_case_docket",
        },
        "join_keys": {
            "case_number": appellate_case_number,
            "opinion_identifier": opinion_identifier,
            "decision_date": decision_date,
            "court_id": court_spec["court_id"],
        },
        "source_url": detail_url,
        "provenance": {
            "index_url": source_url,
            "native_page_index": page_index,
            "page_item_index": page_item_index,
            "source_document_sha256": source_document_sha256,
        },
    }


def parse_listing_page(
    artifact: Artifact,
    *,
    collection: str,
    requested_page: int,
    requested_page_size: int,
) -> OpinionPage:
    """Parse and validate one official server-rendered listing page."""

    if collection not in COLLECTIONS:
        raise SelectionError(
            "Unknown California opinion collection",
            details={"collection": collection},
        )
    html = artifact.content.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(f".view-results.opinions.{collection}")
    if root is None:
        raise SourceChangedError(
            "California opinion page lacks its collection view",
            details={
                "collection": collection,
                "source_url": artifact.source_url,
            },
        )
    form = root.select_one("form.views-exposed-form")
    if form is None or str(form.get("method", "")).casefold() != "get":
        raise SourceChangedError(
            "California opinion collection lacks its GET filter form",
            details={"collection": collection},
        )
    field_names = {
        str(node.get("name"))
        for node in form.select("input[name], select[name]")
        if node.get("name")
    }
    required_fields = {"field_case_number_plain_value", "title"}
    if not required_fields.issubset(field_names):
        raise SourceChangedError(
            "California opinion filter fields changed",
            details={
                "collection": collection,
                "required": sorted(required_fields),
                "observed": sorted(field_names),
            },
        )
    taxonomy = _taxonomy(root, collection)
    cards = root.select(".result-excerpt")

    count_node = root.select_one(".views-results_content-header")
    count_match = (
        _COUNT_RE.search(
            _clean(count_node.get_text(" ", strip=True)) or ""
        )
        if count_node is not None
        else None
    )
    if not cards:
        empty_text = (_clean(root.get_text(" ", strip=True)) or "").casefold()
        if "no results found" not in empty_text:
            raise SourceChangedError(
                "California opinion view has neither result cards nor its empty state",
                details={"collection": collection},
            )
        total_count = 0
        showing_start = 0
        showing_end = 0
    else:
        if count_match is None:
            raise SourceChangedError(
                "California opinion result count is missing or changed",
                details={"collection": collection},
            )
        showing_start = _integer(count_match.group("start"))
        showing_end = _integer(count_match.group("end"))
        total_count = _integer(count_match.group("total"))
        if showing_end - showing_start + 1 != len(cards):
            raise SourceChangedError(
                "California opinion count does not match visible cards",
                details={
                    "collection": collection,
                    "showing_start": showing_start,
                    "showing_end": showing_end,
                    "visible_cards": len(cards),
                },
            )
        if showing_start < 1 or showing_end > total_count:
            raise SourceChangedError(
                "California opinion result range is inconsistent",
                details={
                    "collection": collection,
                    "showing_start": showing_start,
                    "showing_end": showing_end,
                    "total_count": total_count,
                },
            )

    records = tuple(
        _parse_listing_card(
            card,
            collection=collection,
            source_url=artifact.source_url,
            page_index=requested_page,
            page_item_index=item_index,
            source_document_sha256=artifact.sha256,
        )
        for item_index, card in enumerate(cards, 1)
    )
    total_pages = (
        math.ceil(total_count / requested_page_size)
        if total_count
        else 0
    )
    if records and requested_page >= total_pages:
        raise SourceChangedError(
            "California opinion page index exceeds the reported result count",
            details={
                "requested_page": requested_page,
                "page_size": requested_page_size,
                "total_count": total_count,
            },
        )
    schema_fingerprint = sha256_fingerprint(
        {
            "collection": collection,
            "required_filters": sorted(required_fields),
            "card_selector": ".result-excerpt",
            "case_selector": ".result-excerpt__brow-primary",
            "date_selector": ".result-excerpt__brow-secondary",
            "notation_selector": ".result-excerpt__brow-notation",
            "title_selector": ".result-excerpt__heading a[href]",
            "count_pattern": _COUNT_RE.pattern,
            "detail_pattern": _DETAIL_PATH_RE.pattern,
            "document_pattern": _DOCUMENT_PATH_RE.pattern,
            "record_schema": OUTPUT_SCHEMA_VERSION,
        }
    )
    page_fingerprint = sha256_fingerprint(
        {
            "collection": collection,
            "page_index": requested_page,
            "page_size": requested_page_size,
            "total_count": total_count,
            "records": [
                {
                    "canonical_ref": record["canonical_ref"],
                    "title": record["title"],
                    "decision_date": record["decision_date"],
                    "publication_status": record["publication_status"],
                    "pdf_url": record["documents"][0]["url"],
                }
                for record in records
            ],
        }
    )
    return OpinionPage(
        collection=collection,
        source_url=artifact.source_url,
        page_index=requested_page,
        page_size=requested_page_size,
        total_count=total_count,
        total_pages=total_pages,
        showing_start=showing_start,
        showing_end=showing_end,
        records=records,
        source_taxonomy=taxonomy,
        schema_fingerprint=schema_fingerprint,
        page_fingerprint=page_fingerprint,
        source_document_sha256=artifact.sha256,
    )


def _asset_bundle_fields(
    artifact: Artifact,
) -> tuple[BeautifulSoup, str, str, str, str, Tag]:
    html = artifact.content.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    case_node = soup.select_one(".brow__accent")
    date_node = soup.select_one(".brow__secondary")
    title_node = soup.select_one("h1.hangover__title")
    detail_node = soup.select_one(".asset-bundle__details")
    if (
        case_node is None
        or date_node is None
        or title_node is None
        or detail_node is None
    ):
        raise SourceChangedError(
            "California opinion detail lacks its identity or asset bundle",
            details={"source_url": artifact.source_url},
        )
    case_number = _required(case_node.get_text(" ", strip=True), "case number").upper()
    decision_date_raw = _required(
        date_node.get_text(" ", strip=True),
        "filing date",
    )
    decision_date = _parse_date(decision_date_raw, "filing date")
    title = _required(title_node.get_text(" ", strip=True), "title")
    return (
        soup,
        case_number,
        decision_date_raw,
        decision_date,
        title,
        detail_node,
    )


def _asset_formats(
    soup: BeautifulSoup,
    *,
    collection: str,
    case_number: str,
) -> list[dict[str, Any]]:
    formats: list[dict[str, Any]] = []
    seen: set[str] = set()
    for link in soup.select("a[href]"):
        try:
            url, observed_collection, observed_case, document_format = (
                _document_url_parts(str(link["href"]))
            )
        except SelectionError:
            continue
        if observed_collection != collection or observed_case != case_number:
            raise SourceChangedError(
                "Opinion detail format link disagrees with its identity",
                details={
                    "collection": collection,
                    "case_number": case_number,
                    "url": url,
                },
            )
        if document_format in seen:
            continue
        seen.add(document_format)
        formats.append(
            {
                "format": document_format,
                "url": url,
                "media_type": (
                    "application/pdf"
                    if document_format == "pdf"
                    else (
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    )
                ),
            }
        )
    if "pdf" not in seen:
        raise SourceChangedError(
            "California opinion detail lacks its PDF format",
            details={"case_number": case_number},
        )
    return formats


def _asset_case_information_url(
    soup: BeautifulSoup,
    opinion_identifier: str,
) -> tuple[str, str]:
    for link in soup.select("a[href]"):
        candidate = str(link["href"])
        if urlsplit(candidate).hostname == "appellatecases.courtinfo.ca.gov":
            return _case_information_url(candidate, opinion_identifier)
    raise SourceChangedError(
        "California opinion detail lacks Appellate Case Information",
        details={"opinion_identifier": opinion_identifier},
    )


def parse_detail_page(artifact: Artifact) -> dict[str, Any]:
    """Parse one exact opinion detail page and its format inventory."""

    (
        safe_url,
        collection,
        url_date,
        url_case,
    ) = _detail_url_parts(artifact.source_url)
    (
        soup,
        opinion_identifier,
        decision_date_raw,
        decision_date,
        title,
        detail_node,
    ) = _asset_bundle_fields(artifact)
    labels = [
        _required(node.get_text(" ", strip=True), "asset label")
        for node in detail_node.select("span")
    ]
    if len(labels) < 2:
        raise SourceChangedError(
            "California opinion detail lacks court/publication labels",
            details={"source_url": safe_url},
        )
    court_name, publication_label = labels[:2]
    court_native_id = COURT_ID_BY_NAME.get(court_name.casefold())
    if court_native_id is None:
        raise SourceChangedError(
            "California opinion detail contains an unknown court",
            details={"court_name": court_name},
        )
    config = COLLECTIONS[collection]
    if (
        publication_label != config["source_label"]
        or opinion_identifier != url_case
        or decision_date != url_date
    ):
        raise SourceChangedError(
            "California opinion detail identity disagrees with its URL",
            details={
                "url": safe_url,
                "url_collection": collection,
                "url_case_number": url_case,
                "url_date": url_date,
                "publication_label": publication_label,
                "opinion_identifier": opinion_identifier,
                "decision_date": decision_date,
            },
        )
    court_spec = COURTS[court_native_id]
    (
        case_information_url,
        appellate_case_number,
    ) = _asset_case_information_url(
        soup,
        opinion_identifier,
    )
    canonical_ref = _canonical_opinion_ref(
        court_id=str(court_spec["court_id"]),
        case_number=appellate_case_number,
        decision_date=decision_date,
    )
    return {
        "record_kind": "appellate_opinion_detail",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": SOURCE_ID,
        "case_number": appellate_case_number,
        "appellate_case_number": appellate_case_number,
        "opinion_identifier": opinion_identifier,
        "opinion_identifier_suffix": (
            opinion_identifier[len(appellate_case_number) :]
            if opinion_identifier != appellate_case_number
            else None
        ),
        "title": title,
        "decision_date": decision_date,
        "decision_date_raw": decision_date_raw,
        "collection": collection,
        "publication_status": config["publication_status"],
        "publication_label": publication_label,
        "document_version": config["document_version"],
        "citation_status": config["citation_status"],
        "court": {
            "court_id": court_spec["court_id"],
            "native_filter_id": court_native_id,
            "name": court_spec["name"],
            "state_code": STATE_CODE,
        },
        "formats": _asset_formats(
            soup,
            collection=collection,
            case_number=opinion_identifier,
        ),
        "case_information_url": case_information_url,
        "corrected_official_reports_text_included": False,
        "official_reports_search_url": OFFICIAL_REPORTS_SEARCH_URL,
        "source_url": safe_url,
        "source_document_sha256": artifact.sha256,
    }


def parse_citings_page(artifact: Artifact) -> dict[str, Any]:
    """Parse one official archive of web pages cited by an opinion."""

    safe_url, url_date, url_case = _citings_url_parts(
        artifact.source_url
    )
    (
        soup,
        opinion_identifier,
        decision_date_raw,
        decision_date,
        title,
        detail_node,
    ) = _asset_bundle_fields(artifact)
    labels = [
        _required(node.get_text(" ", strip=True), "asset label")
        for node in detail_node.select("span")
    ]
    if len(labels) < 2 or labels[1] != "Citings Archive":
        raise SourceChangedError(
            "California citings page lacks its archive label",
            details={"source_url": safe_url, "labels": labels},
        )
    court_name = labels[0]
    court_native_id = COURT_ID_BY_NAME.get(court_name.casefold())
    if court_native_id is None:
        raise SourceChangedError(
            "California citings archive contains an unknown court",
            details={"court_name": court_name},
        )
    if opinion_identifier != url_case or decision_date != url_date:
        raise SourceChangedError(
            "California citings archive identity disagrees with its URL",
            details={
                "source_url": safe_url,
                "opinion_identifier": opinion_identifier,
                "decision_date": decision_date,
            },
        )
    web_citings: list[dict[str, str]] = []
    for paragraph in soup.find_all("p"):
        if (_clean(paragraph.get_text(" ", strip=True)) or "").casefold() != (
            "web page citings:"
        ):
            continue
        citing_list = paragraph.find_next_sibling("ul")
        if citing_list is None:
            continue
        for link in citing_list.select("li a[href]"):
            archived_url = _official_site_url(str(link["href"]))
            if _CITING_ARCHIVE_PATH_RE.fullmatch(
                urlsplit(archived_url).path
            ) is None:
                raise SourceChangedError(
                    "Citings archive link left the verified archive path",
                    details={"url": archived_url},
                )
            original_url = _required(
                link.get_text(" ", strip=True),
                "original citing URL",
            )
            web_citings.append(
                {
                    "original_url": original_url,
                    "archived_copy_url": archived_url,
                }
            )
    court_spec = COURTS[court_native_id]
    (
        case_information_url,
        appellate_case_number,
    ) = _asset_case_information_url(
        soup,
        opinion_identifier,
    )
    canonical_ref = canonical_court_ref(
        SOURCE_ID,
        str(court_spec["court_id"]),
        appellate_case_number,
        "opinion-citings-archive",
        decision_date,
    )
    return {
        "record_kind": "opinion_citings_archive",
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": SOURCE_ID,
        "case_number": appellate_case_number,
        "appellate_case_number": appellate_case_number,
        "opinion_identifier": opinion_identifier,
        "opinion_identifier_suffix": (
            opinion_identifier[len(appellate_case_number) :]
            if opinion_identifier != appellate_case_number
            else None
        ),
        "title": title,
        "decision_date": decision_date,
        "decision_date_raw": decision_date_raw,
        "court": {
            "court_id": court_spec["court_id"],
            "native_filter_id": court_native_id,
            "name": court_spec["name"],
            "state_code": STATE_CODE,
        },
        "formats": _asset_formats(
            soup,
            collection="published",
            case_number=opinion_identifier,
        ),
        "case_information_url": case_information_url,
        "web_citings": web_citings,
        "web_citing_count": len(web_citings),
        "archive_role": "preserved_copy_of_opinion_cited_web_material",
        "source_url": safe_url,
        "source_document_sha256": artifact.sha256,
    }


def _cursor_encode(
    *,
    selection_fingerprint: str,
    collection_index: int,
    page: int,
    offset: int,
    page_fingerprint: str,
) -> str:
    payload = {
        "v": 1,
        "selection": selection_fingerprint,
        "collection_index": collection_index,
        "page": page,
        "offset": offset,
        "page_fingerprint": page_fingerprint,
    }
    token = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{CURSOR_PREFIX}{token}"


def _cursor_decode(
    value: str,
    *,
    selection_fingerprint: str,
    collection_count: int,
) -> dict[str, Any]:
    if not value.startswith(CURSOR_PREFIX):
        raise CursorError(
            "California opinion cursor has an unknown prefix",
        )
    token = value[len(CURSOR_PREFIX) :]
    try:
        padded = token + "=" * (-len(token) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        )
    except (
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        raise CursorError(
            "California opinion cursor is malformed",
        ) from error
    if not isinstance(payload, dict) or payload.get("v") != 1:
        raise CursorError(
            "California opinion cursor has an unsupported version",
        )
    if payload.get("selection") != selection_fingerprint:
        raise CursorError(
            "California opinion cursor belongs to another query",
            code="cursor_query_mismatch",
        )
    for field_name in ("collection_index", "page", "offset"):
        value_at_field = payload.get(field_name)
        if (
            isinstance(value_at_field, bool)
            or not isinstance(value_at_field, int)
            or value_at_field < 0
        ):
            raise CursorError(
                "California opinion cursor position is invalid",
                details={"field": field_name},
            )
    if payload["collection_index"] >= collection_count:
        raise CursorError(
            "California opinion cursor points beyond the selected collections",
        )
    if not isinstance(payload.get("page_fingerprint"), str):
        raise CursorError(
            "California opinion cursor lacks its page fingerprint",
        )
    return payload


def _selection(args: argparse.Namespace) -> dict[str, Any]:
    court_native_id = _court_native_id(args.court)
    collections = _collection_names(args.collection, court_native_id)
    case_number = _clean(args.case_number)
    title = _clean(args.title)
    return {
        "requested_collection": args.collection,
        "collections": list(collections),
        "court_native_id": court_native_id,
        "case_number": case_number,
        "title": title,
        "page": args.page,
        "page_size": args.page_size,
    }


def _search(
    args: argparse.Namespace,
    *,
    client: CaliforniaOpinionsClient | Any,
    selection: Mapping[str, Any],
) -> SearchOutcome:
    collections = tuple(str(item) for item in selection["collections"])
    selection_fingerprint = sha256_fingerprint(selection)
    cursor_payload = (
        _cursor_decode(
            args.cursor,
            selection_fingerprint=selection_fingerprint,
            collection_count=len(collections),
        )
        if args.cursor
        else None
    )
    collection_index = (
        int(cursor_payload["collection_index"])
        if cursor_payload
        else 0
    )
    page_index = (
        int(cursor_payload["page"])
        if cursor_payload
        else int(selection["page"])
    )
    offset = int(cursor_payload["offset"]) if cursor_payload else 0
    expected_page_fingerprint = (
        str(cursor_payload["page_fingerprint"])
        if cursor_payload
        else None
    )
    output: list[Mapping[str, Any]] = []
    refs: list[str] = []

    while collection_index < len(collections):
        collection = collections[collection_index]
        artifact = client.listing(
            collection,
            page=page_index,
            page_size=int(selection["page_size"]),
            court_native_id=selection.get("court_native_id"),
            case_number=selection.get("case_number"),
            title=selection.get("title"),
        )
        page = parse_listing_page(
            artifact,
            collection=collection,
            requested_page=page_index,
            requested_page_size=int(selection["page_size"]),
        )
        refs.append(page.source_url)
        if expected_page_fingerprint is not None:
            if page.page_fingerprint != expected_page_fingerprint:
                raise CursorError(
                    "California opinion page changed before cursor resume",
                    code="cursor_page_changed",
                    details={
                        "collection": collection,
                        "page": page_index,
                        "expected_page_fingerprint": expected_page_fingerprint,
                        "observed_page_fingerprint": page.page_fingerprint,
                    },
                )
            expected_page_fingerprint = None
        if offset > len(page.records):
            raise CursorError(
                "California opinion cursor offset exceeds its source page",
            )

        for record_index in range(offset, len(page.records)):
            output.append(page.records[record_index])
            if len(output) >= args.limit:
                more = (
                    record_index + 1 < len(page.records)
                    or page.has_next
                    or collection_index + 1 < len(collections)
                )
                next_cursor = (
                    _cursor_encode(
                        selection_fingerprint=selection_fingerprint,
                        collection_index=collection_index,
                        page=page_index,
                        offset=record_index + 1,
                        page_fingerprint=page.page_fingerprint,
                    )
                    if more
                    else None
                )
                return SearchOutcome(
                    records=tuple(output),
                    next_cursor=next_cursor,
                    raw_artifact_refs=tuple(dict.fromkeys(refs)),
                )
        if page.has_next:
            page_index += 1
            offset = 0
            continue
        collection_index += 1
        page_index = int(selection["page"])
        offset = 0
    return SearchOutcome(
        records=tuple(output),
        next_cursor=None,
        raw_artifact_refs=tuple(dict.fromkeys(refs)),
    )


def alternative_routes() -> list[dict[str, Any]]:
    """Return official complementary routes for material outside the feeds."""

    return [
        {
            "source_id": "us-ca-appellate-case-information",
            "name": "California Appellate Case Information",
            "authority": "Judicial Council of California",
            "url": APPELLATE_CASE_INFORMATION_URL,
            "role": "older_opinion_and_appellate_case_lookup",
            "adds": [
                "opinions after the 120-day published feed window",
                "opinions after the 60-day unpublished feed window",
                "case chronology and appellate case metadata",
            ],
            "gaps": [
                "interactive case-oriented lookup",
                "not the corrected Official Reports corpus",
            ],
            "join_keys": ["appellate case number"],
        },
        {
            "source_id": "us-ca-official-reports-opinions",
            "name": "California Official Reports Opinions",
            "authority": "Judicial Council of California",
            "operator": "LexisNexis",
            "url": OFFICIAL_REPORTS_SEARCH_URL,
            "guide_url": OFFICIAL_REPORTS_GUIDE_URL,
            "role": "corrected_searchable_citable_opinions",
            "coverage": "1850-present",
            "access": "official no-fee service",
            "adds": [
                "post-filing corrections",
                "Official Reports enhancements and editing",
                "historical published opinions from 1850 onward",
            ],
            "gaps": [
                "does not replace the current as-filed slip-opinion record",
                "external official-service search interface",
            ],
            "join_keys": [
                "case name",
                "citation",
                "appellate case number",
                "decision date",
            ],
        },
    ]


def source_manifest_record() -> dict[str, Any]:
    """Return the network-free source, identity, and route contract."""

    return {
        "record_kind": "source_manifest",
        "source": SOURCE_METADATA.to_dict(),
        "jurisdiction": JURISDICTION.to_dict(),
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "collections": {
            collection: {
                "url": config["url"],
                "publication_status": config["publication_status"],
                "source_label": config["source_label"],
                "current_window_days": config["window_days"],
                "document_version": config["document_version"],
                "citation_status": config["citation_status"],
                "native_filters": [
                    "field_opinion_source_target_id",
                    "field_case_number_plain_value",
                    "title",
                    "items_per_page",
                    "page",
                ],
                "court_taxonomy": {
                    native_id: {
                        "slug": spec["slug"],
                        "name": spec["name"],
                        "court_id": spec["court_id"],
                    }
                    for native_id, spec in COURTS.items()
                    if collection in spec["collections"]
                },
            }
            for collection, config in COLLECTIONS.items()
        },
        "observed_live_state": {
            "observed_at": "2026-07-30",
            "published_total": 243,
            "unpublished_total": 1277,
            "native_page_sizes": list(PAGE_SIZE_CHOICES),
            "modified_opinion_crosswalk": {
                "observed_opinion_identifier": "B350634M",
                "appellate_case_number": "B350634",
                "preserved_as_separate_fields": True,
            },
            "interpretation": (
                "mutable current-feed counts, not fixed historical coverage"
            ),
        },
        "identity": {
            "opinion": [
                "source_id",
                "court_id",
                "appellate_case_number",
                "opinion_filing_date",
            ],
            "document": [
                "official document path",
                "format",
            ],
            "opinion_identifier": (
                "source-visible publication/document identifier; may carry "
                "a suffix while the linked appellate case number remains "
                "the base case identity"
            ),
            "publication_status_is_identity": False,
            "reason": (
                "an unpublished opinion may later be ordered published; the "
                "case number and filing date retain the opinion identity"
            ),
        },
        "operations": {
            "search": "bounded native filtering and zero-based paging",
            "detail": "exact opinion metadata and available-format inventory",
            "citings": "official archived copies of web pages cited by an opinion",
            "download": "validated direct PDF or DOCX artifact retrieval",
            "alternatives": "older-opinion and corrected-text route map",
            "probe": "bounded first-page and detail contract check",
        },
        "version_distinctions": {
            "published_listing": "as-filed slip opinion",
            "official_reports": (
                "searchable citable text reflecting post-filing corrections"
            ),
            "unpublished_listing": (
                "source-designated unpublished/non-citable opinion"
            ),
        },
        "alternative_routes": alternative_routes(),
    }


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    ignored = {
        "command",
        "output",
        "json_out",
        "quiet",
        "timeout",
        "minimum_interval",
        "max_attempts",
        "retry_backoff",
        "destination",
        "overwrite",
    }
    return {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
        if key not in ignored and value is not None
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _failure(
    query: PublicRecordsQuery,
    error: CaliforniaOpinionsError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def _probe(
    client: CaliforniaOpinionsClient | Any,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    operations: dict[str, Any] = {}
    refs: list[str] = []
    parsed_pages: dict[str, OpinionPage] = {}
    for collection in ("published", "unpublished"):
        artifact = client.listing(
            collection,
            page=0,
            page_size=DEFAULT_PAGE_SIZE,
        )
        page = parse_listing_page(
            artifact,
            collection=collection,
            requested_page=0,
            requested_page_size=DEFAULT_PAGE_SIZE,
        )
        parsed_pages[collection] = page
        refs.append(page.source_url)
        operations[f"{collection}_listing"] = {
            "state": "available",
            "visible_count": len(page.records),
            "total_count": page.total_count,
            "total_pages": page.total_pages,
            "schema_fingerprint": page.schema_fingerprint,
            "page_fingerprint": page.page_fingerprint,
            "source_document_sha256": page.source_document_sha256,
            "source_taxonomy": dict(page.source_taxonomy),
            "source_url": page.source_url,
        }
        if page.records:
            detail_artifact = client.detail(
                str(page.records[0]["detail_url"])
            )
            detail = parse_detail_page(detail_artifact)
            refs.append(str(detail["source_url"]))
            operations[f"{collection}_detail"] = {
                "state": "available",
                "case_number": detail["case_number"],
                "publication_status": detail["publication_status"],
                "formats": [
                    item["format"] for item in detail["formats"]
                ],
                "source_document_sha256": detail[
                    "source_document_sha256"
                ],
                "source_url": detail["source_url"],
            }
    record = {
        "record_kind": "source_probe",
        "source_id": SOURCE_ID,
        "status": "ok",
        "operations": operations,
        "feed_totals": {
            collection: page.total_count
            for collection, page in parsed_pages.items()
        },
        "stable_contract_fingerprint": sha256_fingerprint(
            {
                "schema_version": OUTPUT_SCHEMA_VERSION,
                "collections": {
                    collection: {
                        "schema_fingerprint": page.schema_fingerprint,
                        "taxonomy": dict(page.source_taxonomy),
                    }
                    for collection, page in parsed_pages.items()
                },
                "page_sizes": list(PAGE_SIZE_CHOICES),
                "detail_formats": {
                    collection: operations[
                        f"{collection}_detail"
                    ]["formats"]
                    for collection in parsed_pages
                    if f"{collection}_detail" in operations
                },
            }
        ),
        "live_state_fingerprint": sha256_fingerprint(
            {
                "feed_totals": {
                    collection: page.total_count
                    for collection, page in parsed_pages.items()
                },
                "page_fingerprints": {
                    collection: page.page_fingerprint
                    for collection, page in parsed_pages.items()
                },
            }
        ),
    }
    return record, tuple(dict.fromkeys(refs))


def execute(
    args: argparse.Namespace,
    *,
    client: CaliforniaOpinionsClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one source operation and return the shared result envelope."""

    query = build_query(args)
    network_command = args.command in {
        "search",
        "detail",
        "citings",
        "download",
        "probe",
    }
    source_client = client
    if network_command and source_client is None:
        source_client = CaliforniaOpinionsClient(
            timeout=args.timeout,
            minimum_interval=args.minimum_interval,
            retry_policy=RetryPolicy(
                max_attempts=args.max_attempts,
                backoff_initial=args.retry_backoff,
            ),
        )
    try:
        if args.command == "manifest":
            result = PublicRecordsResult.success(
                query,
                [source_manifest_record()],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "alternatives":
            result = PublicRecordsResult.success(
                query,
                [
                    {
                        "record_kind": "alternative_route_manifest",
                        "source_id": SOURCE_ID,
                        "routes": alternative_routes(),
                    }
                ],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "search":
            selection = _selection(args)
            outcome = _search(
                args,
                client=source_client,
                selection=selection,
            )
            result = PublicRecordsResult.success(
                query,
                outcome.records,
                next_cursor=outcome.next_cursor,
                raw_artifact_refs=outcome.raw_artifact_refs,
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "detail":
            record = parse_detail_page(
                source_client.detail(args.url)
            )
            result = PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=[str(record["source_url"])],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "citings":
            record = parse_citings_page(
                source_client.citings(args.url)
            )
            result = PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=[str(record["source_url"])],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "download":
            (
                safe_url,
                collection,
                case_number,
                document_format,
            ) = _document_url_parts(args.url)
            destination = Path(args.destination)
            if destination.exists() and not args.overwrite:
                raise SelectionError(
                    "Download destination already exists; pass --overwrite to replace it",
                    code="destination_exists",
                    details={"destination": str(destination)},
                )
            artifact = source_client.document(safe_url)
            if document_format == "pdf" and not artifact.content.startswith(
                b"%PDF-"
            ):
                raise SourceChangedError(
                    "Official PDF response lacks a PDF signature",
                    details={
                        "source_url": artifact.source_url,
                        "media_type": artifact.media_type,
                    },
                )
            if document_format == "docx" and not artifact.content.startswith(
                b"PK\x03\x04"
            ):
                raise SourceChangedError(
                    "Official DOCX response lacks a ZIP/OOXML signature",
                    details={
                        "source_url": artifact.source_url,
                        "media_type": artifact.media_type,
                    },
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(artifact.content)
            canonical_ref = _canonical_document_ref(
                case_number=case_number,
                document_format=document_format,
            )
            record = {
                "record_kind": "opinion_document_artifact",
                "canonical_ref": canonical_ref,
                "evidence_ref": canonical_ref,
                "source_id": SOURCE_ID,
                "case_number": case_number,
                "collection": collection,
                "publication_status": COLLECTIONS[collection][
                    "publication_status"
                ],
                "document_version": COLLECTIONS[collection][
                    "document_version"
                ],
                "format": document_format,
                "media_type": artifact.media_type,
                "source_url": artifact.source_url,
                "byte_length": len(artifact.content),
                "sha256": artifact.sha256,
                "saved_path": str(destination.resolve()),
            }
            result = PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=[
                    artifact.source_url,
                    str(destination.resolve()),
                ],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            record, refs = _probe(source_client)
            result = PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=refs,
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise ValueError(
                f"unsupported California opinions command {args.command!r}"
            )
    except CaliforniaOpinionsError as error:
        result = _failure(query, error)
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="artifact_write_failed",
                    message=str(error),
                    category="local_artifact",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    finally:
        if network_command and client is None and source_client is not None:
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
            canonical_json(query.to_dict()),
            SOURCE_ID,
            result_count,
        )
    return result


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_int,
        default=DEFAULT_MAX_ATTEMPTS,
    )
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query current published slip and unpublished California "
            "appellate opinion pages"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest = subparsers.add_parser(
        "manifest",
        help="Show source, version, identity, coverage, and route metadata",
    )
    _add_runtime_and_output(manifest)

    alternatives = subparsers.add_parser(
        "alternatives",
        help="Show older-opinion and corrected Official Reports routes",
    )
    _add_runtime_and_output(alternatives)

    search = subparsers.add_parser(
        "search",
        help="Search and page through one or both current opinion collections",
    )
    search.add_argument(
        "--collection",
        choices=("published", "unpublished", "both"),
        default="both",
    )
    search.add_argument(
        "--court",
        help="Native source ID, manifest slug, court ID, or exact court name",
    )
    search.add_argument("--case-number")
    search.add_argument("--title")
    search.add_argument(
        "--page",
        type=_nonnegative_int,
        default=0,
        help="Zero-based native starting page",
    )
    search.add_argument(
        "--page-size",
        type=int,
        choices=PAGE_SIZE_CHOICES,
        default=DEFAULT_PAGE_SIZE,
    )
    search.add_argument("--limit", type=_positive_int, default=DEFAULT_LIMIT)
    search.add_argument("--cursor")
    _add_runtime_and_output(search)

    detail = subparsers.add_parser(
        "detail",
        help="Fetch exact opinion metadata and available document formats",
    )
    detail.add_argument("url")
    _add_runtime_and_output(detail)

    citings = subparsers.add_parser(
        "citings",
        help="List official archived copies of web pages cited by an opinion",
    )
    citings.add_argument("url")
    _add_runtime_and_output(citings)

    download = subparsers.add_parser(
        "download",
        help="Fetch and validate one exact official opinion PDF or DOCX",
    )
    download.add_argument("url")
    download.add_argument("destination", type=Path)
    download.add_argument("--overwrite", action="store_true")
    _add_runtime_and_output(download)

    probe = subparsers.add_parser(
        "probe",
        help="Run a bounded listing and format-detail source check",
    )
    _add_runtime_and_output(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"California opinions {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"California opinions {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = execute(args)
    except ValueError as error:
        parser.error(str(error))
        return
    _emit(result, args)
    if result.status not in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    }:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
