from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tools import query_usaspending


def _args(output, *, uei=None, query=None, award_id=None, agency=None):
    return SimpleNamespace(
        query=query,
        uei=uei,
        award_id=award_id,
        agency=agency,
        grants=False,
        limit=100,
        page=1,
        output=str(output),
        json_out=False,
    )


def _row(uei, name, *, award_id="PRIME-1", agency="Department of Homeland Security"):
    return {
        "Sub-Award ID": f"SUB-{uei}",
        "Sub-Awardee Name": name,
        "Sub-Recipient UEI": uei,
        "Sub-Award Amount": 100,
        "Sub-Award Date": "2026-01-01",
        "Sub-Award Description": "Services",
        "Prime Award ID": award_id,
        "Prime Recipient Name": "Prime Recipient",
        "Prime Award Recipient UEI": "PRIMEUEI1234",
        "Awarding Agency": agency,
        "Awarding Sub Agency": "Test Component",
    }


def test_subawards_use_advanced_search_and_keep_uei_queries_distinct(monkeypatch, tmp_path):
    captured = []
    rows = {
        "JMLKZZ1NL2Z6": _row("JMLKZZ1NL2Z6", "THE GEO GROUP, INC."),
        "DFEKRCYPZD84": _row("DFEKRCYPZD84", "GEO TRANSPORT, INC."),
    }

    def fake_fetch(endpoint, payload):
        captured.append((endpoint, payload))
        uei = payload["filters"]["recipient_search_text"][0]
        return {
            "spending_level": "subawards",
            "results": [rows[uei]],
            "page_metadata": {"page": 1, "hasNext": False},
        }

    monkeypatch.setattr(query_usaspending, "_fetch_post", fake_fetch)
    outputs = []
    for uei in rows:
        output = tmp_path / f"{uei}.json"
        query_usaspending.cmd_subawards(
            _args(output, uei=uei, agency="Department of Homeland Security")
        )
        outputs.append(json.loads(output.read_text()))

    assert outputs[0] != outputs[1]
    assert [result["results"][0]["Sub-Recipient UEI"] for result in outputs] == list(rows)
    for endpoint, payload in captured:
        assert endpoint == "/search/spending_by_award/"
        assert payload["subawards"] is True
        assert payload["spending_level"] == "subawards"
        assert payload["filters"]["agencies"] == [{
            "type": "awarding",
            "tier": "toptier",
            "name": "Department of Homeland Security",
        }]
        assert "Sub-Recipient UEI" in payload["fields"]


def test_subawards_serialize_exact_prime_award_and_normalize_recipient_name(
    monkeypatch, tmp_path
):
    captured = {}
    output = tmp_path / "award.json"

    def fake_fetch(endpoint, payload):
        captured["payload"] = payload
        return {
            "results": [_row(
                "DFEKRCYPZD84",
                "GEO TRANSPORT, INC.",
                award_id="70CDCR23FR0000035",
            )]
        }

    monkeypatch.setattr(query_usaspending, "_fetch_post", fake_fetch)
    query_usaspending.cmd_subawards(_args(
        output,
        query="GEO Transport Inc",
        award_id="70CDCR23FR0000035",
    ))

    assert captured["payload"]["filters"]["award_ids"] == ["70CDCR23FR0000035"]
    assert json.loads(output.read_text())["results"][0]["Prime Award ID"] == "70CDCR23FR0000035"


def test_subawards_write_error_without_out_of_scope_rows(monkeypatch, tmp_path, capsys):
    output = tmp_path / "leaked.json"
    leaked = _row("UNRELATED123", "MAYA BRIDGE LLC")
    monkeypatch.setattr(
        query_usaspending,
        "_fetch_post",
        lambda endpoint, payload: {"results": [leaked]},
    )

    with pytest.raises(SystemExit) as exc_info:
        query_usaspending.cmd_subawards(_args(
            output,
            uei="JMLKZZ1NL2Z6",
            agency="Department of Homeland Security",
        ))

    assert exc_info.value.code == 1
    saved = json.loads(output.read_text())
    assert saved["status"] == "error"
    assert saved["results"] == []
    assert saved["errors"][0]["kind"] == "scope_mismatch"
    assert "MAYA BRIDGE LLC" not in output.read_text()
    assert "refusing to emit potentially unfiltered results" in capsys.readouterr().err
