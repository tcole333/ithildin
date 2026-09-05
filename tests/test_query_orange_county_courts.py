from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tools import query_orange_county_courts
from tools.ingest_state_court_records import ingest_envelope, validate_envelope
from tools.public_records_contract import ResultStatus
from tools.public_records_http import (
    RateLimitedHTTPError,
    SourceSchemaError,
)


FIXTURE_DIR = Path("tests/fixtures/public_records/orange_county_courts")
SUCCESS_HTML = (FIXTURE_DIR / "search_success.html").read_text(encoding="utf-8")
EMPTY_HTML = (FIXTURE_DIR / "search_empty.html").read_text(encoding="utf-8")
INVALID_HTML = (FIXTURE_DIR / "search_invalid.html").read_text(encoding="utf-8")
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
    def __init__(self, get_html: str, post_html: str) -> None:
        self.get_html = get_html
        self.post_html = post_html
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("get", {"url": url, **kwargs}))
        return FakeResponse(self.get_html)

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("post", {"url": url, **kwargs}))
        return FakeResponse(self.post_html)


class FakeOrangeClient:
    def __init__(
        self,
        *,
        page: query_orange_county_courts.OrangeCalendarPage | None = None,
        error: Exception | None = None,
    ) -> None:
        parsed = page or query_orange_county_courts.parse_calendar_html(
            SUCCESS_HTML
        )
        self.page = replace(
            parsed,
            request_parameters={
                "hearDate": "",
                "caseNumber": "2020-CT-001540-A-O",
                "firstName": "",
                "lastName": "",
                "judge": "",
            },
        )
        self.error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def search(self, **kwargs: Any):
        self.calls.append(("search", dict(kwargs)))
        if self.error is not None:
            raise self.error
        return self.page

    def probe(self):
        self.calls.append(("probe", {}))
        if self.error is not None:
            raise self.error
        return replace(
            self.page,
            request_parameters={
                "hearDate": "2026-07-28",
                "caseNumber": "",
                "firstName": "",
                "lastName": "",
                "judge": "",
            },
        )


def _parse(*values: str):
    return query_orange_county_courts.build_parser().parse_args(list(values))


def _execute(args, monkeypatch, *, client=None, decision=ALLOWED):
    monkeypatch.setattr(
        query_orange_county_courts,
        "log_search",
        lambda *_args: None,
    )
    return query_orange_county_courts.execute(
        args,
        access_decision=decision,
        client=client or FakeOrangeClient(),
    )


def test_parser_exposes_source_form_rows_and_authoritative_total():
    page = query_orange_county_courts.parse_calendar_html(SUCCESS_HTML)

    assert page.request_verification_token == "fixture-token-success"
    assert page.form_action == "/Court/Index"
    assert page.form_method == "post"
    assert page.columns == query_orange_county_courts.EXPECTED_COLUMNS
    assert page.total_count == 2
    assert len(page.rows) == 2
    assert page.rows[0].case_number == "2020-CT-001540-A-O"
    assert page.rows[0].status == "Cancelled"
    assert page.rows[1].status is None


def test_parser_preserves_an_observed_blank_location_as_null():
    html = SUCCESS_HTML.replace(
        "<td>Room 4-c On The 4th Floor</td>",
        "<td></td>",
    )

    page = query_orange_county_courts.parse_calendar_html(html)

    assert page.rows[0].location is None
    entry = query_orange_county_courts.normalize_cases(page)[0][
        "docket_entries"
    ][0]
    assert entry["location"] is None
    assert entry["identity_basis"]["location"] == ""


def test_parser_accepts_default_page_total_label_order():
    html = SUCCESS_HTML.replace(
        "2 Total Hearings for case 2020-CT-001540-A-O",
        "Total Hearings: 2",
    )

    page = query_orange_county_courts.parse_calendar_html(html)

    assert page.total_count == 2


def test_parser_accepts_singular_exact_case_count():
    html = (
        SUCCESS_HTML.replace(
            "2 Total Hearings for case 2020-CT-001540-A-O",
            "1 Hearing for case 2020-CT-001540-A-O",
        )
        .replace(
            """            <tr>
              <td>2020-CT-001540-A-O</td>
              <td>08/20/2026</td>
              <td>1:30 PM</td>
              <td>Video/audio/tele Conference</td>
              <td>State Of Florida Vs. Douglas, Justin Andrew</td>
              <td>Bova, Amanda S</td>
              <td></td>
            </tr>
""",
            "",
        )
    )

    page = query_orange_county_courts.parse_calendar_html(html)

    assert page.total_count == 1
    assert len(page.rows) == 1


def test_result_count_ignores_hearing_text_in_judge_options():
    html = SUCCESS_HTML.replace(
        '<select id="judge" name="judge"><option value=""></option></select>',
        (
            '<select id="judge" name="judge">'
            '<option value="Officer, 95 Hearing">Officer, 95 Hearing</option>'
            "</select>"
        ),
    )

    page = query_orange_county_courts.parse_calendar_html(html)

    assert page.total_count == 2


def test_client_preserves_session_and_posts_exact_official_fields():
    session = FakeSession(SUCCESS_HTML, SUCCESS_HTML)
    client = query_orange_county_courts.OrangeCountyCourtsClient(
        session=session,
        timeout=7,
    )

    page = client.search(
        case_number="2020-CT-001540-A-O",
        judge="Bova, Amanda S",
    )

    assert page.total_count == 2
    assert [name for name, _kwargs in session.calls] == ["get", "post"]
    post = session.calls[1][1]
    assert post["url"] == query_orange_county_courts.CALENDAR_URL
    assert post["timeout"] == 7
    assert post["data"] == {
        "__RequestVerificationToken": "fixture-token-success",
        "hearDate": "",
        "caseNumber": "2020-CT-001540-A-O",
        "firstName": "",
        "lastName": "",
        "judge": "Bova, Amanda S",
    }
    assert page.request_parameters == {
        "hearDate": "",
        "caseNumber": "2020-CT-001540-A-O",
        "firstName": "",
        "lastName": "",
        "judge": "Bova, Amanda S",
    }


def test_search_groups_one_case_with_stable_distinct_hearing_identities(
    monkeypatch,
):
    result = _execute(
        _parse(
            "search",
            "--case-number",
            "2020-CT-001540-A-O",
            "--limit",
            "137",
        ),
        monkeypatch,
    )
    payload = result.to_dict()
    validate_envelope(payload)

    assert payload["status"] == "ok"
    assert len(payload["records"]) == 1
    record = payload["records"][0]
    assert record["raw_case_number"] == "2020-CT-001540-A-O"
    assert record["source_internal_id"] is None
    assert record["filing_date"] is None
    assert record["parties"] == []
    assert record["source_scope"]["past_hearings_available"] is False
    assert record["source_scope"]["case_detail_link_available"] is False
    assert len(record["docket_entries"]) == 2
    first, second = record["docket_entries"]
    assert first["native_entry_id"] != second["native_entry_id"]
    assert first["event_date"] == "2026-07-28"
    assert first["event_time"] == "07:30:00"
    assert first["status"] == "Cancelled"
    assert first["native_status"] == "Cancelled"
    assert first["filed_date"] is None
    assert second["event_date"] == "2026-08-20"
    assert second["status"] is None
    assert "fixture-token" not in str(payload)

    repeated = _execute(
        _parse(
            "search",
            "--case-number",
            "2020-CT-001540-A-O",
        ),
        monkeypatch,
    ).to_dict()
    assert (
        repeated["records"][0]["docket_entries"][0]["native_entry_id"]
        == first["native_entry_id"]
    )


def test_normalized_envelope_ingests_one_case_and_two_docket_entries(
    tmp_path,
    monkeypatch,
):
    result = _execute(
        _parse(
            "search",
            "--case-number",
            "2020-CT-001540-A-O",
        ),
        monkeypatch,
    )

    ingested = ingest_envelope(
        result.to_dict(),
        court_db=tmp_path / "courts.db",
    )

    assert ingested["status"] == "ingested"
    assert ingested["projected"]["cases"] == 1
    assert ingested["projected"]["docket_entries"] == 2
    assert ingested["projected"]["parties"] == 0
    assert ingested["projected"]["documents"] == 0


def test_valid_zero_row_table_is_no_results(monkeypatch):
    empty_page = query_orange_county_courts.parse_calendar_html(EMPTY_HTML)

    result = _execute(
        _parse(
            "search",
            "--case-number",
            "2099-CF-999999-A-O",
        ),
        monkeypatch,
        client=FakeOrangeClient(page=empty_page),
    )

    assert result.status is ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_source_validation_alert_is_not_no_results(monkeypatch):
    invalid_page = query_orange_county_courts.parse_calendar_html(INVALID_HTML)
    client = FakeOrangeClient(
        error=query_orange_county_courts.OrangeCourtQueryError(
            invalid_page.alerts
        )
    )

    result = _execute(
        _parse("search", "--case-number", "ZZZZ-NOT-A-CASE"),
        monkeypatch,
        client=client,
    )

    assert result.status is ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "source_validation_error"
    assert result.errors[0].details["alerts"] == ("Invalid case number.",)


def test_missing_or_changed_table_header_is_source_changed():
    changed = SUCCESS_HTML.replace("<th>Status</th>", "<th>Outcome</th>")

    with pytest.raises(SourceSchemaError, match="columns changed"):
        query_orange_county_courts.parse_calendar_html(changed)


def test_rate_limit_remains_an_explicit_failure(monkeypatch):
    client = FakeOrangeClient(
        error=RateLimitedHTTPError(
            429,
            url=query_orange_county_courts.CALENDAR_URL,
        )
    )

    result = _execute(
        _parse("search", "--date", "2026-07-28"),
        monkeypatch,
        client=client,
    )

    assert result.status is ResultStatus.RATE_LIMITED
    assert result.errors[0].code == "rate_limited"


def test_catalog_denial_stops_before_source_dispatch(monkeypatch):
    client = FakeOrangeClient()

    result = _execute(
        _parse("search", "--date", "2026-07-28"),
        monkeypatch,
        client=client,
        decision={
            "allowed": False,
            "access_class": "C",
            "reason_code": "route_unavailable",
            "reason": "use another route",
        },
    )

    assert result.status is ResultStatus.HUMAN_REQUIRED
    assert result.errors[0].code == "route_unavailable"
    assert client.calls == []


def test_selectors_are_forwarded_without_an_adapter_total_cap(monkeypatch):
    client = FakeOrangeClient()

    _execute(
        _parse(
            "search",
            "--date",
            "2026-07-28",
            "--first-name",
            "Justin",
            "--last-name",
            "Douglas",
            "--judge",
            "Bova, Amanda S",
            "--limit",
            "137",
            "--offset",
            "274",
        ),
        monkeypatch,
        client=client,
    )

    assert client.calls == [
        (
            "search",
            {
                "hearing_date": "2026-07-28",
                "case_number": None,
                "first_name": "Justin",
                "last_name": "Douglas",
                "judge": "Bova, Amanda S",
            },
        )
    ]


def test_limit_and_offset_page_normalized_cases_without_a_source_cap(
    monkeypatch,
):
    page = query_orange_county_courts.parse_calendar_html(SUCCESS_HTML)
    other = query_orange_county_courts.OrangeHearingRow(
        case_number="2026-CF-009999-A-O",
        hearing_date="08/21/2026",
        time_slot="9:00 AM",
        location=None,
        caption="State Of Florida Vs. Example, Avery",
        judge="Example, Jordan",
        status=None,
    )
    page = replace(page, rows=(*page.rows, other), total_count=3)
    client = FakeOrangeClient(page=page)

    first = _execute(
        _parse("search", "--date", "2026-08-21", "--limit", "1"),
        monkeypatch,
        client=client,
    )
    second = _execute(
        _parse(
            "search",
            "--date",
            "2026-08-21",
            "--limit",
            "1",
            "--offset",
            "1",
        ),
        monkeypatch,
        client=client,
    )

    assert first.records[0]["raw_case_number"] == "2020-CT-001540-A-O"
    assert first.next_cursor == "orange-calendar:offset:1"
    assert second.records[0]["raw_case_number"] == "2026-CF-009999-A-O"
    assert second.next_cursor is None


@pytest.mark.parametrize(
    ("values", "error_code"),
    [
        (("search", "--date", "07/28/2026"), "invalid_hearing_date"),
        (("search", "--first-name", "Justin"), "incomplete_name"),
        (("search",), "search_selector_required"),
    ],
)
def test_unrepresentable_selection_is_explicit_failure(
    monkeypatch,
    values,
    error_code,
):
    result = _execute(_parse(*values), monkeypatch)

    assert result.status is ResultStatus.UNAVAILABLE
    assert result.errors[0].code == error_code


def test_probe_reports_validated_form_table_and_scope(monkeypatch):
    client = FakeOrangeClient()

    result = _execute(_parse("probe"), monkeypatch, client=client)
    record = result.to_dict()["records"][0]

    assert client.calls == [("probe", {})]
    assert record["record_kind"] == "probe"
    assert record["source_total_hearings"] == 2
    assert record["parsed_row_count"] == 2
    assert record["request_parameters"]["hearDate"] == "2026-07-28"
    assert record["source_scope"]["record_type"] == (
        "current_future_hearing_calendar"
    )
