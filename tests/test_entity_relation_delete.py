"""Tests for entity_tracker.py `delete-relation` graph-hygiene verb.

Covers: delete by relation-id, delete by triple, the multi-match guard,
the corrections audit record being written, and dry-run making no change.
"""
from __future__ import annotations

import argparse

import pytest

from tools import entity_tracker


@pytest.fixture
def entity_db(tmp_path, monkeypatch):
    """Fresh investigation DB wired into entity_tracker + lead_tracker.

    Seeds a few entities and relation edges to prune.
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("tools.lead_tracker.DB_PATH", db_path)
    monkeypatch.setattr("tools.lead_tracker._schema_initialized", False)
    monkeypatch.setattr("tools.entity_tracker.DB_PATH", db_path)

    db = entity_tracker.get_db()
    for eid, name in [(1, "Alpha"), (2, "Beta"), (3, "Gamma")]:
        db.execute(
            "INSERT INTO entities (id, name, entity_type) VALUES (?, ?, 'person')",
            (eid, name),
        )
    # Edge 1: 1 --associate--> 2
    db.execute(
        "INSERT INTO entity_relations (entity_a_id, entity_b_id, relation_type, source) "
        "VALUES (1, 2, 'associate', 'seed')"
    )
    # Edge 2: 1 --custodian--> 3
    db.execute(
        "INSERT INTO entity_relations (entity_a_id, entity_b_id, relation_type, source) "
        "VALUES (1, 3, 'custodian', 'seed')"
    )
    db.commit()
    db.close()
    return db_path


def _args(**kw):
    defaults = dict(
        relation_id=None,
        entity_a_id=None,
        entity_b_id=None,
        relation_type=None,
        reason="test reason",
        actor="tester",
        dry_run=False,
    )
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def _relations(db_path):
    db = entity_tracker.get_db()
    rows = [dict(r) for r in db.execute("SELECT * FROM entity_relations ORDER BY id")]
    db.close()
    return rows


def _corrections(db_path):
    db = entity_tracker.get_db()
    rows = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM corrections WHERE table_name = 'entity_relations'"
        )
    ]
    db.close()
    return rows


class TestDeleteRelation:
    def test_delete_by_relation_id(self, entity_db):
        entity_tracker.cmd_delete_relation(_args(relation_id=1))
        rels = _relations(entity_db)
        assert [r["id"] for r in rels] == [2]

    def test_delete_by_triple(self, entity_db):
        entity_tracker.cmd_delete_relation(
            _args(entity_a_id=1, entity_b_id=3, relation_type="custodian")
        )
        rels = _relations(entity_db)
        assert [r["id"] for r in rels] == [1]

    def test_audit_record_written(self, entity_db):
        entity_tracker.cmd_delete_relation(
            _args(relation_id=1, reason="wrong edge", actor="tester")
        )
        corrections = _corrections(entity_db)
        assert len(corrections) == 1
        c = corrections[0]
        assert c["record_id"] == 1
        assert c["field_name"] == "deleted"
        assert c["reason"] == "wrong edge"
        assert c["corrected_by"] == "tester"
        assert c["correction_type"] == "retraction"
        # Full deleted row preserved for recoverability
        assert "associate" in c["old_value"]

    def test_multi_match_guard(self, entity_db, monkeypatch):
        # A UNIQUE(entity_a_id, entity_b_id, relation_type) constraint normally
        # prevents duplicate triples, but the guard defends against legacy/legacy
        # multi-match rows. Force a two-row match to exercise the refusal path.
        real_get_db = entity_tracker.get_db

        class MultiCursor:
            def fetchall(self):
                return [
                    {"id": 1, "entity_a_id": 1, "entity_b_id": 2,
                     "relation_type": "associate", "description": None, "source": "a"},
                    {"id": 5, "entity_a_id": 1, "entity_b_id": 2,
                     "relation_type": "associate", "description": None, "source": "b"},
                ]

        class MultiDB:
            def __init__(self):
                self.inner = real_get_db()
                self.closed = False

            def execute(self, *a, **k):
                return MultiCursor()

            def close(self):
                self.inner.close()
                self.closed = True

        monkeypatch.setattr(entity_tracker, "get_db", lambda: MultiDB())

        with pytest.raises(SystemExit):
            entity_tracker.cmd_delete_relation(
                _args(entity_a_id=1, entity_b_id=2, relation_type="associate")
            )
        # Restore and confirm nothing was deleted / no audit entry
        monkeypatch.setattr(entity_tracker, "get_db", real_get_db)
        assert len(_relations(entity_db)) == 2
        assert len(_corrections(entity_db)) == 0

    def test_dry_run_makes_no_change(self, entity_db):
        entity_tracker.cmd_delete_relation(_args(relation_id=1, dry_run=True))
        assert len(_relations(entity_db)) == 2
        assert len(_corrections(entity_db)) == 0

    def test_no_match_exits(self, entity_db):
        with pytest.raises(SystemExit):
            entity_tracker.cmd_delete_relation(_args(relation_id=999))

    def test_requires_selector(self, entity_db):
        with pytest.raises(SystemExit):
            entity_tracker.cmd_delete_relation(_args())
