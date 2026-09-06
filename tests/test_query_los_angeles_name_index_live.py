from __future__ import annotations

import os

import pytest

from tools import query_los_angeles_name_index as index


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded live probes",
)


def _client() -> index.LANameIndexClient:
    return index.LANameIndexClient(
        minimum_interval=0.1,
        timeout=45,
    )


def test_live_probe_exposes_exact_coverage_fees_and_form_contract() -> None:
    client = _client()
    try:
        probe = client.probe()
    finally:
        client.close()

    assert probe["landing"]["coverage"] == [
        {"case_type": "Unlimited Civil", "source_date_range": "1983 - Present"},
        {"case_type": "Probate", "source_date_range": "1983 - Present"},
        {"case_type": "Family Law", "source_date_range": "1983 - Present"},
        {"case_type": "Limited Civil", "source_date_range": "1991 - Present"},
        {"case_type": "Small Claims", "source_date_range": "1992 - Present"},
    ]
    guest_fees = [
        row
        for row in probe["fees"]["name_search_fees"]
        if row["account_type"] == "guest"
    ]
    assert guest_fees == [
        {
            "account_type": "guest",
            "description": "Per search fee",
            "amount_text": "$4.75",
            "amount_usd": 4.75,
        }
    ]
    assert probe["search_form"]["field_names"] == [
        "LastName",
        "FirstName",
        "CompanyName",
        "Remark",
        "FilingDateStart",
        "FilingDateEnd",
        "__RequestVerificationToken",
    ]
    assert (
        probe["guest"]["result_availability_statement"]
        == "Name Search results remain available for 24 hours after completing "
        "the transaction."
    )
    assert (
        probe["guest"]["faq_redo_statement"]
        == 'The "Redo Search" button will only be available for 2 hours after '
        "the original search was initially done."
    )


def test_live_fictitious_query_reaches_exact_cart_without_checkout() -> None:
    criteria = index._query_criteria(
        first_name=None,
        last_name=None,
        company="ZZZCODEXNAMEINDEXLIVEPROBE",
        filing_date_start=None,
        filing_date_end=None,
        remark="live-contract-probe",
    )
    client = _client()
    try:
        prepared = client.prepare(criteria)
    finally:
        client.close()

    assert len(prepared.cart.items) == 1
    assert (
        prepared.cart.items[0].description
        == 'Civil Name Search For "ZZZCODEXNAMEINDEXLIVEPROBE"'
    )
    assert prepared.cart.items[0].amount_usd == 4.75
    assert prepared.cart.total_usd == 4.75
    assert prepared.checkout_url.startswith(
        "https://ww2.lacourt.org/ShoppingCart/v3/Home/Index/"
    )
