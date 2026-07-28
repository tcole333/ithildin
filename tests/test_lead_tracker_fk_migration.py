"""Regression tests for stale leads_old_backup foreign-key repair."""

from __future__ import annotations

import re
import sqlite3

import pytest

from tools import lead_tracker


def _schema_objects(db, table):
    return {
        (row[0], row[1], row[2])
        for row in db.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE tbl_name = ? AND type IN ('index', 'trigger') "
            "AND sql IS NOT NULL",
            (table,),
        )
    }


def _table_rows(db, table):
    return [
        tuple(row)
        for row in db.execute(f'SELECT * FROM "{table}" ORDER BY id').fetchall()
    ]


def _make_leads_fk_stale(db, table):
    """Rebuild one fresh-schema table with the historical bad FK target."""
    db.commit()
    db.execute("PRAGMA foreign_keys=OFF")
    replacement = f"__make_stale_{table}"
    old_sequence = db.execute(
        "SELECT MAX(seq) FROM sqlite_sequence WHERE name = ?", (table,)
    ).fetchone()[0]
    table_sql = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()[0]
    objects = _schema_objects(db, table)
    columns = [
        row[1] for row in db.execute(f'PRAGMA table_xinfo("{table}")') if row[6] == 0
    ]
    create_sql = re.sub(
        rf"^CREATE TABLE\s+{re.escape(table)}",
        f'CREATE TABLE "{replacement}"',
        table_sql,
        count=1,
        flags=re.IGNORECASE,
    )
    create_sql, replacements = re.subn(
        r"(REFERENCES\s+)leads(?=\s*\()",
        r'\1"leads_old_backup"',
        create_sql,
        flags=re.IGNORECASE,
    )
    assert replacements >= 1

    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    db.execute("BEGIN IMMEDIATE")
    db.execute(create_sql)
    db.execute(
        f'INSERT INTO "{replacement}" ({quoted_columns}) '
        f'SELECT {quoted_columns} FROM "{table}"'
    )
    db.execute(f'DROP TABLE "{table}"')
    db.execute(f'ALTER TABLE "{replacement}" RENAME TO "{table}"')
    for _object_type, _object_name, object_sql in sorted(objects):
        db.execute(object_sql)
    db.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))
    if old_sequence is not None:
        db.execute(
            "INSERT INTO sqlite_sequence(name, seq) VALUES (?, ?)",
            (table, old_sequence),
        )
    db.commit()
    db.execute("PRAGMA foreign_keys=ON")


def _sequence_rows(db, table):
    return db.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = ? ORDER BY seq", (table,)
    ).fetchall()


def test_workflow_fk_rebuild_preserves_rows_objects_sequences_and_fts(tmp_path):
    db = sqlite3.connect(tmp_path / "workflow-fk.db")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    lead_tracker._ensure_schema(db)

    lead_id = db.execute(
        "INSERT INTO leads (title, status) VALUES ('current lead', 'open')"
    ).lastrowid
    db.execute(
        "INSERT INTO human_actions "
        "(id, title, description, action_type, priority, status, related_lead_id, "
        "created_at, completed_at, notes) VALUES "
        "(41, 'Retrieve record', 'Preserve this action', 'manual_verification', "
        "'high', 'in_progress', ?, '2026-06-01 01:02:03', NULL, 'action note')",
        (lead_id,),
    )
    db.execute(
        "INSERT INTO infra_requests "
        "(id, title, description, request_type, priority, status, source_name, "
        "source_url, data_type, access_method, auth_requirements, estimated_coverage, "
        "discovered_by, discovered_during, related_lead_id, tool_file, files_modified, "
        "probe_results, evaluation_notes, completed_by, created_at, updated_at, "
        "claimed_at, completed_at) VALUES "
        "(73, 'Repair workflow schema', 'Preserve this request', 'tool_fix', 'critical', "
        "'in_progress', 'investigation_db', NULL, 'sqlite_schema', 'manual', 'none', "
        "'all profiles', 'test', 'migration regression', ?, 'tools/lead_tracker.py', "
        "'[\"tools/lead_tracker.py\"]', 'confirmed', 'working', NULL, "
        "'2026-06-02 01:02:03', '2026-06-03 04:05:06', "
        "'2026-06-02 02:03:04', NULL)",
        (lead_id,),
    )
    db.execute(
        "CREATE INDEX idx_human_actions_related_test "
        "ON human_actions(related_lead_id, title)"
    )
    db.execute(
        "CREATE TABLE human_action_audit "
        "(action_id INTEGER NOT NULL, new_status TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TRIGGER human_actions_status_test AFTER UPDATE OF status ON human_actions "
        "BEGIN INSERT INTO human_action_audit(action_id, new_status) "
        "VALUES (new.id, new.status); END"
    )
    db.execute("UPDATE sqlite_sequence SET seq = 400 WHERE name = 'human_actions'")
    db.execute("UPDATE sqlite_sequence SET seq = 700 WHERE name = 'infra_requests'")
    db.commit()

    expected_rows = {
        table: _table_rows(db, table) for table in ("human_actions", "infra_requests")
    }
    expected_objects = {
        table: _schema_objects(db, table)
        for table in ("human_actions", "infra_requests")
    }
    expected_sequences = {
        "human_actions": 400,
        "infra_requests": 700,
    }

    for table in ("human_actions", "infra_requests"):
        _make_leads_fk_stale(db, table)
    assert lead_tracker._stale_leads_fk_tables(db) == [
        "human_actions",
        "infra_requests",
    ]

    # Exercise the real schema startup path, not only the migration helper.
    lead_tracker._ensure_schema(db)

    assert lead_tracker._stale_leads_fk_tables(db) == []
    for table in ("human_actions", "infra_requests"):
        assert _table_rows(db, table) == expected_rows[table]
        assert _schema_objects(db, table) == expected_objects[table]
        sequence_rows = _sequence_rows(db, table)
        assert len(sequence_rows) == 1
        assert sequence_rows[0][0] == expected_sequences[table]
        assert {
            row[2] for row in db.execute(f'PRAGMA foreign_key_list("{table}")')
        } >= {"leads"}

    # Restored triggers still synchronize both the audit table and external FTS.
    db.execute("UPDATE human_actions SET status = 'completed' WHERE id = 41")
    db.execute(
        "UPDATE infra_requests SET title = 'Renewed workflow schema' WHERE id = 73"
    )
    assert [
        tuple(row)
        for row in db.execute(
            "SELECT action_id, new_status FROM human_action_audit"
        ).fetchall()
    ] == [(41, "completed")]
    assert [
        tuple(row)
        for row in db.execute(
            "SELECT rowid FROM infra_requests_fts "
            "WHERE infra_requests_fts MATCH 'Renewed'"
        ).fetchall()
    ] == [(73,)]
    db.commit()

    # Correct current IDs are accepted; absent lead IDs are rejected.
    db.execute(
        "INSERT INTO human_actions "
        "(title, action_type, related_lead_id) VALUES ('Valid link', 'other', ?)",
        (lead_id,),
    )
    db.execute(
        "INSERT INTO infra_requests "
        "(title, description, request_type, related_lead_id) "
        "VALUES ('Valid request link', 'Current lead FK', 'tool_fix', ?)",
        (lead_id,),
    )
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO human_actions "
            "(title, action_type, related_lead_id) VALUES "
            "('Invalid link', 'other', 999999)"
        )
    db.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO infra_requests "
            "(title, description, request_type, related_lead_id) "
            "VALUES ('Invalid request link', 'Missing lead FK', 'tool_fix', 999999)"
        )
    db.rollback()
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []

    # A second startup is a no-op for the repaired tables.
    before_second_run = {
        table: (_table_rows(db, table), _schema_objects(db, table))
        for table in ("human_actions", "infra_requests")
    }
    lead_tracker._ensure_schema(db)
    assert lead_tracker._repair_stale_leads_foreign_keys(db) == []
    assert {
        table: (_table_rows(db, table), _schema_objects(db, table))
        for table in ("human_actions", "infra_requests")
    } == before_second_run
    db.close()


def test_rebuild_discovers_non_hardcoded_stale_fk_table(tmp_path):
    db = sqlite3.connect(tmp_path / "generic-fk.db")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(
        """
        CREATE TABLE leads (id INTEGER PRIMARY KEY);
        CREATE TABLE custom_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER REFERENCES "leads_old_backup"(id),
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX idx_custom_queue_status ON custom_queue(status);
        """
    )
    db.execute("PRAGMA foreign_keys=OFF")
    db.execute("INSERT INTO leads(id) VALUES (7)")
    db.execute(
        "INSERT INTO custom_queue(id, lead_id, status, created_at) "
        "VALUES (11, 7, 'pending', '2026-07-14T12:00:00')"
    )
    db.commit()
    db.execute("PRAGMA foreign_keys=ON")

    assert lead_tracker._repair_stale_leads_foreign_keys(db) == ["custom_queue"]
    assert db.execute("SELECT * FROM custom_queue").fetchall() == [
        (11, 7, "pending", "2026-07-14T12:00:00")
    ]
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' "
        "AND name = 'idx_custom_queue_status'"
    ).fetchone() == ("idx_custom_queue_status",)
    db.close()


def test_schema_repairs_lead_fts_triggers_left_on_backup_table(tmp_path):
    db = sqlite3.connect(tmp_path / "stale-lead-fts.db")
    db.row_factory = sqlite3.Row
    lead_tracker._ensure_schema(db)

    early_id = db.execute(
        "INSERT INTO leads (title, status) VALUES ('Indexed early token', 'open')"
    ).lastrowid
    db.commit()
    assert [
        row[0]
        for row in db.execute(
            "SELECT rowid FROM leads_fts WHERE leads_fts MATCH 'early'"
        ).fetchall()
    ] == [early_id]

    db.executescript(
        """
        DROP TRIGGER leads_ai;
        DROP TRIGGER leads_ad;
        DROP TRIGGER leads_au;
        CREATE TABLE leads_old_backup AS SELECT * FROM leads WHERE 0;
        CREATE TRIGGER leads_ai AFTER INSERT ON leads_old_backup BEGIN
            INSERT INTO leads_fts(rowid, title, description, findings, target_name)
            VALUES (new.id, new.title, COALESCE(new.description,''),
                    COALESCE(new.findings,''), COALESCE(new.target_name,''));
        END;
        CREATE TRIGGER leads_ad AFTER DELETE ON leads_old_backup BEGIN
            INSERT INTO leads_fts(
                leads_fts, rowid, title, description, findings, target_name
            )
            VALUES ('delete', old.id, old.title, COALESCE(old.description,''),
                    COALESCE(old.findings,''), COALESCE(old.target_name,''));
        END;
        CREATE TRIGGER leads_au AFTER UPDATE ON leads_old_backup BEGIN
            INSERT INTO leads_fts(
                leads_fts, rowid, title, description, findings, target_name
            )
            VALUES ('delete', old.id, old.title, COALESCE(old.description,''),
                    COALESCE(old.findings,''), COALESCE(old.target_name,''));
            INSERT INTO leads_fts(rowid, title, description, findings, target_name)
            VALUES (new.id, new.title, COALESCE(new.description,''),
                    COALESCE(new.findings,''), COALESCE(new.target_name,''));
        END;
        """
    )
    late_id = db.execute(
        "INSERT INTO leads (title, status) VALUES ('Previously missing token', 'open')"
    ).lastrowid
    db.commit()
    assert db.execute(
        "SELECT rowid FROM leads_fts WHERE leads_fts MATCH 'previously'"
    ).fetchall() == []

    lead_tracker._ensure_schema(db)

    triggers = db.execute(
        "SELECT name, tbl_name FROM sqlite_master "
        "WHERE type='trigger' AND name IN ('leads_ai', 'leads_ad', 'leads_au') "
        "ORDER BY name"
    ).fetchall()
    assert [tuple(row) for row in triggers] == [
        ("leads_ad", "leads"),
        ("leads_ai", "leads"),
        ("leads_au", "leads"),
    ]
    assert [
        row[0]
        for row in db.execute(
            "SELECT rowid FROM leads_fts WHERE leads_fts MATCH 'previously'"
        ).fetchall()
    ] == [late_id]

    newest_id = db.execute(
        "INSERT INTO leads (title, status) VALUES ('Trigger continuity token', 'open')"
    ).lastrowid
    assert [
        row[0]
        for row in db.execute(
            "SELECT rowid FROM leads_fts WHERE leads_fts MATCH 'continuity'"
        ).fetchall()
    ] == [newest_id]
    db.close()
