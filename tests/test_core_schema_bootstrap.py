"""Current-command bootstrap and historical connection migration regressions."""

import sqlite3

import pytest

from scripts import migrate_core_model_v2
from tools import analysis_export, core_schema, findings_tracker, lead_tracker, name_resolver


def test_fresh_bootstrap_supports_finding_links_relations_and_profile_export(
    monkeypatch, tmp_path
):
    db_path = tmp_path / "fresh.db"
    for module in (lead_tracker, findings_tracker):
        monkeypatch.setattr(module, "DB_PATH", db_path)
        monkeypatch.setattr(module, "_schema_initialized", False)
    # Spelling canonicalization otherwise consults the shared repository DB.
    monkeypatch.setattr(name_resolver, "resolve_canonical", lambda name: name)

    db = lead_tracker.get_db()
    required_tables = {
        "finding_entities", "finding_relations", "investigation_profiles",
        "data_change_sets", "schema_migrations",
    }
    assert required_tables <= {
        row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    db.close()

    finding_ids = []
    for number, subject in enumerate(("Schema Fixture Alpha LLC", "Schema Fixture Beta LLC")):
        evidence_ref = f"COURTLISTENER:schema-fixture-{number}"
        finding_ids.append(findings_tracker.add_finding(
            target_name=subject,
            summary=f"{subject} filed its annual report.",
            source_datasets=["courtlistener"],
            evidence_ids=[evidence_ref],
            source_quotes={evidence_ref: {"quote": f"{subject} filed its annual report."}},
            claim_type="direct_quote",
            confidence="confirmed",
            date_of_event="2026-09",
            profile_id="schema-fixture",
        ))

    assert findings_tracker.relate_findings(*finding_ids, "corroborates")
    exported = analysis_export.export_entity_network(profile_id="schema-fixture")
    assert {entity["name"] for entity in exported["entities"]} == {
        "Schema Fixture Alpha LLC", "Schema Fixture Beta LLC",
    }
    assert analysis_export.export_entity_network(profile_id="unrelated-fixture")["entities"] == []

    db = lead_tracker.get_db()
    assert db.execute("SELECT COUNT(*) FROM finding_entities").fetchone()[0] == 2
    assert tuple(db.execute(
        "SELECT from_finding_id, to_finding_id, relation_type FROM finding_relations"
    ).fetchone()) == (*finding_ids, "corroborates")
    assert tuple(db.execute(
        "SELECT event_date_iso, date_precision FROM findings WHERE id=?", (finding_ids[0],)
    ).fetchone()) == ("2026-09-01", "month")
    migrations = [tuple(row) for row in db.execute("SELECT * FROM schema_migrations")]
    assert [row[0] for row in migrations] == [core_schema.SCHEMA_MIGRATION_ID]
    assert migrate_core_model_v2.MIGRATION_ID not in {row[0] for row in migrations}
    lead_tracker._ensure_schema(db)
    assert [tuple(row) for row in db.execute("SELECT * FROM schema_migrations")] == migrations
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        db.execute(
            "INSERT INTO finding_entities(finding_id, entity_id) VALUES (999999, 999999)"
        )
    db.close()


def test_schema_install_is_atomic_and_does_not_commit_caller_work(tmp_path):
    db = sqlite3.connect(tmp_path / "transaction.db")
    db.execute("CREATE TABLE findings(id INTEGER PRIMARY KEY)")
    db.execute("INSERT INTO findings(id) VALUES (1)")
    core_schema.ensure_core_model_schema(db)
    db.rollback()
    assert db.execute("SELECT * FROM findings").fetchall() == []
    assert db.execute(
        "SELECT name FROM sqlite_master WHERE name='schema_migrations'"
    ).fetchall() == []
    assert [row[1] for row in db.execute("PRAGMA table_info(findings)")] == ["id"]
    db.close()


def test_schema_install_failure_leaves_no_partial_ddl(tmp_path):
    db = sqlite3.connect(tmp_path / "failed.db")
    with pytest.raises(sqlite3.OperationalError, match="no such table: findings"):
        core_schema.ensure_core_model_schema(db)
    assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
    assert not db.in_transaction
    db.close()


def test_schema_upgrade_preserves_existing_ledger_without_backfilling_claims(tmp_path):
    db = sqlite3.connect(tmp_path / "upgrade.db")
    db.executescript("""
        CREATE TABLE findings(id INTEGER PRIMARY KEY, target_name TEXT, date_of_event TEXT);
        CREATE TABLE entities(id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE schema_migrations (
            migration_id TEXT PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP, note TEXT
        );
        INSERT INTO findings VALUES (7, 'Existing Subject', '2026-08');
        INSERT INTO entities VALUES (11, 'Existing Subject');
    """)
    db.execute(
        "INSERT INTO schema_migrations VALUES (?, '2026-07-04', 'historical backfill record')",
        (migrate_core_model_v2.MIGRATION_ID,),
    )
    db.commit()

    core_schema.ensure_core_model_schema(db)
    core_schema.ensure_core_model_schema(db)

    assert db.execute("SELECT * FROM finding_entities").fetchall() == []
    assert db.execute("SELECT * FROM findings").fetchall() == [
        (7, "Existing Subject", "2026-08", None, None),
    ]
    assert db.execute(
        "SELECT applied_at, note FROM schema_migrations WHERE migration_id=?",
        (migrate_core_model_v2.MIGRATION_ID,),
    ).fetchone() == ("2026-07-04", "historical backfill record")
    assert {row[0] for row in db.execute("SELECT migration_id FROM schema_migrations")} == {
        migrate_core_model_v2.MIGRATION_ID, core_schema.SCHEMA_MIGRATION_ID,
    }
    db.close()


def _legacy_connections(db):
    db.executescript("""
        CREATE TABLE connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_a TEXT NOT NULL,
            person_b TEXT NOT NULL,
            relationship_type TEXT CHECK(relationship_type IN (
                'financial','social','legal','intelligence','employment',
                'familial','corporate','advisory','political'
            )),
            description TEXT,
            strength TEXT DEFAULT 'medium' CHECK(strength IN (
                'strong','medium','weak','circumstantial'
            )),
            date_range TEXT,
            finding_id INTEGER REFERENCES findings(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            agent_run_id TEXT,
            profile_id TEXT,
            custom_metadata TEXT DEFAULT 'baseline',
            pair_key TEXT GENERATED ALWAYS AS (person_a || ':' || person_b) VIRTUAL
        );
        CREATE TABLE connection_evidence (
            connection_id INTEGER NOT NULL REFERENCES connections(id),
            evidence_type TEXT NOT NULL,
            evidence_ref TEXT NOT NULL,
            PRIMARY KEY (connection_id, evidence_ref)
        );
        CREATE TABLE custom_child (
            id INTEGER PRIMARY KEY,
            connection_id INTEGER NOT NULL REFERENCES connections(id) ON DELETE CASCADE
        );
        CREATE TABLE metadata_audit(connection_id INTEGER, new_metadata TEXT);
        CREATE INDEX idx_connection_fixture_metadata ON connections(custom_metadata);
        CREATE TRIGGER connection_fixture_metadata AFTER UPDATE OF custom_metadata ON connections
        BEGIN
            INSERT INTO metadata_audit VALUES(new.id, new.custom_metadata);
        END;
        INSERT INTO connections (
            id, person_a, person_b, relationship_type, description, strength,
            date_range, created_at, agent_run_id, profile_id, custom_metadata
        ) VALUES (
            41, 'Alpha', 'Beta', 'financial', 'Preserve description', 'strong',
            '2026', '2026-01-02 03:04:05', 'original-agent', 'schema-fixture', 'custom provenance'
        );
        INSERT INTO connection_evidence VALUES (41, 'ref', 'FIXTURE:original-evidence');
        INSERT INTO custom_child VALUES (7, 41);
        UPDATE sqlite_sequence SET seq=900 WHERE name='connections';
    """)


@pytest.mark.parametrize("foreign_keys", [0, 1])
def test_legacy_connection_startup_preserves_metadata_dependents_and_fk_setting(
    tmp_path, foreign_keys
):
    db = sqlite3.connect(tmp_path / "historical.db")
    db.row_factory = sqlite3.Row
    _legacy_connections(db)
    db.execute(f"PRAGMA foreign_keys={foreign_keys}")
    original = dict(db.execute("SELECT * FROM connections").fetchone())
    old_columns = [tuple(row) for row in db.execute("PRAGMA table_xinfo(connections)")]
    old_objects = {tuple(row) for row in db.execute(
        "SELECT name, sql FROM sqlite_master WHERE tbl_name='connections' "
        "AND type IN ('index','trigger') AND sql IS NOT NULL"
    )}

    lead_tracker._ensure_schema(db)

    migrated = dict(db.execute("SELECT * FROM connections").fetchone())
    assert {column: migrated[column] for column in original} == original
    assert [tuple(row) for row in db.execute("PRAGMA table_xinfo(connections)")][:len(old_columns)] == old_columns
    assert old_objects <= {tuple(row) for row in db.execute(
        "SELECT name, sql FROM sqlite_master WHERE tbl_name='connections' "
        "AND type IN ('index','trigger') AND sql IS NOT NULL"
    )}
    assert [tuple(row) for row in db.execute("SELECT * FROM custom_child")] == [(7, 41)]
    assert tuple(db.execute(
        "SELECT connection_id, evidence_ref FROM connection_evidence"
    ).fetchone()) == (41, "FIXTURE:original-evidence")
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == foreign_keys
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.execute(
        "SELECT seq FROM sqlite_sequence WHERE name='connections'"
    ).fetchone()[0] == 900
    assert not lead_tracker._widen_connections_relationships(db)

    new_id = db.execute(
        "INSERT INTO connections(person_a, person_b, relationship_type, agent_run_id) "
        "VALUES ('Parent', 'Subsidiary', 'owns', 'new-agent')"
    ).lastrowid
    assert new_id == 901
    db.execute("UPDATE connections SET custom_metadata='edited' WHERE id=41")
    assert [tuple(row) for row in db.execute("SELECT * FROM metadata_audit")] == [(41, "edited")]
    db.commit()
    db.execute("PRAGMA foreign_keys=ON")
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        db.execute("INSERT INTO custom_child VALUES (8, 999999)")
    db.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        db.execute(
            "INSERT INTO connection_evidence VALUES (999999, 'ref', 'FIXTURE:orphan', NULL, NULL, NULL)"
        )
    db.close()


@pytest.mark.parametrize("foreign_keys", [0, 1])
def test_failed_connection_rebuild_rolls_back_and_restores_fk_setting(tmp_path, foreign_keys):
    db = sqlite3.connect(tmp_path / "failed-rebuild.db")
    _legacy_connections(db)
    db.execute("CREATE TABLE findings(id INTEGER PRIMARY KEY)")
    db.execute("PRAGMA ignore_check_constraints=ON")
    db.execute("UPDATE connections SET relationship_type='invalid-legacy-value' WHERE id=41")
    db.commit()
    db.execute("PRAGMA ignore_check_constraints=OFF")
    db.execute(f"PRAGMA foreign_keys={foreign_keys}")
    schema_before = db.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall()
    rows_before = db.execute("SELECT * FROM connections").fetchall()

    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint"):
        lead_tracker._widen_connections_relationships(db)

    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == foreign_keys
    assert not db.in_transaction
    assert db.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall() == schema_before
    assert db.execute("SELECT * FROM connections").fetchall() == rows_before
    assert db.execute("SELECT * FROM custom_child").fetchall() == [(7, 41)]
    db.close()
