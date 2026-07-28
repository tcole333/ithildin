#!/usr/bin/env python3
"""Reusable bulk-file transport and archive helpers for public records.

The module separates a source's release manifest from transfer mechanics. It
supports snapshot and incremental releases, metadata/range probes, resumable
downloads, SHA-256 verification, and safe ZIP inspection/extraction.

Resource ceilings are opt-in and explicit through ``ArchiveSafetyPolicy`` and
``max_bytes``. Path traversal, duplicate paths, links, and special archive
members are always rejected because they can escape or alter the extraction
target.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import time
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

try:
    from tools.public_records_contract import (
        PublicRecordsError,
        ResultStatus,
        canonical_json,
        sha256_fingerprint,
    )
except ImportError:
    from public_records_contract import (
        PublicRecordsError,
        ResultStatus,
        canonical_json,
        sha256_fingerprint,
    )


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CONTENT_RANGE_TOTAL_RE = re.compile(r"/(\d+)$")
_CONTENT_RANGE_START_RE = re.compile(r"^bytes\s+(\d+)-\d+/\d+$", re.I)
_RETRYABLE_HTTP_STATUSES = frozenset({429, 500, 502, 503, 504})


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _json_value(value: Any) -> Any:
    """Return a detached JSON-compatible value."""
    return json.loads(canonical_json(value))


def _freeze(value: Any) -> Any:
    normalized = _json_value(value)
    if isinstance(normalized, dict):
        return MappingProxyType({key: _freeze(item) for key, item in normalized.items()})
    if isinstance(normalized, list):
        return tuple(_freeze(item) for item in normalized)
    return normalized


def _normalize_sha256(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = _require_text(value, field_name).lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a lowercase or uppercase SHA-256 hex digest")
    return normalized


def _positive_optional(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


@dataclass(frozen=True)
class BulkReleaseMetadata:
    """Version semantics for a bulk source release."""

    release_id: str
    kind: str
    effective_at: str | None = None
    base_release_id: str | None = None
    sequence: int | None = None
    coverage: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "release_id", _require_text(self.release_id, "release_id"))
        if self.kind not in {"snapshot", "incremental"}:
            raise ValueError("release kind must be snapshot or incremental")
        if self.effective_at is not None:
            object.__setattr__(
                self, "effective_at", _require_text(self.effective_at, "effective_at")
            )
        if self.base_release_id is not None:
            object.__setattr__(
                self,
                "base_release_id",
                _require_text(self.base_release_id, "base_release_id"),
            )
        if self.sequence is not None:
            object.__setattr__(
                self, "sequence", _positive_optional(self.sequence, "sequence")
            )
        object.__setattr__(self, "coverage", _freeze(self.coverage))

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "kind": self.kind,
            "effective_at": self.effective_at,
            "base_release_id": self.base_release_id,
            "sequence": self.sequence,
            "coverage": _json_value(self.coverage),
        }


@dataclass(frozen=True)
class BulkArtifact:
    """One downloadable artifact declared by a bulk release."""

    artifact_id: str
    url: str
    filename: str
    media_type: str | None = None
    archive_format: str | None = None
    expected_size: int | None = None
    expected_sha256: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "artifact_id", _require_text(self.artifact_id, "artifact_id")
        )
        normalized_url = _require_text(self.url, "url")
        if urlsplit(normalized_url).scheme not in {"http", "https"}:
            raise ValueError("bulk artifact URL must use HTTP or HTTPS")
        object.__setattr__(self, "url", normalized_url)
        filename = _require_text(self.filename, "filename")
        if Path(filename).name != filename or filename in {".", ".."}:
            raise ValueError("filename must be a basename")
        object.__setattr__(self, "filename", filename)
        for field_name in ("media_type", "archive_format", "etag", "last_modified"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _require_text(value, field_name))
        object.__setattr__(
            self,
            "expected_size",
            _positive_optional(self.expected_size, "expected_size"),
        )
        object.__setattr__(
            self,
            "expected_sha256",
            _normalize_sha256(self.expected_sha256, "expected_sha256"),
        )
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    @classmethod
    def from_url(
        cls,
        artifact_id: str,
        url: str,
        **kwargs: Any,
    ) -> "BulkArtifact":
        filename = Path(unquote(urlsplit(url).path)).name
        if not filename:
            raise ValueError("artifact URL does not contain a filename")
        return cls(artifact_id=artifact_id, url=url, filename=filename, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "url": self.url,
            "filename": self.filename,
            "media_type": self.media_type,
            "archive_format": self.archive_format,
            "expected_size": self.expected_size,
            "expected_sha256": self.expected_sha256,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "metadata": _json_value(self.metadata),
        }


@dataclass(frozen=True)
class BulkDatasetManifest:
    """Deterministic manifest for one source-scoped release."""

    source_id: str
    dataset_id: str
    release: BulkReleaseMetadata
    artifacts: Sequence[BulkArtifact]
    schema: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _require_text(self.source_id, "source_id"))
        object.__setattr__(
            self, "dataset_id", _require_text(self.dataset_id, "dataset_id")
        )
        if not isinstance(self.release, BulkReleaseMetadata):
            raise TypeError("release must be BulkReleaseMetadata")
        artifacts = tuple(self.artifacts)
        if not artifacts or any(not isinstance(item, BulkArtifact) for item in artifacts):
            raise ValueError("artifacts must contain at least one BulkArtifact")
        artifact_ids = [item.artifact_id for item in artifacts]
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("artifact IDs must be unique within a release")
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "schema", _freeze(self.schema))
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    @property
    def schema_fingerprint(self) -> str:
        return sha256_fingerprint(self.schema)

    @property
    def manifest_fingerprint(self) -> str:
        return sha256_fingerprint(self.fingerprint_payload())

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "release": self.release.to_dict(),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "schema": _json_value(self.schema),
            "metadata": _json_value(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        value = self.fingerprint_payload()
        value["schema_fingerprint"] = self.schema_fingerprint
        value["manifest_fingerprint"] = self.manifest_fingerprint
        return value


class BulkSourceError(RuntimeError):
    """Structured source-family error suitable for the shared result envelope."""

    result_status = ResultStatus.UNAVAILABLE
    code = "bulk_source_error"
    category = "bulk_source"
    retryable = False

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None):
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


class BulkTransportError(BulkSourceError):
    code = "bulk_transport_error"
    category = "transport"
    retryable = True


class BulkHTTPStatusError(BulkSourceError):
    code = "bulk_http_status"
    category = "http"

    def __init__(self, status_code: int, url: str, response_text: str = ""):
        self.status_code = status_code
        self.retryable = status_code in _RETRYABLE_HTTP_STATUSES
        if status_code == 429:
            self.result_status = ResultStatus.RATE_LIMITED
            self.code = "bulk_rate_limited"
            self.category = "rate_limit"
        elif status_code in {401, 403}:
            self.result_status = ResultStatus.RESTRICTED
            self.code = "bulk_access_restricted"
            self.category = "access"
        elif status_code in {404, 410}:
            self.result_status = ResultStatus.SOURCE_CHANGED
            self.code = "bulk_artifact_missing"
            self.category = "source"
        super().__init__(
            f"HTTP {status_code} from bulk source",
            details={
                "url": url,
                "status_code": status_code,
                "response_text": response_text[:500],
            },
        )


class BulkIntegrityError(BulkSourceError):
    result_status = ResultStatus.SOURCE_CHANGED
    code = "bulk_integrity_error"
    category = "integrity"


class ArchiveSafetyError(BulkSourceError):
    result_status = ResultStatus.SOURCE_CHANGED
    code = "unsafe_archive"
    category = "archive"


class _HTTPResponse(Protocol):
    headers: Any

    def read(self, size: int = -1) -> bytes: ...

    def close(self) -> None: ...

    def __enter__(self) -> "_HTTPResponse": ...

    def __exit__(self, *args: Any) -> None: ...


def _status(response: _HTTPResponse) -> int:
    return int(getattr(response, "status", getattr(response, "status_code", 0)))


def _headers(response: _HTTPResponse) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in response.headers.items()}


def _header_int(headers: Mapping[str, str], name: str) -> int | None:
    raw = headers.get(name.lower())
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value >= 0 else None


def _total_from_content_range(headers: Mapping[str, str]) -> int | None:
    raw = headers.get("content-range")
    if raw is None:
        return None
    match = _CONTENT_RANGE_TOTAL_RE.search(raw.strip())
    return int(match.group(1)) if match else None


def _sha256_from_headers(headers: Mapping[str, str]) -> str | None:
    for name in (
        "x-amz-meta-checksum-sha256",
        "x-checksum-sha256",
        "x-content-sha256",
    ):
        value = headers.get(name)
        if value and _SHA256_RE.fullmatch(value.strip().lower()):
            return value.strip().lower()

    digest = headers.get("digest", "")
    for component in digest.split(","):
        key, separator, value = component.strip().partition("=")
        if separator and key.lower() in {"sha-256", "sha256"}:
            try:
                decoded = base64.b64decode(value.strip(), validate=True)
            except ValueError:
                continue
            if len(decoded) == hashlib.sha256().digest_size:
                return decoded.hex()
    return None


def _retry_delay(attempt: int) -> float:
    return min(0.25 * (2 ** max(0, attempt - 1)), 5.0)


@dataclass(frozen=True)
class ArtifactProbe:
    """Metadata and bounded signature observation for one artifact."""

    url: str
    http_status: int
    content_length: int | None
    media_type: str | None
    etag: str | None
    last_modified: str | None
    accept_ranges: bool
    source_sha256: str | None
    sample_size: int
    sample_sha256: str | None
    signature_hex: str | None
    format_hint: str | None
    headers: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "http_status": self.http_status,
            "content_length": self.content_length,
            "media_type": self.media_type,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "accept_ranges": self.accept_ranges,
            "source_sha256": self.source_sha256,
            "sample_size": self.sample_size,
            "sample_sha256": self.sample_sha256,
            "signature_hex": self.signature_hex,
            "format_hint": self.format_hint,
            "headers": dict(sorted(self.headers.items())),
        }


@dataclass(frozen=True)
class DownloadResult:
    """Completed, verified bulk transfer."""

    path: str
    url: str
    size: int
    sha256: str
    expected_sha256: str | None
    etag: str | None
    last_modified: str | None
    resumed_from: int
    reused_existing: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "url": self.url,
            "size": self.size,
            "sha256": self.sha256,
            "expected_sha256": self.expected_sha256,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "resumed_from": self.resumed_from,
            "reused_existing": self.reused_existing,
        }


class BulkTransferClient:
    """HTTP client for bounded probes and resumable bulk transfers."""

    def __init__(
        self,
        *,
        timeout: float = 60.0,
        max_attempts: int = 3,
        chunk_size: int = 1024 * 1024,
        user_agent: str = "Ithildin-Public-Records/1.0",
        opener: Callable[..., _HTTPResponse] = urlopen,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.chunk_size = chunk_size
        self.user_agent = user_agent
        self._opener = opener
        self._sleeper = sleeper

    def _open_once(self, request: Request) -> _HTTPResponse:
        try:
            return self._opener(request, timeout=self.timeout)
        except HTTPError as error:
            body = error.read(500).decode("utf-8", errors="replace")
            raise BulkHTTPStatusError(error.code, request.full_url, body) from error
        except (URLError, TimeoutError, ConnectionError, OSError) as error:
            raise BulkTransportError(
                f"Bulk source request failed: {error}",
                details={"url": request.full_url},
            ) from error

    def _open_with_retry(self, request: Request) -> _HTTPResponse:
        last_error: BulkSourceError | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return self._open_once(request)
            except BulkSourceError as error:
                last_error = error
                if not error.retryable or attempt >= self.max_attempts:
                    raise
                self._sleeper(_retry_delay(attempt))
        assert last_error is not None
        raise last_error

    def _request(self, url: str, *, method: str, headers: Mapping[str, str] | None = None):
        return Request(
            url,
            method=method,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "*/*",
                **dict(headers or {}),
            },
        )

    def probe(self, artifact: BulkArtifact | str, *, sample_bytes: int = 4096) -> ArtifactProbe:
        """Issue a metadata request and optionally read a bounded leading range."""
        if sample_bytes < 0:
            raise ValueError("sample_bytes must not be negative")
        url = artifact.url if isinstance(artifact, BulkArtifact) else str(artifact)
        head_headers: dict[str, str] = {}
        head_status = 0
        try:
            with self._open_with_retry(self._request(url, method="HEAD")) as response:
                head_status = _status(response)
                if head_status < 200 or head_status >= 300:
                    raise BulkHTTPStatusError(head_status, url)
                head_headers = _headers(response)
        except BulkHTTPStatusError as error:
            if error.status_code not in {405, 501}:
                raise

        sample = b""
        range_headers: dict[str, str] = {}
        range_status = 0
        if sample_bytes > 0 or not head_headers:
            end = max(0, sample_bytes - 1)
            request = self._request(
                url,
                method="GET",
                headers={"Range": f"bytes=0-{end}"},
            )
            with self._open_with_retry(request) as response:
                range_status = _status(response)
                if range_status not in {200, 206}:
                    raise BulkHTTPStatusError(range_status, url)
                range_headers = _headers(response)
                if sample_bytes > 0:
                    sample = response.read(sample_bytes)

        merged = {**range_headers, **head_headers}
        total = _header_int(head_headers, "content-length")
        if total is None:
            total = _total_from_content_range(range_headers)
        source_sha256 = _sha256_from_headers(merged)
        signature = sample[:16].hex() if sample else None
        format_hint = "zip" if sample.startswith(b"PK\x03\x04") else None
        return ArtifactProbe(
            url=url,
            http_status=head_status or range_status,
            content_length=total,
            media_type=merged.get("content-type"),
            etag=merged.get("etag"),
            last_modified=merged.get("last-modified"),
            accept_ranges=(
                merged.get("accept-ranges", "").lower() == "bytes"
                or range_status == 206
            ),
            source_sha256=source_sha256,
            sample_size=len(sample),
            sample_sha256=hashlib.sha256(sample).hexdigest() if sample else None,
            signature_hex=signature,
            format_hint=format_hint,
            headers=MappingProxyType(merged),
        )

    def download(
        self,
        artifact: BulkArtifact,
        destination: Path | str,
        *,
        resume: bool = True,
        max_bytes: int | None = None,
    ) -> DownloadResult:
        """Download *artifact* to *destination* and verify its SHA-256.

        Partial bytes and a validator sidecar remain in place after transient
        failures so a later call can continue the transfer.
        """
        max_bytes = _positive_optional(max_bytes, "max_bytes")
        destination_path = Path(destination)
        if destination_path.exists() and destination_path.is_dir():
            destination_path = destination_path / artifact.filename
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        partial_path = destination_path.with_name(f"{destination_path.name}.part")
        state_path = destination_path.with_name(f"{destination_path.name}.part.json")

        probe = self.probe(artifact, sample_bytes=0)
        expected_size = artifact.expected_size or probe.content_length
        expected_sha256 = artifact.expected_sha256 or probe.source_sha256
        if max_bytes is not None and expected_size is not None and expected_size > max_bytes:
            raise BulkIntegrityError(
                "Artifact exceeds the requested maximum download size",
                details={
                    "url": artifact.url,
                    "expected_size": expected_size,
                    "max_bytes": max_bytes,
                },
            )

        if destination_path.is_file():
            existing_size = destination_path.stat().st_size
            existing_sha256 = file_sha256(destination_path)
            if (
                (expected_size is None or existing_size == expected_size)
                and (expected_sha256 is None or existing_sha256 == expected_sha256)
            ):
                return DownloadResult(
                    path=str(destination_path),
                    url=artifact.url,
                    size=existing_size,
                    sha256=existing_sha256,
                    expected_sha256=expected_sha256,
                    etag=probe.etag,
                    last_modified=probe.last_modified,
                    resumed_from=existing_size,
                    reused_existing=True,
                )

        state = {
            "url": artifact.url,
            "etag": probe.etag,
            "last_modified": probe.last_modified,
            "expected_size": expected_size,
            "expected_sha256": expected_sha256,
        }
        offset = 0
        if resume and partial_path.is_file() and state_path.is_file():
            try:
                previous_state = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                previous_state = None
            if isinstance(previous_state, Mapping) and _resume_state_matches(
                previous_state, state
            ):
                offset = partial_path.stat().st_size
        if offset == 0:
            partial_path.unlink(missing_ok=True)
            state_path.unlink(missing_ok=True)
        state_path.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        initial_offset = offset

        if expected_size is not None and offset == expected_size:
            digest = file_sha256(partial_path)
            return self._finalize_download(
                partial_path,
                state_path,
                destination_path,
                artifact,
                probe,
                digest,
                expected_size,
                expected_sha256,
                initial_offset,
            )

        last_error: BulkSourceError | None = None
        for attempt in range(1, self.max_attempts + 1):
            current_offset = partial_path.stat().st_size if partial_path.exists() else 0
            headers: dict[str, str] = {}
            if resume and current_offset:
                headers["Range"] = f"bytes={current_offset}-"
                validator = probe.etag or probe.last_modified
                if validator:
                    headers["If-Range"] = validator
            request = self._request(artifact.url, method="GET", headers=headers)
            try:
                with self._open_once(request) as response:
                    response_status = _status(response)
                    response_headers = _headers(response)
                    if response_status not in {200, 206}:
                        raise BulkHTTPStatusError(response_status, artifact.url)
                    append = response_status == 206 and current_offset > 0
                    if append:
                        content_range = response_headers.get("content-range", "")
                        match = _CONTENT_RANGE_START_RE.match(content_range)
                        if not match or int(match.group(1)) != current_offset:
                            raise BulkIntegrityError(
                                "Resume response starts at an unexpected byte",
                                details={
                                    "url": artifact.url,
                                    "requested_offset": current_offset,
                                    "content_range": content_range,
                                },
                            )
                    else:
                        current_offset = 0

                    mode = "ab" if append else "wb"
                    total_written = current_offset
                    with partial_path.open(mode) as output:
                        while True:
                            chunk = response.read(self.chunk_size)
                            if not chunk:
                                break
                            total_written += len(chunk)
                            if max_bytes is not None and total_written > max_bytes:
                                raise BulkIntegrityError(
                                    "Artifact exceeded the requested maximum download size",
                                    details={
                                        "url": artifact.url,
                                        "max_bytes": max_bytes,
                                    },
                                )
                            output.write(chunk)
                        output.flush()
                        os.fsync(output.fileno())
                last_error = None
                break
            except BulkSourceError as error:
                last_error = error
                if not error.retryable or attempt >= self.max_attempts:
                    raise
                self._sleeper(_retry_delay(attempt))
            except (URLError, TimeoutError, ConnectionError, OSError) as error:
                last_error = BulkTransportError(
                    f"Bulk transfer interrupted: {error}",
                    details={"url": artifact.url, "attempt": attempt},
                )
                if attempt >= self.max_attempts:
                    raise last_error from error
                self._sleeper(_retry_delay(attempt))

        if last_error is not None:
            raise last_error
        size = partial_path.stat().st_size
        digest = file_sha256(partial_path)
        return self._finalize_download(
            partial_path,
            state_path,
            destination_path,
            artifact,
            probe,
            digest,
            size,
            expected_sha256,
            initial_offset,
            expected_size=expected_size,
        )

    @staticmethod
    def _finalize_download(
        partial_path: Path,
        state_path: Path,
        destination_path: Path,
        artifact: BulkArtifact,
        probe: ArtifactProbe,
        digest: str,
        size: int,
        expected_sha256: str | None,
        resumed_from: int,
        *,
        expected_size: int | None = None,
    ) -> DownloadResult:
        expected_size = expected_size if expected_size is not None else size
        if size != expected_size:
            raise BulkIntegrityError(
                "Downloaded artifact size does not match source metadata",
                details={
                    "url": artifact.url,
                    "expected_size": expected_size,
                    "actual_size": size,
                },
            )
        if expected_sha256 is not None and digest != expected_sha256:
            raise BulkIntegrityError(
                "Downloaded artifact SHA-256 does not match source metadata",
                details={
                    "url": artifact.url,
                    "expected_sha256": expected_sha256,
                    "actual_sha256": digest,
                },
            )
        os.replace(partial_path, destination_path)
        state_path.unlink(missing_ok=True)
        return DownloadResult(
            path=str(destination_path),
            url=artifact.url,
            size=size,
            sha256=digest,
            expected_sha256=expected_sha256,
            etag=probe.etag,
            last_modified=probe.last_modified,
            resumed_from=resumed_from,
            reused_existing=False,
        )


def _resume_state_matches(previous: Mapping[str, Any], current: Mapping[str, Any]) -> bool:
    if previous.get("url") != current.get("url"):
        return False
    for key in ("etag", "last_modified", "expected_size", "expected_sha256"):
        old_value = previous.get(key)
        new_value = current.get(key)
        if old_value is not None and new_value is not None and old_value != new_value:
            return False
    return True


def file_sha256(path: Path | str, *, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file without loading it into memory."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ArchiveSafetyPolicy:
    """Explicit optional resource bounds for ZIP inspection and extraction."""

    max_members: int | None = None
    max_total_uncompressed_bytes: int | None = None
    max_member_uncompressed_bytes: int | None = None
    max_compression_ratio: float | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "max_members",
            "max_total_uncompressed_bytes",
            "max_member_uncompressed_bytes",
        ):
            object.__setattr__(
                self, field_name, _positive_optional(getattr(self, field_name), field_name)
            )
        if self.max_compression_ratio is not None:
            if self.max_compression_ratio <= 0:
                raise ValueError("max_compression_ratio must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_members": self.max_members,
            "max_total_uncompressed_bytes": self.max_total_uncompressed_bytes,
            "max_member_uncompressed_bytes": self.max_member_uncompressed_bytes,
            "max_compression_ratio": self.max_compression_ratio,
        }


@dataclass(frozen=True)
class ArchiveInspection:
    """Safe ZIP member inventory and deterministic fingerprints."""

    path: str
    archive_sha256: str
    archive_size: int
    member_count: int
    total_uncompressed_bytes: int
    total_compressed_bytes: int
    members: Sequence[Mapping[str, Any]]
    schema: Mapping[str, Any]
    schema_fingerprint: str
    manifest_fingerprint: str
    policy: ArchiveSafetyPolicy

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "archive_sha256": self.archive_sha256,
            "archive_size": self.archive_size,
            "member_count": self.member_count,
            "total_uncompressed_bytes": self.total_uncompressed_bytes,
            "total_compressed_bytes": self.total_compressed_bytes,
            "members": [_json_value(member) for member in self.members],
            "schema": _json_value(self.schema),
            "schema_fingerprint": self.schema_fingerprint,
            "manifest_fingerprint": self.manifest_fingerprint,
            "policy": self.policy.to_dict(),
        }


def _safe_member_path(info: zipfile.ZipInfo) -> tuple[str, bool]:
    raw = info.filename
    if "\x00" in raw or "\\" in raw:
        raise ArchiveSafetyError(
            "ZIP member uses an unsafe path representation",
            details={"member": raw},
        )
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ArchiveSafetyError(
            "ZIP member would escape the extraction directory",
            details={"member": raw},
        )
    parts = tuple(part for part in path.parts if part not in {"", "."})
    if not parts or parts[0].endswith(":"):
        raise ArchiveSafetyError(
            "ZIP member has an invalid extraction path",
            details={"member": raw},
        )
    normalized = "/".join(parts)
    mode = info.external_attr >> 16
    file_type = stat.S_IFMT(mode)
    is_directory = info.is_dir()
    if stat.S_ISLNK(mode):
        raise ArchiveSafetyError(
            "ZIP links are not extracted",
            details={"member": raw},
        )
    if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
        raise ArchiveSafetyError(
            "ZIP special-file members are not extracted",
            details={"member": raw, "mode": oct(mode)},
        )
    if info.flag_bits & 0x1:
        raise ArchiveSafetyError(
            "Encrypted ZIP members are not supported",
            details={"member": raw},
        )
    return normalized, is_directory


def inspect_zip(
    path: Path | str,
    *,
    policy: ArchiveSafetyPolicy | None = None,
) -> ArchiveInspection:
    """Inspect a ZIP, reject unsafe members, and fingerprint its structure."""
    archive_path = Path(path)
    active_policy = policy or ArchiveSafetyPolicy()
    members: list[dict[str, Any]] = []
    normalized_paths: set[str] = set()
    total_uncompressed = 0
    total_compressed = 0

    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            if (
                active_policy.max_members is not None
                and len(infos) > active_policy.max_members
            ):
                raise ArchiveSafetyError(
                    "ZIP member count exceeds the requested archive policy",
                    details={
                        "member_count": len(infos),
                        "max_members": active_policy.max_members,
                    },
                )
            for info in infos:
                normalized, is_directory = _safe_member_path(info)
                if normalized in normalized_paths:
                    raise ArchiveSafetyError(
                        "ZIP contains duplicate normalized member paths",
                        details={"member": normalized},
                    )
                normalized_paths.add(normalized)
                total_uncompressed += info.file_size
                total_compressed += info.compress_size
                if (
                    active_policy.max_member_uncompressed_bytes is not None
                    and info.file_size
                    > active_policy.max_member_uncompressed_bytes
                ):
                    raise ArchiveSafetyError(
                        "ZIP member exceeds the requested archive policy",
                        details={
                            "member": normalized,
                            "size": info.file_size,
                            "max_member_uncompressed_bytes": (
                                active_policy.max_member_uncompressed_bytes
                            ),
                        },
                    )
                ratio = (
                    float("inf")
                    if info.compress_size == 0 and info.file_size
                    else info.file_size / max(1, info.compress_size)
                )
                if (
                    active_policy.max_compression_ratio is not None
                    and ratio > active_policy.max_compression_ratio
                ):
                    raise ArchiveSafetyError(
                        "ZIP member compression ratio exceeds the requested archive policy",
                        details={
                            "member": normalized,
                            "compression_ratio": ratio,
                            "max_compression_ratio": active_policy.max_compression_ratio,
                        },
                    )
                members.append(
                    {
                        "path": normalized,
                        "kind": "directory" if is_directory else "file",
                        "size": info.file_size,
                        "compressed_size": info.compress_size,
                        "crc32": f"{info.CRC:08x}",
                    }
                )
    except zipfile.BadZipFile as error:
        raise ArchiveSafetyError(
            "Artifact is not a readable ZIP archive",
            details={"path": str(archive_path)},
        ) from error

    if (
        active_policy.max_total_uncompressed_bytes is not None
        and total_uncompressed > active_policy.max_total_uncompressed_bytes
    ):
        raise ArchiveSafetyError(
            "ZIP total size exceeds the requested archive policy",
            details={
                "total_uncompressed_bytes": total_uncompressed,
                "max_total_uncompressed_bytes": (
                    active_policy.max_total_uncompressed_bytes
                ),
            },
        )

    members.sort(key=lambda member: str(member["path"]))
    shapefile_stems = sorted(
        {
            str(PurePosixPath(member["path"]).with_suffix(""))
            for member in members
            if member["kind"] == "file"
            and PurePosixPath(member["path"]).suffix.lower() == ".shp"
        }
    )
    geodatabases = sorted(
        {
            "/".join(PurePosixPath(member["path"]).parts[: index + 1])
            for member in members
            for index, part in enumerate(PurePosixPath(member["path"]).parts)
            if part.lower().endswith(".gdb")
        }
    )
    schema = {
        "archive_format": "zip",
        "members": [
            {
                "path": member["path"],
                "kind": member["kind"],
                "extension": (
                    PurePosixPath(str(member["path"])).suffix.lower()
                    if member["kind"] == "file"
                    else None
                ),
            }
            for member in members
        ],
        "shapefile_datasets": shapefile_stems,
        "file_geodatabases": geodatabases,
    }
    manifest_payload = {
        "members": members,
        "total_uncompressed_bytes": total_uncompressed,
        "total_compressed_bytes": total_compressed,
    }
    return ArchiveInspection(
        path=str(archive_path),
        archive_sha256=file_sha256(archive_path),
        archive_size=archive_path.stat().st_size,
        member_count=len(members),
        total_uncompressed_bytes=total_uncompressed,
        total_compressed_bytes=total_compressed,
        members=tuple(members),
        schema=_freeze(schema),
        schema_fingerprint=sha256_fingerprint(schema),
        manifest_fingerprint=sha256_fingerprint(manifest_payload),
        policy=active_policy,
    )


def safe_extract_zip(
    path: Path | str,
    destination: Path | str,
    *,
    policy: ArchiveSafetyPolicy | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Extract a ZIP after validation, without following archive-provided links."""
    inspection = inspect_zip(path, policy=policy)
    destination_path = Path(destination)
    destination_path.mkdir(parents=True, exist_ok=True)
    root = destination_path.resolve()
    extracted: list[str] = []

    with zipfile.ZipFile(path) as archive:
        info_by_path = {
            _safe_member_path(info)[0]: info for info in archive.infolist()
        }
        for member in inspection.members:
            relative_path = str(member["path"])
            target = destination_path.joinpath(*PurePosixPath(relative_path).parts)
            target_parent = target.parent
            target_parent.mkdir(parents=True, exist_ok=True)
            if not target_parent.resolve().is_relative_to(root):
                raise ArchiveSafetyError(
                    "Extraction target resolves outside the destination",
                    details={"member": relative_path},
                )
            if member["kind"] == "directory":
                target.mkdir(parents=True, exist_ok=True)
                extracted.append(relative_path)
                continue
            if target.exists() and not overwrite:
                raise ArchiveSafetyError(
                    "Extraction target already exists",
                    details={"member": relative_path, "target": str(target)},
                )
            mode = "wb" if overwrite else "xb"
            with archive.open(info_by_path[relative_path]) as source, target.open(mode) as out:
                while chunk := source.read(1024 * 1024):
                    out.write(chunk)
            extracted.append(relative_path)

    return {
        "archive": inspection.to_dict(),
        "destination": str(destination_path),
        "extracted_members": extracted,
        "overwrite": overwrite,
    }
