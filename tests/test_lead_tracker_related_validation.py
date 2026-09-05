import sqlite3
import sys

import pytest

from tools import lead_tracker


@pytest.fixture
def lead_db(monkeypatch, tmp_path):
    db_path = tmp_path / "investigation.db"
    monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    db = lead_tracker.get_db()
    existing_id = db.execute(
        "INSERT INTO leads (title, profile_id) VALUES ('Existing lead', 'test')"
    ).lastrowid
    db.commit()
    db.close()
    return db_path, existing_id


def test_add_lead_rejects_missing_related_ids_before_insert(lead_db):
    db_path, existing_id = lead_db

    with pytest.raises(
        ValueError,
        match=r"Related lead IDs do not exist: 999999.*not finding IDs",
    ):
        lead_tracker.add_lead(
            "Must roll back",
            related_leads=[existing_id, 999999],
            profile_id="test",
        )

    db = sqlite3.connect(db_path)
    assert db.execute(
        "SELECT COUNT(*) FROM leads WHERE title='Must roll back'"
    ).fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM lead_relations").fetchone()[0] == 0
    db.close()


def test_add_lead_accepts_existing_related_lead(lead_db):
    db_path, existing_id = lead_db

    lead_id = lead_tracker.add_lead(
        "Valid relation",
        related_leads=[existing_id],
        profile_id="test",
    )

    db = sqlite3.connect(db_path)
    assert db.execute(
        "SELECT lead_id, related_lead_id FROM lead_relations"
    ).fetchall() == [(lead_id, existing_id)]
    db.close()


def test_add_cli_can_override_active_profile(lead_db, monkeypatch):
    db_path, _ = lead_db
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "lead_tracker.py",
            "add",
            "--title",
            "Profile-safe lead",
            "--profile",
            "epstein",
        ],
    )

    lead_tracker.main()

    db = sqlite3.connect(db_path)
    assert db.execute(
        "SELECT profile_id FROM leads WHERE title='Profile-safe lead'"
    ).fetchone()[0] == "epstein"
    db.close()
