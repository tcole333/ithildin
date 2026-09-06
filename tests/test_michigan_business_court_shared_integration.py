from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from tools import public_records_monitor
from tools import query_michigan_business_court as business
from tools import query_state_courts
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_monitor import ProbeContext


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "michigan_business_court"
)
RETRIEVED_AT = "2026-07-30T12:00:00Z"


def _json(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _shared_args(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def _normalized_record(
    native_row: int,
    *,
    selected_courts: list[str] | None = None,
) -> dict[str, Any]:
    page = business.parse_search_payload(
        _json("search-page-1.json"),
        requested_page=1,
        source_url=business.SEARCH_URL,
    )
    courts = selected_courts or []
    query_context = {
        "query_text": "",
        "sort_order": "Oldest",
        "business_courts": [],
        "courts": courts,
        "audience": None,
    }
    fingerprint = business._selection_fingerprint(
        query_text="",
        sort_order="Oldest",
        business_courts=(),
        courts=tuple(courts),
        audience=None,
    )
    return business.normalize_search_item(
        page.records[native_row - 1],
        source_url=business.SEARCH_URL,
        source_schema_fingerprint=page.schema_fingerprint,
        native_page=1,
        native_row=native_row,
        page=page,
        query_context=query_context,
        selection_fingerprint=fingerprint,
    )


def _envelope(records: list[dict[str, Any]]) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=business.SOURCE_METADATA,
        jurisdiction=business.JURISDICTION,
        query=QueryMetadata(operation="search", parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=RETRIEVED_AT,
    ).to_dict()


def test_shared_routes_preserve_exhaustive_limit_and_native_operation_scope(
    tmp_path: Path,
) -> None:
    routes = query_state_courts.LIVE_ROUTES[business.SOURCE_ID]
    assert set(routes) == {"search", "discovery", "probe", "download"}

    search = routes["search"].translate(
        _shared_args(
            "search",
            "summary disposition",
            "--source",
            business.SOURCE_ID,
            "--jurisdiction",
            "26",
            "--court-id",
            business.COLLECTION_COURT_ID,
            "--case-type",
            "Real Estate",
            "--cursor",
            "opaque-query-bound-cursor",
        ),
        routes["search"].adapter_command,
    )
    assert search.command == "search"
    assert search.query_text == "summary disposition"
    assert search.business_courts == ["Real Estate"]
    assert search.courts is None
    assert search.limit is None
    assert search.page == 1
    assert search.cursor == "opaque-query-bound-cursor"

    bounded = routes["search"].translate(
        _shared_args(
            "search",
            "order",
            "--source",
            business.SOURCE_ID,
            "--limit",
            "9",
        ),
        routes["search"].adapter_command,
    )
    assert bounded.limit == 9

    discovery = routes["discovery"].translate(
        _shared_args("discovery", "courts", "--source", business.SOURCE_ID),
        routes["discovery"].adapter_command,
    )
    assert discovery.command == "sources"

    probe = routes["probe"].translate(
        _shared_args("probe", "--source", business.SOURCE_ID),
        routes["probe"].adapter_command,
    )
    assert probe.command == "probe"
    assert probe.zero_query == business.PROBE_ZERO_QUERY

    destination = tmp_path / "business-court.pdf"
    download = routes["download"].translate(
        _shared_args(
            "download",
            (
                "https://www.courts.michigan.gov/siteassets/"
                "business-court-opinions/example.pdf"
            ),
            "--source",
            business.SOURCE_ID,
            "--destination",
            str(destination),
        ),
        routes["download"].adapter_command,
    )
    assert download.command == "download"
    assert download.destination == destination
    assert download.max_bytes is None


def test_ingestion_preserves_document_row_and_case_candidate_identities(
    tmp_path: Path,
) -> None:
    sparse = _normalized_record(
        1,
        selected_courts=["Genesee County Circuit Court"],
    )
    compound = _normalized_record(2)
    court_db = tmp_path / "courts.db"

    report = ingest_envelope(
        _envelope([sparse, compound]),
        court_db=court_db,
    )
    assert report["projected"]["cases"] == 3
    assert report["projected"]["docket_entries"] == 3
    assert report["projected"]["documents"] == 3
    assert report["snapshot_only"]["record_count"] == 0

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        cases = db.execute(
            """
            SELECT raw_case_number, display_case_number, caption, court_id,
                   raw_json
            FROM case_record
            ORDER BY raw_case_number
            """
        ).fetchall()
        assert [row["raw_case_number"] for row in cases[:2]] == [
            "25-058317-CZ",
            "25-SC0059-SC",
        ]
        assert cases[0]["caption"] == (
            "Alpha Development LLC v Beta Holdings Inc"
        )
        sparse_case = cases[2]
        assert sparse_case["raw_case_number"].startswith(
            "MI-BUSINESS-DOCUMENT:"
        )
        assert sparse_case["caption"] is None
        sparse_case_payload = json.loads(sparse_case["raw_json"])
        assert sparse_case_payload["source_omissions"] == [
            "pleadingOrderDate",
            "caseName",
            "caseNumber",
        ]
        assert {
            row["court_id"] for row in cases
        } == {business.COLLECTION_COURT_ID}

        court = db.execute(
            "SELECT court_id, name FROM court"
        ).fetchone()
        assert tuple(court) == (
            business.COLLECTION_COURT_ID,
            "Michigan Business Court Document Collection",
        )

        occurrences = db.execute(
            """
            SELECT source_result_id, filing_location, raw_json
            FROM case_source_occurrence
            ORDER BY source_result_id
            """
        ).fetchall()
        assert len(occurrences) == 3
        assert len({row["source_result_id"] for row in occurrences}) == 3
        assert all(row["filing_location"] is None for row in occurrences)
        occurrence_payloads = [
            json.loads(row["raw_json"]) for row in occurrences
        ]
        sparse_occurrence = next(
            payload
            for payload in occurrence_payloads
            if payload["source_occurrence_id"] == sparse[
                "source_occurrence_id"
            ]
        )
        assert sparse_occurrence["court_locator_candidates"] == [
            {
                "authoritative_assignment": False,
                "basis": "selected_single_court_facet",
                "value": "Genesee County Circuit Court",
            },
            {
                "authoritative_assignment": False,
                "basis": "filename_court_code_candidate",
                "value": "c06",
            },
        ]

        documents = db.execute(
            """
            SELECT native_document_id, source_url, filed_date
            FROM document_artifact
            ORDER BY native_document_id, document_id
            """
        ).fetchall()
        assert len(documents) == 3
        compound_document_id = compound["document"]["native_document_id"]
        assert sum(
            row["native_document_id"] == compound_document_id
            for row in documents
        ) == 2
        sparse_document = next(
            row
            for row in documents
            if row["native_document_id"]
            == sparse["document"]["native_document_id"]
        )
        assert sparse_document["filed_date"] is None
        assert sparse_document["source_url"].endswith(
            ".pdf?download=1"
        )
    finally:
        db.close()


def _probe_result(
    *,
    total_results: int,
    total_pages: int,
    document_sha256: str,
) -> PublicRecordsResult:
    query = PublicRecordsQuery(
        source=business.SOURCE_METADATA,
        jurisdiction=business.JURISDICTION,
        query=QueryMetadata(operation="probe", parameters={}),
    )
    record = {
        "source_id": business.SOURCE_ID,
        "record_kind": "business_court_source_probe",
        "search_contract": {
            "source_url": business.SEARCH_URL,
            "native_page_size": business.NATIVE_PAGE_SIZE,
            "total_results": total_results,
            "total_pages": total_pages,
            "result_count": business.NATIVE_PAGE_SIZE,
            "source_has_more_results": False,
            "continuation_basis": "currentPage_less_than_totalPages",
            "sort_by_options": list(business.SORT_ORDERS),
            "facets": [
                {
                    "query_string_key": business.BUSINESS_CATEGORY_QUERY_KEY,
                    "values": ["Contracts", "Real Estate"],
                },
                {
                    "query_string_key": business.COURT_QUERY_KEY,
                    "values": ["Genesee County Circuit Court"],
                },
            ],
            "schema_fingerprint": "1" * 64,
        },
        "zero_result_contract": {
            "query": business.PROBE_ZERO_QUERY,
            "result_count": 0,
            "total_results": 0,
            "total_pages": 0,
            "schema_fingerprint": "2" * 64,
        },
        "document_contract": {
            "source_url": (
                "https://www.courts.michigan.gov/siteassets/"
                "business-court-opinions/sample.pdf"
            ),
            "filename": "sample.pdf",
            "media_type": "application/pdf",
            "content_length": 100,
            "sha256": document_sha256,
            "signature_hex": "255044462d312e37",
        },
        "source_url": business.LANDING_URL,
    }
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at=RETRIEVED_AT,
    )


def test_monitor_separates_native_totals_from_stable_probe_contract(
    monkeypatch,
) -> None:
    context = ProbeContext(
        source_id=business.SOURCE_ID,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.25},
        },
        timeout=1,
        max_attempts=1,
        sample_bytes=None,
    )
    first_result = _probe_result(
        total_results=240,
        total_pages=30,
        document_sha256="a" * 64,
    )
    monkeypatch.setattr(
        public_records_monitor.query_michigan_business_court,
        "execute",
        lambda args, log_results=False: first_result,
    )
    first = public_records_monitor.probe_michigan_business_court(context)

    second_result = _probe_result(
        total_results=248,
        total_pages=31,
        document_sha256="b" * 64,
    )
    monkeypatch.setattr(
        public_records_monitor.query_michigan_business_court,
        "execute",
        lambda args, log_results=False: second_result,
    )
    second = public_records_monitor.probe_michigan_business_court(context)

    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["requests_made"] == 3
    assert first.details["stable_contract"]["pagination"] == {
        "page_origin": 1,
        "continuation_basis": "currentPage_less_than_totalPages",
        "omitted_limit": "traverse_totalPages",
        "cursor_binding": "source_query_selection_fingerprint",
    }
    assert first.details["rolling_observation"]["total_results"] == 240
    assert second.details["rolling_observation"]["total_results"] == 248
    handler = public_records_monitor.HANDLER_REGISTRY[business.SOURCE_ID]
    assert handler.expected_requests == 3


def test_business_court_citation_mapping_uses_the_official_landing_page() -> None:
    source_urls = json.loads(
        Path("web/src/data/source-urls.json").read_text(encoding="utf-8")
    )
    assert source_urls[
        f"STATECOURT_SOURCE:{business.SOURCE_ID}"
    ] == business.LANDING_URL
