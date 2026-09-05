from __future__ import annotations

import os

import pytest

from tools import query_edva_bankruptcy


pytestmark = [
    pytest.mark.live_data,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
        reason="set RUN_LIVE_PUBLIC_RECORDS=1 for official live probes",
    ),
]


def test_live_blocked_docket_sentinels_and_entry_gap() -> None:
    client = query_edva_bankruptcy.EDVABankruptcyClient()
    try:
        for sentinel in query_edva_bankruptcy.SENTINELS:
            docket = client.get_docket(
                int(sentinel["courtlistener_docket_id"])
            )
            first_page = client.get_entries(
                int(sentinel["courtlistener_docket_id"]),
                one_page=True,
            )

            assert docket["id"] == sentinel["courtlistener_docket_id"]
            assert docket["docket_number"] == sentinel["docket_number"]
            assert docket["pacer_case_id"] == sentinel["pacer_case_id"]
            assert docket["date_blocked"] == sentinel["expected_date_blocked"]
            assert first_page.records == ()
            assert first_page.next_cursor is None
    finally:
        client.close()


def test_live_exact_docket_filter_and_recap_fetch_options_contract() -> None:
    client = query_edva_bankruptcy.EDVABankruptcyClient()
    try:
        matches = client.find_dockets("05-39367")
        options = client.options(query_edva_bankruptcy.RECAP_FETCH_URL)
    finally:
        client.close()

    assert matches.incomplete_error is None
    assert len(matches.records) == 1
    assert matches.records[0]["id"] == 49921079
    assert matches.records[0]["pacer_case_id"] == "425734"
    post_fields = set(query_edva_bankruptcy._extract_post_fields(options))
    assert {
        "request_type",
        "court",
        "docket",
        "docket_number",
        "pacer_case_id",
        "pacer_username",
        "pacer_password",
        "recap_document",
    }.issubset(post_fields)
