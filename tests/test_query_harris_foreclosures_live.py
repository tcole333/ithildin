from __future__ import annotations

import pytest

from tools import query_harris_foreclosures as frcl


pytestmark = pytest.mark.live_data


def test_harris_foreclosure_live_sentinel():
    payload = frcl.run_sentinel()

    assert payload["status"] == "ok", payload
    assert payload["checks"][0]["document_id"] == "FRCL-2026-4797"
    assert payload["checks"][0]["sale_date"] == "2026-08-04"
    assert payload["checks"][0]["file_date"] == "2026-07-08"
    assert payload["checks"][0]["page_count"] == 2
    assert payload["checks"][1]["pdf_signature"] == "%PDF-"
    assert payload["checks"][1]["size"] > 100_000
    assert payload["exact_urls"]["search"] == (
        "https://www.cclerk.hctx.net/applications/websearch/FRCL_R.aspx"
    )
