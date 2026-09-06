"""Regression coverage for atomic connection and evidence writes."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from tools import findings_tracker


@pytest.fixture
def connection_db(monkeypatch, tmp_path):
    db_path = tmp_path / "connections.db"
    db = sqlite3.connect(db_path)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(
        """
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            entity_type TEXT
        );
        CREATE TABLE connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_a TEXT NOT NULL,
            person_b TEXT NOT NULL,
            relationship_type TEXT,
            description TEXT,
            strength TEXT,
            date_range TEXT,
            finding_id INTEGER,
            profile_id TEXT,
            agent_run_id TEXT,
            verification_status TEXT DEFAULT 'unverified',
            verified_by TEXT,
            verified_at TEXT
        );
        CREATE UNIQUE INDEX idx_connections_unique ON connections(
            person_a,
            person_b,
            COALESCE(relationship_type, ''),
            COALESCE(profile_id, '')
        );
        CREATE TABLE connection_evidence (
            connection_id INTEGER NOT NULL REFERENCES connections(id),
            evidence_type TEXT NOT NULL,
            evidence_ref TEXT NOT NULL,
            source_quote TEXT,
            source_page TEXT,
            assessment TEXT,
            PRIMARY KEY (connection_id, evidence_ref)
        );
        CREATE TABLE corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            record_key TEXT,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            reason TEXT NOT NULL,
            corrected_by TEXT,
            correction_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TRIGGER reject_test_evidence
        BEFORE INSERT ON connection_evidence
        WHEN NEW.evidence_ref = 'reject-me'
        BEGIN
            SELECT RAISE(ABORT, 'reject test evidence');
        END;
        """
    )
    db.commit()
    db.close()

    def ensure_entity(db, name, entity_type="unknown", source="auto:connect",
                      agent_run_id=None):
        cursor = db.execute(
            "INSERT OR IGNORE INTO entities(name, entity_type) VALUES (?, ?)",
            (name, entity_type),
        )
        entity_id = db.execute("SELECT id FROM entities WHERE name=?", (name,)).fetchone()[0]
        return entity_id, cursor.rowcount == 1

    monkeypatch.setattr(findings_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(findings_tracker, "_schema_initialized", True)
    monkeypatch.setattr(findings_tracker, "_ensure_entity", ensure_entity)
    return db_path


def _seed_connection(db_path, person_a="Alpha", person_b="Beta"):
    db = sqlite3.connect(db_path)
    cursor = db.execute(
        """
        INSERT INTO connections
            (person_a, person_b, relationship_type, strength, profile_id)
        VALUES (?, ?, 'legal', 'medium', 'test-profile')
        """,
        (person_a, person_b),
    )
    connection_id = cursor.lastrowid
    db.commit()
    db.close()
    return connection_id


def test_duplicate_connection_resolves_canonical_id_after_stale_lastrowid(connection_db):
    canonical_id = _seed_connection(connection_db)

    resolved_id = findings_tracker.add_connection(
        "Alpha",
        "Beta",
        relationship_type="legal",
        evidence_ids=["NEW-EVIDENCE"],
        profile_id="test-profile",
    )

    assert resolved_id == canonical_id
    db = sqlite3.connect(connection_db)
    assert db.execute("SELECT COUNT(*) FROM connections").fetchone()[0] == 1
    assert db.execute(
        "SELECT connection_id, evidence_ref FROM connection_evidence"
    ).fetchall() == [(canonical_id, "NEW-EVIDENCE")]
    db.close()


def test_directional_connection_preserves_requested_endpoint_order(connection_db):
    connection_id = findings_tracker.add_connection(
        "Zeta Owner",
        "Alpha Subsidiary",
        relationship_type="owns",
        profile_id="test-profile",
    )

    db = sqlite3.connect(connection_db)
    row = db.execute(
        "SELECT person_a, person_b, relationship_type FROM connections WHERE id = ?",
        (connection_id,),
    ).fetchone()
    db.close()

    assert row == ("Zeta Owner", "Alpha Subsidiary", "owns")


def test_repeat_attachment_is_idempotent_and_adds_new_evidence(connection_db):
    first_id = findings_tracker.add_connection(
        "Gamma",
        "Delta",
        relationship_type="corporate",
        evidence_ids=["EV-1"],
        profile_id="test-profile",
    )
    second_id = findings_tracker.add_connection(
        "Gamma",
        "Delta",
        relationship_type="corporate",
        evidence_ids=["EV-1", "EV-2"],
        profile_id="test-profile",
    )

    assert second_id == first_id
    db = sqlite3.connect(connection_db)
    assert db.execute("SELECT COUNT(*) FROM connections").fetchone()[0] == 1
    assert db.execute(
        "SELECT evidence_ref FROM connection_evidence ORDER BY evidence_ref"
    ).fetchall() == [("EV-1",), ("EV-2",)]
    db.close()


def test_concurrent_duplicate_writers_share_connection_and_keep_evidence(connection_db):
    canonical_id = _seed_connection(connection_db)
    db = sqlite3.connect(connection_db)
    db.executemany(
        "INSERT INTO entities(name, entity_type) VALUES (?, 'unknown')",
        [("Alpha",), ("Beta",)],
    )
    db.commit()
    db.close()
    barrier = Barrier(2)

    def attach(evidence_ref):
        barrier.wait()
        return findings_tracker.add_connection(
            "Alpha",
            "Beta",
            relationship_type="legal",
            evidence_ids=[evidence_ref],
            profile_id="test-profile",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attach, ref) for ref in ("EV-A", "EV-B")]
        resolved_ids = [future.result(timeout=10) for future in futures]

    assert resolved_ids == [canonical_id, canonical_id]
    db = sqlite3.connect(connection_db)
    assert db.execute("SELECT COUNT(*) FROM connections").fetchone()[0] == 1
    assert db.execute(
        "SELECT evidence_ref FROM connection_evidence ORDER BY evidence_ref"
    ).fetchall() == [("EV-A",), ("EV-B",)]
    db.close()


def test_evidence_failure_rolls_back_entities_and_connection(connection_db):
    with pytest.raises(sqlite3.IntegrityError, match="reject test evidence"):
        findings_tracker.add_connection(
            "Rollback A",
            "Rollback B",
            relationship_type="legal",
            evidence_ids=["reject-me"],
            profile_id="test-profile",
        )

    db = sqlite3.connect(connection_db)
    assert db.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM connections").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM connection_evidence").fetchone()[0] == 0
    db.close()
