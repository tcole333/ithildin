from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tools.public_records_contract import ResultStatus
from tools.query_va_general_district import (
    CASE_SEARCH_URL,
    LANDING_POST_URL,
    LANDING_URL,
    CourtOption,
    SearchFetch,
    VAGeneralDistrictClient,
    VAGeneralDistrictError,
    VAGDCSelectionError,
    VAGDCSourceChangedError,
    _decode_cursor,
    _raise_page_failure,
    _route_record,
    _search_result,
    build_query,
    build_parser,
    execute,
    parse_case_detail,
    parse_courts_page,
    parse_search_page,
    resolve_court,
)


FIXTURES = Path(__file__).parent / "fixtures" / "public_records" / "va_general_district"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@dataclass
class FakeResponse:
    text: str
    url: str
    status_code: int = 200
    headers: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.headers is None:
            self.headers = {}


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def response(name: str, url: str) -> FakeResponse:
    return FakeResponse(fixture(name), url)


def client_for_hearing_pages(
    *pages: str,
) -> tuple[VAGeneralDistrictClient, FakeSession]:
    session = FakeSession(
        [
            response("terms.html", LANDING_URL),
            response("welcome.html", LANDING_POST_URL),
            response(
                "welcome.html",
                "https://eapps.courts.state.va.us/gdcourts/changeCourt.do",
            ),
            response("hearing_form.html", CASE_SEARCH_URL),
            *[response(page, CASE_SEARCH_URL) for page in pages],
        ]
    )
    return (
        VAGeneralDistrictClient(
            session=session,
            minimum_interval=0,
            sleeper=lambda _seconds: None,
        ),
        session,
    )


def test_route_manifest_keeps_complements_distinct() -> None:
    record = _route_record()
    assert record["primary_route"]["native_page_size"] == 20
    assert record["primary_route"]["reported_total"] is None
    complements = {item["source_id"]: item for item in record["complementary_sources"]}
    assert complements["us-va-ocis-statewide-search"]["equivalent"] is False
    assert "Statewide discovery" in complements["us-va-ocis-statewide-search"]["adds"]
    assert complements["us-va-secure-remote-access-land-records"]["equivalent"] is False
    assert (
        "land-record" in complements["us-va-secure-remote-access-land-records"]["adds"]
    )
    statuses = {item["code"]: item for item in record["source_native_name_statuses"]}
    assert "after January 2007" in statuses["A"]["source_definition"]
    assert record["primary_route"]["name_search_syntax"]["wildcard"] == "*"


def test_parse_and_resolve_source_court_components() -> None:
    courts = parse_courts_page(fixture("welcome.html"))
    assert len(courts) == 3
    assert courts[1] == CourtOption(
        name="Arlington General District Court",
        source_code="013",
    )
    assert resolve_court(courts, "013") == courts[1]
    assert resolve_court(courts, "Arlington") == courts[1]
    record = courts[1].to_record()
    assert record["court_id"] == "va-gdc-013"
    assert "application court-component" in record["court_source_code_semantics"]


def test_resolve_court_rejects_unknown_or_ambiguous_selector() -> None:
    courts = (
        CourtOption("Fairfax City General District Court", "600"),
        CourtOption("Fairfax County General District Court", "059"),
    )
    with pytest.raises(VAGDCSelectionError, match="matches 2"):
        resolve_court(courts, "Fairfax")
    with pytest.raises(VAGDCSelectionError, match="does not match"):
        resolve_court(courts, "Nowhere")


def test_verification_field_is_human_required() -> None:
    with pytest.raises(VAGeneralDistrictError) as caught:
        _raise_page_failure(
            fixture("verification_terms.html"),
            source_url=LANDING_URL,
            allow_terms=True,
        )
    assert caught.value.status == ResultStatus.HUMAN_REQUIRED
    assert caught.value.code == "verification_required"


def test_parse_civil_result_page_preserves_native_paging_and_locator() -> None:
    page = parse_search_page(
        fixture("civil_results_page1.html"),
        operation="hearing",
        division="V",
        court=CourtOption("Arlington General District Court", "013"),
        native_page=1,
        source_url=CASE_SEARCH_URL,
    )
    assert len(page.records) == 2
    assert page.has_next is True
    assert page.has_previous is False
    assert page.boundary["first_case_number"] == "GV26000001-00"
    assert page.boundary["last_case_number"] == "GV26000002-00"
    first = page.records[0]
    assert first["raw_case_number"] == "GV26000001-00"
    assert first["source_values"]["Case #"] == "GV26000001-00"
    assert first["values"]["case_type"] == "Warrant In Debt"
    assert first["source_native_page"] == 1
    assert first["source_detail_locator"]["session_bound"] is True
    assert (
        first["source_detail_locator"]["parameters"]["displayCaseNumber"]
        == "GV26000001-00"
    )
    assert (
        first["source_detail_locator"]["session_values"]["clientSearchCounter"] == "3"
    )
    assert ("caseInfoScrollForward", "Next") in page.next_payload


def test_parse_name_page_preserves_boundary_fields_and_date() -> None:
    page = parse_search_page(
        fixture("name_results_page1.html"),
        operation="name",
        division="V",
        court=CourtOption("Arlington General District Court", "013"),
        native_page=1,
        source_url="https://eapps.courts.state.va.us/gdcourts/nameSearch.do",
    )
    assert page.has_next is True
    assert page.boundary["source_boundary_fields"] == {
        "firstRowName": "EXAMPLE COUNTY",
        "firstRowCaseNumber": "GV24000123-00",
        "lastRowName": "EXAMPLE COUNTY",
        "lastRowCaseNumber": "GV24000123-00",
    }
    assert page.records[0]["values"]["hearing_date_iso"] == "2026-06-09"
    assert ("formAction", "next") in page.next_payload
    assert page.records[0]["source_detail_locator"]["session_values"] == {
        "clientSearchCounter": "10",
        "caseActive": "true",
    }


def test_parse_traffic_result_page_preserves_charge_and_result() -> None:
    page = parse_search_page(
        fixture("traffic_results.html"),
        operation="hearing",
        division="T",
        court=CourtOption("Arlington General District Court", "013"),
        native_page=1,
        source_url=CASE_SEARCH_URL,
    )
    assert page.has_next is False
    assert page.records[0]["values"] == {
        "case": "GT26000123-00",
        "defendant": "CASEY EXAMPLE",
        "complainant": "OFFICER SAMPLE",
        "charge": "40/25 SP",
        "hearing_time": "09:00 AM",
        "result": "Finalized",
    }


def test_parse_service_result_preserves_process_and_dates() -> None:
    page = parse_search_page(
        fixture("service_results.html"),
        operation="service",
        division="V",
        court=CourtOption("Arlington General District Court", "013"),
        native_page=1,
        source_url=CASE_SEARCH_URL,
    )
    assert page.has_next is False
    record = page.records[0]
    assert record["query_role"] == "service"
    assert record["values"]["person_served"] == "EXAMPLE DYNAMICS LLC"
    assert record["values"]["process_type"] == "Garnishment Summons"
    assert record["values"]["how_served"] == "In Person"
    assert record["values"]["date_issued_iso"] == "2026-06-04"
    assert record["values"]["date_served_iso"] == "2026-07-07"


def test_name_search_posts_visible_hidden_fields_and_source_status() -> None:
    session = FakeSession(
        [
            response("terms.html", LANDING_URL),
            response("welcome.html", LANDING_POST_URL),
            response(
                "welcome.html",
                "https://eapps.courts.state.va.us/gdcourts/changeCourt.do",
            ),
            response(
                "name_form.html",
                "https://eapps.courts.state.va.us/gdcourts/nameSearch.do",
            ),
            response(
                "no_results.html",
                "https://eapps.courts.state.va.us/gdcourts/nameSearch.do",
            ),
        ]
    )
    client = VAGeneralDistrictClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _seconds: None,
    )
    fetched = client.search_name(
        "013",
        "EXAMPLE*",
        division="civil",
        first_name="ALEX",
        status="all",
    )
    assert fetched.records == ()
    assert fetched.source_exhausted is True
    submitted = session.calls[-1]["data"]
    assert submitted["localnamesearchlastName"] == "EXAMPLE*"
    assert submitted["lastName"] == "EXAMPLE*"
    assert submitted["localnamesearchfirstName"] == "ALEX"
    assert submitted["firstName"] == "ALEX"
    assert submitted["localnamesearchsearchCategory"] == "O"
    assert submitted["searchCategory"] == "O"


def test_service_search_posts_source_service_state() -> None:
    session = FakeSession(
        [
            response("terms.html", LANDING_URL),
            response("welcome.html", LANDING_POST_URL),
            response(
                "welcome.html",
                "https://eapps.courts.state.va.us/gdcourts/changeCourt.do",
            ),
            response("service_form.html", CASE_SEARCH_URL),
            response("service_results.html", CASE_SEARCH_URL),
        ]
    )
    client = VAGeneralDistrictClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _seconds: None,
    )
    fetched = client.search_service(
        "013",
        "EXAMPLE",
        division="civil",
    )
    assert fetched.records[0]["values"]["person_served"] == ("EXAMPLE DYNAMICS LLC")
    submitted = session.calls[-1]["data"]
    assert submitted["lastName"] == "EXAMPLE"
    assert submitted["searchCategory"] == "S"
    assert submitted["searchType"] == "servicesName"
    assert submitted["caseSearch"] == "Search"


def test_parse_civil_detail_preserves_empty_and_absent_section_states() -> None:
    record = parse_case_detail(
        fixture("civil_detail.html"),
        division="V",
        court=CourtOption("Arlington General District Court", "013"),
        source_url=(
            "https://eapps.courts.state.va.us/gdcourts/criminalCivilCaseSearch.do"
        ),
        requested_case_number="GV26000001-00",
    )
    assert record is not None
    assert record["raw_case_number"] == "GV26000001-00"
    assert record["filed_date_iso"] == "2026-06-18"
    assert len(record["plaintiffs"]) == 2
    assert record["plaintiffs"][0]["values"]["name"] == "ALEX RIVER"
    assert record["reports"] == []
    assert record["section_states"]["reports"] == "published_empty"
    assert record["section_states"]["garnishment_information"] == ("published_empty")
    assert record["section_states"]["appeal_information"] == "published_empty"
    assert record["judgment"]["principal_amount"] == "$1,250.00"
    assert record["document_access"]["filing_index_present"] is False
    assert record["document_access"]["state"] == (
        "not_published_by_case_information_source"
    )
    assert record["payment_access"] == {
        "state": "not_present_on_returned_case",
        "links": [],
    }


def test_parse_traffic_detail_preserves_masked_dob_and_disposition() -> None:
    record = parse_case_detail(
        fixture("traffic_detail.html"),
        division="T",
        court=CourtOption("Arlington General District Court", "013"),
        source_url=(
            "https://eapps.courts.state.va.us/gdcourts/criminalCivilCaseSearch.do"
        ),
        requested_case_number="GT26000123-00",
    )
    assert record is not None
    assert record["date_of_birth_at_source"] == "04/11/****"
    assert record["date_of_birth_state"] == "year_redacted"
    assert record["charge"]["offense_date_iso"] == "2026-06-26"
    assert record["hearings"][0]["values"]["date_iso"] == "2026-07-30"
    assert record["service_process"] == []
    assert record["section_states"]["service_process"] == "published_empty"
    assert record["disposition"]["final_disposition"] == "Dismissed"
    assert record["disposition"]["sentence_time"] == ("00Months 000Days 00Hours")


def test_authoritative_empty_and_validation_error_are_distinct() -> None:
    court = CourtOption("Arlington General District Court", "013")
    assert (
        parse_case_detail(
            fixture("no_results.html"),
            division="V",
            court=court,
            source_url=CASE_SEARCH_URL,
            requested_case_number="GV99999999-99",
        )
        is None
    )
    with pytest.raises(VAGDCSelectionError, match="valid Case Number"):
        parse_case_detail(
            fixture("invalid_search.html"),
            division="V",
            court=court,
            source_url=CASE_SEARCH_URL,
            requested_case_number="INVALID",
        )


def test_rate_limit_page_is_not_an_empty_result() -> None:
    with pytest.raises(VAGeneralDistrictError) as caught:
        _raise_page_failure(
            fixture("rate_limited.html"),
            source_url=LANDING_URL,
        )
    assert caught.value.status == ResultStatus.RATE_LIMITED
    assert caught.value.retryable is True


def test_client_exhausts_session_bound_native_pages() -> None:
    client, session = client_for_hearing_pages(
        "civil_results_page1.html",
        "civil_results_page2.html",
    )
    fetched = client.search_hearing(
        "013",
        "2026-07-30",
        division="civil",
    )
    assert [row["raw_case_number"] for row in fetched.records] == [
        "GV26000001-00",
        "GV26000002-00",
        "GV26000003-00",
    ]
    assert fetched.pages_fetched == 2
    assert fetched.start_native_page == 1
    assert fetched.end_native_page == 2
    assert fetched.source_exhausted is True
    assert fetched.next_cursor is None
    assert fetched.reported_total is None
    next_call = session.calls[-1]
    assert next_call["method"] == "POST"
    assert ("caseInfoScrollForward", "Next") in next_call["data"]


def test_limit_cursor_replays_and_resumes_mid_page() -> None:
    first_client, _session = client_for_hearing_pages(
        "civil_results_page1.html",
    )
    first = first_client.search_hearing(
        "013",
        "2026-07-30",
        division="civil",
        limit=1,
    )
    assert [row["raw_case_number"] for row in first.records] == ["GV26000001-00"]
    assert first.source_exhausted is False
    assert first.next_cursor is not None
    cursor = _decode_cursor(first.next_cursor)
    assert cursor["resume_page"] == 1
    assert cursor["row_offset"] == 1

    resumed_client, _session = client_for_hearing_pages(
        "civil_results_page1.html",
        "civil_results_page2.html",
    )
    resumed = resumed_client.search_hearing(
        "013",
        "2026-07-30",
        division="civil",
        cursor=first.next_cursor,
    )
    assert [row["raw_case_number"] for row in resumed.records] == [
        "GV26000002-00",
        "GV26000003-00",
    ]
    assert resumed.source_exhausted is True


def test_cursor_detects_changed_page_boundary() -> None:
    first_client, _session = client_for_hearing_pages(
        "civil_results_page1.html",
    )
    first = first_client.search_hearing(
        "013",
        "2026-07-30",
        division="civil",
        limit=1,
    )
    changed_html = fixture("civil_results_page1.html").replace(
        "GV26000002-00",
        "GV26000999-00",
    )
    session = FakeSession(
        [
            response("terms.html", LANDING_URL),
            response("welcome.html", LANDING_POST_URL),
            response(
                "welcome.html",
                "https://eapps.courts.state.va.us/gdcourts/changeCourt.do",
            ),
            response("hearing_form.html", CASE_SEARCH_URL),
            FakeResponse(changed_html, CASE_SEARCH_URL),
        ]
    )
    changed_client = VAGeneralDistrictClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _seconds: None,
    )
    with pytest.raises(VAGDCSourceChangedError, match="ordering changed"):
        changed_client.search_hearing(
            "013",
            "2026-07-30",
            division="civil",
            cursor=first.next_cursor,
        )


def test_cursor_does_not_turn_changed_empty_result_into_authoritative_negative() -> (
    None
):
    first_client, _session = client_for_hearing_pages(
        "civil_results_page1.html",
    )
    first = first_client.search_hearing(
        "013",
        "2026-07-30",
        division="civil",
        limit=1,
    )
    empty_client, _session = client_for_hearing_pages("no_results.html")
    with pytest.raises(VAGDCSourceChangedError, match="replaying a cursor"):
        empty_client.search_hearing(
            "013",
            "2026-07-30",
            division="civil",
            cursor=first.next_cursor,
        )


def test_mid_paging_failure_preserves_records_and_cursor() -> None:
    client, _session = client_for_hearing_pages(
        "civil_results_page1.html",
        "rate_limited.html",
    )
    fetched = client.search_hearing(
        "013",
        "2026-07-30",
        division="civil",
    )
    assert [row["raw_case_number"] for row in fetched.records] == [
        "GV26000001-00",
        "GV26000002-00",
    ]
    assert fetched.source_exhausted is False
    assert fetched.next_cursor is not None
    assert fetched.error is not None
    assert fetched.error.status == ResultStatus.RATE_LIMITED


def test_partial_result_envelope_keeps_records_error_and_cursor() -> None:
    page = parse_search_page(
        fixture("civil_results_page1.html"),
        operation="hearing",
        division="V",
        court=CourtOption("Arlington General District Court", "013"),
        native_page=1,
        source_url=CASE_SEARCH_URL,
    )
    error = VAGeneralDistrictError(
        "rate_limited",
        "source paused paging",
        status=ResultStatus.RATE_LIMITED,
        category="rate_limit",
        retryable=True,
    )
    fetched = SearchFetch(
        records=page.records,
        pages_fetched=1,
        replay_pages_fetched=0,
        start_native_page=1,
        end_native_page=1,
        source_exhausted=False,
        next_cursor="va-gdc:v1:test",
        reported_total=None,
        schema_fingerprints=(page.schema_fingerprint,),
        source_url=page.source_url,
        error=error,
    )
    args = build_parser().parse_args(
        [
            "hearing",
            "013",
            "2026-07-30",
            "--division",
            "civil",
            "--json",
        ]
    )
    result = _search_result(build_query(args), fetched, args)
    assert result.status == ResultStatus.PARTIAL
    assert len(result.records) == 2
    assert result.next_cursor == "va-gdc:v1:test"
    assert result.errors[0].code == "rate_limited"


def test_max_pages_returns_next_native_page_cursor() -> None:
    client, _session = client_for_hearing_pages(
        "civil_results_page1.html",
    )
    fetched = client.search_hearing(
        "013",
        "2026-07-30",
        division="civil",
        max_pages=1,
    )
    assert len(fetched.records) == 2
    assert fetched.source_exhausted is False
    assert fetched.next_cursor is not None
    cursor = _decode_cursor(fetched.next_cursor)
    assert cursor["resume_page"] == 2
    assert cursor["row_offset"] == 0
    assert cursor["anchor_page"] == 1


def test_probe_is_bounded_and_verifies_both_division_forms() -> None:
    session = FakeSession(
        [
            response("terms.html", LANDING_URL),
            response("welcome.html", LANDING_POST_URL),
            response(
                "welcome.html",
                "https://eapps.courts.state.va.us/gdcourts/changeCourt.do",
            ),
            response(
                "case_form.html",
                "https://eapps.courts.state.va.us/gdcourts/criminalCivilCaseSearch.do",
            ),
            response(
                "case_form.html",
                "https://eapps.courts.state.va.us/gdcourts/criminalCivilCaseSearch.do",
            ),
            response("hearing_form.html", CASE_SEARCH_URL),
        ]
    )
    client = VAGeneralDistrictClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _seconds: None,
    )
    record = client.probe("013")[0]
    assert record["status"] == "ok"
    assert record["terms_state"] == "accepted_by_adapter"
    assert record["court_component_count"] == 3
    assert len(record["selected_court_route_labels"]) == 8
    assert record["civil_case_form_present"] is True
    assert record["traffic_criminal_case_form_present"] is True
    assert record["source_native_hearing_types"] == [
        {"code": "MO", "source_label": "MO - Motion"}
    ]
    assert record["request_count"] == 6


def test_execute_returns_no_results_without_turning_it_into_failure() -> None:
    class EmptyClient:
        def get_case(
            self,
            _court: str,
            _case_number: str,
            *,
            division: str,
        ) -> None:
            assert division == "civil"
            return None

    args = build_parser().parse_args(
        ["case", "013", "GV99999999-99", "--division", "civil", "--json"]
    )
    result = execute(args, client=EmptyClient(), log_results=False)
    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_execute_routes_needs_no_network_client() -> None:
    class ExplodingClient:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError(f"unexpected client access: {name}")

    args = build_parser().parse_args(["routes", "--json"])
    result = execute(args, client=ExplodingClient(), log_results=False)
    assert result.status == ResultStatus.OK
    assert result.records[0]["record_kind"] == "source_route_manifest"
