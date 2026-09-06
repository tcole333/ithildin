#!/usr/bin/env python3
"""Public-records source catalog and acquisition capability registry.

The catalog is a control-plane sidecar for property and state/local court
sources. Source manifests describe candidate capabilities. The current
immutable access review records the acquisition mode supported for operational
use.

The machine-acquisition decision is derived from the latest access review:

* the latest review classifies the source as A, B, or D;
* its automation disposition is ``allowed`` or ``allowed_with_limits``;
* class D sources also have a verified license/procurement contract in the
  access review.

Usage:
    uv run python tools/public_records_catalog.py init
    uv run python tools/public_records_catalog.py register source.yaml
    uv run python tools/public_records_catalog.py list --domain property
    uv run python tools/public_records_catalog.py show us-fl-dor-property-roll
    uv run python tools/public_records_catalog.py evaluate-access SOURCE_ID ...
    uv run python tools/public_records_catalog.py record-probe SOURCE_ID ...
    uv run python tools/public_records_catalog.py health SOURCE_ID
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "datasets" / "public_records_catalog.db"
SCHEMA_VERSION = 3

ACCESS_CLASSES = frozenset({"A", "B", "C", "D", "E", "X"})
AUTOMATION_DISPOSITIONS = frozenset(
    {
        "allowed",
        "allowed_with_limits",
        "unclear",
        "prohibited",
        "not_applicable",
    }
)
DOMAINS = frozenset({"property", "court", "mixed"})
SOURCE_STATUSES = frozenset({"candidate", "active", "inactive", "retired"})
TERMS_SNAPSHOT_TYPES = frozenset(
    {
        "terms",
        "robots",
        "court_rule",
        "license",
        "privacy",
        "access_notice",
        "other",
    }
)
PROBE_STATUSES = frozenset(
    {
        "ok",
        "no_results",
        "partial",
        "unavailable",
        "restricted",
        "human_required",
        "rate_limited",
        "terms_blocked",
        "source_changed",
        "error",
    }
)

_SOURCE_ID_RE = re.compile(r"^[a-z]{2}(?:-[a-z0-9]+){2,}$")
_JURISDICTION_ID_RE = re.compile(r"^[a-z]{2}(?:-[a-z0-9]+)+$")
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jurisdictions (
    jurisdiction_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    country_code TEXT NOT NULL,
    subdivision_code TEXT,
    geoid TEXT,
    parent_jurisdiction_id TEXT,
    official_url TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_jurisdiction_geoid
    ON jurisdictions(country_code, geoid)
    WHERE geoid IS NOT NULL;

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    domain TEXT NOT NULL CHECK(domain IN ('property', 'court', 'mixed')),
    authority TEXT NOT NULL,
    operator TEXT NOT NULL,
    official_url TEXT NOT NULL,
    platform_family TEXT NOT NULL,
    source_status TEXT NOT NULL DEFAULT 'candidate'
        CHECK(source_status IN ('candidate', 'active', 'inactive', 'retired')),
    proposed_access_class TEXT NOT NULL
        CHECK(proposed_access_class IN ('A', 'B', 'C', 'D', 'E', 'X')),
    proposed_automation_disposition TEXT NOT NULL
        CHECK(proposed_automation_disposition IN (
            'allowed', 'allowed_with_limits', 'unclear', 'prohibited',
            'not_applicable'
        )),
    authentication_json TEXT NOT NULL,
    fees_json TEXT NOT NULL,
    license_or_terms_url TEXT,
    redistribution TEXT,
    protected_record_policy TEXT,
    coverage_start TEXT,
    coverage_end TEXT,
    update_cadence TEXT,
    stable_keys_json TEXT NOT NULL,
    adapter_family TEXT,
    adapter_version TEXT,
    owner_team TEXT,
    declared_health_status TEXT,
    last_verified_at TEXT,
    current_manifest_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sources_domain ON sources(domain);
CREATE INDEX IF NOT EXISTS idx_sources_platform ON sources(platform_family);

CREATE TABLE IF NOT EXISTS source_manifests (
    manifest_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    manifest_sha256 TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    submitted_by TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    effective_at TEXT,
    recorded_at TEXT NOT NULL,
    UNIQUE(source_id, manifest_sha256)
);
CREATE INDEX IF NOT EXISTS idx_manifests_source
    ON source_manifests(source_id, manifest_id);

CREATE TABLE IF NOT EXISTS source_jurisdictions (
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    jurisdiction_id TEXT NOT NULL
        REFERENCES jurisdictions(jurisdiction_id) ON DELETE CASCADE,
    coverage_json TEXT NOT NULL DEFAULT '{}',
    exclusions_json TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY(source_id, jurisdiction_id)
);
CREATE INDEX IF NOT EXISTS idx_source_jurisdiction_jurisdiction
    ON source_jurisdictions(jurisdiction_id, source_id);

CREATE TABLE IF NOT EXISTS source_roles (
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    PRIMARY KEY(source_id, role)
);

CREATE TABLE IF NOT EXISTS capabilities (
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    capability TEXT NOT NULL,
    supported INTEGER NOT NULL DEFAULT 1 CHECK(supported IN (0, 1)),
    details_json TEXT NOT NULL DEFAULT '{}',
    recorded_at TEXT NOT NULL,
    PRIMARY KEY(source_id, capability)
);

CREATE TABLE IF NOT EXISTS terms_snapshots (
    terms_snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    snapshot_type TEXT NOT NULL CHECK(snapshot_type IN (
        'terms', 'robots', 'court_rule', 'license', 'privacy',
        'access_notice', 'other'
    )),
    source_url TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    content_text TEXT,
    artifact_ref TEXT,
    recorded_by TEXT NOT NULL,
    notes TEXT,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_terms_source
    ON terms_snapshots(source_id, terms_snapshot_id);

CREATE TABLE IF NOT EXISTS access_reviews (
    access_review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    access_class TEXT NOT NULL CHECK(access_class IN ('A', 'B', 'C', 'D', 'E', 'X')),
    automation_disposition TEXT NOT NULL CHECK(automation_disposition IN (
        'allowed', 'allowed_with_limits', 'unclear', 'prohibited',
        'not_applicable'
    )),
    limits_json TEXT NOT NULL DEFAULT '{}',
    review_basis TEXT NOT NULL,
    notes TEXT,
    terms_snapshot_id INTEGER REFERENCES terms_snapshots(terms_snapshot_id),
    contract_verified INTEGER NOT NULL DEFAULT 0
        CHECK(contract_verified IN (0, 1)),
    contract_reference TEXT,
    reviewed_by TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    valid_until TEXT,
    supersedes_review_id INTEGER REFERENCES access_reviews(access_review_id),
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_access_reviews_source
    ON access_reviews(source_id, access_review_id);

CREATE TABLE IF NOT EXISTS probes (
    probe_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    probe_kind TEXT NOT NULL DEFAULT 'sentinel',
    capability TEXT,
    status TEXT NOT NULL CHECK(status IN (
        'ok', 'no_results', 'partial', 'unavailable', 'restricted',
        'human_required', 'rate_limited', 'terms_blocked', 'source_changed',
        'error'
    )),
    endpoint TEXT,
    http_status INTEGER,
    latency_ms REAL,
    schema_sha256 TEXT,
    artifact_sha256 TEXT,
    result_count INTEGER,
    details_json TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    probed_by TEXT NOT NULL,
    probed_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_probes_source
    ON probes(source_id, probe_id);
CREATE INDEX IF NOT EXISTS idx_probes_status
    ON probes(status, probed_at);

CREATE TABLE IF NOT EXISTS source_census_targets (
    census_target_id INTEGER PRIMARY KEY AUTOINCREMENT,
    jurisdiction_id TEXT NOT NULL
        REFERENCES jurisdictions(jurisdiction_id) ON DELETE CASCADE,
    domain TEXT NOT NULL CHECK(domain IN ('property', 'court')),
    role TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN (
            'pending', 'in_progress', 'source_identified',
            'manifest_submitted', 'manual_only', 'not_found', 'blocked'
        )),
    benefit_score REAL NOT NULL DEFAULT 0,
    feasibility_score REAL NOT NULL DEFAULT 0,
    risk_score REAL NOT NULL DEFAULT 0,
    priority_basis_json TEXT NOT NULL DEFAULT '{}',
    source_id TEXT REFERENCES sources(source_id) ON DELETE SET NULL,
    official_url TEXT,
    evidence_json TEXT NOT NULL DEFAULT '[]',
    notes TEXT,
    coverage_status TEXT NOT NULL DEFAULT 'unassessed'
        CHECK(coverage_status IN (
            'unassessed', 'partial', 'comprehensive', 'not_applicable'
        )),
    coverage_notes TEXT,
    coverage_gaps_json TEXT NOT NULL DEFAULT '[]',
    claimed_by TEXT,
    claimed_at TEXT,
    resolved_by TEXT,
    resolved_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(jurisdiction_id, domain, role)
);
CREATE INDEX IF NOT EXISTS idx_census_queue
    ON source_census_targets(
        status, benefit_score DESC, feasibility_score DESC,
        risk_score ASC, census_target_id
    );
CREATE INDEX IF NOT EXISTS idx_census_jurisdiction
    ON source_census_targets(jurisdiction_id, domain, role);

CREATE TABLE IF NOT EXISTS source_census_target_sources (
    census_target_id INTEGER NOT NULL
        REFERENCES source_census_targets(census_target_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    official_url TEXT,
    coverage_json TEXT NOT NULL DEFAULT '{}',
    coverage_gaps_json TEXT NOT NULL DEFAULT '[]',
    notes TEXT,
    evidence_json TEXT NOT NULL DEFAULT '[]',
    added_by TEXT NOT NULL,
    added_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(census_target_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_census_target_sources_source
    ON source_census_target_sources(source_id, census_target_id);

CREATE TABLE IF NOT EXISTS source_census_events (
    census_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    census_target_id INTEGER NOT NULL
        REFERENCES source_census_targets(census_target_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_census_events_target
    ON source_census_events(census_target_id, census_event_id);
"""


class CatalogError(RuntimeError):
    """Base error for catalog validation and state failures."""


class ManifestValidationError(CatalogError):
    """Raised when a source manifest is incomplete or noncanonical."""


class AcquisitionUnavailableError(CatalogError):
    """Raised when the catalog lacks a currently usable machine route."""

    def __init__(self, decision: Mapping[str, Any]):
        self.decision = dict(decision)
        reason = self.decision.get("reason", "machine acquisition unavailable")
        super().__init__(str(reason))


def acquisition_result_status(decision: Mapping[str, Any]) -> str:
    """Map a catalog decision to the most precise shared result status.

    Missing or stale review evidence describes readiness, not source terms.
    Interactive or offline acquisition stays visible as ``human_required``;
    ``terms_blocked`` denotes an explicit prohibition with no such route.
    """
    if decision.get("allowed"):
        return "ok"
    if decision.get("access_class") in {"C", "E"}:
        return "human_required"
    if decision.get("automation_disposition") == "prohibited":
        return "terms_blocked"
    if str(decision.get("reason_code") or "") == "licensed_contract_required":
        return "restricted"
    return "unavailable"


def utc_now() -> str:
    """Return a second-precision UTC timestamp."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def normalize_timestamp(value: str, field_name: str) -> str:
    """Validate an aware ISO-8601 timestamp and normalize it to UTC."""
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{field_name} must be a non-empty ISO-8601 timestamp")
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise CatalogError(f"{field_name} is not a valid ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise CatalogError(f"{field_name} must include a timezone")
    return (
        parsed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def canonical_source_id(value: str) -> str:
    """Return the canonical lowercase kebab-case form for a source ID."""
    if not isinstance(value, str) or not value.strip():
        raise ManifestValidationError("source_id must be a non-empty string")
    canonical = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not _SOURCE_ID_RE.fullmatch(canonical):
        raise ManifestValidationError(
            "source_id must contain a two-letter country prefix and at least "
            "two additional lowercase kebab-case segments"
        )
    return canonical


def _validate_source_id(value: str) -> str:
    canonical = canonical_source_id(value)
    if value != canonical:
        raise ManifestValidationError(
            f"source_id must already be canonical; use '{canonical}'"
        )
    return canonical


def _validate_jurisdiction_id(value: str) -> str:
    if not isinstance(value, str) or not _JURISDICTION_ID_RE.fullmatch(value):
        raise ManifestValidationError(
            "jurisdiction_id must be lowercase kebab case with a country prefix"
        )
    return value


def _validate_url(value: str | None, field_name: str, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise ManifestValidationError(f"{field_name} is required")
        return None
    if not isinstance(value, str) or not value.strip():
        raise ManifestValidationError(f"{field_name} must be a non-empty URL")
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ManifestValidationError(f"{field_name} must be an HTTP(S) URL")
    return value.strip()


def _validate_probe_endpoint(value: str) -> str:
    """Validate an observed network endpoint, including WebSocket transports."""
    if not isinstance(value, str) or not value.strip():
        raise ManifestValidationError("endpoint must be a non-empty URL")
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https", "ws", "wss"} or not parsed.netloc:
        raise ManifestValidationError(
            "endpoint must be an HTTP(S) or WebSocket URL"
        )
    return value.strip()


def _json_dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _json_load(raw: str | None, default: Any) -> Any:
    if raw is None:
        return default
    return json.loads(raw)


def _require_string(
    manifest: Mapping[str, Any],
    key: str,
    *,
    default: str | None = None,
) -> str:
    value = manifest.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ManifestValidationError(f"{key} must be a non-empty string")
    return value.strip()


def _canonical_names(values: Any, field_name: str) -> list[str]:
    if (
        not isinstance(values, Sequence)
        or isinstance(values, (str, bytes))
        or not values
    ):
        raise ManifestValidationError(f"{field_name} must be a non-empty list")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not _NAME_RE.fullmatch(value):
            raise ManifestValidationError(
                f"{field_name} entries must use lowercase snake_case"
            )
        if value in normalized:
            raise ManifestValidationError(f"{field_name} contains duplicate '{value}'")
        normalized.append(value)
    return normalized


def _normalize_capabilities(values: Any) -> list[dict[str, Any]]:
    if values is None:
        return []
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ManifestValidationError("capabilities must be a list")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in values:
        if isinstance(item, str):
            name = item
            supported = True
            details: dict[str, Any] = {}
        elif isinstance(item, Mapping):
            name = item.get("name") or item.get("capability")
            supported = item.get("supported", True)
            details = item.get("details", {})
        else:
            raise ManifestValidationError(
                "capabilities entries must be names or objects"
            )
        if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
            raise ManifestValidationError(
                "capability names must use lowercase snake_case"
            )
        if not isinstance(supported, bool):
            raise ManifestValidationError("capability supported must be boolean")
        if not isinstance(details, Mapping):
            raise ManifestValidationError("capability details must be an object")
        if name in seen:
            raise ManifestValidationError(f"duplicate capability '{name}'")
        seen.add(name)
        normalized.append(
            {"name": name, "supported": supported, "details": dict(details)}
        )
    return normalized


def _normalize_jurisdictions(
    manifest: Mapping[str, Any],
    source_id: str,
) -> list[dict[str, Any]]:
    raw_jurisdictions = manifest.get("jurisdictions")
    raw_geoids = manifest.get("jurisdiction_geoids")
    if raw_jurisdictions is None and raw_geoids is None:
        raise ManifestValidationError(
            "manifest must include jurisdictions or jurisdiction_geoids"
        )

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_geoids: set[str] = set()
    country_prefix = source_id.split("-", 1)[0]

    if raw_jurisdictions is not None:
        if not isinstance(raw_jurisdictions, Sequence) or isinstance(
            raw_jurisdictions, (str, bytes)
        ):
            raise ManifestValidationError("jurisdictions must be a list")
        for item in raw_jurisdictions:
            if isinstance(item, str):
                jurisdiction_id = _validate_jurisdiction_id(item)
                entry = {
                    "jurisdiction_id": jurisdiction_id,
                    "name": jurisdiction_id.upper(),
                    "kind": "unspecified",
                    "country_code": jurisdiction_id[:2].upper(),
                    "subdivision_code": None,
                    "geoid": None,
                    "parent_jurisdiction_id": None,
                    "official_url": None,
                    "coverage": {},
                    "exclusions": [],
                    "metadata": {},
                }
            elif isinstance(item, Mapping):
                jurisdiction_id = _validate_jurisdiction_id(
                    _require_string(item, "jurisdiction_id")
                )
                country_code = _require_string(item, "country_code").upper()
                if not re.fullmatch(r"[A-Z]{2}", country_code):
                    raise ManifestValidationError(
                        "jurisdiction country_code must be two letters"
                    )
                parent = item.get("parent_jurisdiction_id")
                if parent is not None:
                    parent = _validate_jurisdiction_id(parent)
                official_url = _validate_url(
                    item.get("official_url"),
                    "jurisdiction official_url",
                    required=False,
                )
                coverage = item.get("coverage", {})
                exclusions = item.get("exclusions", [])
                metadata = item.get("metadata", {})
                if not isinstance(coverage, Mapping):
                    raise ManifestValidationError(
                        "jurisdiction coverage must be an object"
                    )
                if not isinstance(exclusions, Sequence) or isinstance(
                    exclusions, (str, bytes)
                ):
                    raise ManifestValidationError(
                        "jurisdiction exclusions must be a list"
                    )
                if not isinstance(metadata, Mapping):
                    raise ManifestValidationError(
                        "jurisdiction metadata must be an object"
                    )
                entry = {
                    "jurisdiction_id": jurisdiction_id,
                    "name": _require_string(item, "name"),
                    "kind": _require_string(item, "kind"),
                    "country_code": country_code,
                    "subdivision_code": item.get("subdivision_code"),
                    "geoid": str(item["geoid"]) if item.get("geoid") else None,
                    "parent_jurisdiction_id": parent,
                    "official_url": official_url,
                    "coverage": dict(coverage),
                    "exclusions": list(exclusions),
                    "metadata": dict(metadata),
                }
            else:
                raise ManifestValidationError(
                    "jurisdictions entries must be IDs or objects"
                )
            if entry["jurisdiction_id"] in seen:
                raise ManifestValidationError(
                    f"duplicate jurisdiction '{entry['jurisdiction_id']}'"
                )
            seen.add(entry["jurisdiction_id"])
            if entry["geoid"] is not None:
                seen_geoids.add(entry["geoid"])
            normalized.append(entry)

    if raw_geoids is not None:
        if not isinstance(raw_geoids, Sequence) or isinstance(
            raw_geoids, (str, bytes)
        ):
            raise ManifestValidationError("jurisdiction_geoids must be a list")
        for raw_geoid in raw_geoids:
            geoid = str(raw_geoid).strip()
            if not geoid or not re.fullmatch(r"[A-Za-z0-9_.-]+", geoid):
                raise ManifestValidationError(
                    "jurisdiction_geoids entries must be stable identifiers"
                )
            if geoid in seen_geoids:
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", geoid.lower()).strip("-")
            jurisdiction_id = f"{country_prefix}-geoid-{slug}"
            if jurisdiction_id in seen:
                continue
            seen.add(jurisdiction_id)
            seen_geoids.add(geoid)
            normalized.append(
                {
                    "jurisdiction_id": jurisdiction_id,
                    "name": f"GEOID {geoid}",
                    "kind": "geoid",
                    "country_code": country_prefix.upper(),
                    "subdivision_code": None,
                    "geoid": geoid,
                    "parent_jurisdiction_id": None,
                    "official_url": None,
                    "coverage": {},
                    "exclusions": [],
                    "metadata": {"placeholder_from_manifest_geoid": True},
                }
            )

    if not normalized:
        raise ManifestValidationError("manifest jurisdiction coverage is empty")
    return normalized


def validate_source_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a declarative public-records source manifest."""
    if not isinstance(manifest, Mapping):
        raise ManifestValidationError("source manifest must be an object")

    try:
        normalized = json.loads(json.dumps(manifest))
    except (TypeError, ValueError) as error:
        raise ManifestValidationError("source manifest must be JSON serializable") from error

    source_id = _validate_source_id(_require_string(manifest, "source_id"))
    domain = _require_string(manifest, "domain")
    if domain not in DOMAINS:
        raise ManifestValidationError(
            f"domain must be one of {', '.join(sorted(DOMAINS))}"
        )

    authority = _require_string(manifest, "authority")
    operator = _require_string(manifest, "operator", default=authority)
    name = _require_string(manifest, "name", default=authority)
    official_url = _validate_url(
        manifest.get("official_url"), "official_url", required=True
    )
    terms_url = _validate_url(
        manifest.get("license_or_terms_url"),
        "license_or_terms_url",
        required=False,
    )

    roles = _canonical_names(manifest.get("roles"), "roles")
    stable_keys = _canonical_names(manifest.get("stable_keys"), "stable_keys")
    capabilities = _normalize_capabilities(manifest.get("capabilities"))
    jurisdictions = _normalize_jurisdictions(manifest, source_id)

    access_class = _require_string(manifest, "access_class").upper()
    if access_class not in ACCESS_CLASSES:
        raise ManifestValidationError(
            f"access_class must be one of {', '.join(sorted(ACCESS_CLASSES))}"
        )
    disposition = _require_string(manifest, "automation_disposition")
    if disposition not in AUTOMATION_DISPOSITIONS:
        raise ManifestValidationError(
            "automation_disposition must be one of "
            + ", ".join(sorted(AUTOMATION_DISPOSITIONS))
        )

    source_status = manifest.get("source_status", "candidate")
    if source_status not in SOURCE_STATUSES:
        raise ManifestValidationError(
            f"source_status must be one of {', '.join(sorted(SOURCE_STATUSES))}"
        )

    adapter_family = manifest.get("adapter_family")
    adapter_version = manifest.get("adapter_version")
    if adapter_family is not None:
        if not isinstance(adapter_family, str) or not _NAME_RE.fullmatch(
            adapter_family
        ):
            raise ManifestValidationError(
                "adapter_family must use lowercase snake_case"
            )
        if adapter_version is None:
            raise ManifestValidationError(
                "adapter_version is required when adapter_family is set"
            )
    if adapter_version is not None and (
        isinstance(adapter_version, bool)
        or not isinstance(adapter_version, (int, str))
        or not str(adapter_version).strip()
    ):
        raise ManifestValidationError("adapter_version must be an integer or string")

    last_verified_at = manifest.get("last_verified_at")
    if last_verified_at is not None:
        last_verified_at = normalize_timestamp(
            last_verified_at, "last_verified_at"
        )
    effective_at = manifest.get("effective_at")
    if effective_at is not None:
        effective_at = normalize_timestamp(effective_at, "effective_at")

    normalized.update(
        {
            "source_id": source_id,
            "name": name,
            "domain": domain,
            "roles": roles,
            "authority": authority,
            "operator": operator,
            "official_url": official_url,
            "platform_family": _require_string(manifest, "platform_family"),
            "access_class": access_class,
            "automation_disposition": disposition,
            "authentication": manifest.get("authentication", "unknown"),
            "fees": manifest.get("fees", "unknown"),
            "license_or_terms_url": terms_url,
            "stable_keys": stable_keys,
            "capabilities": capabilities,
            "jurisdictions": jurisdictions,
            "source_status": source_status,
            "adapter_family": adapter_family,
            "adapter_version": (
                str(adapter_version) if adapter_version is not None else None
            ),
            "last_verified_at": last_verified_at,
            "effective_at": effective_at,
        }
    )
    normalized.pop("jurisdiction_geoids", None)
    return normalized


class PublicRecordsCatalog:
    """SQLite-backed public-records source and capability catalog."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        *,
        initialize: bool = True,
    ):
        self.db_path = Path(db_path)
        if initialize:
            self.initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.db_path), timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    @staticmethod
    def _migrate_schema(db: sqlite3.Connection) -> None:
        """Bring older catalog sidecars forward without discarding census data."""
        census_columns = {
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(source_census_targets)"
            ).fetchall()
        }
        if "coverage_status" not in census_columns:
            db.execute(
                """
                ALTER TABLE source_census_targets
                ADD COLUMN coverage_status TEXT NOT NULL DEFAULT 'unassessed'
                    CHECK(coverage_status IN (
                        'unassessed', 'partial', 'comprehensive',
                        'not_applicable'
                    ))
                """
            )
        if "coverage_notes" not in census_columns:
            db.execute(
                "ALTER TABLE source_census_targets "
                "ADD COLUMN coverage_notes TEXT"
            )
        if "coverage_gaps_json" not in census_columns:
            db.execute(
                "ALTER TABLE source_census_targets "
                "ADD COLUMN coverage_gaps_json TEXT NOT NULL DEFAULT '[]'"
            )

        # Version 2 stored one source directly on each target. Retain those
        # compatibility columns and also materialize the association so future
        # resolutions can add sources without replacing earlier discoveries.
        db.execute(
            """
            INSERT OR IGNORE INTO source_census_target_sources(
                census_target_id, source_id, official_url, coverage_json,
                coverage_gaps_json, notes, evidence_json, added_by, added_at,
                updated_at
            )
            SELECT census_target_id, source_id, official_url, '{}', '[]',
                   notes, evidence_json,
                   COALESCE(resolved_by, 'schema-migration'),
                   COALESCE(resolved_at, updated_at), updated_at
            FROM source_census_targets
            WHERE source_id IS NOT NULL
            """
        )

    def initialize(self) -> dict[str, Any]:
        """Create the sidecar and schema if needed."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        db = self._connect()
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA_SQL)
            self._migrate_schema(db)
            db.execute(
                "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
            db.commit()
        finally:
            db.close()
        return {
            "status": "initialized",
            "db_path": str(self.db_path),
            "schema_version": SCHEMA_VERSION,
        }

    @staticmethod
    def validate_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
        return validate_source_manifest(manifest)

    def _require_source(self, db: sqlite3.Connection, source_id: str) -> sqlite3.Row:
        source_id = _validate_source_id(source_id)
        row = db.execute(
            "SELECT * FROM sources WHERE source_id = ?", (source_id,)
        ).fetchone()
        if row is None:
            raise CatalogError(f"unknown source_id: {source_id}")
        return row

    def register_manifest(
        self,
        manifest: Mapping[str, Any],
        *,
        submitted_by: str,
        submitted_at: str | None = None,
    ) -> dict[str, Any]:
        """Register a validated manifest without granting machine access."""
        normalized = validate_source_manifest(manifest)
        if not isinstance(submitted_by, str) or not submitted_by.strip():
            raise CatalogError("submitted_by is required")
        submitted_at = normalize_timestamp(
            submitted_at or utc_now(), "submitted_at"
        )
        recorded_at = utc_now()
        manifest_json = _json_dump(normalized)
        manifest_sha256 = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()

        db = self._connect()
        try:
            with db:
                db.execute(
                    """
                    INSERT INTO sources(
                        source_id, name, domain, authority, operator, official_url,
                        platform_family, source_status, proposed_access_class,
                        proposed_automation_disposition, authentication_json,
                        fees_json, license_or_terms_url, redistribution,
                        protected_record_policy, coverage_start, coverage_end,
                        update_cadence, stable_keys_json, adapter_family,
                        adapter_version, owner_team, declared_health_status,
                        last_verified_at, created_at, updated_at
                    ) VALUES(
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                    ON CONFLICT(source_id) DO UPDATE SET
                        name=excluded.name,
                        domain=excluded.domain,
                        authority=excluded.authority,
                        operator=excluded.operator,
                        official_url=excluded.official_url,
                        platform_family=excluded.platform_family,
                        source_status=excluded.source_status,
                        proposed_access_class=excluded.proposed_access_class,
                        proposed_automation_disposition=
                            excluded.proposed_automation_disposition,
                        authentication_json=excluded.authentication_json,
                        fees_json=excluded.fees_json,
                        license_or_terms_url=excluded.license_or_terms_url,
                        redistribution=excluded.redistribution,
                        protected_record_policy=excluded.protected_record_policy,
                        coverage_start=excluded.coverage_start,
                        coverage_end=excluded.coverage_end,
                        update_cadence=excluded.update_cadence,
                        stable_keys_json=excluded.stable_keys_json,
                        adapter_family=excluded.adapter_family,
                        adapter_version=excluded.adapter_version,
                        owner_team=excluded.owner_team,
                        declared_health_status=excluded.declared_health_status,
                        last_verified_at=excluded.last_verified_at,
                        updated_at=excluded.updated_at
                    """,
                    (
                        normalized["source_id"],
                        normalized["name"],
                        normalized["domain"],
                        normalized["authority"],
                        normalized["operator"],
                        normalized["official_url"],
                        normalized["platform_family"],
                        normalized["source_status"],
                        normalized["access_class"],
                        normalized["automation_disposition"],
                        _json_dump(normalized["authentication"]),
                        _json_dump(normalized["fees"]),
                        normalized.get("license_or_terms_url"),
                        normalized.get("redistribution"),
                        normalized.get("protected_record_policy"),
                        normalized.get("coverage_start"),
                        normalized.get("coverage_end"),
                        normalized.get("update_cadence"),
                        _json_dump(normalized["stable_keys"]),
                        normalized.get("adapter_family"),
                        normalized.get("adapter_version"),
                        normalized.get("owner_team"),
                        normalized.get("health_status"),
                        normalized.get("last_verified_at"),
                        recorded_at,
                        recorded_at,
                    ),
                )

                db.execute(
                    """
                    INSERT OR IGNORE INTO source_manifests(
                        source_id, manifest_sha256, manifest_json, submitted_by,
                        submitted_at, effective_at, recorded_at
                    ) VALUES(?,?,?,?,?,?,?)
                    """,
                    (
                        normalized["source_id"],
                        manifest_sha256,
                        manifest_json,
                        submitted_by.strip(),
                        submitted_at,
                        normalized.get("effective_at"),
                        recorded_at,
                    ),
                )
                manifest_row = db.execute(
                    """
                    SELECT manifest_id FROM source_manifests
                    WHERE source_id = ? AND manifest_sha256 = ?
                    """,
                    (normalized["source_id"], manifest_sha256),
                ).fetchone()
                assert manifest_row is not None
                manifest_id = int(manifest_row["manifest_id"])
                db.execute(
                    "UPDATE sources SET current_manifest_id=? WHERE source_id=?",
                    (manifest_id, normalized["source_id"]),
                )

                db.execute(
                    "DELETE FROM source_jurisdictions WHERE source_id=?",
                    (normalized["source_id"],),
                )
                for jurisdiction in normalized["jurisdictions"]:
                    existing_jurisdiction = None
                    if jurisdiction["geoid"] is not None:
                        existing_jurisdiction = db.execute(
                            """
                            SELECT jurisdiction_id FROM jurisdictions
                            WHERE country_code=? AND geoid=?
                            """,
                            (
                                jurisdiction["country_code"],
                                jurisdiction["geoid"],
                            ),
                        ).fetchone()
                    resolved_jurisdiction_id = (
                        str(existing_jurisdiction["jurisdiction_id"])
                        if existing_jurisdiction is not None
                        else jurisdiction["jurisdiction_id"]
                    )
                    is_geoid_placeholder = bool(
                        jurisdiction["metadata"].get(
                            "placeholder_from_manifest_geoid"
                        )
                    )
                    if existing_jurisdiction is None or not is_geoid_placeholder:
                        db.execute(
                            """
                            INSERT INTO jurisdictions(
                                jurisdiction_id, name, kind, country_code,
                                subdivision_code, geoid, parent_jurisdiction_id,
                                official_url, metadata_json, created_at, updated_at
                            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                            ON CONFLICT(jurisdiction_id) DO UPDATE SET
                                name=excluded.name,
                                kind=excluded.kind,
                                country_code=excluded.country_code,
                                subdivision_code=excluded.subdivision_code,
                                geoid=excluded.geoid,
                                parent_jurisdiction_id=
                                    excluded.parent_jurisdiction_id,
                                official_url=excluded.official_url,
                                metadata_json=excluded.metadata_json,
                                updated_at=excluded.updated_at
                            """,
                            (
                                resolved_jurisdiction_id,
                                jurisdiction["name"],
                                jurisdiction["kind"],
                                jurisdiction["country_code"],
                                jurisdiction["subdivision_code"],
                                jurisdiction["geoid"],
                                jurisdiction["parent_jurisdiction_id"],
                                jurisdiction["official_url"],
                                _json_dump(jurisdiction["metadata"]),
                                recorded_at,
                                recorded_at,
                            ),
                        )
                    db.execute(
                        """
                        INSERT INTO source_jurisdictions(
                            source_id, jurisdiction_id, coverage_json,
                            exclusions_json
                        ) VALUES(?,?,?,?)
                        """,
                        (
                            normalized["source_id"],
                            resolved_jurisdiction_id,
                            _json_dump(jurisdiction["coverage"]),
                            _json_dump(jurisdiction["exclusions"]),
                        ),
                    )

                db.execute(
                    "DELETE FROM source_roles WHERE source_id=?",
                    (normalized["source_id"],),
                )
                db.executemany(
                    "INSERT INTO source_roles(source_id, role) VALUES(?,?)",
                    [
                        (normalized["source_id"], role)
                        for role in normalized["roles"]
                    ],
                )

                db.execute(
                    "DELETE FROM capabilities WHERE source_id=?",
                    (normalized["source_id"],),
                )
                db.executemany(
                    """
                    INSERT INTO capabilities(
                        source_id, capability, supported, details_json,
                        recorded_at
                    ) VALUES(?,?,?,?,?)
                    """,
                    [
                        (
                            normalized["source_id"],
                            capability["name"],
                            int(capability["supported"]),
                            _json_dump(capability["details"]),
                            recorded_at,
                        )
                        for capability in normalized["capabilities"]
                    ],
                )
        finally:
            db.close()

        return {
            "source_id": normalized["source_id"],
            "manifest_id": manifest_id,
            "manifest_sha256": manifest_sha256,
            "submitted_at": submitted_at,
            "access_review_required": True,
        }

    def list_sources(
        self,
        *,
        domain: str | None = None,
        jurisdiction: str | None = None,
        access_class: str | None = None,
        automation_disposition: str | None = None,
    ) -> list[dict[str, Any]]:
        """List sources with their latest reviewed access and probe state."""
        if domain is not None and domain not in DOMAINS:
            raise CatalogError(f"invalid domain: {domain}")
        if access_class is not None:
            access_class = access_class.upper()
            if access_class not in ACCESS_CLASSES:
                raise CatalogError(f"invalid access class: {access_class}")
        if (
            automation_disposition is not None
            and automation_disposition not in AUTOMATION_DISPOSITIONS
        ):
            raise CatalogError(
                f"invalid automation disposition: {automation_disposition}"
            )

        conditions: list[str] = []
        params: list[Any] = []
        if domain:
            conditions.append("s.domain = ?")
            params.append(domain)
        if jurisdiction:
            conditions.append(
                """
                EXISTS(
                    SELECT 1
                    FROM source_jurisdictions sj
                    JOIN jurisdictions j USING(jurisdiction_id)
                    WHERE sj.source_id=s.source_id
                      AND (
                        j.jurisdiction_id=? OR j.geoid=? OR
                        lower(j.name)=lower(?) OR
                        lower(COALESCE(j.subdivision_code, ''))=lower(?) OR
                        (
                          length(?)=2 AND
                          ? NOT GLOB '*[^0-9]*' AND
                          j.geoid LIKE ? || '%'
                        ) OR
                        (
                          length(j.geoid)=2 AND
                          ? != '' AND
                          ? NOT GLOB '*[^0-9]*' AND
                          ? LIKE j.geoid || '%'
                        ) OR
                        EXISTS(
                          SELECT 1 FROM jurisdictions requested
                          WHERE (
                            requested.jurisdiction_id=? OR
                            requested.geoid=? OR
                            lower(requested.name)=lower(?) OR
                            lower(COALESCE(
                              requested.subdivision_code, ''
                            ))=lower(?)
                          )
                          AND requested.geoid IS NOT NULL
                          AND j.geoid IS NOT NULL
                          AND (
                            j.geoid=requested.geoid OR
                            (
                              length(requested.geoid)=2 AND
                              j.geoid LIKE requested.geoid || '%'
                            ) OR
                            (
                              length(j.geoid)=2 AND
                              requested.geoid LIKE j.geoid || '%'
                            )
                          )
                        )
                      )
                )
                """
            )
            params.extend([jurisdiction] * 14)
        if access_class:
            conditions.append("ar.access_class = ?")
            params.append(access_class)
        if automation_disposition:
            conditions.append("ar.automation_disposition = ?")
            params.append(automation_disposition)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        db = self._connect()
        try:
            rows = db.execute(
                f"""
                SELECT
                    s.source_id, s.name, s.domain, s.authority,
                    s.official_url, s.platform_family, s.source_status,
                    s.proposed_access_class,
                    s.proposed_automation_disposition,
                    ar.access_review_id, ar.access_class,
                    ar.automation_disposition, ar.reviewed_at,
                    p.probe_id, p.status AS probe_status,
                    p.probed_at
                FROM sources s
                LEFT JOIN access_reviews ar
                  ON ar.access_review_id = (
                      SELECT MAX(ar2.access_review_id)
                      FROM access_reviews ar2
                      WHERE ar2.source_id=s.source_id
                  )
                LEFT JOIN probes p
                  ON p.probe_id = (
                      SELECT MAX(p2.probe_id)
                      FROM probes p2
                      WHERE p2.source_id=s.source_id
                  )
                {where}
                ORDER BY s.source_id
                """,
                params,
            ).fetchall()
        finally:
            db.close()
        return [dict(row) for row in rows]

    def show_source(self, source_id: str) -> dict[str, Any]:
        """Return source, manifest, jurisdiction, review, terms, and probe detail."""
        db = self._connect()
        try:
            source = self._require_source(db, source_id)
            source_data = dict(source)
            for field in ("authentication_json", "fees_json", "stable_keys_json"):
                source_data[field.removesuffix("_json")] = _json_load(
                    source_data.pop(field), None
                )

            roles = [
                row["role"]
                for row in db.execute(
                    "SELECT role FROM source_roles WHERE source_id=? ORDER BY role",
                    (source_id,),
                )
            ]
            capabilities = [
                {
                    "name": row["capability"],
                    "supported": bool(row["supported"]),
                    "details": _json_load(row["details_json"], {}),
                    "recorded_at": row["recorded_at"],
                }
                for row in db.execute(
                    """
                    SELECT * FROM capabilities
                    WHERE source_id=? ORDER BY capability
                    """,
                    (source_id,),
                )
            ]
            jurisdictions = []
            for row in db.execute(
                """
                SELECT j.*, sj.coverage_json, sj.exclusions_json
                FROM source_jurisdictions sj
                JOIN jurisdictions j USING(jurisdiction_id)
                WHERE sj.source_id=? ORDER BY j.jurisdiction_id
                """,
                (source_id,),
            ):
                item = dict(row)
                item["metadata"] = _json_load(item.pop("metadata_json"), {})
                item["coverage"] = _json_load(item.pop("coverage_json"), {})
                item["exclusions"] = _json_load(item.pop("exclusions_json"), [])
                jurisdictions.append(item)

            manifest_rows = db.execute(
                """
                SELECT manifest_id, manifest_sha256, submitted_by, submitted_at,
                       effective_at, recorded_at
                FROM source_manifests
                WHERE source_id=? ORDER BY manifest_id DESC
                """,
                (source_id,),
            ).fetchall()
            current_manifest = db.execute(
                """
                SELECT manifest_json FROM source_manifests
                WHERE manifest_id=?
                """,
                (source["current_manifest_id"],),
            ).fetchone()

            review_rows = db.execute(
                """
                SELECT * FROM access_reviews
                WHERE source_id=? ORDER BY access_review_id DESC
                """,
                (source_id,),
            ).fetchall()
            reviews = []
            for row in review_rows:
                item = dict(row)
                item["limits"] = _json_load(item.pop("limits_json"), {})
                item["contract_verified"] = bool(item["contract_verified"])
                reviews.append(item)

            terms = []
            for row in db.execute(
                """
                SELECT terms_snapshot_id, source_id, snapshot_type, source_url,
                       captured_at, content_sha256, artifact_ref, recorded_by,
                       notes, recorded_at,
                       CASE WHEN content_text IS NULL THEN 0 ELSE 1 END
                           AS has_inline_content
                FROM terms_snapshots
                WHERE source_id=? ORDER BY terms_snapshot_id DESC
                """,
                (source_id,),
            ):
                item = dict(row)
                item["has_inline_content"] = bool(item["has_inline_content"])
                terms.append(item)

            probes = []
            for row in db.execute(
                """
                SELECT * FROM probes
                WHERE source_id=? ORDER BY probe_id DESC LIMIT 20
                """,
                (source_id,),
            ):
                item = dict(row)
                item["details"] = _json_load(item.pop("details_json"), {})
                probes.append(item)
        finally:
            db.close()

        return {
            "source": source_data,
            "roles": roles,
            "capabilities": capabilities,
            "jurisdictions": jurisdictions,
            "current_manifest": (
                _json_load(current_manifest["manifest_json"], {})
                if current_manifest
                else None
            ),
            "manifest_history": [dict(row) for row in manifest_rows],
            "latest_access_review": reviews[0] if reviews else None,
            "access_review_history": reviews,
            "terms_snapshots": terms,
            "latest_probe": probes[0] if probes else None,
            "probe_history": probes,
        }

    def probe_history(
        self,
        source_id: str,
        *,
        probe_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Return immutable probes newest-first, optionally selecting exact IDs."""
        selected_ids: tuple[int, ...] | None = None
        if probe_ids is not None:
            selected_ids = tuple(probe_ids)
            if any(
                isinstance(probe_id, bool)
                or not isinstance(probe_id, int)
                or probe_id <= 0
                for probe_id in selected_ids
            ):
                raise CatalogError("probe_ids must contain positive integers")
            if len(set(selected_ids)) != len(selected_ids):
                raise CatalogError("probe_ids must not contain duplicates")

        db = self._connect()
        try:
            self._require_source(db, source_id)
            if selected_ids is None:
                rows = db.execute(
                    """
                    SELECT * FROM probes
                    WHERE source_id=?
                    ORDER BY probe_id DESC
                    """,
                    (source_id,),
                ).fetchall()
            elif not selected_ids:
                rows = []
            else:
                placeholders = ",".join("?" for _ in selected_ids)
                rows = db.execute(
                    f"""
                    SELECT * FROM probes
                    WHERE source_id=? AND probe_id IN ({placeholders})
                    ORDER BY probe_id DESC
                    """,
                    (source_id, *selected_ids),
                ).fetchall()
        finally:
            db.close()

        probes: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["details"] = _json_load(item.pop("details_json"), {})
            probes.append(item)
        return probes

    def record_terms_snapshot(
        self,
        source_id: str,
        *,
        snapshot_type: str,
        source_url: str,
        captured_at: str,
        recorded_by: str,
        content_text: str | None = None,
        content_sha256: str | None = None,
        artifact_ref: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Append an immutable terms, robots, license, or court-rule snapshot."""
        if snapshot_type not in TERMS_SNAPSHOT_TYPES:
            raise CatalogError(f"invalid snapshot_type: {snapshot_type}")
        source_url = _validate_url(source_url, "source_url", required=True)
        captured_at = normalize_timestamp(captured_at, "captured_at")
        if not isinstance(recorded_by, str) or not recorded_by.strip():
            raise CatalogError("recorded_by is required")
        if content_text is None and content_sha256 is None:
            raise CatalogError(
                "a terms snapshot needs content_text or an actual content_sha256"
            )
        calculated_sha = (
            hashlib.sha256(content_text.encode("utf-8")).hexdigest()
            if content_text is not None
            else None
        )
        if content_sha256 is not None:
            content_sha256 = content_sha256.lower()
            if not _SHA256_RE.fullmatch(content_sha256):
                raise CatalogError("content_sha256 must be a lowercase SHA-256")
            if calculated_sha and calculated_sha != content_sha256:
                raise CatalogError("content_sha256 does not match content_text")
        content_sha256 = content_sha256 or calculated_sha
        assert content_sha256 is not None
        recorded_at = utc_now()

        db = self._connect()
        try:
            with db:
                self._require_source(db, source_id)
                cursor = db.execute(
                    """
                    INSERT INTO terms_snapshots(
                        source_id, snapshot_type, source_url, captured_at,
                        content_sha256, content_text, artifact_ref, recorded_by,
                        notes, recorded_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        source_id,
                        snapshot_type,
                        source_url,
                        captured_at,
                        content_sha256,
                        content_text,
                        artifact_ref,
                        recorded_by.strip(),
                        notes,
                        recorded_at,
                    ),
                )
                snapshot_id = int(cursor.lastrowid)
        finally:
            db.close()
        return {
            "terms_snapshot_id": snapshot_id,
            "source_id": source_id,
            "snapshot_type": snapshot_type,
            "captured_at": captured_at,
            "content_sha256": content_sha256,
            "recorded_at": recorded_at,
        }

    def evaluate_access(
        self,
        source_id: str,
        *,
        access_class: str,
        automation_disposition: str,
        reviewed_by: str,
        review_basis: str,
        reviewed_at: str | None = None,
        limits: Mapping[str, Any] | None = None,
        notes: str | None = None,
        terms_snapshot_id: int | None = None,
        contract_verified: bool = False,
        contract_reference: str | None = None,
        valid_until: str | None = None,
    ) -> dict[str, Any]:
        """Append a human/deterministic access review.

        A manifest's proposed access fields are deliberately ignored here.
        """
        access_class = access_class.upper()
        if access_class not in ACCESS_CLASSES:
            raise CatalogError(f"invalid access_class: {access_class}")
        if automation_disposition not in AUTOMATION_DISPOSITIONS:
            raise CatalogError(
                f"invalid automation_disposition: {automation_disposition}"
            )
        if not isinstance(reviewed_by, str) or not reviewed_by.strip():
            raise CatalogError("reviewed_by is required")
        if not isinstance(review_basis, str) or not review_basis.strip():
            raise CatalogError("review_basis is required")
        limits = dict(limits or {})
        if automation_disposition == "allowed_with_limits" and not limits:
            raise CatalogError(
                "allowed_with_limits requires a non-empty limits contract"
            )
        if not isinstance(contract_verified, bool):
            raise CatalogError("contract_verified must be boolean")
        if contract_verified and (
            not isinstance(contract_reference, str)
            or not contract_reference.strip()
        ):
            raise CatalogError(
                "contract_reference is required when contract_verified is true"
            )
        if contract_verified and access_class != "D":
            raise CatalogError("contract_verified is only applicable to class D")

        reviewed_at = normalize_timestamp(
            reviewed_at or utc_now(), "reviewed_at"
        )
        if valid_until is not None:
            valid_until = normalize_timestamp(valid_until, "valid_until")
            if _parse_timestamp(valid_until) <= _parse_timestamp(reviewed_at):
                raise CatalogError("valid_until must be after reviewed_at")
        recorded_at = utc_now()

        db = self._connect()
        try:
            with db:
                self._require_source(db, source_id)
                if terms_snapshot_id is not None:
                    snapshot = db.execute(
                        """
                        SELECT source_id FROM terms_snapshots
                        WHERE terms_snapshot_id=?
                        """,
                        (terms_snapshot_id,),
                    ).fetchone()
                    if snapshot is None:
                        raise CatalogError(
                            f"unknown terms_snapshot_id: {terms_snapshot_id}"
                        )
                    if snapshot["source_id"] != source_id:
                        raise CatalogError(
                            "terms snapshot belongs to a different source"
                        )
                previous = db.execute(
                    """
                    SELECT MAX(access_review_id) AS review_id
                    FROM access_reviews WHERE source_id=?
                    """,
                    (source_id,),
                ).fetchone()["review_id"]
                cursor = db.execute(
                    """
                    INSERT INTO access_reviews(
                        source_id, access_class, automation_disposition,
                        limits_json, review_basis, notes, terms_snapshot_id,
                        contract_verified, contract_reference, reviewed_by,
                        reviewed_at, valid_until, supersedes_review_id,
                        recorded_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        source_id,
                        access_class,
                        automation_disposition,
                        _json_dump(limits),
                        review_basis.strip(),
                        notes,
                        terms_snapshot_id,
                        int(contract_verified),
                        (
                            contract_reference.strip()
                            if contract_reference is not None
                            else None
                        ),
                        reviewed_by.strip(),
                        reviewed_at,
                        valid_until,
                        previous,
                        recorded_at,
                    ),
                )
                review_id = int(cursor.lastrowid)
        finally:
            db.close()

        return {
            "access_review_id": review_id,
            "source_id": source_id,
            "access_class": access_class,
            "automation_disposition": automation_disposition,
            "limits": limits,
            "contract_verified": contract_verified,
            "reviewed_by": reviewed_by.strip(),
            "reviewed_at": reviewed_at,
            "valid_until": valid_until,
            "supersedes_review_id": previous,
            "recorded_at": recorded_at,
        }

    def machine_acquisition_decision(
        self,
        source_id: str,
        *,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        """Return the current catalog decision for an acquisition attempt."""
        as_of = normalize_timestamp(as_of or utc_now(), "as_of")

        db = self._connect()
        try:
            self._require_source(db, source_id)
            row = db.execute(
                """
                SELECT * FROM access_reviews
                WHERE source_id=?
                ORDER BY access_review_id DESC LIMIT 1
                """,
                (source_id,),
            ).fetchone()
        finally:
            db.close()

        base = {
            "source_id": source_id,
            "allowed": False,
            "as_of": as_of,
        }
        if row is None:
            return {
                **base,
                "reason": "no reviewed access decision exists",
                "reason_code": "access_review_required",
            }

        review = dict(row)
        limits = _json_load(review.pop("limits_json"), {})
        base.update(
            {
                "access_review_id": review["access_review_id"],
                "access_class": review["access_class"],
                "automation_disposition": review["automation_disposition"],
                "limits": limits,
                "reviewed_at": review["reviewed_at"],
                "valid_until": review["valid_until"],
                "contract_verified": bool(review["contract_verified"]),
            }
        )

        if review["valid_until"] and _parse_timestamp(as_of) > _parse_timestamp(
            review["valid_until"]
        ):
            return {
                **base,
                "reason": "the latest access review has expired",
                "reason_code": "access_review_expired",
            }
        if review["access_class"] == "X":
            return {
                **base,
                "reason": "the current review records no acquisition route",
                "reason_code": "no_acquisition_route",
            }
        if review["automation_disposition"] not in {
            "allowed",
            "allowed_with_limits",
        }:
            return {
                **base,
                "reason": (
                    "automation disposition is "
                    f"{review['automation_disposition']}"
                ),
                "reason_code": "automation_not_approved",
            }
        if review["access_class"] == "D" and not review["contract_verified"]:
            return {
                **base,
                "reason": "class D license/procurement contract is not verified",
                "reason_code": "licensed_contract_required",
            }
        return {
            **base,
            "allowed": True,
            "reason": "latest access review permits machine acquisition",
            "reason_code": "allowed",
        }

    def require_machine_acquisition(
        self,
        source_id: str,
        *,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        """Return the current route or raise with its catalog decision."""
        decision = self.machine_acquisition_decision(
            source_id,
            as_of=as_of,
        )
        if not decision["allowed"]:
            raise AcquisitionUnavailableError(decision)
        return decision

    def assert_machine_acquisition_allowed(
        self,
        source_id: str,
        *,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        """Compatibility alias with an explicit assertion-style name."""
        return self.require_machine_acquisition(
            source_id,
            as_of=as_of,
        )

    def record_probe(
        self,
        source_id: str,
        *,
        status: str,
        probed_by: str,
        probed_at: str | None = None,
        probe_kind: str = "sentinel",
        capability: str | None = None,
        endpoint: str | None = None,
        http_status: int | None = None,
        latency_ms: float | None = None,
        schema_sha256: str | None = None,
        artifact_sha256: str | None = None,
        result_count: int | None = None,
        details: Mapping[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Append a source probe without conflating errors with true zeroes."""
        if status not in PROBE_STATUSES:
            raise CatalogError(f"invalid probe status: {status}")
        if not isinstance(probed_by, str) or not probed_by.strip():
            raise CatalogError("probed_by is required")
        if not isinstance(probe_kind, str) or not _NAME_RE.fullmatch(probe_kind):
            raise CatalogError("probe_kind must use lowercase snake_case")
        if capability is not None and not _NAME_RE.fullmatch(capability):
            raise CatalogError("capability must use lowercase snake_case")
        if endpoint is not None:
            endpoint = _validate_probe_endpoint(endpoint)
        if http_status is not None and not 100 <= http_status <= 599:
            raise CatalogError("http_status must be between 100 and 599")
        if latency_ms is not None and latency_ms < 0:
            raise CatalogError("latency_ms cannot be negative")
        if result_count is not None and result_count < 0:
            raise CatalogError("result_count cannot be negative")
        for field_name, digest in (
            ("schema_sha256", schema_sha256),
            ("artifact_sha256", artifact_sha256),
        ):
            if digest is not None and not _SHA256_RE.fullmatch(digest):
                raise CatalogError(f"{field_name} must be a lowercase SHA-256")
        if details is not None and not isinstance(details, Mapping):
            raise CatalogError("details must be an object")
        if status == "error" and not error:
            raise CatalogError("error probe status requires an error message")

        probed_at = normalize_timestamp(probed_at or utc_now(), "probed_at")
        recorded_at = utc_now()
        db = self._connect()
        try:
            with db:
                self._require_source(db, source_id)
                cursor = db.execute(
                    """
                    INSERT INTO probes(
                        source_id, probe_kind, capability, status, endpoint,
                        http_status, latency_ms, schema_sha256, artifact_sha256,
                        result_count, details_json, error, probed_by, probed_at,
                        recorded_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        source_id,
                        probe_kind,
                        capability,
                        status,
                        endpoint,
                        http_status,
                        latency_ms,
                        schema_sha256,
                        artifact_sha256,
                        result_count,
                        _json_dump(dict(details or {})),
                        error,
                        probed_by.strip(),
                        probed_at,
                        recorded_at,
                    ),
                )
                probe_id = int(cursor.lastrowid)
        finally:
            db.close()
        return {
            "probe_id": probe_id,
            "source_id": source_id,
            "status": status,
            "probed_at": probed_at,
            "recorded_at": recorded_at,
        }

    def health(
        self,
        source_id: str | None = None,
        *,
        max_age_hours: float = 168,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return source health derived from the latest immutable probe."""
        if max_age_hours < 0:
            raise CatalogError("max_age_hours cannot be negative")
        as_of = normalize_timestamp(as_of or utc_now(), "as_of")
        if source_id is not None:
            source_ids = [source_id]
        else:
            source_ids = [row["source_id"] for row in self.list_sources()]

        results: list[dict[str, Any]] = []
        db = self._connect()
        try:
            for current_source_id in source_ids:
                source = self._require_source(db, current_source_id)
                probe = db.execute(
                    """
                    SELECT * FROM probes
                    WHERE source_id=?
                    ORDER BY probe_id DESC LIMIT 1
                    """,
                    (current_source_id,),
                ).fetchone()
                access = db.execute(
                    """
                    SELECT access_review_id, access_class,
                           automation_disposition, reviewed_at
                    FROM access_reviews
                    WHERE source_id=?
                    ORDER BY access_review_id DESC LIMIT 1
                    """,
                    (current_source_id,),
                ).fetchone()
                item: dict[str, Any] = {
                    "source_id": current_source_id,
                    "name": source["name"],
                    "health": "unknown",
                    "observed_status": None,
                    "probe_id": None,
                    "probed_at": None,
                    "age_hours": None,
                    "access_review": dict(access) if access else None,
                }
                if probe is None:
                    results.append(item)
                    continue

                age_hours = max(
                    0.0,
                    (
                        _parse_timestamp(as_of)
                        - _parse_timestamp(probe["probed_at"])
                    ).total_seconds()
                    / 3600,
                )
                observed_status = probe["status"]
                if observed_status in {"ok", "no_results"}:
                    health_state = "healthy"
                elif observed_status in {"partial", "rate_limited"}:
                    health_state = "degraded"
                elif observed_status in {
                    "restricted",
                    "human_required",
                    "terms_blocked",
                }:
                    health_state = "restricted"
                else:
                    health_state = "unhealthy"
                if age_hours > max_age_hours:
                    health_state = "stale"
                item.update(
                    {
                        "health": health_state,
                        "observed_status": observed_status,
                        "probe_id": probe["probe_id"],
                        "probed_at": probe["probed_at"],
                        "age_hours": round(age_hours, 3),
                        "endpoint": probe["endpoint"],
                        "http_status": probe["http_status"],
                        "error": probe["error"],
                    }
                )
                results.append(item)
        finally:
            db.close()
        return results


SourceCatalog = PublicRecordsCatalog


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load a JSON or YAML source manifest."""
    if str(path) == "-":
        text = sys.stdin.read()
        suffix = ""
    else:
        manifest_path = Path(path)
        text = manifest_path.read_text()
        suffix = manifest_path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ImportError as error:
            raise CatalogError(
                "PyYAML is required for YAML manifests; use JSON instead"
            ) from error
        data = yaml.safe_load(text)
    if not isinstance(data, Mapping):
        raise ManifestValidationError("manifest file must contain an object")
    return dict(data)


def _parse_json_object(raw: str | None, field_name: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if raw.startswith("@"):
        raw = Path(raw[1:]).read_text()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CatalogError(f"{field_name} must be valid JSON") from error
    if not isinstance(value, Mapping):
        raise CatalogError(f"{field_name} must be a JSON object")
    return dict(value)


def _add_command_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        dest="command_db",
        help="Override the catalog SQLite path",
    )
    parser.add_argument(
        "--json",
        dest="command_json",
        action="store_true",
        help="Print machine-readable JSON",
    )
    parser.add_argument(
        "--output",
        dest="command_output",
        help="Write the complete JSON result to this file",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Public property/court source and capability catalog"
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Catalog SQLite path",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON")
    parser.add_argument("--output", help="Write complete JSON to a file")
    sub = parser.add_subparsers(dest="command", required=True)

    command = sub.add_parser("init", help="Initialize the catalog schema")
    _add_command_common(command)

    command = sub.add_parser("register", help="Register a JSON/YAML source manifest")
    command.add_argument("manifest")
    command.add_argument("--submitted-by", required=True)
    command.add_argument("--submitted-at")
    _add_command_common(command)

    command = sub.add_parser("list", help="List cataloged sources")
    command.add_argument("--domain", choices=sorted(DOMAINS))
    command.add_argument("--jurisdiction")
    command.add_argument("--access-class", choices=sorted(ACCESS_CLASSES))
    command.add_argument(
        "--disposition", choices=sorted(AUTOMATION_DISPOSITIONS)
    )
    _add_command_common(command)

    command = sub.add_parser("show", help="Show complete source metadata")
    command.add_argument("source_id")
    _add_command_common(command)

    command = sub.add_parser(
        "record-terms", help="Record an immutable terms/robots/rule snapshot"
    )
    command.add_argument("source_id")
    command.add_argument("--type", required=True, choices=sorted(TERMS_SNAPSHOT_TYPES))
    command.add_argument("--url", required=True)
    command.add_argument("--captured-at", required=True)
    command.add_argument("--recorded-by", required=True)
    command.add_argument("--content-file")
    command.add_argument("--content-sha256")
    command.add_argument("--artifact-ref")
    command.add_argument("--notes")
    _add_command_common(command)

    command = sub.add_parser(
        "evaluate-access", help="Append a reviewed access decision"
    )
    command.add_argument("source_id")
    command.add_argument("--access-class", required=True, choices=sorted(ACCESS_CLASSES))
    command.add_argument(
        "--disposition",
        required=True,
        choices=sorted(AUTOMATION_DISPOSITIONS),
    )
    command.add_argument("--reviewed-by", required=True)
    command.add_argument("--reviewed-at")
    command.add_argument("--basis", required=True)
    command.add_argument("--notes")
    command.add_argument("--terms-snapshot-id", type=int)
    command.add_argument("--limits", help="JSON object or @file")
    command.add_argument("--contract-verified", action="store_true")
    command.add_argument("--contract-reference")
    command.add_argument("--valid-until")
    _add_command_common(command)

    command = sub.add_parser("record-probe", help="Append a source probe")
    command.add_argument("source_id")
    command.add_argument("--status", required=True, choices=sorted(PROBE_STATUSES))
    command.add_argument("--probed-by", required=True)
    command.add_argument("--probed-at")
    command.add_argument("--kind", default="sentinel")
    command.add_argument("--capability")
    command.add_argument("--endpoint")
    command.add_argument("--http-status", type=int)
    command.add_argument("--latency-ms", type=float)
    command.add_argument("--schema-sha256")
    command.add_argument("--artifact-sha256")
    command.add_argument("--result-count", type=int)
    command.add_argument("--details", help="JSON object or @file")
    command.add_argument("--error")
    _add_command_common(command)

    command = sub.add_parser("health", help="Show latest probe-derived health")
    command.add_argument("source_id", nargs="?")
    command.add_argument("--max-age-hours", type=float, default=168)
    command.add_argument("--as-of")
    _add_command_common(command)
    return parser


def _emit(
    data: Any,
    *,
    json_mode: bool,
    output: str | None,
    human_summary: str | None = None,
) -> None:
    serialized = json.dumps(data, indent=2, sort_keys=True, default=str)
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized + "\n")
        if not json_mode:
            print(f"Saved catalog result to {output_path}")
            return
    if json_mode or human_summary is None:
        print(serialized)
    else:
        print(human_summary)


def _source_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No cataloged sources."
    lines = [
        "SOURCE_ID | DOMAIN | ACCESS | DISPOSITION | PROBE",
        "-" * 78,
    ]
    for row in rows:
        lines.append(
            " | ".join(
                [
                    row["source_id"],
                    row["domain"],
                    row.get("access_class") or "unreviewed",
                    row.get("automation_disposition") or "unreviewed",
                    row.get("probe_status") or "unprobed",
                ]
            )
        )
    return "\n".join(lines)


def _health_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No cataloged sources."
    lines = ["SOURCE_ID | HEALTH | OBSERVED | PROBED_AT", "-" * 72]
    for row in rows:
        lines.append(
            " | ".join(
                [
                    row["source_id"],
                    row["health"],
                    row.get("observed_status") or "-",
                    row.get("probed_at") or "-",
                ]
            )
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    db_path = args.command_db or args.db
    json_mode = bool(args.json or args.command_json)
    output = args.command_output or args.output

    try:
        catalog = PublicRecordsCatalog(db_path)
        if args.command == "init":
            data = catalog.initialize()
            summary = (
                f"Initialized public-records catalog at {data['db_path']} "
                f"(schema {data['schema_version']})"
            )
        elif args.command == "register":
            data = catalog.register_manifest(
                load_manifest(args.manifest),
                submitted_by=args.submitted_by,
                submitted_at=args.submitted_at,
            )
            summary = (
                f"Registered {data['source_id']} manifest "
                f"#{data['manifest_id']}; access review required"
            )
        elif args.command == "list":
            data = catalog.list_sources(
                domain=args.domain,
                jurisdiction=args.jurisdiction,
                access_class=args.access_class,
                automation_disposition=args.disposition,
            )
            summary = _source_table(data)
        elif args.command == "show":
            data = catalog.show_source(args.source_id)
            summary = None
        elif args.command == "record-terms":
            content_text = (
                Path(args.content_file).read_text() if args.content_file else None
            )
            data = catalog.record_terms_snapshot(
                args.source_id,
                snapshot_type=args.type,
                source_url=args.url,
                captured_at=args.captured_at,
                recorded_by=args.recorded_by,
                content_text=content_text,
                content_sha256=args.content_sha256,
                artifact_ref=args.artifact_ref,
                notes=args.notes,
            )
            summary = (
                f"Recorded terms snapshot #{data['terms_snapshot_id']} "
                f"for {data['source_id']}"
            )
        elif args.command == "evaluate-access":
            data = catalog.evaluate_access(
                args.source_id,
                access_class=args.access_class,
                automation_disposition=args.disposition,
                reviewed_by=args.reviewed_by,
                reviewed_at=args.reviewed_at,
                review_basis=args.basis,
                notes=args.notes,
                terms_snapshot_id=args.terms_snapshot_id,
                limits=_parse_json_object(args.limits, "limits"),
                contract_verified=args.contract_verified,
                contract_reference=args.contract_reference,
                valid_until=args.valid_until,
            )
            summary = (
                f"Recorded access review #{data['access_review_id']} "
                f"for {data['source_id']}: {data['access_class']}/"
                f"{data['automation_disposition']}"
            )
        elif args.command == "record-probe":
            data = catalog.record_probe(
                args.source_id,
                status=args.status,
                probed_by=args.probed_by,
                probed_at=args.probed_at,
                probe_kind=args.kind,
                capability=args.capability,
                endpoint=args.endpoint,
                http_status=args.http_status,
                latency_ms=args.latency_ms,
                schema_sha256=args.schema_sha256,
                artifact_sha256=args.artifact_sha256,
                result_count=args.result_count,
                details=_parse_json_object(args.details, "details"),
                error=args.error,
            )
            summary = (
                f"Recorded probe #{data['probe_id']} for {data['source_id']}: "
                f"{data['status']}"
            )
        elif args.command == "health":
            data = catalog.health(
                args.source_id,
                max_age_hours=args.max_age_hours,
                as_of=args.as_of,
            )
            summary = _health_table(data)
        else:  # pragma: no cover - argparse enforces command choices
            raise CatalogError(f"unsupported command: {args.command}")
        _emit(data, json_mode=json_mode, output=output, human_summary=summary)
        return 0
    except (CatalogError, OSError, json.JSONDecodeError) as error:
        if json_mode:
            print(json.dumps({"status": "error", "error": str(error)}))
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
