from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tools import (
    ingest_state_court_records as ingest,
    query_california_opinions as opinions,
    query_state_courts,
)
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "california_opinions"
)
RETRIEVED_AT = "2026-07-30T22:00:00Z"


def _shared_args(*values: str) -> Any:
    return query_state_courts.build_parser().parse_args(list(values))


def _artifact(
    name: str,
    *,
    source_url: str,
    body: bytes | None = None,
) -> opinions.Artifact:
    return opinions.Artifact(
        content=body or (FIXTURE_ROOT / name).read_bytes(),
        source_url=source_url,
        media_type="text/html",
        headers={"content-type": "text/html"},
    )


def _listing_record(
    collection: str,
    *,
    body: bytes | None = None,
    index: int = 0,
) -> dict[str, Any]:
    page = opinions.parse_listing_page(
        _artifact(
            f"{collection}.html",
            source_url=(
                f"{opinions.COLLECTIONS[collection]['url']}"
                "?items_per_page=50&page=0"
            ),
            body=body,
        ),
        collection=collection,
        requested_page=0,
        requested_page_size=50,
    )
    return dict(page.records[index])


def _detail_record(
    name: str = "detail-published.html",
    *,
    source_url: str = (
        "https://courts.ca.gov/opinion/published/2026-07-30/s287786"
    ),
) -> dict[str, Any]:
    return opinions.parse_detail_page(
        _artifact(name, source_url=source_url)
    )


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


def test_shared_routes_preserve_native_search_and_exact_download_semantics(
    tmp_path: Path,
) -> None:
    routes = query_state_courts.LIVE_ROUTES[opinions.SOURCE_ID]

    assert set(routes) == {
        "case",
        "discovery",
        "documents",
        "download",
        "probe",
        "search",
    }
    assert "detail" not in routes

    inferred_case = routes["search"].translate(
        _shared_args(
            "search",
            "S287786",
            "--source",
            opinions.SOURCE_ID,
        ),
        routes["search"].adapter_command,
    )
    title = routes["search"].translate(
        _shared_args(
            "search",
            "Sanmiguel",
            "--source",
            opinions.SOURCE_ID,
            "--search-field",
            "title",
            "--case-type",
            "published",
            "--court-id",
            "ca-supreme-court",
            "--max-records",
            "12",
        ),
        routes["search"].adapter_command,
    )
    exact_case = routes["case"].translate(
        _shared_args(
            "case",
            "H052909",
            "--source",
            opinions.SOURCE_ID,
            "--case-type",
            "unpublished",
        ),
        routes["case"].adapter_command,
    )
    documents = routes["documents"].translate(
        _shared_args(
            "documents",
            "H052909",
            "--source",
            opinions.SOURCE_ID,
            "--document-type",
            "unpublished",
        ),
        routes["documents"].adapter_command,
    )
    destination = tmp_path / "S287786.PDF"
    download = routes["download"].translate(
        _shared_args(
            "download",
            "https://www.courts.ca.gov/opinions/documents/S287786.PDF",
            "--source",
            opinions.SOURCE_ID,
            "--destination",
            str(destination),
        ),
        routes["download"].adapter_command,
    )

    assert inferred_case.command == "search"
    assert inferred_case.collection == "both"
    assert inferred_case.case_number == "S287786"
    assert inferred_case.title is None
    assert inferred_case.page == 0
    assert inferred_case.page_size == 100
    assert title.collection == "published"
    assert title.court == "ca-supreme-court"
    assert title.case_number is None
    assert title.title == "Sanmiguel"
    assert title.limit == 12
    assert exact_case.command == "search"
    assert exact_case.collection == "unpublished"
    assert exact_case.case_number == "H052909"
    assert documents.command == "search"
    assert documents.collection == "unpublished"
    assert download.command == "download"
    assert download.url.endswith("/opinions/documents/S287786.PDF")
    assert download.destination == destination


def test_discovery_probe_guidance_and_selector_validation() -> None:
    routes = query_state_courts.LIVE_ROUTES[opinions.SOURCE_ID]
    manifest = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "manifest",
            "--source",
            opinions.SOURCE_ID,
        ),
        routes["discovery"].adapter_command,
    )
    alternatives = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "alternatives",
            "--source",
            opinions.SOURCE_ID,
        ),
        routes["discovery"].adapter_command,
    )
    probe = routes["probe"].translate(
        _shared_args(
            "probe",
            "--source",
            opinions.SOURCE_ID,
        ),
        routes["probe"].adapter_command,
    )

    assert manifest.command == "manifest"
    assert alternatives.command == "alternatives"
    assert probe.command == "probe"
    guidance = query_state_courts._source_guidance(opinions.SOURCE_ID)
    assert guidance["current_windows_days"] == {
        "published": 120,
        "unpublished": 60,
    }
    assert guidance["unified_operations"] == [
        "case",
        "discovery",
        "documents",
        "download",
        "probe",
        "search",
    ]
    assert "complete case dockets" in guidance["note"]

    with pytest.raises(ValueError, match="date-range"):
        routes["search"].translate(
            _shared_args(
                "search",
                "Sanmiguel",
                "--source",
                opinions.SOURCE_ID,
                "--after",
                "2026-07-01",
            ),
            routes["search"].adapter_command,
        )
    with pytest.raises(ValueError, match="exact document URL"):
        routes["download"].translate(
            _shared_args(
                "download",
                "S287786",
                "--source",
                opinions.SOURCE_ID,
                "--case-number",
                "S287786",
                "--destination",
                "/tmp/S287786.PDF",
            ),
            routes["download"].adapter_command,
        )


def test_shared_adapter_wrapper_forwards_source_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route = query_state_courts.LIVE_ROUTES[opinions.SOURCE_ID]["case"]
    translated = route.translate(
        _shared_args(
            "case",
            "S287786",
            "--source",
            opinions.SOURCE_ID,
        ),
        route.adapter_command,
    )
    captured: dict[str, Any] = {}
    sentinel = object()

    def fake_execute(args: Any, *, client: Any = None, log_results: bool = True):
        captured["args"] = vars(args)
        captured["client"] = client
        captured["log_results"] = log_results
        return sentinel

    monkeypatch.setattr(opinions, "execute", fake_execute)
    returned = route.adapter.execute(
        translated,
        access_decision={"allowed": True, "reason_code": "open"},
    )

    assert returned is sentinel
    assert captured["args"]["command"] == "search"
    assert captured["args"]["case_number"] == "S287786"


def test_index_then_detail_adds_docx_without_duplicate_event_or_case(
    tmp_path: Path,
) -> None:
    index_record = _listing_record("published")
    detail_record = _detail_record()
    court_db = tmp_path / "courts.db"

    index_report = ingest.ingest_envelope(
        _envelope("search", [index_record]),
        court_db=court_db,
    )
    assert index_report["projected"]["cases"] == 1
    assert index_report["projected"]["docket_entries"] == 1
    assert index_report["projected"]["documents"] == 1
    assert index_report["projected"]["parties"] == 0

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        index_event = json.loads(
            db.execute("SELECT raw_json FROM docket_entry").fetchone()[0]
        )
        assert index_event["collection"] == "published"
        assert index_event["document_version"] == "slip_opinion_as_filed"
        assert index_event["citation_status"] == "citable"
        assert index_event["corrected_official_reports"]["included"] is False
        assert index_event["case_information_complement"]["url"].startswith(
            opinions.APPELLATE_CASE_INFORMATION_URL
        )
        assert index_event["citings_archive"] == {
            "independent_corroboration": False,
            "role": "ancillary_source_snapshot",
            "url": index_record["citings_archive_url"],
        }
    finally:
        db.close()

    detail_report = ingest.ingest_envelope(
        _envelope("detail", [detail_record]),
        court_db=court_db,
    )
    assert detail_report["projected"]["cases"] == 1
    assert detail_report["projected"]["docket_entries"] == 1
    assert detail_report["projected"]["documents"] == 2
    assert detail_report["snapshot_only"]["record_count"] == 0

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        case = db.execute(
            """
            SELECT raw_case_number, caption, case_type, disposition_date,
                   status, native_access_state, raw_json
            FROM case_record
            """
        ).fetchone()
        assert case is not None
        assert case["raw_case_number"] == "S287786"
        assert case["caption"] == index_record["title"]
        assert case["case_type"] == "appellate"
        assert case["disposition_date"] == "2026-07-30"
        assert case["status"] is None
        assert case["native_access_state"] == "public"
        case_payload = json.loads(case["raw_json"])
        assert case_payload["preserve_existing_case_fields"] is True
        assert case_payload["native_access_state"] == (
            "official_partial_opinion_case_shell"
        )
        assert db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM case_party").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM docket_entry").fetchone()[0] == 1
        documents = db.execute(
            """
            SELECT source_url, mime_type, native_access_state
            FROM document_artifact
            ORDER BY source_url
            """
        ).fetchall()
        assert len(documents) == 2
        assert {Path(row["source_url"]).suffix.casefold() for row in documents} == {
            ".docx",
            ".pdf",
        }
        assert all(
            row["native_access_state"].startswith(
                "official_slip_opinion_as_filed_"
            )
            for row in documents
        )
        event = json.loads(
            db.execute("SELECT raw_json FROM docket_entry").fetchone()[0]
        )
        assert event["event_type"] == "appellate_opinion_publication"
        assert event["california_opinion_source_occurrence"]["record_kind"] == (
            "appellate_opinion_detail"
        )
    finally:
        db.close()


def test_modified_identifier_keeps_base_case_crosswalk_and_distinct_occurrences(
    tmp_path: Path,
) -> None:
    original = _listing_record("published")
    modified_body = (
        (FIXTURE_ROOT / "published.html")
        .read_bytes()
        .replace(b"S287786", b"S287786M")
        .replace(b"s287786", b"s287786m")
        .replace(
            b"query_caseNumber=S287786M",
            b"query_caseNumber=S287786",
        )
    )
    modified = _listing_record("published", body=modified_body)
    court_db = tmp_path / "courts.db"

    report = ingest.ingest_envelope(
        _envelope("search", [original, modified]),
        court_db=court_db,
    )

    assert report["projected"]["cases"] == 2
    assert report["projected"]["docket_entries"] == 2
    assert report["projected"]["documents"] == 2
    assert report["projected"]["parties"] == 0
    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        assert db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0] == 1
        case = db.execute(
            "SELECT raw_case_number FROM case_record"
        ).fetchone()
        assert case["raw_case_number"] == "S287786"
        events = db.execute(
            "SELECT native_entry_id, raw_json FROM docket_entry"
        ).fetchall()
        assert len({row["native_entry_id"] for row in events}) == 2
        identifiers = {
            json.loads(row["raw_json"])["opinion_identifier"]
            for row in events
        }
        assert identifiers == {"S287786", "S287786M"}
        document_urls = {
            row[0]
            for row in db.execute(
                "SELECT source_url FROM document_artifact"
            )
        }
        assert any(url.endswith("/S287786.PDF") for url in document_urls)
        assert any(url.endswith("/S287786M.PDF") for url in document_urls)
    finally:
        db.close()


def test_citings_archive_remains_an_ancillary_snapshot(
    tmp_path: Path,
) -> None:
    record = opinions.parse_citings_page(
        _artifact(
            "citings.html",
            source_url=(
                "https://courts.ca.gov/opinion/"
                "citings-archive/2026-07-30/s287786"
            ),
        )
    )

    report = ingest.ingest_envelope(
        _envelope("citings", [record]),
        court_db=tmp_path / "courts.db",
    )

    assert report["projected"]["cases"] == 0
    assert report["snapshot_only"] == {
        "record_count": 1,
        "record_kinds": {"opinion_citings_archive": 1},
    }
    assert ingest.CALIFORNIA_OPINIONS_SOURCE_ID == opinions.SOURCE_ID
