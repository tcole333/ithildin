"""Regression coverage for profile-scoped auto-lead generation."""

from __future__ import annotations

import argparse
import sqlite3
from types import SimpleNamespace

import pytest

import tools.auto_leads as auto_leads


@pytest.fixture
def crossref_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY, name TEXT, entity_type TEXT, jurisdiction TEXT
        );
        CREATE TABLE entity_roles (
            id INTEGER PRIMARY KEY, entity_id INTEGER, person_name TEXT
        );
        CREATE TABLE connections (
            id INTEGER PRIMARY KEY, person_a TEXT, person_b TEXT
        );
        CREATE TABLE findings (id INTEGER PRIMARY KEY, target_name TEXT);
        CREATE TABLE auto_crossref_log (
            id INTEGER PRIMARY KEY, table_name TEXT, record_id INTEGER,
            crossref_type TEXT, lead_id INTEGER,
            UNIQUE(table_name, record_id, crossref_type)
        );
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY, title TEXT, category TEXT, priority TEXT,
            status TEXT, source TEXT, target_name TEXT, profile_id TEXT,
            thread_id INTEGER, created_at TEXT
        );
        CREATE TABLE lead_notes (
            id INTEGER PRIMARY KEY, lead_id INTEGER, note TEXT, created_at TEXT
        );
        """
    )
    auto_leads._leads_created_this_run = 0
    yield db
    db.close()


def test_cmd_run_propagates_active_profile_to_every_generator(monkeypatch):
    """Both global-data and thread-scoped branches receive the active profile."""
    calls = {}
    generator_names = [
        "process_new_addresses", "process_new_roles", "process_new_entities",
        "process_new_connections", "process_alumni_clustering", "process_pillar_gaps",
        "process_officer_escalation", "process_filing_clusters",
        "process_jurisdiction_clusters", "process_entity_crossref",
        "process_person_crossref", "process_enforcement_check",
        "process_findings_coverage_gaps", "process_contract_patterns",
        "process_connection_persons",
    ]

    class FakeDb:
        def close(self):
            pass

    monkeypatch.setattr(auto_leads, "get_db", lambda: FakeDb())
    monkeypatch.setattr(
        auto_leads, "_load_profile",
        lambda _name=None: SimpleNamespace(name="fink", bridge_threads=[]),
    )
    monkeypatch.setattr(auto_leads, "get_profile_thread_ids", lambda *_args: {87})

    def recorder(name):
        def run(*args):
            calls[name] = args
            return 0, 0
        return run

    for name in generator_names:
        monkeypatch.setattr(auto_leads, name, recorder(name))

    auto_leads.cmd_run(argparse.Namespace(
        profile="fink", dry_run=True, max_leads=100,
    ))

    assert set(calls) == set(generator_names)
    for name, args in calls.items():
        assert "fink" in args, f"{name} did not receive active profile: {args!r}"


def test_exact_entity_identity_is_suppressed(crossref_db):
    db = crossref_db
    db.execute("INSERT INTO entities VALUES (1, 'LumaBio I LP', 'fund', 'DE')")
    db.execute("INSERT INTO connections VALUES (1, 'LumaBio I LP', 'Another Person')")
    db.execute("INSERT INTO findings VALUES (1, 'LumaBio I LP')")

    assert auto_leads.process_entity_crossref(db, profile_id="fink") == (0, 1)
    assert db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0


def test_exact_person_identity_is_suppressed(crossref_db):
    db = crossref_db
    db.execute("INSERT INTO entities VALUES (1, 'Luma Group', 'fund', 'DE')")
    db.execute("INSERT INTO entity_roles VALUES (1, 1, 'Joshua Aaron Fink')")
    db.execute("INSERT INTO connections VALUES (1, 'Joshua Aaron Fink', 'Another Person')")
    db.execute("INSERT INTO findings VALUES (1, 'Joshua Aaron Fink')")

    assert auto_leads.process_person_crossref(db, profile_id="fink") == (0, 1)
    assert db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0


def test_shared_entities_still_fuzzy_match_and_emit_scoped_idempotently(crossref_db):
    """Global canonical entities remain matchable; their lead belongs to this run's profile."""
    db = crossref_db
    db.executemany(
        "INSERT INTO entities VALUES (?, ?, 'fund', 'DE')",
        [
            (1, "Enso Capital Management LLP"),
            (2, "Enso Capital Mgmt LLP"),
        ],
    )

    created, scanned = auto_leads.process_entity_crossref(db, profile_id="fink")
    assert scanned == 2
    assert created == 2
    rows = db.execute("SELECT profile_id, title FROM leads ORDER BY id").fetchall()
    assert len(rows) == 2
    assert {row["profile_id"] for row in rows} == {"fink"}
    assert all("Enso Capital" in row["title"] for row in rows)

    # The processing log makes repeat runs idempotent for globally shared rows.
    assert auto_leads.process_entity_crossref(db, profile_id="fink") == (0, 0)
    assert db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 2

