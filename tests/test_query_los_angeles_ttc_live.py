from __future__ import annotations

import os
from urllib.parse import urlsplit

import pytest

from tools import query_los_angeles_ttc as la_ttc


pytestmark = [
    pytest.mark.live_data,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_LA_TTC") != "1",
        reason="set RUN_LIVE_LA_TTC=1 for official live probes",
    ),
]


def test_live_assessor_payment_and_negative_contracts() -> None:
    client = la_ttc.LosAngelesTTCClient(minimum_interval=0.25)
    try:
        assessor = client.assessor_exact(la_ttc.PROBE_AIN)
        bootstrap = client.payment_bootstrap()
        positive = client.payment_page(
            la_ttc.PROBE_AIN,
            1,
            bootstrap=bootstrap,
        )
        negative = client.payment_page(
            la_ttc.INVALID_PROBE_AIN,
            1,
            bootstrap=bootstrap,
        )
    finally:
        client.close()

    assert assessor is not None
    assert assessor["AIN"] == la_ttc.PROBE_AIN
    assert urlsplit(bootstrap.ajax_url).hostname == "ttc.lacounty.gov"
    assert positive.no_result is False
    assert positive.rows
    assert positive.meta["totalRecords"] >= len(positive.rows)
    assert positive.meta["totalPages"] >= 1
    assert positive.meta["lastUpdated"]
    assert negative.no_result is True
    assert negative.native_state["status"] == 404


def test_live_schedule_publication_and_latest_result_contract() -> None:
    client = la_ttc.LosAngelesTTCClient(minimum_interval=0.25)
    try:
        schedules = la_ttc.parse_auction_schedule_html(
            client.html(la_ttc.AUCTION_SCHEDULE_URL)
        )
        publications = la_ttc.parse_publications_html(
            client.html(la_ttc.AUCTION_CONTACT_URL)
        )
        result_artifacts = [
            item
            for item in publications
            if item.kind == "sale_results_excess_proceeds"
        ]
        latest = max(result_artifacts, key=lambda item: item.cycle)
        artifact = client.bytes(
            latest.url,
            max_bytes=la_ttc.DEFAULT_MAX_DOCUMENT_BYTES,
        )
        text = la_ttc.extract_pdf_text(artifact)
        rows, _windows = la_ttc.parse_sale_results_text(
            text,
            expected_cycle=latest.cycle,
        )
    finally:
        client.close()

    assert schedules
    assert all(row["redemption"]["last_day_to_redeem"] for row in schedules)
    assert result_artifacts
    assert artifact.content.startswith(b"%PDF-")
    assert rows
    assert all(len(row.ain) == 10 for row in rows)
