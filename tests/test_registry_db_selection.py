"""Registry tools read the selected registry.db and never create a stand-in.

These run the real CLI against real temporary SQLite files: a worktree once
created an empty registry.db and every query returned zero rows without error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tools import query_registry
from tools import registry_address_index as address_index
from tools.runtime_db import REGISTRY_DB_ENV, MissingDatabaseError

REPO_ROOT = Path(__file__).resolve().parent.parent


def _query_registry(registry: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "query_registry.py"), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**os.environ, REGISTRY_DB_ENV: str(registry)},
        timeout=120,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    """A WAL-mode registry with the production schema and one indexed entity."""
    path = tmp_path / "registry.db"
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    query_registry._ensure_schema(db)
    entity_id = db.execute(
        "INSERT INTO registry_entities "
        "(source_jurisdiction, source_id, entity_name, principal_address) "
        "VALUES ('de', 'F-1', 'Fixture Holdings LLC', '200 South Biscayne Boulevard') "
        "RETURNING id"
    ).fetchone()[0]
    db.execute(
        "INSERT INTO registry_officers (entity_id, officer_name, title, address) "
        "VALUES (?, 'Pat Fixture', 'manager', '200 South Biscayne Boulevard')",
        (entity_id,),
    )
    db.execute(
        "INSERT INTO registry_agents (entity_id, agent_name, address) "
        "VALUES (?, 'Fixture Agent', '1 Agent Way')",
        (entity_id,),
    )
    query_registry._rebuild_fts(db)
    db.commit()
    db.close()
    return path


def test_search_reads_the_registry_selected_by_environment(registry, tmp_path):
    output = tmp_path / "search.json"

    result = _query_registry(registry, "search", "Fixture", "--output", str(output))

    assert result.returncode == 0, result.stderr
    assert [row["entity_name"] for row in json.loads(output.read_text())] == [
        "Fixture Holdings LLC"
    ]


def test_search_fails_loudly_instead_of_creating_a_missing_registry(tmp_path):
    missing = tmp_path / "registry.db"

    result = _query_registry(missing, "search", "Fixture")

    assert (result.returncode, missing.exists()) == (2, False)
    assert REGISTRY_DB_ENV in result.stderr


def test_query_commands_do_not_modify_the_registry_file(registry):
    before = (_sha256(registry), registry.stat().st_mtime_ns)

    for command in (
        ("search", "Fixture"),
        ("officers", "Pat"),
        ("agent", "Fixture"),
        ("ucc-search", "Fixture"),
        ("stats",),
    ):
        result = _query_registry(registry, *command)
        assert result.returncode == 0, (command, result.stderr)

    assert (_sha256(registry), registry.stat().st_mtime_ns) == before


def test_ingest_connection_refuses_to_create_a_missing_registry(tmp_path, monkeypatch):
    missing = tmp_path / "registry.db"
    monkeypatch.setattr(query_registry, "DB_PATH", missing)

    with pytest.raises(MissingDatabaseError, match="query_registry.py init"):
        query_registry.get_db()

    assert not missing.exists()


def test_init_creates_an_empty_registry_explicitly(tmp_path):
    created = tmp_path / "registry.db"

    result = _query_registry(created, "init")

    assert result.returncode == 0, result.stderr
    with sqlite3.connect(created) as db:
        assert db.execute("SELECT COUNT(*) FROM registry_entities").fetchone() == (0,)
    db.close()


def test_address_index_stays_current_after_registry_reads(registry, tmp_path, monkeypatch, capsys):
    index = tmp_path / "registry_address_search.db"
    address_index.build_index(registry, index, min_free_gib=0)

    for command in (("search", "Fixture"), ("officers", "Pat"), ("ucc-search", "Fixture")):
        assert _query_registry(registry, *command).returncode == 0
    # An ingest-style read-write connection that writes nothing deletes the
    # empty WAL on close; that churn must not read as a registry change.
    monkeypatch.setattr(query_registry, "DB_PATH", registry)
    query_registry.get_db().close()
    monkeypatch.setattr(query_registry, "ADDRESS_INDEX_PATH", index)

    query_registry.cmd_address(
        argparse.Namespace(query="South Biscayne", limit=20, output=None, json_out=False)
    )

    assert "Fixture Holdings LLC" in capsys.readouterr().out


def test_sidecar_that_recorded_an_empty_wal_stays_current(registry, tmp_path):
    index = tmp_path / "registry_address_search.db"
    address_index.build_index(registry, index, min_free_gib=0)
    with sqlite3.connect(index) as db:
        metadata = json.loads(db.execute("SELECT metadata_json FROM address_index_meta").fetchone()[0])
        metadata["source_fingerprint"]["wal"] = {"size": 0, "mtime_ns": 1}
        db.execute("UPDATE address_index_meta SET metadata_json = ?", (json.dumps(metadata),))
    db.close()

    assert address_index.validate_index_fast(registry, index)["schema_version"] == (
        address_index.SCHEMA_VERSION
    )
