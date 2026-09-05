from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tools import query_pima_courts
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURE_DIR = Path("tests/fixtures/public_records/pima_courts")


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


@dataclass
class FakeResponse:
    url: str
    text: str = ""
    status_code: int = 200
    headers: dict[str, str] | None = None
    content: bytes | None = None

    def __post_init__(self) -> None:
        if self.headers is None:
            self.headers = {"Content-Type": "text/html; charset=utf-8"}
        if self.content is None:
            self.content = self.text.encode("utf-8")


class QueueSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        response = self.responses.pop(0)
        assert response.url == url
        return response

    def close(self) -> None:
        self.closed = True


def _client(session: QueueSession) -> query_pima_courts.PimaCourtClient:
    return query_pima_courts.PimaCourtClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )


def _parse(*values: str) -> Any:
    return query_pima_courts.build_parser().parse_args(list(values))


def test_parser_exposes_search_case_document_and_probe_commands():
    search = _parse(
        "search",
        "CHOMSKY",
        "--first-name",
        "NOAM",
        "--limit",
        "7",
        "--output",
        "search.json",
    )
    case = _parse(
        "case",
        "C20256501",
        "--last-name",
        "SAMPLE",
        "--json",
    )
    document = _parse(
        "document",
        "C20256501",
        "pima:document-row:abc",
        "filing.pdf",
        "--overwrite",
    )
    probe = _parse("probe", "--timeout", "4")

    assert search.command == "search"
    assert search.last_name == "CHOMSKY"
    assert search.first_name == "NOAM"
    assert search.limit == 7
    assert search.output == "search.json"
    assert case.case_number == "C20256501"
    assert case.last_name == "SAMPLE"
    assert case.json_out is True
    assert document.entry_id == "pima:document-row:abc"
    assert document.overwrite is True
    assert probe.timeout == 4


def test_bootstrap_parsers_resolve_only_the_stable_form_action():
    menu_url = query_pima_courts.parse_landing_menu_url(
        _fixture("landing.html"),
        response_url=query_pima_courts.BASE_URL,
    )
    form = query_pima_courts.parse_search_form(
        _fixture("menu.html"),
        menu_url=menu_url,
    )
    main_url = query_pima_courts.parse_main_frame_url(
        _fixture("search_post.html"),
        response_url=query_pima_courts.SEARCH_URL,
    )

    assert menu_url.endswith("/MENU_SESSION_TOKEN")
    assert form.search_url == query_pima_courts.SEARCH_URL
    assert form.hidden_fields == {
        "__VIEWSTATE": "fixture-viewstate",
        "__VIEWSTATEGENERATOR": "F943B1BE",
        "__EVENTVALIDATION": "fixture-validation",
    }
    assert main_url.endswith("/RESULT_SESSION_TOKEN")
    assert (
        query_pima_courts.parse_search_notice(
            _fixture("case_not_found_post.html")
        )
        == "Case Not Found"
    )


def test_name_result_parser_deduplicates_on_case_number_without_tokens():
    hits = query_pima_courts.parse_name_results(
        _fixture("name_results.html"),
        response_url=query_pima_courts.BASE_URL,
    )
    records, source_unique_count = (
        query_pima_courts.normalize_name_search_records(hits)
    )

    assert len(hits) == 3
    assert source_unique_count == 2
    assert len(records) == 2
    probate = records[0]
    assert probate["raw_case_number"] == "PB20210563"
    assert probate["matched_party_names"] == [
        "ALPHA SAMPLE",
        "SAMPLE PERSON",
    ]
    assert probate["source_result_row_count"] == 2
    assert probate["filing_date"] == "2021-04-01"
    assert "SESSION_TOKEN" not in json.dumps(records)
    assert hits[0].detail_url.endswith("/DETAIL_SESSION_TOKEN_A")


def test_case_detail_parses_parties_docket_and_derived_duplicate_ids():
    page = query_pima_courts.parse_case_detail(
        _fixture("case_detail.html"),
        response_url=(
            f"{query_pima_courts.BASE_URL}DETAIL_SESSION_TOKEN_CASE"
        ),
    )
    record = page.record

    assert record["raw_case_number"] == "PB20210563"
    assert record["source_internal_id"] == "1632792"
    assert record["source_internal_case_id"] == "1632792"
    assert record["filing_date"] == "2021-04-01"
    assert record["judge"] is None
    assert record["judge_raw"] == "No Judge Info"
    assert record["parties"][0]["role"] == "Fiduciary"
    assert record["parties"][0]["dob_iso"] == "1935-05"
    assert record["parties"][0]["dob_precision"] == "month"
    assert record["parties"][1]["dob_iso"] == "1934"
    assert record["parties"][1]["dob_precision"] == "year"

    first, duplicate, will = record["docket_entries"]
    assert first["native_entry_id"] != duplicate["native_entry_id"]
    assert (first["duplicate_occurrence"], duplicate["duplicate_occurrence"]) == (
        1,
        2,
    )
    assert first["document_available"] is True
    assert duplicate["document_available"] is False
    assert will["entry_subtype"] == "Last Will & Testament"
    assert list(page.document_urls) == [first["native_entry_id"]]
    assert page.document_urls[first["native_entry_id"]].endswith(
        "/PDF_SESSION_TOKEN_1"
    )
    assert "SESSION_TOKEN" not in json.dumps(record)

    repeated = query_pima_courts.parse_case_detail(
        _fixture("case_detail.html"),
        response_url=f"{query_pima_courts.BASE_URL}ANOTHER_TOKEN",
    )
    assert [
        entry["native_entry_id"] for entry in repeated.record["docket_entries"]
    ] == [
        entry["native_entry_id"] for entry in record["docket_entries"]
    ]


def test_criminal_detail_parses_disposition_rows_and_carries_party_name():
    page = query_pima_courts.parse_case_detail(
        _fixture("criminal_detail.html"),
        response_url=f"{query_pima_courts.BASE_URL}CRIMINAL_DETAIL_TOKEN",
    )
    record = page.record

    assert record["raw_case_number"] == "CR20253098"
    assert record["judge"] == "SAMPLE JUDGE"
    assert len(record["charges"]) == 2
    first, second = record["charges"]
    assert first["count"] == 1
    assert first["statute"] == "13-0000A1"
    assert first["disposition_date"] == "2025-08-18"
    assert first["disposition"] == "Court Dismissed"
    assert second["party_name"] == "SAMPLE DEFENDANT"
    assert second["preparatory_offense"] == "Attempt"


def test_client_posts_aspnet_state_and_follows_name_result_token():
    menu_url = f"{query_pima_courts.BASE_URL}MENU_SESSION_TOKEN"
    result_url = f"{query_pima_courts.BASE_URL}RESULT_SESSION_TOKEN"
    session = QueueSession(
        [
            FakeResponse(
                query_pima_courts.BASE_URL,
                _fixture("landing.html"),
            ),
            FakeResponse(menu_url, _fixture("menu.html")),
            FakeResponse(
                query_pima_courts.SEARCH_URL,
                _fixture("search_post.html"),
            ),
            FakeResponse(result_url, _fixture("name_results.html")),
        ]
    )

    page = _client(session).search_name("SAMPLE", first_name="ALPHA")

    assert len(page.hits) == 3
    post = session.calls[2]
    assert post["method"] == "POST"
    assert post["url"] == query_pima_courts.SEARCH_URL
    assert post["data"]["__VIEWSTATE"] == "fixture-viewstate"
    assert post["data"]["SearchGroup"] == "rdoName"
    assert post["data"]["txtLastName"] == "SAMPLE"
    assert post["data"]["txtFirstName"] == "ALPHA"
    assert session.calls[3]["url"] == result_url


def test_client_case_not_found_does_not_fetch_the_empty_main_frame():
    menu_url = f"{query_pima_courts.BASE_URL}MENU_SESSION_TOKEN"
    session = QueueSession(
        [
            FakeResponse(
                query_pima_courts.BASE_URL,
                _fixture("landing.html"),
            ),
            FakeResponse(menu_url, _fixture("menu.html")),
            FakeResponse(
                query_pima_courts.SEARCH_URL,
                _fixture("case_not_found_post.html"),
            ),
        ]
    )

    with pytest.raises(query_pima_courts.PimaCourtNotFoundError):
        _client(session).fetch_case("ZZ99999999")

    assert len(session.calls) == 3
    assert session.calls[2]["data"]["SearchGroup"] == "rdoCase"
    assert session.calls[2]["data"]["txtCaseNumber"] == "ZZ99999999"


def test_client_can_resolve_case_through_party_index_fallback():
    menu_url = f"{query_pima_courts.BASE_URL}MENU_SESSION_TOKEN"
    result_url = f"{query_pima_courts.BASE_URL}RESULT_SESSION_TOKEN"
    detail_url = f"{query_pima_courts.BASE_URL}DETAIL_SESSION_TOKEN_A"
    session = QueueSession(
        [
            FakeResponse(
                query_pima_courts.BASE_URL,
                _fixture("landing.html"),
            ),
            FakeResponse(menu_url, _fixture("menu.html")),
            FakeResponse(
                query_pima_courts.SEARCH_URL,
                _fixture("search_post.html"),
            ),
            FakeResponse(result_url, _fixture("empty_main.html")),
            FakeResponse(
                query_pima_courts.BASE_URL,
                _fixture("landing.html"),
            ),
            FakeResponse(menu_url, _fixture("menu.html")),
            FakeResponse(
                query_pima_courts.SEARCH_URL,
                _fixture("search_post.html"),
            ),
            FakeResponse(result_url, _fixture("name_results.html")),
            FakeResponse(detail_url, _fixture("case_detail.html")),
        ]
    )

    page = _client(session).fetch_case(
        "PB20210563",
        last_name="SAMPLE",
    )

    assert page.record["raw_case_number"] == "PB20210563"
    assert session.calls[2]["data"]["SearchGroup"] == "rdoCase"
    assert session.calls[6]["data"]["SearchGroup"] == "rdoName"
    assert session.calls[-1]["url"] == detail_url


def test_client_re_resolves_document_and_validates_pdf():
    parsed = query_pima_courts.parse_case_detail(
        _fixture("case_detail.html"),
        response_url=f"{query_pima_courts.BASE_URL}DETAIL_SESSION_TOKEN_CASE",
    )
    entry_id = next(iter(parsed.document_urls))
    menu_url = f"{query_pima_courts.BASE_URL}MENU_SESSION_TOKEN"
    detail_url = f"{query_pima_courts.BASE_URL}RESULT_SESSION_TOKEN"
    pdf_url = f"{query_pima_courts.BASE_URL}PDF_SESSION_TOKEN_1"
    pdf_bytes = (FIXTURE_DIR / "document.pdf").read_bytes()
    session = QueueSession(
        [
            FakeResponse(
                query_pima_courts.BASE_URL,
                _fixture("landing.html"),
            ),
            FakeResponse(menu_url, _fixture("menu.html")),
            FakeResponse(
                query_pima_courts.SEARCH_URL,
                _fixture("search_post.html"),
            ),
            FakeResponse(detail_url, _fixture("case_detail.html")),
            FakeResponse(
                pdf_url,
                status_code=200,
                headers={
                    "Content-Type": "application/pdf",
                    "Content-Disposition": (
                        "inline; filename=NOTICE TO CREDITORS.pdf"
                    ),
                    "ETag": '"fixture-etag"',
                },
                content=pdf_bytes,
            ),
        ]
    )

    fetch = _client(session).fetch_document("PB20210563", entry_id)

    assert fetch.entry_id == entry_id
    assert fetch.pdf.content == pdf_bytes
    assert fetch.pdf.media_type == "application/pdf"
    assert fetch.pdf.filename == "NOTICE TO CREDITORS.pdf"
    assert fetch.pdf.sha256 == query_pima_courts.hashlib.sha256(
        pdf_bytes
    ).hexdigest()
    assert session.calls[-1]["url"] == pdf_url


class FixtureClient:
    def __init__(self) -> None:
        self.case_page = query_pima_courts.parse_case_detail(
            _fixture("case_detail.html"),
            response_url=(
                f"{query_pima_courts.BASE_URL}DETAIL_SESSION_TOKEN_CASE"
            ),
        )

    def search_name(
        self,
        last_name: str,
        *,
        first_name: str | None = None,
    ) -> query_pima_courts.PimaSearchPage:
        del last_name, first_name
        return query_pima_courts.PimaSearchPage(
            hits=tuple(
                query_pima_courts.parse_name_results(
                    _fixture("name_results.html"),
                    response_url=query_pima_courts.BASE_URL,
                )
            )
        )

    def fetch_case(
        self,
        case_number: str,
        *,
        last_name: str | None = None,
        first_name: str | None = None,
    ) -> query_pima_courts.PimaCasePage:
        del case_number, last_name, first_name
        return self.case_page

    def fetch_document(
        self,
        case_number: str,
        entry_id: str,
        *,
        last_name: str | None = None,
        first_name: str | None = None,
    ) -> query_pima_courts.PimaDocumentFetch:
        del case_number, last_name, first_name
        content = (FIXTURE_DIR / "document.pdf").read_bytes()
        return query_pima_courts.PimaDocumentFetch(
            case_page=self.case_page,
            entry_id=entry_id,
            pdf=query_pima_courts.PimaPDF(
                content=content,
                media_type="application/pdf",
                filename="fixture.pdf",
                sha256=query_pima_courts.hashlib.sha256(content).hexdigest(),
                etag='"fixture-etag"',
            ),
        )

    def bootstrap(self) -> query_pima_courts.PimaSearchForm:
        return query_pima_courts.parse_search_form(
            _fixture("menu.html"),
            menu_url=f"{query_pima_courts.BASE_URL}MENU_SESSION_TOKEN",
        )


def test_execute_emits_valid_envelope_and_logs_unique_case_count(monkeypatch):
    logged: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        query_pima_courts,
        "log_search",
        lambda *args: logged.append(args),
    )

    result = query_pima_courts.execute(
        _parse("search", "SAMPLE"),
        client=FixtureClient(),
    )
    payload = result.to_dict()
    validate_envelope(payload)

    assert result.status == ResultStatus.OK
    assert len(result.records) == 2
    assert logged[-1][1:] == (query_pima_courts.SOURCE_ID, 2)
    assert "SESSION_TOKEN" not in json.dumps(payload)


def test_document_command_writes_pdf_and_projects_only_selected_entry(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(query_pima_courts, "log_search", lambda *args: None)
    client = FixtureClient()
    entry_id = next(iter(client.case_page.document_urls))
    destination = tmp_path / "filing.pdf"

    result = query_pima_courts.execute(
        _parse(
            "document",
            "PB20210563",
            entry_id,
            str(destination),
        ),
        client=client,
    )

    assert result.status == ResultStatus.OK
    assert destination.read_bytes().startswith(b"%PDF-")
    assert result.raw_artifact_refs == (str(destination.resolve()),)
    record = result.records[0]
    assert len(record["docket_entries"]) == 1
    assert record["docket_entries"][0]["native_entry_id"] == entry_id
    assert record["document_download"]["sha256"] == hashlib_sha256(
        destination.read_bytes()
    )


def hashlib_sha256(content: bytes) -> str:
    return query_pima_courts.hashlib.sha256(content).hexdigest()


def test_detail_header_change_is_an_explicit_source_changed_error():
    changed = _fixture("case_detail.html").replace(
        "<td>Document Caption</td>",
        "<td>Document Description</td>",
    )

    with pytest.raises(
        query_pima_courts.PimaCourtSourceChangedError
    ) as caught:
        query_pima_courts.parse_case_detail(
            changed,
            response_url=query_pima_courts.BASE_URL,
        )

    assert caught.value.code == "table_header_changed"
