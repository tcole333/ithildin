from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_montana_cadastral as mt
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_contract import sha256_fingerprint
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]
LIVE_SCHEMA_FINGERPRINT = (
    "7262b409e6dff0e4c8ecfa5be5823d9419d93fd05107c6eb7b9e694a4aa09d85"
)
MONITOR_HASHES = {
    "monitor_stable_schema_sha256": (
        "ca8d4101ec147dd485b1496a65b05b8fc6a8790f4bcd23122ff852daa2a35fb6"
    ),
    "monitor_stable_contract_sha256": (
        "6d7edd3daf53a9be84014d82afc2a8ea46b0c6cc5e2ed8259a5afa7d5a07defc"
    ),
    "monitor_artifact_identity_sha256": (
        "18213f7de515153fee8dba19fe8b1d2d77c6ed75eb986572f0696adddd970bba"
    ),
}


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=mt.SOURCE_ID,
        catalog_decision={
            "allowed": True,
            "limits": {},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _snapshot(marker: int) -> dict[str, Any]:
    total_features = 56 * marker
    county_rows = [
        {
            "COUNTYCD": county.prefix,
            "CountyName": county.name,
            "CountyAbbr": county.abbreviation,
            "feature_count": marker,
        }
        for county in mt.COUNTIES
    ]
    record = {
        "source_id": mt.SOURCE_ID,
        "record_type": "parcel_feature_occurrence",
        "source_record_id": f"{{montana-feature-{marker}}}",
        "canonical_ref": (
            f"PROPERTY:{mt.SOURCE_ID}/30069/parcel-feature/"
            f"{{montana-feature-{marker}}}"
        ),
        "identity": {
            "object_id": marker,
            "global_id": f"{{montana-feature-{marker}}}",
            "parcel_id": "56382732101040000",
            "occurrence_key": "GlobalID",
            "transport_cursor_key": "OBJECTID",
            "parcel_join_key": "PARCELID",
            "parcel_join_key_present": True,
        },
        "jurisdiction": {
            "state_code": "MT",
            "state_fips": "30",
            "county_geoid": "30069",
            "county_name": "Petroleum",
            "county_abbreviation": "PE",
            "orion_county_prefix": 55,
        },
        "geometry": {"rings": []},
        "source_snapshot": {
            "schema_fingerprint": LIVE_SCHEMA_FINGERPRINT,
            "data_fingerprint": str(marker) * 64,
            "total_features": total_features,
            "features_with_parcel_id": total_features - 1,
            "features_without_parcel_id": 1,
            "maximum_object_id": total_features,
            "edge_tax_year": 2026,
            "native_page_size": 2000,
            "layer_url": mt.LAYER_URL,
        },
    }
    release_discovery = {
        "source_id": mt.SOURCE_ID,
        "record_type": "bulk_release_discovery",
        "statewide_parcel_artifacts": [
            {
                "name": "MontanaCadastral_GDB.zip",
                "publisher_modified_local": f"7/{marker}/2026 1:00 AM",
                "size": marker,
            },
            {
                "name": "MontanaCadastral_SHP.zip",
                "publisher_modified_local": f"7/{marker}/2026 1:00 AM",
                "size": marker,
            },
        ],
        "statewide_orion_artifact": {
            "name": "STATE-WIDE.ZIP",
            "publisher_modified_local": f"7/{marker}/2026 1:00 AM",
            "size": marker,
        },
        "parcel_county_directory_count": 56,
        "orion_county_archive_count": 56,
        "missing_parcel_county_directories": [],
        "unexpected_parcel_county_directories": [],
        "missing_orion_county_prefixes": [],
        "release_discovery_fingerprint": str(marker) * 64,
    }
    return {
        "record": record,
        "warnings": [f"rolling marker {marker}"],
        "county_rows": county_rows,
        "release_discovery": release_discovery,
        "requests_made": 15,
        "live_probe_requests": 11,
        "county_group_requests": 1,
        "directory_requests": 3,
    }


def test_monitor_keeps_live_counts_and_release_aliases_out_of_stable_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = 1

    def fake_snapshot(_context: ProbeContext) -> dict[str, Any]:
        return _snapshot(marker)

    monkeypatch.setattr(
        public_records_monitor,
        "_montana_cadastral_snapshot",
        fake_snapshot,
    )
    first = public_records_monitor.probe_montana_cadastral(_context())
    marker = 2
    second = public_records_monitor.probe_montana_cadastral(_context())

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details["stable_contract"]
    assert first.details["schema_contract"] == second.details["schema_contract"]
    assert first.details["artifact_identity"] == second.details[
        "artifact_identity"
    ]
    assert first.details["rolling_observation"] != second.details[
        "rolling_observation"
    ]
    assert first.details["requests_made"] == 15
    assert first.details["live_probe_requests"] == 11
    assert first.details["county_group_requests"] == 1
    assert first.details["directory_requests"] == 3
    assert first.details["stable_contract_sha256"] == sha256_fingerprint(
        first.details["stable_contract"]
    )
    assert first.details["stable_schema_sha256"] == sha256_fingerprint(
        first.details["schema_contract"]
    )
    assert {
        "monitor_stable_schema_sha256": first.schema_sha256,
        "monitor_stable_contract_sha256": first.details[
            "stable_contract_sha256"
        ],
        "monitor_artifact_identity_sha256": first.artifact_sha256,
    } == MONITOR_HASHES

    identity = first.details["stable_contract"]["identity"]
    assert len(identity["county_crosswalk"]) == 56
    assert identity["county_crosswalk"][0] == {
        "orion_county_prefix": 1,
        "county_name": "Silver Bow",
        "county_abbreviation": "SB",
        "parcel_directory": "SilverBow",
        "census_county_geoid": "30093",
    }
    assert identity["orion_prefix_is_census_fips"] is False
    assert identity["nullable_parcel_join_key"] == "PARCELID"
    assert first.details["stable_contract"]["publication_semantics"][
        "assessment_owner_is_recorded_title"
    ] is False

    comparison = compare_probes(
        {
            "probe_id": 1,
            "status": first.status,
            "schema_sha256": first.schema_sha256,
            "artifact_sha256": first.artifact_sha256,
        },
        {
            "probe_id": 2,
            "status": second.status,
            "schema_sha256": second.schema_sha256,
            "artifact_sha256": second.artifact_sha256,
        },
    )
    assert comparison["drift_detected"] is False


def test_catalog_census_and_projection_contracts_cover_all_56_counties(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    census = PublicRecordsCensus(catalog_path)

    decision = catalog.require_machine_acquisition(mt.SOURCE_ID)
    assert decision["allowed"] is True
    assert decision["limits"] == {}
    manifest = catalog.show_source(mt.SOURCE_ID)["current_manifest"]
    capabilities = {
        capability["name"]: capability["details"]
        for capability in manifest["capabilities"]
    }
    assert capabilities["query_shared_property_records"][
        "shared_operations"
    ] == [
        "account",
        "address",
        "count",
        "discovery",
        "download",
        "manifest",
        "map",
        "owner",
        "parcel",
        "point",
        "probe",
        "releases",
        "search",
    ]
    identity = manifest["identity_contract"]
    assert identity["source_occurrence_keys"] == ["GlobalID", "OBJECTID"]
    assert identity["parcel_join_key"] == "PARCELID"
    assert identity["parcel_join_key_nullable"] is True
    assert identity["county_source_key_semantics"] == (
        "ORION_CountyPrefix_not_Census_FIPS"
    )
    assert identity["orion_prefix_to_census_geoid"] == {
        str(county.prefix): county.geoid for county in mt.COUNTIES
    }
    assert manifest["publication_contract"][
        "owner_assertion_is_recorded_title"
    ] is False
    assert manifest["implementation_maturity"][
        "nullable_PARCELID_occurrence_preservation"
    ] == "implemented"

    expected_geoids = {county.geoid for county in mt.COUNTIES}
    assert manifest["source_coverage"]["county_count"] == 56
    assert set(manifest["source_coverage"]["county_geoids"]) == expected_geoids
    assert {
        complement["role"] for complement in manifest["official_complements"]
    } == {
        "interactive_parcel_and_property_research",
        "statewide_and_county_geometry_and_selected_CAMA_bulk",
        "richer_county_and_statewide_CAMA_bulk",
        "authoritative_public_land_survey_geometry",
        "public_land_ownership_context",
        "conservation_easement_geometry",
        "prior_parcel_snapshots",
        "current_local_assessment_tax_and_recorded_instruments",
    }
    assert {
        key: manifest["probe_evidence"][key] for key in MONITOR_HASHES
    } == MONITOR_HASHES

    associations = {
        association["role"]: association
        for association in manifest["census_associations"]
    }
    assert set(associations) == {"assessment_roll", "parcel_geometry"}
    for association in associations.values():
        assert association["jurisdiction_geoid"] == "30"
        assert association["coverage"]["statewide"] is True
        assert set(association["coverage"]["county_geoids"]) == expected_geoids
    assert associations["assessment_roll"]["coverage"][
        "recorded_title_evidence"
    ] is False

    for role in ("assessment_roll", "parcel_geometry"):
        target = census.list_targets(
            state="MT",
            domain="property",
            role=role,
        )[0]
        assert target["geoid"] == "30"
        assert mt.SOURCE_ID in target["source_ids"]


def test_catalog_audit_monitor_registry_docs_and_citation(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    audit = audit_catalog(db_path=catalog_path)
    mismatches = {
        item["source_id"]
        for item in audit["shared_adapter_operation_mismatches"]
    }
    assert mt.SOURCE_ID not in mismatches

    handler = public_records_monitor.HANDLER_REGISTRY[mt.SOURCE_ID]
    assert handler.handler is public_records_monitor.probe_montana_cadastral
    assert handler.endpoint == mt.LAYER_URL
    assert handler.expected_requests == 15
    assert handler.sentinel_record_count == 1
    assert handler.sample_bytes is None

    source_urls = json.loads(
        (
            ROOT / "web" / "src" / "data" / "source-urls.json"
        ).read_text(encoding="utf-8")
    )
    assert source_urls[f"PROPERTY_SOURCE:{mt.SOURCE_ID}"] == mt.LANDING_URL

    property_docs = (
        ROOT / "docs" / "modules" / "property.md"
    ).read_text(encoding="utf-8")
    tool_reference = (
        ROOT / "docs" / "TOOL_REFERENCE.md"
    ).read_text(encoding="utf-8")
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")
    for content in (property_docs, tool_reference, roadmap):
        assert mt.SOURCE_ID in content
    assert "ORION CountyPrefix is not a Census county FIPS code" in property_docs
    assert "34,173" in property_docs
    assert "assessment-roll observation, not recorded-title proof" in property_docs
    assert "all 56 counties" in property_docs


@pytest.mark.live_data
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for the bounded official source probe",
)
def test_live_monitor_hashes_match_catalog_pins() -> None:
    observation = public_records_monitor.probe_montana_cadastral(_context())

    assert observation.status == "ok"
    assert observation.schema_sha256 == MONITOR_HASHES[
        "monitor_stable_schema_sha256"
    ]
    assert observation.details["stable_contract_sha256"] == MONITOR_HASHES[
        "monitor_stable_contract_sha256"
    ]
    assert observation.artifact_sha256 == MONITOR_HASHES[
        "monitor_artifact_identity_sha256"
    ]
    rolling = observation.details["rolling_observation"]
    source_snapshot = rolling["source_snapshot"]
    assert source_snapshot["features_with_parcel_id"] + source_snapshot[
        "features_without_parcel_id"
    ] == source_snapshot["total_features"]
    assert len(rolling["county_coverage"]) == 56
    assert rolling["county_feature_total"] == source_snapshot["total_features"]
    releases = rolling["release_discovery"]
    assert releases["parcel_county_directory_count"] == 56
    assert releases["orion_county_archive_count"] == 56
    assert releases["missing_parcel_county_directories"] == []
    assert releases["missing_orion_county_prefixes"] == []
    assert observation.details["requests_made"] == 15
