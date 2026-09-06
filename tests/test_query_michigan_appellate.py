from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_michigan_appellate as mi
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURE_DIR = Path("tests/fixtures/public_records/michigan_appellate")


def _fixture(name: str) -> dict[str, Any]:
    value = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


CASES_PAGE_1 = _fixture("cases-page-1.json")
CASES_PAGE_2 = _fixture("cases-page-2.json")
OPINIONS_PAGE = _fixture("opinions-page.json")
ORDERS_PAGE = _fixture("orders-page.json")


@dataclass
class FixtureResponse:
    body: dict[str, Any] | bytes | str
    status_code: int = 200
    url: str = mi.SEARCH_ENDPOINTS["cases"]
    headers: dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "application/json"}
    )

    @property
    def content(self) -> bytes:
        if isinstance(self.body, bytes):
            return self.body
        if isinstance(self.body, str):
            return self.body.encode("utf-8")
        return json.dumps(self.body).encode("utf-8")

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        if isinstance(self.body, dict):
            return self.body
        return json.loads(self.text)


class SequenceSession:
    def __init__(self, *responses: FixtureResponse) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.headers: dict[str, str] = {}
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> FixtureResponse:
        self.calls.append({"url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected GET {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def _client(
    *responses: FixtureResponse,
) -> tuple[mi.MichiganAppellateClient, SequenceSession]:
    session = SequenceSession(*responses)
    return (
        mi.MichiganAppellateClient(
            session=session,
            minimum_interval=0,
            retry_policy=RetryPolicy(max_attempts=1),
        ),
        session,
    )


def _parse(*values: str) -> argparse.Namespace:
    return mi.build_parser().parse_args(list(values))


def test_source_and_parser_expose_all_official_result_roles() -> None:
    assert mi.SOURCE_METADATA.source_id == ("us-mi-appellate-case-opinion-order-search")
    assert set(mi.SEARCH_ENDPOINTS) == {"cases", "opinions", "orders"}

    search = _parse(
        "search",
        "Epstein",
        "--result-type",
        "opinions",
        "--party-name",
        "Jordan Epstein",
        "--resource",
        "opinion",
        "--native-param",
        "aFutureField=value",
        "--limit",
        "25",
        "--output",
        "results.json",
    )
    overview = _parse("overview", "Epstein", "--json")
    routes = _parse("routes", "--json")
    probe = _parse("probe", "--query", "insurance")

    assert search.result_type == "opinions"
    assert search.party_name == "Jordan Epstein"
    assert search.limit == 25
    assert search.output == "results.json"
    assert overview.command == "overview"
    assert routes.command == "routes"
    assert probe.query_text == "insurance"


def test_page_parser_uses_total_pages_when_has_more_flag_is_false() -> None:
    page = mi.parse_search_payload(
        CASES_PAGE_1,
        result_type="cases",
        requested_page=1,
        source_url="https://example.test/cases?page=1",
    )

    assert page.current_page == 1
    assert page.total_pages == 2
    assert page.total_results == 3
    assert page.next_page == 2
    assert CASES_PAGE_1["hasMoreResults"] is False
    assert len(page.schema_fingerprint) == 64
    assert page.facets[0]["queryStringKey"] == "court"


def test_case_normalization_prefers_route_over_inconsistent_flags() -> None:
    page = mi.parse_search_payload(
        CASES_PAGE_1,
        result_type="cases",
        requested_page=1,
        source_url=mi.SEARCH_ENDPOINTS["cases"],
    )
    record = mi.normalize_item(
        page.records[0],
        result_type="cases",
        source_url=page.source_url,
        source_schema_fingerprint=page.schema_fingerprint,
        retrieval={"native_page": 1},
    )

    assert page.records[0]["isCourtOfAppealsCase"] is False
    assert record["court"]["court_id"] == "us-mi-court-of-appeals"
    assert record["court"]["identity_basis"] == "case_url_route"
    assert record["raw_case_number"] == "360440"
    assert record["join_keys"]["coa_case_number"] == "360440"
    assert record["join_keys"]["attorney_p_numbers"] == ["38101"]
    assert record["attorneys"][0]["bar_number"] == "P38101"
    assert record["lower_courts"] == ["WAYNE CIRCUIT COURT"]
    assert record["document"] is None
    assert record["canonical_ref"].startswith("STATECOURT:")


def test_opinion_and_order_keep_documents_and_distinct_courts() -> None:
    opinion_page = mi.parse_search_payload(
        OPINIONS_PAGE,
        result_type="opinions",
        requested_page=1,
        source_url=mi.SEARCH_ENDPOINTS["opinions"],
    )
    order_page = mi.parse_search_payload(
        ORDERS_PAGE,
        result_type="orders",
        requested_page=1,
        source_url=mi.SEARCH_ENDPOINTS["orders"],
    )

    opinion = mi.normalize_item(
        opinion_page.records[0],
        result_type="opinions",
        source_url=opinion_page.source_url,
        source_schema_fingerprint=opinion_page.schema_fingerprint,
        retrieval={},
    )
    order = mi.normalize_item(
        order_page.records[0],
        result_type="orders",
        source_url=order_page.source_url,
        source_schema_fingerprint=order_page.schema_fingerprint,
        retrieval={},
    )

    assert opinion["record_kind"] == "appellate_opinion"
    assert opinion["court"]["court_id"] == "us-mi-court-of-appeals"
    assert opinion["raw_case_number"] == "367360"
    assert opinion["document"]["document_type"] == ("court_of_appeals_opinion")
    assert opinion["document"]["native_document_id"].endswith(".opn.pdf")
    assert opinion["filing_or_release_date"] == "2026-07-22"
    assert opinion["is_published"] is False

    assert order["record_kind"] == "appellate_order"
    assert order["court"]["court_id"] == "us-mi-supreme-court"
    assert order["raw_case_number"] == "166702"
    assert order["join_keys"]["coa_case_number"] == "350655"
    assert order["document"]["document_type"] == "supreme_court_order"


def test_native_and_convenience_filters_are_composable() -> None:
    args = _parse(
        "search",
        "--result-type",
        "cases",
        "--appellate-court",
        "Court Of Appeals",
        "--party-name",
        "Epstein",
        "--open-only",
        "--court",
        "WAYNE CIRCUIT COURT",
        "--court",
        "OAKLAND CIRCUIT COURT",
        "--native-param",
        "aFutureField=one",
        "--native-param",
        "aFutureField=two",
    )

    parameters = mi.parameters_from_args(args)

    assert parameters["aAppellateCourt"] == "Court Of Appeals"
    assert parameters["aPartyName"] == "Epstein"
    assert parameters["aOpenStatus"] == "true"
    assert parameters["court"] == ("WAYNE CIRCUIT COURT,OAKLAND CIRCUIT COURT")
    assert parameters["aFutureField"] == "one,two"


def test_invalid_native_parameter_is_an_explicit_selection_error() -> None:
    args = _parse(
        "search",
        "--native-param",
        "missing-separator",
    )

    with pytest.raises(mi.MichiganSelectionError, match="KEY=VALUE"):
        mi.parameters_from_args(args)


def test_client_sends_exact_paginated_query_parameters() -> None:
    client, session = _client(FixtureResponse(CASES_PAGE_1))

    page = client.fetch_page(
        result_type="cases",
        query_text="Epstein",
        sort_order="Newest",
        page=1,
        page_size=2,
        filters={
            "aPartyName": "Epstein",
            "court": "WAYNE CIRCUIT COURT",
        },
    )

    assert page.total_results == 3
    call = session.calls[0]
    assert call["url"] == mi.SEARCH_ENDPOINTS["cases"]
    assert call["params"] == {
        "aPartyName": "Epstein",
        "court": "WAYNE CIRCUIT COURT",
        "searchQuery": "Epstein",
        "sortOrder": "Newest",
        "page": 1,
        "pageSize": 2,
    }


def test_client_traverses_pages_despite_false_has_more_results() -> None:
    client, session = _client(
        FixtureResponse(CASES_PAGE_1),
        FixtureResponse(CASES_PAGE_2),
    )

    collection = client.search(
        result_type="cases",
        query_text="Epstein",
        sort_order="Newest",
        page_size=2,
        start_page=1,
        start_offset=0,
        limit=3,
        filters={},
    )

    assert [record["raw_case_number"] for record in collection.records] == [
        "360440",
        "162354",
        "271745",
    ]
    assert collection.pages_fetched == 2
    assert collection.total_results == 3
    assert collection.next_page is None
    assert [call["params"]["page"] for call in session.calls] == [1, 2]


def test_cursor_resumes_at_next_native_page_and_rejects_other_query() -> None:
    fingerprint = mi._query_fingerprint(
        "cases",
        "Epstein",
        "Newest",
        2,
        {},
    )
    cursor = mi.make_cursor(
        result_type="cases",
        page=2,
        offset=0,
        query_fingerprint=fingerprint,
    )

    assert mi.parse_cursor(
        cursor,
        result_type="cases",
        query_fingerprint=fingerprint,
    ) == (2, 0)
    with pytest.raises(mi.MichiganSelectionError, match="different query"):
        mi.parse_cursor(
            cursor,
            result_type="cases",
            query_fingerprint="0" * 16,
        )


def test_late_page_failure_returns_resumable_partial_collection() -> None:
    client, _ = _client(
        FixtureResponse(CASES_PAGE_1),
        FixtureResponse(
            "temporary failure",
            status_code=503,
            url=mi.SEARCH_ENDPOINTS["cases"],
            headers={"Content-Type": "text/plain"},
        ),
    )

    collection = client.search(
        result_type="cases",
        query_text="Epstein",
        sort_order="Newest",
        page_size=2,
        start_page=1,
        start_offset=0,
        limit=3,
        filters={},
    )

    assert len(collection.records) == 2
    assert collection.next_page == 2
    assert collection.next_offset == 0
    assert isinstance(
        collection.incomplete_error,
        mi.MichiganTransportError,
    )


def test_empty_page_is_authoritative_but_schema_change_is_not() -> None:
    empty = {
        **OPINIONS_PAGE,
        "resultCount": 0,
        "searchItems": [],
        "totalPages": 0,
        "totalResults": 0,
    }
    page = mi.parse_search_payload(
        empty,
        result_type="opinions",
        requested_page=1,
        source_url=mi.SEARCH_ENDPOINTS["opinions"],
    )
    assert page.records == ()
    assert page.next_page is None

    changed = dict(OPINIONS_PAGE)
    changed.pop("searchItems")
    with pytest.raises(mi.MichiganSourceChangedError) as raised:
        mi.parse_search_payload(
            changed,
            result_type="opinions",
            requested_page=1,
            source_url=mi.SEARCH_ENDPOINTS["opinions"],
        )
    assert raised.value.status is ResultStatus.SOURCE_CHANGED


def test_overview_parser_keeps_category_totals_and_record_roles() -> None:
    payload = {
        "caseDetailResults": CASES_PAGE_1,
        "opinionResults": OPINIONS_PAGE,
        "orderResults": ORDERS_PAGE,
        "typedSearchForAllResultsPage": None,
    }

    pages = mi.parse_overview_payload(
        payload,
        source_url=mi.OVERVIEW_URL,
    )

    assert set(pages) == {"cases", "opinions", "orders"}
    assert pages["cases"].total_results == 3
    assert pages["opinions"].records[0]["documentUrl"].endswith(".pdf")
    assert pages["orders"].records[0]["isSupremeCourtDocument"] is True


def test_execute_emits_valid_contract_and_resumable_cursor() -> None:
    args = _parse(
        "search",
        "Epstein",
        "--result-type",
        "cases",
        "--sort",
        "Newest",
        "--page-size",
        "2",
        "--limit",
        "2",
    )
    client, _ = _client(FixtureResponse(CASES_PAGE_1))

    result = mi.execute(args, client=client, log_results=False)
    lineage = validate_envelope(result.to_dict())

    assert lineage["source_id"] == mi.SOURCE_ID
    assert result.status is ResultStatus.OK
    assert len(result.records) == 2
    assert result.next_cursor is not None
    assert ":page:2:offset:0:" in result.next_cursor
    assert result.query.query.parameters["result_type"] == "cases"


def test_execute_distinguishes_no_results_from_source_failure() -> None:
    empty = {
        **OPINIONS_PAGE,
        "resultCount": 0,
        "searchItems": [],
        "totalPages": 0,
        "totalResults": 0,
    }
    args = _parse(
        "search",
        "not-present",
        "--result-type",
        "opinions",
        "--page-size",
        "1",
    )
    empty_client, _ = _client(FixtureResponse(empty))
    empty_result = mi.execute(args, client=empty_client, log_results=False)
    assert empty_result.status is ResultStatus.NO_RESULTS
    assert empty_result.errors == ()

    failed_client, _ = _client(
        FixtureResponse(
            "rate limited",
            status_code=429,
            headers={"Content-Type": "text/plain"},
        )
    )
    failed_result = mi.execute(args, client=failed_client, log_results=False)
    assert failed_result.status is ResultStatus.RATE_LIMITED
    assert failed_result.errors[0].code == "rate_limited"


def test_download_validates_official_pdf_before_writing(tmp_path: Path) -> None:
    pdf = b"%PDF-1.7\nMichigan fixture\n%%EOF\n"
    document_url = f"{mi.BASE_URL}/siteassets/case-documents/opinion-fixture.pdf"
    client, _ = _client(
        FixtureResponse(
            pdf,
            url=document_url,
            headers={"Content-Type": "application/pdf"},
        )
    )

    document = client.download(document_url)

    assert document.content == pdf
    assert document.media_type == "application/pdf"
    assert document.filename == "opinion-fixture.pdf"
    assert document.sha256 == (
        "7829e08f542b48eeb66ef032dae8b1dd6e263af99ff72aa5ae081740b775a727"
    )
    with pytest.raises(mi.MichiganSelectionError):
        client.download("https://example.com/not-official.pdf")

    args = _parse(
        "download",
        document_url,
        str(tmp_path / "opinion.pdf"),
    )
    client_for_execute, _ = _client(
        FixtureResponse(
            pdf,
            url=document_url,
            headers={"Content-Type": "application/pdf"},
        )
    )
    result = mi.execute(args, client=client_for_execute, log_results=False)
    assert result.status is ResultStatus.OK
    assert (tmp_path / "opinion.pdf").read_bytes() == pdf


def test_route_map_triages_complementary_sources_by_join_key() -> None:
    result = mi.execute(
        _parse("routes"),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    routes = {record["route_id"]: record for record in result.records}
    assert "micourt_trial_case_search" in routes
    assert "micourt_developer_api" in routes
    assert "michigan_business_court" in routes
    assert "michigan_trial_court_directory" in routes
    assert "lower_court_case_number" in routes["micourt_trial_case_search"]["join_keys"]


def test_probe_checks_page_vocabulary_each_role_and_pdf() -> None:
    class ProbeClient:
        def page_model(self) -> dict[str, Any]:
            return {
                "pageSizeOptions": [10, 25, 50, 100],
                "appellateCourtOptions": [
                    "Supreme Court",
                    "Court Of Appeals",
                ],
                "lowerCourtOptions": ["WAYNE CIRCUIT COURT"],
            }

        def fetch_page(self, *, result_type: str, **_kwargs: Any):
            payload = {
                "cases": CASES_PAGE_1,
                "opinions": OPINIONS_PAGE,
                "orders": ORDERS_PAGE,
            }[result_type]
            payload = {
                **payload,
                "pageSize": 1,
                "resultCount": min(1, len(payload["searchItems"])),
                "searchItems": payload["searchItems"][:1],
            }
            return mi.parse_search_payload(
                payload,
                result_type=result_type,
                requested_page=1,
                source_url=mi.SEARCH_ENDPOINTS[result_type],
            )

        def download(self, _url: str) -> mi.MichiganDocument:
            return mi.MichiganDocument(
                source_url=mi.PROBE_DOCUMENT_URL,
                content=b"%PDF-1.7\nfixture",
                media_type="application/pdf",
                filename="360440_6_01.pdf",
                sha256="a" * 64,
            )

    result = mi.execute(
        _parse("probe"),
        client=ProbeClient(),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    checks = result.records[0]["checks"]
    assert list(checks["page_size_options"]) == [10, 25, 50, 100]
    assert checks["lower_court_option_count"] == 1
    assert set(checks) >= {"cases", "opinions", "orders", "document"}


def test_source_schema_error_when_pdf_endpoint_returns_html() -> None:
    client, _ = _client(
        FixtureResponse(
            "<html>challenge</html>",
            url=mi.PROBE_DOCUMENT_URL,
            headers={"Content-Type": "text/html"},
        )
    )

    with pytest.raises(mi.MichiganSourceChangedError, match="not a PDF"):
        client.download(mi.PROBE_DOCUMENT_URL)
