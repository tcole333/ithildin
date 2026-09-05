from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_new_jersey_tax_court as tax_court
from tools import query_state_courts
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_monitor import ProbeContext
from tools.public_records_search_plan import build_search_plan
from tools.seed_public_records_catalog import seed_catalog


RETRIEVED_AT = "2026-07-30T12:00:00Z"


def _shared_args(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def _source_row(
    occurrence_id: str,
    *,
    docket_number: str = "2026000001",
    display_number: str = "000001-2026",
    dataset_id: str = "docketed",
    row_number: int,
    block: str,
    lot: str,
) -> dict[str, Any]:
    artifact_sha = "a" * 64
    row_sha = chr(ord("b") + row_number) * 64
    return {
        "record_type": "tax_court_property_case_parcel_row",
        "native_record_id": occurrence_id,
        "source_occurrence_id": occurrence_id,
        "canonical_ref": (
            f"STATECOURT:{tax_court.SOURCE_ID}/{tax_court.COURT_ID}/"
            f"{docket_number}/property-case-parcel-row/{occurrence_id}"
        ),
        "case_canonical_ref": (
            f"STATECOURT:{tax_court.SOURCE_ID}/{tax_court.COURT_ID}/"
            f"{docket_number}/case"
        ),
        "case": {
            "docket_number_raw": docket_number,
            "docket_number": display_number,
            "filing_year": 2026,
            "title": "ALPHA HOLDINGS LLC V NEWARK CITY",
            "entered_date": {
                "raw": "01/05/2026",
                "source_format": "MM/DD/YYYY",
                "iso": "2026-01-05",
            },
        },
        "property": {
            "county_name": "Essex",
            "county_fips": "34013",
            "block": block,
            "lot": lot,
            "unit": None,
            "assessment_year_raw": "2026",
            "assessment_year": 2026,
        },
        "dataset": {
            "id": dataset_id,
            "label": (
                "Local Property Tax Cases Docketed"
                if dataset_id == "docketed"
                else "Open Local Property Tax Cases"
            ),
            "scope": "fixture current report",
        },
        "jurisdiction": {
            "state_code": "NJ",
            "state_fips": "34",
            "county_name": "Essex",
            "county_fips": "34013",
        },
        "normalization_issues": [],
        "source_record": {
            "publisher": "New Jersey Judiciary",
            "landing_url": tax_court.LANDING_URL,
            "manifest_url": tax_court.S3_LIST_URL,
            "artifact_url": (f"{tax_court.S3_BASE_URL}/tax-reports/localtaxcases.xlsx"),
            "s3_key": "tax-reports/localtaxcases.xlsx",
            "artifact_size": 1000,
            "artifact_sha256": artifact_sha,
            "etag": "fixture-etag",
            "last_modified": "2026-07-01T00:00:00Z",
            "version_id": "fixture-version",
            "workbook_sheet": "Local Property Docketed",
            "worksheet_member": "xl/worksheets/sheet1.xml",
            "raw_headers": list(tax_court.DOCKETED_HEADERS),
            "header_aliases": {},
            "row_position": row_number - 2,
            "row_number": row_number,
            "row_sha256": row_sha,
        },
    }


def _envelope(records: list[dict[str, Any]]) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=tax_court.SOURCE_METADATA,
        jurisdiction=tax_court.JURISDICTION,
        query=QueryMetadata(operation="search", parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=RETRIEVED_AT,
    ).to_dict()


def test_unified_router_maps_text_fields_dates_and_exact_case() -> None:
    route = query_state_courts.LIVE_ROUTES[tax_court.SOURCE_ID]["search"]
    search = route.translate(
        _shared_args(
            "search",
            "ALPHA HOLDINGS",
            "--source",
            tax_court.SOURCE_ID,
            "--jurisdiction",
            "34013",
            "--court-id",
            tax_court.COURT_ID,
            "--search-field",
            "case-title",
            "--county",
            "Essex",
            "--after",
            "2026-01-01",
            "--before",
            "2026-01-31",
            "--limit",
            "12",
        ),
        route.adapter_command,
    )

    assert search.command == "search"
    assert search.query == "ALPHA HOLDINGS"
    assert search.field == "case-title"
    assert search.dataset == "both"
    assert search.county == "Essex"
    assert search.entered_from == "2026-01-01"
    assert search.entered_to == "2026-01-31"
    assert search.limit == 12

    case_route = query_state_courts.LIVE_ROUTES[tax_court.SOURCE_ID]["case"]
    case = case_route.translate(
        _shared_args(
            "case",
            "000001-2026",
            "--source",
            tax_court.SOURCE_ID,
        ),
        case_route.adapter_command,
    )
    assert case.query is None
    assert case.docket == "000001-2026"
    assert case.field == "docket"
    assert case.limit is None

    with pytest.raises(ValueError, match="cover New Jersey"):
        route.translate(
            _shared_args(
                "search",
                "ALPHA",
                "--source",
                tax_court.SOURCE_ID,
                "--jurisdiction",
                "24",
            ),
            route.adapter_command,
        )


def test_ingest_keeps_one_case_and_every_property_row_occurrence(
    tmp_path: Path,
) -> None:
    court_db = tmp_path / "courts.db"
    records = [
        _source_row("occurrence-1", row_number=2, block="100", lot="2"),
        _source_row("occurrence-2", row_number=3, block="101", lot="3"),
        _source_row("occurrence-3", row_number=4, block="101", lot="3"),
    ]

    report = ingest_envelope(_envelope(records), court_db=court_db)

    assert report["projected"]["cases"] == 3
    assert report["projected"]["docket_entries"] == 3
    assert report["projected"]["parties"] == 0
    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        cases = db.execute(
            """
            SELECT raw_case_number, display_case_number, caption, case_type
            FROM case_record
            """
        ).fetchall()
        assert [tuple(row) for row in cases] == [
            (
                "2026000001",
                "000001-2026",
                "ALPHA HOLDINGS LLC V NEWARK CITY",
                "local_property_tax",
            )
        ]
        entries = db.execute(
            """
            SELECT native_entry_id, event_type, entered_date, raw_json
            FROM docket_entry
            ORDER BY native_entry_id
            """
        ).fetchall()
        assert [row["native_entry_id"] for row in entries] == [
            "occurrence-1",
            "occurrence-2",
            "occurrence-3",
        ]
        assert {row["event_type"] for row in entries} == {
            "tax_court_property_case_report_occurrence"
        }
        assert {row["entered_date"] for row in entries} == {"2026-01-05"}
        assert [
            json.loads(row["raw_json"])["property_components"]["block"]
            for row in entries
        ] == ["100", "101", "101"]
        assert db.execute("SELECT COUNT(*) FROM case_party").fetchone()[0] == 0
    finally:
        db.close()


def _validation_record(
    dataset_id: str,
    *,
    record_count: int,
    artifact_hash: str,
    corrected_open_header: bool,
) -> dict[str, Any]:
    spec = tax_court.DATASET_SPECS[dataset_id]
    raw_headers = (
        tax_court.DOCKETED_HEADERS
        if dataset_id == "docketed" or corrected_open_header
        else tax_court.OPEN_HEADERS_WITH_ANOMALY
    )
    return {
        "record_type": "workbook_validation",
        "dataset": {
            "id": dataset_id,
            "label": spec.label,
            "scope": spec.scope,
        },
        "artifact": {
            "dataset": dataset_id,
            "s3_key": spec.xlsx_key,
            "url": f"{tax_court.S3_BASE_URL}/{spec.xlsx_key}",
            "size": 1000 + record_count,
            "sha256": artifact_hash,
            "etag": f"etag-{record_count}",
            "last_modified": "2026-07-30T00:00:00Z",
            "version_id": f"version-{record_count}",
            "sheet_name": spec.sheet_name,
            "sheet_member": "xl/worksheets/sheet1.xml",
            "raw_headers": list(raw_headers),
            "record_count": record_count,
            "manifest_fingerprint": "c" * 64,
        },
        "workbook": {
            "sheet_name": spec.sheet_name,
            "sheet_member": "xl/worksheets/sheet1.xml",
            "raw_headers": list(raw_headers),
            "semantic_headers": list(tax_court.SEMANTIC_HEADERS),
            "record_count": record_count,
            "shared_string_count": 20,
            "dimension": f"A1:H{record_count + 1}",
            "header_aliases": (
                {} if raw_headers == tax_court.DOCKETED_HEADERS else {"Year": "county"}
            ),
        },
        "validation": {
            "complete_workbook_traversal": True,
            "records_traversed": record_count,
            "unique_dockets": record_count - 1,
            "duplicate_docket_rows": 1,
            "maximum_rows_per_docket": 2,
            "exact_duplicate_rows": 1,
            "county_counts": {"Essex": record_count},
            "assessment_year_counts": {"2026": record_count},
            "entered_date_min": "2026-01-01",
            "entered_date_max": "2026-07-30",
            "normalization_issue_counts_by_field": {},
        },
    }


def test_monitor_hashes_contract_not_replaceable_report_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {
        "count": 10,
        "hash": "d" * 64,
        "corrected_open_header": False,
    }

    def fake_execute(
        args: Any,
        *,
        log_results: bool,
    ) -> PublicRecordsResult:
        assert args.command == "validate"
        assert args.dataset == "both"
        assert log_results is False
        return PublicRecordsResult.success(
            tax_court.build_query(args),
            [
                _validation_record(
                    "docketed",
                    record_count=rolling["count"],
                    artifact_hash=rolling["hash"],
                    corrected_open_header=True,
                ),
                _validation_record(
                    "open",
                    record_count=rolling["count"] + 5,
                    artifact_hash=rolling["hash"],
                    corrected_open_header=rolling["corrected_open_header"],
                ),
            ],
            retrieved_at=RETRIEVED_AT,
        )

    monkeypatch.setattr(tax_court, "execute", fake_execute)
    context = ProbeContext(
        source_id=tax_court.SOURCE_ID,
        catalog_decision={"allowed": True},
        timeout=5,
        max_attempts=1,
        sample_bytes=16,
    )
    first = public_records_monitor.probe_new_jersey_tax_court(context)
    rolling.update(
        count=11,
        hash="e" * 64,
        corrected_open_header=True,
    )
    second = public_records_monitor.probe_new_jersey_tax_court(context)

    assert first.status == "ok"
    assert first.result_count == 2
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"]["open"]["artifact"]["sha256"]
        != second.details["rolling_observation"]["open"]["artifact"]["sha256"]
    )
    assert (
        first.details["rolling_observation"]["open"]["raw_headers"]
        != second.details["rolling_observation"]["open"]["raw_headers"]
    )


def test_catalog_planner_and_monitor_expose_primary_and_alternative_routes(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    assert catalog.require_machine_acquisition(tax_court.SOURCE_ID)["allowed"] is True
    detail = catalog.show_source(tax_court.SOURCE_ID)
    assert {capability["name"] for capability in detail["capabilities"]} == {
        "search_property_tax_cases",
        "inspect_current_report_artifacts",
        "ingest_property_tax_cases",
        "list_complementary_tax_court_routes",
        "probe_source",
    }
    complements = set(detail["current_manifest"]["complementary_source_ids"])
    assert {
        "us-nj-tax-court-current-object-versions",
        "us-nj-tax-court-judgment-archives",
        "us-nj-govconnect-tax-notices",
        "us-nj-tax-case-public-access",
        "us-nj-tax-court-opinions",
        "us-nj-property-tax-appeals",
        "us-nj-county-tax-boards",
        "us-nj-njgin-parcels-modiv",
        "us-nj-treasury-sr1a-sales",
    } <= complements
    county_boards = catalog.show_source("us-nj-county-tax-boards")
    assert (
        county_boards["current_manifest"]["record_identity_source_id"]
        == "us-nj-local-assessors-tax-boards"
    )
    assert (
        county_boards["current_manifest"]["probe_evidence"][
            "counts_as_independent_corroboration"
        ]
        is False
    )

    plan = build_search_plan(
        "ALPHA HOLDINGS LLC",
        jurisdictions=["34"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    tasks = [
        task
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
        if task["source_id"] == tax_court.SOURCE_ID
    ]
    assert {task["capability"] for task in tasks} == {"search_property_tax_cases"}
    route_group = next(
        group
        for group in plan["complementary_routes"]
        if group["primary_source_id"] == tax_court.SOURCE_ID
    )
    assert {route["source_id"] for route in route_group["complements"]} >= {
        "us-nj-tax-court-judgment-archives",
        "us-nj-tax-case-public-access",
        "us-nj-tax-court-opinions",
        "us-nj-njgin-parcels-modiv",
    }

    spec = public_records_monitor.HANDLER_REGISTRY[tax_court.SOURCE_ID]
    assert spec.handler is public_records_monitor.probe_new_jersey_tax_court
    assert spec.expected_requests == 9
    assert spec.sentinel_record_count == 2
