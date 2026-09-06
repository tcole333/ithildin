from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest

from tools import query_colorado_judicial
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURES = Path(__file__).parent / "fixtures" / "colorado_judicial"
FORM_HTML = (FIXTURES / "bootstrap.html").read_text()
PAGE_1_FRAGMENT = (FIXTURES / "results_page_1.html").read_text()
PAGE_2_FRAGMENT = (FIXTURES / "results_page_2.html").read_text()
EMPTY_FRAGMENT = (FIXTURES / "no_results.html").read_text()

ALLOWED = {
    "allowed": True,
    "access_class": "B",
    "reason_code": "anonymous_public_route",
    "limits": {},
}


def _document(fragment: str = "") -> str:
    return f"<html><body>{FORM_HTML}{fragment}</body></html>"


BOOTSTRAP_HTML = _document()
PAGE_1_HTML = _document(PAGE_1_FRAGMENT)
PAGE_2_HTML = _document(PAGE_2_FRAGMENT)
EMPTY_HTML = _document(EMPTY_FRAGMENT)

QUERY_URL = (
    "https://www.coloradojudicial.gov/dockets?"
    "courthouse=16_civil&date_range=specific_date&"
    "specific_date=2026-07-29&name_type=individual&attorney_type=name"
)
CURSOR_EXAMPLE = (
    "colorado-judicial:v1:query:"
    f"{'a' * 64}:page:1:row:5"
)


class FakeResponse:
    def __init__(
        self,
        text: str = "",
        *,
        status_code: int = 200,
        content_type: str = "text/html; charset=UTF-8",
        url: str | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.text = text
        self.status_code = status_code
        self.url = url
        self.content = text.encode() if content is None else content
        self.headers = {"Content-Type": content_type, **(headers or {})}


class FakeSession:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((method, url, dict(kwargs)))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if response.url is None:
            params = kwargs.get("params")
            response.url = f"{url}?{urlencode(params)}" if params else url
        return response

    def close(self) -> None:
        self.closed = True


class NoWait:
    def wait(self) -> None:
        return None


def _client(responses: list[Any]) -> query_colorado_judicial.ColoradoJudicialClient:
    return query_colorado_judicial.ColoradoJudicialClient(
        session=FakeSession(responses),
        retry_policy=RetryPolicy(max_attempts=1),
        rate_limiter=NoWait(),
    )


def _parse(*values: str):
    return query_colorado_judicial.build_parser().parse_args(list(values))


def _page(
    html: str = PAGE_1_HTML,
    *,
    url: str = QUERY_URL,
) -> query_colorado_judicial.ColoradoDocketPage:
    return query_colorado_judicial.parse_docket_html(html, page_url=url)


def test_bootstrap_parser_captures_directory_without_transient_values():
    page = _page(BOOTSTRAP_HTML, url=query_colorado_judicial.DOCKET_URL)

    assert page.form_action == "/dockets"
    assert page.form_method == "post"
    assert page.result_state == "not_searched"
    assert [option.value for option in page.options["district"]] == ["-1", "2"]
    assert [option.value for option in page.options["courthouse"]] == [
        "",
        "16_civil",
        "16_criminal",
    ]
    assert "form_build_id" in page.form_fields
    public = query_colorado_judicial._directory_record(page)
    serialized = json.dumps(public)
    assert "TRANSIENT" not in serialized
    assert public["counts"]["courthouse"] == 3


def test_results_parser_preserves_source_rows_links_and_native_count():
    page = _page()

    assert page.result_state == "results"
    assert page.total_count == 3
    assert page.range_start == 1
    assert page.range_end == 2
    assert len(page.rows) == 2
    assert page.rows[0].case_number == "2025CV858"
    assert page.rows[0].calendar_name == "EXAMPLE ASPHALT CO LLC"
    assert page.rows[0].duration == "1 Hour(s)"
    assert page.rows[0].appearance_type == "IN PERSON"
    assert page.next_page_url is not None
    assert page.next_page_url.endswith("page=1")
    assert page.export_url is not None
    assert page.printable_url is not None


def test_final_page_and_valid_empty_are_distinct_states():
    final = _page(PAGE_2_HTML, url=f"{QUERY_URL}&page=1")
    empty = _page(EMPTY_HTML)

    assert final.result_state == "results"
    assert final.page_index == 1
    assert final.total_count == 3
    assert final.next_page_url is None
    assert len(final.rows) == 1
    assert empty.result_state == "no_results"
    assert empty.total_count == 0
    assert empty.rows == ()


def test_missing_form_and_malformed_count_are_source_changed():
    with pytest.raises(Exception) as missing:
        query_colorado_judicial.parse_docket_html("<html></html>")
    assert getattr(missing.value, "result_status", None) == ResultStatus.SOURCE_CHANGED

    malformed = PAGE_1_HTML.replace(
        "Showing <span>1-2</span> of 3 results.",
        "Found three records",
    )
    with pytest.raises(Exception) as count:
        _page(malformed)
    assert getattr(count.value, "result_status", None) == ResultStatus.SOURCE_CHANGED


def test_schema_fingerprint_ignores_page_rows_and_transient_form_value():
    first = _page()
    second = _page(PAGE_2_HTML, url=f"{QUERY_URL}&page=1")
    changed_token = _page(
        PAGE_1_HTML.replace(
            "form-TRANSIENT-DO-NOT-EXPOSE",
            "form-ANOTHER-TRANSIENT",
        )
    )

    assert first.schema_fingerprint == second.schema_fingerprint
    assert first.schema_fingerprint == changed_token.schema_fingerprint
    assert first.directory_fingerprint == second.directory_fingerprint


def test_search_parameters_resolve_ids_labels_and_all_source_filters():
    args = _parse(
        "search",
        "--judicial-district",
        "2nd Judicial District",
        "--county",
        "16",
        "--courthouse",
        "Denver City & County Bldg (Civil and Domestic Matters)",
        "--court-type",
        "D",
        "--division",
        "259",
        "--date",
        "2026-07-29",
        "--case-year",
        "2025",
        "--case-class",
        "CV",
        "--case-sequence",
        "858",
        "--party-first-name",
        "Raven",
        "--party-last-name",
        "Example",
        "--attorney-first-name",
        "Casey",
        "--attorney-last-name",
        "Counsel",
    )
    parameters = query_colorado_judicial.search_parameters(
        args,
        _page(BOOTSTRAP_HTML),
    )

    assert parameters == {
        "date_range": "specific_date",
        "name_type": "individual",
        "attorney_type": "name",
        "specific_date": "2026-07-29",
        "district": "2",
        "county": "16",
        "courthouse": "16_civil",
        "court": "D",
        "case_class": "CV",
        "division": "259",
        "four_digit_year": "2025",
        "case_sequence": "858",
        "first_name": "Raven",
        "last_name": "Example",
        "attorney_first_name": "Casey",
        "attorney_last_name": "Counsel",
    }


def test_business_and_bar_number_modes_match_source_radio_contract():
    business = _parse(
        "search",
        "--business-name",
        "Example LLC",
        "--date-range",
        "1_month",
    )
    attorney = _parse(
        "search",
        "--attorney-bar-number",
        "12345",
        "--date-range",
        "today",
    )
    directory = _page(BOOTSTRAP_HTML)

    assert query_colorado_judicial.search_parameters(
        business,
        directory,
    )["name_type"] == "company"
    assert query_colorado_judicial.search_parameters(
        attorney,
        directory,
    )["attorney_type"] == "number"


@pytest.mark.parametrize(
    "values,code",
    [
        (("search", "--date-range", "today"), "search_selector_required"),
        (
            (
                "search",
                "--business-name",
                "A",
                "--party-last-name",
                "B",
            ),
            "conflicting_party_filters",
        ),
        (
            (
                "search",
                "--attorney-bar-number",
                "123",
                "--attorney-last-name",
                "B",
            ),
            "conflicting_attorney_filters",
        ),
        (
            ("search", "--case-year", "26", "--case-sequence", "1"),
            "invalid_case_year",
        ),
        (
            ("search", "--case-year", "2026", "--case-sequence", "ABC"),
            "invalid_case_sequence",
        ),
        (
            ("search", "--courthouse", "Not a court"),
            "invalid_source_option",
        ),
    ],
)
def test_invalid_search_selections_are_explicit(values, code):
    args = _parse(*values)
    with pytest.raises(query_colorado_judicial.ColoradoJudicialSelectionError) as error:
        query_colorado_judicial.search_parameters(args, _page(BOOTSTRAP_HTML))
    assert error.value.code == code


def test_client_exhausts_native_pages_without_hidden_aggregate_cap():
    client = _client(
        [
            FakeResponse(PAGE_1_HTML, url=QUERY_URL),
            FakeResponse(PAGE_2_HTML, url=f"{QUERY_URL}&page=1"),
        ]
    )

    batch = client.search(
        {
            "courthouse": "16_civil",
            "date_range": "specific_date",
            "specific_date": "2026-07-29",
            "name_type": "individual",
            "attorney_type": "name",
        }
    )

    assert len(batch.rows) == 3
    assert batch.source_total_count == 3
    assert batch.pages_fetched == 2
    assert batch.next_cursor is None
    session = client.session
    assert session.calls[1][2]["params"]["page"] == 1


def test_caller_limit_and_cursor_resume_within_native_pages():
    parameters = {"courthouse": "16_civil"}
    first = _client([FakeResponse(PAGE_1_HTML, url=QUERY_URL)]).search(
        parameters,
        limit=1,
    )
    assert len(first.rows) == 1
    assert first.next_cursor == query_colorado_judicial._cursor(
        0,
        1,
        parameters=parameters,
    )

    resumed = _client(
        [
            FakeResponse(PAGE_1_HTML, url=QUERY_URL),
            FakeResponse(PAGE_2_HTML, url=f"{QUERY_URL}&page=1"),
        ]
    ).search(
        parameters,
        cursor=first.next_cursor,
    )
    assert [row.calendar_name for row in resumed.rows] == [
        "EXAMPLE, RAVEN",
        "DOE, JANE",
    ]
    assert resumed.next_cursor is None


def test_limit_at_native_page_boundary_returns_next_page_cursor():
    parameters = {"courthouse": "16_civil"}
    batch = _client([FakeResponse(PAGE_1_HTML, url=QUERY_URL)]).search(
        parameters,
        limit=2,
    )
    assert len(batch.rows) == 2
    assert batch.next_cursor == query_colorado_judicial._cursor(
        1,
        0,
        parameters=parameters,
    )


def test_cursor_is_bound_to_canonical_search_parameters():
    parameters = {
        "courthouse": "16_civil",
        "date_range": "specific_date",
        "specific_date": "2026-07-29",
    }
    first = _client([FakeResponse(PAGE_1_HTML, url=QUERY_URL)]).search(
        parameters,
        limit=1,
    )
    assert first.next_cursor is not None

    changed_client = _client([])
    with pytest.raises(
        query_colorado_judicial.ColoradoJudicialSelectionError,
    ) as error:
        changed_client.search(
            {
                **parameters,
                "specific_date": "2026-07-30",
            },
            cursor=first.next_cursor,
        )

    assert error.value.code == "cursor_query_mismatch"
    assert changed_client.session.calls == []

    reordered = {
        "specific_date": "2026-07-29",
        "date_range": "specific_date",
        "courthouse": "16_civil",
    }
    page, row = query_colorado_judicial._cursor_position(
        first.next_cursor,
        parameters=reordered,
    )
    assert (page, row) == (0, 1)


def test_invalid_and_out_of_range_cursors_are_selection_failures():
    with pytest.raises(query_colorado_judicial.ColoradoJudicialSelectionError):
        query_colorado_judicial._cursor_position("offset:20")

    client = _client([FakeResponse(PAGE_1_HTML, url=QUERY_URL)])
    parameters = {"courthouse": "16_civil"}
    with pytest.raises(query_colorado_judicial.ColoradoJudicialSelectionError) as error:
        client.search(
            parameters,
            cursor=query_colorado_judicial._cursor(
                0,
                9,
                parameters=parameters,
            ),
        )
    assert error.value.code == "cursor_out_of_range"


def test_normalization_has_stable_case_row_and_shared_hearing_identities():
    page = _page()
    first = query_colorado_judicial.normalize_row(
        page.rows[0],
        schema=page.schema_fingerprint,
        source_url=page.source_url,
    )
    second = query_colorado_judicial.normalize_row(
        page.rows[1],
        schema=page.schema_fingerprint,
        source_url=page.source_url,
    )
    repeated = query_colorado_judicial.normalize_row(
        page.rows[0],
        schema=page.schema_fingerprint,
        source_url=page.source_url,
    )

    assert first["record_kind"] == "docket_entry"
    assert first["canonical_ref"] == repeated["canonical_ref"]
    assert first["native_entry_id"] == repeated["native_entry_id"]
    assert first["case"]["canonical_ref"] == second["case"]["canonical_ref"]
    assert first["native_entry_id"] != second["native_entry_id"]
    assert first["hearing_id"] == second["hearing_id"]
    assert first["case"]["caption"] is None
    assert first["calendar_name"] == "EXAMPLE ASPHALT CO LLC"


def test_execute_search_returns_contract_envelope_and_does_not_log_probe_state():
    args = _parse(
        "search",
        "--courthouse",
        "16_civil",
        "--date",
        "2026-07-29",
    )
    client = _client(
        [
            FakeResponse(BOOTSTRAP_HTML),
            FakeResponse(PAGE_1_HTML, url=QUERY_URL),
            FakeResponse(PAGE_2_HTML, url=f"{QUERY_URL}&page=1"),
        ]
    )

    result = query_colorado_judicial.execute(
        args,
        access_decision=ALLOWED,
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert len(result.records) == 3
    assert result.query.source.source_id == query_colorado_judicial.SOURCE_ID
    serialized = json.dumps(result.to_dict())
    assert "form-TRANSIENT" not in serialized


def test_execute_valid_empty_is_no_results_not_unavailable():
    args = _parse(
        "search",
        "--case-year",
        "2026",
        "--case-class",
        "CV",
        "--case-sequence",
        "999999",
        "--date",
        "2026-07-29",
    )
    result = query_colorado_judicial.execute(
        args,
        access_decision=ALLOWED,
        client=_client(
            [
                FakeResponse(BOOTSTRAP_HTML),
                FakeResponse(EMPTY_HTML, url=QUERY_URL),
            ]
        ),
        log_results=False,
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_execute_selection_and_access_failures_are_structured():
    args = _parse("search", "--date-range", "today")
    selection = query_colorado_judicial.execute(
        args,
        access_decision=ALLOWED,
        client=_client([FakeResponse(BOOTSTRAP_HTML)]),
        log_results=False,
    )
    denied = query_colorado_judicial.execute(
        args,
        access_decision={
            "allowed": False,
            "reason_code": "manual_route",
            "reason": "Use reviewed manual route",
            "result_status": "manual_required",
        },
        client=_client([]),
        log_results=False,
    )

    assert selection.status == ResultStatus.UNAVAILABLE
    assert selection.errors[0].code == "search_selector_required"
    assert denied.errors[0].code == "manual_route"


def test_export_204_is_explicitly_unavailable_not_an_empty_search():
    args = _parse(
        "export",
        "--courthouse",
        "16_civil",
        "--date",
        "2026-07-29",
    )
    result = query_colorado_judicial.execute(
        args,
        access_decision=ALLOWED,
        client=_client(
            [
                FakeResponse(BOOTSTRAP_HTML),
                FakeResponse(PAGE_1_HTML, url=QUERY_URL),
                FakeResponse("", status_code=204, content=b""),
            ]
        ),
        log_results=False,
    )

    assert result.status == ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "source_export_unavailable"
    assert result.records == ()


def test_export_artifact_can_be_saved_with_hash_and_provenance(tmp_path):
    destination = tmp_path / "dockets.csv"
    args = _parse(
        "export",
        "--courthouse",
        "16_civil",
        "--date",
        "2026-07-29",
        str(destination),
    )
    result = query_colorado_judicial.execute(
        args,
        access_decision=ALLOWED,
        client=_client(
            [
                FakeResponse(BOOTSTRAP_HTML),
                FakeResponse(PAGE_1_HTML, url=QUERY_URL),
                FakeResponse(
                    "",
                    content=b"case_number,date\n2025CV858,2026-07-29\n",
                    content_type="text/csv",
                    headers={
                        "Content-Disposition": 'attachment; filename="dockets.csv"'
                    },
                ),
            ]
        ),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert destination.read_bytes().startswith(b"case_number")
    assert result.records[0]["record_kind"] == "source_generated_export"
    assert result.records[0]["storage_path"] == str(destination.resolve())
    assert result.raw_artifact_refs == (str(destination.resolve()),)


def test_probe_treats_export_204_as_observed_condition_not_probe_failure():
    args = _parse(
        "probe",
        "--courthouse",
        "16_civil",
        "--date",
        "2026-07-29",
    )
    result = query_colorado_judicial.execute(
        args,
        access_decision=ALLOWED,
        client=_client(
            [
                FakeResponse(BOOTSTRAP_HTML),
                FakeResponse(PAGE_1_HTML, url=QUERY_URL),
                FakeResponse(PAGE_1_HTML, url=QUERY_URL),
                FakeResponse("", status_code=204, content=b""),
            ]
        ),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    probe = result.records[0]
    assert probe["record_kind"] == "source_health_check"
    assert probe["export_link_advertised"] is True
    assert probe["export_status"] == "unavailable"
    assert probe["source_total_count"] == 3


def test_log_results_false_skips_search_log(monkeypatch):
    args = _parse("courts")
    monkeypatch.setattr(
        query_colorado_judicial,
        "log_search",
        lambda *_args: pytest.fail("log_search should not be called"),
    )
    result = query_colorado_judicial.execute(
        args,
        access_decision=ALLOWED,
        client=_client([FakeResponse(BOOTSTRAP_HTML)]),
        log_results=False,
    )
    assert result.status == ResultStatus.OK


def test_parser_exposes_exact_cli_filter_names_and_optional_limit_cursor():
    args = _parse(
        "search",
        "--judicial-district",
        "2",
        "--county",
        "16",
        "--courthouse",
        "16_civil",
        "--court-type",
        "D",
        "--division",
        "259",
        "--date-range",
        "1_month",
        "--case-year",
        "2025",
        "--case-class",
        "CV",
        "--case-sequence",
        "858",
        "--party-first-name",
        "Raven",
        "--party-last-name",
        "Example",
        "--attorney-first-name",
        "Casey",
        "--attorney-last-name",
        "Counsel",
        "--limit",
        "25",
        "--cursor",
        CURSOR_EXAMPLE,
        "--output",
        "/tmp/colorado-dockets.json",
    )

    assert args.command == "search"
    assert args.judicial_district == "2"
    assert args.party_first_name == "Raven"
    assert args.attorney_last_name == "Counsel"
    assert args.limit == 25
    assert args.cursor == CURSOR_EXAMPLE
    assert str(args.output) == "/tmp/colorado-dockets.json"


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_CO_JUDICIAL") != "1",
    reason="set RUN_LIVE_CO_JUDICIAL=1 for the official live probe",
)
def test_live_form_directory_and_replayable_search_contract():
    client = query_colorado_judicial.ColoradoJudicialClient()
    try:
        directory = client.bootstrap()
        args = _parse("probe")
        parameters = query_colorado_judicial.search_parameters(
            args,
            directory,
            probe_defaults=True,
        )
        batch = client.search(parameters, limit=1)
    finally:
        client.close()

    assert len(query_colorado_judicial._offered_options(directory, "district")) >= 23
    assert len(query_colorado_judicial._offered_options(directory, "county")) >= 64
    assert len(query_colorado_judicial._offered_options(directory, "courthouse")) >= 70
    assert batch.first_page.result_state in {"results", "no_results"}
    assert batch.pages_fetched == 1
