from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import query_dc_superior_calendar as dc_calendar
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy, SourceSchemaError


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "dc_superior_calendar"
)
RESPONSE_HEADERS = {
    "content-type": "text/html; charset=UTF-8",
    "date": "Thu, 30 Jul 2026 06:40:11 GMT",
}


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str) -> Any:
    return json.loads(fixture_text(name))


def parse_args(*values: str) -> Any:
    return dc_calendar.build_parser().parse_args(list(values))


def test_parser_defaults_to_exhaustive_calendar_collection() -> None:
    search = parse_args("search")
    snapshot = parse_args("snapshot")

    assert search.max_pages is None
    assert snapshot.limit is None


class FixtureClient:
    def __init__(self) -> None:
        self.html_calls: list[tuple[str, dict[str, Any]]] = []
        self.json_calls: list[tuple[str, dict[str, Any]]] = []

    def html(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dc_calendar.FetchedText:
        parameters = dict(params or {})
        self.html_calls.append((url, parameters))
        if url == dc_calendar.TODAY_URL:
            if parameters.get("case_no") == "ZZZ-NO-SUCH-CASE":
                name = "today_empty.html"
            elif parameters.get("page") == 1:
                name = "today_last_page.html"
            else:
                name = "today_page.html"
        elif url == dc_calendar.CRIMINAL_URL:
            name = "criminal_page.html"
        elif url == dc_calendar.TAX_URL:
            name = "tax_page.html"
        else:
            raise AssertionError(url)
        return dc_calendar.FetchedText(
            text=fixture_text(name),
            source_url=f"{url}?fixture=1",
            headers=RESPONSE_HEADERS,
        )

    def json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dc_calendar.FetchedJSON:
        parameters = dict(params or {})
        self.json_calls.append((url, parameters))
        if url == dc_calendar.TODAY_REST_URL:
            name = "today_snapshot.json"
        elif url == dc_calendar.APPEALS_REST_URL:
            name = "appeals.json"
        else:
            raise AssertionError(url)
        return dc_calendar.FetchedJSON(
            payload=fixture_json(name),
            source_url=f"{url}?fixture=1",
            headers={
                "content-type": "application/json",
                "date": RESPONSE_HEADERS["date"],
            },
        )


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        text: str = "",
        payload: Any = None,
        headers: dict[str, str] | None = None,
        url: str = dc_calendar.TODAY_URL,
    ) -> None:
        self.status_code = status_code
        self.text = text
        self._payload = payload
        self.headers = headers or {"content-type": "text/html"}
        self.url = url

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("no JSON fixture")
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def test_source_manifest_keeps_representations_and_complements_explicit() -> None:
    manifest = dc_calendar.source_manifest()
    source_ids = {item["source_id"] for item in manifest["sources"]}

    assert source_ids == {
        dc_calendar.TODAY_SOURCE_ID,
        dc_calendar.CRIMINAL_SOURCE_ID,
        dc_calendar.TAX_SOURCE_ID,
        dc_calendar.APPEALS_SOURCE_ID,
    }
    assert manifest["operations"]["search"]["pagination"] == (
        "native_zero_based_page"
    )
    assert manifest["operations"]["snapshot"]["representation"] == (
        "rest_full_current_array"
    )
    systems = {
        item["source_id"]: item
        for item in manifest["complementary_case_systems"]
    }
    assert systems["us-dc-superior-court-portal"]["operation_states"][
        "smart_search"
    ]["state"] == "human_verification_observed"
    assert systems["us-dc-superior-eaccess"]["operation_states"][
        "case_search"
    ]["state"] == "captcha_observed"
    assert all(
        source["metadata"]["access"] == "anonymous_open"
        for source in manifest["sources"]
    )


def test_today_parser_preserves_native_taxonomy_and_each_table_row() -> None:
    page = dc_calendar.parse_calendar_html(
        fixture_text("today_page.html"),
        kind="today",
        native_page=0,
    )

    assert len(page.rows) == 3
    assert page.reported_total == 12
    assert page.total_pages == 2
    assert page.next_page == 1
    assert page.rows[0]["Party"] == page.rows[1]["Party"]
    assert page.rows[0]["Judge"] != page.rows[1]["Judge"]
    assert page.rows[0]["_event_datetime"] == (
        "2026-07-30T09:00:00-04:00"
    )
    assert page.rows[0]["_remote_hearing_url"].endswith("ctbb109")
    assert [item["name"] for item in page.filters["text_fields"]] == [
        "party",
        "case_no",
    ]
    assert [item["name"] for item in page.filters["select_fields"]] == [
        "judges",
        "courtroom",
    ]
    assert page.filters["sort_fields"]["Time"] == "field_timestamp"
    assert len(page.schema_fingerprint) == 64


def test_today_empty_marker_is_authoritative_no_results() -> None:
    parsed = dc_calendar.parse_calendar_html(
        fixture_text("today_empty.html"),
        kind="today",
    )
    assert parsed.no_results is True
    assert parsed.rows == ()

    result = dc_calendar.execute(
        parse_args("search", "--case-number", "ZZZ-NO-SUCH-CASE"),
        client=FixtureClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.NO_RESULTS
    assert result.errors == ()


def test_today_search_returns_resumable_native_page_cursor() -> None:
    client = FixtureClient()
    args = parse_args(
        "search",
        "--case-number",
        "2026-LTB-005132",
        "--judge",
        "10234",
        "--max-pages",
        "1",
    )
    result = dc_calendar.execute(args, client=client, log_results=False)

    assert result.status == ResultStatus.PARTIAL
    assert len(result.records) == 3
    assert result.next_cursor
    assert result.next_cursor.endswith(":page:1")
    assert client.html_calls[0][1] == {
        "case_no": "2026-LTB-005132",
        "judges": "10234",
        "courtroom": "All",
        "page": 0,
    }
    first = result.records[0]
    assert first["record_kind"] == "court_calendar_hearing_occurrence"
    assert first["event_date"] == "2026-07-30"
    assert first["event_time"] == "09:00:00-04:00"
    assert first["timezone"] == "America/New_York"
    assert first["source_occurrence"]["native_page"] == 0
    assert first["source_freshness"]["response_date"] == "2026-07-30"

    resumed = dc_calendar.execute(
        parse_args(
            "search",
            "--case-number",
            "2026-LTB-005132",
            "--judge",
            "10234",
            "--cursor",
            result.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert resumed.status == ResultStatus.OK
    assert len(resumed.records) == 1
    assert resumed.records[0]["source_occurrence"]["native_page"] == 1


def test_cursor_cannot_be_reused_with_different_filters() -> None:
    client = FixtureClient()
    first = dc_calendar.execute(
        parse_args("search", "--party", "Example", "--max-pages", "1"),
        client=client,
        log_results=False,
    )
    assert first.next_cursor

    mismatch = dc_calendar.execute(
        parse_args(
            "search",
            "--party",
            "Different",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert mismatch.status == ResultStatus.UNAVAILABLE
    assert mismatch.errors[0].code == "cursor_query_mismatch"


def test_multi_page_search_keeps_page_occurrences_and_finishes() -> None:
    result = dc_calendar.execute(
        parse_args("search"),
        client=FixtureClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.OK
    assert len(result.records) == 4
    assert [row["source_occurrence"]["native_page"] for row in result.records] == [
        0,
        0,
        0,
        1,
    ]


def test_criminal_parser_preserves_charge_level_occurrences() -> None:
    page = dc_calendar.parse_calendar_html(
        fixture_text("criminal_page.html"),
        kind="criminal",
    )

    assert len(page.rows) == 3
    assert {row["Charge"] for row in page.rows} == {
        "-DRIVING UNDER THE INFLUENCE OF ALCOHOL OR A DRUG",
        "-OPERATING A VEHICLE WHILE IMPAIRED",
        "-NO PERMIT",
    }
    assert {row["Case Number"] for row in page.rows} == {"2026 CTF 004287"}
    assert page.page_last_updated == "2026-02-13"
    assert page.filters["sort_fields"]["Charge"] == "field_xml_charge"

    result = dc_calendar.execute(
        parse_args(
            "criminal",
            "--case-number",
            "2026 CTF 004287",
            "--max-pages",
            "1",
        ),
        client=FixtureClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.PARTIAL
    assert len(result.records) == 3
    assert len({row["native_entry_id"] for row in result.records}) == 3
    assert {row["charge"] for row in result.records} == {
        "-DRIVING UNDER THE INFLUENCE OF ALCOHOL OR A DRUG",
        "-OPERATING A VEHICLE WHILE IMPAIRED",
        "-NO PERMIT",
    }


def test_today_snapshot_keeps_distinct_representation_and_local_cursor() -> None:
    parsed = dc_calendar.parse_today_snapshot(
        fixture_json("today_snapshot.json")
    )
    assert len(parsed) == 2

    client = FixtureClient()
    first = dc_calendar.execute(
        parse_args("snapshot", "--limit", "1"),
        client=client,
        log_results=False,
    )
    assert first.status == ResultStatus.PARTIAL
    assert first.next_cursor
    assert first.next_cursor.endswith(":offset:1")
    assert first.records[0]["representation"] == "rest_snapshot"
    assert first.records[0]["event_datetime"] == (
        "2026-07-30T11:00:00-04:00"
    )
    assert first.records[0]["case_type"] == (
        "Landlord & Tenant - Residential"
    )
    assert first.records[0]["source_freshness"]["event_date_basis"] == (
        "official_today_feed_and_http_response_date"
    )

    second = dc_calendar.execute(
        parse_args(
            "snapshot",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert second.status == ResultStatus.OK
    assert second.records[0]["case_number"] == "2026-CAB-000777"
    assert second.records[0]["source_occurrence"]["snapshot_row_index"] == 1


def test_today_snapshot_without_limit_returns_complete_feed() -> None:
    result = dc_calendar.execute(
        parse_args("snapshot"),
        client=FixtureClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert len(result.records) == 2
    assert result.next_cursor is None


def test_snapshot_schema_drift_and_missing_response_date_are_failures() -> None:
    broken = fixture_json("today_snapshot.json")
    del broken[0]["case_no"]
    with pytest.raises(SourceSchemaError, match="schema changed"):
        dc_calendar.parse_today_snapshot(broken)

    class MissingDateClient(FixtureClient):
        def json(
            self,
            url: str,
            *,
            params: dict[str, Any] | None = None,
        ) -> dc_calendar.FetchedJSON:
            fetched = super().json(url, params=params)
            return dc_calendar.FetchedJSON(
                payload=fetched.payload,
                source_url=fetched.source_url,
                headers={"content-type": "application/json"},
            )

    result = dc_calendar.execute(
        parse_args("snapshot"),
        client=MissingDateClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "source_schema_changed"


def test_criminal_and_tax_artifact_indexes_remain_separate() -> None:
    criminal = dc_calendar.parse_artifact_index_html(
        fixture_text("criminal_page.html"),
        family="criminal",
    )
    assert {item.artifact_type for item in criminal} == {
        "criminal_attorney_schedule",
        "criminal_court_schedule",
    }

    tax = dc_calendar.parse_artifact_index_html(
        fixture_text("tax_page.html"),
        family="tax",
    )
    assert {item.artifact_type for item in tax} == {
        "tax_show_cause",
        "tax_multi_door_mediation",
    }
    assert {item.page_last_updated for item in tax} == {"2026-03-02"}

    result = dc_calendar.execute(
        parse_args("artifacts", "--family", "tax"),
        client=FixtureClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.OK
    assert len(result.records) == 2
    assert {row["source_id"] for row in result.records} == {
        dc_calendar.TAX_SOURCE_ID
    }


def test_appeals_native_year_filter_and_missing_regular_pdf() -> None:
    artifacts = dc_calendar.parse_appeals_payload(fixture_json("appeals.json"))
    assert len(artifacts) == 3
    assert sum(item.artifact_type == "regular_calendar" for item in artifacts) == 1

    client = FixtureClient()
    result = dc_calendar.execute(
        parse_args("appeals", "--year", "2026"),
        client=client,
        log_results=False,
    )
    assert result.status == ResultStatus.OK
    assert len(result.records) == 3
    assert client.json_calls == [
        (
            dc_calendar.APPEALS_REST_URL,
            {"field_year_court_calendar_value[]": 2026},
        )
    ]
    assert all(
        row["calendar_year"] == 2026 for row in result.records
    )

    current = dc_calendar.execute(
        parse_args("appeals"),
        client=FixtureClient(),
        log_results=False,
    )
    assert current.records[-1]["artifact_type"] == "weekly_panel_calendar"


def test_filters_operation_returns_values_and_labels() -> None:
    result = dc_calendar.execute(
        parse_args("filters", "--calendar", "today"),
        client=FixtureClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.OK
    record = result.records[0]
    judge_filter = record["filters"]["select_fields"][0]
    assert judge_filter["name"] == "judges"
    assert {
        item["value"]: item["label"] for item in judge_filter["options"]
    }["10234"] == "Berkower, Risa"


def test_probe_reports_each_verified_operation_without_merging_coverage() -> None:
    result = dc_calendar.execute(
        parse_args("probe"),
        client=FixtureClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.OK
    operations = result.records[0]["operations"]
    assert set(operations) == {
        "today_html",
        "today_rest_snapshot",
        "criminal_html",
        "tax_artifacts",
        "appeals_rest_index",
    }
    assert operations["today_rest_snapshot"]["response_shape"] == (
        "full_current_array"
    )
    assert result.records[0]["transport"][
        "generic_custom_user_agent_observation"
    ] == "azure_gateway_http_403"


def test_client_sends_verified_browser_request_shape() -> None:
    session = FakeSession(
        [
            FakeResponse(
                text=fixture_text("today_page.html"),
                headers=RESPONSE_HEADERS,
            )
        ]
    )
    client = dc_calendar.DCCalendarClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )
    fetched = client.html(dc_calendar.TODAY_URL, params={"page": 0})

    assert fetched.text.startswith("<!doctype html>")
    assert session.calls[0]["headers"]["User-Agent"] == (
        dc_calendar.BROWSER_USER_AGENT
    )
    assert session.calls[0]["params"] == {"page": 0}


def test_parser_rejects_changed_table_headers() -> None:
    changed = fixture_text("today_page.html").replace(
        ">Case Type</a>",
        ">Matter Type</a>",
    )
    with pytest.raises(SourceSchemaError, match="neither the expected table"):
        dc_calendar.parse_calendar_html(changed, kind="today")
