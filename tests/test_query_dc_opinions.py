from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_dc_opinions as dc
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURE_DIR = Path("tests/fixtures/public_records/dc_opinions")
LIST_HTML = (FIXTURE_DIR / "list_page.html").read_text(encoding="utf-8")
NO_RESULTS_HTML = (FIXTURE_DIR / "no_results.html").read_text(
    encoding="utf-8"
)
SOURCE_CHANGED_HTML = (FIXTURE_DIR / "source_changed.html").read_text(
    encoding="utf-8"
)
PDF_BYTES = b"%PDF-1.7\nfixture dc opinion\n%%EOF\n"


@dataclass
class FakeResponse:
    status_code: int = 200
    text: str = ""
    content: bytes = b""
    url: str = dc.INDEX_URL
    headers: dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "text/html; charset=UTF-8"}
    )


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected D.C. Courts request")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


class FakeClient:
    def __init__(
        self,
        page: dc.DCOpinionsPage,
        *,
        collection: dc.DCOpinionsCollection | None = None,
        pdf: dc.DCOpinionPDF | None = None,
    ) -> None:
        self.page = page
        self.collection = collection
        self.pdf = pdf
        self.page_calls: list[tuple[dict[str, str], int]] = []
        self.all_calls: list[tuple[dict[str, str], int]] = []
        self.pdf_calls: list[str] = []

    def fetch_page(
        self,
        selection: Mapping[str, str],
        *,
        page_number: int,
    ) -> dc.DCOpinionsPage:
        self.page_calls.append((dict(selection), page_number))
        return self.page

    def fetch_all(
        self,
        selection: Mapping[str, str],
        *,
        start_page: int,
    ) -> dc.DCOpinionsCollection:
        self.all_calls.append((dict(selection), start_page))
        if self.collection is None:
            raise AssertionError("unexpected all-page request")
        return self.collection

    def fetch_pdf(self, source_url: str) -> dc.DCOpinionPDF:
        self.pdf_calls.append(source_url)
        if self.pdf is None:
            raise AssertionError("unexpected PDF request")
        return self.pdf


def _parse(*values: str) -> argparse.Namespace:
    return dc.build_parser().parse_args(list(values))


def _page(
    html: str = LIST_HTML,
    *,
    page_number: int = 0,
    selected_type: str = "All",
    source_url: str = dc.INDEX_URL,
) -> dc.DCOpinionsPage:
    return dc.parse_page(
        html,
        source_url=source_url,
        requested_page=page_number,
        selected_type=selected_type,
    )


def _pdf() -> dc.DCOpinionPDF:
    return dc.DCOpinionPDF(
        source_url=(
            f"{dc.BASE_URL}/sites/default/files/2026-07/"
            "In_re_Alpert-24-BG-1045.pdf"
        ),
        content=PDF_BYTES,
        media_type="application/pdf",
        sha256=__import__("hashlib").sha256(PDF_BYTES).hexdigest(),
    )


def test_list_defaults_to_exhaustive_traversal() -> None:
    exhaustive = _parse("list")
    page_only = _parse("list", "--page-only")

    assert exhaustive.all_pages is True
    assert page_only.all_pages is False


def test_source_uses_current_redesigned_route_and_distinct_complements() -> None:
    assert dc.INDEX_PATH.endswith(
        "/opinions-and-memorandum-of-judgments"
    )
    assert "opinions-memorandum-of-judgments" not in dc.INDEX_PATH
    assert dc.SOURCE_METADATA.source_id == dc.SOURCE_ID
    assert (
        dc.SOURCE_METADATA.metadata["case_search_complement"]
        == dc.CASE_SEARCH_PAGE
    )
    assert dc.SUPERIOR_CASE_SEARCH_PAGE != dc.CASE_SEARCH_PAGE


def test_page_parser_preserves_native_pagination_and_record_identity() -> None:
    page = _page()

    assert page.page_number == 0
    assert page.total_items == 16_313
    assert page.total_pages == 1_632
    assert page.next_page == 1
    assert len(page.records) == 2
    opinion = page.records[0]
    moj = page.records[1]
    assert opinion["raw_case_number"] == "24-BG-1045"
    assert opinion["appeal_numbers"] == ["24-BG-1045"]
    assert opinion["decision_date"] == "2026-07-23"
    assert opinion["publication_kind"] == "published_opinion"
    assert opinion["publication_kind_basis"] == "official_pdf_link"
    assert opinion["full_text_status"] == "available"
    assert opinion["pdf_url"].endswith("In_re_Alpert-24-BG-1045.pdf")
    assert opinion["document"]["mime_type"] == "application/pdf"
    assert opinion["canonical_ref"].startswith("STATECOURT:")
    assert opinion["case_canonical_ref"] != opinion["canonical_ref"]
    assert moj["appeal_numbers"] == [
        "22-CV-0273",
        "22-CV-0529",
    ]
    assert moj["publication_kind"] == "moj_or_unclassified_index_entry"
    assert moj["pdf_url"] is None
    assert moj["document"] is None
    assert len(page.schema_fingerprint) == 64


def test_type_specific_classification_uses_source_filter() -> None:
    opinion = dc._record_type("Opinions", pdf_url=None)
    moj = dc._record_type("Memorandums", pdf_url=None)

    assert opinion == (
        "published_opinion",
        "source_type_filter",
        "not_linked",
    )
    assert moj == (
        "memorandum_opinion_and_judgment_index",
        "source_type_filter",
        "not_published_by_court",
    )


def test_authoritative_empty_page_is_no_records_not_failure() -> None:
    page = _page(NO_RESULTS_HTML)

    assert page.records == ()
    assert page.total_items == 0
    assert page.total_pages == 0
    assert page.next_page is None


def test_table_header_change_is_explicit_source_changed() -> None:
    with pytest.raises(dc.DCOpinionsSourceChangedError) as raised:
        _page(SOURCE_CHANGED_HTML)

    assert raised.value.code == "table_headers_changed"
    assert raised.value.status is ResultStatus.SOURCE_CHANGED


def test_native_selection_preserves_keyword_type_date_range_and_sort() -> None:
    args = _parse(
        "list",
        "--query",
        "Georgia Television",
        "--type",
        "mojs",
        "--date-from",
        "2026-07-01",
        "--date-to",
        "2026-07-31",
        "--order",
        "case",
        "--sort",
        "asc",
    )

    assert dc._selection(args) == {
        "search": "Georgia Television",
        "date": "07/01/2026",
        "date_range": "07/31/2026",
        "type": "Memorandums",
        "order": "body",
        "sort": "asc",
    }


def test_exact_date_and_invalid_range_semantics_are_structured() -> None:
    exact = dc._selection(
        _parse("list", "--date", "2026-07-23")
    )
    assert exact["date"] == "07/23/2026"
    assert exact["date_range"] == ""

    with pytest.raises(dc.DCOpinionsSelectionError) as incomplete:
        dc._selection(_parse("list", "--date-from", "2026-07-01"))
    assert incomplete.value.code == "incomplete_date_range"

    with pytest.raises(dc.DCOpinionsSelectionError) as reversed_range:
        dc._selection(
            _parse(
                "list",
                "--date-from",
                "2026-08-01",
                "--date-to",
                "2026-07-01",
            )
        )
    assert reversed_range.value.code == "invalid_date_range"


def test_client_sends_zero_based_native_page_and_browser_user_agent() -> None:
    session = FakeSession(
        [
            FakeResponse(
                text=LIST_HTML.replace('href="?page=1"', 'href="?page=4"'),
                url=f"{dc.INDEX_URL}?type=Opinions&page=3",
            )
        ]
    )
    client = dc.DCOpinionsClient(
        session=session,
        minimum_interval=0,
    )

    page = client.fetch_page(
        {"type": "Opinions", "search": "", "sort": "desc"},
        page_number=3,
    )

    assert page.page_number == 3
    assert session.calls[0][0] == dc.INDEX_URL
    assert session.calls[0][1]["params"] == {
        "type": "Opinions",
        "sort": "desc",
        "page": 3,
    }
    assert session.headers["User-Agent"] == dc.DEFAULT_USER_AGENT


def test_client_retries_transient_status_then_parses_page() -> None:
    session = FakeSession(
        [
            FakeResponse(status_code=503),
            FakeResponse(text=LIST_HTML),
        ]
    )
    delays: list[float] = []
    client = dc.DCOpinionsClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(
            max_attempts=2,
            backoff_initial=0.01,
        ),
        sleeper=delays.append,
    )

    page = client.fetch_page({"type": "All"}, page_number=0)

    assert len(page.records) == 2
    assert len(session.calls) == 2
    assert delays == [0.01]


def test_client_exhausts_native_pages_without_adapter_cap() -> None:
    last_html = LIST_HTML.replace(
        """<li class="pager__item pager__item--next">
              <a href="?page=1" rel="next">Next</a>
            </li>""",
        "",
    )
    session = FakeSession(
        [
            FakeResponse(text=LIST_HTML, url=dc.INDEX_URL),
            FakeResponse(
                text=last_html,
                url=f"{dc.INDEX_URL}?page=1",
            ),
        ]
    )
    client = dc.DCOpinionsClient(
        session=session,
        minimum_interval=0,
    )

    collection = client.fetch_all({"type": "All"})

    assert collection.pages_fetched == 2
    assert len(collection.records) == 4
    assert collection.incomplete_error is None
    assert session.calls[1][1]["params"]["page"] == 1


def test_execute_single_page_returns_cursor_and_valid_envelope() -> None:
    page = _page()
    client = FakeClient(page)
    result = dc.execute(
        _parse("list", "--type", "all", "--page", "0", "--page-only"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert result.next_cursor == "page:1"
    assert result.query.query.parameters["type"] == "All"
    assert len(result.records) == 2
    validate_envelope(result.to_dict())


def test_execute_empty_page_is_authoritative_no_results() -> None:
    result = dc.execute(
        _parse(
            "list",
            "--query",
            "ZZZ-NO-SUCH-CASE-999",
            "--page-only",
        ),
        client=FakeClient(_page(NO_RESULTS_HTML)),
        log_results=False,
    )

    assert result.status is ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_partial_all_page_traversal_preserves_records_and_error() -> None:
    page = _page()
    error = dc.DCOpinionsError(
        "transport_error",
        "second page failed",
        category="transport",
        retryable=True,
    )
    collection = dc.DCOpinionsCollection(
        records=page.records,
        pages_fetched=1,
        total_items=page.total_items,
        total_pages=page.total_pages,
        source_urls=(page.source_url,),
        schema_fingerprints=(page.schema_fingerprint,),
        incomplete_error=error,
    )
    result = dc.execute(
        _parse("list"),
        client=FakeClient(page, collection=collection),
        log_results=False,
    )

    assert result.status is ResultStatus.PARTIAL
    assert len(result.records) == 2
    assert result.errors[0].code == "transport_error"


def test_probe_validates_index_sentinel_and_pdf_bytes() -> None:
    result = dc.execute(
        _parse("probe"),
        client=FakeClient(
            _page(selected_type="Opinions"),
            pdf=_pdf(),
        ),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert result.records[0]["caption"] == dc.PROBE_CAPTION
    assert result.records[0]["probe"]["pdf_size_bytes"] == len(PDF_BYTES)
    assert len(result.records[0]["probe"]["pdf_sha256"]) == 64


def test_download_validates_pdf_writes_artifact_and_returns_receipt(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "opinion.pdf"
    result = dc.execute(
        _parse(
            "download",
            _pdf().source_url,
            str(destination),
        ),
        client=FakeClient(_page(), pdf=_pdf()),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert destination.read_bytes() == PDF_BYTES
    assert result.records[0]["sha256"] == _pdf().sha256
    assert result.raw_artifact_refs == (str(destination),)


def test_pdf_fetch_rejects_non_pdf_response() -> None:
    pdf_url = (
        f"{dc.BASE_URL}/sites/default/files/2026-07/example.pdf"
    )
    session = FakeSession(
        [
            FakeResponse(
                text="<html>not pdf</html>",
                content=b"<html>not pdf</html>",
                url=pdf_url,
            )
        ]
    )
    client = dc.DCOpinionsClient(
        session=session,
        minimum_interval=0,
    )

    with pytest.raises(dc.DCOpinionsSourceChangedError) as raised:
        client.fetch_pdf(pdf_url)

    assert raised.value.code == "pdf_signature_missing"


def test_invalid_pdf_host_is_structured_selection_error() -> None:
    with pytest.raises(dc.DCOpinionsSelectionError) as raised:
        dc._official_pdf_url("https://example.com/opinion.pdf")

    assert raised.value.code == "invalid_pdf_url"
