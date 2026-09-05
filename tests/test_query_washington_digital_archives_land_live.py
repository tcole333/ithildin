from __future__ import annotations

import os

import pytest

from tools import query_washington_digital_archives_land as adapter
from tools.public_records_http import RetryPolicy


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_WASHINGTON_DIGITAL_ARCHIVES_LAND") != "1",
    reason=(
        "set RUN_LIVE_WASHINGTON_DIGITAL_ARCHIVES_LAND=1 to run "
        "Washington Digital Archives sentinels"
    ),
)


def _client() -> adapter.DigitalArchivesClient:
    return adapter.DigitalArchivesClient(
        timeout=60,
        minimum_interval=0.25,
        retry_policy=RetryPolicy(max_attempts=2),
    )


def test_live_record_series_inventory_and_adams_title_schema() -> None:
    client = _client()

    titles = client.fetch_title_list()
    discovered_ids = {record["title_id"] for record in titles}
    detail = client.fetch_title(adapter.TITLES_BY_KEY["adams"].title_id)

    assert len(titles) >= len(adapter.TITLES)
    assert set(adapter.TITLES_BY_ID) <= discovered_ids
    assert detail["record_series_id"] == adapter.RECORD_SERIES_ID
    assert detail["title_id"] == adapter.TITLES_BY_KEY["adams"].title_id
    assert detail["county_key"] == "adams"
    assert detail["record_count"] >= 89_823
    assert detail["search_operation"]["party_roles"] == ["Grantor", "Grantee"]
    assert detail["instrument_vocabulary"]["text"]


def test_live_adams_exact_search_and_record_detail_sentinel() -> None:
    client = _client()
    title = adapter.TITLES_BY_KEY["adams"]
    payload = adapter.build_search_payload(
        title,
        search_type="DetailedSearch",
        last_name=title.sentinel_last_name,
        first_name=title.sentinel_first_name,
        start_year=title.sentinel_year,
        end_year=title.sentinel_year,
    )

    handle = client.start_search(payload)
    page = client.fetch_results(
        handle.search_id,
        page=1,
        page_size=50,
    )
    record_ids = {record["native_record_id"] for record in page.records}
    detail = client.fetch_detail(str(title.sentinel_record_id))

    assert page.total_count >= 1
    assert page.page == 1
    assert page.page_size in adapter.NATIVE_PAGE_SIZES
    assert title.sentinel_record_id in record_ids
    assert [record["native_result_ordinal"] for record in page.records] == list(
        range(page.first_record or 1, (page.last_record or 0) + 1)
    )
    assert len(
        {record["ordinal_occurrence_key"] for record in page.records}
    ) == len(page.records)
    assert detail["native_record_id"] == title.sentinel_record_id
    assert detail["title_id"] == title.title_id
    assert detail["reference_number"] == "324744"
    assert detail["recording_date"] == "06/19/2020"
    assert detail["document_type"] == "Assignment Of Deed Of Trust"
    assert [party["sequence_no"] for party in detail["parties"]] == list(
        range(1, len(detail["parties"]) + 1)
    )
    assert detail["digital_objects"]
    assert detail["document_delivery"]["state"] == "site_recaptcha_queue"
