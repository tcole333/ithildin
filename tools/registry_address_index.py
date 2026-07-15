#!/usr/bin/env python3
"""Build and query the generated registry-address trigram FTS sidecar.

The source registry is always opened read-only. A complete index is built in a
same-directory temporary SQLite file, validated, and atomically published only
when the source fingerprint is unchanged.

Usage:
    uv run python tools/registry_address_index.py build
    uv run python tools/registry_address_index.py status
    uv run python tools/registry_address_index.py validate
    uv run python tools/registry_address_index.py rollback
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import unicodedata
import urllib.parse
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_PATH = PROJECT_ROOT / "registry.db"
DEFAULT_INDEX_PATH = PROJECT_ROOT / "datasets" / "registry_address_search.db"

SCHEMA_VERSION = 1
NORMALIZER_VERSION = "nfkd-casefold-alnum-po-v1"
MIN_SELECTOR_CHARACTERS = 3
DEFAULT_MIN_FREE_GIB = 5.0
DEFAULT_BATCH_SIZE = 25_000
HIGH_CARDINALITY_CANDIDATES = 10_000
INDEX_TABLES = (
    "entity_address_fts",
    "officer_address_fts",
    "agent_address_fts",
)
SOURCE_TABLES = (
    "registry_entities",
    "registry_officers",
    "registry_agents",
)


class RegistryAddressIndexError(RuntimeError):
    """Raised for missing, stale, invalid, or unsafe address-index operations."""


def _ro_uri(path: Path) -> str:
    encoded = urllib.parse.quote(str(path.resolve()), safe="/")
    return f"file:{encoded}?mode=ro"


def open_source_readonly(path: Path = DEFAULT_SOURCE_PATH) -> sqlite3.Connection:
    """Open a registry database without permitting writes."""
    path = Path(path)
    if not path.is_file():
        raise RegistryAddressIndexError(f"Registry database not found: {path}")
    db = sqlite3.connect(_ro_uri(path), uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    db.execute("PRAGMA cache_size=-131072")
    db.execute("PRAGMA mmap_size=536870912")
    return db


def normalize_address(value: str | None) -> str:
    """Return the versioned, punctuation-insensitive address search form."""
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", str(value)).casefold()
    value = "".join(char for char in value if not unicodedata.combining(char))
    tokens = re.findall(r"[a-z0-9]+", value)
    normalized: list[str] = []
    index = 0
    while index < len(tokens):
        if index + 1 < len(tokens) and tokens[index] == "p" and tokens[index + 1] == "o":
            normalized.append("po")
            index += 2
        else:
            normalized.append(tokens[index])
            index += 1
    return " ".join(normalized).upper()


def normalize_selector(value: str) -> str:
    """Normalize and enforce FTS5 trigram's minimum useful selector length."""
    normalized = normalize_address(value)
    searchable_characters = len(normalized.replace(" ", ""))
    if searchable_characters < MIN_SELECTOR_CHARACTERS:
        raise RegistryAddressIndexError(
            "Address selector must contain at least 3 normalized letters or digits; "
            "the trigram index does not fall back to a registry scan."
        )
    return normalized


def _match_expression(normalized: str) -> str:
    return f'"{normalized.replace(chr(34), chr(34) * 2)}"'


def _file_identity(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    stat = path.stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _source_file_identities(source_path: Path) -> dict[str, Any]:
    return {
        "database": _file_identity(source_path),
        "wal": _file_identity(Path(str(source_path) + "-wal")),
    }


def source_fingerprint(
    source_path: Path = DEFAULT_SOURCE_PATH,
    db: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Fingerprint source bytes, WAL state, relevant schema, and high-water IDs."""
    source_path = Path(source_path).resolve()
    own_connection = db is None
    if own_connection:
        db = open_source_readonly(source_path)
    assert db is not None

    before = _source_file_identities(source_path)
    try:
        table_marks = {
            table: int(db.execute(f'SELECT COALESCE(MAX(id), 0) FROM "{table}"').fetchone()[0])
            for table in SOURCE_TABLES
        }
        schema_rows = [
            tuple(row)
            for row in db.execute(
                "SELECT type,name,sql FROM sqlite_master "
                "WHERE name IN (?,?,?) ORDER BY type,name",
                SOURCE_TABLES,
            ).fetchall()
        ]
        schema_hash = hashlib.sha256(
            json.dumps(schema_rows, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        fingerprint = {
            "source_path": str(source_path),
            "page_count": int(db.execute("PRAGMA page_count").fetchone()[0]),
            "schema_version": int(db.execute("PRAGMA schema_version").fetchone()[0]),
            "relevant_schema_sha256": schema_hash,
            "max_ids": table_marks,
        }
        after = _source_file_identities(source_path)
        if before != after:
            raise RegistryAddressIndexError(
                "registry.db or its WAL changed while the source fingerprint was "
                "being sampled; retry when registry ingestion is idle"
            )
        fingerprint.update(after)
        return fingerprint
    except sqlite3.Error as error:
        raise RegistryAddressIndexError(
            f"Could not fingerprint registry source {source_path}: {error}"
        ) from error
    finally:
        if own_connection:
            db.close()


def _read_metadata(index_path: Path) -> dict[str, Any]:
    index_path = Path(index_path)
    if not index_path.is_file():
        raise RegistryAddressIndexError(
            f"Registry address index is missing: {index_path}. Build it with: "
            "uv run python tools/registry_address_index.py build"
        )
    try:
        db = sqlite3.connect(_ro_uri(index_path), uri=True, timeout=10)
        row = db.execute(
            "SELECT metadata_json FROM address_index_meta WHERE id=1"
        ).fetchone()
        required = {
            item[0]
            for item in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN (?,?,?)",
                INDEX_TABLES,
            )
        }
        db.close()
    except sqlite3.Error as error:
        raise RegistryAddressIndexError(
            f"Registry address index is unreadable: {index_path}: {error}"
        ) from error
    if not row:
        raise RegistryAddressIndexError(
            f"Registry address index lacks build metadata: {index_path}"
        )
    if required != set(INDEX_TABLES):
        missing = sorted(set(INDEX_TABLES) - required)
        raise RegistryAddressIndexError(
            f"Registry address index is incomplete; missing tables: {', '.join(missing)}"
        )
    try:
        return json.loads(row[0])
    except json.JSONDecodeError as error:
        raise RegistryAddressIndexError(
            f"Registry address index metadata is invalid JSON: {error}"
        ) from error


def validate_index_fast(
    source_path: Path = DEFAULT_SOURCE_PATH,
    index_path: Path = DEFAULT_INDEX_PATH,
) -> dict[str, Any]:
    """Validate versions and source fingerprint without scanning the sidecar."""
    metadata = _read_metadata(Path(index_path))
    if metadata.get("schema_version") != SCHEMA_VERSION:
        raise RegistryAddressIndexError(
            f"Registry address index schema version is {metadata.get('schema_version')}; "
            f"expected {SCHEMA_VERSION}. Rebuild the sidecar."
        )
    if metadata.get("normalizer_version") != NORMALIZER_VERSION:
        raise RegistryAddressIndexError(
            "Registry address index normalizer version is stale. Rebuild the sidecar."
        )
    current = source_fingerprint(Path(source_path))
    if metadata.get("source_fingerprint") != current:
        raise RegistryAddressIndexError(
            "Registry address index is stale relative to registry.db. Rebuild it with: "
            "uv run python tools/registry_address_index.py build --force"
        )
    return metadata


def _fts_query_plans(db: sqlite3.Connection) -> dict[str, list[str]]:
    plans: dict[str, list[str]] = {}
    for table in INDEX_TABLES:
        rows = db.execute(
            f"EXPLAIN QUERY PLAN SELECT rowid FROM {table} "
            f"WHERE {table} MATCH ? LIMIT 1",
            ('"SUITE"',),
        ).fetchall()
        details = [str(row[3]) for row in rows]
        if not any("VIRTUAL TABLE INDEX" in detail for detail in details):
            raise RegistryAddressIndexError(
                f"FTS query plan for {table} does not use a virtual-table index: {details}"
            )
        plans[table] = details
    return plans


def validate_index_full(
    source_path: Path = DEFAULT_SOURCE_PATH,
    index_path: Path = DEFAULT_INDEX_PATH,
    *,
    run_fts_integrity: bool = True,
) -> dict[str, Any]:
    """Run SQLite/FTS integrity and query-plan checks on a published sidecar."""
    metadata = validate_index_fast(source_path, index_path)
    index_path = Path(index_path)
    db = sqlite3.connect(str(index_path), timeout=30)
    try:
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RegistryAddressIndexError(
                f"Registry address index integrity_check returned {integrity!r}"
            )
        if run_fts_integrity:
            db.execute("BEGIN")
            for table in INDEX_TABLES:
                db.execute(f"INSERT INTO {table}({table}) VALUES('integrity-check')")
            db.rollback()
        plans = _fts_query_plans(db)
    finally:
        db.close()
    return {"integrity_check": "ok", "query_plans": plans, "metadata": metadata}


def _create_sidecar_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE address_index_meta(
            id INTEGER PRIMARY KEY CHECK(id=1),
            metadata_json TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE entity_address_fts USING fts5(
            principal_address,
            mailing_address,
            content='',
            tokenize='trigram'
        );
        CREATE VIRTUAL TABLE officer_address_fts USING fts5(
            address,
            content='',
            tokenize='trigram'
        );
        CREATE VIRTUAL TABLE agent_address_fts USING fts5(
            address,
            content='',
            tokenize='trigram'
        );
        """
    )


def _stream_table(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    *,
    source_sql: str,
    insert_sql: str,
    transform: Callable[[sqlite3.Row], tuple[Any, ...] | None],
    batch_size: int,
    label: str,
) -> dict[str, int]:
    cursor = source.execute(source_sql)
    indexed_rows = 0
    normalized_characters = 0
    first_rowid: int | None = None
    last_rowid: int | None = None
    last_report = time.monotonic()
    batches_since_commit = 0

    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        payload: list[tuple[Any, ...]] = []
        for row in rows:
            transformed = transform(row)
            if transformed is None:
                continue
            payload.append(transformed)
            rowid = int(transformed[0])
            first_rowid = rowid if first_rowid is None else first_rowid
            last_rowid = rowid
            normalized_characters += sum(
                len(value) for value in transformed[1:] if isinstance(value, str)
            )
        if payload:
            target.executemany(insert_sql, payload)
            indexed_rows += len(payload)
        batches_since_commit += 1
        if batches_since_commit >= 10:
            target.commit()
            batches_since_commit = 0
        if time.monotonic() - last_report >= 5:
            print(f"  {label}: indexed {indexed_rows:,} rows", file=sys.stderr, flush=True)
            last_report = time.monotonic()

    target.commit()
    print(f"  {label}: indexed {indexed_rows:,} rows", file=sys.stderr, flush=True)
    return {
        "rows": indexed_rows,
        "normalized_characters": normalized_characters,
        "first_rowid": first_rowid or 0,
        "last_rowid": last_rowid or 0,
    }


def _validate_rowid_samples(
    source: sqlite3.Connection,
    metrics: dict[str, dict[str, int]],
) -> None:
    mapping = {
        "entities": "registry_entities",
        "officers": "registry_officers",
        "agents": "registry_agents",
    }
    for label, table in mapping.items():
        for key in ("first_rowid", "last_rowid"):
            rowid = metrics[label][key]
            if not rowid:
                continue
            if not source.execute(
                f'SELECT 1 FROM "{table}" WHERE id=?', (rowid,)
            ).fetchone():
                raise RegistryAddressIndexError(
                    f"Indexed {label} rowid {rowid} does not resolve in {table}"
                )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def _lifecycle_lock(index_path: Path):
    """Exclude concurrent build/publish/rollback operations across processes."""
    lock_path = index_path.with_name(index_path.name + ".lock")
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RegistryAddressIndexError(
                f"Another registry address-index lifecycle operation holds {lock_path}"
            ) from error
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _hardlink_replace(source: Path, destination: Path) -> None:
    """Atomically point destination at source's immutable bytes without a gap."""
    link_path = destination.with_name(
        destination.name + f".link-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    )
    try:
        os.link(source, link_path)
        os.replace(link_path, destination)
    finally:
        if link_path.exists():
            link_path.unlink()


def _publish(temp_path: Path, index_path: Path) -> Path | None:
    backup_path = index_path.with_name(index_path.name + ".bak")
    had_existing = index_path.exists()
    if had_existing:
        _hardlink_replace(index_path, backup_path)
    os.replace(temp_path, index_path)
    _fsync_directory(index_path.parent)
    return backup_path if had_existing else None


def _restore_after_failed_publish(index_path: Path, backup_path: Path | None) -> None:
    """Restore the prior immutable sidecar after post-publish validation fails."""
    if backup_path is not None and backup_path.is_file():
        _hardlink_replace(backup_path, index_path)
    elif index_path.exists():
        index_path.unlink()
    _fsync_directory(index_path.parent)


def build_index(
    source_path: Path = DEFAULT_SOURCE_PATH,
    index_path: Path = DEFAULT_INDEX_PATH,
    *,
    force: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
    min_free_gib: float = DEFAULT_MIN_FREE_GIB,
) -> dict[str, Any]:
    """Build, validate, and atomically publish under an interprocess lock."""
    index_path = Path(index_path).resolve()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with _lifecycle_lock(index_path):
        return _build_index_locked(
            source_path,
            index_path,
            force=force,
            batch_size=batch_size,
            min_free_gib=min_free_gib,
        )


def _build_index_locked(
    source_path: Path,
    index_path: Path,
    *,
    force: bool,
    batch_size: int,
    min_free_gib: float,
) -> dict[str, Any]:
    """Build implementation; caller must hold the lifecycle lock."""
    source_path = Path(source_path).resolve()
    index_path = Path(index_path).resolve()
    if batch_size < 1:
        raise RegistryAddressIndexError("batch_size must be positive")
    if min_free_gib < 0:
        raise RegistryAddressIndexError("min_free_gib cannot be negative")

    if index_path.exists() and not force:
        try:
            validation = validate_index_full(source_path, index_path)
            return {
                "status": "up_to_date",
                "index_path": str(index_path),
                "index_bytes": index_path.stat().st_size,
                "validation": validation,
            }
        except RegistryAddressIndexError:
            pass

    free_bytes = shutil.disk_usage(index_path.parent).free
    required_bytes = int(min_free_gib * 1024**3)
    if free_bytes < required_bytes:
        raise RegistryAddressIndexError(
            f"Insufficient free space for address-index build: {free_bytes / 1024**3:.2f} "
            f"GiB available, {min_free_gib:.2f} GiB required"
        )

    temp_path = index_path.with_name(
        f"{index_path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    )
    if temp_path.exists():
        temp_path.unlink()
    started = time.monotonic()
    source: sqlite3.Connection | None = None
    target: sqlite3.Connection | None = None

    try:
        source = open_source_readonly(source_path)
        source.execute("BEGIN")
        initial_fingerprint = source_fingerprint(source_path, source)

        target = sqlite3.connect(str(temp_path), timeout=30)
        target.execute("PRAGMA journal_mode=OFF")
        target.execute("PRAGMA synchronous=OFF")
        target.execute("PRAGMA locking_mode=EXCLUSIVE")
        target.execute("PRAGMA temp_store=MEMORY")
        target.execute("PRAGMA cache_size=-262144")
        _create_sidecar_schema(target)

        metrics: dict[str, dict[str, int]] = {}

        def entity_transform(row: sqlite3.Row) -> tuple[Any, ...] | None:
            principal = normalize_address(row[1])
            mailing = normalize_address(row[2])
            if not principal and not mailing:
                return None
            return (int(row[0]), principal, mailing)

        def single_address_transform(row: sqlite3.Row) -> tuple[Any, ...] | None:
            address = normalize_address(row[1])
            if not address:
                return None
            return (int(row[0]), address)

        metrics["entities"] = _stream_table(
            source,
            target,
            source_sql=(
                "SELECT id,principal_address,mailing_address FROM registry_entities "
                "WHERE principal_address IS NOT NULL OR mailing_address IS NOT NULL "
                "ORDER BY id"
            ),
            insert_sql=(
                "INSERT INTO entity_address_fts(rowid,principal_address,mailing_address) "
                "VALUES (?,?,?)"
            ),
            transform=entity_transform,
            batch_size=batch_size,
            label="entities",
        )
        metrics["officers"] = _stream_table(
            source,
            target,
            source_sql=(
                "SELECT id,address FROM registry_officers WHERE address IS NOT NULL ORDER BY id"
            ),
            insert_sql="INSERT INTO officer_address_fts(rowid,address) VALUES (?,?)",
            transform=single_address_transform,
            batch_size=batch_size,
            label="officers",
        )
        metrics["agents"] = _stream_table(
            source,
            target,
            source_sql=(
                "SELECT id,address FROM registry_agents WHERE address IS NOT NULL ORDER BY id"
            ),
            insert_sql="INSERT INTO agent_address_fts(rowid,address) VALUES (?,?)",
            transform=single_address_transform,
            batch_size=batch_size,
            label="agents",
        )
        _validate_rowid_samples(source, metrics)

        print("  optimizing trigram segments", file=sys.stderr, flush=True)
        for table in INDEX_TABLES:
            target.execute(f"INSERT INTO {table}({table}) VALUES('optimize')")
        target.commit()

        print("  checking FTS and SQLite integrity", file=sys.stderr, flush=True)
        for table in INDEX_TABLES:
            target.execute(f"INSERT INTO {table}({table}) VALUES('integrity-check')")
        plans = _fts_query_plans(target)
        elapsed = time.monotonic() - started
        metadata = {
            "schema_version": SCHEMA_VERSION,
            "normalizer_version": NORMALIZER_VERSION,
            "source_fingerprint": initial_fingerprint,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "build_seconds": round(elapsed, 3),
            "sqlite_version": sqlite3.sqlite_version,
            "metrics": metrics,
            "validation": {
                "integrity_check": "ok",
                "fts_integrity_tables": list(INDEX_TABLES),
                "query_plans": plans,
                "rowid_samples_resolved": True,
            },
        }
        target.execute(
            "INSERT INTO address_index_meta(id,metadata_json) VALUES (1,?)",
            (json.dumps(metadata, sort_keys=True, separators=(",", ":")),),
        )
        target.commit()
        integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RegistryAddressIndexError(
                f"Temporary sidecar integrity_check returned {integrity!r}"
            )
        target.close()
        target = None
        _fsync_file(temp_path)
        source.rollback()
        source.close()
        source = None

        current_fingerprint = source_fingerprint(source_path)
        if current_fingerprint != initial_fingerprint:
            raise RegistryAddressIndexError(
                "registry.db changed during the sidecar build; refusing to publish a stale index"
            )

        backup_path = _publish(temp_path, index_path)
        try:
            validation = validate_index_fast(source_path, index_path)
        except Exception:
            _restore_after_failed_publish(index_path, backup_path)
            raise
        return {
            "status": "built",
            "source_path": str(source_path),
            "index_path": str(index_path),
            "backup_path": str(backup_path) if backup_path else None,
            "index_bytes": index_path.stat().st_size,
            "free_bytes_before": free_bytes,
            "build_seconds": round(time.monotonic() - started, 3),
            "metrics": metrics,
            "query_plans": plans,
            "metadata": validation,
        }
    finally:
        if target is not None:
            target.close()
        if source is not None:
            source.rollback()
            source.close()
        if temp_path.exists():
            temp_path.unlink()


def rollback_index(index_path: Path = DEFAULT_INDEX_PATH) -> dict[str, Any]:
    """Atomically replace the live sidecar under an interprocess lock."""
    index_path = Path(index_path).resolve()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with _lifecycle_lock(index_path):
        return _rollback_index_locked(index_path)


def _rollback_index_locked(index_path: Path) -> dict[str, Any]:
    """Rollback implementation; caller must hold the lifecycle lock."""
    backup_path = index_path.with_name(index_path.name + ".bak")
    if not index_path.exists() or not backup_path.exists():
        raise RegistryAddressIndexError(
            f"Rollback requires both {index_path} and {backup_path}"
        )

    current_snapshot = index_path.with_name(
        index_path.name + f".rollback-current-{uuid.uuid4().hex[:8]}"
    )
    backup_snapshot = index_path.with_name(
        index_path.name + f".rollback-backup-{uuid.uuid4().hex[:8]}"
    )
    os.link(index_path, current_snapshot)
    try:
        os.link(backup_path, backup_snapshot)
        os.replace(backup_snapshot, index_path)
        try:
            os.replace(current_snapshot, backup_path)
        except Exception:
            os.replace(current_snapshot, index_path)
            raise
        _fsync_directory(index_path.parent)
    finally:
        if current_snapshot.exists():
            current_snapshot.unlink()
        if backup_snapshot.exists():
            backup_snapshot.unlink()
    return {
        "status": "rolled_back",
        "index_path": str(index_path),
        "backup_path": str(backup_path),
    }


def _address_sql() -> dict[str, str]:
    return {
        "entities": """
            WITH candidates AS MATERIALIZED (
                SELECT rowid FROM address_idx.entity_address_fts
                WHERE entity_address_fts MATCH ?
            )
            SELECT re.*
            FROM candidates c
            JOIN registry_entities re ON re.id=c.rowid
            ORDER BY re.entity_name,re.id
            LIMIT ?
        """,
        "officers": """
            WITH candidates AS MATERIALIZED (
                SELECT rowid FROM address_idx.officer_address_fts
                WHERE officer_address_fts MATCH ?
            )
            SELECT o.*,re.entity_name,re.source_jurisdiction
            FROM candidates c
            JOIN registry_officers o ON o.id=c.rowid
            JOIN registry_entities re ON re.id=o.entity_id
            ORDER BY o.officer_name,o.id
            LIMIT ?
        """,
        "agents": """
            WITH candidates AS MATERIALIZED (
                SELECT rowid FROM address_idx.agent_address_fts
                WHERE agent_address_fts MATCH ?
            )
            SELECT a.*,re.entity_name,re.source_jurisdiction
            FROM candidates c
            JOIN registry_agents a ON a.id=c.rowid
            JOIN registry_entities re ON re.id=a.entity_id
            ORDER BY a.agent_name,a.id
            LIMIT ?
        """,
    }


def _base_first_address_sql() -> dict[str, str]:
    """Return strict top-N queries driven by existing alphabetical indexes."""
    return {
        "entities": """
            SELECT re.*
            FROM registry_entities AS re INDEXED BY idx_re_name
            WHERE EXISTS (
                SELECT 1 FROM address_idx.entity_address_fts AS f
                WHERE f.rowid=re.id AND entity_address_fts MATCH ?
            )
            ORDER BY re.entity_name,re.id
            LIMIT ?
        """,
        "officers": """
            SELECT o.*,re.entity_name,re.source_jurisdiction
            FROM registry_officers AS o INDEXED BY idx_ro_name
            JOIN registry_entities re ON re.id=o.entity_id
            WHERE EXISTS (
                SELECT 1 FROM address_idx.officer_address_fts AS f
                WHERE f.rowid=o.id AND officer_address_fts MATCH ?
            )
            ORDER BY o.officer_name,o.id
            LIMIT ?
        """,
        "agents": """
            SELECT a.*,re.entity_name,re.source_jurisdiction
            FROM registry_agents AS a INDEXED BY idx_ra_name
            JOIN registry_entities re ON re.id=a.entity_id
            WHERE EXISTS (
                SELECT 1 FROM address_idx.agent_address_fts AS f
                WHERE f.rowid=a.id AND agent_address_fts MATCH ?
            )
            ORDER BY a.agent_name,a.id
            LIMIT ?
        """,
    }


def _candidate_counts(db: sqlite3.Connection, expression: str) -> dict[str, int]:
    tables = dict(zip(("entities", "officers", "agents"), INDEX_TABLES, strict=True))
    return {
        bucket: int(
            db.execute(
                f"SELECT COUNT(*) FROM address_idx.{table} WHERE {table} MATCH ?",
                (expression,),
            ).fetchone()[0]
        )
        for bucket, table in tables.items()
    }


def _address_strategy(candidate_count: int) -> str:
    if candidate_count > HIGH_CARDINALITY_CANDIDATES:
        return "base_name_index"
    return "fts_candidates"


def _selected_address_sql(bucket: str, candidate_count: int) -> tuple[str, str]:
    strategy = _address_strategy(candidate_count)
    if strategy == "base_name_index":
        return strategy, _base_first_address_sql()[bucket]
    return strategy, _address_sql()[bucket]


def search_addresses(
    query: str,
    limit: int,
    *,
    source_path: Path = DEFAULT_SOURCE_PATH,
    index_path: Path = DEFAULT_INDEX_PATH,
) -> dict[str, list[dict[str, Any]]]:
    """Search all existing address buckets with strict global alphabetical top-N."""
    if limit < 1:
        raise RegistryAddressIndexError("Address search limit must be positive")
    normalized = normalize_selector(query)
    validate_index_fast(source_path, index_path)

    db = open_source_readonly(source_path)
    try:
        db.execute("ATTACH DATABASE ? AS address_idx", (_ro_uri(Path(index_path)),))
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA temp_store=MEMORY")
        expression = _match_expression(normalized)
        candidate_counts = _candidate_counts(db, expression)
        result: dict[str, list[dict[str, Any]]] = {}
        for bucket in ("entities", "officers", "agents"):
            _, sql = _selected_address_sql(bucket, candidate_counts[bucket])
            result[bucket] = [
                dict(row) for row in db.execute(sql, (expression, limit)).fetchall()
            ]
        return result
    except sqlite3.Error as error:
        raise RegistryAddressIndexError(
            f"Registry address index query failed: {error}"
        ) from error
    finally:
        db.close()


def address_query_plans(
    query: str,
    *,
    source_path: Path = DEFAULT_SOURCE_PATH,
    index_path: Path = DEFAULT_INDEX_PATH,
) -> dict[str, list[str]]:
    """Return the attached source/sidecar query plans for verification."""
    diagnostics = address_query_diagnostics(
        query,
        source_path=source_path,
        index_path=index_path,
    )
    return {
        bucket: details["query_plan"]
        for bucket, details in diagnostics.items()
    }


def address_query_diagnostics(
    query: str,
    *,
    source_path: Path = DEFAULT_SOURCE_PATH,
    index_path: Path = DEFAULT_INDEX_PATH,
) -> dict[str, dict[str, Any]]:
    """Return candidate counts, selected strategies, and query plans."""
    normalized = normalize_selector(query)
    validate_index_fast(source_path, index_path)
    db = open_source_readonly(source_path)
    try:
        db.execute("ATTACH DATABASE ? AS address_idx", (_ro_uri(Path(index_path)),))
        db.execute("PRAGMA query_only=ON")
        expression = _match_expression(normalized)
        candidate_counts = _candidate_counts(db, expression)
        result: dict[str, dict[str, Any]] = {}
        for bucket in ("entities", "officers", "agents"):
            strategy, sql = _selected_address_sql(bucket, candidate_counts[bucket])
            result[bucket] = {
                "candidate_count": candidate_counts[bucket],
                "strategy": strategy,
                "query_plan": [
                    str(row[3])
                    for row in db.execute(
                        "EXPLAIN QUERY PLAN " + sql, (expression, 20)
                    ).fetchall()
                ],
            }
        return result
    finally:
        db.close()


def _write_result(data: dict[str, Any], output: str | None) -> None:
    rendered = json.dumps(data, indent=2, default=str)
    if output:
        Path(output).write_text(rendered + "\n")
        print(f"Address-index report saved to {output}")
    else:
        print(rendered)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and validate the generated registry-address FTS sidecar"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_paths(command: argparse.ArgumentParser) -> None:
        command.add_argument("--source", type=Path, default=DEFAULT_SOURCE_PATH)
        command.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
        command.add_argument("--output", help="Write the JSON report to this file")

    build = sub.add_parser("build", help="Build and atomically publish the sidecar")
    add_paths(build)
    build.add_argument("--force", action="store_true", help="Rebuild even when current")
    build.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    build.add_argument("--min-free-gib", type=float, default=DEFAULT_MIN_FREE_GIB)

    status = sub.add_parser("status", help="Check sidecar existence and freshness")
    add_paths(status)

    validate = sub.add_parser("validate", help="Run full SQLite/FTS validation")
    add_paths(validate)

    rollback = sub.add_parser("rollback", help="Swap the sidecar with its .bak file")
    rollback.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    rollback.add_argument("--output", help="Write the JSON report to this file")

    args = parser.parse_args()
    try:
        if args.command == "build":
            result = build_index(
                args.source,
                args.index,
                force=args.force,
                batch_size=args.batch_size,
                min_free_gib=args.min_free_gib,
            )
        elif args.command == "status":
            metadata = validate_index_fast(args.source, args.index)
            result = {
                "status": "current",
                "source_path": str(args.source.resolve()),
                "index_path": str(args.index.resolve()),
                "index_bytes": args.index.stat().st_size,
                "metadata": metadata,
            }
        elif args.command == "validate":
            result = validate_index_full(args.source, args.index)
        else:
            result = rollback_index(args.index)
        _write_result(result, args.output)
    except RegistryAddressIndexError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
