#!/usr/bin/env python3
"""Reusable client for Kofile/GovOS Neumo ``publicsearch.us`` tenants.

The public application bootstraps an anonymous HTTP session, then performs
search and document-detail requests over a versioned WebSocket protocol. Page
image URLs are signed for that anonymous session and must be fetched with the
same cookie jar.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urljoin, urlparse

import requests
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect as websocket_connect


SEARCH_REQUEST_TYPE = "@kofile/FETCH_DOCUMENTS/v4"
SEARCH_SUCCESS_TYPE = "@kofile/FETCH_DOCUMENTS_FULFILLED/v6"
SEARCH_FAILURE_TYPE = "@kofile/FETCH_DOCUMENTS_REJECTED/v6"
DETAIL_REQUEST_TYPE = "fetch-a-document"
DETAIL_SUCCESS_TYPE = "document"
DETAIL_FAILURE_TYPE = "error-fetching-document"

_SEARCH_SUCCESS_PREFIX = "@kofile/FETCH_DOCUMENTS_FULFILLED/"
_SEARCH_FAILURE_PREFIX = "@kofile/FETCH_DOCUMENTS_REJECTED/"
_HYDRATED_STATE_RE = re.compile(
    r"<script(?:\s[^>]*)?>\s*window\.__data\s*=\s*(.*?);\s*</script>",
    flags=re.DOTALL,
)


class KofilePublicSearchError(RuntimeError):
    """Base exception carrying a stable error code for source adapters."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        retryable: bool,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.details = dict(details or {})


class KofileAccessError(KofilePublicSearchError):
    """The anonymous session was not accepted for the requested resource."""


class KofileRateLimitError(KofilePublicSearchError):
    """The source returned an explicit rate-limit response."""


class KofileUnavailableError(KofilePublicSearchError):
    """The source could not complete an otherwise valid request."""


class KofileSourceChangedError(KofilePublicSearchError):
    """The source protocol or response schema no longer matches observations."""


class KofileNotFoundError(KofilePublicSearchError):
    """The source authoritatively reported that a selected document is absent."""


@dataclass(frozen=True)
class KofileBootstrap:
    """Anonymous tenant state hydrated by the public application shell."""

    state: Mapping[str, Any]
    auth_token: str
    ip: str
    tenant_id: str
    department_codes: tuple[str, ...]
    department_date_ranges: Mapping[str, Any]


@dataclass(frozen=True)
class KofileSearchPage:
    """One source-returned search page without an adapter-invented total cap."""

    records: tuple[Mapping[str, Any], ...]
    total_count: int
    statistics: Mapping[str, Any]
    offset: int
    limit: int
    next_offset: int | None
    response_type: str


@dataclass(frozen=True)
class KofilePageImage:
    """One page image fetched through its refreshed anonymous session."""

    document: Mapping[str, Any]
    page_number: int
    source_url: str
    media_type: str
    content: bytes
    etag: str | None


def _replace_javascript_undefined(raw: str) -> str:
    """Replace JavaScript ``undefined`` tokens outside strings with JSON null."""

    output: list[str] = []
    index = 0
    in_string = False
    escaped = False
    token = "undefined"
    while index < len(raw):
        character = raw[index]
        if in_string:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue
        if character == '"':
            in_string = True
            output.append(character)
            index += 1
            continue
        if raw.startswith(token, index):
            before = raw[index - 1] if index else ""
            after_index = index + len(token)
            after = raw[after_index] if after_index < len(raw) else ""
            if not (before.isalnum() or before in "_$") and not (
                after.isalnum() or after in "_$"
            ):
                output.append("null")
                index = after_index
                continue
        output.append(character)
        index += 1
    return "".join(output)


def parse_hydrated_state(html: str) -> dict[str, Any]:
    """Parse ``window.__data`` from a PublicSearch application response."""

    if not isinstance(html, str) or not html:
        raise KofileSourceChangedError(
            "PublicSearch bootstrap response was empty",
            code="bootstrap_state_missing",
            retryable=False,
        )
    match = _HYDRATED_STATE_RE.search(html)
    if match is None:
        raise KofileSourceChangedError(
            "PublicSearch bootstrap response lacks window.__data",
            code="bootstrap_state_missing",
            retryable=False,
        )
    try:
        state = json.loads(_replace_javascript_undefined(match.group(1)))
    except json.JSONDecodeError as error:
        raise KofileSourceChangedError(
            "PublicSearch bootstrap state is not parseable JSON",
            code="bootstrap_state_invalid",
            retryable=False,
            details={"line": error.lineno, "column": error.colno},
        ) from error
    if not isinstance(state, dict):
        raise KofileSourceChangedError(
            "PublicSearch bootstrap state must be an object",
            code="bootstrap_state_invalid",
            retryable=False,
        )
    return state


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise KofileSourceChangedError(
            f"PublicSearch response lacks object {field_name}",
            code="source_schema_changed",
            retryable=False,
            details={"field": field_name},
        )
    return value


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KofileSourceChangedError(
            f"PublicSearch response lacks {field_name}",
            code="source_schema_changed",
            retryable=False,
            details={"field": field_name},
        )
    return value.strip()


def _status_code(response: Any) -> int:
    try:
        return int(response.status_code)
    except (AttributeError, TypeError, ValueError) as error:
        raise KofileSourceChangedError(
            "HTTP transport response lacks a numeric status code",
            code="transport_contract_changed",
            retryable=False,
        ) from error


def _response_header(response: Any, name: str) -> str | None:
    headers = getattr(response, "headers", {})
    if not isinstance(headers, Mapping):
        return None
    for key, value in headers.items():
        if str(key).lower() == name.lower():
            return str(value)
    return None


def _http_error(response: Any, *, operation: str) -> None:
    status = _status_code(response)
    details = {"operation": operation, "http_status": status}
    if status in {401, 403}:
        raise KofileAccessError(
            f"PublicSearch denied anonymous {operation} access",
            code="anonymous_access_denied",
            retryable=False,
            details=details,
        )
    if status == 404:
        raise KofileNotFoundError(
            f"PublicSearch {operation} resource was not found",
            code="source_record_not_found",
            retryable=False,
            details=details,
        )
    if status == 429:
        raise KofileRateLimitError(
            f"PublicSearch rate-limited {operation}",
            code="source_rate_limited",
            retryable=True,
            details=details,
        )
    if status >= 500:
        raise KofileUnavailableError(
            f"PublicSearch failed {operation} with HTTP {status}",
            code="source_http_error",
            retryable=True,
            details=details,
        )
    if status >= 400:
        raise KofileUnavailableError(
            f"PublicSearch failed {operation} with HTTP {status}",
            code="source_http_error",
            retryable=False,
            details=details,
        )


def _remote_failure(response: Mapping[str, Any], *, operation: str) -> None:
    payload = response.get("payload")
    detail = payload if isinstance(payload, Mapping) else {}
    raw_status = (
        detail.get("status")
        or detail.get("statusCode")
        or detail.get("httpStatus")
    )
    try:
        status = int(raw_status)
    except (TypeError, ValueError):
        status = None
    reason = (
        detail.get("reason")
        or detail.get("message")
        or detail.get("error")
        or f"PublicSearch rejected {operation}"
    )
    if isinstance(reason, Mapping):
        reason = (
            reason.get("message")
            or reason.get("reason")
            or json.dumps(dict(reason), sort_keys=True)
        )
    details = {
        "operation": operation,
        "response_type": response.get("type"),
        "payload": dict(detail),
    }
    if status in {401, 403}:
        raise KofileAccessError(
            str(reason),
            code="anonymous_access_denied",
            retryable=False,
            details=details,
        )
    if status == 404 or "not found" in str(reason).casefold():
        raise KofileNotFoundError(
            str(reason),
            code="source_record_not_found",
            retryable=False,
            details=details,
        )
    if status == 429:
        raise KofileRateLimitError(
            str(reason),
            code="source_rate_limited",
            retryable=True,
            details=details,
        )
    raise KofileUnavailableError(
        str(reason),
        code="source_request_rejected",
        retryable=status is None or status >= 500,
        details=details,
    )


class KofilePublicSearchClient:
    """Anonymous HTTP/WebSocket client for one PublicSearch tenant."""

    def __init__(
        self,
        base_url: str,
        *,
        websocket_url: str | None = None,
        timeout: float = 30.0,
        session: requests.Session | Any | None = None,
        websocket_factory: Callable[..., Any] = websocket_connect,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.base_url = base_url.rstrip("/")
        ws_scheme = "wss" if parsed.scheme == "https" else "ws"
        self.websocket_url = websocket_url or (
            f"{ws_scheme}://{parsed.netloc}/ws"
        )
        self.timeout = timeout
        self.session = session or requests.Session()
        self.websocket_factory = websocket_factory
        self._bootstrap_state: KofileBootstrap | None = None
        self.request_count = 0

    def _cookie_values(self) -> dict[str, str]:
        jar = getattr(self.session, "cookies", None)
        if jar is None:
            return {}
        get_dict = getattr(jar, "get_dict", None)
        if callable(get_dict):
            return {
                str(key): str(value)
                for key, value in get_dict().items()
            }
        if isinstance(jar, Mapping):
            return {
                str(key): str(value)
                for key, value in jar.items()
            }
        try:
            return {
                str(cookie.name): str(cookie.value)
                for cookie in jar
            }
        except TypeError:
            return {}

    def _cookie_header(self) -> str:
        cookies = self._cookie_values()
        token = cookies.get("authToken")
        signature = cookies.get("authToken.sig")
        if not token or not signature:
            raise KofileSourceChangedError(
                "PublicSearch bootstrap did not issue its anonymous cookie pair",
                code="anonymous_cookie_missing",
                retryable=False,
            )
        return f"authToken={token}; authToken.sig={signature}"

    def bootstrap(self, *, force: bool = False) -> KofileBootstrap:
        """Hydrate tenant state and establish its anonymous cookie session."""

        if self._bootstrap_state is not None and not force:
            return self._bootstrap_state
        try:
            self.request_count += 1
            response = self.session.get(
                f"{self.base_url}/",
                timeout=self.timeout,
                headers={"Accept": "text/html,application/xhtml+xml"},
            )
        except requests.RequestException as error:
            raise KofileUnavailableError(
                f"PublicSearch bootstrap failed: {error}",
                code="bootstrap_transport_error",
                retryable=True,
            ) from error
        _http_error(response, operation="bootstrap")
        state = parse_hydrated_state(str(getattr(response, "text", "")))
        configuration = _mapping(
            state.get("configuration"),
            "configuration",
        )
        user = _mapping(state.get("user"), "user")
        auth_token = _required_text(user.get("authToken"), "user.authToken")
        ip = _required_text(user.get("ip"), "user.ip")
        tenant_id = _required_text(
            configuration.get("tenantId"),
            "configuration.tenantId",
        )
        cookie_values = self._cookie_values()
        if cookie_values.get("authToken") != auth_token:
            raise KofileSourceChangedError(
                "PublicSearch cookie and hydrated anonymous token disagree",
                code="anonymous_token_mismatch",
                retryable=False,
            )
        self._cookie_header()

        departments = configuration.get("departments")
        if not isinstance(departments, Sequence) or isinstance(
            departments,
            (str, bytes),
        ):
            raise KofileSourceChangedError(
                "PublicSearch configuration lacks a department list",
                code="source_schema_changed",
                retryable=False,
            )
        department_codes: list[str] = []
        for index, department in enumerate(departments):
            department_mapping = _mapping(
                department,
                f"configuration.departments[{index}]",
            )
            department_codes.append(
                _required_text(
                    department_mapping.get("code"),
                    f"configuration.departments[{index}].code",
                )
            )
        search_state = _mapping(state.get("search"), "search")
        date_ranges = _mapping(
            search_state.get("departmentDateRanges"),
            "search.departmentDateRanges",
        )
        bootstrap = KofileBootstrap(
            state=state,
            auth_token=auth_token,
            ip=ip,
            tenant_id=tenant_id,
            department_codes=tuple(department_codes),
            department_date_ranges=dict(date_ranges),
        )
        self._bootstrap_state = bootstrap
        return bootstrap

    def _exchange(
        self,
        *,
        request_type: str,
        payload: Mapping[str, Any],
        success_type: str,
        failure_type: str,
        operation: str,
    ) -> Mapping[str, Any]:
        bootstrap = self.bootstrap()
        correlation_id = str(uuid.uuid4())
        message = {
            "type": request_type,
            "payload": dict(payload),
            "authToken": bootstrap.auth_token,
            "ip": bootstrap.ip,
            "correlationId": correlation_id,
            "sync": True,
        }
        origin = self.base_url
        try:
            self.request_count += 1
            with self.websocket_factory(
                self.websocket_url,
                origin=origin,
                additional_headers={"Cookie": self._cookie_header()},
                open_timeout=self.timeout,
                close_timeout=min(5.0, self.timeout),
            ) as websocket:
                websocket.send(json.dumps(message))
                deadline = time.monotonic() + self.timeout
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    raw_response = websocket.recv(timeout=remaining)
                    if isinstance(raw_response, bytes):
                        raw_response = raw_response.decode("utf-8")
                    try:
                        response = json.loads(raw_response)
                    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
                        raise KofileSourceChangedError(
                            "PublicSearch WebSocket returned invalid JSON",
                            code="websocket_response_invalid",
                            retryable=False,
                        ) from error
                    response_mapping = _mapping(
                        response,
                        "websocket response",
                    )
                    response_type = response_mapping.get("type")
                    response_correlation = response_mapping.get("correlationId")
                    if (
                        response_correlation is not None
                        and response_correlation != correlation_id
                    ):
                        continue
                    if response_type == success_type:
                        return response_mapping
                    if response_type == failure_type:
                        _remote_failure(response_mapping, operation=operation)
                    if (
                        operation == "search"
                        and isinstance(response_type, str)
                        and response_type.startswith(
                            (_SEARCH_SUCCESS_PREFIX, _SEARCH_FAILURE_PREFIX)
                        )
                    ):
                        raise KofileSourceChangedError(
                            "PublicSearch search protocol version changed",
                            code="search_protocol_version_changed",
                            retryable=False,
                            details={
                                "expected_success": success_type,
                                "expected_failure": failure_type,
                                "observed": response_type,
                            },
                        )
        except KofilePublicSearchError:
            raise
        except (ConnectionClosed, OSError, TimeoutError) as error:
            raise KofileUnavailableError(
                f"PublicSearch {operation} WebSocket failed: {error}",
                code="websocket_transport_error",
                retryable=True,
                details={"operation": operation},
            ) from error

    def search(
        self,
        *,
        department: str,
        limit: int,
        offset: int = 0,
        search_value: str | None = None,
        search_ocr_text: bool = False,
        recorded_date_range: str | None = None,
        workspace_id: str | None = None,
    ) -> KofileSearchPage:
        """Fetch one search page with source-native offset pagination."""

        if not department.strip():
            raise ValueError("department must not be blank")
        if limit <= 0:
            raise ValueError("limit must be positive")
        if offset < 0:
            raise ValueError("offset must not be negative")
        if recorded_date_range and search_value and not search_ocr_text:
            raise ValueError(
                "date-range text search requires OCR mode; omit the text for "
                "date-only search"
            )
        query: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "department": department.strip(),
            "searchOcrText": bool(search_ocr_text),
        }
        if recorded_date_range:
            query.update(
                searchType="advancedSearch",
                recordedDateRange=recorded_date_range,
            )
            if search_value:
                query["ocrText"] = search_value
        else:
            query.update(
                searchType="quickSearch",
                searchValue=search_value or "",
            )
        response = self._exchange(
            request_type=SEARCH_REQUEST_TYPE,
            payload={
                "workspaceID": workspace_id or f"ithildin-{uuid.uuid4()}",
                "query": query,
            },
            success_type=SEARCH_SUCCESS_TYPE,
            failure_type=SEARCH_FAILURE_TYPE,
            operation="search",
        )
        payload = _mapping(response.get("payload"), "payload")
        data = _mapping(payload.get("data"), "payload.data")
        meta = _mapping(payload.get("meta"), "payload.meta")
        by_order = data.get("byOrder")
        by_hash = data.get("byHash")
        statistics = meta.get("statistics")
        if not isinstance(by_order, list):
            raise KofileSourceChangedError(
                "PublicSearch search response lacks data.byOrder",
                code="search_schema_changed",
                retryable=False,
            )
        by_hash_mapping = _mapping(by_hash, "payload.data.byHash")
        statistics_mapping = _mapping(
            statistics,
            "payload.meta.statistics",
        )
        try:
            total_count = int(meta.get("numRecords"))
        except (TypeError, ValueError) as error:
            raise KofileSourceChangedError(
                "PublicSearch search response lacks numeric numRecords",
                code="search_schema_changed",
                retryable=False,
            ) from error
        if total_count < 0:
            raise KofileSourceChangedError(
                "PublicSearch search response has negative numRecords",
                code="search_schema_changed",
                retryable=False,
            )
        records: list[Mapping[str, Any]] = []
        for identifier in by_order:
            record = by_hash_mapping.get(identifier)
            if record is None:
                record = by_hash_mapping.get(str(identifier))
            records.append(
                dict(_mapping(record, f"payload.data.byHash[{identifier}]"))
            )
        if total_count == 0 and records:
            raise KofileSourceChangedError(
                "PublicSearch returned records with numRecords zero",
                code="search_schema_changed",
                retryable=False,
            )
        if total_count > offset and not records:
            raise KofileSourceChangedError(
                "PublicSearch omitted a page within its reported result range",
                code="search_schema_changed",
                retryable=False,
            )
        consumed = offset + len(records)
        next_offset = consumed if consumed < total_count else None
        return KofileSearchPage(
            records=tuple(records),
            total_count=total_count,
            statistics=dict(statistics_mapping),
            offset=offset,
            limit=limit,
            next_offset=next_offset,
            response_type=str(response.get("type")),
        )

    def fetch_document(self, doc_id: int) -> Mapping[str, Any]:
        """Fetch exact document/case-file detail by source-native document ID."""

        if isinstance(doc_id, bool) or doc_id <= 0:
            raise ValueError("doc_id must be a positive integer")
        response = self._exchange(
            request_type=DETAIL_REQUEST_TYPE,
            payload={"id": doc_id},
            success_type=DETAIL_SUCCESS_TYPE,
            failure_type=DETAIL_FAILURE_TYPE,
            operation="detail",
        )
        payload_value = response.get("payload")
        payload = (
            _mapping(payload_value, "payload")
            if payload_value is not None
            else {
                key: value
                for key, value in response.items()
                if key not in {"type", "correlationId"}
            }
        )
        try:
            observed_id = int(payload.get("id"))
        except (TypeError, ValueError) as error:
            raise KofileSourceChangedError(
                "PublicSearch detail response lacks numeric id",
                code="detail_schema_changed",
                retryable=False,
            ) from error
        if observed_id != doc_id:
            raise KofileSourceChangedError(
                "PublicSearch detail response returned a different document",
                code="detail_identity_mismatch",
                retryable=False,
                details={"requested": doc_id, "observed": observed_id},
            )
        for field_name in ("docNumber", "rsId", "parties"):
            if field_name not in payload:
                raise KofileSourceChangedError(
                    f"PublicSearch detail response lacks {field_name}",
                    code="detail_schema_changed",
                    retryable=False,
                    details={"field": field_name},
                )
        return dict(payload)

    def fetch_page_image(
        self,
        doc_id: int,
        page_number: int,
        *,
        refresh_session: bool = True,
    ) -> KofilePageImage:
        """Refresh detail URLs and fetch one caller-selected page image."""

        if isinstance(page_number, bool) or page_number <= 0:
            raise ValueError("page_number must be a positive integer")
        if refresh_session:
            self.bootstrap(force=True)
        document = self.fetch_document(doc_id)
        if document.get("isSecured"):
            raise KofileAccessError(
                f"PublicSearch document {doc_id} is secured",
                code="source_record_secured",
                retryable=False,
                details={"doc_id": doc_id},
            )
        urls = document.get("urls")
        if not isinstance(urls, list) or any(
            not isinstance(value, str) for value in urls
        ):
            raise KofileSourceChangedError(
                "PublicSearch detail response lacks signed page URLs",
                code="page_manifest_changed",
                retryable=False,
            )
        if page_number > len(urls):
            raise KofileNotFoundError(
                f"Document {doc_id} has no page {page_number}",
                code="source_page_not_found",
                retryable=False,
                details={
                    "doc_id": doc_id,
                    "page_number": page_number,
                    "available_pages": len(urls),
                },
            )
        source_url = urljoin(f"{self.base_url}/", urls[page_number - 1])
        try:
            self.request_count += 1
            response = self.session.get(
                source_url,
                timeout=self.timeout,
                headers={"Accept": "image/*"},
            )
        except requests.RequestException as error:
            raise KofileUnavailableError(
                f"PublicSearch page image failed: {error}",
                code="page_image_transport_error",
                retryable=True,
            ) from error
        _http_error(response, operation="page_image")
        media_type = (
            _response_header(response, "Content-Type") or ""
        ).split(";", 1)[0].strip().lower()
        if not media_type.startswith("image/"):
            raise KofileSourceChangedError(
                "PublicSearch page response is not an image",
                code="page_image_type_changed",
                retryable=False,
                details={"content_type": media_type},
            )
        content = getattr(response, "content", None)
        if not isinstance(content, bytes) or not content:
            raise KofileSourceChangedError(
                "PublicSearch page response has no image bytes",
                code="page_image_empty",
                retryable=False,
            )
        return KofilePageImage(
            document=document,
            page_number=page_number,
            source_url=source_url,
            media_type=media_type,
            content=content,
            etag=_response_header(response, "ETag"),
        )

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()
