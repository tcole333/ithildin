from __future__ import annotations

import hashlib
from argparse import Namespace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_texas_appellate
from tools.ingest_state_court_records import ingest_envelope, validate_envelope
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = Path("tests/fixtures/public_records/texas_appellate")
SEARCH_PAGE_1_HTML = (FIXTURE_DIR / "search_page_1.html").read_text(
    encoding="utf-8"
)
SEARCH_PAGE_2_HTML = (FIXTURE_DIR / "search_page_2.html").read_text(
    encoding="utf-8"
)
SEARCH_CAPPED_HTML = (FIXTURE_DIR / "search_capped.html").read_text(
    encoding="utf-8"
)
CASE_DETAIL_HTML = (FIXTURE_DIR / "case_detail.html").read_text(
    encoding="utf-8"
)
CASE_URL = (
    "https://search.txcourts.gov/"
    "Case.aspx?cn=03-25-00287-CV&coa=coa03"
)


def _parse(*values: str) -> Namespace:
    return query_texas_appellate.build_parser().parse_args(list(values))


def _criteria(query: str = "Tesla") -> dict[str, Any]:
    return {
        "query": query,
        "scope": "style",
        "style_other": None,
        "case_type": "both",
        "exclude_inactive": False,
        "date_from": None,
        "date_to": None,
        "courts": ("all",),
        "originating_coa": None,
        "county": None,
        "trial_court": None,
    }


@dataclass
class FixtureResponse:
    text: str = ""
    content: bytes = b""
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    url: str = query_texas_appellate.SEARCH_URL


class QueueSession:
    def __init__(self, responses: list[FixtureResponse]) -> None:
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def mount(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def request(self, method: str, url: str, **kwargs: Any) -> FixtureResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError("unexpected TAMES request")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


CASE_PAGE = query_texas_appellate.parse_case_page(
    CASE_DETAIL_HTML,
    source_url=CASE_URL,
    expected_case_number="03-25-00287-CV",
    expected_court_code="coa03",
)
assert CASE_PAGE is not None


class FakeTAMESClient:
    def __init__(
        self,
        *,
        search_page: query_texas_appellate.TAMESSearchPage | None = None,
        case_page: query_texas_appellate.TAMESCasePage | None = CASE_PAGE,
        pdf: bytes = b"%PDF-1.7\nfixture",
    ) -> None:
        self.search_page = search_page or query_texas_appellate.parse_search_page(
            SEARCH_PAGE_1_HTML
        )
        self.case_page = case_page
        self.pdf = pdf
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def search_pages(
        self,
        criteria: dict[str, Any],
        *,
        target_page: int,
        limit: int,
        offset: int,
    ):
        self.calls.append(
            (
                "search_pages",
                {
                    "criteria": dict(criteria),
                    "target_page": target_page,
                    "limit": limit,
                    "offset": offset,
                },
            )
        )
        rows = list(self.search_page.rows[offset : offset + limit])
        next_offset = offset + len(rows)
        return (
            rows,
            self.search_page,
            target_page,
            next_offset,
        )

    def case(self, case_number: str, *, court_code: str):
        self.calls.append(
            (
                "case",
                {"case_number": case_number, "court_code": court_code},
            )
        )
        return self.case_page

    def download(self, source_url: str, native_document_id: str):
        self.calls.append(
            (
                "download",
                {
                    "source_url": source_url,
                    "native_document_id": native_document_id,
                },
            )
        )
        return query_texas_appellate.TAMESDownload(
            native_document_id=native_document_id,
            source_url=source_url,
            content=self.pdf,
            media_type="application/pdf",
            raw_content_type="Application/pdf; charset=binary",
            filename="notice.pdf",
        )

    def probe(self):
        self.calls.append(("probe", {}))
        return {
            "source_url": query_texas_appellate.SEARCH_URL,
            "form_action": "./CaseSearch.aspx?coa=cossup",
            "court_labels": list(query_texas_appellate.COURT_NAMES.values()),
            "county_option_count": 255,
            "trial_court_option_count": 1142,
            "schema_fingerprint": "a" * 64,
        }


def _execute(args: Namespace, monkeypatch, *, client=None):
    monkeypatch.setattr(
        query_texas_appellate,
        "log_search",
        lambda *_args, **_kwargs: None,
    )
    return query_texas_appellate.execute(
        args,
        client=client or FakeTAMESClient(),
    )


def test_parser_exposes_search_case_docket_documents_download_and_probe():
    search = _parse(
        "search",
        "Tesla",
        "--scope",
        "style",
        "--court",
        "coa03",
        "--county",
        "Travis",
        "--date-from",
        "2025-01-01",
        "--date-to",
        "2026-01-31",
        "--limit",
        "137",
        "--cursor",
        "fixture-cursor",
        "--output",
        "results.json",
    )
    case = _parse("case", "03-25-00287-CV", "--json")
    docket = _parse("docket", "03-25-00287-CV")
    documents = _parse("documents", "03-25-00287-CV")
    download = _parse(
        "download",
        "03-25-00287-CV",
        "document-1",
        "document.pdf",
    )
    probe = _parse("probe", "--timeout", "4")

    assert search.command == "search"
    assert search.courts == ["coa03"]
    assert search.county == "Travis"
    assert search.limit == 137
    assert search.output == "results.json"
    assert case.json_out is True
    assert docket.command == "docket"
    assert documents.command == "documents"
    assert download.destination == Path("document.pdf")
    assert probe.timeout == 4


def test_search_parser_preserves_native_fields_and_pager_state():
    page = query_texas_appellate.parse_search_page(SEARCH_PAGE_1_HTML)

    assert page.current_page == 1
    assert page.total_pages == 2
    assert page.total_reported == 3
    assert page.source_ceiling_reached is False
    assert page.next_control_name is not None
    assert len(page.schema_fingerprint) == 64
    first, second = page.rows
    assert first.case_number == "26-0797"
    assert first.court_code == "cossup"
    assert first.filed_date == "2026-07-27"
    assert first.coa_case_numbers == (
        "14-26-00393-CV",
        "14-25-00034-CV",
    )
    assert second.case_number == "03-25-00287-CV"
    assert second.court_code == "coa03"
    assert second.trial_case_number == "D-1-GN-24-008508"
    assert second.trial_county == "Travis"

    second_page = query_texas_appellate.parse_search_page(
        SEARCH_PAGE_2_HTML
    )
    assert second_page.current_page == 2
    assert second_page.next_control_name is None


def test_webforms_pagination_posts_live_state_and_returns_all_rows():
    session = QueueSession(
        [
            FixtureResponse(text=SEARCH_PAGE_1_HTML),
            FixtureResponse(text=SEARCH_PAGE_1_HTML),
            FixtureResponse(text=SEARCH_PAGE_2_HTML),
        ]
    )
    client = query_texas_appellate.TexasTAMESClient(
        session=session,
        minimum_interval=0,
    )

    rows, page, next_page, next_offset = client.search_pages(
        _criteria(),
        target_page=1,
        limit=3,
        offset=0,
    )

    assert [row.case_number for row in rows] == [
        "26-0797",
        "03-25-00287-CV",
        "05-22-01054-CV",
    ]
    assert (page.current_page, next_page, next_offset) == (2, 2, 1)
    assert [call["method"] for call in session.calls] == [
        "GET",
        "POST",
        "POST",
    ]
    first_post = session.calls[1]
    assert first_post["data"][
        "ctl00$ContentPlaceHolder1$txtStyle1"
    ] == "Tesla"
    assert first_post["data"][
        "ctl00$ContentPlaceHolder1$chkAllCourts"
    ] == "on"
    next_post = session.calls[2]
    assert next_post["data"]["__VIEWSTATE"] == "fixture-page-1"
    assert (
        next_post["data"][
            "ctl00$ContentPlaceHolder1$grdCases$ctl00$ctl03$ctl01$ctl03"
        ]
        == " "
    )


def test_single_trial_case_match_redirects_to_detail_and_remains_a_search_row():
    session = QueueSession(
        [
            FixtureResponse(text=SEARCH_PAGE_1_HTML),
            FixtureResponse(text=CASE_DETAIL_HTML, url=CASE_URL),
        ]
    )
    client = query_texas_appellate.TexasTAMESClient(
        session=session,
        minimum_interval=0,
    )
    criteria = {
        **_criteria("D-1-GN-24-008508"),
        "scope": "trial-case-number",
        "county": "Travis",
    }

    rows, page, next_page, next_offset = client.search_pages(
        criteria,
        target_page=1,
        limit=25,
        offset=0,
    )

    assert len(rows) == 1
    assert rows[0].case_number == "03-25-00287-CV"
    assert rows[0].court_code == "coa03"
    assert rows[0].trial_case_number == "D-1-GN-24-008508"
    assert rows[0].raw["detail_redirect"] is True
    assert page.total_reported == 1
    assert (next_page, next_offset) == (1, 1)


def test_search_respects_caller_limit_and_emits_query_bound_cursor(
    monkeypatch,
):
    client = FakeTAMESClient()

    result = _execute(
        _parse("search", "Tesla", "--limit", "1"),
        monkeypatch,
        client=client,
    )
    payload = result.to_dict()
    validate_envelope(payload)

    assert payload["status"] == "ok"
    assert len(payload["records"]) == 1
    assert payload["next_cursor"].startswith("tx-tames:v1:page:1:offset:1:")
    record = payload["records"][0]
    assert record["source_internal_id"] == "cossup:26-0797"
    assert record["canonical_ref"].endswith(
        "/tx-appellate-cossup/26-0797/case"
    )

    criteria = client.calls[0][1]["criteria"]
    cursor = query_texas_appellate._cursor(criteria, 1, 1)
    other = {**criteria, "query": "Different"}
    with pytest.raises(
        query_texas_appellate.TAMESSelectionError,
        match="different search",
    ):
        query_texas_appellate._parse_cursor(cursor, other)


def test_adapter_forwards_large_caller_limit_without_adding_a_total_cap(
    monkeypatch,
):
    client = FakeTAMESClient()

    _execute(
        _parse("search", "Tesla", "--limit", "137"),
        monkeypatch,
        client=client,
    )

    assert client.calls[0][1]["limit"] == 137


def test_source_result_ceiling_is_explicit_partial_with_records(
    monkeypatch,
):
    capped = query_texas_appellate.parse_search_page(SEARCH_CAPPED_HTML)
    client = FakeTAMESClient(search_page=capped)

    result = _execute(
        _parse("search", "Smith", "--limit", "1"),
        monkeypatch,
        client=client,
    )

    assert result.status is ResultStatus.PARTIAL
    assert len(result.records) == 1
    assert result.errors[0].code == "source_result_ceiling"
    assert result.errors[0].details["source_result_ceiling"] == 1000
    assert result.next_cursor is not None


def test_case_parser_normalizes_parties_events_calendar_trial_and_documents():
    page = CASE_PAGE
    record = query_texas_appellate.normalize_case(page)

    assert record["raw_case_number"] == "03-25-00287-CV"
    assert record["caption"] == "Tesla Insurance Company v. Karla Roberson"
    assert record["filing_date"] == "2025-04-25"
    assert [party["role"] for party in record["parties"]] == [
        "Appellee",
        "Appellant",
    ]
    assert len(record["parties"][0]["attorneys"]) == 2
    assert len(record["docket_entries"]) == 2
    first_event = record["docket_entries"][0]
    assert first_event["event_date"] == "2026-01-22"
    assert first_event["document_available"] is True
    assert first_event["native_entry_id"].startswith(
        "03-25-00287-CV:event:"
    )
    document = first_event["documents"][0]
    assert (
        document["native_document_id"]
        == "bc16a831-998e-449f-9d28-84b61486178b"
    )
    assert document["media_id"] == "f70e423d-a658-43a0-9bec-c73064bdcff2"
    assert document["file_size"] == 659 * 1024
    assert record["calendar_events"] == [
        {
            "set_date": "2025-09-08",
            "calendar_type": "At Issue",
            "reason_set": "Holding",
        }
    ]
    assert record["originating_court_cases"] == [
        {
            "case_number": "D-1-GN-24-008508",
            "county": "Travis",
            "court": "250th District Court",
            "judge": "Honorable J. David Phillips",
            "reporter": "Jamie Foley",
        }
    ]
    assert len(record["case_relations"]) == 1
    relation = record["case_relations"][0]
    assert relation["native_relation_id"].startswith(
        "coa03:03-25-00287-CV:originating-trial:"
    )
    assert record["judicial_assignments"] == []
    assert {
        key: relation[key]
        for key in (
            "relation_type",
            "raw_case_number",
            "court_name",
            "county",
            "judge",
            "reporter",
            "source_url",
        )
    } == {
        "relation_type": "originating_trial_case",
        "raw_case_number": "D-1-GN-24-008508",
        "court_name": "250th District Court",
        "county": "Travis",
        "judge": "Honorable J. David Phillips",
        "reporter": "Jamie Foley",
        "source_url": CASE_URL,
    }
    assert len(record["case_events"]) == 1
    calendar_event = record["case_events"][0]
    assert calendar_event["native_event_id"].startswith(
        "03-25-00287-CV:calendar:"
    )
    assert {
        key: calendar_event[key]
        for key in (
            "event_type",
            "event_date",
            "disposition",
            "assertion_kind",
            "calendar_type",
            "reason_set",
        )
    } == {
        "event_type": "calendar_setting",
        "event_date": "2025-09-08",
        "disposition": "Holding",
        "assertion_kind": "docket_metadata",
        "calendar_type": "At Issue",
        "reason_set": "Holding",
    }
    reparsed = query_texas_appellate.parse_case_page(
        CASE_DETAIL_HTML,
        source_url=CASE_URL,
    )
    assert reparsed is not None
    assert (
        reparsed.docket_entries[0]["native_entry_id"]
        == first_event["native_entry_id"]
    )
    reparsed_record = query_texas_appellate.normalize_case(reparsed)
    assert (
        reparsed_record["case_relations"][0]["native_relation_id"]
        == relation["native_relation_id"]
    )
    assert (
        reparsed_record["case_events"][0]["native_event_id"]
        == calendar_event["native_event_id"]
    )


def test_case_envelope_validates_and_projects_to_state_court_store(
    tmp_path,
    monkeypatch,
):
    result = _execute(
        _parse("case", "03-25-00287-CV"),
        monkeypatch,
    )
    payload = result.to_dict()
    validate_envelope(payload)

    ingested = ingest_envelope(
        payload,
        court_db=tmp_path / "courts.db",
    )

    assert ingested["status"] == "ingested"
    assert ingested["projected"]["courts"] == 1
    assert ingested["projected"]["cases"] == 1
    assert ingested["projected"]["related_courts"] == 1
    assert ingested["projected"]["related_cases"] == 1
    assert ingested["projected"]["case_relations"] == 1
    assert ingested["projected"]["parties"] == 2
    assert ingested["projected"]["attorneys"] == 3
    assert ingested["projected"]["representations"] == 3
    assert ingested["projected"]["judicial_officers"] == 1
    assert ingested["projected"]["assignments"] == 1
    assert ingested["projected"]["docket_entries"] == 2
    assert ingested["projected"]["case_events"] == 1
    assert ingested["projected"]["documents"] == 1


def test_document_download_selects_case_link_and_records_hash(
    tmp_path,
    monkeypatch,
):
    client = FakeTAMESClient()
    destination = tmp_path / "notice.pdf"
    document_id = "bc16a831-998e-449f-9d28-84b61486178b"

    result = _execute(
        _parse(
            "download",
            "03-25-00287-CV",
            document_id,
            str(destination),
        ),
        monkeypatch,
        client=client,
    )
    payload = result.to_dict()
    validate_envelope(payload)
    record = payload["records"][0]

    assert destination.read_bytes() == client.pdf
    assert record["native_document_id"] == document_id
    assert record["sha256"] == hashlib.sha256(client.pdf).hexdigest()
    assert record["byte_count"] == len(client.pdf)
    assert record["mime_type"] == "application/pdf"
    assert record["raw_content_type"] == "Application/pdf; charset=binary"
    assert payload["raw_artifact_refs"] == [str(destination.resolve())]
    assert [name for name, _kwargs in client.calls] == ["case", "download"]


@pytest.mark.parametrize(
    ("case_number", "court_code"),
    [
        ("03-25-00287-CV", "coa03"),
        ("PD-0123-26", "coscca"),
        ("WR-99,999-01", "coscca"),
        ("26-0797", "cossup"),
    ],
)
def test_case_number_infers_court(case_number: str, court_code: str):
    assert query_texas_appellate.infer_court_code(case_number) == court_code


def test_schema_change_and_missing_case_are_distinct_from_empty_search():
    with pytest.raises(
        query_texas_appellate.TAMESRequestError,
        match="expected form/results",
    ):
        query_texas_appellate.parse_search_page("<html><body>changed</body></html>")

    missing = query_texas_appellate.parse_case_page(
        "<html><body>Case not found</body></html>",
        source_url=CASE_URL,
    )
    assert missing is None
