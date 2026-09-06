from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest

from tools import query_michigan_business_court as business
from tools.public_records_http import RetryPolicy


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "michigan_business_court"
)


def _json(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        payload: dict[str, Any] | None = None,
        content: bytes | None = None,
        content_type: str = "application/json; charset=utf-8",
        status_code: int = 200,
    ) -> None:
        self.url = url
        self._payload = payload
        self.content = (
            json.dumps(payload).encode("utf-8")
            if content is None and payload is not None
            else content or b""
        )
        self.headers = {"Content-Type": content_type}
        self.status_code = status_code
        self.text = self.content.decode("utf-8", errors="replace")

    def json(self) -> dict[str, Any]:
        if self._payload is None:
            raise ValueError("not JSON")
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
        allow_redirects: bool,
    ) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "params": dict(params),
                "headers": dict(headers),
                "timeout": timeout,
                "allow_redirects": allow_redirects,
            }
        )
        if url == business.SEARCH_URL:
            query = str(params.get("searchQuery", ""))
            page = int(params["page"])
            if query == business.PROBE_ZERO_QUERY:
                payload = _json("search-zero.json")
            else:
                payload = _json(
                    "search-page-1.json"
                    if page == 1
                    else "search-page-2.json"
                )
                payload["selectedSortOption"] = params["sortOrder"]
            effective_url = f"{url}?{urlencode(params)}"
            return FakeResponse(url=effective_url, payload=payload)
        return FakeResponse(
            url=url,
            content=(FIXTURE_DIR / "sample.pdf").read_bytes(),
            content_type="application/pdf",
        )

    def close(self) -> None:
        self.closed = True


def _client(session: FakeSession | None = None) -> business.MichiganBusinessCourtClient:
    return business.MichiganBusinessCourtClient(
        session=session or FakeSession(),
        timeout=1,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )


def _context(*, courts: list[str] | None = None) -> dict[str, Any]:
    return {
        "query_text": "",
        "sort_order": "Oldest",
        "business_courts": [],
        "courts": courts or [],
        "audience": None,
    }


def test_parser_uses_total_pages_and_accepts_old_rows_with_omissions() -> None:
    payload = _json("search-page-1.json")
    page = business.parse_search_payload(
        payload,
        requested_page=1,
        source_url=business.SEARCH_URL,
    )

    assert page.page_size == 8
    assert page.total_results == 10
    assert page.total_pages == 2
    assert page.has_more_results is False
    assert page.next_page == 2
    assert "pleadingOrderDate" not in page.records[0]
    assert "caseName" not in page.records[0]
    assert "caseNumber" not in page.records[0]

    fingerprint = business._selection_fingerprint(
        query_text="",
        sort_order="Oldest",
        business_courts=(),
        courts=("Genesee County Circuit Court",),
        audience=None,
    )
    record = business.normalize_search_item(
        page.records[0],
        source_url=business.SEARCH_URL,
        source_schema_fingerprint=page.schema_fingerprint,
        native_page=1,
        native_row=1,
        page=page,
        query_context=_context(courts=["Genesee County Circuit Court"]),
        selection_fingerprint=fingerprint,
    )

    assert record["pleading_or_order_date"] is None
    assert record["case_name_observation"] is None
    assert record["case_number_observation"] is None
    assert record["document"]["source_url"] == (
        "https://www.courts.michigan.gov/4a697c/siteassets/"
        "business-court-opinions/"
        "c06-2018-167555-cb-(aug-16,-2018).pdf?download=1"
    )
    assert record["raw_source_record"]["url"].startswith("/")
    assert record["raw_source_record"]["url"].endswith("#page=2")
    assert record["source_row"]["native_total_results"] == 10
    assert record["source_row"]["native_total_pages"] == 2
    assert record["source_row"]["source_has_more_results"] is False
    assert [facet["query_string_key"] for facet in record["retrieval"]["facets"]] == [
        "businessCourt",
        "court",
    ]
    assert record["court_locator_candidates"] == [
        {
            "value": "Genesee County Circuit Court",
            "basis": "selected_single_court_facet",
            "authoritative_assignment": False,
        },
        {
            "value": "c06",
            "basis": "filename_court_code_candidate",
            "authoritative_assignment": False,
        },
    ]


def test_compound_case_label_preserves_each_published_candidate() -> None:
    page = business.parse_search_payload(
        _json("search-page-1.json"),
        requested_page=1,
        source_url=business.SEARCH_URL,
    )
    fingerprint = business._selection_fingerprint(
        query_text="",
        sort_order="Oldest",
        business_courts=(),
        courts=(),
        audience=None,
    )
    record = business.normalize_search_item(
        page.records[1],
        source_url=business.SEARCH_URL,
        source_schema_fingerprint=page.schema_fingerprint,
        native_page=1,
        native_row=2,
        page=page,
        query_context=_context(),
        selection_fingerprint=fingerprint,
    )

    assert record["case_number_observation"] == {
        "raw": "25-058317-CZ and 25-SC0059-SC",
        "candidates": ["25-058317-CZ", "25-SC0059-SC"],
        "candidate_basis": "source_caseNumber_label",
        "canonical_case_number": None,
    }


def test_document_identity_and_query_occurrence_remain_distinct() -> None:
    page = business.parse_search_payload(
        _json("search-page-1.json"),
        requested_page=1,
        source_url=business.SEARCH_URL,
    )
    first_fingerprint = business._selection_fingerprint(
        query_text="",
        sort_order="Oldest",
        business_courts=(),
        courts=(),
        audience=None,
    )
    second_fingerprint = business._selection_fingerprint(
        query_text="Alpha",
        sort_order="Relevance",
        business_courts=(),
        courts=(),
        audience=None,
    )
    first = business.normalize_search_item(
        page.records[1],
        source_url=business.SEARCH_URL,
        source_schema_fingerprint=page.schema_fingerprint,
        native_page=1,
        native_row=2,
        page=page,
        query_context=_context(),
        selection_fingerprint=first_fingerprint,
    )
    second = business.normalize_search_item(
        page.records[1],
        source_url=business.SEARCH_URL,
        source_schema_fingerprint=page.schema_fingerprint,
        native_page=1,
        native_row=2,
        page=page,
        query_context={
            **_context(),
            "query_text": "Alpha",
            "sort_order": "Relevance",
        },
        selection_fingerprint=second_fingerprint,
    )

    assert first["document"] == second["document"]
    assert first["source_occurrence_id"] != second["source_occurrence_id"]
    assert first["case_number_observation"] == second[
        "case_number_observation"
    ]


def test_client_sends_native_filters_and_exhausts_total_pages() -> None:
    session = FakeSession()
    client = _client(session)
    fingerprint = business._selection_fingerprint(
        query_text="land",
        sort_order="Oldest",
        business_courts=("Real Estate", "Contracts"),
        courts=("Oakland County Circuit Court", "Genesee County Circuit Court"),
        audience="Public",
    )

    collection = client.search(
        query_text="land",
        sort_order="Oldest",
        business_courts=("Real Estate", "Contracts"),
        courts=("Oakland County Circuit Court", "Genesee County Circuit Court"),
        audience="Public",
        start_page=1,
        start_offset=0,
        limit=None,
        selection_fingerprint=fingerprint,
    )

    assert len(collection.records) == 10
    assert collection.pages_fetched == 2
    assert collection.next_page is None
    assert [call["params"]["page"] for call in session.calls] == [1, 2]
    assert session.calls[0]["params"] == {
        "searchQuery": "land",
        "page": 1,
        "sortOrder": "Oldest",
        "businessCourt": "Real Estate,Contracts",
        "court": (
            "Oakland County Circuit Court,"
            "Genesee County Circuit Court"
        ),
        "audience": "Public",
    }


def test_limit_cursor_resumes_within_page_and_is_query_bound() -> None:
    session = FakeSession()
    client = _client(session)
    first_args = business.build_parser().parse_args(
        [
            "search",
            "land",
            "--sort",
            "Oldest",
            "--court",
            "Oakland County Circuit Court",
            "--limit",
            "3",
        ]
    )
    first = business.execute(
        first_args,
        client=client,
        log_results=False,
    )

    assert first.status.value == "ok"
    assert len(first.records) == 3
    assert first.next_cursor is not None

    second_args = business.build_parser().parse_args(
        [
            "search",
            "land",
            "--sort",
            "Oldest",
            "--court",
            "Oakland County Circuit Court",
            "--limit",
            "3",
            "--cursor",
            first.next_cursor,
        ]
    )
    second = business.execute(
        second_args,
        client=client,
        log_results=False,
    )
    assert second.status.value == "ok"
    assert len(second.records) == 3
    assert first.records[-1]["source_row"]["native_row"] == 3
    assert second.records[0]["source_row"]["native_row"] == 4

    mismatch_args = business.build_parser().parse_args(
        [
            "search",
            "different query",
            "--sort",
            "Oldest",
            "--court",
            "Oakland County Circuit Court",
            "--limit",
            "3",
            "--cursor",
            first.next_cursor,
        ]
    )
    mismatch = business.execute(
        mismatch_args,
        client=client,
        log_results=False,
    )
    assert mismatch.status.value == "unavailable"
    assert mismatch.errors[0].code == "invalid_selection"
    assert "different query" not in first.next_cursor


def test_categories_and_sources_preserve_native_facet_order_and_spacing() -> None:
    client = _client()
    categories = business.execute(
        business.build_parser().parse_args(["categories"]),
        client=client,
        log_results=False,
    )
    sources = business.execute(
        business.build_parser().parse_args(["sources"]),
        client=client,
        log_results=False,
    )

    assert [record["label"] for record in categories.records] == [
        "Contracts",
        "Real Estate",
        "Business Governance",
    ]
    assert [record["label"] for record in sources.records] == [
        "Genesee County Circuit Court",
        "Genesee  County Circuit Court",
        "Oakland County Circuit Court",
    ]
    assert [record["value_index"] for record in sources.records] == [0, 1, 2]


def test_download_validates_pdf_and_writes_digest(
    tmp_path: Path,
) -> None:
    session = FakeSession()
    client = _client(session)
    content = (FIXTURE_DIR / "sample.pdf").read_bytes()
    expected_sha = hashlib.sha256(content).hexdigest()
    destination = tmp_path / "business-opinion.pdf"
    args = business.build_parser().parse_args(
        [
            "download",
            "/4a697c/siteassets/business-court-opinions/"
            "c06-2018-167555-cb-(aug-16,-2018).pdf",
            str(destination),
            "--expected-sha256",
            expected_sha,
        ]
    )

    result = business.execute(args, client=client, log_results=False)

    assert result.status.value == "ok"
    assert destination.read_bytes() == content
    assert result.records[0]["sha256"] == expected_sha
    assert result.records[0]["media_type"] == "application/pdf"

    with pytest.raises(business.MichiganBusinessCourtSelectionError):
        client.download("https://example.com/not-official.pdf")


def test_json_and_pdf_signatures_are_validated() -> None:
    class BadJSONSession(FakeSession):
        def get(self, *args: Any, **kwargs: Any) -> FakeResponse:
            return FakeResponse(
                url=business.SEARCH_URL,
                payload=_json("search-page-1.json"),
                content=b"<html>not json</html>",
                content_type="text/html",
            )

    with pytest.raises(business.MichiganBusinessCourtSourceChanged):
        _client(BadJSONSession()).fetch_page(
            query_text="",
            page=1,
            sort_order="Oldest",
        )

    class BadPDFSession(FakeSession):
        def get(self, url: str, **_kwargs: Any) -> FakeResponse:
            return FakeResponse(
                url=url,
                content=b"<html>not pdf</html>",
                content_type="text/html",
            )

    with pytest.raises(business.MichiganBusinessCourtSourceChanged):
        _client(BadPDFSession()).download(
            "/4a697c/siteassets/business-court-opinions/example.pdf"
        )


def test_probe_checks_full_page_zero_result_facets_and_pdf() -> None:
    session = FakeSession()
    client = _client(session)
    result = business.execute(
        business.build_parser().parse_args(["probe"]),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    probe = result.records[0]
    assert probe["search_contract"]["total_results"] == 10
    assert probe["search_contract"]["total_pages"] == 2
    assert probe["search_contract"]["source_has_more_results"] is False
    assert probe["search_contract"]["category_facet_count"] == 3
    assert probe["search_contract"]["court_facet_count"] == 3
    assert probe["zero_result_contract"]["total_results"] == 0
    assert probe["document_contract"]["signature_hex"].startswith("25504446")
    assert len(session.calls) == 3


def test_search_preserves_authoritative_zero_result() -> None:
    result = business.execute(
        business.build_parser().parse_args(
            ["search", business.PROBE_ZERO_QUERY]
        ),
        client=_client(),
        log_results=False,
    )

    assert result.status.value == "no_results"
    assert result.records == ()
    assert result.next_cursor is None


def test_parser_rejects_changed_page_size_and_missing_required_item_field() -> None:
    wrong_page_size = _json("search-page-1.json")
    wrong_page_size["pageSize"] = 10
    with pytest.raises(business.MichiganBusinessCourtSourceChanged):
        business.parse_search_payload(
            wrong_page_size,
            requested_page=1,
            source_url=business.SEARCH_URL,
        )

    missing_url = deepcopy(_json("search-page-1.json"))
    del missing_url["searchItems"][0]["url"]
    with pytest.raises(
        business.MichiganBusinessCourtSourceChanged,
        match="missing expected fields",
    ):
        business.parse_search_payload(
            missing_url,
            requested_page=1,
            source_url=business.SEARCH_URL,
        )


def test_search_limit_is_optional_and_native_page_size_is_fixed() -> None:
    args = business.build_parser().parse_args(["search", "contracts"])
    assert args.limit is None
    assert business.NATIVE_PAGE_SIZE == 8
    assert tuple(business.SORT_ORDERS) == (
        "Relevance",
        "A-Z",
        "Z-A",
        "Newest",
        "Oldest",
    )
