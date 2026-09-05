from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_ny_attorneys as attorneys
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import seed_catalog


ROOT = Path(__file__).resolve().parents[1]


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=attorneys.SOURCE_ID,
        catalog_decision={"limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _probe_record(version: int) -> dict[str, Any]:
    rows_updated_at = 1_785_387_837 + version
    rows_updated_iso = f"2026-07-30T0{version}:03:57Z"
    response_schema = "2" * 64
    sentinel = {
        "record_kind": "attorney_registration",
        "source_id": attorneys.SOURCE_ID,
        "dataset_id": attorneys.DATASET_ID,
        "source_record_id": attorneys.PROBE_REGISTRATION_NUMBER,
        "canonical_ref": (
            f"{attorneys.SOURCE_ID}:registration:"
            f"{attorneys.PROBE_REGISTRATION_NUMBER}"
        ),
        "native_ids": {
            "registration_number": attorneys.PROBE_REGISTRATION_NUMBER,
        },
        "name": {
            "display": f"Example Attorney {version}",
            "first": "Example",
            "middle": None,
            "last": f"Attorney {version}",
            "suffix": None,
        },
        "registration": {
            "status": "Currently registered",
            "year_admitted": 1999,
        },
        "organization": {
            "name": f"ACME HOLDINGS, LLC {version}",
            "relationship": "registered_office_or_employer",
        },
        "office": {
            "city": "New York",
            "state": "NY",
        },
        "source_snapshot": {
            "posting_frequency": "quarterly",
            "rows_updated_at_epoch": rows_updated_at,
            "rows_updated_at": rows_updated_iso,
            "declared_schema_fingerprint": "1" * 64,
            "response_schema_fingerprint": response_schema,
        },
        "source_urls": {
            "dataset": attorneys.DATASET_URL,
            "api": attorneys.QUERY_URL,
        },
        "complementary_routes": [
            {
                "name": "Unified Court System interactive Attorney Directory",
                "url": attorneys.INTERACTIVE_DIRECTORY_URL,
            },
            {
                "name": "22 NYCRR 118.2 written-request registration data",
                "url": attorneys.PUBLIC_ACCESS_RULE_URL,
            },
            {
                "name": "NYSCEF civil case filings",
                "url": attorneys.NYSCEF_URL,
            },
        ],
        "raw_record": {
            "registration_number": attorneys.PROBE_REGISTRATION_NUMBER,
            "company_name": f"ACME HOLDINGS, LLC {version}",
        },
    }
    request_breakdown = {
        "initial_metadata": 1,
        "matching_count": 1,
        "sentinel_query": 1,
        "final_metadata": 1,
        "total_count": 1,
    }
    return {
        "record_kind": "source_probe",
        "source_id": attorneys.SOURCE_ID,
        "dataset_id": attorneys.DATASET_ID,
        "dataset_name": "Attorney Registrations",
        "total_registration_rows": 432_566 + version,
        "declared_field_count": len(attorneys.EXPECTED_FIELDS),
        "declared_fields": list(attorneys.EXPECTED_FIELDS),
        "declared_schema_fingerprint": "1" * 64,
        "rows_updated_at_epoch": rows_updated_at,
        "rows_updated_at": rows_updated_iso,
        "requests_made": sum(request_breakdown.values()),
        "request_breakdown": request_breakdown,
        "sentinel": sentinel,
    }


def _probe_query() -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=attorneys.SOURCE_METADATA,
        jurisdiction=attorneys.JURISDICTION,
        query=QueryMetadata(
            operation="probe",
            parameters={
                "sentinel_registration_number": (
                    attorneys.PROBE_REGISTRATION_NUMBER
                )
            },
        ),
    )


def test_monitor_separates_stable_contract_from_rolling_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"version": 1}
    calls: list[Any] = []

    def fake_execute(
        args: Any,
        *,
        log_results: bool = True,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert args.minimum_interval == 0
        assert args.retry_attempts == 1
        assert log_results is False
        calls.append(args)
        return PublicRecordsResult.success(
            _probe_query(),
            [_probe_record(state["version"])],
        )

    monkeypatch.setattr(attorneys, "execute", fake_execute)

    first = (
        public_records_monitor.probe_ny_oca_attorney_registrations(
            _context()
        )
    )
    state["version"] = 2
    second = (
        public_records_monitor.probe_ny_oca_attorney_registrations(
            _context()
        )
    )

    assert len(calls) == 2
    assert first.status == "ok"
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
    assert first.result_count == 432_567
    assert second.result_count == 432_568
    assert first.details["requests_made"] == 5
    assert first.details["request_breakdown"] == {
        "initial_metadata": 1,
        "matching_count": 1,
        "sentinel_query": 1,
        "final_metadata": 1,
        "total_count": 1,
    }
    assert first.details["stable_contract"]["registration_identity"] == {
        "field": "registration_number",
        "record_kind": "attorney_registration",
        "sentinel_registration_number": (
            attorneys.PROBE_REGISTRATION_NUMBER
        ),
        "organization_name_semantics": "whole publisher field",
        "case_projection": False,
    }


def test_catalog_census_and_capabilities_match_adapter_contract(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    manifest = catalog.show_source(attorneys.SOURCE_ID)["current_manifest"]
    decision = catalog.require_machine_acquisition(attorneys.SOURCE_ID)

    assert decision["allowed"] is True
    assert decision["limits"] == {}
    assert manifest["stable_keys"] == ["registration_number"]
    assert manifest["identity_contract"][
        "source_identity_fields"
    ] == ["source_id", "dataset_id", "registration_number"]
    assert manifest["identity_contract"][
        "organization_name_semantics"
    ] == "whole_publisher_field"
    assert manifest["identity_contract"]["case_projection"] is False
    assert manifest["identity_contract"]["snapshot_fields"] == [
        "rows_updated_at_epoch",
        "rows_updated_at",
        "declared_schema_fingerprint",
        "response_schema_fingerprint",
    ]
    publication = manifest["publication_contract"]
    assert publication["record_grain"] == "attorney_registration"
    assert publication[
        "interactive_directory_remains_separately_attributed"
    ] is True
    assert publication[
        "written_request_data_remains_separately_attributed"
    ] is True
    assert publication[
        "discipline_decisions_remain_separate_records"
    ] is True
    assert publication["nyscef_filings_remain_separate_records"] is True

    capabilities = {
        item["name"]: item["details"]
        for item in manifest["capabilities"]
    }
    search = capabilities["search_attorney_registrations"]
    assert search["default_result_cap"] is None
    assert search["continuation_binding"] == [
        "criteria",
        "declared_schema",
        "rows_updated_at",
        "matching_total",
        "offset",
        "checksum",
    ]
    assert capabilities["fetch_exact_attorney_registration"][
        "selector"
    ] == "exact_registration_number"
    shared = capabilities["query_shared_court_records"]
    assert shared["shared_operations"] == [
        "search",
        "detail",
        "discovery",
        "probe",
    ]
    assert shared["case_operations_exposed"] is False
    assert "ingest_state_court_records" not in capabilities
    assert capabilities["probe_source"]["expected_requests"] == 5
    assert capabilities["probe_source"]["stable_contract"] == [
        "dataset_identity",
        "registration_identity",
        "declared_fields",
        "declared_schema",
        "response_schema",
        "cursor_contract",
        "complementary_route_identity",
    ]
    assert capabilities["probe_source"]["rolling_observations"] == [
        "total_registration_rows",
        "rows_updated_at",
        "sentinel_record_contents",
    ]

    association = manifest["census_associations"][0]
    assert association["jurisdiction_geoid"] == "36"
    assert association["role"] == "attorney_registration_index"
    assert association["coverage"]["statewide"] is True
    assert association["coverage"]["identity_key"] == (
        "registration_number"
    )
    assert association["coverage"][
        "exact_detail_by_registration_number"
    ] is True
    assert association["coverage"]["case_projection"] is False

    complements = manifest["official_complements"]
    assert all(item["dataset_equivalent"] is False for item in complements)
    assert {
        item.get("route_id")
        for item in complements
        if item.get("route_id")
    } == {
        "us-ny-oca-interactive-attorney-directory",
        "us-ny-oca-attorney-registration-written-requests",
        "us-ny-appellate-division-attorney-discipline",
    }
    assert {
        item.get("source_id")
        for item in complements
        if item.get("source_id")
    } == {"us-ny-nyscef"}
    assert manifest["probe_evidence"]["observed_request_count"] == 5
    assert manifest["probe_evidence"]["request_breakdown"] == {
        "initial_metadata": 1,
        "matching_count": 1,
        "sentinel_query": 1,
        "final_metadata": 1,
        "total_count": 1,
    }


def test_monitor_registry_has_real_five_request_probe() -> None:
    spec = public_records_monitor.HANDLER_REGISTRY[attorneys.SOURCE_ID]

    assert spec.handler is (
        public_records_monitor.probe_ny_oca_attorney_registrations
    )
    assert spec.endpoint == attorneys.QUERY_URL
    assert spec.expected_requests == 5
    assert spec.sentinel_record_count == 1


def test_state_court_citation_and_docs_cover_source_lifecycle() -> None:
    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_urls[
        f"STATECOURT_SOURCE:{attorneys.SOURCE_ID}"
    ] == attorneys.DATASET_URL

    legal = (ROOT / "docs" / "modules" / "legal.md").read_text(
        encoding="utf-8"
    )
    tool_reference = (ROOT / "docs" / "TOOL_REFERENCE.md").read_text(
        encoding="utf-8"
    )
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")

    assert "## New York OCA attorney registrations" in legal
    assert "five-request lifecycle probe" in legal
    assert "Registration rows are not cases, dockets, or filings" in legal
    assert "### New York OCA attorney-registration adapter" in (
        tool_reference
    )
    assert attorneys.SOURCE_ID in tool_reference
    assert "New York OCA's quarterly attorney-registration snapshot" in (
        roadmap
    )
    assert (
        "open snapshot, interactive presentation, written-request delivery"
        in roadmap
    )
