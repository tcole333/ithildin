from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import public_records_monitor
from tools import query_harris_court_bulk as bulk
from tools import query_state_courts
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]
MONITOR_HASHES = {
    "monitor_stable_schema_sha256": (
        "1d2eed31f855de5dfba96e8c81997bbeb25f95abbfe861d78052d0665e649716"
    ),
    "monitor_stable_contract_sha256": (
        "faeaa48a955d45ee1b4a364e3c9062b032964163bf07245aea736e9c6f40a40a"
    ),
    "monitor_artifact_identity_sha256": (
        "e8e18fa69207e3e7801e0f99b2cb8e6d0dce14283e2d0d561da8385c6195d855"
    ),
}


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=bulk.SOURCE_ID,
        catalog_decision={
            "limits": {"minimum_interval_seconds": bulk.REQUEST_DELAY},
        },
        timeout=10,
        max_attempts=1,
        sample_bytes=bulk.DEFAULT_SAMPLE_BYTES,
    )


def test_catalog_census_shared_routes_and_citations_match_implementation(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed = seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    census = PublicRecordsCensus(catalog_path)
    manifest = catalog.show_source(bulk.SOURCE_ID)["current_manifest"]

    assert seed["sources_seen"] >= 1
    assert manifest["record_identity_source_id"] == bulk.SOURCE_ID
    capabilities = {
        item["name"]: item["details"] for item in manifest["capabilities"]
    }
    assert capabilities["query_shared_state_courts"][
        "shared_operations"
    ] == [
        "discovery",
        "documents",
        "download",
        "probe",
    ]
    assert sorted(query_state_courts.LIVE_ROUTES[bulk.SOURCE_ID]) == [
        "discovery",
        "documents",
        "download",
        "probe",
    ]
    assert capabilities["ingest_harris_court_bulk"][
        "supported_families"
    ] == [
        "Civil/activity",
        "Civil/case_summary",
        "Civil/party",
        "Criminal/dispositions",
        "Criminal/filings",
    ]
    assert capabilities["ingest_harris_court_bulk"][
        "filing_document_artifacts_created"
    ] is False
    assert capabilities["probe_source"]["expected_requests"] == 2
    assert {
        key: manifest["probe_evidence"][key] for key in MONITOR_HASHES
    } == MONITOR_HASHES

    associations = {
        item["role"]: item for item in manifest["census_associations"]
    }
    assert set(associations) == {"bulk_data_program", "trial_case_index"}
    assert associations["trial_case_index"]["coverage"]["county_fips"] == (
        "48201"
    )
    assert associations["trial_case_index"]["coverage"][
        "coverage_status"
    ] == "partial"
    assert associations["bulk_data_program"]["coverage"][
        "parser_families_implemented"
    ] == 5
    assert bulk.SOURCE_ID in next(
        target["source_ids"]
        for target in census.list_targets(
            state="TX",
            domain="court",
            role="trial_case_index",
        )
        if bulk.SOURCE_ID in target["source_ids"]
    )
    assert bulk.SOURCE_ID in next(
        target["source_ids"]
        for target in census.list_targets(
            state="TX",
            domain="court",
            role="bulk_data_program",
        )
        if bulk.SOURCE_ID in target["source_ids"]
    )

    observation = manifest["verified_ingest_observation"]
    assert observation["artifact_count"] == 5
    assert observation["source_row_occurrences"] == 18_419
    assert observation["unresolved_rows"] == 0
    assert observation["filing_document_artifacts"] == 0
    assert observation["repeat_import_new_rows"] == 0
    assert manifest["implementation_maturity"][
        "remaining_published_family_projection"
    ] == "follow_up"
    assert manifest["implementation_maturity"]["filing_document_retrieval"] == (
        "separate_source"
    )

    audit = audit_catalog(db_path=catalog_path)
    assert bulk.SOURCE_ID not in {
        item["source_id"]
        for item in audit["shared_adapter_operation_mismatches"]
    }
    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_urls[f"STATECOURT_SOURCE:{bulk.SOURCE_ID}"] == (
        "https://www.hcdistrictclerk.com/common/e-services/PublicDatasets.aspx"
    )


def test_lifecycle_documentation_names_occurrence_and_artifact_scopes() -> None:
    legal = (ROOT / "docs" / "modules" / "legal.md").read_text(
        encoding="utf-8"
    )
    tool_reference = (ROOT / "docs" / "TOOL_REFERENCE.md").read_text(
        encoding="utf-8"
    )

    for document in (legal, tool_reference):
        assert "ingest_harris_court_bulk.py" in document
        assert "source-row" in document
        assert "filing-document artifacts" in document
        for operation in ("`discovery`", "`documents`", "`download`", "`probe`"):
            assert operation in document


@pytest.mark.live_data
def test_live_monitor_matches_stable_lifecycle_hashes() -> None:
    observation = public_records_monitor.probe_harris_court_bulk(_context())

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
    assert observation.details["requests_made"] == 2
    assert observation.details["rolling_observation"]["catalog"][
        "artifact_count"
    ] >= 1
    assert observation.details["rolling_observation"]["sentinel"][
        "signature_hex"
    ] == "504b0304"
