from __future__ import annotations

import sqlite3

from scripts import bulk_lead_cleanup


def _make_db(path):
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            target_name TEXT,
            thread_id INTEGER,
            source TEXT,
            status TEXT,
            profile_id TEXT,
            updated_at TEXT
        );
        CREATE TABLE investigation_threads (
            id INTEGER PRIMARY KEY,
            profile_id TEXT
        );
        INSERT INTO investigation_threads VALUES (7, 'example-profile');
        INSERT INTO leads VALUES
            (1, 'Open lead', NULL, NULL, 7, NULL, 'open', NULL, NULL),
            (2, 'Pending lead', NULL, NULL, 7, NULL, 'pending_triage', NULL, NULL);
        """
    )
    db.commit()
    db.close()


def test_assign_profiles_respects_explicit_pending_status(tmp_path, monkeypatch):
    db_path = tmp_path / "investigation.db"
    _make_db(db_path)
    monkeypatch.setattr(bulk_lead_cleanup, "DB_PATH", db_path)
    monkeypatch.setattr(bulk_lead_cleanup, "_load_all_profiles", lambda: {})

    bulk_lead_cleanup.run_assign_profiles(statuses=("pending_triage",))

    db = sqlite3.connect(db_path)
    rows = dict(db.execute("SELECT id, profile_id FROM leads"))
    db.close()
    assert rows == {1: None, 2: "example-profile"}
