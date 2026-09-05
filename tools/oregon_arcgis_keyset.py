"""Bounded deterministic ArcGIS layer access for public-record adapters."""

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

import requests

try:
    from tools.public_records_contract import canonical_json, sha256_fingerprint
    from tools.public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TransportError,
        arcgis_declared_schema,
        schema_fingerprint,
        system_trust_session,
    )
except ImportError:
    from public_records_contract import canonical_json, sha256_fingerprint
    from public_records_http import (
        HTTPStatusError,
        MinimumIntervalRateLimiter,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TransportError,
        arcgis_declared_schema,
        schema_fingerprint,
        system_trust_session,
    )


DEFAULT_USER_AGENT = "Ithildin-Public-Records/1.0"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_MAXIMUM_JSON_BYTES = 32 * 1024 * 1024
DEFAULT_MAXIMUM_ERROR_BYTES = 8 * 1024
CURSOR_VERSION = 1


class _ArcGISStreamError(RuntimeError):
    """Retain whether a streamed response failed before yielding any bytes."""

    def __init__(
        self,
        error: requests.RequestException,
        *,
        bytes_read: int,
    ) -> None:
        super().__init__(str(error))
        self.error = error
        self.bytes_read = bytes_read


@dataclass(frozen=True)
class ArcGISLayerManifest:
    source_id: str
    name: str
    layer_url: str
    layer_id: int
    service_item_id: str | None
    expected_layer_name: str
    object_id_field: str
    required_fields: tuple[str, ...]
    source_crs_wkids: tuple[int, ...]
    record_kind: str
    publisher: str
    observed_count: int | None = None
    maximum_json_bytes: int = DEFAULT_MAXIMUM_JSON_BYTES
    maximum_error_bytes: int = DEFAULT_MAXIMUM_ERROR_BYTES
    has_attachments: bool = False

    def __post_init__(self) -> None:
        parsed = urlparse(self.layer_url)
        if (
            parsed.scheme.casefold() != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("layer_url must be an unauthenticated HTTPS URL")
        if not re.search(r"/(?:FeatureServer|MapServer)/[0-9]+$", parsed.path, re.I):
            raise ValueError("layer_url must identify a concrete ArcGIS layer")
        if not self.required_fields or self.object_id_field not in self.required_fields:
            raise ValueError("required_fields must include the object ID")
        if not self.source_crs_wkids:
            raise ValueError("source_crs_wkids must be explicit")

    @property
    def query_url(self) -> str:
        return f"{self.layer_url.rstrip('/')}/query"

    def attachment_url(self, object_id: int, attachment_id: int | None = None) -> str:
        base = f"{self.layer_url.rstrip('/')}/{object_id}/attachments"
        return f"{base}/{attachment_id}" if attachment_id is not None else base

    def contract_record(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "layer_url": self.layer_url,
            "layer_id": self.layer_id,
            "service_item_id": self.service_item_id,
            "expected_layer_name": self.expected_layer_name,
            "object_id_field": self.object_id_field,
            "required_fields": list(self.required_fields),
            "source_crs_wkids": list(self.source_crs_wkids),
            "record_kind": self.record_kind,
            "publisher": self.publisher,
            "observed_count": self.observed_count,
            "has_attachments": self.has_attachments,
            "maximum_json_bytes": self.maximum_json_bytes,
        }


@dataclass(frozen=True)
class ArcGISCursorState:
    source_id: str
    criteria_fingerprint: str
    schema_fingerprint: str
    boundary_object_id: int
    last_object_id: int
    snapshot_count: int


@dataclass(frozen=True)
class ArcGISBatch:
    features: tuple[Mapping[str, Any], ...]
    next_cursor: str | None
    total_count: int
    bounded_count: int
    boundary_object_id: int | None
    last_object_id: int | None
    schema_fingerprint: str
    pages_fetched: int
    count_changed_since_cursor: bool


def _header(response: Any, name: str) -> str | None:
    for key, value in getattr(response, "headers", {}).items():
        if str(key).casefold() == name.casefold():
            return str(value)
    return None


def _retry_after(response: Any) -> float | None:
    raw = _header(response, "retry-after")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


def _encode_cursor(prefix: str, payload: Mapping[str, Any]) -> str:
    encoded = base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8")).decode(
        "ascii"
    )
    return f"{prefix}{encoded.rstrip('=')}"


def _decode_cursor(prefix: str, cursor: str) -> Mapping[str, Any]:
    if not cursor.startswith(prefix):
        raise ValueError("continuation cursor belongs to a different adapter")
    value = cursor[len(prefix) :]
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("continuation cursor is malformed") from exc
    if not isinstance(payload, Mapping) or payload.get("v") != CURSOR_VERSION:
        raise ValueError("continuation cursor version is unsupported")
    return payload


def cursor_prefix(
    adapter_slug: str,
    *,
    namespace: str = "oregon",
) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", adapter_slug):
        raise ValueError("adapter_slug must be lowercase kebab case")
    if not re.fullmatch(r"[a-z0-9-]+", namespace):
        raise ValueError("cursor namespace must be lowercase kebab case")
    return f"{namespace}-{adapter_slug}-arcgis:v1:"


def decode_cursor(prefix: str, cursor: str) -> ArcGISCursorState:
    payload = _decode_cursor(prefix, cursor)
    try:
        state = ArcGISCursorState(
            source_id=str(payload["source"]),
            criteria_fingerprint=str(payload["criteria"]),
            schema_fingerprint=str(payload["schema"]),
            boundary_object_id=int(payload["boundary"]),
            last_object_id=int(payload["last_oid"]),
            snapshot_count=int(payload["snapshot_count"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("continuation cursor values are malformed") from exc
    if (
        state.boundary_object_id < 0
        or state.last_object_id < 0
        or state.last_object_id > state.boundary_object_id
        or state.snapshot_count < 0
        or not re.fullmatch(r"[0-9a-f]{64}", state.schema_fingerprint)
    ):
        raise ValueError("continuation cursor values are inconsistent")
    return state


def feature_attributes(feature: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("attributes", "properties"):
        value = feature.get(key)
        if isinstance(value, Mapping):
            return value
    raise SourceSchemaError(
        "ArcGIS feature lacks an attributes object",
        url="arcgis://feature",
        details={"feature_keys": sorted(str(key) for key in feature)},
    )


class BoundedArcGISClient:
    """Small requests client with bounded JSON bodies and injectable transport."""

    def __init__(
        self,
        manifest: ArcGISLayerManifest,
        *,
        session: requests.Session | Any | None = None,
        page_size: int = 1_000,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_attempts: int = 3,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if page_size < 1:
            raise ValueError("page_size must be positive")
        self.manifest = manifest
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.page_size = page_size
        self.timeout = timeout
        self.retry_policy = RetryPolicy(max_attempts=retry_attempts)
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            clock=clock,
            sleeper=sleeper,
        )
        self.sleeper = sleeper
        self.request_count = 0
        self.headers = {
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _validate_response_url(self, value: str) -> None:
        expected = urlparse(self.manifest.layer_url)
        observed = urlparse(value)
        service_root = re.sub(
            r"/[0-9]+$",
            "",
            expected.path,
        ).rstrip("/")
        if (
            observed.scheme.casefold() != "https"
            or observed.hostname != expected.hostname
            or observed.username
            or observed.password
            or not observed.path.startswith(service_root)
        ):
            raise SourceSchemaError(
                "ArcGIS response redirected outside its declared service",
                url=value,
            )

    @staticmethod
    def _read_bounded(
        response: Any,
        *,
        maximum_bytes: int,
    ) -> tuple[bytes, bool]:
        body = bytearray()
        truncated = False
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                remaining = maximum_bytes - len(body)
                if remaining <= 0:
                    truncated = True
                    break
                body.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    truncated = True
                    break
            return bytes(body), truncated
        except requests.RequestException as error:
            raise _ArcGISStreamError(
                error,
                bytes_read=len(body),
            ) from error
        finally:
            response.close()

    def _request_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any],
        maximum_bytes: int | None = None,
    ) -> Mapping[str, Any]:
        maximum = maximum_bytes or self.manifest.maximum_json_bytes
        last_error: requests.RequestException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                self.request_count += 1
                response = self.session.request(
                    "GET",
                    url,
                    params=params,
                    headers=self.headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    stream=True,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                break
            for hop in [*getattr(response, "history", ()), response]:
                self._validate_response_url(str(getattr(hop, "url", url)))
            status = int(getattr(response, "status_code", 0))
            if (
                status in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                delay = self.retry_policy.delay(attempt, _retry_after(response))
                response.close()
                self.sleeper(delay)
                continue
            if status == 429:
                response.close()
                raise RateLimitedHTTPError(status, url=url)
            if status in {401, 403}:
                response.close()
                raise RestrictedHTTPError(status, url=url)
            if status in {404, 410}:
                response.close()
                raise SourceChangedHTTPError(status, url=url)
            if status < 200 or status >= 300:
                try:
                    body, truncated = self._read_bounded(
                        response,
                        maximum_bytes=self.manifest.maximum_error_bytes,
                    )
                except _ArcGISStreamError as error:
                    last_error = error.error
                    if (
                        error.bytes_read == 0
                        and attempt < self.retry_policy.max_attempts
                    ):
                        self.sleeper(self.retry_policy.delay(attempt))
                        continue
                    raise TransportError(
                        "ArcGIS response stream failed",
                        url=url,
                        details={
                            "error": str(error.error),
                            "bytes_read": error.bytes_read,
                            "http_status": status,
                        },
                    ) from error
                excerpt = body.decode("utf-8", errors="replace")
                raise HTTPStatusError(
                    status,
                    url=url,
                    response_text=f"{excerpt}{'…' if truncated else ''}",
                )
            declared = _header(response, "content-length")
            if declared is not None:
                try:
                    declared_size = int(declared)
                except ValueError:
                    declared_size = None
                if declared_size is not None and declared_size > maximum:
                    response.close()
                    raise SourceSchemaError(
                        "ArcGIS JSON response exceeds its declared bound",
                        url=url,
                        details={
                            "declared_bytes": declared_size,
                            "maximum_bytes": maximum,
                        },
                    )
            try:
                body, truncated = self._read_bounded(
                    response,
                    maximum_bytes=maximum + 1,
                )
            except _ArcGISStreamError as error:
                last_error = error.error
                if error.bytes_read == 0 and attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise TransportError(
                    "ArcGIS response stream failed",
                    url=url,
                    details={
                        "error": str(error.error),
                        "bytes_read": error.bytes_read,
                        "http_status": status,
                    },
                ) from error
            if truncated or len(body) > maximum:
                raise SourceSchemaError(
                    "ArcGIS JSON response exceeded its bound while streaming",
                    url=url,
                    details={"bytes_read": len(body), "maximum_bytes": maximum},
                )
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SourceResponseError(
                    "ArcGIS returned invalid JSON",
                    url=url,
                    details={"error": str(exc)},
                ) from exc
            if not isinstance(payload, Mapping):
                raise SourceSchemaError(
                    "ArcGIS response must be a JSON object",
                    url=url,
                    details={"response_type": type(payload).__name__},
                )
            if "error" in payload:
                raise SourceResponseError(
                    "ArcGIS returned an error response",
                    url=url,
                    details={"response": payload["error"]},
                )
            return payload
        raise TransportError(
            "ArcGIS request failed after bounded retries",
            url=url,
            details={"error": str(last_error or "retry attempts exhausted")},
        )

    def fetch_metadata(self) -> Mapping[str, Any]:
        return self._request_json(self.manifest.layer_url, params={"f": "json"})

    def fetch_count(self, where: str) -> int:
        payload = self._request_json(
            self.manifest.query_url,
            params={"where": where, "returnCountOnly": "true", "f": "json"},
            maximum_bytes=128 * 1024,
        )
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "ArcGIS count is not a non-negative integer",
                url=self.manifest.query_url,
                details={"count": count},
            )
        return count

    def fetch_page(
        self,
        *,
        where: str,
        record_count: int,
        return_geometry: bool,
        descending: bool = False,
    ) -> tuple[Mapping[str, Any], ...]:
        payload = self._request_json(
            self.manifest.query_url,
            params={
                "where": where,
                "outFields": "*",
                "returnGeometry": str(return_geometry).lower(),
                "outSR": 4326,
                "orderByFields": (
                    f"{self.manifest.object_id_field} {'DESC' if descending else 'ASC'}"
                ),
                "resultRecordCount": record_count,
                "f": "json",
            },
        )
        features = payload.get("features")
        if not isinstance(features, list) or any(
            not isinstance(feature, Mapping) for feature in features
        ):
            raise SourceSchemaError(
                "ArcGIS response lacks a valid features array",
                url=self.manifest.query_url,
            )
        return tuple(features)

    def fetch_attachments(self, object_id: int) -> tuple[Mapping[str, Any], ...]:
        if not self.manifest.has_attachments:
            return ()
        url = self.manifest.attachment_url(object_id)
        payload = self._request_json(url, params={"f": "json"}, maximum_bytes=2_000_000)
        infos = payload.get("attachmentInfos")
        if not isinstance(infos, list) or any(
            not isinstance(info, Mapping) for info in infos
        ):
            raise SourceSchemaError(
                "ArcGIS attachment response is malformed",
                url=url,
            )
        return tuple(infos)


def metadata_contract(
    manifest: ArcGISLayerManifest,
    metadata: Mapping[str, Any],
) -> tuple[str, int]:
    expected = {
        "id": manifest.layer_id,
        "name": manifest.expected_layer_name,
    }
    if manifest.service_item_id is not None:
        expected["serviceItemId"] = manifest.service_item_id
    changed = {
        key: {"expected": expected_value, "observed": metadata.get(key)}
        for key, expected_value in expected.items()
        if metadata.get(key) != expected_value
    }
    if changed:
        raise SourceSchemaError(
            "ArcGIS layer identity changed",
            url=manifest.layer_url,
            details={"changed": changed},
        )
    fields = metadata.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "ArcGIS metadata lacks field declarations",
            url=manifest.layer_url,
        )
    names = {
        str(field.get("name")) for field in fields if field.get("name") is not None
    }
    declared_object_id = metadata.get("objectIdField")
    if declared_object_id is None:
        oid_fields = {
            str(field.get("name"))
            for field in fields
            if field.get("type") == "esriFieldTypeOID" and field.get("name") is not None
        }
        if oid_fields != {manifest.object_id_field}:
            raise SourceSchemaError(
                "ArcGIS layer lacks an unambiguous object-ID declaration",
                url=manifest.layer_url,
                details={
                    "expected": manifest.object_id_field,
                    "observed_oid_fields": sorted(oid_fields),
                },
            )
    elif declared_object_id != manifest.object_id_field:
        raise SourceSchemaError(
            "ArcGIS layer object-ID field changed",
            url=manifest.layer_url,
            details={
                "expected": manifest.object_id_field,
                "observed": declared_object_id,
            },
        )
    missing = sorted(set(manifest.required_fields) - names)
    if missing:
        raise SourceSchemaError(
            "ArcGIS layer is missing expected fields",
            url=manifest.layer_url,
            details={"missing_fields": missing},
        )
    wkids: set[int] = set()
    for spatial in (
        metadata.get("spatialReference"),
        metadata.get("sourceSpatialReference"),
        metadata.get("extent", {}).get("spatialReference")
        if isinstance(metadata.get("extent"), Mapping)
        else None,
    ):
        if isinstance(spatial, Mapping):
            for key in ("wkid", "latestWkid"):
                value = spatial.get(key)
                if isinstance(value, int) and not isinstance(value, bool):
                    wkids.add(value)
    if not wkids.intersection(manifest.source_crs_wkids):
        raise SourceSchemaError(
            "ArcGIS layer CRS changed",
            url=manifest.layer_url,
            details={
                "expected_wkids": list(manifest.source_crs_wkids),
                "observed_wkids": sorted(wkids),
            },
        )
    advanced = metadata.get("advancedQueryCapabilities")
    if not isinstance(advanced, Mapping) or not all(
        advanced.get(capability)
        for capability in ("supportsOrderBy", "supportsPagination")
    ):
        raise SourceSchemaError(
            "ArcGIS layer no longer declares ordered pagination",
            url=manifest.layer_url,
        )
    maximum = metadata.get("maxRecordCount")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 1:
        raise SourceSchemaError(
            "ArcGIS metadata lacks a positive maxRecordCount",
            url=manifest.layer_url,
            details={"maxRecordCount": maximum},
        )
    return schema_fingerprint(arcgis_declared_schema(fields)), maximum


def _object_id(
    manifest: ArcGISLayerManifest,
    feature: Mapping[str, Any],
) -> int:
    value = feature_attributes(feature).get(manifest.object_id_field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SourceSchemaError(
            "ArcGIS feature lacks an integer object ID",
            url=manifest.layer_url,
            details={
                "object_id_field": manifest.object_id_field,
                "value": value,
            },
        )
    return value


def _bounded_where(
    manifest: ArcGISLayerManifest,
    base_where: str,
    *,
    boundary: int,
    anchor: int | None = None,
) -> str:
    clauses = [
        f"({base_where})",
        f"{manifest.object_id_field} <= {boundary}",
    ]
    if anchor is not None:
        clauses.append(f"{manifest.object_id_field} > {anchor}")
    return " AND ".join(clauses)


def fetch_batch(
    client: BoundedArcGISClient | Any,
    manifest: ArcGISLayerManifest,
    *,
    adapter_slug: str,
    operation: str,
    where: str,
    limit: int,
    cursor: str | None,
    return_geometry: bool,
    cursor_namespace: str = "oregon",
) -> ArcGISBatch:
    if limit < 1:
        raise ValueError("limit must be positive")
    metadata = client.fetch_metadata()
    current_schema, server_page_size = metadata_contract(manifest, metadata)
    criteria = sha256_fingerprint(
        {
            "source_id": manifest.source_id,
            "operation": operation,
            "where": where,
            "return_geometry": return_geometry,
            "ordering": f"{manifest.object_id_field} ASC",
        }
    )
    prefix = cursor_prefix(adapter_slug, namespace=cursor_namespace)
    state = decode_cursor(prefix, cursor) if cursor else None
    if state is not None:
        if (
            state.source_id != manifest.source_id
            or state.criteria_fingerprint != criteria
        ):
            raise ValueError("continuation cursor belongs to different criteria")
        if state.schema_fingerprint != current_schema:
            raise SourceSchemaError(
                "ArcGIS schema changed after the continuation was issued",
                url=manifest.layer_url,
            )
    total_count = client.fetch_count(where)
    if state is None:
        boundary_page = client.fetch_page(
            where=where,
            record_count=1,
            return_geometry=False,
            descending=True,
        )
        boundary = _object_id(manifest, boundary_page[0]) if boundary_page else None
        bounded_count = total_count
        anchor = None
        snapshot_count = bounded_count
    else:
        boundary = state.boundary_object_id
        anchor = state.last_object_id
        bounded_count = client.fetch_count(
            _bounded_where(manifest, where, boundary=boundary)
        )
        snapshot_count = state.snapshot_count
    if boundary is None:
        return ArcGISBatch(
            features=(),
            next_cursor=None,
            total_count=total_count,
            bounded_count=0,
            boundary_object_id=None,
            last_object_id=None,
            schema_fingerprint=current_schema,
            pages_fetched=0,
            count_changed_since_cursor=False,
        )
    collected: list[Mapping[str, Any]] = []
    seen: set[int] = set()
    pages_fetched = 0
    target = limit + 1
    page_size = min(int(client.page_size), server_page_size)
    last_seen = anchor
    while len(collected) < target:
        requested = min(page_size, target - len(collected))
        page = client.fetch_page(
            where=_bounded_where(
                manifest,
                where,
                boundary=boundary,
                anchor=last_seen,
            ),
            record_count=requested,
            return_geometry=return_geometry,
        )
        pages_fetched += 1
        if not page:
            break
        for feature in page:
            object_id = _object_id(manifest, feature)
            if (
                object_id in seen
                or (last_seen is not None and object_id <= last_seen)
                or object_id > boundary
            ):
                raise SourceSchemaError(
                    "ArcGIS keyset page repeated or crossed its snapshot boundary",
                    url=manifest.layer_url,
                    details={
                        "object_id": object_id,
                        "previous_object_id": last_seen,
                        "boundary_object_id": boundary,
                    },
                )
            seen.add(object_id)
            last_seen = object_id
            collected.append(feature)
        if len(page) < requested:
            break
    has_more = len(collected) > limit
    returned = collected[:limit]
    returned_last = _object_id(manifest, returned[-1]) if returned else None
    next_cursor = None
    if has_more and returned_last is not None:
        next_cursor = _encode_cursor(
            prefix,
            {
                "v": CURSOR_VERSION,
                "source": manifest.source_id,
                "criteria": criteria,
                "schema": current_schema,
                "boundary": boundary,
                "last_oid": returned_last,
                "snapshot_count": snapshot_count,
            },
        )
    return ArcGISBatch(
        features=tuple(returned),
        next_cursor=next_cursor,
        total_count=total_count,
        bounded_count=bounded_count,
        boundary_object_id=boundary,
        last_object_id=returned_last,
        schema_fingerprint=current_schema,
        pages_fetched=pages_fetched,
        count_changed_since_cursor=(
            state is not None and bounded_count != snapshot_count
        ),
    )


def attachment_records(
    manifest: ArcGISLayerManifest,
    object_id: int,
    infos: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for info in infos:
        attachment_id = info.get("id")
        if isinstance(attachment_id, bool) or not isinstance(attachment_id, int):
            raise SourceSchemaError(
                "ArcGIS attachment lacks an integer ID",
                url=manifest.attachment_url(object_id),
            )
        records.append(
            {
                "attachment_id": attachment_id,
                "name": info.get("name"),
                "content_type": info.get("contentType"),
                "size_bytes": info.get("size"),
                "download_url": manifest.attachment_url(
                    object_id,
                    attachment_id,
                ),
            }
        )
    return records
