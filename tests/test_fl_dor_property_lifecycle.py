from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_fl_dor_property as florida
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_contract import sha256_fingerprint
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]
MONITOR_HASHES = {
    "monitor_stable_schema_sha256": (
        "a07ca0abf4a0dbe4d3a6223539e163a723020234802508bef5e49c4ae7d29265"
    ),
    "monitor_stable_contract_sha256": (
        "43864603b5fd2e68dc7f4701272e706eab183feab92e1732aecce51f0b2af856"
    ),
    "monitor_artifact_identity_sha256": (
        "13a5aa11980a0abee8896a149bd1263500a2f7deaa923e2bda80e36125d41910"
    ),
}


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=florida.SOURCE_ID,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.1},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=4096,
    )


def _snapshot(marker: str) -> dict[str, Any]:
    components = {}
    for dataset_type in ("nal", "sdf", "gis-pin"):
        components[dataset_type] = {
            "release_id": f"{dataset_type}:2026{marker}",
            "assessment_year": 2026,
            "submission_stage": (
                "preliminary" if marker == "P" else "final"
            ),
            "submission_code": marker,
            "release_last_modified": f"2026-07-{marker}",
            "directory_artifact_count": 67,
            "manifest_record_count": 67,
            "base_artifact_count": 67,
            "observed_county_count": 67,
            "missing_county_dor_numbers": [],
            "extra_county_dor_numbers": [],
            "release_fingerprint": marker * 64,
            "sentinel": {
                "canonical_ref": (
                    f"property:{florida.SOURCE_ID}:12:bulk:{marker}"
                ),
                "county_name": "Baker",
                "county_dor_number": 12,
                "artifact": {
                    "filename": f"baker-{dataset_type}-{marker}.zip",
                    "expected_size": 100 if marker == "P" else 200,
                },
            },
        }
    return {
        "components": components,
        "artifact_probe": {
            "url": f"https://example.test/baker-{marker}.zip",
            "http_status": 206,
            "content_length": 100 if marker == "P" else 200,
            "media_type": "application/zip",
            "etag": marker,
            "last_modified": f"2026-07-{marker}",
            "accept_ranges": True,
            "source_sha256": None,
            "sample_size": 4,
            "sample_sha256": marker * 64,
            "signature_hex": "504b0304",
            "format_hint": "zip",
            "headers": {},
        },
        "requests_made": 9,
        "directory_requests": 7,
        "artifact_probe_requests": 2,
    }


def test_monitor_keeps_release_changes_out_of_stable_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = "P"

    def fake_snapshot(_context: ProbeContext) -> dict[str, Any]:
        return _snapshot(marker)

    monkeypatch.setattr(
        public_records_monitor,
        "_fl_dor_manifest_snapshot",
        fake_snapshot,
    )
    first = public_records_monitor.probe_fl_dor_property(_context())
    marker = "F"
    second = public_records_monitor.probe_fl_dor_property(_context())

    assert first.status == "ok"
    assert first.result_count == 3
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details[
        "stable_contract"
    ]
    assert first.details["schema_contract"] == second.details[
        "schema_contract"
    ]
    assert first.details["artifact_identity"] == second.details[
        "artifact_identity"
    ]
    assert first.details["rolling_observation"] != second.details[
        "rolling_observation"
    ]
    assert first.details["requests_made"] == 9
    assert first.details["directory_requests"] == 7
    assert first.details["artifact_probe_requests"] == 2
    assert first.details["stable_contract_sha256"] == sha256_fingerprint(
        first.details["stable_contract"]
    )
    assert first.details["stable_schema_sha256"] == sha256_fingerprint(
        first.details["schema_contract"]
    )
    assert first.schema_sha256 == MONITOR_HASHES[
        "monitor_stable_schema_sha256"
    ]
    assert first.details["stable_contract_sha256"] == MONITOR_HASHES[
        "monitor_stable_contract_sha256"
    ]
    assert first.artifact_sha256 == MONITOR_HASHES[
        "monitor_artifact_identity_sha256"
    ]
    drift = compare_probes(
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
    assert drift["drift_detected"] is False


def test_catalog_and_census_separate_source_coverage_from_projection(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    census = PublicRecordsCensus(catalog_path)

    assert catalog.require_machine_acquisition(florida.SOURCE_ID)[
        "allowed"
    ] is True
    manifest = catalog.show_source(florida.SOURCE_ID)[
        "current_manifest"
    ]
    capabilities = {
        capability["name"]: capability["details"]
        for capability in manifest["capabilities"]
    }
    assert capabilities["query_shared_property_records"][
        "shared_operations"
    ] == [
        "discovery",
        "download",
        "manifest",
        "probe",
        "releases",
    ]
    assert manifest["source_coverage"] == {
        "geography": "statewide",
        "county_count": 67,
        "county_release_grain": (
            "one_archive_per_county_dataset_year_and_stage"
        ),
        "assessment_components": ["nal", "sdf"],
        "parcel_geometry_components": ["gis-pin", "gis-par"],
        "release_stages": ["preliminary", "final"],
    }
    maturity = manifest["implementation_maturity"]
    assert maturity["gis_pin_dbf_join_and_crs_preservation"] == (
        "implemented"
    )
    assert maturity["shapefile_geometry_decoding"] == "follow_up"
    assert maturity["shapefile_geometry_follow_up_infra_request"] == 314
    assert {
        field: manifest["probe_evidence"][field]
        for field in MONITOR_HASHES
    } == MONITOR_HASHES
    assert capabilities["ingest_release_archives"][
        "recorded_title_instruments_created"
    ] is False
    assert capabilities["ingest_release_archives"][
        "parcel_geometry_rows_created"
    ] is False

    associations = {
        association["role"]: association
        for association in manifest["census_associations"]
    }
    assert set(associations) == {
        "assessment_roll",
        "parcel_geometry",
    }
    assert associations["assessment_roll"]["coverage"]["statewide"] is True
    assert associations["assessment_roll"]["coverage"]["counties"] == (
        "all_67_counties"
    )
    geometry = associations["parcel_geometry"]
    assert geometry["coverage"]["statewide"] is True
    assert geometry["coverage"]["source_geometry_type"] == "polygon"
    assert geometry["coverage"]["current_ingest_projection"] == (
        "dbf_join_rows_and_crs_without_decoded_geometry"
    )
    assert "infrastructure request #314" in geometry["notes"]

    assessment_target = census.list_targets(
        state="FL",
        domain="property",
        role="assessment_roll",
    )[0]
    geometry_target = census.list_targets(
        state="FL",
        domain="property",
        role="parcel_geometry",
    )[0]
    assert florida.SOURCE_ID in assessment_target["source_ids"]
    assert florida.SOURCE_ID in geometry_target["source_ids"]


def test_catalog_shared_operation_audit_and_monitor_registry(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    audit = audit_catalog(db_path=catalog_path)
    mismatches = {
        item["source_id"]: item
        for item in audit["shared_adapter_operation_mismatches"]
    }

    assert florida.SOURCE_ID not in mismatches
    handler = public_records_monitor.HANDLER_REGISTRY[
        florida.SOURCE_ID
    ]
    assert handler.handler is public_records_monitor.probe_fl_dor_property
    assert handler.endpoint == florida.SOURCE_PAGE
    assert handler.expected_requests == 9
    assert handler.sentinel_record_count == 3
    assert handler.sample_bytes == 4096


def test_docs_and_citation_cover_release_and_ingest_lifecycle() -> None:
    source_urls = json.loads(
        (
            ROOT / "web" / "src" / "data" / "source-urls.json"
        ).read_text(encoding="utf-8")
    )
    assert source_urls[
        f"PROPERTY_SOURCE:{florida.SOURCE_ID}"
    ] == florida.SOURCE_PAGE

    property_docs = (
        ROOT / "docs" / "modules" / "property.md"
    ).read_text(encoding="utf-8")
    tool_reference = (
        ROOT / "docs" / "TOOL_REFERENCE.md"
    ).read_text(encoding="utf-8")
    for content in (property_docs, tool_reference):
        assert florida.SOURCE_ID in content
        assert "ingest_fl_dor_property.py" in content
        assert "infrastructure request #314" in content
