"""Regression tests for entity merges across canonical junction tables."""

import sqlite3
from types import SimpleNamespace

import pytest

from tools import entity_dedup, entity_resolution


def _seed_merge_db(path):
    db = sqlite3.connect(path)
    db.executescript(
        """
        PRAGMA foreign_keys=ON;
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            entity_type TEXT,
            jurisdiction TEXT,
            source TEXT,
            notes TEXT
        );
        CREATE TABLE findings (id INTEGER PRIMARY KEY);
        CREATE TABLE entity_roles (
            id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL REFERENCES entities(id),
            person_name TEXT NOT NULL,
            role TEXT NOT NULL,
            date_start TEXT,
            date_end TEXT,
            source TEXT,
            UNIQUE(entity_id, person_name, role)
        );
        CREATE TABLE entity_addresses (
            id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL REFERENCES entities(id),
            address TEXT NOT NULL,
            address_type TEXT NOT NULL,
            date_observed TEXT,
            source TEXT,
            UNIQUE(entity_id, address, address_type)
        );
        CREATE TABLE entity_relations (
            id INTEGER PRIMARY KEY,
            entity_a_id INTEGER NOT NULL REFERENCES entities(id),
            entity_b_id INTEGER NOT NULL REFERENCES entities(id),
            relation_type TEXT NOT NULL,
            description TEXT,
            source TEXT,
            UNIQUE(entity_a_id, entity_b_id, relation_type)
        );
        CREATE TABLE finding_entities (
            finding_id INTEGER NOT NULL REFERENCES findings(id),
            entity_id INTEGER NOT NULL REFERENCES entities(id),
            mention_role TEXT NOT NULL DEFAULT 'subject',
            raw_name TEXT,
            resolution_status TEXT NOT NULL DEFAULT 'asserted',
            resolution_method TEXT,
            resolution_score REAL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(finding_id, entity_id, mention_role)
        );
        CREATE TABLE name_aliases (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            alias TEXT NOT NULL UNIQUE,
            alias_type TEXT NOT NULL,
            entity_id INTEGER REFERENCES entities(id),
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE institutional_pillars (
            id INTEGER PRIMARY KEY,
            entity_id INTEGER NOT NULL REFERENCES entities(id),
            pillar_id INTEGER NOT NULL,
            UNIQUE(entity_id, pillar_id)
        );

        INSERT INTO entities VALUES
            (1, 'Canonical Person', 'person', 'US', 'keep-source', 'keep notes'),
            (2, 'Alias Person', 'person', 'US', 'drop-source', 'drop notes'),
            (3, 'Example Org', 'corporation', 'US', 'org-source', NULL),
            (4, 'Other Person', 'person', 'US', 'other-source', NULL);
        INSERT INTO findings VALUES (10), (11);

        INSERT INTO entity_roles
            (id, entity_id, person_name, role, source)
        VALUES (1, 2, 'Alias Person', 'director', 'role-source');
        INSERT INTO entity_addresses
            (id, entity_id, address, address_type, source)
        VALUES (1, 2, '1 Main St', 'registered', 'address-source');

        INSERT INTO entity_relations VALUES
            (1, 1, 3, 'officer_of', 'keep relation', 'keep-rel-source'),
            (2, 2, 3, 'officer_of', 'drop relation', 'drop-rel-source'),
            (3, 2, 1, 'same_as', 'merge pair', 'same-as-source'),
            (4, 3, 2, 'employed_by', 'reverse relation', 'reverse-source');

        INSERT INTO finding_entities VALUES
            (10, 1, 'subject', 'Canonical Person', 'candidate', 'fuzzy', 0.60,
             '2026-02-01 00:00:00'),
            (10, 2, 'subject', 'Alias Person', 'reviewed', 'manual', 0.95,
             '2026-01-01 00:00:00'),
            (11, 2, 'mentioned', 'Alias Person', 'asserted', 'exact', 1.00,
             '2026-03-01 00:00:00');

        INSERT INTO name_aliases
            (id, canonical_name, alias, alias_type, entity_id, created_by)
        VALUES (1, 'Alias Person', 'Previous Alias', 'entity_variant', 2, 'test');
        INSERT INTO institutional_pillars VALUES (1, 1, 7), (2, 2, 7);
        """
    )
    db.commit()
    db.close()


def _assert_merged(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")

    assert db.execute("SELECT 1 FROM entities WHERE id=2").fetchone() is None
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []

    links = db.execute(
        """SELECT * FROM finding_entities
           WHERE entity_id=1 ORDER BY finding_id, mention_role"""
    ).fetchall()
    assert [(row["finding_id"], row["mention_role"]) for row in links] == [
        (10, "subject"),
        (11, "mentioned"),
    ]
    collision = links[0]
    assert collision["raw_name"] == "Alias Person"
    assert collision["resolution_status"] == "reviewed"
    assert collision["resolution_method"] == "manual"
    assert collision["resolution_score"] == pytest.approx(0.95)
    assert collision["created_at"] == "2026-01-01 00:00:00"

    relations = db.execute(
        "SELECT * FROM entity_relations ORDER BY entity_a_id, entity_b_id, relation_type"
    ).fetchall()
    assert all(row["entity_a_id"] != row["entity_b_id"] for row in relations)
    assert all(2 not in (row["entity_a_id"], row["entity_b_id"]) for row in relations)
    officer = next(row for row in relations if row["relation_type"] == "officer_of")
    assert "keep relation" in officer["description"]
    assert "drop relation" in officer["description"]
    assert officer["source"] == "keep-rel-source,drop-rel-source"
    assert any(
        (row["entity_a_id"], row["entity_b_id"], row["relation_type"])
        == (3, 1, "employed_by")
        for row in relations
    )

    aliases = {
        row["alias"]: row
        for row in db.execute("SELECT * FROM name_aliases ORDER BY alias")
    }
    assert aliases["Alias Person"]["entity_id"] == 1
    assert aliases["Alias Person"]["canonical_name"] == "Canonical Person"
    assert aliases["Alias Person"]["alias_type"] == "person_variant"
    assert aliases["Previous Alias"]["entity_id"] == 1
    assert aliases["Previous Alias"]["alias_type"] == "person_variant"

    assert db.execute(
        "SELECT entity_id FROM entity_roles WHERE person_name='Alias Person'"
    ).fetchone()[0] == 1
    assert db.execute(
        "SELECT entity_id FROM entity_addresses WHERE address='1 Main St'"
    ).fetchone()[0] == 1
    assert db.execute(
        "SELECT COUNT(*) FROM institutional_pillars WHERE entity_id=1 AND pillar_id=7"
    ).fetchone()[0] == 1

    entity = db.execute("SELECT * FROM entities WHERE id=1").fetchone()
    assert "drop notes" in entity["notes"]
    assert entity["source"] == "keep-source,drop-source"
    db.close()


@pytest.mark.parametrize("command", ["entity_resolution", "entity_dedup"])
def test_merge_commands_preserve_junctions_and_avoid_self_relations(
    tmp_path, monkeypatch, command
):
    path = tmp_path / f"{command}.db"
    _seed_merge_db(path)

    if command == "entity_resolution":
        monkeypatch.setattr(entity_resolution, "DB_PATH", path)
        entity_resolution.cmd_merge(
            SimpleNamespace(keep_id=1, drop_id=2, dry_run=False)
        )
    else:
        monkeypatch.setattr(entity_dedup, "DB_PATH", path)
        entity_dedup.cmd_merge(
            SimpleNamespace(keep_id=1, delete_id=2, dry_run=False)
        )

    _assert_merged(path)


def test_merge_rejects_alias_owned_by_third_entity(tmp_path):
    path = tmp_path / "alias-conflict.db"
    _seed_merge_db(path)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute(
        """INSERT INTO name_aliases
           (canonical_name, alias, alias_type, entity_id, created_by)
           VALUES ('Other Person', 'Alias Person', 'person_variant', 4, 'test')"""
    )
    db.commit()

    with pytest.raises(ValueError, match="already belongs"):
        entity_resolution.merge_entity_records(db, 1, 2, created_by="test")
    db.rollback()

    assert db.execute("SELECT 1 FROM entities WHERE id=2").fetchone() is not None
    assert db.execute(
        "SELECT COUNT(*) FROM finding_entities WHERE entity_id=2"
    ).fetchone()[0] == 2
    db.close()
