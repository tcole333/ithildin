from __future__ import annotations

import json
from pathlib import Path

from tools import (
    public_records_monitor,
    query_michigan_appellate,
    query_state_courts,
)
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_store import connect_courts


FIXTURE_ROOT = Path("tests/fixtures/public_records/michigan_appellate")


def _normalized_fixture(filename: str, result_type: str) -> dict:
    payload = json.loads(
        (FIXTURE_ROOT / filename).read_text(encoding="utf-8")
    )
    page = query_michigan_appellate.parse_search_payload(
        payload,
        result_type=result_type,
        requested_page=1,
        source_url=query_michigan_appellate.SEARCH_ENDPOINTS[result_type],
    )
    return query_michigan_appellate.normalize_item(
        page.records[0],
        result_type=result_type,
        source_url=page.source_url,
        source_schema_fingerprint=page.schema_fingerprint,
        retrieval={
            "native_page": page.current_page,
            "native_page_size": page.page_size,
            "native_total_pages": page.total_pages,
            "native_total_results": page.total_results,
        },
    )


def _envelope(operation: str, records: list[dict]) -> dict:
    query = PublicRecordsQuery(
        source=query_michigan_appellate.SOURCE_METADATA,
        jurisdiction=query_michigan_appellate.JURISDICTION,
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(query, records).to_dict()


def _shared_args(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def test_michigan_cases_publications_and_attorney_ids_project_separately(
    tmp_path: Path,
) -> None:
    case_record = _normalized_fixture("cases-page-1.json", "cases")
    opinion_record = _normalized_fixture("opinions-page.json", "opinions")
    order_record = _normalized_fixture("orders-page.json", "orders")
    db_path = tmp_path / "courts.db"

    case_report = ingest_envelope(
        _envelope("search", [case_record]),
        court_db=db_path,
    )
    opinion_report = ingest_envelope(
        _envelope("search", [opinion_record]),
        court_db=db_path,
    )
    order_report = ingest_envelope(
        _envelope("search", [order_record]),
        court_db=db_path,
    )

    assert case_report["projected"]["cases"] == 1
    assert case_report["projected"]["attorneys"] == 1
    assert case_report["projected"]["docket_entries"] == 0
    assert opinion_report["projected"]["docket_entries"] == 1
    assert opinion_report["projected"]["documents"] == 1
    assert order_report["projected"]["docket_entries"] == 1
    assert order_report["projected"]["documents"] == 1

    db = connect_courts(db_path)
    try:
        case = db.execute(
            """
            SELECT court_id, raw_case_number, caption, filing_date, status
            FROM case_record
            WHERE source_id=? AND raw_case_number='360440'
            """,
            (query_michigan_appellate.SOURCE_ID,),
        ).fetchone()
        assert tuple(case) == (
            "us-mi-court-of-appeals",
            "360440",
            "LION LABS LTD V JORDAN EPSTEIN",
            "2022-02-25",
            "Case Concluded; File Archived",
        )
        attorney = db.execute(
            "SELECT raw_name, bar_id FROM attorney WHERE source_id=?",
            (query_michigan_appellate.SOURCE_ID,),
        ).fetchone()
        assert tuple(attorney) == ("EPSTEIN JONATHAN", "P38101")

        publications = db.execute(
            """
            SELECT c.raw_case_number, e.event_code, e.event_date,
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
                "166702",
                "appellate_order",
                "2022-12-07",
                "163086_90_01.pdf",
            ),
            (
                "367360",
                "appellate_opinion",
                "2026-07-22",
                "20260722_c367360_44_367360c.opn.pdf",
            ),
        ]
    finally:
        db.close()


def test_michigan_unresolved_case_number_remains_snapshot_only(
    tmp_path: Path,
) -> None:
    unresolved = _normalized_fixture("cases-page-1.json", "cases")
    unresolved["case_number_resolved"] = False
    unresolved["raw_case_number"] = None
    unresolved["normalized_case_number"] = None
    db_path = tmp_path / "courts.db"

    report = ingest_envelope(
        _envelope("search", [unresolved]),
        court_db=db_path,
    )

    assert report["snapshot_id"] > 0
    assert report["projected"]["cases"] == 0
    assert report["snapshot_only"]["record_kinds"] == {
        "appellate_case_index": 1
    }


def test_michigan_shared_routes_preserve_result_and_field_selectors() -> None:
    route = query_state_courts.LIVE_ROUTES[
        query_michigan_appellate.SOURCE_ID
    ]["search"]
    opinion = route.translate(
        _shared_args(
            "search",
            "Epstein",
            "--source",
            query_michigan_appellate.SOURCE_ID,
            "--jurisdiction",
            "26",
            "--case-type",
            "opinions",
            "--search-field",
            "party",
            "--court-id",
            "us-mi-court-of-appeals",
            "--limit",
            "25",
        ),
        route.adapter_command,
    )
    assert opinion.command == "search"
    assert opinion.result_type == "opinions"
    assert opinion.party_name == "Epstein"
    assert opinion.query_text == ""
    assert opinion.appellate_court == "Court Of Appeals"
    assert opinion.limit == 25

    case_route = query_state_courts.LIVE_ROUTES[
        query_michigan_appellate.SOURCE_ID
    ]["case"]
    case = case_route.translate(
        _shared_args(
            "case",
            "360440",
            "--source",
            query_michigan_appellate.SOURCE_ID,
        ),
        case_route.adapter_command,
    )
    assert case.command == "search"
    assert case.result_type == "cases"
    assert case.case_id == "360440"


def test_michigan_monitor_handler_is_registered() -> None:
    handler = public_records_monitor.HANDLER_REGISTRY[
        query_michigan_appellate.SOURCE_ID
    ]

    assert handler.handler is public_records_monitor.probe_michigan_appellate
    assert handler.endpoint == query_michigan_appellate.SEARCH_PAGE_URL
    assert handler.expected_requests == 5
    assert handler.sentinel_record_count == 1
