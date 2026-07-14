"""Regression tests for the USAspending transaction-search wrapper."""

from __future__ import annotations

import json
from types import SimpleNamespace

from tools import query_usaspending


def _transaction_args(output):
    return SimpleNamespace(
        query=None,
        uei="JMLKZZ1NL2Z6",
        agency="Department of Homeland Security",
        date_range=None,
        grants=False,
        limit=100,
        page=1,
        output=str(output),
        json_out=False,
    )


def test_transactions_use_current_fields_and_preserve_forensic_identifiers(
    monkeypatch, tmp_path
):
    captured = {}
    result_row = {
        "Award ID": "70CDCR26FR0000042",
        "Recipient Name": "THE GEO GROUP, INC.",
        "Action Date": "2026-06-26",
        "Transaction Amount": 41167972.72,
        "Awarding Agency": "Department of Homeland Security",
        "Awarding Sub Agency": "U.S. Immigration and Customs Enforcement",
        "Award Type": "DELIVERY ORDER",
        "Transaction Description": "DETENTION SERVICES",
        "Mod": "P00003",
        "Recipient UEI": "JMLKZZ1NL2Z6",
        "NAICS": {"code": "561612", "description": "Security Guards"},
        "PSC": {"code": "S206", "description": "Guard Services"},
    }

    def fake_fetch(endpoint, payload):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        return {"results": [result_row], "page_metadata": {"total": 1}}

    monkeypatch.setattr(query_usaspending, "_fetch_post", fake_fetch)
    output = tmp_path / "transactions.json"

    query_usaspending.cmd_transactions(_transaction_args(output))

    fields = captured["payload"]["fields"]
    assert captured["endpoint"] == "/search/spending_by_transaction/"
    assert captured["payload"]["sort"] == "Transaction Amount"
    assert "Federal Action Obligation" not in fields
    assert "Description" not in fields
    assert {
        "Transaction Amount",
        "Transaction Description",
        "Mod",
        "Recipient UEI",
        "NAICS",
        "PSC",
    }.issubset(fields)
    assert json.loads(output.read_text()) == [result_row]
