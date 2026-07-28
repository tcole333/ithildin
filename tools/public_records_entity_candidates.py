#!/usr/bin/env python3
"""Explainable, reversible entity candidates for public-record sidecars.

Candidate generation compares raw public-record names with investigation
entities and aliases using conservative normalization. Every matching name,
address, and identifier signal is retained. Candidates are suggestions only:
accept, reject, reopen, and undo are explicit append-only decisions.

Usage:
    uv run python tools/public_records_entity_candidates.py generate
    uv run python tools/public_records_entity_candidates.py list --status open
    uv run python tools/public_records_entity_candidates.py decide 12 \
      --action accept --actor analyst
    uv run python tools/public_records_entity_candidates.py history 12
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
import sys
import unicodedata
import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import canonical_json, utc_now_iso
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_contract import canonical_json, utc_now_iso


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "datasets" / "public_records_entity_candidates.db"
DEFAULT_PROPERTY_DB = PROJECT_ROOT / "datasets" / "property_records.db"
DEFAULT_COURT_DB = PROJECT_ROOT / "datasets" / "state_court_records.db"
DEFAULT_CORE_DB = PROJECT_ROOT / "investigation.db"
SCHEMA_VERSION = 1

_RECORD_SPECS = {
    "ownership_assertion": {
        "domain": "property",
        "pk": "ownership_assertion_id",
        "name": "raw_owner_name",
        "normalized_name": "normalized_owner_name",
        "address": None,
        "resolution_confidence": None,
        "resolution_status": None,
    },
    "instrument_party": {
        "domain": "property",
        "pk": "instrument_party_id",
        "name": "raw_name",
        "normalized_name": "normalized_name",
        "address": "raw_address",
        "resolution_confidence": "resolution_confidence",
        "resolution_status": "resolution_status",
    },
    "case_party": {
        "domain": "court",
        "pk": "case_party_id",
        "name": "raw_name",
        "normalized_name": "normalized_name",
        "address": None,
        "resolution_confidence": "resolution_confidence",
        "resolution_status": "resolution_status",
    },
}
_IDENTIFIER_COLUMNS = (
    "ein",
    "tax_id",
    "entity_identifier",
    "registration_id",
    "business_id",
    "bar_id",
    "native_entity_id",
)
_IDENTIFIER_KINDS = {
    "ein": "tax_identifier",
    "tax_id": "tax_identifier",
}
_JSON_COLUMNS = frozenset(
    {
        "addresses_json",
        "identifiers_json",
        "row_snapshot_json",
        "entity_snapshot_json",
        "signals_json",
        "metadata_json",
        "prior_state_json",
        "new_state_json",
    }
)


class CandidateStoreError(RuntimeError):
    """Base exception for candidate generation and decisions."""


class CandidateNotFoundError(CandidateStoreError):
    """Raised when a candidate or source row is absent."""


class DecisionConflictError(CandidateStoreError):
    """Raised when a requested decision conflicts with current audited state."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generation_run (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_ref TEXT NOT NULL UNIQUE,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    property_db_path TEXT,
    court_db_path TEXT,
    core_db_path TEXT NOT NULL,
    record_types_json TEXT NOT NULL,
    records_observed INTEGER,
    candidates_observed INTEGER,
    signal_observations_added INTEGER
);

CREATE TABLE IF NOT EXISTS source_record (
    source_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_ref TEXT NOT NULL UNIQUE,
    domain TEXT NOT NULL CHECK (domain IN ('property', 'court')),
    record_type TEXT NOT NULL,
    sidecar_db_path TEXT NOT NULL,
    table_name TEXT NOT NULL,
    primary_key_column TEXT NOT NULL,
    row_id INTEGER NOT NULL,
    first_seen_at TEXT NOT NULL,
    UNIQUE(sidecar_db_path, table_name, row_id)
);

CREATE TABLE IF NOT EXISTS source_record_observation (
    source_observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_record_id INTEGER NOT NULL
        REFERENCES source_record(source_record_id),
    run_id INTEGER NOT NULL REFERENCES generation_run(run_id),
    observed_at TEXT NOT NULL,
    raw_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    addresses_json TEXT NOT NULL DEFAULT '[]',
    identifiers_json TEXT NOT NULL DEFAULT '{}',
    row_snapshot_json TEXT NOT NULL,
    observation_fingerprint TEXT NOT NULL,
    UNIQUE(source_record_id, observation_fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_source_observation_record
    ON source_record_observation(source_record_id, source_observation_id);

CREATE TABLE IF NOT EXISTS entity_candidate (
    candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_ref TEXT NOT NULL UNIQUE,
    source_record_id INTEGER NOT NULL REFERENCES source_record(source_record_id),
    core_db_path TEXT NOT NULL,
    core_entity_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(source_record_id, core_db_path, core_entity_id)
);
CREATE INDEX IF NOT EXISTS idx_candidate_entity
    ON entity_candidate(core_db_path, core_entity_id);

CREATE TABLE IF NOT EXISTS candidate_signal_observation (
    signal_observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES entity_candidate(candidate_id),
    run_id INTEGER NOT NULL REFERENCES generation_run(run_id),
    source_observation_id INTEGER NOT NULL
        REFERENCES source_record_observation(source_observation_id),
    observed_at TEXT NOT NULL,
    entity_snapshot_json TEXT NOT NULL,
    signals_json TEXT NOT NULL,
    signal_fingerprint TEXT NOT NULL,
    UNIQUE(candidate_id, signal_fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_candidate_signal
    ON candidate_signal_observation(candidate_id, signal_observation_id);

CREATE TABLE IF NOT EXISTS decision_event (
    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_ref TEXT NOT NULL UNIQUE,
    candidate_id INTEGER NOT NULL REFERENCES entity_candidate(candidate_id),
    action TEXT NOT NULL
        CHECK (action IN ('accept', 'reject', 'reopen', 'undo')),
    previous_state TEXT NOT NULL,
    resulting_state TEXT NOT NULL,
    actor TEXT NOT NULL,
    reason TEXT,
    resolution_confidence REAL,
    decided_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    previous_decision_id INTEGER REFERENCES decision_event(decision_id),
    undo_of_decision_id INTEGER REFERENCES decision_event(decision_id),
    CHECK (
        resolution_confidence IS NULL
        OR (
            resolution_confidence >= 0.0
            AND resolution_confidence <= 1.0
        )
    )
);
CREATE INDEX IF NOT EXISTS idx_decision_candidate
    ON decision_event(candidate_id, decision_id);

CREATE TABLE IF NOT EXISTS candidate_projection (
    candidate_id INTEGER PRIMARY KEY REFERENCES entity_candidate(candidate_id),
    state TEXT NOT NULL,
    current_decision_id INTEGER REFERENCES decision_event(decision_id),
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS link_mutation_event (
    mutation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    mutation_ref TEXT NOT NULL UNIQUE,
    decision_id INTEGER NOT NULL REFERENCES decision_event(decision_id),
    candidate_id INTEGER NOT NULL REFERENCES entity_candidate(candidate_id),
    source_record_id INTEGER NOT NULL REFERENCES source_record(source_record_id),
    mutation_type TEXT NOT NULL CHECK (mutation_type IN ('accept', 'undo')),
    sidecar_db_path TEXT NOT NULL,
    table_name TEXT NOT NULL,
    primary_key_column TEXT NOT NULL,
    row_id INTEGER NOT NULL,
    prior_state_json TEXT NOT NULL,
    new_state_json TEXT NOT NULL,
    reverses_mutation_id INTEGER REFERENCES link_mutation_event(mutation_id),
    applied_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_link_mutation_decision
    ON link_mutation_event(decision_id);

CREATE TRIGGER IF NOT EXISTS source_record_no_update
BEFORE UPDATE ON source_record
BEGIN
    SELECT RAISE(ABORT, 'source records are immutable');
END;
CREATE TRIGGER IF NOT EXISTS source_record_no_delete
BEFORE DELETE ON source_record
BEGIN
    SELECT RAISE(ABORT, 'source records are immutable');
END;
CREATE TRIGGER IF NOT EXISTS source_observation_no_update
BEFORE UPDATE ON source_record_observation
BEGIN
    SELECT RAISE(ABORT, 'source observations are immutable');
END;
CREATE TRIGGER IF NOT EXISTS source_observation_no_delete
BEFORE DELETE ON source_record_observation
BEGIN
    SELECT RAISE(ABORT, 'source observations are immutable');
END;
CREATE TRIGGER IF NOT EXISTS entity_candidate_no_update
BEFORE UPDATE ON entity_candidate
BEGIN
    SELECT RAISE(ABORT, 'entity candidates are immutable');
END;
CREATE TRIGGER IF NOT EXISTS entity_candidate_no_delete
BEFORE DELETE ON entity_candidate
BEGIN
    SELECT RAISE(ABORT, 'entity candidates are immutable');
END;
CREATE TRIGGER IF NOT EXISTS signal_observation_no_update
BEFORE UPDATE ON candidate_signal_observation
BEGIN
    SELECT RAISE(ABORT, 'candidate signals are immutable');
END;
CREATE TRIGGER IF NOT EXISTS signal_observation_no_delete
BEFORE DELETE ON candidate_signal_observation
BEGIN
    SELECT RAISE(ABORT, 'candidate signals are immutable');
END;
CREATE TRIGGER IF NOT EXISTS decision_event_no_update
BEFORE UPDATE ON decision_event
BEGIN
    SELECT RAISE(ABORT, 'decision events are immutable');
END;
CREATE TRIGGER IF NOT EXISTS decision_event_no_delete
BEFORE DELETE ON decision_event
BEGIN
    SELECT RAISE(ABORT, 'decision events are immutable');
END;
CREATE TRIGGER IF NOT EXISTS link_mutation_no_update
BEFORE UPDATE ON link_mutation_event
BEGIN
    SELECT RAISE(ABORT, 'link mutation events are immutable');
END;
CREATE TRIGGER IF NOT EXISTS link_mutation_no_delete
BEFORE DELETE ON link_mutation_event
BEGIN
    SELECT RAISE(ABORT, 'link mutation events are immutable');
END;
"""


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, field_name)


def _normalize_timestamp(value: str | datetime | None, field_name: str) -> str:
    if value is None:
        return utc_now_iso()
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO 8601 timestamp") from exc
    else:
        raise ValueError(f"{field_name} must be an ISO 8601 timestamp")
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_json(value: Any, field_name: str) -> Any:
    try:
        return json.loads(canonical_json(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain JSON-compatible data") from exc


def _normalize_mapping(
    value: Mapping[str, Any] | None, field_name: str
) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a JSON object")
    result = _normalize_json(value, field_name)
    if not isinstance(result, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return result


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalize_name(value: str) -> str:
    """Conservatively normalize a name for exact comparison."""

    text = unicodedata.normalize("NFKC", _require_text(value, "name")).casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def normalize_address(value: str) -> str:
    """Normalize address punctuation and spacing without fuzzy expansion."""

    text = unicodedata.normalize("NFKC", _require_text(value, "address")).casefold()
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def normalize_identifier(value: Any) -> str:
    """Normalize an identifier to uppercase alphanumeric characters."""

    text = unicodedata.normalize(
        "NFKC", _require_text(str(value), "identifier")
    ).upper()
    return re.sub(r"[^A-Z0-9]", "", text)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    for key in _JSON_COLUMNS.intersection(result):
        if result[key] is not None:
            result[key.removesuffix("_json")] = json.loads(result.pop(key))
    return result


def _open_readonly(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(f"database not found: {path}")
    db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def _table_columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}


def _require_table(db: sqlite3.Connection, table: str) -> None:
    if db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone() is None:
        raise CandidateStoreError(f"required table is missing: {table}")


def connect_candidate_db(path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    """Open and initialize the candidate audit database in WAL mode."""

    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA busy_timeout = 5000")
    db.executescript(SCHEMA)
    db.execute(
        "INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    db.commit()
    return db


def _core_entities(core: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    _require_table(core, "entities")
    columns = _table_columns(core, "entities")
    selected = ["id", "name"]
    for optional in ("address", "ein", "jurisdiction", "entity_type"):
        if optional in columns:
            selected.append(optional)
    entities: dict[int, dict[str, Any]] = {}
    for row in core.execute(f"SELECT {', '.join(selected)} FROM entities"):
        item = dict(row)
        item["addresses"] = []
        if item.get("address"):
            item["addresses"].append(
                {
                    "value": item["address"],
                    "normalized": normalize_address(item["address"]),
                    "origin": "entities.address",
                }
            )
        item["identifiers"] = {}
        if item.get("ein"):
            item["identifiers"]["tax_identifier"] = {
                "value": item["ein"],
                "normalized": normalize_identifier(item["ein"]),
                "origin": "entities.ein",
            }
        entities[item["id"]] = item

    if core.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = 'entity_addresses'
        """
    ).fetchone():
        for row in core.execute(
            "SELECT id, entity_id, address, address_type FROM entity_addresses"
        ):
            entity = entities.get(row["entity_id"])
            if entity is None or not row["address"]:
                continue
            entity["addresses"].append(
                {
                    "value": row["address"],
                    "normalized": normalize_address(row["address"]),
                    "origin": "entity_addresses.address",
                    "row_id": row["id"],
                    "address_type": row["address_type"],
                }
            )
    return entities


def _name_index(
    core: sqlite3.Connection, entities: Mapping[int, dict[str, Any]]
) -> dict[str, dict[int, list[dict[str, Any]]]]:
    index: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    entity_names: dict[str, list[int]] = defaultdict(list)
    for entity_id, entity in entities.items():
        normalized = normalize_name(entity["name"])
        entity_names[normalized].append(entity_id)
        index[normalized][entity_id].append(
            {
                "type": "entity_name_exact",
                "source_value": entity["name"],
                "entity_value": entity["name"],
                "normalized_value": normalized,
                "origin": "entities.name",
            }
        )

    if core.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = 'name_aliases'
        """
    ).fetchone():
        columns = _table_columns(core, "name_aliases")
        selected = ["id", "canonical_name", "alias"]
        if "alias_type" in columns:
            selected.append("alias_type")
        if "entity_id" in columns:
            selected.append("entity_id")
        for row in core.execute(
            f"SELECT {', '.join(selected)} FROM name_aliases ORDER BY id"
        ):
            alias = row["alias"]
            if not alias:
                continue
            normalized_alias = normalize_name(alias)
            direct_id = row["entity_id"] if "entity_id" in row.keys() else None
            if direct_id in entities:
                candidate_ids = [direct_id]
                resolution = "alias_entity_id"
            else:
                canonical = row["canonical_name"]
                candidate_ids = (
                    entity_names.get(normalize_name(canonical), [])
                    if canonical
                    else []
                )
                resolution = "alias_canonical_name"
            for entity_id in candidate_ids:
                index[normalized_alias][entity_id].append(
                    {
                        "type": "alias_exact",
                        "source_value": alias,
                        "entity_value": entities[entity_id]["name"],
                        "normalized_value": normalized_alias,
                        "origin": "name_aliases.alias",
                        "alias_id": row["id"],
                        "alias_type": (
                            row["alias_type"]
                            if "alias_type" in row.keys()
                            else None
                        ),
                        "alias_resolution": resolution,
                    }
                )
    return index


def _property_addresses(
    db: sqlite3.Connection, record_type: str, row: sqlite3.Row
) -> list[dict[str, Any]]:
    addresses: list[dict[str, Any]] = []
    spec = _RECORD_SPECS[record_type]
    direct_column = spec["address"]
    if direct_column and row[direct_column]:
        addresses.append(
            {
                "value": row[direct_column],
                "normalized": normalize_address(row[direct_column]),
                "origin": f"{record_type}.{direct_column}",
            }
        )
    parcel_ids: list[int] = []
    if record_type == "ownership_assertion":
        parcel_ids.append(row["parcel_id"])
    elif record_type == "instrument_party":
        if db.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'instrument_parcel'
            """
        ).fetchone():
            parcel_ids.extend(
                item["parcel_id"]
                for item in db.execute(
                    """
                    SELECT parcel_id FROM instrument_parcel
                    WHERE instrument_id = ?
                    """,
                    (row["instrument_id"],),
                )
            )
    if parcel_ids and db.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = 'parcel_address'
        """
    ).fetchone():
        marks = ",".join("?" for _ in parcel_ids)
        for address in db.execute(
            f"""
            SELECT address_id, parcel_id, address_role, raw_address
            FROM parcel_address WHERE parcel_id IN ({marks})
            ORDER BY address_id
            """,
            parcel_ids,
        ):
            if not address["raw_address"]:
                continue
            addresses.append(
                {
                    "value": address["raw_address"],
                    "normalized": normalize_address(address["raw_address"]),
                    "origin": "parcel_address.raw_address",
                    "address_id": address["address_id"],
                    "address_role": address["address_role"],
                    "parcel_id": address["parcel_id"],
                }
            )
    return addresses


def _source_identifiers(row: sqlite3.Row) -> dict[str, dict[str, Any]]:
    identifiers: dict[str, dict[str, Any]] = {}
    row_keys = set(row.keys())
    for column in _IDENTIFIER_COLUMNS:
        if column not in row_keys or row[column] in (None, ""):
            continue
        identifier_kind = _IDENTIFIER_KINDS.get(column, column)
        identifiers[identifier_kind] = {
            "value": row[column],
            "normalized": normalize_identifier(row[column]),
            "origin": column,
        }
    return identifiers


def _observe_records(
    sidecar_path: Path, record_types: Iterable[str]
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    with _open_readonly(sidecar_path) as db:
        for record_type in record_types:
            spec = _RECORD_SPECS[record_type]
            _require_table(db, record_type)
            columns = _table_columns(db, record_type)
            required = {
                spec["pk"],
                spec["name"],
                "core_entity_id",
            }
            missing = required - columns
            if missing:
                raise CandidateStoreError(
                    f"{record_type} is missing columns: {', '.join(sorted(missing))}"
                )
            for row in db.execute(
                f"SELECT * FROM {record_type} ORDER BY {spec['pk']}"
            ):
                raw_name = row[spec["name"]]
                if not raw_name or not str(raw_name).strip():
                    continue
                addresses = (
                    _property_addresses(db, record_type, row)
                    if spec["domain"] == "property"
                    else []
                )
                identifiers = _source_identifiers(row)
                snapshot = {
                    key: row[key]
                    for key in row.keys()
                    if isinstance(row[key], (str, int, float, bool, type(None)))
                }
                observations.append(
                    {
                        "domain": spec["domain"],
                        "record_type": record_type,
                        "table_name": record_type,
                        "primary_key_column": spec["pk"],
                        "row_id": row[spec["pk"]],
                        "raw_name": raw_name,
                        "normalized_name": normalize_name(raw_name),
                        "addresses": addresses,
                        "identifiers": identifiers,
                        "row_snapshot": snapshot,
                    }
                )
    return observations


def _corroborating_signals(
    observation: Mapping[str, Any], entity: Mapping[str, Any]
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for source_address in observation["addresses"]:
        for entity_address in entity["addresses"]:
            if (
                source_address["normalized"]
                and source_address["normalized"] == entity_address["normalized"]
            ):
                signals.append(
                    {
                        "type": "address_exact",
                        "normalized_value": source_address["normalized"],
                        "source": source_address,
                        "entity": entity_address,
                    }
                )
    for identifier_type, source_identifier in observation["identifiers"].items():
        entity_identifier = entity["identifiers"].get(identifier_type)
        if (
            entity_identifier
            and source_identifier["normalized"]
            and source_identifier["normalized"] == entity_identifier["normalized"]
        ):
            signals.append(
                {
                    "type": "identifier_exact",
                    "identifier_type": identifier_type,
                    "normalized_value": source_identifier["normalized"],
                    "source": source_identifier,
                    "entity": entity_identifier,
                }
            )
    return signals


class PublicRecordsEntityCandidates:
    """Candidate generator and append-only decision audit store."""

    def __init__(self, db_path: str | Path = DEFAULT_DB) -> None:
        self.db_path = Path(db_path)
        self.db = connect_candidate_db(self.db_path)

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> PublicRecordsEntityCandidates:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _get_or_create_source_record(
        self, observation: Mapping[str, Any], sidecar_path: Path
    ) -> sqlite3.Row:
        resolved_path = str(sidecar_path.resolve())
        existing = self.db.execute(
            """
            SELECT * FROM source_record
            WHERE sidecar_db_path = ? AND table_name = ? AND row_id = ?
            """,
            (
                resolved_path,
                observation["table_name"],
                observation["row_id"],
            ),
        ).fetchone()
        if existing is not None:
            return existing
        record_ref = (
            f"PRSRC:{observation['domain']}:{observation['record_type']}:"
            f"{observation['row_id']}:{_fingerprint(resolved_path)[:12]}"
        )
        cursor = self.db.execute(
            """
            INSERT INTO source_record(
                record_ref, domain, record_type, sidecar_db_path, table_name,
                primary_key_column, row_id, first_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_ref,
                observation["domain"],
                observation["record_type"],
                resolved_path,
                observation["table_name"],
                observation["primary_key_column"],
                observation["row_id"],
                utc_now_iso(),
            ),
        )
        return self.db.execute(
            "SELECT * FROM source_record WHERE source_record_id = ?",
            (cursor.lastrowid,),
        ).fetchone()

    def _record_source_observation(
        self,
        source_record_id: int,
        run_id: int,
        observation: Mapping[str, Any],
    ) -> tuple[sqlite3.Row, bool]:
        payload = {
            "raw_name": observation["raw_name"],
            "normalized_name": observation["normalized_name"],
            "addresses": observation["addresses"],
            "identifiers": observation["identifiers"],
            "row_snapshot": observation["row_snapshot"],
        }
        fingerprint = _fingerprint(payload)
        existing = self.db.execute(
            """
            SELECT * FROM source_record_observation
            WHERE source_record_id = ? AND observation_fingerprint = ?
            """,
            (source_record_id, fingerprint),
        ).fetchone()
        if existing is not None:
            return existing, False
        cursor = self.db.execute(
            """
            INSERT INTO source_record_observation(
                source_record_id, run_id, observed_at, raw_name,
                normalized_name, addresses_json, identifiers_json,
                row_snapshot_json, observation_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_record_id,
                run_id,
                utc_now_iso(),
                observation["raw_name"],
                observation["normalized_name"],
                canonical_json(observation["addresses"]),
                canonical_json(observation["identifiers"]),
                canonical_json(observation["row_snapshot"]),
                fingerprint,
            ),
        )
        return self.db.execute(
            """
            SELECT * FROM source_record_observation
            WHERE source_observation_id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone(), True

    def _get_or_create_candidate(
        self, source_record_id: int, core_path: Path, entity_id: int
    ) -> sqlite3.Row:
        resolved_core = str(core_path.resolve())
        existing = self.db.execute(
            """
            SELECT * FROM entity_candidate
            WHERE source_record_id = ? AND core_db_path = ?
              AND core_entity_id = ?
            """,
            (source_record_id, resolved_core, entity_id),
        ).fetchone()
        if existing is not None:
            return existing
        cursor = self.db.execute(
            """
            INSERT INTO entity_candidate(
                candidate_ref, source_record_id, core_db_path,
                core_entity_id, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                f"PRCAND:{uuid.uuid4()}",
                source_record_id,
                resolved_core,
                entity_id,
                utc_now_iso(),
            ),
        )
        candidate_id = cursor.lastrowid
        self.db.execute(
            """
            INSERT INTO candidate_projection(
                candidate_id, state, current_decision_id, updated_at
            ) VALUES (?, 'open', NULL, ?)
            """,
            (candidate_id, utc_now_iso()),
        )
        return self.db.execute(
            "SELECT * FROM entity_candidate WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()

    def generate(
        self,
        *,
        property_db: str | Path = DEFAULT_PROPERTY_DB,
        court_db: str | Path = DEFAULT_COURT_DB,
        core_db: str | Path = DEFAULT_CORE_DB,
        record_types: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Generate every exact normalized name/alias candidate and its signals."""

        selected = list(record_types or _RECORD_SPECS)
        unknown = set(selected) - set(_RECORD_SPECS)
        if unknown:
            raise ValueError(f"unknown record types: {', '.join(sorted(unknown))}")
        selected = list(dict.fromkeys(selected))
        property_path = Path(property_db)
        court_path = Path(court_db)
        core_path = Path(core_db)
        with _open_readonly(core_path) as core:
            entities = _core_entities(core)
            name_index = _name_index(core, entities)

        started_at = utc_now_iso()
        cursor = self.db.execute(
            """
            INSERT INTO generation_run(
                run_ref, started_at, property_db_path, court_db_path,
                core_db_path, record_types_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"PRRUN:{uuid.uuid4()}",
                started_at,
                str(property_path.resolve()) if property_path.exists() else None,
                str(court_path.resolve()) if court_path.exists() else None,
                str(core_path.resolve()),
                canonical_json(selected),
            ),
        )
        run_id = cursor.lastrowid
        observed: list[tuple[Path, dict[str, Any]]] = []
        property_types = [
            item for item in selected if _RECORD_SPECS[item]["domain"] == "property"
        ]
        court_types = [
            item for item in selected if _RECORD_SPECS[item]["domain"] == "court"
        ]
        if property_types:
            observed.extend(
                (property_path, item)
                for item in _observe_records(property_path, property_types)
            )
        if court_types:
            observed.extend(
                (court_path, item)
                for item in _observe_records(court_path, court_types)
            )

        candidate_observations = 0
        signal_observations_added = 0
        new_candidates = 0
        for sidecar_path, observation in observed:
            source_record = self._get_or_create_source_record(
                observation, sidecar_path
            )
            source_observation, _ = self._record_source_observation(
                source_record["source_record_id"], run_id, observation
            )
            matching = name_index.get(observation["normalized_name"], {})
            for entity_id, name_signals in matching.items():
                candidate_before = self.db.execute(
                    """
                    SELECT candidate_id FROM entity_candidate
                    WHERE source_record_id = ? AND core_db_path = ?
                      AND core_entity_id = ?
                    """,
                    (
                        source_record["source_record_id"],
                        str(core_path.resolve()),
                        entity_id,
                    ),
                ).fetchone()
                candidate = self._get_or_create_candidate(
                    source_record["source_record_id"], core_path, entity_id
                )
                if candidate_before is None:
                    new_candidates += 1
                signals = [*name_signals, *_corroborating_signals(
                    observation, entities[entity_id]
                )]
                entity_snapshot = {
                    key: value
                    for key, value in entities[entity_id].items()
                    if key in {
                        "id",
                        "name",
                        "entity_type",
                        "jurisdiction",
                        "address",
                        "ein",
                        "addresses",
                        "identifiers",
                    }
                }
                signal_payload = {
                    "source_observation_fingerprint": source_observation[
                        "observation_fingerprint"
                    ],
                    "entity": entity_snapshot,
                    "signals": signals,
                }
                signal_fingerprint = _fingerprint(signal_payload)
                existing = self.db.execute(
                    """
                    SELECT signal_observation_id
                    FROM candidate_signal_observation
                    WHERE candidate_id = ? AND signal_fingerprint = ?
                    """,
                    (candidate["candidate_id"], signal_fingerprint),
                ).fetchone()
                if existing is None:
                    self.db.execute(
                        """
                        INSERT INTO candidate_signal_observation(
                            candidate_id, run_id, source_observation_id,
                            observed_at, entity_snapshot_json, signals_json,
                            signal_fingerprint
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            candidate["candidate_id"],
                            run_id,
                            source_observation["source_observation_id"],
                            utc_now_iso(),
                            canonical_json(entity_snapshot),
                            canonical_json(signals),
                            signal_fingerprint,
                        ),
                    )
                    signal_observations_added += 1
                candidate_observations += 1

        completed_at = utc_now_iso()
        self.db.execute(
            """
            UPDATE generation_run SET
                completed_at = ?, records_observed = ?,
                candidates_observed = ?, signal_observations_added = ?
            WHERE run_id = ?
            """,
            (
                completed_at,
                len(observed),
                candidate_observations,
                signal_observations_added,
                run_id,
            ),
        )
        self.db.commit()
        return {
            "status": "ok",
            "run_id": run_id,
            "started_at": started_at,
            "completed_at": completed_at,
            "record_types": selected,
            "records_observed": len(observed),
            "candidate_observations": candidate_observations,
            "new_candidates": new_candidates,
            "signal_observations_added": signal_observations_added,
        }

    def _candidate_row(self, identifier: int | str) -> sqlite3.Row:
        if isinstance(identifier, int) or str(identifier).isdigit():
            row = self.db.execute(
                "SELECT * FROM entity_candidate WHERE candidate_id = ?",
                (int(identifier),),
            ).fetchone()
        else:
            row = self.db.execute(
                "SELECT * FROM entity_candidate WHERE candidate_ref = ?",
                (str(identifier),),
            ).fetchone()
        if row is None:
            raise CandidateNotFoundError(f"candidate not found: {identifier}")
        return row

    def _candidate_context(self, identifier: int | str) -> dict[str, Any]:
        candidate = self._candidate_row(identifier)
        row = self.db.execute(
            """
            SELECT
                c.*, p.state, p.current_decision_id, p.updated_at,
                sr.record_ref, sr.domain, sr.record_type,
                sr.sidecar_db_path, sr.table_name, sr.primary_key_column,
                sr.row_id
            FROM entity_candidate c
            JOIN candidate_projection p ON p.candidate_id = c.candidate_id
            JOIN source_record sr ON sr.source_record_id = c.source_record_id
            WHERE c.candidate_id = ?
            """,
            (candidate["candidate_id"],),
        ).fetchone()
        return dict(row)

    def _latest_source_observation(self, source_record_id: int) -> dict[str, Any]:
        row = self.db.execute(
            """
            SELECT * FROM source_record_observation
            WHERE source_record_id = ?
            ORDER BY source_observation_id DESC LIMIT 1
            """,
            (source_record_id,),
        ).fetchone()
        if row is None:
            raise CandidateStoreError("candidate has no source observation")
        return _row_to_dict(row) or {}

    def _latest_signal_observation(self, candidate_id: int) -> dict[str, Any]:
        row = self.db.execute(
            """
            SELECT * FROM candidate_signal_observation
            WHERE candidate_id = ?
            ORDER BY signal_observation_id DESC LIMIT 1
            """,
            (candidate_id,),
        ).fetchone()
        if row is None:
            raise CandidateStoreError("candidate has no signal observation")
        return _row_to_dict(row) or {}

    @staticmethod
    def _sidecar_state(
        db: sqlite3.Connection, context: Mapping[str, Any]
    ) -> dict[str, Any]:
        spec = _RECORD_SPECS[context["record_type"]]
        columns = ["core_entity_id"]
        for column_key in ("resolution_confidence", "resolution_status"):
            column = spec[column_key]
            if column:
                columns.append(column)
        row = db.execute(
            f"""
            SELECT {', '.join(columns)}
            FROM target_sidecar.{context['table_name']}
            WHERE {context['primary_key_column']} = ?
            """,
            (context["row_id"],),
        ).fetchone()
        if row is None:
            raise CandidateNotFoundError(
                f"source row no longer exists: {context['record_ref']}"
            )
        state = {"core_entity_id": row["core_entity_id"]}
        for column_key in ("resolution_confidence", "resolution_status"):
            column = spec[column_key]
            if column:
                state[column_key] = row[column]
        return state

    @staticmethod
    def _update_sidecar_state(
        db: sqlite3.Connection,
        context: Mapping[str, Any],
        state: Mapping[str, Any],
    ) -> None:
        spec = _RECORD_SPECS[context["record_type"]]
        assignments = ["core_entity_id = ?"]
        values: list[Any] = [state.get("core_entity_id")]
        for column_key in ("resolution_confidence", "resolution_status"):
            column = spec[column_key]
            if column:
                assignments.append(f"{column} = ?")
                values.append(state.get(column_key))
        values.append(context["row_id"])
        cursor = db.execute(
            f"""
            UPDATE target_sidecar.{context['table_name']}
            SET {', '.join(assignments)}
            WHERE {context['primary_key_column']} = ?
            """,
            values,
        )
        if cursor.rowcount != 1:
            raise CandidateNotFoundError(
                f"source row no longer exists: {context['record_ref']}"
            )

    def _attach_sidecar(self, path: str) -> None:
        self.db.commit()
        self.db.execute("ATTACH DATABASE ? AS target_sidecar", (path,))
        self.db.row_factory = sqlite3.Row

    def _detach_sidecar(self) -> None:
        self.db.execute("DETACH DATABASE target_sidecar")

    def _insert_decision(
        self,
        context: Mapping[str, Any],
        *,
        action: str,
        resulting_state: str,
        actor: str,
        reason: str | None,
        resolution_confidence: float | None,
        metadata: Mapping[str, Any],
        undo_of_decision_id: int | None = None,
    ) -> int:
        cursor = self.db.execute(
            """
            INSERT INTO decision_event(
                decision_ref, candidate_id, action, previous_state,
                resulting_state, actor, reason, resolution_confidence,
                decided_at, metadata_json, previous_decision_id,
                undo_of_decision_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"PRDEC:{uuid.uuid4()}",
                context["candidate_id"],
                action,
                context["state"],
                resulting_state,
                _require_text(actor, "actor"),
                _optional_text(reason, "reason"),
                resolution_confidence,
                utc_now_iso(),
                canonical_json(metadata),
                context["current_decision_id"],
                undo_of_decision_id,
            ),
        )
        return cursor.lastrowid

    def _project_decision(
        self, candidate_id: int, state: str, decision_id: int
    ) -> None:
        self.db.execute(
            """
            UPDATE candidate_projection
            SET state = ?, current_decision_id = ?, updated_at = ?
            WHERE candidate_id = ?
            """,
            (state, decision_id, utc_now_iso(), candidate_id),
        )

    def decide(
        self,
        identifier: int | str,
        *,
        action: str,
        actor: str,
        reason: str | None = None,
        resolution_confidence: float | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an explicit candidate decision and apply reversible links."""

        normalized_action = _require_text(action, "action").lower()
        if normalized_action not in {"accept", "reject", "reopen", "undo"}:
            raise ValueError("action must be accept, reject, reopen, or undo")
        normalized_metadata = _normalize_mapping(metadata, "metadata")
        if resolution_confidence is not None:
            if (
                isinstance(resolution_confidence, bool)
                or not isinstance(resolution_confidence, (int, float))
                or not math.isfinite(float(resolution_confidence))
                or not 0.0 <= float(resolution_confidence) <= 1.0
            ):
                raise ValueError("resolution_confidence must be from 0 to 1")
            resolution_confidence = float(resolution_confidence)
        context = self._candidate_context(identifier)

        if normalized_action == "accept":
            if context["state"] == "accepted":
                raise DecisionConflictError("candidate is already accepted")
            return self._accept(
                context,
                actor=actor,
                reason=reason,
                resolution_confidence=resolution_confidence,
                metadata=normalized_metadata,
            )
        if normalized_action == "reject":
            if context["state"] == "accepted":
                raise DecisionConflictError(
                    "undo the accepted link before recording a rejection"
                )
            if context["state"] == "rejected":
                raise DecisionConflictError("candidate is already rejected")
            decision_id = self._insert_decision(
                context,
                action="reject",
                resulting_state="rejected",
                actor=actor,
                reason=reason,
                resolution_confidence=None,
                metadata=normalized_metadata,
            )
            self._project_decision(context["candidate_id"], "rejected", decision_id)
            self.db.commit()
            return self.history(identifier, decision_id=decision_id)
        if normalized_action == "reopen":
            if context["state"] != "rejected":
                raise DecisionConflictError(
                    "reopen applies to a rejected candidate"
                )
            decision_id = self._insert_decision(
                context,
                action="reopen",
                resulting_state="open",
                actor=actor,
                reason=reason,
                resolution_confidence=None,
                metadata=normalized_metadata,
            )
            self._project_decision(context["candidate_id"], "open", decision_id)
            self.db.commit()
            return self.history(identifier, decision_id=decision_id)
        return self._undo(
            context,
            actor=actor,
            reason=reason,
            metadata=normalized_metadata,
        )

    def _accept(
        self,
        context: Mapping[str, Any],
        *,
        actor: str,
        reason: str | None,
        resolution_confidence: float | None,
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        core_path = Path(context["core_db_path"])
        with _open_readonly(core_path) as core:
            if core.execute(
                "SELECT 1 FROM entities WHERE id = ?",
                (context["core_entity_id"],),
            ).fetchone() is None:
                raise CandidateNotFoundError(
                    f"core entity no longer exists: {context['core_entity_id']}"
                )
        self._attach_sidecar(context["sidecar_db_path"])
        try:
            self.db.execute("BEGIN IMMEDIATE")
            prior_state = self._sidecar_state(self.db, context)
            new_state = dict(prior_state)
            new_state["core_entity_id"] = context["core_entity_id"]
            spec = _RECORD_SPECS[context["record_type"]]
            if spec["resolution_confidence"]:
                new_state["resolution_confidence"] = resolution_confidence
            if spec["resolution_status"]:
                new_state["resolution_status"] = "accepted_candidate"
            decision_id = self._insert_decision(
                context,
                action="accept",
                resulting_state="accepted",
                actor=actor,
                reason=reason,
                resolution_confidence=resolution_confidence,
                metadata=metadata,
            )
            self._update_sidecar_state(self.db, context, new_state)
            self.db.execute(
                """
                INSERT INTO link_mutation_event(
                    mutation_ref, decision_id, candidate_id, source_record_id,
                    mutation_type, sidecar_db_path, table_name,
                    primary_key_column, row_id, prior_state_json,
                    new_state_json, applied_at
                ) VALUES (?, ?, ?, ?, 'accept', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"PRLINK:{uuid.uuid4()}",
                    decision_id,
                    context["candidate_id"],
                    context["source_record_id"],
                    context["sidecar_db_path"],
                    context["table_name"],
                    context["primary_key_column"],
                    context["row_id"],
                    canonical_json(prior_state),
                    canonical_json(new_state),
                    utc_now_iso(),
                ),
            )
            self._project_decision(
                context["candidate_id"], "accepted", decision_id
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        finally:
            self._detach_sidecar()
        return self.history(context["candidate_id"], decision_id=decision_id)

    def _undo(
        self,
        context: Mapping[str, Any],
        *,
        actor: str,
        reason: str | None,
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        current_decision_id = context["current_decision_id"]
        if current_decision_id is None:
            raise DecisionConflictError("candidate has no decision to undo")
        target = self.db.execute(
            "SELECT * FROM decision_event WHERE decision_id = ?",
            (current_decision_id,),
        ).fetchone()
        assert target is not None
        resulting_state = target["previous_state"]
        mutation = self.db.execute(
            """
            SELECT * FROM link_mutation_event
            WHERE decision_id = ? ORDER BY mutation_id DESC LIMIT 1
            """,
            (current_decision_id,),
        ).fetchone()
        if mutation is None:
            decision_id = self._insert_decision(
                context,
                action="undo",
                resulting_state=resulting_state,
                actor=actor,
                reason=reason,
                resolution_confidence=None,
                metadata=metadata,
                undo_of_decision_id=current_decision_id,
            )
            self._project_decision(
                context["candidate_id"], resulting_state, decision_id
            )
            self.db.commit()
            return self.history(context["candidate_id"], decision_id=decision_id)

        prior_state = json.loads(mutation["prior_state_json"])
        applied_state = json.loads(mutation["new_state_json"])
        self._attach_sidecar(context["sidecar_db_path"])
        try:
            self.db.execute("BEGIN IMMEDIATE")
            current_sidecar_state = self._sidecar_state(self.db, context)
            if current_sidecar_state != applied_state:
                raise DecisionConflictError(
                    "sidecar link changed after this decision; undo newer link "
                    "changes first"
                )
            decision_id = self._insert_decision(
                context,
                action="undo",
                resulting_state=resulting_state,
                actor=actor,
                reason=reason,
                resolution_confidence=None,
                metadata=metadata,
                undo_of_decision_id=current_decision_id,
            )
            self._update_sidecar_state(self.db, context, prior_state)
            self.db.execute(
                """
                INSERT INTO link_mutation_event(
                    mutation_ref, decision_id, candidate_id, source_record_id,
                    mutation_type, sidecar_db_path, table_name,
                    primary_key_column, row_id, prior_state_json,
                    new_state_json, reverses_mutation_id, applied_at
                ) VALUES (?, ?, ?, ?, 'undo', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"PRLINK:{uuid.uuid4()}",
                    decision_id,
                    context["candidate_id"],
                    context["source_record_id"],
                    context["sidecar_db_path"],
                    context["table_name"],
                    context["primary_key_column"],
                    context["row_id"],
                    canonical_json(current_sidecar_state),
                    canonical_json(prior_state),
                    mutation["mutation_id"],
                    utc_now_iso(),
                ),
            )
            self._project_decision(
                context["candidate_id"], resulting_state, decision_id
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        finally:
            self._detach_sidecar()
        return self.history(context["candidate_id"], decision_id=decision_id)

    def list_candidates(
        self,
        *,
        state: str | None = None,
        record_type: str | None = None,
        core_entity_id: int | None = None,
        name: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List candidates with their latest raw observation and all signals."""

        if record_type is not None and record_type not in _RECORD_SPECS:
            raise ValueError(f"unknown record type: {record_type}")
        if limit is not None and limit < 1:
            raise ValueError("limit must be a positive integer")
        clauses: list[str] = []
        parameters: list[Any] = []
        if state is not None:
            clauses.append("p.state = ?")
            parameters.append(_require_text(state, "state"))
        if record_type is not None:
            clauses.append("sr.record_type = ?")
            parameters.append(record_type)
        if core_entity_id is not None:
            clauses.append("c.core_entity_id = ?")
            parameters.append(core_entity_id)
        if name is not None:
            clauses.append("lower(sro.raw_name) LIKE lower(?)")
            parameters.append(f"%{_require_text(name, 'name')}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT
                c.*, p.state, p.current_decision_id, p.updated_at,
                sr.record_ref, sr.domain, sr.record_type,
                sr.sidecar_db_path, sr.table_name, sr.primary_key_column,
                sr.row_id,
                sro.raw_name, sro.normalized_name, sro.addresses_json,
                sro.identifiers_json, sro.row_snapshot_json,
                cso.entity_snapshot_json, cso.signals_json,
                cso.signal_fingerprint
            FROM entity_candidate c
            JOIN candidate_projection p ON p.candidate_id = c.candidate_id
            JOIN source_record sr ON sr.source_record_id = c.source_record_id
            JOIN source_record_observation sro
              ON sro.source_observation_id = (
                SELECT MAX(sro2.source_observation_id)
                FROM source_record_observation sro2
                WHERE sro2.source_record_id = sr.source_record_id
              )
            JOIN candidate_signal_observation cso
              ON cso.signal_observation_id = (
                SELECT MAX(cso2.signal_observation_id)
                FROM candidate_signal_observation cso2
                WHERE cso2.candidate_id = c.candidate_id
              )
            {where}
            ORDER BY c.candidate_id
        """
        if limit is not None:
            query += " LIMIT ?"
            parameters.append(limit)
        return [
            _row_to_dict(row) or {}
            for row in self.db.execute(query, parameters).fetchall()
        ]

    def history(
        self, identifier: int | str, *, decision_id: int | None = None
    ) -> dict[str, Any]:
        """Return candidate observations, decisions, and reversible mutations."""

        context = self._candidate_context(identifier)
        decisions = [
            _row_to_dict(row) or {}
            for row in self.db.execute(
                """
                SELECT * FROM decision_event
                WHERE candidate_id = ? ORDER BY decision_id
                """,
                (context["candidate_id"],),
            )
        ]
        mutations = [
            _row_to_dict(row) or {}
            for row in self.db.execute(
                """
                SELECT * FROM link_mutation_event
                WHERE candidate_id = ? ORDER BY mutation_id
                """,
                (context["candidate_id"],),
            )
        ]
        signals = [
            _row_to_dict(row) or {}
            for row in self.db.execute(
                """
                SELECT * FROM candidate_signal_observation
                WHERE candidate_id = ? ORDER BY signal_observation_id
                """,
                (context["candidate_id"],),
            )
        ]
        result = {
            "status": "ok",
            "candidate": context,
            "source_observation": self._latest_source_observation(
                context["source_record_id"]
            ),
            "latest_signal_observation": self._latest_signal_observation(
                context["candidate_id"]
            ),
            "signal_history": signals,
            "decisions": decisions,
            "link_mutations": mutations,
        }
        if decision_id is not None:
            result["decision"] = next(
                item for item in decisions if item["decision_id"] == decision_id
            )
        return result


def _parse_json_argument(value: str | None, field_name: str) -> Any:
    if value is None:
        return {}
    raw = value
    if raw.startswith("@"):
        raw = Path(raw[1:]).read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} is not valid JSON: {exc.msg}") from exc


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db", default=str(DEFAULT_DB), help=f"Candidate DB (default: {DEFAULT_DB})"
    )
    add_output_args(parser)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reversible public-record entity candidate workflow"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser(
        "generate", help="Generate candidates from public-record sidecars"
    )
    generate.add_argument("--property-db", default=str(DEFAULT_PROPERTY_DB))
    generate.add_argument("--court-db", default=str(DEFAULT_COURT_DB))
    generate.add_argument("--core-db", default=str(DEFAULT_CORE_DB))
    generate.add_argument(
        "--record-type",
        action="append",
        choices=tuple(_RECORD_SPECS),
        dest="record_types",
        help="Record type to scan; repeat as needed (default: all)",
    )
    _add_common(generate)

    list_parser = subparsers.add_parser("list", help="List candidates")
    list_parser.add_argument("--status", dest="state")
    list_parser.add_argument("--record-type", choices=tuple(_RECORD_SPECS))
    list_parser.add_argument("--core-entity-id", type=int)
    list_parser.add_argument("--name")
    list_parser.add_argument(
        "--limit", type=int, help="Maximum candidates to return (default: all)"
    )
    _add_common(list_parser)

    decide = subparsers.add_parser(
        "decide", help="Accept, reject, reopen, or undo a candidate decision"
    )
    decide.add_argument("candidate")
    decide.add_argument(
        "--action", choices=("accept", "reject", "reopen", "undo"), required=True
    )
    decide.add_argument("--actor", required=True)
    decide.add_argument("--reason")
    decide.add_argument("--resolution-confidence", type=float)
    decide.add_argument("--metadata-json", default="{}")
    _add_common(decide)

    history = subparsers.add_parser(
        "history", help="Show candidate signals and decision history"
    )
    history.add_argument("candidate")
    _add_common(history)
    return parser


def _emit(data: Any, args: argparse.Namespace, summary: str) -> None:
    if write_output(data, args, summary=summary):
        return
    print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))


def _run(args: argparse.Namespace) -> tuple[Any, str]:
    with PublicRecordsEntityCandidates(args.db) as store:
        if args.command == "generate":
            payload = store.generate(
                property_db=args.property_db,
                court_db=args.court_db,
                core_db=args.core_db,
                record_types=args.record_types,
            )
            return payload, (
                f"generated {payload['candidate_observations']} candidate observations"
            )
        if args.command == "list":
            candidates = store.list_candidates(
                state=args.state,
                record_type=args.record_type,
                core_entity_id=args.core_entity_id,
                name=args.name,
                limit=args.limit,
            )
            return {
                "status": "ok",
                "count": len(candidates),
                "candidates": candidates,
            }, f"listed {len(candidates)} candidates"
        if args.command == "decide":
            payload = store.decide(
                args.candidate,
                action=args.action,
                actor=args.actor,
                reason=args.reason,
                resolution_confidence=args.resolution_confidence,
                metadata=_parse_json_argument(args.metadata_json, "metadata"),
            )
            return payload, f"{args.action} decision recorded"
        if args.command == "history":
            return store.history(args.candidate), "candidate history"
    raise ValueError(f"unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        payload, summary = _run(args)
        _emit(payload, args, summary)
        return 0
    except (
        CandidateStoreError,
        FileNotFoundError,
        OSError,
        StopIteration,
        TypeError,
        ValueError,
        sqlite3.Error,
    ) as exc:
        _emit(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
            args,
            f"{args.command} failed",
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
