"""Tracker tools honor ITHILDIN_DB_PATH and never create a stand-in database.

In a git worktree auto_leads.py once created an empty investigation.db next to
itself instead of reading the selected database, then crashed on a missing
table. These run the real CLIs against real temporary SQLite files.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tools import lead_tracker
from tools.runtime_db import INVESTIGATION_DB_ENV, connect

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_tool(tool: str, database: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / tool), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**os.environ, INVESTIGATION_DB_ENV: str(database), "ITHILDIN_PROFILE": "fixture"},
        timeout=120,
    )


@pytest.fixture
def investigation_db(tmp_path: Path) -> Path:
    """An investigation database created explicitly with the tracker schema."""
    path = tmp_path / "selected-investigation.db"
    db = connect(path, "rwc")
    db.row_factory = sqlite3.Row
    db = lead_tracker._ensure_schema(db)
    # Production-only table: no current code path creates it.
    db.execute(
        "CREATE TABLE auto_crossref_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "table_name TEXT NOT NULL, record_id INTEGER NOT NULL, crossref_type TEXT NOT NULL, "
        "lead_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
        "UNIQUE(table_name, record_id, crossref_type))"
    )
    db.execute(
        "INSERT INTO leads (title, category, priority, status, source, profile_id) "
        "VALUES ('Fixture auto lead', 'entity', 'low', 'open', 'agent:auto_leads:fixture', 'fixture')"
    )
    db.commit()
    db.close()
    return path


def test_auto_leads_stats_reads_the_selected_database(investigation_db):
    result = _run_tool("auto_leads.py", investigation_db, "stats")

    assert result.returncode == 0, result.stderr
    assert "Total auto-generated leads: 1" in result.stdout


@pytest.mark.parametrize("command", [("stats",), ("run", "--dry-run")])
def test_auto_leads_fails_loudly_instead_of_creating_a_missing_database(tmp_path, command):
    missing = tmp_path / "investigation.db"

    result = _run_tool("auto_leads.py", missing, *command)

    assert (result.returncode != 0, missing.exists()) == (True, False)
    assert INVESTIGATION_DB_ENV in result.stderr


def test_entity_dedup_writes_and_reads_the_selected_database(investigation_db):
    added = _run_tool(
        "entity_dedup.py", investigation_db,
        "add-alias", "--canonical", "Fixture Person", "--alias", "F. Person",
        "--type", "person_variant",
    )
    listed = _run_tool("entity_dedup.py", investigation_db, "list-aliases")

    assert (added.returncode, listed.returncode) == (0, 0), added.stderr + listed.stderr
    assert "'F. Person' -> 'Fixture Person'" in listed.stdout


def test_entity_dedup_fails_loudly_instead_of_creating_a_missing_database(tmp_path):
    missing = tmp_path / "investigation.db"

    result = _run_tool("entity_dedup.py", missing, "stats")

    assert (result.returncode != 0, missing.exists()) == (True, False)
    assert INVESTIGATION_DB_ENV in result.stderr


@pytest.mark.parametrize(
    ("tool", "command"),
    [
        ("lead_tracker.py", ("list",)),
        ("findings_tracker.py", ("stats",)),
        ("entity_tracker.py", ("lookup", "Fixture")),
        ("infra_tracker.py", ("show", "331")),
    ],
)
def test_trackers_fail_loudly_instead_of_creating_a_missing_database(tmp_path, tool, command):
    missing = tmp_path / "investigation.db"

    result = _run_tool(tool, missing, *command)

    assert (result.returncode != 0, missing.exists()) == (True, False)
    assert INVESTIGATION_DB_ENV in result.stderr


def test_lead_tracker_init_creates_the_selected_database_explicitly(tmp_path):
    created = tmp_path / "investigation.db"

    first = _run_tool("lead_tracker.py", created, "init")
    second = _run_tool("lead_tracker.py", created, "init")

    assert (first.returncode, second.returncode) == (0, 0), first.stderr + second.stderr
    assert "already exists" in second.stdout
    with sqlite3.connect(created) as db:
        assert db.execute("SELECT COUNT(*) FROM leads").fetchone() == (0,)
    db.close()


def test_active_profile_lookup_never_creates_a_database(tmp_path, monkeypatch):
    from tools import investigation_context
    from tools.runtime_db import MissingDatabaseError

    missing = tmp_path / "investigation.db"
    monkeypatch.delenv("ITHILDIN_PROFILE", raising=False)
    monkeypatch.setattr(investigation_context, "DB_PATH", missing)

    with pytest.raises(MissingDatabaseError):
        investigation_context.get_active_profile_name()

    assert not missing.exists()
