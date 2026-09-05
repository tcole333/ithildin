from __future__ import annotations

import os

import pytest

from tools import query_los_angeles_court as la
from tools.public_records_contract import ResultStatus


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded live probes",
)


def _client() -> la.LosAngelesCourtClient:
    return la.LosAngelesCourtClient(
        minimum_interval=0.1,
        timeout=45,
    )


def test_live_case_summary_sentinel_exposes_all_six_sections() -> None:
    client = _client()
    try:
        lookup = client.case(la.PROBE_CASE_NUMBER)
    finally:
        client.close()

    assert lookup.page is not None
    page = lookup.page
    assert page.case_number == la.PROBE_CASE_NUMBER
    assert page.case_title.startswith("JAMES MATYAS")
    assert page.filing_date == "3/22/2024"
    assert page.filing_courthouse == "Alhambra Courthouse"
    assert page.parties
    assert page.documents
    assert page.past_proceedings
    assert page.register_actions
    assert page.document_image_url.startswith(
        f"{la.BASE_URL}/paos/v2web3/DocumentImages/"
    )


def test_live_tentative_index_exposes_current_webforms_inventory() -> None:
    client = _client()
    try:
        index = client.bootstrap_tentatives()
    finally:
        client.close()

    assert "__VIEWSTATE" in index.hidden_fields
    assert "__EVENTVALIDATION" in index.hidden_fields
    assert len(index.selections) > 10
    assert all(selection.native_value for selection in index.selections)
    assert all(selection.hearing_date_iso for selection in index.selections)


def test_live_one_current_tentative_selection_is_case_split() -> None:
    client = _client()
    try:
        index = client.bootstrap_tentatives()
        if not index.selections:
            pytest.skip("the court currently publishes no civil selections")
        selection, page = client.tentative_rulings(
            index.selections[0].native_value,
            bootstrap=index,
        )
    finally:
        client.close()

    assert selection.native_value == index.selections[0].native_value
    assert page.source_url.startswith(
        f"{la.BASE_URL}/tentativeRulingNet/ui/Result.aspx"
    )
    assert all(ruling.case_number for ruling in page.rulings)
    assert all(ruling.hearing_date_iso for ruling in page.rulings)
    assert all(ruling.department for ruling in page.rulings)
    assert all(ruling.full_text for ruling in page.rulings)


def test_live_probe_checks_both_components() -> None:
    result = la.execute(
        la.build_parser().parse_args(
            ["probe", "--minimum-interval", "0.1"]
        ),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    probe = result.records[0]
    assert probe["probe_case_number"] == la.PROBE_CASE_NUMBER
    assert probe["tentative_selection_count"] > 10
    assert probe["case_summary_counts"]["documents"] > 0
