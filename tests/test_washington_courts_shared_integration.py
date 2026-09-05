from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tools import ingest_state_court_records as ingest
from tools import query_state_courts
from tools import query_washington_courts as washington
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "washington_courts"
)
RETRIEVED_AT = "2026-07-30T12:00:00Z"


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _artifact(
    name: str,
    url: str,
    *,
    media_type: str = "text/html",
) -> washington.Artifact:
    return washington.Artifact(
        content=_fixture(name),
        source_url=url,
        media_type=media_type,
        headers={"content-type": media_type},
    )


class _QueueClient:
    def __init__(self, responses: list[washington.Artifact]) -> None:
        self.responses = list(responses)

    def get(self, _url: str, **_kwargs: Any) -> washington.Artifact:
        if not self.responses:
            raise AssertionError("unexpected Washington source request")
        return self.responses.pop(0)

    def close(self) -> None:
        return None


def _shared_args(*values: str) -> Any:
    return query_state_courts.build_parser().parse_args(list(values))


def _envelope(
    source_id: str,
    operation: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=washington.SOURCE_METADATA[source_id],
        jurisdiction=washington._jurisdiction(),
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=RETRIEVED_AT,
    ).to_dict()


def test_shared_routes_keep_opinions_and_directory_as_distinct_components(
    tmp_path: Path,
) -> None:
    opinion_routes = query_state_courts.LIVE_ROUTES[
        washington.OPINIONS_SOURCE_ID
    ]
    assert set(opinion_routes) == {
        "search",
        "case",
        "documents",
        "download",
    }

    search = opinion_routes["search"].translate(
        _shared_args(
            "search",
            "Farah",
            "--source",
            washington.OPINIONS_SOURCE_ID,
            "--jurisdiction",
            "WA",
        ),
        opinion_routes["search"].adapter_command,
    )
    assert search.command == "opinions-list"
    assert search.scope == "all"
    assert search.query == "Farah"
    assert search.limit is None

    bounded = opinion_routes["search"].translate(
        _shared_args(
            "search",
            "*",
            "--source",
            washington.OPINIONS_SOURCE_ID,
            "--max-records",
            "12",
        ),
        opinion_routes["search"].adapter_command,
    )
    assert bounded.query is None
    assert bounded.limit == 12

    case = opinion_routes["case"].translate(
        _shared_args(
            "case",
            "88366-6",
            "--source",
            washington.OPINIONS_SOURCE_ID,
        ),
        opinion_routes["case"].adapter_command,
    )
    assert case.command == "opinion-detail"
    assert case.identifier == "88366-6"

    documents = opinion_routes["documents"].translate(
        _shared_args(
            "documents",
            "883666MAJ",
            "--source",
            washington.OPINIONS_SOURCE_ID,
            "--document-type",
            "opinion",
        ),
        opinion_routes["documents"].adapter_command,
    )
    assert documents.command == "opinion-detail"
    assert documents.identifier == "883666MAJ"

    destination = tmp_path / "88366-6.pdf"
    download = opinion_routes["download"].translate(
        _shared_args(
            "download",
            "88366-6",
            "--source",
            washington.OPINIONS_SOURCE_ID,
            "--destination",
            str(destination),
        ),
        opinion_routes["download"].adapter_command,
    )
    assert download.command == "opinion-download"
    assert download.destination == destination

    with pytest.raises(ValueError, match="date-range"):
        opinion_routes["search"].translate(
            _shared_args(
                "search",
                "Farah",
                "--source",
                washington.OPINIONS_SOURCE_ID,
                "--after",
                "2026-01-01",
            ),
            opinion_routes["search"].adapter_command,
        )

    directory_route = query_state_courts.LIVE_ROUTES[
        washington.DIRECTORY_SOURCE_ID
    ]["search"]
    directory = directory_route.translate(
        _shared_args(
            "search",
            "Whedbee",
            "--source",
            washington.DIRECTORY_SOURCE_ID,
            "--search-field",
            "judge",
            "--first-name",
            "J",
            "--limit",
            "7",
        ),
        directory_route.adapter_command,
    )
    assert directory.command == "directory-search"
    assert directory.last_name == "Whedbee"
    assert directory.initial == "J"
    assert directory.limit == 7


def test_directory_people_remain_snapshot_only(tmp_path: Path) -> None:
    people, _total = washington.parse_directory_people(
        _artifact(
            "directory_master.html",
            washington.DIRECTORY_MASTER_URL,
        )
    )
    court_db = tmp_path / "courts.db"

    report = ingest_envelope(
        _envelope(
            washington.DIRECTORY_SOURCE_ID,
            "directory-search",
            people,
        ),
        court_db=court_db,
    )

    assert report["projected"]["cases"] == 0
    assert report["snapshot_only"] == {
        "record_count": 2,
        "record_kinds": {"court_directory_person": 2},
    }


def test_current_supreme_court_docket_format_projects_with_source_comma() -> None:
    assert ingest._washington_opinion_case_numbers(
        {
            "case_number": "104,108-0 / 88366-6",
            "fields": {"docket_number": "104,108-0"},
        }
    ) == ["104,108-0", "88366-6"]


def test_opinion_occurrences_information_and_pdf_versions_keep_every_docket(
    tmp_path: Path,
) -> None:
    listing = dict(
        washington.parse_opinion_list(
            _artifact(
                "opinions_year.html",
                washington.OPINIONS_INDEX_URL,
            ),
            scope="year",
            year=2026,
            court_level="C",
            publication_status="UNP",
            query_text="Farah",
            limit=None,
        )[0]
    )
    detail = dict(
        washington.parse_opinion_info(
            _artifact(
                "opinion_info.html",
                washington.OPINIONS_INDEX_URL,
            ),
            "883666MAJ",
        )
    )

    pdf = b"%PDF-1.7\nfixture Washington opinion\n%%EOF\n"
    downloaded = washington.execute(
        washington.build_parser().parse_args(
            [
                "opinion-download",
                "88366-6",
                str(tmp_path / "88366-6.pdf"),
            ]
        ),
        client=_QueueClient(
            [
                _artifact(
                    "opinion_info.html",
                    washington.OPINIONS_INDEX_URL,
                ),
                washington.Artifact(
                    content=pdf,
                    source_url=f"{washington.OPINIONS_PDF_BASE}883666.pdf",
                    media_type="application/pdf",
                    headers={"content-type": "application/pdf"},
                ),
            ]
        ),
        log_results=False,
    )
    artifact_record = dict(downloaded.records[0])
    assert artifact_record["court"] == "Court of Appeals Division I"
    assert artifact_record["fields"]["title_of_case"].startswith("Farah")

    consolidated_dockets = ["88366-6", "88872-2"]
    listing["case_number"] = "88366-6 / 88872-2"
    detail["case_number"] = consolidated_dockets
    detail["fields"]["docket_number"] = consolidated_dockets
    artifact_record["case_number"] = consolidated_dockets
    artifact_record["fields"] = dict(artifact_record["fields"])
    artifact_record["fields"]["docket_number"] = consolidated_dockets
    court_db = tmp_path / "courts.db"

    report = ingest_envelope(
        _envelope(
            washington.OPINIONS_SOURCE_ID,
            "opinion-chain",
            [listing, detail, artifact_record],
        ),
        court_db=court_db,
    )

    assert report["projected"]["cases"] == 6
    assert report["projected"]["docket_entries"] == 4
    assert report["projected"]["documents"] == 12

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        cases = db.execute(
            """
            SELECT raw_case_number, court_id, caption, disposition_date
            FROM case_record
            ORDER BY raw_case_number
            """
        ).fetchall()
        assert [row["raw_case_number"] for row in cases] == consolidated_dockets
        assert {row["court_id"] for row in cases} == {
            "wa-court-of-appeals-division-i"
        }
        assert {row["disposition_date"] for row in cases} == {"2026-07-27"}

        occurrences = db.execute(
            """
            SELECT c.raw_case_number, e.native_entry_id, e.raw_json
            FROM docket_entry e
            JOIN case_record c USING(case_id)
            ORDER BY c.raw_case_number, e.native_entry_id
            """
        ).fetchall()
        assert len(occurrences) == 4
        assert {
            row["raw_case_number"] for row in occurrences
        } == set(consolidated_dockets)
        assert all(
            '"washington_opinion_source_occurrence"' in row["raw_json"]
            for row in occurrences
        )

        documents = db.execute(
            """
            SELECT c.raw_case_number, d.native_document_id, d.sha256,
                   d.mime_type, d.storage_path
            FROM document_artifact d
            JOIN case_record c USING(case_id)
            ORDER BY c.raw_case_number, d.native_document_id, d.sha256
            """
        ).fetchall()
        assert len(documents) == 8
        assert {
            row["native_document_id"]
            for row in documents
            if row["mime_type"] == "text/html"
        } == {"wa-opinion-information:883666MAJ"}
        assert {
            row["native_document_id"]
            for row in documents
            if row["mime_type"] == "application/pdf"
        } == {"wa-opinion-pdf:883666.pdf"}
        for docket in consolidated_dockets:
            docket_documents = [
                row for row in documents if row["raw_case_number"] == docket
            ]
            assert len(docket_documents) == 4
            assert sum(row["sha256"] is not None for row in docket_documents) == 2
            assert any(row["storage_path"] for row in docket_documents)
    finally:
        db.close()
