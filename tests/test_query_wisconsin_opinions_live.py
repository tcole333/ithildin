from __future__ import annotations

import os

import pytest

from tools import query_wisconsin_opinions as wi
from tools.public_records_contract import ResultStatus


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded live probes",
)


def _client() -> wi.WisconsinOpinionsClient:
    return wi.WisconsinOpinionsClient(
        minimum_interval=0.1,
        timeout=45,
    )


def test_live_exact_metadata_indexes_preserve_case_and_pdf_identity() -> None:
    client = _client()
    try:
        supreme = client.fetch_metadata_page(
            "supreme-opinions",
            {"docket_number": wi.PROBE_SUPREME_CASE},
            page_number=1,
        )
        appeals = client.fetch_metadata_page(
            "appeals-opinions",
            {"docket_number": wi.PROBE_APPEALS_CASE},
            page_number=1,
        )
    finally:
        client.close()

    assert any(
        record["caption"] == wi.PROBE_SUPREME_CAPTION
        for record in supreme.records
    )
    matching = [
        record
        for record in appeals.records
        if record["caption"] == wi.PROBE_APPEALS_CAPTION
    ]
    assert matching
    assert (
        matching[0]["document"]["native_document_id"]
        == wi.PROBE_APPEALS_DOCUMENT_ID
    )
    assert matching[0]["pdf_url"] == wi.PROBE_APPEALS_PDF_URL


def test_live_fulltext_and_feed_routes_are_current() -> None:
    client = _client()
    try:
        page = client.fetch_fulltext_page(
            "supreme",
            '"Wisconsin Voter Alliance"',
            page_number=1,
        )
        feed_records, feed_url = client.fetch_feed("appeals")
    finally:
        client.close()

    assert page.records
    assert any(
        record["native_document_id"] == "903123"
        for record in page.records
    )
    assert feed_url == wi.FEED_URLS["appeals"]
    assert feed_records
    assert all(
        record["court"]["court_id"] == wi.APPEALS_COURT_ID
        for record in feed_records
    )


def test_live_pdf_and_end_to_end_probe() -> None:
    client = _client()
    try:
        pdf = client.fetch_pdf(wi.PROBE_APPEALS_PDF_URL)
    finally:
        client.close()

    assert pdf.content.startswith(b"%PDF-")
    assert len(pdf.content) > 100_000
    assert pdf.native_document_id == wi.PROBE_APPEALS_DOCUMENT_ID

    result = wi.execute(
        wi.build_parser().parse_args(
            [
                "probe",
                "--component",
                "all",
                "--minimum-interval",
                "0.1",
            ]
        ),
        log_results=False,
    )
    assert result.status is ResultStatus.OK
    assert {
        record["probe_component"] for record in result.records
    } == {
        "supreme_metadata_index",
        "appeals_metadata_index",
        "supreme_full_text",
        "supreme_rss",
        "appeals_rss",
        "official_pdf",
    }
