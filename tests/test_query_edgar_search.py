from __future__ import annotations

import argparse
import json

import pytest

from tools import query_edgar


def _args(output, forms):
    return argparse.Namespace(
        query=["Admiral Permian Resources"],
        offset=0,
        start=None,
        end=None,
        forms=forms,
        size=20,
        sort="relevance",
        output=str(output),
        json_out=False,
    )


@pytest.mark.parametrize(
    ("forms", "expected"),
    [
        ("D,D/A", "D"),
        ("D/A,D", "D"),
        ("S-1,S-1/A,8-K", "S-1,8-K"),
        ("D,8-K", "D,8-K"),
        ("D/A,S-1/A", "D/A,S-1/A"),
        ("D", "D"),
        ("D/A", "D/A"),
    ],
)
def test_normalize_efts_forms_only_removes_redundant_amendments(forms, expected):
    assert query_edgar._normalize_efts_forms(forms) == expected


def test_search_collapses_base_and_amendment_before_request(
    tmp_path, monkeypatch
):
    response = {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_id": "0000000000-17-000001:primary_doc.xml",
                    "_source": {
                        "form": "D",
                        "file_date": "2017-03-15",
                    },
                }
            ],
        }
    }
    captured = {}

    def fake_request(url, params):
        captured["url"] = url
        captured["params"] = params
        return response

    monkeypatch.setattr(query_edgar, "_request", fake_request)
    monkeypatch.setattr(query_edgar, "_log", lambda *args: None)
    output = tmp_path / "results.json"

    query_edgar.cmd_search(_args(output, "D,D/A"))

    assert captured == {
        "url": query_edgar.EFTS_URL,
        "params": {
            "q": '"Admiral Permian Resources"',
            "from": 0,
            "forms": "D",
        },
    }
    assert json.loads(output.read_text()) == response


def test_search_preserves_single_amendment_filter(tmp_path, monkeypatch):
    captured = {}

    def fake_request(url, params):
        captured.update(params)
        return {"hits": {"total": {"value": 0}, "hits": []}}

    monkeypatch.setattr(query_edgar, "_request", fake_request)
    monkeypatch.setattr(query_edgar, "_log", lambda *args: None)

    query_edgar.cmd_search(_args(tmp_path / "results.json", "D/A"))

    assert captured["forms"] == "D/A"
