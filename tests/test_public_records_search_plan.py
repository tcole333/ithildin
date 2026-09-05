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
from tools.seed_public_records_catalog import seed_catalog


NOW = "2026-07-28T12:00:00Z"


def _manifest(
    source_id: str,
    *,
    domain: str,
    roles: list[str],
    geoid: str,
    capabilities: list[str | dict],
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
            {
                "name": "search_parcels",
                "details": {"adapter_command": "folio"},
            },
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
    assert names["Acme Hldgs"]["provenance"] == ["investigation_db:name_aliases"]
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
        sources["us-ny-test-court"]["access"]["latest_review"]["automation_disposition"]
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
    stages = {stage["stage_id"]: stage["tasks"] for stage in plan["workflow"]["stages"]}
    property_ids = {task["task_id"] for task in stages["property"]}
    recorder_ids = {task["task_id"] for task in stages["recorder"]}

    assert plan["workflow"]["dependency_order"] == [
        "property",
        "recorder",
        "court",
    ]
    assert property_ids
    assert recorder_ids
    assert all(
        task["source_id"] != "us-ny-test-recorder" for task in stages["property"]
    )
    for recorder in stages["recorder"]:
        assert property_ids.issubset(set(recorder["depends_on"]))
    parcel_search = next(
        task
        for task in stages["recorder"]
        if task["source_id"] == "us-ny-test-recorder"
        and task["capability"] == "search_parcels"
    )
    assert parcel_search["capability_details"] == {"adapter_command": "folio"}
    instrument_fetch = next(
        task
        for task in stages["recorder"]
        if task["source_id"] == "us-ny-test-recorder"
        and task["capability"] == "fetch_instrument"
    )
    route_fields = instrument_fetch["runtime_inputs"][0]["fields"]
    assert {
        "cfn_master_ids",
        "document_type",
        "recording_date",
        "book",
        "page",
        "book_type",
    }.issubset(route_fields)
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


def test_tracked_miami_sources_plan_folio_index_then_public_enrichment(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Holdings LLC",
        addresses=["111 NW 1 ST, Miami, FL"],
        jurisdictions=["12086"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    stages = {stage["stage_id"]: stage["tasks"] for stage in plan["workflow"]["stages"]}

    assert all(
        task["source_id"] != "us-fl-miami-dade-official-records"
        for task in stages["property"]
    )
    recorder_by_id = {task["task_id"]: task for task in stages["recorder"]}
    folio_task_id = "recorder.us-fl-miami-dade-official-records.search_parcels"
    assert recorder_by_id[folio_task_id]["capability_details"] == {
        "adapter_command": "folio",
        "input_fields": [
            "native_parcel_id",
            "alternate_parcel_id",
        ],
    }
    assert (
        "recorder.us-fl-miami-dade-official-records.search_folio" not in recorder_by_id
    )
    public_capabilities = {
        task["capability"]
        for task in stages["recorder"]
        if task["source_id"] == "us-fl-miami-dade-official-records-public"
    }
    assert public_capabilities == {
        "fetch_document",
        "fetch_financial_detail",
        "fetch_instrument",
        "fetch_parties",
        "hydrate_search_results",
    }
    for task in stages["recorder"]:
        if task["source_id"] == ("us-fl-miami-dade-official-records-public"):
            assert folio_task_id in task["depends_on"]
            fields = task["runtime_inputs"][0]["fields"]
            assert {
                "cfn_master_ids",
                "document_type",
                "recording_date",
                "book",
                "page",
                "book_type",
            }.issubset(fields)


def test_tracked_orleans_source_plans_account_parcel_and_geometry_routes(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Holdings LLC",
        addresses=["1300 Perdido Street, New Orleans, LA"],
        jurisdictions=["22071"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    property_tasks = next(
        stage["tasks"]
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "property"
    )
    orleans_tasks = {
        task["capability"]: task
        for task in property_tasks
        if task["source_id"] == "us-la-orleans-property-viewer"
    }
    orleans_source = next(
        source
        for source in plan["sources"]
        if source["source_id"] == "us-la-orleans-property-viewer"
    )

    assert set(orleans_tasks) == {
        "search_owner",
        "search_address",
        "search_assessment_records",
        "fetch_account",
        "fetch_parcel",
        "fetch_geometry",
    }
    assert {
        capability["name"] for capability in orleans_source["capabilities"]
    }.issuperset({"assessment_value", "source_update"})
    assert orleans_tasks["search_owner"]["capability_details"] == {
        "adapter_command": "owner",
        "input_fields": ["owner_name"],
    }
    assert orleans_tasks["search_address"]["seed_parameters"]["addresses"] == [
        "1300 Perdido Street, New Orleans, LA"
    ]
    assert orleans_tasks["search_assessment_records"]["seed_parameters"]["queries"] == [
        "1300 Perdido Street, New Orleans, LA",
        "Example Holdings LLC",
    ]
    assert orleans_tasks["fetch_account"]["capability_details"] == {
        "adapter_command": "account",
        "input_fields": ["tax_bill_id"],
    }
    for capability in ("fetch_account", "fetch_parcel", "fetch_geometry"):
        fields = orleans_tasks[capability]["runtime_inputs"][0]["fields"]
        assert {"tax_bill_id", "parcel_id", "parid"}.issubset(fields)


def test_tracked_florida_acis_capabilities_and_uuid_inputs_are_planned(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Holdings LLC",
        jurisdictions=["12"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    court_tasks = next(
        stage["tasks"]
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "court"
    )
    acis_tasks = {
        task["capability"]: task
        for task in court_tasks
        if task["source_id"] == "us-fl-acis"
    }

    assert set(acis_tasks) == {
        "list_courts",
        "search_cases",
        "search_parties",
        "fetch_case",
        "fetch_parties",
        "list_docket_entries",
        "search_appellate_calendars",
        "search_documents",
        "fetch_document",
        "search_publications",
        "fetch_publication",
    }
    court_list_task_id = "court.us-fl-acis.list_courts"
    assert acis_tasks["list_courts"]["depends_on"] == []
    assert acis_tasks["search_cases"]["capability_details"] == {
        "adapter_command": "case-search",
        "input_fields": ["query", "court_resource_uuid", "cursor"],
    }
    assert acis_tasks["fetch_publication"]["capability_details"] == {
        "adapter_command": "publication",
        "input_fields": ["court_resource_uuid", "publication_uuid"],
    }
    for capability in (
        "search_cases",
        "search_appellate_calendars",
        "search_documents",
        "search_parties",
        "search_publications",
    ):
        assert court_list_task_id in acis_tasks[capability]["depends_on"]

    document_input = acis_tasks["fetch_document"]["runtime_inputs"][0]
    assert {
        "court_resource_uuid",
        "native_court_id",
        "case_instance_uuid",
        "source_internal_id",
        "docket_entry_uuid",
        "document_link_uuid",
        "native_document_id",
        "publication_uuid",
    }.issubset(document_input["fields"])
    assert court_list_task_id in document_input["from_tasks"]
    assert "court.us-fl-acis.search_documents" in document_input["from_tasks"]


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
    assert (
        first["fingerprint"]
        == hashlib.sha256(
            canonical_json(_without_fingerprint(first)).encode("utf-8")
        ).hexdigest()
    )
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


def test_flags_difficult_route_without_a_cataloged_complement(
    catalog_db: Path,
    tmp_path: Path,
) -> None:
    plan = build_search_plan(
        "Acme Holdings LLC",
        jurisdictions=["36"],
        catalog_db=catalog_db,
        investigation_db=tmp_path / "missing.db",
    )
    gap = next(
        note
        for note in plan["unresolved"]
        if note["code"] == "complementary_route_not_cataloged"
    )

    assert gap["sources"] == [
        {
            "source_id": "us-ny-test-court",
            "access_mode": "prohibited",
        }
    ]


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


def test_tracked_bexar_court_routes_plan_machine_and_interactive_capabilities(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Holdings LLC",
        jurisdictions=["48029"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {source["source_id"]: source for source in plan["sources"]}
    historical_id = "us-tx-bexar-district-historical-cases"
    portal_id = "us-tx-bexar-justice-portal"
    district_request_id = "us-tx-bexar-district-clerk-records-request"
    county_request_id = "us-tx-bexar-county-clerk-records-request"

    assert sources[historical_id]["access"]["mode"] == ("allowed_with_limits")
    assert sources[portal_id]["access"]["mode"] == "unclear"
    assert sources[district_request_id]["access"]["mode"] == ("not_applicable")
    assert sources[county_request_id]["access"]["mode"] == ("not_applicable")

    court_tasks = {
        task["task_id"]: task
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "court"
        for task in stage["tasks"]
    }
    historical_tasks = {
        task["capability"]: task
        for task in court_tasks.values()
        if task["source_id"] == historical_id
    }
    assert set(historical_tasks) == {
        "search_cases",
        "search_documents",
        "fetch_case",
        "fetch_document",
    }
    assert historical_tasks["fetch_document"]["capability_details"] == {
        "adapter_command": "page",
        "input_fields": ["doc_id", "page_number"],
        "retrieval_granularity": "page_image",
    }
    assert {"doc_id", "rs_id", "image_id"}.issubset(
        historical_tasks["fetch_document"]["runtime_inputs"][0]["fields"]
    )

    portal_tasks = {
        task["capability"]: task
        for task in court_tasks.values()
        if task["source_id"] == portal_id
    }
    assert set(portal_tasks) == {
        "search_cases",
        "search_hearings",
        "fetch_case",
    }
    assert "fetch_document" not in portal_tasks
    for request_source_id in {
        district_request_id,
        county_request_id,
    }:
        assert {
            task["capability"]
            for task in court_tasks.values()
            if task["source_id"] == request_source_id
        } == {
            "request_case_copy",
            "request_court_data",
        }


def test_texas_assignment_plan_combines_county_index_ucc_and_rrc_routes(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "THREE RIVERS ACQUISITION III LLC",
        jurisdictions=["48389"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {source["source_id"]: source for source in plan["sources"]}
    reeves_id = "us-tx-reeves-county-clerk-official-records"
    reeves_bulk_id = "us-tx-reeves-clerk-bulk-images"
    ucc_portal_id = "us-tx-sos-ucc-portal"
    ucc_bulk_id = "us-tx-sos-ucc-bulk"
    p4_id = "us-tx-rrc-p4-bulk"
    p5_id = "us-tx-rrc-p5-bulk"
    wellbore_id = "us-tx-rrc-wellbore-bulk"

    assert sources[reeves_id]["access"]["mode"] == "allowed_with_limits"
    assert sources[reeves_bulk_id]["access"]["mode"] == "unclear"
    assert sources[ucc_portal_id]["access"]["mode"] == "unclear"
    assert sources[ucc_bulk_id]["access"]["mode"] == "unclear"
    assert sources[p4_id]["access"]["mode"] == "allowed"

    tasks_by_source: dict[str, set[str]] = {}
    for stage in plan["workflow"]["stages"]:
        for task in stage["tasks"]:
            tasks_by_source.setdefault(task["source_id"], set()).add(task["capability"])
    assert tasks_by_source[reeves_id] == {
        "search_document_text",
        "search_instruments",
        "search_parties",
        "fetch_instrument",
        "fetch_document",
    }
    assert tasks_by_source[reeves_bulk_id] == {
        "request_bulk_files",
        "request_bulk_images",
    }
    assert tasks_by_source[ucc_portal_id] == {
        "search_instruments",
        "search_parties",
        "fetch_instrument",
        "fetch_document",
    }
    assert tasks_by_source[ucc_bulk_id] == {
        "search_parties",
        "fetch_instrument",
        "request_bulk_files",
        "request_bulk_images",
    }
    assert tasks_by_source[p4_id] == {
        "sync",
        "list_releases",
        "download_bulk",
        "list_operator_history",
    }
    assert tasks_by_source[p5_id] == {
        "sync",
        "list_releases",
        "download_bulk",
        "resolve_operator",
    }
    assert tasks_by_source[wellbore_id] == {
        "sync",
        "list_releases",
        "download_bulk",
        "resolve_well",
    }


def test_vicourts_plan_keeps_probate_claims_and_legacy_files_distinct(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Estate",
        jurisdictions=["78"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )

    source = next(row for row in plan["sources"] if row["source_id"] == "us-vi-c-track")
    assert source["access"]["mode"] == "allowed_with_limits"

    tasks = {
        task["capability"]: task
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "court"
        for task in stage["tasks"]
        if task["source_id"] == "us-vi-c-track"
    }
    assert set(tasks) == {
        "list_courts",
        "search_cases",
        "search_parties",
        "fetch_case",
        "list_docket_entries",
        "list_probate_claims",
        "list_docket_documents",
        "search_documents",
        "fetch_document",
        "search_publications",
        "fetch_publication",
        "fetch_legacy_document",
    }
    assert tasks["list_probate_claims"]["capability_details"] == {
        "adapter_command": "claims",
        "input_fields": ["case_number", "court", "cursor"],
        "result_scope": "limited_claim_header_stubs",
    }
    assert tasks["fetch_legacy_document"]["capability_details"] == {
        "adapter_command": "legacy-file",
        "input_fields": ["item_id"],
    }
    assert tasks["fetch_document"]["capability_details"] == {
        "adapter_command": "download",
        "input_fields": ["court", "case_uuid", "document_uuid"],
    }


def test_orange_county_plan_keeps_interactive_case_route_explicit(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Holdings LLC",
        jurisdictions=["12095"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )

    source = next(
        row
        for row in plan["sources"]
        if row["source_id"] == "us-fl-orange-clerk-my-eclerk"
    )
    assert source["access"]["mode"] == "unclear"

    tasks = {
        task["capability"]: task
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "court"
        for task in stage["tasks"]
        if task["source_id"] == "us-fl-orange-clerk-my-eclerk"
    }
    assert set(tasks) == {
        "search_cases",
        "fetch_case",
        "fetch_parties",
        "list_docket_entries",
        "fetch_document",
    }
    assert tasks["fetch_document"]["capability_details"] == {
        "route_type": "interactive_portal",
        "input_fields": [
            "raw_case_number",
            "document_identification_number",
        ],
    }


def test_orange_county_plan_combines_case_action_and_hearing_adapter(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        jurisdictions=["12095"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {row["source_id"]: row for row in plan["sources"]}

    assert sources["us-fl-orange-clerk-my-eclerk"]["access"]["mode"] == ("unclear")
    assert (
        sources["us-fl-orange-county-hearing-calendar"]["access"]["mode"] == "allowed"
    )

    hearing_tasks = [
        task
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "court"
        for task in stage["tasks"]
        if task["source_id"] == "us-fl-orange-county-hearing-calendar"
    ]
    assert [task["capability"] for task in hearing_tasks] == ["search_hearings"]
    assert hearing_tasks[0]["capability_details"] == {
        "adapter_command": "search",
        "input_fields": [
            "hearing_date",
            "raw_case_number",
            "party_first_name_and_last_name",
            "judge",
        ],
    }


def test_pima_plan_includes_public_case_docket_and_document_route(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        jurisdictions=["04019"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )

    source = next(
        row
        for row in plan["sources"]
        if row["source_id"] == "us-az-pima-superior-agave"
    )
    assert source["access"]["mode"] == "allowed"

    tasks = {
        task["capability"]: task
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "court"
        for task in stage["tasks"]
        if task["source_id"] == "us-az-pima-superior-agave"
    }
    assert set(tasks) == {
        "search_cases",
        "fetch_case",
        "fetch_parties",
        "list_docket_entries",
        "list_charges",
        "fetch_document",
    }
    assert tasks["fetch_document"]["capability_details"] == {
        "adapter_command": "document",
        "input_fields": ["raw_case_number", "derived_docket_entry_id"],
    }


def test_palm_beach_plan_combines_browser_product_request_and_recorder_routes(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        jurisdictions=["12099"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {row["source_id"]: row for row in plan["sources"]}
    assert sources["us-fl-palm-beach-ecaseview"]["access"]["mode"] == (
        "allowed_with_limits"
    )
    assert sources["us-fl-palm-beach-clerkcart"]["access"]["mode"] == ("unclear")
    assert sources["us-fl-palm-beach-records-service"]["access"]["mode"] == (
        "not_applicable"
    )
    assert sources["us-fl-palm-beach-official-records"]["access"]["mode"] == (
        "allowed_with_limits"
    )

    tasks_by_source: dict[str, set[str]] = {}
    for stage in plan["workflow"]["stages"]:
        for task in stage["tasks"]:
            tasks_by_source.setdefault(task["source_id"], set()).add(task["capability"])
    assert tasks_by_source["us-fl-palm-beach-ecaseview"] == {
        "search_cases",
        "fetch_case",
        "fetch_parties",
        "list_docket_entries",
        "list_charges",
        "list_case_events",
        "fetch_document",
    }
    assert tasks_by_source["us-fl-palm-beach-clerkcart"] == {
        "request_case_report",
        "request_bulk_files",
    }
    assert tasks_by_source["us-fl-palm-beach-records-service"] == {
        "request_case_copy",
        "request_docket_range",
        "request_certified_copy",
    }
    assert tasks_by_source["us-fl-palm-beach-official-records"] == {
        "search_instruments",
        "fetch_instrument",
        "fetch_by_book_page",
        "fetch_document",
    }


def test_wisconsin_plan_separates_case_publication_archive_and_rest_routes(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        jurisdictions=["55"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {row["source_id"]: row for row in plan["sources"]}
    assert sources["us-wi-wcca-public"]["access"]["mode"] == "unclear"
    assert sources["us-wi-wscca-public"]["access"]["mode"] == ("allowed_with_limits")
    assert sources["us-wi-court-opinions"]["access"]["mode"] == ("allowed_with_limits")
    assert sources["us-wi-state-law-library-briefs"]["access"]["mode"] == ("unclear")
    assert sources["us-wi-uw-law-historical-briefs"]["access"]["mode"] == ("unclear")
    assert sources["us-wi-appellate-clerk"]["access"]["mode"] == ("not_applicable")
    assert sources["us-wi-wcca-rest"]["access"]["mode"] == "unclear"

    tasks_by_source: dict[str, set[str]] = {}
    for stage in plan["workflow"]["stages"]:
        if stage["stage_id"] != "court":
            continue
        for task in stage["tasks"]:
            tasks_by_source.setdefault(task["source_id"], set()).add(task["capability"])

    assert tasks_by_source["us-wi-wcca-public"] == {
        "search_cases",
        "search_judgments",
        "search_hearings",
        "fetch_case",
        "list_docket_entries",
    }
    assert tasks_by_source["us-wi-wscca-public"] == {
        "search_cases",
        "search_documents",
        "fetch_case",
        "fetch_document",
        "list_docket_entries",
    }
    assert tasks_by_source["us-wi-wcca-rest"] == {
        "search_cases",
        "list_docket_entries",
    }
    assert tasks_by_source["us-wi-court-opinions"] == {
        "search_full_text",
        "search_opinions",
        "search_orders",
        "fetch_document",
    }


def test_dc_plan_separates_appellate_and_trial_portal_components(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        jurisdictions=["11"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {row["source_id"]: row for row in plan["sources"]}
    assert (
        sources["us-dc-court-of-appeals-case-search"]["access"]["mode"]
        == "allowed_with_limits"
    )
    assert (
        sources["us-dc-court-of-appeals-opinions-mojs"]["access"]["mode"] == "allowed"
    )
    assert sources["us-dc-court-of-appeals-calendars"]["access"]["mode"] == "allowed"
    assert sources["us-dc-superior-eaccess"]["access"]["mode"] == "unclear"
    assert sources["us-dc-superior-court-portal"]["access"]["mode"] == "unclear"

    tasks_by_source: dict[str, set[str]] = {}
    for stage in plan["workflow"]["stages"]:
        for task in stage["tasks"]:
            tasks_by_source.setdefault(task["source_id"], set()).add(task["capability"])
    assert tasks_by_source["us-dc-court-of-appeals-case-search"] == {
        "search_cases",
        "search_participants",
        "fetch_case",
        "fetch_document",
    }

    route_groups = {
        group["primary_source_id"]: group for group in plan["complementary_routes"]
    }
    complements = {
        row["source_id"]: row
        for row in route_groups["us-dc-court-of-appeals-case-search"]["complements"]
    }
    for source_id in {
        "us-dc-court-of-appeals-opinions-mojs",
        "us-dc-court-of-appeals-calendars",
        "us-dc-superior-eaccess",
        "us-dc-superior-court-portal",
    }:
        assert complements[source_id]["record_identity_relation"] == ("independent")


def test_maryland_plan_exposes_case_feed_judgments_and_adjacent_routes(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Holdings LLC",
        addresses=["100 Main Street, Baltimore, MD"],
        jurisdictions=["24"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {row["source_id"]: row for row in plan["sources"]}
    assert sources["us-md-case-search"]["access"]["mode"] == "unclear"
    assert sources["us-md-mdec-public-cases"]["access"]["mode"] == (
        "allowed_with_limits"
    )
    assert sources["us-md-judgment-liens"]["access"]["mode"] == ("allowed_with_limits")
    assert sources["us-md-estate-search"]["access"]["mode"] == ("allowed_with_limits")
    assert sources["us-md-circuit-clerk-records"]["access"]["mode"] == (
        "not_applicable"
    )
    assert sources["us-md-local-finance-tax-liens"]["access"]["mode"] == (
        "not_applicable"
    )
    assert {
        "us-md-estate-search",
        "us-md-appellate-opinions",
        "us-md-business-technology-opinions",
        "us-md-land-records",
        "us-md-plats",
        "us-md-sdat-real-property",
    } <= set(sources)

    tasks_by_source: dict[str, set[str]] = {}
    for stage in plan["workflow"]["stages"]:
        for task in stage["tasks"]:
            tasks_by_source.setdefault(task["source_id"], set()).add(task["capability"])
    assert tasks_by_source["us-md-mdec-public-cases"] == {
        "list_case_reports",
        "search_recent_cases",
        "fetch_report",
        "parse_report",
    }
    assert tasks_by_source["us-md-judgment-liens"] == {
        "search_person_judgments",
        "search_company_judgments",
        "fetch_judgment_events",
    }
    assert tasks_by_source["us-md-estate-search"] == {
        "search_decedent_estates",
        "search_representative_estates",
        "search_estate_number",
        "fetch_estate_detail",
        "list_estate_docket",
    }
    assert tasks_by_source["us-md-business-technology-opinions"] == {
        "search_business_technology_opinions",
        "fetch_business_technology_document",
    }

    route_groups = {
        group["primary_source_id"]: group for group in plan["complementary_routes"]
    }
    mdec_complements = {
        row["source_id"]: row
        for row in route_groups["us-md-mdec-public-cases"]["complements"]
    }
    for source_id in {
        "us-md-case-search",
        "us-md-judgment-liens",
        "us-md-estate-search",
        "us-md-appellate-opinions",
        "us-md-business-technology-opinions",
        "us-md-land-records",
        "us-md-plats",
    }:
        assert mdec_complements[source_id]["record_identity_relation"] == "independent"


def test_michigan_plan_exposes_appellate_categories_and_trial_alternatives(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Holdings LLC",
        jurisdictions=["26"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {row["source_id"]: row for row in plan["sources"]}
    primary_id = "us-mi-appellate-case-opinion-order-search"

    assert sources[primary_id]["access"]["mode"] == "allowed_with_limits"
    assert sources["us-mi-micourt-trial-case-search"]["access"]["mode"] == ("unclear")
    assert (
        sources["us-mi-micourt-developer-case-search-api"]["access"]["mode"]
        == "unclear"
    )
    assert (
        sources["us-mi-business-court-search"]["access"]["mode"]
        == "allowed_with_limits"
    )
    assert sources["us-mi-business-court-search"]["source_status"] == "active"
    assert sources["us-mi-trial-court-directory"]["access"]["mode"] == (
        "not_applicable"
    )

    tasks_by_source: dict[str, set[str]] = {}
    for stage in plan["workflow"]["stages"]:
        for task in stage["tasks"]:
            tasks_by_source.setdefault(task["source_id"], set()).add(task["capability"])
    assert tasks_by_source[primary_id] == {
        "search_cases",
        "search_opinions",
        "search_orders",
        "fetch_document",
    }
    assert tasks_by_source["us-mi-business-court-search"] == {
        "search_business_court_rulings",
        "fetch_ruling",
    }

    route_groups = {
        group["primary_source_id"]: group for group in plan["complementary_routes"]
    }
    complements = {
        row["source_id"]: row for row in route_groups[primary_id]["complements"]
    }
    for source_id in {
        "us-mi-micourt-trial-case-search",
        "us-mi-micourt-developer-case-search-api",
        "us-mi-business-court-search",
        "us-mi-trial-court-directory",
    }:
        assert complements[source_id]["record_identity_relation"] == ("independent")


def test_los_angeles_plan_preserves_routes_and_shares_case_identity(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        addresses=["100 Main Street, Los Angeles, CA"],
        jurisdictions=["06037"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {row["source_id"]: row for row in plan["sources"]}
    core_id = "us-ca-los-angeles-superior-probate"
    name_id = f"{core_id}-name-index"
    images_id = f"{core_id}-document-images"
    archives_id = f"{core_id}-records"
    assessor_id = "us-ca-los-angeles-county-assessor-parcels"
    recorder_id = "us-ca-los-angeles-registrar-recorder-real-estate"

    assert sources[core_id]["access"]["mode"] == "allowed"
    assert sources[name_id]["access"]["mode"] == "not_applicable"
    assert sources[images_id]["access"]["mode"] == "not_applicable"
    assert sources[archives_id]["access"]["mode"] == "not_applicable"
    assert sources[assessor_id]["access"]["mode"] == "allowed_with_limits"
    assert sources[recorder_id]["access"]["mode"] == "not_applicable"
    for source_id in (core_id, name_id, images_id, archives_id):
        assert sources[source_id]["record_identity_source_id"] == core_id
    assert name_id in sources[core_id]["complementary_source_ids"]
    assert recorder_id in sources[assessor_id]["complementary_source_ids"]
    route_groups = {
        row["primary_source_id"]: row for row in plan["complementary_routes"]
    }
    probate_complements = {
        row["source_id"]: row for row in route_groups[core_id]["complements"]
    }
    assert probate_complements[name_id]["record_identity_relation"] == "shared"
    assessor_complements = {
        row["source_id"]: row for row in route_groups[assessor_id]["complements"]
    }
    assert (
        assessor_complements[recorder_id]["record_identity_relation"] == "independent"
    )

    tasks = {
        task["task_id"]: task
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
    }
    core_capabilities = {
        task["capability"] for task in tasks.values() if task["source_id"] == core_id
    }
    assert {
        "fetch_case",
        "fetch_parties",
        "list_docket_entries",
        "list_document_index",
        "list_probate_notes",
        "search_hearings",
    } <= core_capabilities
    note_details = tasks[f"court.{core_id}.list_probate_notes"]["capability_details"]
    assert note_details["adapter_command"] == "notes"
    assert note_details["input_fields"] == [
        "raw_case_number",
        "view",
        "offset",
        "limit",
    ]
    assert note_details["views"] == ["future", "past", "all"]
    assert {
        "summary_text",
        "facts_text",
        "matters_to_clear",
        "probate_examiner_comments",
        "recommended_disposition",
    } <= set(note_details["output_fields"])

    shared_case_searches = {
        f"court.{name_id}.search_cases",
        f"court.{images_id}.search_documents",
        f"court.{core_id}.search_hearings",
    }
    for task_id in (
        f"court.{core_id}.fetch_case",
        f"court.{core_id}.list_probate_notes",
        f"court.{images_id}.fetch_document",
        f"court.{archives_id}.request_case_copy",
    ):
        assert shared_case_searches <= set(tasks[task_id]["depends_on"])
        runtime_fields = set(tasks[task_id]["runtime_inputs"][0]["fields"])
        assert {
            "raw_case_number",
            "trial_case_number",
            "appellate_case_number",
            "native_document_id",
            "notice_refcode",
            "calendar_item",
        } <= runtime_fields

    assert {
        f"property.{assessor_id}.search_address",
        f"property.{assessor_id}.search_assessment_records",
        f"property.{assessor_id}.fetch_parcel",
        f"property.{assessor_id}.fetch_geometry",
        f"property.{assessor_id}.sync",
        f"recorder.{recorder_id}.search_parties",
        f"recorder.{recorder_id}.request_instrument_copy",
        "court.us-ca-second-district-appellate-case-information.search_cases",
        "court.us-ca-judicial-branch-opinions.search_current_opinions",
        "court.us-ca-public-notices.search_publications",
    } <= tasks.keys()
    recorder_inputs = tasks[f"recorder.{recorder_id}.search_parties"]["runtime_inputs"][
        0
    ]["fields"]
    assert {"ain", "apn", "legal_description"} <= set(recorder_inputs)


def test_texas_plan_combines_tames_account_and_complementary_routes(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Holdings LLC",
        jurisdictions=["48"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {row["source_id"]: row for row in plan["sources"]}
    tasks = {
        task["task_id"]: task
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
    }
    tames_id = "us-tx-appellate-tames"
    researchtx_id = "us-tx-researchtx"

    assert sources[tames_id]["access"]["mode"] == "allowed_with_limits"
    assert sources[researchtx_id]["access"]["mode"] == "not_applicable"
    tames_tasks = {
        task["capability"]: task
        for task in tasks.values()
        if task["source_id"] == tames_id
    }
    assert set(tames_tasks) == {
        "search_cases",
        "fetch_case",
        "fetch_parties",
        "list_docket_entries",
        "list_case_events",
        "list_docket_documents",
        "fetch_document",
    }
    assert (
        tames_tasks["search_cases"]["capability_details"]["adapter_command"] == "search"
    )
    for capability in (
        "fetch_case",
        "fetch_parties",
        "list_docket_entries",
        "list_case_events",
        "list_docket_documents",
        "fetch_document",
    ):
        runtime_fields = set(tames_tasks[capability]["runtime_inputs"][0]["fields"])
        assert {
            "raw_case_number",
            "trial_case_number",
            "native_entry_id",
            "native_document_id",
        } <= runtime_fields

    for source_id in (
        "us-tx-appellate-released-orders-opinions",
        "us-tx-supreme-orders-opinions",
    ):
        assert sources[source_id]["record_identity_source_id"] == tames_id
        assert f"court.{source_id}.search_opinions" in tasks
        assert f"court.{source_id}.search_publications" in tasks

    assert f"court.{researchtx_id}.search_cases" in tasks
    assert f"court.{researchtx_id}.search_parties" in tasks
    assert f"court.{researchtx_id}.search_documents" in tasks
    assert f"court.{researchtx_id}.search_hearings" in tasks
    assert f"court.{researchtx_id}.fetch_document" in tasks

    route_groups = {
        row["primary_source_id"]: row for row in plan["complementary_routes"]
    }
    tames_complements = {
        row["source_id"]: row for row in route_groups[tames_id]["complements"]
    }
    assert (
        route_groups[tames_id]["primary_coverage_start"]
        == sources[tames_id]["coverage_start"]
    )
    assert {
        researchtx_id,
        "us-tx-appellate-released-orders-opinions",
        "us-tx-supreme-orders-opinions",
        "us-tx-oca-citations-notices",
    } <= set(tames_complements)
    assert tames_complements[researchtx_id]["access_mode"] == ("not_applicable")
    assert (
        tames_complements[researchtx_id]["coverage_start"]
        == sources[researchtx_id]["coverage_start"]
    )
    assert "search_documents" in tames_complements[researchtx_id]["adds_capabilities"]
    assert (
        tames_complements["us-tx-appellate-released-orders-opinions"][
            "record_identity_relation"
        ]
        == "shared"
    )
    assert plan["coverage"]["complementary_route_group_count"] >= 1


def test_texas_local_portals_and_custodians_remain_distinct_in_plan(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        jurisdictions=["48453", "48209"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {row["source_id"]: row for row in plan["sources"]}
    tasks = {
        task["task_id"]: task
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
    }

    travis_portal = "us-tx-travis-odyssey-courts"
    travis_request = "us-tx-travis-district-clerk-records-request"
    assert sources[travis_request]["record_identity_source_id"] == (travis_portal)
    assert sources[travis_portal]["access"]["mode"] == "unclear"
    assert sources[travis_request]["access"]["mode"] == "not_applicable"
    assert f"court.{travis_portal}.search_cases" in tasks
    assert f"court.{travis_portal}.list_docket_documents" in tasks
    assert f"court.{travis_request}.request_case_copy" in tasks
    assert f"court.{travis_request}.request_court_data" in tasks
    assert "court.us-tx-travis-criminal-docket-search.search_hearings" in tasks

    hays_portal = "us-tx-hays-district-court-portal"
    hays_request = "us-tx-hays-district-clerk-records-request"
    hays_county = "us-tx-hays-county-clerk-courts"
    assert sources[hays_request]["record_identity_source_id"] == hays_portal
    assert {
        task["capability"]
        for task in tasks.values()
        if task["source_id"] == hays_portal
    } == {"search_cases", "fetch_case"}
    assert f"court.{hays_request}.request_case_report" in tasks
    assert f"court.{hays_request}.request_case_copy" in tasks
    assert f"court.{hays_request}.request_certified_copy" in tasks
    assert f"court.{hays_county}.search_cases" in tasks
    assert f"court.{hays_county}.search_hearings" in tasks
    assert f"court.{hays_county}.fetch_case" in tasks


def test_texas_aggregate_sources_stay_out_of_case_workflow(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        jurisdictions=["48"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    task_sources = {
        task["source_id"]
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
    }

    assert "us-tx-oca-court-activity" not in task_sources
    assert "us-tx-oca-statistical-supplements" not in task_sources


def test_pa_de_complementary_routes_emit_actionable_tasks(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)

    pa_plan = build_search_plan(
        "Example Person",
        jurisdictions=["42"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    pa_tasks = {
        task["task_id"]: task
        for stage in pa_plan["workflow"]["stages"]
        for task in stage["tasks"]
    }
    assert (
        "property.us-pa-county-recorder-and-court-routing.route_to_county_recorder"
    ) in pa_tasks
    assert (
        "court.us-pa-county-recorder-and-court-routing.list_prothonotaries"
    ) in pa_tasks
    assert "court.us-pa-judges-and-mdj-districts.list_judges" in pa_tasks
    assert "court.us-pa-judges-and-mdj-districts.search_judges" in pa_tasks
    assert (
        "court.us-pa-judges-and-mdj-districts.route_address_to_magisterial_district"
    ) in pa_tasks

    de_plan = build_search_plan(
        "Example Person",
        addresses=["100 Main Street, Dover, DE"],
        jurisdictions=["10"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    de_tasks = {
        task["task_id"]: task
        for stage in de_plan["workflow"]["stages"]
        for task in stage["tasks"]
    }
    for capability in (
        "list_excess_proceeds",
        "search_owner",
        "search_address",
        "lookup_case",
        "export",
    ):
        assert f"court.us-de-project-rightful-owner.{capability}" in de_tasks


def test_partial_pa_state_layers_do_not_imply_every_county(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        jurisdictions=["42011"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {row["source_id"]: row for row in plan["sources"]}

    for source_id in ("us-pa-dep-parcels", "us-pa-pasda-parcels"):
        coverage = sources[source_id]["requested_jurisdiction_coverage"]
        assert coverage["matched"] == []
        assert coverage["unmatched"] == ["42011"]


def test_govos_plan_capabilities_keep_required_source_selector(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        jurisdictions=["42011"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    source = next(
        row
        for row in plan["sources"]
        if row["source_id"] == "us-pa-berks-recorder-publicsearch"
    )

    for capability in source["capabilities"]:
        if capability["name"] not in {
            "search_instruments",
            "search_document_text",
            "fetch_instrument",
            "fetch_document",
            "probe_source",
        }:
            continue
        assert capability["details"]["fixed_options"]["source"] == (
            "us-pa-berks-recorder-publicsearch"
        )


def test_orange_plan_exposes_distinct_official_complements(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        jurisdictions=["12095"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {source["source_id"]: source for source in plan["sources"]}
    expected = {
        "us-fl-ninth-circuit-division-calendars",
        "us-fl-ninth-circuit-appellate-opinions-archive",
        "us-fl-ninth-circuit-administrative-orders",
        "us-fl-orange-clerk-records-request",
        "us-fl-ninth-circuit-court-reporters",
        "us-fl-orange-official-records",
        "us-fl-orange-court-registry-balance",
        "us-fl-orange-confidentiality-notices",
        "us-fl-appellate-opinions-search",
        "us-fl-sixth-dca-opinion-releases",
        "us-flmd-recent-opinions",
        "us-ca11-published-opinions",
        "us-ca11-unpublished-opinions",
        "us-fl-orange-tax-collector-property-tax",
        "us-fl-orange-comptroller-tax-deed-sales",
    }
    assert expected <= set(sources)
    assert sources["us-flmd-recent-opinions"]["requested_jurisdiction_coverage"][
        "matched"
    ] == ["12095"]
    assert sources["us-ca11-published-opinions"]["requested_jurisdiction_coverage"][
        "matched"
    ] == ["12095"]

    route_groups = {
        group["primary_source_id"]: group for group in plan["complementary_routes"]
    }
    clerk_complements = {
        complement["source_id"]: complement
        for complement in route_groups["us-fl-orange-clerk-my-eclerk"]["complements"]
    }
    assert (
        clerk_complements["us-fl-orange-clerk-records-request"][
            "record_identity_relation"
        ]
        == "shared"
    )
    for source_id in {
        "us-fl-ninth-circuit-division-calendars",
        "us-fl-orange-official-records",
        "us-fl-orange-court-registry-balance",
        "us-fl-orange-confidentiality-notices",
    }:
        assert clerk_complements[source_id]["record_identity_relation"] == "independent"

    statewide_complements = {
        complement["source_id"]: complement
        for complement in route_groups["us-fl-appellate-opinions-search"]["complements"]
    }
    assert (
        statewide_complements["us-fl-sixth-dca-opinion-releases"][
            "record_identity_relation"
        ]
        == "shared"
    )
    assert (
        statewide_complements["us-fl-acis"]["record_identity_relation"] == "independent"
    )

    tasks = {
        task["task_id"]: task
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
    }
    assert "court.us-fl-ninth-circuit-division-calendars.search_hearings" in tasks
    assert "court.us-fl-orange-court-registry-balance.lookup_case" in tasks
    assert "court.us-fl-appellate-opinions-search.search_opinions" in tasks
    assert "court.us-fl-sixth-dca-opinion-releases.search_opinions" in tasks
    assert "court.us-flmd-recent-opinions.search_opinions" in tasks
    assert "court.us-ca11-published-opinions.search_opinions" in tasks
    assert "court.us-ca11-unpublished-opinions.search_opinions" in tasks
    assert "recorder.us-fl-orange-official-records.search_instruments" in tasks
    orange_tax_capability_commands = {
        "search_tax_accounts": None,
        "search_owner": "owner",
        "search_address": "address",
        "fetch_account": "account",
        "fetch_parcel": "parcel",
        "list_releases": "releases",
        "download_bulk": "download",
    }
    for capability, adapter_command in orange_tax_capability_commands.items():
        task_id = (
            "property.us-fl-orange-tax-collector-property-tax."
            f"{capability}"
        )
        assert task_id in tasks
        if adapter_command is not None:
            assert tasks[task_id]["capability_details"]["adapter_command"] == (
                adapter_command
            )
    assert (
        "property.us-fl-orange-comptroller-tax-deed-sales.search_tax_default" in tasks
    )


def test_denver_plan_exposes_verified_property_and_court_complements(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Holdings LLC",
        addresses=["625 N Santa Fe Drive, Denver, CO"],
        jurisdictions=["08031"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {source["source_id"]: source for source in plan["sources"]}
    expected = {
        "us-co-denver-public-trustee-gts",
        "us-co-denver-delinquent-real-property-tax-list",
        "us-co-denver-spatialest-property-tax",
        "us-co-denver-district-court-records-request",
        "us-co-denver-county-court-records-request",
        "us-co-denver-tax-lien-auction",
        "us-co-denver-realforeclose-auctions",
        "us-co-denver-district-administrative-orders",
    }
    assert expected <= set(sources)
    assert all(
        sources[source_id]["requested_jurisdiction_coverage"]["matched"] == ["08031"]
        for source_id in expected
    )
    assert sources["us-co-denver-public-trustee-gts"]["access"]["mode"] == "allowed"
    assert sources["us-co-denver-tax-lien-auction"]["access"]["mode"] == "unclear"
    assert sources["us-co-denver-realforeclose-auctions"]["access"]["mode"] == "unclear"
    assert (
        sources["us-co-denver-district-court-records-request"]["access"]["mode"]
        == "not_applicable"
    )
    assert (
        sources["us-co-denver-county-court-records-request"]["access"]["mode"]
        == "not_applicable"
    )

    route_groups = {
        group["primary_source_id"]: group for group in plan["complementary_routes"]
    }
    parcel_complements = {
        complement["source_id"]: complement
        for complement in route_groups["us-co-denver-parcels"]["complements"]
    }
    for source_id in {
        "us-co-denver-public-trustee-gts",
        "us-co-denver-delinquent-real-property-tax-list",
        "us-co-denver-spatialest-property-tax",
        "us-co-denver-tax-lien-auction",
    }:
        assert (
            parcel_complements[source_id]["record_identity_relation"] == "independent"
        )

    county_complements = {
        complement["source_id"]: complement
        for complement in route_groups["us-co-denver-county-court-public-docket"][
            "complements"
        ]
    }
    assert (
        county_complements["us-co-denver-county-court-records-request"][
            "record_identity_relation"
        ]
        == "shared"
    )

    judicial_complements = {
        complement["source_id"]: complement
        for complement in route_groups["us-co-judicial-docket-search"]["complements"]
    }
    assert (
        judicial_complements["us-co-denver-district-court-records-request"][
            "record_identity_relation"
        ]
        == "shared"
    )
    assert (
        judicial_complements["us-co-denver-district-administrative-orders"][
            "record_identity_relation"
        ]
        == "independent"
    )

    archive_complements = {
        complement["source_id"]: complement
        for complement in route_groups["us-co-appellate-case-law-search"]["complements"]
    }
    assert (
        archive_complements["us-co-judicial-appellate-opinion-releases"][
            "record_identity_relation"
        ]
        == "independent"
    )

    data_complements = {
        complement["source_id"]: complement
        for complement in route_groups["us-co-judicial-data-reports"]["complements"]
    }
    assert {
        "us-co-judicial-compiled-aggregate-data-requests",
        "us-co-judicial-annual-statistical-reports",
        "us-co-judicial-case-parties-without-representation",
        "us-co-judicial-eviction-filings-dashboard",
    } <= set(data_complements)
    assert {
        "us-co-judicial-data-reports",
        "us-co-judicial-compiled-aggregate-data-requests",
        "us-co-judicial-annual-statistical-reports",
        "us-co-judicial-case-parties-without-representation",
        "us-co-judicial-eviction-filings-dashboard",
    } <= set(sources)

    tasks = {
        task["task_id"]: task
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
    }
    for task_id in {
        "property.us-co-denver-public-trustee-gts.search_owner",
        "property.us-co-denver-public-trustee-gts.search_address",
        "property.us-co-denver-public-trustee-gts.search_sales",
        "property.us-co-denver-delinquent-real-property-tax-list.list_releases",
        "property.us-co-denver-delinquent-real-property-tax-list.download_bulk",
        "property.us-co-denver-spatialest-property-tax.search_address",
        "property.us-co-denver-spatialest-property-tax.search_parcels",
        "property.us-co-denver-spatialest-property-tax.fetch_account",
        "property.us-co-denver-tax-lien-auction.search_tax_default",
        "property.us-co-denver-tax-lien-auction.search_sales",
        "property.us-co-denver-realforeclose-auctions.search_sales",
        "recorder.us-co-denver-recorder-publicsearch.request_bulk_files",
        "court.us-co-denver-district-court-records-request.request_case_copy",
        "court.us-co-denver-district-court-records-request.request_certified_copy",
        "court.us-co-denver-county-court-records-request.request_case_copy",
        "court.us-co-denver-county-court-records-request.request_certified_copy",
        "court.us-co-denver-district-administrative-orders.list_document_index",
        "court.us-co-denver-district-administrative-orders.fetch_document",
        "court.us-co-appellate-case-law-search.search_opinions",
        "court.us-co-appellate-case-law-search.fetch_opinion",
        "court.us-co-appellate-case-law-search.fetch_opinion_pdf",
        "court.us-co-judicial-appellate-opinion-releases.list_current_releases",
    }:
        assert task_id in tasks

    gts_search = tasks["property.us-co-denver-public-trustee-gts.search_sales"]
    assert "default_result_cap" not in gts_search["capability_details"]
    assert gts_search["capability_details"]["input_fields"] == [
        "foreclosure_number",
        "status",
        "ned_from",
        "ned_to",
        "sold_from",
        "sold_to",
        "sale_from",
        "sale_to",
        "expedited",
        "show_all",
        "limit",
        "cursor",
    ]


def test_new_york_plan_uses_statewide_parcels_and_field_specific_complements(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Holdings LLC",
        addresses=["10 Main St, Poughkeepsie, NY"],
        jurisdictions=["36"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {source["source_id"]: source for source in plan["sources"]}
    expected = {
        "us-ny-statewide-parcels",
        "us-ny-statewide-parcels-bulk",
        "us-ny-county-parcel-resource-directory",
        "us-ny-orpts-sales-web",
        "us-ny-richmond-county-clerk-land-documents",
        "us-nyc-property-information-portal",
        "us-nyc-acris",
        "us-ny-ogs-land-records",
        "us-ny-assessment-coordinate-lookup",
    }
    assert expected <= set(sources)
    assert sources["us-ny-statewide-parcels"]["access"]["mode"] == (
        "allowed_with_limits"
    )
    assert sources["us-ny-statewide-parcels-bulk"]["access"]["mode"] == "allowed"
    assert (
        sources["us-ny-county-parcel-resource-directory"]["access"]["mode"]
        == "not_applicable"
    )
    assert sources["us-ny-assessment-coordinate-lookup"]["access"]["mode"] == "unclear"

    route_groups = {
        group["primary_source_id"]: group for group in plan["complementary_routes"]
    }
    complements = {
        complement["source_id"]: complement
        for complement in route_groups["us-ny-statewide-parcels"]["complements"]
    }
    assert (
        complements["us-ny-statewide-parcels-bulk"]["record_identity_relation"]
        == "shared"
    )
    for source_id in {
        "us-ny-county-parcel-resource-directory",
        "us-nyc-acris",
        "us-ny-ogs-land-records",
        "us-ny-assessment-coordinate-lookup",
    }:
        assert complements[source_id]["record_identity_relation"] == ("independent")

    tasks = {
        task["task_id"]: task
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
    }
    assert {
        "property.us-ny-statewide-parcels.search_owner",
        "property.us-ny-statewide-parcels.search_address",
        "property.us-ny-statewide-parcels.search_parcels",
        "property.us-ny-statewide-parcels.fetch_geometry",
        "property.us-ny-statewide-parcels.search_recent_deed_reference",
        "property.us-ny-statewide-parcels.search_state_agency",
        "property.us-ny-orpts-sales-web.search_parties",
        "property.us-ny-orpts-sales-web.search_address",
        "property.us-ny-orpts-sales-web.search_parcels",
        "property.us-ny-orpts-sales-web.search_sales",
        "property.us-ny-orpts-sales-web.fetch_sale",
        "property.us-ny-orpts-sales-web.export_search_results",
        "recorder.us-ny-richmond-county-clerk-land-documents.search_instruments",
    } <= set(tasks)
