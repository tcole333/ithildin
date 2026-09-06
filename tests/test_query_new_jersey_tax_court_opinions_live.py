from __future__ import annotations

import os

import pytest

from tools import query_new_jersey_tax_court_opinions as nj


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded live probes",
)


def _client() -> nj.NewJerseyTaxOpinionsClient:
    return nj.NewJerseyTaxOpinionsClient(
        minimum_interval=0.25,
        timeout=60,
    )


def test_live_unpublished_search_preserves_reposted_document_occurrences() -> None:
    client = _client()
    try:
        page = client.fetch_index_page(
            "unpublished",
            search="Giammarino",
        )
    finally:
        client.close()

    assert page.total_count == 2
    assert len(page.records) == 2
    first, second = page.records
    assert first["document"]["document_id"] == second["document"]["document_id"]
    assert first["posted_date"] != second["posted_date"]
    assert (
        first["index_entry"]["occurrence_id"] != second["index_entry"]["occurrence_id"]
    )


def test_live_both_index_counts_and_native_page_facts() -> None:
    client = _client()
    try:
        published = client.fetch_index_page("published")
        unpublished = client.fetch_index_page("unpublished")
    finally:
        client.close()

    assert published.total_count >= 104
    assert published.total_pages >= 6
    assert len(published.records) == 20
    assert unpublished.total_count >= 374
    assert unpublished.total_pages >= 19
    assert len(unpublished.records) == 20
    assert published.retrieval_transport in {
        "official_direct",
        "reader_relay",
    }
    assert unpublished.retrieval_transport in {
        "official_direct",
        "reader_relay",
    }


def test_live_exact_secondary_docket_scans_consolidated_summary() -> None:
    args = nj.build_parser().parse_args(
        [
            "search",
            "--collection",
            "published",
            "--docket",
            "000055-25",
            "--limit",
            "1",
        ]
    )
    client = _client()
    try:
        result = nj.execute(
            args,
            client=client,
            log_results=False,
        )
    finally:
        client.close()

    assert len(result.records) == 1
    assert "000055-2025" in result.records[0]["docket_numbers"]
    assert result.records[0]["document"]["document_id"].endswith(
        "court-opinions/2026/000052-2025.pdf"
    )


def test_live_official_document_is_bytes_or_labeled_reader_extraction() -> None:
    client = _client()
    try:
        page = client.fetch_index_page(
            "published",
            search="MT FREEHOLD BPE",
        )
        assert page.records
        document = client.fetch_document(str(page.records[0]["document"]["source_url"]))
    finally:
        client.close()

    if document.retrieval_transport == "official_direct":
        assert document.original_bytes is not None
        assert document.original_bytes.startswith(b"%PDF-")
        assert document.content_hash_scope == "original_pdf_bytes"
    else:
        assert document.original_bytes is None
        assert document.extracted_text
        assert "TAX COURT OF NEW JERSEY" in document.extracted_text
        assert document.content_hash_scope == "reader_extracted_text"
        assert document.page_count is not None
