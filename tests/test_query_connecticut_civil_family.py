from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup

from tools import query_connecticut_civil_family as ct
from tools.public_records_contract import ResultStatus


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "connecticut_civil_family"
)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


class FakeResponse:
    def __init__(
        self,
        text: str = "",
        *,
        url: str,
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.text = text
        self.url = url
        self.status_code = status_code
        self.content = (
            content if content is not None else text.encode("utf-8")
        )
        self.headers = {
            "Content-Type": content_type,
            **(headers or {}),
        }


class FakeSession:
    def __init__(self, *responses: FakeResponse) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []
        self.headers: dict[str, str] = {}
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append(
            {"method": method, "url": url, **kwargs}
        )
        if not self.responses:
            raise AssertionError("unexpected request")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def parsed_form() -> ct.PartySearchForm:
    return ct.parse_party_search_form(
        fixture("party_search.html"),
        source_url=ct.PARTY_SEARCH_URL,
    )


def parsed_party_page() -> ct.PartyResultPage:
    return ct.parse_party_results(
        fixture("party_results_50.html"),
        source_url=ct.PARTY_SEARCH_URL,
    )


def parsed_case() -> dict[str, Any]:
    return ct.parse_case_detail(
        fixture("case_detail.html"),
        requested_docket=ct.SENTINEL_DOCKET,
        source_url=(
            f"{ct.CASE_DETAIL_URL}?DocketNo="
            f"{ct.compact_docket(ct.SENTINEL_DOCKET)}"
        ),
    )


def test_source_id_and_docket_normalization_are_stable() -> None:
    assert (
        ct.SOURCE_ID
        == "us-ct-superior-court-civil-family-case-lookup"
    )
    assert (
        ct.normalize_docket("fbt-cv26-6159214-s")
        == "FBT-CV-26-6159214-S"
    )
    assert (
        ct.normalize_docket("FBTCV266159214S")
        == "FBT-CV-26-6159214-S"
    )
    assert ct.compact_docket("FBT-CV-26-6159214-S") == (
        "FBTCV266159214S"
    )
    with pytest.raises(ct.ConnecticutSelectionError) as raised:
        ct.normalize_docket("not-a-docket")
    assert raised.value.code == "invalid_docket"


def test_party_form_and_exact_payload_preserve_webforms_state() -> None:
    form = parsed_form()
    payload = ct.build_party_search_payload(
        form,
        last_name=" epstein ",
        first_name="jeffrey",
        match="exact",
        location="FBT",
        category="CV",
        case_type="C40",
        sort="court_location",
    )

    assert form.action_url == ct.PARTY_SEARCH_URL
    assert payload["__VIEWSTATE"] == "fixture-viewstate"
    assert payload["__EVENTVALIDATION"] == "fixture-validation"
    assert (
        payload["ctl00$ContentPlaceHolder1$txtLastName"]
        == "epstein"
    )
    assert (
        payload["ctl00$ContentPlaceHolder1$rblLastNameSearchType"]
        == "Is Equal To"
    )
    assert payload["ctl00$ContentPlaceHolder1$ddlLocation"] == "FBT"
    assert payload["ctl00$ContentPlaceHolder1$ddlCaseCategory"] == "CV"
    assert (
        payload["ctl00$ContentPlaceHolder1$ddlSortOrder"]
        == "court_loc, party_name"
    )


def test_party_form_rejects_source_schema_drift() -> None:
    changed = fixture("party_search.html").replace(
        'name="__EVENTVALIDATION"',
        'name="removed_EVENTVALIDATION"',
    )
    with pytest.raises(ct.ConnecticutSourceChanged) as raised:
        ct.parse_party_search_form(
            changed,
            source_url=ct.PARTY_SEARCH_URL,
        )
    assert raised.value.code == "party_search_controls_changed"


def test_party_result_preserves_verified_source_display_slice() -> None:
    page = parsed_party_page()

    assert len(page.rows) == 50
    assert page.displayed_start == 1
    assert page.displayed_end == 50
    assert page.source_reported_count == 50
    assert page.has_pager is False
    assert page.source_slice_unresolved is True
    sentinel = page.rows[39]
    assert sentinel["party_name"] == "EPSTEIN JEFFREY"
    assert sentinel["docket"] == ct.SENTINEL_DOCKET
    assert sentinel["publisher_party_number"] == "D-01"


def test_party_not_found_is_authoritative_empty() -> None:
    page = ct.parse_party_results(
        fixture("party_not_found.html"),
        source_url=ct.PARTY_SEARCH_URL,
    )
    assert page.authoritative_no_results is True
    assert page.rows == ()


def test_party_result_column_change_is_source_change() -> None:
    changed = fixture("party_results_50.html").replace(
        "<th>Pty No.</th>",
        "<th>Party Identifier</th>",
    )
    with pytest.raises(ct.ConnecticutSourceChanged) as raised:
        ct.parse_party_results(
            changed,
            source_url=ct.PARTY_SEARCH_URL,
        )
    assert raised.value.code == "party_results_columns_changed"


class PartyClient:
    def __init__(
        self,
        page: ct.PartyResultPage | None = None,
    ) -> None:
        self.form = parsed_form()
        self.page = page or parsed_party_page()
        self.calls: list[dict[str, Any]] = []

    def search_parties(self, **kwargs: Any):
        self.calls.append(kwargs)
        return self.form, self.page


def test_search_has_no_implicit_local_limit_and_keeps_names_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ct, "log_search", lambda *_args: None)
    client = PartyClient()
    result = ct.search_parties(
        last_name="EPSTEIN",
        match="exact",
        client=client,
    )

    assert result.status is ResultStatus.PARTIAL
    assert len(result.records) == 50
    assert result.next_cursor is None
    assert {error.code for error in result.errors} == {
        "source_display_slice"
    }
    assert all(
        record["identity_resolution"]["status"]
        == "unresolved_same_name_candidate"
        for record in result.records
    )
    assert all(
        record["source_display"]["completeness"]
        == "unresolved_source_display_slice"
        for record in result.records
    )


def test_caller_limit_resumes_within_bound_source_slice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ct, "log_search", lambda *_args: None)
    client = PartyClient()
    first = ct.search_parties(
        last_name="EPSTEIN",
        limit=7,
        client=client,
    )
    assert first.status is ResultStatus.PARTIAL
    assert len(first.records) == 7
    assert first.next_cursor
    assert {error.code for error in first.errors} == {
        "source_display_slice",
        "caller_selected_slice",
    }

    resumed = ct.search_parties(
        last_name="EPSTEIN",
        limit=43,
        cursor=first.next_cursor,
        client=client,
    )
    assert resumed.status is ResultStatus.PARTIAL
    assert len(resumed.records) == 43
    assert resumed.next_cursor is None
    assert resumed.records[0]["party_name"] == "EPSTEIN ALEX 08"

    mismatch = ct.search_parties(
        last_name="OTHER",
        limit=7,
        cursor=first.next_cursor,
        client=client,
    )
    assert mismatch.status is ResultStatus.UNAVAILABLE
    assert mismatch.errors[0].code == "cursor_query_mismatch"


def test_case_detail_normalizes_case_parties_counsel_and_filings() -> None:
    case = parsed_case()

    assert case["docket"] == ct.SENTINEL_DOCKET
    assert case["case_type_code"] == "C40"
    assert case["case_type_description"] == (
        "C40 - Contracts - Collections"
    )
    assert case["file_date"] == "2026-04-23"
    assert case["return_date"] == "2026-05-12"
    assert case["information_updated_as_of"] == "2026-07-31"
    assert len(case["parties"]) == 2

    plaintiff = case["parties"][0]
    assert plaintiff["publisher_party_number"] == "P-01"
    assert plaintiff["category"] == "Plaintiff"
    assert plaintiff["appearances"][0]["publisher_juris_number"] == (
        "438783"
    )
    assert plaintiff["appearances"][0]["file_date"] == "2026-04-23"
    defendant = case["parties"][1]
    assert defendant["publisher_party_number"] == "D-01"
    assert defendant["appearance_status"] == "Non-Appearing"
    assert "/party/D-01" in defendant["canonical_ref"]

    assert len(case["docket_entries"]) == 4
    assert len(case["filing_documents"]) == 3
    complaint = case["filing_documents"][1]
    assert complaint["publisher_document_number"] == "32503295"
    assert complaint["identity_basis"] == "publisher_document_number"
    assert "/document/32503295" in complaint["canonical_ref"]
    status_entry = case["docket_entries"][3]
    assert status_entry["publisher_entry_number"] == "101.00"
    assert status_entry["document_available"] is False
    assert status_entry["result"] == "Order 04/24/2026 BY THE CLERK"


def test_case_detail_rejects_docket_mismatch() -> None:
    with pytest.raises(ct.ConnecticutSourceChanged) as raised:
        ct.parse_case_detail(
            fixture("case_detail.html"),
            requested_docket="FBT-CV-26-6100001-S",
            source_url=ct.CASE_DETAIL_URL,
        )
    assert raised.value.code == "case_detail_docket_mismatch"


def test_scheduled_events_keep_publisher_event_numbers() -> None:
    soup = BeautifulSoup(fixture("scheduled_events.html"), "html.parser")
    events, as_of_raw = ct._parse_scheduled_events(
        soup,
        docket="FBT-CV-25-6153725-S",
        source_url=ct.CASE_DETAIL_URL,
    )
    assert as_of_raw == "07/30/2026"
    assert [event["publisher_event_number"] for event in events] == [
        "1",
        "2",
    ]
    assert events[0]["date"] == "2026-07-31"
    assert events[0]["description"] == "Remote Mediation"
    assert "/scheduled_event/1" in events[0]["canonical_ref"]


def test_history_supports_empty_and_transfer_rows() -> None:
    assert (
        ct.parse_case_history(
            fixture("history_empty.html"),
            docket=ct.SENTINEL_DOCKET,
            source_url=ct.CASE_HISTORY_URL,
        )
        == []
    )
    transfers = ct.parse_case_history(
        fixture("history_transfer.html"),
        docket="KNL-CV-25-6076026-S",
        source_url=ct.CASE_HISTORY_URL,
    )
    assert transfers[0]["transferred_from_docket"] == (
        "KNL-CV-25-6076026-S"
    )
    assert transfers[0]["transferred_to_docket"] == (
        "HHB-CV-25-6098750-S"
    )
    assert transfers[0]["transfer_date"] == "2025-08-22"
    assert transfers[0]["identity_basis"] == (
        "published_transfer_field_tuple"
    )


def test_notices_keep_enid_and_psid() -> None:
    assert (
        ct.parse_notices(
            fixture("notices_empty.html"),
            docket=ct.SENTINEL_DOCKET,
            source_url=ct.NOTICES_URL,
        )
        == []
    )
    notices = ct.parse_notices(
        fixture("notices.html"),
        docket="HHD-CV-26-6217425-S",
        source_url=ct.NOTICES_URL,
    )
    assert [notice["publisher_notice_id"] for notice in notices] == [
        "11573846",
        "11573847",
    ]
    assert notices[0]["publisher_publication_set_id"] == "106992"
    assert notices[0]["notice_handler"] == "ViewJDNO.aspx"
    assert "/notice/11573846" in notices[0]["canonical_ref"]


def test_client_posts_exact_search_in_one_session() -> None:
    session = FakeSession(
        FakeResponse(
            fixture("party_search.html"),
            url=ct.PARTY_SEARCH_URL,
        ),
        FakeResponse(
            fixture("party_results_50.html"),
            url=ct.PARTY_SEARCH_URL,
        ),
    )
    client = ct.ConnecticutCivilFamilyClient(
        session=session,
        minimum_interval=0,
    )
    form, page = client.search_parties(
        last_name="EPSTEIN",
        first_name="JEFFREY",
        match="exact",
    )

    assert form.action_url == ct.PARTY_SEARCH_URL
    assert len(page.rows) == 50
    assert [call["method"] for call in session.requests] == ["GET", "POST"]
    payload = session.requests[1]["data"]
    assert payload["__VIEWSTATE"] == "fixture-viewstate"
    assert (
        payload["ctl00$ContentPlaceHolder1$rblLastNameSearchType"]
        == "Is Equal To"
    )
    assert session.requests[1]["headers"]["Referer"] == (
        ct.PARTY_SEARCH_URL
    )


def test_client_case_bundle_uses_detail_referer_for_child_pages() -> None:
    detail_url = (
        f"{ct.CASE_DETAIL_URL}?DocketNo="
        f"{ct.compact_docket(ct.SENTINEL_DOCKET)}"
    )
    session = FakeSession(
        FakeResponse(fixture("case_detail.html"), url=detail_url),
        FakeResponse(fixture("history_empty.html"), url=ct.CASE_HISTORY_URL),
        FakeResponse(fixture("notices_empty.html"), url=ct.NOTICES_URL),
    )
    client = ct.ConnecticutCivilFamilyClient(
        session=session,
        minimum_interval=0,
    )
    bundle = client.fetch_case_bundle(ct.SENTINEL_DOCKET)

    assert bundle.child_errors == ()
    assert bundle.record["history"] == []
    assert bundle.record["notices"] == []
    assert session.requests[1]["headers"]["Referer"] == detail_url
    assert session.requests[2]["headers"]["Referer"] == detail_url


def test_wrong_host_and_media_type_are_source_changes() -> None:
    wrong_host = FakeSession(
        FakeResponse(
            fixture("party_search.html"),
            url="https://example.com/PartySearch.aspx",
        )
    )
    client = ct.ConnecticutCivilFamilyClient(
        session=wrong_host,
        minimum_interval=0,
    )
    with pytest.raises(ct.ConnecticutSourceChanged) as host_error:
        client.search_parties(last_name="EPSTEIN")
    assert host_error.value.code == "unexpected_source_route"

    wrong_media = FakeSession(
        FakeResponse(
            "{}",
            url=ct.PARTY_SEARCH_URL,
            content_type="application/json",
        )
    )
    client = ct.ConnecticutCivilFamilyClient(
        session=wrong_media,
        minimum_interval=0,
    )
    with pytest.raises(ct.ConnecticutSourceChanged) as media_error:
        client.search_parties(last_name="EPSTEIN")
    assert media_error.value.code == "response_media_type_changed"


def test_missing_curl_transport_is_classified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ct, "curl_requests", None)
    with pytest.raises(ct.ConnecticutTransportUnavailable) as raised:
        ct.ConnecticutCivilFamilyClient()
    assert raised.value.code == "connecticut_transport_unavailable"
    assert raised.value.details["dependency"] == "curl-cffi>=0.13.0"


def test_installed_curl_transport_import_contract() -> None:
    assert ct.curl_requests is not None
    assert ct.CurlRequestException is not None


def test_document_retrieval_validates_and_writes_pdf(
    tmp_path: Path,
) -> None:
    pdf = b"%PDF-1.5\nfixture filing\n%%EOF\n"
    response_url = f"{ct.DOCUMENT_URL}?DocumentNo=32503295"
    session = FakeSession(
        FakeResponse(
            url=response_url,
            content_type="application/pdf",
            content=pdf,
            headers={
                "Content-Disposition": (
                    "inline;filename=DocumentInquiry.pdf"
                )
            },
        )
    )
    client = ct.ConnecticutCivilFamilyClient(
        session=session,
        minimum_interval=0,
    )
    output = tmp_path / "complaint.pdf"
    result = ct.retrieve_document(
        "32503295",
        pdf_output=output,
        client=client,
    )

    assert result.status is ResultStatus.OK
    assert output.read_bytes() == pdf
    assert result.raw_artifact_refs == (str(output),)
    record = result.records[0]
    assert record["publisher_document_number"] == "32503295"
    assert record["byte_length"] == len(pdf)
    assert record["sha256"]
    assert record["canonical_ref"] is None


def test_document_can_be_verified_against_docket(tmp_path: Path) -> None:
    class DocumentClient:
        def fetch_case_detail(self, docket: str):
            assert docket == ct.SENTINEL_DOCKET
            return parsed_case()

        def fetch_document(self, document_number: str):
            assert document_number == "32503295"
            content = b"%PDF-1.5\nverified\n"
            return {
                "publisher_document_number": document_number,
                "source_url": (
                    f"{ct.DOCUMENT_URL}?DocumentNo={document_number}"
                ),
                "content_type": "application/pdf",
                "content_disposition": None,
                "byte_length": len(content),
                "sha256": "fixture-sha",
                "content": content,
            }

    result = ct.retrieve_document(
        "32503295",
        docket=ct.SENTINEL_DOCKET,
        pdf_output=tmp_path / "verified.pdf",
        client=DocumentClient(),
    )
    assert result.status is ResultStatus.OK
    assert "/document/32503295" in result.records[0]["canonical_ref"]
    assert result.records[0]["filing_metadata"]["description"] == (
        "COMPLAINT"
    )


def test_document_rejects_non_pdf_response() -> None:
    response_url = f"{ct.DOCUMENT_URL}?DocumentNo=32503295"
    session = FakeSession(
        FakeResponse(
            "<html>not a filing</html>",
            url=response_url,
            content_type="text/html",
        )
    )
    client = ct.ConnecticutCivilFamilyClient(
        session=session,
        minimum_interval=0,
    )
    with pytest.raises(ct.ConnecticutSourceChanged) as raised:
        client.fetch_document("32503295")
    assert raised.value.code == "document_response_changed"


def test_case_child_failure_returns_partial_record() -> None:
    error = ct.ConnecticutSourceChanged(
        "case_notices_grid_missing",
        "notices changed",
        url=ct.NOTICES_URL,
    )

    class PartialClient:
        def fetch_case_bundle(self, docket: str) -> ct.CaseBundle:
            assert docket == ct.SENTINEL_DOCKET
            return ct.CaseBundle(
                record=parsed_case(),
                child_errors=(error,),
            )

    result = ct.lookup_case(
        ct.SENTINEL_DOCKET,
        client=PartialClient(),
    )
    assert result.status is ResultStatus.PARTIAL
    assert len(result.records) == 1
    assert result.errors[0].code == "case_notices_grid_missing"


def test_probe_checks_slice_case_and_document_sentinels() -> None:
    class ProbeClient(PartyClient):
        def fetch_case_bundle(self, docket: str) -> ct.CaseBundle:
            assert docket == ct.SENTINEL_DOCKET
            record = parsed_case()
            record["history"] = []
            record["notices"] = []
            return ct.CaseBundle(record=record)

    result = ct.probe_source(client=ProbeClient())
    assert result.status is ResultStatus.OK
    assert result.records[0]["party_search"]["displayed_rows"] == 50
    assert result.records[0]["sentinel"][
        "publisher_document_number"
    ] == "32503295"


def test_routes_identify_bulk_as_comprehensive_complement() -> None:
    result = ct.source_routes()
    assert result.status is ResultStatus.OK
    routes = {record["route_id"]: record for record in result.records}
    bulk = routes["civil_family_bulk"]
    assert bulk["implemented"] is False
    assert bulk["electronic_documents_included"] is False
    assert "comprehensive complement" in bulk["relationship"]
    assert bulk["independent_corroboration"] is False
    assert routes["filing_document"]["publisher_identifier"] == (
        "DocumentNo"
    )


def test_cli_defaults_do_not_add_a_result_cap() -> None:
    parser = ct.build_parser()
    args = parser.parse_args(["search", "EPSTEIN"])
    assert isinstance(args, argparse.Namespace)
    assert args.limit is None
    assert args.match == "exact"
    with pytest.raises(SystemExit):
        parser.parse_args(["document", "32503295"])
