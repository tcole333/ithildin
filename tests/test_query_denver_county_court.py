from __future__ import annotations

import html
import sqlite3
from dataclasses import replace
from typing import Any

import pytest

from tools import query_denver_county_court
from tools.ingest_state_court_records import ingest_envelope, validate_envelope
from tools.public_records_contract import ResultStatus
from tools.public_records_http import (
    RetryPolicy,
    SourceSchemaError,
    TransportError,
)


ALLOWED = {
    "allowed": True,
    "access_class": "A",
    "reason_code": "anonymous_public_route",
    "limits": {},
}


def _row(
    *,
    case_number: str = "26M00001",
    ab_tk: str = "202600001",
    defendant: str = "DOE JANE A",
    status: str = "BOND",
    language: str = "",
    case_type: str = "DOMESTIC VIOLENCE",
    scheduled_hearing: str = "JURY TRIAL",
    hearing_time: str = "08:30 AM",
    disposition: str = "",
    dv: str = "Y",
    counsel: str = "Counsel, Casey",
    dob: str = "01/02/1990",
    violations: tuple[str, ...] = (
        "18-3-204(1)(a) - ASSAULT 3",
        "18-6-803.5(1)(a) - VIOLATION P/O",
    ),
) -> str:
    values = (
        (
            f'<a href="/Case/CaseHistory?CaseNumber={html.escape(case_number)}">'
            f"{html.escape(case_number)}</a>"
        ),
        html.escape(ab_tk),
        html.escape(defendant),
        html.escape(status),
        html.escape(language),
        html.escape(case_type),
        html.escape(scheduled_hearing),
        (
            '<span data-marker="time">'
            f"{html.escape(hearing_time)}</span>"
        ),
        html.escape(disposition),
        html.escape(dv),
        html.escape(counsel),
        html.escape(dob),
        '<a title="Show Violations"><span>icon</span></a>',
        html.escape("^".join(violations) + "^"),
    )
    cells: list[str] = []
    for index, value in enumerate(values):
        if index == 7:
            cells.append(
                '<td data-order="7/29/2026 8:30:00 AM">'
                f"{value}</td>"
            )
        else:
            cells.append(f"<td>{value}</td>")
    return "<tr>" + "".join(cells) + "</tr>"


def _document(
    *,
    selected_room: str | None = None,
    court_date: str = "",
    rows: tuple[str, ...] = (),
    table_id: str = "DocketTable",
    form_id: str = "docketForm",
    scheduled_header: str = "Scheduled Hearing",
) -> str:
    def option(value: str, *, selected: bool = False) -> str:
        selected_attr = ' selected="selected"' if selected else ""
        return (
            f'<option value="{html.escape(value)}"{selected_attr}>'
            f"{html.escape(value or 'Select One')}</option>"
        )

    options = "".join(
        (
            option("3A", selected=selected_room == "3A"),
            option("4B", selected=selected_room == "4B"),
            option("", selected=selected_room is None),
        )
    )
    headers = (
        "Case No",
        "AB/TK",
        "Defendant",
        "Status",
        "Language",
        "Case Type",
        scheduled_header,
        "Time",
        "Disposition",
        "DV",
        "Counsel",
        "DOB",
        "Charge",
        "Charge",
    )
    header_html = "".join(f"<th>{html.escape(value)}</th>" for value in headers)
    return f"""
    <html>
      <body>
        <form action="/Docket/Docket" id="{form_id}" method="post">
          <input type="hidden" id="token" name="token" value="" />
          <select id="SelectedCourtroom" name="SelectedCourtroom">
            {options}
          </select>
          <input id="Court_Date" name="Court_Date" type="text"
                 value="{html.escape(court_date)}" />
        </form>
        <form action="/Search/Docket" id="DocketContent" method="get">
          <input id="showViolation" name="showViolation" type="hidden"
                 value="True" />
          <table id="{table_id}">
            <thead><tr>{header_html}</tr></thead>
            <tbody>{"".join(rows)}</tbody>
          </table>
        </form>
        <div id="captchaEnabledConfigDocket"
             data-captcha-enabled="False"></div>
      </body>
    </html>
    """


BOOTSTRAP_HTML = _document()
SUCCESS_HTML = _document(
    selected_room="3A",
    court_date="07/29/2026",
    rows=(
        _row(),
        _row(
            case_number="26M00001",
            scheduled_hearing="SENTENCING",
            hearing_time="01:30 PM",
            disposition="CONTINUED",
            status="JAIL",
            counsel="Different, Counsel",
            violations=("18-3-204(1)(a) - ASSAULT 3",),
        ),
    ),
)
EMPTY_HTML = _document(
    selected_room="3A",
    court_date="08/02/2026",
)


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
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class NoWait:
    def wait(self) -> None:
        return None


class FakeDenverClient:
    def __init__(
        self,
        *,
        page: query_denver_county_court.DenverDocketPage | None = None,
        error: Exception | None = None,
    ) -> None:
        self.page = page or query_denver_county_court.parse_docket_html(
            SUCCESS_HTML
        )
        self.error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def search(self, **kwargs: Any):
        self.calls.append(("search", dict(kwargs)))
        if self.error is not None:
            raise self.error
        return self.page

    def probe(self, **kwargs: Any):
        self.calls.append(("probe", dict(kwargs)))
        if self.error is not None:
            raise self.error
        return self.page


def _parse(*values: str):
    return query_denver_county_court.build_parser().parse_args(list(values))


def _execute(args, monkeypatch, *, client=None, decision=ALLOWED):
    monkeypatch.setattr(
        query_denver_county_court,
        "log_search",
        lambda *_args: None,
    )
    return query_denver_county_court.execute(
        args,
        access_decision=decision,
        client=client or FakeDenverClient(),
    )


def test_parser_preserves_live_form_rows_and_violation_text():
    page = query_denver_county_court.parse_docket_html(SUCCESS_HTML)

    assert page.form_action == "/Docket/Docket"
    assert page.form_method == "post"
    assert page.token == ""
    assert page.courtroom_options == ("3A", "4B")
    assert page.selected_courtroom == "3A"
    assert page.court_date == "07/29/2026"
    assert page.columns == query_denver_county_court.EXPECTED_COLUMNS
    assert page.captcha_enabled is False
    assert len(page.rows) == 2
    first = page.rows[0]
    assert first.case_number == "26M00001"
    assert first.defendant == "DOE JANE A"
    assert first.hearing_time == "08:30 AM"
    assert first.source_time_order_raw == "7/29/2026 8:30:00 AM"
    assert first.case_history_url == (
        "https://public.denvercountycourt.org/"
        "Case/CaseHistory?CaseNumber=26M00001"
    )
    assert first.violations == (
        "18-3-204(1)(a) - ASSAULT 3",
        "18-6-803.5(1)(a) - VIOLATION P/O",
    )


def test_client_uses_verified_get_and_post_contract():
    session = FakeSession(
        [FakeResponse(BOOTSTRAP_HTML), FakeResponse(SUCCESS_HTML)]
    )
    client = query_denver_county_court.DenverCountyCourtClient(
        session=session,
        retry_policy=RetryPolicy(max_attempts=1),
        rate_limiter=NoWait(),
        sleeper=lambda _delay: None,
    )

    page = client.search(courtroom="3A", court_date="2026-07-29")

    assert len(page.rows) == 2
    assert [call[0] for call in session.calls] == ["GET", "POST"]
    assert session.calls[0][1] == query_denver_county_court.DOCKET_URL
    assert session.calls[1][2]["data"] == {
        "SelectedCourtroom": "3A",
        "Court_Date": "07/29/2026",
        "token": "",
    }
    assert page.request_parameters == {
        "SelectedCourtroom": "3A",
        "Court_Date": "07/29/2026",
        "token": "",
    }


def test_client_retries_a_retryable_get_before_posting():
    session = FakeSession(
        [
            FakeResponse("busy", status_code=503),
            FakeResponse(BOOTSTRAP_HTML),
            FakeResponse(SUCCESS_HTML),
        ]
    )
    client = query_denver_county_court.DenverCountyCourtClient(
        session=session,
        retry_policy=RetryPolicy(
            max_attempts=2,
            backoff_initial=0,
            max_backoff=0,
        ),
        rate_limiter=NoWait(),
        sleeper=lambda _delay: None,
    )

    page = client.search(courtroom="3A", court_date="2026-07-29")

    assert len(page.rows) == 2
    assert [call[0] for call in session.calls] == ["GET", "GET", "POST"]


def test_native_entry_ids_are_order_independent_and_ignore_mutable_fields():
    page = query_denver_county_court.parse_docket_html(SUCCESS_HTML)
    records = query_denver_county_court.normalize_rows(page)
    reversed_records = query_denver_county_court.normalize_rows(
        replace(page, rows=tuple(reversed(page.rows)))
    )

    assert len(records) == 2
    assert records[0]["case"]["raw_case_number"] == "26M00001"
    assert records[1]["case"]["raw_case_number"] == "26M00001"
    assert records[0]["canonical_ref"] != records[1]["canonical_ref"]
    assert records[0]["case"]["canonical_ref"] == (
        records[1]["case"]["canonical_ref"]
    )
    assert records[0]["native_entry_id"] != records[1]["native_entry_id"]
    assert {row["native_entry_id"] for row in records} == {
        row["native_entry_id"] for row in reversed_records
    }

    changed_page = replace(
        page,
        rows=(
            replace(
                page.rows[0],
                status="NEW STATUS",
                disposition="NEW DISPOSITION",
                counsel="New, Counsel",
                violations=("NEW VIOLATION",),
            ),
            page.rows[1],
        ),
    )
    changed = query_denver_county_court.normalize_rows(changed_page)
    assert changed[0]["native_entry_id"] == records[0]["native_entry_id"]
    assert "status" not in records[0]["identity_basis"]
    assert "disposition" not in records[0]["identity_basis"]


def test_execute_can_skip_search_log_for_monitor_probe(monkeypatch):
    calls = []
    monkeypatch.setattr(
        query_denver_county_court,
        "log_search",
        lambda *_args: calls.append(_args),
    )

    result = query_denver_county_court.execute(
        _parse(
            "probe",
            "--courtroom",
            "3A",
            "--date",
            "2026-07-29",
        ),
        access_decision=ALLOWED,
        client=FakeDenverClient(),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert calls == []


def test_normalized_row_preserves_source_labels_without_assigning_counsel_role():
    page = query_denver_county_court.parse_docket_html(SUCCESS_HTML)
    record = query_denver_county_court.normalize_rows(page)[0]

    assert record["event_date"] == "2026-07-29"
    assert record["event_time"] == "08:30:00"
    assert record["courtroom"] == "3A"
    assert record["defendant_name"] == "DOE JANE A"
    assert record["case_type"] == "DOMESTIC VIOLENCE"
    assert record["status"] == "BOND"
    assert record["counsel"] == "Counsel, Casey"
    assert record["violations"] == [
        "18-3-204(1)(a) - ASSAULT 3",
        "18-6-803.5(1)(a) - VIOLATION P/O",
    ]
    assert record["case"]["parties"] == [
        {
            "sequence_no": 1,
            "role": "Defendant",
            "raw_name": "DOE JANE A",
            "access_state": "public",
        }
    ]
    assert "attorneys" not in record["case"]


def test_valid_empty_post_is_authoritative_no_results(monkeypatch):
    empty_page = query_denver_county_court.parse_docket_html(EMPTY_HTML)
    result = _execute(
        _parse(
            "search",
            "--courtroom",
            "3A",
            "--date",
            "2026-08-02",
        ),
        monkeypatch,
        client=FakeDenverClient(page=empty_page),
    )

    assert result.status is ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()
    validate_envelope(result.to_dict())


@pytest.mark.parametrize(
    "changed_html",
    [
        _document(form_id="changedForm"),
        _document(table_id="ChangedTable"),
        _document(scheduled_header="Unexpected Column"),
        _document().replace(
            'action="/Docket/Docket"',
            'action="https://example.test/Docket/Docket"',
            1,
        ),
        _document().replace(
            "<th>Charge</th>",
            "<th>Notes</th>",
            1,
        ),
    ],
)
def test_missing_form_table_or_required_header_is_source_changed(
    changed_html,
):
    with pytest.raises(SourceSchemaError):
        query_denver_county_court.parse_docket_html(changed_html)


def test_source_schema_failure_becomes_source_changed_envelope(monkeypatch):
    error = SourceSchemaError(
        "changed",
        url=query_denver_county_court.DOCKET_URL,
    )
    result = _execute(
        _parse(
            "search",
            "--courtroom",
            "3A",
            "--date",
            "2026-07-29",
        ),
        monkeypatch,
        client=FakeDenverClient(error=error),
    )

    assert result.status is ResultStatus.SOURCE_CHANGED
    assert result.records == ()
    assert result.errors[0].code == "source_schema_changed"
    validate_envelope(result.to_dict())


def test_transport_failure_becomes_unavailable_envelope(monkeypatch):
    error = TransportError(
        "offline",
        url=query_denver_county_court.DOCKET_URL,
    )
    result = _execute(
        _parse(
            "search",
            "--courtroom",
            "3A",
            "--date",
            "2026-07-29",
        ),
        monkeypatch,
        client=FakeDenverClient(error=error),
    )

    assert result.status is ResultStatus.UNAVAILABLE
    assert result.records == ()
    assert result.errors[0].code == "transport_error"


def test_caller_selected_slicing_sets_only_a_local_next_cursor(monkeypatch):
    result = _execute(
        _parse(
            "search",
            "--courtroom",
            "3A",
            "--date",
            "2026-07-29",
            "--limit",
            "1",
            "--offset",
            "0",
        ),
        monkeypatch,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == 1
    assert result.next_cursor == "denver-county-docket:offset:1"
    assert result.query.query.requested_limit == 1

    unbounded = _execute(
        _parse(
            "search",
            "--courtroom",
            "3A",
            "--date",
            "2026-07-29",
        ),
        monkeypatch,
    )
    assert len(unbounded.records) == 2
    assert unbounded.next_cursor is None
    assert unbounded.query.query.requested_limit is None


def test_envelope_validates_and_projects_docket_rows_by_case_identity(
    tmp_path,
    monkeypatch,
):
    result = _execute(
        _parse(
            "search",
            "--courtroom",
            "3A",
            "--date",
            "2026-07-29",
        ),
        monkeypatch,
    )
    payload = result.to_dict()
    validate_envelope(payload)
    court_db = tmp_path / "state-courts.db"

    report = ingest_envelope(payload, court_db=court_db)

    assert report["status"] == "ingested"
    assert report["projected"]["docket_entries"] == 2
    with sqlite3.connect(court_db) as db:
        case_count = db.execute(
            "SELECT COUNT(*) FROM case_record"
        ).fetchone()[0]
        docket_count = db.execute(
            "SELECT COUNT(*) FROM docket_entry"
        ).fetchone()[0]
        party_count = db.execute(
            "SELECT COUNT(*) FROM case_party"
        ).fetchone()[0]
    assert case_count == 1
    assert docket_count == 2
    assert party_count == 1


def test_probe_emits_health_record_even_when_post_table_is_empty(monkeypatch):
    empty_page = query_denver_county_court.parse_docket_html(EMPTY_HTML)
    empty_page = replace(
        empty_page,
        request_parameters={
            "SelectedCourtroom": "3A",
            "Court_Date": "08/02/2026",
            "token": "transient-value",
        },
    )
    result = _execute(
        _parse(
            "probe",
            "--courtroom",
            "3A",
            "--date",
            "2026-08-02",
        ),
        monkeypatch,
        client=FakeDenverClient(page=empty_page),
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == 1
    assert result.records[0]["record_kind"] == "source_health_check"
    assert result.records[0]["parsed_row_count"] == 0
    assert result.records[0]["captcha_enabled"] is False
    assert result.records[0]["request_parameters"] == {
        "SelectedCourtroom": "3A",
        "Court_Date": "08/02/2026",
    }
    validate_envelope(result.to_dict())
