"""Regression tests for seed(): only UNIQUE violations count as dedups.

A seed pillar with an invalid enum value (e.g. status 'unknown') used to be
silently swallowed as "already existed" because every sqlite3.IntegrityError
was treated as a duplicate.
"""

import sqlite3

import pytest

from tools import pillar_tracker


@pytest.fixture
def pillar_db(monkeypatch, tmp_path):
    db_path = tmp_path / "pillars.db"
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    pillar_tracker._ensure_pillar_schema(db)
    db.commit()
    db.close()

    def open_db():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    monkeypatch.setattr(pillar_tracker, "get_pillar_db", open_db)
    return open_db


def _seed_with(monkeypatch, entries):
    monkeypatch.setattr(pillar_tracker, "_load_seed_pillars", lambda: entries)


def test_seed_warns_on_invalid_status_instead_of_counting_dedup(pillar_db, monkeypatch, capsys):
    _seed_with(monkeypatch, [
        {"name": "Valid Pillar", "pillar_type": "banking"},
        {"name": "Nexus Centre for Peace and Health", "pillar_type": "philanthropy", "status": "unknown"},
    ])

    created = pillar_tracker.seed()

    out = capsys.readouterr().out
    assert created == 1
    assert "WARNING: seed pillar 'Nexus Centre for Peace and Health': invalid status 'unknown'" in out
    assert "1 created, 0 already existed, 1 invalid" in out

    db = pillar_db()
    names = [r["name"] for r in db.execute("SELECT name FROM institutional_pillars").fetchall()]
    db.close()
    assert names == ["Valid Pillar"]


def test_seed_warns_on_invalid_pillar_type(pillar_db, monkeypatch, capsys):
    _seed_with(monkeypatch, [{"name": "Mystery Org", "pillar_type": "cult"}])

    created = pillar_tracker.seed()

    out = capsys.readouterr().out
    assert created == 0
    assert "WARNING: seed pillar 'Mystery Org': invalid pillar_type 'cult'" in out
    assert "0 created, 0 already existed, 1 invalid" in out


def test_seed_counts_unique_violation_as_already_existed(pillar_db, monkeypatch, capsys):
    _seed_with(monkeypatch, [{"name": "Valid Pillar", "pillar_type": "banking"}])

    assert pillar_tracker.seed() == 1
    assert pillar_tracker.seed() == 0

    out = capsys.readouterr().out
    assert "0 created, 1 already existed" in out
    assert "invalid" not in out
    assert "WARNING" not in out


def test_seed_warns_on_non_unique_integrity_error(pillar_db, monkeypatch, capsys):
    # Passes enum pre-validation but violates NOT NULL on name at insert time,
    # exercising the IntegrityError classification directly.
    _seed_with(monkeypatch, [{"name": None, "pillar_type": "banking"}])

    created = pillar_tracker.seed()

    out = capsys.readouterr().out
    assert created == 0
    assert "WARNING: seed pillar 'None' rejected: NOT NULL constraint failed" in out
    assert "0 created, 0 already existed, 1 invalid" in out
