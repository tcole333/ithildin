from __future__ import annotations

import pytest

from tools import query_harris_recorder as recorder


pytestmark = pytest.mark.live_data


def test_harris_recorder_live_sentinel():
    payload = recorder.run_sentinel()

    assert payload["status"] == "ok", payload
    assert all(check["status"] == "ok" for check in payload["checks"])
    index = payload["checks"][0]
    assert index["file_number"] == recorder.SENTINEL_FILE_NUMBER
    assert index["file_date"] == "2026-02-26"
    assert index["instrument_type_code"] == "W/D"
    access = payload["checks"][1]
    assert access["anonymous_status"] == "login_required"
    assert access["registration_required"] is True
    assert payload["exact_urls"]["search"] == (
        "https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx"
    )
    assert payload["exact_urls"]["bulk_data_sales"] == (
        "https://www.cclerk.hctx.net/PublicRecords.aspx"
    )
