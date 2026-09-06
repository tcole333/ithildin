from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools import (
    public_records_monitor,
    query_state_courts,
    query_wisconsin_opinions,
    query_wisconsin_wscca,
)
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_store import connect_courts


FIXTURE_ROOT = Path("tests/fixtures/public_records")


def _envelope(
    *,
    source,
    jurisdiction,
    operation: str,
    records: list[dict],
) -> dict:
    query = PublicRecordsQuery(
        source=source,
        jurisdiction=jurisdiction,
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(query, records).to_dict()


def _shared_args(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def test_wscca_projects_case_children_and_preserves_case_on_rss_refresh(
    tmp_path: Path,
) -> None:
    payload = json.loads(
        (
            FIXTURE_ROOT / "wisconsin_wscca" / "case.json"
        ).read_text(encoding="utf-8")
    )
    case_record = query_wisconsin_wscca._normalize_case(payload["result"])
    db_path = tmp_path / "courts.db"

    first = ingest_envelope(
        _envelope(
            source=query_wisconsin_wscca.SOURCE_METADATA,
            jurisdiction=query_wisconsin_wscca.JURISDICTION,
            operation="case",
            records=[case_record],
        ),
        court_db=db_path,
    )
    rss_records = query_wisconsin_wscca.parse_rss(
        (
            FIXTURE_ROOT / "wisconsin_wscca" / "case-rss.xml"
        ).read_bytes(),
        case_number="2025AP000699",
    )
    second = ingest_envelope(
        _envelope(
            source=query_wisconsin_wscca.SOURCE_METADATA,
            jurisdiction=query_wisconsin_wscca.JURISDICTION,
            operation="rss",
            records=rss_records,
        ),
        court_db=db_path,
    )

    assert first["projected"]["cases"] == 1
    assert first["projected"]["related_cases"] == 1
    assert first["projected"]["case_relations"] == 1
    assert first["projected"]["documents"] == 2
    assert second["projected"]["cases"] == 2

    db = connect_courts(db_path)
    try:
        case = db.execute(
            """
            SELECT caption, status, filing_date, disposition_date
            FROM case_record
            WHERE source_id=? AND raw_case_number=?
              AND court_id=?
            """,
            (
                query_wisconsin_wscca.SOURCE_ID,
                "2025AP000699",
                query_wisconsin_wscca.COURT_OF_APPEALS_ID,
            ),
        ).fetchone()
        assert case is not None
        assert case["caption"] == "Khider A.K. Elnimeiry v. Amal Benshili"
        assert case["status"] == "Closed"
        assert case["filing_date"] == "2025-04-04"
        assert case["disposition_date"] == "2026-05-29"

        parties = db.execute(
            """
            SELECT role, raw_name FROM case_party
            WHERE case_id=(
                SELECT case_id FROM case_record
                WHERE source_id=? AND raw_case_number=?
                  AND court_id=?
            )
            ORDER BY sequence_no
            """,
            (
                query_wisconsin_wscca.SOURCE_ID,
                "2025AP000699",
                query_wisconsin_wscca.COURT_OF_APPEALS_ID,
            ),
        ).fetchall()
        assert len(parties) == 3

        relation = db.execute(
            """
            SELECT relation_type FROM case_relation
            """
        ).fetchone()
        assert relation is not None
        assert relation["relation_type"] == "appealed_to"

        documents = db.execute(
            """
            SELECT native_document_id, docket_entry_id
            FROM document_artifact ORDER BY native_document_id
            """
        ).fetchall()
        assert [row["native_document_id"] for row in documents] == [
            "948283",
            "994970",
        ]
        by_document = {
            row["native_document_id"]: row["docket_entry_id"]
            for row in documents
        }
        assert by_document["948283"] is None
        assert by_document["994970"] is not None
    finally:
        db.close()


def test_opinion_projection_keeps_case_scope_for_shared_consolidated_pdf(
    tmp_path: Path,
) -> None:
    html_text = (
        FIXTURE_ROOT / "wisconsin_opinions" / "metadata-appeals.html"
    ).read_text(encoding="utf-8")
    page = query_wisconsin_opinions.parse_metadata_page(
        html_text,
        collection="appeals-opinions",
        source_url=(
            query_wisconsin_opinions.COLLECTIONS[
                "appeals-opinions"
            ].endpoint
        ),
        requested_page=1,
    )
    original = dict(page.records[0])
    consolidated = copy.deepcopy(original)
    consolidated["raw_case_number"] = "2024AP002485"
    consolidated["normalized_appellate_case_number"] = "2024AP002485"
    consolidated["caption"] = f"{original['caption']} (consolidated)"
    db_path = tmp_path / "courts.db"

    report = ingest_envelope(
        _envelope(
            source=query_wisconsin_opinions.SOURCE_METADATA,
            jurisdiction=query_wisconsin_opinions.JURISDICTION,
            operation="search",
            records=[original, consolidated],
        ),
        court_db=db_path,
    )

    assert report["projected"]["cases"] == 2
    assert report["projected"]["documents"] == 2
    db = connect_courts(db_path)
    try:
        rows = db.execute(
            """
            SELECT c.raw_case_number, d.native_document_id
            FROM document_artifact d
            JOIN case_record c ON c.case_id=d.case_id
            ORDER BY c.raw_case_number
            """
        ).fetchall()
        assert [tuple(row) for row in rows] == [
            ("2024AP002484", "1149000"),
            ("2024AP002485", "1149000"),
        ]
    finally:
        db.close()


def test_wisconsin_shared_routes_preserve_native_selectors() -> None:
    wscca_route = query_state_courts.LIVE_ROUTES[
        query_state_courts.WISCONSIN_WSCCA_SOURCE_ID
    ]["search"]
    wscca_args = wscca_route.translate(
        _shared_args(
            "search",
            "Wisconsin Voter Alliance",
            "--source",
            query_state_courts.WISCONSIN_WSCCA_SOURCE_ID,
            "--entity-kind",
            "organization",
            "--limit",
            "12",
        ),
        wscca_route.adapter_command,
    )
    assert wscca_args.command == "search"
    assert wscca_args.scope == "business"
    assert wscca_args.limit == 12

    opinion_route = query_state_courts.LIVE_ROUTES[
        query_state_courts.WISCONSIN_OPINIONS_SOURCE_ID
    ]["documents"]
    opinion_args = opinion_route.translate(
        _shared_args(
            "documents",
            "2025AP000482",
            "--source",
            query_state_courts.WISCONSIN_OPINIONS_SOURCE_ID,
            "--search-field",
            "appeals-opinions",
            "--cursor",
            "metadata:appeals-opinions:page:2",
        ),
        opinion_route.adapter_command,
    )
    assert opinion_args.command == "search"
    assert opinion_args.collection == "appeals-opinions"
    assert opinion_args.case_number == "2025AP000482"
    assert opinion_args.page == 2

    keyword_args = opinion_route.translate(
        _shared_args(
            "documents",
            "Wisconsin Voter Alliance",
            "--source",
            query_state_courts.WISCONSIN_OPINIONS_SOURCE_ID,
            "--search-field",
            "keyword",
            "--court-id",
            query_wisconsin_opinions.SUPREME_COURT_ID,
            "--cursor",
            "fulltext:supreme:offset:10",
        ),
        opinion_route.adapter_command,
    )
    assert keyword_args.command == "keyword"
    assert keyword_args.court == "supreme"
    assert keyword_args.page == 2

    with pytest.raises(ValueError, match="Wisconsin full-text search"):
        opinion_route.translate(
            _shared_args(
                "documents",
                "Wisconsin Voter Alliance",
                "--source",
                query_state_courts.WISCONSIN_OPINIONS_SOURCE_ID,
                "--search-field",
                "keyword",
                "--court-id",
                "us-ny-appellate-division",
            ),
            opinion_route.adapter_command,
        )


def test_wisconsin_monitor_handlers_are_registered() -> None:
    wscca = public_records_monitor.HANDLER_REGISTRY[
        query_wisconsin_wscca.SOURCE_ID
    ]
    opinions = public_records_monitor.HANDLER_REGISTRY[
        query_wisconsin_opinions.SOURCE_ID
    ]

    assert wscca.handler is public_records_monitor.probe_wisconsin_wscca
    assert wscca.expected_requests == 4
    assert opinions.handler is public_records_monitor.probe_wisconsin_opinions
    assert opinions.expected_requests == 6
    assert opinions.sentinel_record_count == 6
