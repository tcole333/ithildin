from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_georgia_court_data as georgia
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import seed_catalog


ROOT = Path(__file__).resolve().parents[1]


def _context(source_id: str) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.5},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _dashboard_probe_record(marker: str) -> dict[str, Any]:
    return {
        "source_id": georgia.DASHBOARD_SOURCE_ID,
        "record_kind": "source_probe",
        "status": "ok",
        "dashboard_count": 6,
        "court_classes": list(georgia.COURT_CLASSES),
        "dashboard_user_guide_url": (
            "https://research.georgiacourts.gov/"
            f"wp-content/uploads/dashboard-guide-{marker}.pdf"
        ),
        "export_request_url": georgia.EXPORT_REQUEST_URL,
        "individual_case_records": False,
        "source_document_sha256": marker * 64,
        "stable_schema_sha256": "1" * 64,
    }


def _workload_probe_record(marker: str) -> dict[str, Any]:
    return {
        "source_id": georgia.WORKLOAD_SOURCE_ID,
        "record_kind": "source_probe",
        "status": "ok",
        "publication_count": 7,
        "publication_years": list(range(2024, 2017, -1)),
        "latest_publication_year": 2024,
        "latest_artifact_url": (
            "https://research.georgiacourts.gov/"
            "wp-content/uploads/2024-workload.pdf"
        ),
        "latest_artifact_sha256": marker * 64,
        "latest_artifact_byte_length": 1_032_026,
        "source_document_sha256": marker * 64,
        "stable_schema_sha256": "2" * 64,
    }


def test_monitors_separate_aggregate_contracts_from_rolling_publications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    markers = {
        georgia.DASHBOARD_SOURCE_ID: "a",
        georgia.WORKLOAD_SOURCE_ID: "b",
    }
    calls: list[str] = []

    def fake_execute(
        args: Any,
        **_: Any,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        calls.append(args.source)
        if args.source == georgia.DASHBOARD_SOURCE_ID:
            record = _dashboard_probe_record(markers[args.source])
        else:
            record = _workload_probe_record(markers[args.source])
        return PublicRecordsResult.success(
            georgia.build_query(args),
            [record],
        )

    monkeypatch.setattr(georgia, "execute", fake_execute)

    first_dashboard = (
        public_records_monitor.probe_georgia_court_data_source(
            _context(georgia.DASHBOARD_SOURCE_ID)
        )
    )
    first_workload = (
        public_records_monitor.probe_georgia_court_data_source(
            _context(georgia.WORKLOAD_SOURCE_ID)
        )
    )
    markers.update(
        {
            georgia.DASHBOARD_SOURCE_ID: "c",
            georgia.WORKLOAD_SOURCE_ID: "d",
        }
    )
    second_dashboard = (
        public_records_monitor.probe_georgia_court_data_source(
            _context(georgia.DASHBOARD_SOURCE_ID)
        )
    )
    second_workload = (
        public_records_monitor.probe_georgia_court_data_source(
            _context(georgia.WORKLOAD_SOURCE_ID)
        )
    )

    assert calls == [
        georgia.DASHBOARD_SOURCE_ID,
        georgia.WORKLOAD_SOURCE_ID,
        georgia.DASHBOARD_SOURCE_ID,
        georgia.WORKLOAD_SOURCE_ID,
    ]
    for first, second, requests_made in (
        (first_dashboard, second_dashboard, 1),
        (first_workload, second_workload, 2),
    ):
        assert first.status == "ok"
        assert first.schema_sha256 == second.schema_sha256
        assert first.artifact_sha256 == second.artifact_sha256
        assert first.details["stable_contract"] == (
            second.details["stable_contract"]
        )
        assert first.details["schema_contract"] == (
            second.details["schema_contract"]
        )
        assert first.details["artifact_identity"] == (
            second.details["artifact_identity"]
        )
        assert first.details["rolling_observation"] != (
            second.details["rolling_observation"]
        )
        assert first.details["requests_made"] == requests_made

    assert first_dashboard.result_count == 6
    assert first_dashboard.details["stable_contract"][
        "aggregate_scope"
    ]["individual_case_records"] is False
    assert first_workload.result_count == 7
    assert first_workload.details["stable_contract"][
        "baseline_years"
    ] == list(range(2018, 2025))


def test_catalog_census_and_shared_operations_preserve_aggregate_grain(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    dashboard = catalog.show_source(
        georgia.DASHBOARD_SOURCE_ID
    )["current_manifest"]
    workload = catalog.show_source(
        georgia.WORKLOAD_SOURCE_ID
    )["current_manifest"]

    assert catalog.require_machine_acquisition(
        georgia.DASHBOARD_SOURCE_ID
    )["allowed"] is True
    assert catalog.require_machine_acquisition(
        georgia.WORKLOAD_SOURCE_ID
    )["allowed"] is True
    assert dashboard["stable_keys"] == ["canonical_ref"]
    assert workload["stable_keys"] == ["canonical_ref"]
    assert dashboard["identity_contract"][
        "source_identity_fields"
    ] == ["canonical_ref"]
    assert workload["identity_contract"][
        "source_identity_fields"
    ] == ["canonical_ref"]

    dashboard_capabilities = {
        item["name"]: item["details"]
        for item in dashboard["capabilities"]
    }
    workload_capabilities = {
        item["name"]: item["details"]
        for item in workload["capabilities"]
    }
    assert dashboard_capabilities["query_shared_court_records"][
        "shared_operations"
    ] == ["search", "discovery", "probe"]
    assert workload_capabilities["query_shared_court_records"][
        "shared_operations"
    ] == ["search", "documents", "detail", "probe"]
    assert workload_capabilities["query_shared_court_records"][
        "download_operation"
    ] == "not_exposed"
    assert dashboard_capabilities["ingest_state_court_records"][
        "projection"
    ] == "source_snapshot_only"
    assert workload_capabilities["ingest_state_court_records"][
        "projection"
    ] == "source_snapshot_only"

    dashboard_association = dashboard["census_associations"][0]
    assert dashboard_association["jurisdiction_geoid"] == "13"
    assert dashboard_association["role"] == "bulk_data_program"
    assert dashboard_association["coverage"]["dashboard_count"] == 6
    assert dashboard_association["coverage"][
        "individual_case_records"
    ] is False
    assert dashboard["publication_contract"]["export_handoff"][
        "available_years"
    ] == [2021, 2022, 2023, 2024, 2025]
    assert dashboard["publication_contract"]["export_handoff"][
        "submission_performed"
    ] is False
    assert dashboard["probe_evidence"][
        "source_document_sha256"
    ] == "8c22c8ad1e4e1bf0d911d8b8044166075797deebd330512ea721ead32e201129"

    workload_association = workload["census_associations"][0]
    assert workload_association["jurisdiction_geoid"] == "13"
    assert workload_association["role"] == "bulk_data_program"
    assert workload_association["coverage"][
        "publication_years"
    ] == list(range(2018, 2025))
    assert workload_association["coverage"][
        "individual_case_records"
    ] is False
    assert workload["probe_evidence"][
        "latest_artifact_byte_length"
    ] == 1_032_026
    assert workload["probe_evidence"][
        "latest_artifact_sha256"
    ] == "21afb894a332aa67bbef46cecfa50a8721fbfee95392d0a711d57a6de8c4c099"


def test_monitor_registry_has_source_specific_request_budgets() -> None:
    dashboard = public_records_monitor.HANDLER_REGISTRY[
        georgia.DASHBOARD_SOURCE_ID
    ]
    workload = public_records_monitor.HANDLER_REGISTRY[
        georgia.WORKLOAD_SOURCE_ID
    ]

    assert dashboard.handler is (
        public_records_monitor.probe_georgia_court_data_source
    )
    assert dashboard.endpoint == georgia.DATA_URL
    assert dashboard.expected_requests == 1
    assert dashboard.sentinel_record_count == 1

    assert workload.handler is (
        public_records_monitor.probe_georgia_court_data_source
    )
    assert workload.endpoint == georgia.DATA_URL
    assert workload.expected_requests == 2
    assert workload.sentinel_record_count == 1


def test_citations_and_docs_cover_both_aggregate_sources() -> None:
    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_urls[
        f"STATECOURT_SOURCE:{georgia.DASHBOARD_SOURCE_ID}"
    ] == georgia.DATA_URL
    assert source_urls[
        f"STATECOURT_SOURCE:{georgia.WORKLOAD_SOURCE_ID}"
    ] == georgia.DATA_URL

    for relative_path in (
        "docs/modules/legal.md",
        "docs/TOOL_REFERENCE.md",
    ):
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        assert georgia.DASHBOARD_SOURCE_ID in content
        assert georgia.WORKLOAD_SOURCE_ID in content
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")
    assert "Georgia AOC aggregate court data" in roadmap
    assert "unsubmitted state" in roadmap
