from __future__ import annotations

import sqlite3

import pytest

from tools import auto_leads
from tools.entity_resolution import is_abstract_entity_target


@pytest.fixture
def identity_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY,
            name TEXT,
            entity_type TEXT,
            jurisdiction TEXT
        );
        CREATE TABLE entity_roles (
            id INTEGER PRIMARY KEY,
            entity_id INTEGER,
            person_name TEXT
        );
        CREATE TABLE connections (
            id INTEGER PRIMARY KEY,
            person_a TEXT,
            person_b TEXT,
            relationship_type TEXT,
            finding_id INTEGER,
            profile_id TEXT
        );
        CREATE TABLE findings (
            id INTEGER PRIMARY KEY,
            target_name TEXT,
            profile_id TEXT
        );
        CREATE TABLE auto_crossref_log (
            id INTEGER PRIMARY KEY,
            table_name TEXT,
            record_id INTEGER,
            crossref_type TEXT,
            lead_id INTEGER,
            UNIQUE(table_name, record_id, crossref_type)
        );
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            category TEXT,
            priority TEXT,
            status TEXT,
            source TEXT,
            target_name TEXT,
            profile_id TEXT,
            thread_id INTEGER,
            created_at TEXT
        );
        CREATE TABLE lead_notes (
            id INTEGER PRIMARY KEY,
            lead_id INTEGER,
            note TEXT,
            created_at TEXT
        );
        """
    )
    auto_leads._leads_created_this_run = 0
    yield db
    db.close()


@pytest.mark.parametrize(
    "target",
    [
        "ICE Director office",
        "ICE Presidential Transition Office response",
        "Trump 2026 OGE disclosure household",
        "Donald J. Trump annual disclosure / GEO Group transaction series",
    ],
)
def test_document_and_office_labels_are_abstract(target):
    assert is_abstract_entity_target(target)


@pytest.mark.parametrize(
    "target",
    [
        "Government Accountability Office",
        "Acme Disclosure",
        "Director Office LLC",
        "Household Finance Corporation",
    ],
)
def test_abstract_label_guard_preserves_named_organizations(target):
    assert not is_abstract_entity_target(target)


def test_self_alias_guard_does_not_collapse_distinct_person_names():
    assert not auto_leads._is_known_self_alias(
        "George C. Zoley", "person", "George D. Zoley", "person"
    )
    assert not auto_leads._is_known_self_alias(
        "David James Venturella", "person", "David Venturella", "person"
    )
    assert not auto_leads._is_known_self_alias(
        "U.S. Steel", "company", "Steel", "company"
    )


def test_suffix_and_facility_guards_preserve_distinct_identities():
    assert auto_leads._has_person_suffix_distinction(
        "Christopher LaCivita Jr.",
        "person",
        "Christopher LaCivita",
        "person",
    )
    assert not auto_leads._has_person_suffix_distinction(
        "Christopher LaCivita Jr.",
        "person",
        "James LaCivita",
        "person",
    )
    assert auto_leads._has_distinct_facility_identity(
        "Val Verde County Detention Facility",
        "Maverick County Detention Facility",
    )
    assert not auto_leads._has_distinct_facility_identity(
        "Val Verde County Detention Facility",
        "Val Verde Detention Center",
    )


def test_entity_crossref_suppresses_suffix_and_facility_noise(identity_db):
    identity_db.executemany(
        "INSERT INTO entities(id, name, entity_type) VALUES (?, ?, ?)",
        [
            (1, "Christopher LaCivita Jr.", "person"),
            (2, "Christopher LaCivita", "person"),
            (3, "Val Verde County Detention Facility", "unknown"),
            (4, "Maverick County Detention Facility", "unknown"),
        ],
    )

    assert auto_leads.process_entity_crossref(
        identity_db, profile_id="geo-group"
    ) == (0, 4)
    assert identity_db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0


def test_entity_crossref_suppresses_person_and_agency_self_aliases(identity_db):
    identity_db.executemany(
        "INSERT INTO entities(id, name, entity_type) VALUES (?, ?, ?)",
        [
            (1, "David J. Venturella", "person"),
            (2, "David Venturella", "person"),
            (3, "U.S. Customs and Border Protection", "agency"),
            (4, "Customs and Border Protection", "agency"),
        ],
    )

    assert auto_leads.process_entity_crossref(
        identity_db, profile_id="geo-group"
    ) == (0, 4)
    assert identity_db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0


def test_person_crossref_suppresses_middle_initial_self_alias(identity_db):
    identity_db.execute(
        "INSERT INTO entities(id, name, entity_type) VALUES (1, 'The GEO Group', 'inc')"
    )
    identity_db.execute(
        "INSERT INTO entity_roles(id, entity_id, person_name) "
        "VALUES (1, 1, 'George C. Zoley')"
    )
    identity_db.execute(
        "INSERT INTO connections(id, person_a, person_b) "
        "VALUES (1, 'George Zoley', 'Another Person')"
    )

    assert auto_leads.process_person_crossref(
        identity_db, profile_id="geo-group"
    ) == (0, 1)
    assert identity_db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0


def test_new_connections_scopes_rows_and_counts_linked_findings(identity_db):
    identity_db.executemany(
        "INSERT INTO findings(id, target_name, profile_id) VALUES (?, ?, ?)",
        [
            (1, "Serguei Kouzmine and Frank Creer", "dfj-network"),
            (2, "Unrelated target", "geo-group"),
        ],
    )
    identity_db.executemany(
        """INSERT INTO connections(
               id, person_a, person_b, relationship_type, finding_id, profile_id
           ) VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (
                1,
                "Serguei Kouzmine (QWave/Fintech)",
                "QWave Capital",
                "corporate",
                1,
                "dfj-network",
            ),
            (
                2,
                "Unrelated Person",
                "Unrelated Company",
                "corporate",
                2,
                "geo-group",
            ),
        ],
    )

    assert auto_leads.process_new_connections(
        identity_db, profile_id="dfj-network"
    ) == (0, 1)
    assert identity_db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0
