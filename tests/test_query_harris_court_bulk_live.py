from __future__ import annotations

import pytest

from tools import query_harris_court_bulk as bulk


pytestmark = pytest.mark.live_data


def test_harris_district_clerk_public_datasets_live_sentinel():
    payload = bulk.run_sentinel()

    assert payload["status"] == "ok", payload
    assert payload["catalog_url"] == (
        "https://www.hcdistrictclerk.com/Common/e-services/"
        "PublicDatasets.aspx"
    )
    assert payload["sentinel"] == {
        "native_locator": r"Civil\2024-08-15 FIELD_CODES.xlsx",
        "filename": "FIELD_CODES.xlsx",
        "published_date": "2024-08-15",
        "format": "xlsx",
        "sample_bytes": bulk.DEFAULT_SAMPLE_BYTES,
        "signature_hex": "504b0304",
        "response_filename": "2024-08-15 FIELD_CODES.xlsx",
    }
