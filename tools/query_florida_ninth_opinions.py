#!/usr/bin/env python3
"""Query Ninth Judicial Circuit archived appellate opinions.

The Ninth Judicial Circuit Court of Florida publishes a server-rendered,
keyword-searchable archive of circuit-appellate, certiorari, and writ opinions.
Each index occurrence links directly to an official PDF.

Examples:
    uv run python tools/query_florida_ninth_opinions.py manifest --json
    uv run python tools/query_florida_ninth_opinions.py search \
        "Orange County" --limit 50 --json
    uv run python tools/query_florida_ninth_opinions.py download \
        https://ninthcircuit.org/sites/default/files/06-45.pdf \
        /tmp/06-45.pdf
    uv run python tools/query_florida_ninth_opinions.py probe --json
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
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

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


SOURCE_ID = "us-fl-ninth-circuit-appellate-opinions-archive"
COURT_ID = "us-fl-ninth-judicial-circuit-appellate-division"
STATE_CODE = "FL"
STATE_GEOID = "12"
COUNTY_GEOIDS = ("12095", "12097")
BASE_URL = "https://ninthcircuit.org"
INDEX_URL = f"{BASE_URL}/resources/appellate-opinions-archived"

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.5
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_LIMIT = 50
MAXIMUM_HTML_BYTES = 16 * 1024 * 1024
MAXIMUM_PDF_BYTES = 160 * 1024 * 1024
CURSOR_PREFIX = "fl-ninth-opinions:v1:"
OUTPUT_SCHEMA_VERSION = "fl-ninth-circuit-appellate-opinions/1.0"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Ninth Judicial Circuit Archived Appellate Opinions",
    source_role=(
        "official_circuit_appellate_certiorari_and_writ_opinion_archive"
    ),
    base_url=INDEX_URL,
    dataset_id="ninth-circuit-appellate-opinions-archive",
    metadata={
        "authority": "Ninth Judicial Circuit Court of Florida",
        "operator": "Ninth Judicial Circuit Court of Florida",
        "jurisdiction_geoids": list(COUNTY_GEOIDS),
        "coverage": "Orange and Osceola circuit-appellate publications",
        "authentication": "none",
        "adapter_family": "official_opinion_archive",
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Florida",
    state_code=STATE_CODE,
)

SOURCE_WARNINGS = (
    "This is a circuit-appellate publication archive, not a general trial-order "
    "feed or complete trial-court docket.",
    "The source does not publish a complete archive date range; each returned "
    "index occurrence retains its official PDF URL.",
    "Keyword matching and result order are source-managed and may include "
    "document text beyond the visible opinion title.",
)

COMPLEMENTARY_SOURCES = (
    {
        "source_id": "us-fl-orange-clerk-my-eclerk",
        "relationship": "underlying Orange County trial-case index and docket",
    },
    {
        "source_id": "us-fl-acis",
        "relationship": "statewide Supreme Court and DCA case and document system",
    },
    {
        "source_id": "us-fl-appellate-opinions-search",
        "relationship": "statewide Supreme Court and DCA opinion publications",
    },
)

_CHALLENGE_MARKERS = (
    "performing security verification",
    "enable javascript and cookies to continue",
    "challenges.cloudflare.com",
)
_PDF_TITLE_SUFFIX_RE = re.compile(r"\s*\(PDF\)\s*$", re.IGNORECASE)


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
class ParsedIndex:
    records: tuple[Mapping[str, Any], ...]
    page_index: int
    last_page_index: int
    has_next: bool
    source_url: str
    source_document_sha256: str


class FloridaNinthOpinionsError(RuntimeError):
    """Source transport, access, schema, or selection failure."""

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


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    result = " ".join(str(value).replace("\x00", "").split()).strip()
    return result or None


def _required(value: Any, field: str) -> str:
    result = _clean(value)
    if result is None:
        raise FloridaNinthOpinionsError(
            "source_field_missing",
            f"Ninth Circuit opinion {field} is blank",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"field": field},
        )
    return result


def _media_type(response: Any) -> str | None:
    headers = getattr(response, "headers", {})
    value = headers.get("Content-Type", headers.get("content-type"))
    return (
        str(value).split(";", 1)[0].strip().casefold()
        if value
        else None
    )


def _retry_after(response: Any) -> float | None:
    headers = getattr(response, "headers", {})
    value = headers.get("Retry-After", headers.get("retry-after"))
    try:
        return max(0.0, float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _official_url(value: str, *, index_only: bool = False) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname != "ninthcircuit.org":
        raise FloridaNinthOpinionsError(
            "unrecognized_official_url",
            "Ninth Circuit URL must use the official HTTPS host",
            category="selection",
            details={"url": value},
        )
    if index_only and parsed.path.rstrip("/") != urlsplit(INDEX_URL).path:
        raise FloridaNinthOpinionsError(
            "unrecognized_index_url",
            "Ninth Circuit index request does not match the official archive",
            category="selection",
            details={"url": value},
        )
    return value


class FloridaNinthOpinionsClient:
    """Bounded, rate-limited client with injectable transport."""

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
        _official_url(url)
        headers = {
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    "GET",
                    url,
                    params=dict(params or {}),
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise FloridaNinthOpinionsError(
                    "transport_error",
                    str(error),
                    category="transport",
                    retryable=True,
                    details={"url": url},
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
                raise FloridaNinthOpinionsError(
                    "rate_limited",
                    "Ninth Circuit archive rate limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="rate_limit",
                    retryable=True,
                    details={"url": url, "status_code": status_code},
                )
            if status_code in {401, 403}:
                raise FloridaNinthOpinionsError(
                    "access_restricted",
                    f"Ninth Circuit archive returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"url": url, "status_code": status_code},
                )
            if status_code < 200 or status_code >= 300:
                raise FloridaNinthOpinionsError(
                    "http_status",
                    f"Ninth Circuit archive returned HTTP {status_code}",
                    category="http",
                    retryable=status_code >= 500,
                    details={"url": url, "status_code": status_code},
                )

            content = bytes(getattr(response, "content", b""))
            if not content and getattr(response, "text", None):
                content = str(response.text).encode()
            if len(content) > maximum_bytes:
                raise FloridaNinthOpinionsError(
                    "response_too_large",
                    "Ninth Circuit response exceeds the configured bound",
                    category="response_size",
                    details={
                        "url": url,
                        "byte_length": len(content),
                        "maximum_bytes": maximum_bytes,
                    },
                )
            response_url = str(getattr(response, "url", None) or url)
            _official_url(response_url)
            return Artifact(
                content=content,
                source_url=response_url,
                media_type=_media_type(response),
                headers={
                    str(key).casefold(): str(value)
                    for key, value in getattr(response, "headers", {}).items()
                },
            )
        raise FloridaNinthOpinionsError(
            "transport_error",
            str(last_error or "request failed"),
            category="transport",
            retryable=True,
            details={"url": url},
        )

    def index(self, query: str | None, *, page: int) -> Artifact:
        if isinstance(page, bool) or page < 0:
            raise ValueError("page must not be negative")
        params: dict[str, Any] = {"page": page}
        if query:
            params["search"] = query
        return self.get(INDEX_URL, params=params)

    def document(self, url: str) -> Artifact:
        artifact = self.get(
            _official_url(url),
            accept="application/pdf",
            maximum_bytes=MAXIMUM_PDF_BYTES,
        )
        if (
            artifact.media_type not in {None, "application/pdf"}
            or not artifact.content.startswith(b"%PDF-")
        ):
            raise FloridaNinthOpinionsError(
                "unexpected_document_response",
                "Ninth Circuit opinion document was not a PDF",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
                details={
                    "url": artifact.source_url,
                    "media_type": artifact.media_type,
                    "signature_hex": artifact.content[:8].hex(),
                },
            )
        return artifact


def _index_page_from_url(url: str, fallback: int) -> int:
    values = parse_qs(urlsplit(url).query).get("page")
    if not values:
        return fallback
    value = values[-1]
    return int(value) if value.isdigit() else fallback


def _opinion_record(
    *,
    title: str,
    document_url: str,
    artifact: Artifact,
    page_index: int,
    ordinal: int,
) -> dict[str, Any]:
    normalized_url = _official_url(document_url)
    path = unquote(urlsplit(normalized_url).path)
    filename = Path(path).name
    identifier = hashlib.sha256(normalized_url.encode()).hexdigest()[:24]
    canonical_ref = (
        f"STATECOURT:{SOURCE_ID}/{COURT_ID}/opinion/{identifier}"
    )
    return {
        "canonical_ref": canonical_ref,
        "evidence_ref": canonical_ref,
        "source_id": SOURCE_ID,
        "record_kind": "circuit_appellate_opinion_index",
        "native_document_id": identifier,
        "published_title": title,
        "source_file_name": filename,
        "source_file_stem": Path(filename).stem,
        "document_url": normalized_url,
        "source_url": artifact.source_url,
        "court": {
            "court_id": COURT_ID,
            "native_court_id": "ninth-judicial-circuit-appellate",
            "name": (
                "Ninth Judicial Circuit Court of Florida, "
                "Appellate Division"
            ),
            "state_code": STATE_CODE,
            "county_geoids": list(COUNTY_GEOIDS),
            "court_level": "circuit_appellate",
            "official_url": INDEX_URL,
        },
        "index_page": page_index,
        "index_ordinal": ordinal,
        "source_document_sha256": artifact.sha256,
        "source_document_bytes": len(artifact.content),
        "projection": {
            "projectable_as_case": False,
            "scope": "official_opinion_index_occurrence",
        },
    }


def parse_index_page(
    artifact: Artifact,
    *,
    requested_page: int,
) -> ParsedIndex:
    """Parse one source page and its source-visible pagination."""
    if artifact.media_type and "html" not in artifact.media_type:
        raise FloridaNinthOpinionsError(
            "unexpected_index_media_type",
            "Ninth Circuit archive did not return HTML",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={
                "url": artifact.source_url,
                "media_type": artifact.media_type,
            },
        )
    soup = BeautifulSoup(artifact.content, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    folded = page_text.casefold()
    if any(marker in folded for marker in _CHALLENGE_MARKERS):
        raise FloridaNinthOpinionsError(
            "human_verification",
            "Ninth Circuit archive returned an interactive verification page",
            status=ResultStatus.HUMAN_REQUIRED,
            category="access",
            details={"url": artifact.source_url},
        )
    if "Appellate Opinions" not in page_text:
        raise FloridaNinthOpinionsError(
            "index_marker_missing",
            "Ninth Circuit archive lacks its expected page marker",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"url": artifact.source_url},
        )
    view = soup.select_one(".view-appellate-opinions-search-index")
    if view is None:
        raise FloridaNinthOpinionsError(
            "opinion_view_missing",
            "Ninth Circuit archive lacks its expected opinion view",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"url": artifact.source_url},
        )

    page_index = _index_page_from_url(
        artifact.source_url,
        requested_page,
    )
    records = []
    for ordinal, item in enumerate(
        view.select(".view-content .appellate-opinions"),
        start=1,
    ):
        anchor = item.select_one("h3 a[href]")
        if anchor is None:
            raise FloridaNinthOpinionsError(
                "opinion_link_missing",
                "Ninth Circuit opinion index item lacks its PDF link",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
                details={"url": artifact.source_url, "ordinal": ordinal},
            )
        title = _required(
            _PDF_TITLE_SUFFIX_RE.sub(
                "",
                anchor.get_text(" ", strip=True),
            ),
            "title",
        )
        document_url = urljoin(
            artifact.source_url,
            _required(anchor.get("href"), "document URL"),
        )
        parsed_document = urlsplit(document_url)
        if (
            not parsed_document.path.casefold().endswith(".pdf")
            or not parsed_document.path.startswith("/sites/default/files/")
        ):
            raise FloridaNinthOpinionsError(
                "opinion_pdf_route_changed",
                "Ninth Circuit opinion link is no longer an official PDF route",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
                details={"url": document_url, "ordinal": ordinal},
            )
        records.append(
            _opinion_record(
                title=title,
                document_url=document_url,
                artifact=artifact,
                page_index=page_index,
                ordinal=ordinal,
            )
        )

    if not records and view.select_one(".view-empty") is None:
        raise FloridaNinthOpinionsError(
            "opinion_results_missing",
            "Ninth Circuit archive contains neither results nor an empty state",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"url": artifact.source_url},
        )

    pager_indexes = [page_index]
    for anchor in view.select(".pager a[href]"):
        page_values = parse_qs(
            urlsplit(urljoin(artifact.source_url, anchor["href"])).query
        ).get("page")
        if page_values and page_values[-1].isdigit():
            pager_indexes.append(int(page_values[-1]))
    last_page_index = max(pager_indexes)
    return ParsedIndex(
        records=tuple(records),
        page_index=page_index,
        last_page_index=last_page_index,
        has_next=page_index < last_page_index,
        source_url=artifact.source_url,
        source_document_sha256=artifact.sha256,
    )


def _query_key(query: str | None) -> str:
    return hashlib.sha256((query or "").encode()).hexdigest()


def _encode_cursor(
    query: str | None,
    *,
    page: int,
    offset: int,
) -> str:
    payload = canonical_json(
        {
            "query_sha256": _query_key(query),
            "page": page,
            "offset": offset,
        }
    ).encode()
    token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return CURSOR_PREFIX + token


def _decode_cursor(
    cursor: str | None,
    query: str | None,
) -> tuple[int, int]:
    if cursor is None:
        return 0, 0
    if not cursor.startswith(CURSOR_PREFIX):
        raise FloridaNinthOpinionsError(
            "invalid_cursor",
            "Ninth Circuit opinion cursor has an unrecognized prefix",
            category="query_selection",
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(
                token + "=" * (-len(token) % 4)
            ).decode()
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FloridaNinthOpinionsError(
            "invalid_cursor",
            "Ninth Circuit opinion cursor is malformed",
            category="query_selection",
        ) from error
    if not isinstance(payload, Mapping):
        raise FloridaNinthOpinionsError(
            "invalid_cursor",
            "Ninth Circuit opinion cursor payload is not an object",
            category="query_selection",
        )
    if payload.get("query_sha256") != _query_key(query):
        raise FloridaNinthOpinionsError(
            "cursor_query_mismatch",
            "Ninth Circuit opinion cursor belongs to a different query",
            category="query_selection",
        )
    page = payload.get("page")
    offset = payload.get("offset")
    if (
        isinstance(page, bool)
        or not isinstance(page, int)
        or page < 0
        or isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
    ):
        raise FloridaNinthOpinionsError(
            "invalid_cursor",
            "Ninth Circuit opinion cursor page or offset is invalid",
            category="query_selection",
        )
    return page, offset


def _search(
    client: FloridaNinthOpinionsClient | Any,
    *,
    query: str | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[Mapping[str, Any]], str | None]:
    page, offset = _decode_cursor(cursor, query)
    records: list[Mapping[str, Any]] = []
    next_cursor: str | None = None
    while len(records) < limit:
        parsed = parse_index_page(
            client.index(query, page=page),
            requested_page=page,
        )
        page_records = list(parsed.records)
        if offset > len(page_records):
            raise FloridaNinthOpinionsError(
                "cursor_offset_out_of_range",
                "Ninth Circuit opinion cursor offset exceeds its source page",
                category="query_selection",
                details={
                    "page": page,
                    "offset": offset,
                    "page_record_count": len(page_records),
                },
            )
        available = page_records[offset:]
        remaining = limit - len(records)
        selected = available[:remaining]
        records.extend(selected)
        consumed = offset + len(selected)
        if consumed < len(page_records):
            next_cursor = _encode_cursor(
                query,
                page=page,
                offset=consumed,
            )
            break
        if parsed.has_next:
            next_cursor = _encode_cursor(
                query,
                page=page + 1,
                offset=0,
            )
            if len(records) >= limit:
                break
            page += 1
            offset = 0
            continue
        next_cursor = None
        break
    return records, next_cursor


def _manifest_record() -> dict[str, Any]:
    return {
        "record_kind": "source_manifest",
        "source_id": SOURCE_ID,
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "authority": "Ninth Judicial Circuit Court of Florida",
        "jurisdiction_geoids": list(COUNTY_GEOIDS),
        "operations": ["search", "download", "probe"],
        "source_roles": [
            "circuit_appellate_opinions",
            "certiorari_opinions",
            "writ_opinions",
            "direct_pdf_documents",
        ],
        "coverage": {
            "court": "Ninth Judicial Circuit appellate division",
            "counties": ["Orange", "Osceola"],
            "complete_date_range_claimed": False,
            "general_trial_orders": False,
        },
        "complementary_sources": list(COMPLEMENTARY_SOURCES),
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
    error: FloridaNinthOpinionsError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category=error.category,
                retryable=error.retryable,
                details=error.details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    status_value = str(
        decision.get("result_status")
        or decision.get("status")
        or (
            ResultStatus.HUMAN_REQUIRED.value
            if decision.get("automation_disposition") == "human_required"
            else ResultStatus.RESTRICTED.value
        )
    )
    try:
        status = ResultStatus(status_value)
    except ValueError:
        status = ResultStatus.RESTRICTED
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code")
                    or "acquisition_route_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or "Catalogued acquisition route is unavailable"
                ),
                category="access",
                retryable=False,
                details=dict(decision),
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: FloridaNinthOpinionsClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = build_query(args)
    if access_decision is not None and not access_decision.get(
        "allowed",
        False,
    ):
        result = _decision_failure(query, access_decision)
        if log_results:
            log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result

    source_client = client or FloridaNinthOpinionsClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
    )
    try:
        if args.command == "manifest":
            result = PublicRecordsResult.success(
                query,
                [_manifest_record()],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "search":
            raw_query = _clean(args.query)
            search_query = None if raw_query in {None, "*"} else raw_query
            records, next_cursor = _search(
                source_client,
                query=search_query,
                limit=args.limit,
                cursor=args.cursor,
            )
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=next_cursor,
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "download":
            artifact = source_client.document(args.document_url)
            destination: Path | None = None
            if args.destination:
                destination = Path(args.destination).expanduser()
                if destination.exists() and not args.overwrite:
                    raise FloridaNinthOpinionsError(
                        "destination_exists",
                        f"destination exists; pass --overwrite: {destination}",
                        category="local_io",
                    )
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(artifact.content)
            identifier = hashlib.sha256(
                artifact.source_url.encode()
            ).hexdigest()[:24]
            record = {
                "canonical_ref": (
                    f"STATECOURT:{SOURCE_ID}/{COURT_ID}/opinion/"
                    f"{identifier}/document"
                ),
                "evidence_ref": f"NINTH-CIRCUIT-PDF:{artifact.sha256}",
                "source_id": SOURCE_ID,
                "record_kind": "opinion_document_download",
                "native_document_id": identifier,
                "document_url": artifact.source_url,
                "source_file_name": Path(
                    unquote(urlsplit(artifact.source_url).path)
                ).name,
                "mime_type": "application/pdf",
                "byte_count": len(artifact.content),
                "sha256": artifact.sha256,
                "storage_path": (
                    str(destination.resolve()) if destination else None
                ),
                "download_status": "saved" if destination else "verified",
            }
            result = PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=(
                    [str(destination.resolve())] if destination else []
                ),
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            parsed = parse_index_page(
                source_client.index(None, page=0),
                requested_page=0,
            )
            result = PublicRecordsResult.success(
                query,
                [
                    {
                        "record_kind": "source_probe",
                        "source_id": SOURCE_ID,
                        "status": "ok",
                        "first_page_record_count": len(parsed.records),
                        "last_page_index": parsed.last_page_index,
                        "first_document_url": (
                            parsed.records[0]["document_url"]
                            if parsed.records
                            else None
                        ),
                        "source_url": parsed.source_url,
                        "source_document_sha256": (
                            parsed.source_document_sha256
                        ),
                    }
                ],
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise ValueError(
                f"unsupported Ninth Circuit opinion command {args.command!r}"
            )
    except FloridaNinthOpinionsError as error:
        result = _failure(query, error)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    finally:
        if client is None:
            source_client.close()

    if log_results:
        count = (
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        )
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Florida Ninth Circuit opinions {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Florida Ninth Circuit opinions {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_runtime(parser: argparse.ArgumentParser) -> None:
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
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Ninth Judicial Circuit archived appellate "
            "opinions and direct PDFs"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    manifest = sub.add_parser(
        "manifest",
        help="Describe source roles and official complements",
    )
    _add_runtime(manifest)

    search = sub.add_parser(
        "search",
        help="Search the source-managed opinion index",
    )
    search.add_argument("query", nargs="?", default="*")
    search.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    search.add_argument("--cursor")
    _add_runtime(search)

    download = sub.add_parser(
        "download",
        help="Verify or save one exact official opinion PDF",
    )
    download.add_argument("document_url")
    download.add_argument("destination", nargs="?")
    download.add_argument("--overwrite", action="store_true")
    _add_runtime(download)

    probe = sub.add_parser(
        "probe",
        help="Run a bounded first-page archive sentinel",
    )
    _add_runtime(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.minimum_interval < 0:
        parser.error("--minimum-interval must not be negative")
    if args.max_attempts <= 0:
        parser.error("--max-attempts must be positive")
    if getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
