from __future__ import annotations

import sqlite3

import pytest

from tools import auto_leads
from tools.entity_resolution import (
    is_abstract_entity_target,
    resolve_or_create_entity,
)
from tools.findings_tracker import _link_finding_entity


ABSTRACT_TARGETS = [
    "Reodica divorce property cluster",
    "Hacienda Heights divorce-property cluster",
    "August 1988 trust-transfer parcel cluster",
    "Reodica divorce property schedule",
    "Golden Land officer-address parcels",
]


@pytest.fixture
def target_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY, name TEXT, entity_type TEXT,
            jurisdiction TEXT, ein TEXT, address TEXT, status TEXT,
            source TEXT, notes TEXT, agent_run_id TEXT,
            UNIQUE(name, jurisdiction)
        );
        CREATE TABLE name_aliases (
            id INTEGER PRIMARY KEY, canonical_name TEXT, alias TEXT,
            alias_type TEXT, entity_id INTEGER, created_by TEXT,
            UNIQUE(alias, alias_type)
        );
        CREATE TABLE findings (
            id INTEGER PRIMARY KEY, target_name TEXT, finding_type TEXT,
            summary TEXT, detail TEXT, source_datasets TEXT, thread_id INTEGER
        );
        CREATE TABLE finding_entities (
            finding_id INTEGER, entity_id INTEGER, mention_role TEXT,
            raw_name TEXT, resolution_status TEXT, resolution_method TEXT,
            resolution_score REAL,
            UNIQUE(finding_id, entity_id, mention_role)
        );
        CREATE TABLE connections (
            id INTEGER PRIMARY KEY, person_a TEXT, person_b TEXT
        );
        CREATE TABLE auto_crossref_log (
            id INTEGER PRIMARY KEY, table_name TEXT, record_id INTEGER,
            crossref_type TEXT, lead_id INTEGER,
            UNIQUE(table_name, record_id, crossref_type)
        );
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY, title TEXT, description TEXT, category TEXT,
            priority TEXT, status TEXT, source TEXT, target_name TEXT,
            profile_id TEXT, thread_id INTEGER, created_at TEXT
        );
        CREATE TABLE lead_notes (
            id INTEGER PRIMARY KEY, lead_id INTEGER, note TEXT, created_at TEXT
        );
        """
    )
    auto_leads._leads_created_this_run = 0
    yield db
    db.close()


@pytest.mark.parametrize("target", ABSTRACT_TARGETS)
def test_original_finding_target_patterns_are_abstract(target):
    assert is_abstract_entity_target(target)


def test_finding_link_does_not_create_pseudo_entities(target_db):
    target_db.executemany(
        "INSERT INTO findings(id, target_name) VALUES (?, ?)",
        [(12075 + index, target) for index, target in enumerate(ABSTRACT_TARGETS)],
    )

    for index, target in enumerate(ABSTRACT_TARGETS):
        assert _link_finding_entity(target_db, 12075 + index, target) is None

    assert target_db.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == 0
    assert target_db.execute("SELECT COUNT(*) FROM finding_entities").fetchone()[0] == 0


def test_named_or_typed_organizations_remain_linkable(target_db):
    assert not is_abstract_entity_target("Golden Land Capital, Inc.")
    assert not is_abstract_entity_target("Reodica Property Cluster LLC")

    named = resolve_or_create_entity(
        target_db,
        "Golden Land Capital, Inc.",
        entity_type="unknown",
        source="auto:finding",
    )
    typed = resolve_or_create_entity(
        target_db,
        "Reodica property cluster",
        entity_type="llc",
        source="auto:finding",
    )

    assert named.action == "created"
    assert typed.action == "created"

    # A later unknown finding target can resolve a previously registered entity
    # even when its bare name resembles an analytical label.
    linked = resolve_or_create_entity(
        target_db,
        "Reodica property cluster",
        entity_type="unknown",
        source="auto:finding",
    )
    assert linked.action == "exact"
    assert linked.entity_id == typed.entity_id


def test_legacy_abstract_entities_do_not_generate_fuzzy_crossrefs(target_db):
    target_db.executemany(
        "INSERT INTO entities(id, name, entity_type) VALUES (?, ?, 'unknown')",
        [
            (1, "Reodica divorce property cluster"),
            (2, "Reodica divorce parcel cluster"),
        ],
    )

    assert auto_leads.process_entity_crossref(
        target_db, profile_id="coscoluella"
    ) == (0, 2)
    assert target_db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0
    assert target_db.execute(
        "SELECT COUNT(*) FROM auto_crossref_log WHERE crossref_type='entity_crossref'"
    ).fetchone()[0] == 2


def test_residential_flags_require_typed_org_and_contract_source(target_db):
    residential_detail = (
        "The record identifies a residential home address and single-family property "
        "associated with the subject."
    )
    target_db.executemany(
        """INSERT INTO findings
               (id, target_name, summary, detail, source_datasets, thread_id)
           VALUES (?, ?, ?, ?, ?, 72)""",
        [
            (
                12076,
                "Hacienda Heights divorce-property cluster",
                "Assessor parcel history",
                residential_detail,
                '["la_county_assessor"]',
            ),
            (
                13001,
                "Acme Defense LLC",
                "Company address profile",
                residential_detail,
                '["web_search"]',
            ),
            (
                13002,
                "Acme Defense LLC",
                "USAspending award address",
                residential_detail,
                '["usaspending"]',
            ),
            (
                13003,
                "Unclassified award target",
                "USAspending award address",
                residential_detail,
                '["usaspending"]',
            ),
        ],
    )
    target_db.executemany(
        "INSERT INTO entities(id, name, entity_type) VALUES (?, ?, ?)",
        [
            (1, "Acme Defense LLC", "llc"),
            (2, "Unclassified award target", "unknown"),
        ],
    )
    target_db.executemany(
        "INSERT INTO finding_entities(finding_id, entity_id, mention_role) VALUES (?, ?, 'subject')",
        [(13001, 1), (13002, 1), (13003, 2)],
    )

    assert auto_leads.process_contract_patterns(
        target_db, {72}, "coscoluella"
    ) == (1, 1)

    leads = target_db.execute(
        "SELECT title, target_name FROM leads ORDER BY id"
    ).fetchall()
    assert [row["target_name"] for row in leads] == ["Acme Defense LLC"]
    assert leads[0]["title"].startswith("Residential address flag: Acme Defense LLC")
