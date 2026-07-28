from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from tools import entity_tracker, lead_tracker, merge_person_names
from tools.entity_resolution import (
    EntityResolutionAmbiguity,
    is_abstract_entity_target,
    resolve_or_create_entity,
)
from tools.findings_tracker import _link_finding_entity


def _resolution_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            entity_type TEXT,
            jurisdiction TEXT,
            ein TEXT,
            address TEXT,
            status TEXT,
            source TEXT,
            notes TEXT,
            agent_run_id TEXT,
            UNIQUE(name, jurisdiction)
        );
        CREATE TABLE name_aliases (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT,
            alias TEXT,
            alias_type TEXT,
            entity_id INTEGER,
            created_by TEXT,
            UNIQUE(alias, alias_type)
        );
        CREATE TABLE finding_entities (
            finding_id INTEGER,
            entity_id INTEGER,
            mention_role TEXT,
            raw_name TEXT,
            resolution_status TEXT,
            resolution_method TEXT,
            resolution_score REAL,
            UNIQUE(finding_id, entity_id, mention_role)
        );
        """
    )
    return db


@pytest.mark.parametrize(
    "target",
    [
        "Brad S. Karp / Continental Grain Company",
        "BII Holding Corporation / Behavioral Holding Corp. / B.I. Incorporated",
        "B.I. Incorporated corporate lineage",
        "B.I. Incorporated identity resolution",
    ],
)
def test_compound_analytical_targets_are_not_auto_entities(target):
    db = _resolution_db()

    result = resolve_or_create_entity(
        db,
        target,
        entity_type="unknown",
        source="auto:finding",
    )

    assert is_abstract_entity_target(target)
    assert result.action == "suppressed"
    assert result.entity_id is None
    assert db.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == 0
    db.close()


def test_legacy_auto_finding_compound_is_not_linked_again():
    db = _resolution_db()
    target = "Brad S. Karp / Continental Grain Company"
    db.execute(
        """
        INSERT INTO entities(id, name, entity_type, source)
        VALUES (1, ?, 'unknown', 'auto:finding')
        """,
        (target,),
    )

    result = resolve_or_create_entity(
        db,
        target,
        entity_type="unknown",
        source="auto:finding",
    )

    assert result.action == "suppressed"
    assert result.entity_id is None
    db.close()


def test_fec_qualified_target_resolves_one_canonical_pac():
    db = _resolution_db()
    db.execute(
        """
        INSERT INTO entities(id, name, entity_type, jurisdiction, source)
        VALUES (1, 'The Sentinel Action Fund', 'pac', 'Federal', 'fec')
        """
    )

    result = resolve_or_create_entity(
        db,
        "The Sentinel Action Fund (C00811166)",
        entity_type="unknown",
        source="auto:finding",
    )

    assert result.entity_id == 1
    assert result.action == "qualified_identifier"
    assert db.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == 1
    db.close()


def test_fec_qualified_target_surfaces_ambiguous_canonical_pacs():
    db = _resolution_db()
    db.executemany(
        """
        INSERT INTO entities(id, name, entity_type, jurisdiction, source)
        VALUES (?, 'The Sentinel Action Fund', 'pac', ?, 'fec')
        """,
        [(1, "Federal"), (2, "District of Columbia")],
    )

    with pytest.raises(EntityResolutionAmbiguity, match="#1, #2"):
        resolve_or_create_entity(
            db,
            "The Sentinel Action Fund (C00811166)",
            entity_type="unknown",
            source="auto:finding",
        )

    assert db.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == 2
    db.close()


def test_finding_link_reports_fec_ambiguity_without_creating_entity(capsys):
    db = _resolution_db()
    db.executemany(
        """
        INSERT INTO entities(id, name, entity_type, jurisdiction, source)
        VALUES (?, 'The Sentinel Action Fund', 'pac', ?, 'fec')
        """,
        [(1, "Federal"), (2, "District of Columbia")],
    )

    linked_id = _link_finding_entity(
        db, 42, "The Sentinel Action Fund (C00811166)"
    )

    assert linked_id is None
    assert "matches multiple canonical entities (#1, #2)" in capsys.readouterr().err
    assert db.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM finding_entities").fetchone()[0] == 0
    db.close()


def test_add_role_reports_ignored_duplicate(tmp_path, monkeypatch, capsys):
    path = tmp_path / "roles.db"
    monkeypatch.setattr(lead_tracker, "DB_PATH", path)
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    monkeypatch.setattr(entity_tracker, "DB_PATH", path)
    db = entity_tracker.get_db()
    db.execute(
        "INSERT INTO entities(id, name, entity_type) VALUES (1, 'Example Inc.', 'inc')"
    )
    db.execute(
        """
        INSERT INTO entity_roles(
            entity_id, person_name, role, date_start, date_end, source
        ) VALUES (1, 'Example Person', 'CEO', '1994-01-01', '2021-12-31', 'filing')
        """
    )
    db.commit()
    db.close()

    inserted = entity_tracker.cmd_add_role(
        SimpleNamespace(
            entity_id=1,
            person_name="Example Person",
            role="CEO",
            date_start="2026-03-01",
            date_end=None,
            source="press_release",
        )
    )

    assert inserted is False
    output = capsys.readouterr().out
    assert "Role already exists; no row recorded" in output
    assert "existing tenure: 1994-01-01 to 2021-12-31" in output
    assert "cannot represent a second tenure" in output


def test_person_merge_preserves_slash_qualified_finding(
    tmp_path, monkeypatch
):
    path = tmp_path / "person-merge.db"
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE findings (
            id INTEGER PRIMARY KEY,
            target_name TEXT
        );
        CREATE TABLE connections (
            id INTEGER PRIMARY KEY,
            person_a TEXT,
            person_b TEXT,
            relationship_type TEXT,
            profile_id TEXT
        );
        CREATE TABLE name_aliases (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT,
            alias TEXT,
            alias_type TEXT,
            entity_id INTEGER,
            created_by TEXT,
            UNIQUE(alias, alias_type)
        );
        CREATE TABLE corrections (
            id INTEGER PRIMARY KEY,
            table_name TEXT,
            record_id INTEGER,
            field_name TEXT,
            old_value TEXT,
            new_value TEXT,
            reason TEXT,
            corrected_by TEXT,
            correction_type TEXT
        );
        INSERT INTO findings(id, target_name) VALUES
            (1, 'Brad Karp'),
            (2, 'Brad S. Karp / Credit Suisse Archegos investigation');
        """
    )
    db.commit()
    db.close()
    monkeypatch.setattr(merge_person_names, "DB_PATH", path)

    merge_person_names.cmd_merge(
        SimpleNamespace(
            alias="Brad Karp",
            canonical="Brad S. Karp",
            entity_id=3720,
            dry_run=False,
        )
    )

    db = sqlite3.connect(path)
    rows = db.execute(
        "SELECT id, target_name FROM findings ORDER BY id"
    ).fetchall()
    db.close()
    assert rows == [
        (1, "Brad S. Karp"),
        (2, "Brad S. Karp / Credit Suisse Archegos investigation"),
    ]
