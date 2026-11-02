from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tools import runtime_db
from tools.runtime_db import (
    INVESTIGATION_DB_ENV,
    REGISTRY_DB_ENV,
    MissingDatabaseError,
    connect,
    connect_investigation_db,
    connect_registry_db,
)


def _database_with_row(path: Path, value: str) -> Path:
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE marker(value TEXT)")
        db.execute("INSERT INTO marker VALUES (?)", (value,))
    db.close()
    return path


@pytest.mark.parametrize("mode", ["ro", "rw"])
def test_opening_a_missing_database_raises_and_creates_no_file(tmp_path, mode):
    missing = tmp_path / "investigation.db"

    with pytest.raises(MissingDatabaseError, match="not found"):
        connect(missing, mode)

    assert list(tmp_path.iterdir()) == []


def test_only_explicit_create_mode_creates_a_database(tmp_path):
    created = tmp_path / "new.db"

    connect(created, "rwc").close()

    assert created.is_file()


def test_read_only_connection_rejects_writes(tmp_path):
    database = _database_with_row(tmp_path / "registry.db", "kept")
    db = connect(database)

    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        db.execute("INSERT INTO marker VALUES ('changed')")
    db.close()


def test_read_only_open_leaves_the_database_directory_unchanged(tmp_path):
    database = _database_with_row(tmp_path / "registry.db", "kept")
    before = {path.name: path.stat().st_mtime_ns for path in tmp_path.iterdir()}

    db = connect(database)
    assert db.execute("SELECT value FROM marker").fetchall() == [("kept",)]
    db.close()

    assert {path.name: path.stat().st_mtime_ns for path in tmp_path.iterdir()} == before


def test_dangling_symlink_counts_as_missing(tmp_path):
    link = tmp_path / "registry.db"
    link.symlink_to(tmp_path / "moved-away.db")

    with pytest.raises(MissingDatabaseError):
        connect(link)


def test_memory_name_opens_a_private_in_memory_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    db = connect(":memory:", "rw")
    db.execute("CREATE TABLE scratch(value TEXT)")
    db.close()

    assert list(tmp_path.iterdir()) == []


def test_unknown_open_mode_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unsupported SQLite open mode"):
        connect(tmp_path / "x.db", "memory")


def test_investigation_path_honors_ithildin_db_path(monkeypatch, tmp_path):
    monkeypatch.setenv(INVESTIGATION_DB_ENV, str(tmp_path / "selected.db"))

    assert runtime_db.investigation_db_path() == tmp_path / "selected.db"


def test_registry_path_honors_its_environment_override(monkeypatch, tmp_path):
    monkeypatch.setenv(REGISTRY_DB_ENV, str(tmp_path / "selected-registry.db"))

    assert runtime_db.registry_db_path() == tmp_path / "selected-registry.db"


@pytest.mark.parametrize(
    ("resolver", "env_var", "name"),
    [
        (runtime_db.investigation_db_path, INVESTIGATION_DB_ENV, "investigation.db"),
        (runtime_db.registry_db_path, REGISTRY_DB_ENV, "registry.db"),
    ],
)
def test_unset_or_empty_override_uses_the_checkout_database(monkeypatch, resolver, env_var, name):
    monkeypatch.setenv(env_var, "")

    assert resolver() == runtime_db.PROJECT_ROOT / name


def test_connect_investigation_db_opens_the_selected_database(monkeypatch, tmp_path):
    database = _database_with_row(tmp_path / "selected.db", "selected")
    monkeypatch.setenv(INVESTIGATION_DB_ENV, str(database))

    db = connect_investigation_db()
    assert db.execute("SELECT value FROM marker").fetchall() == [("selected",)]
    db.close()


def test_missing_registry_error_names_the_override_and_the_link_script(monkeypatch, tmp_path):
    missing = tmp_path / "registry.db"
    monkeypatch.setenv(REGISTRY_DB_ENV, str(missing))

    with pytest.raises(MissingDatabaseError) as raised:
        connect_registry_db()

    message = str(raised.value)
    assert REGISTRY_DB_ENV in message and "link_worktree_runtime.py" in message
