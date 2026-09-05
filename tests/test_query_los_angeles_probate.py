from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools import query_los_angeles_probate
from tools.ingest_state_court_records import ingest_envelope, validate_envelope
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RateLimitedHTTPError, SourceSchemaError


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/los_angeles_probate"
)
CASE_SEARCH_HTML = (FIXTURE_DIR / "case_search.html").read_text(
    encoding="utf-8"
)
CASE_SEARCH_LIVE_OPTIONS_HTML = (
    FIXTURE_DIR / "case_search_live_options.html"
).read_text(encoding="utf-8")
CASE_SUMMARY_HTML = (FIXTURE_DIR / "case_summary.html").read_text(
    encoding="utf-8"
)
CASE_EMPTY_HTML = (FIXTURE_DIR / "case_empty.html").read_text(
    encoding="utf-8"
)
NOTES_SEARCH_HTML = (FIXTURE_DIR / "notes_search.html").read_text(
    encoding="utf-8"
)
NOTES_FUTURE_HTML = (FIXTURE_DIR / "notes_future.html").read_text(
    encoding="utf-8"
)
NOTES_EMPTY_HTML = (FIXTURE_DIR / "notes_empty.html").read_text(
    encoding="utf-8"
)
CALENDAR_HTML = (FIXTURE_DIR / "calendar.html").read_text(
    encoding="utf-8"
)
CALENDAR_EMPTY_HTML = (FIXTURE_DIR / "calendar_empty.html").read_text(
    encoding="utf-8"
)
ALLOWED = {
    "allowed": True,
    "access_class": "A",
    "reason_code": "anonymous_public_route",
    "limits": {},
}


class FakeResponse:
    def __init__(
        self,
        text: str,
        *,
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.text = text
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}


class FakeSession:
    def __init__(
        self,
        *,
        get_responses: list[FakeResponse] | None = None,
        post_responses: list[FakeResponse] | None = None,
    ) -> None:
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("get", {"url": url, **kwargs}))
        return self.get_responses.pop(0)

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("post", {"url": url, **kwargs}))
        return self.post_responses.pop(0)


class FakeLAClient:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        lookup = query_los_angeles_probate.parse_case_lookup_html(
            CASE_SUMMARY_HTML
        )
        assert lookup.page is not None
        self.case_lookup = lookup
        self.notes_pages = (
            query_los_angeles_probate.parse_notes_results_html(
                NOTES_FUTURE_HTML
            ),
        )
        self.calendar_page = query_los_angeles_probate.parse_calendar_html(
            CALENDAR_HTML
        )
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def case(self, case_number: str, *, courthouse: str | None = None):
        self.calls.append(
            (
                "case",
                {"case_number": case_number, "courthouse": courthouse},
            )
        )
        if self.error is not None:
            raise self.error
        return self.case_lookup

    def notes(self, case_number: str, *, view: str = "future"):
        self.calls.append(
            ("notes", {"case_number": case_number, "view": view})
        )
        if self.error is not None:
            raise self.error
        return self.notes_pages

    def calendar(self, case_number: str):
        self.calls.append(("calendar", {"case_number": case_number}))
        if self.error is not None:
            raise self.error
        return self.calendar_page

    def probe(self):
        self.calls.append(("probe", {}))
        if self.error is not None:
            raise self.error
        return query_los_angeles_probate.ProbeSnapshot(
            case_search=query_los_angeles_probate.parse_case_search_html(
                CASE_SEARCH_HTML
            ),
            case_summary=self.case_lookup.page,
            notes_search=query_los_angeles_probate.parse_notes_search_html(
                NOTES_SEARCH_HTML
            ),
            calendar=query_los_angeles_probate.parse_calendar_html(
                CALENDAR_EMPTY_HTML
            ),
        )


def _parse(*values: str):
    return query_los_angeles_probate.build_parser().parse_args(list(values))


def _execute(args, monkeypatch, *, client=None, decision=ALLOWED):
    monkeypatch.setattr(
        query_los_angeles_probate,
        "log_search",
        lambda *_args: None,
    )
    return query_los_angeles_probate.execute(
        args,
        access_decision=decision,
        client=client or FakeLAClient(),
    )


def test_case_search_parser_preserves_native_courthouse_codes():
    page = query_los_angeles_probate.parse_case_search_html(CASE_SEARCH_HTML)

    assert page.request_verification_token == "case-token"
    assert page.courthouse_options == {
        "": "All Courthouses",
        "ATP": "Michael Antonovich Antelope Valley Courthouse",
        "LA": "Stanley Mosk Courthouse",
    }


def test_case_client_uses_same_session_and_exact_official_fields():
    session = FakeSession(
        get_responses=[FakeResponse(CASE_SEARCH_HTML)],
        post_responses=[FakeResponse(CASE_SUMMARY_HTML)],
    )
    client = query_los_angeles_probate.LosAngelesProbateClient(
        session=session,
        timeout=11,
    )

    lookup = client.case("17STPB02676", courthouse="LA")

    assert lookup.page is not None
    assert lookup.page.case_number == "17STPB02676"
    assert [name for name, _kwargs in session.calls] == ["get", "post"]
    post = session.calls[1][1]
    assert post["url"] == query_los_angeles_probate.CASE_SEARCH_URL
    assert post["timeout"] == 11
    assert post["data"] == {
        "txtCaseNumber": "17STPB02676",
        "ddlCourthouse": "LA",
        "action": "Search",
        "__RequestVerificationToken": "case-token",
    }
    assert post["headers"]["Referer"] == (
        query_los_angeles_probate.CASE_SEARCH_URL
    )


@pytest.mark.parametrize(
    ("requested", "posted"),
    [
        ("LA", "LA;Stanley Mosk Courthouse"),
        ("la", "LA;Stanley Mosk Courthouse"),
        (
            "LA;Stanley Mosk Courthouse",
            "LA;Stanley Mosk Courthouse",
        ),
        (
            "ATP",
            "ATP;Michael Antonovich Antelope Valley Courthouse",
        ),
    ],
)
def test_case_client_resolves_code_and_preserves_live_native_option(
    requested,
    posted,
):
    session = FakeSession(
        get_responses=[FakeResponse(CASE_SEARCH_LIVE_OPTIONS_HTML)],
        post_responses=[FakeResponse(CASE_SUMMARY_HTML)],
    )
    client = query_los_angeles_probate.LosAngelesProbateClient(
        session=session,
    )

    lookup = client.case("17STPB02676", courthouse=requested)

    assert lookup.page is not None
    assert lookup.native_courthouse_value == posted
    assert session.calls[1][1]["data"]["ddlCourthouse"] == posted


def test_unknown_courthouse_reports_source_offered_options():
    session = FakeSession(
        get_responses=[FakeResponse(CASE_SEARCH_HTML)],
    )
    client = query_los_angeles_probate.LosAngelesProbateClient(
        session=session
    )

    with pytest.raises(
        query_los_angeles_probate.LAProbateQueryError
    ) as raised:
        client.case("17STPB02676", courthouse="OTHER")

    assert raised.value.code == "unknown_courthouse"
    assert raised.value.details["available_courthouses"]["LA"] == (
        "Stanley Mosk Courthouse"
    )


def test_case_parser_and_normalizer_preserve_all_source_sections_and_duplicates():
    lookup = query_los_angeles_probate.parse_case_lookup_html(
        CASE_SUMMARY_HTML,
        expected_case_number="17STPB02676",
    )
    assert lookup.page is not None
    page = lookup.page

    assert page.case_title == "HAMILTON, CLARISSA RUNNELS - DECEDENT"
    assert page.filing_date == "3/28/2017"
    assert len(page.future_hearings) == 1
    assert len(page.parties) == 3
    assert len(page.documents) == 2
    assert len(page.past_proceedings) == 1
    assert len(page.register_actions) == 3

    record, next_cursor = query_los_angeles_probate.normalize_case(page)

    assert next_cursor is None
    assert record["filing_date"] == "2017-03-28"
    assert record["status"] == "Court Supervision Terminated on 7/20/2020"
    assert len(record["docket_entries"]) == 5
    assert len(record["documents"]) == 2
    assert len(record["parties"]) == 3
    duplicate_register = [
        entry
        for entry in record["docket_entries"]
        if entry["event_type"] == "register_of_actions"
        and entry["raw_text"] == "Petition for Final Discharge"
    ]
    assert len(duplicate_register) == 2
    assert (
        duplicate_register[0]["native_entry_id"]
        != duplicate_register[1]["native_entry_id"]
    )
    assert (
        record["documents"][0]["native_document_id"]
        != record["documents"][1]["native_document_id"]
    )
    assert record["document_access"] == {
        "service_url": (
            "https://www.lacourt.ca.gov/paos/v2web3/DocumentImages/"
            "SearchCaseNumber?casenumber=17STPB02676"
        ),
        "search_without_account": True,
        "delivery": "email_after_purchase",
        "probate_preview_available": False,
    }

    repeated, _cursor = query_los_angeles_probate.normalize_case(page)
    assert [
        entry["native_entry_id"] for entry in record["docket_entries"]
    ] == [
        entry["native_entry_id"] for entry in repeated["docket_entries"]
    ]
    assert [
        document["native_document_id"] for document in record["documents"]
    ] == [
        document["native_document_id"]
        for document in repeated["documents"]
    ]


def test_case_has_no_implicit_cap_and_supports_caller_paging(monkeypatch):
    default_args = _parse("case", "17STPB02676")
    assert default_args.limit is None

    full = _execute(default_args, monkeypatch).to_dict()
    assert len(full["records"][0]["docket_entries"]) == 5
    assert full["next_cursor"] is None

    paged = _execute(
        _parse(
            "case",
            "17STPB02676",
            "--limit",
            "2",
            "--offset",
            "1",
        ),
        monkeypatch,
    ).to_dict()
    assert len(paged["records"][0]["docket_entries"]) == 2
    assert paged["next_cursor"] == "la-probate:offset:3"
    assert paged["records"][0]["search_metadata"][
        "source_counts"
    ]["docket_entries_combined"] == 5


def test_case_result_round_trips_through_court_ingestion(
    monkeypatch,
    tmp_path,
):
    result = _execute(
        _parse("case", "17STPB02676"),
        monkeypatch,
    )
    payload = result.to_dict()

    validate_envelope(payload)
    receipt = ingest_envelope(
        payload,
        court_db=tmp_path / "courts.db",
    )

    assert receipt["source_status"] == "ok"
    assert receipt["projected"]["cases"] == 1
    assert receipt["projected"]["parties"] == 3
    assert receipt["projected"]["docket_entries"] == 5
    assert receipt["projected"]["documents"] == 2


def test_case_no_match_is_authoritative_no_results(monkeypatch):
    lookup = query_los_angeles_probate.parse_case_lookup_html(CASE_EMPTY_HTML)
    assert lookup.page is None
    assert lookup.no_match_message == (
        "No match found for case number 99STPB99999."
    )
    client = FakeLAClient()
    client.case_lookup = lookup

    result = _execute(
        _parse("case", "99STPB99999"),
        monkeypatch,
        client=client,
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_case_missing_required_section_is_source_changed(monkeypatch):
    broken = CASE_SUMMARY_HTML.replace('<a name="Parties"></a>', "")
    with pytest.raises(SourceSchemaError):
        query_los_angeles_probate.parse_case_lookup_html(broken)

    result = _execute(
        _parse("case", "17STPB02676"),
        monkeypatch,
        client=FakeLAClient(error=SourceSchemaError(
            "section changed",
            url=query_los_angeles_probate.CASE_RESULT_URL,
        )),
    )
    assert result.status == ResultStatus.SOURCE_CHANGED


def test_notes_parser_extracts_hearing_metadata_and_key_text_sections():
    page = query_los_angeles_probate.parse_notes_results_html(
        NOTES_FUTURE_HTML,
        expected_case_number="26STPB00601",
    )

    assert page.view == "future"
    assert len(page.notes) == 1
    note = page.notes[0]
    assert note.department == "217"
    assert note.hearing_datetime == "8/13/2026 10:32 AM"
    assert note.calendar_item == "3001"
    assert note.caption == "Schultz, Steven A. - Conservatorship"
    assert note.hearing_type == "Status Hearing"
    assert note.petitioners == "Superior Court"
    assert note.attorneys == "County Counsel"
    assert note.last_date_changed == "7/24/2026"
    assert note.last_note_changed_by == "Trena Arismendez"
    assert note.recommended_disposition == "Continue"
    assert note.related_items == "3001"
    assert note.is_contested == "False"
    assert "Public Guardian appointed conservator" in (note.summary_text or "")
    assert "court set a status hearing" in (note.facts_text or "")
    assert "requested status report" in (note.matters_to_clear or "")
    assert note.relief_text is None
    assert note.findings_and_order_text is None
    assert "Court to review the filing" in (
        note.probate_examiner_comments or ""
    )


def test_notes_client_switches_to_past_view_on_results_route():
    past_html = NOTES_FUTURE_HTML.replace(
        "FUTURE HEARINGS",
        "PAST HEARINGS",
    ).replace(
        "notes-result-token",
        "notes-past-token",
    )
    session = FakeSession(
        get_responses=[FakeResponse(NOTES_SEARCH_HTML)],
        post_responses=[
            FakeResponse(NOTES_FUTURE_HTML),
            FakeResponse(past_html),
        ],
    )
    client = query_los_angeles_probate.LosAngelesProbateClient(
        session=session,
        timeout=9,
    )

    pages = client.notes("26STPB00601", view="all")

    assert [page.view for page in pages] == ["future", "past"]
    assert [name for name, _kwargs in session.calls] == [
        "get",
        "post",
        "post",
    ]
    assert session.calls[1][1]["data"] == {
        "CaseNumber": "26STPB00601",
        "__RequestVerificationToken": "notes-search-token",
    }
    assert session.calls[2][1]["url"] == (
        query_los_angeles_probate.NOTES_RESULTS_URL
    )
    assert session.calls[2][1]["data"] == {
        "FormAction": "26STPB00601;past",
        "__RequestVerificationToken": "notes-result-token",
    }


def test_notes_empty_view_is_authoritative_no_results(monkeypatch):
    page = query_los_angeles_probate.parse_notes_results_html(
        NOTES_EMPTY_HTML
    )
    assert page.notes == ()
    assert page.message == "No probate notes found for future hearings."
    client = FakeLAClient()
    client.notes_pages = (page,)

    result = _execute(
        _parse("notes", "17STPB02676"),
        monkeypatch,
        client=client,
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.errors == ()


def test_notes_normalization_is_ingestible_and_uncapped(
    monkeypatch,
    tmp_path,
):
    args = _parse("notes", "26STPB00601", "--view", "future")
    assert args.limit is None

    payload = _execute(args, monkeypatch).to_dict()
    validate_envelope(payload)
    note_record = payload["records"][0]
    assert len(note_record["docket_entries"]) == 1
    assert note_record["docket_entries"][0]["event_type"] == "probate_note"
    assert note_record["probate_notes"][0]["matters_to_clear"] is not None
    assert note_record["probate_notes"][0]["facts_text"] is not None
    assert (
        note_record["probate_notes"][0]["probate_examiner_comments"] is not None
    )

    receipt = ingest_envelope(
        payload,
        court_db=tmp_path / "notes-courts.db",
    )
    assert receipt["projected"]["cases"] == 1
    assert receipt["projected"]["docket_entries"] == 1


def test_calendar_parser_preserves_window_and_hearing_fields():
    page = query_los_angeles_probate.parse_calendar_html(
        CALENDAR_HTML,
        expected_case_number="26STPB00601",
    )
    assert page.caption == "SCHULTZ, STEVEN A. - CONSERVATORSHIP"
    assert page.filing_date == "1/16/2026"
    assert len(page.hearings) == 2
    assert page.hearings[0].hearing_time == "10:32 AM"
    assert page.hearings[0].department == "Probate Department 217"
    assert page.hearings[0].location == (
        "111 North Hill Street, Los Angeles, CA 90012"
    )

    empty = query_los_angeles_probate.parse_calendar_html(
        CALENDAR_EMPTY_HTML
    )
    assert empty.hearings == ()
    assert empty.calendar_window_days == 266
    assert empty.business_window_days == 180


def test_calendar_execute_is_ingestible_and_empty_window_is_no_results(
    monkeypatch,
    tmp_path,
):
    args = _parse("calendar", "26STPB00601")
    assert args.limit is None
    payload = _execute(args, monkeypatch).to_dict()
    validate_envelope(payload)
    assert len(payload["records"][0]["docket_entries"]) == 2
    receipt = ingest_envelope(
        payload,
        court_db=tmp_path / "calendar-courts.db",
    )
    assert receipt["projected"]["docket_entries"] == 2

    client = FakeLAClient()
    client.calendar_page = query_los_angeles_probate.parse_calendar_html(
        CALENDAR_EMPTY_HTML
    )
    result = _execute(
        _parse("calendar", "17STPB02676"),
        monkeypatch,
        client=client,
    )
    assert result.status == ResultStatus.NO_RESULTS


def test_rate_limit_and_access_decision_remain_distinct_failures(monkeypatch):
    rate_limited = _execute(
        _parse("case", "17STPB02676"),
        monkeypatch,
        client=FakeLAClient(
            error=RateLimitedHTTPError(
                429,
                url=query_los_angeles_probate.CASE_SEARCH_URL,
            )
        ),
    )
    assert rate_limited.status == ResultStatus.RATE_LIMITED

    restricted = _execute(
        _parse("case", "17STPB02676"),
        monkeypatch,
        decision={
            "allowed": False,
            "access_class": "C",
            "reason_code": "human_required",
            "reason": "fixture decision",
        },
    )
    assert restricted.status == ResultStatus.HUMAN_REQUIRED
    assert restricted.errors[0].code == "human_required"


def test_probe_reports_each_verified_machine_contract(monkeypatch):
    result = _execute(_parse("probe"), monkeypatch)
    payload = result.to_dict()
    validate_envelope(payload)

    assert payload["status"] == "ok"
    probe = payload["records"][0]
    assert probe["probe_case_number"] == "17STPB02676"
    assert set(probe["available_courthouses"]) == {"", "ATP", "LA"}
    assert probe["case_summary_counts"] == {
        "future_hearings": 1,
        "parties": 3,
        "documents": 2,
        "past_proceedings": 1,
        "register_actions": 3,
    }
    assert probe["calendar_probe_message"].startswith(
        "There are no future hearings scheduled"
    )
