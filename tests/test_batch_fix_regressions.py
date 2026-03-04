from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
from argparse import Namespace
from pathlib import Path

import pytest

import tools.auto_leads as auto_leads
import tools.findings_tracker as findings_tracker
import tools.lead_tracker as lead_tracker


@pytest.fixture
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "investigation.db"

    monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(findings_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(auto_leads, "DB_PATH", db_path)

    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    db = lead_tracker.get_db()
    db.close()

    # Skip standalone schema init path in findings_tracker (imports lead_tracker by file path).
    monkeypatch.setattr(findings_tracker, "_schema_initialized", True)
    monkeypatch.setattr(auto_leads, "_profile_cache", None)
    return db_path


def test_add_connection_dedups_when_relationship_type_is_null(isolated_db: Path) -> None:
    first_id = findings_tracker.add_connection(
        person_a="Bob",
        person_b="Alice",
        relationship_type=None,
        profile_id="test-profile",
    )
    second_id = findings_tracker.add_connection(
        person_a="Alice",
        person_b="Bob",
        relationship_type=None,
        profile_id="test-profile",
    )

    assert first_id == second_id

    db = sqlite3.connect(isolated_db)
    count = db.execute("SELECT COUNT(*) FROM connections").fetchone()[0]
    assert count == 1
    idx_sql = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_connections_unique'"
    ).fetchone()[0].lower()
    db.close()

    assert "coalesce(relationship_type" in idx_sql
    assert "coalesce(profile_id" in idx_sql


def test_cmd_run_commits_partial_progress_when_max_leads_hit(
    isolated_db: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def trigger_limit(db: sqlite3.Connection, dry_run: bool = False) -> tuple[int, int]:
        assert not dry_run
        auto_leads.create_lead(db, "first lead", "person", "high", "agent:test")
        auto_leads.create_lead(db, "second lead", "person", "high", "agent:test")
        return 2, 2

    monkeypatch.setattr(auto_leads, "_load_profile", lambda _=None: None)
    monkeypatch.setattr(auto_leads, "process_new_addresses", trigger_limit)

    auto_leads.cmd_run(Namespace(command="run", dry_run=False, profile=None, max_leads=1))
    output = capsys.readouterr().out

    assert "Lead creation limit reached" in output
    assert "Stopped early:" in output

    db = sqlite3.connect(isolated_db)
    lead_count = db.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    db.close()
    assert lead_count == 1


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq is required by hook scripts")
def test_check_existing_research_hook_extracts_target_without_grep_p(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "investigation.db"
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE findings (id INTEGER PRIMARY KEY AUTOINCREMENT, target_name TEXT)")
    db.execute("INSERT INTO findings (target_name) VALUES (?)", ("ACME LLC",))
    db.execute("INSERT INTO findings (target_name) VALUES (?)", ("ACME LLC affiliate",))
    db.commit()
    db.close()

    hook_path = repo_root / ".claude" / "hooks" / "check-existing-research.sh"
    payload = {
        "tool_input": {
            "command": 'python tools/findings_tracker.py add --target="ACME LLC" --summary "x"'
        }
    }
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)

    result = subprocess.run(
        [str(hook_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0
    assert "additionalContext" in result.stdout
    assert "ACME LLC" in result.stdout
