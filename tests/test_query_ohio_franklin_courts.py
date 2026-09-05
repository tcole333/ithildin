from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.query_ohio_franklin_courts import (
    BASE_URL,
    CASE_SEARCH_URL,
    DOCUMENT_URL,
    DOCKET_URL,
    NAME_SEARCH_URL,
    FranklinCourtClient,
    FranklinPartyWindowSpec,
    FranklinSourceChangedError,
    build_parser,
    execute,
    finalize_case_page,
    parse_case_detail_initial,
    parse_case_number,
    parse_disclaimer_action,
    parse_party_search_results,
)


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_franklin_courts"
)


class FakeResponse:
    def __init__(
        self,
        *,
        text: str = "",
        url: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        payload: Any = None,
    ) -> None:
        self.text = text
        self.url = url
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content if content is not None else text.encode()
        self._payload = payload

    def json(self) -> Any:
        if self._payload is not None:
            return self._payload
        return json.loads(self.text)


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text()


def fixture_json(name: str) -> dict[str, Any]:
    return json.loads(fixture_text(name))


def fixture_pdf() -> bytes:
    return bytes.fromhex(fixture_text("document.pdf.hex").strip())


def parsed_fixture_case():
    requested = parse_case_number("22CV3098")
    return parse_case_detail_initial(
        fixture_text("case_detail.html"),
        requested_case=requested,
    )


def party_window(
    *,
    filed_from: str | None = "2020-05-19",
    filed_to: str | None = "2020-05-19",
    court_category: str = "civil",
    native_row_count: int = 25,
) -> FranklinPartyWindowSpec:
    from datetime import date

    return FranklinPartyWindowSpec(
        last_name="WEXNER",
        first_name=None,
        middle_initial=None,
        court_category=court_category,
        filed_from=(date.fromisoformat(filed_from) if filed_from else None),
        filed_to=(date.fromisoformat(filed_to) if filed_to else None),
        native_row_count=native_row_count,
    )


def test_case_number_preserves_input_and_normalizes_realauction_spelling() -> None:
    parsed = parse_case_number("22CV3098")

    assert parsed.input_raw == "22CV3098"
    assert parsed.sequence_raw == "3098"
    assert parsed.sequence_normalized == "003098"
    assert parsed.normalized == "22CV003098"
    assert parse_case_number("2022 CV 003098").normalized == "22CV003098"


def test_disclaimer_action_uses_dynamic_official_route() -> None:
    action = parse_disclaimer_action(
        fixture_text("disclaimer.html"),
        response_url=BASE_URL,
    )

    assert action == (
        "https://fcdcfcjs.co.franklin.oh.us/"
        "CaseInformationOnline/acceptDisclaimer?fixture-session-token"
    )


def test_party_parser_preserves_lower_bound_spillover_and_identity_scope() -> None:
    parsed = parse_party_search_results(
        fixture_text("name_results_complete.html"),
        window=party_window(),
    )

    assert parsed.coverage_complete is True
    assert parsed.completion_reason == "ordered_spillover"
    assert parsed.source_buffer_truncated is False
    assert parsed.source_row_count == 3
    assert parsed.matched_row_count == 1
    assert [record["matched_query"] for record in parsed.records] == [
        True,
        False,
        False,
    ]
    match = parsed.records[0]
    assert match["record_kind"] == "case_index_occurrence"
    assert match["normalized_case_number"] == "20CV003259"
    assert match["display_case_number"] == "20 CV 003259"
    assert match["raw_name"] == "WEXNER, LESLIE H"
    assert match["party_role"] == "DF"
    assert match["filing_date"] == "2020-05-19"
    assert match["query_fingerprint"] == parsed.query_fingerprint
    assert match["native_occurrence_id"].endswith(":000001")
    assert match["source_metadata"]["native_row_id_published"] is False
    assert [record["response_ordinal"] for record in parsed.records] == [
        1,
        2,
        3,
    ]


def test_party_parser_preserves_exact_duplicate_source_rows() -> None:
    parsed = parse_party_search_results(
        fixture_text("name_results_duplicates.html"),
        window=party_window(filed_from=None, filed_to=None),
    )

    first, second = parsed.records[:2]
    assert first["raw"] == second["raw"]
    assert first["normalized_case_number"] == second["normalized_case_number"]
    assert first["native_occurrence_id"] != second["native_occurrence_id"]
    assert first["response_ordinal"] == 1
    assert second["response_ordinal"] == 2
    assert parsed.matched_row_count == 2
    assert parsed.coverage_complete is True


def test_party_parser_surfaces_native_buffer_cut_without_a_cursor() -> None:
    parsed = parse_party_search_results(
        fixture_text("name_results_boundary.html"),
        window=party_window(native_row_count=350),
    )

    assert parsed.source_row_count == 3
    assert parsed.complete_row_count == 2
    assert parsed.incomplete_row_count == 1
    assert parsed.source_buffer_truncated is True
    assert parsed.coverage_complete is False
    assert parsed.ended_in_matching_rows is True
    assert all(record["matched_query"] for record in parsed.records)


def test_party_name_command_uses_three_request_session_and_emits_spillover() -> None:
    session = FakeSession(
        [
            FakeResponse(text=fixture_text("disclaimer.html"), url=BASE_URL),
            FakeResponse(
                text=fixture_text("welcome.html"),
                url=f"{BASE_URL}Welcome.jsp",
            ),
            FakeResponse(
                text=fixture_text("name_results_complete.html"),
                url=NAME_SEARCH_URL,
            ),
        ]
    )
    client = FranklinCourtClient(session=session, minimum_interval=0)
    args = build_parser().parse_args(
        [
            "name",
            "WEXNER",
            "--first-name",
            "LESLIE",
            "--middle-initial",
            "H",
            "--court",
            "civil",
            "--filed-from",
            "2020-05-19",
            "--filed-to",
            "05/19/2020",
            "--native-row-count",
            "25",
        ]
    )

    result = execute(args, client=client, record_search=False)

    assert result.status.value == "ok"
    assert result.next_cursor is None
    assert len(result.records) == 3
    assert sum(record["matched_query"] for record in result.records) == 1
    assert len(session.requests) == 3
    assert session.requests[2]["url"] == NAME_SEARCH_URL
    assert session.requests[2]["data"] == {
        "lname": "WEXNER",
        "fname": "LESLIE",
        "mint": "H",
        "selType": "Civil",
        "caseYear": "",
        "caseYear_h": "",
        "caseType": "AP",
        "caseType_h": "",
        "caseSeq": "",
        "caseSeq_h": "",
        "attyIdx": "",
        "advFlag": "show",
        "reallySubmit": "true",
        "personType": "P",
        "attyNum": "",
        "txtCalendar1": "05/19/2020",
        "txtCalendar2": "05/19/2020",
        "recs": "25",
    }


def test_party_name_command_marks_unresolved_buffer_window_partial() -> None:
    session = FakeSession(
        [
            FakeResponse(text=fixture_text("disclaimer.html"), url=BASE_URL),
            FakeResponse(
                text=fixture_text("welcome.html"),
                url=f"{BASE_URL}Welcome.jsp",
            ),
            FakeResponse(
                text=fixture_text("name_results_boundary.html"),
                url=NAME_SEARCH_URL,
            ),
        ]
    )
    client = FranklinCourtClient(session=session, minimum_interval=0)
    args = build_parser().parse_args(
        ["search", "WEXNER", "--court", "civil", "--native-row-count", "350"]
    )

    result = execute(args, client=client, record_search=False)

    assert result.status.value == "partial"
    assert result.next_cursor is None
    assert len(result.records) == 2
    assert {error.code for error in result.errors} == {
        "party_coverage_unresolved",
        "party_source_buffer_truncated",
    }


def test_exhaustive_party_search_partitions_dates_and_keeps_terminal_rows() -> None:
    session = FakeSession(
        [
            FakeResponse(text=fixture_text("disclaimer.html"), url=BASE_URL),
            FakeResponse(
                text=fixture_text("welcome.html"),
                url=f"{BASE_URL}Welcome.jsp",
            ),
            FakeResponse(
                text=fixture_text("name_results_boundary.html"),
                url=NAME_SEARCH_URL,
            ),
            FakeResponse(
                text=fixture_text("name_results_complete.html"),
                url=NAME_SEARCH_URL,
            ),
            FakeResponse(
                text=fixture_text("name_results_boundary.html"),
                url=NAME_SEARCH_URL,
            ),
        ]
    )
    client = FranklinCourtClient(session=session, minimum_interval=0)

    search = client.search_parties(
        last_name="WEXNER",
        court_category="civil",
        filed_from="2020-05-19",
        filed_to="2020-05-20",
        native_row_count=350,
        exhaustive=True,
    )

    assert len(session.requests) == 5
    assert len(search.windows) == 2
    assert len(search.records) == 5
    assert search.coverage_complete is False
    assert search.unresolved_windows == (
        {
            "last_name": "WEXNER",
            "first_name": None,
            "middle_initial": None,
            "court_category": "civil",
            "filed_from": "2020-05-20",
            "filed_to": "2020-05-20",
            "native_row_count": 350,
            "reason": "source_buffer_boundary",
            "source_row_count": 3,
            "complete_row_count": 2,
            "incomplete_row_count": 1,
            "matched_row_count": 2,
            "verified_continuation": False,
        },
    )
    party_requests = session.requests[2:]
    assert [request["data"]["txtCalendar1"] for request in party_requests] == [
        "05/19/2020",
        "05/19/2020",
        "05/20/2020",
    ]
    assert [request["data"]["txtCalendar2"] for request in party_requests] == [
        "05/20/2020",
        "05/19/2020",
        "05/20/2020",
    ]
    assert len({record["query_fingerprint"] for record in search.records}) == 2


def test_same_day_all_courts_partitions_into_native_categories() -> None:
    children = FranklinCourtClient._partition_party_window(
        party_window(court_category="all")
    )

    assert [child.court_category for child in children] == [
        "appeals",
        "civil",
        "criminal",
        "domestic",
    ]
    assert all(child.filed_from == child.filed_to for child in children)


def test_probe_contract_adds_party_sentinel_with_exactly_five_requests() -> None:
    docket_page = fixture_json("docket_page_2.json")
    session = FakeSession(
        [
            FakeResponse(text=fixture_text("disclaimer.html"), url=BASE_URL),
            FakeResponse(
                text=fixture_text("welcome.html"),
                url=f"{BASE_URL}Welcome.jsp",
            ),
            FakeResponse(
                text=fixture_text("name_results_complete.html"),
                url=NAME_SEARCH_URL,
            ),
            FakeResponse(
                text=fixture_text("case_detail.html"),
                url=CASE_SEARCH_URL,
            ),
            FakeResponse(
                text=json.dumps(docket_page),
                payload=docket_page,
                url=DOCKET_URL,
                headers={"Content-Type": "application/json"},
            ),
        ]
    )
    client = FranklinCourtClient(
        session=session,
        minimum_interval=0,
        request_budget=5,
    )

    snapshot = client.probe_contract()

    assert snapshot.request_count == 5
    assert snapshot.party_sentinel_case_number == "20CV003259"
    assert snapshot.party_matching_count == 1
    assert snapshot.party_coverage_complete is True
    assert snapshot.party_result_field_names[0:3] == (
        "CASE",
        "CASE TYPE",
        "NAME",
    )
    assert "recs" in snapshot.party_search_field_names
    assert [request["url"] for request in session.requests] == [
        BASE_URL,
        (
            "https://fcdcfcjs.co.franklin.oh.us/"
            "CaseInformationOnline/acceptDisclaimer?fixture-session-token"
        ),
        NAME_SEARCH_URL,
        CASE_SEARCH_URL,
        DOCKET_URL,
    ]
    assert session.requests[2]["data"]["txtCalendar1"] == "05/19/2020"
    assert session.requests[2]["data"]["txtCalendar2"] == "05/19/2020"
    assert session.requests[2]["data"]["recs"] == "25"


def test_parse_and_finalize_keeps_docket_and_document_identities_separate() -> None:
    parsed = parsed_fixture_case()
    page_2 = fixture_json("docket_page_2.json")
    from tools.query_ohio_franklin_courts import parse_docket_ajax

    later_rows, next_key = parse_docket_ajax(page_2, source_page_no=2)
    page = finalize_case_page(
        parsed,
        all_docket_rows=[*parsed.docket_rows, *later_rows],
        native_page_count=2,
    )
    record = page.record

    assert next_key is None
    assert record["query_case_number_raw"] == "22CV3098"
    assert record["source_case_number_raw"] == "22CV003098"
    assert record["display_case_number"] == "22 CV 003098"
    assert record["normalized_case_number"] == "22CV003098"
    assert record["docket_retrieval"] == {
        "pagination": "source_next_key_until_empty",
        "native_page_count": 2,
        "entry_count": 6,
        "document_count": 2,
        "exhausted": True,
    }

    notice, confirmation = record["docket_entries"][:2]
    assert notice["native_entry_id"] != confirmation["native_entry_id"]
    assert notice["document_ids"] == confirmation["document_ids"]
    shared_document_id = notice["document_ids"][0]
    assert shared_document_id.startswith("franklin:document:")
    assert shared_document_id not in {
        notice["native_entry_id"],
        confirmation["native_entry_id"],
    }
    shared_document = next(
        document
        for document in record["documents"]
        if document["native_document_id"] == shared_document_id
    )
    assert shared_document["docket_entry_ids"] == [
        notice["native_entry_id"],
        confirmation["native_entry_id"],
    ]

    duplicates = [
        entry
        for entry in record["docket_entries"]
        if entry["description"] == "MISCELLANEOUS PAPER"
    ]
    assert [entry["duplicate_occurrence"] for entry in duplicates] == [1, 2]
    assert duplicates[0]["native_entry_id"] != duplicates[1]["native_entry_id"]

    serialized = json.dumps(record)
    assert "fixture-coordinate" not in serialized
    assert set(page.document_coordinates) == {
        document["native_document_id"] for document in record["documents"]
    }


def test_client_exhausts_native_docket_pages_without_a_local_result_cap() -> None:
    docket_page = fixture_json("docket_page_2.json")
    session = FakeSession(
        [
            FakeResponse(
                text=fixture_text("disclaimer.html"),
                url=BASE_URL,
            ),
            FakeResponse(
                text=fixture_text("welcome.html"),
                url=f"{BASE_URL}Welcome.jsp",
            ),
            FakeResponse(
                text=fixture_text("case_detail.html"),
                url=CASE_SEARCH_URL,
            ),
            FakeResponse(
                text=json.dumps(docket_page),
                payload=docket_page,
                url=DOCKET_URL,
                headers={"Content-Type": "application/json"},
            ),
        ]
    )
    client = FranklinCourtClient(
        session=session,
        minimum_interval=0,
    )

    page = client.fetch_case("22CV3098")

    assert len(page.record["docket_entries"]) == 6
    assert page.record["docket_retrieval"]["native_page_count"] == 2
    assert page.record["docket_retrieval"]["exhausted"] is True
    assert len(session.requests) == 4
    assert session.requests[1]["url"].endswith(
        "acceptDisclaimer?fixture-session-token"
    )
    assert session.requests[2]["data"]["caseSeq"] == "003098"
    assert session.requests[3]["url"] == DOCKET_URL
    assert session.requests[3]["data"] == {
        "caseYear": "22",
        "caseType": "CV",
        "caseSeq": "003098",
        "docketdatekey": "797786999950000",
        "docketdir": "3",
    }


def test_client_detects_native_docket_next_key_cycle() -> None:
    cycle_page = fixture_json("docket_cycle.json")
    session = FakeSession(
        [
            FakeResponse(
                text=fixture_text("disclaimer.html"),
                url=BASE_URL,
            ),
            FakeResponse(
                text=fixture_text("welcome.html"),
                url=f"{BASE_URL}Welcome.jsp",
            ),
            FakeResponse(
                text=fixture_text("case_detail.html"),
                url=CASE_SEARCH_URL,
            ),
            FakeResponse(
                text=json.dumps(cycle_page),
                payload=cycle_page,
                url=DOCKET_URL,
            ),
        ]
    )
    client = FranklinCourtClient(session=session, minimum_interval=0)

    with pytest.raises(
        FranklinSourceChangedError,
        match="repeated a next key",
    ):
        client.fetch_case("22CV3098")


def test_exact_case_not_found_is_authoritative_empty_result() -> None:
    session = FakeSession(
        [
            FakeResponse(
                text=fixture_text("disclaimer.html"),
                url=BASE_URL,
            ),
            FakeResponse(
                text=fixture_text("welcome.html"),
                url=f"{BASE_URL}Welcome.jsp",
            ),
            FakeResponse(
                text=fixture_text("case_not_found.html"),
                url=CASE_SEARCH_URL,
            ),
        ]
    )
    client = FranklinCourtClient(session=session, minimum_interval=0)
    args = build_parser().parse_args(["case", "99CV9999999"])

    result = execute(args, client=client, record_search=False)

    assert result.status.value == "no_results"
    assert result.records == ()
    assert result.errors == ()
    assert len(session.requests) == 3


def test_document_fetch_validates_media_signature_and_final_host() -> None:
    parsed = parsed_fixture_case()
    page = finalize_case_page(
        parsed,
        all_docket_rows=parsed.docket_rows,
        native_page_count=1,
    )
    document_id = page.record["documents"][0]["native_document_id"]
    pdf = fixture_pdf()
    session = FakeSession(
        [
            FakeResponse(
                url=f"{DOCUMENT_URL}?coords=redacted",
                headers={
                    "Content-Type": "application/pdf; charset=binary",
                    "Content-Disposition": 'inline; filename="order.pdf"',
                },
                content=pdf,
            )
        ]
    )
    client = FranklinCourtClient(session=session, minimum_interval=0)
    client.fetch_case = lambda _case_number: page

    fetched = client.fetch_document("22CV3098", document_id)

    assert fetched.pdf.content == pdf
    assert fetched.pdf.media_type == "application/pdf"
    assert fetched.pdf.filename == "order.pdf"
    assert fetched.pdf.final_host == "fcdcfcjs.co.franklin.oh.us"
    assert fetched.pdf.resolved_path.endswith("imageLinkProcessor.pdf")
    assert fetched.pdf.sha256
    assert session.requests[0]["params"] == {
        "coords": "fixture-coordinate-shared-a"
    }


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (
            FakeResponse(
                url=f"{DOCUMENT_URL}?coords=redacted",
                headers={"Content-Type": "text/html"},
                content=b"%PDF-fixture",
            ),
            "non-PDF media type",
        ),
        (
            FakeResponse(
                url=f"{DOCUMENT_URL}?coords=redacted",
                headers={"Content-Type": "application/pdf"},
                content=b"<html>not a pdf</html>",
            ),
            "lacks a PDF signature",
        ),
        (
            FakeResponse(
                url="https://example.com/file.pdf",
                headers={"Content-Type": "application/pdf"},
                content=b"%PDF-fixture",
            ),
            "outside the official host",
        ),
    ],
)
def test_document_fetch_rejects_invalid_artifact_response(
    response: FakeResponse,
    message: str,
) -> None:
    parsed = parsed_fixture_case()
    page = finalize_case_page(
        parsed,
        all_docket_rows=parsed.docket_rows,
        native_page_count=1,
    )
    document_id = page.record["documents"][0]["native_document_id"]
    client = FranklinCourtClient(
        session=FakeSession([response]),
        minimum_interval=0,
    )
    client.fetch_case = lambda _case_number: page

    with pytest.raises(FranklinSourceChangedError, match=message):
        client.fetch_document("22CV3098", document_id)


def test_source_command_is_offline_and_case_cli_has_no_result_limit() -> None:
    parser = build_parser()
    case_args = parser.parse_args(["case", "22CV3098"])
    search_args = parser.parse_args(["search", "WEXNER"])
    source_args = parser.parse_args(["source"])

    assert not hasattr(case_args, "limit")
    assert search_args.command == "search"
    assert search_args.native_row_count == 250
    result = execute(
        source_args,
        client=object(),
        record_search=False,
    )
    assert result.status.value == "ok"
    capabilities = result.records[0]
    assert capabilities["platform_family"] == "franklin_cio_ibm_jsp_servlet"
    docket = next(
        route
        for route in capabilities["routes"]
        if route["role"] == "docket_chronology"
    )
    assert docket["pagination"] == "source_next_key_until_empty"
    party = next(
        route
        for route in capabilities["routes"]
        if route["role"] == "party_name_index"
    )
    assert party["matching"] == "ordered_lower_bound_index_window"
    assert party["pagination"] is None
