"""Regression tests for safe institutional-pillar bootstrap matching."""

import sqlite3
from types import SimpleNamespace

import pytest

from tools import investigation_context
from tools import pillar_tracker


@pytest.fixture
def pillar_db(monkeypatch, tmp_path):
    db_path = tmp_path / "pillars.db"
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(
        """
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );
        CREATE TABLE entity_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id INTEGER NOT NULL REFERENCES entities(id),
            person_name TEXT NOT NULL,
            role TEXT NOT NULL,
            date_start TEXT,
            date_end TEXT,
            source TEXT
        );
        CREATE TABLE connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_a TEXT,
            person_b TEXT,
            relationship_type TEXT,
            description TEXT,
            date_range TEXT
        );
        CREATE TABLE findings (id INTEGER PRIMARY KEY);
        CREATE TABLE name_aliases (
            canonical_name TEXT,
            alias TEXT,
            alias_type TEXT
        );
        """
    )
    pillar_tracker._ensure_pillar_schema(db)
    db.commit()
    db.close()

    def open_db():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    monkeypatch.setattr(pillar_tracker, "get_pillar_db", open_db)
    monkeypatch.setattr(
        investigation_context,
        "get_active_profile",
        lambda: SimpleNamespace(primary_subject="Excluded Subject"),
    )
    return db_path, open_db


def _add_entity_role(db, entity_name, person_name="Test Officer", role="officer"):
    entity_id = db.execute(
        "INSERT INTO entities(name) VALUES (?)",
        (entity_name,),
    ).lastrowid
    db.execute(
        "INSERT INTO entity_roles(entity_id, person_name, role) VALUES (?, ?, ?)",
        (entity_id, person_name, role),
    )
    return entity_id


def test_bootstrap_does_not_map_cia_substring_inside_financial(pillar_db):
    _, open_db = pillar_db
    db = open_db()
    db.execute(
        "INSERT INTO institutional_pillars(name, pillar_type) VALUES ('CIA', 'intelligence')"
    )
    _add_entity_role(db, "Financial Trust Company, Inc.", person_name="False Officer")
    db.commit()
    db.close()

    stats = pillar_tracker.bootstrap()

    db = open_db()
    assert db.execute("SELECT COUNT(*) FROM career_arcs").fetchone()[0] == 0
    db.close()
    assert stats["arcs_created"] == 0


def test_employment_bootstrap_does_not_map_cia_substring_inside_financial(pillar_db):
    _, open_db = pillar_db
    db = open_db()
    db.execute(
        "INSERT INTO institutional_pillars(name, pillar_type) VALUES ('CIA', 'intelligence')"
    )
    db.execute(
        """
        INSERT INTO connections(person_a, person_b, relationship_type, description)
        VALUES ('False Employee', 'Financial Trust Company, Inc.', 'employment', 'employee')
        """
    )
    db.commit()
    db.close()

    stats = pillar_tracker.bootstrap()

    db = open_db()
    assert db.execute("SELECT COUNT(*) FROM career_arcs").fetchone()[0] == 0
    db.close()
    assert stats["arcs_created"] == 0
    assert stats["arcs_skipped"] == 1


def test_bootstrap_uses_explicit_pillar_entity_link(pillar_db):
    _, open_db = pillar_db
    db = open_db()
    entity_id = _add_entity_role(
        db,
        "United States Foreign Intelligence Service",
        person_name="Linked Officer",
    )
    pillar_id = db.execute(
        """
        INSERT INTO institutional_pillars(name, pillar_type, entity_id)
        VALUES ('CIA', 'intelligence', ?)
        """,
        (entity_id,),
    ).lastrowid
    db.commit()
    db.close()

    stats = pillar_tracker.bootstrap()

    db = open_db()
    arc = db.execute(
        "SELECT person_name, pillar_id, source FROM career_arcs"
    ).fetchone()
    db.close()
    assert dict(arc) == {
        "person_name": "Linked Officer",
        "pillar_id": pillar_id,
        "source": "bootstrap:entity_roles",
    }
    assert stats["arcs_created"] == 1


def test_match_institution_preserves_exact_names_and_curated_aliases(pillar_db):
    _, open_db = pillar_db
    db = open_db()
    pillar_id = db.execute(
        "INSERT INTO institutional_pillars(name, pillar_type) VALUES ('Goldman Sachs', 'banking')"
    ).lastrowid
    db.commit()

    assert pillar_tracker._match_institution("Goldman Sachs", db) == (
        pillar_id,
        "Goldman Sachs",
    )
    assert pillar_tracker._match_institution("goldman", db) == (
        pillar_id,
        "Goldman Sachs",
    )
    assert pillar_tracker._match_institution("Goldman Sachs Group Inc.", db) == (
        None,
        None,
    )
    db.close()


def test_arc_delete_removes_only_requested_arc(pillar_db):
    _, open_db = pillar_db
    db = open_db()
    pillar_id = db.execute(
        "INSERT INTO institutional_pillars(name, pillar_type) VALUES ('CIA', 'intelligence')"
    ).lastrowid
    person_id = db.execute(
        "INSERT INTO persons(canonical_name) VALUES ('Test Officer')"
    ).lastrowid
    requested_arc = db.execute(
        """
        INSERT INTO career_arcs(person_id, person_name, pillar_id, role, source)
        VALUES (?, 'Test Officer', ?, 'officer', 'bootstrap:entity_roles')
        """,
        (person_id, pillar_id),
    ).lastrowid
    retained_arc = db.execute(
        """
        INSERT INTO career_arcs(person_id, person_name, pillar_id, role, source)
        VALUES (?, 'Test Officer', ?, 'analyst', 'manual')
        """,
        (person_id, pillar_id),
    ).lastrowid
    db.commit()
    db.close()

    assert pillar_tracker.delete_arc(requested_arc) is True
    assert pillar_tracker.delete_arc(requested_arc) is False

    db = open_db()
    remaining = db.execute("SELECT id FROM career_arcs").fetchall()
    db.close()
    assert [row["id"] for row in remaining] == [retained_arc]
