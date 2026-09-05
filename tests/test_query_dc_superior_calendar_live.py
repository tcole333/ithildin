from __future__ import annotations

import os

import pytest

from tools import query_dc_superior_calendar as dc_calendar


pytestmark = [
    pytest.mark.live_data,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_DC_COURTS") != "1",
        reason="set RUN_LIVE_DC_COURTS=1 for official live probes",
    ),
]


def test_live_today_html_and_full_snapshot_contracts() -> None:
    client = dc_calendar.DCCalendarClient(minimum_interval=0.25)
    try:
        fetched = client.html(dc_calendar.TODAY_URL, params={"page": 0})
        page = dc_calendar.parse_calendar_html(
            fetched.text,
            kind="today",
            native_page=0,
            source_url=fetched.source_url,
        )
        snapshot_fetch = client.json(dc_calendar.TODAY_REST_URL)
        snapshot = dc_calendar.parse_today_snapshot(snapshot_fetch.payload)
    finally:
        client.close()

    assert page.rows
    assert page.reported_total is not None
    assert page.reported_total >= len(page.rows)
    assert page.total_pages >= 1
    assert all(row["_event_datetime"] for row in page.rows)
    assert snapshot
    assert all(row["case_no"] for row in snapshot)


def test_live_criminal_tax_and_appeals_alternatives() -> None:
    client = dc_calendar.DCCalendarClient(minimum_interval=0.25)
    try:
        criminal_fetch = client.html(
            dc_calendar.CRIMINAL_URL,
            params={"page": 0},
        )
        criminal = dc_calendar.parse_calendar_html(
            criminal_fetch.text,
            kind="criminal",
            native_page=0,
            source_url=criminal_fetch.source_url,
        )
        tax_fetch = client.html(dc_calendar.TAX_URL)
        tax = dc_calendar.parse_artifact_index_html(
            tax_fetch.text,
            family="tax",
            page_url=tax_fetch.source_url,
        )
        appeals_fetch = client.json(
            dc_calendar.APPEALS_REST_URL,
            params={"field_year_court_calendar_value[]": 2024},
        )
        appeals = dc_calendar.parse_appeals_payload(appeals_fetch.payload)
    finally:
        client.close()

    assert criminal.rows
    assert criminal.reported_total is not None
    assert {item.artifact_type for item in tax} == {
        "tax_show_cause",
        "tax_multi_door_mediation",
    }
    assert appeals
    assert {item.year for item in appeals} == {2024}
