from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import yaml

from tools import public_records_monitor
from tools import query_state_courts
from tools import query_texas_supreme_publications as publications
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
    / "texas_supreme_publications"
)
RELEASE_URL = (
    "https://www.txcourts.gov/supreme/orders-opinions/"
    "2026/may/may-29-2026/"
)
RETRIEVED_AT = "2026-07-31T12:00:00Z"


def _artifact(name: str, source_url: str) -> publications.Artifact:
    return publications.Artifact(
        content=(FIXTURE_DIR / name).read_bytes(),
        source_url=source_url,
        media_type=(
            "application/pdf" if name.endswith(".pdf") else "text/html"
        ),
        headers={},
    )


class FixtureClient:
    def landing(self) -> publications.Artifact:
        return _artifact("landing.html", publications.LANDING_URL)

    def annual(self, year: int) -> publications.Artifact:
        assert year == 2026
        return _artifact("annual-2026.html", publications.annual_url(year))

    def release(self, source_url: str) -> publications.Artifact:
        assert source_url == RELEASE_URL
        return _artifact("release-2026-05-29.html", source_url)

    def document(self, source_url: str) -> publications.Artifact:
        return _artifact("sample.pdf", source_url)


def _shared_args(*values: str) -> Any:
    return query_state_courts.build_parser().parse_args(list(values))


def _publication_records() -> list[dict[str, Any]]:
    page = publications.parse_release_page(
        _artifact("release-2026-05-29.html", RELEASE_URL),
        expected_date="2026-05-29",
    )
    return [dict(record) for record in page.records]


def _envelope(records: list[dict[str, Any]]) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=publications.SOURCE_METADATA,
        jurisdiction=publications.JURISDICTION,
        query=QueryMetadata(operation="search", parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=RETRIEVED_AT,
    ).to_dict()


def test_shared_routes_preserve_date_scope_exact_case_and_omitted_limit(
    tmp_path: Path,
) -> None:
    routes = query_state_courts.LIVE_ROUTES[publications.SOURCE_ID]
    assert set(routes) == {
        "search",
        "case",
        "documents",
        "detail",
        "discovery",
        "probe",
        "download",
    }

    search = routes["search"].translate(
        _shared_args(
            "search",
            "Huffman",
            "--source",
            publications.SOURCE_ID,
            "--jurisdiction",
            "TX",
            "--court-id",
            publications.COURT_ID,
            "--after",
            "2026-01-01",
            "--before",
            "2026-12-31",
        ),
        routes["search"].adapter_command,
    )
    assert search.command == "search"
    assert search.query == "Huffman"
    assert search.date_from == "2026-01-01"
    assert search.date_to == "2026-12-31"
    assert search.limit is None

    case = routes["case"].translate(
        _shared_args(
            "case",
            "24-0205",
            "--source",
            publications.SOURCE_ID,
            "--after",
            "2026-01-01",
            "--before",
            "2026-12-31",
        ),
        routes["case"].adapter_command,
    )
    assert case.command == "search"
    assert case.query == "*"
    assert case.case_number == "24-0205"

    documents = routes["documents"].translate(
        _shared_args(
            "documents",
            "24-0286",
            "--source",
            publications.SOURCE_ID,
            "--document-type",
            "dissenting_opinion",
            "--after",
            "2026-01-01",
            "--before",
            "2026-12-31",
        ),
        routes["documents"].adapter_command,
    )
    assert documents.case_number == "24-0286"
    assert documents.document_type == ["dissenting_opinion"]

    detail = routes["detail"].translate(
        _shared_args(
            "detail",
            "2026-05-29",
            "--source",
            publications.SOURCE_ID,
        ),
        routes["detail"].adapter_command,
    )
    assert detail.command == "release"
    assert detail.release_date == "2026-05-29"

    years = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "years",
            "--source",
            publications.SOURCE_ID,
        ),
        routes["discovery"].adapter_command,
    )
    assert years.command == "years"

    destination = tmp_path / "publication.pdf"
    download = routes["download"].translate(
        _shared_args(
            "download",
            "https://www.txcourts.gov/media/1462796/240205.pdf",
            "--source",
            publications.SOURCE_ID,
            "--destination",
            str(destination),
        ),
        routes["download"].adapter_command,
    )
    assert download.command == "download"
    assert download.destination == destination

    assert query_state_courts._source_guidance(publications.SOURCE_ID)[
        "unified_operations"
    ] == sorted(routes)


def test_ingestion_preserves_release_occurrence_and_document_identities(
    tmp_path: Path,
) -> None:
    record = _publication_records()[0]
    court_db = tmp_path / "courts.db"
    report = ingest_envelope(
        _envelope([record]),
        court_db=court_db,
    )
    assert report["projected"]["cases"] == 1
    assert report["projected"]["docket_entries"] == 1
    assert report["projected"]["documents"] == 4
    assert report["projected"]["case_relations"] == 0
    assert report["snapshot_only"]["record_count"] == 0

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        case = db.execute(
            """
            SELECT source_id, raw_case_number, caption, raw_json
            FROM case_record
            """
        ).fetchone()
        assert case["source_id"] == publications.SOURCE_ID
        assert case["raw_case_number"] == "24-0205"
        assert case["caption"].startswith("HUFFMAN ASSET MANAGEMENT")
        case_raw = json.loads(case["raw_json"])
        assert case_raw["record_identity_source_candidate"] == (
            publications.RECORD_IDENTITY_SOURCE_ID
        )
        assert case_raw["lower_court_candidate"][
            "authoritative_assignment"
        ] is False

        occurrence = db.execute(
            """
            SELECT source_id, record_identity_source_id, source_result_id,
                   filing_location, raw_json
            FROM case_source_occurrence
            """
        ).fetchone()
        assert occurrence["source_id"] == publications.SOURCE_ID
        assert occurrence["record_identity_source_id"] == (
            publications.SOURCE_ID
        )
        assert occurrence["source_result_id"] == (
            "TXSC-RELEASE:2026-05-29:24-0205:1"
        )
        assert occurrence["filing_location"] == "Dallas County"
        occurrence_raw = json.loads(occurrence["raw_json"])
        assert occurrence_raw["record_identity_source_candidate"] == (
            publications.RECORD_IDENTITY_SOURCE_ID
        )
        assert occurrence_raw["independent_corroboration"] is False

        docket = db.execute(
            """
            SELECT native_entry_id, event_code, event_date, raw_json
            FROM docket_entry
            """
        ).fetchone()
        assert docket["native_entry_id"] == (
            "TXSC-RELEASE:2026-05-29:24-0205:1"
        )
        assert docket["event_code"] == "supreme_court_hand_down"
        assert docket["event_date"] == "2026-05-29"
        docket_raw = json.loads(docket["raw_json"])
        assert docket_raw["section_heading_raw"] == "ORDERS ON CAUSES"
        assert "reverses" in docket_raw["disposition_text"]

        documents = db.execute(
            """
            SELECT native_document_id, document_type, filed_date, source_url
            FROM document_artifact
            ORDER BY native_document_id
            """
        ).fetchall()
        assert len({row["native_document_id"] for row in documents}) == 4
        assert {row["document_type"] for row in documents} == {
            "print_order_release",
            "editorial_case_summary",
            "court_opinion",
            "concurring_opinion",
        }
        assert all(row["filed_date"] == "2026-05-29" for row in documents)
    finally:
        db.close()


def test_archive_inventory_records_remain_snapshot_only(
    tmp_path: Path,
) -> None:
    records = publications.parse_landing(
        _artifact("landing.html", publications.LANDING_URL)
    )
    report = ingest_envelope(
        _envelope(records),
        court_db=tmp_path / "courts.db",
    )
    assert report["projected"]["cases"] == 0
    assert report["snapshot_only"]["record_count"] == len(records)
    assert "network_outage_document" in report["snapshot_only"]["record_kinds"]


def _probe_result(
    *,
    landing_sha256: str,
    release_sha256: str,
    release_case_count: int,
) -> PublicRecordsResult:
    result = publications.execute(
        publications.build_parser().parse_args(["probe"]),
        client=FixtureClient(),
        log_results=False,
    )
    payload = result.to_dict()["records"][0]
    payload["rolling_observation"]["landing_sha256"] = landing_sha256
    payload["rolling_observation"]["release_page_sha256"] = release_sha256
    payload["release_case_count"] = release_case_count
    query = PublicRecordsQuery(
        source=publications.SOURCE_METADATA,
        jurisdiction=publications.JURISDICTION,
        query=QueryMetadata(operation="probe", parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        [payload],
        retrieved_at=RETRIEVED_AT,
    )


def test_monitor_separates_stable_contract_from_rolling_artifacts(
    monkeypatch,
) -> None:
    context = ProbeContext(
        source_id=publications.SOURCE_ID,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.2},
        },
        timeout=1,
        max_attempts=1,
        sample_bytes=None,
    )
    first_result = _probe_result(
        landing_sha256="a" * 64,
        release_sha256="b" * 64,
        release_case_count=3,
    )
    second_result = _probe_result(
        landing_sha256="c" * 64,
        release_sha256="d" * 64,
        release_case_count=4,
    )
    monkeypatch.setattr(
        public_records_monitor.query_texas_supreme_publications,
        "execute",
        lambda args, log_results=False: first_result,
    )
    first = public_records_monitor.probe_texas_supreme_publications(context)

    monkeypatch.setattr(
        public_records_monitor.query_texas_supreme_publications,
        "execute",
        lambda args, log_results=False: second_result,
    )
    second = public_records_monitor.probe_texas_supreme_publications(context)

    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["requests_made"] == 4
    assert first.details["rolling_observation"]["landing_sha256"] == "a" * 64
    assert second.details["rolling_observation"]["landing_sha256"] == "c" * 64
    assert first.details["release_case_count"] == 3
    assert second.details["release_case_count"] == 4

    handler = public_records_monitor.HANDLER_REGISTRY[publications.SOURCE_ID]
    assert handler.expected_requests == 4
    assert handler.sentinel_record_count == 1


def test_catalog_promotes_the_source_to_an_executable_adapter() -> None:
    catalog = yaml.safe_load(
        Path("config/public_records_sources.yaml").read_text(encoding="utf-8")
    )
    source = next(
        item
        for item in catalog["sources"]
        if item["source_id"] == publications.SOURCE_ID
    )
    assert source["official_url"] == publications.LANDING_URL
    assert source["adapter_family"] == "texas_supreme_publication_pages"
    assert source["source_status"] == "active"
    search_capability = next(
        capability
        for capability in source["capabilities"]
        if capability["name"] == "search_publications"
    )
    assert set(search_capability["details"]["result_fields"]) == {
        "raw_case_number",
        "caption",
        "release_date",
        "release_occurrence",
        "raw_case_text",
        "section_heading_raw",
        "action_heading_raw",
        "disposition_text",
        "participation_text",
        "originating_county_candidate",
        "lower_court_candidate",
        "release_artifact",
        "release_documents",
        "case_documents",
    }
    assert {
        capability["details"]["adapter_command"]
        for capability in source["capabilities"]
    } >= {
        "source",
        "years",
        "releases",
        "release",
        "search",
        "download",
        "probe",
    }
    assert source["complementary_source_ids"] == [
        "us-tx-appellate-tames",
        "us-tx-appellate-released-orders-opinions",
    ]


def test_citation_mapping_uses_the_verified_official_landing_page() -> None:
    source_urls = json.loads(
        Path("web/src/data/source-urls.json").read_text(encoding="utf-8")
    )
    assert source_urls[
        f"STATECOURT_SOURCE:{publications.SOURCE_ID}"
    ] == publications.LANDING_URL
