from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.public_records_contract import ResultStatus
from tools.public_records_http import SourceSchemaError
from tools.query_denver_foreclosures import (
    DETAIL_URL,
    EXPECTED_DETAIL_SECTIONS,
    SEARCH_URL,
    DenverForeclosureClient,
    DenverForeclosureSelectionError,
    DownloadedDocument,
    ForeclosureDetail,
    _criteria_from_args,
    _cursor,
    _document_id,
    _emit,
    _parse_cursor,
    build_parser,
    execute,
    normalize_detail,
    normalize_search_row,
    parse_detail_page,
    parse_search_form,
    parse_search_page,
)


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "denver_foreclosures"
)
ALLOWED = {
    "allowed": True,
    "reason_code": "anonymous_html",
    "limits": {"minimum_interval_seconds": 0},
}


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(
        self,
        *,
        text: str = "",
        url: str = SEARCH_URL,
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
        content: bytes | None = None,
        content_disposition: str | None = None,
        history: tuple[object, ...] = (),
    ) -> None:
        self.text = text
        self.url = url
        self.status_code = status_code
        self.content = content if content is not None else text.encode()
        self.headers = {"Content-Type": content_type}
        if content_disposition is not None:
            self.headers["Content-Disposition"] = content_disposition
        self.history = history


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, object]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def client_for(responses: list[FakeResponse]) -> tuple[DenverForeclosureClient, FakeSession]:
    session = FakeSession(responses)
    client = DenverForeclosureClient(
        session=session,
        rate_limiter=SimpleNamespace(wait=lambda: None),
    )
    return client, session


def search_response(name: str) -> FakeResponse:
    return FakeResponse(text=fixture(name), url=SEARCH_URL)


def detail_response(name: str) -> FakeResponse:
    return FakeResponse(text=fixture(name), url=DETAIL_URL)


def fixture_detail() -> ForeclosureDetail:
    page_one = parse_search_page(fixture("results_page_1.html"), SEARCH_URL)
    address = parse_detail_page(fixture("detail_address.html"), DETAIL_URL)
    basics = parse_detail_page(fixture("detail_basics.html"), DETAIL_URL)
    documents = parse_detail_page(fixture("detail_documents.html"), DETAIL_URL)
    sections = {label: address for label in EXPECTED_DETAIL_SECTIONS}
    sections["Basics"] = basics
    sections["View Documents"] = documents
    return ForeclosureDetail(index_row=page_one.rows[0], sections=sections)


def test_parse_search_form_captures_contract_without_exposing_state() -> None:
    parsed = parse_search_form(fixture("search_form.html"), SEARCH_URL)
    assert parsed.action_url == SEARCH_URL
    assert parsed.status_values == ("", "NED Recorded", "Sold", "Withdrawn")
    assert parsed.expedited_values == ("-1", "0", "1")
    assert len(parsed.schema_fingerprint) == 64
    assert "fixture-viewstate" not in parsed.schema_fingerprint


def test_parse_search_form_detects_missing_webforms_state() -> None:
    broken = fixture("search_form.html").replace(
        'name="__EVENTVALIDATION"',
        'name="OLD_EVENTVALIDATION"',
    )
    with pytest.raises(SourceSchemaError, match="form state changed"):
        parse_search_form(broken, SEARCH_URL)


def test_parse_search_page_normalizes_native_rows_and_pager() -> None:
    page = parse_search_page(fixture("results_page_1.html"), SEARCH_URL)
    assert page.total_results == 3
    assert page.current_page == 1
    assert page.next_target and "TopPager" in page.next_target
    assert [row.foreclosure_number for row in page.rows] == [
        "2026-000418",
        "2026-000417",
    ]
    assert page.rows[0].balance_due_raw == "$38,341,090.99"
    assert page.rows[0].sale_date_raw == "11/12/2026"


def test_parse_search_page_distinguishes_valid_empty() -> None:
    page = parse_search_page(fixture("no_results.html"), SEARCH_URL)
    assert page.total_results == 0
    assert page.rows == ()
    assert page.next_target is None


def test_parse_search_page_detects_column_drift() -> None:
    broken = fixture("results_page_1.html").replace(
        "<th>Balance Due</th>",
        "<th>Debt</th>",
    )
    with pytest.raises(SourceSchemaError, match="columns changed"):
        parse_search_page(broken, SEARCH_URL)


def test_parse_detail_page_extracts_grouped_fields() -> None:
    page = parse_detail_page(fixture("detail_basics.html"), DETAIL_URL)
    assert page.foreclosure_number == "2026-000418"
    assert tuple(page.navigation) == EXPECTED_DETAIL_SECTIONS
    groups = {group.heading: dict(group.fields) for group in page.groups}
    assert groups["Basics"]["NED Reception #"] == "2026089324"
    assert (
        groups["Loan Information"]["Outstanding Principal Balance"]
        == "$38,341,090.99"
    )


def test_parse_detail_documents_uses_stable_filename_identity() -> None:
    first = parse_detail_page(fixture("detail_documents.html"), DETAIL_URL)
    second = parse_detail_page(fixture("detail_documents.html"), DETAIL_URL)
    assert len(first.documents) == 2
    assert first.documents[0].native_document_id == second.documents[0].native_document_id
    assert first.documents[0].native_document_id == _document_id(
        "2026-000418",
        "2026-000418 DATA SHEET.pdf",
    )
    assert first.documents[0].source_size_bytes == 89 * 1024
    assert first.documents[0].source_modified_at == "2026-07-29T08:20:37"
    assert "__VIEWSTATE" not in first.documents[0].source_url


def test_query_bound_cursor_rejects_different_search() -> None:
    cursor = _cursor(
        {"grantor": "Smith"},
        show_all=False,
        page=2,
        offset=3,
    )
    assert _parse_cursor(
        cursor,
        {"grantor": "Smith"},
        show_all=False,
    ) == (2, 3)
    with pytest.raises(DenverForeclosureSelectionError, match="different"):
        _parse_cursor(
            cursor,
            {"grantor": "Jones"},
            show_all=False,
        )


def test_search_requires_criteria_or_explicit_show_all() -> None:
    args = build_parser().parse_args(["search"])
    with pytest.raises(DenverForeclosureSelectionError, match="criterion"):
        _criteria_from_args(args)
    args = build_parser().parse_args(["search", "--show-all"])
    assert _criteria_from_args(args) == ({}, True)


def test_search_allows_independent_iso_date_selectors() -> None:
    args = build_parser().parse_args(
        ["search", "--ned-from", "2026-01-01"]
    )
    criteria, show_all = _criteria_from_args(args)
    assert criteria == {"ned_from": "2026-01-01"}
    assert show_all is False


def test_client_follows_all_native_pages_without_default_cap() -> None:
    client, session = client_for(
        [
            search_response("search_form.html"),
            search_response("results_page_1.html"),
            search_response("results_page_2.html"),
        ]
    )
    rows, next_cursor, final_page, skipped = client.search(
        {},
        show_all=True,
        limit=None,
        cursor=None,
    )
    assert [row.foreclosure_number for row in rows] == [
        "2026-000418",
        "2026-000417",
        "2026-000416",
    ]
    assert next_cursor is None
    assert final_page.current_page == 2
    assert skipped == 0
    assert [call["method"] for call in session.requests] == [
        "GET",
        "POST",
        "POST",
    ]
    assert session.requests[1]["data"][
        "ctl00$ctl00$MainContent$CustomContentPlaceHolder$btnShowAll"
    ] == "Show All"
    assert session.requests[2]["data"]["__EVENTTARGET"].endswith(
        "$TopPager$ctl01$Page"
    )


def test_client_can_reuse_verified_bootstrap_form() -> None:
    parsed_form = parse_search_form(fixture("search_form.html"), SEARCH_URL)
    client, session = client_for([search_response("results_page_1.html")])
    page = client.start_search({}, show_all=True, form=parsed_form)
    assert page.total_results == 3
    assert [call["method"] for call in session.requests] == ["POST"]


def test_client_limit_and_cursor_resume_mid_page() -> None:
    first_client, _session = client_for(
        [
            search_response("search_form.html"),
            search_response("results_page_1.html"),
        ]
    )
    rows, cursor, _page, _skipped = first_client.search(
        {},
        show_all=True,
        limit=1,
        cursor=None,
    )
    assert [row.foreclosure_number for row in rows] == ["2026-000418"]
    assert cursor is not None

    resumed_client, _session = client_for(
        [
            search_response("search_form.html"),
            search_response("results_page_1.html"),
            search_response("results_page_2.html"),
        ]
    )
    resumed, next_cursor, _page, skipped = resumed_client.search(
        {},
        show_all=True,
        limit=2,
        cursor=cursor,
    )
    assert [row.foreclosure_number for row in resumed] == [
        "2026-000417",
        "2026-000416",
    ]
    assert next_cursor is None
    assert skipped == 1


def test_client_detail_keeps_search_and_sections_in_one_session() -> None:
    section_responses = []
    for label in EXPECTED_DETAIL_SECTIONS[1:]:
        name = {
            "Basics": "detail_basics.html",
            "View Documents": "detail_documents.html",
        }.get(label, "detail_address.html")
        section_responses.append(detail_response(name))
    client, session = client_for(
        [
            search_response("search_form.html"),
            search_response("results_page_1.html"),
            detail_response("detail_address.html"),
            *section_responses,
        ]
    )
    detail = client.detail("2026-000418")
    assert detail is not None
    assert tuple(detail.sections) == EXPECTED_DETAIL_SECTIONS
    assert len(detail.documents) == 2
    assert len(session.requests) == 3 + len(EXPECTED_DETAIL_SECTIONS) - 1
    assert all(call["headers"].get("Cookie") is None for call in session.requests)
    assert session.requests[2]["data"]["__EVENTTARGET"].endswith("$linkBtn")


def test_probe_uses_sixteen_requests_and_exposes_no_session_state() -> None:
    section_responses = []
    for label in EXPECTED_DETAIL_SECTIONS[1:]:
        name = {
            "Basics": "detail_basics.html",
            "View Documents": "detail_documents.html",
        }.get(label, "detail_address.html")
        section_responses.append(detail_response(name))
    client, session = client_for(
        [
            search_response("search_form.html"),
            search_response("results_page_1.html"),
            search_response("search_form.html"),
            search_response("results_page_1.html"),
            detail_response("detail_address.html"),
            *section_responses,
        ]
    )
    probe = client.probe("2026-000418")
    assert len(session.requests) == 16
    assert probe["canonical_ref"].endswith(
        "/source-health/probe%3A2026-000418"
    )
    assert probe["source_url"] == SEARCH_URL
    assert probe["source_reported_total_results"] == 3
    assert probe["native_page_size"] == 2
    assert probe["detail_sections"] == list(EXPECTED_DETAIL_SECTIONS)
    assert probe["document_count"] == 2
    serialized = str(probe)
    assert "__VIEWSTATE" not in serialized
    assert "__EVENTVALIDATION" not in serialized
    assert "ASP.NET_SessionId" not in serialized


def test_client_download_accepts_verified_pdf_response() -> None:
    pdf = b"%PDF-1.4\nfixture\n%%EOF"
    client, _session = client_for(
        [
            FakeResponse(
                url=(
                    "https://denvergov.org/foreclosuresearch/"
                    "docviewer?fn=2026-000418+NED.tif"
                ),
                content_type="application/pdf",
                content=pdf,
                content_disposition='filename="2026-000418 NED.pdf"',
            )
        ]
    )
    downloaded = client.download(
        "https://denvergov.org/foreclosuresearch/"
        "docviewer?fn=2026-000418+NED.tif"
    )
    assert downloaded.content == pdf
    assert downloaded.media_type == "application/pdf"
    assert downloaded.filename == "2026-000418 NED.pdf"


def test_client_download_rejects_non_pdf_source_change() -> None:
    client, _session = client_for(
        [
            FakeResponse(
                url=(
                    "https://denvergov.org/foreclosuresearch/"
                    "docviewer?fn=2026-000418+NED.tif"
                ),
                content_type="text/html",
                content=b"<html>changed</html>",
            )
        ]
    )
    with pytest.raises(SourceSchemaError, match="did not return a PDF"):
        client.download(
            "https://denvergov.org/foreclosuresearch/"
            "docviewer?fn=2026-000418+NED.tif"
        )


def test_normalize_search_row_uses_native_case_identity() -> None:
    page = parse_search_page(fixture("results_page_1.html"), SEARCH_URL)
    record = normalize_search_row(
        page.rows[0],
        schema_value=page.schema_fingerprint,
    )
    assert record["record_kind"] == "foreclosure_case"
    assert record["record_scope"] == "index"
    assert record["foreclosure_number"] == "2026-000418"
    assert record["canonical_ref"].endswith("/2026-000418")
    assert record["balance_due"]["amount"] == "38341090.99"
    assert record["scheduled_sale_date"] == "2026-11-12"


def test_normalize_detail_preserves_sections_documents_and_recorder_joins() -> None:
    record = normalize_detail(fixture_detail())
    assert record["record_scope"] == "detail"
    assert record["current_owner"]["raw_name"] == "Santa Fe Drive Development, LLC"
    assert record["loan"]["outstanding_principal_balance"]["amount"] == "38341090.99"
    assert record["document_count"] == 2
    assert set(record["source_sections"]) == set(EXPECTED_DETAIL_SECTIONS)
    assert {
        item["reception_number"] for item in record["recorded_instruments"]
    } == {"2026089324", "2023117249"}


class HighLevelSearchClient:
    def __init__(self) -> None:
        page = parse_search_page(fixture("results_page_1.html"), SEARCH_URL)
        self.page = page
        self.closed = False

    def search(self, criteria, *, show_all, limit, cursor):
        assert criteria == {"grantor": "Santa Fe"}
        assert show_all is False
        assert limit is None
        assert cursor is None
        return list(self.page.rows), None, self.page, 0

    def close(self) -> None:
        self.closed = True


def test_execute_injects_catalog_decision_and_probe_logging_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_log(*_args, **_kwargs):
        raise AssertionError("log_search should not be called")

    monkeypatch.setattr(
        "tools.query_denver_foreclosures.log_search",
        fail_log,
    )
    args = build_parser().parse_args(["search", "--grantor", "Santa Fe"])
    result = execute(
        args,
        access_decision=ALLOWED,
        client=HighLevelSearchClient(),
        log_results=False,
    )
    assert result.status is ResultStatus.OK
    assert len(result.records) == 2
    query = result.query.to_dict()
    assert query["query"]["requested_limit"] is None
    assert query["query"]["metadata"]["access_decision"]["allowed"] is True
    serialized = result.to_dict()
    assert "__VIEWSTATE" not in str(serialized)
    assert "ASP.NET_SessionId" not in str(serialized)


def test_execute_logs_only_public_query_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    monkeypatch.setattr(
        "tools.query_denver_foreclosures.log_search",
        lambda query, source, count: calls.append((query, source, count)),
    )
    args = build_parser().parse_args(["search", "--grantor", "Santa Fe"])
    execute(
        args,
        access_decision=ALLOWED,
        client=HighLevelSearchClient(),
    )
    assert len(calls) == 1
    query, source, count = calls[0]
    assert source == "us-co-denver-public-trustee-gts"
    assert count == 2
    assert "__VIEWSTATE" not in query
    assert "__EVENTVALIDATION" not in query
    assert "ASP.NET_SessionId" not in query


def test_output_flag_writes_shared_result_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "tools.query_denver_foreclosures.log_search",
        lambda *_args, **_kwargs: None,
    )
    destination = tmp_path / "result.json"
    args = build_parser().parse_args(
        [
            "search",
            "--grantor",
            "Santa Fe",
            "--output",
            str(destination),
        ]
    )
    result = execute(
        args,
        access_decision=ALLOWED,
        client=HighLevelSearchClient(),
        log_results=False,
    )
    _emit(result, args)
    payload = json.loads(destination.read_text())
    assert payload["status"] == "ok"
    assert payload["records"][0]["record_kind"] == "foreclosure_case"


def test_execute_maps_valid_empty_to_no_results() -> None:
    class EmptyClient:
        def search(self, criteria, *, show_all, limit, cursor):
            page = parse_search_page(fixture("no_results.html"), SEARCH_URL)
            return [], None, page, 0

    args = build_parser().parse_args(
        ["search", "--foreclosure-number", "9999-999999"]
    )
    result = execute(
        args,
        access_decision=ALLOWED,
        client=EmptyClient(),
        log_results=False,
    )
    assert result.status is ResultStatus.NO_RESULTS
    assert result.errors == ()


def test_execute_maps_schema_drift_to_source_changed() -> None:
    class ChangedClient:
        def search(self, criteria, *, show_all, limit, cursor):
            raise SourceSchemaError("changed", url=SEARCH_URL)

    args = build_parser().parse_args(["search", "--grantor", "Smith"])
    result = execute(
        args,
        access_decision=ALLOWED,
        client=ChangedClient(),
        log_results=False,
    )
    assert result.status is ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "source_schema_changed"


def test_execute_documents_returns_case_with_nested_artifacts() -> None:
    class DetailClient:
        def detail(self, foreclosure_number: str) -> ForeclosureDetail:
            assert foreclosure_number == "2026-000418"
            return fixture_detail()

    args = build_parser().parse_args(["documents", "2026-000418"])
    result = execute(
        args,
        access_decision=ALLOWED,
        client=DetailClient(),
        log_results=False,
    )
    assert result.status is ResultStatus.OK
    assert result.records[0]["record_scope"] == "documents"
    assert result.records[0]["document_count"] == 2


def test_execute_download_writes_explicit_destination(tmp_path: Path) -> None:
    detail = fixture_detail()
    document = detail.documents[0]
    pdf = b"%PDF-1.4\nfixture\n%%EOF"

    class DownloadClient:
        def detail(self, foreclosure_number: str) -> ForeclosureDetail:
            return detail

        def download(self, source_url: str) -> DownloadedDocument:
            assert source_url == document.source_url
            return DownloadedDocument(
                content=pdf,
                source_url=source_url,
                media_type="application/pdf",
                filename="source.pdf",
            )

    destination = tmp_path / "record.pdf"
    args = build_parser().parse_args(
        [
            "download",
            "2026-000418",
            document.native_document_id,
            "--destination",
            str(destination),
        ]
    )
    result = execute(
        args,
        access_decision=ALLOWED,
        client=DownloadClient(),
        log_results=False,
    )
    assert result.status is ResultStatus.OK
    assert destination.read_bytes() == pdf
    assert result.records[0]["storage_path"] == str(destination.resolve())
    assert result.records[0]["sha256"]


def test_search_parser_has_no_implicit_limit() -> None:
    args = build_parser().parse_args(["search", "--show-all"])
    assert args.limit is None
    assert args.cursor is None


def test_build_parser_exposes_exact_search_and_document_operations() -> None:
    parser = build_parser()
    for command in ("search", "detail", "documents", "download", "probe"):
        args = parser.parse_args(
            (
                [command, "2026-000418"]
                if command in {"detail", "documents"}
                else (
                    [
                        "download",
                        "2026-000418",
                        "a" * 64,
                        "--destination",
                        "/tmp/fixture.pdf",
                    ]
                    if command == "download"
                    else [command, "--show-all"]
                    if command == "search"
                    else [command]
                )
            )
        )
        assert args.command == command
