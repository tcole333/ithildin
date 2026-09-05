#!/usr/bin/env python3
"""Persist and assess Oregon local-court source discovery candidates.

The queue consumes complete ``discovery`` envelopes from
``query_oregon_court_directories.py``.  One row represents one registry court,
while URL observations are retained separately so a website move does not
replace the court's identity or its assessment history.

Examples:
    uv run python tools/oregon_court_discovery_queue.py sync
    uv run python tools/oregon_court_discovery_queue.py list --state active
    uv run python tools/oregon_court_discovery_queue.py claim 12 --by agent:name
    uv run python tools/oregon_court_discovery_queue.py assess 12 \
        --by agent:name --case-search @/tmp/case-search.json
    uv run python tools/oregon_court_discovery_queue.py promote 12 \
        --infra-request-id 300 --by agent:name
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB,
        PublicRecordsCatalog,
        normalize_timestamp,
        utc_now,
    )
    from tools.public_records_contract import canonical_json, sha256_fingerprint
    from tools.query_oregon_court_directories import (
        DEFAULT_MAX_ATTEMPTS,
        DEFAULT_MINIMUM_INTERVAL,
        DEFAULT_TIMEOUT,
        LOCAL_COURT_SOURCE_ID,
        execute as execute_directory,
    )
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB,
        PublicRecordsCatalog,
        normalize_timestamp,
        utc_now,
    )
    from public_records_contract import canonical_json, sha256_fingerprint
    from query_oregon_court_directories import (
        DEFAULT_MAX_ATTEMPTS,
        DEFAULT_MINIMUM_INTERVAL,
        DEFAULT_TIMEOUT,
        LOCAL_COURT_SOURCE_ID,
        execute as execute_directory,
    )


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INVESTIGATION_DB = PROJECT_ROOT / "investigation.db"
DISCOVERY_SCHEMA_VERSION = 1
QUEUE_STATES = ("active", "stale")
ASSESSMENT_FIELDS = (
    "case_search",
    "calendars",
    "registers_dockets",
    "opinions_orders",
    "request_routes",
    "bulk_products",
    "vendor_family",
)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS oregon_court_discovery_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oregon_court_discovery_candidate (
    candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stable_key TEXT NOT NULL,
    registry_source_id TEXT NOT NULL,
    registry_source_url TEXT,
    registry_list_name TEXT,
    registry_view_id TEXT,
    sharepoint_item_id TEXT,
    sharepoint_unique_id TEXT,
    court_canonical_ref TEXT,
    court_native_id TEXT,
    court_name TEXT,
    court_types_json TEXT NOT NULL DEFAULT '[]',
    counties_json TEXT NOT NULL DEFAULT '[]',
    city TEXT,
    current_url TEXT,
    current_host TEXT,
    state TEXT NOT NULL DEFAULT 'active',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    stale_at TEXT,
    claimed_by TEXT,
    claimed_at TEXT,
    identity_basis_json TEXT NOT NULL DEFAULT '{}',
    provenance_json TEXT NOT NULL DEFAULT '{}',
    raw_candidate_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oregon_court_discovery_url (
    candidate_url_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL
        REFERENCES oregon_court_discovery_candidate(candidate_id)
        ON DELETE CASCADE,
    url TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    host TEXT,
    state TEXT NOT NULL DEFAULT 'active',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    stale_at TEXT,
    UNIQUE(candidate_id, normalized_url)
);

CREATE TABLE IF NOT EXISTS oregon_court_discovery_assessment (
    candidate_id INTEGER PRIMARY KEY
        REFERENCES oregon_court_discovery_candidate(candidate_id)
        ON DELETE CASCADE,
    case_search_json TEXT NOT NULL DEFAULT '{}',
    calendars_json TEXT NOT NULL DEFAULT '{}',
    registers_dockets_json TEXT NOT NULL DEFAULT '{}',
    opinions_orders_json TEXT NOT NULL DEFAULT '{}',
    request_routes_json TEXT NOT NULL DEFAULT '{}',
    bulk_products_json TEXT NOT NULL DEFAULT '{}',
    vendor_family_json TEXT NOT NULL DEFAULT '{}',
    complements_json TEXT NOT NULL DEFAULT '[]',
    summary TEXT,
    assessed_by TEXT NOT NULL,
    assessed_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oregon_court_discovery_infra_link (
    candidate_id INTEGER NOT NULL
        REFERENCES oregon_court_discovery_candidate(candidate_id)
        ON DELETE CASCADE,
    infra_request_id INTEGER NOT NULL,
    infra_title TEXT,
    infra_status_at_link TEXT,
    notes TEXT,
    linked_by TEXT NOT NULL,
    linked_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(candidate_id, infra_request_id)
);

CREATE TABLE IF NOT EXISTS oregon_court_discovery_event (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER
        REFERENCES oregon_court_discovery_candidate(candidate_id)
        ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    actor TEXT,
    event_at TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS oregon_court_discovery_sync (
    sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    source_status TEXT NOT NULL,
    candidate_count INTEGER NOT NULL,
    active_count INTEGER NOT NULL,
    stale_count INTEGER NOT NULL,
    envelope_sha256 TEXT NOT NULL,
    query_fingerprint TEXT,
    schema_fingerprint TEXT,
    details_json TEXT NOT NULL DEFAULT '{}'
);
"""

INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS
    uq_oregon_court_discovery_candidate_stable_key
ON oregon_court_discovery_candidate(stable_key);

CREATE INDEX IF NOT EXISTS
    idx_oregon_court_discovery_candidate_state
ON oregon_court_discovery_candidate(state, court_name, candidate_id);

CREATE INDEX IF NOT EXISTS
    idx_oregon_court_discovery_candidate_claim
ON oregon_court_discovery_candidate(claimed_by, claimed_at);

CREATE INDEX IF NOT EXISTS
    idx_oregon_court_discovery_url_state
ON oregon_court_discovery_url(candidate_id, state);

CREATE INDEX IF NOT EXISTS
    idx_oregon_court_discovery_event_candidate
ON oregon_court_discovery_event(candidate_id, event_id);
"""


class OregonCourtDiscoveryQueueError(ValueError):
    """Raised when queue input or lifecycle state is inconsistent."""


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split()).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise OregonCourtDiscoveryQueueError(f"{field_name} is required")
    return normalized


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OregonCourtDiscoveryQueueError(f"{field_name} must be an object")
    return value


def _sequence(value: Any, field_name: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise OregonCourtDiscoveryQueueError(f"{field_name} must be a list")
    return value


def _json_object(value: Any, field_name: str) -> dict[str, Any]:
    return dict(_mapping(value, field_name))


def _json_object_list(value: Any, field_name: str) -> list[dict[str, Any]]:
    return [
        dict(_mapping(item, f"{field_name}[{index}]"))
        for index, item in enumerate(_sequence(value, field_name))
    ]


def _json_load(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise OregonCourtDiscoveryQueueError(
            "persisted queue JSON is invalid"
        ) from error


def _normalized_timestamp(value: str | None = None) -> str:
    return normalize_timestamp(value or utc_now(), "timestamp")


def normalize_candidate_url(value: Any) -> tuple[str, str | None]:
    """Return a comparison-safe URL and lowercase host."""

    url = _required_text(value, "candidate_url")
    parsed = urlsplit(url)
    scheme = parsed.scheme.casefold()
    host = (parsed.hostname or "").casefold()
    if scheme not in {"http", "https"} or not host:
        raise OregonCourtDiscoveryQueueError(
            f"candidate_url is not an HTTP(S) URL: {url}"
        )
    port = parsed.port
    netloc = host
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    path = parsed.path.rstrip("/") or ""
    normalized = urlunsplit((scheme, netloc, path, parsed.query, parsed.fragment))
    return normalized, host


def candidate_stable_identity(
    candidate: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Derive a registry identity that excludes the court website URL."""

    supplied_key = _text(candidate.get("registry_candidate_key"))
    registry_identity = candidate.get("registry_identity")
    if supplied_key and isinstance(registry_identity, Mapping):
        return supplied_key, dict(registry_identity)

    court = _mapping(candidate.get("court"), "candidate.court")
    provenance = _mapping(
        candidate.get("discovered_from"),
        "candidate.discovered_from",
    )
    source_id = (
        _text(provenance.get("source_id"))
        or _text(candidate.get("source_id"))
        or LOCAL_COURT_SOURCE_ID
    )
    list_name = _text(provenance.get("list_name"))
    unique_id = _text(provenance.get("sharepoint_unique_id"))
    item_id = _text(provenance.get("sharepoint_item_id"))
    court_ref = _text(court.get("canonical_ref"))
    if unique_id:
        basis = {
            "kind": "sharepoint_unique_id",
            "source_id": source_id,
            "list_name": list_name,
            "sharepoint_unique_id": unique_id,
        }
    elif court_ref:
        basis = {
            "kind": "court_canonical_ref",
            "source_id": source_id,
            "list_name": list_name,
            "court_canonical_ref": court_ref,
        }
    elif item_id:
        basis = {
            "kind": "sharepoint_item_id",
            "source_id": source_id,
            "list_name": list_name,
            "sharepoint_item_id": item_id,
        }
    else:
        basis = {
            "kind": "semantic_fallback",
            "source_id": source_id,
            "list_name": list_name,
            "court_name": _text(court.get("name")),
            "court_types": list(court.get("court_types") or []),
            "counties": list(court.get("counties") or []),
            "city": _text(court.get("city")),
        }
    return (
        f"ORCOURTDIR-DISCOVERY-COURT:{sha256_fingerprint(basis)}",
        basis,
    )


def _candidate_snapshot(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    court = _mapping(candidate.get("court"), "candidate.court")
    provenance = _mapping(
        candidate.get("discovered_from"),
        "candidate.discovered_from",
    )
    stable_key, identity_basis = candidate_stable_identity(candidate)
    normalized_url, host = normalize_candidate_url(candidate.get("candidate_url"))
    court_types = [
        _required_text(value, "candidate.court.court_types[]")
        for value in _sequence(
            court.get("court_types") or [],
            "candidate.court.court_types",
        )
    ]
    counties = [
        _required_text(value, "candidate.court.counties[]")
        for value in _sequence(
            court.get("counties") or [],
            "candidate.court.counties",
        )
    ]
    source_id = (
        _text(provenance.get("source_id"))
        or _text(candidate.get("source_id"))
        or LOCAL_COURT_SOURCE_ID
    )
    return {
        "stable_key": stable_key,
        "identity_basis": identity_basis,
        "registry_source_id": source_id,
        "registry_source_url": _text(provenance.get("source_url")),
        "registry_list_name": _text(provenance.get("list_name")),
        "registry_view_id": _text(provenance.get("view_id")),
        "sharepoint_item_id": _text(provenance.get("sharepoint_item_id")),
        "sharepoint_unique_id": _text(provenance.get("sharepoint_unique_id")),
        "court_canonical_ref": _text(court.get("canonical_ref")),
        "court_native_id": _text(court.get("native_id")),
        "court_name": _text(court.get("name")),
        "court_types": court_types,
        "counties": counties,
        "city": _text(court.get("city")),
        "url": _required_text(
            candidate.get("candidate_url"),
            "candidate.candidate_url",
        ),
        "normalized_url": normalized_url,
        "host": host,
        "provenance": dict(provenance),
        "raw_candidate": dict(candidate),
    }


def _complete_discovery_envelope(
    payload: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], str, str, str | None, str | None]:
    status = _required_text(payload.get("status"), "payload.status")
    if status not in {"ok", "no_results"}:
        raise OregonCourtDiscoveryQueueError(
            f"sync requires an ok or no_results envelope, got {status}"
        )
    if payload.get("next_cursor") is not None:
        raise OregonCourtDiscoveryQueueError(
            "sync requires the complete discovery snapshot without a cursor"
        )
    query_wrapper = _mapping(payload.get("query"), "payload.query")
    source = _mapping(query_wrapper.get("source"), "payload.query.source")
    source_id = _required_text(
        source.get("source_id"),
        "payload.query.source.source_id",
    )
    if source_id != LOCAL_COURT_SOURCE_ID:
        raise OregonCourtDiscoveryQueueError(
            f"sync requires source {LOCAL_COURT_SOURCE_ID}, got {source_id}"
        )
    query = _mapping(query_wrapper.get("query"), "payload.query.query")
    if query.get("operation") != "discovery":
        raise OregonCourtDiscoveryQueueError(
            "sync input must come from the discovery operation"
        )
    parameters = _mapping(
        query.get("parameters") or {},
        "payload.query.query.parameters",
    )
    if _text(parameters.get("query")) is not None:
        raise OregonCourtDiscoveryQueueError(
            "filtered discovery output cannot retire queue candidates"
        )
    if query.get("requested_limit") is not None or query.get("cursor") is not None:
        raise OregonCourtDiscoveryQueueError(
            "paginated discovery output cannot retire queue candidates"
        )
    records = [
        _mapping(record, f"payload.records[{index}]")
        for index, record in enumerate(
            _sequence(payload.get("records"), "payload.records")
        )
    ]
    for record in records:
        if record.get("record_kind") != "source_discovery_candidate":
            raise OregonCourtDiscoveryQueueError(
                "discovery envelope contains a non-candidate record"
            )
    retrieved_at = _normalized_timestamp(_text(payload.get("retrieved_at")))
    return (
        records,
        source_id,
        status,
        _text(query_wrapper.get("fingerprint")),
        retrieved_at,
    )


class OregonCourtDiscoveryQueue:
    """SQLite-backed renewable queue for official local-court websites."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_CATALOG_DB,
        *,
        initialize: bool = True,
    ) -> None:
        self.db_path = Path(db_path)
        if initialize:
            self.initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.db_path), timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def initialize(self) -> dict[str, Any]:
        """Create queue tables alongside the existing public-record catalog."""

        PublicRecordsCatalog(self.db_path)
        db = self._connect()
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA_SQL)
            db.executescript(INDEX_SQL)
            db.execute(
                """
                INSERT INTO oregon_court_discovery_meta(key, value)
                VALUES('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (str(DISCOVERY_SCHEMA_VERSION),),
            )
            db.commit()
        finally:
            db.close()
        return {
            "status": "initialized",
            "db_path": str(self.db_path),
            "schema_version": DISCOVERY_SCHEMA_VERSION,
        }

    @staticmethod
    def _event(
        db: sqlite3.Connection,
        *,
        candidate_id: int | None,
        event_type: str,
        actor: str | None,
        event_at: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        db.execute(
            """
            INSERT INTO oregon_court_discovery_event(
                candidate_id, event_type, actor, event_at, details_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                event_type,
                actor,
                event_at,
                canonical_json(dict(details or {})),
            ),
        )

    @staticmethod
    def _selector_row(
        db: sqlite3.Connection,
        selector: str | int,
    ) -> sqlite3.Row:
        value = str(selector).strip()
        if value.isdigit():
            row = db.execute(
                """
                SELECT * FROM oregon_court_discovery_candidate
                WHERE candidate_id=?
                """,
                (int(value),),
            ).fetchone()
        else:
            row = db.execute(
                """
                SELECT * FROM oregon_court_discovery_candidate
                WHERE stable_key=?
                """,
                (value,),
            ).fetchone()
        if row is None:
            raise OregonCourtDiscoveryQueueError(
                f"unknown Oregon court discovery candidate: {selector}"
            )
        return row

    @staticmethod
    def _assessment(
        db: sqlite3.Connection,
        candidate_id: int,
    ) -> dict[str, Any] | None:
        row = db.execute(
            """
            SELECT * FROM oregon_court_discovery_assessment
            WHERE candidate_id=?
            """,
            (candidate_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            field: _json_load(row[f"{field}_json"], {}) for field in ASSESSMENT_FIELDS
        } | {
            "complements": _json_load(row["complements_json"], []),
            "summary": row["summary"],
            "assessed_by": row["assessed_by"],
            "assessed_at": row["assessed_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _links(
        db: sqlite3.Connection,
        candidate_id: int,
    ) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in db.execute(
                """
                SELECT infra_request_id, infra_title, infra_status_at_link,
                       notes, linked_by, linked_at, updated_at
                FROM oregon_court_discovery_infra_link
                WHERE candidate_id=?
                ORDER BY infra_request_id
                """,
                (candidate_id,),
            ).fetchall()
        ]

    @staticmethod
    def _urls(
        db: sqlite3.Connection,
        candidate_id: int,
    ) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in db.execute(
                """
                SELECT candidate_url_id, url, normalized_url, host, state,
                       first_seen_at, last_seen_at, stale_at
                FROM oregon_court_discovery_url
                WHERE candidate_id=?
                ORDER BY
                    CASE state WHEN 'active' THEN 0 ELSE 1 END,
                    normalized_url
                """,
                (candidate_id,),
            ).fetchall()
        ]

    @classmethod
    def _row_payload(
        cls,
        db: sqlite3.Connection,
        row: sqlite3.Row,
        *,
        include_events: bool = False,
    ) -> dict[str, Any]:
        candidate_id = int(row["candidate_id"])
        assessment = cls._assessment(db, candidate_id)
        links = cls._links(db, candidate_id)
        workflow_state = (
            "promoted"
            if links
            else "claimed"
            if row["claimed_by"]
            else "assessed"
            if assessment is not None
            else "pending"
        )
        payload = {
            "candidate_id": candidate_id,
            "stable_key": row["stable_key"],
            "state": row["state"],
            "workflow_state": workflow_state,
            "court": {
                "canonical_ref": row["court_canonical_ref"],
                "native_id": row["court_native_id"],
                "name": row["court_name"],
                "court_types": _json_load(row["court_types_json"], []),
                "counties": _json_load(row["counties_json"], []),
                "city": row["city"],
            },
            "current_url": row["current_url"],
            "current_host": row["current_host"],
            "urls": cls._urls(db, candidate_id),
            "registry_provenance": {
                "source_id": row["registry_source_id"],
                "source_url": row["registry_source_url"],
                "list_name": row["registry_list_name"],
                "view_id": row["registry_view_id"],
                "sharepoint_item_id": row["sharepoint_item_id"],
                "sharepoint_unique_id": row["sharepoint_unique_id"],
                "identity_basis": _json_load(
                    row["identity_basis_json"],
                    {},
                ),
                "source_observation": _json_load(
                    row["provenance_json"],
                    {},
                ),
            },
            "first_seen_at": row["first_seen_at"],
            "last_seen_at": row["last_seen_at"],
            "stale_at": row["stale_at"],
            "claimed_by": row["claimed_by"],
            "claimed_at": row["claimed_at"],
            "assessment": assessment,
            "infra_requests": links,
            "updated_at": row["updated_at"],
        }
        if include_events:
            payload["events"] = [
                {
                    **dict(event),
                    "details": _json_load(event["details_json"], {}),
                }
                for event in db.execute(
                    """
                    SELECT event_id, event_type, actor, event_at, details_json
                    FROM oregon_court_discovery_event
                    WHERE candidate_id=?
                    ORDER BY event_id
                    """,
                    (candidate_id,),
                ).fetchall()
            ]
        return payload

    def sync_payload(
        self,
        payload: Mapping[str, Any],
        *,
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        """Idempotently synchronize one complete discovery envelope."""

        records, source_id, source_status, query_fingerprint, retrieved_at = (
            _complete_discovery_envelope(payload)
        )
        observed = _normalized_timestamp(observed_at or retrieved_at)
        grouped: dict[str, dict[str, Any]] = {}
        for record in records:
            snapshot = _candidate_snapshot(record)
            stable_key = snapshot["stable_key"]
            existing = grouped.get(stable_key)
            if existing is None:
                grouped[stable_key] = {
                    **snapshot,
                    "urls": {
                        snapshot["normalized_url"]: {
                            "url": snapshot["url"],
                            "normalized_url": snapshot["normalized_url"],
                            "host": snapshot["host"],
                        }
                    },
                }
                continue
            existing["urls"][snapshot["normalized_url"]] = {
                "url": snapshot["url"],
                "normalized_url": snapshot["normalized_url"],
                "host": snapshot["host"],
            }

        db = self._connect()
        try:
            with db:
                latest = db.execute(
                    """
                    SELECT observed_at
                    FROM oregon_court_discovery_sync
                    WHERE source_id=?
                    ORDER BY observed_at DESC, sync_id DESC
                    LIMIT 1
                    """,
                    (source_id,),
                ).fetchone()
                if latest is not None and observed < latest["observed_at"]:
                    raise OregonCourtDiscoveryQueueError(
                        "sync snapshot predates the latest persisted snapshot"
                    )

                created = 0
                updated = 0
                reactivated = 0
                urls_created = 0
                urls_staled = 0
                seen_candidate_ids: list[int] = []
                schema_values: set[str] = set()
                for stable_key in sorted(grouped):
                    snapshot = grouped[stable_key]
                    before = db.execute(
                        """
                        SELECT candidate_id, state, first_seen_at
                        FROM oregon_court_discovery_candidate
                        WHERE stable_key=?
                        """,
                        (stable_key,),
                    ).fetchone()
                    current_url = sorted(snapshot["urls"])[0]
                    current_url_value = snapshot["urls"][current_url]
                    db.execute(
                        """
                        INSERT INTO oregon_court_discovery_candidate(
                            stable_key, registry_source_id,
                            registry_source_url, registry_list_name,
                            registry_view_id, sharepoint_item_id,
                            sharepoint_unique_id, court_canonical_ref,
                            court_native_id, court_name, court_types_json,
                            counties_json, city, current_url, current_host,
                            state, first_seen_at, last_seen_at, stale_at,
                            identity_basis_json, provenance_json,
                            raw_candidate_json, created_at, updated_at
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            'active', ?, ?, NULL, ?, ?, ?, ?, ?
                        )
                        ON CONFLICT(stable_key) DO UPDATE SET
                            registry_source_id=excluded.registry_source_id,
                            registry_source_url=excluded.registry_source_url,
                            registry_list_name=excluded.registry_list_name,
                            registry_view_id=excluded.registry_view_id,
                            sharepoint_item_id=excluded.sharepoint_item_id,
                            sharepoint_unique_id=excluded.sharepoint_unique_id,
                            court_canonical_ref=excluded.court_canonical_ref,
                            court_native_id=excluded.court_native_id,
                            court_name=excluded.court_name,
                            court_types_json=excluded.court_types_json,
                            counties_json=excluded.counties_json,
                            city=excluded.city,
                            current_url=excluded.current_url,
                            current_host=excluded.current_host,
                            state='active',
                            last_seen_at=excluded.last_seen_at,
                            stale_at=NULL,
                            identity_basis_json=excluded.identity_basis_json,
                            provenance_json=excluded.provenance_json,
                            raw_candidate_json=excluded.raw_candidate_json,
                            updated_at=excluded.updated_at
                        """,
                        (
                            stable_key,
                            snapshot["registry_source_id"],
                            snapshot["registry_source_url"],
                            snapshot["registry_list_name"],
                            snapshot["registry_view_id"],
                            snapshot["sharepoint_item_id"],
                            snapshot["sharepoint_unique_id"],
                            snapshot["court_canonical_ref"],
                            snapshot["court_native_id"],
                            snapshot["court_name"],
                            canonical_json(snapshot["court_types"]),
                            canonical_json(snapshot["counties"]),
                            snapshot["city"],
                            current_url_value["url"],
                            current_url_value["host"],
                            observed,
                            observed,
                            canonical_json(snapshot["identity_basis"]),
                            canonical_json(snapshot["provenance"]),
                            canonical_json(snapshot["raw_candidate"]),
                            observed,
                            observed,
                        ),
                    )
                    row = db.execute(
                        """
                        SELECT candidate_id
                        FROM oregon_court_discovery_candidate
                        WHERE stable_key=?
                        """,
                        (stable_key,),
                    ).fetchone()
                    candidate_id = int(row["candidate_id"])
                    seen_candidate_ids.append(candidate_id)
                    if before is None:
                        created += 1
                        self._event(
                            db,
                            candidate_id=candidate_id,
                            event_type="discovered",
                            actor="registry_sync",
                            event_at=observed,
                            details={
                                "source_id": source_id,
                                "current_url": current_url_value["url"],
                            },
                        )
                    else:
                        updated += 1
                        if before["state"] == "stale":
                            reactivated += 1
                            self._event(
                                db,
                                candidate_id=candidate_id,
                                event_type="reactivated",
                                actor="registry_sync",
                                event_at=observed,
                                details={"source_id": source_id},
                            )

                    active_url_keys = sorted(snapshot["urls"])
                    placeholders = ",".join("?" for _ in active_url_keys)
                    stale_cursor = db.execute(
                        f"""
                        UPDATE oregon_court_discovery_url
                        SET state='stale', stale_at=?
                        WHERE candidate_id=? AND state='active'
                          AND normalized_url NOT IN ({placeholders})
                        """,
                        (observed, candidate_id, *active_url_keys),
                    )
                    urls_staled += max(stale_cursor.rowcount, 0)
                    for normalized_url in active_url_keys:
                        url = snapshot["urls"][normalized_url]
                        url_before = db.execute(
                            """
                            SELECT candidate_url_id
                            FROM oregon_court_discovery_url
                            WHERE candidate_id=? AND normalized_url=?
                            """,
                            (candidate_id, normalized_url),
                        ).fetchone()
                        db.execute(
                            """
                            INSERT INTO oregon_court_discovery_url(
                                candidate_id, url, normalized_url, host,
                                state, first_seen_at, last_seen_at, stale_at
                            ) VALUES (?, ?, ?, ?, 'active', ?, ?, NULL)
                            ON CONFLICT(candidate_id, normalized_url)
                            DO UPDATE SET
                                url=excluded.url,
                                host=excluded.host,
                                state='active',
                                last_seen_at=excluded.last_seen_at,
                                stale_at=NULL
                            """,
                            (
                                candidate_id,
                                url["url"],
                                normalized_url,
                                url["host"],
                                observed,
                                observed,
                            ),
                        )
                        urls_created += int(url_before is None)
                    schema_value = _text(
                        snapshot["provenance"].get("schema_fingerprint")
                    )
                    if schema_value:
                        schema_values.add(schema_value)

                if seen_candidate_ids:
                    placeholders = ",".join("?" for _ in seen_candidate_ids)
                    stale_cursor = db.execute(
                        f"""
                        UPDATE oregon_court_discovery_candidate
                        SET state='stale', stale_at=?, updated_at=?
                        WHERE registry_source_id=? AND state='active'
                          AND candidate_id NOT IN ({placeholders})
                        """,
                        (
                            observed,
                            observed,
                            source_id,
                            *seen_candidate_ids,
                        ),
                    )
                else:
                    stale_cursor = db.execute(
                        """
                        UPDATE oregon_court_discovery_candidate
                        SET state='stale', stale_at=?, updated_at=?
                        WHERE registry_source_id=? AND state='active'
                        """,
                        (observed, observed, source_id),
                    )
                candidates_staled = max(stale_cursor.rowcount, 0)
                db.execute(
                    """
                    UPDATE oregon_court_discovery_url
                    SET state='stale', stale_at=?
                    WHERE state='active' AND candidate_id IN (
                        SELECT candidate_id
                        FROM oregon_court_discovery_candidate
                        WHERE registry_source_id=? AND state='stale'
                    )
                    """,
                    (observed, source_id),
                )
                active_count = int(
                    db.execute(
                        """
                        SELECT COUNT(*)
                        FROM oregon_court_discovery_candidate
                        WHERE registry_source_id=? AND state='active'
                        """,
                        (source_id,),
                    ).fetchone()[0]
                )
                stale_count = int(
                    db.execute(
                        """
                        SELECT COUNT(*)
                        FROM oregon_court_discovery_candidate
                        WHERE registry_source_id=? AND state='stale'
                        """,
                        (source_id,),
                    ).fetchone()[0]
                )
                completed_at = _normalized_timestamp()
                details = {
                    "created": created,
                    "updated": updated,
                    "reactivated": reactivated,
                    "candidates_staled": candidates_staled,
                    "urls_created": urls_created,
                    "urls_staled": urls_staled,
                    "source_record_count": len(records),
                    "unique_court_count": len(grouped),
                }
                cursor = db.execute(
                    """
                    INSERT INTO oregon_court_discovery_sync(
                        source_id, observed_at, completed_at, source_status,
                        candidate_count, active_count, stale_count,
                        envelope_sha256, query_fingerprint,
                        schema_fingerprint, details_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        observed,
                        completed_at,
                        source_status,
                        len(grouped),
                        active_count,
                        stale_count,
                        sha256_fingerprint(payload),
                        query_fingerprint,
                        (
                            next(iter(schema_values))
                            if len(schema_values) == 1
                            else sha256_fingerprint(sorted(schema_values))
                            if schema_values
                            else None
                        ),
                        canonical_json(details),
                    ),
                )
                sync_id = int(cursor.lastrowid)
        finally:
            db.close()
        return {
            "status": "synced",
            "sync_id": sync_id,
            "source_id": source_id,
            "observed_at": observed,
            "candidate_count": len(grouped),
            "active_count": active_count,
            "stale_count": stale_count,
            **details,
        }

    def list_candidates(
        self,
        *,
        state: str = "active",
        workflow_state: str | None = None,
        query: str | None = None,
        claimed_by: str | None = None,
        unclaimed: bool = False,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        if state not in {*QUEUE_STATES, "all"}:
            raise OregonCourtDiscoveryQueueError(f"unknown queue state: {state}")
        db = self._connect()
        try:
            clauses: list[str] = []
            values: list[Any] = []
            if state != "all":
                clauses.append("state=?")
                values.append(state)
            if claimed_by is not None:
                clauses.append("claimed_by=?")
                values.append(_required_text(claimed_by, "claimed_by"))
            if unclaimed:
                clauses.append("claimed_by IS NULL")
            if query:
                clauses.append(
                    """
                    (
                        UPPER(COALESCE(court_name, '')) LIKE ?
                        OR UPPER(COALESCE(city, '')) LIKE ?
                        OR UPPER(COALESCE(current_url, '')) LIKE ?
                        OR UPPER(COALESCE(counties_json, '')) LIKE ?
                    )
                    """
                )
                pattern = f"%{query.upper()}%"
                values.extend((pattern, pattern, pattern, pattern))
            sql = "SELECT * FROM oregon_court_discovery_candidate"
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            sql += (
                " ORDER BY CASE state WHEN 'active' THEN 0 ELSE 1 END, "
                "UPPER(COALESCE(court_name, '')), candidate_id"
            )
            rows = db.execute(sql, values).fetchall()
            records = [self._row_payload(db, row, include_events=False) for row in rows]
            if workflow_state is not None:
                records = [
                    record
                    for record in records
                    if record["workflow_state"] == workflow_state
                ]
            if limit is not None:
                records = records[:limit]
            return records
        finally:
            db.close()

    def show(self, selector: str | int) -> dict[str, Any]:
        db = self._connect()
        try:
            row = self._selector_row(db, selector)
            return self._row_payload(db, row, include_events=True)
        finally:
            db.close()

    def claim(
        self,
        selector: str | int,
        *,
        claimed_by: str,
        claimed_at: str | None = None,
    ) -> dict[str, Any]:
        actor = _required_text(claimed_by, "claimed_by")
        timestamp = _normalized_timestamp(claimed_at)
        db = self._connect()
        try:
            with db:
                row = self._selector_row(db, selector)
                if row["claimed_by"] and row["claimed_by"] != actor:
                    raise OregonCourtDiscoveryQueueError(
                        f"candidate is already claimed by {row['claimed_by']}"
                    )
                db.execute(
                    """
                    UPDATE oregon_court_discovery_candidate
                    SET claimed_by=?, claimed_at=?, updated_at=?
                    WHERE candidate_id=?
                    """,
                    (actor, timestamp, timestamp, row["candidate_id"]),
                )
                self._event(
                    db,
                    candidate_id=int(row["candidate_id"]),
                    event_type="claimed",
                    actor=actor,
                    event_at=timestamp,
                )
            return self.show(int(row["candidate_id"]))
        finally:
            db.close()

    def release(
        self,
        selector: str | int,
        *,
        released_by: str,
        released_at: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        actor = _required_text(released_by, "released_by")
        timestamp = _normalized_timestamp(released_at)
        db = self._connect()
        try:
            with db:
                row = self._selector_row(db, selector)
                former_claimant = row["claimed_by"]
                db.execute(
                    """
                    UPDATE oregon_court_discovery_candidate
                    SET claimed_by=NULL, claimed_at=NULL, updated_at=?
                    WHERE candidate_id=?
                    """,
                    (timestamp, row["candidate_id"]),
                )
                self._event(
                    db,
                    candidate_id=int(row["candidate_id"]),
                    event_type="released",
                    actor=actor,
                    event_at=timestamp,
                    details={
                        "former_claimant": former_claimant,
                        "notes": _text(notes),
                    },
                )
            return self.show(int(row["candidate_id"]))
        finally:
            db.close()

    def assess(
        self,
        selector: str | int,
        *,
        assessed_by: str,
        fields: Mapping[str, Any],
        complements: Sequence[Mapping[str, Any]] | None = None,
        summary: str | None = None,
        assessed_at: str | None = None,
    ) -> dict[str, Any]:
        actor = _required_text(assessed_by, "assessed_by")
        timestamp = _normalized_timestamp(assessed_at)
        unknown = sorted(set(fields) - set(ASSESSMENT_FIELDS))
        if unknown:
            raise OregonCourtDiscoveryQueueError(
                f"unknown assessment fields: {', '.join(unknown)}"
            )
        normalized_fields = {
            field: _json_object(value, field) for field, value in fields.items()
        }
        normalized_complements = (
            _json_object_list(complements, "complements")
            if complements is not None
            else None
        )
        db = self._connect()
        try:
            with db:
                candidate = self._selector_row(db, selector)
                candidate_id = int(candidate["candidate_id"])
                existing = self._assessment(db, candidate_id) or {
                    field: {} for field in ASSESSMENT_FIELDS
                }
                merged = {
                    field: normalized_fields.get(field, existing.get(field, {}))
                    for field in ASSESSMENT_FIELDS
                }
                complement_values = (
                    normalized_complements
                    if normalized_complements is not None
                    else existing.get("complements", [])
                )
                summary_value = (
                    _text(summary) if summary is not None else existing.get("summary")
                )
                db.execute(
                    """
                    INSERT INTO oregon_court_discovery_assessment(
                        candidate_id, case_search_json, calendars_json,
                        registers_dockets_json, opinions_orders_json,
                        request_routes_json, bulk_products_json,
                        vendor_family_json, complements_json, summary,
                        assessed_by, assessed_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(candidate_id) DO UPDATE SET
                        case_search_json=excluded.case_search_json,
                        calendars_json=excluded.calendars_json,
                        registers_dockets_json=excluded.registers_dockets_json,
                        opinions_orders_json=excluded.opinions_orders_json,
                        request_routes_json=excluded.request_routes_json,
                        bulk_products_json=excluded.bulk_products_json,
                        vendor_family_json=excluded.vendor_family_json,
                        complements_json=excluded.complements_json,
                        summary=excluded.summary,
                        assessed_by=excluded.assessed_by,
                        assessed_at=excluded.assessed_at,
                        updated_at=excluded.updated_at
                    """,
                    (
                        candidate_id,
                        *(canonical_json(merged[field]) for field in ASSESSMENT_FIELDS),
                        canonical_json(complement_values),
                        summary_value,
                        actor,
                        timestamp,
                        timestamp,
                    ),
                )
                self._event(
                    db,
                    candidate_id=candidate_id,
                    event_type="assessed",
                    actor=actor,
                    event_at=timestamp,
                    details={
                        "updated_fields": sorted(normalized_fields),
                        "complements_updated": complements is not None,
                    },
                )
            return self.show(candidate_id)
        finally:
            db.close()

    @staticmethod
    def _infra_request(
        infra_request_id: int,
        investigation_db: str | Path,
    ) -> dict[str, Any]:
        db_path = Path(investigation_db)
        if not db_path.exists():
            raise OregonCourtDiscoveryQueueError(
                f"investigation database not found: {db_path}"
            )
        db = sqlite3.connect(str(db_path))
        db.row_factory = sqlite3.Row
        try:
            try:
                row = db.execute(
                    """
                    SELECT id, title, status
                    FROM infra_requests
                    WHERE id=?
                    """,
                    (infra_request_id,),
                ).fetchone()
            except sqlite3.Error as error:
                raise OregonCourtDiscoveryQueueError(
                    "investigation database lacks the infra request table"
                ) from error
        finally:
            db.close()
        if row is None:
            raise OregonCourtDiscoveryQueueError(
                f"unknown infra request: {infra_request_id}"
            )
        return dict(row)

    def link_infra_request(
        self,
        selector: str | int,
        *,
        infra_request_id: int,
        linked_by: str,
        investigation_db: str | Path = DEFAULT_INVESTIGATION_DB,
        notes: str | None = None,
        linked_at: str | None = None,
    ) -> dict[str, Any]:
        if isinstance(infra_request_id, bool) or infra_request_id <= 0:
            raise OregonCourtDiscoveryQueueError("infra_request_id must be positive")
        actor = _required_text(linked_by, "linked_by")
        timestamp = _normalized_timestamp(linked_at)
        infra_request = self._infra_request(
            infra_request_id,
            investigation_db,
        )
        db = self._connect()
        try:
            with db:
                candidate = self._selector_row(db, selector)
                candidate_id = int(candidate["candidate_id"])
                db.execute(
                    """
                    INSERT INTO oregon_court_discovery_infra_link(
                        candidate_id, infra_request_id, infra_title,
                        infra_status_at_link, notes, linked_by, linked_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(candidate_id, infra_request_id) DO UPDATE SET
                        infra_title=excluded.infra_title,
                        infra_status_at_link=excluded.infra_status_at_link,
                        notes=excluded.notes,
                        linked_by=excluded.linked_by,
                        updated_at=excluded.updated_at
                    """,
                    (
                        candidate_id,
                        infra_request_id,
                        infra_request["title"],
                        infra_request["status"],
                        _text(notes),
                        actor,
                        timestamp,
                        timestamp,
                    ),
                )
                self._event(
                    db,
                    candidate_id=candidate_id,
                    event_type="infra_request_linked",
                    actor=actor,
                    event_at=timestamp,
                    details={
                        "infra_request_id": infra_request_id,
                        "infra_title": infra_request["title"],
                        "infra_status": infra_request["status"],
                    },
                )
            return self.show(candidate_id)
        finally:
            db.close()

    def stats(self) -> dict[str, Any]:
        db = self._connect()
        try:
            state_counts = {
                row["state"]: int(row["count"])
                for row in db.execute(
                    """
                    SELECT state, COUNT(*) AS count
                    FROM oregon_court_discovery_candidate
                    GROUP BY state
                    """
                ).fetchall()
            }
            return {
                "candidates": sum(state_counts.values()),
                "by_state": state_counts,
                "claimed": int(
                    db.execute(
                        """
                        SELECT COUNT(*)
                        FROM oregon_court_discovery_candidate
                        WHERE claimed_by IS NOT NULL
                        """
                    ).fetchone()[0]
                ),
                "assessed": int(
                    db.execute(
                        "SELECT COUNT(*) FROM oregon_court_discovery_assessment"
                    ).fetchone()[0]
                ),
                "promoted": int(
                    db.execute(
                        """
                        SELECT COUNT(DISTINCT candidate_id)
                        FROM oregon_court_discovery_infra_link
                        """
                    ).fetchone()[0]
                ),
                "infra_links": int(
                    db.execute(
                        """
                        SELECT COUNT(*)
                        FROM oregon_court_discovery_infra_link
                        """
                    ).fetchone()[0]
                ),
                "sync_runs": int(
                    db.execute(
                        "SELECT COUNT(*) FROM oregon_court_discovery_sync"
                    ).fetchone()[0]
                ),
            }
        finally:
            db.close()


def _read_json_file(path: str) -> Mapping[str, Any]:
    if path == "-":
        value = json.load(sys.stdin)
    else:
        with Path(path).expanduser().open(encoding="utf-8") as handle:
            value = json.load(handle)
    return _mapping(value, "input")


def _parse_json_argument(value: str, field_name: str) -> Any:
    raw = value
    if value.startswith("@"):
        with Path(value[1:]).expanduser().open(encoding="utf-8") as handle:
            return json.load(handle)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise OregonCourtDiscoveryQueueError(
            f"{field_name} must be JSON or @file"
        ) from error


def _live_discovery_payload(args: argparse.Namespace) -> dict[str, Any]:
    directory_args = argparse.Namespace(
        command="discovery",
        query=None,
        source=LOCAL_COURT_SOURCE_ID,
        view="court-registry",
        limit=None,
        cursor=None,
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_attempts=args.max_attempts,
        retry_backoff=args.retry_backoff,
        output=None,
        json_out=False,
    )
    return execute_directory(directory_args).to_dict()


def execute_command(args: argparse.Namespace) -> Any:
    queue = OregonCourtDiscoveryQueue(args.db)
    if args.command == "sync":
        payload = (
            _read_json_file(args.input) if args.input else _live_discovery_payload(args)
        )
        return queue.sync_payload(payload, observed_at=args.observed_at)
    if args.command == "list":
        return queue.list_candidates(
            state=args.state,
            workflow_state=args.workflow,
            query=args.query,
            claimed_by=args.claimed_by,
            unclaimed=args.unclaimed,
            limit=args.limit,
        )
    if args.command == "show":
        return queue.show(args.selector)
    if args.command == "claim":
        return queue.claim(args.selector, claimed_by=args.by)
    if args.command == "release":
        return queue.release(
            args.selector,
            released_by=args.by,
            notes=args.notes,
        )
    if args.command == "assess":
        fields = {
            field: _parse_json_argument(
                getattr(args, field),
                field,
            )
            for field in ASSESSMENT_FIELDS
            if getattr(args, field) is not None
        }
        complements = (
            _parse_json_argument(args.complements, "complements")
            if args.complements is not None
            else None
        )
        if not fields and complements is None and args.summary is None:
            raise OregonCourtDiscoveryQueueError(
                "assess requires at least one assessment field or summary"
            )
        return queue.assess(
            args.selector,
            assessed_by=args.by,
            fields=fields,
            complements=complements,
            summary=args.summary,
        )
    if args.command == "promote":
        return queue.link_infra_request(
            args.selector,
            infra_request_id=args.infra_request_id,
            linked_by=args.by,
            investigation_db=args.investigation_db,
            notes=args.notes,
        )
    if args.command == "stats":
        return queue.stats()
    raise OregonCourtDiscoveryQueueError(f"unsupported command: {args.command}")


def _add_output(parser: argparse.ArgumentParser) -> None:
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist and assess Oregon local-court source candidates"
    )
    parser.add_argument("--db", default=str(DEFAULT_CATALOG_DB))
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync = subparsers.add_parser(
        "sync",
        help="Synchronize one complete registry discovery snapshot",
    )
    sync.add_argument(
        "--input",
        help="Existing discovery result envelope, or - for stdin; default is live",
    )
    sync.add_argument(
        "--observed-at",
        help="Override the envelope observation timestamp",
    )
    sync.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    sync.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    sync.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
    )
    sync.add_argument("--retry-backoff", type=float, default=0.25)
    _add_output(sync)

    list_parser = subparsers.add_parser("list", help="List queue candidates")
    list_parser.add_argument(
        "--state",
        choices=(*QUEUE_STATES, "all"),
        default="active",
    )
    list_parser.add_argument(
        "--workflow",
        choices=("pending", "claimed", "assessed", "promoted"),
    )
    list_parser.add_argument("--query")
    list_parser.add_argument("--claimed-by")
    list_parser.add_argument("--unclaimed", action="store_true")
    list_parser.add_argument("--limit", type=int)
    _add_output(list_parser)

    show = subparsers.add_parser("show", help="Show one candidate and history")
    show.add_argument("selector")
    _add_output(show)

    claim = subparsers.add_parser("claim", help="Claim one candidate")
    claim.add_argument("selector")
    claim.add_argument("--by", required=True)
    _add_output(claim)

    release = subparsers.add_parser("release", help="Release one candidate")
    release.add_argument("selector")
    release.add_argument("--by", required=True)
    release.add_argument("--notes")
    _add_output(release)

    assess = subparsers.add_parser(
        "assess",
        help="Update structured source-discovery assessment fields",
    )
    assess.add_argument("selector")
    assess.add_argument("--by", required=True)
    assessment_help = "JSON object or @path to a JSON object"
    assess.add_argument(
        "--case-search",
        dest="case_search",
        help=assessment_help,
    )
    assess.add_argument("--calendars", help=assessment_help)
    assess.add_argument(
        "--registers-dockets",
        dest="registers_dockets",
        help=assessment_help,
    )
    assess.add_argument(
        "--opinions-orders",
        dest="opinions_orders",
        help=assessment_help,
    )
    assess.add_argument(
        "--request-routes",
        dest="request_routes",
        help=assessment_help,
    )
    assess.add_argument(
        "--bulk-products",
        dest="bulk_products",
        help=assessment_help,
    )
    assess.add_argument(
        "--vendor-family",
        dest="vendor_family",
        help=assessment_help,
    )
    assess.add_argument(
        "--complements",
        help="JSON list of objects or @path to a JSON list",
    )
    assess.add_argument("--summary")
    _add_output(assess)

    promote = subparsers.add_parser(
        "promote",
        help="Link a selected candidate to an existing infra request",
    )
    promote.add_argument("selector")
    promote.add_argument("--infra-request-id", type=int, required=True)
    promote.add_argument("--by", required=True)
    promote.add_argument(
        "--investigation-db",
        default=str(DEFAULT_INVESTIGATION_DB),
    )
    promote.add_argument("--notes")
    _add_output(promote)

    stats = subparsers.add_parser("stats", help="Show queue lifecycle counts")
    _add_output(stats)
    return parser


def _emit(value: Any, args: argparse.Namespace) -> None:
    summary = f"Oregon court discovery queue {args.command}"
    if write_output(value, args, summary=summary):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(value, indent=2, sort_keys=True))
        return
    if isinstance(value, list):
        print(f"{len(value)} Oregon court discovery candidates")
        for candidate in value:
            court = candidate.get("court") or {}
            print(
                f"  {candidate.get('candidate_id')} | "
                f"{candidate.get('state')} | "
                f"{candidate.get('workflow_state')} | "
                f"{court.get('name') or candidate.get('current_url')}"
            )
        return
    if isinstance(value, Mapping) and "candidate_id" in value:
        court = value.get("court") or {}
        print(
            f"{value['candidate_id']} | {value.get('state')} | "
            f"{value.get('workflow_state')} | "
            f"{court.get('name') or value.get('current_url')}"
        )
        return
    print(json.dumps(value, indent=2, sort_keys=True))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "timeout", 1) <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "minimum_interval", 0) < 0:
        parser.error("--minimum-interval must not be negative")
    if getattr(args, "max_attempts", 1) <= 0:
        parser.error("--max-attempts must be positive")
    if getattr(args, "retry_backoff", 0) < 0:
        parser.error("--retry-backoff must not be negative")
    limit = getattr(args, "limit", None)
    if limit is not None and limit <= 0:
        parser.error("--limit must be positive")
    try:
        value = execute_command(args)
    except (
        OregonCourtDiscoveryQueueError,
        OSError,
        sqlite3.Error,
        json.JSONDecodeError,
    ) as error:
        parser.error(str(error))
        return
    _emit(value, args)


if __name__ == "__main__":
    main()
