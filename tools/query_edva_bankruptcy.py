#!/usr/bin/env python3
"""Access E.D. Virginia bankruptcy dockets through PACER and RECAP.

The adapter uses CourtListener's supported RECAP APIs for free docket metadata,
archived documents, and explicit PACER-backed acquisition jobs. It also records
the official direct-access and copy-request paths that remain useful when a
docket is absent or blocked in the RECAP archive.

Read commands exhaust CourtListener cursor pagination unless the caller supplies
``--limit``. Acquisition and prayer commands are explicit POST operations; case
lookup and ``probe`` never create a PACER charge or an external request.

Examples:
    uv run python tools/query_edva_bankruptcy.py case 05-39367 --json
    uv run python tools/query_edva_bankruptcy.py entries 49921079 --json
    uv run python tools/query_edva_bankruptcy.py fetch-docket \
        --docket-id 49921079 --json
    uv run python tools/query_edva_bankruptcy.py fetch-status 12345 --json
    uv run python tools/query_edva_bankruptcy.py sources --json
    uv run python tools/query_edva_bankruptcy.py probe --json
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

import requests

try:
    from tools.env_loader import load_env_file
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
    from env_loader import load_env_file
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


SOURCE_ID = "us-va-ed-bankruptcy-pacer-recap"
COURT_ID = "us-bankr-edva"
COURTLISTENER_COURT_ID = "vaeb"
COURT_NAME = "United States Bankruptcy Court, Eastern District of Virginia"
STATE_CODE = "VA"

COURTLISTENER_BASE_URL = "https://www.courtlistener.com/api/rest/v4"
DOCKETS_URL = f"{COURTLISTENER_BASE_URL}/dockets/"
DOCKET_ENTRIES_URL = f"{COURTLISTENER_BASE_URL}/docket-entries/"
RECAP_FETCH_URL = f"{COURTLISTENER_BASE_URL}/recap-fetch/"
PRAYERS_URL = f"{COURTLISTENER_BASE_URL}/prayers/"

PACER_AUTH_URL = "https://pacer.login.uscourts.gov/services/cso-auth"
PACER_CASE_LOCATOR_URL = (
    "https://pcl.uscourts.gov/pcl-public-api/rest/cases/find"
)
PACER_DEVELOPER_URL = "https://pacer.uscourts.gov/file-case/developer-resources"
PACER_FEES_URL = "https://pacer.uscourts.gov/pacer-pricing-how-fees-work"
EDVA_PACER_INFO_URL = "https://www.vaeb.uscourts.gov/pacer-information"
EDVA_ECF_URL = "https://ecf.vaeb.uscourts.gov/"
EDVA_COPY_REQUEST_URL = (
    "https://www.vaeb.uscourts.gov/sites/vaeb/files/CopyRequestForm.pdf"
)
EDVA_FORMS_URL = "https://www.vaeb.uscourts.gov/bankruptcy-forms"
RECAP_COVERAGE_URL = "https://www.courtlistener.com/help/coverage/recap/"
RECAP_API_DOCS_URL = (
    "https://wiki.free.law/c/courtlistener/help/api/rest/v4/recap"
)

DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_USER_AGENT = "Ithildin public-record research/1.0"
CURSOR_PREFIX = "edva-bankruptcy:v2:"
CURSOR_VERSION = 2

SENTINELS: tuple[dict[str, Any], ...] = (
    {
        "docket_number": "97-37920",
        "courtlistener_docket_id": 33467987,
        "pacer_case_id": "121166",
        "expected_date_blocked": "2021-01-21",
    },
    {
        "docket_number": "05-39367",
        "courtlistener_docket_id": 49921079,
        "pacer_case_id": "425734",
        "expected_date_blocked": "2021-01-28",
    },
)

FETCH_STATUS_LABELS = {
    1: "queued",
    2: "successful",
    3: "error",
    4: "processing",
    5: "retry",
    6: "invalid_request",
    7: "insufficient_metadata",
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="E.D. Virginia Bankruptcy PACER and RECAP Access",
    source_role="federal_bankruptcy_docket_metadata_and_document_acquisition",
    base_url=RECAP_FETCH_URL,
    dataset_id="courtlistener-recap-vaeb",
    metadata={
        "authority": [
            "United States Bankruptcy Court, Eastern District of Virginia",
            "Administrative Office of the United States Courts",
        ],
        "archive_operator": "Free Law Project",
        "courtlistener_court_id": COURTLISTENER_COURT_ID,
        "court_id": COURT_ID,
        "state_code": STATE_CODE,
        "read_pagination": "courtlistener_cursor",
        "acquisition": "explicit_asynchronous_recap_fetch",
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-va-ed-bankruptcy",
    name=COURT_NAME,
    state_code=STATE_CODE,
    metadata={
        "court_id": COURT_ID,
        "courtlistener_court_id": COURTLISTENER_COURT_ID,
        "court_level": "federal_bankruptcy",
    },
)

SOURCE_WARNINGS = (
    "RECAP availability reflects documents contributed to or acquired through "
    "the archive; it is not a completeness statement about the official docket.",
    "A docket date_blocked value or an empty RECAP entry response is preserved "
    "as an access gap, not interpreted as proof that the case has no filings.",
)


class EDVABankruptcyError(RuntimeError):
    """Source, access, or response error with result-envelope semantics."""

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


class SourceChangedError(EDVABankruptcyError):
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
class CursorCollection:
    records: tuple[dict[str, Any], ...]
    pages_fetched: int
    next_cursor: str | None
    source_urls: tuple[str, ...]
    incomplete_error: EDVABankruptcyError | None = None


@dataclass(frozen=True)
class CursorState:
    url: str
    offset: int
    criteria_fingerprint: str
    page_fingerprint: str | None


def _nonempty_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _last_path_id(value: Any) -> str | None:
    text = _nonempty_text(value)
    if not text:
        return None
    return text.rstrip("/").rsplit("/", 1)[-1] or None


def _scrub_credentials(value: Any) -> Any:
    """Remove credential-bearing fields if an upstream response echoes them."""

    secret_keys = {
        "password",
        "pacer_password",
        "pacer_username",
        "loginid",
        "nextgencso",
        "next_gen_cso",
        "otpcode",
        "otp_code",
    }
    if isinstance(value, Mapping):
        return {
            str(key): _scrub_credentials(item)
            for key, item in value.items()
            if str(key).lower() not in secret_keys
        }
    if isinstance(value, list):
        return [_scrub_credentials(item) for item in value]
    return value


def _cursor_criteria_fingerprint(
    url: str,
    params: Mapping[str, Any] | None,
) -> str:
    return sha256_fingerprint(
        {
            "url": url,
            "params": dict(params or {}),
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
        "url": url,
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
    expected_url: str,
    expected_criteria_fingerprint: str,
) -> CursorState:
    if not cursor.startswith(CURSOR_PREFIX):
        raise EDVABankruptcyError(
            "invalid_cursor",
            "The supplied cursor is not a cursor emitted by this adapter",
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
        url = str(payload["url"])
        offset = payload["offset"]
        criteria_fingerprint = str(payload["criteria_fingerprint"])
        page_fingerprint = payload.get("page_fingerprint")
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise EDVABankruptcyError(
            "invalid_cursor",
            "The supplied cursor is not a cursor emitted by this adapter",
            category="query_selection",
        ) from exc
    parsed = urlparse(url)
    expected = urlparse(expected_url)
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
        or parsed.scheme != "https"
        or parsed.scheme != expected.scheme
        or parsed.netloc != expected.netloc
        or parsed.path != expected.path
    ):
        raise EDVABankruptcyError(
            "invalid_cursor",
            "The supplied cursor does not match this CourtListener query",
            category="query_selection",
        )
    return CursorState(
        url=url,
        offset=offset,
        criteria_fingerprint=criteria_fingerprint,
        page_fingerprint=page_fingerprint,
    )


class EDVABankruptcyClient:
    """Transport-injectable CourtListener/RECAP client."""

    def __init__(
        self,
        *,
        token: str | None = None,
        session: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if token is None:
            load_env_file()
        self.token = token or os.environ.get("COURTLISTENER_TOKEN")
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

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        if self.token:
            headers["Authorization"] = f"Token {self.token}"
        return headers

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> tuple[Any, str]:
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                response = self.session.request(
                    method,
                    url,
                    params=dict(params) if params else None,
                    json=dict(payload) if payload else None,
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise EDVABankruptcyError(
                    "transport_error",
                    f"CourtListener request failed: {exc}",
                    category="transport",
                    retryable=True,
                    details={"url": url},
                ) from exc

            response_url = str(getattr(response, "url", url))
            status_code = int(getattr(response, "status_code", 0))
            if status_code in self.retry_policy.retry_statuses:
                if attempt < self.retry_policy.max_attempts:
                    retry_after: float | None = None
                    raw_retry = getattr(response, "headers", {}).get(
                        "Retry-After"
                    )
                    if raw_retry:
                        try:
                            retry_after = float(raw_retry)
                        except ValueError:
                            retry_after = None
                    self.sleeper(
                        self.retry_policy.delay(attempt, retry_after)
                    )
                    continue
                status = (
                    ResultStatus.RATE_LIMITED
                    if status_code == 429
                    else ResultStatus.UNAVAILABLE
                )
                raise EDVABankruptcyError(
                    "rate_limited" if status_code == 429 else "http_status",
                    f"CourtListener returned HTTP {status_code}",
                    status=status,
                    category="http",
                    retryable=True,
                    details={"url": response_url, "status_code": status_code},
                )
            if status_code in {401, 403}:
                raise EDVABankruptcyError(
                    "authentication_required",
                    f"CourtListener returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"url": response_url, "status_code": status_code},
                )
            if status_code < 200 or status_code >= 300:
                raise EDVABankruptcyError(
                    "http_status",
                    f"CourtListener returned HTTP {status_code}",
                    category="http",
                    retryable=status_code >= 500,
                    details={"url": response_url, "status_code": status_code},
                )
            try:
                return response.json(), response_url
            except (ValueError, json.JSONDecodeError) as exc:
                raise SourceChangedError(
                    "non_json_response",
                    "CourtListener returned a non-JSON response",
                    details={"url": response_url},
                ) from exc
        raise EDVABankruptcyError(
            "transport_error",
            f"CourtListener request failed: {last_error}",
            category="transport",
            retryable=True,
            details={"url": url},
        )

    @staticmethod
    def _validate_object(payload: Any, *, url: str) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise SourceChangedError(
                "unexpected_object_shape",
                "CourtListener response is not a JSON object",
                details={"url": url},
            )
        return dict(payload)

    @staticmethod
    def _validate_page(
        payload: Any,
        *,
        url: str,
    ) -> tuple[list[dict[str, Any]], str | None]:
        obj = EDVABankruptcyClient._validate_object(payload, url=url)
        rows = obj.get("results")
        if not isinstance(rows, list):
            raise SourceChangedError(
                "pagination_shape_changed",
                "CourtListener cursor response is missing a results list",
                details={"url": url, "keys": sorted(obj)},
            )
        normalized: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                raise SourceChangedError(
                    "record_shape_changed",
                    "CourtListener cursor response contains a non-object row",
                    details={"url": url, "row_index": index},
                )
            normalized.append(dict(row))
        next_url = obj.get("next")
        if next_url is not None and not isinstance(next_url, str):
            raise SourceChangedError(
                "pagination_shape_changed",
                "CourtListener next cursor is not a URL",
                details={"url": url},
            )
        return normalized, next_url

    def get_docket(self, docket_id: int) -> dict[str, Any]:
        url = f"{DOCKETS_URL}{docket_id}/"
        payload, response_url = self._request_json("GET", url)
        return self._validate_object(payload, url=response_url)

    def paginate(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        one_page: bool = False,
    ) -> CursorCollection:
        if limit is not None and limit <= 0:
            raise EDVABankruptcyError(
                "invalid_limit",
                "--limit must be a positive integer",
                category="query_selection",
            )
        current_url = url
        offset = 0
        current_params = dict(params or {})
        criteria_fingerprint = _cursor_criteria_fingerprint(url, current_params)
        cursor_page_fingerprint: str | None = None
        if cursor:
            cursor_state = _decode_cursor(
                cursor,
                expected_url=url,
                expected_criteria_fingerprint=criteria_fingerprint,
            )
            current_url = cursor_state.url
            offset = cursor_state.offset
            cursor_page_fingerprint = cursor_state.page_fingerprint
            current_params = {}

        records: list[dict[str, Any]] = []
        pages_fetched = 0
        source_urls: list[str] = []
        seen_pages: set[tuple[str, int]] = set()
        next_cursor: str | None = None
        incomplete_error: EDVABankruptcyError | None = None

        while current_url:
            page_key = (current_url, offset)
            if page_key in seen_pages:
                incomplete_error = SourceChangedError(
                    "cursor_cycle",
                    "CourtListener pagination repeated the same cursor",
                    details={"url": current_url, "offset": offset},
                )
                break
            seen_pages.add(page_key)
            try:
                payload, response_url = self._request_json(
                    "GET",
                    current_url,
                    params=current_params,
                )
                page_rows, following_url = self._validate_page(
                    payload,
                    url=response_url,
                )
            except EDVABankruptcyError as exc:
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
            source_urls.append(response_url)
            current_params = {}
            page_fingerprint = sha256_fingerprint(page_rows)

            if (
                cursor_page_fingerprint is not None
                and page_fingerprint != cursor_page_fingerprint
            ):
                raise SourceChangedError(
                    "cursor_page_changed",
                    "CourtListener page contents changed before cursor resumption",
                    details={
                        "url": response_url,
                        "cursor_page_fingerprint": cursor_page_fingerprint,
                        "observed_page_fingerprint": page_fingerprint,
                    },
                )
            cursor_page_fingerprint = None

            if offset > len(page_rows):
                raise SourceChangedError(
                    "cursor_offset_changed",
                    "Cursor offset exceeds the returned CourtListener page",
                    details={
                        "url": response_url,
                        "offset": offset,
                        "page_rows": len(page_rows),
                    },
                )

            for row_index in range(offset, len(page_rows)):
                if limit is not None and len(records) >= limit:
                    next_cursor = _encode_cursor(
                        response_url,
                        criteria_fingerprint=criteria_fingerprint,
                        offset=row_index,
                        page_fingerprint=page_fingerprint,
                    )
                    return CursorCollection(
                        records=tuple(records),
                        pages_fetched=pages_fetched,
                        next_cursor=next_cursor,
                        source_urls=tuple(source_urls),
                    )
                records.append(page_rows[row_index])
            offset = 0

            if one_page:
                if following_url:
                    next_cursor = _encode_cursor(
                        following_url,
                        criteria_fingerprint=criteria_fingerprint,
                    )
                break
            if limit is not None and len(records) >= limit and following_url:
                next_cursor = _encode_cursor(
                    following_url,
                    criteria_fingerprint=criteria_fingerprint,
                )
                break
            current_url = following_url or ""

        return CursorCollection(
            records=tuple(records),
            pages_fetched=pages_fetched,
            next_cursor=next_cursor,
            source_urls=tuple(source_urls),
            incomplete_error=incomplete_error,
        )

    def find_dockets(self, docket_number: str) -> CursorCollection:
        return self.paginate(
            DOCKETS_URL,
            params={
                "court": COURTLISTENER_COURT_ID,
                "docket_number": docket_number,
            },
        )

    def get_entries(
        self,
        docket_id: int,
        *,
        limit: int | None = None,
        cursor: str | None = None,
        one_page: bool = False,
    ) -> CursorCollection:
        return self.paginate(
            DOCKET_ENTRIES_URL,
            params={"docket": docket_id},
            limit=limit,
            cursor=cursor,
            one_page=one_page,
        )

    def options(self, url: str) -> dict[str, Any]:
        payload, response_url = self._request_json("OPTIONS", url)
        return self._validate_object(payload, url=response_url)

    def create_fetch(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        response, response_url = self._request_json(
            "POST",
            RECAP_FETCH_URL,
            payload=payload,
        )
        return self._validate_object(response, url=response_url)

    def get_fetch(self, request_id: int) -> dict[str, Any]:
        url = f"{RECAP_FETCH_URL}{request_id}/"
        response, response_url = self._request_json("GET", url)
        return self._validate_object(response, url=response_url)

    def create_prayer(self, recap_document_id: int) -> dict[str, Any]:
        response, response_url = self._request_json(
            "POST",
            PRAYERS_URL,
            payload={"recap_document": recap_document_id},
        )
        return self._validate_object(response, url=response_url)


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


def _court() -> dict[str, Any]:
    return {
        "court_id": COURT_ID,
        "native_court_id": COURTLISTENER_COURT_ID,
        "name": COURT_NAME,
        "state_code": STATE_CODE,
        "court_level": "federal_bankruptcy",
        "official_url": EDVA_ECF_URL,
    }


def _normalize_document(raw: Mapping[str, Any]) -> dict[str, Any]:
    document_id = raw.get("id")
    return {
        "record_kind": "federal_bankruptcy_docket_document",
        "courtlistener_document_id": document_id,
        "canonical_ref": (
            f"courtlistener:recap-document:{document_id}"
            if document_id is not None
            else None
        ),
        "document_number": _nonempty_text(raw.get("document_number")),
        "attachment_number": raw.get("attachment_number"),
        "description": _nonempty_text(
            raw.get("description") or raw.get("short_description")
        ),
        "pacer_doc_id": _nonempty_text(raw.get("pacer_doc_id")),
        "is_available": bool(raw.get("is_available")),
        "page_count": raw.get("page_count"),
        "filepath_local": _nonempty_text(raw.get("filepath_local")),
        "filepath_ia": _nonempty_text(raw.get("filepath_ia")),
        "download_url": _nonempty_text(
            raw.get("download_url") or raw.get("absolute_url")
        ),
    }


def _normalize_entry(raw: Mapping[str, Any]) -> dict[str, Any]:
    entry_id = raw.get("id")
    documents = raw.get("recap_documents")
    if not isinstance(documents, list):
        documents = []
    return {
        "record_kind": "federal_bankruptcy_docket_entry",
        "courtlistener_entry_id": entry_id,
        "canonical_ref": (
            f"courtlistener:docket-entry:{entry_id}"
            if entry_id is not None
            else None
        ),
        "entry_number": raw.get("entry_number"),
        "date_filed": _nonempty_text(raw.get("date_filed")),
        "description": _nonempty_text(raw.get("description")),
        "recap_documents": [
            _normalize_document(document)
            for document in documents
            if isinstance(document, Mapping)
        ],
    }


def _source_docket_url(raw: Mapping[str, Any]) -> str | None:
    absolute_url = _nonempty_text(raw.get("absolute_url"))
    if not absolute_url:
        return None
    if absolute_url.startswith("http://") or absolute_url.startswith("https://"):
        return absolute_url
    return f"https://www.courtlistener.com{absolute_url}"


def _normalize_docket(
    raw: Mapping[str, Any],
    *,
    entries: Sequence[Mapping[str, Any]],
    pages_fetched: int,
    next_cursor: str | None,
    incomplete_error: EDVABankruptcyError | None,
    caller_limit: int | None,
) -> dict[str, Any]:
    docket_id = raw.get("id")
    date_blocked = _nonempty_text(raw.get("date_blocked"))
    filepath_ia = _nonempty_text(raw.get("filepath_ia"))
    filepath_ia_json = _nonempty_text(raw.get("filepath_ia_json"))
    normalized_entries = [_normalize_entry(row) for row in entries]
    document_count = sum(
        len(row["recap_documents"]) for row in normalized_entries
    )
    access_gap = bool(
        date_blocked
        or incomplete_error
        or next_cursor
        or not normalized_entries
    )
    return {
        "record_kind": "federal_bankruptcy_docket",
        "courtlistener_docket_id": docket_id,
        "canonical_ref": (
            f"courtlistener:docket:{docket_id}"
            if docket_id is not None
            else None
        ),
        "court": _court(),
        "docket_number": _nonempty_text(raw.get("docket_number")),
        "pacer_case_id": _nonempty_text(raw.get("pacer_case_id")),
        "case_name": _nonempty_text(
            raw.get("case_name") or raw.get("case_name_full")
        ),
        "date_filed": _nonempty_text(raw.get("date_filed")),
        "date_terminated": _nonempty_text(raw.get("date_terminated")),
        "date_blocked": date_blocked,
        "source_docket_url": _source_docket_url(raw),
        "internet_archive": {
            "docket_html": filepath_ia,
            "docket_json": filepath_ia_json,
        },
        "entries": normalized_entries,
        "coverage": {
            "entries_returned": len(normalized_entries),
            "documents_returned": document_count,
            "transport_pages_fetched": pages_fetched,
            "caller_limit": caller_limit,
            "caller_bound_reached": next_cursor is not None
            and incomplete_error is None,
            "source_pagination_complete": next_cursor is None
            and incomplete_error is None,
            "source_blocked_date": date_blocked,
            "document_access_gap": access_gap,
            "gap_reason": (
                "courtlistener_docket_blocked"
                if date_blocked
                else "pagination_incomplete"
                if incomplete_error
                else "caller_bound"
                if next_cursor
                else "no_recap_entries_returned"
                if not normalized_entries
                else None
            ),
        },
        "access_paths": {
            "recap_fetch": RECAP_FETCH_URL,
            "official_ecf": EDVA_ECF_URL,
            "official_pacer_information": EDVA_PACER_INFO_URL,
            "clerk_copy_request": EDVA_COPY_REQUEST_URL,
        },
    }


def _normalize_fetch(raw: Mapping[str, Any]) -> dict[str, Any]:
    scrubbed = _scrub_credentials(raw)
    status = scrubbed.get("status")
    try:
        status_number = int(status)
    except (TypeError, ValueError):
        status_number = None
    request_id = scrubbed.get("id")
    return {
        "record_kind": "recap_fetch_job",
        "canonical_ref": (
            f"courtlistener:recap-fetch:{request_id}"
            if request_id is not None
            else None
        ),
        "request_id": request_id,
        "request_type": scrubbed.get("request_type"),
        "status": status_number if status_number is not None else status,
        "status_label": FETCH_STATUS_LABELS.get(status_number, "unknown"),
        "docket": _last_path_id(scrubbed.get("docket")),
        "docket_number": _nonempty_text(scrubbed.get("docket_number")),
        "pacer_case_id": _nonempty_text(scrubbed.get("pacer_case_id")),
        "recap_document": _last_path_id(scrubbed.get("recap_document")),
        "date_created": _nonempty_text(scrubbed.get("date_created")),
        "date_completed": _nonempty_text(scrubbed.get("date_completed")),
        "message": _nonempty_text(scrubbed.get("message")),
        "status_url": (
            f"{RECAP_FETCH_URL}{request_id}/"
            if request_id is not None
            else None
        ),
    }


def _normalize_prayer(raw: Mapping[str, Any]) -> dict[str, Any]:
    scrubbed = _scrub_credentials(raw)
    prayer_id = scrubbed.get("id")
    status = scrubbed.get("status")
    return {
        "record_kind": "recap_document_prayer",
        "canonical_ref": (
            f"courtlistener:prayer:{prayer_id}"
            if prayer_id is not None
            else None
        ),
        "prayer_id": prayer_id,
        "recap_document": _last_path_id(scrubbed.get("recap_document")),
        "status": status,
        "date_created": _nonempty_text(scrubbed.get("date_created")),
    }


def source_inventory() -> dict[str, Any]:
    """Return role-specific routes for the same case/document questions."""

    return {
        "record_kind": "bankruptcy_access_source_inventory",
        "court": _court(),
        "routes": [
            {
                "route_id": "courtlistener_recap",
                "role": "free_docket_metadata_and_contributed_documents",
                "url": RECAP_COVERAGE_URL,
                "access": "courtlistener_account_token_for_api",
                "coverage_note": "Archive coverage varies by docket and document.",
            },
            {
                "route_id": "courtlistener_recap_fetch",
                "role": "supported_pacer_backed_docket_and_document_acquisition",
                "url": RECAP_API_DOCS_URL,
                "access": "courtlistener_token_and_pacer_account",
                "operation": "asynchronous_explicit_request",
            },
            {
                "route_id": "pacer_case_locator",
                "role": "official_exact_case_metadata_lookup",
                "url": PACER_CASE_LOCATOR_URL,
                "documentation_url": PACER_DEVELOPER_URL,
                "access": "pacer_account",
                "coverage_note": "Metadata locator; use PACER/ECF or RECAP Fetch for documents.",
            },
            {
                "route_id": "edva_cm_ecf",
                "role": "official_docket_and_document_access",
                "url": EDVA_ECF_URL,
                "access": "pacer_account",
                "pricing_url": PACER_FEES_URL,
            },
            {
                "route_id": "recap_pray_and_pay",
                "role": "wait_for_future_free_archive_availability",
                "url": PRAYERS_URL,
                "access": "courtlistener_account_token",
                "operation": "explicit_asynchronous_request",
            },
            {
                "route_id": "edva_clerk_copy_request",
                "role": "official_copy_request_for_electronic_or_paper_files",
                "url": EDVA_COPY_REQUEST_URL,
                "information_url": EDVA_FORMS_URL,
                "access": "request_form_and_applicable_copy_fees",
            },
            {
                "route_id": "edva_public_access_terminal",
                "role": "in_person_docket_and_document_access",
                "url": EDVA_PACER_INFO_URL,
                "access": "court_public_terminal",
            },
            {
                "route_id": "federal_records_archive",
                "role": "transferred_or_archived_older_case_files",
                "url": EDVA_FORMS_URL,
                "access": "court_archive_or_records_center_request",
            },
        ],
        "target_dockets": list(SENTINELS),
    }


def _missing_credentials(*names: str) -> tuple[str, ...]:
    load_env_file()
    return tuple(name for name in names if not os.environ.get(name))


def _pacer_fetch_credentials() -> dict[str, str]:
    required = ("PACER_USERNAME", "PACER_PASSWORD")
    missing = _missing_credentials(*required)
    if missing:
        raise EDVABankruptcyError(
            "credentials_required",
            "PACER credentials are required for this explicit acquisition command",
            status=ResultStatus.HUMAN_REQUIRED,
            category="access",
            details={"missing_environment_variables": list(missing)},
        )
    credentials = {
        "pacer_username": os.environ["PACER_USERNAME"],
        "pacer_password": os.environ["PACER_PASSWORD"],
    }
    client_code = os.environ.get("PACER_CLIENT_CODE")
    if client_code:
        credentials["client_code"] = client_code
    return credentials


def _error_result(
    query: PublicRecordsQuery,
    error: EDVABankruptcyError,
    *,
    records: Sequence[Mapping[str, Any]] = (),
    next_cursor: str | None = None,
    warnings: Sequence[str] = SOURCE_WARNINGS,
) -> PublicRecordsResult:
    status = ResultStatus.PARTIAL if records else error.status
    return PublicRecordsResult.failure(
        query,
        status,
        [error.to_contract_error()],
        records=records,
        next_cursor=next_cursor,
        warnings=warnings,
    )


def _case_result(
    args: argparse.Namespace,
    client: EDVABankruptcyClient,
) -> PublicRecordsResult:
    query = _query(
        "case",
        {"docket_number": args.docket_number},
        requested_limit=args.entry_limit,
        cursor=args.cursor,
        metadata={
            "selection": "exact_court_and_docket_number",
            "pagination": (
                "caller_bound" if args.entry_limit else "exhaustive"
            ),
        },
    )
    try:
        matches = client.find_dockets(args.docket_number)
        exact = [
            row
            for row in matches.records
            if _nonempty_text(row.get("docket_number"))
            == args.docket_number.strip()
            and _last_path_id(row.get("court"))
            == COURTLISTENER_COURT_ID
        ]
        records: list[dict[str, Any]] = []
        errors: list[EDVABankruptcyError] = []
        next_cursor: str | None = None
        for raw_docket in exact:
            docket_id = raw_docket.get("id")
            if not isinstance(docket_id, int):
                raise SourceChangedError(
                    "docket_id_missing",
                    "Exact CourtListener docket result has no integer id",
                    details={"docket_number": args.docket_number},
                )
            collection = client.get_entries(
                docket_id,
                limit=args.entry_limit,
                cursor=args.cursor,
            )
            if collection.incomplete_error:
                errors.append(collection.incomplete_error)
            if collection.next_cursor:
                next_cursor = collection.next_cursor
            records.append(
                _normalize_docket(
                    raw_docket,
                    entries=collection.records,
                    pages_fetched=collection.pages_fetched,
                    next_cursor=collection.next_cursor,
                    incomplete_error=collection.incomplete_error,
                    caller_limit=args.entry_limit,
                )
            )
        if matches.incomplete_error:
            errors.append(matches.incomplete_error)
        if errors:
            return PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL if records else errors[0].status,
                [error.to_contract_error() for error in errors],
                records=records,
                next_cursor=next_cursor,
                warnings=SOURCE_WARNINGS,
            )
        return PublicRecordsResult.success(
            query,
            records,
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    except EDVABankruptcyError as exc:
        return _error_result(query, exc)


def _entries_result(
    args: argparse.Namespace,
    client: EDVABankruptcyClient,
) -> PublicRecordsResult:
    query = _query(
        "entries",
        {"courtlistener_docket_id": args.docket_id},
        requested_limit=args.limit,
        cursor=args.cursor,
        metadata={
            "pagination": "caller_bound" if args.limit else "exhaustive",
        },
    )
    try:
        docket = client.get_docket(args.docket_id)
        collection = client.get_entries(
            args.docket_id,
            limit=args.limit,
            cursor=args.cursor,
        )
        record = _normalize_docket(
            docket,
            entries=collection.records,
            pages_fetched=collection.pages_fetched,
            next_cursor=collection.next_cursor,
            incomplete_error=collection.incomplete_error,
            caller_limit=args.limit,
        )
        if collection.incomplete_error:
            return _error_result(
                query,
                collection.incomplete_error,
                records=[record],
                next_cursor=collection.next_cursor,
            )
        return PublicRecordsResult.success(
            query,
            [record],
            next_cursor=collection.next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    except EDVABankruptcyError as exc:
        return _error_result(query, exc)


def _fetch_docket_result(
    args: argparse.Namespace,
    client: EDVABankruptcyClient,
) -> PublicRecordsResult:
    identifiers = {
        key: value
        for key, value in {
            "docket": args.docket_id,
            "docket_number": args.docket_number,
            "pacer_case_id": args.pacer_case_id,
        }.items()
        if value is not None
    }
    query = _query("fetch_docket", identifiers)
    if not identifiers:
        return _error_result(
            query,
            EDVABankruptcyError(
                "identifier_required",
                "Provide --docket-id, --docket-number, or --pacer-case-id",
                category="query_selection",
            ),
        )
    try:
        payload: dict[str, Any] = {
            "request_type": 1,
            "court": COURTLISTENER_COURT_ID,
            **identifiers,
            **_pacer_fetch_credentials(),
        }
        response = client.create_fetch(payload)
        return PublicRecordsResult.success(
            query,
            [_normalize_fetch(response)],
            warnings=SOURCE_WARNINGS,
        )
    except EDVABankruptcyError as exc:
        return _error_result(query, exc)


def _fetch_document_result(
    args: argparse.Namespace,
    client: EDVABankruptcyClient,
) -> PublicRecordsResult:
    query = _query(
        "fetch_document",
        {"courtlistener_recap_document_id": args.recap_document_id},
    )
    try:
        payload: dict[str, Any] = {
            "request_type": 2,
            "recap_document": args.recap_document_id,
            **_pacer_fetch_credentials(),
        }
        response = client.create_fetch(payload)
        return PublicRecordsResult.success(
            query,
            [_normalize_fetch(response)],
            warnings=SOURCE_WARNINGS,
        )
    except EDVABankruptcyError as exc:
        return _error_result(query, exc)


def _fetch_status_result(
    args: argparse.Namespace,
    client: EDVABankruptcyClient,
) -> PublicRecordsResult:
    query = _query("fetch_status", {"request_id": args.request_id})
    try:
        response = client.get_fetch(args.request_id)
        return PublicRecordsResult.success(
            query,
            [_normalize_fetch(response)],
            warnings=SOURCE_WARNINGS,
        )
    except EDVABankruptcyError as exc:
        return _error_result(query, exc)


def _prayer_result(
    args: argparse.Namespace,
    client: EDVABankruptcyClient,
) -> PublicRecordsResult:
    query = _query(
        "pray",
        {"courtlistener_recap_document_id": args.recap_document_id},
    )
    try:
        response = client.create_prayer(args.recap_document_id)
        return PublicRecordsResult.success(
            query,
            [_normalize_prayer(response)],
            warnings=SOURCE_WARNINGS,
        )
    except EDVABankruptcyError as exc:
        return _error_result(query, exc)


def _sources_result() -> PublicRecordsResult:
    return PublicRecordsResult.success(
        _query("sources"),
        [source_inventory()],
        warnings=SOURCE_WARNINGS,
    )


def _extract_post_fields(options: Mapping[str, Any]) -> list[str]:
    actions = options.get("actions")
    if not isinstance(actions, Mapping):
        return []
    post = actions.get("POST")
    if not isinstance(post, Mapping):
        return []
    return sorted(str(key) for key in post)


def _probe_result(
    client: EDVABankruptcyClient,
) -> PublicRecordsResult:
    query = _query(
        "probe",
        metadata={
            "probe_scope": "bounded_source_health_check",
            "target_dockets": len(SENTINELS),
            "docket_entry_pages_per_target": 1,
            "options_requests": 1,
            "coverage_inference": False,
        },
    )
    try:
        observations: list[dict[str, Any]] = []
        for sentinel in SENTINELS:
            docket = client.get_docket(
                int(sentinel["courtlistener_docket_id"])
            )
            entries = client.get_entries(
                int(sentinel["courtlistener_docket_id"]),
                one_page=True,
            )
            observations.append(
                {
                    "docket_number": _nonempty_text(
                        docket.get("docket_number")
                    ),
                    "courtlistener_docket_id": docket.get("id"),
                    "pacer_case_id": _nonempty_text(
                        docket.get("pacer_case_id")
                    ),
                    "date_blocked": _nonempty_text(
                        docket.get("date_blocked")
                    ),
                    "first_page_entry_count": len(entries.records),
                    "first_page_has_next": entries.next_cursor is not None,
                    "matches_sentinel": (
                        docket.get("id")
                        == sentinel["courtlistener_docket_id"]
                        and _nonempty_text(docket.get("docket_number"))
                        == sentinel["docket_number"]
                        and _nonempty_text(docket.get("pacer_case_id"))
                        == sentinel["pacer_case_id"]
                    ),
                }
            )
        options = client.options(RECAP_FETCH_URL)
        post_fields = _extract_post_fields(options)
        required_fields = {
            "request_type",
            "court",
            "docket",
            "docket_number",
            "pacer_case_id",
            "pacer_username",
            "pacer_password",
            "recap_document",
        }
        record = {
            "record_kind": "source_probe",
            "probe_scope": {
                "bounded": True,
                "docket_entry_pages_per_target": 1,
                "coverage_inference": False,
            },
            "sentinel_observations": observations,
            "recap_fetch_post_fields": post_fields,
            "recap_fetch_contract_present": required_fields.issubset(
                post_fields
            ),
            "healthy": (
                all(row["matches_sentinel"] for row in observations)
                and required_fields.issubset(post_fields)
            ),
        }
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )
    except EDVABankruptcyError as exc:
        return _error_result(query, exc)


def execute(
    args: argparse.Namespace,
    *,
    client: EDVABankruptcyClient | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    owns_client = client is None
    active_client = client or EDVABankruptcyClient()
    try:
        if args.command == "case":
            result = _case_result(args, active_client)
        elif args.command == "entries":
            result = _entries_result(args, active_client)
        elif args.command == "fetch-docket":
            result = _fetch_docket_result(args, active_client)
        elif args.command == "fetch-document":
            result = _fetch_document_result(args, active_client)
        elif args.command == "fetch-status":
            result = _fetch_status_result(args, active_client)
        elif args.command == "pray":
            result = _prayer_result(args, active_client)
        elif args.command == "sources":
            result = _sources_result()
        elif args.command == "probe":
            result = _probe_result(active_client)
        else:
            raise AssertionError(f"unknown command: {args.command}")
    finally:
        if owns_client:
            active_client.close()

    if log_results:
        result_count = (
            len(result.records)
            if result.status
            in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
            else None
        )
        try:
            log_search(
                canonical_json(result.query.to_dict()),
                SOURCE_ID,
                result_count,
            )
        except Exception:
            pass
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    case = subparsers.add_parser(
        "case",
        help="Resolve an exact E.D. Virginia bankruptcy docket and its RECAP entries",
    )
    case.add_argument("docket_number")
    case.add_argument(
        "--entry-limit",
        type=int,
        help="Caller-selected maximum docket entries; omitted means exhaustive",
    )
    case.add_argument(
        "--cursor",
        help="Resume from a cursor emitted by a prior bounded result",
    )
    add_output_args(case)

    entries = subparsers.add_parser(
        "entries",
        help="Read RECAP docket entries for a CourtListener docket id",
    )
    entries.add_argument("docket_id", type=int)
    entries.add_argument(
        "--limit",
        type=int,
        help="Caller-selected maximum rows; omitted means exhaustive",
    )
    entries.add_argument(
        "--cursor",
        help="Resume from a cursor emitted by a prior bounded result",
    )
    add_output_args(entries)

    fetch_docket = subparsers.add_parser(
        "fetch-docket",
        help="Create an explicit asynchronous PACER-backed docket acquisition",
    )
    fetch_docket.add_argument("--docket-id", type=int)
    fetch_docket.add_argument("--docket-number")
    fetch_docket.add_argument("--pacer-case-id")
    add_output_args(fetch_docket)

    fetch_document = subparsers.add_parser(
        "fetch-document",
        help="Create an explicit PACER-backed document acquisition",
    )
    fetch_document.add_argument("recap_document_id", type=int)
    add_output_args(fetch_document)

    fetch_status = subparsers.add_parser(
        "fetch-status",
        help="Read the state of a RECAP Fetch request",
    )
    fetch_status.add_argument("request_id", type=int)
    add_output_args(fetch_status)

    pray = subparsers.add_parser(
        "pray",
        help="Register an explicit wait request for an unavailable RECAP document",
    )
    pray.add_argument("recap_document_id", type=int)
    add_output_args(pray)

    sources = subparsers.add_parser(
        "sources",
        help="Show official and credible role-specific access alternatives",
    )
    add_output_args(sources)

    probe = subparsers.add_parser(
        "probe",
        help="Run a bounded read-only contract and sentinel check",
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
    parser = build_parser()
    args = parser.parse_args()
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
