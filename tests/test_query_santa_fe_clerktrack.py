from __future__ import annotations

import base64
import json
from argparse import Namespace
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from tools import query_santa_fe_clerktrack as clerktrack
from tools.public_records_contract import ResultStatus
from tools.public_records_http import SourceSchemaError, TransportError


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/santa_fe_clerktrack"
)


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


def args(command: str = "search", **overrides) -> Namespace:
    values = {
        "command": command,
        "name": "MAYNARD*",
        "party_role": "both",
        "from_date": None,
        "to_date": None,
        "instrument": None,
        "book": None,
        "page": None,
        "document_type": None,
        "legal": None,
        "subdivision": None,
        "lot": None,
        "block": None,
        "tract": None,
        "section": None,
        "township": None,
        "range_value": None,
        "unit": None,
        "additional_info": None,
        "limit": None,
        "cursor": None,
        "timeout": 30.0,
        "minimum_interval": 0.0,
        "retry_attempts": 1,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


class FakeResponse:
    def __init__(
        self,
        url: str,
        text: str,
        *,
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.url = url
        self.text = text
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls: list[dict] = []

    def request(self, method: str, url: str, **kwargs):
        self.calls.append(
            {"method": method, "url": url, "kwargs": kwargs}
        )
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self.responses.pop(0)


def authenticated_search_responses(
    result_fixture: str = "results_page_1.html",
) -> list[FakeResponse]:
    return [
        FakeResponse(clerktrack.LOGIN_URL, fixture("login.html")),
        FakeResponse(clerktrack.MAIN_URL, fixture("main.html")),
        FakeResponse(clerktrack.SEARCH_URL, fixture("search_form.html")),
        FakeResponse(
            clerktrack.RESULTS_URL,
            fixture(result_fixture),
        ),
    ]


@pytest.fixture(autouse=True)
def disable_search_log(monkeypatch):
    monkeypatch.setattr(
        clerktrack,
        "log_search",
        lambda *_args, **_kwargs: None,
    )


def test_login_and_search_forms_validate_published_contract():
    login = clerktrack.parse_login_form(fixture("login.html"))
    form = clerktrack.parse_search_form(fixture("search_form.html"))

    assert login.action_url == clerktrack.LOGIN_URL
    assert login.hidden_fields["__VIEWSTATE"] == "login-state"
    assert form.action_url == clerktrack.SEARCH_URL
    assert form.index_through_date == "2026-07-30"
    assert form.index_through_date_raw == (
        "Last Index Date: 7/30/2026"
    )
    assert [
        (option.value, option.label)
        for option in form.document_types
    ] == [
        ("1010", "QUITCLAIM DEED"),
        ("1020", "WARRANTY DEED"),
    ]

    with pytest.raises(SourceSchemaError, match="guest route"):
        clerktrack.parse_login_form(
            fixture("login.html").replace("INDEX", "GUEST")
        )
    with pytest.raises(SourceSchemaError, match="controls changed"):
        clerktrack.parse_search_form(
            fixture("search_form.html").replace(
                'name="txtInstr"',
                'name="changedInstrument"',
            )
        )


def test_search_payload_preserves_verified_fields_and_type_values():
    form = clerktrack.parse_search_form(fixture("search_form.html"))
    criteria = clerktrack.SearchCriteria(
        name="MAYNARD*",
        party_role="grantor",
        from_date="1998-04-01",
        to_date="1998-04-30",
        instrument="1019405",
        book="1477",
        page="604",
        document_types=("QUITCLAIM DEED", "1020"),
        legal="SEC 31",
        subdivision="TEST SUBDIVISION",
        lot="12",
        block="2",
        tract="A",
        section="31",
        township="10N",
        range_value="07E",
        unit="4",
        additional_info="PLAT BK 214 PG 9",
    )

    payload = clerktrack.search_payload(form, criteria)

    assert payload["txtName"] == "MAYNARD*"
    assert payload["rbNameType"] == "Grantor"
    assert payload["txtDateF"] == "4/1/1998"
    assert payload["txtDateT"] == "4/30/1998"
    assert payload["txtInstr"] == "1019405"
    assert payload["lstTypes"] == ["1010", "1020"]
    assert payload["txtTown"] == "10N"
    assert payload["txtRange"] == "07E"
    assert payload["btnSearch"] == "Search"
    assert (
        clerktrack.search_payload(
            form,
            clerktrack.SearchCriteria(instrument="1019405"),
        )["lstTypes"]
        == "-1"
    )
    with pytest.raises(ValueError, match="unknown ClerkTrack"):
        clerktrack.search_payload(
            form,
            clerktrack.SearchCriteria(
                document_types=("NOT A PUBLISHED TYPE",)
            ),
        )


def test_result_pages_preserve_native_paging_and_index_grain():
    first = clerktrack.parse_results_page(
        fixture("results_page_1.html"),
        expected_page=1,
    )
    second = clerktrack.parse_results_page(
        fixture("results_page_2.html"),
        expected_page=2,
    )

    assert first.total_records == 26
    assert first.page_count == 2
    assert len(first.rows) == 25
    assert first.rows[0].selector == "opaque-page1-a"
    assert first.rows[0].instrument_number == "1019405"
    assert first.rows[0].recording_date == "1998-04-08"
    assert first.rows[0].grantors_display_raw == (
        "MAYNARD, TODD S, MAYNARD, BRENDA A"
    )
    assert second.page_number == 2
    assert second.rows[0].instrument_number == "3000001"
    assert first.schema_fingerprint == second.schema_fingerprint

    changed = fixture("results_page_1.html").replace(
        "<th>Document Type</th>",
        "<th>Document Category</th>",
    )
    with pytest.raises(SourceSchemaError, match="columns changed"):
        clerktrack.parse_results_page(changed)


def test_page_completeness_and_duplicate_identity_drift_are_rejected():
    incomplete = BeautifulSoup(
        fixture("results_page_1.html"),
        "html.parser",
    )
    result_rows = incomplete.select(
        'tr[title="Click to view record detail."]'
    )
    result_rows[-1].decompose()

    with pytest.raises(SourceSchemaError, match="page is incomplete"):
        clerktrack.parse_results_page(str(incomplete))

    repeated = fixture("results_page_1.html").replace(
        ">2000004<",
        ">2000003<",
        1,
    )
    with pytest.raises(
        SourceSchemaError,
        match="repeated an instrument identity",
    ):
        clerktrack.parse_results_page(repeated)

    missing_multi_page_pager = BeautifulSoup(
        fixture("results_page_1.html"),
        "html.parser",
    )
    missing_multi_page_pager.select_one(
        "#gvItems_ctl01_ddlPaging"
    ).decompose()
    with pytest.raises(
        SourceSchemaError,
        match="page selector changed",
    ):
        clerktrack.parse_results_page(
            str(missing_multi_page_pager)
        )


def test_explicit_no_results_marker_is_distinct_from_source_failure():
    assert clerktrack.parse_no_results(fixture("no_results.html"))
    assert not clerktrack.parse_no_results(
        fixture("no_results.html").replace(
            "No records found.",
            "Search is temporarily unavailable.",
        )
    )


def test_detail_parser_separates_parties_and_legal_information():
    detail = clerktrack.parse_detail_page(fixture("detail.html"))

    assert detail.instrument_number == "1019405"
    assert detail.book == "1477"
    assert detail.page == "604"
    assert detail.recording_date == "1998-04-08"
    assert detail.recording_datetime_local == "1998-04-08T15:35:00"
    assert detail.grantors == (
        "MAYNARD, BRENDA A",
        "MAYNARD, TODD S",
    )
    assert detail.grantees == (
        "MAYNARD, ELIZABETH S",
        "MAYNARD, ROBERT G",
    )
    assert detail.legal_information == (
        "SEC: 31 RANGE: 07E TWSHP: 10N",
    )
    assert detail.descriptions == ("PLAT BK 214 PG 9",)


def test_normalized_records_never_persist_opaque_selector():
    form = clerktrack.parse_search_form(fixture("search_form.html"))
    page = clerktrack.parse_results_page(
        fixture("instrument_result.html")
    )
    listing = page.rows[0]
    detail = clerktrack.parse_detail_page(fixture("detail.html"))

    index_record = clerktrack.normalize_index_row(
        listing,
        search_form=form,
        results_schema_fingerprint=page.schema_fingerprint,
    )
    detail_record = clerktrack.normalize_detail(
        listing,
        detail,
        search_form=form,
    )
    serialized = json.dumps([index_record, detail_record])

    assert index_record["source_id"] == (
        "us-nm-santa-fe-clerktrack-index"
    )
    assert index_record["evidence_role"] == (
        "independent_county_clerk_recorded_instrument_index"
    )
    assert index_record["detail_retrieval"] == {
        "operation": "detail",
        "instrument_number": "1019405",
        "selector_policy": (
            "reacquire_by_exact_instrument_in_fresh_session"
        ),
        "opaque_selector_persisted": False,
    }
    assert detail_record["retrieval_verification"][
        "visible_identity_fields_matched"
    ]
    assert detail_record["evidence_role"] == (
        "same_clerk_instrument_detail"
    )
    assert detail_record["independent_of_assessor_observation"]
    assert not detail_record["independent_corroboration_of_index"]
    assert [party["role"] for party in detail_record["parties"]] == [
        "grantor",
        "grantor",
        "grantee",
        "grantee",
    ]
    assert "fresh-session-selector" not in serialized
    assert "opaque-page" not in serialized
    assert "param=" not in serialized


def test_client_exhausts_native_pages_when_limit_is_omitted():
    session = FakeSession(
        [
            *authenticated_search_responses(),
            FakeResponse(
                clerktrack.RESULTS_URL,
                fixture("results_page_2.html"),
            ),
        ]
    )
    client = clerktrack.ClerkTrackClient(
        session,
        minimum_interval=0,
        retry_attempts=1,
    )

    collection = client.search(
        clerktrack.SearchCriteria(name="MAYNARD*")
    )

    instruments = [
        row.instrument_number for row in collection.rows
    ]
    assert instruments[:2] == ["1019405", "1024467"]
    assert instruments[-1] == "3000001"
    assert len(instruments) == 26
    assert collection.total_records == 26
    assert collection.pages_fetched == 2
    assert collection.next_cursor is None
    assert len(session.calls) == 5
    assert session.calls[4]["kwargs"]["data"][
        "gvItems$ctl01$ddlPaging"
    ] == "2"
    assert session.calls[3]["kwargs"]["data"]["txtName"] == "MAYNARD*"


def test_caller_window_cursor_resumes_same_query_across_pages():
    criteria = clerktrack.SearchCriteria(name="MAYNARD*")
    first_session = FakeSession(authenticated_search_responses())
    first_client = clerktrack.ClerkTrackClient(
        first_session,
        minimum_interval=0,
        retry_attempts=1,
    )

    first = first_client.search(criteria, limit=1)

    assert [row.instrument_number for row in first.rows] == ["1019405"]
    assert first.next_cursor
    _, _, snapshot = clerktrack._decode_cursor(
        first.next_cursor,
        criteria_fingerprint=criteria.fingerprint,
    )
    assert snapshot
    assert snapshot.total_records == 26
    assert snapshot.page_count == 2
    assert snapshot.index_through_date == "2026-07-30"
    encoded = first.next_cursor.removeprefix(
        clerktrack.CURSOR_PREFIX
    )
    decoded = base64.urlsafe_b64decode(
        encoded + ("=" * (-len(encoded) % 4))
    ).decode()
    assert "__VIEWSTATE" not in decoded
    assert "searchsc" not in decoded
    assert "selector" not in decoded

    resume_session = FakeSession(
        [
            *authenticated_search_responses(),
            FakeResponse(
                clerktrack.RESULTS_URL,
                fixture("results_page_2.html"),
            ),
        ]
    )
    resume_client = clerktrack.ClerkTrackClient(
        resume_session,
        minimum_interval=0,
        retry_attempts=1,
    )
    resumed = resume_client.search(
        criteria,
        limit=25,
        cursor=first.next_cursor,
    )

    resumed_instruments = [
        row.instrument_number for row in resumed.rows
    ]
    assert resumed_instruments[0] == "1024467"
    assert resumed_instruments[-1] == "3000001"
    assert len(resumed_instruments) == 25
    assert resumed.next_cursor is None
    with pytest.raises(ValueError, match="does not match"):
        clerktrack._decode_cursor(
            first.next_cursor,
            criteria_fingerprint=clerktrack.SearchCriteria(
                name="OTHER*"
            ).fingerprint,
        )


def test_cursor_rejects_fresh_session_snapshot_reordering():
    criteria = clerktrack.SearchCriteria(name="MAYNARD*")
    first_client = clerktrack.ClerkTrackClient(
        FakeSession(authenticated_search_responses()),
        minimum_interval=0,
        retry_attempts=1,
    )
    initial = first_client.search(criteria, limit=1)
    assert initial.next_cursor

    changed_first_page = fixture("results_page_1.html").replace(
        ">2000025<",
        ">2000026<",
        1,
    )
    resume_responses = authenticated_search_responses()
    resume_responses[-1] = FakeResponse(
        clerktrack.RESULTS_URL,
        changed_first_page,
    )
    resume_client = clerktrack.ClerkTrackClient(
        FakeSession(resume_responses),
        minimum_interval=0,
        retry_attempts=1,
    )

    with pytest.raises(
        SourceSchemaError,
        match="continuation snapshot changed",
    ):
        resume_client.search(
            criteria,
            limit=1,
            cursor=initial.next_cursor,
        )


def test_paging_requires_forward_instrument_progress():
    stalled_second_page = fixture("results_page_2.html").replace(
        ">3000001<",
        ">1000000<",
        1,
    )
    session = FakeSession(
        [
            *authenticated_search_responses(),
            FakeResponse(
                clerktrack.RESULTS_URL,
                stalled_second_page,
            ),
        ]
    )
    client = clerktrack.ClerkTrackClient(
        session,
        minimum_interval=0,
        retry_attempts=1,
    )

    with pytest.raises(SourceSchemaError, match="no forward progress"):
        client.search(clerktrack.SearchCriteria(name="MAYNARD*"))


def test_detail_reacquires_selector_then_verifies_visible_identity():
    session = FakeSession(
        [
            *authenticated_search_responses("instrument_result.html"),
            FakeResponse(
                f"{clerktrack.DETAIL_URL}?param=fresh-session-selector",
                fixture("detail.html"),
            ),
        ]
    )
    client = clerktrack.ClerkTrackClient(
        session,
        minimum_interval=0,
        retry_attempts=1,
    )

    listing, detail, form = client.detail("1019405")

    assert listing.instrument_number == detail.instrument_number
    assert detail.document_type == "QUITCLAIM DEED"
    assert form.index_through_date == "2026-07-30"
    assert session.calls[3]["kwargs"]["data"]["txtInstr"] == "1019405"
    assert session.calls[4]["kwargs"]["params"] == {
        "param": "fresh-session-selector"
    }


def test_detail_identity_mismatch_is_a_source_schema_failure():
    changed_detail = fixture("detail.html").replace(
        "<td>1477</td>",
        "<td>9999</td>",
        1,
    )
    session = FakeSession(
        [
            *authenticated_search_responses("instrument_result.html"),
            FakeResponse(clerktrack.DETAIL_URL, changed_detail),
        ]
    )
    client = clerktrack.ClerkTrackClient(
        session,
        minimum_interval=0,
        retry_attempts=1,
    )

    with pytest.raises(SourceSchemaError, match="did not match"):
        client.detail("1019405")


def test_missing_probe_sentinel_is_source_change_not_no_results():
    class MissingProbeClient:
        def detail(self, _instrument):
            raise LookupError(clerktrack.PROBE_INSTRUMENT)

    result = clerktrack.execute_detail(
        args(
            command="probe",
            instrument=clerktrack.PROBE_INSTRUMENT,
            name=None,
        ),
        client=MissingProbeClient(),
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.records == ()
    assert result.errors[0].code == "source_schema_changed"
    assert "sentinel is missing" in result.errors[0].message


def test_execute_preserves_partial_and_no_results_status():
    partial_session = FakeSession(authenticated_search_responses())
    partial_client = clerktrack.ClerkTrackClient(
        partial_session,
        minimum_interval=0,
        retry_attempts=1,
    )

    partial = clerktrack.execute_search(
        args(limit=1),
        client=partial_client,
    )

    assert partial.status == ResultStatus.PARTIAL
    assert len(partial.records) == 1
    assert partial.next_cursor
    assert partial.query.query.requested_limit == 1

    empty_responses = authenticated_search_responses()
    empty_responses[-1] = FakeResponse(
        clerktrack.SEARCH_URL,
        fixture("no_results.html"),
    )
    empty_session = FakeSession(empty_responses)
    empty_client = clerktrack.ClerkTrackClient(
        empty_session,
        minimum_interval=0,
        retry_attempts=1,
    )
    empty = clerktrack.execute_search(
        args(instrument="999999999", name=None),
        client=empty_client,
    )

    assert empty.status == ResultStatus.NO_RESULTS
    assert empty.records == ()


def test_transport_failure_is_not_an_authoritative_empty_result():
    class FailingClient:
        def search(self, *_args, **_kwargs):
            raise TransportError(
                "offline",
                url=clerktrack.SEARCH_URL,
            )

    result = clerktrack.execute_search(
        args(),
        client=FailingClient(),
    )

    assert result.status == ResultStatus.UNAVAILABLE
    assert result.records == ()
    assert result.errors[0].code == "transport_error"


def test_search_log_failure_does_not_replace_source_result(
    monkeypatch,
    capsys,
):
    class CollectionClient:
        def search(self, *_args, **_kwargs):
            form = clerktrack.parse_search_form(
                fixture("search_form.html")
            )
            page = clerktrack.parse_results_page(
                fixture("instrument_result.html")
            )
            return clerktrack.SearchCollection(
                rows=page.rows,
                total_records=1,
                pages_fetched=1,
                next_cursor=None,
                search_form=form,
                results_schema_fingerprint=page.schema_fingerprint,
            )

    def fail_log(*_args, **_kwargs):
        raise RuntimeError("tracker unavailable")

    monkeypatch.setattr(clerktrack, "log_search", fail_log)

    result = clerktrack.execute_search(
        args(instrument="1019405", name=None),
        client=CollectionClient(),
    )

    assert result.status == ResultStatus.OK
    assert len(result.records) == 1
    assert "search log was not updated" in capsys.readouterr().err


def test_route_map_classifies_same_artifact_and_independent_sources():
    routes = {
        route["route_id"]: route
        for route in clerktrack.route_map()["routes"]
    }

    assert clerktrack.SOURCE_ID == "us-nm-santa-fe-clerktrack-index"
    assert routes[clerktrack.SOURCE_ID]["independent_evidence"]
    assert not routes[
        "us-nm-santa-fe-clerktrack-detail"
    ]["independent_evidence"]
    assert not routes[
        "us-nm-santa-fe-clerktrack-public-images"
    ]["independent_evidence"]
    assert routes[
        "us-nm-santa-fe-assessor-accounts"
    ]["relationship_to_primary"] == "field_matched_assessor_join_hints"


def test_parser_has_no_implicit_result_limit():
    parsed = clerktrack.build_parser().parse_args(
        ["search", "--name", "MAYNARD*"]
    )

    assert parsed.limit is None
