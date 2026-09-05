from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from tools import (
    ingest_state_court_records as ingest,
    query_osceola_courts as osceola,
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
    / "osceola_benchmark"
)
RETRIEVED_AT = "2026-07-30T22:00:00Z"


def _shared_args(*values: str) -> Any:
    return query_state_courts.build_parser().parse_args(list(values))


def _artifact(
    name: str,
    source_url: str,
    *,
    media_type: str = "text/html",
    headers: Mapping[str, str] | None = None,
) -> osceola.Artifact:
    return osceola.Artifact(
        content=(FIXTURE_ROOT / name).read_bytes(),
        source_url=source_url,
        status_code=200,
        media_type=media_type,
        headers=dict(headers or {"content-type": media_type}),
    )


def _bundle_record() -> dict[str, Any]:
    locator = osceola.parse_case_shell(
        _artifact(
            "case_shell.html",
            osceola.PORTAL_BASE_URL
            + "CourtCase.aspx/Details/3284536?digest=fixture",
        )
    )
    record = osceola.parse_summary(
        _artifact(
            "details_summary.html",
            osceola.PORTAL_BASE_URL
            + "CourtCase.aspx/DetailsSummary/3284536",
        ),
        locator,
    )
    dockets, _locators = osceola.parse_dockets(
        _artifact(
            "case_dockets.html",
            osceola.PORTAL_BASE_URL
            + "CourtCase.aspx/CaseDockets/3284536",
        ),
        locator,
    )
    record["docket_entries"] = dockets
    record.update(
        osceola.parse_history(
            _artifact(
                "details_history.html",
                osceola.PORTAL_BASE_URL
                + "CourtCase.aspx/DetailsHistory/3284536",
            )
        )
    )
    record["charge_details"] = osceola.parse_charge_details(
        _artifact(
            "details_charges.html",
            osceola.PORTAL_BASE_URL
            + "CourtCase.aspx/DetailsCharges/3284536",
        )
    )
    record["source_bundle_sha256"] = "fixture-bundle"
    return record


def _search_records() -> list[dict[str, Any]]:
    headers, _total, _too_broad = osceola.parse_search_results_page(
        _artifact(
            "search_results_page.html",
            osceola.CASE_SEARCH_URL,
        )
    )
    hits, _source_rows = osceola.parse_search_rows(
        json.loads(
            (FIXTURE_ROOT / "search_results.json").read_text(
                encoding="utf-8"
            )
        ),
        headers,
    )
    return osceola.merge_search_hits(hits)


def _page_records() -> list[dict[str, Any]]:
    return osceola.parse_document_pages(
        _artifact(
            "pages.json",
            osceola.PORTAL_BASE_URL
            + "CaseDocket.aspx/Pages?did=56773534",
            media_type="application/json",
        ),
        case_number="2023 CF 001540",
        case_id="3284536",
        docket_id="56773534",
    )


def _envelope(
    source: Any,
    operation: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=source,
        jurisdiction=osceola.JURISDICTION,
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at=RETRIEVED_AT,
    ).to_dict()


def test_main_source_exposes_exact_shared_operations_and_stable_selectors() -> None:
    routes = query_state_courts.LIVE_ROUTES[osceola.PORTAL_SOURCE_ID]

    assert set(routes) == {
        "case",
        "discovery",
        "docket",
        "documents",
        "probe",
        "search",
    }
    assert "download" not in routes
    assert "detail" not in routes

    search = routes["search"].translate(
        _shared_args(
            "search",
            "2023 CF 001540",
            "--source",
            osceola.PORTAL_SOURCE_ID,
            "--max-records",
            "12",
        ),
        routes["search"].adapter_command,
    )
    case = routes["case"].translate(
        _shared_args(
            "case",
            "2023 CF 001540",
            "--source",
            osceola.PORTAL_SOURCE_ID,
        ),
        routes["case"].adapter_command,
    )
    docket = routes["docket"].translate(
        _shared_args(
            "docket",
            "2023 CF 001540",
            "--source",
            osceola.PORTAL_SOURCE_ID,
        ),
        routes["docket"].adapter_command,
    )
    documents = routes["documents"].translate(
        _shared_args(
            "documents",
            "2023 CF 001540",
            "--source",
            osceola.PORTAL_SOURCE_ID,
            "--docket-entry-uuid",
            "56773534",
        ),
        routes["documents"].adapter_command,
    )

    assert search.command == "search"
    assert search.search_mode == "case-number"
    assert search.limit == 12
    assert case.command == "case"
    assert case.case_number == "2023 CF 001540"
    assert docket.command == "docket"
    assert documents.command == "document-metadata"
    assert documents.case_number == "2023 CF 001540"
    assert documents.docket_id == "56773534"


def test_report_sources_are_separate_snapshot_only_routes() -> None:
    for source_id in (
        osceola.CALENDAR_SOURCE_ID,
        osceola.FORECLOSURE_SOURCE_ID,
    ):
        routes = query_state_courts.LIVE_ROUTES[source_id]
        assert set(routes) == {"discovery", "probe"}
        manifest = routes["discovery"].translate(
            _shared_args(
                "discovery",
                "--source",
                source_id,
            ),
            routes["discovery"].adapter_command,
        )
        probe = routes["probe"].translate(
            _shared_args(
                "probe",
                "--source",
                source_id,
            ),
            routes["probe"].adapter_command,
        )
        assert manifest.command == "manifest"
        assert manifest.source == source_id
        assert probe.command == "probe"
        assert probe.source == source_id
        assert query_state_courts._source_guidance(source_id)[
            "unified_operations"
        ] == ["discovery", "probe"]

    assert query_state_courts._source_guidance(
        osceola.CALENDAR_SOURCE_ID
    )["artifact_url"] == osceola.CALENDAR_URL
    assert query_state_courts._source_guidance(
        osceola.FORECLOSURE_SOURCE_ID
    )["artifact_url"] == osceola.FORECLOSURE_URL
    assert "/BenchmarkWeb/reports/" not in osceola.CALENDAR_URL
    assert "/BenchmarkWeb/reports/" not in osceola.FORECLOSURE_URL


def test_report_probe_wrapper_keeps_only_selected_source_snapshot(
    monkeypatch: Any,
) -> None:
    source_id = osceola.CALENDAR_SOURCE_ID
    route = query_state_courts.LIVE_ROUTES[source_id]["probe"]
    translated = route.translate(
        _shared_args("probe", "--source", source_id),
        route.adapter_command,
    )
    query = PublicRecordsQuery(
        source=osceola.CALENDAR_SOURCE,
        jurisdiction=osceola.JURISDICTION,
        query=QueryMetadata(operation="probe", parameters={}),
    )
    family_result = PublicRecordsResult.success(
        query,
        [
            {
                "source_id": osceola.PORTAL_SOURCE_ID,
                "record_kind": "source_probe",
                "report_routes": {
                    "calendar": {
                        "url": osceola.CALENDAR_URL,
                        "media_type": "application/pdf",
                        "content_length": "1234",
                        "last_modified": "Thu, 30 Jul 2026 11:15:17 GMT",
                        "etag": '"calendar"',
                    },
                    "foreclosure": {
                        "url": osceola.FORECLOSURE_URL,
                        "media_type": "application/pdf",
                    },
                },
            }
        ],
        retrieved_at=RETRIEVED_AT,
    )
    monkeypatch.setattr(osceola, "execute", lambda _args: family_result)

    result = route.adapter.execute(
        translated,
        access_decision={"allowed": True},
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record["source_id"] == source_id
    assert record["artifact_url"] == osceola.CALENDAR_URL
    assert record["record_kind"] == "rolling_report_probe"
    assert record["projection"]["projectable_as_case_record"] is False


def test_full_case_projects_parties_attorney_charge_events_and_docket(
    tmp_path: Path,
) -> None:
    record = _bundle_record()
    court_db = tmp_path / "courts.db"
    envelope = _envelope(osceola.PORTAL_SOURCE, "case", [record])

    first = ingest.ingest_envelope(envelope, court_db=court_db)
    second = ingest.ingest_envelope(envelope, court_db=court_db)

    assert first["projected"] == second["projected"]
    assert first["projected"]["cases"] == 1
    assert first["projected"]["parties"] == 2
    assert first["projected"]["attorneys"] == 1
    assert first["projected"]["representations"] == 1
    assert first["projected"]["claims"] == 1
    assert first["projected"]["docket_entries"] == 3
    assert first["projected"]["case_events"] == 1
    assert first["projected"]["documents"] == 3
    assert first["projected"]["judicial_officers"] == 1
    assert first["projected"]["assignments"] == 1
    assert first["snapshot_only"]["record_count"] == 0

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        case = db.execute(
            """
            SELECT raw_case_number, source_internal_id, caption, filing_date,
                   status, certified_record, raw_json
            FROM case_record
            """
        ).fetchone()
        assert case is not None
        assert case["raw_case_number"] == "2023 CF 001540"
        assert case["source_internal_id"] == "3284536"
        assert case["filing_date"] == "2023-05-22"
        assert case["certified_record"] == 0
        assert "digest" not in case["raw_json"].casefold()

        assert db.execute("SELECT COUNT(*) FROM case_party").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM attorney").fetchone()[0] == 1
        assert (
            db.execute("SELECT COUNT(*) FROM case_representation").fetchone()[0]
            == 1
        )
        claim = db.execute(
            """
            SELECT native_claim_id, claim_type, status, limited_stub, raw_json
            FROM case_claim
            """
        ).fetchone()
        assert dict(claim) == {
            "native_claim_id": "3034861",
            "claim_type": "case_charge",
            "status": "NOLLE PROSEQUI",
            "limited_stub": 1,
            "raw_json": claim["raw_json"],
        }
        assert json.loads(claim["raw_json"])["description"] == "FIXTURE OFFENSE"

        docket_rows = db.execute(
            """
            SELECT native_entry_id, access_state, native_access_state
            FROM docket_entry
            ORDER BY native_entry_id
            """
        ).fetchall()
        assert [row["native_entry_id"] for row in docket_rows] == [
            "56759615",
            "56770000",
            "56773534",
        ]
        assert {row["access_state"] for row in docket_rows} == {
            "public",
            "restricted",
            "unknown",
        }
        assert db.execute("SELECT COUNT(*) FROM case_event").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM document_artifact").fetchone()[0] == 3
    finally:
        db.close()


def test_search_hit_projects_explicit_matches_as_partial_case_observation(
    tmp_path: Path,
) -> None:
    record = _search_records()[0]
    court_db = tmp_path / "courts.db"

    report = ingest.ingest_envelope(
        _envelope(osceola.PORTAL_SOURCE, "search", [record]),
        court_db=court_db,
    )

    assert report["projected"]["cases"] == 1
    assert report["projected"]["parties"] == 2
    assert report["projected"]["docket_entries"] == 0
    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        case = json.loads(
            db.execute("SELECT raw_json FROM case_record").fetchone()[0]
        )
        assert case["partial_case_shell"] is True
        assert case["source_result_row_count"] == 2
        assert [party["alias"] for party in case["parties"]] == [False, True]
        assert "digest" not in json.dumps(case).casefold()
    finally:
        db.close()


def test_document_pages_project_as_metadata_without_content_hash_or_certificate(
    tmp_path: Path,
) -> None:
    records = _page_records()
    court_db = tmp_path / "courts.db"
    envelope = _envelope(
        osceola.PORTAL_SOURCE,
        "document-metadata",
        records,
    )

    first = ingest.ingest_envelope(envelope, court_db=court_db)
    second = ingest.ingest_envelope(envelope, court_db=court_db)

    assert first["projected"]["cases"] == 2
    assert first["projected"]["documents"] == 2
    assert second["projected"]["documents"] == 2
    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        cases = db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0]
        assert cases == 1
        documents = db.execute(
            """
            SELECT native_document_id, sha256, storage_path,
                   certification_status, access_state
            FROM document_artifact
            ORDER BY native_document_id
            """
        ).fetchall()
        assert [row["native_document_id"] for row in documents] == [
            "76951980",
            "76951981",
        ]
        assert all(row["sha256"] is None for row in documents)
        assert all(row["storage_path"] is None for row in documents)
        assert {
            row["certification_status"] for row in documents
        } == {"metadata_only"}
        assert {row["access_state"] for row in documents} == {
            "public",
            "restricted",
        }
        snapshot = json.loads(
            db.execute(
                "SELECT raw_json FROM source_snapshot ORDER BY snapshot_id DESC"
            ).fetchone()[0]
        )
        assert {
            row["native_entry_id"] for row in snapshot["records"]
        } == {"56773534"}
        assert [row["page_sequence"] for row in snapshot["records"]] == [1, 2]
    finally:
        db.close()


def test_report_manifest_ingests_as_snapshot_only(tmp_path: Path) -> None:
    record = osceola._manifest_record(osceola.CALENDAR_SOURCE_ID)
    report = ingest.ingest_envelope(
        _envelope(osceola.CALENDAR_SOURCE, "manifest", [record]),
        court_db=tmp_path / "courts.db",
    )

    assert report["projected"]["cases"] == 0
    assert report["snapshot_only"] == {
        "record_count": 1,
        "record_kinds": {"source_manifest": 1},
    }
