from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import (
    ingest_state_court_records,
    query_georgia_court_data as georgia,
    query_state_courts,
)
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_store import connect_courts


def _shared_args(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def _envelope(
    source_id: str,
    operation: str,
    records: list[dict],
) -> dict:
    query = PublicRecordsQuery(
        source=georgia.SOURCE_BY_ID[source_id],
        jurisdiction=georgia.JURISDICTION,
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at="2026-07-30T21:00:00Z",
    ).to_dict()


def test_dashboard_routes_preserve_filter_cursor_handoff_and_probe() -> None:
    routes = query_state_courts.LIVE_ROUTES[
        georgia.DASHBOARD_SOURCE_ID
    ]
    cursor = "ga-court-data:v1:opaque-source-bound-cursor"

    search = routes["search"].translate(
        _shared_args(
            "search",
            "Superior",
            "--source",
            georgia.DASHBOARD_SOURCE_ID,
            "--jurisdiction",
            "GA",
            "--search-field",
            "court-class",
            "--limit",
            "2",
            "--cursor",
            cursor,
        ),
        routes["search"].adapter_command,
    )
    assert search.command == "dashboards"
    assert search.source == georgia.DASHBOARD_SOURCE_ID
    assert search.query == "Superior"
    assert search.limit == 2
    assert search.cursor == cursor
    assert search.minimum_interval == georgia.DEFAULT_MINIMUM_INTERVAL

    discovery = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "--source",
            georgia.DASHBOARD_SOURCE_ID,
            "--search-field",
            "export",
        ),
        routes["discovery"].adapter_command,
    )
    assert discovery.command == "handoff"
    assert discovery.source == georgia.DASHBOARD_SOURCE_ID

    probe = routes["probe"].translate(
        _shared_args(
            "probe",
            "--source",
            georgia.DASHBOARD_SOURCE_ID,
        ),
        routes["probe"].adapter_command,
    )
    assert probe.command == "probe"
    assert probe.source == georgia.DASHBOARD_SOURCE_ID
    assert set(routes) == {"discovery", "probe", "search"}


def test_workload_routes_separate_listing_metadata_from_exact_pdf_detail() -> None:
    routes = query_state_courts.LIVE_ROUTES[
        georgia.WORKLOAD_SOURCE_ID
    ]

    search = routes["search"].translate(
        _shared_args(
            "search",
            "2024",
            "--source",
            georgia.WORKLOAD_SOURCE_ID,
            "--search-field",
            "year",
            "--max-records",
            "3",
        ),
        routes["search"].adapter_command,
    )
    assert search.command == "workloads"
    assert search.source == georgia.WORKLOAD_SOURCE_ID
    assert search.year == 2024
    assert search.limit == 3

    documents = routes["documents"].translate(
        _shared_args(
            "documents",
            "*",
            "--source",
            georgia.WORKLOAD_SOURCE_ID,
            "--document-type",
            "pdf",
            "--limit",
            "4",
        ),
        routes["documents"].adapter_command,
    )
    assert documents.command == "workloads"
    assert documents.year is None
    assert documents.limit == 4

    detail = routes["detail"].translate(
        _shared_args(
            "detail",
            "2024",
            "--source",
            georgia.WORKLOAD_SOURCE_ID,
            "--search-field",
            "publication-year",
        ),
        routes["detail"].adapter_command,
    )
    assert detail.command == "document"
    assert detail.source == georgia.WORKLOAD_SOURCE_ID
    assert detail.year == 2024
    assert detail.artifact_output is None

    probe = routes["probe"].translate(
        _shared_args(
            "probe",
            "--source",
            georgia.WORKLOAD_SOURCE_ID,
            "--jurisdiction",
            "13",
        ),
        routes["probe"].adapter_command,
    )
    assert probe.command == "probe"
    assert probe.source == georgia.WORKLOAD_SOURCE_ID
    assert set(routes) == {"detail", "documents", "probe", "search"}
    assert "download" not in routes


def test_guidance_keeps_aggregate_source_roles_and_operations_distinct() -> None:
    dashboard = query_state_courts._source_guidance(
        georgia.DASHBOARD_SOURCE_ID
    )
    workload = query_state_courts._source_guidance(
        georgia.WORKLOAD_SOURCE_ID
    )

    assert dashboard["unified_operations"] == [
        "discovery",
        "probe",
        "search",
    ]
    assert dashboard["record_grain"] == (
        "aggregate_self_reported_case_counts"
    )
    assert dashboard["court_classes"] == list(georgia.COURT_CLASSES)
    assert workload["unified_operations"] == [
        "detail",
        "documents",
        "probe",
        "search",
    ]
    assert workload["record_grain"] == (
        "annual_aggregate_circuit_workload_publication"
    )
    assert workload["baseline_years"] == list(
        range(2018, 2025)
    )


def test_routes_reject_case_selectors_and_non_year_workload_detail() -> None:
    dashboard = query_state_courts.LIVE_ROUTES[
        georgia.DASHBOARD_SOURCE_ID
    ]["search"]
    with pytest.raises(ValueError, match="rather than case"):
        dashboard.translate(
            _shared_args(
                "search",
                "Superior",
                "--source",
                georgia.DASHBOARD_SOURCE_ID,
                "--case-type",
                "civil",
            ),
            dashboard.adapter_command,
        )

    detail = query_state_courts.LIVE_ROUTES[
        georgia.WORKLOAD_SOURCE_ID
    ]["detail"]
    with pytest.raises(ValueError, match="four-digit publication year"):
        detail.translate(
            _shared_args(
                "detail",
                "latest",
                "--source",
                georgia.WORKLOAD_SOURCE_ID,
            ),
            detail.adapter_command,
        )
    with pytest.raises(ValueError, match="requires one exact publication year"):
        detail.translate(
            _shared_args(
                "detail",
                "*",
                "--source",
                georgia.WORKLOAD_SOURCE_ID,
            ),
            detail.adapter_command,
        )


def test_shared_adapter_passes_source_identity_and_access_decision(
    monkeypatch,
) -> None:
    route = query_state_courts.LIVE_ROUTES[
        georgia.WORKLOAD_SOURCE_ID
    ]["detail"]
    translated = route.translate(
        _shared_args(
            "detail",
            "2024",
            "--source",
            georgia.WORKLOAD_SOURCE_ID,
        ),
        route.adapter_command,
    )
    captured = {}
    sentinel = object()

    def fake_execute(args, *, access_decision=None):
        captured["args"] = vars(args)
        captured["access_decision"] = access_decision
        return sentinel

    monkeypatch.setattr(georgia, "execute", fake_execute)
    decision = {"allowed": True, "reason_code": "open"}
    returned = route.adapter.execute(
        translated,
        access_decision=decision,
    )

    assert returned is sentinel
    assert captured["args"]["command"] == "document"
    assert captured["args"]["source"] == georgia.WORKLOAD_SOURCE_ID
    assert captured["access_decision"] == decision


@pytest.mark.parametrize(
    ("source_id", "operation", "record_kinds"),
    [
        (
            georgia.DASHBOARD_SOURCE_ID,
            "dashboards",
            [
                "aggregate_caseload_dashboard",
                "aggregate_dashboard_export_acquisition_handoff",
                "source_probe",
            ],
        ),
        (
            georgia.WORKLOAD_SOURCE_ID,
            "workloads",
            [
                "annual_superior_court_workload_assessment",
                "annual_superior_court_workload_pdf",
                "source_probe",
            ],
        ),
    ],
)
def test_aggregate_rows_are_source_snapshots_with_zero_projection(
    tmp_path: Path,
    source_id: str,
    operation: str,
    record_kinds: list[str],
) -> None:
    records = []
    for index, record_kind in enumerate(record_kinds, start=1):
        records.append(
            {
                "canonical_ref": f"GA-AGGREGATE:{source_id}:{index}",
                "source_id": source_id,
                "record_kind": record_kind,
                "data_scope": {
                    "record_grain": "aggregate",
                    "individual_case_records": False,
                },
                "projection": {
                    "projectable_as_case_record": False,
                },
                # Deliberate case-shaped values prove source-level dispatch,
                # rather than today's field shape, controls projection.
                "raw_case_number": f"NOT-A-CASE-{index}",
                "court": {
                    "court_id": "ga-aggregate-test",
                    "name": "Aggregate Test Court",
                },
                "parties": [
                    {
                        "raw_name": "NOT AN INDIVIDUAL CASE PARTY",
                        "role": "aggregate label",
                    }
                ],
                "docket_entries": [
                    {
                        "native_entry_id": f"not-a-docket-{index}",
                        "raw_text": "aggregate report row",
                    }
                ],
            }
        )
    envelope = _envelope(source_id, operation, records)
    court_db = tmp_path / f"{source_id}.db"

    report = ingest_state_court_records.ingest_envelope(
        envelope,
        court_db=court_db,
    )

    assert all(value == 0 for value in report["projected"].values())
    assert report["snapshot_only"] == {
        "record_count": 3,
        "record_kinds": {
            record_kind: 1 for record_kind in sorted(record_kinds)
        },
    }
    assert report["canonical_refs"] == []

    db = connect_courts(court_db)
    try:
        assert db.execute("SELECT COUNT(*) FROM source_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM court").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM case_party").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM docket_entry").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM document_artifact").fetchone()[0] == 0
        raw_json = db.execute(
            "SELECT raw_json FROM source_snapshot"
        ).fetchone()["raw_json"]
        assert json.loads(raw_json) == envelope
    finally:
        db.close()
