from __future__ import annotations

import pytest

from tools import query_ny_column as nyc


pytestmark = pytest.mark.live_data


def test_new_york_column_live_sentinel():
    payload = nyc.run_sentinel()

    assert payload["status"] == "ok", payload
    assert all(check["status"] == "ok" for check in payload["checks"])
    partitioned = payload["checks"][0]
    assert partitioned["notice_id"] == "5r3wmbl7IAfYExOneLRQ-3"
    assert partitioned["published_date"] == "2026-10-01"
    assert partitioned["county"] == "Oswego"
    assert partitioned["notice_type"] == "Foreclosure Sale"
    assert payload["checks"][1]["source_display_ceiling"] == 10000
    assert payload["exact_urls"]["portal"] == "https://newyork.column.us/"
    assert payload["exact_urls"]["search_endpoint"] == (
        "https://us-central1-enotice-production.cloudfunctions.net/"
        "api/search/public-notices"
    )
