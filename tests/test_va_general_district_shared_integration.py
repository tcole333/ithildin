from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tools import query_state_courts
from tools import query_va_general_district as va_gdc
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)


FIXTURES = Path(__file__).parent / "fixtures" / "public_records" / "va_general_district"
RETRIEVED_AT = "2026-07-30T12:00:00Z"
COURT = va_gdc.CourtOption(
    "Arlington General District Court",
    "013",
)


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _shared_args(*values: str) -> Any:
    return query_state_courts.build_parser().parse_args(list(values))


def _envelope(
    operation: str,
    records: list[dict[str, Any]],
    *,
    next_cursor: str | None = None,
) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=va_gdc.SOURCE_METADATA,
        jurisdiction=va_gdc.JURISDICTION,
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=next_cursor,
        retrieved_at=RETRIEVED_AT,
    ).to_dict()


def test_shared_routes_translate_distinct_source_operations_and_selectors() -> None:
    routes = query_state_courts.LIVE_ROUTES[va_gdc.SOURCE_ID]
    assert set(routes) == {"search", "case", "calendar"}

    name = routes["search"].translate(
        _shared_args(
            "search",
            "EXAMPLE",
            "--source",
            va_gdc.SOURCE_ID,
            "--jurisdiction",
            "VA",
            "--courthouse",
            "013",
            "--case-type",
            "civil",
            "--first-name",
            "ALEX",
            "--max-records",
            "25",
            "--cursor",
            "va-gdc:v1:fixture",
        ),
        routes["search"].adapter_command,
    )
    assert name.command == "name"
    assert name.court == "013"
    assert name.division == "civil"
    assert name.last_name_or_business == "EXAMPLE"
    assert name.first_name == "ALEX"
    assert name.status == "all"
    assert name.limit == 25
    assert name.cursor == "va-gdc:v1:fixture"
    assert name.max_pages is None

    service = routes["search"].translate(
        _shared_args(
            "search",
            "EXAMPLE",
            "--source",
            va_gdc.SOURCE_ID,
            "--court-id",
            "va-gdc-013",
            "--search-field",
            "service-process",
        ),
        routes["search"].adapter_command,
    )
    assert service.command == "service"
    assert service.court == "013"
    assert service.last_name == "EXAMPLE"

    searched_case = routes["search"].translate(
        _shared_args(
            "search",
            "GV26000001-00",
            "--source",
            va_gdc.SOURCE_ID,
            "--courthouse",
            "013",
            "--search-field",
            "case-number",
        ),
        routes["search"].adapter_command,
    )
    assert searched_case.command == "case"
    assert searched_case.case_number == "GV26000001-00"

    case = routes["case"].translate(
        _shared_args(
            "case",
            "GT26000123-00",
            "--source",
            va_gdc.SOURCE_ID,
            "--court-id",
            "va-gdc-013",
            "--case-type",
            "traffic-criminal",
        ),
        routes["case"].adapter_command,
    )
    assert case.command == "case"
    assert case.court == "013"
    assert case.division == "traffic-criminal"

    hearing = routes["calendar"].translate(
        _shared_args(
            "calendar",
            "2026-07-30",
            "--source",
            va_gdc.SOURCE_ID,
            "--courthouse",
            "013",
            "--case-type",
            "traffic-criminal",
            "--hearing-date",
            "2026-07-30",
            "--limit",
            "3",
            "--cursor",
            "va-gdc:v1:hearing-fixture",
        ),
        routes["calendar"].adapter_command,
    )
    assert hearing.command == "hearing"
    assert hearing.hearing_date == "07/30/2026"
    assert hearing.limit == 3
    assert hearing.cursor == "va-gdc:v1:hearing-fixture"

    with pytest.raises(ValueError, match="statewide Virginia"):
        routes["search"].translate(
            _shared_args(
                "search",
                "EXAMPLE",
                "--source",
                va_gdc.SOURCE_ID,
                "--jurisdiction",
                "51013",
                "--courthouse",
                "013",
            ),
            routes["search"].adapter_command,
        )


def test_shared_adapter_preserves_completeness_metadata_and_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route = query_state_courts.LIVE_ROUTES[va_gdc.SOURCE_ID]["search"]
    translated = route.translate(
        _shared_args(
            "search",
            "EXAMPLE",
            "--source",
            va_gdc.SOURCE_ID,
            "--courthouse",
            "013",
            "--limit",
            "1",
            "--cursor",
            "va-gdc:v1:input",
        ),
        route.adapter_command,
    )
    record = {
        "source_id": va_gdc.SOURCE_ID,
        "record_kind": "case_search_hit",
        "raw_case_number": "GV26000001-00",
        "search_metadata": {
            "source_exhausted": False,
            "reported_total": None,
            "completeness_basis": "continuation cursor returned",
        },
    }
    expected = PublicRecordsResult.success(
        va_gdc.build_query(translated),
        [record],
        next_cursor="va-gdc:v1:output",
        retrieved_at=RETRIEVED_AT,
    )
    observed: dict[str, Any] = {}

    def fake_execute(args: Any) -> PublicRecordsResult:
        observed["args"] = args
        return expected

    monkeypatch.setattr(va_gdc, "execute", fake_execute)
    result = route.adapter.execute(
        translated,
        access_decision={"allowed": True},
    )

    assert observed["args"].cursor == "va-gdc:v1:input"
    assert result.next_cursor == "va-gdc:v1:output"
    assert result.records[0]["search_metadata"] == record["search_metadata"]


def test_search_rows_share_case_identity_and_keep_session_locators_as_occurrences(
    tmp_path: Path,
) -> None:
    page = va_gdc.parse_search_page(
        _fixture("civil_results_page1.html"),
        operation="hearing",
        division="V",
        court=COURT,
        native_page=1,
        source_url=va_gdc.CASE_SEARCH_URL,
    )
    first = dict(page.records[0])
    first["search_metadata"] = {
        "source_exhausted": False,
        "reported_total": None,
        "completeness_basis": "continuation cursor returned",
    }
    repeated = copy.deepcopy(first)
    repeated["source_native_row"] = 2
    repeated["source_detail_locator"]["session_values"]["clientSearchCounter"] = "999"
    court_db = tmp_path / "courts.db"

    report = ingest_envelope(
        _envelope(
            "hearing",
            [first, repeated],
            next_cursor="va-gdc:v1:next",
        ),
        court_db=court_db,
    )

    assert report["projected"]["cases"] == 2
    assert report["projected"]["parties"] == 0
    assert report["projected"]["docket_entries"] == 0
    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        case = db.execute(
            """
            SELECT raw_case_number, case_identity_key, source_internal_id,
                   caption, case_type, filing_date
            FROM case_record
            """
        ).fetchone()
        assert case is not None
        assert dict(case) == {
            "raw_case_number": "GV26000001-00",
            "case_identity_key": "number:GV26000001-00",
            "source_internal_id": None,
            "caption": None,
            "case_type": None,
            "filing_date": None,
        }
        court = db.execute(
            """
            SELECT native_court_id, state_code, county_geoid, division
            FROM court
            """
        ).fetchone()
        assert court is not None
        assert tuple(court) == ("013", "VA", None, None)
        occurrences = db.execute(
            """
            SELECT source_result_id, source_internal_id, raw_json
            FROM case_source_occurrence
            ORDER BY occurrence_id
            """
        ).fetchall()
        assert len(occurrences) == 2
        assert len({row["source_result_id"] for row in occurrences}) == 2
        assert {row["source_internal_id"] for row in occurrences} == {None}
        assert {
            json.loads(row["raw_json"])["source_detail_locator"]["session_bound"]
            for row in occurrences
        } == {True}
        assert db.execute("SELECT COUNT(*) FROM case_party").fetchone()[0] == 0
    finally:
        db.close()


def test_detail_projection_preserves_section_and_masking_states_without_documents(
    tmp_path: Path,
) -> None:
    civil = va_gdc.parse_case_detail(
        _fixture("civil_detail.html"),
        division="V",
        court=COURT,
        source_url=va_gdc.CASE_NUMBER_SEARCH_URL,
        requested_case_number="GV26000001-00",
    )
    traffic = va_gdc.parse_case_detail(
        _fixture("traffic_detail.html"),
        division="T",
        court=COURT,
        source_url=va_gdc.CASE_NUMBER_SEARCH_URL,
        requested_case_number="GT26000123-00",
    )
    assert civil is not None
    assert traffic is not None
    civil = copy.deepcopy(civil)
    civil["section_states"]["appeal_information"] = "not_present"
    civil["sections"] = [
        section
        for section in civil["sections"]
        if section["section_key"] != "appeal_information"
    ]
    court_db = tmp_path / "courts.db"

    report = ingest_envelope(
        _envelope("case", [civil, traffic]),
        court_db=court_db,
    )

    assert report["projected"]["cases"] == 2
    assert report["projected"]["parties"] == 4
    assert report["projected"]["docket_entries"] == 3
    assert report["projected"]["documents"] == 0
    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        cases = {
            row["raw_case_number"]: row
            for row in db.execute(
                """
                SELECT raw_case_number, source_internal_id, caption, case_type,
                       filing_date, status, raw_json
                FROM case_record
                ORDER BY raw_case_number
                """
            )
        }
        assert set(cases) == {"GT26000123-00", "GV26000001-00"}
        civil_case = cases["GV26000001-00"]
        assert civil_case["source_internal_id"] is None
        assert civil_case["caption"] is None
        assert civil_case["case_type"] == "Warrant In Debt"
        assert civil_case["filing_date"] == "2026-06-18"
        assert civil_case["status"] is None
        civil_raw = json.loads(civil_case["raw_json"])
        assert civil_raw["section_states"]["hearing_information"] == "published"
        assert civil_raw["section_states"]["reports"] == "published_empty"
        assert civil_raw["section_states"]["appeal_information"] == "not_present"
        assert civil_raw["document_access"] == {
            "state": "not_published_by_case_information_source",
            "filing_index_present": False,
            "filing_images_present": False,
            "official_copy_route": "individual_court_clerk",
            "official_copy_guidance_url": va_gdc.PUBLIC_RECORDS_REQUEST_URL,
        }

        traffic_case = cases["GT26000123-00"]
        assert traffic_case["case_type"] == "Infraction"
        traffic_raw = json.loads(traffic_case["raw_json"])
        assert traffic_raw["date_of_birth_at_source"] == "04/11/****"
        assert traffic_raw["date_of_birth_state"] == "year_redacted"
        assert traffic_raw["section_states"]["service_process"] == "published_empty"

        parties = {
            (row["role"], row["raw_name"])
            for row in db.execute("SELECT role, raw_name FROM case_party")
        }
        assert parties == {
            ("plaintiff", "ALEX RIVER"),
            ("plaintiff", "SAM RIVER"),
            ("defendant", "EXAMPLE PROPERTIES LLC"),
            ("defendant", "CASEY EXAMPLE"),
        }
        entries = db.execute(
            """
            SELECT event_type, document_available, raw_json
            FROM docket_entry
            ORDER BY event_type, native_entry_id
            """
        ).fetchall()
        assert [row["event_type"] for row in entries].count("hearing") == 2
        assert [row["event_type"] for row in entries].count("service_process") == 1
        assert {row["document_available"] for row in entries} == {0}
        assert db.execute("SELECT COUNT(*) FROM document_artifact").fetchone()[0] == 0
    finally:
        db.close()
