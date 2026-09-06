from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_md_opinions as md
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


FIXTURE_DIR = Path("tests/fixtures/public_records/md_opinions")
RETRIEVED_AT = "2026-07-30T12:00:00Z"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _reported_records() -> tuple[dict[str, Any], ...]:
    index = md.parse_reported_results(
        fixture("reported_results.html"),
        source_url=(
            f"{md.REPORTED_RESULTS_URL}?court=both&year=2026&order=bydate"
        ),
        native_court_filter="both",
    )
    return tuple(dict(record) for record in index.records)


def _unreported_records(
    filename: str = "unreported_month.html",
    *,
    month: str = "202607",
) -> tuple[dict[str, Any], ...]:
    index = md.parse_unreported_month(
        fixture(filename),
        month=month,
        source_url=f"{md.UNREPORTED_MONTH_PREFIX}/{month}",
    )
    return tuple(dict(record) for record in index.records)


def _envelope(operation: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=md.SOURCE_METADATA,
        jurisdiction=md.JURISDICTION,
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=RETRIEVED_AT,
    ).to_dict()


def _shared_args(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def test_unified_router_preserves_collection_court_and_date_semantics() -> None:
    reported_route = query_state_courts.LIVE_ROUTES[md.SOURCE_ID]["search"]
    reported = reported_route.translate(
        _shared_args(
            "search",
            "Harbor Properties",
            "--source",
            md.SOURCE_ID,
            "--court-id",
            "md-appellate-court",
            "--limit",
            "12",
        ),
        reported_route.adapter_command,
    )
    assert reported.command == "reported"
    assert reported.court == "appellate"
    assert reported.year == "all"
    assert reported.order == "date"
    assert reported.query == "Harbor Properties"
    assert reported.match_mode == "text"
    assert reported.limit == 12

    case_route = query_state_courts.LIVE_ROUTES[md.SOURCE_ID]["case"]
    exact_case = case_route.translate(
        _shared_args(
            "case",
            "42/25",
            "--source",
            md.SOURCE_ID,
        ),
        case_route.adapter_command,
    )
    assert exact_case.command == "reported"
    assert exact_case.order == "case"
    assert exact_case.match_mode == "case_number"

    unreported_route = query_state_courts.LIVE_ROUTES[
        md.SOURCE_ID
    ]["documents"]
    unreported = unreported_route.translate(
        _shared_args(
            "documents",
            "1539/24",
            "--source",
            md.SOURCE_ID,
            "--search-field",
            "unreported",
            "--court-id",
            "md-supreme-court",
            "--after",
            "2026-01-01",
            "--before",
            "2026-07-31",
        ),
        unreported_route.adapter_command,
    )
    assert unreported.command == "unreported"
    assert unreported.court == "supreme"
    assert unreported.date_from == "2026-01-01"
    assert unreported.date_to == "2026-07-31"
    assert unreported.query == "1539/24"
    assert unreported.match_mode == "case_number"

    with pytest.raises(ValueError, match="filing-year indexes"):
        reported_route.translate(
            _shared_args(
                "search",
                "Harbor Properties",
                "--source",
                md.SOURCE_ID,
                "--after",
                "2026-01-01",
            ),
            reported_route.adapter_command,
        )


def test_reported_and_unreported_rows_project_as_distinct_publications(
    tmp_path: Path,
) -> None:
    reported = _reported_records()[0]
    unreported = _unreported_records()[0]
    metadata_only = _unreported_records(
        "unreported_metadata_only.html",
        month="201504",
    )[0]
    court_db = tmp_path / "courts.db"

    report = ingest_envelope(
        _envelope(
            "search",
            [reported, unreported, metadata_only],
        ),
        court_db=court_db,
    )
    assert report["projected"]["cases"] == 3
    assert report["projected"]["docket_entries"] == 3
    assert report["projected"]["documents"] == 2
    assert report["projected"]["parties"] == 4
    assert report["projected"]["judicial_officers"] == 3

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        publications = db.execute(
            """
            SELECT c.raw_case_number, c.status, e.event_code, e.event_date,
                   d.native_document_id
            FROM docket_entry e
            JOIN case_record c USING(case_id)
            LEFT JOIN document_artifact d
              ON d.docket_entry_id=e.docket_entry_id
            ORDER BY c.raw_case_number
            """
        ).fetchall()
        assert [tuple(row) for row in publications] == [
            (
                "1002/14",
                "unreported",
                "appellate_opinion",
                "2015-04-30",
                None,
            ),
            (
                "1539/24",
                "unreported",
                "appellate_opinion",
                "2026-07-28",
                "unreported-opinions/1539s24.pdf",
            ),
            (
                "42/25",
                "reported",
                "appellate_opinion",
                "2026-07-27",
                "coa/2026/42a25.pdf",
            ),
        ]
        parties = db.execute(
            """
            SELECT c.raw_case_number, p.role, p.raw_name
            FROM case_party p
            JOIN case_record c USING(case_id)
            ORDER BY c.raw_case_number, p.sequence_no
            """
        ).fetchall()
        assert [tuple(row) for row in parties] == [
            (
                "1002/14",
                "appellant_or_first_party",
                "DeAngelo, Joseph J., III",
            ),
            ("1002/14", "appellee_or_second_party", "State"),
            ("1539/24", "appellant_or_first_party", "Brunson, Shawn Lee"),
            ("1539/24", "appellee_or_second_party", "State"),
        ]
        assignment_roles = {
            row[0]
            for row in db.execute(
                "SELECT assignment_role FROM case_assignment"
            )
        }
        assert assignment_roles == {"published_opinion_judge_or_author"}
    finally:
        db.close()


def test_monitor_separates_index_contract_from_rolling_publications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {
        "reported_count": 130,
        "pdf_url": f"{md.BASE_URL}/data/opinions/coa/2026/42a25.pdf",
        "pdf_hash": "a" * 64,
    }

    def fake_execute(
        args: Any,
        *,
        log_results: bool,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert log_results is False
        query = md._query(args, selection={})
        record = {
            "source_id": md.SOURCE_ID,
            "record_kind": "source_probe",
            "reported_year_count": 32,
            "reported_sample_count": rolling["reported_count"],
            "reported_schema_fingerprint": "b" * 64,
            "unreported_month_count": 296,
            "unreported_sample_month": "2026-07",
            "unreported_sample_count": 132,
            "unreported_schema_fingerprint": "c" * 64,
            "pdf_url": rolling["pdf_url"],
            "pdf_sha256": rolling["pdf_hash"],
            "pdf_size_bytes": 215743,
            "pdf_media_type": "application/pdf",
        }
        return PublicRecordsResult.success(
            query,
            [record],
            retrieved_at=RETRIEVED_AT,
        )

    monkeypatch.setattr(md, "execute", fake_execute)
    context = ProbeContext(
        source_id=md.SOURCE_ID,
        catalog_decision={
            "allowed": True,
            "limits": {"minimum_interval_seconds": 0.25},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )
    first = public_records_monitor.probe_maryland_opinions(context)
    rolling.update(
        reported_count=131,
        pdf_url=f"{md.BASE_URL}/data/opinions/coa/2026/43a25.pdf",
        pdf_hash="d" * 64,
    )
    second = public_records_monitor.probe_maryland_opinions(context)

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"]["reported_sample_count"]
        != second.details["rolling_observation"]["reported_sample_count"]
    )
    assert (
        first.details["rolling_observation"]["pdf_url"]
        != second.details["rolling_observation"]["pdf_url"]
    )


def test_catalog_planner_and_monitor_use_verified_opinion_components(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    assert catalog.require_machine_acquisition(md.SOURCE_ID)["allowed"] is True
    detail = catalog.show_source(md.SOURCE_ID)
    capabilities = {
        capability["name"] for capability in detail["capabilities"]
    }
    assert capabilities == {
        "search_reported_opinions",
        "search_unreported_opinions",
        "fetch_opinion_pdf",
        "list_opinion_routes",
        "probe_source",
    }

    plan = build_search_plan(
        "Harbor Properties",
        jurisdictions=["24"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {row["source_id"]: row for row in plan["sources"]}
    assert sources[md.SOURCE_ID]["access"]["mode"] == "allowed_with_limits"
    tasks = {
        task["capability"]
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
        if task["source_id"] == md.SOURCE_ID
    }
    assert tasks == {
        "search_reported_opinions",
        "search_unreported_opinions",
        "fetch_opinion_pdf",
    }
    route_groups = {
        group["primary_source_id"]: group
        for group in plan["complementary_routes"]
    }
    complements = {
        value["source_id"]
        for value in route_groups[md.SOURCE_ID]["complements"]
    }
    assert {
        "us-md-case-search",
        "us-md-mdec-public-cases",
        "us-md-judgment-liens",
        "us-md-estate-search",
        "us-md-circuit-clerk-records",
        "us-courtlistener-api",
    } <= complements

    handler = public_records_monitor.HANDLER_REGISTRY[md.SOURCE_ID]
    assert handler.handler is public_records_monitor.probe_maryland_opinions
    assert handler.expected_requests == 5
    assert handler.sentinel_record_count == 1
