from __future__ import annotations

import os

import pytest

from tools import query_michigan_appellate as mi


pytestmark = [
    pytest.mark.live_data,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_MI_APPELLATE") != "1",
        reason="set RUN_LIVE_MI_APPELLATE=1 for official live probes",
    ),
]


def test_live_page_model_and_each_paginated_result_role() -> None:
    client = mi.MichiganAppellateClient(minimum_interval=0.25)
    try:
        model = client.page_model()
        pages = {
            result_type: client.fetch_page(
                result_type=result_type,
                query_text="insurance",
                sort_order="Newest",
                page=1,
                page_size=1,
                filters={},
            )
            for result_type in mi.SEARCH_ENDPOINTS
        }
    finally:
        client.close()

    assert model["pageSizeOptions"] == [10, 25, 50, 100]
    assert model["lowerCourtOptions"]
    assert set(pages) == {"cases", "opinions", "orders"}
    assert all(page.result_count == 1 for page in pages.values())
    assert all(page.total_results > 0 for page in pages.values())
    assert all(len(page.schema_fingerprint) == 64 for page in pages.values())


def test_live_advanced_party_search_and_document_pdf() -> None:
    client = mi.MichiganAppellateClient(minimum_interval=0.25)
    try:
        page = client.fetch_page(
            result_type="cases",
            query_text="",
            sort_order="Newest",
            page=1,
            page_size=2,
            filters={"aPartyName": "Epstein"},
        )
        document = client.download(mi.PROBE_DOCUMENT_URL)
    finally:
        client.close()

    assert page.result_count == 2
    assert page.total_results >= 2
    assert any("EPSTEIN" in str(row["title"]).upper() for row in page.records)
    assert document.content.startswith(b"%PDF-")
    assert document.media_type == "application/pdf"
    assert len(document.sha256) == 64


def test_live_explicit_empty_search_is_not_a_transport_failure() -> None:
    client = mi.MichiganAppellateClient(minimum_interval=0.25)
    try:
        page = client.fetch_page(
            result_type="opinions",
            query_text="zzzzunlikelyphrase8675309",
            sort_order="Newest",
            page=1,
            page_size=10,
            filters={},
        )
    finally:
        client.close()

    assert page.records == ()
    assert page.total_results == 0
    assert page.total_pages == 0
