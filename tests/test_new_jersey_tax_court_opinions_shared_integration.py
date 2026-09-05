from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tools import query_new_jersey_tax_court_opinions as opinions
from tools import query_state_courts
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/new_jersey_tax_court_opinions"
)
RETRIEVED_AT = "2026-07-30T12:00:00Z"


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _shared_args(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def _envelope(
    operation: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=opinions.SOURCE_METADATA,
        jurisdiction=opinions.JURISDICTION,
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=RETRIEVED_AT,
    ).to_dict()


def _published_records() -> tuple[dict[str, Any], ...]:
    page = opinions.parse_index_page(
        _fixture("published_page.html"),
        collection="published",
        source_url=opinions.PUBLISHED_INDEX_URL,
    )
    return tuple(dict(record) for record in page.records)


def _duplicate_unpublished_records() -> tuple[dict[str, Any], ...]:
    page = opinions.parse_index_page(
        _fixture("unpublished_duplicates.html"),
        collection="unpublished",
        source_url=f"{opinions.UNPUBLISHED_INDEX_URL}?search=Giammarino",
    )
    return tuple(dict(record) for record in page.records)


def test_unified_router_preserves_query_docket_collection_and_limit_semantics() -> None:
    route = query_state_courts.LIVE_ROUTES[opinions.SOURCE_ID]["search"]
    exhaustive = route.translate(
        _shared_args(
            "search",
            "Freehold Township",
            "--source",
            opinions.SOURCE_ID,
            "--jurisdiction",
            "34",
            "--court-id",
            opinions.COURT_ID,
            "--after",
            "2025-01-01",
            "--before",
            "2026-12-31",
        ),
        route.adapter_command,
    )
    assert exhaustive.command == "search"
    assert exhaustive.query == "Freehold Township"
    assert exhaustive.docket is None
    assert exhaustive.collection == "both"
    assert exhaustive.all_pages is True
    assert exhaustive.limit is None
    assert exhaustive.minimum_interval == opinions.DEFAULT_MINIMUM_INTERVAL

    bounded = route.translate(
        _shared_args(
            "search",
            "Freehold Township",
            "--source",
            opinions.SOURCE_ID,
            "--search-field",
            "published",
            "--max-records",
            "12",
        ),
        route.adapter_command,
    )
    assert bounded.collection == "published"
    assert bounded.limit == 12
    assert bounded.all_pages is False

    case_route = query_state_courts.LIVE_ROUTES[opinions.SOURCE_ID]["case"]
    case = case_route.translate(
        _shared_args(
            "case",
            "000055-25",
            "--source",
            opinions.SOURCE_ID,
        ),
        case_route.adapter_command,
    )
    assert case.query is None
    assert case.docket == "000055-25"
    assert case.collection == "both"
    assert case.all_pages is True

    documents_route = query_state_courts.LIVE_ROUTES[
        opinions.SOURCE_ID
    ]["documents"]
    documents = documents_route.translate(
        _shared_args(
            "documents",
            "001040-2024",
            "--source",
            opinions.SOURCE_ID,
            "--document-type",
            "unpublished",
            "--limit",
            "2",
        ),
        documents_route.adapter_command,
    )
    assert documents.docket == "001040-2024"
    assert documents.collection == "unpublished"
    assert documents.limit == 2

    with pytest.raises(ValueError, match="cover New Jersey"):
        route.translate(
            _shared_args(
                "search",
                "Freehold",
                "--source",
                opinions.SOURCE_ID,
                "--jurisdiction",
                "24",
            ),
            route.adapter_command,
        )


def test_unified_download_keeps_official_url_and_representation_destination(
    tmp_path: Path,
) -> None:
    route = query_state_courts.LIVE_ROUTES[opinions.SOURCE_ID]["download"]
    source_url = (
        "https://www.njcourts.gov/system/files/court-opinions/"
        "2026/000052-2025.pdf"
    )
    destination = tmp_path / "opinion.md"
    translated = route.translate(
        _shared_args(
            "download",
            source_url,
            "--source",
            opinions.SOURCE_ID,
            "--destination",
            str(destination),
        ),
        route.adapter_command,
    )

    assert translated.command == "document"
    assert translated.url == source_url
    assert translated.save == destination
    assert translated.transport == "auto"
    assert translated.metadata_only is False


def test_index_occurrences_project_every_docket_without_collapsing_duplicates(
    tmp_path: Path,
) -> None:
    consolidated = _published_records()[0]
    duplicate_first, duplicate_second = _duplicate_unpublished_records()
    court_db = tmp_path / "courts.db"

    report = ingest_envelope(
        _envelope(
            "search",
            [consolidated, duplicate_first, duplicate_second],
        ),
        court_db=court_db,
    )

    assert report["projected"]["cases"] == 6
    assert report["projected"]["docket_entries"] == 6
    assert report["projected"]["documents"] == 6
    assert report["projected"]["parties"] == 0

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        cases = db.execute(
            """
            SELECT raw_case_number, caption
            FROM case_record
            ORDER BY raw_case_number
            """
        ).fetchall()
        assert [row["raw_case_number"] for row in cases] == [
            "000052-2025",
            "000054-2025",
            "000055-2025",
            "000056-2025",
            "001040-2024",
        ]
        assert cases[0]["caption"] == (
            "MT FREEHOLD BPE, LLC V FREEHOLD TOWNSHIP"
        )

        consolidated_documents = db.execute(
            """
            SELECT c.raw_case_number, d.native_document_id
            FROM document_artifact d
            JOIN case_record c USING(case_id)
            WHERE c.raw_case_number LIKE '0000%'
            ORDER BY c.raw_case_number
            """
        ).fetchall()
        assert len(consolidated_documents) == 4
        assert {
            row["native_document_id"] for row in consolidated_documents
        } == {consolidated["document"]["document_id"]}

        duplicate_entries = db.execute(
            """
            SELECT e.native_entry_id, e.event_date, e.raw_json
            FROM docket_entry e
            JOIN case_record c USING(case_id)
            WHERE c.raw_case_number='001040-2024'
            ORDER BY e.event_date
            """
        ).fetchall()
        assert [row["event_date"] for row in duplicate_entries] == [
            "2025-07-09",
            "2025-11-13",
        ]
        assert len({row["native_entry_id"] for row in duplicate_entries}) == 2
        assert all(
            '"new_jersey_tax_court_opinion_source_occurrence"' in row["raw_json"]
            for row in duplicate_entries
        )
        duplicate_documents = db.execute(
            """
            SELECT COUNT(*)
            FROM document_artifact d
            JOIN case_record c USING(case_id)
            WHERE c.raw_case_number='001040-2024'
            """
        ).fetchone()[0]
        assert duplicate_documents == 1
    finally:
        db.close()


def test_reader_document_hash_is_stored_as_extracted_representation(
    tmp_path: Path,
) -> None:
    parsed = opinions.parse_reader_document(
        _fixture("document_relay.txt"),
        source_url=(
            "https://www.njcourts.gov/system/files/court-opinions/"
            "2026/000052-2025.pdf"
        ),
    )
    record = {
        "record_type": "tax_court_opinion_document",
        "source_id": opinions.SOURCE_ID,
        "document_id": parsed.document_id,
        "source_url": parsed.source_url,
        "retrieval_transport": parsed.retrieval_transport,
        "media_type": parsed.media_type,
        "original_pdf_bytes_retrieved": False,
        "content_sha256": parsed.content_sha256,
        "content_hash_scope": parsed.content_hash_scope,
        "content_size": len(parsed.extracted_text or ""),
        "title": parsed.title,
        "page_count": parsed.page_count,
        "docket_components": list(parsed.docket_components),
        "docket_numbers": [
            component["normalized"] for component in parsed.docket_components
        ],
        "extracted_text": parsed.extracted_text,
        "saved_path": None,
    }
    court_db = tmp_path / "courts.db"

    report = ingest_envelope(
        _envelope("document", [record]),
        court_db=court_db,
    )

    assert report["projected"]["cases"] == 4
    assert report["projected"]["documents"] == 4
    assert report["projected"]["docket_entries"] == 0
    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(
            """
            SELECT native_document_id, sha256, mime_type, ocr_status,
                   certification_status, native_access_state
            FROM document_artifact
            """
        ).fetchall()
        assert len(rows) == 4
        assert {row["native_document_id"] for row in rows} == {
            parsed.document_id
        }
        assert {row["sha256"] for row in rows} == {parsed.content_sha256}
        assert {row["mime_type"] for row in rows} == {"text/markdown"}
        assert {row["ocr_status"] for row in rows} == {
            "reader_extracted_text"
        }
        assert {row["certification_status"] for row in rows} == {
            "reader_extracted_text"
        }
        assert {row["native_access_state"] for row in rows} == {
            "official_tax_court_opinion_reader_extracted_representation"
        }
    finally:
        db.close()
