from __future__ import annotations

import json
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
    build_parser,
    compact_target_rows,
)


def _configured_target_count() -> int:
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    role_count = sum(
        len(domain_roles) for domain_roles in config["roles"].values()
    )
    return (
        len(config["jurisdictions"]) * role_count
        + len(config.get("additional_targets", []))
    )


def _manifest(
    *,
    source_id: str,
    domain: str = "property",
    official_url: str = "https://example.gov/records",
) -> dict:
    return {
        "source_id": source_id,
        "name": "North Carolina Test Source",
        "domain": domain,
        "roles": ["assessment"],
        "authority": "Test Authority",
        "operator": "Test Authority",
        "jurisdiction_geoids": ["37"],
        "official_url": official_url,
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

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    assert first["jurisdictions_seen"] == (
        len(config["jurisdictions"])
        + len(config.get("additional_jurisdictions", []))
    )
    assert first["targets_seen"] == _configured_target_count()
    assert first["targets_created"] == _configured_target_count()
    assert second["jurisdictions_created"] == 0
    assert second["targets_created"] == 0

    db = sqlite3.connect(db_path)
    row = db.execute(
        "SELECT jurisdiction_id, name, kind, subdivision_code "
        "FROM jurisdictions WHERE geoid='37'"
    ).fetchone()
    db.close()
    assert row == ("us-geoid-37", "North Carolina", "state_equivalent", "NC")


def test_additional_targets_seed_only_declared_geographies_and_roles(tmp_path):
    census = PublicRecordsCensus(tmp_path / "catalog.db")
    census.seed()

    expected_county_targets = {
        ("12095", "property", "tax_collection"),
        ("12099", "property", "assessment_roll"),
        ("12099", "property", "parcel_geometry"),
        ("12099", "property", "tax_collection"),
        ("12099", "property", "tax_deed_cases_and_sales"),
        ("41039", "property", "assessment_roll"),
        ("41039", "property", "parcel_geometry"),
        ("41039", "property", "tax_collection"),
        ("41039", "property", "land_records_index"),
        ("41047", "property", "assessment_roll"),
        ("53045", "property", "assessment_roll"),
        ("53045", "property", "parcel_geometry"),
    }
    expected_maryland_extensions = {
        ("24", "property", "assessment_component_bulk_releases"),
        ("24", "property", "assessment_roll_bulk_representation"),
        ("24", "property", "residential_sales_analytic_bulk"),
    }

    db = sqlite3.connect(census.db_path)
    county_rows = db.execute(
        """
        SELECT j.geoid, t.domain, t.role
        FROM source_census_targets t
        JOIN jurisdictions j USING(jurisdiction_id)
        WHERE j.geoid IN ('12095', '12099', '41039', '41047', '53045')
        """
    ).fetchall()
    maryland_rows = db.execute(
        """
        SELECT j.geoid, t.domain, t.role
        FROM source_census_targets t
        JOIN jurisdictions j USING(jurisdiction_id)
        WHERE j.geoid='24'
          AND t.role IN (
              'assessment_component_bulk_releases',
              'assessment_roll_bulk_representation',
              'residential_sales_analytic_bulk'
          )
        """
    ).fetchall()
    jurisdictions = db.execute(
        """
        SELECT child.geoid, child.kind, child.subdivision_code,
               parent.geoid
        FROM jurisdictions child
        JOIN jurisdictions parent
          ON parent.jurisdiction_id=child.parent_jurisdiction_id
        WHERE child.geoid IN ('12095', '12099', '41039', '41047', '53045')
        ORDER BY child.geoid
        """
    ).fetchall()
    db.close()

    assert set(county_rows) == expected_county_targets
    assert set(maryland_rows) == expected_maryland_extensions
    assert jurisdictions == [
        ("12095", "county_equivalent", "FL", "12"),
        ("12099", "county_equivalent", "FL", "12"),
        ("41039", "county_equivalent", "OR", "41"),
        ("41047", "county_equivalent", "OR", "41"),
        ("53045", "county_equivalent", "WA", "53"),
    ]


def test_additional_target_configuration_rejects_duplicate_keys(tmp_path):
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    config["additional_targets"].append(
        dict(config["additional_targets"][0])
    )
    config_path = tmp_path / "census.yaml"
    config_path.write_text(
        yaml.safe_dump(config, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(
        CensusError,
        match="duplicate additional census target",
    ):
        PublicRecordsCensus(tmp_path / "catalog.db").seed(config_path)


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
    assert "disassociate-source" in result.stdout
    assert "assess-coverage" in result.stdout


def test_associate_and_coverage_help_identify_json_arguments():
    project_root = Path(__file__).resolve().parent.parent
    associate = subprocess.run(
        [
            sys.executable,
            "tools/public_records_census.py",
            "associate",
            "--help",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    coverage = subprocess.run(
        [
            sys.executable,
            "tools/public_records_census.py",
            "assess-coverage",
            "--help",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert associate.returncode == 0, associate.stderr
    assert coverage.returncode == 0, coverage.stderr
    assert "JSON object" in associate.stdout
    assert "JSON list" in associate.stdout
    assert "JSON list" in coverage.stdout


def test_compact_list_projection_keeps_ranked_triage_fields() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["list", "--compact", "--candidate-presence", "some"]
    )
    assert args.compact is True
    assert args.candidate_presence == "some"

    compact = compact_target_rows(
        [
            {
                "census_target_id": 17,
                "jurisdiction_id": "us-state-nc",
                "jurisdiction_name": "North Carolina",
                "geoid": "37",
                "subdivision_code": "NC",
                "domain": "property",
                "role": "assessment_roll",
                "status": "pending",
                "coverage_status": "partial",
                "benefit_score": 80.0,
                "feasibility_score": 65.0,
                "risk_score": 20.0,
                "priority_profile_name": "test-profile",
                "priority_as_of": "2026-07-30T12:00:00Z",
                "priority_run_id": "priority-example",
                "priority_input_fingerprint": "input-example",
                "source_count": 2,
                "source_ids": ["us-nc-one", "us-nc-two"],
                "candidate_source_count": 2,
                "candidate_source_ids": [
                    "us-nc-candidate-one",
                    "us-nc-candidate-two",
                ],
                "claimed_by": None,
                "priority_basis": {"large": "expanded evidence"},
                "coverage_gaps": ["Remaining counties"],
                "source_associations": [{"source_id": "us-nc-one"}],
            }
        ]
    )

    assert compact == [
        {
            "census_target_id": 17,
            "jurisdiction_id": "us-state-nc",
            "jurisdiction_name": "North Carolina",
            "geoid": "37",
            "subdivision_code": "NC",
            "domain": "property",
            "role": "assessment_roll",
            "status": "pending",
            "coverage_status": "partial",
            "benefit_score": 80.0,
            "feasibility_score": 65.0,
            "risk_score": 20.0,
            "priority_profile_name": "test-profile",
            "priority_as_of": "2026-07-30T12:00:00Z",
            "priority_run_id": "priority-example",
            "priority_input_fingerprint": "input-example",
            "source_count": 2,
            "source_ids": ["us-nc-one", "us-nc-two"],
            "candidate_source_count": 2,
            "candidate_source_ids": [
                "us-nc-candidate-one",
                "us-nc-candidate-two",
            ],
            "claimed_by": None,
        }
    ]
    assert "priority_basis" not in compact[0]
    assert "source_associations" not in compact[0]


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


def test_source_presence_and_coverage_filters_separate_discovery_backlog(
    tmp_path,
):
    db_path = tmp_path / "catalog.db"
    catalog = PublicRecordsCatalog(db_path)
    catalog.register_manifest(
        _manifest(source_id="us-nc-known-assessment"),
        submitted_by="test",
    )
    census = PublicRecordsCensus(db_path)
    census.seed()
    assessment = census.list_targets(
        state="NC",
        domain="property",
        role="assessment_roll",
    )[0]
    census.associate_source(
        assessment["census_target_id"],
        source_id="us-nc-known-assessment",
        added_by="test",
    )
    census.assess_coverage(
        assessment["census_target_id"],
        coverage_status="partial",
        coverage_gaps=["Remaining record classes"],
        assessed_by="test",
    )

    sourced = census.list_targets(
        state="NC",
        domain="property",
        source_presence="some",
    )
    unsourced = census.list_targets(
        state="NC",
        domain="property",
        source_presence="none",
    )
    partial = census.list_targets(
        state="NC",
        domain="property",
        coverage_status="partial",
    )

    assert [row["census_target_id"] for row in sourced] == [
        assessment["census_target_id"]
    ]
    assert assessment["census_target_id"] not in {
        row["census_target_id"] for row in unsourced
    }
    assert [row["census_target_id"] for row in partial] == [
        assessment["census_target_id"]
    ]


def test_claim_source_presence_skips_targets_that_already_have_a_source(
    tmp_path,
):
    db_path = tmp_path / "catalog.db"
    catalog = PublicRecordsCatalog(db_path)
    catalog.register_manifest(
        _manifest(source_id="us-nc-known-assessment"),
        submitted_by="test",
    )
    census = PublicRecordsCensus(db_path)
    census.seed()
    assessment = census.list_targets(
        state="NC",
        domain="property",
        role="assessment_roll",
    )[0]
    census.associate_source(
        assessment["census_target_id"],
        source_id="us-nc-known-assessment",
        added_by="test",
    )
    census.score(
        assessment["census_target_id"],
        benefit=100,
        feasibility=100,
        risk=0,
        basis={"known_source": True},
        scored_by="test",
    )

    discovery = census.claim(
        claimed_by="discovery-agent",
        domain="property",
        state="NC",
        source_presence="none",
    )
    integration = census.claim(
        claimed_by="integration-agent",
        domain="property",
        state="NC",
        source_presence="some",
    )

    assert discovery is not None
    assert discovery["census_target_id"] != assessment["census_target_id"]
    assert discovery["source_count"] == 0
    assert integration is not None
    assert integration["census_target_id"] == assessment["census_target_id"]
    assert integration["source_count"] == 1


def test_candidate_presence_separates_known_candidates_from_discovery(
    tmp_path,
):
    census = PublicRecordsCensus(tmp_path / "catalog.db")
    census.seed()
    assessment = census.list_targets(
        state="NC",
        domain="property",
        role="assessment_roll",
    )[0]
    geometry = census.list_targets(
        state="NC",
        domain="property",
        role="parcel_geometry",
    )[0]
    census.score(
        assessment["census_target_id"],
        benefit=90,
        feasibility=80,
        risk=10,
        basis={
            "dimensions": {
                "feasibility": {
                    "candidate_sources": [
                        {"source_id": "us-nc-candidate-a"},
                        {"source_id": "us-nc-candidate-b"},
                        {"source_id": "us-nc-candidate-a"},
                    ]
                }
            }
        },
        scored_by="priority-recompute",
    )
    census.score(
        geometry["census_target_id"],
        benefit=80,
        feasibility=0,
        risk=25,
        basis={
            "dimensions": {
                "feasibility": {
                    "candidate_sources": [
                        {},
                        {"source_id": ""},
                        "not-a-candidate-record",
                    ]
                }
            }
        },
        scored_by="priority-recompute",
    )

    candidate_review = census.list_targets(
        state="NC",
        domain="property",
        source_presence="none",
        candidate_presence="some",
    )
    source_discovery = census.list_targets(
        state="NC",
        domain="property",
        source_presence="none",
        candidate_presence="none",
    )

    assert [row["census_target_id"] for row in candidate_review] == [
        assessment["census_target_id"]
    ]
    assert candidate_review[0]["candidate_source_ids"] == [
        "us-nc-candidate-a",
        "us-nc-candidate-b",
    ]
    assert candidate_review[0]["candidate_source_count"] == 2
    assert geometry["census_target_id"] in {
        row["census_target_id"] for row in source_discovery
    }
    assert assessment["census_target_id"] not in {
        row["census_target_id"] for row in source_discovery
    }

    discovery_claim = census.claim(
        claimed_by="discovery-agent",
        domain="property",
        state="NC",
        source_presence="none",
        candidate_presence="none",
    )
    candidate_claim = census.claim(
        claimed_by="candidate-review-agent",
        domain="property",
        state="NC",
        source_presence="none",
        candidate_presence="some",
    )

    assert discovery_claim is not None
    assert discovery_claim["candidate_source_count"] == 0
    assert candidate_claim is not None
    assert candidate_claim["census_target_id"] == (
        assessment["census_target_id"]
    )
    assert candidate_claim["candidate_source_count"] == 2


def test_disassociate_source_reselects_primary_and_preserves_assessment(tmp_path):
    db_path = tmp_path / "catalog.db"
    catalog = PublicRecordsCatalog(db_path)
    for source_id in (
        "us-nc-source-a",
        "us-nc-source-b",
        "us-nc-source-c",
    ):
        catalog.register_manifest(
            _manifest(
                source_id=source_id,
                official_url=f"https://example.gov/{source_id[-1]}",
            ),
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
        source_id="us-nc-source-a",
        resolved_by="test",
    )
    for source_id in ("us-nc-source-b", "us-nc-source-c"):
        census.associate_source(
            target_id,
            source_id=source_id,
            added_by="test",
        )
    census.assess_coverage(
        target_id,
        coverage_status="partial",
        coverage_gaps=["One field family remains open"],
        notes="Keep this assessment while associations change.",
        assessed_by="test",
    )

    first = census.disassociate_source(
        target_id,
        source_id="us-nc-source-a",
        removed_by="reviewer",
    )

    assert first["source_ids"] == ["us-nc-source-b", "us-nc-source-c"]
    assert first["source_id"] == "us-nc-source-b"
    assert first["official_url"] == "https://example.gov/b"
    assert first["status"] == "source_identified"
    assert first["coverage_status"] == "partial"
    assert first["coverage_gaps"] == ["One field family remains open"]
    assert first["coverage_notes"] == (
        "Keep this assessment while associations change."
    )
    event = first["events"][-1]
    assert event["event_type"] == "source_disassociated"
    assert event["actor"] == "reviewer"
    assert event["from_status"] == event["to_status"] == "source_identified"
    assert event["details"]["source_id"] == "us-nc-source-a"
    assert event["details"]["was_primary"] is True
    assert event["details"]["replacement_source_id"] == "us-nc-source-b"
    assert event["details"]["removed_association"]["source_id"] == (
        "us-nc-source-a"
    )

    second = census.disassociate_source(
        target_id,
        source_id="us-nc-source-c",
        removed_by="reviewer",
    )
    assert second["source_ids"] == ["us-nc-source-b"]
    assert second["source_id"] == "us-nc-source-b"
    assert second["events"][-1]["details"]["was_primary"] is False

    final = census.disassociate_source(
        target_id,
        source_id="us-nc-source-b",
        removed_by="reviewer",
    )
    assert final["source_ids"] == []
    assert final["source_id"] is None
    assert final["official_url"] is None
    assert final["status"] == "source_identified"
    assert final["coverage_status"] == "partial"
    with pytest.raises(CensusError, match="is not associated"):
        census.disassociate_source(
            target_id,
            source_id="us-nc-source-b",
            removed_by="reviewer",
        )


def test_disassociate_source_cli_updates_a_temporary_catalog(tmp_path):
    project_root = Path(__file__).resolve().parent.parent
    db_path = tmp_path / "catalog.db"
    catalog = PublicRecordsCatalog(db_path)
    for source_id in ("us-nc-primary", "us-nc-remove"):
        catalog.register_manifest(
            _manifest(source_id=source_id),
            submitted_by="test",
        )
    census = PublicRecordsCensus(db_path)
    census.seed()
    target_id = census.list_targets(
        state="NC",
        domain="property",
        role="assessment_roll",
    )[0]["census_target_id"]
    census.resolve(
        target_id,
        status="source_identified",
        source_id="us-nc-primary",
        resolved_by="test",
    )
    census.associate_source(
        target_id,
        source_id="us-nc-remove",
        added_by="test",
    )
    output_path = tmp_path / "disassociated.json"

    result = subprocess.run(
        [
            sys.executable,
            "tools/public_records_census.py",
            "--db",
            str(db_path),
            "disassociate-source",
            str(target_id),
            "--source-id",
            "us-nc-remove",
            "--by",
            "cli-test",
            "--output",
            str(output_path),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["source_ids"] == ["us-nc-primary"]
    assert payload["source_id"] == "us-nc-primary"
    assert payload["events"][-1]["event_type"] == "source_disassociated"
    assert payload["events"][-1]["actor"] == "cli-test"


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
