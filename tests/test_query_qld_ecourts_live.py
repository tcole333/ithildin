from __future__ import annotations

import os

import pytest

from tools.query_qld_ecourts import (
    PROBE_COURT,
    PROBE_FILE_NUMBER,
    PROBE_LOCATION,
    QldECourtsClient,
    SearchCriteria,
)


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS_TESTS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS_TESTS=1 for live public-record tests",
)


def test_live_exact_file_and_document_list() -> None:
    client = QldECourtsClient()
    try:
        batch = client.first_page(
            SearchCriteria(
                file_number=PROBE_FILE_NUMBER,
                court=PROBE_COURT,
                originating_location=PROBE_LOCATION,
            )
        )
        assert batch.first_page.reported_total == 1
        hit = batch.first_page.rows[0]
        assert hit.file_number == PROBE_FILE_NUMBER
        assert hit.court_code == PROBE_COURT
        assert hit.originating_location_code == PROBE_LOCATION

        detail = client.detail(
            PROBE_FILE_NUMBER,
            court=PROBE_COURT,
            location=PROBE_LOCATION,
        )
        assert detail is not None
        assert detail.hit.file_number == PROBE_FILE_NUMBER
        assert len(detail.parties) >= 4
        assert len(detail.events) >= 1
        assert len(detail.documents) >= 30
        assert any(value["acn"] == "067302158" for value in detail.parties)
    finally:
        client.close()
