"""Schema initialization belongs to the selected database, not the process."""

import sqlite3

import pytest

from tools import lead_tracker


@pytest.fixture
def schema_calls(monkeypatch, tmp_path):
    monkeypatch.setattr(lead_tracker, "DB_PATH", tmp_path / "first.db")
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    monkeypatch.setattr(lead_tracker, "_schema_cache", {})
    original = lead_tracker._ensure_schema
    calls = []

    def initialize(db):
        calls.append(str(lead_tracker.DB_PATH))
        return original(db)

    monkeypatch.setattr(lead_tracker, "_ensure_schema", initialize)
    return calls


def test_switching_databases_preserves_independent_schema_and_search_logs(
    monkeypatch, tmp_path, schema_calls,
):
    first = lead_tracker.DB_PATH
    second = tmp_path / "second.db"
    for db_path, query in [(first, "first query"), (second, "second query"), (first, "repeat visit")]:
        monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
        lead_tracker.log_search(query, "fixture", 1)
        db = lead_tracker.get_db()
        try:
            assert db.execute("SELECT COUNT(*) FROM search_history").fetchone()[0] == (
                2 if query == "repeat visit" else 1
            )
        finally:
            db.close()
    assert schema_calls == [str(first), str(second)]


@pytest.mark.parametrize("replace_with_file", [False, True])
def test_deleted_or_replaced_path_cannot_reuse_schema_cache(
    tmp_path, schema_calls, replace_with_file,
):
    lead_tracker.log_search("old file", "fixture", 1)
    db_path = lead_tracker.DB_PATH
    db = sqlite3.connect(db_path)
    version = db.execute("PRAGMA schema_version").fetchone()[0]
    db.close()
    if replace_with_file:
        replacement = tmp_path / "replacement.db"
        db = sqlite3.connect(replacement)
        db.execute(f"PRAGMA schema_version={version}")
        db.close()
        replacement.replace(db_path)
    else:
        db_path.unlink()

    lead_tracker.log_search("new file", "fixture", 0)
    db = lead_tracker.get_db()
    try:
        assert [tuple(row) for row in db.execute(
            "SELECT query_text, result_count FROM search_log"
        )] == [("new file", 0)]
        assert db.execute("SELECT COUNT(*) FROM search_history").fetchone()[0] == 1
    finally:
        db.close()
    assert len(schema_calls) == 2


def test_schema_damage_with_same_inode_and_counter_is_detected(schema_calls):
    db = lead_tracker.get_db()
    version = db.execute("PRAGMA schema_version").fetchone()[0]
    db.execute("DROP TABLE search_log")
    db.execute(f"PRAGMA schema_version={version}")
    db.commit()
    db.close()

    lead_tracker.log_search("repaired", "fixture", 1)
    db = lead_tracker.get_db()
    try:
        assert db.execute("SELECT query_text FROM search_log").fetchone()[0] == "repaired"
    finally:
        db.close()
    assert len(schema_calls) == 2


def test_independent_memory_connections_each_initialize(monkeypatch, schema_calls):
    monkeypatch.setattr(lead_tracker, "DB_PATH", ":memory:")
    for _ in range(2):
        db = lead_tracker.get_db()
        try:
            assert db.execute("SELECT COUNT(*) FROM search_log").fetchone()[0] == 0
        finally:
            db.close()
    assert len(schema_calls) == 2


def test_explicit_cache_invalidation_still_reinitializes(schema_calls, monkeypatch):
    lead_tracker.get_db().close()
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    lead_tracker.get_db().close()
    assert len(schema_calls) == 2
