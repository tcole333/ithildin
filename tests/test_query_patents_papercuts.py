from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from tools import query_patents


def _inventor_entry(app_number, patent_number, inventor_name):
    return {
        "applicationNumberText": app_number,
        "applicationMetaData": {
            "patentNumber": patent_number,
            "inventorBag": [{"inventorNameText": inventor_name}],
            "inventionTitle": f"Patent by {inventor_name}",
        },
    }


def test_inventor_search_quotes_and_exactly_resolves_full_name(
    monkeypatch,
    tmp_path,
):
    output = tmp_path / "inventor.json"
    captured = {}
    response = {
        "count": 2022,
        "patentFileWrapperDataBag": [
            _inventor_entry("1", "101", "Carl Gregory Behm"),
            _inventor_entry("2", "102", "Gregory Behm"),
            _inventor_entry("3", "103", "Behm, Gregory"),
        ],
    }

    def fake_search(query, **kwargs):
        captured["query"] = query
        return response

    monkeypatch.setattr(query_patents, "_search_patents", fake_search)
    monkeypatch.setattr(query_patents, "DB_PATH", tmp_path / "patents.db")
    monkeypatch.setattr(query_patents, "_log", lambda *args: None)

    query_patents.cmd_inventor(
        SimpleNamespace(
            name="Gregory Behm",
            limit=100,
            output=str(output),
            json_out=False,
        )
    )

    assert captured["query"] == 'inventorNameText:"Gregory Behm"'
    result = json.loads(output.read_text())
    assert result["match_semantics"] == "exact_normalized_inventor_name"
    assert result["api_candidate_total"] == 2022
    assert result["api_candidates_screened"] == 3
    assert result["total"] == 2
    assert [
        patent["inventors"][0] for patent in result["patents"]
    ] == ["Gregory Behm", "Behm, Gregory"]


def test_single_token_inventor_search_preserves_surname_lookup():
    assert query_patents._exact_inventor_match(
        {"inventors": [{"name": "Steven Paul Jobs"}]},
        "Jobs",
    )


def test_network_failure_writes_unavailable_artifact_and_returns_nonzero(
    monkeypatch,
    tmp_path,
    capsys,
):
    output = tmp_path / "unavailable.json"

    def unavailable(*args, **kwargs):
        raise query_patents.PatentSourceUnavailable("DNS lookup failed")

    monkeypatch.setattr(query_patents, "_search_patents", unavailable)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_patents.py",
            "inventor",
            "Gregory Behm",
            "--output",
            str(output),
        ],
    )

    assert query_patents.main() == 1
    result = json.loads(output.read_text())
    assert result == {
        "status": "unavailable",
        "source": "uspto_odp",
        "command": "inventor",
        "query": "Gregory Behm",
        "error": "DNS lookup failed",
        "results": [],
    }
    captured = capsys.readouterr()
    assert "results unavailable" in captured.out
    assert "USPTO ODP unavailable" in captured.err
