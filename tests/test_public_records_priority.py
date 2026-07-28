from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import yaml

from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_priority import PublicRecordsPriority


AS_OF = "2026-07-28T12:00:00Z"


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
) -> dict:
    rows = PublicRecordsCensus(catalog_db).list_targets(
        state=state,
        domain=domain,
        role=role,
    )
    assert len(rows) == 1
    return rows[0]


def test_recompute_uses_separate_explainable_dimensions(tmp_path):
    priority, catalog_db = _priority_fixture(tmp_path)

    result = priority.recompute(actor="test-agent", as_of=AS_OF)

    assert result["targets_evaluated"] == 448
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
    priority, _ = _priority_fixture(tmp_path)
    priority.recompute(actor="test-agent", as_of=AS_OF)

    metrics = priority.metrics()

    assert metrics["targets"] == 448
    assert metrics["targets_with_recomputed_basis"] == 448
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
    serialized = json.dumps(metrics)
    assert "priority_score" not in serialized
    assert "combined_score" not in serialized


def test_nationwide_capability_does_not_imply_every_state_role(tmp_path):
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
    ] == "us-national-opinion-archive"
    assert trial["priority_basis"]["dimensions"]["feasibility"][
        "selected_source_id"
    ] is None
    assert bulk["priority_basis"]["dimensions"]["feasibility"][
        "selected_source_id"
    ] is None


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
