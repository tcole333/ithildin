from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pytest
import requests

from tools import ingest_state_court_records
from tools import query_oregon_court_calendar as oregon_calendar
from tools.public_records_http import SourceSchemaError


FIXTURES = (
    Path(__file__).parent / "fixtures" / "public_records" / "oregon_court_calendar"
)


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


@dataclass
class FixtureResponse:
    text: str
    status_code: int = 200
    headers: dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "text/html; charset=utf-8"}
    )


class QueueSession:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def _next(self, method: str, url: str, **kwargs: Any) -> FixtureResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected Oregon calendar request: {url}")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def get(self, url: str, **kwargs: Any) -> FixtureResponse:
        return self._next("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> FixtureResponse:
        return self._next("POST", url, **kwargs)

    def close(self) -> None:
        self.closed = True


def _client(
    *responses: Any,
) -> tuple[
    oregon_calendar.OregonCourtCalendarClient,
    QueueSession,
]:
    session = QueueSession(list(responses))
    return (
        oregon_calendar.OregonCourtCalendarClient(
            session=session,
            timeout=5,
        ),
        session,
    )


def _parse(*values: str):
    return oregon_calendar.build_parser().parse_args(list(values))


def _search_args(*extra: str):
    return _parse(
        "search",
        "--location",
        "Deschutes",
        "--after",
        "2026-07-29",
        "--before",
        "2026-07-30",
        *extra,
    )


def _parsed_source_pages():
    landing = oregon_calendar.parse_landing_html(_fixture("landing.html"))
    location = oregon_calendar._resolve_location(landing, "Deschutes")
    form = oregon_calendar.parse_search_form_html(
        _fixture("search_form.html"),
        location=location,
    )
    results = oregon_calendar.parse_results_html(_fixture("results.html"))
    return landing, location, form, results


@pytest.fixture(autouse=True)
def _stable_source_today(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    if request.node.name != "test_live_official_calendar_probe":
        monkeypatch.setattr(
            oregon_calendar,
            "_oregon_today",
            lambda: oregon_calendar.date(2026, 7, 29),
        )


def test_landing_preserves_component_identity_locations_and_alternatives():
    landing = oregon_calendar.parse_landing_html(_fixture("landing.html"))

    assert [location.name for location in landing.locations] == [
        "All Locations",
        "Deschutes",
        "Multnomah",
        "Tax Court",
    ]
    assert landing.locations[2].node_ids == ("104100", "104210")
    assert landing.locations[3].court_id == "or-tax-court"
    assert landing.locations[1].county_geoid == "41017"
    assert landing.appellate_links == {
        "court_of_appeals_calendar": ("https://web.courts.oregon.gov/coadocket"),
        "supreme_court_calendar": ("https://web.courts.oregon.gov/sclist"),
    }
    assert "Violence Against Women Act" in landing.restriction_notice
    assert {
        route["source_id"] for route in oregon_calendar.COMPLEMENTARY_OFFICIAL_ROUTES
    } >= {
        "us-or-appellate-record-search",
        "us-or-ojd-free-circuit-tax-record-search",
        "us-or-ojcin",
        "us-or-ojd-case-record-request",
        "us-or-ojd-statewide-data-request",
    }


def test_form_preserves_asp_session_search_modes_officers_and_90_day_fact():
    _, location, form, _ = _parsed_source_pages()

    assert form.location == location
    assert form.hidden_fields["__VIEWSTATE"] == "fixture-viewstate"
    assert form.hidden_fields["NodeID"] == "111100"
    assert form.search_modes == oregon_calendar.EXPECTED_SEARCH_MODES
    assert [officer.native_id for officer in form.judicial_officers] == [
        "1001",
        "1002",
    ]
    assert form.maximum_date_window_days == 90
    assert form.forward_only
    assert len(form.schema_fingerprint) == 64


def test_results_preserve_all_verified_fields_and_authoritative_empty():
    results = oregon_calendar.parse_results_html(_fixture("results.html"))
    empty = oregon_calendar.parse_results_html(_fixture("empty_results.html"))

    assert results.reported_count == 3
    assert len(results.rows) == 3
    first = results.rows[0]
    assert first.case_number == "26CR10001"
    assert first.case_type == "Offense Felony"
    assert first.caption == "State of Oregon\nAlex Example"
    assert first.judge == "Flint, Bethany"
    assert first.physical_location == "Courtroom 2D"
    assert first.hearing_date == "07/29/2026"
    assert first.hearing_time == "8:30 AM"
    assert first.hearing_type == "Hearing - Plea"
    assert first.status_icons == ("Active Warrant",)
    assert empty.reported_count == 0
    assert empty.rows == ()


def test_result_count_drift_is_source_changed_not_empty():
    malformed = _fixture("results.html").replace(
        "<tr><td>3</td></tr>",
        "<tr><td>4</td></tr>",
    )

    with pytest.raises(SourceSchemaError) as caught:
        oregon_calendar.parse_results_html(malformed)

    assert caught.value.details == {
        "reported_count": 4,
        "parsed_rows": 3,
    }


@pytest.mark.parametrize(
    ("calendar_request", "expected"),
    [
        (
            oregon_calendar.OregonCalendarRequest(
                mode="case",
                date_after=oregon_calendar.date(2026, 7, 29),
                date_before=oregon_calendar.date(2026, 7, 29),
                categories=("criminal",),
                case_number="26CR10001",
            ),
            {
                "SearchBy": "0",
                "SearchType": "CASE",
                "SearchMode": "CASENUMBER",
                "CourtCaseSearchValue": "26CR10001",
            },
        ),
        (
            oregon_calendar.OregonCalendarRequest(
                mode="party",
                date_after=oregon_calendar.date(2026, 7, 29),
                date_before=oregon_calendar.date(2026, 7, 29),
                categories=("civil", "family"),
                party_first_name="Alex",
                party_last_name="Example",
                party_middle_name="Q",
                exact_name=True,
                soundex=False,
            ),
            {
                "SearchBy": "1",
                "SearchType": "PARTY",
                "SearchMode": "NAME",
                "NameTypeKy": "ALIAS",
                "BaseConnKy": "DF",
                "FirstName": "Alex",
                "LastName": "Example",
                "MiddleName": "Q",
                "ExactName": "on",
            },
        ),
        (
            oregon_calendar.OregonCalendarRequest(
                mode="business",
                date_after=oregon_calendar.date(2026, 7, 29),
                date_before=oregon_calendar.date(2026, 7, 29),
                categories=("civil",),
                business_name="Example LLC",
            ),
            {
                "SearchBy": "1",
                "SearchType": "PARTY",
                "SearchMode": "BUSINESSNAME",
                "NameTypeKy": "DBA",
                "LastName": "Example LLC",
            },
        ),
        (
            oregon_calendar.OregonCalendarRequest(
                mode="attorney",
                date_after=oregon_calendar.date(2026, 7, 29),
                date_before=oregon_calendar.date(2026, 7, 29),
                categories=("criminal",),
                attorney_first_name="Avery",
                attorney_last_name="Lawyer",
            ),
            {
                "SearchBy": "2",
                "SearchType": "PARTY",
                "SearchMode": "NAME",
                "BaseConnKy": "AT",
                "FirstName": "Avery",
                "LastName": "Lawyer",
            },
        ),
        (
            oregon_calendar.OregonCalendarRequest(
                mode="attorney_bar",
                date_after=oregon_calendar.date(2026, 7, 29),
                date_before=oregon_calendar.date(2026, 7, 29),
                categories=("criminal",),
                attorney_bar_number="123456",
            ),
            {
                "SearchBy": "2",
                "SearchType": "PARTY",
                "SearchMode": "BARNUMBER",
                "BaseConnKy": "AT",
                "LastName": "123456",
            },
        ),
        (
            oregon_calendar.OregonCalendarRequest(
                mode="judicial_officer",
                date_after=oregon_calendar.date(2026, 7, 29),
                date_before=oregon_calendar.date(2026, 7, 29),
                categories=("criminal", "civil"),
                judicial_officer="Flint, Bethany",
            ),
            {
                "SearchBy": "3",
                "SearchType": "JUDOFFC",
                "SearchMode": "JUDOFFC",
                "cboJudOffc": "1001",
            },
        ),
        (
            oregon_calendar.OregonCalendarRequest(
                mode="date_range",
                date_after=oregon_calendar.date(2026, 7, 29),
                date_before=oregon_calendar.date(2026, 7, 30),
                categories=tuple(oregon_calendar.CATEGORY_CODES),
            ),
            {
                "SearchBy": "5",
                "SearchType": "DATERANGE",
                "SearchMode": "DATERANGE",
                "CaseCategories": "CR,CV,FAM,PR",
            },
        ),
    ],
)
def test_all_verified_source_selectors_build_native_payloads(
    calendar_request: oregon_calendar.OregonCalendarRequest,
    expected: dict[str, str],
):
    _, _, form, _ = _parsed_source_pages()

    payload = oregon_calendar._build_search_payload(
        form,
        calendar_request,
    )

    assert payload["__VIEWSTATE"] == "fixture-viewstate"
    assert payload["DateSettingOnAfter"] == "07/29/2026"
    for key, value in expected.items():
        assert payload[key] == value


def test_same_session_search_normalizes_stable_ingestible_case_records(
    tmp_path: Path,
):
    client, session = _client(
        FixtureResponse(_fixture("landing.html")),
        FixtureResponse(_fixture("search_form.html")),
        FixtureResponse(_fixture("results.html")),
    )

    result = oregon_calendar.execute(
        _search_args(),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 2
    assert [call["method"] for call in session.calls] == [
        "GET",
        "POST",
        "POST",
    ]
    assert session.calls[1]["data"] == {
        "NodeID": "111100",
        "NodeDesc": "Deschutes",
    }
    submitted = session.calls[2]["data"]
    assert submitted["SearchType"] == "DATERANGE"
    assert submitted["DateSettingOnAfter"] == "07/29/2026"
    assert submitted["DateSettingOnBefore"] == "07/30/2026"

    case = result.records[0]
    assert case["source_id"] == oregon_calendar.SOURCE_ID
    assert case["record_kind"] == "case"
    assert case["court"]["native_court_id"] == "111100"
    assert case["court"]["county_geoid"] == "41017"
    assert case["raw_case_number"] == "26CR10001"
    assert case["source_internal_id"] is None
    assert len(case["docket_entries"]) == 2
    assert all(
        entry["native_entry_id"].startswith("calendar-hearing:")
        for entry in case["docket_entries"]
    )
    assert len({entry["native_entry_id"] for entry in case["docket_entries"]}) == 2
    assert case["docket_entries"][0]["status"] == "Active Warrant"
    assert len(case["schema_fingerprint"]) == 64
    envelope = result.to_dict()
    ingest_state_court_records.validate_envelope(envelope)
    report = ingest_state_court_records.ingest_envelope(
        envelope,
        court_db=tmp_path / "oregon-calendar.db",
    )
    assert report["projected"]["cases"] == 2
    assert report["projected"]["docket_entries"] == 3


def test_hearing_identity_uses_manifest_stable_keys_not_volatile_assignment():
    _, location, _, results = _parsed_source_pages()
    row = results.rows[0]
    original = oregon_calendar._hearing_entry(row, location=location)
    reassigned = oregon_calendar._hearing_entry(
        replace(
            row,
            judge="Another, Judge",
            physical_location="Courtroom 9Z",
            status_icons=(),
        ),
        location=location,
    )
    rescheduled = oregon_calendar._hearing_entry(
        replace(row, hearing_time="9:00 AM"),
        location=location,
    )

    assert original["native_entry_id"] == reassigned["native_entry_id"]
    assert original["native_entry_id"] != rescheduled["native_entry_id"]
    assert set(original["identity_basis"]) == {
        "court_location",
        "case_number",
        "event_date",
        "event_time",
        "hearing_type",
    }


def test_empty_source_page_becomes_authoritative_no_results():
    client, _ = _client(
        FixtureResponse(_fixture("landing.html")),
        FixtureResponse(_fixture("search_form.html")),
        FixtureResponse(_fixture("empty_results.html")),
    )

    result = oregon_calendar.execute(
        _search_args("--case-number", "ZZZZ999999999"),
        client=client,
        log_results=False,
    )

    assert result.status.value == "no_results"
    assert result.records == ()
    assert result.errors == ()


def test_cursor_is_query_and_snapshot_bound_and_resumes_without_overlap():
    client_one, _ = _client(
        FixtureResponse(_fixture("landing.html")),
        FixtureResponse(_fixture("search_form.html")),
        FixtureResponse(_fixture("results.html")),
    )
    first = oregon_calendar.execute(
        _search_args("--limit", "1"),
        client=client_one,
        log_results=False,
    )
    assert first.status.value == "ok"
    assert len(first.records) == 1
    assert first.next_cursor

    client_two, _ = _client(
        FixtureResponse(_fixture("landing.html")),
        FixtureResponse(_fixture("search_form.html")),
        FixtureResponse(_fixture("results.html")),
    )
    second = oregon_calendar.execute(
        _search_args("--limit", "1", "--cursor", first.next_cursor),
        client=client_two,
        log_results=False,
    )

    assert second.status.value == "ok"
    assert len(second.records) == 1
    assert second.records[0]["canonical_ref"] != (first.records[0]["canonical_ref"])
    assert second.next_cursor is None

    changed_html = _fixture("results.html").replace(
        "Hearing - Modification",
        "Hearing - Status",
    )
    client_changed, _ = _client(
        FixtureResponse(_fixture("landing.html")),
        FixtureResponse(_fixture("search_form.html")),
        FixtureResponse(changed_html),
    )
    stale = oregon_calendar.execute(
        _search_args("--limit", "1", "--cursor", first.next_cursor),
        client=client_changed,
        log_results=False,
    )
    assert stale.status.value == "source_changed"
    assert stale.errors[0].code == "cursor_snapshot_changed"


class StaticSearchClient:
    def __init__(self, batch: oregon_calendar.OregonCalendarBatch) -> None:
        self.batch = batch
        self.calls = 0

    def search(self, **_kwargs: Any) -> oregon_calendar.OregonCalendarBatch:
        self.calls += 1
        return self.batch


def test_documented_400_ceiling_is_partial_but_live_excess_is_preserved():
    assert (
        oregon_calendar.SOURCE_METADATA.metadata["documented_result_ceiling"]
        == 400
    )
    assert (
        oregon_calendar.SOURCE_METADATA.metadata[
            "live_observed_returned_rows"
        ]
        == 550
    )
    assert "native_result_ceiling" not in (
        oregon_calendar.SOURCE_METADATA.metadata
    )

    _, location, form, results = _parsed_source_pages()
    exact_ceiling = oregon_calendar.OregonCalendarResults(
        location_name=results.location_name,
        rows=results.rows,
        reported_count=400,
        request_parameters=results.request_parameters,
        schema_fingerprint=results.schema_fingerprint,
    )
    batch = oregon_calendar.OregonCalendarBatch(
        location=location,
        form=form,
        payload={},
        results=exact_ceiling,
    )
    partial = oregon_calendar.execute(
        _search_args(),
        client=StaticSearchClient(batch),
        log_results=False,
    )
    assert partial.status.value == "partial"
    assert partial.errors[0].code == ("documented_source_result_ceiling_reached")
    assert partial.errors[0].details["partition_hints"]
    assert len(partial.records) == 2

    above_ceiling = oregon_calendar.OregonCalendarResults(
        location_name=results.location_name,
        rows=results.rows,
        reported_count=550,
        request_parameters=results.request_parameters,
        schema_fingerprint=results.schema_fingerprint,
    )
    preserved = oregon_calendar.execute(
        _search_args(),
        client=StaticSearchClient(
            oregon_calendar.OregonCalendarBatch(
                location=location,
                form=form,
                payload={},
                results=above_ceiling,
            )
        ),
        log_results=False,
    )
    assert preserved.status.value == "ok"
    assert any("returned 550 rows" in value for value in preserved.warnings)
    assert preserved.records[0]["source_scope"][
        "live_response_exceeded_documented_ceiling"
    ]

    explicit_truncation = oregon_calendar.OregonCalendarResults(
        location_name=results.location_name,
        rows=results.rows,
        reported_count=550,
        request_parameters=results.request_parameters,
        schema_fingerprint=results.schema_fingerprint,
        alerts=(
            "The search resulted in too many matches to display. "
            "Narrow the search by entering more precise criteria.",
        ),
    )
    truncated = oregon_calendar.execute(
        _search_args(),
        client=StaticSearchClient(
            oregon_calendar.OregonCalendarBatch(
                location=location,
                form=form,
                payload={},
                results=explicit_truncation,
            )
        ),
        log_results=False,
    )
    assert truncated.status.value == "partial"
    assert truncated.errors[0].code == "source_result_truncation_detected"
    assert truncated.errors[0].details["explicit_source_truncation"]
    assert truncated.records[0]["source_scope"]["native_truncation_detected"]


class ExplodingClient:
    def __getattr__(self, name: str):
        raise AssertionError(f"source client must not be used: {name}")


def test_source_date_window_and_access_decision_fail_before_transport():
    invalid_limit = oregon_calendar.execute(
        _search_args("--limit", "0"),
        client=ExplodingClient(),
        log_results=False,
    )
    assert invalid_limit.status.value == "unavailable"
    assert invalid_limit.errors[0].code == "invalid_limit"

    too_wide = oregon_calendar.execute(
        _parse(
            "search",
            "--location",
            "Deschutes",
            "--after",
            "2026-01-01",
            "--before",
            "2026-04-02",
        ),
        client=ExplodingClient(),
        log_results=False,
    )
    assert too_wide.status.value == "unavailable"
    assert too_wide.errors[0].code == "date_range_exceeds_source_window"
    assert too_wide.errors[0].details["source_maximum_days"] == 90

    mismatch = oregon_calendar.execute(
        _parse("locations"),
        access_decision={
            "source_id": "another-source",
            "allowed": True,
        },
        client=ExplodingClient(),
        log_results=False,
    )
    assert mismatch.status.value == "unavailable"
    assert mismatch.errors[0].code == "catalog_decision_source_mismatch"

    denied = oregon_calendar.execute(
        _parse("locations"),
        access_decision={
            "source_id": oregon_calendar.SOURCE_ID,
            "allowed": False,
            "automation_disposition": "human_required",
            "reason_code": "reviewed_route_requires_handoff",
            "reason": "fixture access decision",
        },
        client=ExplodingClient(),
        log_results=False,
    )
    assert denied.status.value == "human_required"
    assert denied.errors[0].code == "reviewed_route_requires_handoff"


def test_forward_window_matches_source_javascript_boundaries():
    allowed = oregon_calendar._search_request(
        _parse(
            "search",
            "--after",
            "2026-07-29",
            "--before",
            "2026-10-26",
        )
    )
    assert (allowed.date_before - allowed.date_after).days + 1 == 90

    past = oregon_calendar.execute(
        _parse(
            "search",
            "--after",
            "2026-07-28",
            "--before",
            "2026-07-29",
        ),
        client=ExplodingClient(),
        log_results=False,
    )
    assert past.status.value == "unavailable"
    assert past.errors[0].code == "date_range_precedes_source_window"

    too_far_forward = oregon_calendar.execute(
        _parse(
            "search",
            "--after",
            "2026-10-27",
            "--before",
            "2026-10-27",
        ),
        client=ExplodingClient(),
        log_results=False,
    )
    assert too_far_forward.status.value == "unavailable"
    assert too_far_forward.errors[0].code == ("date_range_exceeds_forward_window")
    assert too_far_forward.errors[0].details["maximum_end_date"] == ("2026-10-26")


def test_locations_officers_probe_and_output_are_transport_injectable():
    locations_client, _ = _client(FixtureResponse(_fixture("landing.html")))
    locations = oregon_calendar.execute(
        _parse("locations"),
        client=locations_client,
        log_results=False,
    )
    assert locations.status.value == "ok"
    assert len(locations.records) == 4

    officers_client, _ = _client(
        FixtureResponse(_fixture("landing.html")),
        FixtureResponse(_fixture("search_form.html")),
    )
    officers = oregon_calendar.execute(
        _parse(
            "judicial-officers",
            "--location",
            "Deschutes",
            "--limit",
            "1",
        ),
        client=officers_client,
        log_results=False,
    )
    assert officers.status.value == "ok"
    assert len(officers.records) == 1
    assert officers.next_cursor

    class ProbeClient:
        def probe(self, **_kwargs: Any):
            landing, location, form, results = _parsed_source_pages()
            return (
                landing,
                oregon_calendar.OregonCalendarBatch(
                    location=location,
                    form=form,
                    payload={},
                    results=results,
                ),
            )

    probe = oregon_calendar.execute(
        _parse("probe", "--location", "Deschutes"),
        client=ProbeClient(),
        log_results=False,
    )
    assert probe.status.value == "ok"
    assert probe.records[0]["checks"]["maximum_date_window_days"] == 90

    class TruncatedProbeClient:
        def probe(self, **_kwargs: Any):
            landing, location, form, results = _parsed_source_pages()
            results = replace(
                results,
                reported_count=550,
                alerts=("Too many matches to display.",),
            )
            return (
                landing,
                oregon_calendar.OregonCalendarBatch(
                    location=location,
                    form=form,
                    payload={},
                    results=results,
                ),
            )

    truncated_probe = oregon_calendar.execute(
        _parse("probe", "--location", "Deschutes"),
        client=TruncatedProbeClient(),
        log_results=False,
    )
    assert truncated_probe.status.value == "partial"
    assert truncated_probe.errors[0].code == (
        "source_result_truncation_detected"
    )
    assert truncated_probe.records[0]["checks"][
        "native_truncation_detected"
    ] is True

    captured: dict[str, Any] = {}

    def output_writer(payload, args, summary=None):
        captured.update({"payload": payload, "args": args, "summary": summary})
        return True

    oregon_calendar._emit(
        locations,
        _parse("locations"),
        output_writer=output_writer,
    )
    assert captured["payload"]["status"] == "ok"
    assert "Oregon court calendar locations" in captured["summary"]


def test_transport_failure_and_search_log_failure_do_not_masquerade_as_empty(
    monkeypatch: pytest.MonkeyPatch,
):
    client, _ = _client(requests.ConnectionError("fixture offline"))
    failed = oregon_calendar.execute(
        _parse("locations"),
        client=client,
        log_results=False,
    )
    assert failed.status.value == "unavailable"
    assert failed.errors[0].code == "transport_error"

    monkeypatch.setattr(
        oregon_calendar,
        "log_search",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("fixture tracker unavailable")
        ),
    )
    working_client, _ = _client(FixtureResponse(_fixture("landing.html")))
    working = oregon_calendar.execute(
        _parse("locations"),
        client=working_client,
        log_results=True,
    )
    assert working.status.value == "ok"


@pytest.mark.skipif(
    os.environ.get("OREGON_COURT_CALENDAR_LIVE") != "1",
    reason="set OREGON_COURT_CALENDAR_LIVE=1 for official live probe",
)
def test_live_official_calendar_probe():
    result = oregon_calendar.execute(
        _parse("probe", "--location", "Deschutes", "--timeout", "60"),
        access_decision={
            "source_id": oregon_calendar.SOURCE_ID,
            "allowed": True,
            "access_class": "B",
            "automation_disposition": "allowed_with_limits",
        },
        log_results=False,
    )

    assert result.status.value == "ok"
    assert result.records[0]["checks"]["anonymous_cookie_handshake"]
    assert result.records[0]["checks"]["result_table"]
