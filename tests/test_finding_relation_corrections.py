"""Regression coverage for safe finding creation and relation corrections."""

import json
import sqlite3
import sys

import pytest

from tools import findings_tracker, lead_tracker


@pytest.fixture
def findings_db(tmp_path, monkeypatch):
    path = tmp_path / "findings.db"
    monkeypatch.setattr(lead_tracker, "DB_PATH", path)
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    monkeypatch.setattr(findings_tracker, "DB_PATH", path)
    monkeypatch.setattr(findings_tracker, "_schema_initialized", False)
    db = lead_tracker.get_db()
    db.executescript(
        """
        CREATE TABLE finding_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_finding_id INTEGER NOT NULL REFERENCES findings(id),
            to_finding_id INTEGER NOT NULL REFERENCES findings(id),
            relation_type TEXT NOT NULL,
            assessment TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (from_finding_id, to_finding_id, relation_type)
        );
        """
    )
    db.commit()
    db.close()
    return path


def _add_finding(summary):
    return findings_tracker.add_finding(
        target_name="Correction Target",
        summary=summary,
        source_datasets=["courtlistener"],
        profile_id="test",
    )


def test_delete_finding_relation_records_full_audit_snapshot(findings_db):
    first = _add_finding("First claim")
    second = _add_finding("Second claim")
    findings_tracker.relate_findings(
        first, second, "refines", assessment="mistaken edge", created_by="agent-a"
    )

    relation_id = findings_tracker.delete_finding_relation(
        first, second, "refines", reason="wrong source ID", corrected_by="reviewer"
    )

    db = sqlite3.connect(findings_db)
    db.row_factory = sqlite3.Row
    assert db.execute("SELECT COUNT(*) FROM finding_relations").fetchone()[0] == 0
    correction = db.execute(
        "SELECT * FROM corrections WHERE table_name='finding_relations'"
    ).fetchone()
    assert correction["record_id"] == relation_id
    assert correction["field_name"] == "__row__"
    assert correction["reason"] == "wrong source ID"
    assert correction["corrected_by"] == "reviewer"
    assert correction["correction_type"] == "retraction"
    snapshot = json.loads(correction["old_value"])
    assert snapshot["from_finding_id"] == first
    assert snapshot["to_finding_id"] == second
    assert snapshot["relation_type"] == "refines"
    db.close()


def test_delete_missing_finding_relation_is_atomic(findings_db):
    first = _add_finding("First claim")
    second = _add_finding("Second claim")

    with pytest.raises(ValueError, match="does not exist"):
        findings_tracker.delete_finding_relation(
            first, second, "refines", reason="wrong source ID"
        )

    db = sqlite3.connect(findings_db)
    assert db.execute("SELECT COUNT(*) FROM corrections").fetchone()[0] == 0
    db.close()


def test_relation_delete_cli_uses_audited_correction_path(
    findings_db, monkeypatch, capsys
):
    first = _add_finding("First claim")
    second = _add_finding("Second claim")
    findings_tracker.relate_findings(first, second, "depends_on")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "findings_tracker.py", "relation-delete", str(first), str(second),
            "--type", "depends_on", "--reason", "Accidental concurrent edge",
            "--by", "reviewer",
        ],
    )

    findings_tracker.main()

    assert "Deleted finding relation #" in capsys.readouterr().out
    db = sqlite3.connect(findings_db)
    assert db.execute("SELECT COUNT(*) FROM finding_relations").fetchone()[0] == 0
    assert db.execute(
        "SELECT COUNT(*) FROM corrections WHERE table_name='finding_relations'"
    ).fetchone()[0] == 1
    db.close()


@pytest.mark.parametrize("output_mode", ["json", "file"])
def test_add_emits_machine_readable_created_id(
    findings_db, monkeypatch, capsys, tmp_path, output_mode
):
    argv = [
        "findings_tracker.py", "add",
        "--target", "Concurrent Target",
        "--summary", "Created without assuming the next ID",
        "--sources", "courtlistener",
        "--profile", "test",
    ]
    output_path = tmp_path / "created.json"
    if output_mode == "json":
        argv.append("--json")
    else:
        argv.extend(["--output", str(output_path)])
    monkeypatch.setattr(sys, "argv", argv)

    findings_tracker.main()

    stdout = capsys.readouterr().out
    payload = json.loads(stdout) if output_mode == "json" else json.loads(
        output_path.read_text()
    )
    assert isinstance(payload["id"], int)
    assert payload["target_name"] == "Concurrent Target"
    assert "Created finding #" not in stdout
