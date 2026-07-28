from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_search_plan import (
    SearchPlanError,
    build_search_plan,
    canonical_json,
    main,
)


NOW = "2026-07-28T12:00:00Z"


def _manifest(
    source_id: str,
    *,
    domain: str,
    roles: list[str],
    geoid: str,
    capabilities: list[str],
) -> dict:
    return {
        "source_id": source_id,
        "name": source_id,
        "domain": domain,
        "roles": roles,
        "authority": "Official test authority",
        "operator": "Official test operator",
        "jurisdiction_geoids": [geoid],
        "official_url": f"https://example.gov/{source_id}",
        "platform_family": "test_fixture",
        "access_class": "B",
        "automation_disposition": "allowed",
        "authentication": "none",
        "fees": "none",
        "redistribution": "source_terms_apply",
        "protected_record_policy": "source_record_state_preserved",
        "coverage_start": "source_specific",
        "update_cadence": "source_managed",
        "stable_keys": ["native_id"],
        "adapter_family": "test_adapter",
        "adapter_version": 1,
        "last_verified_at": NOW,
        "source_status": "active",
        "capabilities": capabilities,
    }


@pytest.fixture
def catalog_db(tmp_path: Path) -> Path:
    path = tmp_path / "catalog.db"
    catalog = PublicRecordsCatalog(path)
    property_manifest = _manifest(
        "us-ny-test-property",
        domain="property",
        roles=["assessment"],
        geoid="36",
        capabilities=[
            "search_owner",
            "search_address",
            "fetch_parcel",
        ],
    )
    recorder_manifest = _manifest(
        "us-ny-test-recorder",
        domain="property",
        roles=["recorder", "instrument_index"],
        geoid="36",
        capabilities=[
            "search_parties",
            "search_parcels",
            "fetch_instrument",
        ],
    )
    court_manifest = _manifest(
        "us-ny-test-court",
        domain="court",
        roles=["court", "document_portal"],
        geoid="36",
        capabilities=[
            "search_cases",
            "list_docket_entries",
            "fetch_document",
        ],
    )
    unreviewed = _manifest(
        "us-fl-test-court",
        domain="court",
        roles=["court"],
        geoid="12",
        capabilities=["search_cases"],
    )
    for manifest in (
        property_manifest,
        recorder_manifest,
        court_manifest,
        unreviewed,
    ):
        catalog.register_manifest(
            manifest,
            submitted_by="test",
            submitted_at=NOW,
        )
    catalog.evaluate_access(
        property_manifest["source_id"],
        access_class="B",
        automation_disposition="allowed",
        reviewed_by="test",
        review_basis="Fixture review.",
        reviewed_at=NOW,
    )
    catalog.evaluate_access(
        recorder_manifest["source_id"],
        access_class="B",
        automation_disposition="allowed",
        reviewed_by="test",
        review_basis="Fixture review.",
        reviewed_at=NOW,
    )
    catalog.evaluate_access(
        court_manifest["source_id"],
        access_class="C",
        automation_disposition="prohibited",
        reviewed_by="test",
        review_basis="Fixture review.",
        reviewed_at=NOW,
    )
    return path


@pytest.fixture
def investigation_context(tmp_path: Path) -> tuple[Path, Path]:
    db_path = tmp_path / "investigation.db"
    db = sqlite3.connect(db_path)
    db.executescript(
        """
        CREATE TABLE investigation_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            entity_type TEXT,
            jurisdiction TEXT,
            address TEXT
        );
        CREATE TABLE name_aliases (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            alias TEXT NOT NULL,
            alias_type TEXT,
            entity_id INTEGER
        );
        INSERT INTO investigation_config(key, value)
        VALUES('active_profile', 'fixture-profile');
        INSERT INTO entities(id, name, entity_type, jurisdiction, address)
        VALUES(
            1, 'Acme Holdings LLC', 'company', '36',
            '100 Main Street, Albany, NY'
        );
        INSERT INTO entities(id, name, entity_type, jurisdiction, address)
        VALUES(
            2, 'Related Ventures Inc', 'company', '12',
            '500 Palm Avenue, Miami, FL'
        );
        INSERT INTO name_aliases(
            canonical_name, alias, alias_type, entity_id
        ) VALUES(
            'Acme Holdings LLC', 'Acme Holdings', 'entity_variant', 1
        );
        INSERT INTO name_aliases(
            canonical_name, alias, alias_type, entity_id
        ) VALUES(
            'Acme Holdings LLC', 'Acme Hldgs', 'entity_variant', 1
        );
        INSERT INTO name_aliases(
            canonical_name, alias, alias_type, entity_id
        ) VALUES(
            'Related Ventures Inc', 'Related Ventures', 'entity_variant', 2
        );
        """
    )
    db.commit()
    db.close()

    profiles_dir = tmp_path / "profiles"
    profile_dir = profiles_dir / "fixture-profile"
    profile_dir.mkdir(parents=True)
    profile = {
        "name": "fixture-profile",
        "primary_subject": "Umbrella Investigation",
        "key_persons": [],
        "known_addresses": {
            "101 State Street, Albany, NY": "Acme Holdings LLC office",
            "999 Unrelated Road": "Other subject",
        },
    }
    (profile_dir / "config.yaml").write_text(json.dumps(profile))
    return db_path, profiles_dir


def _without_fingerprint(plan: dict) -> dict:
    payload = copy.deepcopy(plan)
    payload.pop("fingerprint")
    return payload


def test_enriches_identity_from_database_and_active_profile(
    catalog_db: Path,
    investigation_context: tuple[Path, Path],
) -> None:
    investigation_db, profiles_dir = investigation_context
    plan = build_search_plan(
        "Acme Holdings",
        aliases=["ACME"],
        addresses=["10 Explicit Lane"],
        related_entities=["Related Ventures"],
        jurisdictions=["36"],
        catalog_db=catalog_db,
        investigation_db=investigation_db,
        profiles_dir=profiles_dir,
    )

    assert plan["identity"]["canonical_name"] == "Acme Holdings LLC"
    names = {row["value"]: row for row in plan["identity"]["names"]}
    assert "Acme Hldgs" in names
    assert names["Acme Hldgs"]["provenance"] == [
        "investigation_db:name_aliases"
    ]
    addresses = {row["value"]: row for row in plan["identity"]["addresses"]}
    assert "100 Main Street, Albany, NY" in addresses
    assert "101 State Street, Albany, NY" in addresses
    assert "999 Unrelated Road" not in addresses
    assert plan["identity"]["related_entities"] == [
        {
            "input": "Related Ventures",
            "canonical_name": "Related Ventures Inc",
            "names": [
                "Related Ventures",
                "Related Ventures Inc",
            ],
            "addresses": ["500 Palm Avenue, Miami, FL"],
            "jurisdictions": ["12"],
        }
    ]
    assert plan["context"]["profile"]["name"] == "fixture-profile"
    assert plan["context"]["profile"]["known_addresses_available"] == 2
    assert plan["context"]["profile"]["known_addresses_matched"] == 1


def test_enumerates_every_source_and_preserves_catalog_access_modes(
    catalog_db: Path,
    tmp_path: Path,
) -> None:
    plan = build_search_plan(
        "Acme Holdings LLC",
        jurisdictions=["36"],
        catalog_db=catalog_db,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {source["source_id"]: source for source in plan["sources"]}

    assert set(sources) == {
        "us-fl-test-court",
        "us-ny-test-court",
        "us-ny-test-property",
        "us-ny-test-recorder",
    }
    assert sources["us-ny-test-court"]["access"]["mode"] == "prohibited"
    assert (
        sources["us-ny-test-court"]["access"]["latest_review"][
            "automation_disposition"
        ]
        == "prohibited"
    )
    assert sources["us-fl-test-court"]["access"] == {
        "review_state": "unreviewed",
        "mode": "unreviewed",
        "latest_review": None,
        "manifest_proposal": {
            "access_class": "B",
            "automation_disposition": "allowed",
        },
    }
    court_tasks = next(
        stage["tasks"]
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "court"
    )
    assert any(
        task["source_id"] == "us-ny-test-court"
        and task["catalog_access"]["mode"] == "prohibited"
        for task in court_tasks
    )
    assert all(task["source_id"] != "us-fl-test-court" for task in court_tasks)
    assert (
        sources["us-fl-test-court"]["requested_jurisdiction_coverage"]["status"]
        == "no_catalog_match"
    )
    assert all(
        task["seed_parameters"]["jurisdictions"] == ["36"]
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
    )


def test_workflow_dependencies_run_property_then_recorder_then_court(
    catalog_db: Path,
    tmp_path: Path,
) -> None:
    plan = build_search_plan(
        "Acme Holdings LLC",
        addresses=["100 Main Street"],
        jurisdictions=["36"],
        catalog_db=catalog_db,
        investigation_db=tmp_path / "missing.db",
    )
    stages = {
        stage["stage_id"]: stage["tasks"]
        for stage in plan["workflow"]["stages"]
    }
    property_ids = {task["task_id"] for task in stages["property"]}
    recorder_ids = {task["task_id"] for task in stages["recorder"]}

    assert plan["workflow"]["dependency_order"] == [
        "property",
        "recorder",
        "court",
    ]
    assert property_ids
    assert recorder_ids
    for recorder in stages["recorder"]:
        assert property_ids.issubset(set(recorder["depends_on"]))
    for court in stages["court"]:
        if court["capability"] == "search_cases":
            assert property_ids.issubset(set(court["depends_on"]))
            assert recorder_ids.issubset(set(court["depends_on"]))
    document_task = next(
        task
        for task in stages["court"]
        if task["source_id"] == "us-ny-test-court"
        and task["capability"] == "fetch_document"
    )
    assert "court.us-ny-test-court.search_cases" in document_task["depends_on"]


def test_fingerprint_and_canonical_json_are_deterministic(
    catalog_db: Path,
    tmp_path: Path,
) -> None:
    kwargs = {
        "subject": "Acme Holdings LLC",
        "addresses": ["2 Second St", "1 First St"],
        "jurisdictions": ["36", "12"],
        "catalog_db": catalog_db,
        "investigation_db": tmp_path / "missing.db",
    }
    first = build_search_plan(
        aliases=["Acme Hldgs", "ACME"],
        related_entities=["Beta LLC", "Alpha LLC"],
        **kwargs,
    )
    second = build_search_plan(
        aliases=["ACME", "Acme Hldgs"],
        related_entities=["Alpha LLC", "Beta LLC"],
        addresses=list(reversed(kwargs["addresses"])),
        jurisdictions=list(reversed(kwargs["jurisdictions"])),
        subject=kwargs["subject"],
        catalog_db=catalog_db,
        investigation_db=kwargs["investigation_db"],
    )

    assert first == second
    assert first["fingerprint"] == hashlib.sha256(
        canonical_json(_without_fingerprint(first)).encode("utf-8")
    ).hexdigest()
    assert canonical_json(first) == canonical_json(second)


def test_coverage_and_unresolved_notes_are_explicit(
    catalog_db: Path,
    tmp_path: Path,
) -> None:
    plan = build_search_plan(
        "Acme Holdings LLC",
        jurisdictions=["99"],
        catalog_db=catalog_db,
        investigation_db=tmp_path / "missing.db",
    )
    codes = {note["code"] for note in plan["unresolved"]}

    assert "address_not_available" in codes
    assert "jurisdiction_catalog_match_unresolved" in codes
    assert plan["coverage"]["requested_jurisdictions"] == [
        {"jurisdiction": "99", "catalog_source_ids": []}
    ]
    assert plan["coverage"]["sources_by_access_mode"] == {
        "allowed": 2,
        "prohibited": 1,
        "unreviewed": 1,
    }


def test_cli_writes_canonical_json(
    catalog_db: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "plan.json"
    exit_code = main(
        [
            "Acme Holdings LLC",
            "--jurisdiction",
            "36",
            "--catalog-db",
            str(catalog_db),
            "--investigation-db",
            str(tmp_path / "missing.db"),
            "--output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text())

    assert exit_code == 0
    assert output.read_text() == canonical_json(payload) + "\n"
    assert payload["fingerprint"] in capsys.readouterr().out


def test_rejects_inverted_or_invalid_date_bounds(
    catalog_db: Path,
    tmp_path: Path,
) -> None:
    with pytest.raises(SearchPlanError, match="after must not be later"):
        build_search_plan(
            "Acme",
            after="2026-02-01",
            before="2026-01-01",
            catalog_db=catalog_db,
            investigation_db=tmp_path / "missing.db",
        )
    with pytest.raises(SearchPlanError, match="ISO date"):
        build_search_plan(
            "Acme",
            after="next week",
            catalog_db=catalog_db,
            investigation_db=tmp_path / "missing.db",
        )
