"""Regression tests for the USAspending transaction-search wrapper."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from tools import query_usaspending


KEYWORD_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "usaspending_txn_skiptracing.json"
)


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
    saved = json.loads(output.read_text())
    assert saved["results"] == [result_row]
    assert saved["pagination"] == {
        "requested_page": 1,
        "requested_limit": 100,
        "returned_count": 1,
        "reported_total": 1,
        "has_next": None,
        "next_page": None,
        "raw": {"total": 1},
    }
    assert saved["query"]["recipient_scope_expansion_observed"] is False
    assert saved["returned_recipients"] == [
        {
            "recipient_uei": "JMLKZZ1NL2Z6",
            "recipient_name": "THE GEO GROUP, INC.",
        }
    ]


def _keyword_args(output=None, *, from_file=None, all_pages=False):
    return SimpleNamespace(
        keyword="skip tracing",
        start="2015-10-01",
        end="2026-07-27",
        naics="561611",
        psc="R799",
        agency="Department of Homeland Security",
        limit=100,
        all_pages=all_pages,
        from_file=str(from_file) if from_file else None,
        output=str(output) if output else None,
        json_out=False,
    )


def test_transactions_keyword_from_file_renders_saved_response(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        query_usaspending,
        "_fetch_post",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("--from-file must not access the network")
        ),
    )
    query_usaspending.cmd_transactions_keyword(
        _keyword_args(from_file=KEYWORD_FIXTURE)
    )

    output = capsys.readouterr().out
    assert "Found 82 transactions matching 'skip tracing'" in output
    assert "2025-10-09 | 70CDCR24FR0000006" in output
    assert "CAPGEMINI GOVERNMENT SOLUTIONS LLC" in output
    assert "$7,372,680.00 | Mod P00011" in output


def test_transactions_keyword_builds_filters_and_paginates(
    monkeypatch, tmp_path
):
    captured_payloads = []
    responses = [
        {
            "results": [
                {
                    "Award ID": "FIRST",
                    "Recipient Name": "FIRST RECIPIENT",
                    "Transaction Amount": 1,
                    "Action Date": "2025-01-01",
                    "Mod": "0",
                    "Transaction Description": "SKIP TRACING",
                }
            ],
            "page_metadata": {"hasNext": True},
        },
        {
            "results": [
                {
                    "Award ID": "SECOND",
                    "Recipient Name": "SECOND RECIPIENT",
                    "Transaction Amount": 2,
                    "Action Date": "2025-01-02",
                    "Mod": "P00001",
                    "Transaction Description": "SKIP TRACING MOD",
                }
            ],
            "page_metadata": {"hasNext": False},
        },
    ]

    def fake_fetch(endpoint, payload):
        assert endpoint == "/search/spending_by_transaction/"
        captured_payloads.append(payload)
        return responses.pop(0)

    monkeypatch.setattr(query_usaspending, "_fetch_post", fake_fetch)
    output = tmp_path / "keyword-transactions.json"

    query_usaspending.cmd_transactions_keyword(
        _keyword_args(output, all_pages=True)
    )

    assert [payload["page"] for payload in captured_payloads] == [1, 2]
    filters = captured_payloads[0]["filters"]
    assert filters["keywords"] == ["skip tracing"]
    assert filters["time_period"] == [
        {"start_date": "2015-10-01", "end_date": "2026-07-27"}
    ]
    assert filters["award_type_codes"] == ["A", "B", "C", "D"]
    # spending_by_transaction takes bare code strings; the object form used by
    # the award endpoints is rejected with HTTP 422 (verified live 2026-07-27).
    assert filters["naics_codes"] == ["561611"]
    assert filters["psc_codes"] == ["R799"]
    assert filters["agencies"] == [
        {
            "type": "awarding",
            "tier": "toptier",
            "name": "Department of Homeland Security",
        }
    ]
    assert [row["Award ID"] for row in json.loads(output.read_text())] == [
        "FIRST",
        "SECOND",
    ]


def test_transactions_keyword_from_file_cli_writes_fixture_results(
    run_python_script, tmp_path
):
    output = tmp_path / "skip-tracing-transactions.json"

    completed = run_python_script(
        "tools/query_usaspending.py",
        "transactions-keyword",
        "skip tracing",
        "--from-file",
        str(KEYWORD_FIXTURE),
        "--output",
        str(output),
    )

    assert completed.returncode == 0, completed.stderr
    results = json.loads(output.read_text())
    assert len(results) == 82
    assert any(
        row["Award ID"] == "70CDCR25FR0000127"
        and row["Mod"] == "P00002"
        for row in results
    )
    assert "82 results" in completed.stdout
