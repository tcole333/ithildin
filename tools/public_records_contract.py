"""Shared query and result contract for public-record source adapters.

The contract intentionally separates an authoritative empty result from failures.
Callers should create successful results with :meth:`PublicRecordsResult.success`
and failures with :meth:`PublicRecordsResult.failure`; transport and source
failures must never be represented as ``no_results``.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

QUERY_SCHEMA_VERSION = "public-records-query/1.0"
RESULT_SCHEMA_VERSION = "public-records-result/1.0"


class ResultStatus(StrEnum):
    """Outcome statuses shared by every public-record source adapter."""

    OK = "ok"
    NO_RESULTS = "no_results"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    RESTRICTED = "restricted"
    HUMAN_REQUIRED = "human_required"
    RATE_LIMITED = "rate_limited"
    TERMS_BLOCKED = "terms_blocked"
    SOURCE_CHANGED = "source_changed"


_FAILURE_STATUSES = frozenset(
    {
        ResultStatus.UNAVAILABLE,
        ResultStatus.RESTRICTED,
        ResultStatus.HUMAN_REQUIRED,
        ResultStatus.RATE_LIMITED,
        ResultStatus.TERMS_BLOCKED,
        ResultStatus.SOURCE_CHANGED,
    }
)


def _normalize_json(value: Any, *, path: str = "$") -> Any:
    """Return a detached, JSON-safe representation of *value*.

    Restricting keys to strings and rejecting non-finite floats avoids different
    Python values serializing to the same JSON or producing non-standard JSON.
    """

    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite float")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} contains non-string mapping key {key!r}")
            normalized[key] = _normalize_json(item, path=f"{path}.{key}")
        return normalized
    if isinstance(value, (list, tuple)):
        return [
            _normalize_json(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise TypeError(f"{path} contains unsupported JSON value {type(value).__name__}")


def _freeze_json(value: Any, *, path: str = "$") -> Any:
    """Detach and recursively freeze a JSON value."""

    normalized = _normalize_json(value, path=path)
    if isinstance(normalized, dict):
        return MappingProxyType(
            {
                key: _freeze_json(item, path=f"{path}.{key}")
                for key, item in normalized.items()
            }
        )
    if isinstance(normalized, list):
        return tuple(
            _freeze_json(item, path=f"{path}[{index}]")
            for index, item in enumerate(normalized)
        )
    return normalized


def canonical_json(value: Any) -> str:
    """Serialize *value* as deterministic, standards-compliant JSON."""

    return json.dumps(
        _normalize_json(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_fingerprint(value: Any) -> str:
    """Return the lowercase SHA-256 digest of a value's canonical JSON."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    """Return a second-precision RFC 3339 timestamp in UTC."""

    return (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def _normalize_timestamp(value: str | datetime) -> str:
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            raise ValueError("retrieved_at must not be empty")
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("retrieved_at must be an ISO 8601 timestamp") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise TypeError("retrieved_at must be a string or datetime")

    if parsed.tzinfo is None:
        raise ValueError("retrieved_at must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class SourceMetadata:
    """Identity and role of the system that will answer a query."""

    source_id: str
    name: str
    source_role: str
    base_url: str | None = None
    dataset_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_id", _require_text(self.source_id, "source_id")
        )
        object.__setattr__(self, "name", _require_text(self.name, "name"))
        object.__setattr__(
            self, "source_role", _require_text(self.source_role, "source_role")
        )
        if self.base_url is not None:
            object.__setattr__(
                self, "base_url", _require_text(self.base_url, "base_url")
            )
        if self.dataset_id is not None:
            object.__setattr__(
                self, "dataset_id", _require_text(self.dataset_id, "dataset_id")
            )
        object.__setattr__(
            self, "metadata", _freeze_json(self.metadata, path="source.metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "source_role": self.source_role,
            "base_url": self.base_url,
            "dataset_id": self.dataset_id,
            "metadata": _normalize_json(self.metadata),
        }


@dataclass(frozen=True)
class JurisdictionMetadata:
    """Geographic and governmental scope of a query."""

    jurisdiction_id: str
    name: str
    country_code: str = "US"
    state_code: str | None = None
    county_fips: str | None = None
    locality: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "jurisdiction_id",
            _require_text(self.jurisdiction_id, "jurisdiction_id"),
        )
        object.__setattr__(self, "name", _require_text(self.name, "name"))
        object.__setattr__(
            self,
            "country_code",
            _require_text(self.country_code, "country_code").upper(),
        )
        for field_name in ("state_code", "county_fips", "locality"):
            value = getattr(self, field_name)
            if value is not None:
                normalized = _require_text(value, field_name)
                if field_name == "state_code":
                    normalized = normalized.upper()
                object.__setattr__(self, field_name, normalized)
        object.__setattr__(
            self,
            "metadata",
            _freeze_json(self.metadata, path="jurisdiction.metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "jurisdiction_id": self.jurisdiction_id,
            "name": self.name,
            "country_code": self.country_code,
            "state_code": self.state_code,
            "county_fips": self.county_fips,
            "locality": self.locality,
            "metadata": _normalize_json(self.metadata),
        }


@dataclass(frozen=True)
class QueryMetadata:
    """Operation, parameters, and bounds requested from a source."""

    operation: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    requested_limit: int | None = None
    cursor: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "operation", _require_text(self.operation, "operation")
        )
        object.__setattr__(
            self,
            "parameters",
            _freeze_json(self.parameters, path="query.parameters"),
        )
        if self.requested_limit is not None:
            if (
                isinstance(self.requested_limit, bool)
                or not isinstance(self.requested_limit, int)
                or self.requested_limit <= 0
            ):
                raise ValueError("requested_limit must be a positive integer")
        if self.cursor is not None:
            object.__setattr__(self, "cursor", _require_text(self.cursor, "cursor"))
        object.__setattr__(
            self, "metadata", _freeze_json(self.metadata, path="query.metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "parameters": _normalize_json(self.parameters),
            "requested_limit": self.requested_limit,
            "cursor": self.cursor,
            "metadata": _normalize_json(self.metadata),
        }


@dataclass(frozen=True)
class PublicRecordsQuery:
    """Canonical, source-scoped public-record query."""

    source: SourceMetadata
    jurisdiction: JurisdictionMetadata
    query: QueryMetadata
    schema_version: str = QUERY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceMetadata):
            raise TypeError("source must be SourceMetadata")
        if not isinstance(self.jurisdiction, JurisdictionMetadata):
            raise TypeError("jurisdiction must be JurisdictionMetadata")
        if not isinstance(self.query, QueryMetadata):
            raise TypeError("query must be QueryMetadata")
        object.__setattr__(
            self,
            "schema_version",
            _require_text(self.schema_version, "schema_version"),
        )

    def fingerprint_payload(self) -> dict[str, Any]:
        """Return the canonical payload hashed to identify this query."""

        return {
            "schema_version": self.schema_version,
            "source": self.source.to_dict(),
            "jurisdiction": self.jurisdiction.to_dict(),
            "query": self.query.to_dict(),
        }

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(self.fingerprint_payload())

    def to_dict(self) -> dict[str, Any]:
        payload = self.fingerprint_payload()
        payload["fingerprint"] = self.fingerprint
        return payload

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True)
class PublicRecordsError:
    """Structured failure or partial-result diagnostic."""

    code: str
    message: str
    category: str
    retryable: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _require_text(self.code, "error.code"))
        object.__setattr__(
            self, "message", _require_text(self.message, "error.message")
        )
        object.__setattr__(
            self, "category", _require_text(self.category, "error.category")
        )
        if not isinstance(self.retryable, bool):
            raise TypeError("error.retryable must be a boolean")
        object.__setattr__(
            self, "details", _freeze_json(self.details, path="error.details")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "category": self.category,
            "retryable": self.retryable,
            "details": _normalize_json(self.details),
        }


@dataclass(frozen=True)
class PublicRecordsResult:
    """Deterministic result envelope for public-record source adapters."""

    query: PublicRecordsQuery
    status: ResultStatus
    retrieved_at: str | datetime = field(default_factory=utc_now_iso)
    records: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    next_cursor: str | None = None
    raw_artifact_refs: Sequence[str] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)
    errors: Sequence[PublicRecordsError] = field(default_factory=tuple)
    schema_version: str = RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.query, PublicRecordsQuery):
            raise TypeError("query must be PublicRecordsQuery")
        try:
            status = ResultStatus(self.status)
        except ValueError as exc:
            raise ValueError(
                f"unknown public-record result status: {self.status}"
            ) from exc
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self, "retrieved_at", _normalize_timestamp(self.retrieved_at)
        )
        object.__setattr__(
            self,
            "schema_version",
            _require_text(self.schema_version, "schema_version"),
        )

        normalized_records: list[dict[str, Any]] = []
        for index, record in enumerate(self.records):
            if not isinstance(record, Mapping):
                raise TypeError(f"records[{index}] must be a mapping")
            normalized_records.append(_freeze_json(record, path=f"records[{index}]"))
        object.__setattr__(self, "records", tuple(normalized_records))

        if self.next_cursor is not None:
            object.__setattr__(
                self, "next_cursor", _require_text(self.next_cursor, "next_cursor")
            )
        object.__setattr__(
            self,
            "raw_artifact_refs",
            tuple(
                _require_text(value, f"raw_artifact_refs[{index}]")
                for index, value in enumerate(self.raw_artifact_refs)
            ),
        )
        object.__setattr__(
            self,
            "warnings",
            tuple(
                _require_text(value, f"warnings[{index}]")
                for index, value in enumerate(self.warnings)
            ),
        )
        for index, error in enumerate(self.errors):
            if not isinstance(error, PublicRecordsError):
                raise TypeError(
                    f"errors[{index}] must be a PublicRecordsError instance"
                )
        object.__setattr__(self, "errors", tuple(self.errors))

        if status == ResultStatus.OK and not self.records:
            raise ValueError("ok results must contain at least one record")
        if status == ResultStatus.NO_RESULTS:
            if self.records:
                raise ValueError("no_results cannot contain records")
            if self.errors:
                raise ValueError(
                    "no_results cannot contain errors; use an explicit failure status"
                )
        if status in _FAILURE_STATUSES and not self.errors:
            raise ValueError(f"{status.value} results must contain an explicit error")

    @classmethod
    def success(
        cls,
        query: PublicRecordsQuery,
        records: Sequence[Mapping[str, Any]],
        *,
        retrieved_at: str | datetime | None = None,
        next_cursor: str | None = None,
        raw_artifact_refs: Sequence[str] = (),
        warnings: Sequence[str] = (),
    ) -> PublicRecordsResult:
        """Build an ``ok`` or authoritative ``no_results`` envelope."""

        status = ResultStatus.OK if records else ResultStatus.NO_RESULTS
        kwargs: dict[str, Any] = {}
        if retrieved_at is not None:
            kwargs["retrieved_at"] = retrieved_at
        return cls(
            query=query,
            status=status,
            records=records,
            next_cursor=next_cursor,
            raw_artifact_refs=raw_artifact_refs,
            warnings=warnings,
            **kwargs,
        )

    @classmethod
    def failure(
        cls,
        query: PublicRecordsQuery,
        status: ResultStatus,
        errors: Sequence[PublicRecordsError],
        *,
        retrieved_at: str | datetime | None = None,
        records: Sequence[Mapping[str, Any]] = (),
        next_cursor: str | None = None,
        raw_artifact_refs: Sequence[str] = (),
        warnings: Sequence[str] = (),
    ) -> PublicRecordsResult:
        """Build an explicit failure or partial-result envelope."""

        normalized_status = ResultStatus(status)
        if normalized_status in {ResultStatus.OK, ResultStatus.NO_RESULTS}:
            raise ValueError("failure() requires partial or an explicit failure status")
        kwargs: dict[str, Any] = {}
        if retrieved_at is not None:
            kwargs["retrieved_at"] = retrieved_at
        return cls(
            query=query,
            status=normalized_status,
            records=records,
            next_cursor=next_cursor,
            raw_artifact_refs=raw_artifact_refs,
            warnings=warnings,
            errors=errors,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "retrieved_at": self.retrieved_at,
            "status": self.status.value,
            "query": self.query.to_dict(),
            "records": [_normalize_json(record) for record in self.records],
            "next_cursor": self.next_cursor,
            "raw_artifact_refs": list(self.raw_artifact_refs),
            "warnings": list(self.warnings),
            "errors": [error.to_dict() for error in self.errors],
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())
