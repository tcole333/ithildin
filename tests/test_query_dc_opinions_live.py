from __future__ import annotations

import os
from datetime import date

import pytest

from tools import query_dc_opinions as dc
from tools.public_records_contract import ResultStatus


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded live probes",
)


def _client() -> dc.DCOpinionsClient:
    return dc.DCOpinionsClient(
        minimum_interval=0.1,
        timeout=45,
    )


def test_live_index_exposes_large_native_pager_and_current_schema() -> None:
    client = _client()
    try:
        page = client.fetch_page(
            {
                "type": "All",
                "order": "field_date",
                "sort": "desc",
            },
            page_number=0,
        )
    finally:
        client.close()

    assert page.total_items > 15_000
    assert page.total_pages > 1_500
    assert page.next_page == 1
    assert len(page.records) == dc.ROWS_PER_PAGE
    assert all(record["source_id"] == dc.SOURCE_ID for record in page.records)


def test_live_opinion_filter_preserves_stable_pdf_sentinel() -> None:
    client = _client()
    try:
        page = client.fetch_page(
            {
                "search": dc.PROBE_APPEAL_NUMBER,
                "type": "Opinions",
                "order": "field_date",
                "sort": "desc",
            },
            page_number=0,
        )
    finally:
        client.close()

    matching = [
        record
        for record in page.records
        if dc.PROBE_APPEAL_NUMBER in record["appeal_numbers"]
    ]
    assert matching
    assert matching[0]["caption"] == dc.PROBE_CAPTION
    assert matching[0]["publication_kind"] == "published_opinion"
    assert matching[0]["pdf_url"].startswith(
        f"{dc.BASE_URL}/sites/default/files/"
    )


def test_live_moj_filter_and_date_range_are_source_typed() -> None:
    client = _client()
    try:
        page = client.fetch_page(
            {
                "search": "Georgia Television",
                "date": "07/01/2026",
                "date_range": "07/31/2026",
                "type": "Memorandums",
                "order": "field_date",
                "sort": "desc",
            },
            page_number=0,
        )
    finally:
        client.close()

    assert page.records
    assert all(
        record["publication_kind"]
        == "memorandum_opinion_and_judgment_index"
        for record in page.records
    )
    assert all(
        date(2026, 7, 1)
        <= date.fromisoformat(record["decision_date"])
        <= date(2026, 7, 31)
        for record in page.records
    )


def test_live_probe_validates_index_and_pdf_in_one_envelope() -> None:
    result = dc.execute(
        dc.build_parser().parse_args(
            [
                "probe",
                "--minimum-interval",
                "0.1",
            ]
        ),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert result.records[0]["probe"]["pdf_size_bytes"] > 1_000
    assert result.records[0]["probe"]["pdf_media_type"] == "application/pdf"
