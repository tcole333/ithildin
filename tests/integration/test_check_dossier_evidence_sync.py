from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.real_fixture
def test_check_sync_passes_with_real_fixture_and_packed_refs(
    copy_fixture_db,
    copy_fixture_tree,
    run_python_script,
) -> None:
    db_path = copy_fixture_db("check_sync_investigation.db")
    dossier_dir = copy_fixture_tree("dossiers")
    dossier_path = dossier_dir / "check-sync.json"

    payload = json.loads(dossier_path.read_text())
    refs = [row.get("evidence_ref", "") for row in payload["findings"][0]["evidence"]]
    assert any("," in value for value in refs), "Fixture must contain packed evidence refs."

    result = run_python_script(
        "scripts/check_dossier_evidence_sync.py",
        "--db-path",
        str(db_path),
        "--dossier-dir",
        str(dossier_dir),
        "--dossier",
        "check-sync",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "0 mismatches" in result.stdout


@pytest.mark.integration
@pytest.mark.real_fixture
def test_check_sync_reports_mismatch(copy_fixture_db, copy_fixture_tree, run_python_script) -> None:
    db_path = copy_fixture_db("check_sync_investigation.db")
    dossier_dir = copy_fixture_tree("dossiers")
    dossier_path = dossier_dir / "check-sync.json"

    payload = json.loads(dossier_path.read_text())
    payload["findings"][0]["evidence"] = payload["findings"][0]["evidence"][:-1]
    dossier_path.write_text(json.dumps(payload, indent=2, sort_keys=True))

    result = run_python_script(
        "scripts/check_dossier_evidence_sync.py",
        "--db-path",
        str(db_path),
        "--dossier-dir",
        str(dossier_dir),
        "--dossier",
        "check-sync",
    )
    assert result.returncode == 1
    assert "Dossier evidence sync FAILED" in result.stdout
    assert "mismatches" in result.stdout


@pytest.mark.integration
@pytest.mark.real_fixture
def test_check_sync_reports_corrected_field_drift(
    copy_fixture_db,
    copy_fixture_tree,
    run_python_script,
) -> None:
    db_path = copy_fixture_db("check_sync_investigation.db")
    dossier_dir = copy_fixture_tree("dossiers")
    dossier_path = dossier_dir / "check-sync.json"

    payload = json.loads(dossier_path.read_text())
    finding = payload["findings"][0]
    finding["summary"] = "stale curated correction"
    dossier_path.write_text(json.dumps(payload, indent=2, sort_keys=True))

    import sqlite3

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE findings (id INTEGER PRIMARY KEY, summary TEXT)")
        conn.execute(
            """
            CREATE TABLE corrections (
                table_name TEXT,
                record_id INTEGER,
                field_name TEXT,
                correction_type TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO findings (id, summary) VALUES (?, ?)",
            (finding["id"], "canonical corrected summary"),
        )
        conn.execute(
            """
            INSERT INTO corrections(table_name, record_id, field_name, correction_type)
            VALUES ('findings', ?, 'summary', 'factual_error')
            """,
            (finding["id"],),
        )

    result = run_python_script(
        "scripts/check_dossier_evidence_sync.py",
        "--db-path",
        str(db_path),
        "--dossier-dir",
        str(dossier_dir),
        "--dossier",
        "check-sync",
    )
    assert result.returncode == 1
    assert "corrected field 'summary' differs from canonical DB" in result.stdout

    finding["summary"] = "canonical corrected summary"
    dossier_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    result = run_python_script(
        "scripts/check_dossier_evidence_sync.py",
        "--db-path",
        str(db_path),
        "--dossier-dir",
        str(dossier_dir),
        "--dossier",
        "check-sync",
    )
    assert result.returncode == 0, result.stderr or result.stdout


@pytest.mark.integration
def test_check_sync_missing_paths_returns_2(run_python_script, tmp_path: Path) -> None:
    missing_db = tmp_path / "missing.db"
    missing_dossier_dir = tmp_path / "missing-dossiers"

    result = run_python_script(
        "scripts/check_dossier_evidence_sync.py",
        "--db-path",
        str(missing_db),
        "--dossier-dir",
        str(missing_dossier_dir),
    )
    assert result.returncode == 2
    assert "Database not found" in result.stderr


@pytest.mark.integration
@pytest.mark.real_fixture
def test_check_sync_missing_dossier_dir_returns_2(copy_fixture_db, run_python_script, tmp_path: Path) -> None:
    db_path = copy_fixture_db("check_sync_investigation.db")
    missing_dossier_dir = tmp_path / "missing-dossiers"

    result = run_python_script(
        "scripts/check_dossier_evidence_sync.py",
        "--db-path",
        str(db_path),
        "--dossier-dir",
        str(missing_dossier_dir),
    )
    assert result.returncode == 2
    assert "Dossier directory not found" in result.stderr
