from __future__ import annotations

import os

import pytest

from tools import query_doj_court_records as doj_courts


pytestmark = [
    pytest.mark.live_data,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
        reason="set RUN_LIVE_PUBLIC_RECORDS=1 for official live probes",
    ),
]


LEGACY_061_URL = (
    "https://www.justice.gov/multimedia/Court%20Records/"
    "United%20States%20v.%20Epstein%2C%20No.%20119-cr-00490%20"
    "%28S.D.N.Y.%202019%29/061.pdf"
)


def test_live_current_index_and_bounded_case_page() -> None:
    client = doj_courts.DOJCourtRecordsClient()
    try:
        cases = client.fetch_index()
        first_page = client.fetch_case(
            doj_courts.SENTINEL_CASE_URL,
            one_page=True,
        )
    finally:
        client.close()

    assert len(cases) >= 1
    assert any(
        case["case_page_url"] == doj_courts.SENTINEL_CASE_URL
        for case in cases
    )
    assert len(first_page.documents) >= 1
    assert any(
        document["efta_id"] == doj_courts.SENTINEL_EFTA
        for document in first_page.documents
    )
    assert first_page.pages_fetched == 1


def test_live_current_pdf_range_magic() -> None:
    result = doj_courts.probe_pdf_magic(doj_courts.SENTINEL_PDF_URL)

    assert result["magic"] == "%PDF-"
    assert result["bytes_read"] == 5
    assert result["content_type"] == "application/pdf"
    assert result["http_status"] in {200, 206}


def test_live_legacy_numeric_link_maps_to_case_but_not_exact_efta() -> None:
    client = doj_courts.DOJCourtRecordsClient()
    try:
        recovery = doj_courts.resolve_recovery(
            LEGACY_061_URL,
            client=client,
        )
    finally:
        client.close()

    assert recovery["current_case_page_url"] == doj_courts.SENTINEL_CASE_URL
    assert recovery["exact_current_url"] is None
    assert recovery["resolution"] == (
        "current_case_found_without_exact_document_mapping"
    )
    assert recovery["case_documents_observed"] >= 1
