"""Reusable HTTP clients for common public-record open-data source families.

The clients in this module are deliberately transport-injectable so pagination,
rate limiting, retries, and failure semantics can be tested without live
endpoints. They return raw source records plus schema metadata; jurisdiction-
specific adapters remain responsible for field normalization.
"""

from __future__ import annotations

import json
import ssl
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import requests
import truststore

try:
    from tools.public_records_contract import (
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        ResultStatus,
        canonical_json,
        sha256_fingerprint,
    )
except ImportError:
    from public_records_contract import (
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        ResultStatus,
        canonical_json,
        sha256_fingerprint,
    )


class HTTPResponse(Protocol):
    """Minimal response interface accepted from an injected transport."""

    status_code: int
    headers: Mapping[str, Any]
    text: str

    def json(self) -> Any: ...


class HTTPTransport(Protocol):
    """Minimal requests-like transport interface."""

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HTTPResponse: ...


@dataclass(frozen=True)
class _UrllibResponse:
    status_code: int
    headers: Mapping[str, Any]
    text: str

    def json(self) -> Any:
        return json.loads(self.text)


class UrllibTransport:
    """Small standard-library transport used when no session is injected."""

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> _UrllibResponse:
        if params:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{urlencode(params, doseq=True)}"
        request = Request(url, headers=dict(headers or {}), method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                return _UrllibResponse(
                    status_code=response.status,
                    headers=dict(response.headers.items()),
                    text=body,
                )
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return _UrllibResponse(
                status_code=exc.code,
                headers=dict(exc.headers.items()) if exc.headers else {},
                text=body,
            )


class SystemTrustHTTPAdapter(requests.adapters.HTTPAdapter):
    """Requests adapter backed by the operating system certificate store."""

    def init_poolmanager(
        self,
        connections: int,
        maxsize: int,
        block: bool = requests.adapters.DEFAULT_POOLBLOCK,
        **pool_kwargs: Any,
    ) -> None:
        pool_kwargs["ssl_context"] = truststore.SSLContext(
            ssl.PROTOCOL_TLS_CLIENT
        )
        super().init_poolmanager(
            connections,
            maxsize,
            block=block,
            **pool_kwargs,
        )


def system_trust_session() -> requests.Session:
    """Return a requests session using the host certificate store."""

    session = requests.Session()
    session.mount("https://", SystemTrustHTTPAdapter())
    return session


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded deterministic retry/backoff configuration."""

    max_attempts: int = 3
    backoff_initial: float = 0.25
    backoff_multiplier: float = 2.0
    max_backoff: float = 5.0
    retry_statuses: frozenset[int] = field(
        default_factory=lambda: frozenset({429, 500, 502, 503, 504})
    )

    def __post_init__(self) -> None:
        if isinstance(self.max_attempts, bool) or self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        for field_name in (
            "backoff_initial",
            "backoff_multiplier",
            "max_backoff",
        ):
            value = getattr(self, field_name)
            if value < 0:
                raise ValueError(f"{field_name} must not be negative")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be at least 1")

    def delay(self, retry_number: int, retry_after: float | None = None) -> float:
        """Return the bounded delay before a one-indexed retry."""

        backoff = self.backoff_initial * (
            self.backoff_multiplier ** max(0, retry_number - 1)
        )
        if retry_after is not None:
            backoff = max(backoff, retry_after)
        return min(backoff, self.max_backoff)


class MinimumIntervalRateLimiter:
    """Thread-safe minimum-interval request limiter."""

    def __init__(
        self,
        minimum_interval: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if minimum_interval < 0:
            raise ValueError("minimum_interval must not be negative")
        self.minimum_interval = minimum_interval
        self._clock = clock
        self._sleeper = sleeper
        self._last_request_at: float | None = None
        self._lock = Lock()

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            if self._last_request_at is not None:
                delay = self.minimum_interval - (now - self._last_request_at)
                if delay > 0:
                    self._sleeper(delay)
                    now = self._clock()
            self._last_request_at = now


class PublicRecordsHTTPError(RuntimeError):
    """Base error carrying a public-record result status and structured details."""

    result_status = ResultStatus.UNAVAILABLE
    category = "http"
    retryable = False
    code = "http_error"

    def __init__(
        self,
        message: str,
        *,
        url: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        details = {"url": self.url, **self.details}
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=details,
        )


class TransportError(PublicRecordsHTTPError):
    result_status = ResultStatus.UNAVAILABLE
    category = "transport"
    retryable = True
    code = "transport_error"


class HTTPStatusError(PublicRecordsHTTPError):
    result_status = ResultStatus.UNAVAILABLE
    category = "http"
    code = "http_status"

    def __init__(
        self,
        status_code: int,
        *,
        url: str,
        response_text: str = "",
    ) -> None:
        super().__init__(
            f"HTTP {status_code} from public-record source",
            url=url,
            details={
                "status_code": status_code,
                "response_text": response_text[:500],
            },
        )
        self.status_code = status_code
        self.retryable = self.retryable or status_code >= 500


class RestrictedHTTPError(HTTPStatusError):
    result_status = ResultStatus.RESTRICTED
    category = "access"
    code = "access_restricted"


class TermsBlockedHTTPError(HTTPStatusError):
    result_status = ResultStatus.TERMS_BLOCKED
    category = "terms"
    code = "terms_blocked"


class RateLimitedHTTPError(HTTPStatusError):
    result_status = ResultStatus.RATE_LIMITED
    category = "rate_limit"
    retryable = True
    code = "rate_limited"


class SourceChangedHTTPError(HTTPStatusError):
    result_status = ResultStatus.SOURCE_CHANGED
    category = "source_schema"
    code = "source_endpoint_changed"


class SourceResponseError(PublicRecordsHTTPError):
    result_status = ResultStatus.UNAVAILABLE
    category = "source"
    code = "source_error_response"


class SourceSchemaError(PublicRecordsHTTPError):
    result_status = ResultStatus.SOURCE_CHANGED
    category = "source_schema"
    code = "source_schema_changed"


class PaginationError(SourceSchemaError):
    code = "pagination_stalled"


def failure_result(
    query: PublicRecordsQuery,
    error: PublicRecordsHTTPError,
    *,
    records: Sequence[Mapping[str, Any]] = (),
    next_cursor: str | None = None,
    warnings: Sequence[str] = (),
) -> PublicRecordsResult:
    """Convert an explicit HTTP/source failure into a non-empty error envelope."""

    status = error.result_status
    if records and status not in {ResultStatus.PARTIAL}:
        status = ResultStatus.PARTIAL
    return PublicRecordsResult.failure(
        query,
        status,
        [error.to_contract_error()],
        records=records,
        next_cursor=next_cursor,
        warnings=warnings,
    )


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, (list, tuple)):
        return "array"
    return type(value).__name__


def _observe_schema(
    value: Any,
    path: str,
    observed: dict[str, set[str]],
) -> None:
    value_type = _json_type(value)
    observed.setdefault(path, set()).add(value_type)
    if isinstance(value, Mapping):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            _observe_schema(item, child_path, observed)
    elif isinstance(value, (list, tuple)):
        for item in value:
            child_path = f"{path}[]" if path else "[]"
            _observe_schema(item, child_path, observed)


def inferred_schema(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Describe field paths and observed JSON types without sample-specific counts."""

    observed: dict[str, set[str]] = {}
    for record in records:
        for key, value in record.items():
            _observe_schema(value, str(key), observed)
    return {
        "kind": "inferred",
        "fields": [
            {"path": path, "types": sorted(types)}
            for path, types in sorted(observed.items())
        ],
    }


def arcgis_declared_schema(fields: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Normalize stable ArcGIS field declarations for drift fingerprinting."""

    stable_keys = ("name", "type", "alias", "sqlType", "length", "nullable")
    normalized = []
    for field_definition in fields:
        normalized.append(
            {
                key: field_definition.get(key)
                for key in stable_keys
                if key in field_definition
            }
        )
    normalized.sort(key=lambda value: str(value.get("name", "")))
    return {"kind": "arcgis_declared", "fields": normalized}


def schema_fingerprint(schema: Mapping[str, Any]) -> str:
    """Fingerprint a normalized schema description."""

    return sha256_fingerprint(schema)


@dataclass(frozen=True)
class PaginatedFetch:
    """Raw records and continuation metadata returned by a source-family client."""

    records: Sequence[Mapping[str, Any]]
    next_cursor: str | None
    schema: Mapping[str, Any]
    schema_fingerprint: str
    pages_fetched: int
    requests_made: int
    truncated_by_cap: bool = False
    warnings: Sequence[str] = field(default_factory=tuple)

    def to_result(
        self,
        query: PublicRecordsQuery,
        *,
        raw_artifact_refs: Sequence[str] = (),
    ) -> PublicRecordsResult:
        if self.truncated_by_cap:
            warning_values = tuple(self.warnings) or (
                "Result was truncated by the configured maximum-record cap.",
            )
            return PublicRecordsResult(
                query=query,
                status=ResultStatus.PARTIAL,
                records=self.records,
                next_cursor=self.next_cursor,
                raw_artifact_refs=raw_artifact_refs,
                warnings=warning_values,
            )
        return PublicRecordsResult.success(
            query,
            self.records,
            next_cursor=self.next_cursor,
            raw_artifact_refs=raw_artifact_refs,
            warnings=self.warnings,
        )


def _response_header(response: HTTPResponse, name: str) -> str | None:
    for key, value in response.headers.items():
        if str(key).lower() == name.lower():
            return str(value)
    return None


def _response_text(response: HTTPResponse) -> str:
    value = getattr(response, "text", "")
    return value if isinstance(value, str) else str(value)


def _transient_exception_types() -> tuple[type[BaseException], ...]:
    exceptions: list[type[BaseException]] = [
        TimeoutError,
        ConnectionError,
        URLError,
    ]
    try:
        import requests

        exceptions.append(requests.RequestException)
    except ImportError:
        pass
    return tuple(exceptions)


_TRANSIENT_EXCEPTIONS = _transient_exception_types()


class _BaseJSONClient:
    def __init__(
        self,
        *,
        transport: HTTPTransport | None = None,
        session: HTTPTransport | None = None,
        timeout: float = 30.0,
        retry_policy: RetryPolicy | None = None,
        minimum_interval: float = 0.25,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        user_agent: str = "Ithildin-Public-Records/1.0",
    ) -> None:
        if transport is not None and session is not None:
            raise ValueError("pass either transport or session, not both")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.transport = transport or session or UrllibTransport()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleeper = sleeper
        self._rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            clock=clock,
            sleeper=sleeper,
        )
        self.user_agent = user_agent
        self.request_count = 0

    def _request_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        request_headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            **dict(headers or {}),
        }
        last_transport_error: BaseException | None = None

        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.transport.request(
                    "GET",
                    url,
                    params=params,
                    headers=request_headers,
                    timeout=self.timeout,
                )
            except _TRANSIENT_EXCEPTIONS as exc:
                last_transport_error = exc
                if attempt >= self.retry_policy.max_attempts:
                    raise TransportError(
                        "Public-record source request failed after "
                        f"{attempt} attempts: {exc}",
                        url=url,
                        details={"attempts": attempt},
                    ) from exc
                self._sleeper(self.retry_policy.delay(attempt))
                continue

            status_code = int(
                getattr(response, "status_code", getattr(response, "status", 0))
            )
            if status_code in self.retry_policy.retry_statuses:
                retry_after = _response_header(response, "Retry-After")
                retry_after_seconds: float | None = None
                if retry_after is not None:
                    try:
                        retry_after_seconds = max(0.0, float(retry_after))
                    except ValueError:
                        retry_after_seconds = None
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(self.retry_policy.delay(attempt, retry_after_seconds))
                    continue
                if status_code == 429:
                    raise RateLimitedHTTPError(
                        status_code,
                        url=url,
                        response_text=_response_text(response),
                    )
                raise HTTPStatusError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )

            if status_code in {401, 403}:
                raise RestrictedHTTPError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            if status_code == 451:
                raise TermsBlockedHTTPError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            if status_code in {404, 410}:
                raise SourceChangedHTTPError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            if status_code < 200 or status_code >= 300:
                raise HTTPStatusError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )

            try:
                return response.json()
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise SourceSchemaError(
                    "Public-record source returned invalid JSON",
                    url=url,
                    details={"response_text": _response_text(response)[:500]},
                ) from exc

        raise TransportError(
            f"Public-record source request failed: {last_transport_error}",
            url=url,
            details={"attempts": self.retry_policy.max_attempts},
        )


def _validate_positive_integer(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _parse_offset_cursor(cursor: str | None, family: str) -> int:
    if cursor is None:
        return 0
    prefix = f"{family}:offset:"
    if cursor.startswith(prefix):
        raw_value = cursor[len(prefix) :]
    elif cursor.isdigit():
        raw_value = cursor
    else:
        raise ValueError(f"invalid {family} cursor")
    try:
        offset = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"invalid {family} cursor") from exc
    if offset < 0:
        raise ValueError(f"invalid {family} cursor")
    return offset


def _offset_cursor(family: str, offset: int) -> str:
    return f"{family}:offset:{offset}"


def _effective_cap(
    requested_limit: int | None,
    max_records: int | None,
) -> tuple[int | None, bool, list[str]]:
    if max_records is not None:
        _validate_positive_integer(max_records, "max_records")
    if requested_limit is None:
        return max_records, max_records is not None, []
    _validate_positive_integer(requested_limit, "requested_limit")
    if max_records is None:
        return requested_limit, False, []
    if requested_limit > max_records:
        return (
            max_records,
            True,
            [
                f"Requested {requested_limit} records but the configured cap is "
                f"{max_records}."
            ],
        )
    return requested_limit, False, []


class SocrataSODAClient(_BaseJSONClient):
    """Paginated client for Socrata SODA ``/resource`` JSON datasets."""

    def __init__(
        self,
        base_url: str,
        dataset_id: str,
        *,
        app_token: str | None = None,
        page_size: int = 1_000,
        max_records: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.base_url = base_url.rstrip("/")
        self.dataset_id = dataset_id.strip()
        if not self.base_url or not self.dataset_id:
            raise ValueError("base_url and dataset_id are required")
        self.page_size = _validate_positive_integer(page_size, "page_size")
        self.max_records = (
            _validate_positive_integer(max_records, "max_records")
            if max_records is not None
            else None
        )
        self.app_token = app_token

    @property
    def query_url(self) -> str:
        return f"{self.base_url}/{self.dataset_id}.json"

    def query(
        self,
        parameters: Mapping[str, Any] | None = None,
        *,
        requested_limit: int | None = None,
        max_records: int | None = None,
        cursor: str | None = None,
    ) -> PaginatedFetch:
        params = dict(parameters or {})
        parameter_limit = params.pop("$limit", None)
        parameter_offset = params.pop("$offset", None)
        if parameter_limit is not None:
            parsed_limit = int(parameter_limit)
            if requested_limit is not None and requested_limit != parsed_limit:
                raise ValueError("conflicting requested_limit and $limit")
            requested_limit = parsed_limit
        if cursor is not None and parameter_offset is not None:
            raise ValueError("pass either cursor or $offset, not both")
        offset = (
            _parse_offset_cursor(cursor, "socrata")
            if cursor is not None
            else int(parameter_offset or 0)
        )
        if offset < 0:
            raise ValueError("$offset must not be negative")

        configured_cap = max_records if max_records is not None else self.max_records
        cap, potentially_truncated, warnings = _effective_cap(
            requested_limit, configured_cap
        )
        records: list[Mapping[str, Any]] = []
        pages_fetched = 0
        start_request_count = self.request_count
        seen_pages: set[str] = set()
        source_has_more = False
        headers = {"X-App-Token": self.app_token} if self.app_token else {}

        while cap is None or len(records) < cap:
            page_limit = (
                self.page_size
                if cap is None
                else min(self.page_size, cap - len(records))
            )
            page_params = {
                **params,
                "$limit": page_limit,
                "$offset": offset,
            }
            payload = self._request_json(
                self.query_url,
                params=page_params,
                headers=headers,
            )
            pages_fetched += 1
            if isinstance(payload, Mapping) and "error" in payload:
                raise SourceResponseError(
                    "Socrata returned an error response",
                    url=self.query_url,
                    details={"response": payload},
                )
            if not isinstance(payload, list):
                raise SourceSchemaError(
                    "Socrata response must be a JSON array",
                    url=self.query_url,
                    details={"response_type": type(payload).__name__},
                )
            if any(not isinstance(record, Mapping) for record in payload):
                raise SourceSchemaError(
                    "Socrata response array contains a non-object record",
                    url=self.query_url,
                )

            page_records = list(payload)
            if page_records:
                page_fingerprint = sha256_fingerprint(page_records)
                if page_fingerprint in seen_pages:
                    raise PaginationError(
                        "Socrata pagination repeated an earlier page",
                        url=self.query_url,
                        details={"offset": offset},
                    )
                seen_pages.add(page_fingerprint)
            records.extend(page_records)
            offset += len(page_records)

            if len(page_records) < page_limit:
                source_has_more = False
                break
            source_has_more = True
            if not page_records:
                break

        truncated_by_cap = potentially_truncated and source_has_more
        next_cursor = _offset_cursor("socrata", offset) if source_has_more else None
        schema = inferred_schema(records)
        return PaginatedFetch(
            records=tuple(records),
            next_cursor=next_cursor,
            schema=schema,
            schema_fingerprint=schema_fingerprint(schema),
            pages_fetched=pages_fetched,
            requests_made=self.request_count - start_request_count,
            truncated_by_cap=truncated_by_cap,
            warnings=tuple(warnings),
        )


class ArcGISRESTClient(_BaseJSONClient):
    """Paginated client for ArcGIS FeatureServer/MapServer layer queries."""

    def __init__(
        self,
        layer_url: str,
        *,
        page_size: int = 1_000,
        max_records: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.layer_url = layer_url.rstrip("/")
        if not self.layer_url:
            raise ValueError("layer_url is required")
        self.page_size = _validate_positive_integer(page_size, "page_size")
        self.max_records = (
            _validate_positive_integer(max_records, "max_records")
            if max_records is not None
            else None
        )

    @property
    def query_url(self) -> str:
        return f"{self.layer_url}/query"

    def query(
        self,
        *,
        where: str = "1=1",
        out_fields: str | Sequence[str] = "*",
        parameters: Mapping[str, Any] | None = None,
        requested_limit: int | None = None,
        max_records: int | None = None,
        cursor: str | None = None,
        return_geometry: bool = False,
    ) -> PaginatedFetch:
        params = dict(parameters or {})
        parameter_limit = params.pop("resultRecordCount", None)
        parameter_offset = params.pop("resultOffset", None)
        if parameter_limit is not None:
            parsed_limit = int(parameter_limit)
            if requested_limit is not None and requested_limit != parsed_limit:
                raise ValueError("conflicting requested_limit and resultRecordCount")
            requested_limit = parsed_limit
        if cursor is not None and parameter_offset is not None:
            raise ValueError("pass either cursor or resultOffset, not both")
        offset = (
            _parse_offset_cursor(cursor, "arcgis")
            if cursor is not None
            else int(parameter_offset or 0)
        )
        if offset < 0:
            raise ValueError("resultOffset must not be negative")

        configured_cap = max_records if max_records is not None else self.max_records
        cap, potentially_truncated, warnings = _effective_cap(
            requested_limit, configured_cap
        )
        records: list[Mapping[str, Any]] = []
        pages_fetched = 0
        start_request_count = self.request_count
        seen_pages: set[str] = set()
        source_has_more = False
        declared_schema: dict[str, Any] | None = None
        out_fields_value = (
            ",".join(out_fields) if not isinstance(out_fields, str) else out_fields
        )

        while cap is None or len(records) < cap:
            page_limit = (
                self.page_size
                if cap is None
                else min(self.page_size, cap - len(records))
            )
            page_params = {
                **params,
                "where": where,
                "outFields": out_fields_value,
                "returnGeometry": str(return_geometry).lower(),
                "resultOffset": offset,
                "resultRecordCount": page_limit,
                "f": "json",
            }
            payload = self._request_json(self.query_url, params=page_params)
            pages_fetched += 1
            if not isinstance(payload, Mapping):
                raise SourceSchemaError(
                    "ArcGIS response must be a JSON object",
                    url=self.query_url,
                    details={"response_type": type(payload).__name__},
                )
            if "error" in payload:
                raise SourceResponseError(
                    "ArcGIS returned an error response",
                    url=self.query_url,
                    details={"response": payload["error"]},
                )
            features = payload.get("features")
            if not isinstance(features, list):
                raise SourceSchemaError(
                    "ArcGIS response is missing a features array",
                    url=self.query_url,
                )
            if any(not isinstance(feature, Mapping) for feature in features):
                raise SourceSchemaError(
                    "ArcGIS features array contains a non-object feature",
                    url=self.query_url,
                )

            page_records = list(features)
            if page_records:
                page_fingerprint = sha256_fingerprint(page_records)
                if page_fingerprint in seen_pages:
                    raise PaginationError(
                        "ArcGIS pagination repeated an earlier page",
                        url=self.query_url,
                        details={"offset": offset},
                    )
                seen_pages.add(page_fingerprint)

            fields = payload.get("fields")
            if fields is not None:
                if not isinstance(fields, list) or any(
                    not isinstance(field_definition, Mapping)
                    for field_definition in fields
                ):
                    raise SourceSchemaError(
                        "ArcGIS fields metadata is malformed",
                        url=self.query_url,
                    )
                page_schema = arcgis_declared_schema(fields)
                if declared_schema is not None and canonical_json(
                    declared_schema
                ) != canonical_json(page_schema):
                    raise SourceSchemaError(
                        "ArcGIS field declarations changed during pagination",
                        url=self.query_url,
                    )
                declared_schema = page_schema

            records.extend(page_records)
            offset += len(page_records)
            exceeded = payload.get("exceededTransferLimit")
            if exceeded is True:
                if not page_records:
                    raise PaginationError(
                        "ArcGIS reported more results without returning features",
                        url=self.query_url,
                        details={"offset": offset},
                    )
                source_has_more = True
            elif exceeded is False:
                source_has_more = False
            else:
                source_has_more = len(page_records) >= page_limit

            if not source_has_more:
                break

        truncated_by_cap = potentially_truncated and source_has_more
        next_cursor = _offset_cursor("arcgis", offset) if source_has_more else None
        schema = declared_schema or inferred_schema(records)
        return PaginatedFetch(
            records=tuple(records),
            next_cursor=next_cursor,
            schema=schema,
            schema_fingerprint=schema_fingerprint(schema),
            pages_fetched=pages_fetched,
            requests_made=self.request_count - start_request_count,
            truncated_by_cap=truncated_by_cap,
            warnings=tuple(warnings),
        )
