from pathlib import Path
import json
import sqlite3
import subprocess
import sys

import pytest
import yaml

from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.seed_public_records_catalog import (
    DEFAULT_CENSUS_CONFIG_PATH,
    DEFAULT_CONFIG_PATH,
    audit_catalog,
    declared_adapter_source_paths,
    ensure_catalog_source,
    seed_catalog,
)


def _configured_census_target_count() -> int:
    config = yaml.safe_load(
        Path(DEFAULT_CENSUS_CONFIG_PATH).read_text(encoding="utf-8")
    )
    role_count = sum(len(domain_roles) for domain_roles in config["roles"].values())
    return (
        len(config["jurisdictions"]) * role_count
        + len(config.get("additional_targets", []))
    )


def _config(path: Path):
    data = {
        "schema_version": 1,
        "submitted_by": "test-bootstrap",
        "sources": [
            {
                "source_id": "us-nc-test-parcels",
                "name": "Test Parcels",
                "domain": "property",
                "roles": ["assessment"],
                "authority": "Test Authority",
                "operator": "Test Authority",
                "jurisdiction_geoids": ["37"],
                "official_url": "https://example.gov/parcels",
                "platform_family": "arcgis_rest",
                "access_class": "B",
                "automation_disposition": "allowed_with_limits",
                "authentication": "none",
                "fees": "none",
                "stable_keys": ["native_parcel_id"],
                "adapter_family": "arcgis_rest",
                "adapter_version": 1,
                "capabilities": ["fetch_parcel"],
                "access_review": {
                    "access_class": "B",
                    "automation_disposition": "allowed_with_limits",
                    "reviewed_by": "test-reviewer",
                    "review_basis": "documented official API",
                    "limits": {"maximum_page_size": 1000},
                },
            },
            {
                "source_id": "us-ny-test-court",
                "name": "Test Court",
                "domain": "court",
                "roles": ["court"],
                "authority": "Test Court",
                "operator": "Test Court",
                "jurisdiction_geoids": ["36"],
                "official_url": "https://example.gov/court",
                "platform_family": "browser_portal",
                "access_class": "C",
                "automation_disposition": "prohibited",
                "authentication": "guest",
                "fees": "none",
                "stable_keys": ["raw_case_number"],
                "adapter_family": "human_action",
                "adapter_version": 1,
                "capabilities": ["search_cases"],
                "access_review": {
                    "access_class": "C",
                    "automation_disposition": "prohibited",
                    "reviewed_by": "test-reviewer",
                    "review_basis": "official terms prohibit bots",
                },
            },
        ],
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_seed_is_idempotent_and_preserves_gate_separation(tmp_path):
    config_path = tmp_path / "sources.yaml"
    db_path = tmp_path / "catalog.db"
    _config(config_path)

    first = seed_catalog(db_path=db_path, config_path=config_path)
    second = seed_catalog(db_path=db_path, config_path=config_path)

    assert first["sources_seen"] == 2
    assert first["manifests_registered"] == 2
    assert first["access_reviews_recorded"] == 2
    assert second["manifests_registered"] == 0
    assert second["access_reviews_recorded"] == 0
    assert second["access_reviews_unchanged"] == 2

    catalog = PublicRecordsCatalog(db_path)
    assert catalog.require_machine_acquisition("us-nc-test-parcels")["allowed"] is True
    assert catalog.machine_acquisition_decision("us-ny-test-court")["allowed"] is False


def test_catalog_audit_reconciles_shared_routes_manifests_and_live_state(
    tmp_path,
):
    config_path = tmp_path / "sources.yaml"
    db_path = tmp_path / "catalog.db"
    _config(config_path)
    seed_catalog(db_path=db_path, config_path=config_path)
    routed = {"us-nc-test-parcels", "us-ny-test-court"}

    clean = audit_catalog(
        db_path=db_path,
        config_path=config_path,
        adapter_source_ids=routed,
        declared_adapter_sources={
            "us-nc-test-parcels": "tools/query_test_parcels.py",
        },
    )

    assert clean["status"] == "ok"
    assert clean["counts"]["tracked_sources"] == 2
    assert clean["counts"]["shared_adapter_sources"] == 2
    assert clean["counts"]["declared_adapter_sources"] == 1
    assert clean["counts"]["adapter_declared_sources"] == 2
    assert clean["counts"]["live_catalog_sources"] == 2
    assert clean["shared_adapter_sources_missing_manifest"] == []
    assert clean["declared_adapter_sources_missing_manifest"] == []
    assert clean["outdated_live_manifests"] == []

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["sources"][0]["name"] = "Renamed Test Parcels"
    data["sources"][0]["census_associations"] = [
        {
            "jurisdiction_geoid": "37",
            "role": "assessment_roll",
            "coverage": {"counties": ["Wake"]},
        }
    ]
    config_path.write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )
    drift = audit_catalog(
        db_path=db_path,
        config_path=config_path,
        adapter_source_ids={*routed, "us-nc-untracked-adapter"},
        declared_adapter_sources={
            "us-nc-test-parcels": "tools/query_test_parcels.py",
            "us-nc-standalone-adapter": (
                "tools/query_test_standalone.py"
            ),
        },
    )

    assert drift["status"] == "drift"
    assert drift["shared_adapter_sources_missing_manifest"] == [
        "us-nc-untracked-adapter"
    ]
    assert drift["shared_adapter_sources_missing_live_catalog"] == [
        "us-nc-untracked-adapter"
    ]
    assert drift["declared_adapter_sources_missing_manifest"] == [
        {
            "source_id": "us-nc-standalone-adapter",
            "tool": "tools/query_test_standalone.py",
        }
    ]
    assert drift["declared_adapter_sources_missing_live_catalog"] == [
        {
            "source_id": "us-nc-standalone-adapter",
            "tool": "tools/query_test_standalone.py",
        }
    ]
    assert drift["adapter_declared_sources_missing_manifest"] == [
        "us-nc-standalone-adapter",
        "us-nc-untracked-adapter",
    ]
    assert drift["outdated_live_manifests"] == ["us-nc-test-parcels"]
    assert drift["declared_associations_missing_live_census"] == [
        "us-nc-test-parcels:37/property/assessment_roll"
    ]


def test_catalog_audit_does_not_create_a_missing_database(tmp_path):
    config_path = tmp_path / "sources.yaml"
    db_path = tmp_path / "missing.db"
    _config(config_path)

    result = audit_catalog(
        db_path=db_path,
        config_path=config_path,
        adapter_source_ids={"us-nc-test-parcels"},
        declared_adapter_sources={},
    )

    assert result["status"] == "drift"
    assert result["db_exists"] is False
    assert result["schema_present"] is False
    assert not db_path.exists()


def test_catalog_audit_compares_declared_shared_operations_to_routes(
    tmp_path,
):
    config_path = tmp_path / "sources.yaml"
    db_path = tmp_path / "catalog.db"
    _config(config_path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["sources"][0]["capabilities"] = [
        {
            "name": "query_shared_property_records",
            "details": {
                "adapter_tool": "query_property.py",
                "shared_operations": ["search", "discover"],
            },
        }
    ]
    config_path.write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )
    seed_catalog(db_path=db_path, config_path=config_path)

    result = audit_catalog(
        db_path=db_path,
        config_path=config_path,
        adapter_source_ids={
            "us-nc-test-parcels",
            "us-ny-test-court",
        },
        adapter_operations={
            "us-nc-test-parcels": {"search", "discovery"},
            "us-ny-test-court": {"search"},
        },
        declared_adapter_sources={},
    )

    assert result["status"] == "drift"
    assert result["shared_adapter_operation_mismatches"] == [
        {
            "source_id": "us-nc-test-parcels",
            "declared": ["discover", "search"],
            "actual": ["discovery", "search"],
        }
    ]


def test_declared_adapter_scan_finds_literal_public_record_source_ids(
    tmp_path,
):
    (tmp_path / "query_alpha.py").write_text(
        "\n".join(
            [
                "from tools.public_records_contract import PublicRecordsQuery",
                'SOURCE_ID: str = "us-test-alpha"',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "query_beta.py").write_text(
        "\n".join(
            [
                "from tools.public_records_contract import PublicRecordsQuery",
                'SOURCE_ID = "us-test-beta"',
                'ARCHIVE_SOURCE_ID = "us-test-beta-archive"',
                'CATALOG_SOURCE_ID = "us-test-beta-adapter-catalog"',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "query_dynamic.py").write_text(
        "\n".join(
            [
                "from tools.public_records_contract import PublicRecordsQuery",
                'PREFIX = "us-test"',
                'SOURCE_ID = PREFIX + "-dynamic"',
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "query_components.py").write_text(
        "\n".join(
            [
                "from tools.public_records_contract import PublicRecordsQuery",
                "COMPONENTS = [",
                '    SourceSpec(source_id="us-test-component"),',
                '    SourceSpec(source_id="au-test-court"),',
                (
                    '    SourceSpec(arcgis_source_id="us-test-component-map"),'
                ),
                (
                    '    SourceSpec(catalog_source_id='
                    '"us-test-component-catalog"),'
                ),
                "]",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "query_unrelated.py").write_text(
        'SOURCE_ID = "us-test-unrelated"\n',
        encoding="utf-8",
    )

    assert declared_adapter_source_paths(tmp_path) == {
        "au-test-court": str(tmp_path / "query_components.py"),
        "us-test-alpha": str(tmp_path / "query_alpha.py"),
        "us-test-beta": str(tmp_path / "query_beta.py"),
        "us-test-beta-archive": str(tmp_path / "query_beta.py"),
        "us-test-component": str(tmp_path / "query_components.py"),
        "us-test-component-map": str(tmp_path / "query_components.py"),
    }


def test_oregon_source_aliases_reuse_catalog_identity() -> None:
    declared = declared_adapter_source_paths()
    configured = {
        source["source_id"]
        for source in yaml.safe_load(
            DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
        )["sources"]
    }

    assert "us-or-ormap-cadastral-routing" in declared
    assert "us-or-ormap-cadastral-routing" in configured
    assert "us-or-ormap-assessor-maps" not in declared
    assert "us-or-lincoln-county-geomoose-map" not in declared
    assert (
        "us-or-linn-josephine-klamath-assessor-arcgis"
        not in declared
    )


def test_seed_materializes_tracked_census_associations_idempotently(tmp_path):
    config_path = tmp_path / "sources.yaml"
    db_path = tmp_path / "catalog.db"
    _config(config_path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["sources"][0]["census_associations"] = [
        {
            "jurisdiction_geoid": "37",
            "role": "parcel_geometry",
            "coverage": {"counties": ["Wake"]},
            "coverage_gaps": ["Remaining counties"],
        },
        {
            "jurisdiction_geoid": "37",
            "role": "assessment_roll",
            "coverage": {
                "counties": ["Wake"],
                "record_classes": ["assessment", "owner"],
            },
            "coverage_gaps": ["Remaining counties"],
            "notes": "County contribution to the statewide target.",
            "evidence": [
                {
                    "kind": "official_page",
                    "url": "https://example.gov/parcels",
                }
            ],
        },
    ]
    data["sources"][1]["census_associations"] = [
        {
            "jurisdiction_geoid": "36",
            "role": "trial_case_index",
            "coverage": {"court_systems": ["Test Court"]},
        }
    ]
    config_path.write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )

    first = seed_catalog(db_path=db_path, config_path=config_path)
    second = seed_catalog(db_path=db_path, config_path=config_path)

    assert first["census_targets_created"] == _configured_census_target_count()
    assert first["census_associations_seen"] == 3
    assert first["census_associations_created"] == 3
    assert first["census_associations_updated"] == 0
    assert second["census_targets_created"] == 0
    assert second["census_associations_created"] == 0
    assert second["census_associations_updated"] == 0
    assert second["census_associations_unchanged"] == 3

    census = PublicRecordsCensus(db_path)
    assessment = census.list_targets(
        state="NC",
        domain="property",
        role="assessment_roll",
    )[0]
    assert assessment["status"] == "pending"
    assert assessment["coverage_status"] == "unassessed"
    assert assessment["source_id"] is None
    assert assessment["source_ids"] == ["us-nc-test-parcels"]
    assert assessment["source_associations"][0]["coverage"] == {
        "counties": ["Wake"],
        "record_classes": ["assessment", "owner"],
    }
    assert assessment["source_associations"][0]["coverage_gaps"] == [
        "Remaining counties"
    ]
    assert [
        event["event_type"]
        for event in census.show(assessment["census_target_id"])["events"]
    ] == ["seeded", "source_associated"]

    current_manifest = PublicRecordsCatalog(db_path).show_source("us-nc-test-parcels")[
        "current_manifest"
    ]
    assert [item["role"] for item in current_manifest["census_associations"]] == [
        "assessment_roll",
        "parcel_geometry",
    ]
    assert all(
        item["domain"] == "property" for item in current_manifest["census_associations"]
    )


def test_seed_preserves_undeclared_association_and_replaces_declared_pair(
    tmp_path,
):
    config_path = tmp_path / "sources.yaml"
    db_path = tmp_path / "catalog.db"
    _config(config_path)
    seed_catalog(db_path=db_path, config_path=config_path)

    census = PublicRecordsCensus(db_path)
    assessment = census.list_targets(
        state="NC",
        domain="property",
        role="assessment_roll",
    )[0]
    census.associate_source(
        assessment["census_target_id"],
        source_id="us-nc-test-parcels",
        added_by="human-reviewer",
        coverage={"counties": ["Durham"]},
        coverage_gaps=["Other counties"],
        notes="Local assessment",
    )

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["sources"][0]["census_associations"] = [
        {
            "jurisdiction_geoid": "37",
            "role": "parcel_geometry",
            "coverage": {"counties": ["Wake"]},
        }
    ]
    config_path.write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )
    added = seed_catalog(db_path=db_path, config_path=config_path)

    preserved = census.list_targets(
        state="NC",
        domain="property",
        role="assessment_roll",
    )[0]["source_associations"][0]
    assert preserved["coverage"] == {"counties": ["Durham"]}
    assert preserved["added_by"] == "human-reviewer"
    assert added["census_associations_created"] == 1
    assert added["census_associations_updated"] == 0

    data["sources"][0]["census_associations"].append(
        {
            "jurisdiction_geoid": "37",
            "role": "assessment_roll",
            "coverage": {"counties": ["Wake", "Durham"]},
            "coverage_gaps": ["Other counties"],
            "notes": "Tracked assessment",
        }
    )
    config_path.write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )
    replaced = seed_catalog(db_path=db_path, config_path=config_path)

    declared = census.list_targets(
        state="NC",
        domain="property",
        role="assessment_roll",
    )[0]["source_associations"][0]
    assert declared["coverage"] == {"counties": ["Wake", "Durham"]}
    assert declared["notes"] == "Tracked assessment"
    assert declared["added_by"] == "test-bootstrap"
    assert replaced["census_associations_updated"] == 1
    assert replaced["census_associations_unchanged"] == 1


def test_seed_rejects_unknown_tracked_census_target_before_source_writes(
    tmp_path,
):
    config_path = tmp_path / "sources.yaml"
    db_path = tmp_path / "catalog.db"
    _config(config_path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    data["sources"][0]["census_associations"] = [
        {
            "jurisdiction_geoid": "37",
            "role": "unknown_role",
        }
    ]
    config_path.write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="targets do not exist"):
        seed_catalog(db_path=db_path, config_path=config_path)

    assert PublicRecordsCatalog(db_path).list_sources() == []


def test_current_local_and_bulk_sources_seed_exact_census_targets(tmp_path):
    db_path = tmp_path / "catalog.db"
    seed_catalog(db_path=db_path)

    expected = {
        (
            "us-fl-orange-tax-collector-property-tax",
            "12095",
            "property",
            "tax_collection",
        ),
        (
            "us-fl-palm-beach-property-appraiser",
            "12099",
            "property",
            "assessment_roll",
        ),
        (
            "us-fl-palm-beach-property-appraiser",
            "12099",
            "property",
            "parcel_geometry",
        ),
        (
            "us-fl-palm-beach-tax-collector",
            "12099",
            "property",
            "tax_collection",
        ),
        (
            "us-fl-palm-beach-tax-deeds",
            "12099",
            "property",
            "tax_deed_cases_and_sales",
        ),
        (
            "us-md-mdp-cama-downloads",
            "24",
            "property",
            "assessment_component_bulk_releases",
        ),
        (
            "us-md-mdp-parcel-downloads",
            "24",
            "property",
            "assessment_roll_bulk_representation",
        ),
        (
            "us-md-mdp-property-sales-downloads",
            "24",
            "property",
            "residential_sales_analytic_bulk",
        ),
        (
            "us-or-marion-comprehensive-assessment-download",
            "41047",
            "property",
            "assessment_roll",
        ),
        (
            "us-wa-mason-county-tax-parcels-gis",
            "53045",
            "property",
            "assessment_roll",
        ),
        (
            "us-wa-mason-county-tax-parcels-gis",
            "53045",
            "property",
            "parcel_geometry",
        ),
    }
    source_ids = sorted({row[0] for row in expected})
    placeholders = ",".join("?" for _ in source_ids)
    db = sqlite3.connect(db_path)
    rows = db.execute(
        f"""
        SELECT a.source_id, j.geoid, t.domain, t.role
        FROM source_census_target_sources a
        JOIN source_census_targets t USING(census_target_id)
        JOIN jurisdictions j USING(jurisdiction_id)
        WHERE a.source_id IN ({placeholders})
        """,
        source_ids,
    ).fetchall()
    marion_land_record = db.execute(
        """
        SELECT a.source_id, j.geoid, t.domain, t.role
        FROM source_census_target_sources a
        JOIN source_census_targets t USING(census_target_id)
        JOIN jurisdictions j USING(jurisdiction_id)
        WHERE a.source_id='us-or-marion-clerk-recorded-documents'
        """
    ).fetchall()
    db.close()

    assert set(rows) == expected
    assert marion_land_record == [
        (
            "us-or-marion-clerk-recorded-documents",
            "41",
            "property",
            "land_records_index",
        )
    ]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda data: data["sources"][0].update(
                {"complementary_source_ids": ["us-missing-source"]}
            ),
            "references unknown source IDs",
        ),
        (
            lambda data: data["sources"][1].update(
                {"source_id": data["sources"][0]["source_id"]}
            ),
            "duplicate source_id",
        ),
        (
            lambda data: data["sources"][0]["access_review"].update(
                {"limits": ["not", "a", "mapping"]}
            ),
            "access_review.limits must be a mapping",
        ),
        (
            lambda data: data["sources"][0].update(
                {"complementary_source_ids": [data["sources"][0]["source_id"]]}
            ),
            "cannot complement themselves",
        ),
    ],
)
def test_seed_rejects_broken_source_relationships(
    tmp_path,
    mutate,
    message,
):
    config_path = tmp_path / "sources.yaml"
    _config(config_path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    mutate(data)
    config_path.write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        seed_catalog(
            db_path=tmp_path / "catalog.db",
            config_path=config_path,
        )


def test_acris_index_and_image_routes_share_document_identity():
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in config["sources"]}
    index = sources["us-nyc-acris"]
    images = sources["us-nyc-acris-images"]

    assert index["record_identity_source_id"] == index["source_id"]
    assert images["record_identity_source_id"] == index["source_id"]
    assert images["source_id"] in index["complementary_source_ids"]
    assert index["source_id"] in images["complementary_source_ids"]


def test_adapter_bootstrap_preserves_newer_catalog_review(tmp_path):
    config_path = tmp_path / "sources.yaml"
    db_path = tmp_path / "catalog.db"
    _config(config_path)
    seed_catalog(db_path=db_path, config_path=config_path)
    catalog = PublicRecordsCatalog(db_path)
    operator_review = catalog.evaluate_access(
        "us-nc-test-parcels",
        access_class="A",
        automation_disposition="allowed",
        reviewed_by="operator",
        review_basis="Current endpoint observation supersedes tracked bootstrap.",
    )

    returned = ensure_catalog_source(
        "us-nc-test-parcels",
        db_path=db_path,
        config_path=config_path,
    )

    latest = returned.show_source("us-nc-test-parcels")["latest_access_review"]
    assert latest["access_review_id"] == operator_review["access_review_id"]
    assert latest["review_basis"] == (
        "Current endpoint observation supersedes tracked bootstrap."
    )


def test_adapter_bootstrap_registers_only_requested_missing_source(tmp_path):
    config_path = tmp_path / "sources.yaml"
    db_path = tmp_path / "catalog.db"
    _config(config_path)

    catalog = ensure_catalog_source(
        "us-nc-test-parcels",
        db_path=db_path,
        config_path=config_path,
    )

    assert [row["source_id"] for row in catalog.list_sources()] == [
        "us-nc-test-parcels"
    ]
    assert catalog.require_machine_acquisition("us-nc-test-parcels")["allowed"]


def test_direct_cli_supports_standard_output_file(tmp_path):
    config_path = tmp_path / "sources.yaml"
    db_path = tmp_path / "catalog.db"
    output_path = tmp_path / "seed.json"
    _config(config_path)
    root = Path(__file__).resolve().parent.parent

    completed = subprocess.run(
        [
            sys.executable,
            "tools/seed_public_records_catalog.py",
            "--db",
            str(db_path),
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["sources_seen"] == 2
    assert "catalog seed: 2 sources" in completed.stdout


def test_miami_public_route_declares_canonical_identity_and_adapter_inputs():
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    public_source = sources["us-fl-miami-dade-official-records-public"]
    canonical_id = public_source["record_identity_source_id"]

    assert canonical_id == "us-fl-miami-dade-official-records"
    assert canonical_id in sources
    assert sources[canonical_id]["record_identity_source_id"] == canonical_id

    public_capabilities = {
        capability["name"]: capability["details"]
        for capability in public_source["capabilities"]
    }
    assert public_capabilities["hydrate_search_results"] == {
        "adapter_command": "hydrate-qs",
        "input_fields": ["issued_search_token"],
    }
    assert public_capabilities["fetch_financial_detail"]["input_fields"] == [
        "cfn_master_id",
        "document_type",
        "recording_date",
    ]

    canonical_capabilities = {
        (capability["name"] if isinstance(capability, dict) else capability): (
            capability.get("details", {}) if isinstance(capability, dict) else {}
        )
        for capability in sources[canonical_id]["capabilities"]
    }
    assert canonical_capabilities["search_parcels"] == {
        "adapter_command": "folio",
        "input_fields": ["native_parcel_id", "alternate_parcel_id"],
    }
    assert canonical_capabilities["search_folio"] == {
        "adapter_command": "folio",
        "input_fields": ["native_parcel_id"],
    }


def test_florida_acis_manifest_declares_appellate_scope_and_uuid_routes():
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    source = next(row for row in config["sources"] if row["source_id"] == "us-fl-acis")

    assert source["source_status"] == "active"
    assert source["jurisdiction_geoids"] == ["12"]
    assert source["access_class"] == "B"
    assert source["automation_disposition"] == "allowed"
    assert source["access_review"]["limits"]["maximum_page_size"] == 500
    assert source["access_review"]["limits"]["court_directory_page_size"] == (1000)
    assert source["probe_evidence"]["court_count"] == 7
    assert source["probe_evidence"]["trial_courts_in_scope"] is False
    assert source["probe_evidence"]["event_case_hearing_hydration_verified"] is True
    assert source["probe_evidence"]["pre_migration_completeness"] == ("not_claimed")
    assert "appellate_calendars" in source["roles"]
    assert {
        "court_resource_uuid",
        "case_instance_uuid",
        "docket_entry_uuid",
        "calendar_event_uuid",
        "calendar_hearing_order",
        "document_link_uuid",
        "publication_uuid",
    }.issubset(source["stable_keys"])

    capabilities = {
        row["name"]: row.get("details", {}) for row in source["capabilities"]
    }
    assert set(capabilities) == {
        "list_courts",
        "search_cases",
        "search_parties",
        "fetch_case",
        "fetch_parties",
        "list_docket_entries",
        "list_calendar_session_types",
        "search_appellate_calendars",
        "search_documents",
        "fetch_document",
        "search_publications",
        "fetch_publication",
        "probe_source",
    }
    assert capabilities["search_appellate_calendars"]["unified_route"] == (
        "query_state_courts.py calendar"
    )
    assert capabilities["fetch_document"]["input_fields"] == [
        "court_resource_uuid",
        "case_instance_uuid",
        "document_link_uuid",
    ]
    assert source["endpoints"]["courts_api"] == ("https://acis-api.flcourts.gov/courts")
    assert source["endpoints"]["calendar_events_api"] == (
        "https://acis-api.flcourts.gov/courts/cms/events"
    )
    calendar_association = next(
        association
        for association in source["census_associations"]
        if association["role"] == "appellate_calendars"
    )
    assert calendar_association["jurisdiction_geoid"] == "12"
    assert calendar_association["coverage"]["record_grain"] == (
        "published_calendar_event_with_case_hearings"
    )


def test_orleans_manifest_declares_verified_layer_and_identity_routes():
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    source = next(
        row
        for row in config["sources"]
        if row["source_id"] == "us-la-orleans-property-viewer"
    )

    assert source["jurisdiction_geoids"] == ["22071"]
    assert source["source_status"] == "active"
    assert source["authority"] == "Orleans Parish Assessor"
    assert source["operator"] == "City of New Orleans"
    assert source["official_url"] == "https://property.nola.gov/"
    assert source["update_cadence"] == "weekly"
    assert source["platform_family"] == ("official_arcgis_locator_and_mapserver")
    assert source["stable_keys"] == ["taxbillid", "parcelid", "parid"]
    assert source["endpoints"]["parcel_layer"].endswith("/MapServer/0")
    assert source["endpoints"]["parcel_query"].endswith("/MapServer/0/query")
    assert source["endpoints"]["deployed_viewer_parcel_layer"].endswith(
        "/dev/property3/MapServer/15"
    )
    assert source["endpoints"]["canonical_viewer_parcel_layer_mirror"].endswith(
        "/apps/property3/MapServer/15"
    )
    assert source["endpoints"]["property_viewer"] == ("https://property.nola.gov/")
    assert source["endpoints"]["composite_locator"].endswith(
        "/PropertyViewerCompositeLocator/GeocodeServer"
    )
    assert source["probe_evidence"] == {
        "layer_id": 0,
        "layer_name": "TaxParcelPublishing",
        "layer_description": (
            "City tax parcel publishing layer for public query and map interaction"
        ),
        "viewer_layer_id": 15,
        "viewer_layer_name": "Property Information [Parcels]",
        "deployed_viewer_service_path": "dev/property3",
        "canonical_viewer_service_mirror_path": "apps/property3",
        "geometry_type": "esriGeometryPolygon",
        "spatial_reference_wkid": 102100,
        "spatial_reference_latest_wkid": 3857,
        "maximum_page_size": 1000,
        "query_transport": "arcgis_get",
        "supports_pagination": True,
        "supports_order_by": True,
        "supports_geojson": True,
        "account_identity_field": "TAXBILLID",
        "parcel_join_fields": ["PARCELID", "PARID"],
        "parcelid_alias": "GeoPIN",
        "locator_roles": [
            "AddressPointLo",
            "ParcelOwnerLoc",
            "ParcelTaxbillL",
        ],
        "sentinel_geopin": "41026779",
        "sentinel_tax_bill_id": "104103301",
        "freshness_statistic": "max(LASTUPDATE)",
        "monitor_request_count": 4,
        "account_to_parcel_cardinality": ("many_accounts_can_share_geopin"),
    }

    capabilities = {row["name"]: row["details"] for row in source["capabilities"]}
    assert capabilities == {
        "search_owner": {
            "adapter_command": "owner",
            "input_fields": ["owner_name"],
        },
        "search_address": {
            "adapter_command": "address",
            "input_fields": ["address"],
        },
        "fetch_account": {
            "adapter_command": "account",
            "input_fields": ["tax_bill_id"],
        },
        "fetch_parcel": {
            "adapter_command": "parcel",
            "input_fields": ["parcel_id", "parid"],
        },
        "fetch_geometry": {
            "adapter_commands": ["account", "parcel"],
            "input_routes": {
                "tax_bill_id": "account",
                "parcel_id": "parcel",
                "parid": "parcel",
            },
            "input_fields": ["tax_bill_id", "parcel_id", "parid"],
        },
        "search_assessment_records": {
            "adapter_command": "search",
            "input_fields": ["query"],
        },
        "assessment_value": {
            "source_fields": [
                "LNDVALUE",
                "PRVASSDVAL",
                "CNTASSDVAL",
                "ASSDVALYRCG",
                "ASSDPCNTCG",
                "PRVTXBLVAL",
                "CNTTXBLVAL",
                "TXBLVALYRCHG",
                "TXBLPCNTCHG",
            ]
        },
        "source_update": {"source_field": "LASTUPDATE"},
    }
    assert "playwright" not in json.dumps(source).lower()


def test_bexar_court_manifests_preserve_route_and_custodian_boundaries(
    tmp_path,
):
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    historical = sources["us-tx-bexar-district-historical-cases"]
    portal = sources["us-tx-bexar-justice-portal"]
    district_request = sources["us-tx-bexar-district-clerk-records-request"]
    county_request = sources["us-tx-bexar-county-clerk-records-request"]

    assert historical["source_status"] == "active"
    assert historical["authority"] == "Bexar County District Clerk"
    assert historical["jurisdiction_geoids"] == ["48029"]
    assert historical["authentication"] == "anonymous_public_session"
    assert historical["platform_family"] == ("kofile_neumo_publicsearch_ws")
    assert historical["adapter_family"] == ("kofile_neumo_publicsearch_ws")
    assert historical["stable_keys"] == [
        "department_code",
        "doc_id",
        "rs_id",
        "image_id",
        "page_number",
    ]
    assert historical["probe_evidence"]["indexed_record_count"] == 13_965
    assert historical["probe_evidence"]["minimum_source_date_value"] == ("1/1/1800")
    assert (
        historical["probe_evidence"]["minimum_source_date_semantics"]
        == "unknown_date_sentinel"
    )
    assert historical["probe_evidence"]["verified_latest_index_date"] == ("1919-09-17")
    assert historical["probe_evidence"]["pagination"] == "offset"
    assert historical["probe_evidence"]["docket_synthesis_available"] is False
    assert historical["endpoints"]["websocket"].startswith("wss://")
    assert historical["endpoints"]["case_detail_template"].endswith("?department=HC")
    historical_capabilities = {
        row["name"]: row["details"] for row in historical["capabilities"]
    }
    assert {
        name: historical_capabilities[name]["adapter_command"]
        for name in (
            "search_cases",
            "search_documents",
            "fetch_case",
            "fetch_document",
            "probe_source",
        )
    } == {
        "search_cases": "search",
        "search_documents": "search",
        "fetch_case": "case",
        "fetch_document": "page",
        "probe_source": "probe",
    }
    assert historical_capabilities["search_cases"]["input_fields"] == [
        "query",
        "date_from",
        "date_to",
        "limit",
        "offset",
        "workspace_id",
    ]
    assert historical_capabilities["search_documents"]["fixed_options"] == {
        "ocr": True,
    }
    assert historical_capabilities["search_documents"]["input_fields"] == [
        "query",
        "date_from",
        "date_to",
        "limit",
        "offset",
        "workspace_id",
    ]
    assert (
        historical_capabilities["fetch_document"]["retrieval_granularity"]
        == "page_image"
    )
    historical_limits = historical["access_review"]["limits"]
    assert historical_limits == {
        "pagination": "offset",
        "require_complete_pagination": True,
    }

    assert portal["source_status"] == "candidate"
    assert portal["platform_family"] == ("tyler_odyssey_interactive_portal")
    assert portal["probe_evidence"]["ui_result_ceiling"] == 200
    assert portal["probe_evidence"]["captcha_observed"] is True
    assert portal["probe_evidence"]["document_images_available"] is False
    portal_capabilities = {row["name"] for row in portal["capabilities"]}
    assert portal_capabilities == {
        "search_cases",
        "fetch_case",
        "search_hearings",
    }
    assert "fetch_document" not in portal_capabilities
    assert set(historical["complementary_source_ids"]) == {
        portal["source_id"],
        district_request["source_id"],
    }
    assert set(portal["complementary_source_ids"]) == {
        historical["source_id"],
        district_request["source_id"],
        county_request["source_id"],
    }

    assert district_request["access_class"] == "E"
    assert county_request["access_class"] == "E"
    assert district_request["authority"] == "Bexar County District Clerk"
    assert county_request["authority"] == "Bexar County Clerk"
    assert district_request["probe_evidence"]["covered_records"] == [
        "civil_district_court_records",
        "criminal_felony_court_records",
    ]
    assert county_request["probe_evidence"]["covered_records"] == [
        "county_court_at_law_records",
        "misdemeanor_records",
        "probate_records",
    ]
    assert portal["source_id"] in district_request["complementary_source_ids"]
    assert portal["source_id"] in county_request["complementary_source_ids"]

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    assert (
        catalog.require_machine_acquisition(historical["source_id"])["allowed"] is True
    )
    assert catalog.machine_acquisition_decision(portal["source_id"])["allowed"] is False
    assert (
        catalog.machine_acquisition_decision(district_request["source_id"])["allowed"]
        is False
    )
    assert (
        catalog.machine_acquisition_decision(county_request["source_id"])["allowed"]
        is False
    )


def test_vicourts_manifest_preserves_ctrack_and_legacy_identities():
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    source = next(
        row for row in config["sources"] if row["source_id"] == "us-vi-c-track"
    )

    assert source["source_status"] == "active"
    assert source["jurisdiction_geoids"] == ["78"]
    assert source["authority"] == "Judicial Branch of the Virgin Islands"
    assert source["adapter_family"] == ("ctrack_public_api_and_vicourts_displayfile")
    assert {
        "court_resource_uuid",
        "case_instance_uuid",
        "docket_entry_uuid",
        "claim_uuid_or_sequence",
        "document_link_uuid",
        "publication_uuid",
        "legacy_item_id",
    }.issubset(source["stable_keys"])
    assert source["probe_evidence"]["court_count"] == 2
    assert source["probe_evidence"]["maximum_page_size"] == 500
    assert source["probe_evidence"]["search_result_source_ceiling"] == 10_000
    assert source["probe_evidence"]["probate_case_sentinel"] == ("ST-2019-PB-00080")
    assert source["probe_evidence"]["probate_case_sentinel_docket_entries"] == 452
    assert source["probe_evidence"]["claim_creditor_name_or_amount_verified"] is False
    assert source["probe_evidence"]["legacy_item_ids_verified"] == [
        16911884,
        16911886,
        17104534,
        17035342,
    ]
    assert source["probe_evidence"]["cross_backend_identity"] == (
        "downloaded_pdf_sha256_only"
    )

    capabilities = {
        row["name"]: row.get("details", {}) for row in source["capabilities"]
    }
    assert set(capabilities) == {
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
        "probe_source",
    }
    assert capabilities["list_probate_claims"] == {
        "adapter_command": "claims",
        "input_fields": ["case_number", "court", "cursor"],
        "result_scope": "limited_claim_header_stubs",
    }
    assert capabilities["fetch_document"]["input_fields"] == [
        "court",
        "case_uuid",
        "document_uuid",
    ]
    assert source["endpoints"]["manage_info"].endswith("/manage/info")
    assert source["endpoints"]["legacy_file"].endswith("DisplayFile.aspx")


def test_orange_county_case_portal_manifest_preserves_interactive_route(
    tmp_path,
):
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    source = next(
        row
        for row in config["sources"]
        if row["source_id"] == "us-fl-orange-clerk-my-eclerk"
    )

    assert source["source_status"] == "active"
    assert source["jurisdiction_geoids"] == ["12095"]
    assert source["adapter_family"] == "human_action"
    assert source["probe_evidence"]["ui_result_ceiling"] == 500
    assert source["probe_evidence"]["captcha_observed_for_anonymous_search"] is True
    assert source["probe_evidence"]["docket_coverage_statement"] == (
        "approximately_1990_to_present_for_most_cases"
    )
    assert source["probe_evidence"]["document_coverage_statement"] == (
        "2009_to_present_for_most_case_types"
    )
    assert {
        "raw_case_number",
        "source_case_id",
        "document_identification_number",
    }.issubset(source["stable_keys"])
    assert source["record_identity_source_id"] == source["source_id"]
    assert set(source["complementary_source_ids"]) >= {
        "us-fl-orange-county-hearing-calendar",
        "us-fl-acis",
        "us-fl-ninth-circuit-division-calendars",
        "us-fl-orange-clerk-records-request",
        "us-fl-orange-official-records",
        "us-fl-appellate-opinions-search",
    }

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    decision = PublicRecordsCatalog(catalog_path).machine_acquisition_decision(
        source["source_id"]
    )
    assert decision["allowed"] is False
    assert decision["automation_disposition"] == "unclear"


def test_orange_county_hearing_calendar_is_a_distinct_machine_route(
    tmp_path,
):
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    source = next(
        row
        for row in config["sources"]
        if row["source_id"] == "us-fl-orange-county-hearing-calendar"
    )

    assert source["source_status"] == "active"
    assert source["jurisdiction_geoids"] == ["12095"]
    assert source["adapter_family"] == "orange_county_myeclerk_calendar"
    assert source["coverage_start"] == "current_and_future_hearings_only"
    assert source["probe_evidence"]["live_reported_rows"] == 1285
    assert source["probe_evidence"]["live_parsed_rows"] == 1285
    assert source["probe_evidence"]["client_side_pagination"] is True
    assert source["probe_evidence"]["server_side_ceiling_observed"] is False
    assert source["probe_evidence"]["past_hearings_available"] is False
    assert source["record_identity_source_id"] == ("us-fl-orange-clerk-my-eclerk")
    assert set(source["complementary_source_ids"]) >= {
        "us-fl-orange-clerk-my-eclerk",
        "us-fl-acis",
        "us-fl-ninth-circuit-division-calendars",
    }

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    decision = PublicRecordsCatalog(catalog_path).machine_acquisition_decision(
        source["source_id"]
    )
    assert decision["allowed"] is True
    assert decision["access_class"] == "B"


def test_pima_agave_manifest_preserves_session_bound_public_route(tmp_path):
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    source = next(
        row
        for row in config["sources"]
        if row["source_id"] == "us-az-pima-superior-agave"
    )

    assert source["source_status"] == "active"
    assert source["jurisdiction_geoids"] == ["04019"]
    assert source["adapter_family"] == "pima_agave_aspnet_publicdocs"
    assert source["probe_evidence"]["anonymous_public_search_verified"] is True
    assert source["probe_evidence"]["public_pdf_signature_verified"] is True
    assert source["probe_evidence"]["session_bound_route_tokens"] is True
    assert source["probe_evidence"]["emitted_route_tokens"] is False
    assert source["stable_keys"] == [
        "raw_case_number",
        "source_internal_id",
        "native_entry_id",
    ]

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    decision = PublicRecordsCatalog(catalog_path).machine_acquisition_decision(
        source["source_id"]
    )
    assert decision["allowed"] is True
    assert decision["access_class"] == "B"


def test_palm_beach_machine_product_request_and_recorder_routes_are_distinct(
    tmp_path,
):
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in config["sources"]}
    ecaseview = sources["us-fl-palm-beach-ecaseview"]
    clerkcart = sources["us-fl-palm-beach-clerkcart"]
    records = sources["us-fl-palm-beach-records-service"]
    official_records = sources["us-fl-palm-beach-official-records"]

    assert ecaseview["jurisdiction_geoids"] == ["12099"]
    assert ecaseview["stable_keys"] == ["raw_case_number", "din"]
    assert ecaseview["probe_evidence"]["source_result_ceiling"] == 200
    assert ecaseview["probe_evidence"]["public_pdf_signature_verified"] is True
    assert ecaseview["adapter_family"] == "palm_beach_ecaseview_browser"
    assert clerkcart["access_class"] == "D"
    assert clerkcart["probe_evidence"]["delivery_formats"] == ["pdf", "excel"]
    assert records["access_class"] == "E"
    assert records["adapter_family"] == "human_action"
    assert official_records["domain"] == "property"
    assert official_records["coverage_start"] == ("online_document_images_since_1968")
    assert ecaseview["record_identity_source_id"] == ecaseview["source_id"]
    assert clerkcart["record_identity_source_id"] == ecaseview["source_id"]
    assert records["record_identity_source_id"] == ecaseview["source_id"]
    assert set(ecaseview["complementary_source_ids"]) == {
        clerkcart["source_id"],
        records["source_id"],
        official_records["source_id"],
        "us-fl-acis",
    }
    assert (
        official_records["record_identity_source_id"] == (official_records["source_id"])
    )
    assert ecaseview["source_id"] in official_records["complementary_source_ids"]

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    assert (
        catalog.machine_acquisition_decision("us-fl-palm-beach-ecaseview")["allowed"]
        is True
    )
    for source_id in (
        "us-fl-palm-beach-clerkcart",
        "us-fl-palm-beach-records-service",
    ):
        assert catalog.machine_acquisition_decision(source_id)["allowed"] is False
    recorder_decision = catalog.machine_acquisition_decision(
        "us-fl-palm-beach-official-records"
    )
    assert recorder_decision["allowed"] is True
    assert recorder_decision["limits"]["exact_routes"] == [
        "instrument_number",
        "book_page",
        "document_detail",
        "document_image",
    ]
    assert recorder_decision["limits"]["broad_discovery_recaptcha_observed"] is True


def test_texas_assignment_sources_keep_index_bulk_and_request_routes_distinct(
    tmp_path,
):
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in config["sources"]}
    reeves = sources["us-tx-reeves-county-clerk-official-records"]
    culberson_history = sources["us-tx-culberson-clerk-historical-deeds"]
    culberson_request = sources["us-tx-culberson-clerk-records-request"]
    ucc_portal = sources["us-tx-sos-ucc-portal"]
    ucc_bulk = sources["us-tx-sos-ucc-bulk"]
    p4 = sources["us-tx-rrc-p4-bulk"]
    p5 = sources["us-tx-rrc-p5-bulk"]
    wellbore = sources["us-tx-rrc-wellbore-bulk"]

    assert reeves["jurisdiction_geoids"] == ["48389"]
    assert reeves["adapter_family"] == ("kofile_neumo_publicsearch_ws")
    assert reeves["probe_evidence"]["probe_document_id"] == 20798096
    assert reeves["probe_evidence"]["ephemeral_page_urls_emitted"] is False
    assert culberson_history["coverage_end"] == "2009"
    assert culberson_request["access_class"] == "E"
    assert ucc_portal["access_class"] == "D"
    assert ucc_bulk["update_cadence"] == ("monthly_master_and_daily_updates")
    assert p4["probe_evidence"]["record_length_bytes"] == 92
    assert p4["adapter_family"] == "texas_rrc_bulk"
    assert p4["source_status"] == "active"
    assert p4["probe_evidence"]["observed_record_count"] == 30303110
    assert p5["probe_evidence"]["join_key"] == "p5_number"
    assert p5["adapter_family"] == "texas_rrc_bulk"
    assert p5["probe_evidence"]["ebcdic_record_length_bytes"] == 350
    assert wellbore["probe_evidence"]["role_in_p4_pipeline"] == (
        "lease_well_location_resolution"
    )
    assert wellbore["adapter_family"] == "texas_rrc_bulk"
    assert wellbore["probe_evidence"]["column_count"] == 59
    assert wellbore["probe_evidence"]["observed_record_count"] == 1368247
    assert (
        wellbore["probe_evidence"][
            "observed_physical_line_count_including_report_footer"
        ]
        == 1368263
    )
    assert wellbore["probe_evidence"]["byte_range_request_status"] == 200
    assert set(reeves["complementary_source_ids"]) >= {
        "us-tx-reeves-clerk-bulk-images",
        "us-tx-sos-ucc-portal",
        "us-tx-rrc-p4-bulk",
    }
    assert set(ucc_portal["complementary_source_ids"]) >= {
        "us-tx-sos-ucc-bulk",
        "us-tx-reeves-county-clerk-official-records",
        "us-tx-culberson-clerk-records-request",
        "us-tx-rrc-p4-bulk",
    }
    assert set(p4["complementary_source_ids"]) >= {
        "us-tx-rrc-p5-bulk",
        "us-tx-rrc-wellbore-bulk",
        "us-tx-reeves-county-clerk-official-records",
        "us-tx-culberson-clerk-records-request",
        "us-tx-sos-ucc-portal",
    }

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    assert catalog.machine_acquisition_decision(reeves["source_id"])["allowed"] is True
    for source_id in (
        culberson_history["source_id"],
        culberson_request["source_id"],
        ucc_portal["source_id"],
        ucc_bulk["source_id"],
    ):
        assert catalog.machine_acquisition_decision(source_id)["allowed"] is False
    for source_id in (
        p4["source_id"],
        p5["source_id"],
        wellbore["source_id"],
    ):
        assert catalog.machine_acquisition_decision(source_id)["allowed"] is True


def test_wisconsin_case_publication_archive_and_subscription_routes_remain_distinct(
    tmp_path,
):
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in config["sources"]}
    circuit = sources["us-wi-wcca-public"]
    appellate = sources["us-wi-wscca-public"]
    opinions = sources["us-wi-court-opinions"]
    library_briefs = sources["us-wi-state-law-library-briefs"]
    historical_briefs = sources["us-wi-uw-law-historical-briefs"]
    clerk = sources["us-wi-appellate-clerk"]
    subscription = sources["us-wi-wcca-rest"]

    assert circuit["jurisdiction_geoids"] == ["55"]
    assert appellate["jurisdiction_geoids"] == ["55"]
    assert opinions["jurisdiction_geoids"] == ["55"]
    assert circuit["stable_keys"] == ["county", "raw_case_number"]
    assert "native_document_id" in appellate["stable_keys"]
    assert "native_document_id" in opinions["stable_keys"]
    assert circuit["probe_evidence"]["appellate_cases_in_scope"] is False
    assert appellate["probe_evidence"]["circuit_cases_in_scope"] is False
    assert (
        appellate["probe_evidence"]["general_case_coverage_statement"]
        == "open_appeals_from_end_of_1993_forward"
    )
    assert subscription["adapter_family"] == "licensed_court_feed"
    assert circuit["adapter_family"] == "human_action"
    assert appellate["adapter_family"] == "wisconsin_wscca_browser_and_rss"
    assert opinions["adapter_family"] == "wisconsin_appellate_publications"
    assert circuit["record_identity_source_id"] == circuit["source_id"]
    assert subscription["record_identity_source_id"] == circuit["source_id"]
    assert appellate["record_identity_source_id"] == appellate["source_id"]
    assert opinions["record_identity_source_id"] == opinions["source_id"]
    assert opinions["source_id"] in appellate["complementary_source_ids"]
    assert appellate["source_id"] in opinions["complementary_source_ids"]
    assert library_briefs["source_id"] in appellate["complementary_source_ids"]
    assert historical_briefs["source_id"] in appellate["complementary_source_ids"]
    assert clerk["source_id"] in appellate["complementary_source_ids"]
    assert set(circuit["complementary_source_ids"]) >= {
        appellate["source_id"],
        subscription["source_id"],
    }
    assert set(subscription["complementary_source_ids"]) == {
        circuit["source_id"],
        appellate["source_id"],
    }

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    for source_id in ("us-wi-wcca-public", "us-wi-wcca-rest"):
        assert catalog.machine_acquisition_decision(source_id)["allowed"] is False
    for source_id in ("us-wi-wscca-public", "us-wi-court-opinions"):
        assert catalog.machine_acquisition_decision(source_id)["allowed"] is True


def test_los_angeles_probate_property_and_complementary_routes_are_distinct(
    tmp_path,
):
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in config["sources"]}
    route_ids = {
        "us-ca-los-angeles-superior-probate",
        "us-ca-los-angeles-superior-probate-name-index",
        "us-ca-los-angeles-superior-probate-document-images",
        "us-ca-los-angeles-superior-probate-records",
        "us-ca-second-district-appellate-case-information",
        "us-ca-judicial-branch-opinions",
        "us-ca-los-angeles-county-assessor-parcels",
        "us-ca-los-angeles-registrar-recorder-real-estate",
        "us-ca-public-notices",
    }
    assert route_ids <= sources.keys()

    identity_source_id = "us-ca-los-angeles-superior-probate"
    for source_id in (
        identity_source_id,
        "us-ca-los-angeles-superior-probate-name-index",
        "us-ca-los-angeles-superior-probate-document-images",
        "us-ca-los-angeles-superior-probate-records",
    ):
        assert sources[source_id]["record_identity_source_id"] == (identity_source_id)

    core = sources[identity_source_id]
    core_capabilities = {
        capability["name"]: capability["details"] for capability in core["capabilities"]
    }
    assert core["adapter_family"] == "lasc_probate_online_services"
    assert core["access_class"] == "B"
    assert core["automation_disposition"] == "allowed"
    assert core_capabilities["fetch_case"]["adapter_command"] == "case"
    note_capability = core_capabilities["list_probate_notes"]
    assert note_capability["adapter_command"] == "notes"
    assert note_capability["input_fields"] == [
        "raw_case_number",
        "view",
        "offset",
        "limit",
    ]
    assert note_capability["views"] == ["future", "past", "all"]
    assert {
        "summary_text",
        "facts_text",
        "matters_to_clear",
        "relief_text",
        "findings_and_order_text",
        "probate_examiner_comments",
        "recommended_disposition",
    } <= set(note_capability["output_fields"])
    assert core_capabilities["search_hearings"]["adapter_command"] == ("calendar")
    assert core["probe_evidence"]["case_summary_is_official_record"] is False
    assert (
        core["access_review"]["limits"]["probate_notes_source_window"]
        == "typically_two_weeks_before_through_60_days_after_hearing"
    )
    assert set(core["complementary_source_ids"]) >= {
        "us-ca-los-angeles-superior-probate-name-index",
        "us-ca-los-angeles-superior-probate-document-images",
        "us-ca-los-angeles-superior-probate-records",
        "us-ca-second-district-appellate-case-information",
        "us-ca-judicial-branch-opinions",
        "us-ca-public-notices",
    }

    name_index = sources["us-ca-los-angeles-superior-probate-name-index"]
    images = sources["us-ca-los-angeles-superior-probate-document-images"]
    archives = sources["us-ca-los-angeles-superior-probate-records"]
    appellate = sources["us-ca-second-district-appellate-case-information"]
    opinions = sources["us-ca-judicial-branch-opinions"]
    assessor = sources["us-ca-los-angeles-county-assessor-parcels"]
    recorder = sources["us-ca-los-angeles-registrar-recorder-real-estate"]
    notices = sources["us-ca-public-notices"]

    assert name_index["coverage_start"] == "1983"
    assert name_index["probe_evidence"]["no_result_is_charged"] is True
    assert images["probe_evidence"]["probate_preview_available"] is False
    assert images["probe_evidence"]["probate_paperless_boundary"] == ("2013-02-27")
    assert archives["probe_evidence"]["pre_1983_name_discovery_route"] == ("archives")
    assert appellate["probe_evidence"]["district_two_pre_1996_gaps"] == [
        "docket_entries",
        "briefing_summaries",
        "scheduled_actions",
    ]
    assert opinions["coverage_start"] == (
        "rolling_published_120_days_and_unpublished_60_days"
    )
    assert "official_reports" not in opinions["roles"]
    official_reports = next(
        complement
        for complement in opinions["official_complements"]
        if complement["name"] == "California Official Reports Opinions"
    )
    assert official_reports["coverage"] == "1850-present"
    assert official_reports["integrated_by_current_feed_adapter"] is False
    assert assessor["probe_evidence"]["maximum_page_size"] == 1000
    assert assessor["probe_evidence"]["supports_pagination"] is True
    assert recorder["probe_evidence"]["online_public_index_search"] is False
    assert recorder["probe_evidence"]["street_address_search"] is False
    assert notices["probe_evidence"]["archive_window"] == "three_years"

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    assert catalog.machine_acquisition_decision(identity_source_id)["allowed"] is True
    assert (
        catalog.machine_acquisition_decision(assessor["source_id"])["allowed"] is True
    )
    for source_id in (
        name_index["source_id"],
        images["source_id"],
        archives["source_id"],
        recorder["source_id"],
    ):
        assert catalog.machine_acquisition_decision(source_id)["allowed"] is False


def test_los_angeles_ttc_property_components_are_queryable_and_census_linked(
    tmp_path,
):
    from tools import query_los_angeles_ttc as la_ttc

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    source_ids = {
        la_ttc.ASSESSOR_SOURCE_ID,
        la_ttc.PAYMENT_SOURCE_ID,
        la_ttc.SALE_SOURCE_ID,
    }
    assert source_ids <= sources.keys()

    assessor = sources[la_ttc.ASSESSOR_SOURCE_ID]
    payment = sources[la_ttc.PAYMENT_SOURCE_ID]
    sale = sources[la_ttc.SALE_SOURCE_ID]
    assert assessor["record_identity_source_id"] == la_ttc.ASSESSOR_SOURCE_ID
    assert {
        la_ttc.PAYMENT_SOURCE_ID,
        la_ttc.SALE_SOURCE_ID,
    } <= set(assessor["complementary_source_ids"])
    assert payment["adapter_family"] == "los_angeles_ttc_property"
    assert sale["adapter_family"] == "los_angeles_ttc_property"
    assert payment["automation_disposition"] == "allowed"
    assert sale["automation_disposition"] == "allowed"
    assert (
        payment["probe_evidence"]["exhaustive_when_caller_page_bound_omitted"] is True
    )
    assert sale["probe_evidence"]["sale_result_pdf_signature_verified"] is True
    assert {item["kind"] for item in payment["official_complements"]} == {
        "current_annual_secured_tax_bill",
        "duplicate_bill_request",
        "multiple_parcel_tax_information_request",
    }
    assert {
        association["role"]
        for source in (assessor, payment, sale)
        for association in source["census_associations"]
    } == {"assessment_roll", "tax_collection"}

    catalog_path = tmp_path / "catalog.db"
    seeded = seed_catalog(db_path=catalog_path)
    assert seeded["sources_seen"] == len(config["sources"])
    catalog = PublicRecordsCatalog(catalog_path)
    assert all(
        catalog.machine_acquisition_decision(source_id)["allowed"]
        for source_id in source_ids
    )
    census = PublicRecordsCensus(catalog_path)
    assessment = census.list_targets(
        state="CA",
        domain="property",
        role="assessment_roll",
    )[0]
    collection = census.list_targets(
        state="CA",
        domain="property",
        role="tax_collection",
    )[0]
    assert la_ttc.ASSESSOR_SOURCE_ID in assessment["source_ids"]
    assert {
        la_ttc.PAYMENT_SOURCE_ID,
        la_ttc.SALE_SOURCE_ID,
    } <= set(collection["source_ids"])


def test_texas_tames_manifest_preserves_live_source_contract(tmp_path):
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    tames = sources["us-tx-appellate-tames"]
    capabilities = {
        capability["name"]: capability["details"]
        for capability in tames["capabilities"]
    }

    assert tames["source_status"] == "active"
    assert tames["jurisdiction_geoids"] == ["48"]
    assert tames["platform_family"] == "tames_webforms"
    assert tames["adapter_family"] == "texas_tames_webforms"
    assert tames["authentication"] == "none"
    assert set(tames["stable_keys"]) == {
        "court_code",
        "raw_case_number",
        "native_entry_id",
        "media_version_id",
        "native_relation_id",
    }
    assert set(capabilities) == {
        "search_cases",
        "fetch_case",
        "fetch_parties",
        "list_docket_entries",
        "list_case_events",
        "list_docket_documents",
        "fetch_document",
        "probe_source",
    }
    assert capabilities["search_cases"]["adapter_command"] == "search"
    assert {
        "scope",
        "date_from",
        "date_to",
        "courts",
        "county",
        "trial_court",
        "limit",
        "cursor",
    } <= set(capabilities["search_cases"]["input_fields"])
    assert capabilities["fetch_document"]["adapter_command"] == "download"
    assert tames["probe_evidence"]["court_count"] == 17
    assert tames["probe_evidence"]["source_result_ceiling"] == 1000
    assert tames["probe_evidence"]["originating_trial_case_relation_verified"] is True
    assert tames["access_review"]["limits"] == {
        "source_result_ceiling": 1000,
        "preserve_source_overflow_state": True,
        "minimum_interval_seconds": 0.25,
        "refresh": "nightly",
    }

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    decision = PublicRecordsCatalog(catalog_path).machine_acquisition_decision(
        tames["source_id"]
    )
    assert decision["allowed"] is True
    assert decision["automation_disposition"] == "allowed_with_limits"


def test_texas_account_and_local_manifests_keep_routes_distinct():
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    researchtx = sources["us-tx-researchtx"]
    research_capabilities = {
        capability["name"] for capability in researchtx["capabilities"]
    }

    assert researchtx["source_status"] == "active"
    assert researchtx["access_class"] == "C"
    assert researchtx["automation_disposition"] == "not_applicable"
    assert researchtx["authentication"] == "efiletexas_account"
    assert {
        "search_cases",
        "search_parties",
        "search_documents",
        "search_hearings",
        "fetch_case",
        "fetch_parties",
        "list_docket_entries",
        "list_case_events",
        "list_docket_documents",
        "fetch_document",
        "export_search_results",
        "purchase_document",
    } <= research_capabilities
    assert (
        researchtx["probe_evidence"]["public_api_documented_in_reviewed_materials"]
        is False
    )

    travis_portal = sources["us-tx-travis-odyssey-courts"]
    travis_request = sources["us-tx-travis-district-clerk-records-request"]
    assert travis_request["record_identity_source_id"] == (travis_portal["source_id"])
    assert travis_portal["probe_evidence"]["family_and_civil_coverage_start"] == 2006
    assert travis_portal["probe_evidence"]["criminal_coverage_start"] == 2008
    assert {
        capability if isinstance(capability, str) else capability["name"]
        for capability in travis_request["capabilities"]
    } >= {
        "request_case_copy",
        "request_certified_copy",
        "request_authenticated_copy",
        "request_court_data",
        "request_subscription",
    }

    hays_portal = sources["us-tx-hays-district-court-portal"]
    hays_request = sources["us-tx-hays-district-clerk-records-request"]
    assert hays_request["record_identity_source_id"] == (hays_portal["source_id"])
    assert {capability["name"] for capability in hays_portal["capabilities"]} == {
        "search_cases",
        "fetch_case",
    }
    assert "docket" not in json.dumps(hays_portal["capabilities"]).lower()
    assert "document" not in json.dumps(hays_portal["capabilities"]).lower()
    hays_county = sources["us-tx-hays-county-clerk-courts"]
    county_capabilities = {
        capability["name"]: capability["details"]
        for capability in hays_county["capabilities"]
    }
    assert {"search_cases", "fetch_case", "search_hearings"} <= set(county_capabilities)
    assert county_capabilities["search_cases"]["record_collections"] == [
        "criminal_case_records",
        "civil_family_probate_case_records",
    ]
    assert (
        hays_county["probe_evidence"]["family_and_divorce_custodian_note"]
        == "district_clerk"
    )


def test_texas_complementary_sources_preserve_record_kinds():
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}

    for source_id in (
        "us-tx-appellate-released-orders-opinions",
        "us-tx-supreme-orders-opinions",
    ):
        assert sources[source_id]["record_identity_source_id"] == (
            "us-tx-appellate-tames"
        )

    notices = sources["us-tx-oca-citations-notices"]
    notice_capabilities = {
        capability["name"]: capability["details"]
        for capability in notices["capabilities"]
    }
    assert {"search_cases", "search_documents", "fetch_document"} <= set(
        notice_capabilities
    )
    assert notice_capabilities["search_notices"]["input_fields"] == [
        "name",
        "cause_number",
        "court",
        "county",
        "status",
        "text",
    ]

    vexatious = sources["us-tx-oca-vexatious-litigants"]
    assert {capability["name"] for capability in vexatious["capabilities"]} >= {
        "search_parties",
        "search_cases",
        "fetch_document",
        "sync",
    }
    assert vexatious["probe_evidence"]["xlsx_download_present"] is True

    activity = sources["us-tx-oca-court-activity"]
    supplements = sources["us-tx-oca-statistical-supplements"]
    assert "aggregate_case_activity" in activity["roles"]
    assert "downloadable_data_files" in supplements["roles"]
    assert "search_cases" not in {
        capability["name"] for capability in activity["capabilities"]
    }
    assert "search_cases" not in {
        capability["name"] for capability in supplements["capabilities"]
    }


def test_san_mateo_routes_preserve_index_and_complement_boundaries():
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    midx = sources["us-ca-san-mateo-midx"]

    assert midx["source_status"] == "active"
    assert midx["automation_disposition"] == "allowed"
    assert midx["probe_evidence"]["native_page_size"] == 15
    assert midx["probe_evidence"]["native_result_ceiling_observed"] is False
    assert set(midx["complementary_source_ids"]) >= {
        "us-ca-san-mateo-odyssey",
        "us-ca-san-mateo-hearings-rulings",
        "us-ca-san-mateo-records",
        "us-ca-first-district-appellate-case-information",
    }
    for source_id in (
        "us-ca-san-mateo-odyssey",
        "us-ca-san-mateo-hearings-rulings",
        "us-ca-san-mateo-records",
    ):
        assert sources[source_id]["record_identity_source_id"] == midx["source_id"]


def test_tax_court_dawson_and_complements_keep_native_contracts():
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    dawson = sources["us-tax-court-dawson"]

    assert dawson["source_status"] == "active"
    assert dawson["automation_disposition"] == "allowed"
    assert set(dawson["complementary_source_ids"]) == {
        "us-tax-court-reports",
        "us-tax-court-records-transcripts",
        "us-govinfo-uscourts",
        "us-courtlistener-api",
    }
    assert dawson["access_review"]["limits"]["case_search_result_ceiling"] == 5000
    assert dawson["access_review"]["limits"]["today_opinions_result_ceiling"] == 200
    assert dawson["probe_evidence"]["public_order_pdf_docket"] == "455-22"
    assert (
        dawson["probe_evidence"]["public_order_pdf_docket_entry_id"]
        == "8fbd790c-3af0-43fb-9059-9754310faa24"
    )
    assert (
        sources["us-tax-court-records-transcripts"]["record_identity_source_id"]
        == dawson["source_id"]
    )


def test_new_york_alternative_routes_keep_discovery_roles_distinct():
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    nyscef = sources["us-ny-nyscef"]
    reports = sources["us-ny-law-reporting-bureau"]
    notices = sources["us-ny-public-notices-column"]

    assert set(nyscef["complementary_source_ids"]) >= {
        "us-ny-law-reporting-bureau",
        "us-ny-webcivil-supreme",
        "us-ny-court-pass",
        "us-ny-court-appeals-archives",
        "us-ny-county-clerk-court-records",
        "us-ny-public-notices-column",
        "us-ny-trellis",
        "us-ny-courtlink",
        "us-ny-elaw",
    }
    assert nyscef["adapter_family"] == ("nyscef_handoff_and_local_fulltext")
    nyscef_capabilities = {
        capability["name"]: capability["details"]
        for capability in nyscef["capabilities"]
    }
    assert (
        nyscef_capabilities["normalize_document_manifest"]["adapter_command"]
        == "normalize"
    )
    assert nyscef_capabilities["extract_filing_text"]["methods"] == [
        "pdftotext_layout",
        "targeted_tesseract_ocr",
    ]
    assert nyscef_capabilities["build_fulltext_index"]["storage"] == (
        "portable_sqlite_fts5"
    )
    assert nyscef_capabilities["search_filing_text"]["mention_classes"] == [
        "listed_party",
        "non_party_candidate",
        "party_list_unavailable",
    ]
    assert nyscef["probe_evidence"]["local_fulltext_processor"] is True
    assert nyscef["probe_evidence"]["incremental_versions_preserved"] is True
    assert reports["source_status"] == "active"
    assert reports["automation_disposition"] == "allowed"
    report_capabilities = {
        capability["name"]: capability["details"]
        for capability in reports["capabilities"]
    }
    assert report_capabilities["list_publications"]["default_result_cap"] is None
    assert report_capabilities["search_opinions"]["default_result_cap"] is None
    assert notices["source_status"] == "active"
    notice_capabilities = {
        capability["name"]: capability["details"]
        for capability in notices["capabilities"]
    }
    assert notice_capabilities["search_publications"]["adapter_command"] == "search"
    assert notice_capabilities["probe_source"]["adapter_command"] == ("sentinel")
    assert notices["probe_evidence"]["court_file_substitute"] is False
    assert notices["access_review"]["limits"]["displayed_result_ceiling"] == 10000
    assert reports.get("record_identity_source_id", reports["source_id"]) != nyscef.get(
        "record_identity_source_id", nyscef["source_id"]
    )


def test_orange_florida_and_federal_official_complements_keep_native_records():
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
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
    assert all(
        sources[source_id]["source_status"] == "active" for source_id in expected
    )

    clerk_id = "us-fl-orange-clerk-my-eclerk"
    statewide_opinion_id = "us-fl-appellate-opinions-search"
    assert (
        sources["us-fl-orange-clerk-records-request"]["record_identity_source_id"]
        == clerk_id
    )
    assert (
        sources["us-fl-sixth-dca-opinion-releases"]["record_identity_source_id"]
        == statewide_opinion_id
    )

    independent_records = {
        "us-fl-ninth-circuit-division-calendars",
        "us-fl-ninth-circuit-appellate-opinions-archive",
        "us-fl-ninth-circuit-administrative-orders",
        "us-fl-ninth-circuit-court-reporters",
        "us-fl-orange-official-records",
        "us-fl-orange-court-registry-balance",
        "us-fl-orange-confidentiality-notices",
        statewide_opinion_id,
        "us-flmd-recent-opinions",
        "us-ca11-published-opinions",
        "us-ca11-unpublished-opinions",
        "us-fl-orange-tax-collector-property-tax",
        "us-fl-orange-comptroller-tax-deed-sales",
    }
    for source_id in independent_records:
        assert sources[source_id]["record_identity_source_id"] == source_id

    official_records = sources["us-fl-orange-official-records"]
    assert official_records["domain"] == "property"
    assert {
        "instrument_number",
        "recording_date",
        "book",
        "page",
    } <= set(official_records["stable_keys"])
    instrument_search = next(
        capability
        for capability in official_records["capabilities"]
        if capability["name"] == "search_instruments"
    )
    assert {
        "case_number",
        "parcel_number",
        "legal_description",
    } <= set(instrument_search["details"]["input_fields"])

    tax_accounts = sources["us-fl-orange-tax-collector-property-tax"]
    tax_search = next(
        capability
        for capability in tax_accounts["capabilities"]
        if capability["name"] == "search_tax_accounts"
    )
    assert tax_search["details"]["input_fields"] == [
        "free_text",
        "owner_name",
        "parcel_account",
        "location_address",
    ]
    historical_bulk = tax_accounts["probe_evidence"]["historical_bulk"]
    assert historical_bulk["landing_page_label"] == "Daily"
    assert historical_bulk["publication_state"] == "fixed_historical_snapshot"
    assert historical_bulk["current_snapshot"]["observed_tax_year"] == 2019
    tax_deeds = sources["us-fl-orange-comptroller-tax-deed-sales"]
    assert tax_deeds["stable_keys"] == [
        "tax_deed_application_number",
        "parcel_id",
        "sale_date",
    ]
    assert tax_deeds["probe_evidence"]["search_fields"] == [
        "party_name",
        "tax_deed_application_number",
        "status",
        "date_range",
        "parcel_id",
    ]

    registry = sources["us-fl-orange-court-registry-balance"]
    assert registry["probe_evidence"]["source_balance_as_of"] == ("last_business_day")
    notices = sources["us-fl-orange-confidentiality-notices"]
    assert (
        notices["probe_evidence"]["publication_period_source_statement"]
        == "not_less_than_30_days"
    )

    statewide = sources[statewide_opinion_id]
    opinion_search = next(
        capability
        for capability in statewide["capabilities"]
        if capability["name"] == "search_opinions"
    )
    assert "opinion_text" in opinion_search["details"]["input_fields"]
    sixth = sources["us-fl-sixth-dca-opinion-releases"]
    assert sixth["probe_evidence"]["distinct_monitoring_views"] == [
        "most_recent_written_opinions",
        "most_recent_pcas",
        "release_date_archive",
    ]
    assert (
        "same_sixth_dca_opinion_documents"
        in sixth["probe_evidence"]["statewide_overlap"]
    )

    flmd = sources["us-flmd-recent-opinions"]
    assert flmd["probe_evidence"]["published_window"] == "previous_30_days"
    assert flmd["probe_evidence"]["orange_county_division"] == "Orlando"
    assert sources["us-ca11-published-opinions"]["coverage_start"] == ("1994-12")
    assert sources["us-ca11-unpublished-opinions"]["coverage_start"] == ("2005-04-18")

    for source_id in {
        statewide_opinion_id,
        "us-fl-sixth-dca-opinion-releases",
        "us-flmd-recent-opinions",
        "us-ca11-published-opinions",
        "us-ca11-unpublished-opinions",
    }:
        search = next(
            capability
            for capability in sources[source_id]["capabilities"]
            if capability["name"] == "search_opinions"
        )
        assert "default_result_cap" not in search["details"]


def test_denver_official_complements_keep_native_records_and_access_routes():
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
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
        sources[source_id]["source_status"] == "active" for source_id in expected
    )
    adapter_backed = {
        "us-co-denver-public-trustee-gts",
        "us-co-denver-delinquent-real-property-tax-list",
    }
    assert all(
        sources[source_id]["adapter_family"]
        and sources[source_id]["adapter_version"] == 1
        for source_id in adapter_backed
    )
    assert all(
        "adapter_family" not in sources[source_id]
        for source_id in expected - adapter_backed
    )

    for source_id in {
        "us-co-denver-public-trustee-gts",
        "us-co-denver-delinquent-real-property-tax-list",
        "us-co-denver-spatialest-property-tax",
        "us-co-denver-tax-lien-auction",
        "us-co-denver-realforeclose-auctions",
        "us-co-denver-district-administrative-orders",
    }:
        assert sources[source_id]["record_identity_source_id"] == source_id

    assert (
        sources["us-co-denver-district-court-records-request"][
            "record_identity_source_id"
        ]
        == "us-co-judicial-docket-search"
    )
    assert (
        sources["us-co-denver-county-court-records-request"][
            "record_identity_source_id"
        ]
        == "us-co-denver-county-court-public-docket"
    )

    gts = sources["us-co-denver-public-trustee-gts"]
    gts_capabilities = {row["name"]: row["details"] for row in gts["capabilities"]}
    assert set(gts_capabilities) == {
        "search_owner",
        "search_address",
        "search_sales",
        "fetch_foreclosure",
        "list_document_index",
        "fetch_document",
        "probe_source",
    }
    assert gts["stable_keys"] == ["public_trustee_number"]
    assert gts["probe_evidence"]["native_page_size"] == 25
    assert gts["probe_evidence"]["total_result_cap_observed"] is False
    assert (
        gts["probe_evidence"]["document_download_verified"]["content_type"]
        == "application/pdf"
    )
    assert {
        "ned_reception_number",
        "deed_of_trust_reception_number",
    } <= set(gts["probe_evidence"]["cross_source_join_fields"])
    assert "default_result_cap" not in gts_capabilities["search_sales"]

    delinquent = sources["us-co-denver-delinquent-real-property-tax-list"]
    assert delinquent["adapter_family"] == "denver_delinquent_tax_xlsx"
    assert delinquent["stable_keys"] == ["tax_year", "parcel_id"]
    assert delinquent["probe_evidence"]["workbook_data_rows"] == 8_373
    assert delinquent["probe_evidence"]["rows_by_tax_year"] == {
        "2019": 1,
        "2023": 8,
        "2024": 8_364,
    }
    assert delinquent["probe_evidence"]["content_type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert (
        delinquent["probe_evidence"]["source_states_list_is_ordered_by_parcel_id"]
        is True
    )

    spatialest = sources["us-co-denver-spatialest-property-tax"]
    assert spatialest["update_cadence"] == "daily"
    assert spatialest["probe_evidence"]["official_search_fields"] == [
        "address",
        "parcel_id",
        "schedule_number",
    ]
    assert spatialest["probe_evidence"]["network_contract_mapped"] is False

    recorder = sources["us-co-denver-recorder-publicsearch"]
    bulk = next(
        capability
        for capability in recorder["capabilities"]
        if capability["name"] == "request_bulk_files"
    )
    assert bulk["details"]["execution_mode"] == "permit_request"
    assert (
        recorder["probe_evidence"]["official_audit_bulk_digital_data_permits_reported"]
        is True
    )
    assert "us-co-denver-recorder-bulk-data-permit" not in sources

    tax_lien = sources["us-co-denver-tax-lien-auction"]
    realforeclose = sources["us-co-denver-realforeclose-auctions"]
    assert tax_lien["automation_disposition"] == "unclear"
    assert tax_lien["probe_evidence"]["listing_schema_verified"] is False
    assert realforeclose["automation_disposition"] == "unclear"
    assert realforeclose["probe_evidence"]["native_stable_key_verified"] is (False)

    district_orders = sources["us-co-denver-district-administrative-orders"]
    assert district_orders["stable_keys"] == [
        "order_number",
        "document_url",
    ]
    assert (
        district_orders["probe_evidence"]["administrative_order_index_observed"] is True
    )


def test_colorado_appellate_and_data_sources_keep_component_provenance(
    tmp_path,
):
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in config["sources"]}

    archive = sources["us-co-appellate-case-law-search"]
    releases = sources["us-co-judicial-appellate-opinion-releases"]
    data_catalog = sources["us-co-judicial-data-reports"]
    compiled = sources["us-co-judicial-compiled-aggregate-data-requests"]
    annual = sources["us-co-judicial-annual-statistical-reports"]
    pro_se = sources["us-co-judicial-case-parties-without-representation"]
    eviction = sources["us-co-judicial-eviction-filings-dashboard"]

    assert archive["adapter_family"] == releases["adapter_family"]
    assert archive["record_identity_source_id"] == archive["source_id"]
    assert releases["record_identity_source_id"] == releases["source_id"]
    assert releases["source_id"] in archive["complementary_source_ids"]
    assert archive["source_id"] in releases["complementary_source_ids"]
    assert archive["probe_evidence"]["count_driven_pagination_required"] is True
    assert archive["probe_evidence"]["short_intermediate_page_observed"] is True

    component_ids = {
        compiled["source_id"],
        annual["source_id"],
        pro_se["source_id"],
        eviction["source_id"],
    }
    assert component_ids <= set(data_catalog["complementary_source_ids"])
    assert data_catalog["probe_evidence"]["live_catalog_record_count"] == 18
    assert data_catalog["probe_evidence"]["component_counts"] == {
        "us-co-judicial-annual-statistical-reports": 9,
        "us-co-judicial-case-parties-without-representation": 5,
        "us-co-judicial-eviction-filings-dashboard": 1,
        "us-co-judicial-compiled-aggregate-data-requests": 3,
    }
    assert compiled["access_class"] == "E"
    assert compiled["automation_disposition"] == "not_applicable"
    assert (
        compiled["probe_evidence"]["compiled_and_aggregate_request_program_verified"]
        is True
    )
    assert annual["access_class"] == "A"
    assert annual["probe_evidence"]["linked_static_fiscal_years"] == [
        2021,
        2022,
        2023,
        2024,
    ]
    assert pro_se["probe_evidence"]["denver_county_court_included"] is False
    assert eviction["capabilities"] == [
        {
            "name": "discover_dashboard",
            "details": {
                "adapter_tool": "query_colorado_court_data.py",
                "adapter_commands": ["catalog", "search"],
                "output_fields": [
                    "title",
                    "description",
                    "landing_url",
                    "dashboard_url",
                ],
            },
        }
    ]

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    assert catalog.require_machine_acquisition(archive["source_id"])["allowed"] is True
    assert catalog.require_machine_acquisition(annual["source_id"])["allowed"] is True
    assert (
        catalog.machine_acquisition_decision(compiled["source_id"])["allowed"] is False
    )


def test_oregon_active_manifests_match_adapters(
    tmp_path,
):
    from tools import (
        query_deschutes_dial,
        query_deschutes_laserfiche,
        query_deschutes_property,
        query_oregon_appellate,
        query_oregon_appellate_calendars,
        query_oregon_court_calendar,
        query_oregon_court_directories,
        query_oregon_helion_recorder,
        query_oregon_lane_marion_parcels,
    )

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in config["sources"]}
    appellate = sources[query_oregon_appellate.SOURCE_ID]
    calendar = sources[query_oregon_court_calendar.SOURCE_ID]
    deschutes = sources[query_deschutes_property.SOURCE_ID]
    deschutes_dial = sources[query_deschutes_dial.SOURCE_ID]
    deschutes_cdd = sources[query_deschutes_laserfiche.SOURCE_ID]
    appellate_calendars = {
        source_id: sources[source_id]
        for source_id in query_oregon_appellate_calendars.SOURCE_IDS
    }
    court_directories = {
        source_id: sources[source_id]
        for source_id in query_oregon_court_directories.SOURCE_IDS
    }
    lane_marion_sources = {
        source_id: sources[source_id]
        for source_id in query_oregon_lane_marion_parcels.SOURCES
    }
    helion_recorders = {
        source_id: sources[source_id]
        for source_id in query_oregon_helion_recorder.SOURCE_IDS
    }

    assert appellate["source_status"] == "active"
    assert appellate["endpoints"]["api_root"] == (query_oregon_appellate.API_ROOT)
    assert {capability["name"] for capability in appellate["capabilities"]} >= {
        "search_cases",
        "search_parties",
        "fetch_case",
        "list_docket_entries",
        "search_calendar",
        "fetch_document_metadata",
        "probe_source",
    }

    assert deschutes["source_status"] == "active"
    assert deschutes["official_url"] == (query_deschutes_property.SERVICE_URL)
    assert deschutes["probe_evidence"]["service_item_id"] == (
        query_deschutes_property.SERVICE_ITEM_ID
    )
    assert deschutes["probe_evidence"]["primary_taxlot_count"] == 109_508
    sale_capability = next(
        capability
        for capability in deschutes["capabilities"]
        if capability["name"] == "fetch_sale_observations"
    )
    assert sale_capability["details"]["declared_arcgis_relationship"] is False
    assert deschutes_dial["source_status"] == "active"
    assert deschutes_dial["official_url"] == query_deschutes_dial.BASE_URL
    assert deschutes_dial["endpoints"]["base"] == query_deschutes_dial.BASE_URL
    dial_capabilities = {
        capability["name"]: capability["details"]
        for capability in deschutes_dial["capabilities"]
    }
    assert dial_capabilities["search_property_accounts"]["input_fields"] == (
        list(query_deschutes_dial.SEARCH_FIELDS)
    )
    assert dial_capabilities["search_property_accounts"]["result_columns"] == (
        list(query_deschutes_dial.SEARCH_COLUMNS)
    )
    assert dial_capabilities["fetch_property_account"]["components"] == list(
        query_deschutes_dial.DEFAULT_COMPONENTS
    )
    assert dial_capabilities["fetch_property_report"]["direct_reports"] == list(
        query_deschutes_dial.DIRECT_REPORTS
    )
    assert dial_capabilities["fetch_property_report"]["generated_reports"] == list(
        query_deschutes_dial.CUSTOM_REPORTS
    )
    assert query_deschutes_dial.SOURCE_ID in (deschutes["complementary_source_ids"])
    assert (
        query_deschutes_property.SOURCE_ID
        in (deschutes_dial["complementary_source_ids"])
    )
    assert deschutes_cdd["source_status"] == "active"
    assert deschutes_cdd["official_url"] == query_deschutes_laserfiche.BASE_URL
    assert deschutes_cdd["stable_keys"] == [
        "laserfiche_entry_id",
        "laserfiche_folder_id",
    ]
    cdd_capabilities = {
        capability["name"]: capability["details"]
        for capability in deschutes_cdd["capabilities"]
    }
    assert cdd_capabilities["list_account_documents"]["pagination"] == (
        "complete_html_table_with_query_and_snapshot_bound_cursor"
    )
    assert cdd_capabilities["download_document"]["representation_modes"] == [
        "electronic_file",
        "generated_pdf_from_imaged_pages",
    ]
    assert {
        query_deschutes_dial.SOURCE_ID,
        query_deschutes_property.SOURCE_ID,
    }.issubset(deschutes_cdd["complementary_source_ids"])

    assert calendar["source_status"] == "active"
    assert calendar["official_url"] == (query_oregon_court_calendar.LANDING_URL)
    assert calendar["endpoints"]["search_form"] == (
        query_oregon_court_calendar.SEARCH_URL
    )
    calendar_search = next(
        capability
        for capability in calendar["capabilities"]
        if capability["name"] == "search_calendar"
    )
    assert calendar_search["details"]["documented_result_display_count"] == (
        query_oregon_court_calendar.DOCUMENTED_RESULT_CEILING
    )
    assert calendar_search["details"]["live_observed_returned_rows"] == (
        query_oregon_court_calendar.LIVE_OBSERVED_RETURNED_ROWS
    )
    assert "native_result_ceiling" not in calendar_search["details"]

    assert set(appellate_calendars) == set(query_oregon_appellate_calendars.SOURCE_IDS)
    for source_id, manifest in appellate_calendars.items():
        spec = next(
            value
            for value in (
                query_oregon_appellate_calendars.COURT_OF_APPEALS,
                query_oregon_appellate_calendars.SUPREME_COURT,
            )
            if value.source_id == source_id
        )
        assert manifest["source_status"] == "active"
        assert manifest["official_url"] == spec.page_url
        assert manifest["endpoints"]["legacy"] == spec.legacy_url
        assert manifest["endpoints"]["list_path"] == spec.list_path
        assert manifest["endpoints"]["view_name"] == spec.view_name
        search = next(
            capability
            for capability in manifest["capabilities"]
            if capability["name"] == "search_calendar"
        )
        assert search["details"]["acquisition_pagination"] == (
            "complete_sharepoint_continuation"
        )

    assert set(court_directories) == set(query_oregon_court_directories.SOURCE_IDS)
    for source_id, manifest in court_directories.items():
        source = query_oregon_court_directories.SOURCES_BY_ID[source_id]
        assert manifest["source_status"] == "active"
        assert manifest["official_url"] == source.page_url
        assert manifest["platform_family"] == (
            query_oregon_court_directories.PLATFORM_FAMILY
        )
        assert manifest["authentication"] == ("anonymous_cookie_session")
        assert manifest["endpoints"]["lists_soap"] == (
            query_oregon_court_directories.LISTS_URL
        )
        assert manifest["endpoints"]["views_soap"] == (
            query_oregon_court_directories.VIEWS_URL
        )
        assert manifest["endpoints"]["list_name"] == source.list_name
        assert manifest["endpoints"]["default_view_id"] == (source.default_view.view_id)

    assert set(lane_marion_sources) == set(query_oregon_lane_marion_parcels.SOURCES)
    for source_id, manifest in lane_marion_sources.items():
        source = query_oregon_lane_marion_parcels.SOURCES[source_id]
        assert manifest["source_status"] == "active"
        assert manifest["official_url"] == source.layer_url
        assert manifest["adapter_family"] == ("oregon_lane_marion_property")
        assert manifest["endpoints"]["layer"] == source.layer_url
        assert manifest["probe_evidence"]["service_item_id"] == (source.service_item_id)
        assert manifest["probe_evidence"]["source_crs"] == (source.original_crs)
    lane = lane_marion_sources[query_oregon_lane_marion_parcels.LANE_PARCELS_SOURCE_ID]
    assert (
        query_oregon_lane_marion_parcels.LANE_SALES_SOURCE_ID
        in lane["complementary_source_ids"]
    )
    marion = lane_marion_sources[
        query_oregon_lane_marion_parcels.MARION_PARCELS_SOURCE_ID
    ]
    assert "us-or-marion-sales-data" in marion["complementary_source_ids"]
    assert (
        sources["us-or-marion-comprehensive-assessment-download"]["probe_evidence"][
            "owner_names_included"
        ]
        is False
    )

    assert set(helion_recorders) == set(query_oregon_helion_recorder.SOURCE_IDS)
    for source_id, manifest in helion_recorders.items():
        tenant = query_oregon_helion_recorder.TENANTS_BY_SOURCE[source_id]
        assert manifest["record_identity_source_id"] == source_id
        assert manifest["official_url"] == tenant.portal_root
        assert manifest["endpoints"]["portal"] == tenant.portal_root
        assert manifest["adapter_family"] == "oregon_helion_recorder"
        expected_challenge = (
            "google_recaptcha" if tenant.captcha_observed else tenant.captcha_observed
        )
        assert manifest["probe_evidence"]["captcha_observed"] == (expected_challenge)
    crook_decision_limits = helion_recorders["us-or-crook-helion-recorder"][
        "access_review"
    ]["limits"]
    assert crook_decision_limits["interactive_challenge_observed"] == (
        "google_recaptcha"
    )

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    assert (
        catalog.require_machine_acquisition(appellate["source_id"])["allowed"] is True
    )
    assert (
        catalog.require_machine_acquisition(deschutes["source_id"])["allowed"] is True
    )
    assert (
        catalog.require_machine_acquisition(deschutes_dial["source_id"])["allowed"]
        is True
    )
    assert catalog.require_machine_acquisition(calendar["source_id"])["allowed"] is True
    for source_id in appellate_calendars:
        assert catalog.require_machine_acquisition(source_id)["allowed"] is True
    for source_id in court_directories:
        assert catalog.require_machine_acquisition(source_id)["allowed"] is True
    for source_id in lane_marion_sources:
        assert catalog.require_machine_acquisition(source_id)["allowed"] is True
    for source_id in helion_recorders:
        assert catalog.require_machine_acquisition(source_id)["allowed"] is True


def test_yamhill_clackamas_and_wasco_manifests_match_component_adapters(tmp_path):
    from tools import (
        query_oregon_clackamas_property,
        query_oregon_wasco_property,
        query_oregon_yamhill_property,
    )

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in config["sources"]}
    component_ids = {
        *query_oregon_yamhill_property.SOURCE_IDS,
        *query_oregon_clackamas_property.SOURCE_IDS,
        *query_oregon_wasco_property.SOURCE_IDS,
    }

    assert component_ids.issubset(sources)
    assert (
        sources[query_oregon_yamhill_property.ASCEND_SOURCE_ID]["official_url"]
        == query_oregon_yamhill_property.ASCEND_ROOT_URL
    )
    assert (
        sources[query_oregon_clackamas_property.CMAP_SOURCE_ID]["official_url"]
        == query_oregon_clackamas_property.CMAP_LAYER_URL
    )
    assert (
        sources[query_oregon_wasco_property.TAXLOT_SOURCE_ID]["official_url"]
        == query_oregon_wasco_property.TAXLOT_LAYER_URL
    )
    for source_id in component_ids:
        manifest = sources[source_id]
        assert manifest["source_status"] == "active"
        assert manifest["access_review"]["automation_disposition"] == (
            "allowed_with_limits"
        )
        assert "probe_source" in {
            (capability if isinstance(capability, str) else capability["name"])
            for capability in manifest["capabilities"]
        }
    assert {
        sources[source_id]["official_url"]
        for source_id in query_oregon_wasco_property.SURVEY_SOURCE_IDS
    } == {
        (
            f"{query_oregon_wasco_property.SURVEY_SERVICE_ROOT}/"
            f"{query_oregon_wasco_property.SURVEY_LAYERS[source_id].layer_id}"
        )
        for source_id in query_oregon_wasco_property.SURVEY_SOURCE_IDS
    }
    roles_by_source = {
        source_id: {
            association["role"]
            for association in sources[source_id].get("census_associations", [])
        }
        for source_id in {
            *component_ids,
            query_oregon_yamhill_property.HELION_SOURCE_ID,
            query_oregon_wasco_property.WASCO_HELION_SOURCE_ID,
        }
    }
    assert roles_by_source[query_oregon_yamhill_property.ASCEND_SOURCE_ID] == {
        "assessment_roll"
    }
    assert roles_by_source[query_oregon_yamhill_property.TAXLOT_SOURCE_ID] == {
        "assessment_roll",
        "parcel_geometry",
    }
    assert roles_by_source[query_oregon_yamhill_property.RETIRED_SOURCE_ID] == set()
    assert roles_by_source[query_oregon_yamhill_property.PERMIT_SOURCE_ID] == set()
    assert roles_by_source[query_oregon_yamhill_property.HELION_SOURCE_ID] == {
        "land_records_index"
    }
    assert roles_by_source[query_oregon_clackamas_property.ASCEND_SOURCE_ID] == {
        "assessment_roll"
    }
    assert roles_by_source[query_oregon_clackamas_property.CMAP_SOURCE_ID] == {
        "assessment_roll",
        "parcel_geometry",
    }
    assert roles_by_source[query_oregon_wasco_property.ASCEND_SOURCE_ID] == {
        "assessment_roll"
    }
    assert roles_by_source[query_oregon_wasco_property.TAXLOT_SOURCE_ID] == {
        "assessment_roll",
        "parcel_geometry",
    }
    assert all(
        roles_by_source[source_id] == set()
        for source_id in query_oregon_wasco_property.SURVEY_SOURCE_IDS
    )
    assert roles_by_source[query_oregon_wasco_property.WASCO_HELION_SOURCE_ID] == {
        "land_records_index"
    }

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    for source_id in component_ids:
        assert catalog.require_machine_acquisition(source_id)["allowed"] is True


def test_washington_property_manifests_match_six_component_contracts(tmp_path):
    from tools import query_oregon_washington_property as washington

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in config["sources"]}
    component_ids = set(washington.SOURCES)

    assert component_ids.issubset(sources)
    assert sources[washington.SURVEY_API_SOURCE_ID]["official_url"] == (
        washington.SURVEY_APP_URL
    )
    assert sources[washington.SURVEY_MAP_SOURCE_ID]["official_url"] == (
        washington.SURVEY_MAP_URL
    )
    assert sources[washington.TAXLOT_SOURCE_ID]["official_url"] == (
        washington.TAXLOT_LAYER_URL
    )
    assert sources[washington.SITUS_SOURCE_ID]["official_url"] == (
        washington.SITUS_LAYER_URL
    )
    assert sources[washington.INTERMAP_SOURCE_ID]["official_url"] == (
        washington.INTERMAP_BASE_URL
    )
    assert sources[washington.TAX_SOURCE_ID]["official_url"] == (
        washington.TAX_BASE_URL
    )
    for source_id in component_ids:
        manifest = sources[source_id]
        assert manifest["record_identity_source_id"] == source_id
        assert manifest["source_status"] == "active"
        assert manifest["adapter_family"] == "oregon_washington_property"
        assert manifest["access_review"]["automation_disposition"] == (
            "allowed_with_limits"
        )
        assert "probe_source" in {
            capability["name"] for capability in manifest["capabilities"]
        }
    assert {
        association["role"]
        for association in sources[washington.SURVEY_API_SOURCE_ID].get(
            "census_associations",
            [],
        )
    } == set()
    assert {
        association["role"]
        for association in sources[washington.SURVEY_MAP_SOURCE_ID].get(
            "census_associations",
            [],
        )
    } == set()
    assert {
        association["role"]
        for association in sources[washington.TAXLOT_SOURCE_ID]["census_associations"]
    } == {"parcel_geometry"}
    assert {
        association["role"]
        for association in sources[washington.SITUS_SOURCE_ID].get(
            "census_associations",
            [],
        )
    } == set()
    assert {
        association["role"]
        for association in sources[washington.TAX_SOURCE_ID]["census_associations"]
    } == {"assessment_roll", "tax_collection"}
    assert all(
        association["jurisdiction_geoid"] == "41"
        and association["coverage"]
        and association["coverage_gaps"]
        for source_id in component_ids
        for association in sources[source_id].get("census_associations", [])
    )
    survey_capability = next(
        capability
        for capability in sources[washington.SURVEY_API_SOURCE_ID]["capabilities"]
        if capability["name"] == "search_survey_records"
    )
    assert set(survey_capability["details"]["record_families"]) == set(
        washington.SURVEY_KINDS
    )
    complements = [
        item
        for source_id in component_ids
        for item in sources[source_id].get("official_complements", [])
    ]
    assert washington.PORTLAND_REGIONAL_SOURCE_ID in {
        item.get("source_id") for item in complements
    }
    assert {item["url"] for item in washington.COMPLEMENTS if item.get("url")}.issubset(
        {item.get("url") for item in complements}
    )

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    for source_id in component_ids:
        assert catalog.require_machine_acquisition(source_id)["allowed"] is True
        assert (
            catalog.show_source(source_id)["current_manifest"]["source_status"]
            == "active"
        )


def test_washington_case_permit_manifests_keep_six_components_and_access_scopes(
    tmp_path,
):
    from tools import query_oregon_washington_case_permits as adapter

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in config["sources"]}
    component_ids = set(adapter.SOURCES)

    assert component_ids.issubset(sources)
    for source_id in component_ids:
        manifest = sources[source_id]
        assert manifest["record_identity_source_id"] == source_id
        assert manifest["official_url"] == adapter.SOURCES[source_id].base_url
        assert manifest["domain"] == "property"
        assert manifest["source_status"] == "active"
        assert manifest["adapter_family"] == "oregon_washington_case_permits"
        assert manifest["census_associations"] == []
        assert manifest["operation_access"]
        assert "probe_source" in {
            capability["name"] for capability in manifest["capabilities"]
        }

    building_access = sources[adapter.BUILDING_SOURCE_ID]["operation_access"]
    assert building_access["taxlot_search"] == "anonymous"
    assert building_access["permit_types"] == "anonymous"
    assert building_access["permit_number_search"] == "source_challenge_observed"
    assert building_access["type_date_address_search"] == "source_challenge_observed"
    assert sources[adapter.CASEFILE_SOURCE_ID]["operation_access"] == {
        "case_search": "anonymous",
        "exact_case_detail": "anonymous",
        "applications_under_review": "anonymous",
        "recent_decisions": "anonymous",
        "staff_vocabulary": "anonymous",
    }
    assert set(sources[adapter.PERMIT_REPORT_SOURCE_ID]["operation_access"]) == {
        "project_report",
        "activity_report",
        "people_report",
        "inspection_report",
        "review_report",
    }
    assert (
        sources[adapter.DOCUMENT_ROUTE_SOURCE_ID]["probe_evidence"][
            "network_requests_per_adapter_catalog_probe"
        ]
        == 0
    )

    complement_urls = {
        item["url"]
        for source_id in component_ids
        for item in sources[source_id]["official_complements"]
    }
    assert {
        adapter.PROJECTS_REVIEW_APP_URL,
        adapter.DECISIONS_APP_URL,
        adapter.DEVELOPMENT_PROGRESS_URL,
        adapter.FREQUENTLY_DISCUSSED_URL,
        adapter.PUBLIC_HEARINGS_URL,
        adapter.CIVICWEB_LAND_USE_URL,
        adapter.LEGACY_LASERFICHE_URL,
        adapter.PERMIT_RECORDS_URL,
    }.issubset(complement_urls)

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    for source_id in component_ids:
        assert catalog.require_machine_acquisition(source_id)["allowed"] is True
        assert (
            catalog.show_source(source_id)["current_manifest"]["source_status"]
            == "active"
        )


def test_multnomah_sail_manifests_match_eight_component_contracts(tmp_path):
    from tools import query_oregon_multnomah_sail as sail

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in config["sources"]}
    component_ids = set(sail.SOURCE_IDS)

    assert component_ids.issubset(sources)
    for source_id in component_ids:
        component = sail.COMPONENTS[source_id]
        manifest = sources[source_id]
        assert manifest["record_identity_source_id"] == source_id
        assert manifest["official_url"] == component.layer_url
        assert manifest["source_status"] == "active"
        assert manifest["adapter_family"] == "oregon_multnomah_sail"
        assert manifest["probe_evidence"]["feature_count"] == (component.observed_count)
        assert manifest["access_review"]["automation_disposition"] == (
            "allowed_with_limits"
        )
        assert "probe_source" in {
            capability["name"] for capability in manifest["capabilities"]
        }
        assert all(
            association["jurisdiction_geoid"] == "41"
            and association["coverage"]["county_geoids"] == ["41051"]
            and association["coverage_gaps"]
            for association in manifest["census_associations"]
        )

    assert {
        association["role"]
        for association in sources[sail.TAX_PARCEL_SOURCE_ID]["census_associations"]
    } == {"assessment_roll", "parcel_geometry"}
    assert all(
        sources[source_id].get("census_associations", []) == []
        for source_id in sail.IMAGE_SOURCE_IDS
    )
    assert {
        association["role"]
        for association in sources["us-or-multnomah-helion-recorder"][
            "census_associations"
        ]
    } == {"land_records_index"}
    assert (
        "complete collection"
        in sources[sail.ROAD_SOURCE_ID]["probe_evidence"]["publisher_coverage_note"]
    )
    complement_urls = {
        complement.get("url")
        for source_id in component_ids
        for complement in sources[source_id].get("official_complements", [])
    }
    assert {complement["url"] for complement in sail.COMPLEMENTARY_SOURCES}.issubset(
        complement_urls
    )
    assert {
        "us-or-portland-regional-taxlots",
        "us-or-multnomah-helion-recorder",
    }.issubset(
        {
            complement
            for source_id in component_ids
            for complement in sources[source_id].get(
                "complementary_source_ids",
                [],
            )
        }
    )

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    for source_id in component_ids:
        assert catalog.require_machine_acquisition(source_id)["allowed"] is True
        assert (
            catalog.show_source(source_id)["current_manifest"]["source_status"]
            == "active"
        )


def test_oregon_eugene_smart_and_ojcin_catalog_contracts(tmp_path):
    from copy import deepcopy

    from tools import (
        query_eugene_municipal_court,
        query_oregon_ojcin_products,
        query_oregon_smart_search,
    )

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    eugene_id = query_eugene_municipal_court.SOURCE_ID
    tyler_ids = {
        tenant.source_id
        for tenant in query_eugene_municipal_court.OREGON_TENANTS.values()
    }
    eugene_request_id = "us-or-eugene-municipal-court-record-request"
    smart_id = query_oregon_smart_search.SOURCE_ID
    umbrella_id = query_oregon_ojcin_products.SOURCE_ID
    product_ids = set(query_oregon_ojcin_products.PRODUCTS)
    legacy_replacements = {
        "us-or-ojd-free-circuit-tax-record-search": [smart_id],
        "us-or-ojcin": [
            umbrella_id,
            "us-or-ojcin-oeci-subscription",
            "us-or-ojcin-acms-subscription",
        ],
        "us-or-ojcin-bulk-data": [
            "us-or-ojcin-standard-report-package",
            "us-or-ojcin-bulk-data-transfer",
        ],
        "us-or-ojd-statewide-data-request": ["us-or-osca-statewide-court-data-request"],
    }
    expected_ids = {
        *tyler_ids,
        eugene_request_id,
        smart_id,
        umbrella_id,
        *product_ids,
        *legacy_replacements,
    }

    assert expected_ids.issubset(sources)

    eugene = sources[eugene_id]
    eugene_request = sources[eugene_request_id]
    assert eugene["official_url"] == query_eugene_municipal_court.BASE_URL
    assert eugene["probe_evidence"]["court_id"] == (
        query_eugene_municipal_court.COURT_ID
    )
    assert eugene["probe_evidence"]["warrant_search_available"] is False
    assert eugene["probe_evidence"]["direct_documents_observed"] is False
    assert (
        eugene["probe_evidence"]["directory_discovery_claim"]["direct_access_proof"]
        is False
    )
    assert eugene_request_id in eugene["complementary_source_ids"]
    assert eugene_id in eugene_request["complementary_source_ids"]
    assert eugene_request["endpoints"]["municipal_court_form"] == (
        query_eugene_municipal_court.JUSTFOIA_MUNICIPAL_COURT_FORM_URL
    )
    assert "census_associations" not in eugene_request
    for tenant in query_eugene_municipal_court.OREGON_TENANTS.values():
        manifest = sources[tenant.source_id]
        assert manifest["record_identity_source_id"] == tenant.source_id
        assert manifest["official_url"] == tenant.base_url
        assert manifest["probe_evidence"]["direct_component_access"] == {
            "cases": tenant.case_access_state,
            "dockets": tenant.docket_access_state,
        }
        assert manifest["probe_evidence"]["court_id"] == tenant.court_id
        if tenant is not query_eugene_municipal_court.GRAND_RONDE_TENANT:
            assert (
                manifest["probe_evidence"]["directory_discovery_claim"][
                    "direct_access_proof"
                ]
                is False
            )
        if tenant.case_access_state == "public":
            assert manifest["access_class"] == "B"
            assert {capability["name"] for capability in manifest["capabilities"]} >= {
                "search_cases",
                "list_dockets",
                "fetch_docket",
                "fetch_case",
            }
        else:
            assert manifest["access_class"] == "C"
            assert {capability["name"] for capability in manifest["capabilities"]} == {
                "probe_source",
                "discover_source_family",
                "open_official_alternatives",
            }
    grand_ronde = sources[query_eugene_municipal_court.GRAND_RONDE_TENANT.source_id]
    assert {
        route.get("audience")
        for route in grand_ronde["official_alternatives"]
        if route.get("audience")
    } == {"court_record_requesters", "tribal_members"}

    smart = sources[smart_id]
    smart_capabilities = {
        capability["name"]: capability["details"]
        for capability in smart["capabilities"]
    }
    assert smart["official_url"] == query_oregon_smart_search.SOURCE_URL
    assert smart["endpoints"]["rendered_form_action"] == (
        query_oregon_smart_search.FORM_ACTION_URL
    )
    assert "search_cases" not in smart_capabilities
    assert (
        smart_capabilities["prepare_search_handoff"]["prepared_search_is_case_result"]
        is False
    )
    assert smart["probe_evidence"]["judicial_officer_counts_are_rolling"] is True

    umbrella = sources[umbrella_id]
    assert set(umbrella["component_source_ids"]) == product_ids
    assert umbrella["probe_evidence"]["public_endpoint_count"] == len(
        query_oregon_ojcin_products.ENDPOINTS
    )
    receipt_contract = umbrella["probe_evidence"]["delivery_receipt_contract"]
    assert receipt_contract["byte_level_artifact_hashes"] is True
    assert receipt_contract["rows_interpreted"] is False
    assert receipt_contract["records_parsed"] == 0
    assert receipt_contract["public_row_schema_published"] is False
    for product_id in product_ids:
        component = sources[product_id]
        assert component["record_identity_source_id"] == product_id
        assert component["product_contract"]["product_id"] == product_id
        inspect_delivery = next(
            capability
            for capability in component["capabilities"]
            if capability["name"] == "inspect_delivery"
        )
        assert inspect_delivery["details"]["receipt_contract"] == receipt_contract

    for legacy_id, replacement_ids in legacy_replacements.items():
        legacy = sources[legacy_id]
        assert legacy["source_status"] == "retired"
        assert legacy["capabilities"] == []
        assert legacy["replacement_source_ids"] == replacement_ids
        assert "census_associations" not in legacy

    association_roles = {
        source_id: [
            association["role"]
            for association in sources[source_id].get("census_associations", [])
        ]
        for source_id in expected_ids
    }
    assert association_roles[eugene_id] == ["trial_case_index"]
    for tenant in query_eugene_municipal_court.OREGON_TENANTS.values():
        expected_roles = (
            []
            if tenant is query_eugene_municipal_court.GRAND_RONDE_TENANT
            else ["trial_case_index"]
        )
        assert association_roles[tenant.source_id] == expected_roles
    assert association_roles[smart_id] == ["trial_case_index"]
    assert association_roles[umbrella_id] == ["bulk_data_program"]
    assert set(association_roles["us-or-ojcin-oeci-subscription"]) == {
        "trial_case_index",
        "bulk_data_program",
    }
    assert association_roles["us-or-ojcin-acms-subscription"] == ["bulk_data_program"]
    assert association_roles["us-or-ojcin-standard-report-package"] == [
        "bulk_data_program"
    ]
    assert association_roles["us-or-ojcin-bulk-data-transfer"] == ["bulk_data_program"]
    assert association_roles["us-or-osca-statewide-court-data-request"] == [
        "bulk_data_program"
    ]
    assert all(
        association["jurisdiction_geoid"] == "41"
        and association["role"] in {"trial_case_index", "bulk_data_program"}
        and association["coverage"]
        and association["coverage_gaps"]
        for source_id in expected_ids
        for association in sources[source_id].get("census_associations", [])
    )

    selected_sources = []
    for source_id in expected_ids:
        source = deepcopy(sources[source_id])
        if "complementary_source_ids" in source:
            source["complementary_source_ids"] = [
                complement_id
                for complement_id in source["complementary_source_ids"]
                if complement_id in expected_ids
            ]
        selected_sources.append(source)
    config_path = tmp_path / "oregon-court-sources.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "submitted_by": "test-oregon-court-catalog",
                "sources": selected_sources,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    catalog_path = tmp_path / "catalog.db"
    seeded = seed_catalog(db_path=catalog_path, config_path=config_path)

    assert seeded["sources_seen"] == len(expected_ids)
    catalog = PublicRecordsCatalog(catalog_path)
    assert (
        catalog.show_source(smart_id)["current_manifest"]["source_status"] == "active"
    )
    assert (
        catalog.show_source("us-or-ojcin")["current_manifest"]["source_status"]
        == "retired"
    )
    census = PublicRecordsCensus(catalog_path)
    trial = census.list_targets(
        state="OR",
        domain="court",
        role="trial_case_index",
    )[0]
    bulk = census.list_targets(
        state="OR",
        domain="court",
        role="bulk_data_program",
    )[0]
    oregon_tyler_census_ids = {
        tenant.source_id
        for tenant in query_eugene_municipal_court.OREGON_TENANTS.values()
        if tenant is not query_eugene_municipal_court.GRAND_RONDE_TENANT
    }
    assert {
        *oregon_tyler_census_ids,
        smart_id,
        "us-or-ojcin-oeci-subscription",
    }.issubset(trial["source_ids"])
    assert {
        umbrella_id,
        "us-or-ojcin-oeci-subscription",
        "us-or-ojcin-acms-subscription",
        "us-or-ojcin-standard-report-package",
        "us-or-ojcin-bulk-data-transfer",
        "us-or-osca-statewide-court-data-request",
    }.issubset(bulk["source_ids"])


def test_benton_property_components_seed_with_distinct_census_roles(tmp_path):
    from copy import deepcopy

    from tools import query_oregon_benton_property

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    component_ids = {
        query_oregon_benton_property.PARCEL_SOURCE_ID,
        query_oregon_benton_property.BULK_SOURCE_ID,
        query_oregon_benton_property.MAP_SOURCE_ID,
    }
    assert component_ids.issubset(sources)

    taxlot = sources[query_oregon_benton_property.PARCEL_SOURCE_ID]
    bulk = sources[query_oregon_benton_property.BULK_SOURCE_ID]
    maps = sources[query_oregon_benton_property.MAP_SOURCE_ID]
    assert taxlot["official_url"] == (query_oregon_benton_property.PARCEL_LAYER_URL)
    assert bulk["official_url"] == (
        query_oregon_benton_property.ASSESSMENT_DIRECTORY_URL
    )
    assert maps["official_url"] == (
        query_oregon_benton_property.ASSESSMENT_MAP_DIRECTORY_URL
    )
    assert {association["role"] for association in taxlot["census_associations"]} == {
        "assessment_roll",
        "parcel_geometry",
    }
    assert {association["role"] for association in bulk["census_associations"]} == {
        "assessment_roll",
        "parcel_geometry",
    }
    assert [association["role"] for association in maps["census_associations"]] == [
        "parcel_geometry"
    ]
    assert {
        query_oregon_benton_property.HELION_SOURCE_ID,
        query_oregon_benton_property.ACCOUNT_API_SOURCE_ID,
        query_oregon_benton_property.BULK_SOURCE_ID,
        query_oregon_benton_property.MAP_SOURCE_ID,
        "us-or-benton-helion-recorder",
    }.issubset(taxlot["complementary_source_ids"])
    for source in (taxlot, bulk, maps):
        assert source["access_review"]["automation_disposition"] == (
            "allowed_with_limits"
        )
        assert all(
            association["jurisdiction_geoid"] == "41"
            and association["coverage"]
            and association["coverage_gaps"]
            for association in source["census_associations"]
        )

    selected = []
    for source_id in component_ids:
        source = deepcopy(sources[source_id])
        source["complementary_source_ids"] = [
            complement
            for complement in source.get("complementary_source_ids", [])
            if complement in component_ids
        ]
        selected.append(source)
    config_path = tmp_path / "benton-property-sources.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "submitted_by": "test-benton-property-catalog",
                "sources": selected,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    catalog_path = tmp_path / "catalog.db"
    seeded = seed_catalog(db_path=catalog_path, config_path=config_path)

    assert seeded["sources_seen"] == 3
    catalog = PublicRecordsCatalog(catalog_path)
    for source_id in component_ids:
        assert catalog.require_machine_acquisition(source_id)["allowed"] is True
    census = PublicRecordsCensus(catalog_path)
    assessment = census.list_targets(
        state="OR",
        domain="property",
        role="assessment_roll",
    )[0]
    geometry = census.list_targets(
        state="OR",
        domain="property",
        role="parcel_geometry",
    )[0]
    assert {
        query_oregon_benton_property.PARCEL_SOURCE_ID,
        query_oregon_benton_property.BULK_SOURCE_ID,
    }.issubset(assessment["source_ids"])
    assert component_ids.issubset(geometry["source_ids"])


def test_lincoln_property_components_seed_with_joinable_census_roles(tmp_path):
    from copy import deepcopy

    from tools import (
        query_oregon_lincoln_propertyweb,
        query_oregon_lincoln_taxlots,
    )

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    component_ids = {
        query_oregon_lincoln_propertyweb.SOURCE_ID,
        query_oregon_lincoln_taxlots.SOURCE_ID,
    }
    recorder_id = "us-or-lincoln-helion-recorder"
    selected_ids = component_ids | {recorder_id}
    assert component_ids.issubset(sources)

    propertyweb = sources[query_oregon_lincoln_propertyweb.SOURCE_ID]
    taxlots = sources[query_oregon_lincoln_taxlots.SOURCE_ID]
    recorder = sources[recorder_id]
    assert propertyweb["official_url"] == query_oregon_lincoln_propertyweb.HOME_URL
    assert taxlots["official_url"] == query_oregon_lincoln_taxlots.APP_URL
    assert [item["role"] for item in propertyweb["census_associations"]] == [
        "assessment_roll"
    ]
    assert {item["role"] for item in taxlots["census_associations"]} == {
        "assessment_roll",
        "parcel_geometry",
    }
    assert {
        query_oregon_lincoln_taxlots.SOURCE_ID,
        recorder_id,
    }.issubset(propertyweb["complementary_source_ids"])
    assert {
        query_oregon_lincoln_propertyweb.SOURCE_ID,
        recorder_id,
    }.issubset(taxlots["complementary_source_ids"])
    assert component_ids.issubset(recorder["complementary_source_ids"])
    assert [item["role"] for item in recorder["census_associations"]] == [
        "land_records_index"
    ]
    assert {
        complement["source_id"]
        for complement in recorder["official_complements"]
        if complement.get("source_id")
    } >= component_ids
    assert propertyweb["access_review"]["automation_disposition"] == (
        "allowed_with_limits"
    )
    assert taxlots["access_review"]["automation_disposition"] == ("allowed_with_limits")

    selected = []
    for source_id in selected_ids:
        source = deepcopy(sources[source_id])
        source["complementary_source_ids"] = [
            complement
            for complement in source["complementary_source_ids"]
            if complement in selected_ids
        ]
        selected.append(source)
    config_path = tmp_path / "lincoln-property-sources.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "submitted_by": "test-lincoln-property-catalog",
                "sources": selected,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    catalog_path = tmp_path / "catalog.db"
    seeded = seed_catalog(db_path=catalog_path, config_path=config_path)

    assert seeded["sources_seen"] == 3
    catalog = PublicRecordsCatalog(catalog_path)
    for source_id in selected_ids:
        assert catalog.require_machine_acquisition(source_id)["allowed"] is True
    census = PublicRecordsCensus(catalog_path)
    assessment = census.list_targets(
        state="OR",
        domain="property",
        role="assessment_roll",
    )[0]
    geometry = census.list_targets(
        state="OR",
        domain="property",
        role="parcel_geometry",
    )[0]
    land_records = census.list_targets(
        state="OR",
        domain="property",
        role="land_records_index",
    )[0]
    assert component_ids.issubset(assessment["source_ids"])
    assert query_oregon_lincoln_taxlots.SOURCE_ID in geometry["source_ids"]
    assert recorder_id in land_records["source_ids"]


def test_dc_property_family_seeds_exact_roles_and_access_states(tmp_path):
    from copy import deepcopy

    from tools import query_dc_property, query_washington_parcels

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    component_ids = {
        component.source_id for component in query_dc_property.COMPONENTS.values()
    }
    selected_ids = {
        query_dc_property.LINEAGE_ID,
        query_dc_property.RECORDER_SOURCE_ID,
        *component_ids,
    }
    assert selected_ids.issubset(sources)

    itspe = sources[query_dc_property.ITSPE_SOURCE_ID]
    geometry = sources[query_dc_property.OWNER_POLYGON_SOURCE_ID]
    sales = sources[query_dc_property.SALES_SOURCE_ID]
    surveys = sources[query_dc_property.SURVEY_SOURCE_ID]
    recorder = sources[query_dc_property.RECORDER_SOURCE_ID]

    assert {association["role"] for association in itspe["census_associations"]} == {
        "assessment_roll",
        "tax_collection",
    }
    assert [association["role"] for association in geometry["census_associations"]] == [
        "parcel_geometry"
    ]
    geometry_coverage = geometry["census_associations"][0]["coverage"]
    assert geometry_coverage["record_grain"] == ("physical_common_ownership_polygon")
    assert geometry_coverage["observed_polygon_count"] == 137_400
    assert geometry_coverage["itspe_account_reference_count"] == 221_400
    assert geometry_coverage["account_polygon_cardinality"] == (
        "not_assumed_one_to_one"
    )
    assert sales["census_associations"] == []
    assert surveys["census_associations"] == []
    assert [association["role"] for association in recorder["census_associations"]] == [
        "land_records_index"
    ]
    assert recorder["authentication"] == "registered_user"
    assert recorder["automation_disposition"] == "unclear"
    assert recorder["probe_evidence"]["current_account_adapter_state"] == (
        "not_implemented"
    )

    for source_id in {
        query_dc_property.LINEAGE_ID,
        *component_ids,
    }:
        source = sources[source_id]
        assert source["automation_disposition"] == "allowed"
        assert source["access_review"]["automation_disposition"] == "allowed"
        assert "limits" not in source["access_review"]
        assert source["transport_contract"]["maximum_page_size"] == 1000

    washington_ids = {
        query_washington_parcels.LINEAGE_ID,
        *{
            representation.source_id
            for representation in query_washington_parcels.REPRESENTATIONS.values()
        },
        query_washington_parcels.FRESHNESS_SOURCE_ID,
        query_washington_parcels.LAND_USE_SOURCE_ID,
    }
    for source_id in washington_ids:
        source = sources[source_id]
        assert source["automation_disposition"] == "allowed"
        assert source["access_review"]["automation_disposition"] == "allowed"
        assert "limits" not in source["access_review"]
        assert "transport_contract" in source

    selected = []
    for source_id in selected_ids:
        source = deepcopy(sources[source_id])
        source["complementary_source_ids"] = [
            complement
            for complement in source.get("complementary_source_ids", [])
            if complement in selected_ids
        ]
        selected.append(source)
    config_path = tmp_path / "dc-property-sources.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "submitted_by": "test-dc-property-catalog",
                "sources": selected,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    catalog_path = tmp_path / "catalog.db"
    seeded = seed_catalog(db_path=catalog_path, config_path=config_path)

    assert seeded["sources_seen"] == len(selected_ids)
    catalog = PublicRecordsCatalog(catalog_path)
    for source_id in {
        query_dc_property.LINEAGE_ID,
        *component_ids,
    }:
        assert catalog.require_machine_acquisition(source_id)["allowed"] is True
    assert (
        catalog.machine_acquisition_decision(query_dc_property.RECORDER_SOURCE_ID)[
            "allowed"
        ]
        is False
    )

    census = PublicRecordsCensus(catalog_path)
    assessment = census.list_targets(
        state="DC",
        domain="property",
        role="assessment_roll",
    )[0]
    taxes = census.list_targets(
        state="DC",
        domain="property",
        role="tax_collection",
    )[0]
    parcel_geometry = census.list_targets(
        state="DC",
        domain="property",
        role="parcel_geometry",
    )[0]
    land_records = census.list_targets(
        state="DC",
        domain="property",
        role="land_records_index",
    )[0]
    assert assessment["source_ids"] == [query_dc_property.ITSPE_SOURCE_ID]
    assert taxes["source_ids"] == [query_dc_property.ITSPE_SOURCE_ID]
    assert parcel_geometry["source_ids"] == [query_dc_property.OWNER_POLYGON_SOURCE_ID]
    assert land_records["source_ids"] == [query_dc_property.RECORDER_SOURCE_ID]


def test_dc_opinions_catalog_seeds_exact_appellate_role_and_complements(
    tmp_path,
):
    from copy import deepcopy

    from tools import query_dc_opinions

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    source = sources[query_dc_opinions.SOURCE_ID]

    assert source["record_identity_source_id"] == query_dc_opinions.SOURCE_ID
    assert source["official_url"] == query_dc_opinions.INDEX_URL
    assert source["source_status"] == "active"
    assert source["automation_disposition"] == "allowed"
    assert source["access_review"]["automation_disposition"] == "allowed"
    assert "limits" not in source["access_review"]
    assert source["transport_contract"] == {
        "native_page_size": 10,
        "native_page_numbering": "zero_based",
        "default_minimum_interval_seconds": 0.25,
    }
    assert set(source["complementary_source_ids"]) == {
        "us-dc-court-of-appeals-case-search",
        "us-dc-court-of-appeals-calendars",
        "us-dc-superior-eaccess",
        "us-courtlistener-api",
    }
    assert source["probe_evidence"]["observed_total_items"] == 16_313
    assert source["probe_evidence"]["observed_total_pages"] == 1_632
    assert (
        source["probe_evidence"]["moj_rows_preserve_index_metadata_and_full_text_state"]
        is True
    )
    assert [association["role"] for association in source["census_associations"]] == [
        "appellate_opinions"
    ]
    association = source["census_associations"][0]
    assert association["jurisdiction_geoid"] == "11"
    assert association["coverage"]["record_grain"] == (
        "appellate_disposition_index_entry"
    )
    assert association["coverage"]["publication_classes"] == [
        "published_opinion",
        "memorandum_opinion_and_judgment_index",
    ]
    assert association["coverage_gaps"]

    selected = deepcopy(source)
    selected["complementary_source_ids"] = []
    selected["official_complements"] = [
        item for item in selected["official_complements"] if "source_id" not in item
    ]
    config_path = tmp_path / "dc-opinions-source.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "submitted_by": "test-dc-opinions-catalog",
                "sources": [selected],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    catalog_path = tmp_path / "catalog.db"
    seeded = seed_catalog(db_path=catalog_path, config_path=config_path)

    assert seeded["sources_seen"] == 1
    catalog = PublicRecordsCatalog(catalog_path)
    assert (
        catalog.require_machine_acquisition(query_dc_opinions.SOURCE_ID)["allowed"]
        is True
    )
    census = PublicRecordsCensus(catalog_path)
    appellate = census.list_targets(
        state="DC",
        domain="court",
        role="appellate_opinions",
    )[0]
    assert appellate["source_ids"] == [query_dc_opinions.SOURCE_ID]


def test_dc_and_maryland_case_routes_preserve_component_and_fallback_identity(
    tmp_path,
):
    from tools import (
        query_dc_appellate_cases,
        query_md_judgment_liens,
        query_md_public_cases,
    )

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}

    dc_appellate = sources[query_dc_appellate_cases.SOURCE_ID]
    assert dc_appellate["record_identity_source_id"] == (
        query_dc_appellate_cases.SOURCE_ID
    )
    assert dc_appellate["official_url"] == (query_dc_appellate_cases.CASE_SEARCH_URL)
    assert dc_appellate["source_status"] == "active"
    assert dc_appellate["automation_disposition"] == "allowed_with_limits"
    assert dc_appellate["census_associations"][0]["role"] == ("appellate_case_index")
    assert {
        "us-dc-court-of-appeals-opinions-mojs",
        "us-dc-court-of-appeals-calendars",
        "us-dc-superior-court-portal",
        "us-dc-superior-eaccess",
    } <= set(dc_appellate["complementary_source_ids"])

    dc_eaccess = sources["us-dc-superior-eaccess"]
    dc_portal = sources["us-dc-superior-court-portal"]
    assert dc_eaccess["probe_evidence"]["current_component"] == (
        "criminal_criminal_tax_and_domestic_violence"
    )
    assert dc_portal["probe_evidence"]["coverage"] == [
        "civil",
        "landlord_and_tenant",
        "small_claims",
        "civil_tax",
        "auditor_master",
        "probate",
    ]
    assert dc_eaccess["automation_disposition"] == "unclear"
    assert dc_portal["automation_disposition"] == "unclear"

    mdec = sources[query_md_public_cases.SOURCE_ID]
    judgments = sources[query_md_judgment_liens.SOURCE_ID]
    assert mdec["source_status"] == "active"
    assert judgments["source_status"] == "active"
    assert mdec["automation_disposition"] == "allowed_with_limits"
    assert judgments["automation_disposition"] == "allowed_with_limits"
    assert mdec["census_associations"][0]["role"] == "trial_case_index"
    assert judgments["census_associations"][0]["role"] == "trial_case_index"
    assert mdec["probe_evidence"]["rolling_report_count"] == 5
    assert judgments["probe_evidence"]["person_and_company_modes_verified"]
    assert judgments["probe_evidence"]["dynamic_jsf_form_and_view_state_discovery"]

    case_search = sources["us-md-case-search"]
    assert case_search["automation_disposition"] == "unclear"
    assert (
        case_search["probe_evidence"]["current_and_legacy_host_probe_state"]
        == "temporary_403_reputation_or_challenge_page"
    )

    expected_alternatives = {
        "us-md-circuit-clerk-records",
        "us-md-estate-search",
        "us-md-register-of-wills-offices",
        "us-md-estate-legal-notices",
        "us-md-estate-claims",
        "us-md-appellate-opinions",
        "us-md-business-technology-opinions",
        "us-md-land-records",
        "us-md-plats",
        "us-md-sdat-real-property",
        "us-md-local-finance-tax-liens",
    }
    assert expected_alternatives <= sources.keys()
    for source_id in expected_alternatives:
        assert sources[source_id]["record_identity_source_id"] == source_id

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    for source_id in (
        query_dc_appellate_cases.SOURCE_ID,
        query_md_public_cases.SOURCE_ID,
        "us-md-estate-search",
        query_md_judgment_liens.SOURCE_ID,
        "us-md-business-technology-opinions",
    ):
        assert catalog.require_machine_acquisition(source_id)["allowed"] is True
    for source_id in (
        "us-dc-superior-eaccess",
        "us-dc-superior-court-portal",
        "us-md-case-search",
        "us-md-land-records",
    ):
        assert catalog.machine_acquisition_decision(source_id)["allowed"] is False

    census = PublicRecordsCensus(catalog_path)
    dc_target = census.list_targets(
        state="DC",
        domain="court",
        role="appellate_case_index",
    )[0]
    assert query_dc_appellate_cases.SOURCE_ID in dc_target["source_ids"]
    md_target = census.list_targets(
        state="MD",
        domain="court",
        role="trial_case_index",
    )[0]
    assert {
        query_md_public_cases.SOURCE_ID,
        query_md_judgment_liens.SOURCE_ID,
    } <= set(md_target["source_ids"])
    md_rulings = census.list_targets(
        state="MD",
        domain="court",
        role="trial_court_rulings",
    )[0]
    assert "us-md-business-technology-opinions" in md_rulings["source_ids"]


def test_michigan_appellate_and_trial_routes_remain_independently_attributable(
    tmp_path,
):
    from tools import query_michigan_appellate, query_michigan_business_court

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    primary = sources[query_michigan_appellate.SOURCE_ID]

    assert primary["record_identity_source_id"] == primary["source_id"]
    assert primary["official_url"] == query_michigan_appellate.SEARCH_PAGE_URL
    assert primary["source_status"] == "active"
    assert primary["automation_disposition"] == "allowed_with_limits"
    assert {association["role"] for association in primary["census_associations"]} == {
        "appellate_case_index",
        "appellate_opinions",
    }
    assert {
        "us-mi-micourt-trial-case-search",
        "us-mi-micourt-developer-case-search-api",
        "us-mi-business-court-search",
        "us-mi-trial-court-directory",
    } <= set(primary["complementary_source_ids"])

    for source_id in {
        "us-mi-micourt-trial-case-search",
        "us-mi-micourt-developer-case-search-api",
        "us-mi-business-court-search",
        "us-mi-trial-court-directory",
    }:
        assert sources[source_id]["record_identity_source_id"] == source_id
    business_court = sources[query_michigan_business_court.SOURCE_ID]
    assert business_court["source_status"] == "active"
    assert business_court["automation_disposition"] == "allowed_with_limits"
    assert business_court["stable_keys"] == [
        "native_document_id",
        "source_occurrence_id",
        "source_case_number_candidate",
    ]
    assert business_court["identity_contract"][
        "selected_court_facet_is_authoritative_assignment"
    ] is False
    assert business_court["identity_contract"][
        "filename_court_code_is_authoritative_assignment"
    ] is False

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    assert (
        catalog.require_machine_acquisition(query_michigan_appellate.SOURCE_ID)[
            "allowed"
        ]
        is True
    )
    assert (
        catalog.require_machine_acquisition(
            query_michigan_business_court.SOURCE_ID
        )["allowed"]
        is True
    )
    assert (
        catalog.machine_acquisition_decision("us-mi-micourt-trial-case-search")[
            "allowed"
        ]
        is False
    )

    census = PublicRecordsCensus(catalog_path)
    appellate = census.list_targets(
        state="MI",
        domain="court",
        role="appellate_case_index",
    )[0]
    assert query_michigan_appellate.SOURCE_ID in appellate["source_ids"]
    opinions = census.list_targets(
        state="MI",
        domain="court",
        role="appellate_opinions",
    )[0]
    assert query_michigan_appellate.SOURCE_ID in opinions["source_ids"]
    trial_rulings = census.list_targets(
        state="MI",
        domain="court",
        role="trial_court_rulings",
    )[0]
    assert query_michigan_business_court.SOURCE_ID in trial_rulings["source_ids"]


def test_dc_calendar_catalog_matches_adapter_sources_and_record_grains():
    from tools import query_dc_superior_calendar

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    adapter_sources = {
        source["source_id"]: source
        for source in query_dc_superior_calendar.source_manifest()["sources"]
    }

    assert set(adapter_sources) == {
        query_dc_superior_calendar.TODAY_SOURCE_ID,
        query_dc_superior_calendar.CRIMINAL_SOURCE_ID,
        query_dc_superior_calendar.TAX_SOURCE_ID,
        query_dc_superior_calendar.APPEALS_SOURCE_ID,
    }
    expected_grains = {
        query_dc_superior_calendar.TODAY_SOURCE_ID: (
            "source_published_hearing_occurrence"
        ),
        query_dc_superior_calendar.CRIMINAL_SOURCE_ID: (
            "source_published_charge_level_hearing_occurrence"
        ),
        query_dc_superior_calendar.TAX_SOURCE_ID: ("court_published_calendar_artifact"),
        query_dc_superior_calendar.APPEALS_SOURCE_ID: (
            "court_published_calendar_artifact"
        ),
    }
    for source_id, metadata in adapter_sources.items():
        source = sources[source_id]
        assert source["record_identity_source_id"] == source_id
        assert source["official_url"] == metadata["base_url"]
        assert source["source_status"] == "active"
        assert source["automation_disposition"] == "allowed"
        assert source["access_review"]["automation_disposition"] == "allowed"
        assert "limits" not in source["access_review"]
        assert source["adapter_family"] == "dc_superior_calendar"
        association = source["census_associations"][0]
        assert association["jurisdiction_geoid"] == "11"
        assert association["coverage"]["record_grain"] == (expected_grains[source_id])
        assert any(
            capability["name"] == "probe_source"
            for capability in source["capabilities"]
        )


def test_fresno_catalog_matches_component_sources_and_coverage_roles(
    tmp_path,
):
    from tools import query_fresno_superior_court as fresno

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    expected_source_ids = {
        fresno.FAMILY_SOURCE_ID,
        fresno.PORTAL_SOURCE_ID,
        fresno.CALENDAR_SOURCE_ID,
        fresno.RULINGS_SOURCE_ID,
        fresno.PROBATE_SOURCE_ID,
        fresno.INDEX_SOURCE_ID,
        fresno.RECORDS_SOURCE_ID,
    }
    assert expected_source_ids <= sources.keys()

    allowed_source_ids = {
        fresno.FAMILY_SOURCE_ID,
        fresno.PORTAL_SOURCE_ID,
        fresno.CALENDAR_SOURCE_ID,
        fresno.RULINGS_SOURCE_ID,
        fresno.PROBATE_SOURCE_ID,
    }
    probe_source_ids = set()
    for source_id in expected_source_ids:
        source = sources[source_id]
        assert source["record_identity_source_id"] == source_id
        assert source["official_url"] == (fresno.SOURCE_METADATA[source_id].base_url)
        assert source["source_status"] == "active"
        assert "limits" not in source["access_review"]
        capability_names = {capability["name"] for capability in source["capabilities"]}
        if "probe_source" in capability_names:
            probe_source_ids.add(source_id)
        expected_disposition = (
            "allowed" if source_id in allowed_source_ids else "not_applicable"
        )
        assert source["automation_disposition"] == expected_disposition
        assert source["access_review"]["automation_disposition"] == expected_disposition
    assert probe_source_ids == allowed_source_ids

    expected_roles = {
        fresno.CALENDAR_SOURCE_ID: "hearing_calendars",
        fresno.RULINGS_SOURCE_ID: "trial_court_rulings",
        fresno.INDEX_SOURCE_ID: "trial_case_index",
    }
    for source_id, role in expected_roles.items():
        associations = sources[source_id]["census_associations"]
        assert [association["role"] for association in associations] == [role]
        assert associations[0]["jurisdiction_geoid"] == "06"
        assert associations[0]["coverage"]["county_fips"] == "06019"

    catalog_path = tmp_path / "catalog.db"
    seeded = seed_catalog(db_path=catalog_path)
    assert seeded["sources_seen"] == len(config["sources"])
    census = PublicRecordsCensus(catalog_path)
    for source_id, role in expected_roles.items():
        target = census.list_targets(
            state="CA",
            domain="court",
            role=role,
        )[0]
        assert source_id in target["source_ids"]


def test_orange_county_court_catalog_preserves_components_and_substitutes(
    tmp_path,
):
    from tools import query_orange_county_court as orange

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    expected_source_ids = {
        orange.SOURCE_FAMILY_ID,
        orange.CALENDAR_SOURCE_ID,
        *orange.RULING_SOURCE_IDS.values(),
        orange.CASE_NAME_SOURCE_ID,
        orange.CASE_PORTALS_SOURCE_ID,
        orange.CASE_INDEX_SOURCE_ID,
        orange.CASE_INDEX_PRODUCT_SOURCE_ID,
        orange.PROBATE_NOTES_SOURCE_ID,
        orange.RECORDS_SOURCE_ID,
    }
    assert expected_source_ids <= sources.keys()

    implemented_source_ids = {
        orange.SOURCE_FAMILY_ID,
        orange.CALENDAR_SOURCE_ID,
        *orange.RULING_SOURCE_IDS.values(),
    }
    manifest_urls = {
        record["source_id"]: record["url"]
        for record in orange.source_records()
        if record["record_kind"]
        in {
            "source_manifest",
            "complementary_source",
        }
    }
    assert expected_source_ids == manifest_urls.keys()

    probe_source_ids = set()
    for source_id in expected_source_ids:
        source = sources[source_id]
        assert source["record_identity_source_id"] == source_id
        assert source["official_url"] == manifest_urls[source_id]
        assert source["source_status"] == "active"
        assert "limits" not in source["access_review"]
        capability_names = {capability["name"] for capability in source["capabilities"]}
        if "probe_source" in capability_names:
            probe_source_ids.add(source_id)
        expected_disposition = (
            "allowed" if source_id in implemented_source_ids else "not_applicable"
        )
        assert source["automation_disposition"] == expected_disposition
        assert source["access_review"]["automation_disposition"] == expected_disposition
    assert probe_source_ids == implemented_source_ids

    expected_roles = {
        orange.CALENDAR_SOURCE_ID: {"hearing_calendars"},
        orange.RULING_SOURCE_IDS["civil"]: {"trial_court_rulings"},
        orange.RULING_SOURCE_IDS["family"]: {"trial_court_rulings"},
        orange.RULING_SOURCE_IDS["probate"]: {"trial_court_rulings"},
        orange.CASE_NAME_SOURCE_ID: {"trial_case_index"},
        orange.CASE_PORTALS_SOURCE_ID: {"trial_case_index"},
        orange.CASE_INDEX_SOURCE_ID: {"trial_case_index"},
        orange.CASE_INDEX_PRODUCT_SOURCE_ID: {
            "trial_case_index",
            "bulk_data_program",
        },
    }
    for source_id, roles in expected_roles.items():
        associations = sources[source_id]["census_associations"]
        assert {association["role"] for association in associations} == roles
        assert all(
            association["jurisdiction_geoid"] == "06"
            and association["coverage"]["county_fips"] == "06059"
            for association in associations
        )

    catalog_path = tmp_path / "catalog.db"
    seeded = seed_catalog(db_path=catalog_path)
    assert seeded["sources_seen"] == len(config["sources"])
    catalog = PublicRecordsCatalog(catalog_path)
    assert (
        catalog.require_machine_acquisition(orange.CALENDAR_SOURCE_ID)["allowed"]
        is True
    )
    assert (
        catalog.machine_acquisition_decision(orange.CASE_NAME_SOURCE_ID)["allowed"]
        is False
    )
    census = PublicRecordsCensus(catalog_path)
    for source_id, roles in expected_roles.items():
        for role in roles:
            target = census.list_targets(
                state="CA",
                domain="court",
                role=role,
            )[0]
            assert source_id in target["source_ids"]


def test_riverside_court_catalog_preserves_components_and_alternate_routes(
    tmp_path,
):
    from tools import query_riverside_court as riverside

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    expected_source_ids = {
        riverside.SOURCE_FAMILY_ID,
        riverside.CALENDAR_SOURCE_ID,
        riverside.RULING_SOURCE_ID,
        *riverside.COMPLEMENT_SOURCE_IDS_BY_URL.values(),
    }
    assert len(expected_source_ids) == 13
    assert expected_source_ids <= sources.keys()

    manifest_urls = {
        record["source_id"]: record["url"] for record in riverside.source_records()
    }
    assert expected_source_ids == manifest_urls.keys()

    implemented_source_ids = {
        riverside.SOURCE_FAMILY_ID,
        riverside.CALENDAR_SOURCE_ID,
        riverside.RULING_SOURCE_ID,
    }
    monitored_source_ids = {
        riverside.CALENDAR_SOURCE_ID,
        riverside.RULING_SOURCE_ID,
    }
    for source_id in expected_source_ids:
        source = sources[source_id]
        assert source["record_identity_source_id"] == source_id
        assert source["official_url"] == manifest_urls[source_id]
        assert source["source_status"] == "active"
        assert "limits" not in source["access_review"]
        expected_disposition = (
            "allowed" if source_id in implemented_source_ids else "not_applicable"
        )
        assert source["automation_disposition"] == expected_disposition
        assert source["access_review"]["automation_disposition"] == expected_disposition
        capability_names = {capability["name"] for capability in source["capabilities"]}
        assert ("probe_source" in capability_names) == (
            source_id in monitored_source_ids
        )

    expected_roles = {
        riverside.CALENDAR_SOURCE_ID: "hearing_calendars",
        riverside.RULING_SOURCE_ID: "trial_court_rulings",
        riverside.PUBLIC_ACCESS_SOURCE_ID: "trial_case_index",
        riverside.NAME_INDEX_SOURCE_ID: "trial_case_index",
        riverside.CLERK_SEARCH_SOURCE_ID: "trial_case_index",
    }
    for source_id, role in expected_roles.items():
        associations = sources[source_id]["census_associations"]
        assert [association["role"] for association in associations] == [role]
        assert associations[0]["jurisdiction_geoid"] == "06"
        assert associations[0]["coverage"]["county_fips"] == "06065"

    catalog_path = tmp_path / "catalog.db"
    seeded = seed_catalog(db_path=catalog_path)
    assert seeded["sources_seen"] == len(config["sources"])
    catalog = PublicRecordsCatalog(catalog_path)
    assert (
        catalog.require_machine_acquisition(riverside.CALENDAR_SOURCE_ID)["allowed"]
        is True
    )
    assert (
        catalog.machine_acquisition_decision(riverside.PUBLIC_ACCESS_SOURCE_ID)[
            "allowed"
        ]
        is False
    )
    census = PublicRecordsCensus(catalog_path)
    for source_id, role in expected_roles.items():
        target = census.list_targets(
            state="CA",
            domain="court",
            role=role,
        )[0]
        assert source_id in target["source_ids"]


def test_philadelphia_property_catalog_separates_components_and_transports(
    tmp_path,
):
    from tools import query_philadelphia_property as phila

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    expected_source_ids = {
        phila.FAMILY_SOURCE_ID,
        phila.SOURCE_ID,
        phila.OPA_BULK_SOURCE_ID,
        phila.OPA_CARTO_SOURCE_ID,
        phila.HISTORY_SOURCE_ID,
        phila.HISTORY_BULK_SOURCE_ID,
        phila.DOR_SOURCE_ID,
        phila.ATLAS_SOURCE_ID,
        phila.PHILADOX_SOURCE_ID,
        phila.RECORDS_SOURCE_ID,
        phila.PROPERTY_APP_SOURCE_ID,
    }
    assert expected_source_ids <= sources.keys()

    alternative_urls = {
        record["source_id"]: record["url"] for record in phila._alternatives()
    }
    assert alternative_urls.keys() == {
        phila.OPA_BULK_SOURCE_ID,
        phila.OPA_CARTO_SOURCE_ID,
        phila.HISTORY_BULK_SOURCE_ID,
        phila.DOR_SOURCE_ID,
        phila.ATLAS_SOURCE_ID,
        phila.PHILADOX_SOURCE_ID,
        phila.RECORDS_SOURCE_ID,
        phila.PROPERTY_APP_SOURCE_ID,
    }
    for source_id, url in alternative_urls.items():
        assert sources[source_id]["official_url"] == url

    assert (
        sources[phila.OPA_BULK_SOURCE_ID]["record_identity_source_id"]
        == phila.SOURCE_ID
    )
    assert (
        sources[phila.OPA_CARTO_SOURCE_ID]["record_identity_source_id"]
        == phila.SOURCE_ID
    )
    assert (
        sources[phila.PROPERTY_APP_SOURCE_ID]["record_identity_source_id"]
        == phila.SOURCE_ID
    )
    assert (
        sources[phila.HISTORY_BULK_SOURCE_ID]["record_identity_source_id"]
        == phila.HISTORY_SOURCE_ID
    )
    assert (
        sources[phila.OPA_CARTO_SOURCE_ID]["probe_evidence"][
            "counts_as_independent_corroboration"
        ]
        is False
    )

    implemented_source_ids = {
        phila.SOURCE_ID,
        phila.HISTORY_SOURCE_ID,
        phila.DOR_SOURCE_ID,
    }
    for source_id in implemented_source_ids:
        capability_names = {
            capability["name"] for capability in sources[source_id]["capabilities"]
        }
        assert {"ingest_property_records", "probe_source"} <= (capability_names)

    expected_roles = {
        phila.SOURCE_ID: "assessment_roll",
        phila.HISTORY_SOURCE_ID: "assessment_roll",
        phila.DOR_SOURCE_ID: "parcel_geometry",
        phila.PHILADOX_SOURCE_ID: "land_records_index",
        phila.RECORDS_SOURCE_ID: "land_records_index",
    }
    for source_id, role in expected_roles.items():
        association = sources[source_id]["census_associations"][0]
        assert association["jurisdiction_geoid"] == "42"
        assert association["role"] == role
        assert association["coverage"]["county_geoids"] == ["42101"]

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    census = PublicRecordsCensus(catalog_path)
    for source_id, role in expected_roles.items():
        target = census.list_targets(
            state="PA",
            domain="property",
            role=role,
        )[0]
        assert source_id in target["source_ids"]


def test_los_angeles_civil_catalog_keeps_primary_and_complements_distinct(
    tmp_path,
):
    from tools import query_los_angeles_court as la
    from tools import query_los_angeles_name_index as name_index_adapter

    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    complement_ids = {
        "us-ca-los-angeles-superior-civil-name-index",
        "us-ca-los-angeles-superior-civil-document-images",
        "us-ca-los-angeles-superior-civil-archives-records-center",
        "us-ca-los-angeles-superior-divorce-judgment-orders",
        "us-ca-los-angeles-superior-family-case-summary",
        "us-ca-los-angeles-superior-small-claims-case-summary",
        "us-ca-los-angeles-superior-appellate-tentative-rulings",
        "us-ca-trellis-los-angeles-superior-court",
    }
    assert {la.SOURCE_ID, *complement_ids} <= sources.keys()

    core = sources[la.SOURCE_ID]
    assert core["record_identity_source_id"] == la.SOURCE_ID
    assert core["official_url"] == la.SOURCE_METADATA.base_url
    assert core["automation_disposition"] == "allowed"
    assert core["access_review"]["automation_disposition"] == "allowed"
    assert "limits" not in core["access_review"]
    assert core["probe_evidence"]["current_selection_count"] == 84
    assert core["probe_evidence"]["exhaustive_all_selection_traversal_verified"] is True
    assert {capability["name"] for capability in core["capabilities"]} >= {
        "fetch_case",
        "list_docket_entries",
        "list_document_index",
        "list_ruling_selections",
        "list_tentative_rulings",
        "probe_source",
    }
    assert complement_ids <= set(core["complementary_source_ids"])

    name_index = sources["us-ca-los-angeles-superior-civil-name-index"]
    images = sources["us-ca-los-angeles-superior-civil-document-images"]
    assert name_index["record_identity_source_id"] == la.SOURCE_ID
    assert images["record_identity_source_id"] == la.SOURCE_ID
    assert name_index["automation_disposition"] == "allowed"
    assert images["automation_disposition"] == "not_applicable"
    assert name_index["adapter_family"] == ("los_angeles_civil_name_index")
    assert name_index["stable_keys"] == [
        "record_identity_source_id",
        "raw_case_number",
        "matched_party_name",
        "case_type",
        "filing_date",
        "filing_location",
        "duplicate_ordinal",
    ]
    assert {capability["name"] for capability in name_index["capabilities"]} == {
        "probe_source",
        "prepare_name_search",
        "recover_purchased_search",
        "parse_purchased_results",
        "ingest_court_records",
    }
    assert name_index["probe_evidence"]["case_family_identity_sources"] == {
        "civil": la.SOURCE_ID,
        "family_law": name_index_adapter.FAMILY_SOURCE_ID,
        "small_claims": name_index_adapter.SMALL_CLAIMS_SOURCE_ID,
        "probate": name_index_adapter.PROBATE_SOURCE_ID,
    }
    assert set(name_index["complementary_source_ids"]) >= {
        "us-ca-los-angeles-superior-civil-archives-records-center",
        "us-ca-los-angeles-superior-divorce-judgment-orders",
        "us-ca-second-district-appellate-case-information",
        "us-ca-trellis-los-angeles-superior-court",
    }

    expected_roles = {
        la.SOURCE_ID: {"trial_case_index", "trial_court_rulings"},
        "us-ca-los-angeles-superior-civil-name-index": {"trial_case_index"},
        "us-ca-los-angeles-superior-family-case-summary": {"trial_case_index"},
        "us-ca-los-angeles-superior-small-claims-case-summary": {"trial_case_index"},
        "us-ca-los-angeles-superior-appellate-tentative-rulings": {
            "trial_court_rulings"
        },
    }
    for source_id, roles in expected_roles.items():
        associations = sources[source_id]["census_associations"]
        assert {association["role"] for association in associations} == roles
        assert all(
            association["jurisdiction_geoid"] == "06"
            and association["coverage"]["county_fips"] == "06037"
            for association in associations
        )

    catalog_path = tmp_path / "catalog.db"
    seeded = seed_catalog(db_path=catalog_path)
    assert seeded["sources_seen"] == len(config["sources"])
    catalog = PublicRecordsCatalog(catalog_path)
    assert catalog.require_machine_acquisition(la.SOURCE_ID)["allowed"] is True
    assert (
        catalog.require_machine_acquisition(name_index["source_id"])["allowed"] is True
    )
    census = PublicRecordsCensus(catalog_path)
    for role in ("trial_case_index", "trial_court_rulings"):
        target = census.list_targets(
            state="CA",
            domain="court",
            role=role,
        )[0]
        assert la.SOURCE_ID in target["source_ids"]
