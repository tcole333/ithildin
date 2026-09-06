from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pytest

from tools import query_ohio_reporter_decisions as rod
from tools.public_records_contract import ResultStatus


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_reporter_decisions"
)


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text()


def fixture_pdf() -> bytes:
    return bytes.fromhex(fixture_text("document.pdf.hex").strip())


class FakeResponse:
    def __init__(
        self,
        *,
        url: str = rod.BASE_URL,
        text: str = "",
        content: bytes | None = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = url
        self.text = text
        self.content = (
            content if content is not None else text.encode("utf-8")
        )
        self.status_code = status_code
        self.headers = headers or {}


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []
        self.headers: dict[str, str] = {}
        self.closed = False

    def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> FakeResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def html_response(name: str) -> FakeResponse:
    return FakeResponse(
        text=fixture_text(name),
        headers={"Content-Type": "text/html; charset=utf-8"},
    )


def pdf_response(
    *,
    url: str = (
        "https://www.supremecourt.ohio.gov/rod/docs/pdf/0/2018/"
        "2018-Ohio-723.pdf"
    ),
    content_type: str = "application/pdf",
) -> FakeResponse:
    return FakeResponse(
        url=url,
        content=fixture_pdf(),
        headers={"Content-Type": content_type},
    )


def parser_args(*values: str) -> argparse.Namespace:
    return rod.build_parser().parse_args(list(values))


def test_webcite_and_publication_document_identities_are_distinct() -> None:
    page = rod.parse_search_page(fixture_text("publication.html"))

    assert rod.normalize_webcite("2018-ohio-0723") == "2018-Ohio-723"
    assert page.total_rows == 1
    record = page.records[0]
    assert record["webcite"] == "2018-Ohio-723"
    assert record["case_number"] is None
    assert record["caption"] == "02/28/2018 Case Announcements"
    assert record["decided_date"] == "2018-02-28"
    assert record["court_id"] == "oh-supreme-court"
    assert record["canonical_ref"] != record["document_ref"]
    assert record["identity"]["case_number_role"] == "optional_case_join"


def test_district_result_retains_deciding_source_and_county() -> None:
    page = rod.parse_search_page(
        fixture_text("search-page-1.html"),
        expected_page=1,
    )

    assert page.total_rows == 3
    assert page.page_size == 2
    assert page.total_pages == 2
    record = page.records[0]
    assert record["webcite"] == "2026-Ohio-2912"
    assert record["case_number"] == "C-250425"
    assert record["court_id"] == "oh-court-of-appeals-district-1"
    assert record["source_native_court_code"] == "1"
    assert record["county"] == "Hamilton"
    assert "print_citation" not in record


def test_source_validation_message_is_not_an_authoritative_empty() -> None:
    with pytest.raises(
        rod.OhioReporterRefinementRequired,
        match="Year Decided To",
    ) as caught:
        rod.parse_search_page(fixture_text("refinement.html"))

    assert caught.value.details["authoritative_empty"] is False
    assert caught.value.code == "source_requires_refinement"


def test_client_exhausts_native_webforms_pages(monkeypatch) -> None:
    monkeypatch.setattr(rod, "NATIVE_PAGE_SIZE", 2)
    session = FakeSession(
        [
            html_response("search-page-1.html"),
            html_response("search-page-1.html"),
            html_response("search-page-2.html"),
        ]
    )
    client = rod.OhioReporterClient(
        session=session,
        minimum_interval=0,
        max_retries=0,
    )

    collection = client.fetch_all(
        {"court_code": "1", "year": 2026}
    )

    assert collection.incomplete_error is None
    assert collection.total_rows == 3
    assert collection.pages_fetched == 2
    assert [record["webcite"] for record in collection.records] == [
        "2026-Ohio-2912",
        "2026-Ohio-2901",
        "2026-Ohio-2888",
    ]
    assert len(session.requests) == 3
    first_post = session.requests[1]
    assert first_post["data"][rod._FORM_FIELDS["rows_per_page"]] == "2"
    assert first_post["data"][rod._FORM_FIELDS["court"]] == "1"
    page_post = session.requests[2]
    assert page_post["data"]["__VIEWSTATE"] == "page-one-state"
    assert page_post["data"]["__EVENTTARGET"] == rod.PAGER_EVENT_TARGET
    assert page_post["data"]["__EVENTARGUMENT"] == "Page$2"


def test_search_records_effective_source_defaults(monkeypatch) -> None:
    monkeypatch.setattr(rod, "NATIVE_PAGE_SIZE", 2)
    client = rod.OhioReporterClient(
        session=FakeSession(
            [
                html_response("search-page-1.html"),
                html_response("search-page-1.html"),
                html_response("search-page-2.html"),
            ]
        ),
        minimum_interval=0,
        max_retries=0,
    )

    result = rod.execute(
        parser_args(
            "search",
            "--source",
            "district-1",
        ),
        client=client,
        log_results=False,
    )

    effective = result.query.query.parameters[
        "effective_source_selection"
    ]
    assert result.query.query.parameters["year"] is None
    assert effective["source"] == {
        "value": "1",
        "label": "First District Court of Appeals",
    }
    assert effective["year_from"]["value"] == "2026"
    assert effective["year_to"]["value"] == "2026"
    assert effective["native_page_size"]["value"] == "2"


def test_pagination_shape_change_returns_explicit_partial_collection(
    monkeypatch,
) -> None:
    monkeypatch.setattr(rod, "NATIVE_PAGE_SIZE", 2)
    session = FakeSession(
        [
            html_response("search-page-1.html"),
            html_response("search-page-1.html"),
            html_response("search-page-1.html"),
        ]
    )
    client = rod.OhioReporterClient(
        session=session,
        minimum_interval=0,
        max_retries=0,
    )

    collection = client.fetch_all(
        {"court_code": "1", "year": 2026}
    )

    assert len(collection.records) == 2
    assert collection.incomplete_error is not None
    assert collection.incomplete_error.status == ResultStatus.PARTIAL
    assert collection.incomplete_error.code == "native_pagination_incomplete"


def test_exact_webcite_empty_is_authoritative_no_results() -> None:
    session = FakeSession(
        [
            html_response("search-page-1.html"),
            html_response("empty.html"),
        ]
    )
    client = rod.OhioReporterClient(
        session=session,
        minimum_interval=0,
        max_retries=0,
    )

    result = rod.execute(
        parser_args("publication", "2026-Ohio-9999"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_exact_webcite_submission_uses_unique_document_fields() -> None:
    session = FakeSession(
        [
            html_response("search-page-1.html"),
            html_response("publication.html"),
        ]
    )
    client = rod.OhioReporterClient(
        session=session,
        minimum_interval=0,
        max_retries=0,
    )

    collection = client.publication("2018-Ohio-723")

    assert len(collection.records) == 1
    post = session.requests[1]["data"]
    assert post[rod._FORM_FIELDS["webcite_year"]] == "2018"
    assert post[rod._FORM_FIELDS["webcite_number"]] == "723"
    assert post[rod._FORM_FIELDS["rows_per_page"]] == "200"


def test_pdf_response_validates_media_signature_host_and_identity() -> None:
    url = (
        "https://www.supremecourt.ohio.gov/rod/docs/pdf/0/2018/"
        "2018-Ohio-723.pdf"
    )
    client = rod.OhioReporterClient(
        session=FakeSession([pdf_response(url=url)]),
        minimum_interval=0,
        max_retries=0,
    )

    artifact = client.fetch_pdf(
        url,
        expected_webcite="2018-Ohio-723",
        expected_source_code="0",
    )

    assert artifact.media_type == "application/pdf"
    assert artifact.content.startswith(b"%PDF-")
    assert artifact.webcite == "2018-Ohio-723"
    assert artifact.source_code == "0"
    assert len(artifact.sha256) == 64

    bad_client = rod.OhioReporterClient(
        session=FakeSession(
            [pdf_response(url=url, content_type="text/html")]
        ),
        minimum_interval=0,
        max_retries=0,
    )
    with pytest.raises(
        rod.OhioReporterSourceChanged,
        match="did not return a PDF",
    ):
        bad_client.fetch_pdf(
            url,
            expected_webcite="2018-Ohio-723",
            expected_source_code="0",
        )


def test_document_command_resolves_publication_before_writing(
    tmp_path: Path,
) -> None:
    session = FakeSession(
        [
            html_response("search-page-1.html"),
            html_response("publication.html"),
            pdf_response(),
        ]
    )
    client = rod.OhioReporterClient(
        session=session,
        minimum_interval=0,
        max_retries=0,
    )
    destination = tmp_path / "2018-Ohio-723.pdf"

    result = rod.execute(
        parser_args(
            "document",
            "2018-Ohio-723",
            str(destination),
        ),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert destination.read_bytes() == fixture_pdf()
    record = result.records[0]
    assert record["record_kind"] == "judicial_publication_document"
    assert record["publication_ref"].endswith(
        "/2018-Ohio-723/publication"
    )
    assert record["canonical_ref"].endswith(
        "/2018-Ohio-723/document/2018-Ohio-723.pdf"
    )
    assert record["signature"] == "%PDF-"


def test_owned_session_closes_and_caller_session_stays_open(
    monkeypatch,
) -> None:
    owned = FakeSession(
        [
            html_response("search-page-1.html"),
            html_response("publication.html"),
        ]
    )
    monkeypatch.setattr(rod.requests, "Session", lambda: owned)

    result = rod.execute(
        parser_args("publication", "2018-Ohio-723"),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert owned.closed is True

    caller = FakeSession([])
    rod.OhioReporterClient(session=caller).close()
    assert caller.closed is False


def test_caller_windows_bind_query_and_ordered_membership() -> None:
    records = list(
        rod.parse_search_page(
            fixture_text("search-page-1.html")
        ).records
    ) + list(
        rod.parse_search_page(
            fixture_text("search-page-2.html"),
            expected_page=2,
        ).records
    )
    selection = {"operation": "search", "source": "district-1"}

    first, cursor = rod._window_records(
        records,
        selection=selection,
        limit=2,
        cursor=None,
    )
    assert len(first) == 2
    assert cursor is not None

    second, next_cursor = rod._window_records(
        records,
        selection=selection,
        limit=2,
        cursor=cursor,
    )
    assert [record["webcite"] for record in second] == [
        "2026-Ohio-2888"
    ]
    assert next_cursor is None

    with pytest.raises(
        rod.OhioReporterSelectionError,
        match="another selector set",
    ):
        rod._window_records(
            records,
            selection={"operation": "search", "source": "supreme"},
            limit=2,
            cursor=cursor,
        )
    with pytest.raises(
        rod.OhioReporterSelectionError,
        match="membership changed",
    ):
        rod._window_records(
            list(reversed(records)),
            selection=selection,
            limit=2,
            cursor=cursor,
        )


def test_full_text_boundary_is_partial_after_all_source_rows() -> None:
    records = tuple(
        {
            "webcite": f"2026-Ohio-{number}",
            "canonical_ref": f"publication-{number}",
        }
        for number in range(1, rod.FULL_TEXT_RESULT_BOUNDARY + 1)
    )
    collection = rod.ReporterCollection(
        records=records,
        total_rows=rod.FULL_TEXT_RESULT_BOUNDARY,
        page_size=rod.NATIVE_PAGE_SIZE,
        total_pages=5,
        pages_fetched=5,
        selected_values={},
        selected_labels={},
        source_urls=(rod.BASE_URL,) * 5,
        schema_fingerprints=("schema",) * 5,
    )
    native_selection = {"query_text": "court", "court_code": "99"}
    selection = {
        "operation": "search",
        "parameters": native_selection,
    }
    query = rod._query("search", parameters=native_selection)

    result = rod._collection_result(
        query,
        collection,
        selection=selection,
        limit=None,
        cursor=None,
    )

    assert result.status == ResultStatus.PARTIAL
    assert len(result.records) == rod.FULL_TEXT_RESULT_BOUNDARY
    assert result.errors[0].code == (
        "documented_full_text_result_boundary"
    )
    assert result.records[0]["retrieval"][
        "native_pagination_complete"
    ] is True
    assert result.records[0]["retrieval"][
        "documented_full_text_boundary_reached"
    ] is True


def test_same_count_without_full_text_is_not_assumed_bounded() -> None:
    records = tuple(
        {"webcite": f"2026-Ohio-{number}"}
        for number in range(1, rod.FULL_TEXT_RESULT_BOUNDARY + 1)
    )
    collection = rod.ReporterCollection(
        records=records,
        total_rows=rod.FULL_TEXT_RESULT_BOUNDARY,
        page_size=rod.NATIVE_PAGE_SIZE,
        total_pages=5,
        pages_fetched=5,
        selected_values={},
        selected_labels={},
        source_urls=(rod.BASE_URL,) * 5,
        schema_fingerprints=("schema",) * 5,
    )
    native_selection = {"query_text": "", "court_code": "99"}
    selection = {
        "operation": "search",
        "parameters": native_selection,
    }
    result = rod._collection_result(
        rod._query("search", parameters=native_selection),
        collection,
        selection=selection,
        limit=None,
        cursor=None,
    )

    assert result.status == ResultStatus.OK
    assert result.errors == ()


def test_schema_and_provenance_changes_fail_visibly() -> None:
    changed_header = fixture_text("publication.html").replace(
        "Topics and Issues",
        "Summary",
        1,
    )
    with pytest.raises(
        rod.OhioReporterSourceChanged,
        match="headers changed",
    ):
        rod.parse_search_page(changed_header)

    with pytest.raises(
        rod.OhioReporterSourceChanged,
        match="official HTTPS host",
    ):
        rod._parse_pdf_url(
            "https://example.com/rod/docs/pdf/0/2018/"
            "2018-Ohio-723.pdf"
        )


def test_source_contract_models_complements_not_corroboration() -> None:
    record = rod._source_record()

    assert record["identities"] == {
        "publication": "WebCite",
        "case": "optional deciding-court case number",
        "document": "WebCite plus official PDF representation",
        "source_attribution": "PDF path source code",
    }
    assert "do not independently corroborate" in record[
        "complementary_sources"
    ]["relationship"]
    assert record["source_semantics"]["full_text_result_boundary"] == 1000


def test_parser_has_no_default_result_or_text_cap() -> None:
    args = parser_args(
        "search",
        "--text",
        "a deliberately long source-native query string",
        "--source",
        "all",
        "--year-from",
        "2018",
    )

    assert args.limit is None
    assert args.text == "a deliberately long source-native query string"
    assert args.year_to is None
