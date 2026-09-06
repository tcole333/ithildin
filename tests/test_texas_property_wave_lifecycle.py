from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_harris_property as hcad_property
from tools import query_hcad_gis
from tools import query_txgio_land_parcels as txgio
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_contract import sha256_fingerprint
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]
MAP_SCHEMA_SHA256 = "bdb42152479238b8096e1c369911504828df393b79b389081ae37a88de366c7c"
MONITOR_HASHES = {
    hcad_property.SOURCE_ID: {
        "monitor_stable_schema_sha256": (
            "d58cfc5841ca59b53fe9206574f01c724cbf0ba251ec13c2ac0f7751fb2f4557"
        ),
        "monitor_stable_contract_sha256": (
            "5796efba2cf4d3287955bb66d3840164ac03be9bb13fa9319bc7acc289e6df88"
        ),
        "monitor_artifact_identity_sha256": (
            "3a2b7436192a5a1b985ae369e9628fad7e0f153d9bbea0e2790ed8983ce4427f"
        ),
    },
    query_hcad_gis.SOURCE_ID: {
        "monitor_stable_schema_sha256": (
            "84a657170f248002c871269b7b8f50e929faa3ec833b4a89d135fedf57ea787d"
        ),
        "monitor_stable_contract_sha256": (
            "eedfbe021cb86d85bf34b124888604f152f49208adb4dfd8967025dbd5d234b2"
        ),
        "monitor_artifact_identity_sha256": (
            "07481f5f0d5698367e84875c0a4efcfcb19bfc2cebe30c6d84367dbf4bf547d4"
        ),
    },
    txgio.SOURCE_ID: {
        "monitor_stable_schema_sha256": (
            "8fb668148cd9dd89fe8912fd8a6845596f2d9e78b1b5022db778a7357b3a385a"
        ),
        "monitor_stable_contract_sha256": (
            "15741a6a4b69b719620b9be0dbbf134352e7aa41819f456a64ae3ad3b901e3ea"
        ),
        "monitor_artifact_identity_sha256": (
            "2c658dc76fb617c9cfe8fcf97daeb4a4d4efc0252d0ce0f86fcb0e4b1860e1ad"
        ),
    },
}


def _context(source_id: str) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.1},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=4096,
    )


def _artifact_probe(marker: str, size: int) -> dict[str, Any]:
    return {
        "url": f"https://example.test/{marker}.zip",
        "http_status": 206,
        "content_length": size,
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
    }


def _hcad_property_snapshot(marker: str) -> dict[str, Any]:
    return {
        "available_tax_year_count": 22,
        "available_tax_years": [2026, 2025],
        "current_tax_year": 2026,
        "certification": {
            "tax_year": 2026,
            "certification_status": ("preliminary" if marker == "a" else "certified"),
            "last_updated_date": f"2026-07-{marker}",
        },
        "real_property_artifact_count": 5,
        "real_property_artifact_filenames": [
            "Code_description_real.zip",
            "Real_acct_owner.zip",
            "Real_acct_ownership_history.zip",
            "Real_building_land.zip",
            "Real_jur_exempt.zip",
        ],
        "sentinel_artifact": {
            "filename": "Real_acct_owner.zip",
            "label": "Owner",
            "description": marker,
            "probe": _artifact_probe(marker, 100 if marker == "a" else 200),
        },
        "requests_made": 5,
        "manifest_requests": 3,
        "artifact_probe_requests": 2,
    }


def _hcad_gis_snapshot(marker: str) -> dict[str, Any]:
    return {
        "bulk": {
            "release_id": f"current:2026-07-{marker}",
            "last_updated": f"2026-07-{marker}",
            "component_artifact_count": 23,
            "combined_bundle_count": 1,
            "artifact_count": 24,
            "artifact_filenames": ["GIS_Public.zip", "Parcels.zip"],
            "historical_snapshot_years": [2025, 2024, 2023, 2022, 2021],
            "parcels_artifact_probe": _artifact_probe(
                marker,
                100 if marker == "a" else 200,
            ),
        },
        "mapserver": {
            "layer_url": query_hcad_gis.MAPSERVER_LAYER_URL,
            "schema_sha256": MAP_SCHEMA_SHA256,
            "max_record_count": 1000,
            "total_feature_count": 1 if marker == "a" else 2,
            "tax_year_values": [2025, None],
            "sentinel": {
                "OBJECTID": 1,
                "HCAD_NUM": "100",
                "acct_num": "100",
                "tax_year": 2025,
                "GlobalID": marker,
            },
        },
        "requests_made": 10,
        "manifest_requests": 4,
        "artifact_probe_requests": 2,
        "mapserver_requests": 4,
    }


def _txgio_snapshot(marker: str) -> dict[str, Any]:
    return {
        "release_count": 6,
        "collection": {
            "collection_id": marker,
            "acquisition_date": f"2025-06-{marker}",
            "publication_date": f"2025-09-{marker}",
            "availability": "full",
            "file_type": "zip",
            "spatial_reference": "source",
            "license_name": "CC0",
            "license_abbreviation": "CC0",
            "county_count_declared": 253,
        },
        "resource_count": 254,
        "county_artifact_count": 253,
        "statewide_artifact_count": 1,
        "missing_counties": ["Donley"],
        "sentinel": {
            "resource_id": marker,
            "filename": f"kenedy-{marker}.zip",
            "expected_size": 100 if marker == "a" else 200,
            "scope": "county",
            "jurisdiction_fips": "48261",
            "county_fips": "48261",
            "county_name": "Kenedy",
            "probe": _artifact_probe(marker, 100 if marker == "a" else 200),
        },
        "statewide_aggregate": {
            "resource_id": f"state-{marker}",
            "filename": f"texas-{marker}.zip",
            "expected_size": 1000 if marker == "a" else 2000,
            "scope": "state",
            "jurisdiction_fips": "48",
        },
        "requests_made": 4,
        "manifest_requests": 2,
        "artifact_probe_requests": 2,
    }


def _hashes(observation: Any) -> dict[str, str | None]:
    return {
        "monitor_stable_schema_sha256": observation.schema_sha256,
        "monitor_stable_contract_sha256": observation.details["stable_contract_sha256"],
        "monitor_artifact_identity_sha256": observation.artifact_sha256,
    }


def test_monitors_keep_rolling_release_changes_out_of_stable_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = "a"
    monkeypatch.setattr(
        public_records_monitor,
        "_hcad_property_manifest_snapshot",
        lambda _context: _hcad_property_snapshot(rolling),
    )
    monkeypatch.setattr(
        public_records_monitor,
        "_hcad_gis_snapshot",
        lambda _context: _hcad_gis_snapshot(rolling),
    )
    monkeypatch.setattr(
        public_records_monitor,
        "_txgio_land_parcels_snapshot",
        lambda _context: _txgio_snapshot(rolling),
    )
    probe_functions = {
        hcad_property.SOURCE_ID: public_records_monitor.probe_hcad_property,
        query_hcad_gis.SOURCE_ID: public_records_monitor.probe_hcad_gis,
        txgio.SOURCE_ID: public_records_monitor.probe_txgio_land_parcels,
    }
    first = {
        source_id: probe(_context(source_id))
        for source_id, probe in probe_functions.items()
    }
    rolling = "b"
    second = {
        source_id: probe(_context(source_id))
        for source_id, probe in probe_functions.items()
    }

    for source_id in probe_functions:
        before = first[source_id]
        after = second[source_id]
        assert before.status == "ok"
        assert before.schema_sha256 == after.schema_sha256
        assert before.artifact_sha256 == after.artifact_sha256
        assert before.details["stable_contract"] == after.details["stable_contract"]
        assert before.details["schema_contract"] == after.details["schema_contract"]
        assert before.details["artifact_identity"] == after.details["artifact_identity"]
        assert (
            before.details["rolling_observation"]
            != after.details["rolling_observation"]
        )
        assert before.details["stable_contract_sha256"] == (
            sha256_fingerprint(before.details["stable_contract"])
        )
        assert before.details["stable_schema_sha256"] == (
            sha256_fingerprint(before.details["schema_contract"])
        )
        drift = compare_probes(
            {
                "probe_id": 1,
                "status": before.status,
                "schema_sha256": before.schema_sha256,
                "artifact_sha256": before.artifact_sha256,
            },
            {
                "probe_id": 2,
                "status": after.status,
                "schema_sha256": after.schema_sha256,
                "artifact_sha256": after.artifact_sha256,
            },
        )
        assert drift["drift_detected"] is False

    assert {
        source_id: _hashes(observation) for source_id, observation in first.items()
    } == MONITOR_HASHES
    assert first[hcad_property.SOURCE_ID].details["requests_made"] == 5
    assert first[query_hcad_gis.SOURCE_ID].details["requests_made"] == 10
    assert first[txgio.SOURCE_ID].details["requests_made"] == 4


def test_catalog_census_and_shared_operations_preserve_source_boundaries(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    census = PublicRecordsCensus(catalog_path)

    expected_operations = {
        hcad_property.SOURCE_ID: [
            "discovery",
            "download",
            "manifest",
            "probe",
            "releases",
        ],
        query_hcad_gis.SOURCE_ID: [
            "account",
            "address",
            "discovery",
            "download",
            "manifest",
            "map",
            "owner",
            "parcel",
            "probe",
            "releases",
            "search",
        ],
        txgio.SOURCE_ID: [
            "address",
            "discovery",
            "download",
            "manifest",
            "map",
            "owner",
            "parcel",
            "probe",
            "releases",
            "search",
        ],
    }
    manifests: dict[str, dict[str, Any]] = {}
    for source_id, operations in expected_operations.items():
        assert catalog.require_machine_acquisition(source_id)["allowed"] is True
        manifest = catalog.show_source(source_id)["current_manifest"]
        manifests[source_id] = manifest
        capabilities = {
            item["name"]: item["details"] for item in manifest["capabilities"]
        }
        assert (
            capabilities["query_shared_property_records"]["shared_operations"]
            == operations
        )

    assert manifests[hcad_property.SOURCE_ID]["identity_contract"][
        "clerk_reference_boundary"
    ]["controlling_title_source"] == ("Harris County Clerk real-property instruments")
    assert manifests[query_hcad_gis.SOURCE_ID]["publication_contract"][
        "freshness_fields_are_separate"
    ] == ["bulk_last_updated", "mapserver_tax_year"]
    assert (
        manifests[query_hcad_gis.SOURCE_ID]["implementation_maturity"][
            "local_filegeodatabase_feature_extraction"
        ]
        == "implemented_dependency_backed"
    )
    assert (
        manifests[query_hcad_gis.SOURCE_ID]["implementation_maturity"][
            "local_filegeodatabase_normalized_HCAD_projection"
        ]
        == "follow_up"
    )
    assert (
        manifests[query_hcad_gis.SOURCE_ID]["implementation_maturity"][
            "generic_shapefile_geometry_decoding"
        ]
        == "implemented"
    )
    assert manifests[txgio.SOURCE_ID]["source_coverage"] == {
        "geography": "Texas",
        "state_geoid": "48",
        "expected_county_count": 254,
        "resource_count": 254,
        "county_artifact_count": 253,
        "statewide_artifact_count": 1,
        "observed_missing_counties": ["Donley"],
        "current_collection_id": "0fa04328-872e-481c-b453-126a74777593",
        "current_acquisition_date": "2025-06-01",
        "current_publication_date": "2025-09-11",
        "source_geometry_type": "polygon",
    }
    assert (
        manifests[txgio.SOURCE_ID]["publication_contract"]["map_operation_result"]
        == "aligned_shapefile_reference_not_decoded_geometry"
    )
    assert (
        manifests[txgio.SOURCE_ID]["implementation_maturity"][
            "shapefile_geometry_follow_up_infra_request"
        ]
        == 314
    )
    for source_id, expected in MONITOR_HASHES.items():
        assert {
            field: manifests[source_id]["probe_evidence"][field] for field in expected
        } == expected

    assessment_target = census.list_targets(
        state="TX",
        domain="property",
        role="assessment_roll",
    )[0]
    geometry_target = census.list_targets(
        state="TX",
        domain="property",
        role="parcel_geometry",
    )[0]
    assert {
        hcad_property.SOURCE_ID,
        query_hcad_gis.SOURCE_ID,
        txgio.SOURCE_ID,
    }.issubset(assessment_target["source_ids"])
    assert {
        query_hcad_gis.SOURCE_ID,
        txgio.SOURCE_ID,
    }.issubset(geometry_target["source_ids"])


def test_catalog_audit_monitor_registry_docs_and_citations(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    audit = audit_catalog(db_path=catalog_path)
    mismatches = {
        item["source_id"] for item in audit["shared_adapter_operation_mismatches"]
    }
    assert {
        hcad_property.SOURCE_ID,
        query_hcad_gis.SOURCE_ID,
        txgio.SOURCE_ID,
    }.isdisjoint(mismatches)

    registry_expectations = {
        hcad_property.SOURCE_ID: (
            public_records_monitor.probe_hcad_property,
            5,
        ),
        query_hcad_gis.SOURCE_ID: (
            public_records_monitor.probe_hcad_gis,
            10,
        ),
        txgio.SOURCE_ID: (
            public_records_monitor.probe_txgio_land_parcels,
            4,
        ),
    }
    for source_id, (handler, requests) in registry_expectations.items():
        spec = public_records_monitor.HANDLER_REGISTRY[source_id]
        assert spec.handler is handler
        assert spec.expected_requests == requests
        assert spec.sentinel_record_count == 1
        assert spec.sample_bytes == 4096

    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(encoding="utf-8")
    )
    expected_urls = {
        hcad_property.SOURCE_ID: hcad_property.SOURCE_PAGE,
        query_hcad_gis.SOURCE_ID: query_hcad_gis.SOURCE_PAGE,
        txgio.SOURCE_ID: txgio.LANDING_URL,
    }
    for source_id, url in expected_urls.items():
        assert source_urls[f"PROPERTY_SOURCE:{source_id}"] == url

    property_docs = (ROOT / "docs" / "modules" / "property.md").read_text(
        encoding="utf-8"
    )
    tool_reference = (ROOT / "docs" / "TOOL_REFERENCE.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md").read_text(
        encoding="utf-8"
    )
    for content in (property_docs, tool_reference, roadmap):
        assert hcad_property.SOURCE_ID in content
        assert query_hcad_gis.SOURCE_ID in content
        assert txgio.SOURCE_ID in content
    assert "ingest_hcad_property.py" in property_docs
    assert "public_records_filegdb.py" in property_docs
    assert "native-FID feature pages" in property_docs
    assert "public_records_shapefile.py" in tool_reference
