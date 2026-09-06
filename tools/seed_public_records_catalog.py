#!/usr/bin/env python3
"""Bootstrap the public-records catalog from tracked manifests and reviews.

The bootstrap keeps candidate manifests and current access reviews distinct so
adapters can read one central, auditable description of each supported route.

Usage:
    uv run python tools/seed_public_records_catalog.py
    uv run python tools/seed_public_records_catalog.py --audit --json
    uv run python tools/seed_public_records_catalog.py --db /tmp/catalog.db --json
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Iterable, Sequence
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH,
        ManifestValidationError,
        PublicRecordsCatalog,
        canonical_source_id,
        utc_now,
        validate_source_manifest,
    )
    from tools.public_records_census import (
        DEFAULT_CONFIG_PATH as DEFAULT_CENSUS_CONFIG_PATH,
        PublicRecordsCensus,
    )
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH,
        ManifestValidationError,
        PublicRecordsCatalog,
        canonical_source_id,
        utc_now,
        validate_source_manifest,
    )
    from public_records_census import (
        DEFAULT_CONFIG_PATH as DEFAULT_CENSUS_CONFIG_PATH,
        PublicRecordsCensus,
    )

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "public_records_sources.yaml"


def shared_router_operations() -> dict[str, set[str]]:
    """Return the operations exposed by each shared public-record router."""

    try:
        from tools import query_property, query_state_courts
    except ImportError:
        import query_property
        import query_state_courts

    operations: dict[str, set[str]] = {}
    for routes in (
        query_property.LIVE_ROUTES,
        query_state_courts.LIVE_ROUTES,
    ):
        for source_id, source_routes in routes.items():
            operations.setdefault(str(source_id), set()).update(
                str(operation) for operation in source_routes
            )
    return operations


def shared_router_source_ids() -> set[str]:
    """Return source IDs exposed through either shared public-record router."""

    return set(shared_router_operations())


def _external_source_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    source_id = value.strip()
    try:
        canonical = canonical_source_id(source_id)
    except ManifestValidationError:
        return None
    return canonical if canonical == source_id else None


def declared_adapter_source_paths(
    tool_root: Path | str = PROJECT_ROOT / "tools",
) -> dict[str, str]:
    """Find external source IDs declared by public-record query adapters.

    This is a static scan: adapter modules are parsed without importing them,
    so lifecycle auditing does not trigger endpoint clients or module setup.
    ``CATALOG_SOURCE_ID`` names are adapter-family query envelopes rather than
    separately attributable external sources. Published component and tenant
    IDs are also discovered from literal ``source_id=`` declarations.
    """

    root = Path(tool_root)
    source_paths: dict[str, str] = {}
    for path in sorted(root.glob("query_*.py")):
        if path.name in {"query_property.py", "query_state_courts.py"}:
            continue
        source = path.read_text(encoding="utf-8")
        if "public_records_contract" not in source:
            continue
        tree = ast.parse(source, filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                names = [
                    target.id
                    for target in node.targets
                    if isinstance(target, ast.Name)
                ]
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                names = (
                    [node.target.id]
                    if isinstance(node.target, ast.Name)
                    else []
                )
                value = node.value
            else:
                continue
            if (
                not isinstance(value, ast.Constant)
                or not isinstance(value.value, str)
            ):
                continue
            source_id = _external_source_id(value.value)
            if (
                source_id is not None
                and any(
                    name != "CATALOG_SOURCE_ID"
                    and (
                        name == "SOURCE_ID"
                        or name.endswith("_SOURCE_ID")
                    )
                    for name in names
                )
            ):
                try:
                    display_path = path.relative_to(PROJECT_ROOT)
                except ValueError:
                    display_path = path
                source_paths.setdefault(source_id, str(display_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                name = keyword.arg
                if (
                    name is None
                    or name == "catalog_source_id"
                    or not (
                        name == "source_id"
                        or name.endswith("_source_id")
                    )
                    or not isinstance(keyword.value, ast.Constant)
                ):
                    continue
                source_id = _external_source_id(keyword.value.value)
                if source_id is None:
                    continue
                try:
                    display_path = path.relative_to(PROJECT_ROOT)
                except ValueError:
                    display_path = path
                source_paths.setdefault(source_id, str(display_path))
    return source_paths


def _normalize_census_associations(
    source: Mapping[str, Any],
) -> list[dict[str, Any]]:
    raw_associations = source.get("census_associations")
    if raw_associations is None:
        return []
    if not isinstance(raw_associations, Sequence) or isinstance(
        raw_associations, (str, bytes)
    ):
        raise ValueError(
            f"{source.get('source_id', '<unknown>')}.census_associations "
            "must be a list"
        )

    source_id = str(source.get("source_id") or "<unknown>")
    source_domain = source.get("domain")
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, raw in enumerate(raw_associations):
        field = f"{source_id}.census_associations[{index}]"
        if not isinstance(raw, Mapping):
            raise ValueError(f"{field} must be a mapping")

        geoid = raw.get("jurisdiction_geoid")
        if (
            not isinstance(geoid, str)
            or not geoid.strip()
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", geoid.strip())
        ):
            raise ValueError(
                f"{field}.jurisdiction_geoid must be a stable string"
            )
        geoid = geoid.strip()

        domain = raw.get("domain", source_domain)
        if source_domain == "mixed" and "domain" not in raw:
            raise ValueError(f"{field}.domain is required for mixed sources")
        if domain not in {"property", "court"}:
            raise ValueError(f"{field}.domain must be property or court")
        if source_domain not in {domain, "mixed"}:
            raise ValueError(
                f"{field}.domain does not match source domain {source_domain!r}"
            )

        role = raw.get("role")
        if not isinstance(role, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]*", role
        ):
            raise ValueError(f"{field}.role must use lowercase snake_case")

        coverage = raw.get("coverage", {})
        if not isinstance(coverage, Mapping):
            raise ValueError(f"{field}.coverage must be a mapping")
        coverage_gaps = raw.get("coverage_gaps", [])
        if not isinstance(coverage_gaps, Sequence) or isinstance(
            coverage_gaps, (str, bytes)
        ):
            raise ValueError(f"{field}.coverage_gaps must be a list")
        evidence = raw.get("evidence", [])
        if not isinstance(evidence, Sequence) or isinstance(
            evidence, (str, bytes)
        ):
            raise ValueError(f"{field}.evidence must be a list")
        if any(not isinstance(item, Mapping) for item in evidence):
            raise ValueError(f"{field}.evidence must contain mappings")

        notes = raw.get("notes")
        if notes is not None and not isinstance(notes, str):
            raise ValueError(f"{field}.notes must be a string")
        official_url = raw.get("official_url")
        if official_url is not None and (
            not isinstance(official_url, str) or not official_url.strip()
        ):
            raise ValueError(f"{field}.official_url must be a non-empty string")

        key = (geoid, str(domain), role)
        if key in seen:
            raise ValueError(
                f"{source_id}.census_associations contains duplicate target "
                f"{geoid}/{domain}/{role}"
            )
        seen.add(key)
        normalized.append(
            {
                "jurisdiction_geoid": geoid,
                "domain": str(domain),
                "role": role,
                "official_url": (
                    official_url.strip()
                    if isinstance(official_url, str)
                    else None
                ),
                "coverage": dict(coverage),
                "coverage_gaps": list(coverage_gaps),
                "notes": notes,
                "evidence": [dict(item) for item in evidence],
            }
        )

    return sorted(
        normalized,
        key=lambda item: (
            item["jurisdiction_geoid"],
            item["domain"],
            item["role"],
        ),
    )


@lru_cache(maxsize=4)
def _cached_config_yaml(
    _path: Path, text: str, loader: Callable[[str], Any]
) -> Any:
    """Cache only parsing, keyed by file contents and the current YAML loader.

    Reading the file on every call detects edits even when its size and mtime
    are unchanged. The small entry bound limits retention of custom catalogs;
    the loader key also isolates callers that replace the parser in tests.
    """
    return loader(text)


def _load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    # Callers may alter nested source manifests. Never expose cached objects,
    # and keep validation/normalization outside the cache so it always runs.
    data = deepcopy(_cached_config_yaml(path.resolve(), text, yaml.safe_load))
    if not isinstance(data, Mapping):
        raise ValueError("public-record source config must be a mapping")
    if data.get("schema_version") != 1:
        raise ValueError("unsupported public-record source config schema")
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("public-record source config requires a non-empty sources list")
    source_ids: list[str] = []
    normalized_sources: list[dict[str, Any]] = []
    for index, source in enumerate(sources):
        if not isinstance(source, Mapping):
            raise ValueError(
                f"public-record source config entry {index} must be a mapping"
            )
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError(
                f"public-record source config entry {index} requires source_id"
            )
        review = source.get("access_review")
        if review is not None:
            if not isinstance(review, Mapping):
                raise ValueError(
                    f"{source_id}.access_review must be a mapping"
                )
            limits = review.get("limits", {})
            if not isinstance(limits, Mapping):
                raise ValueError(
                    f"{source_id}.access_review.limits must be a mapping"
                )
        source_ids.append(source_id.strip())
        normalized_source = dict(source)
        if "census_associations" in source:
            normalized_source["census_associations"] = (
                _normalize_census_associations(source)
            )
        normalized_sources.append(normalized_source)

    duplicate_ids = sorted(
        {
            source_id
            for source_id in source_ids
            if source_ids.count(source_id) > 1
        }
    )
    if duplicate_ids:
        raise ValueError(
            "public-record source config has duplicate source_id values: "
            + ", ".join(duplicate_ids)
        )

    known_ids = set(source_ids)
    missing_references: list[str] = []
    self_complements: list[str] = []
    for source in sources:
        source_id = str(source["source_id"]).strip()
        identity_source_id = source.get("record_identity_source_id")
        if identity_source_id is not None:
            if (
                not isinstance(identity_source_id, str)
                or identity_source_id.strip() not in known_ids
            ):
                missing_references.append(
                    f"{source_id}.record_identity_source_id="
                    f"{identity_source_id!r}"
                )
        complements = source.get("complementary_source_ids") or []
        if not isinstance(complements, list):
            raise ValueError(
                f"{source_id}.complementary_source_ids must be a list"
            )
        for complement in complements:
            if not isinstance(complement, str) or complement.strip() not in known_ids:
                missing_references.append(
                    f"{source_id}.complementary_source_ids={complement!r}"
                )
                continue
            if complement.strip() == source_id:
                self_complements.append(source_id)
    if missing_references:
        raise ValueError(
            "public-record source config references unknown source IDs: "
            + "; ".join(sorted(missing_references))
        )
    if self_complements:
        raise ValueError(
            "public-record sources cannot complement themselves: "
            + ", ".join(sorted(set(self_complements)))
        )
    normalized_config = dict(data)
    normalized_config["sources"] = normalized_sources
    return normalized_config


def _target_index(
    db_path: Path | str,
) -> dict[tuple[str, str, str], int]:
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(
            """
            SELECT t.census_target_id, j.geoid, t.domain, t.role
            FROM source_census_targets t
            JOIN jurisdictions j USING(jurisdiction_id)
            WHERE j.country_code='US'
            """
        ).fetchall()
    finally:
        db.close()
    return {
        (str(row["geoid"]), str(row["domain"]), str(row["role"])): int(
            row["census_target_id"]
        )
        for row in rows
    }


def _association_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _validate_declared_targets(
    sources: Sequence[Mapping[str, Any]],
    target_index: Mapping[tuple[str, str, str], int],
) -> None:
    missing: list[str] = []
    for source in sources:
        source_id = str(source["source_id"])
        for association in source.get("census_associations", []):
            key = (
                str(association["jurisdiction_geoid"]),
                str(association["domain"]),
                str(association["role"]),
            )
            if key not in target_index:
                missing.append(f"{source_id}:{'/'.join(key)}")
    if missing:
        raise ValueError(
            "census association targets do not exist: "
            + ", ".join(sorted(missing))
        )


def _sync_source_census_associations(
    *,
    db_path: Path | str,
    source_id: str,
    associations: Sequence[Mapping[str, Any]],
    target_index: Mapping[tuple[str, str, str], int],
    added_by: str,
) -> dict[str, int]:
    counts = {"created": 0, "updated": 0, "unchanged": 0}
    if not associations:
        return counts

    db = sqlite3.connect(str(db_path), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    try:
        db.execute("BEGIN IMMEDIATE")
        source = db.execute(
            "SELECT domain, official_url FROM sources WHERE source_id=?",
            (source_id,),
        ).fetchone()
        if source is None:
            raise ValueError(f"unknown catalog source: {source_id}")

        for association in associations:
            key = (
                str(association["jurisdiction_geoid"]),
                str(association["domain"]),
                str(association["role"]),
            )
            target_id = target_index.get(key)
            if target_id is None:
                geoid, domain, role = key
                raise ValueError(
                    "census association target does not exist: "
                    f"{geoid}/{domain}/{role}"
                )
            target_row = db.execute(
                """
                SELECT status FROM source_census_targets
                WHERE census_target_id=?
                """,
                (target_id,),
            ).fetchone()
            if target_row is None:
                raise ValueError(f"unknown census target: {target_id}")
            target_status = str(target_row["status"])

            source_domain = str(source["domain"])
            if source_domain not in {key[1], "mixed"}:
                raise ValueError(
                    f"source {source_id} domain does not match census target"
                )

            official_url = (
                association.get("official_url") or source["official_url"]
            )
            coverage = dict(association.get("coverage") or {})
            coverage_gaps = list(association.get("coverage_gaps") or [])
            notes = association.get("notes")
            evidence = [
                dict(item) for item in association.get("evidence") or []
            ]
            existing = db.execute(
                """
                SELECT * FROM source_census_target_sources
                WHERE census_target_id=? AND source_id=?
                """,
                (target_id, source_id),
            ).fetchone()
            matches = bool(
                existing
                and existing["official_url"] == official_url
                and json.loads(existing["coverage_json"]) == coverage
                and json.loads(existing["coverage_gaps_json"])
                == coverage_gaps
                and existing["notes"] == notes
                and json.loads(existing["evidence_json"]) == evidence
            )
            if matches:
                counts["unchanged"] += 1
                continue

            now = utc_now()
            action = "created" if existing is None else "updated"
            if existing is None:
                db.execute(
                    """
                    INSERT INTO source_census_target_sources(
                        census_target_id, source_id, official_url,
                        coverage_json, coverage_gaps_json, notes,
                        evidence_json, added_by, added_at, updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        target_id,
                        source_id,
                        official_url,
                        _association_json(coverage),
                        _association_json(coverage_gaps),
                        notes,
                        _association_json(evidence),
                        added_by,
                        now,
                        now,
                    ),
                )
            else:
                db.execute(
                    """
                    UPDATE source_census_target_sources
                    SET official_url=?, coverage_json=?,
                        coverage_gaps_json=?, notes=?, evidence_json=?,
                        added_by=?, updated_at=?
                    WHERE census_target_id=? AND source_id=?
                    """,
                    (
                        official_url,
                        _association_json(coverage),
                        _association_json(coverage_gaps),
                        notes,
                        _association_json(evidence),
                        added_by,
                        now,
                        target_id,
                        source_id,
                    ),
                )
            db.execute(
                """
                UPDATE source_census_targets SET updated_at=?
                WHERE census_target_id=?
                """,
                (now, target_id),
            )
            db.execute(
                """
                INSERT INTO source_census_events(
                    census_target_id, event_type, actor, from_status,
                    to_status, details_json, recorded_at
                ) VALUES(?,?,?,?,?,?,?)
                """,
                (
                    target_id,
                    "source_associated",
                    added_by,
                    target_status,
                    target_status,
                    _association_json(
                        {
                            "action": action,
                            "declaration": "tracked_source_config",
                            "source_id": source_id,
                            "coverage": coverage,
                            "coverage_gaps": coverage_gaps,
                            "notes": notes,
                        }
                    ),
                    now,
                ),
            )
            counts[action] += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return counts


def _same_review(latest: Mapping[str, Any] | None, review: Mapping[str, Any]) -> bool:
    if not latest:
        return False
    latest_limits = latest.get("limits", {})
    return (
        latest.get("access_class") == str(review["access_class"]).upper()
        and latest.get("automation_disposition")
        == review["automation_disposition"]
        and latest.get("review_basis") == review["review_basis"]
        and latest_limits == review.get("limits", {})
    )


def _manifest_sha256(source: Mapping[str, Any]) -> str:
    manifest = dict(source)
    manifest.pop("access_review", None)
    normalized = validate_source_manifest(manifest)
    payload = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _association_label(key: tuple[str, str, str, str]) -> str:
    source_id, geoid, domain, role = key
    return f"{source_id}:{geoid}/{domain}/{role}"


def audit_catalog(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    config_path: Path | str = DEFAULT_CONFIG_PATH,
    adapter_source_ids: Iterable[str] | None = None,
    adapter_operations: Mapping[str, Iterable[str]] | None = None,
    declared_adapter_sources: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Compare adapters and tracked declarations with live catalog state."""

    config = _load_config(Path(config_path))
    sources = {
        str(source["source_id"]): source for source in config["sources"]
    }
    tracked_source_ids = set(sources)
    operation_audit_enabled = (
        adapter_operations is not None or adapter_source_ids is None
    )
    routed_operations = {
        str(source_id): {
            str(operation) for operation in operations
        }
        for source_id, operations in (
            shared_router_operations()
            if adapter_operations is None
            else adapter_operations
        ).items()
    } if operation_audit_enabled else {}
    routed_source_ids = {
        str(source_id)
        for source_id in (
            routed_operations
            if adapter_source_ids is None
            else adapter_source_ids
        )
    }
    declared_adapter_paths = {
        str(source_id): str(path)
        for source_id, path in (
            declared_adapter_source_paths()
            if declared_adapter_sources is None
            else declared_adapter_sources
        ).items()
    }
    declared_adapter_ids = set(declared_adapter_paths)
    adapter_declared_source_ids = routed_source_ids | declared_adapter_ids
    expected_manifest_hashes = {
        source_id: _manifest_sha256(source)
        for source_id, source in sources.items()
    }
    expected_review_ids = {
        source_id
        for source_id, source in sources.items()
        if source.get("access_review") is not None
    }
    declared_shared_operations: dict[str, set[str]] = {}
    for source_id, source in sources.items():
        for capability in source.get("capabilities", []):
            if not isinstance(capability, Mapping):
                continue
            details = capability.get("details")
            if not isinstance(details, Mapping):
                continue
            operations = details.get("shared_operations")
            if operations is None:
                continue
            if not isinstance(operations, Sequence) or isinstance(
                operations,
                (str, bytes),
            ):
                raise ValueError(
                    f"{source_id} shared_operations must be a list"
                )
            if any(
                not isinstance(operation, str) or not operation.strip()
                for operation in operations
            ):
                raise ValueError(
                    f"{source_id} shared_operations must contain names"
                )
            declared_shared_operations.setdefault(source_id, set()).update(
                operation.strip() for operation in operations
            )
    expected_associations: dict[
        tuple[str, str, str, str], dict[str, Any]
    ] = {}
    for source_id, source in sources.items():
        for association in source.get("census_associations", []):
            key = (
                source_id,
                str(association["jurisdiction_geoid"]),
                str(association["domain"]),
                str(association["role"]),
            )
            expected_associations[key] = {
                "official_url": (
                    association.get("official_url")
                    or source.get("official_url")
                ),
                "coverage": dict(association.get("coverage") or {}),
                "coverage_gaps": list(
                    association.get("coverage_gaps") or []
                ),
                "notes": association.get("notes"),
                "evidence": [
                    dict(item)
                    for item in association.get("evidence") or []
                ],
            }

    catalog_path = Path(db_path)
    schema_present = False
    catalog_source_ids: set[str] = set()
    reviewed_source_ids: set[str] = set()
    current_manifest_hashes: dict[str, str | None] = {}
    live_associations: dict[
        tuple[str, str, str, str], dict[str, Any]
    ] = {}
    if catalog_path.exists():
        db = sqlite3.connect(str(catalog_path))
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        try:
            table_names = {
                str(row["name"])
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            required_tables = {
                "sources",
                "source_manifests",
                "access_reviews",
                "jurisdictions",
                "source_census_targets",
                "source_census_target_sources",
            }
            schema_present = required_tables <= table_names
            if schema_present:
                source_rows = db.execute(
                    """
                    SELECT s.source_id, m.manifest_sha256
                    FROM sources s
                    LEFT JOIN source_manifests m
                      ON m.manifest_id=s.current_manifest_id
                    """
                ).fetchall()
                catalog_source_ids = {
                    str(row["source_id"]) for row in source_rows
                }
                current_manifest_hashes = {
                    str(row["source_id"]): (
                        str(row["manifest_sha256"])
                        if row["manifest_sha256"] is not None
                        else None
                    )
                    for row in source_rows
                }
                reviewed_source_ids = {
                    str(row["source_id"])
                    for row in db.execute(
                        "SELECT DISTINCT source_id FROM access_reviews"
                    ).fetchall()
                }
                for row in db.execute(
                    """
                    SELECT a.source_id, j.geoid, t.domain, t.role,
                           a.official_url, a.coverage_json,
                           a.coverage_gaps_json, a.notes, a.evidence_json
                    FROM source_census_target_sources a
                    JOIN source_census_targets t
                      USING(census_target_id)
                    JOIN jurisdictions j USING(jurisdiction_id)
                    WHERE j.geoid IS NOT NULL
                    """
                ).fetchall():
                    key = (
                        str(row["source_id"]),
                        str(row["geoid"]),
                        str(row["domain"]),
                        str(row["role"]),
                    )
                    live_associations[key] = {
                        "official_url": row["official_url"],
                        "coverage": json.loads(row["coverage_json"]),
                        "coverage_gaps": json.loads(
                            row["coverage_gaps_json"]
                        ),
                        "notes": row["notes"],
                        "evidence": json.loads(row["evidence_json"]),
                    }
        finally:
            db.close()

    tracked_missing_catalog = tracked_source_ids - catalog_source_ids
    adapter_missing_manifest = routed_source_ids - tracked_source_ids
    adapter_missing_catalog = routed_source_ids - catalog_source_ids
    declared_adapters_missing_manifest = (
        declared_adapter_ids - tracked_source_ids
    )
    declared_adapters_missing_catalog = (
        declared_adapter_ids - catalog_source_ids
    )
    adapter_declared_missing_manifest = (
        adapter_declared_source_ids - tracked_source_ids
    )
    adapter_declared_missing_catalog = (
        adapter_declared_source_ids - catalog_source_ids
    )
    outdated_manifests = {
        source_id
        for source_id in tracked_source_ids & catalog_source_ids
        if current_manifest_hashes.get(source_id)
        != expected_manifest_hashes[source_id]
    }
    missing_reviews = expected_review_ids - reviewed_source_ids
    expected_association_keys = set(expected_associations)
    live_association_keys = set(live_associations)
    missing_associations = expected_association_keys - live_association_keys
    outdated_associations = {
        key
        for key in expected_association_keys & live_association_keys
        if expected_associations[key] != live_associations[key]
    }
    shared_operation_mismatches = {
        source_id: {
            "declared": sorted(declared),
            "actual": sorted(routed_operations.get(source_id, set())),
        }
        for source_id, declared in declared_shared_operations.items()
        if operation_audit_enabled
        and declared != routed_operations.get(source_id, set())
    }
    drift_groups = (
        tracked_missing_catalog,
        adapter_missing_manifest,
        adapter_missing_catalog,
        declared_adapters_missing_manifest,
        declared_adapters_missing_catalog,
        outdated_manifests,
        missing_reviews,
        missing_associations,
        outdated_associations,
        shared_operation_mismatches,
    )

    return {
        "status": "drift" if any(drift_groups) else "ok",
        "db_path": str(catalog_path),
        "config_path": str(Path(config_path)),
        "db_exists": catalog_path.exists(),
        "schema_present": schema_present,
        "counts": {
            "tracked_sources": len(tracked_source_ids),
            "shared_adapter_sources": len(routed_source_ids),
            "declared_adapter_sources": len(declared_adapter_ids),
            "adapter_declared_sources": len(adapter_declared_source_ids),
            "declared_shared_operation_sources": len(
                declared_shared_operations
            ),
            "live_catalog_sources": len(catalog_source_ids),
            "declared_census_associations": len(
                expected_association_keys
            ),
            "live_census_associations": len(live_association_keys),
        },
        "manifest_sources_missing_live_catalog": sorted(
            tracked_missing_catalog
        ),
        "shared_adapter_sources_missing_manifest": sorted(
            adapter_missing_manifest
        ),
        "shared_adapter_sources_missing_live_catalog": sorted(
            adapter_missing_catalog
        ),
        "shared_adapter_operation_mismatches": [
            {
                "source_id": source_id,
                **shared_operation_mismatches[source_id],
            }
            for source_id in sorted(shared_operation_mismatches)
        ],
        "declared_adapter_sources_missing_manifest": [
            {
                "source_id": source_id,
                "tool": declared_adapter_paths[source_id],
            }
            for source_id in sorted(declared_adapters_missing_manifest)
        ],
        "declared_adapter_sources_missing_live_catalog": [
            {
                "source_id": source_id,
                "tool": declared_adapter_paths[source_id],
            }
            for source_id in sorted(declared_adapters_missing_catalog)
        ],
        "adapter_declared_sources_missing_manifest": sorted(
            adapter_declared_missing_manifest
        ),
        "adapter_declared_sources_missing_live_catalog": sorted(
            adapter_declared_missing_catalog
        ),
        "outdated_live_manifests": sorted(outdated_manifests),
        "declared_reviews_missing_live_catalog": sorted(missing_reviews),
        "declared_associations_missing_live_census": sorted(
            _association_label(key) for key in missing_associations
        ),
        "outdated_live_census_associations": sorted(
            _association_label(key) for key in outdated_associations
        ),
        "live_catalog_sources_not_in_manifest": sorted(
            catalog_source_ids - tracked_source_ids
        ),
        "live_census_associations_not_declared": sorted(
            _association_label(key)
            for key in live_association_keys - expected_association_keys
        ),
    }


def ensure_catalog_source(
    source_id: str,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    config_path: Path | str = DEFAULT_CONFIG_PATH,
) -> PublicRecordsCatalog:
    """Return a catalog containing ``source_id`` without rewriting current state.

    Query adapters use this lightweight bootstrap path.  An already registered
    source is left untouched, including any access review recorded after the
    tracked configuration was written.  The explicit ``seed_catalog`` command
    remains the synchronization path for the complete tracked catalog.
    """
    catalog = PublicRecordsCatalog(db_path)
    if source_id in {row["source_id"] for row in catalog.list_sources()}:
        return catalog

    config = _load_config(Path(config_path))
    source_entry = next(
        (
            entry
            for entry in config["sources"]
            if isinstance(entry, Mapping) and entry.get("source_id") == source_id
        ),
        None,
    )
    if source_entry is None:
        raise ValueError(
            f"source {source_id!r} is not present in {Path(config_path)}"
        )

    manifest = dict(source_entry)
    review = manifest.pop("access_review", None)
    submitted_by = str(config.get("submitted_by") or "public-records-bootstrap")
    catalog.register_manifest(
        manifest,
        submitted_by=submitted_by,
        submitted_at=utc_now(),
    )
    if review is not None:
        if not isinstance(review, Mapping):
            raise ValueError(f"{source_id} access_review must be a mapping")
        catalog.evaluate_access(
            source_id,
            access_class=str(review["access_class"]),
            automation_disposition=str(review["automation_disposition"]),
            reviewed_by=str(review["reviewed_by"]),
            review_basis=str(review["review_basis"]),
            limits=review.get("limits", {}),
            notes=review.get("notes"),
        )
    return catalog


def seed_catalog(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    config_path: Path | str = DEFAULT_CONFIG_PATH,
    census_config_path: Path | str = DEFAULT_CENSUS_CONFIG_PATH,
) -> dict[str, Any]:
    """Seed census targets, manifests, reviews, and tracked associations."""
    config = _load_config(Path(config_path))
    census_seed = PublicRecordsCensus(db_path).seed(census_config_path)
    catalog = PublicRecordsCatalog(db_path)
    targets = _target_index(db_path)
    _validate_declared_targets(config["sources"], targets)
    submitted_by = str(config.get("submitted_by") or "public-records-bootstrap")
    counts = {
        "sources_seen": 0,
        "manifests_registered": 0,
        "manifests_unchanged": 0,
        "access_reviews_recorded": 0,
        "access_reviews_unchanged": 0,
        "census_targets_created": census_seed["targets_created"],
        "census_associations_seen": 0,
        "census_associations_created": 0,
        "census_associations_updated": 0,
        "census_associations_unchanged": 0,
    }

    for source_entry in config["sources"]:
        if not isinstance(source_entry, Mapping):
            raise ValueError("each source config entry must be a mapping")
        manifest = dict(source_entry)
        review = manifest.pop("access_review", None)
        counts["sources_seen"] += 1

        before = {row["source_id"] for row in catalog.list_sources()}
        registration = catalog.register_manifest(
            manifest,
            submitted_by=submitted_by,
            submitted_at=utc_now(),
        )
        if registration["source_id"] in before:
            counts["manifests_unchanged"] += 1
        else:
            counts["manifests_registered"] += 1

        associations = manifest.get("census_associations", [])
        association_counts = _sync_source_census_associations(
            db_path=db_path,
            source_id=str(registration["source_id"]),
            associations=associations,
            target_index=targets,
            added_by=submitted_by,
        )
        counts["census_associations_seen"] += len(associations)
        for status, count in association_counts.items():
            counts[f"census_associations_{status}"] += count

        if review is None:
            continue
        if not isinstance(review, Mapping):
            raise ValueError(
                f"{registration['source_id']} access_review must be a mapping"
            )
        detail = catalog.show_source(registration["source_id"])
        latest = detail.get("latest_access_review")
        if _same_review(latest, review):
            counts["access_reviews_unchanged"] += 1
            continue
        catalog.evaluate_access(
            registration["source_id"],
            access_class=str(review["access_class"]),
            automation_disposition=str(review["automation_disposition"]),
            reviewed_by=str(review["reviewed_by"]),
            review_basis=str(review["review_basis"]),
            limits=review.get("limits", {}),
            notes=review.get("notes"),
        )
        counts["access_reviews_recorded"] += 1

    counts["db_path"] = str(Path(db_path))
    counts["config_path"] = str(Path(config_path))
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed the public-record source catalog")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Report adapter, manifest, catalog, and census drift without seeding",
    )
    parser.add_argument(
        "--census-config",
        default=str(DEFAULT_CENSUS_CONFIG_PATH),
    )
    add_output_args(parser)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.audit:
        result = audit_catalog(
            db_path=args.db,
            config_path=args.config,
        )
        summary = (
            "catalog audit: "
            f"{result['status']}; "
            f"{result['counts']['adapter_declared_sources']} "
            "adapter-declared sources"
        )
    else:
        result = seed_catalog(
            db_path=args.db,
            config_path=args.config,
            census_config_path=args.census_config,
        )
        summary = f"catalog seed: {result['sources_seen']} sources"
    if write_output(result, args, summary=summary):
        return
    if args.json_out:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.audit:
        print(
            f"Catalog audit: {result['status']}; "
            f"{result['counts']['tracked_sources']} tracked; "
            f"{result['counts']['adapter_declared_sources']} "
            "adapter-declared sources; "
            f"{result['counts']['live_catalog_sources']} live"
        )
    else:
        print(
            f"Catalog seed: {result['sources_seen']} sources; "
            f"{result['manifests_registered']} new manifests; "
            f"{result['access_reviews_recorded']} new access reviews"
        )


if __name__ == "__main__":
    main()
