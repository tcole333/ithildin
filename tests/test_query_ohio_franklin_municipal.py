from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy
from tools.query_ohio_franklin_municipal import (
    CASE_PDF_URL,
    CASE_VIEW_URL,
    COURT_ID,
    NATIVE_RESULT_LIMIT,
    PROBE_REQUEST_COUNT,
    SEARCH_RESULTS_URL,
    SEARCH_URL,
    SOURCE_ID,
    FranklinMunicipalClient,
    FranklinMunicipalSelectionError,
    FranklinMunicipalSourceChanged,
    build_parser,
    execute,
    normalize_case_number,
    parse_case_detail,
    parse_search_form,
    parse_search_results,
    parse_summary_pdf,
)


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_franklin_municipal"
)


class FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        text: str = "",
        content: bytes | None = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = url
        self.text = text
        self.content = content if content is not None else text.encode()
        self.status_code = status_code
        self.headers = headers or {}


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


def fixture_pdf() -> bytes:
    return bytes.fromhex(fixture_text("case_summary.pdf.hex").strip())


def response(name: str, url: str) -> FakeResponse:
    return FakeResponse(text=fixture_text(name), url=url)


def pdf_response() -> FakeResponse:
    return FakeResponse(
        url=CASE_PDF_URL,
        content=fixture_pdf(),
        headers={
            "Content-Type": "application/pdf",
            "Content-Disposition": (
                'inline; filename="FCMC Case Information - '
                '2022 CVF 020731.pdf"'
            ),
            "X-RateLimit-Limit": "25",
            "X-RateLimit-Remaining": "23",
        },
    )


def client_with(responses: list[FakeResponse]) -> tuple[FranklinMunicipalClient, FakeSession]:
    session = FakeSession(responses)
    client = FranklinMunicipalClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )
    return client, session


def test_source_contract_uses_shared_ids_and_maps_complements() -> None:
    args = build_parser().parse_args(["source"])

    result = execute(args, record_search=False)

    assert result.status is ResultStatus.OK
    record = result.records[0]
    assert record["source_id"] == SOURCE_ID == "us-oh-franklin-municipal-court-records"
    assert record["court"]["court_id"] == COURT_ID == "oh-franklin-municipal-court"
    assert record["search"]["native_result_limit"] == 250
    assert record["search"]["native_pagination"] == "none"
    assert record["case_summary"]["is_filed_document"] is False
    roles = {row["role"] for row in record["complementary_sources"]}
    assert {
        "individual_filing_inspection_and_copy",
        "daily_arraignment_reports",
        "monthly_eviction_csv",
        "civil_drop_list",
        "common_pleas_and_tenth_district",
    }.issubset(roles)
    assert record["probe"]["request_count"] == PROBE_REQUEST_COUNT


def test_case_number_normalization_keeps_court_case_identity_stable() -> None:
    assert normalize_case_number("2022 CVF 020731") == "2022CVF020731"
    assert normalize_case_number("2026 ER D 071120") == "2026ERD071120"
    with pytest.raises(FranklinMunicipalSelectionError, match="six-digit"):
        normalize_case_number("22 CVF 20731")


def test_search_form_parses_dynamic_filters_and_csrf() -> None:
    form = parse_search_form(fixture_text("search_form.html"))

    assert form.action_url == SEARCH_RESULTS_URL
    assert form.csrf_token == "fixture-csrf-token"
    assert form.case_types == ("CIVIL", "CRIMINAL/TRAFFIC")
    assert form.party_types == (
        "DEFENDANT",
        "PLAINTIFF",
        "OFFICER COMPLAINANT",
    )
    assert form.case_statuses == ("OPEN", "CLOSED")


def test_search_parser_reads_only_desktop_occurrence_and_preserves_dob_sentinel() -> None:
    fingerprint = "f" * 64
    page = parse_search_results(
        fixture_text("person_results.html"),
        query_fingerprint=fingerprint,
        matched_query={"last_name": "BURKHALTER", "first_name": "ERIKA"},
    )

    assert len(page.records) == 1
    record = page.records[0]
    assert record["record_kind"] == "case_index_occurrence"
    assert record["normalized_case_number"] == "2022CVF020731"
    assert record["canonical_case_ref"].endswith("/2022CVF020731/case")
    assert record["raw_name"] == "ERIKA  BURKHALTER"
    assert record["name"] == "ERIKA BURKHALTER"
    assert record["raw_date_of_birth_sort"] == "00000000"
    assert record["date_of_birth_display"] is None
    assert record["date_of_birth"] is None
    assert record["pending_events"] == "NO"
    assert record["query_fingerprint"] == fingerprint
    assert record["response_ordinal"] == 1
    assert record["native_occurrence_id"].endswith(
        f"{fingerprint}:ordinal:1"
    )
    serialized = json.dumps(record)
    assert "encrypted-person-handle" not in serialized
    assert "different-mobile-handle" not in serialized


def test_search_parser_normalizes_populated_sort_dob_without_losing_raw() -> None:
    html = fixture_text("person_results.html").replace(
        "00000000", "19780515", 1
    )
    page = parse_search_results(
        html,
        query_fingerprint="d" * 64,
        matched_query={"last_name": "DEMETER", "first_name": "SAMUEL"},
    )

    record = page.records[0]
    assert record["raw_date_of_birth_sort"] == "19780515"
    assert record["date_of_birth"] == "1978-05-15"


def test_exact_case_results_preserve_each_party_occurrence_and_ordinal() -> None:
    page = parse_search_results(
        fixture_text("exact_results.html"),
        query_fingerprint="e" * 64,
        matched_query={"case_number": "2022 CVF 020731"},
    )

    assert page.reported_count == 2
    assert [row["party_role"] for row in page.records] == [
        "PLAINTIFF",
        "DEFENDANT",
    ]
    assert [row["response_ordinal"] for row in page.records] == [1, 2]
    assert len({row["native_occurrence_id"] for row in page.records}) == 2
    assert len({row["canonical_case_ref"] for row in page.records}) == 1


def test_explicit_native_limit_is_partial_without_an_invented_cursor() -> None:
    page = parse_search_results(
        fixture_text("limited_results.html"),
        query_fingerprint="c" * 64,
        matched_query={"company_name": "CAPITAL ONE"},
    )

    assert page.reported_count == NATIVE_RESULT_LIMIT
    assert page.truncated is True
    boundary = page.records[0]["search_boundary"]
    assert boundary["native_result_limit"] == 250
    assert boundary["truncated"] is True
    assert boundary["complete"] is False
    assert boundary["next_cursor"] is None
    assert boundary["unresolved_reason"] == "native_result_limit_reached"


def test_empty_redirect_page_is_authoritative_no_results() -> None:
    page = parse_search_results(
        fixture_text("no_results.html"),
        query_fingerprint="0" * 64,
        matched_query={"case_year": "1970"},
        source_url=SEARCH_URL,
    )

    assert page.records == ()
    assert page.reported_count == 0
    assert page.truncated is False


def test_new_native_pagination_is_reported_as_source_change() -> None:
    html = fixture_text("person_results.html").replace(
        "</body>", '<a rel="next" href="?page=2">Next</a></body>'
    )
    with pytest.raises(FranklinMunicipalSourceChanged, match="paginator"):
        parse_search_results(
            html,
            query_fingerprint="p" * 64,
            matched_query={"company_name": "EXAMPLE"},
        )


def test_civil_case_parser_keeps_parties_financials_and_docket_occurrences() -> None:
    record = parse_case_detail(
        fixture_text("civil_detail.html"),
        requested_case_number="2022 CVF 020731",
    )

    assert record["record_kind"] == "case"
    assert record["normalized_case_number"] == "2022CVF020731"
    assert record["filing_date"] == "07/11/2022"
    assert record["status"] == "CLOSED"
    assert [party["type"] for party in record["parties"]] == [
        "PLAINTIFF",
        "DEFENDANT",
    ]
    assert record["attorneys"][0]["name"] == "HOFF, DAVID J"
    assert record["dispositions"][0]["judge"] == "ADMINISTRATIVE"
    assert record["financial_summary"][0]["amount_owed"] == "$123.00"
    assert record["receipts"][0]["number"] == "22676708"
    assert len(record["docket_entries"]) == 3
    assert "Tracking No: C001416665" in record["docket_entries"][0]["detail"]
    assert record["docket_entries"][1]["title"] == "IMAGE OF COMPLAINT"
    assert record["docket_entries"][1]["online_filing_link"] is None
    assert record["docket_entries"][1]["filed_document_access"] == (
        "not_linked_online"
    )
    assert len({row["native_entry_id"] for row in record["docket_entries"]}) == 3
    assert record["documents"] == []
    summary = record["document_access"]["generated_case_summary"]
    assert summary["is_filed_document"] is False


def test_criminal_case_parser_covers_defendant_charge_event_and_case_details() -> None:
    record = parse_case_detail(
        fixture_text("criminal_detail.html"),
        requested_case_number="2026 ER D 071120",
    )

    assert record["normalized_case_number"] == "2026ERD071120"
    assert record["defendant_information"]["date_of_birth"] == "05/15/1978"
    assert record["defendant_information"]["race"] == "WHITE"
    assert record["case_details"]["ticket_number"] == (
        "0COP00W002552072226003"
    )
    assert record["case_details"]["officer_code"] == "FINCH, DONALD"
    assert record["parties"][1]["officer_agency"] == (
        "COLUMBUS POLICE DEPARTMENT"
    )
    assert record["charges"][0]["action_code"] == "4513.31(A)"
    assert record["events"][0]["courtroom"] == "15A"
    assert record["events"][0]["start"] == "09:00 AM"


def test_case_detail_rejects_identity_mismatch() -> None:
    with pytest.raises(FranklinMunicipalSourceChanged, match="does not match"):
        parse_case_detail(
            fixture_text("civil_detail.html"),
            requested_case_number="2022 CVF 999999",
        )


def test_generated_summary_validation_distinguishes_it_from_a_filing() -> None:
    summary = parse_summary_pdf(
        fixture_pdf(),
        headers={
            "Content-Type": "application/pdf; charset=binary",
            "Content-Disposition": (
                'inline; filename="FCMC Case Information - '
                '2022 CVF 020731.pdf"'
            ),
        },
        response_url=CASE_PDF_URL,
    )

    assert summary.content.startswith(b"%PDF")
    assert summary.media_type == "application/pdf"
    assert summary.filename == "FCMC Case Information - 2022 CVF 020731.pdf"
    assert len(summary.sha256) == 64


@pytest.mark.parametrize(
    ("content", "headers", "url"),
    [
        (b"<html>blocked</html>", {"Content-Type": "text/html"}, CASE_PDF_URL),
        (
            b"%PDF-fixture",
            {"Content-Type": "application/pdf"},
            "https://example.com/summary.pdf",
        ),
    ],
)
def test_generated_summary_rejects_non_pdf_or_official_host_change(
    content: bytes,
    headers: dict[str, str],
    url: str,
) -> None:
    with pytest.raises(FranklinMunicipalSourceChanged):
        parse_summary_pdf(content, headers=headers, response_url=url)


def test_client_search_bootstraps_and_posts_csrf_without_exposing_handle() -> None:
    client, session = client_with(
        [
            response("search_form.html", SEARCH_URL),
            response("person_results.html", SEARCH_RESULTS_URL),
        ]
    )

    page = client.search(
        {"last_name": "BURKHALTER", "first_name": "ERIKA"},
        query_fingerprint="q" * 64,
    )

    assert len(session.requests) == 2
    assert session.requests[0]["method"] == "GET"
    assert session.requests[1]["method"] == "POST"
    assert session.requests[1]["url"] == SEARCH_RESULTS_URL
    assert session.requests[1]["data"] == {
        "_token": "fixture-csrf-token",
        "last_name": "BURKHALTER",
        "first_name": "ERIKA",
        "desktop_view": "on",
    }
    assert "encrypted-person-handle" not in json.dumps(page.records)


def test_client_exact_case_uses_fresh_handle_but_persists_case_number_only() -> None:
    client, session = client_with(
        [
            response("search_form.html", SEARCH_URL),
            response("exact_results.html", SEARCH_RESULTS_URL),
            response("civil_detail.html", CASE_VIEW_URL),
        ]
    )

    resolved = client.resolve_case("2022 CVF 020731")

    assert len(session.requests) == 3
    assert session.requests[2]["data"]["case_id"] == "encrypted-exact-handle-a"
    serialized = json.dumps(resolved.record)
    assert "encrypted-exact-handle" not in serialized
    assert resolved.record["source_metadata"]["encrypted_case_handle_persisted"] is False


def test_execute_marks_capped_search_partial_and_emits_no_cursor() -> None:
    client, _ = client_with(
        [
            response("search_form.html", SEARCH_URL),
            response("limited_results.html", SEARCH_RESULTS_URL),
        ]
    )
    args = build_parser().parse_args(["company", "CAPITAL ONE", "--year", "2026"])

    result = execute(args, client=client, record_search=False)

    assert result.status is ResultStatus.PARTIAL
    assert len(result.records) == 1
    assert result.next_cursor is None
    assert result.errors[0].code == "native_result_limit_reached"
    assert result.records[0]["matched_query"]["case_year"] == "2026"


def test_probe_has_exactly_five_requests_and_no_transport_secret_output() -> None:
    client, session = client_with(
        [
            response("search_form.html", SEARCH_URL),
            response("person_results.html", SEARCH_RESULTS_URL),
            response("exact_results.html", SEARCH_RESULTS_URL),
            response("civil_detail.html", CASE_VIEW_URL),
            pdf_response(),
        ]
    )

    probe = client.probe()

    assert probe["request_count"] == 5
    assert len(session.requests) == 5
    assert [item["method"] for item in session.requests] == [
        "GET",
        "POST",
        "POST",
        "POST",
        "POST",
    ]
    assert [item["url"] for item in session.requests] == [
        SEARCH_URL,
        SEARCH_RESULTS_URL,
        SEARCH_RESULTS_URL,
        CASE_VIEW_URL,
        CASE_PDF_URL,
    ]
    assert probe["summary_document_kind"] == "generated_case_summary"
    assert probe["summary_is_filed_document"] is False
    assert probe["transport_secrets_persisted"] is False
    assert "encrypted-exact-handle" not in json.dumps(probe)


def test_summary_command_writes_pdf_and_emits_artifact_metadata(
    tmp_path: Path,
) -> None:
    client, _ = client_with(
        [
            response("search_form.html", SEARCH_URL),
            response("exact_results.html", SEARCH_RESULTS_URL),
            response("civil_detail.html", CASE_VIEW_URL),
            pdf_response(),
        ]
    )
    destination = tmp_path / "summary.pdf"
    args = build_parser().parse_args(
        ["summary-pdf", "2022 CVF 020731", str(destination)]
    )

    result = execute(args, client=client, record_search=False)

    assert result.status is ResultStatus.OK
    assert destination.read_bytes() == fixture_pdf()
    artifact = result.records[0]
    assert artifact["record_kind"] == "case_summary_artifact"
    assert artifact["document_kind"] == "generated_case_summary"
    assert artifact["is_filed_document"] is False
    assert artifact["destination"] == str(destination.resolve())
    assert "encrypted-exact-handle" not in result.to_json()


def test_cli_accepts_native_filters_without_hard_coding_observed_values() -> None:
    args = build_parser().parse_args(
        [
            "person",
            "DOE",
            "JANE",
            "--middle-name",
            "Q",
            "--date-of-birth",
            "01/02/1980",
            "--party-type",
            "THIRD PARTY PLAINTIFF",
            "--case-type",
            "CIVIL",
            "--year",
            "2020",
            "--status",
            "CLOSED",
        ]
    )

    assert args.middle_name == "Q"
    assert args.date_of_birth == "01/02/1980"
    assert args.party_type == "THIRD PARTY PLAINTIFF"
    assert args.year == "2020"


def test_rate_limit_is_an_explicit_failure_not_an_empty_result() -> None:
    client, _ = client_with(
        [
            FakeResponse(
                url=SEARCH_URL,
                status_code=429,
                headers={"X-RateLimit-Limit": "25", "X-RateLimit-Remaining": "0"},
            )
        ]
    )
    args = build_parser().parse_args(["company", "EXAMPLE"])

    result = execute(args, client=client, record_search=False)

    assert result.status is ResultStatus.RATE_LIMITED
    assert result.records == ()
    assert result.errors[0].code == "rate_limited"
