from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_delaware_courts
from tools.ingest_state_court_records import ingest_envelope


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "delaware_courts"
)


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def _case_with_events() -> str:
    return _fixture("case_jp13_23_013991.html").replace(
        "<i>No case events were found.</i>",
        """
        <table border>
          <tr>
            <th>Event</th><th>Date/Time</th><th>Room</th>
            <th>Location</th><th>Judge</th>
          </tr>
          <tr>
            <td>MOTION TO STAY</td>
            <td>30-JUL-2026<br>10:30 AM</td>
            <td>SCN COURTROOM TBD</td>
            <td>SUPERIOR CT NEW CASTLE COUNTY</td>
            <td>RENNIE, SHELDON K</td>
          </tr>
        </table>
        """,
        1,
    )


@dataclass
class FixtureResponse:
    text: str
    url: str | None = None
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)


class QueueSession:
    def __init__(self, responses: list[FixtureResponse]):
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(
        self,
        method,
        url,
        *,
        params=None,
        data=None,
        headers=None,
        timeout=None,
    ):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": dict(params or {}),
                "data": dict(data or {}),
                "headers": dict(headers or {}),
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError("unexpected CourtConnect request")
        return self.responses.pop(0)

    def close(self):
        self.closed = True


def _parse(*values: str):
    return query_delaware_courts.build_parser().parse_args(list(values))


def test_party_results_parse_stable_ids_dates_and_native_next_link():
    page = query_delaware_courts.parse_party_results_page(
        _fixture("party_results_page_1.html"),
        source_url=query_delaware_courts.PARTY_RESULTS_URL,
    )

    assert page.page_number == 1
    assert page.record_start == 1
    assert page.record_end == 20
    assert len(page.records) == 2
    assert page.next_url is not None
    assert "PageNo=2" in page.next_url
    hit = page.records[0]
    assert hit["search_hit_id"] == "@3870536:JP13-23-013991"
    assert hit["party_name"] == "TESLA"
    assert hit["filing_date"] == "2023-11-20"
    assert hit["caption"] == "RUMEN MLADENOV VS TESLA INC"
    assert hit["address"].startswith("132 CHRISTIANA MALL")


def test_party_results_authoritative_empty_is_not_a_schema_failure():
    page = query_delaware_courts.parse_party_results_page(
        _fixture("no_results.html")
    )

    assert page.records == ()
    assert page.authoritative_empty is True
    assert page.next_url is None


def test_client_follows_every_native_party_page_without_an_adapter_cap():
    first_url = (
        f"{query_delaware_courts.PARTY_RESULTS_URL}"
        "?backto=P&last_name=TESLA&PageNo=1"
    )
    second_url = (
        f"{query_delaware_courts.BASE_URL}/"
        "ck_public_qry_cpty.cp_personcase_srch_details"
        "?backto=P&partial_ind=checked&last_name=TESLA"
        "&case_type=ALL&PageNo=2"
    )
    session = QueueSession(
        [
            FixtureResponse(
                _fixture("party_results_page_1.html"),
                url=first_url,
            ),
            FixtureResponse(
                _fixture("party_results_page_2.html"),
                url=second_url,
            ),
        ]
    )
    client = query_delaware_courts.DelawareCourtConnectClient(
        session=session,
        minimum_interval=0,
    )
    client._accepted_modes.add("party")

    fetched = client.search_cases("TESLA", partial=True)

    assert len(fetched.records) == 3
    assert fetched.pages_fetched == 2
    assert fetched.next_url is None
    assert len(session.calls) == 2
    assert session.calls[0]["params"]["PageNo"] == 1
    assert "limit" not in session.calls[0]["params"]
    assert session.calls[1]["url"] == second_url


def test_native_page_mode_returns_exact_continuation_and_converts_dates():
    session = QueueSession(
        [
            FixtureResponse(
                _fixture("party_results_page_1.html"),
                url=query_delaware_courts.PARTY_RESULTS_URL,
            )
        ]
    )
    client = query_delaware_courts.DelawareCourtConnectClient(
        session=session,
        minimum_interval=0,
    )
    client._accepted_modes.add("party")

    fetched = client.search_cases(
        "TESLA",
        filed_after="2023-01-02",
        filed_before="31-DEC-2023",
        case_type="60 - JP DEBT ACTION",
        page=1,
    )

    assert fetched.pages_fetched == 1
    assert fetched.next_url is not None
    params = session.calls[0]["params"]
    assert params["begin_date"] == "02-JAN-2023"
    assert params["end_date"] == "31-DEC-2023"
    assert params["case_type"] == "60 - JP DEBT ACTION"


class FixtureSearchClient:
    def __init__(self, fetched):
        self.fetched = fetched
        self.calls: list[dict[str, Any]] = []

    def search_cases(self, last_name_or_company, **kwargs):
        self.calls.append(
            {
                "last_name_or_company": last_name_or_company,
                **kwargs,
            }
        )
        return self.fetched


def test_caller_limit_slices_after_fetch_and_reports_truncation():
    first = query_delaware_courts.parse_party_results_page(
        _fixture("party_results_page_1.html")
    )
    second = query_delaware_courts.parse_party_results_page(
        _fixture("party_results_page_2.html")
    )
    fetched = query_delaware_courts.CourtConnectFetch(
        records=(*first.records, *second.records),
        pages_fetched=2,
        next_url=None,
        schema_fingerprint="a" * 64,
        source_url=query_delaware_courts.PARTY_RESULTS_URL,
    )
    client = FixtureSearchClient(fetched)

    result = query_delaware_courts.execute(
        _parse("cases", "TESLA", "--partial", "--limit", "2"),
        access_decision={"allowed": True},
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 2
    assert result.query.query.requested_limit == 2
    assert client.calls[0]["last_name_or_company"] == "TESLA"
    assert "limit" not in client.calls[0]
    assert result.warnings[-1] == (
        "Caller limit returned 2 of 3 source hits fetched."
    )


def test_disclaimer_acceptance_uses_the_source_provided_action():
    session = QueueSession(
        [
            FixtureResponse(
                _fixture("disclaimer.html"),
                url=(
                    f"{query_delaware_courts.DISCLAIMER_URL}"
                    "?search_option=party"
                ),
            ),
            FixtureResponse(
                _fixture("disclaimer_action_party.html"),
                url=(
                    f"{query_delaware_courts.BASE_URL}/"
                    "ck_public_qry_main.cp_disclaimer_srch_link"
                    "?search_option=party"
                ),
            ),
            FixtureResponse(
                _fixture("setup_frameset.html"),
                url=(
                    f"{query_delaware_courts.BASE_URL}/"
                    "ck_public_qry_cpty.cp_personcase_setup_idx"
                ),
            ),
        ]
    )
    client = query_delaware_courts.DelawareCourtConnectClient(
        session=session,
        minimum_interval=0,
    )

    client._accept("party")

    assert [call["method"] for call in session.calls] == [
        "GET",
        "GET",
        "POST",
    ]
    assert session.calls[-1]["url"].endswith(
        "ck_public_qry_cpty.cp_personcase_setup_idx"
    )
    assert "party" in client._accepted_modes


def test_case_report_parses_parties_and_docket_with_stable_entry_ids():
    record = query_delaware_courts.parse_case_report(
        _fixture("case_jp13_23_013991.html"),
        source_url=(
            f"{query_delaware_courts.CASE_REPORT_URL}"
            "?case_id=JP13-23-013991"
        ),
    )

    assert record["raw_case_number"] == "JP13-23-013991"
    assert record["caption"] == "RUMEN MLADENOV VS TESLA INC"
    assert record["case_subtype"] == "NON JURY TRIAL"
    assert record["filing_date"] == "2023-11-20"
    assert record["native_case_type_code"] == "60"
    assert record["case_type"] == "JP DEBT ACTION"
    assert record["status"] == "CLOSED"
    assert record["court"]["native_court_id"] == (
        query_delaware_courts.COURT_ID
    )
    assert len(record["parties"]) == 3
    assert record["parties"][1]["native_party_id"] == "@3870536"
    assert record["parties"][1]["role"] == "DEFENDANT"
    assert len(record["docket_entries"]) == 2
    first_entry = record["docket_entries"][0]
    assert first_entry["filing_date"] == "2023-11-20"
    assert first_entry["filed_date"] == "2023-11-20"
    assert first_entry["filed_at"].startswith("2023-11-20T08:44:00")
    assert first_entry["entry_text"] == "COMPLAINT"
    assert first_entry["native_entry_id"].startswith(
        "courtconnect-docket:"
    )
    assert first_entry["raw_text"] == (
        "CLAIM AMOUNT $1000 TO $5000 | COMPLAINT"
    )


def test_case_report_normalizes_nonempty_event_schedule():
    record = query_delaware_courts.parse_case_report(
        _case_with_events(),
        source_url=(
            f"{query_delaware_courts.CASE_REPORT_URL}"
            "?case_id=JP13-23-013991"
        ),
    )

    assert record["native_case_event_rows"] == [
        {
            "event": "MOTION TO STAY",
            "datetime": "30-JUL-2026 10:30 AM",
            "room": "SCN COURTROOM TBD",
            "location": "SUPERIOR CT NEW CASTLE COUNTY",
            "judge": "RENNIE, SHELDON K",
        }
    ]
    assert len(record["case_events"]) == 1
    event = record["case_events"][0]
    assert event["native_event_id"].startswith("courtconnect-event:")
    assert event["event_type"] == "MOTION TO STAY"
    assert event["event_date"] == "2026-07-30T10:30:00-04:00"
    assert event["scheduled_date"] == "2026-07-30"
    assert event["judge_raw"] == "RENNIE, SHELDON K"
    assert event["assertion_kind"] == "docket_metadata"
    assert event["native_assertion_kind"] == "case_event_schedule"


def test_chancery_stub_preserves_source_document_access_ceiling():
    record = query_delaware_courts.parse_case_report(
        _fixture("case_2026_0094.html"),
        source_url=(
            f"{query_delaware_courts.CASE_REPORT_URL}?case_id=2026-0094"
        ),
    )

    assert record["raw_case_number"] == "2026-0094"
    assert record["documents"] == []
    assert record["parties"][1]["address"] == (
        "COURT OF CHANCERY OF DELAWARE"
    )
    notices = record["document_access"]["native_docket_notices"]
    assert len(notices) == 1
    assert "FILEANDSERVEXPRESS.COM" in notices[0]
    assert record["source_scope"]["filing_documents_available"] is False


def test_judgment_search_and_related_case_parsers_preserve_native_identity():
    search_page = query_delaware_courts.parse_judgment_results_page(
        _fixture("judgment_results.html")
    )
    judgment = search_page.records[0]

    assert judgment["judgment_id"] == "775119:4623454"
    assert judgment["person_id"] == "@3602323"
    assert judgment["amount"] == "7965.00"
    assert judgment["currency"] == "USD"
    assert judgment["judgment_date"] == "2022-10-21"

    detail_page = query_delaware_courts.parse_judgment_detail_page(
        _fixture("judgment_detail.html")
    )
    assert detail_page.records == (
        {
            "case_id": "JP17-22-002184",
            "caption": "WILLIAM CHEN VS TESLA BIOHEALING",
            "docket_description": "JUDGMENT ARGUMENT",
            "case_status": "APPEAL-APPEAL",
            "case_url": (
                f"{query_delaware_courts.BASE_URL}/"
                "ck_public_qry_doct.cp_dktrpt_frames"
                "?backto=J&case_id=JP17-22-002184"
            ),
        },
    )


def test_options_parser_uses_live_form_values_without_hard_coding():
    case_types = query_delaware_courts.parse_options_page(
        _fixture("party_options.html"),
        select_name="case_type",
        option_group="case_type",
        source_url=query_delaware_courts.PARTY_SETUP_URL,
    )
    statuses = query_delaware_courts.parse_options_page(
        _fixture("judgment_options.html"),
        select_name="sat_ind",
        option_group="judgment_status",
        source_url=query_delaware_courts.JUDGMENT_SETUP_URL,
    )

    assert [row["native_value"] for row in case_types] == [
        "ALL",
        "2A - CIVIL ACTIONS",
        "60 - JP DEBT ACTION",
    ]
    assert case_types[1]["native_code"] == "2A"
    assert case_types[1]["label"] == "CIVIL ACTIONS"
    assert statuses[-1]["native_value"] == "SATISFIED"


class FixtureCaseClient:
    def __init__(self, record: dict[str, Any]):
        self.record = record
        self.calls: list[str] = []

    def get_case(self, case_id, *, docket_after=None, docket_before=None):
        self.calls.append(case_id)
        assert docket_after is None
        assert docket_before is None
        return self.record


def test_case_result_envelope_projects_to_state_court_store(tmp_path):
    record = query_delaware_courts.parse_case_report(
        _case_with_events(),
        source_url=(
            f"{query_delaware_courts.CASE_REPORT_URL}"
            "?case_id=JP13-23-013991"
        ),
    )
    client = FixtureCaseClient(record)

    result = query_delaware_courts.execute(
        _parse("case", "JP13-23-013991"),
        access_decision={"allowed": True},
        client=client,
        log_results=False,
    )
    ingested = ingest_envelope(
        result.to_dict(),
        court_db=tmp_path / "state-courts.db",
    )

    assert result.status.value == "ok"
    assert client.calls == ["JP13-23-013991"]
    assert ingested["status"] == "ingested"
    assert ingested["projected"]["cases"] == 1
    assert ingested["projected"]["parties"] == 3
    assert ingested["projected"]["docket_entries"] == 2
    assert ingested["projected"]["case_events"] == 1
    assert ingested["projected"]["documents"] == 0

    db = sqlite3.connect(tmp_path / "state-courts.db")
    try:
        docket_dates = db.execute(
            """
            SELECT filed_date, entered_date
            FROM docket_entry
            ORDER BY docket_entry_id
            """
        ).fetchall()
        case_events = db.execute(
            """
            SELECT event_type, event_date, assertion_kind,
                   native_assertion_kind
            FROM case_event
            """
        ).fetchall()
    finally:
        db.close()
    assert docket_dates[0] == (
        "2023-11-20",
        "2023-11-20T08:44:00-05:00",
    )
    assert case_events == [
        (
            "MOTION TO STAY",
            "2026-07-30T10:30:00-04:00",
            "docket_metadata",
            "case_event_schedule",
        )
    ]


class BombClient:
    def __getattr__(self, name):
        raise AssertionError(f"denied acquisition called client method {name}")


def test_denied_access_decision_returns_structured_failure_before_acquisition():
    result = query_delaware_courts.execute(
        _parse("case", "JP13-23-013991"),
        access_decision={
            "allowed": False,
            "access_class": "C",
            "reason_code": "interactive_route_required",
            "reason": "fixture denial",
        },
        client=BombClient(),
        log_results=False,
    )

    assert result.status.value == "human_required"
    assert result.records == ()
    assert result.errors[0].code == "interactive_route_required"
    assert result.errors[0].category == "access"
    assert result.errors[0].details["reason"] == "fixture denial"


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DE_COURTCONNECT") != "1",
    reason="set RUN_LIVE_DE_COURTCONNECT=1 for the official live probe",
)
def test_live_courtconnect_probe():
    client = query_delaware_courts.DelawareCourtConnectClient(
        timeout=30,
        minimum_interval=0.1,
    )
    try:
        records = client.probe()
        options = client.options()
        case_page = client.search_cases("TESLA", partial=True, page=1)
        judgment_page = client.search_judgments(
            "TESLA",
            partial=True,
            page=1,
        )
        judgment_detail = client.judgment_detail(
            "775119",
            "4623454",
            name="TESLA BIOHEALING",
            page=1,
        )
    finally:
        client.close()

    assert [record["raw_case_number"] for record in records] == list(
        query_delaware_courts.PROBE_CASE_IDS
    )
    assert all(record["parties"] for record in records)
    assert all(record["docket_entries"] for record in records)
    assert {record["option_group"] for record in options} == {
        "case_type",
        "judgment_status",
    }
    assert case_page.records
    assert judgment_page.records
    assert judgment_detail.records[0]["case_id"] == "JP17-22-002184"
