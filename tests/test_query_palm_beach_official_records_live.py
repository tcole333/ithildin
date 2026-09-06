from __future__ import annotations

import os

import pytest

from tools import query_palm_beach_official_records as recorder


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded live probes",
)


def test_live_exact_instrument_detail_and_public_image():
    client = recorder.PalmBeachRecorderClient(minimum_interval=0)

    record = client.instrument(recorder.SENTINEL_INSTRUMENT)

    assert record is not None
    assert record["native_document_id"] == recorder.SENTINEL_DOCUMENT_ID
    assert record["book"] == str(recorder.SENTINEL_BOOK)
    assert record["page"] == str(recorder.SENTINEL_PAGE)
    assert record["document_type"] == recorder.SENTINEL_DOC_TYPE
    assert record["recording_date_raw"].startswith(
        recorder.SENTINEL_RECORD_DATE
    )
    image = client.image(record, 1)
    assert image.media_type == "image/png"
    assert len(image.content) > 1000


def test_live_exact_book_page_matches_instrument_identity():
    client = recorder.PalmBeachRecorderClient(minimum_interval=0)

    record = client.book_page(
        recorder.SENTINEL_BOOK,
        recorder.SENTINEL_PAGE,
    )

    assert record is not None
    assert record["instrument_number"] == recorder.SENTINEL_INSTRUMENT
    assert record["native_document_id"] == recorder.SENTINEL_DOCUMENT_ID


def test_live_probe_reports_captcha_boundary_and_all_exact_routes():
    payload = recorder.run_probe(
        recorder.PalmBeachRecorderClient(minimum_interval=0)
    )

    assert payload["status"] == "ok"
    assert payload["broad_search_captcha_required"] is True
    assert payload["sentinel"]["image_media_type"] == "image/png"
    assert payload["sentinel"]["image_byte_count"] > 1000
    assert payload["routes"]["instrument"] == recorder.DIRECT_CFN_URL
    assert payload["routes"]["book_page"] == recorder.DIRECT_BOOK_PAGE_URL
