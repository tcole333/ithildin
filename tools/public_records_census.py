#!/usr/bin/env python3
"""Agent-scale source-census queue for property and state/local court records.

Usage:
    uv run python tools/public_records_census.py seed
    uv run python tools/public_records_census.py stats --json
    uv run python tools/public_records_census.py claim --by agent-name
    uv run python tools/public_records_census.py score 17 --benefit 80 \
        --feasibility 65 --risk 20 --basis '{"active_profile_addresses": 2}'
    uv run python tools/public_records_census.py submit 17 manifest.yaml \
        --by agent-name
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH,
        PublicRecordsCatalog,
        utc_now,
    )
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH,
        PublicRecordsCatalog,
        utc_now,
    )

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "public_records_census.yaml"
CENSUS_STATUSES = frozenset(
    {
        "pending",
        "in_progress",
        "source_identified",
        "manifest_submitted",
        "manual_only",
        "not_found",
        "blocked",
    }
)
RESOLUTION_STATUSES = CENSUS_STATUSES - {"pending", "in_progress"}
COVERAGE_STATUSES = frozenset(
    {"unassessed", "partial", "comprehensive", "not_applicable"}
)
COMPACT_TARGET_FIELDS = (
    "census_target_id",
    "jurisdiction_id",
    "jurisdiction_name",
    "geoid",
    "subdivision_code",
    "domain",
    "role",
    "status",
    "coverage_status",
    "benefit_score",
    "feasibility_score",
    "risk_score",
    "priority_profile_name",
    "priority_as_of",
    "priority_run_id",
    "priority_input_fingerprint",
    "source_count",
    "source_ids",
    "candidate_source_count",
    "candidate_source_ids",
    "claimed_by",
)
CANDIDATE_SOURCE_EXISTS_SQL = """
EXISTS(
    SELECT 1
    FROM json_each(
        COALESCE(
            json_extract(
                t.priority_basis_json,
                '$.dimensions.feasibility.candidate_sources'
            ),
            '[]'
        )
    ) AS candidate
    WHERE candidate.type='object'
      AND NULLIF(
        TRIM(json_extract(candidate.value, '$.source_id')),
        ''
      ) IS NOT NULL
)
""".strip()


class CensusError(RuntimeError):
    """Raised when a census transition or input is invalid."""


def _json_value(raw: str | None, *, default: Any) -> Any:
    if raw is None:
        return default
    if raw.startswith("@"):
        raw = Path(raw[1:]).read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise CensusError(f"invalid JSON: {error}") from error


def _json_dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _candidate_source_ids(priority_basis: Any) -> list[str]:
    if not isinstance(priority_basis, Mapping):
        return []
    dimensions = priority_basis.get("dimensions")
    if not isinstance(dimensions, Mapping):
        return []
    feasibility = dimensions.get("feasibility")
    if not isinstance(feasibility, Mapping):
        return []
    candidates = feasibility.get("candidate_sources")
    if not isinstance(candidates, Sequence) or isinstance(
        candidates,
        (str, bytes),
    ):
        return []
    source_ids: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        source_id = candidate.get("source_id")
        if (
            isinstance(source_id, str)
            and source_id
            and source_id not in source_ids
        ):
            source_ids.append(source_id)
    return source_ids


def _load_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise CensusError("census config must be a mapping")
    if data.get("schema_version") != 1:
        raise CensusError("unsupported census config schema")
    jurisdictions = data.get("jurisdictions")
    roles = data.get("roles")
    if not isinstance(jurisdictions, Mapping) or not jurisdictions:
        raise CensusError("census config requires jurisdictions")
    if not isinstance(roles, Mapping) or not roles:
        raise CensusError("census config requires roles")

    base_geoids: set[str] = set()
    for state_code, raw in jurisdictions.items():
        if not isinstance(raw, Mapping):
            raise CensusError(f"jurisdiction {state_code} must be a mapping")
        geoid = str(raw.get("geoid") or "").strip()
        if not geoid:
            raise CensusError(f"jurisdiction {state_code} requires geoid")
        if geoid in base_geoids:
            raise CensusError(f"duplicate census jurisdiction geoid: {geoid}")
        base_geoids.add(geoid)

    additional_jurisdictions = data.get("additional_jurisdictions", [])
    if not isinstance(additional_jurisdictions, Sequence) or isinstance(
        additional_jurisdictions,
        (str, bytes),
    ):
        raise CensusError("additional_jurisdictions must be a list")
    additional_geoids: set[str] = set()
    additional_ids: set[str] = set()
    for index, raw in enumerate(additional_jurisdictions):
        field = f"additional_jurisdictions[{index}]"
        if not isinstance(raw, Mapping):
            raise CensusError(f"{field} must be a mapping")
        required = (
            "jurisdiction_id",
            "name",
            "kind",
            "country_code",
            "subdivision_code",
            "geoid",
            "parent_geoid",
        )
        values = {
            name: str(raw.get(name) or "").strip() for name in required
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise CensusError(
                f"{field} requires {', '.join(sorted(missing))}"
            )
        if values["country_code"] != "US":
            raise CensusError(f"{field}.country_code must be US")
        if values["geoid"] in base_geoids | additional_geoids:
            raise CensusError(
                f"duplicate census jurisdiction geoid: {values['geoid']}"
            )
        if values["jurisdiction_id"] in additional_ids:
            raise CensusError(
                "duplicate additional jurisdiction_id: "
                f"{values['jurisdiction_id']}"
            )
        additional_geoids.add(values["geoid"])
        additional_ids.add(values["jurisdiction_id"])

    known_geoids = base_geoids | additional_geoids
    for index, raw in enumerate(additional_jurisdictions):
        parent_geoid = str(raw["parent_geoid"]).strip()
        if parent_geoid not in known_geoids:
            raise CensusError(
                "additional_jurisdictions"
                f"[{index}].parent_geoid is not declared: {parent_geoid}"
            )

    additional_targets = data.get("additional_targets", [])
    if not isinstance(additional_targets, Sequence) or isinstance(
        additional_targets,
        (str, bytes),
    ):
        raise CensusError("additional_targets must be a list")
    target_keys: set[tuple[str, str, str]] = set()
    for index, raw in enumerate(additional_targets):
        field = f"additional_targets[{index}]"
        if not isinstance(raw, Mapping):
            raise CensusError(f"{field} must be a mapping")
        geoid = str(raw.get("jurisdiction_geoid") or "").strip()
        domain = str(raw.get("domain") or "").strip()
        role = str(raw.get("role") or "").strip()
        description = str(raw.get("description") or "").strip()
        if geoid not in known_geoids:
            raise CensusError(
                f"{field}.jurisdiction_geoid is not declared: {geoid}"
            )
        if domain not in {"property", "court"}:
            raise CensusError(f"{field}.domain must be property or court")
        if not role:
            raise CensusError(f"{field}.role is required")
        if not description:
            raise CensusError(f"{field}.description is required")
        key = (geoid, domain, role)
        if key in target_keys:
            raise CensusError(
                "duplicate additional census target: "
                f"{'/'.join(key)}"
            )
        if (
            geoid in base_geoids
            and isinstance(roles.get(domain), Mapping)
            and role in roles[domain]
        ):
            raise CensusError(
                "additional census target duplicates a nationwide target: "
                f"{'/'.join(key)}"
            )
        target_keys.add(key)

    normalized = dict(data)
    normalized["additional_jurisdictions"] = list(
        additional_jurisdictions
    )
    normalized["additional_targets"] = list(additional_targets)
    return normalized


class PublicRecordsCensus:
    """Queue and audit trail stored inside the public-records catalog."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        PublicRecordsCatalog(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.db_path), timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    @staticmethod
    def _event(
        db: sqlite3.Connection,
        target_id: int,
        *,
        event_type: str,
        actor: str,
        from_status: str | None,
        to_status: str | None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        db.execute(
            """
            INSERT INTO source_census_events(
                census_target_id, event_type, actor, from_status, to_status,
                details_json, recorded_at
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                target_id,
                event_type,
                actor,
                from_status,
                to_status,
                _json_dump(dict(details or {})),
                utc_now(),
            ),
        )

    @staticmethod
    def _jurisdiction_by_geoid(
        db: sqlite3.Connection,
        geoid: str,
    ) -> sqlite3.Row | None:
        return db.execute(
            """
            SELECT * FROM jurisdictions
            WHERE country_code='US' AND geoid=?
            """,
            (geoid,),
        ).fetchone()

    def seed(
        self,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
    ) -> dict[str, Any]:
        """Seed all state-equivalent jurisdictions and role-specific targets."""
        config = _load_config(Path(config_path))
        now = utc_now()
        geography_source = str(config["official_geography_source"])
        country = dict(config["country"])
        counts = {
            "jurisdictions_seen": 0,
            "jurisdictions_created": 0,
            "targets_seen": 0,
            "targets_created": 0,
        }

        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            country_row = self._jurisdiction_by_geoid(db, str(country["geoid"]))
            country_id = (
                str(country_row["jurisdiction_id"])
                if country_row
                else str(country["jurisdiction_id"])
            )
            if country_row is None:
                db.execute(
                    """
                    INSERT INTO jurisdictions(
                        jurisdiction_id, name, kind, country_code,
                        subdivision_code, geoid, parent_jurisdiction_id,
                        official_url, metadata_json, created_at, updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        country_id,
                        str(country["name"]),
                        "country",
                        "US",
                        str(country.get("subdivision_code") or "US"),
                        str(country["geoid"]),
                        None,
                        geography_source,
                        _json_dump({"census_seed": True}),
                        now,
                        now,
                    ),
                )
            else:
                db.execute(
                    """
                    UPDATE jurisdictions
                    SET name=?, kind='country', subdivision_code=?,
                        official_url=?, metadata_json=?, updated_at=?
                    WHERE jurisdiction_id=?
                    """,
                    (
                        str(country["name"]),
                        str(country.get("subdivision_code") or "US"),
                        geography_source,
                        _json_dump({"census_seed": True}),
                        now,
                        country_id,
                    ),
                )

            for state_code, raw in config["jurisdictions"].items():
                if not isinstance(raw, Mapping):
                    raise CensusError(f"jurisdiction {state_code} must be a mapping")
                state_code = str(state_code).upper()
                geoid = str(raw["geoid"])
                counts["jurisdictions_seen"] += 1
                existing = self._jurisdiction_by_geoid(db, geoid)
                jurisdiction_id = (
                    str(existing["jurisdiction_id"])
                    if existing
                    else f"us-state-{state_code.lower()}"
                )
                metadata = {
                    "census_seed": True,
                    "state_abbreviation": state_code,
                    "state_fips": geoid,
                }
                if existing is None:
                    db.execute(
                        """
                        INSERT INTO jurisdictions(
                            jurisdiction_id, name, kind, country_code,
                            subdivision_code, geoid, parent_jurisdiction_id,
                            official_url, metadata_json, created_at, updated_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            jurisdiction_id,
                            str(raw["name"]),
                            "state_equivalent",
                            "US",
                            state_code,
                            geoid,
                            country_id,
                            geography_source,
                            _json_dump(metadata),
                            now,
                            now,
                        ),
                    )
                    counts["jurisdictions_created"] += 1
                else:
                    db.execute(
                        """
                        UPDATE jurisdictions
                        SET name=?, kind='state_equivalent',
                            subdivision_code=?, parent_jurisdiction_id=?,
                            official_url=?, metadata_json=?, updated_at=?
                        WHERE jurisdiction_id=?
                        """,
                        (
                            str(raw["name"]),
                            state_code,
                            country_id,
                            geography_source,
                            _json_dump(metadata),
                            now,
                            jurisdiction_id,
                        ),
                    )

                for domain, role_map in config["roles"].items():
                    if domain not in {"property", "court"}:
                        raise CensusError(f"unsupported census domain: {domain}")
                    if not isinstance(role_map, Mapping):
                        raise CensusError(f"roles.{domain} must be a mapping")
                    for role, description in role_map.items():
                        counts["targets_seen"] += 1
                        cursor = db.execute(
                            """
                            INSERT OR IGNORE INTO source_census_targets(
                                jurisdiction_id, domain, role, description,
                                created_at, updated_at
                            ) VALUES(?,?,?,?,?,?)
                            """,
                            (
                                jurisdiction_id,
                                domain,
                                str(role),
                                str(description),
                                now,
                                now,
                            ),
                        )
                        if cursor.rowcount:
                            target_id = int(cursor.lastrowid)
                            counts["targets_created"] += 1
                            self._event(
                                db,
                                target_id,
                                event_type="seeded",
                                actor="public-records-census",
                                from_status=None,
                                to_status="pending",
                                details={
                                    "state_code": state_code,
                                    "geoid": geoid,
                                },
                            )

            for raw in config["additional_jurisdictions"]:
                geoid = str(raw["geoid"])
                parent_geoid = str(raw["parent_geoid"])
                parent = self._jurisdiction_by_geoid(db, parent_geoid)
                if parent is None:
                    raise CensusError(
                        "additional jurisdiction parent does not exist: "
                        f"{parent_geoid}"
                    )
                counts["jurisdictions_seen"] += 1
                existing = self._jurisdiction_by_geoid(db, geoid)
                jurisdiction_id = (
                    str(existing["jurisdiction_id"])
                    if existing
                    else str(raw["jurisdiction_id"])
                )
                metadata = {
                    "census_seed": True,
                    "additional_target_jurisdiction": True,
                    "parent_geoid": parent_geoid,
                }
                official_url = str(
                    raw.get("official_url") or geography_source
                )
                if existing is None:
                    db.execute(
                        """
                        INSERT INTO jurisdictions(
                            jurisdiction_id, name, kind, country_code,
                            subdivision_code, geoid,
                            parent_jurisdiction_id, official_url,
                            metadata_json, created_at, updated_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            jurisdiction_id,
                            str(raw["name"]),
                            str(raw["kind"]),
                            str(raw["country_code"]),
                            str(raw["subdivision_code"]),
                            geoid,
                            str(parent["jurisdiction_id"]),
                            official_url,
                            _json_dump(metadata),
                            now,
                            now,
                        ),
                    )
                    counts["jurisdictions_created"] += 1
                else:
                    db.execute(
                        """
                        UPDATE jurisdictions
                        SET name=?, kind=?, country_code=?,
                            subdivision_code=?,
                            parent_jurisdiction_id=?, official_url=?,
                            metadata_json=?, updated_at=?
                        WHERE jurisdiction_id=?
                        """,
                        (
                            str(raw["name"]),
                            str(raw["kind"]),
                            str(raw["country_code"]),
                            str(raw["subdivision_code"]),
                            str(parent["jurisdiction_id"]),
                            official_url,
                            _json_dump(metadata),
                            now,
                            jurisdiction_id,
                        ),
                    )

            for raw in config["additional_targets"]:
                geoid = str(raw["jurisdiction_geoid"])
                jurisdiction = self._jurisdiction_by_geoid(db, geoid)
                if jurisdiction is None:
                    raise CensusError(
                        "additional target jurisdiction does not exist: "
                        f"{geoid}"
                    )
                counts["targets_seen"] += 1
                cursor = db.execute(
                    """
                    INSERT OR IGNORE INTO source_census_targets(
                        jurisdiction_id, domain, role, description,
                        created_at, updated_at
                    ) VALUES(?,?,?,?,?,?)
                    """,
                    (
                        str(jurisdiction["jurisdiction_id"]),
                        str(raw["domain"]),
                        str(raw["role"]),
                        str(raw["description"]),
                        now,
                        now,
                    ),
                )
                if cursor.rowcount:
                    target_id = int(cursor.lastrowid)
                    counts["targets_created"] += 1
                    self._event(
                        db,
                        target_id,
                        event_type="seeded",
                        actor="public-records-census",
                        from_status=None,
                        to_status="pending",
                        details={
                            "configuration": "additional_target",
                            "geoid": geoid,
                        },
                    )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        return {
            **counts,
            "db_path": str(self.db_path),
            "config_path": str(Path(config_path)),
        }

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for field, default in (
            ("priority_basis_json", {}),
            ("evidence_json", []),
            ("coverage_gaps_json", []),
        ):
            raw = result.pop(field)
            result[field.removesuffix("_json")] = (
                json.loads(raw) if raw is not None else default
            )
        candidate_source_ids = _candidate_source_ids(
            result["priority_basis"]
        )
        profile = result["priority_basis"].get("profile")
        result["priority_profile_name"] = (
            str(profile.get("name")).strip()
            if isinstance(profile, Mapping) and profile.get("name")
            else None
        )
        result["priority_as_of"] = (
            str(result["priority_basis"].get("as_of")).strip()
            if result["priority_basis"].get("as_of")
            else None
        )
        result["priority_run_id"] = (
            str(result["priority_basis"].get("run_id")).strip()
            if result["priority_basis"].get("run_id")
            else None
        )
        result["priority_input_fingerprint"] = (
            str(result["priority_basis"].get("input_fingerprint")).strip()
            if result["priority_basis"].get("input_fingerprint")
            else None
        )
        result["candidate_source_ids"] = candidate_source_ids
        result["candidate_source_count"] = len(candidate_source_ids)
        return result

    @staticmethod
    def _decode_association(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for field, default in (
            ("coverage_json", {}),
            ("coverage_gaps_json", []),
            ("evidence_json", []),
        ):
            raw = result.pop(field)
            result[field.removesuffix("_json")] = (
                json.loads(raw) if raw is not None else default
            )
        return result

    @classmethod
    def _attach_associations(
        cls,
        db: sqlite3.Connection,
        targets: Sequence[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not targets:
            return []
        target_ids = [int(item["census_target_id"]) for item in targets]
        placeholders = ",".join("?" for _ in target_ids)
        grouped: dict[int, list[dict[str, Any]]] = {
            target_id: [] for target_id in target_ids
        }
        rows = db.execute(
            f"""
            SELECT a.*, s.name AS source_name, s.domain AS source_domain
            FROM source_census_target_sources a
            JOIN sources s USING(source_id)
            WHERE a.census_target_id IN ({placeholders})
            ORDER BY a.census_target_id, a.added_at, a.rowid
            """,
            target_ids,
        ).fetchall()
        for row in rows:
            decoded = cls._decode_association(row)
            grouped[int(decoded["census_target_id"])].append(decoded)
        for target in targets:
            associations = grouped[int(target["census_target_id"])]
            target["source_associations"] = associations
            target["source_ids"] = [
                association["source_id"] for association in associations
            ]
            target["source_count"] = len(associations)
        return list(targets)

    def list_targets(
        self,
        *,
        status: str | None = None,
        domain: str | None = None,
        state: str | None = None,
        role: str | None = None,
        coverage_status: str | None = None,
        source_presence: str | None = None,
        candidate_presence: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if status is not None and status not in CENSUS_STATUSES:
            raise CensusError(f"invalid status: {status}")
        if domain is not None and domain not in {"property", "court"}:
            raise CensusError(f"invalid domain: {domain}")
        if (
            coverage_status is not None
            and coverage_status not in COVERAGE_STATUSES
        ):
            raise CensusError(
                f"invalid coverage status: {coverage_status}"
            )
        if source_presence not in {None, "none", "some"}:
            raise CensusError(
                f"invalid source presence: {source_presence}"
            )
        if candidate_presence not in {None, "none", "some"}:
            raise CensusError(
                f"invalid candidate presence: {candidate_presence}"
            )
        if limit <= 0:
            raise CensusError("limit must be positive")
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("t.status=?")
            params.append(status)
        if domain:
            clauses.append("t.domain=?")
            params.append(domain)
        if state:
            clauses.append("UPPER(j.subdivision_code)=?")
            params.append(state.upper())
        if role:
            clauses.append("t.role=?")
            params.append(role)
        if coverage_status:
            clauses.append("t.coverage_status=?")
            params.append(coverage_status)
        if source_presence:
            existence = "" if source_presence == "some" else "NOT "
            clauses.append(
                f"""
                {existence}EXISTS(
                    SELECT 1
                    FROM source_census_target_sources a
                    WHERE a.census_target_id=t.census_target_id
                )
                """
            )
        if candidate_presence:
            negation = "" if candidate_presence == "some" else "NOT "
            clauses.append(
                f"{negation}({CANDIDATE_SOURCE_EXISTS_SQL})"
            )
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        db = self._connect()
        try:
            rows = db.execute(
                f"""
                SELECT t.*, j.name AS jurisdiction_name, j.geoid,
                       j.subdivision_code
                FROM source_census_targets t
                JOIN jurisdictions j USING(jurisdiction_id)
                {where}
                ORDER BY t.benefit_score DESC, t.feasibility_score DESC,
                         t.risk_score ASC, t.census_target_id
                LIMIT ?
                """,
                params,
            ).fetchall()
            targets = self._attach_associations(
                db,
                [self._decode_row(row) for row in rows],
            )
        finally:
            db.close()
        return targets

    def show(self, target_id: int) -> dict[str, Any]:
        db = self._connect()
        try:
            row = db.execute(
                """
                SELECT t.*, j.name AS jurisdiction_name, j.geoid,
                       j.subdivision_code
                FROM source_census_targets t
                JOIN jurisdictions j USING(jurisdiction_id)
                WHERE census_target_id=?
                """,
                (target_id,),
            ).fetchone()
            if row is None:
                raise CensusError(f"unknown census target: {target_id}")
            target = self._attach_associations(
                db,
                [self._decode_row(row)],
            )[0]
            events = [
                {
                    **dict(event),
                    "details": json.loads(event["details_json"]),
                }
                for event in db.execute(
                    """
                    SELECT * FROM source_census_events
                    WHERE census_target_id=?
                    ORDER BY census_event_id
                    """,
                    (target_id,),
                ).fetchall()
            ]
            for event in events:
                event.pop("details_json")
        finally:
            db.close()
        return {**target, "events": events}

    def score(
        self,
        target_id: int,
        *,
        benefit: float,
        feasibility: float,
        risk: float,
        basis: Mapping[str, Any],
        scored_by: str,
    ) -> dict[str, Any]:
        for label, value in (
            ("benefit", benefit),
            ("feasibility", feasibility),
            ("risk", risk),
        ):
            if not 0 <= value <= 100:
                raise CensusError(f"{label} score must be between 0 and 100")
        if not scored_by.strip():
            raise CensusError("scored_by must not be blank")
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status FROM source_census_targets WHERE census_target_id=?",
                (target_id,),
            ).fetchone()
            if row is None:
                raise CensusError(f"unknown census target: {target_id}")
            db.execute(
                """
                UPDATE source_census_targets
                SET benefit_score=?, feasibility_score=?, risk_score=?,
                    priority_basis_json=?, updated_at=?
                WHERE census_target_id=?
                """,
                (
                    benefit,
                    feasibility,
                    risk,
                    _json_dump(dict(basis)),
                    utc_now(),
                    target_id,
                ),
            )
            self._event(
                db,
                target_id,
                event_type="scored",
                actor=scored_by.strip(),
                from_status=row["status"],
                to_status=row["status"],
                details={
                    "benefit": benefit,
                    "feasibility": feasibility,
                    "risk": risk,
                    "basis": dict(basis),
                },
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return self.show(target_id)

    def claim(
        self,
        *,
        claimed_by: str,
        domain: str | None = None,
        state: str | None = None,
        coverage_status: str | None = None,
        source_presence: str | None = None,
        candidate_presence: str | None = None,
    ) -> dict[str, Any] | None:
        if not claimed_by.strip():
            raise CensusError("claimed_by must not be blank")
        clauses = ["t.status='pending'"]
        params: list[Any] = []
        if domain:
            if domain not in {"property", "court"}:
                raise CensusError(f"invalid domain: {domain}")
            clauses.append("t.domain=?")
            params.append(domain)
        if state:
            clauses.append("UPPER(j.subdivision_code)=?")
            params.append(state.upper())
        if (
            coverage_status is not None
            and coverage_status not in COVERAGE_STATUSES
        ):
            raise CensusError(
                f"invalid coverage status: {coverage_status}"
            )
        if coverage_status:
            clauses.append("t.coverage_status=?")
            params.append(coverage_status)
        if source_presence not in {None, "none", "some"}:
            raise CensusError(
                f"invalid source presence: {source_presence}"
            )
        if source_presence:
            existence = "" if source_presence == "some" else "NOT "
            clauses.append(
                f"""
                {existence}EXISTS(
                    SELECT 1
                    FROM source_census_target_sources a
                    WHERE a.census_target_id=t.census_target_id
                )
                """
            )
        if candidate_presence not in {None, "none", "some"}:
            raise CensusError(
                f"invalid candidate presence: {candidate_presence}"
            )
        if candidate_presence:
            negation = "" if candidate_presence == "some" else "NOT "
            clauses.append(
                f"{negation}({CANDIDATE_SOURCE_EXISTS_SQL})"
            )
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                f"""
                SELECT t.census_target_id
                FROM source_census_targets t
                JOIN jurisdictions j USING(jurisdiction_id)
                WHERE {' AND '.join(clauses)}
                ORDER BY t.benefit_score DESC, t.feasibility_score DESC,
                         t.risk_score ASC, t.census_target_id
                LIMIT 1
                """,
                params,
            ).fetchone()
            if row is None:
                db.commit()
                return None
            target_id = int(row["census_target_id"])
            now = utc_now()
            db.execute(
                """
                UPDATE source_census_targets
                SET status='in_progress', claimed_by=?, claimed_at=?,
                    updated_at=?
                WHERE census_target_id=? AND status='pending'
                """,
                (claimed_by.strip(), now, now, target_id),
            )
            self._event(
                db,
                target_id,
                event_type="claimed",
                actor=claimed_by.strip(),
                from_status="pending",
                to_status="in_progress",
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return self.show(target_id)

    @staticmethod
    def _source_for_target(
        db: sqlite3.Connection,
        *,
        source_id: str,
        target_domain: str,
    ) -> sqlite3.Row:
        source = db.execute(
            "SELECT domain, official_url FROM sources WHERE source_id=?",
            (source_id,),
        ).fetchone()
        if source is None:
            raise CensusError(f"unknown catalog source: {source_id}")
        if source["domain"] not in {target_domain, "mixed"}:
            raise CensusError(
                "catalog source domain does not match census target"
            )
        return source

    @staticmethod
    def _upsert_source_association(
        db: sqlite3.Connection,
        *,
        target_id: int,
        source_id: str,
        official_url: str | None,
        coverage: Mapping[str, Any] | None,
        coverage_gaps: Sequence[Any] | None,
        notes: str | None,
        evidence: Sequence[Mapping[str, Any]] | None,
        added_by: str,
        now: str,
    ) -> None:
        existing = db.execute(
            """
            SELECT * FROM source_census_target_sources
            WHERE census_target_id=? AND source_id=?
            """,
            (target_id, source_id),
        ).fetchone()
        existing_coverage = (
            json.loads(existing["coverage_json"]) if existing else {}
        )
        existing_gaps = (
            json.loads(existing["coverage_gaps_json"]) if existing else []
        )
        existing_evidence = (
            json.loads(existing["evidence_json"]) if existing else []
        )
        stored_url = (
            str(existing["official_url"])
            if existing and existing["official_url"]
            else None
        )
        stored_notes = existing["notes"] if existing else None
        db.execute(
            """
            INSERT INTO source_census_target_sources(
                census_target_id, source_id, official_url, coverage_json,
                coverage_gaps_json, notes, evidence_json, added_by, added_at,
                updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(census_target_id, source_id) DO UPDATE SET
                official_url=excluded.official_url,
                coverage_json=excluded.coverage_json,
                coverage_gaps_json=excluded.coverage_gaps_json,
                notes=excluded.notes,
                evidence_json=excluded.evidence_json,
                added_by=excluded.added_by,
                updated_at=excluded.updated_at
            """,
            (
                target_id,
                source_id,
                official_url or stored_url,
                _json_dump(
                    dict(coverage)
                    if coverage is not None
                    else existing_coverage
                ),
                _json_dump(
                    list(coverage_gaps)
                    if coverage_gaps is not None
                    else existing_gaps
                ),
                notes if notes is not None else stored_notes,
                _json_dump(
                    [dict(item) for item in evidence]
                    if evidence is not None
                    else existing_evidence
                ),
                added_by,
                str(existing["added_at"]) if existing else now,
                now,
            ),
        )

    def associate_source(
        self,
        target_id: int,
        *,
        source_id: str,
        added_by: str,
        official_url: str | None = None,
        coverage: Mapping[str, Any] | None = None,
        coverage_gaps: Sequence[Any] | None = None,
        notes: str | None = None,
        evidence: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Associate another catalog source and its specific coverage evidence."""
        if not added_by.strip():
            raise CensusError("added_by must not be blank")
        if coverage is not None and not isinstance(coverage, Mapping):
            raise CensusError("coverage must be an object")
        if coverage_gaps is not None and isinstance(
            coverage_gaps, (str, bytes)
        ):
            raise CensusError("coverage_gaps must be a list")
        if evidence is not None:
            for item in evidence:
                if not isinstance(item, Mapping):
                    raise CensusError("evidence must be a list of objects")

        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            target = db.execute(
                """
                SELECT status, domain, source_id
                FROM source_census_targets
                WHERE census_target_id=?
                """,
                (target_id,),
            ).fetchone()
            if target is None:
                raise CensusError(f"unknown census target: {target_id}")
            source = self._source_for_target(
                db,
                source_id=source_id,
                target_domain=str(target["domain"]),
            )
            source_url = official_url or str(source["official_url"])
            now = utc_now()
            self._upsert_source_association(
                db,
                target_id=target_id,
                source_id=source_id,
                official_url=source_url,
                coverage=coverage,
                coverage_gaps=coverage_gaps,
                notes=notes,
                evidence=evidence,
                added_by=added_by.strip(),
                now=now,
            )
            if target["source_id"] is None:
                db.execute(
                    """
                    UPDATE source_census_targets
                    SET source_id=?, official_url=?, updated_at=?
                    WHERE census_target_id=?
                    """,
                    (source_id, source_url, now, target_id),
                )
            else:
                db.execute(
                    """
                    UPDATE source_census_targets SET updated_at=?
                    WHERE census_target_id=?
                    """,
                    (now, target_id),
                )
            self._event(
                db,
                target_id,
                event_type="source_associated",
                actor=added_by.strip(),
                from_status=str(target["status"]),
                to_status=str(target["status"]),
                details={
                    "source_id": source_id,
                    "coverage": dict(coverage or {}),
                    "coverage_gaps": list(coverage_gaps or []),
                    "notes": notes,
                },
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return self.show(target_id)

    def disassociate_source(
        self,
        target_id: int,
        *,
        source_id: str,
        removed_by: str,
    ) -> dict[str, Any]:
        """Remove one source association while preserving the target assessment."""
        if not source_id.strip():
            raise CensusError("source_id must not be blank")
        if not removed_by.strip():
            raise CensusError("removed_by must not be blank")

        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            target = db.execute(
                """
                SELECT status, source_id
                FROM source_census_targets
                WHERE census_target_id=?
                """,
                (target_id,),
            ).fetchone()
            if target is None:
                raise CensusError(f"unknown census target: {target_id}")

            association = db.execute(
                """
                SELECT *
                FROM source_census_target_sources
                WHERE census_target_id=? AND source_id=?
                """,
                (target_id, source_id),
            ).fetchone()
            if association is None:
                raise CensusError(
                    f"source {source_id} is not associated with "
                    f"census target {target_id}"
                )

            was_primary = target["source_id"] == source_id
            db.execute(
                """
                DELETE FROM source_census_target_sources
                WHERE census_target_id=? AND source_id=?
                """,
                (target_id, source_id),
            )

            replacement = None
            if was_primary:
                replacement = db.execute(
                    """
                    SELECT source_id, official_url
                    FROM source_census_target_sources
                    WHERE census_target_id=?
                    ORDER BY added_at, source_id
                    LIMIT 1
                    """,
                    (target_id,),
                ).fetchone()

            now = utc_now()
            if was_primary:
                db.execute(
                    """
                    UPDATE source_census_targets
                    SET source_id=?, official_url=?, updated_at=?
                    WHERE census_target_id=?
                    """,
                    (
                        replacement["source_id"] if replacement else None,
                        replacement["official_url"] if replacement else None,
                        now,
                        target_id,
                    ),
                )
            else:
                db.execute(
                    """
                    UPDATE source_census_targets SET updated_at=?
                    WHERE census_target_id=?
                    """,
                    (now, target_id),
                )

            removed_association = self._decode_association(association)
            self._event(
                db,
                target_id,
                event_type="source_disassociated",
                actor=removed_by.strip(),
                from_status=str(target["status"]),
                to_status=str(target["status"]),
                details={
                    "source_id": source_id,
                    "was_primary": was_primary,
                    "replacement_source_id": (
                        replacement["source_id"] if replacement else None
                    ),
                    "removed_association": removed_association,
                },
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return self.show(target_id)

    def assess_coverage(
        self,
        target_id: int,
        *,
        coverage_status: str,
        assessed_by: str,
        coverage_gaps: Sequence[Any] = (),
        notes: str | None = None,
        evidence: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        """Record a target-level assessment separately from source discovery."""
        if coverage_status not in COVERAGE_STATUSES:
            raise CensusError(f"invalid coverage status: {coverage_status}")
        if not assessed_by.strip():
            raise CensusError("assessed_by must not be blank")
        if isinstance(coverage_gaps, (str, bytes)):
            raise CensusError("coverage_gaps must be a list")
        for item in evidence:
            if not isinstance(item, Mapping):
                raise CensusError("evidence must be a list of objects")
        if coverage_status == "comprehensive" and coverage_gaps:
            raise CensusError(
                "comprehensive coverage cannot include unresolved gaps"
            )

        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT status, coverage_status
                FROM source_census_targets
                WHERE census_target_id=?
                """,
                (target_id,),
            ).fetchone()
            if row is None:
                raise CensusError(f"unknown census target: {target_id}")
            db.execute(
                """
                UPDATE source_census_targets
                SET coverage_status=?, coverage_notes=?,
                    coverage_gaps_json=?, updated_at=?
                WHERE census_target_id=?
                """,
                (
                    coverage_status,
                    notes,
                    _json_dump(list(coverage_gaps)),
                    utc_now(),
                    target_id,
                ),
            )
            self._event(
                db,
                target_id,
                event_type="coverage_assessed",
                actor=assessed_by.strip(),
                from_status=str(row["status"]),
                to_status=str(row["status"]),
                details={
                    "from_coverage_status": row["coverage_status"],
                    "coverage_status": coverage_status,
                    "coverage_gaps": list(coverage_gaps),
                    "notes": notes,
                    "evidence": [dict(item) for item in evidence],
                },
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return self.show(target_id)

    def resolve(
        self,
        target_id: int,
        *,
        status: str,
        resolved_by: str,
        source_id: str | None = None,
        official_url: str | None = None,
        evidence: Sequence[Mapping[str, Any]] = (),
        notes: str | None = None,
    ) -> dict[str, Any]:
        if status not in RESOLUTION_STATUSES:
            raise CensusError(
                "resolution status must be one of "
                + ", ".join(sorted(RESOLUTION_STATUSES))
            )
        if not resolved_by.strip():
            raise CensusError("resolved_by must not be blank")
        if status == "manifest_submitted" and not source_id:
            raise CensusError("manifest_submitted requires source_id")
        for item in evidence:
            if not isinstance(item, Mapping):
                raise CensusError("evidence must be a list of objects")

        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT status, domain FROM source_census_targets
                WHERE census_target_id=?
                """,
                (target_id,),
            ).fetchone()
            if row is None:
                raise CensusError(f"unknown census target: {target_id}")
            if source_id:
                source = self._source_for_target(
                    db,
                    source_id=source_id,
                    target_domain=str(row["domain"]),
                )
                official_url = official_url or str(source["official_url"])
            now = utc_now()
            db.execute(
                """
                UPDATE source_census_targets
                SET status=?,
                    source_id=COALESCE(source_id, ?),
                    official_url=COALESCE(official_url, ?),
                    evidence_json=?, notes=?, resolved_by=?, resolved_at=?,
                    updated_at=?
                WHERE census_target_id=?
                """,
                (
                    status,
                    source_id,
                    official_url,
                    _json_dump([dict(item) for item in evidence]),
                    notes,
                    resolved_by.strip(),
                    now,
                    now,
                    target_id,
                ),
            )
            if source_id:
                self._upsert_source_association(
                    db,
                    target_id=target_id,
                    source_id=source_id,
                    official_url=official_url,
                    coverage=None,
                    coverage_gaps=None,
                    notes=notes,
                    evidence=evidence,
                    added_by=resolved_by.strip(),
                    now=now,
                )
            self._event(
                db,
                target_id,
                event_type="resolved",
                actor=resolved_by.strip(),
                from_status=str(row["status"]),
                to_status=status,
                details={
                    "source_id": source_id,
                    "official_url": official_url,
                    "notes": notes,
                },
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return self.show(target_id)

    def release(self, target_id: int, *, released_by: str) -> dict[str, Any]:
        if not released_by.strip():
            raise CensusError("released_by must not be blank")
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status FROM source_census_targets WHERE census_target_id=?",
                (target_id,),
            ).fetchone()
            if row is None:
                raise CensusError(f"unknown census target: {target_id}")
            if row["status"] != "in_progress":
                raise CensusError("only an in-progress target can be released")
            db.execute(
                """
                UPDATE source_census_targets
                SET status='pending', claimed_by=NULL, claimed_at=NULL,
                    updated_at=?
                WHERE census_target_id=?
                """,
                (utc_now(), target_id),
            )
            self._event(
                db,
                target_id,
                event_type="released",
                actor=released_by.strip(),
                from_status="in_progress",
                to_status="pending",
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return self.show(target_id)

    def submit_manifest(
        self,
        target_id: int,
        manifest_path: str | Path,
        *,
        submitted_by: str,
    ) -> dict[str, Any]:
        manifest_data = yaml.safe_load(
            Path(manifest_path).read_text(encoding="utf-8")
        )
        if not isinstance(manifest_data, Mapping):
            raise CensusError("source manifest must be a mapping")
        registration = PublicRecordsCatalog(self.db_path).register_manifest(
            manifest_data,
            submitted_by=submitted_by,
        )
        target = self.resolve(
            target_id,
            status="manifest_submitted",
            source_id=str(registration["source_id"]),
            resolved_by=submitted_by,
            official_url=str(manifest_data["official_url"]),
            evidence=[
                {
                    "kind": "manifest",
                    "manifest_sha256": registration["manifest_sha256"],
                    "path": str(Path(manifest_path)),
                }
            ],
            notes=(
                "Manifest and access-review status are tracked separately."
            ),
        )
        return {"registration": registration, "target": target}

    def stats(self) -> dict[str, Any]:
        db = self._connect()
        try:
            total = int(
                db.execute("SELECT COUNT(*) FROM source_census_targets").fetchone()[0]
            )
            by_status = {
                row["status"]: int(row["count"])
                for row in db.execute(
                    """
                    SELECT status, COUNT(*) AS count
                    FROM source_census_targets GROUP BY status ORDER BY status
                    """
                ).fetchall()
            }
            by_domain = {
                row["domain"]: int(row["count"])
                for row in db.execute(
                    """
                    SELECT domain, COUNT(*) AS count
                    FROM source_census_targets GROUP BY domain ORDER BY domain
                    """
                ).fetchall()
            }
            by_coverage_status = {
                row["coverage_status"]: int(row["count"])
                for row in db.execute(
                    """
                    SELECT coverage_status, COUNT(*) AS count
                    FROM source_census_targets
                    GROUP BY coverage_status
                    ORDER BY coverage_status
                    """
                ).fetchall()
            }
            source_associations = int(
                db.execute(
                    "SELECT COUNT(*) FROM source_census_target_sources"
                ).fetchone()[0]
            )
            targets_with_multiple_sources = int(
                db.execute(
                    """
                    SELECT COUNT(*) FROM (
                        SELECT census_target_id
                        FROM source_census_target_sources
                        GROUP BY census_target_id
                        HAVING COUNT(*) > 1
                    )
                    """
                ).fetchone()[0]
            )
            targets_with_explicit_gaps = int(
                db.execute(
                    """
                    SELECT COUNT(*) FROM source_census_targets
                    WHERE coverage_gaps_json <> '[]'
                    """
                ).fetchone()[0]
            )
            reviewed_sources = int(
                db.execute(
                    """
                    SELECT COUNT(DISTINCT s.source_id)
                    FROM sources s
                    JOIN access_reviews a USING(source_id)
                    """
                ).fetchone()[0]
            )
            sources = int(db.execute("SELECT COUNT(*) FROM sources").fetchone()[0])
        finally:
            db.close()
        return {
            "total_targets": total,
            "by_status": by_status,
            "by_domain": by_domain,
            "by_coverage_status": by_coverage_status,
            "source_associations": source_associations,
            "targets_with_multiple_sources": targets_with_multiple_sources,
            "targets_with_explicit_gaps": targets_with_explicit_gaps,
            "catalog_sources": sources,
            "sources_with_access_review": reviewed_sources,
            "access_review_percentage": (
                round((reviewed_sources / sources) * 100, 2) if sources else 0
            ),
        }


def _add_common_output(parser: argparse.ArgumentParser) -> None:
    add_output_args(parser)


def compact_target_rows(targets: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Project census targets into the fields used for ranked queue triage."""

    return [
        {field: target.get(field) for field in COMPACT_TARGET_FIELDS}
        for target in targets
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage the nationwide public-record source-census queue"
    )
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    sub = parser.add_subparsers(dest="command", required=True)

    seed_parser = sub.add_parser("seed")
    seed_parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    _add_common_output(seed_parser)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--status", choices=sorted(CENSUS_STATUSES))
    list_parser.add_argument("--domain", choices=["property", "court"])
    list_parser.add_argument("--state")
    list_parser.add_argument("--role")
    list_parser.add_argument(
        "--coverage-status",
        choices=sorted(COVERAGE_STATUSES),
    )
    list_parser.add_argument(
        "--source-presence",
        choices=["none", "some"],
        help="Select targets without or with a catalog source association",
    )
    list_parser.add_argument(
        "--candidate-presence",
        choices=["none", "some"],
        help=(
            "Select targets without or with compatible catalog candidates "
            "recorded by priority recomputation"
        ),
    )
    list_parser.add_argument("--limit", type=int, default=100)
    list_parser.add_argument(
        "--compact",
        action="store_true",
        help=(
            "Return ranked queue fields without expanded priority evidence, "
            "coverage gaps, or source-association records"
        ),
    )
    _add_common_output(list_parser)

    show_parser = sub.add_parser("show")
    show_parser.add_argument("target_id", type=int)
    _add_common_output(show_parser)

    claim_parser = sub.add_parser("claim")
    claim_parser.add_argument("--by", required=True)
    claim_parser.add_argument("--domain", choices=["property", "court"])
    claim_parser.add_argument("--state")
    claim_parser.add_argument(
        "--coverage-status",
        choices=sorted(COVERAGE_STATUSES),
    )
    claim_parser.add_argument(
        "--source-presence",
        choices=["none", "some"],
        help="Claim a target without or with a catalog source association",
    )
    claim_parser.add_argument(
        "--candidate-presence",
        choices=["none", "some"],
        help=(
            "Claim a target without or with compatible catalog candidates "
            "recorded by priority recomputation"
        ),
    )
    _add_common_output(claim_parser)

    release_parser = sub.add_parser("release")
    release_parser.add_argument("target_id", type=int)
    release_parser.add_argument("--by", required=True)
    _add_common_output(release_parser)

    score_parser = sub.add_parser("score")
    score_parser.add_argument("target_id", type=int)
    score_parser.add_argument("--benefit", type=float, required=True)
    score_parser.add_argument("--feasibility", type=float, required=True)
    score_parser.add_argument("--risk", type=float, required=True)
    score_parser.add_argument("--basis", default="{}")
    score_parser.add_argument("--by", required=True)
    _add_common_output(score_parser)

    resolve_parser = sub.add_parser("resolve")
    resolve_parser.add_argument("target_id", type=int)
    resolve_parser.add_argument(
        "--status",
        choices=sorted(RESOLUTION_STATUSES),
        required=True,
    )
    resolve_parser.add_argument("--source-id")
    resolve_parser.add_argument("--official-url")
    resolve_parser.add_argument("--evidence", default="[]")
    resolve_parser.add_argument("--notes")
    resolve_parser.add_argument("--by", required=True)
    _add_common_output(resolve_parser)

    associate_parser = sub.add_parser("associate")
    associate_parser.add_argument("target_id", type=int)
    associate_parser.add_argument("--source-id", required=True)
    associate_parser.add_argument("--official-url")
    associate_parser.add_argument(
        "--coverage",
        default="{}",
        help="JSON object describing the source's contribution",
    )
    associate_parser.add_argument(
        "--coverage-gaps",
        default="[]",
        help="JSON list of gaps left by this source",
    )
    associate_parser.add_argument(
        "--evidence",
        default="[]",
        help="JSON list of evidence objects",
    )
    associate_parser.add_argument("--notes")
    associate_parser.add_argument("--by", required=True)
    _add_common_output(associate_parser)

    disassociate_parser = sub.add_parser(
        "disassociate-source",
        help="Remove one catalog source association from a census target",
    )
    disassociate_parser.add_argument("target_id", type=int)
    disassociate_parser.add_argument("--source-id", required=True)
    disassociate_parser.add_argument("--by", required=True)
    _add_common_output(disassociate_parser)

    coverage_parser = sub.add_parser("assess-coverage")
    coverage_parser.add_argument("target_id", type=int)
    coverage_parser.add_argument(
        "--status",
        dest="coverage_status",
        choices=sorted(COVERAGE_STATUSES),
        required=True,
    )
    coverage_parser.add_argument(
        "--gaps",
        default="[]",
        help="JSON list of unresolved coverage gaps",
    )
    coverage_parser.add_argument(
        "--evidence",
        default="[]",
        help="JSON list of evidence objects",
    )
    coverage_parser.add_argument("--notes")
    coverage_parser.add_argument("--by", required=True)
    _add_common_output(coverage_parser)

    submit_parser = sub.add_parser("submit")
    submit_parser.add_argument("target_id", type=int)
    submit_parser.add_argument("manifest")
    submit_parser.add_argument("--by", required=True)
    _add_common_output(submit_parser)

    stats_parser = sub.add_parser("stats")
    _add_common_output(stats_parser)
    return parser


def _emit(value: Any, args: argparse.Namespace, summary: str) -> None:
    if write_output(value, args, summary=summary):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(value, indent=2, sort_keys=True))
        return
    if isinstance(value, list):
        for item in value:
            print(
                f"{item['census_target_id']:>4} "
                f"{item['subdivision_code']:<2} {item['domain']:<8} "
                f"{item['role']:<22} {item['status']} "
                f"sources={item['source_count']} "
                f"coverage={item['coverage_status']}"
            )
        return
    print(json.dumps(value, indent=2, sort_keys=True))


def main() -> int:
    args = build_parser().parse_args()
    census = PublicRecordsCensus(args.db)
    try:
        if args.command == "seed":
            value = census.seed(args.config)
        elif args.command == "list":
            value = census.list_targets(
                status=args.status,
                domain=args.domain,
                state=args.state,
                role=args.role,
                coverage_status=args.coverage_status,
                source_presence=args.source_presence,
                candidate_presence=args.candidate_presence,
                limit=args.limit,
            )
            if args.compact:
                value = compact_target_rows(value)
        elif args.command == "show":
            value = census.show(args.target_id)
        elif args.command == "claim":
            value = census.claim(
                claimed_by=args.by,
                domain=args.domain,
                state=args.state,
                coverage_status=args.coverage_status,
                source_presence=args.source_presence,
                candidate_presence=args.candidate_presence,
            )
        elif args.command == "release":
            value = census.release(args.target_id, released_by=args.by)
        elif args.command == "score":
            basis = _json_value(args.basis, default={})
            if not isinstance(basis, Mapping):
                raise CensusError("basis must be a JSON object")
            value = census.score(
                args.target_id,
                benefit=args.benefit,
                feasibility=args.feasibility,
                risk=args.risk,
                basis=basis,
                scored_by=args.by,
            )
        elif args.command == "resolve":
            evidence = _json_value(args.evidence, default=[])
            if not isinstance(evidence, list):
                raise CensusError("evidence must be a JSON list")
            value = census.resolve(
                args.target_id,
                status=args.status,
                source_id=args.source_id,
                official_url=args.official_url,
                evidence=evidence,
                notes=args.notes,
                resolved_by=args.by,
            )
        elif args.command == "associate":
            coverage = _json_value(args.coverage, default={})
            coverage_gaps = _json_value(args.coverage_gaps, default=[])
            evidence = _json_value(args.evidence, default=[])
            if not isinstance(coverage, Mapping):
                raise CensusError("coverage must be a JSON object")
            if not isinstance(coverage_gaps, list):
                raise CensusError("coverage-gaps must be a JSON list")
            if not isinstance(evidence, list):
                raise CensusError("evidence must be a JSON list")
            value = census.associate_source(
                args.target_id,
                source_id=args.source_id,
                official_url=args.official_url,
                coverage=coverage,
                coverage_gaps=coverage_gaps,
                evidence=evidence,
                notes=args.notes,
                added_by=args.by,
            )
        elif args.command == "disassociate-source":
            value = census.disassociate_source(
                args.target_id,
                source_id=args.source_id,
                removed_by=args.by,
            )
        elif args.command == "assess-coverage":
            gaps = _json_value(args.gaps, default=[])
            evidence = _json_value(args.evidence, default=[])
            if not isinstance(gaps, list):
                raise CensusError("gaps must be a JSON list")
            if not isinstance(evidence, list):
                raise CensusError("evidence must be a JSON list")
            value = census.assess_coverage(
                args.target_id,
                coverage_status=args.coverage_status,
                coverage_gaps=gaps,
                evidence=evidence,
                notes=args.notes,
                assessed_by=args.by,
            )
        elif args.command == "submit":
            value = census.submit_manifest(
                args.target_id,
                args.manifest,
                submitted_by=args.by,
            )
        else:
            value = census.stats()
    except (CensusError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    _emit(value, args, f"Public-record source census {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
