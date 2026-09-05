from __future__ import annotations

import os

import pytest

from tools import query_denver_foreclosures as denver


pytestmark = [
    pytest.mark.live_data,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_DENVER_FORECLOSURES") != "1",
        reason=(
            "set RUN_LIVE_DENVER_FORECLOSURES=1 for the official live probe"
        ),
    ),
]


def test_denver_public_trustee_live_webforms_contract():
    client = denver.DenverForeclosureClient()
    try:
        rows, next_cursor, page, skipped = client.search(
            {},
            show_all=True,
            limit=26,
            cursor=None,
        )
        assert skipped == 0
        assert len(rows) == 26
        assert rows[0].foreclosure_number
        assert rows[-1].source_page == 2
        assert page.total_results >= len(rows)
        assert next_cursor is not None

        detail = client.detail(denver.DEFAULT_PROBE_FORECLOSURE)
        assert detail is not None
        assert tuple(detail.sections) == denver.EXPECTED_DETAIL_SECTIONS
        assert detail.documents

        downloaded = client.download(detail.documents[0].source_url)
        assert downloaded.media_type == "application/pdf"
        assert downloaded.content.startswith(b"%PDF-")

        public_record = denver.normalize_detail(detail)
        serialized = denver.canonical_json(public_record)
        assert "__VIEWSTATE" not in serialized
        assert "__EVENTVALIDATION" not in serialized
        assert "ASP.NET_SessionId" not in serialized
    finally:
        client.close()
