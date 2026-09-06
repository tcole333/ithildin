from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import yaml

from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_priority import (
    PublicRecordsPriority,
    catalog_audit_summary,
)


AS_OF = "2026-07-28T12:00:00Z"


def test_catalog_audit_summary_surfaces_drift_without_blocking(
    monkeypatch,
    tmp_path,
):
    def fake_audit_catalog(*, db_path):
        assert db_path == tmp_path / "catalog.db"
        return {
            "status": "drift",
            "counts": {
                "tracked_sources": 12,
                "live_catalog_sources": 10,
            },
            "adapter_declared_sources_missing_live_catalog": [
                "us-test-one",
                "us-test-two",
            ],
            "outdated_live_manifests": ["us-test-three"],
            "declared_reviews_missing_live_catalog": [],
            "declared_associations_missing_live_census": [],
            "outdated_live_census_associations": [],
            "shared_adapter_operation_mismatches": [],
        }

    monkeypatch.setattr(
        "tools.seed_public_records_catalog.audit_catalog",
        fake_audit_catalog,
    )

    summary = catalog_audit_summary(tmp_path / "catalog.db")

    assert summary == {
        "status": "drift",
        "tracked_sources": 12,
        "live_catalog_sources": 10,
        "issue_count": 3,
        "issues": {
            "adapter_declared_sources_missing_live_catalog": [
                "us-test-one",
                "us-test-two",
            ],
            "outdated_live_manifests": ["us-test-three"],
        },
    }


def test_sheriff_sale_capabilities_do_not_establish_assessment_coverage():
    source = {
        "roles": ["sales", "sheriff_sale_auction_records"],
        "capabilities": ["search_sales"],
    }

    assert (
        PublicRecordsPriority._role_evidence(
            source,
            domain="property",
            role="assessment_roll",
            directly_linked=False,
            coverage_kind="jurisdiction",
        )
        is None
    )


def _manifest(
    *,
    source_id: str,
    geoid: str,
    source_status: str = "active",
) -> dict:
    return {
        "source_id": source_id,
        "name": f"Test Source {source_id}",
        "domain": "property",
        "roles": ["assessment"],
        "authority": "Test Authority",
        "operator": "Test Authority",
        "jurisdiction_geoids": [geoid],
        "official_url": f"https://example.gov/{source_id}",
        "platform_family": "documented_api",
        "access_class": "B",
        "automation_disposition": "allowed_with_limits",
        "authentication": "none",
        "fees": "none",
        "stable_keys": ["native_id"],
        "adapter_family": "test_adapter",
        "adapter_version": 1,
        "last_verified_at": "2026-07-27T12:00:00Z",
        "source_status": source_status,
        "capabilities": ["search_owner", "fetch_parcel"],
    }


def _investigation_fixture(tmp_path: Path) -> tuple[Path, Path]:
    investigation_db = tmp_path / "investigation.db"
    db = sqlite3.connect(investigation_db)
    db.executescript(
        """
        CREATE TABLE investigation_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT INTO investigation_config(key, value)
        VALUES('active_profile', 'test-profile');

        CREATE TABLE leads (
            id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            category TEXT,
            priority TEXT,
            status TEXT,
            source TEXT,
            target_name TEXT,
            findings TEXT,
            profile_id TEXT
        );
        INSERT INTO leads(
            id, title, description, category, priority, status, profile_id
        ) VALUES
            (
                1,
                'North Carolina court docket',
                'Find the state trial case filing and judgment',
                'legal',
                'high',
                'open',
                'test-profile'
            ),
            (
                2,
                'North Carolina property assessment',
                'Completed parcel question',
                'entity',
                'critical',
                'completed',
                'test-profile'
            ),
            (
                3,
                'North Carolina unrelated profile lead',
                'court docket',
                'legal',
                'critical',
                'open',
                'different-profile'
            );

        CREATE TABLE infra_requests (
            id INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            priority TEXT,
            status TEXT,
            source_name TEXT,
            source_url TEXT,
            data_type TEXT,
            access_method TEXT,
            estimated_coverage TEXT,
            related_lead_id INTEGER
        );
        INSERT INTO infra_requests(
            id, title, description, priority, status, data_type
        ) VALUES
            (
                11,
                'North Carolina parcel assessment source',
                'Official statewide property roll',
                'high',
                'in_progress',
                'property assessment'
            ),
            (
                12,
                'North Carolina old court source',
                'No longer active',
                'critical',
                'completed',
                'court cases'
            );
        """
    )
    db.commit()
    db.close()

    investigations_dir = tmp_path / "investigations"
    profile_dir = investigations_dir / "test-profile"
    profile_dir.mkdir(parents=True)
    (profile_dir / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "test-profile",
                "primary_subject": "Test Subject",
                "known_addresses": {
                    "123 Main Street, Raleigh, NC": "Known office",
                    "1 Unlocated Road": "No geographic hint",
                },
            }
        ),
        encoding="utf-8",
    )
    return investigation_db, investigations_dir


def _priority_fixture(tmp_path: Path) -> tuple[PublicRecordsPriority, Path]:
    catalog_db = tmp_path / "catalog.db"
    census = PublicRecordsCensus(catalog_db)
    census.seed()
    catalog = PublicRecordsCatalog(catalog_db)

    catalog.register_manifest(
        _manifest(source_id="us-nc-test-assessment", geoid="37"),
        submitted_by="test",
    )
    catalog.evaluate_access(
        "us-nc-test-assessment",
        access_class="B",
        automation_disposition="allowed_with_limits",
        limits={"page_size": 1000},
        reviewed_by="test",
        review_basis="Documented public test API.",
        reviewed_at="2026-07-27T12:00:00Z",
    )
    catalog.record_probe(
        "us-nc-test-assessment",
        status="ok",
        probed_by="test",
        probed_at="2026-07-27T12:00:00Z",
        endpoint="https://example.gov/us-nc-test-assessment",
        result_count=1,
    )

    catalog.register_manifest(
        _manifest(
            source_id="us-ca-test-assessment",
            geoid="06037",
            source_status="candidate",
        ),
        submitted_by="test",
    )
    catalog.record_probe(
        "us-ca-test-assessment",
        status="error",
        probed_by="test",
        probed_at="2024-01-01T00:00:00Z",
        endpoint="https://example.gov/us-ca-test-assessment",
        error="test source error",
    )

    investigation_db, investigations_dir = _investigation_fixture(tmp_path)
    return (
        PublicRecordsPriority(
            catalog_db,
            investigation_db=investigation_db,
            investigations_dir=investigations_dir,
        ),
        catalog_db,
    )


def _target(
    catalog_db: Path,
    *,
    state: str,
    domain: str,
    role: str,
    jurisdiction_geoid: str | None = None,
) -> dict:
    rows = PublicRecordsCensus(catalog_db).list_targets(
        state=state,
        domain=domain,
        role=role,
    )
    if jurisdiction_geoid is not None:
        rows = [
            row
            for row in rows
            if row["geoid"] == jurisdiction_geoid
        ]
    assert len(rows) == 1
    return rows[0]


def test_recompute_uses_separate_explainable_dimensions(tmp_path):
    priority, catalog_db = _priority_fixture(tmp_path)

    result = priority.recompute(actor="test-agent", as_of=AS_OF)

    expected_targets = PublicRecordsCensus(catalog_db).stats()["total_targets"]
    assert result["targets_evaluated"] == expected_targets
    assert result["dry_run"] is False
    assert result["demand_inputs"] == {
        "known_addresses": 2,
        "known_addresses_with_state": 1,
        "unmatched_addresses": ["1 Unlocated Road"],
        "open_leads": 1,
        "active_infra_requests": 1,
        "input_fingerprint": result["demand_inputs"]["input_fingerprint"],
    }

    nc_property = _target(
        catalog_db,
        state="NC",
        domain="property",
        role="assessment_roll",
    )
    assert nc_property["benefit_score"] == 25
    assert nc_property["feasibility_score"] == 90
    assert nc_property["risk_score"] == 9
    benefit = nc_property["priority_basis"]["dimensions"]["benefit"]
    assert benefit["components"]["known_addresses"]["score"] == 10
    assert benefit["components"]["open_leads"]["score"] == 0
    assert benefit["components"]["active_infra_requests"]["score"] == 15
    feasibility = nc_property["priority_basis"]["dimensions"]["feasibility"]
    risk = nc_property["priority_basis"]["dimensions"]["risk"]
    assert feasibility["selected_source_id"] == "us-nc-test-assessment"
    assert risk["selected_source_id"] == "us-nc-test-assessment"

    nc_court = _target(
        catalog_db,
        state="NC",
        domain="court",
        role="trial_case_index",
    )
    assert nc_court["benefit_score"] == 17
    assert nc_court["feasibility_score"] == 0
    assert nc_court["risk_score"] == 25
    court_benefit = nc_court["priority_basis"]["dimensions"]["benefit"]
    assert court_benefit["components"]["known_addresses"]["score"] == 5
    assert court_benefit["components"]["open_leads"]["score"] == 12

    ca_property = _target(
        catalog_db,
        state="CA",
        domain="property",
        role="assessment_roll",
    )
    assert ca_property["benefit_score"] == 0
    assert ca_property["feasibility_score"] < nc_property["feasibility_score"]
    assert ca_property["risk_score"] > nc_property["risk_score"]
    ca_scope = ca_property["priority_basis"]["dimensions"]["feasibility"][
        "components"
    ]["jurisdiction_coverage"]
    assert ca_scope == {
        "score": 5.0,
        "kind": "subjurisdiction",
        "covers_complete_target_scope": False,
    }

    serialized = json.dumps(nc_property["priority_basis"])
    assert "priority_score" not in serialized
    assert "combined_score" not in serialized


def test_recompute_emits_audit_events_and_dry_run_does_not_write(tmp_path):
    priority, catalog_db = _priority_fixture(tmp_path)
    first = priority.recompute(actor="first-agent", as_of=AS_OF)
    target = _target(
        catalog_db,
        state="NC",
        domain="property",
        role="assessment_roll",
    )
    target_id = target["census_target_id"]

    db = sqlite3.connect(catalog_db)
    before = db.execute(
        """
        SELECT COUNT(*) FROM source_census_events
        WHERE census_target_id=? AND event_type='priority_recomputed'
        """,
        (target_id,),
    ).fetchone()[0]
    db.close()

    dry_run = priority.recompute(
        actor="dry-run-agent",
        as_of=AS_OF,
        dry_run=True,
    )
    db = sqlite3.connect(catalog_db)
    after_dry_run = db.execute(
        """
        SELECT COUNT(*) FROM source_census_events
        WHERE census_target_id=? AND event_type='priority_recomputed'
        """,
        (target_id,),
    ).fetchone()[0]
    db.close()

    second = priority.recompute(actor="second-agent", as_of=AS_OF)
    explanation = priority.explain(target_id)
    priority_events = explanation["priority_events"]

    assert first["run_id"] == dry_run["run_id"] == second["run_id"]
    assert dry_run["targets_changed"] == 0
    assert before == after_dry_run == 1
    assert [event["actor"] for event in priority_events] == [
        "first-agent",
        "second-agent",
    ]
    assert priority_events[-1]["details"]["changed"] is False
    assert priority_events[-1]["details"]["new_scores"] == {
        "benefit": 25.0,
        "feasibility": 90.0,
        "risk": 9.0,
    }


def test_metrics_report_dimensions_and_pareto_frontier(tmp_path):
    priority, catalog_db = _priority_fixture(tmp_path)
    priority.recompute(actor="test-agent", as_of=AS_OF)

    metrics = priority.metrics()
    expected_targets = PublicRecordsCensus(catalog_db).stats()["total_targets"]

    assert metrics["targets"] == expected_targets
    assert metrics["targets_with_recomputed_basis"] == expected_targets
    assert metrics["targets_with_catalog_capability_path"] == 2
    assert metrics["catalog_state"]["sources"] == 2
    assert metrics["catalog_state"]["sources_with_access_review"] == 1
    assert metrics["catalog_state"]["sources_with_probe"] == 2
    assert metrics["by_capability"]["property.assessment_roll"][
        "with_catalog_capability_path"
    ] == 2
    assert set(metrics["score_dimensions"]) == {
        "benefit",
        "feasibility",
        "risk",
    }
    assert metrics["comparison_model"]["dimensions"] == [
        {"name": "benefit", "direction": "higher"},
        {"name": "feasibility", "direction": "higher"},
        {"name": "risk", "direction": "lower"},
    ]
    assert metrics["comparison_model"]["pareto_frontier"]
    provenance = metrics["priority_provenance"]
    assert provenance["status"] == "current"
    assert provenance["active_profile"] == "test-profile"
    assert provenance["targets_matching_active_profile"] == expected_targets
    assert provenance["targets_matching_current_inputs"] == expected_targets
    assert provenance["targets_with_other_profile"] == 0
    serialized = json.dumps(metrics)
    assert "priority_score" not in serialized
    assert "combined_score" not in serialized


def test_metrics_exposes_active_profile_and_input_drift(tmp_path):
    priority, catalog_db = _priority_fixture(tmp_path)
    priority.recompute(actor="test-agent", as_of=AS_OF)
    expected_targets = PublicRecordsCensus(catalog_db).stats()["total_targets"]

    profile_path = (
        priority.investigations_dir / "test-profile" / "config.yaml"
    )
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["known_addresses"]["456 New Street, Charlotte, NC"] = (
        "New demand"
    )
    profile_path.write_text(yaml.safe_dump(profile), encoding="utf-8")

    changed_inputs = priority.metrics()["priority_provenance"]
    assert changed_inputs["status"] == "inputs_changed"
    assert changed_inputs["targets_matching_active_profile"] == expected_targets
    assert changed_inputs["targets_matching_current_inputs"] == 0

    other_profile = priority.investigations_dir / "other-profile"
    other_profile.mkdir()
    (other_profile / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "other-profile",
                "primary_subject": "Other Subject",
                "known_addresses": {},
            }
        ),
        encoding="utf-8",
    )
    db = sqlite3.connect(priority.investigation_db)
    db.execute(
        """
        UPDATE investigation_config SET value='other-profile'
        WHERE key='active_profile'
        """
    )
    db.commit()
    db.close()

    wrong_profile = priority.metrics()["priority_provenance"]
    assert wrong_profile["status"] == "profile_mismatch"
    assert wrong_profile["active_profile"] == "other-profile"
    assert wrong_profile["targets_matching_active_profile"] == 0
    assert wrong_profile["targets_with_other_profile"] == expected_targets


def test_nationwide_source_needs_explicit_state_coverage_role(tmp_path):
    priority, catalog_db = _priority_fixture(tmp_path)
    catalog = PublicRecordsCatalog(catalog_db)
    catalog.register_manifest(
        {
            "source_id": "us-national-opinion-archive",
            "name": "National Opinion Archive",
            "domain": "court",
            "roles": ["opinion_archive", "federal_docket_archive"],
            "authority": "Test Authority",
            "operator": "Test Authority",
            "jurisdiction_geoids": ["US"],
            "official_url": "https://example.gov/national-opinions",
            "platform_family": "documented_api",
            "access_class": "B",
            "automation_disposition": "unclear",
            "authentication": "none",
            "fees": "none",
            "stable_keys": ["native_id"],
            "adapter_family": "test_adapter",
            "adapter_version": 1,
            "last_verified_at": "2026-07-27T12:00:00Z",
            "source_status": "active",
            "capabilities": ["search_cases", "search_opinions", "sync"],
        },
        submitted_by="test",
    )
    catalog.register_manifest(
        {
            "source_id": "us-national-state-opinion-aggregator",
            "name": "National State Opinion Aggregator",
            "domain": "court",
            "roles": ["legal_aggregator", "opinion_archive"],
            "authority": "Source courts",
            "operator": "Test Authority",
            "jurisdiction_geoids": ["US"],
            "official_url": "https://example.gov/state-opinions",
            "platform_family": "documented_api",
            "access_class": "B",
            "automation_disposition": "unclear",
            "authentication": "none",
            "fees": "none",
            "stable_keys": ["native_id"],
            "adapter_family": "test_adapter",
            "adapter_version": 1,
            "last_verified_at": "2026-07-27T12:00:00Z",
            "source_status": "active",
            "capabilities": ["search_cases", "search_opinions"],
        },
        submitted_by="test",
    )

    priority.recompute(actor="test-agent", as_of=AS_OF)

    appellate = _target(
        catalog_db,
        state="NC",
        domain="court",
        role="appellate_opinions",
    )
    trial = _target(
        catalog_db,
        state="NC",
        domain="court",
        role="trial_case_index",
    )
    bulk = _target(
        catalog_db,
        state="NC",
        domain="court",
        role="bulk_data_program",
    )
    assert appellate["priority_basis"]["dimensions"]["feasibility"][
        "selected_source_id"
    ] == "us-national-state-opinion-aggregator"
    assert {
        item["source_id"]
        for item in appellate["priority_basis"]["dimensions"]["feasibility"][
            "candidate_sources"
        ]
    } == {"us-national-state-opinion-aggregator"}
    assert trial["priority_basis"]["dimensions"]["feasibility"][
        "selected_source_id"
    ] is None
    assert bulk["priority_basis"]["dimensions"]["feasibility"][
        "selected_source_id"
    ] is None


def test_parcel_identifier_search_does_not_establish_geometry_coverage(
    tmp_path,
):
    priority, catalog_db = _priority_fixture(tmp_path)
    catalog = PublicRecordsCatalog(catalog_db)
    manifest = _manifest(
        source_id="us-ny-test-recorder",
        geoid="36061",
    )
    manifest["roles"] = ["recorder", "instrument_index"]
    manifest["capabilities"] = [
        "search_parties",
        "search_parcels",
        "fetch_instrument",
    ]
    catalog.register_manifest(manifest, submitted_by="test")

    priority.recompute(actor="test-agent", as_of=AS_OF)

    geometry = _target(
        catalog_db,
        state="NY",
        domain="property",
        role="parcel_geometry",
        jurisdiction_geoid="36061",
    )
    land_records = _target(
        catalog_db,
        state="NY",
        domain="property",
        role="land_records_index",
    )
    geometry_candidates = geometry["priority_basis"]["dimensions"][
        "feasibility"
    ]["candidate_sources"]
    land_candidates = land_records["priority_basis"]["dimensions"][
        "feasibility"
    ]["candidate_sources"]

    assert "us-ny-test-recorder" not in {
        candidate["source_id"] for candidate in geometry_candidates
    }
    assert "us-ny-test-recorder" in {
        candidate["source_id"] for candidate in land_candidates
    }


def test_case_search_source_does_not_satisfy_bulk_data_target(tmp_path):
    priority, catalog_db = _priority_fixture(tmp_path)
    catalog = PublicRecordsCatalog(catalog_db)
    base = {
        "domain": "court",
        "authority": "Test State Courts",
        "operator": "Test State Courts",
        "jurisdiction_geoids": ["37"],
        "access_class": "B",
        "automation_disposition": "unclear",
        "authentication": "none",
        "fees": "none",
        "stable_keys": ["case_number"],
        "adapter_family": "test_adapter",
        "adapter_version": 1,
        "last_verified_at": "2026-07-27T12:00:00Z",
        "source_status": "active",
    }
    catalog.register_manifest(
        {
            **base,
            "source_id": "us-nc-test-case-search",
            "name": "North Carolina Test Case Search",
            "roles": ["court_administration", "case_metadata"],
            "official_url": "https://example.gov/nc-case-search",
            "platform_family": "browser_portal",
            "capabilities": ["search_cases", "fetch_case"],
        },
        submitted_by="test",
    )
    catalog.register_manifest(
        {
            **base,
            "source_id": "us-nc-test-directory",
            "name": "North Carolina Test Court Directory",
            "roles": ["court_administration"],
            "official_url": "https://example.gov/nc-court-directory",
            "platform_family": "public_directory",
            "capabilities": ["list_courts"],
        },
        submitted_by="test",
    )
    catalog.register_manifest(
        {
            **base,
            "source_id": "us-nc-test-bulk",
            "name": "North Carolina Test Bulk Feed",
            "roles": ["court_administration", "bulk_case_metadata"],
            "official_url": "https://example.gov/nc-bulk",
            "platform_family": "licensed_bulk",
            "capabilities": ["sync", "apply_deletions"],
        },
        submitted_by="test",
    )
    catalog.register_manifest(
        {
            **base,
            "source_id": "us-nc-test-specialized-case-list",
            "name": "North Carolina Specialized Case List",
            "roles": [
                "litigant_index",
                "case_discovery",
                "public_spreadsheet",
            ],
            "official_url": "https://example.gov/nc-specialized-list",
            "platform_family": "public_html_and_xlsx",
            "capabilities": [
                "search_cases",
                "fetch_document",
                "sync",
            ],
        },
        submitted_by="test",
    )
    catalog.register_manifest(
        {
            **base,
            "source_id": "us-nc-test-appellate-releases",
            "name": "North Carolina Appellate Releases",
            "roles": ["appellate_release_index", "opinions", "orders"],
            "official_url": "https://example.gov/nc-appellate-releases",
            "platform_family": "public_release_index",
            "capabilities": ["search_opinions", "fetch_document"],
        },
        submitted_by="test",
    )

    priority.recompute(actor="test-agent", as_of=AS_OF)

    bulk = _target(
        catalog_db,
        state="NC",
        domain="court",
        role="bulk_data_program",
    )
    directory = _target(
        catalog_db,
        state="NC",
        domain="court",
        role="court_directory",
    )
    trial = _target(
        catalog_db,
        state="NC",
        domain="court",
        role="trial_case_index",
    )
    appellate = _target(
        catalog_db,
        state="NC",
        domain="court",
        role="appellate_opinions",
    )
    feasibility = bulk["priority_basis"]["dimensions"]["feasibility"]
    assert feasibility["selected_source_id"] == "us-nc-test-bulk"
    assert {
        item["source_id"] for item in feasibility["candidate_sources"]
    } == {"us-nc-test-bulk"}
    directory_feasibility = directory["priority_basis"]["dimensions"][
        "feasibility"
    ]
    assert directory_feasibility["selected_source_id"] == (
        "us-nc-test-directory"
    )
    directory_role_evidence = directory_feasibility["components"][
        "role_capability_evidence"
    ]
    assert directory_role_evidence["alias_roles"] == []
    assert directory_role_evidence["capabilities"] == ["list_courts"]
    assert directory_role_evidence[
        "capability_establishes_coverage"
    ] is True
    assert {
        item["source_id"]
        for item in trial["priority_basis"]["dimensions"]["feasibility"][
            "candidate_sources"
        ]
    } == {"us-nc-test-case-search"}
    assert {
        item["source_id"]
        for item in appellate["priority_basis"]["dimensions"]["feasibility"][
            "candidate_sources"
        ]
    } == {"us-nc-test-appellate-releases"}


def test_all_census_source_associations_feed_priority_selection(tmp_path):
    priority, catalog_db = _priority_fixture(tmp_path)
    catalog = PublicRecordsCatalog(catalog_db)
    for source_id in (
        "us-ca-first-tax-source",
        "us-ca-second-tax-source",
    ):
        manifest = _manifest(source_id=source_id, geoid="06037")
        manifest["roles"] = ["tax_collection"]
        manifest["capabilities"] = ["search"]
        catalog.register_manifest(manifest, submitted_by="test")
    catalog.evaluate_access(
        "us-ca-second-tax-source",
        access_class="B",
        automation_disposition="allowed",
        limits={},
        reviewed_by="test",
        review_basis="Documented public test API.",
        reviewed_at="2026-07-27T12:00:00Z",
    )
    catalog.record_probe(
        "us-ca-second-tax-source",
        status="ok",
        probed_by="test",
        probed_at="2026-07-27T12:00:00Z",
        endpoint="https://example.gov/us-ca-second-tax-source",
        result_count=1,
    )
    census = PublicRecordsCensus(catalog_db)
    target = _target(
        catalog_db,
        state="NC",
        domain="property",
        role="tax_collection",
    )
    census.resolve(
        target["census_target_id"],
        status="source_identified",
        source_id="us-ca-first-tax-source",
        resolved_by="test",
    )
    census.associate_source(
        target["census_target_id"],
        source_id="us-ca-second-tax-source",
        added_by="test",
        coverage={"route": "supplemental"},
    )

    priority.recompute(actor="test-agent", as_of=AS_OF)
    updated = _target(
        catalog_db,
        state="NC",
        domain="property",
        role="tax_collection",
    )
    feasibility = updated["priority_basis"]["dimensions"]["feasibility"]

    assert feasibility["selected_source_id"] == "us-ca-second-tax-source"
    assert {
        item["source_id"] for item in feasibility["candidate_sources"]
    } == {
        "us-ca-first-tax-source",
        "us-ca-second-tax-source",
    }
    explanation = priority.explain(target["census_target_id"])
    assert explanation["source_ids"] == [
        "us-ca-first-tax-source",
        "us-ca-second-tax-source",
    ]


def test_direct_cli_import_path_supports_repository_tool_pattern():
    project_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "tools/public_records_priority.py", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "benefit, feasibility, and risk" in result.stdout


def test_recompute_help_documents_as_of_timezone_requirement():
    project_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [
            sys.executable,
            "tools/public_records_priority.py",
            "recompute",
            "--help",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "ISO 8601 timestamp with timezone" in result.stdout


def test_state_abbreviations_require_address_or_location_context():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(
            """
            SELECT 'OR' AS subdivision_code, 'Oregon' AS jurisdiction_name
            UNION ALL
            SELECT 'IN', 'Indiana'
            UNION ALL
            SELECT 'CO', 'Colorado'
            """
        ).fetchall()
    finally:
        db.close()
    patterns = PublicRecordsPriority._jurisdiction_patterns(rows)

    assert PublicRecordsPriority._mentioned_states(
        "Need OR integration and an IN clause",
        patterns,
    ) == frozenset()
    assert PublicRecordsPriority._mentioned_states(
        "Request records from the agency, or use the public portal",
        patterns,
    ) == frozenset()
    assert PublicRecordsPriority._mentioned_states(
        "Search permits, in addition to court records",
        patterns,
    ) == frozenset()
    assert PublicRecordsPriority._mentioned_states(
        "Palantir HQ, Denver CO",
        patterns,
    ) == frozenset({"CO"})
    assert PublicRecordsPriority._mentioned_states(
        "123 Main Street, Portland, OR 97201",
        patterns,
    ) == frozenset({"OR"})


def test_appellate_and_probate_only_sources_do_not_imply_general_trial_index():
    appellate = {
        "roles": [
            "appellate_case_metadata",
            "party_index",
            "docket_entries",
            "document_portal",
        ],
        "capabilities": ["search_cases", "list_docket_entries"],
    }
    probate = {
        "roles": [
            "superior_court_probate",
            "trial_case_metadata",
            "docket_entries",
        ],
        "capabilities": ["search_cases", "list_docket_entries"],
    }

    assert PublicRecordsPriority._role_evidence(
        appellate,
        domain="court",
        role="trial_case_index",
        directly_linked=False,
        coverage_kind="jurisdiction",
    ) is None
    assert PublicRecordsPriority._role_evidence(
        probate,
        domain="court",
        role="trial_case_index",
        directly_linked=False,
        coverage_kind="subjurisdiction",
    ) is None
