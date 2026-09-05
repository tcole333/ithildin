from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tools import ingest_state_court_records
from tools import query_oregon_appellate_calendars as appellate_calendars


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_appellate_calendars"
)


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _json_fixture(name: str) -> dict[str, Any]:
    value = json.loads(_fixture(name))
    assert isinstance(value, dict)
    return value


class FixtureResponse:
    def __init__(
        self,
        body: str | dict[str, Any],
        *,
        url: str,
        status_code: int = 200,
        history: list["FixtureResponse"] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.url = url
        self.history = history or []
        self.headers = headers or {}
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self) -> Any:
        return json.loads(self.text)


class SequenceSession:
    def __init__(self, *responses: FixtureResponse) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> FixtureResponse:
        self.calls.append({"url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected GET {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        pass


def _client(
    spec: appellate_calendars.CalendarSource,
    *fixture_names: str,
) -> tuple[appellate_calendars.OregonAppellateCalendarClient, SequenceSession]:
    responses = [
        FixtureResponse(
            _json_fixture(name),
            url=(
                spec.items_url
                if index == 0
                else str(
                    (
                        _json_fixture(fixture_names[index - 1]).get(
                            "odata.nextLink"
                        )
                        or _json_fixture(fixture_names[index - 1]).get(
                            "@odata.nextLink"
                        )
                        or spec.items_url
                    )
                )
            ),
        )
        for index, name in enumerate(fixture_names)
    ]
    session = SequenceSession(*responses)
    return (
        appellate_calendars.OregonAppellateCalendarClient(
            session=session,
            minimum_interval=0,
        ),
        session,
    )


def _args(*values: str) -> Any:
    return appellate_calendars.build_parser().parse_args(list(values))


def _fetch(
    spec: appellate_calendars.CalendarSource,
    *fixture_names: str,
) -> appellate_calendars.CalendarFetch:
    client, _ = _client(spec, *fixture_names)
    return client.fetch(spec)


def test_sources_keep_legacy_and_current_routes_separately_attributed():
    coa = appellate_calendars.COURT_OF_APPEALS
    supreme = appellate_calendars.SUPREME_COURT

    assert coa.source_id == "us-or-court-of-appeals-calendar"
    assert supreme.source_id == "us-or-supreme-court-calendar"
    assert coa.source_id != supreme.source_id
    assert coa.legacy_url == "https://web.courts.oregon.gov/coadocket"
    assert supreme.legacy_url == "https://web.courts.oregon.gov/sclist"
    assert coa.page_url.endswith("/Pages/coa-calendar.aspx")
    assert supreme.page_url.endswith("/Pages/sc-calendar.aspx")
    assert coa.list_title == "ORCTrack"
    assert supreme.list_title == "Supreme Court Calendar"


@pytest.mark.parametrize(
    ("spec", "fixture_name", "expected_list", "expected_view"),
    [
        (
            appellate_calendars.COURT_OF_APPEALS,
            "coa_page.html",
            "/courts/appellate/go/Lists/ORCTrack",
            "CurrentNoGroup",
        ),
        (
            appellate_calendars.SUPREME_COURT,
            "supreme_page.html",
            "/courts/appellate/go/Lists/SupremeCourtCalendar",
            "Current",
        ),
    ],
)
def test_current_page_contract_preserves_distinct_list_and_view(
    spec: appellate_calendars.CalendarSource,
    fixture_name: str,
    expected_list: str,
    expected_view: str,
):
    contract = appellate_calendars.parse_page_contract(
        _fixture(fixture_name),
        spec,
    )

    assert contract["data_source"] == "list"
    assert contract["sharepoint_list_url"] == expected_list
    assert contract["sharepoint_view_name"] == expected_view
    assert contract["pagination_enabled"] is True
    assert contract["search_enabled"] is True


def test_page_contract_rejects_cross_court_provenance():
    with pytest.raises(
        appellate_calendars.SourceSchemaError,
        match="unexpected list or view",
    ):
        appellate_calendars.parse_page_contract(
            _fixture("coa_page.html"),
            appellate_calendars.SUPREME_COURT,
        )


@pytest.mark.parametrize(
    ("spec", "fixtures", "expected_ids", "next_key"),
    [
        (
            appellate_calendars.COURT_OF_APPEALS,
            ("coa_items_page_1.json", "coa_items_page_2.json"),
            (101, 102, 103),
            "odata.nextLink",
        ),
        (
            appellate_calendars.SUPREME_COURT,
            ("supreme_items_page_1.json", "supreme_items_page_2.json"),
            (201, 202, 203),
            "@odata.nextLink",
        ),
    ],
)
def test_list_client_follows_both_sharepoint_continuation_shapes(
    spec: appellate_calendars.CalendarSource,
    fixtures: tuple[str, str],
    expected_ids: tuple[int, ...],
    next_key: str,
):
    client, session = _client(spec, *fixtures)

    fetched = client.fetch(spec)

    assert fetched.item_ids == expected_ids
    assert fetched.pages_fetched == 2
    assert fetched.requests_made == 2
    assert len(fetched.schema_fingerprint) == 64
    assert session.calls[0]["params"]["$top"] == 100
    assert session.calls[0]["params"]["$orderby"] == "ID"
    if spec is appellate_calendars.SUPREME_COURT:
        assert session.calls[0]["params"]["$expand"] == "AttachmentFiles"
    assert session.calls[1]["params"] == {}
    assert _json_fixture(fixtures[0])[next_key] in session.calls[1]["url"]


def test_court_of_appeals_normalization_preserves_event_semantics():
    fetched = _fetch(
        appellate_calendars.COURT_OF_APPEALS,
        "coa_items_page_1.json",
        "coa_items_page_2.json",
    )

    records = appellate_calendars.normalize_cases(
        appellate_calendars.COURT_OF_APPEALS,
        fetched.rows,
        source_schema_fingerprint=fetched.schema_fingerprint,
        retrieval={"source_pagination_complete": True},
    )

    assert [record["raw_case_number"] for record in records] == [
        "A100001",
        "A100002",
        "A100003",
    ]
    first = records[0]
    assert first["canonical_ref"].startswith(
        "STATECOURT:us-or-court-of-appeals-calendar/"
    )
    assert first["court"]["court_id"] == "or-court-of-appeals"
    assert first["case_type"] == "Criminal - General"
    entry = first["docket_entries"][0]
    assert entry["event_type"] == "oral_argument"
    assert entry["event_code"] == "ORAL_ARGUMENT"
    assert entry["event_date"] == "2026-07-29"
    assert entry["event_time"] == "09:00"
    assert entry["event_datetime"] == "2026-07-29T09:00:00-07:00"
    assert entry["argument_format"] == "Oral Argument Remote"
    assert entry["panel"] == ["Aoyagi", "Egan", "Pagán"]
    assert entry["comments"] == "Remote argument."
    assert records[1]["docket_entries"][0]["event_type"] == "submission"


def test_supreme_normalization_preserves_issues_attorneys_and_brief_links():
    fetched = _fetch(
        appellate_calendars.SUPREME_COURT,
        "supreme_items_page_1.json",
        "supreme_items_page_2.json",
    )
    rows = [row for row in fetched.rows if row["ID"] == 202]

    records = appellate_calendars.normalize_cases(
        appellate_calendars.SUPREME_COURT,
        rows,
        source_schema_fingerprint=fetched.schema_fingerprint,
        retrieval={"source_pagination_complete": True},
    )

    assert len(records) == 1
    record = records[0]
    assert record["source_id"] == "us-or-supreme-court-calendar"
    assert record["raw_case_number"] == "S072119"
    assert record["case_number_variants"] == ["S072119", "A182119"]
    assert record["attorneys_text"] == (
        "Jane Lawyer on behalf of Petitioner\n"
        "John Counsel on behalf of Respondent"
    )
    assert record["issues_summary"] == (
        "Whether the source rule applies.\nMedia summary disclaimer."
    )
    entry = record["docket_entries"][0]
    assert entry["event_type"] == "oral_argument"
    assert entry["event_date"] == "2026-09-10"
    assert entry["event_time"] == "09:00"
    assert entry["panel"] == ["Meagan A. Flynn", "Rebecca A. Duncan"]
    assert entry["document_available"] is True
    assert len(entry["documents"]) == 2
    document = entry["documents"][0]
    assert document["document_type"] == "appellate_brief"
    assert document["mime_type"] == "application/pdf"
    assert document["file_retrievable"] is True
    assert document["source_url"].endswith(
        "/202/72119%20Brief%20-%20Opening.pdf"
    )


def test_combined_supreme_case_number_is_searchable_by_each_number():
    row = _json_fixture("supreme_items_page_2.json")["value"][0]

    assert appellate_calendars._matches_case_number(
        appellate_calendars.SUPREME_COURT,
        row,
        "S072976",
    )
    assert appellate_calendars._matches_case_number(
        appellate_calendars.SUPREME_COURT,
        row,
        "S072978",
    )
    assert appellate_calendars._matches_case_number(
        appellate_calendars.SUPREME_COURT,
        row,
        "A188129",
    )


class StaticClient:
    def __init__(self, fetched: appellate_calendars.CalendarFetch) -> None:
        self.fetched = fetched

    def fetch(
        self,
        _spec: appellate_calendars.CalendarSource,
    ) -> appellate_calendars.CalendarFetch:
        return self.fetched


def test_search_defaults_to_all_accessible_rows_without_a_local_cap(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        appellate_calendars,
        "_oregon_today",
        lambda: date(2026, 7, 29),
    )
    fetched = _fetch(
        appellate_calendars.SUPREME_COURT,
        "supreme_items_page_1.json",
        "supreme_items_page_2.json",
    )

    all_result = appellate_calendars.execute(
        _args("search", "--court", "supreme"),
        client=StaticClient(fetched),
        log_results=False,
    )
    current_result = appellate_calendars.execute(
        _args("search", "--court", "supreme", "--current"),
        client=StaticClient(fetched),
        log_results=False,
    )

    assert all_result.status.value == "ok"
    assert len(all_result.records) == 3
    assert all_result.query.query.requested_limit is None
    assert current_result.status.value == "ok"
    assert [record["raw_case_number"] for record in current_result.records] == [
        "S072119",
        "S072976 / S072978",
    ]


def test_case_filter_no_match_is_authoritative_empty():
    fetched = _fetch(
        appellate_calendars.COURT_OF_APPEALS,
        "coa_items_page_1.json",
        "coa_items_page_2.json",
    )

    result = appellate_calendars.execute(
        _args(
            "search",
            "--court",
            "coa",
            "--case-number",
            "A999999",
        ),
        client=StaticClient(fetched),
        log_results=False,
    )

    assert result.status.value == "no_results"
    assert result.records == ()
    assert result.errors == ()


def test_local_cursor_is_snapshot_bound():
    fetched = _fetch(
        appellate_calendars.COURT_OF_APPEALS,
        "coa_items_page_1.json",
        "coa_items_page_2.json",
    )
    first = appellate_calendars.execute(
        _args("search", "--court", "coa", "--limit", "1"),
        client=StaticClient(fetched),
        log_results=False,
    )

    second = appellate_calendars.execute(
        _args(
            "search",
            "--court",
            "coa",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=StaticClient(fetched),
        log_results=False,
    )

    assert first.status.value == "ok"
    assert first.records[0]["raw_case_number"] == "A100001"
    assert first.next_cursor is not None
    assert second.status.value == "ok"
    assert second.records[0]["raw_case_number"] == "A100002"

    changed_rows = [dict(row) for row in fetched.rows]
    changed_rows[0]["Modified"] = "2026-07-29T23:59:00Z"
    changed = replace(fetched, rows=tuple(changed_rows))
    stale = appellate_calendars.execute(
        _args(
            "search",
            "--court",
            "coa",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=StaticClient(changed),
        log_results=False,
    )

    assert stale.status.value == "source_changed"
    assert stale.errors[0].code == "cursor_snapshot_changed"


def _redirect_history(
    spec: appellate_calendars.CalendarSource,
) -> list[FixtureResponse]:
    return [
        FixtureResponse(
            "",
            url=spec.legacy_url,
            status_code=302,
            headers={
                "Location": (
                    "https://www.courts.oregon.gov/"
                    f"?aspxerrorpath=/{'coadocket' if spec.key == 'coa' else 'sclist'}"
                )
            },
        )
    ]


def _probe_client(
    spec: appellate_calendars.CalendarSource,
    *,
    declared_item_count: int | None = None,
) -> appellate_calendars.OregonAppellateCalendarClient:
    prefix = "coa" if spec is appellate_calendars.COURT_OF_APPEALS else "supreme"
    list_payload = _json_fixture(f"{prefix}_list.json")
    if declared_item_count is not None:
        list_payload["ItemCount"] = declared_item_count
    list_fixtures = (
        ("coa_items_page_1.json", "coa_items_page_2.json")
        if spec is appellate_calendars.COURT_OF_APPEALS
        else ("supreme_items_page_1.json", "supreme_items_page_2.json")
    )
    responses = [
        FixtureResponse(
            "<html><title>OJD Home</title></html>",
            url=(
                "https://www.courts.oregon.gov/Pages/default.aspx"
                "?aspxerrorpath=/legacy"
            ),
            history=_redirect_history(spec),
        ),
        FixtureResponse(
            _fixture(f"{prefix}_page.html"),
            url=spec.page_url,
        ),
        FixtureResponse(
            _json_fixture(f"{prefix}_view.json"),
            url=spec.view_url,
        ),
        FixtureResponse(
            _json_fixture(f"{prefix}_view_fields.json"),
            url=spec.view_fields_url,
        ),
        FixtureResponse(
            list_payload,
            url=spec.list_root,
        ),
        FixtureResponse(
            _json_fixture(list_fixtures[0]),
            url=spec.items_url,
        ),
        FixtureResponse(
            _json_fixture(list_fixtures[1]),
            url=str(
                _json_fixture(list_fixtures[0]).get("odata.nextLink")
                or _json_fixture(list_fixtures[0]).get("@odata.nextLink")
            ),
        ),
    ]
    return appellate_calendars.OregonAppellateCalendarClient(
        session=SequenceSession(*responses),
        minimum_interval=0,
    )


def test_probe_reports_legacy_migration_and_ui_view_truncation(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        appellate_calendars,
        "_oregon_today",
        lambda: date(2026, 7, 29),
    )

    result = appellate_calendars.execute(
        _args("probe", "--court", "coa"),
        client=_probe_client(appellate_calendars.COURT_OF_APPEALS),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert result.query.source.source_id == (
        appellate_calendars.COURT_OF_APPEALS_SOURCE_ID
    )
    probe = result.records[0]
    statuses = probe["checks"]["component_status"]
    assert statuses == {
        "legacy_entrypoint": "migrated",
        "current_official_page": "ok",
        "sharepoint_list_api": "ok",
        "official_page_view": "partial",
        "adapter_acquisition": "ok",
    }
    assert probe["checks"]["list_item_count"] == 3
    assert probe["checks"]["declared_list_item_count"] == 3
    assert probe["checks"]["declared_and_fetched_item_counts_match"] is True
    assert probe["checks"]["official_view_row_limit"] == 2
    assert probe["checks"]["official_view_may_truncate"] is True
    assert probe["checks"]["source_pagination_complete"] is True
    assert any("preserved all source pages" in warning for warning in result.warnings)


def test_supreme_probe_reports_current_view_and_attachment_value(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        appellate_calendars,
        "_oregon_today",
        lambda: date(2026, 7, 29),
    )

    result = appellate_calendars.execute(
        _args("probe", "--court", "supreme"),
        client=_probe_client(appellate_calendars.SUPREME_COURT),
        log_results=False,
    )

    assert result.status.value == "ok"
    probe = result.records[0]
    assert probe["checks"]["official_view_eligible_item_count"] == 2
    assert probe["checks"]["official_view_row_limit"] == 30
    assert probe["checks"]["official_view_may_truncate"] is False
    assert probe["checks"]["attachment_item_count"] == 1
    assert probe["checks"]["attachment_document_count"] == 2
    assert (
        probe["checks"]["component_status"]["official_page_view"]
        == "ok"
    )


def test_probe_is_partial_when_declared_list_count_does_not_match_traversal(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        appellate_calendars,
        "_oregon_today",
        lambda: date(2026, 7, 29),
    )

    result = appellate_calendars.execute(
        _args("probe", "--court", "coa"),
        client=_probe_client(
            appellate_calendars.COURT_OF_APPEALS,
            declared_item_count=4,
        ),
        log_results=False,
    )

    assert result.status.value == "partial"
    assert result.errors[0].code == "source_list_count_mismatch"
    assert result.records[0]["checks"]["component_status"][
        "sharepoint_list_api"
    ] == "partial"
    assert (
        result.records[0]["checks"][
            "declared_and_fetched_item_counts_match"
        ]
        is False
    )


def test_search_envelope_projects_cases_events_and_supreme_briefs(
    tmp_path: Path,
):
    fetched = _fetch(
        appellate_calendars.SUPREME_COURT,
        "supreme_items_page_1.json",
        "supreme_items_page_2.json",
    )

    result = appellate_calendars.execute(
        _args(
            "search",
            "--court",
            "supreme",
            "--case-number",
            "S072119",
        ),
        client=StaticClient(fetched),
        log_results=False,
    )
    envelope = result.to_dict()
    ingest_state_court_records.validate_envelope(envelope)
    report = ingest_state_court_records.ingest_envelope(
        envelope,
        court_db=tmp_path / "oregon-appellate-calendars.db",
    )

    assert report["projected"]["cases"] == 1
    assert report["projected"]["docket_entries"] == 1
    assert report["projected"]["documents"] == 2


def test_missing_list_field_is_explicit_source_change():
    payload = _json_fixture("coa_items_page_2.json")
    del payload["value"][0]["Panel"]
    session = SequenceSession(
        FixtureResponse(
            payload,
            url=appellate_calendars.COURT_OF_APPEALS.items_url,
        )
    )
    client = appellate_calendars.OregonAppellateCalendarClient(
        session=session,
        minimum_interval=0,
    )

    result = appellate_calendars.execute(
        _args("search", "--court", "coa"),
        client=client,
        log_results=False,
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "source_schema_changed"
    assert "missing expected fields" in result.errors[0].message
