from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import query_edva_bankruptcy
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_store import connect_courts


FIXTURE_DIR = Path("tests/fixtures/public_records/edva_bankruptcy")
RETRIEVED_AT = "2026-07-30T12:00:00Z"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _envelope(
    records: list[dict[str, Any]],
    *,
    operation: str = "entries",
) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=query_edva_bankruptcy.SOURCE_METADATA,
        jurisdiction=query_edva_bankruptcy.JURISDICTION,
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=RETRIEVED_AT,
        warnings=query_edva_bankruptcy.SOURCE_WARNINGS,
    ).to_dict()


def _normalized_docket(
    *,
    docket: dict[str, Any] | None = None,
    entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return query_edva_bankruptcy._normalize_docket(
        docket or _fixture("docket_49921079.json"),
        entries=entries or [],
        pages_fetched=1,
        next_cursor=None,
        incomplete_error=None,
        caller_limit=None,
    )


def test_projects_docket_entries_documents_and_source_occurrences(
    tmp_path: Path,
) -> None:
    first_page = _fixture("entries_page_1.json")["results"]
    second_page = _fixture("entries_page_2.json")["results"]
    first_document = first_page[0]["recap_documents"][0]
    first_document.update(
        {
            "is_available": True,
            "download_url": (
                "https://storage.courtlistener.com/recap/test-document.pdf"
            ),
            "filepath_ia": (
                "https://archive.org/download/test-item/test-document.pdf"
            ),
        }
    )
    first_page[0]["recap_documents"].append(
        {
            "id": 8002,
            "document_number": "1",
            "attachment_number": 1,
            "description": "Metadata-only attachment",
            "pacer_doc_id": "051012345679",
            "is_available": False,
            "page_count": 2,
            "filepath_local": "",
            "filepath_ia": "",
        }
    )
    record = _normalized_docket(entries=[*first_page, *second_page])
    court_db = tmp_path / "courts.db"

    report = ingest_envelope(_envelope([record]), court_db=court_db)

    assert report["projected"]["cases"] == 1
    assert report["projected"]["docket_entries"] == 3
    assert report["projected"]["documents"] == 2
    assert report["projected"]["restriction_events"] == 1

    db = connect_courts(court_db)
    try:
        case = db.execute("SELECT * FROM case_record").fetchone()
        assert case["source_internal_id"] == "49921079"
        assert case["raw_case_number"] == "05-39367"
        assert case["caption"] == "Frank C. Creer and Jean M. Creer"
        assert case["case_type"] == "bankruptcy"
        assert case["source_url"].startswith(
            "https://www.courtlistener.com/docket/49921079/"
        )
        assert case["native_access_state"] == "public"
        case_raw = json.loads(case["raw_json"])
        assert case_raw["native_access_state"] == (
            "courtlistener_recap_archive_with_coverage_gap"
        )
        assert case_raw["coverage"]["gap_reason"] == (
            "courtlistener_docket_blocked"
        )
        assert case_raw["access_paths"]["official_ecf"] == (
            query_edva_bankruptcy.EDVA_ECF_URL
        )

        court = db.execute("SELECT * FROM court").fetchone()
        assert court["court_id"] == query_edva_bankruptcy.COURT_ID
        assert court["native_court_id"] == (
            query_edva_bankruptcy.COURTLISTENER_COURT_ID
        )
        assert court["official_url"] == query_edva_bankruptcy.EDVA_ECF_URL

        entries = db.execute(
            """
            SELECT native_entry_id, sequence_no, document_available,
                   snapshot_id, raw_json
            FROM docket_entry
            ORDER BY CAST(sequence_no AS INTEGER)
            """
        ).fetchall()
        assert [row["native_entry_id"] for row in entries] == [
            "7001",
            "7002",
            "7003",
        ]
        assert entries[0]["document_available"] == 1
        assert entries[1]["document_available"] == 0
        assert all(row["snapshot_id"] == report["snapshot_id"] for row in entries)
        assert (
            json.loads(entries[0]["raw_json"])["canonical_ref"]
            == "courtlistener:docket-entry:7001"
        )

        documents = db.execute(
            """
            SELECT d.*, e.native_entry_id
            FROM document_artifact d
            JOIN docket_entry e
              ON e.docket_entry_id=d.docket_entry_id
            ORDER BY d.native_document_id
            """
        ).fetchall()
        document = documents[0]
        assert document["native_document_id"] == "8001"
        assert document["native_entry_id"] == "7001"
        assert document["source_url"] == (
            "https://storage.courtlistener.com/recap/test-document.pdf"
        )
        assert document["page_count"] == 12
        assert document["storage_path"] is None
        assert document["native_access_state"] == (
            "recap_archive_document_available"
        )
        metadata_only = documents[1]
        assert metadata_only["native_document_id"] == "8002"
        assert metadata_only["access_state"] == "unknown"
        assert metadata_only["native_access_state"] == (
            "recap_archive_document_metadata_only"
        )
        assert metadata_only["source_url"] is None

        occurrences = db.execute(
            """
            SELECT record_kind, source_internal_id, source_result_id,
                   raw_json
            FROM case_source_occurrence
            ORDER BY occurrence_id
            """
        ).fetchall()
        assert len(occurrences) == 6
        assert {
            row["record_kind"] for row in occurrences
        } == {
            "federal_bankruptcy_docket",
            "federal_bankruptcy_docket_entry",
            "federal_bankruptcy_docket_document",
        }
        assert {
            row["source_internal_id"] for row in occurrences
        } == {"49921079", "7001", "7002", "7003", "8001", "8002"}
        document_occurrence = next(
            row
            for row in occurrences
            if row["record_kind"]
            == "federal_bankruptcy_docket_document"
            and row["source_internal_id"] == "8001"
        )
        document_observation = json.loads(document_occurrence["raw_json"])
        assert document_observation["pacer_doc_id"] == "051012345678"
        assert document_observation["is_available"] is True
        assert document_observation["download_url"].endswith(
            "test-document.pdf"
        )
    finally:
        db.close()


@pytest.mark.parametrize(
    ("date_blocked", "gap_reason", "restriction_count"),
    [
        ("2021-01-28", "courtlistener_docket_blocked", 1),
        (None, "no_recap_entries_returned", 0),
    ],
)
def test_empty_recap_entries_preserve_a_case_and_coverage_gap(
    tmp_path: Path,
    date_blocked: str | None,
    gap_reason: str,
    restriction_count: int,
) -> None:
    docket = _fixture("docket_49921079.json")
    docket["date_blocked"] = date_blocked
    record = _normalized_docket(docket=docket, entries=[])
    court_db = tmp_path / "courts.db"

    report = ingest_envelope(_envelope([record]), court_db=court_db)

    assert report["source_status"] == "ok"
    assert report["projected"]["cases"] == 1
    assert report["projected"]["docket_entries"] == 0
    assert report["projected"]["documents"] == 0
    assert (
        report["projected"]["restriction_events"] == restriction_count
    )
    db = connect_courts(court_db)
    try:
        case = db.execute("SELECT * FROM case_record").fetchone()
        assert case is not None
        assert case["access_state"] == "public"
        assert case["native_access_state"] == "public"
        case_raw = json.loads(case["raw_json"])
        assert case_raw["native_access_state"] == (
            "courtlistener_recap_archive_with_coverage_gap"
        )
        assert case_raw["coverage"]["document_access_gap"] is True
        assert case_raw["coverage"]["gap_reason"] == gap_reason
        assert db.execute(
            "SELECT COUNT(*) FROM case_source_occurrence"
        ).fetchone()[0] == 1
        if restriction_count:
            restriction = db.execute(
                "SELECT * FROM restriction_event"
            ).fetchone()
            assert restriction["native_event_type"] == (
                "courtlistener_docket_blocked"
            )
            assert "official PACER/ECF docket" in restriction["reason"]
    finally:
        db.close()


def test_courtlistener_docket_id_is_the_case_identity(
    tmp_path: Path,
) -> None:
    first = _fixture("docket_49921079.json")
    second = dict(first)
    second.update(
        {
            "id": 59921079,
            "case_name": "Second CourtListener Docket Identity",
            "absolute_url": "/docket/59921079/second-identity/",
        }
    )
    records = [
        _normalized_docket(docket=first),
        _normalized_docket(docket=second),
    ]
    court_db = tmp_path / "courts.db"

    report = ingest_envelope(_envelope(records), court_db=court_db)

    assert report["projected"]["cases"] == 2
    db = connect_courts(court_db)
    try:
        cases = db.execute(
            """
            SELECT raw_case_number, source_internal_id, caption
            FROM case_record
            ORDER BY source_internal_id
            """
        ).fetchall()
        assert [row["source_internal_id"] for row in cases] == [
            "49921079",
            "59921079",
        ]
        assert {row["raw_case_number"] for row in cases} == {"05-39367"}
    finally:
        db.close()
