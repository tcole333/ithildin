from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_md_business_opinions as md
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


FIXTURE_DIR = Path("tests/fixtures/public_records/md_business_opinions")
RETRIEVED_AT = "2026-07-30T12:00:00Z"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _current_records() -> tuple[dict[str, Any], ...]:
    page = md.parse_opinion_page(
        fixture("current.html"),
        source_url=md.CURRENT_URL,
    )
    return tuple(dict(record) for record in page.records)


def _archive_records(
    filename: str,
    *,
    year: int,
) -> tuple[dict[str, Any], ...]:
    page = md.parse_opinion_page(
        fixture(filename),
        source_url=f"{md.ARCHIVE_INDEX_URL}{year}",
        expected_publication_year=year,
    )
    return tuple(dict(record) for record in page.records)


def _envelope(records: list[dict[str, Any]]) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=md.SOURCE_METADATA,
        jurisdiction=md.JURISDICTION,
        query=QueryMetadata(operation="search", parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=RETRIEVED_AT,
    ).to_dict()


def _shared_args(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def test_unified_router_preserves_trial_publication_search_semantics() -> None:
    search_route = query_state_courts.LIVE_ROUTES[md.SOURCE_ID]["search"]
    search = search_route.translate(
        _shared_args(
            "search",
            "Lockheed Martin",
            "--source",
            md.SOURCE_ID,
            "--jurisdiction",
            "24",
            "--court-id",
            "md-circuit-prince-george-s",
            "--after",
            "2002-01-01",
            "--before",
            "2004-12-31",
            "--limit",
            "12",
        ),
        search_route.adapter_command,
    )

    assert search.command == "search"
    assert search.all_pages is True
    assert search.query == "Lockheed Martin"
    assert search.case_number is None
    assert search.county == "prince george s"
    assert search.filed_from == "2002-01-01"
    assert search.filed_to == "2004-12-31"
    assert search.limit == 12

    case_route = query_state_courts.LIVE_ROUTES[md.SOURCE_ID]["case"]
    case = case_route.translate(
        _shared_args(
            "case",
            "24-C-05-009296",
            "--source",
            md.SOURCE_ID,
        ),
        case_route.adapter_command,
    )
    assert case.query is None
    assert case.case_number == "24-C-05-009296"
    assert case.all_pages is True

    documents_route = query_state_courts.LIVE_ROUTES[md.SOURCE_ID]["documents"]
    documents = documents_route.translate(
        _shared_args(
            "documents",
            "24-C-05-009296",
            "--source",
            md.SOURCE_ID,
            "--document-type",
            "order",
        ),
        documents_route.adapter_command,
    )
    assert documents.case_number == "24-C-05-009296"
    assert documents.document_type == "order"


def test_unified_router_maps_source_fields_without_losing_query_role() -> None:
    route = query_state_courts.LIVE_ROUTES[md.SOURCE_ID]["search"]
    judge = route.translate(
        _shared_args(
            "search",
            "Rubin",
            "--source",
            md.SOURCE_ID,
            "--search-field",
            "judge",
        ),
        route.adapter_command,
    )
    assert judge.judge == "Rubin"
    assert judge.query is None

    opinion = route.translate(
        _shared_args(
            "search",
            "Sachs Capital",
            "--source",
            md.SOURCE_ID,
            "--search-field",
            "opinion",
        ),
        route.adapter_command,
    )
    assert opinion.query == "Sachs Capital"
    assert opinion.document_type == "opinion"

    with pytest.raises(ValueError, match="cover Maryland"):
        route.translate(
            _shared_args(
                "search",
                "Fixture",
                "--source",
                md.SOURCE_ID,
                "--jurisdiction",
                "36",
            ),
            route.adapter_command,
        )


def test_trial_publications_project_case_events_documents_and_identity_gaps(
    tmp_path: Path,
) -> None:
    archive_2008 = _archive_records("archive2008.html", year=2008)
    irregular = _archive_records("archive_irregular.html", year=2004)
    missing_case = next(
        record
        for record in _current_records()
        if record["publication_designation"] == "2009 MDBT-4"
    )
    court_db = tmp_path / "courts.db"

    report = ingest_envelope(
        _envelope(
            [
                archive_2008[1],
                irregular[0],
                missing_case,
            ]
        ),
        court_db=court_db,
    )
    assert report["projected"]["cases"] == 4
    assert report["projected"]["docket_entries"] == 4
    assert report["projected"]["documents"] == 8
    assert report["projected"]["judicial_officers"] == 4

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        cases = db.execute(
            """
            SELECT raw_case_number, display_case_number, case_type
            FROM case_record
            ORDER BY raw_case_number
            """
        ).fetchall()
        assert [tuple(row) for row in cases] == [
            ("24-C-03-001111", "24-C-03-001111", "business_and_technology"),
            ("24-C-03-001112", "24-C-03-001112", "business_and_technology"),
            ("24-C-05-009296", "24-C-05-009296", "business_and_technology"),
            (
                "MDBT-PUBLICATION:2009 MDBT-4",
                "2009 MDBT-4",
                "business_and_technology",
            ),
        ]
        events = db.execute(
            """
            SELECT c.raw_case_number, e.native_entry_id, e.event_type,
                   e.event_date, e.document_available
            FROM docket_entry e
            JOIN case_record c USING(case_id)
            ORDER BY c.raw_case_number
            """
        ).fetchall()
        assert [tuple(row) for row in events] == [
            (
                "24-C-03-001111",
                "2004 MDBT-10",
                "trial_court_publication",
                "2004-04",
                1,
            ),
            (
                "24-C-03-001112",
                "2004 MDBT-10",
                "trial_court_publication",
                "2004-04",
                1,
            ),
            (
                "24-C-05-009296",
                "2008 MDBT-4",
                "trial_court_publication",
                "2008-04-15",
                1,
            ),
            (
                "MDBT-PUBLICATION:2009 MDBT-4",
                "2009 MDBT-4",
                "trial_court_publication",
                "2009-06-05",
                1,
            ),
        ]
        documents = db.execute(
            """
            SELECT c.raw_case_number, d.document_type, d.mime_type,
                   d.source_url
            FROM document_artifact d
            JOIN case_record c USING(case_id)
            ORDER BY c.raw_case_number, d.native_document_id
            """
        ).fetchall()
        assert len(documents) == 8
        assert {"opinion", "order"} == {row["document_type"] for row in documents}
        assert {
            "application/pdf",
            "application/msword",
            "application/vnd.wordperfect",
        } <= {row["mime_type"] for row in documents}
        assert all(
            row["source_url"].startswith(
                "https://www.mdcourts.gov/sites/default/files/"
            )
            for row in documents
        )
    finally:
        db.close()


def test_monitor_separates_contract_from_rolling_current_publications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {
        "current_count": 95,
        "omission_count": 5,
        "anomaly_count": 5,
        "pdf_url": (
            f"{md.BASE_URL}/sites/default/files/import/businesstech/"
            "opinions/2026/mdbt2-26.pdf"
        ),
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
            "archive_years": [2008, 2007, 2006, 2005, 2004, 2003],
            "current_publication_count": rolling["current_count"],
            "current_schema_fingerprint": "b" * 64,
            "archive_sample_year": 2003,
            "archive_sample_count": 11,
            "archive_schema_fingerprint": "c" * 64,
            "current_rows_with_source_omissions": rolling["omission_count"],
            "current_rows_with_source_link_anomalies": rolling["anomaly_count"],
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
    first = public_records_monitor.probe_maryland_business_opinions(context)
    rolling.update(
        current_count=96,
        omission_count=6,
        anomaly_count=7,
        pdf_url=(
            f"{md.BASE_URL}/sites/default/files/import/businesstech/"
            "opinions/2026/mdbt3-26.pdf"
        ),
        pdf_hash="d" * 64,
    )
    second = public_records_monitor.probe_maryland_business_opinions(context)

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"]["current_publication_count"]
        != second.details["rolling_observation"]["current_publication_count"]
    )
    assert (
        first.details["rolling_observation"]["pdf_url"]
        != second.details["rolling_observation"]["pdf_url"]
    )


def test_catalog_planner_and_monitor_expose_trial_publication_components(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    assert catalog.require_machine_acquisition(md.SOURCE_ID)["allowed"] is True
    detail = catalog.show_source(md.SOURCE_ID)
    capabilities = {capability["name"] for capability in detail["capabilities"]}
    assert capabilities == {
        "search_business_technology_opinions",
        "fetch_business_technology_document",
        "list_opinion_routes",
        "probe_source",
    }

    plan = build_search_plan(
        "Lockheed Martin",
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
        "search_business_technology_opinions",
        "fetch_business_technology_document",
    }
    route_groups = {
        group["primary_source_id"]: group for group in plan["complementary_routes"]
    }
    complements = {
        value["source_id"] for value in route_groups[md.SOURCE_ID]["complements"]
    }
    assert complements == {
        "us-md-case-search",
        "us-md-mdec-public-cases",
        "us-md-judgment-liens",
        "us-md-appellate-opinions",
        "us-md-circuit-clerk-records",
    }

    handler = public_records_monitor.HANDLER_REGISTRY[md.SOURCE_ID]
    assert handler.handler is public_records_monitor.probe_maryland_business_opinions
    assert handler.expected_requests == 4
    assert handler.sentinel_record_count == 1
