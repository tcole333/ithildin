"""Regression coverage for legacy canonical-connection deduplication."""

import sqlite3

from tools import lead_tracker


def test_legacy_connection_dedup_preserves_rich_provenance_and_corrections(tmp_path):
    db = sqlite3.connect(tmp_path / "legacy-connections.db")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_a TEXT NOT NULL,
            person_b TEXT NOT NULL,
            relationship_type TEXT CHECK(relationship_type IS NULL OR relationship_type IN (
                'financial','social','legal','intelligence','employment','familial',
                'corporate','advisory','political','owns','controls','funds',
                'subsidiary_of','contracts_with','successor_to','shares_officer','supplies'
            )),
            description TEXT,
            strength TEXT DEFAULT 'medium',
            date_range TEXT,
            finding_id INTEGER,
            created_at TEXT,
            verification_status TEXT DEFAULT 'unverified',
            verified_by TEXT,
            verified_at TEXT,
            profile_id TEXT,
            valid_from TEXT,
            valid_until TEXT
        );
        CREATE TABLE connection_evidence (
            connection_id INTEGER NOT NULL REFERENCES connections(id),
            evidence_type TEXT NOT NULL,
            evidence_ref TEXT NOT NULL,
            source_quote TEXT,
            source_page TEXT,
            assessment TEXT,
            PRIMARY KEY(connection_id, evidence_ref)
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.executemany(
        "INSERT INTO connections(id,person_a,person_b,relationship_type,profile_id) "
        "VALUES (?, 'Alpha', 'Beta', NULL, NULL)",
        [(10,), (20,), (30,)],
    )
    shared_ref = "COURTLISTENER:legacy/shared"
    unique_ref = "COURTLISTENER:legacy/unique"
    db.executemany(
        "INSERT INTO connection_evidence "
        "(connection_id,evidence_type,evidence_ref,source_quote,source_page,assessment) "
        "VALUES (?,?,?,?,?,?)",
        [
            (10, "canonical", shared_ref, None, "canonical-page", None),
            (20, "canonical", shared_ref, "richer quote", "duplicate-page", "richer assessment"),
            (30, "canonical", shared_ref, "later conflicting quote", None, "richer assessment"),
            (30, "canonical", unique_ref, "unique quote", "p. 9", "unique assessment"),
        ],
    )
    db.executemany(
        "INSERT INTO corrections "
        "(table_name,record_id,record_key,field_name,old_value,new_value,reason,correction_type) "
        "VALUES (?,?,?,?,?,?,?,'refinement')",
        [
            ("connections", 20, None, "description", None, "legacy description", "legacy edge edit"),
            ("connection_evidence", 20, shared_ref, "source_quote", None, "richer quote", "legacy quote edit"),
            ("connection_evidence", 30, unique_ref, "assessment", None, "unique assessment", "legacy assessment edit"),
        ],
    )
    db.commit()

    lead_tracker._ensure_schema(db)

    assert [row["id"] for row in db.execute("SELECT id FROM connections")] == [10]
    shared = db.execute(
        "SELECT source_quote,source_page,assessment FROM connection_evidence "
        "WHERE connection_id=10 AND evidence_ref=?", (shared_ref,),
    ).fetchone()
    assert tuple(shared) == ("richer quote", "canonical-page", "richer assessment")
    unique = db.execute(
        "SELECT source_quote,source_page,assessment FROM connection_evidence "
        "WHERE connection_id=10 AND evidence_ref=?", (unique_ref,),
    ).fetchone()
    assert tuple(unique) == ("unique quote", "p. 9", "unique assessment")

    assert db.execute(
        "SELECT COUNT(*) FROM corrections WHERE record_id IN (20,30) "
        "AND table_name IN ('connections','connection_evidence')"
    ).fetchone()[0] == 0
    assert db.execute(
        "SELECT COUNT(*) FROM corrections WHERE record_id=10 "
        "AND table_name IN ('connections','connection_evidence')"
    ).fetchone()[0] >= 3
    page_conflict = db.execute(
        "SELECT old_value,new_value FROM corrections "
        "WHERE record_id=10 AND record_key=? AND field_name='source_page' "
        "AND correction_type='merge'", (shared_ref,),
    ).fetchone()
    assert tuple(page_conflict) == ("duplicate-page", "canonical-page")
    quote_conflict = db.execute(
        "SELECT old_value,new_value FROM corrections "
        "WHERE record_id=10 AND record_key=? AND field_name='source_quote' "
        "AND correction_type='merge' AND old_value='later conflicting quote'",
        (shared_ref,),
    ).fetchone()
    assert tuple(quote_conflict) == ("later conflicting quote", "richer quote")
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    index_sql = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_connections_unique'"
    ).fetchone()[0].lower()
    assert "coalesce(relationship_type" in index_sql
    assert "coalesce(profile_id" in index_sql

    before = (
        db.execute("SELECT COUNT(*) FROM connection_evidence").fetchone()[0],
        db.execute("SELECT COUNT(*) FROM corrections").fetchone()[0],
    )
    lead_tracker._ensure_schema(db)
    after = (
        db.execute("SELECT COUNT(*) FROM connection_evidence").fetchone()[0],
        db.execute("SELECT COUNT(*) FROM corrections").fetchone()[0],
    )
    assert after == before
    db.close()
