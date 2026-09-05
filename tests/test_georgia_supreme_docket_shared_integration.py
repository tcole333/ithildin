from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import (
    ingest_state_court_records,
    query_georgia_supreme_docket as georgia,
    query_state_courts,
)
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_store import connect_courts


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/georgia_supreme_docket"
)


def _fixture(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _shared_args(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def _envelope(operation: str, records: list[dict]) -> dict:
    query = PublicRecordsQuery(
        source=georgia.SOURCE_METADATA,
        jurisdiction=georgia.JURISDICTION,
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at="2026-07-30T22:00:00Z",
    ).to_dict()


def _detail_record(fixture_name: str = "detail_current.json") -> dict:
    payload = _fixture(fixture_name)
    case_number = payload["caseNumber"]
    parsed = georgia.parse_detail_payload(
        payload,
        requested_case_number=case_number,
        source_url=f"{georgia.CASE_DETAIL_ROOT}/{case_number}",
    )
    return georgia.normalize_detail_record(parsed)


def test_live_routes_use_case_not_non_case_detail_and_keep_handoff_distinct() -> None:
    routes = query_state_courts.LIVE_ROUTES[georgia.SOURCE_ID]

    assert set(routes) == {
        "case",
        "discovery",
        "docket",
        "documents",
        "probe",
        "search",
    }
    assert "detail" not in routes

    case = routes["case"].translate(
        _shared_args(
            "case",
            "S26G0537",
            "--source",
            georgia.SOURCE_ID,
            "--court-id",
            georgia.COURT_ID,
        ),
        routes["case"].adapter_command,
    )
    docket = routes["docket"].translate(
        _shared_args(
            "docket",
            "S26G0537",
            "--source",
            georgia.SOURCE_ID,
        ),
        routes["docket"].adapter_command,
    )
    documents = routes["documents"].translate(
        _shared_args(
            "documents",
            "S26G0537",
            "--source",
            georgia.SOURCE_ID,
            "--document-type",
            "filing-metadata",
        ),
        routes["documents"].adapter_command,
    )

    assert case.command == "detail"
    assert case.case_number == "S26G0537"
    assert docket.command == "detail"
    assert docket.case_number == "S26G0537"
    assert documents.command == "documents"
    assert documents.case_number == "S26G0537"


def test_search_translation_preserves_native_fields_county_cursor_and_bounds() -> None:
    route = query_state_courts.LIVE_ROUTES[georgia.SOURCE_ID]["search"]
    cursor = (
        "ga-supreme-docket:v1:query:0000000000000000:"
        "snapshot:1111111111111111:offset:20"
    )
    lower_case = route.translate(
        _shared_args(
            "search",
            "2018CV02040",
            "--source",
            georgia.SOURCE_ID,
            "--jurisdiction",
            "GA",
            "--search-field",
            "lower-court-case-number",
            "--county",
            "Clayton",
            "--max-records",
            "25",
            "--cursor",
            cursor,
        ),
        route.adapter_command,
    )
    inferred_case = route.translate(
        _shared_args(
            "search",
            "S26G0537",
            "--source",
            georgia.SOURCE_ID,
        ),
        route.adapter_command,
    )
    inferred_party = route.translate(
        _shared_args(
            "search",
            "American Honda",
            "--source",
            georgia.SOURCE_ID,
            "--entity-kind",
            "organization",
        ),
        route.adapter_command,
    )

    assert lower_case.command == "search"
    assert lower_case.field == "lower-court-case-number"
    assert lower_case.county == "Clayton"
    assert lower_case.county_id is None
    assert lower_case.limit == 25
    assert lower_case.cursor == cursor
    assert inferred_case.field == "case-number"
    assert inferred_party.field == "party"


def test_discovery_can_return_counties_or_manifest_and_probe_is_bounded() -> None:
    routes = query_state_courts.LIVE_ROUTES[georgia.SOURCE_ID]
    counties = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "counties",
            "--source",
            georgia.SOURCE_ID,
        ),
        routes["discovery"].adapter_command,
    )
    manifest = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "manifest",
            "--source",
            georgia.SOURCE_ID,
        ),
        routes["discovery"].adapter_command,
    )
    probe = routes["probe"].translate(
        _shared_args(
            "probe",
            "--source",
            georgia.SOURCE_ID,
        ),
        routes["probe"].adapter_command,
    )

    assert counties.command == "counties"
    assert manifest.command == "manifest"
    assert probe.command == "probe"
    assert probe.case_number == georgia.PROBE_CASE_NUMBER


def test_guidance_describes_recent_scope_and_exact_shared_operations() -> None:
    guidance = query_state_courts._source_guidance(georgia.SOURCE_ID)

    assert guidance["coverage"] == "cases docketed in the last 5 years"
    assert guidance["court_id"] == georgia.COURT_ID
    assert guidance["search_fields"] == list(georgia.SEARCH_FIELDS)
    assert guidance["unified_operations"] == [
        "case",
        "discovery",
        "docket",
        "documents",
        "probe",
        "search",
    ]


def test_shared_adapter_ignores_catalog_decision_only_after_routing(
    monkeypatch,
) -> None:
    route = query_state_courts.LIVE_ROUTES[georgia.SOURCE_ID]["case"]
    translated = route.translate(
        _shared_args(
            "case",
            "S26G0537",
            "--source",
            georgia.SOURCE_ID,
        ),
        route.adapter_command,
    )
    captured = {}
    sentinel = object()

    def fake_execute(args, *, client=None, log_results=True):
        captured["args"] = vars(args)
        captured["client"] = client
        captured["log_results"] = log_results
        return sentinel

    monkeypatch.setattr(georgia, "execute", fake_execute)
    returned = route.adapter.execute(
        translated,
        access_decision={"allowed": True, "reason_code": "open"},
    )

    assert returned is sentinel
    assert captured["args"]["command"] == "detail"
    assert captured["args"]["case_number"] == "S26G0537"


def test_search_projects_real_appellate_case_without_invented_parties(
    tmp_path: Path,
) -> None:
    raw = _fixture("search_cases.json")[0]
    record = georgia.normalize_search_record(
        raw,
        field="case-number",
        query="S26G",
    )
    court_db = tmp_path / "courts.db"

    report = ingest_state_court_records.ingest_envelope(
        _envelope("search", [record]),
        court_db=court_db,
    )

    assert report["projected"] == {
        "courts": 1,
        "related_courts": 0,
        "cases": 1,
        "related_cases": 0,
        "case_relations": 0,
        "parties": 0,
        "attorneys": 0,
        "representations": 0,
        "judicial_officers": 0,
        "assignments": 0,
        "claims": 0,
        "docket_entries": 0,
        "case_events": 0,
        "documents": 0,
        "restriction_events": 0,
    }
    assert report["snapshot_only"]["record_count"] == 0

    db = connect_courts(court_db)
    try:
        case = db.execute(
            """
            SELECT raw_case_number, caption, case_type, filing_date, status,
                   raw_json
            FROM case_record
            """
        ).fetchone()
        assert case is not None
        assert case["raw_case_number"] == "S26G0021"
        assert case["caption"] == raw["caseStyle"]
        assert case["case_type"] == "G"
        assert case["filing_date"] == "2026-06-02"
        assert case["status"] == "Docketed"
        source = json.loads(case["raw_json"])
        assert source["parties"] == []
        assert source["lower_court_case_numbers"] == [
            "24DP01828",
            "24DP01831",
        ]
        assert db.execute("SELECT COUNT(*) FROM case_party").fetchone()[0] == 0
    finally:
        db.close()


def test_attorney_search_projects_explicit_match_without_party_or_representation(
    tmp_path: Path,
) -> None:
    raw = _fixture("search_attorney.json")[0]
    record = georgia.normalize_search_record(
        raw,
        field="attorney",
        query="Blackwell",
        party_types={"403": "Appellant"},
    )
    court_db = tmp_path / "courts.db"

    report = ingest_state_court_records.ingest_envelope(
        _envelope("search", [record]),
        court_db=court_db,
    )

    assert report["projected"]["cases"] == 1
    assert report["projected"]["attorneys"] == 1
    assert report["projected"]["parties"] == 0
    assert report["projected"]["representations"] == 0
    db = connect_courts(court_db)
    try:
        attorney = db.execute(
            "SELECT raw_name, firm_name FROM attorney"
        ).fetchone()
        assert dict(attorney) == {
            "raw_name": "Keith Blackwell",
            "firm_name": None,
        }
        raw_case = json.loads(
            db.execute("SELECT raw_json FROM case_record").fetchone()[0]
        )
        assert raw_case["attorneys"][0]["party_type"] == "Appellant"
        assert raw_case["attorneys"][0]["party_type_native_id"] == "403"
    finally:
        db.close()


def test_detail_projects_docket_attorneys_calendar_and_lower_court_relation(
    tmp_path: Path,
) -> None:
    record = _detail_record()
    court_db = tmp_path / "courts.db"

    report = ingest_state_court_records.ingest_envelope(
        _envelope("detail", [record]),
        court_db=court_db,
    )

    projected = report["projected"]
    assert projected["cases"] == 1
    assert projected["related_cases"] == 1
    assert projected["case_relations"] == 1
    assert projected["docket_entries"] == 2
    assert projected["attorneys"] == 2
    assert projected["parties"] == 0
    assert projected["representations"] == 0
    assert projected["case_events"] == 1
    assert projected["documents"] == 0

    db = connect_courts(court_db)
    try:
        case = db.execute(
            """
            SELECT raw_case_number, caption, case_type, filing_date, status,
                   raw_json
            FROM case_record
            WHERE raw_case_number='S26G0537'
            """
        ).fetchone()
        assert case is not None
        assert case["case_type"] == "Civil - Granted Certiorari"
        assert case["filing_date"] == "2026-07-16"
        case_source = json.loads(case["raw_json"])
        assert case_source["parties"] == []
        assert case_source["attorneys"][0]["party_type"] == "Appellant"
        assert case_source["attorneys"][0]["firm_name"] == "ALSTON & BIRD LLP"
        assert case_source["attorneys"][0]["contact"]["phone"] == (
            "(404) 881-7968"
        )

        entries = db.execute(
            """
            SELECT native_entry_id, filed_date, event_date, status, raw_json
            FROM docket_entry
            ORDER BY sequence_no
            """
        ).fetchall()
        assert len(entries) == 2
        first = json.loads(entries[0]["raw_json"])
        assert entries[0]["native_entry_id"].startswith(
            "ga-supreme-docket-event:"
        )
        assert entries[0]["filed_date"] == "2025-11-24T16:16:00"
        assert entries[0]["event_date"] == "2026-07-16"
        assert entries[0]["status"] is None
        assert first["filing_date_time"] == "2025-11-24T16:16:00"
        assert first["order_date"] == "2026-07-16"
        assert first["docketed_in_error"] is False
        assert first["request_from_clerk"] is True

        assert db.execute("SELECT COUNT(*) FROM attorney").fetchone()[0] == 2
        assert db.execute(
            "SELECT COUNT(*) FROM document_artifact"
        ).fetchone()[0] == 0
        calendar = db.execute(
            """
            SELECT event_type, event_date, raw_json
            FROM case_event
            WHERE event_type='appellate_calendar_assignment'
            """
        ).fetchone()
        assert calendar is not None
        assert calendar["event_date"] is None
        assert json.loads(calendar["raw_json"])["calendar"] == "November 2026"

        relation = db.execute(
            """
            SELECT relation_type, evidence_ref
            FROM case_relation
            """
        ).fetchone()
        assert dict(relation) == {
            "relation_type": "appealed_to",
            "evidence_ref": "S26G0537:originating:2018CV02040",
        }
        lower_case = db.execute(
            """
            SELECT raw_case_number
            FROM case_record
            WHERE raw_case_number='2018CV02040'
            """
        ).fetchone()
        assert lower_case is not None
    finally:
        db.close()


def test_judgment_projects_as_judgment_event_and_case_disposition_date(
    tmp_path: Path,
) -> None:
    record = _detail_record("detail_judgment.json")
    court_db = tmp_path / "courts.db"

    report = ingest_state_court_records.ingest_envelope(
        _envelope("detail", [record]),
        court_db=court_db,
    )

    assert report["projected"]["case_events"] == 2
    db = connect_courts(court_db)
    try:
        case = db.execute(
            """
            SELECT disposition_date
            FROM case_record
            WHERE raw_case_number='S24C0420'
            """
        ).fetchone()
        assert case["disposition_date"] == "2024-03-27"
        judgment = db.execute(
            """
            SELECT event_date, disposition, assertion_kind, raw_json
            FROM case_event
            WHERE event_type='judgment'
            """
        ).fetchone()
        assert judgment["event_date"] == "2024-03-27"
        assert judgment["disposition"] == "Certiorari - Writ denied"
        assert judgment["assertion_kind"] == "judgment"
        assert json.loads(judgment["raw_json"])["judgment_line"] == (
            "All the Justices concur."
        )
    finally:
        db.close()


@pytest.mark.parametrize(
    ("operation", "record"),
    [
        (
            "documents",
            georgia.normalize_document_handoff(
                georgia.parse_detail_payload(
                    _fixture("detail_current.json"),
                    requested_case_number="S26G0537",
                    source_url=f"{georgia.CASE_DETAIL_ROOT}/S26G0537",
                )
            ),
        ),
        ("manifest", georgia.source_manifest()),
        (
            "counties",
            {
                "canonical_ref": (
                    f"STATECOURT:{georgia.SOURCE_ID}/county/31"
                ),
                "source_id": georgia.SOURCE_ID,
                "record_kind": "county_lookup",
                "county_id": "31",
                "name": "Clayton",
                "county_code": "031",
                "active": True,
            },
        ),
        (
            "probe",
            {
                "canonical_ref": (
                    f"STATECOURT:{georgia.SOURCE_ID}/probe"
                ),
                "source_id": georgia.SOURCE_ID,
                "record_kind": "source_probe",
                "source_url": georgia.PORTAL_URL,
                "requests_made": 2,
            },
        ),
    ],
)
def test_non_case_operations_are_snapshot_only(
    tmp_path: Path,
    operation: str,
    record: dict,
) -> None:
    record = dict(record)
    record["court"] = {
        "court_id": georgia.COURT_ID,
        "name": "Supreme Court of Georgia",
    }
    record["raw_case_number"] = "DO-NOT-PROJECT"
    court_db = tmp_path / f"{operation}.db"

    report = ingest_state_court_records.ingest_envelope(
        _envelope(operation, [record]),
        court_db=court_db,
    )

    assert report["projected"]["cases"] == 0
    assert report["projected"]["docket_entries"] == 0
    assert report["projected"]["documents"] == 0
    assert report["snapshot_only"] == {
        "record_count": 1,
        "record_kinds": {record["record_kind"]: 1},
    }
    db = connect_courts(court_db)
    try:
        assert db.execute("SELECT COUNT(*) FROM source_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM document_artifact"
        ).fetchone()[0] == 0
    finally:
        db.close()
