from __future__ import annotations

import copy
import sqlite3

import pytest

from pipeline import curate_dossier, export_dossiers


@pytest.fixture
def dossier_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE findings (
            id INTEGER PRIMARY KEY,
            target_name TEXT NOT NULL,
            finding_type TEXT,
            summary TEXT NOT NULL,
            detail TEXT,
            source_datasets TEXT,
            confidence TEXT,
            date_of_event TEXT,
            claim_type TEXT,
            verification_status TEXT,
            created_at TEXT,
            verified_at TEXT,
            profile_id TEXT
        );
        CREATE TABLE finding_evidence (
            finding_id INTEGER,
            evidence_type TEXT,
            evidence_ref TEXT,
            source_quote TEXT,
            source_page TEXT,
            assessment TEXT
        );
        CREATE TABLE corrections (
            table_name TEXT,
            record_id INTEGER,
            field_name TEXT,
            correction_type TEXT
        );
        CREATE TABLE connections (
            id INTEGER PRIMARY KEY,
            person_a TEXT NOT NULL,
            person_b TEXT NOT NULL,
            relationship_type TEXT,
            description TEXT,
            strength TEXT,
            date_range TEXT,
            verification_status TEXT,
            created_at TEXT,
            verified_at TEXT,
            profile_id TEXT,
            finding_id INTEGER
        );
        CREATE TABLE connection_evidence (
            connection_id INTEGER,
            evidence_type TEXT,
            evidence_ref TEXT,
            source_quote TEXT,
            source_page TEXT,
            assessment TEXT
        );
        CREATE TABLE name_aliases (canonical_name TEXT, alias TEXT);
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY,
            name TEXT,
            entity_type TEXT,
            jurisdiction TEXT,
            status TEXT
        );
        CREATE TABLE entity_roles (
            entity_id INTEGER,
            person_name TEXT,
            role TEXT,
            date_start TEXT,
            date_end TEXT,
            source TEXT
        );
        """
    )

    conn.executemany(
        """
        INSERT INTO findings (
            id, target_name, finding_type, summary, detail, source_datasets,
            confidence, date_of_event, claim_type, verification_status,
            created_at, verified_at, profile_id
        ) VALUES (?, 'Alpha Person', 'relationship', ?, NULL, NULL, 'medium', ?,
                  'paraphrase', ?, ?, ?, 'test-profile')
        """,
        [
            (1, "Verified finding", "2024-01-01", "verified", "2024-01-02", "2024-02-01"),
            (2, "Unverified finding", "2024-01-02", "unverified", "2024-01-03", None),
            (3, "Disputed finding", "2024-01-03", "disputed", "2024-01-04", None),
            (4, "Retracted finding", "2024-01-04", "retracted", "2024-01-05", "2024-04-01"),
        ],
    )
    conn.execute(
        """
        INSERT INTO finding_evidence (
            finding_id, evidence_type, evidence_ref, source_quote
        ) VALUES (1, 'url', 'https://example.test/verified-finding', 'Primary quote')
        """
    )
    conn.executemany(
        """
        INSERT INTO connections (
            id, person_a, person_b, relationship_type, description, strength,
            date_range, verification_status, created_at, verified_at, profile_id,
            finding_id
        ) VALUES (?, 'Alpha Person', ?, 'professional', ?, 'strong', ?, ?, ?, ?,
                  'test-profile', ?)
        """,
        [
            (11, "Verified Contact", "Verified connection", "2024-01", "verified", "2024-01-06", "2024-03-01", 1),
            (12, "Unverified Contact", "Unverified connection", "2024-02", "unverified", "2024-01-07", None, None),
            (13, "Disputed Contact", "Disputed connection", "2024-03", "disputed", "2024-01-08", None, None),
            (14, "Retracted Contact", "Retracted connection", "2024-04", "retracted", "2024-01-09", "2024-04-02", None),
            (15, "No Evidence Contact", "Stale verified connection with no evidence", "2024-05", "verified", "2024-01-10", "2024-02-15", None),
            (16, "Unverified Upstream Contact", "Stale verified connection", "2024-06", "verified", "2024-01-11", "2024-02-16", 2),
            (17, "Unquoted Contact", "Stale verified evidence", "2024-07", "verified", "2024-01-12", "2024-02-17", None),
        ],
    )
    conn.executemany(
        """
        INSERT INTO connection_evidence (
            connection_id, evidence_type, evidence_ref, source_quote, source_page,
            assessment
        ) VALUES (?, 'url', ?, ?, NULL, NULL)
        """,
        [
            (11, "https://example.test/verified-connection", "Exact connection quote"),
            (16, "https://example.test/unverified-upstream", "Exact upstream edge quote"),
            (17, "https://example.test/unquoted", None),
        ],
    )
    conn.commit()
    yield conn
    conn.close()


def test_public_export_is_verified_only_everywhere(dossier_db: sqlite3.Connection) -> None:
    dossier = export_dossiers.export_target(
        dossier_db,
        "Alpha Person",
        ["Alpha Person"],
        profile_id="test-profile",
    )

    assert [finding["id"] for finding in dossier["findings"]] == [1]
    assert [connection["id"] for connection in dossier["connections"]] == [11]
    assert dossier["stats"]["total_findings"] == 1
    assert dossier["stats"]["total_connections"] == 1
    assert dossier["stats"]["finding_types"] == {"relationship": 1}
    assert dossier["stats"]["connection_types"] == {"professional": 1}
    assert {(event["type"], event["id"]) for event in dossier["timeline"]} == {
        ("finding", 1),
        ("connection", 11),
    }
    assert dossier["last_updated"] == "2024-03-01T00:00:00"
    assert dossier["export_options"] == {"include_unverified": False}


def test_mixed_timezone_timestamps_are_normalized_before_comparison(
    dossier_db: sqlite3.Connection,
) -> None:
    dossier_db.execute(
        "UPDATE findings SET verified_at = ? WHERE id = 1",
        ("2024-02-01T05:00:00+05:00",),
    )
    dossier_db.execute(
        "UPDATE connections SET verified_at = ? WHERE id = 11",
        ("2024-03-01T00:00:00Z",),
    )
    dossier_db.commit()

    dossier = export_dossiers.export_target(
        dossier_db,
        "Alpha Person",
        ["Alpha Person"],
        profile_id="test-profile",
    )

    assert dossier["last_updated"] == "2024-03-01T00:00:00"


def test_research_override_includes_non_retracted_states(
    dossier_db: sqlite3.Connection,
) -> None:
    dossier = export_dossiers.export_target(
        dossier_db,
        "Alpha Person",
        ["Alpha Person"],
        profile_id="test-profile",
        include_unverified=True,
    )

    assert [finding["id"] for finding in dossier["findings"]] == [1, 2, 3]
    assert [connection["id"] for connection in dossier["connections"]] == [
        11, 12, 13, 15, 16, 17,
    ]
    assert dossier["stats"]["total_findings"] == 3
    assert dossier["stats"]["total_connections"] == 6
    assert {event["id"] for event in dossier["timeline"]} == {
        1, 2, 3, 11, 12, 13, 15, 16, 17,
    }
    assert dossier["export_options"] == {"include_unverified": True}


def test_target_threshold_uses_the_requested_verification_scope(
    dossier_db: sqlite3.Connection,
) -> None:
    assert export_dossiers.get_targets(
        dossier_db,
        min_findings=2,
        profile_id="test-profile",
    ) == []

    targets = export_dossiers.get_targets(
        dossier_db,
        min_findings=2,
        profile_id="test-profile",
        include_unverified=True,
    )
    assert targets == [("Alpha Person", ["Alpha Person"])]


def test_incremental_skip_requires_matching_scope_and_record_membership(
    dossier_db: sqlite3.Connection,
) -> None:
    dossier = export_dossiers.export_target(
        dossier_db,
        "Alpha Person",
        ["Alpha Person"],
        profile_id="test-profile",
    )
    existing = copy.deepcopy(dossier)
    existing["generated_at"] = "2025-01-01T00:00:00"

    assert export_dossiers._can_skip_incremental(existing, dossier, False)

    legacy_unscoped = copy.deepcopy(existing)
    legacy_unscoped.pop("export_options")
    assert not export_dossiers._can_skip_incremental(legacy_unscoped, dossier, False)

    wrong_scope = copy.deepcopy(existing)
    wrong_scope["export_options"]["include_unverified"] = True
    assert not export_dossiers._can_skip_incremental(wrong_scope, dossier, False)

    stale_membership = copy.deepcopy(existing)
    stale_membership["findings"].append(
        {"id": 2, "verification_status": "unverified"}
    )
    assert not export_dossiers._can_skip_incremental(stale_membership, dossier, False)

    retracted_transition = copy.deepcopy(dossier)
    retracted_transition["connections"] = []
    assert not export_dossiers._can_skip_incremental(
        existing, retracted_transition, False
    )

    stale_citation_catalog = copy.deepcopy(existing)
    stale_citation_catalog["citation_findings"] = [
        {"id": 99, "verification_status": "verified"}
    ]
    assert not export_dossiers._can_skip_incremental(
        stale_citation_catalog, dossier, False
    )


def test_static_citation_catalog_contains_only_verified_findings(
    dossier_db: sqlite3.Connection,
) -> None:
    curation = {
        "lead": "<p>Supported [Finding #1] but not public [Finding #2].</p>",
        "sections": [],
    }

    citation_findings = export_dossiers.load_citation_findings(
        dossier_db, curation
    )

    assert [finding["id"] for finding in citation_findings] == [1]
    assert citation_findings[0]["verification_status"] == "verified"


def test_public_export_excludes_internal_only_verified_findings(
    dossier_db: sqlite3.Connection,
) -> None:
    dossier_db.execute(
        """
        INSERT INTO findings (
            id, target_name, finding_type, summary, confidence, date_of_event,
            claim_type, verification_status, created_at, verified_at, profile_id
        ) VALUES (
            5, 'Alpha Person', 'relationship', 'Internal synthesis', 'medium',
            '2024-01-05', 'synthesis', 'verified', '2024-01-10', '2024-02-10',
            'test-profile'
        )
        """
    )
    dossier_db.execute(
        """
        INSERT INTO finding_evidence (
            finding_id, evidence_type, evidence_ref, source_quote
        ) VALUES (5, 'ref', 'analysis-run-126', 'Internal chronology summary')
        """
    )
    dossier_db.commit()

    public_dossier = export_dossiers.export_target(
        dossier_db, "Alpha Person", ["Alpha Person"], profile_id="test-profile"
    )
    assert [finding["id"] for finding in public_dossier["findings"]] == [1]

    research_dossier = export_dossiers.export_target(
        dossier_db,
        "Alpha Person",
        ["Alpha Person"],
        profile_id="test-profile",
        include_unverified=True,
    )
    assert [finding["id"] for finding in research_dossier["findings"]] == [1, 2, 3, 5]

    citation_findings = export_dossiers.load_citation_findings(
        dossier_db,
        {"lead": "<p>External [Finding #1], internal [Finding #5].</p>"},
    )
    assert [finding["id"] for finding in citation_findings] == [1]


def test_ego_network_second_hop_respects_export_scope(
    dossier_db: sqlite3.Connection,
    tmp_path,
) -> None:
    dossier_db.executemany(
        """
        INSERT INTO connections (
            id, person_a, person_b, relationship_type, description, strength,
            date_range, verification_status, created_at, verified_at, profile_id
        ) VALUES (?, 'Verified Contact', ?, 'professional', ?, 'medium', NULL,
                  ?, '2024-01-10', NULL, 'test-profile')
        """,
        [
            (21, "Verified Second Hop", "verified second hop", "verified"),
            (22, "Unverified Second Hop", "unverified second hop", "unverified"),
            (23, "Disputed Second Hop", "disputed second hop", "disputed"),
            (24, "Retracted Second Hop", "retracted second hop", "retracted"),
        ],
    )
    dossier_db.commit()
    db_path = tmp_path / "dossier.db"
    disk_db = sqlite3.connect(db_path)
    dossier_db.backup(disk_db)
    disk_db.close()

    public_dossier = export_dossiers.export_target(
        dossier_db,
        "Alpha Person",
        ["Alpha Person"],
        profile_id="test-profile",
    )
    public_ego = curate_dossier.build_ego_network(public_dossier, db_path)
    assert [
        item["target"] for item in public_ego["secondHop"]["Verified Contact"]
    ] == ["Verified Second Hop"]

    research_dossier = export_dossiers.export_target(
        dossier_db,
        "Alpha Person",
        ["Alpha Person"],
        profile_id="test-profile",
        include_unverified=True,
    )
    research_ego = curate_dossier.build_ego_network(research_dossier, db_path)
    assert {
        item["target"] for item in research_ego["secondHop"]["Verified Contact"]
    } == {"Verified Second Hop", "Unverified Second Hop", "Disputed Second Hop"}
