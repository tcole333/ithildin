import json
import sqlite3
from datetime import datetime, timezone

import pytest

from tools import investigation_status as status


@pytest.fixture
def status_db(tmp_path):
    selected = tmp_path / "selected.db"
    with sqlite3.connect(selected) as db:
        db.executescript("""
            CREATE TABLE investigation_config(key TEXT PRIMARY KEY, value TEXT);
            INSERT INTO investigation_config VALUES ('active_profile', 'alpha');
            CREATE TABLE investigation_profiles(profile_id TEXT PRIMARY KEY);
            INSERT INTO investigation_profiles VALUES ('alpha'), ('beta'), ('empty');
            CREATE TABLE leads(profile_id TEXT, status TEXT);
            INSERT INTO leads VALUES ('alpha', 'open'), ('beta', 'blocked');
            CREATE TABLE findings(profile_id TEXT, confidence TEXT, created_at TEXT);
            INSERT INTO findings VALUES
                ('alpha', 'high', '2026-09-04 10:00:00'),
                ('alpha', 'medium', '2026-08-01T10:00:00Z'),
                ('alpha', 'low', '2026-09-07T10:00:00Z'),
                ('beta', 'confirmed', '2026-09-05T10:00:00Z');
            CREATE TABLE analysis_runs(profile_id TEXT, status TEXT, started_at TEXT);
            INSERT INTO analysis_runs VALUES
                ('alpha', 'completed', '2026-09-03 09:00:00'),
                ('beta', 'running', '2026-09-04 09:00:00');
        """)
    return selected


def test_snapshot_is_scoped_and_changes_no_database_bytes(status_db):
    before = status_db.read_bytes()
    result = status.collect_status(
        db_path=status_db, environ={}, now=datetime(2026, 9, 6, tzinfo=timezone.utc),
    )
    assert status_db.read_bytes() == before
    assert result["status"] == "ok"
    assert result["profile_id"] == "alpha"
    assert result["profile_validation"] == {"available": True, "registered": True}
    assert result["db_path"] == str(status_db.resolve())
    metrics = result["metrics"]
    assert metrics["lead_count"]["value"] == 1
    assert metrics["leads_by_status"]["value"] == [{"status": "open", "count": 1}]
    assert metrics["findings_count"]["value"] == 3
    assert metrics["recent_findings_count"]["value"] == 1
    assert metrics["analysis_runs_count"]["value"] == 1
    assert metrics["latest_analysis_at"]["value"] == "2026-09-03 09:00:00"


def test_explicit_context_overrides_inherited_context(status_db):
    result = status.collect_status(
        "beta", status_db,
        environ={"ITHILDIN_PROFILE": "alpha", "ITHILDIN_DB_PATH": "/missing.db"},
    )
    assert result["profile_id"] == "beta"
    assert result["metrics"]["leads_by_status"]["value"] == [{"status": "blocked", "count": 1}]


def test_partial_schema_is_unavailable_without_migrations(tmp_path):
    selected = tmp_path / "legacy.db"
    with sqlite3.connect(selected) as db:
        db.executescript("""
            CREATE TABLE leads(profile_id TEXT);
            CREATE TABLE analysis_runs(status TEXT);
            INSERT INTO analysis_runs VALUES ('completed');
        """)
    before = selected.read_bytes()
    result = status.collect_status("alpha", selected, environ={})
    assert result["status"] == "partial"
    assert result["profile_validation"]["available"] is False
    assert result["metrics"]["lead_count"] == {"available": True, "value": 0}
    assert result["metrics"]["leads_by_status"] == {
        "available": False, "reason": "missing columns in leads: status",
    }
    assert result["metrics"]["findings_count"] == {
        "available": False, "reason": "missing table: findings",
    }
    assert result["metrics"]["analysis_runs_count"] == {
        "available": False, "reason": "missing columns in analysis_runs: profile_id",
    }
    assert selected.read_bytes() == before


def test_missing_database_is_never_created(tmp_path):
    missing = tmp_path / "missing.db"
    with pytest.raises(sqlite3.OperationalError):
        status.collect_status("alpha", missing, environ={})
    assert not missing.exists()


def test_cli_writes_output_but_rejects_database_alias(status_db, tmp_path):
    output = tmp_path / "status.json"
    assert status.main(["--profile", "beta", "--db", str(status_db), "--output", str(output)]) == 0
    assert json.loads(output.read_text())["profile_id"] == "beta"
    alias = tmp_path / "alias.json"
    alias.hardlink_to(status_db)
    before = status_db.read_bytes()
    with pytest.raises(SystemExit) as error:
        status.main(["--profile", "beta", "--db", str(status_db), "--output", str(alias)])
    assert error.value.code == 2
    assert status_db.read_bytes() == before


def test_zero_recent_window_is_invalid(status_db):
    with pytest.raises(ValueError, match="positive"):
        status.collect_status("alpha", status_db, recent_days=0)


def test_unknown_profile_is_not_a_successful_empty_snapshot(status_db, tmp_path):
    before = status_db.read_bytes()
    with pytest.raises(ValueError, match="Unknown investigation profile 'alhpa'"):
        status.collect_status("alhpa", status_db, environ={})
    output = tmp_path / "unknown.json"
    with pytest.raises(SystemExit) as error:
        status.main(["--profile", "alhpa", "--db", str(status_db), "--output", str(output)])
    assert error.value.code == 2
    assert not output.exists()
    assert status_db.read_bytes() == before


def test_registered_empty_profile_has_verified_zero_counts(status_db):
    result = status.collect_status("empty", status_db, environ={})
    assert result["status"] == "ok"
    assert result["profile_validation"] == {"available": True, "registered": True}
    for key in ("lead_count", "findings_count", "recent_findings_count", "analysis_runs_count"):
        assert result["metrics"][key] == {"available": True, "value": 0}


@pytest.mark.parametrize("legacy_catalog", [False, True])
def test_unavailable_catalog_distinguishes_unverified_membership(status_db, legacy_catalog):
    with sqlite3.connect(status_db) as db:
        db.execute("DROP TABLE investigation_profiles")
        if legacy_catalog:
            db.execute("CREATE TABLE investigation_profiles(id TEXT PRIMARY KEY, name TEXT)")
            db.execute("INSERT INTO investigation_profiles VALUES ('alpha', 'Alpha')")
    before = status_db.read_bytes()
    result = status.collect_status("alhpa", status_db, environ={})
    assert result["status"] == "partial"
    assert result["profile_validation"]["available"] is False
    assert "profile membership is unverified" in result["profile_validation"]["reason"]
    assert result["metrics"]["lead_count"] == {"available": True, "value": 0}
    assert status_db.read_bytes() == before
