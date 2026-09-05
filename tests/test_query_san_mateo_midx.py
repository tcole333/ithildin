from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_san_mateo_midx
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURE_DIR = Path("tests/fixtures/public_records/san_mateo_midx")
INDEX_HTML = (FIXTURE_DIR / "index.html").read_text(encoding="utf-8")
SEARCH_PAGE_1_HTML = (FIXTURE_DIR / "search_page_1.html").read_text(
    encoding="utf-8"
)
SEARCH_PAGE_2_HTML = (FIXTURE_DIR / "search_page_2.html").read_text(
    encoding="utf-8"
)
NO_RESULTS_HTML = (FIXTURE_DIR / "no_results.html").read_text(
    encoding="utf-8"
)


def _parse(*values: str) -> Namespace:
    return query_san_mateo_midx.build_parser().parse_args(list(values))


@dataclass
class FixtureResponse:
    text: str
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    url: str = query_san_mateo_midx.LANDING_URL


class QueueSession:
    def __init__(self, responses: list[FixtureResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FixtureResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError("unexpected MIDX request")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def _client(session: QueueSession) -> query_san_mateo_midx.MIDXClient:
    return query_san_mateo_midx.MIDXClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )


def _search_result(
    rows: tuple[query_san_mateo_midx.MIDXRow, ...] | None = None,
) -> query_san_mateo_midx.MIDXSearchResult:
    page = query_san_mateo_midx.parse_results_page(SEARCH_PAGE_2_HTML)
    return query_san_mateo_midx.MIDXSearchResult(
        rows=page.rows if rows is None else rows,
        total_reported=len(page.rows if rows is None else rows),
        source_total_pages=1,
        pages_fetched=1,
        current_as_of="July 28, 2026 at 05:30 AM",
        schema_fingerprint="a" * 64,
        source_url=query_san_mateo_midx.LOOKUP_URL,
    )


class FakeClient:
    def __init__(
        self,
        result: query_san_mateo_midx.MIDXSearchResult | None = None,
    ) -> None:
        self.result = result or _search_result()
        self.calls: list[tuple[str, Any]] = []

    def search(
        self,
        selection: dict[str, Any],
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> query_san_mateo_midx.MIDXSearchResult:
        self.calls.append(("search", dict(selection), limit, offset))
        return self.result

    def probe(self) -> query_san_mateo_midx.MIDXSearchResult:
        self.calls.append(("probe",))
        return self.result


def test_parser_exposes_native_searches_without_a_default_result_cap():
    search = _parse(
        "search",
        "--first-name",
        "Frank",
        "--last-name",
        "Creer",
        "--offset",
        "15",
        "--output",
        "creer.json",
    )
    case = _parse("case", "PRO116668-B", "--json")
    probe = _parse("probe", "--timeout", "4")

    assert search.command == "search"
    assert search.limit is None
    assert search.offset == 15
    assert search.output == "creer.json"
    assert case.case_number == "PRO116668-B"
    assert case.json_out is True
    assert probe.timeout == 4


def test_bootstrap_parses_all_tokenized_forms_and_source_timestamp():
    bootstrap = query_san_mateo_midx.parse_bootstrap(INDEX_HTML)

    assert set(bootstrap.forms) == {
        "casenumber",
        "partyname",
        "businessname",
        "filedate",
    }
    assert bootstrap.forms["casenumber"].hidden_values == {
        "5m2op": "ASC",
        "searchtype": "casenumber",
        "ct": "case-token",
    }
    assert bootstrap.forms["partyname"].visible_fields == (
        "firstname",
        "lastname",
    )
    assert bootstrap.forms["filedate"].action_url == (
        query_san_mateo_midx.LOOKUP_URL
    )
    assert bootstrap.current_as_of == "July 28, 2026 at 05:30 AM"
    assert len(bootstrap.schema_fingerprint) == 64


def test_bootstrap_reports_a_missing_native_form_as_source_change():
    changed = INDEX_HTML.replace('name="midxsearch4"', 'name="removed"').replace(
        'name="searchtype" value="filedate"',
        'name="searchtype" value="removed"',
    )
    with pytest.raises(
        query_san_mateo_midx.MIDXSourceChangedError,
        match="lacks one or more",
    ):
        query_san_mateo_midx.parse_bootstrap(changed)


def test_result_parser_preserves_native_fields_and_opaque_pagination():
    page = query_san_mateo_midx.parse_results_page(
        SEARCH_PAGE_1_HTML,
        source_url=query_san_mateo_midx.LOOKUP_URL,
    )

    assert page.total_reported == 4
    assert page.current_page == 1
    assert page.total_pages == 2
    assert page.next_url == (
        "https://web.sanmateocourt.org/midx/lookup.php?data=page-2"
    )
    assert [row.case_number for row in page.rows] == [
        "CIV12345",
        "CIV12345",
    ]
    assert page.rows[0].party_name == "ACME CORPORATION"
    assert page.rows[0].party_type == "P"
    assert page.rows[0].filing_date == "2026-07-23"
    assert page.rows[0].index_info_url == (
        "https://web.sanmateocourt.org/midx/lookup.php?data=case-a"
    )


def test_no_record_found_is_an_authoritative_empty_result():
    page = query_san_mateo_midx.parse_results_page(NO_RESULTS_HTML)

    assert page.authoritative_empty is True
    assert page.total_reported == 0
    assert page.rows == ()
    assert page.next_url is None


def test_client_uses_same_session_tokenized_post_and_fetches_all_pages():
    session = QueueSession(
        [
            FixtureResponse(INDEX_HTML),
            FixtureResponse(
                SEARCH_PAGE_1_HTML,
                url=query_san_mateo_midx.LOOKUP_URL,
            ),
            FixtureResponse(
                SEARCH_PAGE_2_HTML,
                url=(
                    "https://web.sanmateocourt.org/midx/"
                    "lookup.php?data=page-2"
                ),
            ),
        ]
    )
    client = _client(session)

    result = client.search(
        {
            "search_type": "casenumber",
            "casenumber": "CIV12345",
        }
    )

    assert len(result.rows) == 4
    assert result.total_reported == 4
    assert result.source_total_pages == 2
    assert result.pages_fetched == 2
    assert [call["method"] for call in session.calls] == [
        "GET",
        "POST",
        "GET",
    ]
    assert session.calls[0]["url"] == query_san_mateo_midx.LANDING_URL
    assert session.calls[1]["url"] == query_san_mateo_midx.LOOKUP_URL
    assert session.calls[1]["data"] == {
        "5m2op": "ASC",
        "searchtype": "casenumber",
        "ct": "case-token",
        "casenumber": "CIV12345",
        "Submit": "Submit",
    }
    assert session.calls[2]["url"].endswith("lookup.php?data=page-2")


def test_client_limit_and_offset_stop_after_enough_native_rows():
    session = QueueSession(
        [
            FixtureResponse(INDEX_HTML),
            FixtureResponse(
                SEARCH_PAGE_1_HTML,
                url=query_san_mateo_midx.LOOKUP_URL,
            ),
        ]
    )
    result = _client(session).search(
        {
            "search_type": "businessname",
            "businessname": "ACME",
        },
        offset=1,
        limit=1,
    )

    assert [row.party_name for row in result.rows] == ["ALICE SMITH"]
    assert result.total_reported == 4
    assert result.pages_fetched == 1
    assert len(session.calls) == 2


def test_client_retries_a_transient_status_with_bounded_policy():
    session = QueueSession(
        [
            FixtureResponse("", status_code=503),
            FixtureResponse(INDEX_HTML),
        ]
    )
    delays: list[float] = []
    client = query_san_mateo_midx.MIDXClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(
            max_attempts=2,
            backoff_initial=0,
        ),
        sleeper=delays.append,
    )

    bootstrap = client.bootstrap()

    assert bootstrap.forms["casenumber"].name == "midxsearch1"
    assert len(session.calls) == 2
    assert delays == [0]


def test_default_client_path_converts_browser_transport_rows():
    calls: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def browser_runner(selection: dict[str, Any], **kwargs: Any):
        calls.append((dict(selection), dict(kwargs)))
        return {
            "ok": True,
            "rows": [
                {
                    "case_number": "PRO116668-B",
                    "party_name": "GILBERT E. KARWICK",
                    "party_type": "P",
                    "filing_date": "2026-07-24",
                    "index_info_url": query_san_mateo_midx.ODYSSEY_URL,
                    "source_url": query_san_mateo_midx.LOOKUP_URL,
                }
            ],
            "total_reported": 3,
            "source_total_pages": 1,
            "pages_fetched": 1,
            "current_as_of": "July 28, 2026 at 05:30 AM",
            "source_url": query_san_mateo_midx.LOOKUP_URL,
        }

    client = query_san_mateo_midx.MIDXClient(
        browser_runner=browser_runner,
        minimum_interval=0.75,
        retry_policy=RetryPolicy(max_attempts=2),
    )
    result = client.search(
        {
            "search_type": "casenumber",
            "casenumber": "PRO116668-B",
        },
        limit=1,
    )
    client.close()

    assert result.total_reported == 3
    assert result.rows[0].filing_date == "2026-07-24"
    assert calls[0][1] == {
        "limit": 1,
        "offset": 0,
        "timeout": query_san_mateo_midx.DEFAULT_TIMEOUT,
        "minimum_interval": 0.75,
        "max_attempts": 2,
    }


@pytest.mark.parametrize(
    ("values", "search_type"),
    [
        (
            (
                "search",
                "--case-number",
                "PRO116668-B",
            ),
            "casenumber",
        ),
        (
            (
                "search",
                "--first-name",
                "Fr*",
                "--last-name",
                "Cr*",
            ),
            "partyname",
        ),
        (
            (
                "search",
                "--business-name",
                "Acme*",
            ),
            "businessname",
        ),
        (
            (
                "search",
                "--filed-from",
                "2026-07-20",
                "--filed-to",
                "2026-07-24",
            ),
            "filedate",
        ),
    ],
)
def test_selection_supports_each_native_search_mode(
    values: tuple[str, ...],
    search_type: str,
):
    selection = query_san_mateo_midx.search_selection(_parse(*values))
    assert selection["search_type"] == search_type


@pytest.mark.parametrize(
    ("values", "code"),
    [
        (("search",), "search_selector_required"),
        (
            (
                "search",
                "--case-number",
                "PRO116668-B",
                "--business-name",
                "Acme",
            ),
            "search_selector_required",
        ),
        (
            ("search", "--first-name", "Frank"),
            "incomplete_person_name",
        ),
        (
            ("search", "--business-name", "AB"),
            "business_name_too_short",
        ),
        (
            (
                "search",
                "--filed-from",
                "2026-07-20",
                "--filed-to",
                "2026-07-25",
            ),
            "filing_date_range_too_wide",
        ),
    ],
)
def test_selection_rejects_only_source_invalid_combinations(
    values: tuple[str, ...],
    code: str,
):
    with pytest.raises(query_san_mateo_midx.MIDXSelectionError) as caught:
        query_san_mateo_midx.search_selection(_parse(*values))
    assert caught.value.code == code


def test_normalization_groups_cases_and_stabilizes_duplicate_parties():
    page_one = query_san_mateo_midx.parse_results_page(SEARCH_PAGE_1_HTML)
    page_two = query_san_mateo_midx.parse_results_page(SEARCH_PAGE_2_HTML)
    search_result = query_san_mateo_midx.MIDXSearchResult(
        rows=page_one.rows + page_two.rows,
        total_reported=4,
        source_total_pages=2,
        pages_fetched=2,
        current_as_of="July 28, 2026 at 05:30 AM",
        schema_fingerprint="b" * 64,
        source_url=query_san_mateo_midx.LOOKUP_URL,
    )
    selection = {"search_type": "businessname", "businessname": "ACME"}

    records = query_san_mateo_midx.normalize_records(
        search_result,
        selection=selection,
    )
    repeated = query_san_mateo_midx.normalize_records(
        search_result,
        selection=selection,
    )

    assert records == repeated
    assert [record["raw_case_number"] for record in records] == [
        "CIV12345",
        "PRO54321",
    ]
    probate = records[1]
    assert probate["caption"] is None
    assert probate["case_type"] is None
    assert probate["filing_date"] == "2026-07-24"
    assert probate["docket_entries"] == []
    assert probate["documents"] == []
    assert [party["native_role"] for party in probate["parties"]] == ["O", "O"]
    assert [party["occurrence"] for party in probate["parties"]] == [1, 2]
    assert len(
        {party["native_party_id"] for party in probate["parties"]}
    ) == 2


def test_execute_returns_contract_envelope_and_logs_case_count(monkeypatch):
    logged: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        query_san_mateo_midx,
        "log_search",
        lambda *values: logged.append(values),
    )
    client = FakeClient()

    result = query_san_mateo_midx.execute(
        _parse(
            "search",
            "--first-name",
            "John",
            "--last-name",
            "Doe",
        ),
        client=client,
        access_decision={"allowed": True},
    )

    assert result.status == ResultStatus.OK
    assert len(result.records) == 1
    lineage = validate_envelope(result.to_dict())
    assert lineage["source_id"] == query_san_mateo_midx.SOURCE_ID
    assert logged[0][1:] == (query_san_mateo_midx.SOURCE_ID, 1)
    assert client.calls[0] == (
        "search",
        {
            "search_type": "partyname",
            "firstname": "John",
            "lastname": "Doe",
        },
        None,
        0,
    )


def test_execute_distinguishes_empty_results_from_selection_failure(monkeypatch):
    monkeypatch.setattr(
        query_san_mateo_midx,
        "log_search",
        lambda *_args: None,
    )
    empty = _search_result(rows=())

    no_results = query_san_mateo_midx.execute(
        _parse("case", "ZZZ99999"),
        client=FakeClient(empty),
    )
    invalid = query_san_mateo_midx.execute(
        _parse("search", "--first-name", "Frank"),
        client=FakeClient(empty),
    )

    assert no_results.status == ResultStatus.NO_RESULTS
    assert no_results.errors == ()
    assert invalid.status == ResultStatus.UNAVAILABLE
    assert invalid.errors[0].code == "incomplete_person_name"


def test_emit_writes_json_output(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        query_san_mateo_midx,
        "log_search",
        lambda *_args: None,
    )
    output_path = tmp_path / "midx.json"
    args = _parse(
        "case",
        "PRO54321",
        "--output",
        str(output_path),
    )
    result = query_san_mateo_midx.execute(args, client=FakeClient())

    query_san_mateo_midx._emit(result, args)

    assert output_path.is_file()
    assert '"source_id": "us-ca-san-mateo-midx"' in output_path.read_text()
    assert "saved to" in capsys.readouterr().out
