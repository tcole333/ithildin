from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import query_new_jersey_tax_court_opinions as nj
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "new_jersey_tax_court_opinions"
)


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class _Response:
    def __init__(
        self,
        *,
        status_code: int,
        text: str = "",
        content: bytes | None = None,
        url: str = "https://example.invalid/",
        content_type: str = "text/html",
    ) -> None:
        self.status_code = status_code
        self.text = text
        self.content = content if content is not None else text.encode("utf-8")
        self.url = url
        self.headers = {"Content-Type": content_type}


class _SequenceSession:
    def __init__(self, responses: list[_Response]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.headers: dict[str, str] = {}
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append({"url": url, **kwargs})
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        response = self.responses.pop(0)
        if response.url == "https://example.invalid/":
            response.url = url
        return response

    def close(self) -> None:
        self.closed = True


class _PageClient:
    def __init__(self, page: nj.OpinionIndexPage) -> None:
        self.page = page
        self.calls: list[dict[str, Any]] = []

    def fetch_index_page(
        self,
        collection: str,
        *,
        page: int = 0,
        search: str | None = None,
        start: str | None = None,
        end: str | None = None,
        transport: str = "auto",
    ) -> nj.OpinionIndexPage:
        self.calls.append(
            {
                "collection": collection,
                "page": page,
                "search": search,
                "start": start,
                "end": end,
                "transport": transport,
            }
        )
        if collection != self.page.collection or page != 0:
            raise AssertionError("fixture client only exposes published page 0")
        return self.page


def test_parse_published_page_preserves_three_identity_layers() -> None:
    page = nj.parse_index_page(
        _fixture("published_page.html"),
        collection="published",
        source_url=nj.PUBLISHED_INDEX_URL,
    )

    assert page.total_count == 22
    assert page.total_pages == 2
    assert page.showing_start == 1
    assert page.showing_end == 2
    assert page.reported_for_date == "July 30, 2026"
    assert len(page.records) == 2

    record = page.records[0]
    assert record["collection"] == "published"
    assert record["publication_status"] == "published"
    assert record["index_entry"]["native_summary_node_id"] == "1031000"
    assert record["document"]["document_id"].endswith(
        "court-opinions/2026/000052-2025.pdf"
    )
    assert record["docket_numbers"] == [
        "000052-2025",
        "000054-2025",
        "000056-2025",
        "000055-2025",
    ]
    assert len(record["case_canonical_refs"]) == 4
    assert record["summary"]["available_on_index"] is True
    assert record["provenance"]["global_source_position"] == 1
    assert record["provenance"]["page_fingerprint"] == page.page_fingerprint


def test_source_docket_anomaly_is_preserved_beside_summary_docket() -> None:
    page = nj.parse_index_page(
        _fixture("published_page.html"),
        collection="published",
        source_url=nj.PUBLISHED_INDEX_URL,
    )

    record = page.records[1]
    assert record["docket_label_raw"] == "008224-2022, 0082269-2022"
    assert "082269-2022" in record["docket_numbers"]
    assert "008229-2022" in record["docket_numbers"]
    provenance = {
        item["normalized"]: item["provenance"] for item in record["docket_components"]
    }
    assert provenance["082269-2022"] == "index_label"
    assert provenance["008229-2022"] == "summary"


def test_unpublished_duplicate_occurrences_share_document_and_case_only() -> None:
    page = nj.parse_index_page(
        _fixture("unpublished_duplicates.html"),
        collection="unpublished",
        source_url=f"{nj.UNPUBLISHED_INDEX_URL}?search=Giammarino",
    )

    assert page.total_count == 2
    first, second = page.records
    assert first["source_url"] == second["source_url"]
    assert first["document"]["document_id"] == second["document"]["document_id"]
    assert first["case_canonical_refs"] == second["case_canonical_refs"]
    assert first["posted_date"] == "2025-11-13"
    assert second["posted_date"] == "2025-07-09"
    assert first["canonical_ref"] != second["canonical_ref"]
    assert (
        first["index_entry"]["occurrence_id"] != second["index_entry"]["occurrence_id"]
    )
    assert first["summary"]["available_on_index"] is False


def test_shared_year_docket_list_is_normalized_without_losing_raw_tokens() -> None:
    records = nj._extract_dockets(
        "10920/10921/10922-13",
        provenance="test",
    )

    assert [record["normalized"] for record in records] == [
        "010920-2013",
        "010921-2013",
        "010922-2013",
    ]
    assert [record["raw"] for record in records] == [
        "10920-13",
        "10921-13",
        "10922-13",
    ]


def test_parser_rejects_missing_official_view() -> None:
    with pytest.raises(nj.SourceChangedError):
        nj.parse_index_page(
            _fixture("source_changed.html"),
            collection="published",
            source_url=nj.PUBLISHED_INDEX_URL,
        )


def test_reader_document_parser_preserves_extraction_scope_and_cases() -> None:
    document = nj.parse_reader_document(
        _fixture("document_relay.txt"),
        source_url=(
            "https://www.njcourts.gov/system/files/court-opinions/2026/000052-2025.pdf"
        ),
    )

    assert document.retrieval_transport == "reader_relay"
    assert document.original_bytes is None
    assert document.content_hash_scope == "reader_extracted_text"
    assert document.page_count == 22
    assert document.title == ("000052-2025 - MT FREEHOLD BPE, LLC V FREEHOLD TOWNSHIP")
    assert [component["normalized"] for component in document.docket_components] == [
        "000052-2025",
        "000054-2025",
        "000056-2025",
        "000055-2025",
    ]
    assert "Block 42" in (document.extracted_text or "")


def test_client_auto_falls_back_once_then_reuses_observed_relay_route() -> None:
    challenge = _fixture("challenge.html")
    published = _fixture("published_page.html")
    session = _SequenceSession(
        [
            _Response(status_code=200, text=challenge),
            _Response(status_code=200, text=published),
            _Response(status_code=200, text=published),
        ]
    )
    client = nj.NewJerseyTaxOpinionsClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    first = client.fetch_index_page("published", transport="auto")
    second = client.fetch_index_page(
        "published",
        search="Freehold",
        transport="auto",
    )

    assert first.retrieval_transport == "reader_relay"
    assert first.transport_attempts[0]["operation_state"] == "edge_challenge"
    assert first.transport_attempts[1]["operation_state"] == "available"
    assert second.transport_attempts[0]["request_made"] is False
    assert second.transport_attempts[1]["transport"] == "reader_relay"
    assert len(session.calls) == 3
    assert session.calls[0]["url"] == nj.PUBLISHED_INDEX_URL
    assert session.calls[0]["headers"]["User-Agent"] == nj.DEFAULT_USER_AGENT
    assert session.calls[1]["url"].startswith(nj.READER_BASE_URL)
    assert session.calls[1]["headers"]["User-Agent"] == nj.READER_USER_AGENT
    assert "search=Freehold" in session.calls[2]["url"]


def test_client_auto_document_fallback_labels_extracted_hash() -> None:
    source_url = (
        "https://www.njcourts.gov/system/files/court-opinions/2026/000052-2025.pdf"
    )
    session = _SequenceSession(
        [
            _Response(
                status_code=403,
                text=_fixture("challenge.html"),
            ),
            _Response(
                status_code=200,
                text=_fixture("document_relay.txt"),
                content_type="text/plain",
            ),
        ]
    )
    client = nj.NewJerseyTaxOpinionsClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    document = client.fetch_document(source_url)

    assert document.retrieval_transport == "reader_relay"
    assert document.content_hash_scope == "reader_extracted_text"
    assert document.transport_attempts[0]["operation_state"] == "edge_challenge"
    assert document.transport_attempts[1]["returned_format"] == "markdown"


def test_search_cursor_is_selection_and_snapshot_bound() -> None:
    page = nj.parse_index_page(
        _fixture("published_page.html"),
        collection="published",
        source_url=nj.PUBLISHED_INDEX_URL,
    )
    client = _PageClient(page)
    parser = nj.build_parser()
    first_args = parser.parse_args(
        [
            "search",
            "--collection",
            "published",
            "--limit",
            "1",
            "--transport",
            "reader",
        ]
    )

    first = nj.execute(first_args, client=client, log_results=False)

    assert first.status is ResultStatus.OK
    assert len(first.records) == 1
    assert first.next_cursor is not None

    second_args = parser.parse_args(
        [
            "search",
            "--collection",
            "published",
            "--limit",
            "1",
            "--transport",
            "reader",
            "--cursor",
            first.next_cursor,
        ]
    )
    second = nj.execute(second_args, client=client, log_results=False)

    assert second.status is ResultStatus.OK
    assert len(second.records) == 1
    assert second.records[0]["canonical_ref"] != first.records[0]["canonical_ref"]

    mismatched_args = parser.parse_args(
        [
            "search",
            "different",
            "--collection",
            "published",
            "--limit",
            "1",
            "--transport",
            "reader",
            "--cursor",
            first.next_cursor,
        ]
    )
    mismatch = nj.execute(
        mismatched_args,
        client=client,
        log_results=False,
    )
    assert mismatch.status is ResultStatus.UNAVAILABLE
    assert mismatch.errors[0].code == nj.CursorError.code


def test_exact_docket_filter_uses_normalized_case_identity() -> None:
    page = nj.parse_index_page(
        _fixture("published_page.html"),
        collection="published",
        source_url=nj.PUBLISHED_INDEX_URL,
    )
    client = _PageClient(page)
    args = nj.build_parser().parse_args(
        [
            "search",
            "--collection",
            "published",
            "--docket",
            "000055-25",
            "--limit",
            "1",
            "--transport",
            "reader",
        ]
    )

    result = nj.execute(args, client=client, log_results=False)

    assert result.status is ResultStatus.OK
    assert len(result.records) == 1
    assert "000055-2025" in result.records[0]["docket_numbers"]
    assert client.calls[0]["search"] is None


def test_manifest_and_alternatives_are_network_free_and_operation_specific() -> None:
    parser = nj.build_parser()
    manifest = nj.execute(
        parser.parse_args(["manifest"]),
        log_results=False,
    )
    alternatives = nj.execute(
        parser.parse_args(["alternatives"]),
        log_results=False,
    )

    assert manifest.status is ResultStatus.OK
    record = manifest.records[0]
    assert record["coverage_observation"]["published"]["entries"] == 104
    assert record["coverage_observation"]["unpublished"]["entries"] == 374
    assert (
        record["operation_access_states"]["index_direct"]["state"] == "edge_challenge"
    )
    assert (
        record["operation_access_states"]["document_reader_relay"]["original_pdf_bytes"]
        is False
    )
    assert len(record["alternative_routes"]) >= 7
    assert {route["source_id"] for route in record["alternative_routes"]} >= {
        "us-nj-rutgers-court-opinions",
        "us-courtlistener-opinions",
    }
    assert alternatives.status is ResultStatus.OK
    assert any(
        route["source_id"] == "us-nj-tax-case-public-access"
        for route in alternatives.records[0]["routes"]
    )


def test_manifest_serializes_as_json() -> None:
    payload = nj.source_manifest_record()
    encoded = json.dumps(payload)
    assert nj.SOURCE_ID in encoded


def test_document_url_validation_rejects_non_source_hosts() -> None:
    with pytest.raises(nj.SelectionError):
        nj._official_document_url(
            "https://example.com/system/files/court-opinions/2026/test.pdf"
        )
