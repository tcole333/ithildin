from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_census_acs as acs
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext
from tools.public_records_search_plan import build_search_plan
from tools.seed_public_records_catalog import seed_catalog


RETRIEVED_AT = "2026-07-30T12:00:00Z"


def test_catalog_preserves_acs_routes_and_same_release_identity(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    assert catalog.require_machine_acquisition(acs.SOURCE_ID)["allowed"] is True
    detail = catalog.show_source(acs.SOURCE_ID)
    assert detail["source"]["domain"] == "mixed"
    assert detail["source"]["source_status"] == "active"
    assert {capability["name"] for capability in detail["capabilities"]} == {
        "enrich_census_geography",
        "inspect_acs_variables",
        "list_acquisition_routes",
        "probe_source",
    }
    manifest = detail["current_manifest"]
    assert manifest["record_identity_source_id"] == acs.SOURCE_ID
    assert {
        "us-census-acs-summary-files",
        "us-census-reporter-acs-api",
        "us-census-geocoder",
        "us-census-tigerweb",
    } <= set(manifest["complementary_source_ids"])

    reporter = catalog.show_source("us-census-reporter-acs-api")
    assert reporter["current_manifest"]["record_identity_source_id"] == acs.SOURCE_ID
    assert (
        reporter["current_manifest"]["probe_evidence"][
            "counts_as_independent_corroboration"
        ]
        is False
    )


def test_planner_emits_one_geography_context_task_without_court_duplication(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Harbor Properties LLC",
        addresses=["100 Main Street, Towson, MD 21204"],
        jurisdictions=["24"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    tasks = [
        task
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
        if task["source_id"] == acs.SOURCE_ID
    ]

    assert len(tasks) == 1
    task = tasks[0]
    assert task["task_id"] == (f"property.{acs.SOURCE_ID}.enrich_census_geography")
    assert task["stage"] == "property_discovery"
    assert task["seed_parameters"]["geographies"] == ["24"]
    assert task["seed_parameters"]["addresses"] == ["100 Main Street, Towson, MD 21204"]
    assert "queries" not in task["seed_parameters"]
    assert not any(
        row["task_id"].startswith(f"court.{acs.SOURCE_ID}.")
        for stage in plan["workflow"]["stages"]
        for row in stage["tasks"]
    )


def test_monitor_separates_acs_contract_from_rolling_release_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {
        "population": 854535,
        "data_fingerprint": "a" * 64,
        "response_schema_fingerprint": "b" * 64,
        "backend": "census_reporter",
        "credential_present": False,
        "official_data_state": "free_api_key_needed",
        "fallback_state": "available",
    }

    def fake_execute(
        args: Any,
        *,
        access_decision: Any,
        log_results: bool,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert args.year == acs.DEFAULT_YEAR
        assert access_decision["allowed"] is True
        assert log_results is False
        query = acs._query("probe", {"year": args.year})
        record = {
            "source_id": acs.SOURCE_ID,
            "record_kind": "source_probe",
            "canonical_ref": "USCENSUS:ACS5:PROBE:fixture",
            "status": "ok",
            "operation_states": {
                "official_dataset_metadata": "available",
                "official_variable_metadata": "available",
                "official_data_query": rolling["official_data_state"],
                "keyless_census_reporter_fallback": rolling["fallback_state"],
                "official_bulk_summary_files": "available",
            },
            "backend": rolling["backend"],
            "credential_present": rolling["credential_present"],
            "release_id": f"acs{acs.DEFAULT_YEAR}_5yr",
            "period": f"{acs.DEFAULT_YEAR - 4}-{acs.DEFAULT_YEAR}",
            "dataset_identifier": "ACS5",
            "dataset_modified": "2025-01-01",
            "sentinel_full_geoid": "05000US24005",
            "sentinel_name": "Baltimore County, Maryland",
            "sentinel_population": rolling["population"],
            "response_schema_fingerprint": rolling["response_schema_fingerprint"],
            "data_fingerprint": rolling["data_fingerprint"],
        }
        return PublicRecordsResult.success(
            query,
            [record],
            retrieved_at=RETRIEVED_AT,
        )

    monkeypatch.setattr(acs, "execute", fake_execute)
    context = ProbeContext(
        source_id=acs.SOURCE_ID,
        catalog_decision={
            "allowed": True,
            "limits": {"minimum_interval_seconds": 0.25},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )
    first = public_records_monitor.probe_census_acs(context)
    rolling.update(
        population=855100,
        data_fingerprint="c" * 64,
        response_schema_fingerprint="d" * 64,
        backend="census_api",
        credential_present=True,
        official_data_state="available",
        fallback_state="not_used",
    )
    second = public_records_monitor.probe_census_acs(context)

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"]["sentinel_population"]
        != second.details["rolling_observation"]["sentinel_population"]
    )
    assert (
        first.details["rolling_observation"]["backend"]
        != second.details["rolling_observation"]["backend"]
    )
    assert (
        first.details["rolling_observation"]["response_schema_fingerprint"]
        != second.details["rolling_observation"]["response_schema_fingerprint"]
    )


def test_monitor_registry_exposes_the_bounded_acs_probe() -> None:
    spec = public_records_monitor.HANDLER_REGISTRY[acs.SOURCE_ID]
    assert spec.handler is public_records_monitor.probe_census_acs
    assert spec.capability == "probe_source"
    assert spec.expected_requests == 3
    assert spec.sentinel_record_count == 1
