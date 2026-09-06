from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools import query_dc_appellate_cases as dc_cases
from tools.public_records_contract import ResultStatus


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "dc_appellate_cases"
)


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(
        self,
        *,
        text: str = "",
        content: bytes | None = None,
        status_code: int = 200,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.text = text
        self.content = (
            content if content is not None else text.encode("utf-8")
        )
        self.status_code = status_code
        self.url = url
        self.headers = headers or {"Content-Type": "text/html"}


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.headers: dict[str, str] = {}
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def test_source_manifest_makes_trial_component_outcomes_first_class() -> None:
    manifest = dc_cases.source_manifest()

    assert manifest["sources"][0]["source_id"] == dc_cases.SOURCE_ID
    assert manifest["operations"]["search"][
        "originating_case_number_field"
    ] == "lcCsNumber"
    outcomes = {
        item["source_id"]: item
        for item in manifest["component_access_outcomes"]
    }
    assert outcomes["us-dc-superior-court-portal"][
        "operation_state"
    ] == "human_verification_observed"
    assert outcomes["us-dc-superior-eaccess"][
        "operation_state"
    ] == "captcha_observed"


def test_parse_case_results_preserves_originating_case_pivot() -> None:
    page = dc_cases.parse_search_results(
        fixture_text("case_results.html"),
        operation="search",
        source_url=dc_cases.CASE_SEARCH_URL,
        requested_start_row=1,
    )

    assert page.total_rows == 2
    assert page.next_start_row is None
    assert len(page.records) == 2
    first = page.records[0]
    assert first["appellate_case_number"] == "99-CV-1385"
    assert first["source_internal_id"] == "32210"
    assert first["originating_case_number"] == "1998-CA-007597"
    portal = next(
        item
        for item in first["related_source_routes"]
        if item["source_id"] == "us-dc-superior-court-portal"
    )
    assert portal["selector"] == {"case_number": "1998-CA-007597"}
    assert page.records[1]["originating_case_number"] is None


def test_parse_participant_results_preserves_role_and_case_link() -> None:
    page = dc_cases.parse_search_results(
        fixture_text("participant_results.html"),
        operation="participant",
        source_url=dc_cases.PARTICIPANT_SEARCH_URL,
        requested_start_row=1,
    )

    assert page.total_rows == 2
    assert page.records[0]["participant_name"] == "Joshua Max Alpert"
    assert page.records[0]["appellate_role"] == "Movant"
    assert page.records[0]["appeal_filed_date"] == "2026-04-02"
    assert page.records[1]["source_internal_id"] == "69335"


def test_parse_empty_result_page_is_not_a_schema_failure() -> None:
    page = dc_cases.parse_search_results(
        fixture_text("empty_results.html"),
        operation="search",
        source_url=dc_cases.CASE_SEARCH_URL,
        requested_start_row=1,
    )

    assert page.records == ()
    assert page.total_rows == 0


def test_parse_result_page_rejects_missing_native_field() -> None:
    html = fixture_text("case_results.html").replace(
        '<input name="lcCsNumber" value="">',
        "",
    )

    with pytest.raises(dc_cases.DCAppellateSourceChangedError) as raised:
        dc_cases.parse_search_results(
            html,
            operation="search",
            source_url=dc_cases.CASE_SEARCH_URL,
            requested_start_row=1,
        )

    assert raised.value.code == "search_fields_changed"


def test_parse_case_view_preserves_parties_events_and_document_locator() -> None:
    record = dc_cases.parse_case_view(
        fixture_text("case_view.html"),
        source_url=(
            f"{dc_cases.BASE_URL}{dc_cases.CASE_VIEW_PATH}?csIID=69335"
        ),
    )

    assert record["appellate_case_number"] == "24-BG-1045"
    assert record["source_internal_id"] == "69335"
    assert record["originating_case_number"] == "DDN 2024-D175"
    assert record["filed_date"] == "2024-11-12"
    assert record["status"] == "Decided/Dismissed"
    assert len(record["parties"]) == 2
    assert [item["name"] for item in record["parties"][0]["attorneys"]] == [
        "Hamilton P. Fox",
        "William R. Ross",
    ]
    assert record["parties"][1]["representation"] == "Pro Se"
    assert record["docket_events"][0]["document_state"] == "not_linked"
    linked = record["docket_events"][1]
    assert linked["native_event_id"] == "1697111"
    assert linked["document_locator"] == {
        "method_code": "50",
        "event_id": "1697111",
        "case_id": "69335",
    }


def test_parse_case_view_rejects_cross_case_document_locator() -> None:
    html = fixture_text("case_view.html").replace(
        "50:1697111:69335",
        "50:1697111:99999",
    )

    with pytest.raises(dc_cases.DCAppellateSourceChangedError) as raised:
        dc_cases.parse_case_view(
            html,
            source_url=dc_cases.BASE_URL,
        )

    assert raised.value.code == "document_locator_case_mismatch"


def test_parse_document_links_returns_stable_official_document() -> None:
    records = dc_cases.parse_document_links(
        fixture_text("document_links.dwr"),
        case_number="24-BG-1045",
        case_internal_id="69335",
        event_id="1697111",
    )

    assert len(records) == 1
    assert records[0]["native_document_id"] == "399765"
    assert records[0]["source_event_id"] == "1697111"
    assert records[0]["download_url"].endswith(
        "documentID=399765&csIID=69335"
    )
    assert records[0]["document_title"] == (
        "REDACTION CERTIFICATE - Redaction Certificate"
    )


def test_document_url_rejects_another_host() -> None:
    with pytest.raises(dc_cases.DCAppellateSelectionError):
        dc_cases._official_document_url(
            "https://example.com/document/view.do?"
            "documentID=399765&csIID=69335"
        )


def test_client_posts_verified_case_search_fields() -> None:
    session = FakeSession(
        [
            FakeResponse(
                text=fixture_text("empty_results.html"),
                url=dc_cases.CASE_SEARCH_URL,
            ),
            FakeResponse(
                text=fixture_text("case_results.html"),
                url=dc_cases.CASE_SEARCH_URL,
            ),
        ]
    )
    client = dc_cases.DCAppellateCasesClient(
        session=session,
        minimum_interval=0,
    )

    page = client.fetch_page(
        "search",
        {
            "appellate_case_number": "",
            "caption": "Smith",
            "originating_case_number": "1998-CA-007597",
            "date_from_native": "01/01/1998",
            "date_to_native": "12/31/1999",
            "open_only": True,
            "order_by": "CsNumber",
            "order_direction": "DESC",
        },
        start_row=1,
    )

    assert len(page.records) == 2
    assert session.calls[0]["method"] == "GET"
    posted = session.calls[1]["data"]
    assert posted["shortTitle"] == "Smith"
    assert posted["lcCsNumber"] == "1998-CA-007597"
    assert posted["fromDt"] == "01/01/1998"
    assert posted["toDt"] == "12/31/1999"
    assert posted["exclude"] == "on"
    assert posted["startRow"] == "1"
    assert posted["displayRows"] == "50"


def test_client_posts_verified_participant_fields() -> None:
    session = FakeSession(
        [
            FakeResponse(
                text=fixture_text("participant_results.html"),
                url=dc_cases.PARTICIPANT_SEARCH_URL,
            ),
            FakeResponse(
                text=fixture_text("participant_results.html"),
                url=dc_cases.PARTICIPANT_SEARCH_URL,
            ),
        ]
    )
    client = dc_cases.DCAppellateCasesClient(
        session=session,
        minimum_interval=0,
    )

    page = client.fetch_page(
        "participant",
        {
            "last_name": "Alpert",
            "first_name": "Marc",
            "middle_name": "S",
            "order_by": "FileDt",
            "order_direction": "DESC",
        },
        start_row=1,
    )

    assert len(page.records) == 2
    posted = session.calls[1]["data"]
    assert posted["lastNm"] == "Alpert"
    assert posted["firstNm"] == "Marc"
    assert posted["middleNm"] == "S"
    assert posted["orderBy"] == "FileDt"


def test_client_accepts_exact_search_redirect_to_case_view() -> None:
    case_url = f"{dc_cases.BASE_URL}{dc_cases.CASE_VIEW_PATH}?csIID=69335"
    session = FakeSession(
        [
            FakeResponse(
                text=fixture_text("empty_results.html"),
                url=dc_cases.CASE_SEARCH_URL,
            ),
            FakeResponse(
                text=fixture_text("case_view.html"),
                url=case_url,
            ),
        ]
    )
    client = dc_cases.DCAppellateCasesClient(
        session=session,
        minimum_interval=0,
    )

    page = client.fetch_page(
        "search",
        {
            "appellate_case_number": "24-BG-1045",
            "caption": "",
            "originating_case_number": "",
            "date_from_native": "",
            "date_to_native": "",
            "open_only": False,
        },
        start_row=1,
    )

    assert page.total_rows == 1
    assert page.records[0]["record_kind"] == "case"
    assert page.records[0]["originating_case_number"] == "DDN 2024-D175"


def test_client_resolves_document_locator_with_verified_dwr_shape() -> None:
    session = FakeSession(
        [
            FakeResponse(
                text=fixture_text("document_links.dwr"),
                url=dc_cases.DOCUMENT_RESOLVER_URL,
                headers={"Content-Type": "text/plain"},
            )
        ]
    )
    client = dc_cases.DCAppellateCasesClient(
        session=session,
        minimum_interval=0,
    )

    records = client.resolve_document_locator(
        case_number="24-BG-1045",
        locator={
            "method_code": "50",
            "event_id": "1697111",
            "case_id": "69335",
        },
    )

    assert records[0]["native_document_id"] == "399765"
    posted = session.calls[0]["data"]
    assert posted["c0-methodName"] == "getViewDocumentLinks"
    assert posted["c0-param0"] == "string:50"
    assert posted["c0-param1"] == "string:1697111"
    assert posted["c0-param2"] == "string:69335"


def test_client_download_validates_pdf_and_filename() -> None:
    url = (
        f"{dc_cases.BASE_URL}{dc_cases.DOCUMENT_VIEW_PATH}?"
        "documentID=399765&csIID=69335"
    )
    session = FakeSession(
        [
            FakeResponse(
                content=b"%PDF-1.6 fixture",
                url=url,
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Disposition": (
                        'attachment; filename="Redaction Certificate.pdf"'
                    ),
                },
            )
        ]
    )
    client = dc_cases.DCAppellateCasesClient(
        session=session,
        minimum_interval=0,
    )

    document = client.fetch_document(url)

    assert document.filename == "Redaction Certificate.pdf"
    assert document.media_type == "application/octet-stream"
    assert len(document.sha256) == 64


def test_resolve_case_documents_attaches_documents_to_event_and_case() -> None:
    record = dc_cases.parse_case_view(
        fixture_text("case_view.html"),
        source_url=dc_cases.BASE_URL,
    )

    class Resolver:
        def resolve_document_locator(
            self,
            *,
            case_number: str,
            locator: dict[str, str],
        ) -> list[dict[str, Any]]:
            assert case_number == "24-BG-1045"
            assert locator["event_id"] == "1697111"
            return [{"native_document_id": "399765", "source_url": "official"}]

    enriched = dc_cases.DCAppellateCasesClient.resolve_case_documents(
        Resolver(),
        record,
    )

    assert enriched["docket_events"][1]["document_state"] == "resolved"
    assert enriched["docket_events"][1]["documents"][0][
        "native_document_id"
    ] == "399765"
    assert enriched["documents"][0]["source_url"] == "official"


def test_cursor_binds_to_operation_and_filters() -> None:
    selection = {
        "caption": "Smith",
        "appellate_case_number": "",
        "originating_case_number": "",
    }
    cursor = dc_cases._encode_cursor("search", selection, 51)
    args = type(
        "Args",
        (),
        {"cursor": cursor, "start_row": None},
    )()

    assert (
        dc_cases._start_row(
            args,
            operation="search",
            selection=selection,
        )
        == 51
    )
    with pytest.raises(dc_cases.DCAppellateSelectionError) as raised:
        dc_cases._start_row(
            args,
            operation="search",
            selection={**selection, "caption": "Jones"},
        )
    assert raised.value.code == "cursor_query_mismatch"


def test_empty_case_search_needs_explicit_all_records() -> None:
    args = dc_cases.build_parser().parse_args(["search", "--page-only"])

    with pytest.raises(dc_cases.DCAppellateSelectionError) as raised:
        dc_cases._selection(args)

    assert raised.value.code == "empty_search"


def test_routes_execute_returns_operation_states_without_network() -> None:
    args = dc_cases.build_parser().parse_args(["routes"])
    result = dc_cases.execute(args, log_results=False)

    assert result.status == ResultStatus.OK
    record = result.records[0]
    outcomes = {
        item["source_id"]: item
        for item in record["component_access_outcomes"]
    }
    assert outcomes["us-dc-superior-eaccess"]["operation"] == "case_search"


def test_case_execute_resolves_documents_by_default() -> None:
    record = dc_cases.parse_case_view(
        fixture_text("case_view.html"),
        source_url=dc_cases.BASE_URL,
    )

    class FakeClient:
        def find_case(self, case_number: str) -> dict[str, Any]:
            assert case_number == "24-BG-1045"
            return record

        def resolve_case_documents(
            self,
            case_record: dict[str, Any],
        ) -> dict[str, Any]:
            return {
                **case_record,
                "documents": [
                    {
                        "source_url": (
                            f"{dc_cases.BASE_URL}"
                            "/document/view.do?"
                            "documentID=399765&csIID=69335"
                        )
                    }
                ],
            }

    args = dc_cases.build_parser().parse_args(["case", "24-BG-1045"])
    result = dc_cases.execute(
        args,
        client=FakeClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert result.records[0]["documents"]


def test_download_execute_writes_validated_artifact(tmp_path: Path) -> None:
    url = (
        f"{dc_cases.BASE_URL}{dc_cases.DOCUMENT_VIEW_PATH}?"
        "documentID=399765&csIID=69335"
    )

    class FakeClient:
        def fetch_document(self, source_url: str) -> dc_cases.DCAppellateDocument:
            assert source_url == url
            content = b"%PDF-1.6 fixture"
            return dc_cases.DCAppellateDocument(
                source_url=url,
                content=content,
                media_type="application/octet-stream",
                filename="fixture.pdf",
                sha256="a" * 64,
            )

    destination = tmp_path / "filing.pdf"
    args = dc_cases.build_parser().parse_args(
        ["download", url, str(destination)]
    )
    result = dc_cases.execute(
        args,
        client=FakeClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert destination.read_bytes() == b"%PDF-1.6 fixture"
    assert result.records[0]["native_document_id"] == "399765"
