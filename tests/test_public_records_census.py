from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import (
    DEFAULT_CONFIG_PATH,
    CensusError,
    PublicRecordsCensus,
)


def _manifest(*, source_id: str, domain: str = "property") -> dict:
    return {
        "source_id": source_id,
        "name": "North Carolina Test Source",
        "domain": domain,
        "roles": ["assessment"],
        "authority": "Test Authority",
        "operator": "Test Authority",
        "jurisdiction_geoids": ["37"],
        "official_url": "https://example.gov/records",
        "platform_family": "documented_api",
        "access_class": "B",
        "automation_disposition": "allowed_with_limits",
        "authentication": "none",
        "fees": "none",
        "stable_keys": ["native_id"],
        "adapter_family": "test_adapter",
        "adapter_version": 1,
        "capabilities": ["search"],
    }


def test_seed_is_nationwide_idempotent_and_upgrades_placeholder(tmp_path):
    db_path = tmp_path / "catalog.db"
    catalog = PublicRecordsCatalog(db_path)
    catalog.register_manifest(_manifest(source_id="us-nc-test-source"), submitted_by="test")

    census = PublicRecordsCensus(db_path)
    first = census.seed()
    second = census.seed()

    assert first["jurisdictions_seen"] == 56
    assert first["targets_seen"] == 448
    assert first["targets_created"] == 448
    assert second["jurisdictions_created"] == 0
    assert second["targets_created"] == 0

    db = sqlite3.connect(db_path)
    row = db.execute(
        "SELECT jurisdiction_id, name, kind, subdivision_code "
        "FROM jurisdictions WHERE geoid='37'"
    ).fetchone()
    db.close()
    assert row == ("us-geoid-37", "North Carolina", "state_equivalent", "NC")


def test_separate_scores_drive_claim_order_and_are_audited(tmp_path):
    census = PublicRecordsCensus(tmp_path / "catalog.db")
    census.seed()
    targets = census.list_targets(
        state="NC",
        domain="property",
        role="assessment_roll",
    )
    target_id = targets[0]["census_target_id"]

    scored = census.score(
        target_id,
        benefit=90,
        feasibility=70,
        risk=15,
        basis={"active_profile_addresses": 2},
        scored_by="test-agent",
    )
    claimed = census.claim(claimed_by="worker", domain="property", state="NC")

    assert scored["benefit_score"] == 90
    assert scored["feasibility_score"] == 70
    assert scored["risk_score"] == 15
    assert "priority_score" not in scored
    assert claimed is not None
    assert claimed["census_target_id"] == target_id
    assert [event["event_type"] for event in claimed["events"]] == [
        "seeded",
        "scored",
        "claimed",
    ]


def test_manifest_submission_does_not_create_an_access_review(tmp_path):
    db_path = tmp_path / "catalog.db"
    census = PublicRecordsCensus(db_path)
    census.seed()
    target = census.claim(claimed_by="worker", domain="property", state="NC")
    assert target is not None
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(_manifest(source_id="us-nc-submitted-source")),
        encoding="utf-8",
    )

    result = census.submit_manifest(
        target["census_target_id"],
        manifest_path,
        submitted_by="worker",
    )

    assert result["target"]["status"] == "manifest_submitted"
    assert result["target"]["source_id"] == "us-nc-submitted-source"
    assert result["target"]["source_ids"] == ["us-nc-submitted-source"]
    assert result["target"]["coverage_status"] == "unassessed"
    decision = PublicRecordsCatalog(db_path).machine_acquisition_decision(
        "us-nc-submitted-source",
    )
    assert decision["allowed"] is False
    assert decision["reason_code"] == "access_review_required"


def test_resolution_rejects_a_source_from_the_wrong_domain(tmp_path):
    db_path = tmp_path / "catalog.db"
    catalog = PublicRecordsCatalog(db_path)
    catalog.register_manifest(
        _manifest(source_id="us-nc-test-courts", domain="court"),
        submitted_by="test",
    )
    census = PublicRecordsCensus(db_path)
    census.seed()
    target = census.list_targets(
        state="NC",
        domain="property",
        role="assessment_roll",
    )[0]

    with pytest.raises(CensusError, match="domain does not match"):
        census.resolve(
            target["census_target_id"],
            status="source_identified",
            source_id="us-nc-test-courts",
            resolved_by="test",
        )


def test_direct_cli_import_path_supports_repository_tool_pattern():
    project_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "tools/public_records_census.py", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "source-census queue" in result.stdout
    assert "associate" in result.stdout
    assert "assess-coverage" in result.stdout


def test_multiple_sources_and_coverage_gaps_remain_explicit(tmp_path):
    db_path = tmp_path / "catalog.db"
    catalog = PublicRecordsCatalog(db_path)
    for source_id in ("us-nc-statewide-index", "us-nc-county-index"):
        catalog.register_manifest(
            _manifest(source_id=source_id),
            submitted_by="test",
        )
    census = PublicRecordsCensus(db_path)
    census.seed()
    target = census.list_targets(
        state="NC",
        domain="property",
        role="assessment_roll",
    )[0]
    target_id = target["census_target_id"]

    resolved = census.resolve(
        target_id,
        status="source_identified",
        source_id="us-nc-statewide-index",
        resolved_by="test",
        notes="State-level source located; local coverage is not yet assessed.",
    )
    associated = census.associate_source(
        target_id,
        source_id="us-nc-county-index",
        added_by="test",
        coverage={"counties": ["Wake"]},
        coverage_gaps=["Remaining counties"],
        notes="County-specific source",
        evidence=[{"kind": "official_page", "url": "https://example.gov/records"}],
    )
    assessed = census.assess_coverage(
        target_id,
        coverage_status="partial",
        coverage_gaps=["Counties outside the documented source footprints"],
        notes="Two routes identified; county coverage remains incomplete.",
        evidence=[{"kind": "coverage_review", "reviewed_by": "test"}],
        assessed_by="test",
    )

    assert resolved["status"] == "source_identified"
    assert resolved["coverage_status"] == "unassessed"
    assert resolved["source_count"] == 1
    assert resolved["source_ids"] == ["us-nc-statewide-index"]
    assert associated["source_id"] == "us-nc-statewide-index"
    assert associated["source_ids"] == [
        "us-nc-statewide-index",
        "us-nc-county-index",
    ]
    assert associated["source_associations"][1]["coverage"] == {
        "counties": ["Wake"]
    }
    assert associated["source_associations"][1]["coverage_gaps"] == [
        "Remaining counties"
    ]
    assert assessed["coverage_status"] == "partial"
    assert assessed["coverage_gaps"] == [
        "Counties outside the documented source footprints"
    ]
    assert census.list_targets(
        state="NC",
        domain="property",
        role="assessment_roll",
    )[0]["source_count"] == 2
    stats = census.stats()
    assert stats["source_associations"] == 2
    assert stats["targets_with_multiple_sources"] == 1
    assert stats["targets_with_explicit_gaps"] == 1


def test_comprehensive_coverage_is_an_explicit_assessment(tmp_path):
    db_path = tmp_path / "catalog.db"
    catalog = PublicRecordsCatalog(db_path)
    catalog.register_manifest(
        _manifest(source_id="us-nc-statewide-index"),
        submitted_by="test",
    )
    census = PublicRecordsCensus(db_path)
    census.seed()
    target = census.list_targets(
        state="NC",
        domain="property",
        role="assessment_roll",
    )[0]
    target_id = target["census_target_id"]

    discovered = census.resolve(
        target_id,
        status="source_identified",
        source_id="us-nc-statewide-index",
        resolved_by="test",
    )

    assert discovered["coverage_status"] == "unassessed"
    with pytest.raises(CensusError, match="unresolved gaps"):
        census.assess_coverage(
            target_id,
            coverage_status="comprehensive",
            coverage_gaps=["One county"],
            assessed_by="test",
        )


def test_version_two_source_link_is_migrated_to_association(tmp_path):
    db_path = tmp_path / "catalog.db"
    catalog = PublicRecordsCatalog(db_path)
    catalog.register_manifest(
        _manifest(source_id="us-nc-legacy-source"),
        submitted_by="test",
    )
    census = PublicRecordsCensus(db_path)
    census.seed()
    target = census.list_targets(
        state="NC",
        domain="property",
        role="assessment_roll",
    )[0]
    target_id = target["census_target_id"]
    census.resolve(
        target_id,
        status="source_identified",
        source_id="us-nc-legacy-source",
        resolved_by="legacy-agent",
        notes="Legacy source",
    )

    db = sqlite3.connect(db_path)
    db.execute("DROP TABLE source_census_target_sources")
    db.execute(
        "ALTER TABLE source_census_targets DROP COLUMN coverage_status"
    )
    db.execute("ALTER TABLE source_census_targets DROP COLUMN coverage_notes")
    db.execute(
        "ALTER TABLE source_census_targets DROP COLUMN coverage_gaps_json"
    )
    db.execute(
        "UPDATE schema_meta SET value='2' WHERE key='schema_version'"
    )
    db.commit()
    db.close()

    migrated = PublicRecordsCensus(db_path).show(target_id)

    assert migrated["coverage_status"] == "unassessed"
    assert migrated["coverage_gaps"] == []
    assert migrated["source_ids"] == ["us-nc-legacy-source"]
    assert migrated["source_associations"][0]["notes"] == "Legacy source"


def test_trial_case_index_description_includes_all_official_routes():
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    description = config["roles"]["court"]["trial_case_index"]

    for route in ("online", "request", "bulk", "subscription", "in person"):
        assert route in description
    assert "remotely public" not in description
