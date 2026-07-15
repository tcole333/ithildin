"""Regression coverage for audited canonical entity metadata corrections."""

import sqlite3
import sys

import pytest

from tools import entity_tracker, lead_tracker


@pytest.fixture
def entity_db(tmp_path, monkeypatch):
    path = tmp_path / "entities.db"
    monkeypatch.setattr(lead_tracker, "DB_PATH", path)
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    monkeypatch.setattr(entity_tracker, "DB_PATH", path)
    db = entity_tracker.get_db()
    db.execute(
        """
        INSERT INTO entities (
            id, name, entity_type, jurisdiction, status, source, notes
        ) VALUES (1, 'Canonical Person', 'person', 'US', 'active',
                  'old-source', 'stale notes')
        """
    )
    db.commit()
    db.close()
    return path


def _row(path, query, params=()):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    row = db.execute(query, params).fetchone()
    db.close()
    return row


def test_correct_entity_notes_records_immutable_audit_row(entity_db):
    changed = entity_tracker.correct_entity_field(
        1,
        "notes",
        "Reviewed canonical notes",
        "Prior amount was superseded by verified evidence",
        corrected_by="reviewer",
        correction_type="factual_error",
    )

    assert changed is True
    assert _row(entity_db, "SELECT notes FROM entities WHERE id=1")["notes"] == (
        "Reviewed canonical notes"
    )
    correction = _row(
        entity_db,
        "SELECT * FROM corrections WHERE table_name='entities' AND record_id=1",
    )
    assert correction["field_name"] == "notes"
    assert correction["old_value"] == "stale notes"
    assert correction["new_value"] == "Reviewed canonical notes"
    assert correction["reason"] == (
        "Prior amount was superseded by verified evidence"
    )
    assert correction["corrected_by"] == "reviewer"
    assert correction["correction_type"] == "factual_error"


def test_correct_entity_can_clear_nullable_metadata_with_audit(entity_db):
    assert entity_tracker.correct_entity_field(
        1, "source", "", "Remove misattributed source", corrected_by="reviewer"
    )

    assert _row(entity_db, "SELECT source FROM entities WHERE id=1")["source"] is None
    correction = _row(entity_db, "SELECT * FROM corrections WHERE field_name='source'")
    assert correction["old_value"] == "old-source"
    assert correction["new_value"] is None


@pytest.mark.parametrize("field", ["id", "name", "created_at", "agent_run_id"])
def test_correct_entity_rejects_identity_and_system_fields(entity_db, field):
    with pytest.raises(ValueError, match="Cannot correct entity field"):
        entity_tracker.correct_entity_field(
            1, field, "unsafe", "Attempted unsafe correction"
        )

    assert _row(entity_db, "SELECT COUNT(*) AS n FROM corrections")["n"] == 0


def test_correct_entity_rejects_blank_reason_and_invalid_controlled_values(entity_db):
    with pytest.raises(ValueError, match="audit reason"):
        entity_tracker.correct_entity_field(1, "notes", "new", "   ")
    with pytest.raises(ValueError, match="entity_type must be one of"):
        entity_tracker.correct_entity_field(
            1, "entity_type", "not-a-type", "Invalid type"
        )
    with pytest.raises(ValueError, match="status cannot be blank"):
        entity_tracker.correct_entity_field(1, "status", "", "Invalid status")

    assert _row(entity_db, "SELECT COUNT(*) AS n FROM corrections")["n"] == 0


def test_correct_entity_noop_does_not_add_audit_noise(entity_db):
    changed = entity_tracker.correct_entity_field(
        1, "notes", "stale notes", "No actual change", corrected_by="reviewer"
    )

    assert changed is False
    assert _row(entity_db, "SELECT COUNT(*) AS n FROM corrections")["n"] == 0


def test_correct_missing_entity_is_atomic(entity_db):
    with pytest.raises(ValueError, match="Entity #999 does not exist"):
        entity_tracker.correct_entity_field(
            999, "notes", "new", "Correct missing entity"
        )

    assert _row(entity_db, "SELECT COUNT(*) AS n FROM corrections")["n"] == 0


def test_entity_correct_cli_uses_audited_path(entity_db, monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "entity_tracker.py",
            "correct",
            "1",
            "--field",
            "notes",
            "--value",
            "CLI-reviewed notes",
            "--reason",
            "Replace stale summary",
            "--by",
            "cli-reviewer",
        ],
    )

    entity_tracker.main()

    assert "Corrected entity #1.notes" in capsys.readouterr().out
    assert _row(entity_db, "SELECT notes FROM entities WHERE id=1")["notes"] == (
        "CLI-reviewed notes"
    )
    correction = _row(entity_db, "SELECT * FROM corrections WHERE record_id=1")
    assert correction["corrected_by"] == "cli-reviewer"
