from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools import query_los_angeles_court as la
from tools.ingest_state_court_records import ingest_envelope, validate_envelope
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/los_angeles_court"
)
CASE_SEARCH_HTML = (FIXTURE_DIR / "case_search.html").read_text(
    encoding="utf-8"
)
CASE_SUMMARY_HTML = (FIXTURE_DIR / "case_summary.html").read_text(
    encoding="utf-8"
)
CASE_EMPTY_HTML = (FIXTURE_DIR / "case_empty.html").read_text(
    encoding="utf-8"
)
TENTATIVE_INDEX_HTML = (FIXTURE_DIR / "tentative_index.html").read_text(
    encoding="utf-8"
)
TENTATIVE_RESULT_HTML = (FIXTURE_DIR / "tentative_result.html").read_text(
    encoding="utf-8"
)
TENTATIVE_EMPTY_HTML = (FIXTURE_DIR / "tentative_empty.html").read_text(
    encoding="utf-8"
)


class FakeResponse:
    def __init__(
        self,
        text: str,
        *,
        status_code: int = 200,
        url: str | None = None,
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.text = text
        self.status_code = status_code
        self.url = url
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
        self.headers: dict[str, str] = {}
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("get", {"url": url, **kwargs}))
        response = self.get_responses.pop(0)
        if response.url is None:
            response.url = url
        return response

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("post", {"url": url, **kwargs}))
        response = self.post_responses.pop(0)
        if response.url is None:
            response.url = url
        return response

    def close(self) -> None:
        self.closed = True


def _client(session: FakeSession) -> la.LosAngelesCourtClient:
    return la.LosAngelesCourtClient(
        session=session,
        timeout=11,
        minimum_interval=0,
        sleeper=lambda _delay: None,
    )


def _parse(*values: str):
    return la.build_parser().parse_args(list(values))


def test_case_search_parser_preserves_native_courthouse_values() -> None:
    page = la.parse_case_search_html(CASE_SEARCH_HTML)

    assert page.request_verification_token == "civil-case-token"
    assert page.courthouse_options == {
        "": "Select a Courthouse (Optional)",
        "ALH;Alhambra Courthouse": "Alhambra Courthouse",
        "LA;Stanley Mosk Courthouse": "Stanley Mosk Courthouse",
    }


def test_case_client_uses_same_session_and_exact_official_fields() -> None:
    session = FakeSession(
        get_responses=[FakeResponse(CASE_SEARCH_HTML)],
        post_responses=[
            FakeResponse(
                CASE_SUMMARY_HTML,
                url=la.CASE_RESULT_URL,
            )
        ],
    )
    client = _client(session)

    lookup = client.case(la.PROBE_CASE_NUMBER, courthouse="ALH")

    assert lookup.page is not None
    assert lookup.page.case_number == la.PROBE_CASE_NUMBER
    assert [name for name, _kwargs in session.calls] == ["get", "post"]
    post = session.calls[1][1]
    assert post["url"] == la.CASE_SEARCH_URL
    assert post["data"] == {
        "txtCaseNumber": la.PROBE_CASE_NUMBER,
        "ddlCourthouse": "ALH;Alhambra Courthouse",
        "action": "Search",
        "__RequestVerificationToken": "civil-case-token",
    }
    assert post["headers"]["Referer"] == la.CASE_SEARCH_URL
    assert post["allow_redirects"] is True
    assert post["timeout"] == 11


def test_unknown_courthouse_reports_current_native_options() -> None:
    session = FakeSession(
        get_responses=[FakeResponse(CASE_SEARCH_HTML)],
    )

    with pytest.raises(la.LASelectionError) as raised:
        _client(session).case(la.PROBE_CASE_NUMBER, courthouse="OTHER")

    assert raised.value.code == "unknown_courthouse"
    assert (
        raised.value.details["available_courthouses"][
            "ALH;Alhambra Courthouse"
        ]
        == "Alhambra Courthouse"
    )


def test_case_parser_and_normalizer_preserve_all_six_sections() -> None:
    lookup = la.parse_case_lookup_html(CASE_SUMMARY_HTML)

    assert lookup.page is not None
    page = lookup.page
    assert page.case_number == la.PROBE_CASE_NUMBER
    assert page.case_title.startswith("JAMES MATYAS")
    assert len(page.future_hearings) == 1
    assert len(page.parties) == 2
    assert len(page.documents) == 2
    assert len(page.past_proceedings) == 1
    assert len(page.register_actions) == 3

    record, next_cursor = la.normalize_case(page)

    assert next_cursor is None
    assert record["filing_date"] == "2024-03-22"
    assert len(record["docket_entries"]) == 5
    assert len(record["documents"]) == 2
    assert (
        record["documents"][0]["native_document_id"]
        != record["documents"][1]["native_document_id"]
    )
    register = [
        entry
        for entry in record["docket_entries"]
        if entry["event_type"] == "register_of_actions"
    ]
    assert len(register) == 3
    assert register[0]["native_entry_id"] != register[1]["native_entry_id"]
    assert record["document_access"] == {
        "index_access_state": "public_anonymous",
        "image_delivery_access_state": "paid_guest_or_account",
        "service_url": page.document_image_url,
    }


def test_case_paging_is_optional_and_caller_selected() -> None:
    page = la.parse_case_lookup_html(CASE_SUMMARY_HTML).page
    assert page is not None

    first, next_cursor = la.normalize_case(page, entry_limit=2)
    complete, complete_cursor = la.normalize_case(page)

    assert len(first["docket_entries"]) == 2
    assert next_cursor == "la-civil-case-entry:2"
    assert len(complete["docket_entries"]) == 5
    assert complete_cursor is None


def test_case_no_match_is_authoritative() -> None:
    lookup = la.parse_case_lookup_html(CASE_EMPTY_HTML)

    assert lookup.page is None
    assert lookup.no_match_message == (
        "No match found for case number 99NNCV99999."
    )


def test_case_missing_required_section_is_source_changed() -> None:
    changed = CASE_SUMMARY_HTML.replace(
        '<a name="RegisterOfAction"></a>',
        "",
    )

    with pytest.raises(la.LASourceChangedError) as raised:
        la.parse_case_lookup_html(changed)

    assert raised.value.code == "case_section_missing"
    assert raised.value.status is ResultStatus.SOURCE_CHANGED


def test_tentative_index_preserves_webforms_state_and_exact_values() -> None:
    page = la.parse_tentative_index_html(TENTATIVE_INDEX_HTML)

    assert page.hidden_fields == {
        "__VIEWSTATE": "fixture-viewstate",
        "__VIEWSTATEGENERATOR": "fixture-generator",
        "__EVENTVALIDATION": "fixture-eventvalidation",
    }
    assert len(page.selections) == 3
    assert page.selections[1].native_value == "BH ,205,07/30/2026"
    assert page.selections[1].location_code == "BH"
    assert page.selections[1].department == "205"
    assert page.selections[1].hearing_date_iso == "2026-07-30"


def test_tentative_client_posts_exact_selection_and_hidden_state() -> None:
    session = FakeSession(
        get_responses=[FakeResponse(TENTATIVE_INDEX_HTML)],
        post_responses=[
            FakeResponse(
                TENTATIVE_RESULT_HTML,
                url=la.TENTATIVE_RESULT_URL,
            )
        ],
    )
    client = _client(session)

    selection, page = client.tentative_rulings(
        "BH ,205,07/30/2026"
    )

    assert selection.native_value == "BH ,205,07/30/2026"
    assert len(page.rulings) == 3
    post = session.calls[1][1]
    assert post["url"] == la.TENTATIVE_INDEX_URL
    assert post["headers"]["Referer"] == la.TENTATIVE_INDEX_URL
    assert post["data"] == {
        "__VIEWSTATE": "fixture-viewstate",
        "__VIEWSTATEGENERATOR": "fixture-generator",
        "__EVENTVALIDATION": "fixture-eventvalidation",
        la.TENTATIVE_SELECTOR_NAME: "BH ,205,07/30/2026",
        "CaseNumber": "",
    }


def test_tentative_parser_splits_cases_and_preserves_full_text() -> None:
    page = la.parse_tentative_result_html(TENTATIVE_RESULT_HTML)

    assert [ruling.case_number for ruling in page.rulings] == [
        "23AHCV00077",
        "24NNCV00427",
        "24NNCV00427",
    ]
    assert all(
        ruling.hearing_date == "July 30, 2026"
        for ruling in page.rulings
    )
    assert all(ruling.hearing_date_iso == "2026-07-30" for ruling in page.rulings)
    assert all(ruling.department == "3" for ruling in page.rulings)
    assert "GRANTED in part" in page.rulings[0].full_text
    assert "meet and confer" in page.rulings[0].full_text
    assert page.rulings[1].full_text == page.rulings[2].full_text
    assert page.rulings[1].duplicate_ordinal == 0
    assert page.rulings[2].duplicate_ordinal == 1


def test_tentative_empty_publication_is_no_results() -> None:
    page = la.parse_tentative_result_html(TENTATIVE_EMPTY_HTML)

    assert page.rulings == ()
    assert page.message == "No rulings have been published"


def test_tentative_occurrences_normalize_as_ingestible_cases() -> None:
    index = la.parse_tentative_index_html(TENTATIVE_INDEX_HTML)
    ruling = la.parse_tentative_result_html(
        TENTATIVE_RESULT_HTML
    ).rulings[1]

    record = la.normalize_tentative_ruling(
        ruling,
        selection=index.selections[0],
    )

    assert record["record_kind"] == "case"
    assert record["raw_case_number"] == la.PROBE_CASE_NUMBER
    assert record["occurrence_kind"] == "tentative_ruling"
    assert len(record["docket_entries"]) == 1
    entry = record["docket_entries"][0]
    assert entry["event_date"] == "2026-07-30"
    assert entry["department"] == "3"
    assert entry["raw_text"] == ruling.full_text
    assert record["provenance"]["selection"]["native_value"] == (
        "ALH,3,07/30/2026"
    )


def test_all_traversal_is_exhaustive_and_refreshes_webforms_state() -> None:
    session = FakeSession(
        get_responses=[
            FakeResponse(TENTATIVE_INDEX_HTML),
            FakeResponse(TENTATIVE_INDEX_HTML),
            FakeResponse(TENTATIVE_INDEX_HTML),
        ],
        post_responses=[
            FakeResponse(TENTATIVE_RESULT_HTML, url=la.TENTATIVE_RESULT_URL),
            FakeResponse(TENTATIVE_RESULT_HTML, url=la.TENTATIVE_RESULT_URL),
            FakeResponse(TENTATIVE_RESULT_HTML, url=la.TENTATIVE_RESULT_URL),
        ],
    )

    collection = _client(session).all_tentative_rulings()

    assert collection.selection_count_snapshot == 3
    assert collection.selections_requested == 3
    assert collection.selections_fetched == 3
    assert collection.next_selection_offset is None
    assert collection.incomplete_error is None
    assert len(collection.records) == 9
    assert [name for name, _kwargs in session.calls] == [
        "get",
        "post",
        "get",
        "post",
        "get",
        "post",
    ]
    posted = [
        kwargs["data"][la.TENTATIVE_SELECTOR_NAME]
        for name, kwargs in session.calls
        if name == "post"
    ]
    assert posted == [
        "ALH,3,07/30/2026",
        "BH ,205,07/30/2026",
        "LAM,309,07/31/2026",
    ]


def test_all_traversal_uses_only_explicit_caller_bound() -> None:
    session = FakeSession(
        get_responses=[FakeResponse(TENTATIVE_INDEX_HTML)],
        post_responses=[
            FakeResponse(TENTATIVE_RESULT_HTML, url=la.TENTATIVE_RESULT_URL)
        ],
    )

    collection = _client(session).all_tentative_rulings(
        max_selections=1
    )

    assert collection.selections_requested == 1
    assert collection.selections_fetched == 1
    assert collection.next_selection_offset == 1
    assert len(collection.records) == 3


def test_all_traversal_returns_partial_records_on_midstream_drift() -> None:
    changed_index = TENTATIVE_INDEX_HTML.replace(
        la.TENTATIVE_SELECTOR_NAME,
        "changed-selector",
    )
    session = FakeSession(
        get_responses=[
            FakeResponse(TENTATIVE_INDEX_HTML),
            FakeResponse(changed_index),
        ],
        post_responses=[
            FakeResponse(TENTATIVE_RESULT_HTML, url=la.TENTATIVE_RESULT_URL)
        ],
    )
    client = _client(session)

    result = la.execute(
        _parse("rulings", "all"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.PARTIAL
    assert len(result.records) == 3
    assert result.errors[0].code == "tentative_selector_missing"
    assert result.next_cursor == "la-tentative-selection:1"
    validate_envelope(result.to_dict())


def test_sources_distinguish_free_primary_and_paid_complements() -> None:
    result = la.execute(
        _parse("sources"),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    by_id = {
        record["component_id"]: record for record in result.records
    }
    assert by_id["civil_case_summary"]["native_access_state"] == (
        "free_anonymous_exact_case_number"
    )
    assert by_id["civil_tentative_rulings"]["native_access_state"] == (
        "free_anonymous_current_selection_full_text"
    )
    assert by_id["civil_name_index"]["access_state"] == "paid"
    assert by_id["civil_document_images"]["access_state"] == "paid"
    assert by_id["family_law_case_summary"]["access_state"] == "public"
    assert by_id["appellate_tentative_rulings"]["access_state"] == "public"
    validate_envelope(result.to_dict())


def test_case_execute_emits_valid_envelope_without_default_cap() -> None:
    session = FakeSession(
        get_responses=[FakeResponse(CASE_SEARCH_HTML)],
        post_responses=[
            FakeResponse(CASE_SUMMARY_HTML, url=la.CASE_RESULT_URL)
        ],
    )

    result = la.execute(
        _parse("case", la.PROBE_CASE_NUMBER),
        client=_client(session),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records[0]["docket_entries"]) == 5
    assert result.next_cursor is None
    validate_envelope(result.to_dict())


def test_case_and_tentative_records_round_trip_through_court_ingestion(
    tmp_path: Path,
) -> None:
    case_session = FakeSession(
        get_responses=[FakeResponse(CASE_SEARCH_HTML)],
        post_responses=[
            FakeResponse(CASE_SUMMARY_HTML, url=la.CASE_RESULT_URL)
        ],
    )
    case_result = la.execute(
        _parse("case", la.PROBE_CASE_NUMBER),
        client=_client(case_session),
        log_results=False,
    )
    court_db = tmp_path / "courts.db"
    case_receipt = ingest_envelope(
        case_result.to_dict(),
        court_db=court_db,
    )

    ruling_session = FakeSession(
        get_responses=[FakeResponse(TENTATIVE_INDEX_HTML)],
        post_responses=[
            FakeResponse(TENTATIVE_RESULT_HTML, url=la.TENTATIVE_RESULT_URL)
        ],
    )
    ruling_result = la.execute(
        _parse("rulings", "ALH,3,07/30/2026"),
        client=_client(ruling_session),
        log_results=False,
    )
    ruling_receipt = ingest_envelope(
        ruling_result.to_dict(),
        court_db=court_db,
    )

    assert case_receipt["projected"]["cases"] == 1
    assert case_receipt["projected"]["parties"] == 2
    assert case_receipt["projected"]["docket_entries"] == 5
    assert case_receipt["projected"]["documents"] == 2
    assert ruling_receipt["projected"]["cases"] == 3
    assert ruling_receipt["projected"]["docket_entries"] == 3


def test_case_execute_maps_no_match_to_no_results() -> None:
    session = FakeSession(
        get_responses=[FakeResponse(CASE_SEARCH_HTML)],
        post_responses=[FakeResponse(CASE_EMPTY_HTML)],
    )

    result = la.execute(
        _parse("case", "99NNCV99999"),
        client=_client(session),
        log_results=False,
    )

    assert result.status is ResultStatus.NO_RESULTS
    assert result.records == ()
    validate_envelope(result.to_dict())


def test_selections_command_lists_every_current_value_by_default() -> None:
    session = FakeSession(
        get_responses=[FakeResponse(TENTATIVE_INDEX_HTML)],
    )

    result = la.execute(
        _parse("selections"),
        client=_client(session),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert [record["native_value"] for record in result.records] == [
        "ALH,3,07/30/2026",
        "BH ,205,07/30/2026",
        "LAM,309,07/31/2026",
    ]
    assert result.next_cursor is None
    validate_envelope(result.to_dict())


def test_probe_checks_both_live_contract_shapes_in_one_envelope() -> None:
    session = FakeSession(
        get_responses=[
            FakeResponse(CASE_SEARCH_HTML),
            FakeResponse(TENTATIVE_INDEX_HTML),
        ],
        post_responses=[
            FakeResponse(CASE_SUMMARY_HTML, url=la.CASE_RESULT_URL),
            FakeResponse(TENTATIVE_RESULT_HTML, url=la.TENTATIVE_RESULT_URL),
        ],
    )

    result = la.execute(
        _parse("probe"),
        client=_client(session),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    probe = result.records[0]
    assert probe["probe_case_number"] == la.PROBE_CASE_NUMBER
    assert probe["case_summary_counts"] == {
        "future_hearings": 1,
        "parties": 2,
        "documents": 2,
        "past_proceedings": 1,
        "register_actions": 3,
    }
    assert probe["tentative_selection_count"] == 3
    assert probe["tentative_ruling_count"] == 3
    assert [name for name, _kwargs in session.calls] == [
        "get",
        "post",
        "get",
        "post",
    ]
    validate_envelope(result.to_dict())


@pytest.mark.parametrize(
    ("status_code", "expected_status", "expected_code"),
    [
        (429, ResultStatus.RATE_LIMITED, "source_rate_limited"),
        (403, ResultStatus.RESTRICTED, "source_access_restricted"),
        (500, ResultStatus.UNAVAILABLE, "source_http_error"),
    ],
)
def test_transport_statuses_remain_distinct(
    status_code: int,
    expected_status: ResultStatus,
    expected_code: str,
) -> None:
    session = FakeSession(
        get_responses=[
            FakeResponse(CASE_SEARCH_HTML, status_code=status_code)
        ],
    )
    client = la.LosAngelesCourtClient(
        session=session,
        minimum_interval=0,
        retry_policy=la.RetryPolicy(max_attempts=1),
        sleeper=lambda _delay: None,
    )

    result = la.execute(
        _parse("case", la.PROBE_CASE_NUMBER),
        client=client,
        log_results=False,
    )

    assert result.status is expected_status
    assert result.errors[0].code == expected_code
    validate_envelope(result.to_dict())
