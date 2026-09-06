from __future__ import annotations

import argparse
from io import BytesIO
import json
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

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

    def fake_request(url, params, *, raise_errors=False):
        captured["url"] = url
        captured["params"] = params
        captured["raise_errors"] = raise_errors
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
        "raise_errors": True,
    }
    assert json.loads(output.read_text()) == response


def test_search_preserves_single_amendment_filter(tmp_path, monkeypatch):
    captured = {}

    def fake_request(url, params, *, raise_errors=False):
        captured.update(params)
        captured["raise_errors"] = raise_errors
        return {"hits": {"total": {"value": 0}, "hits": []}}

    monkeypatch.setattr(query_edgar, "_request", fake_request)
    monkeypatch.setattr(query_edgar, "_log", lambda *args: None)

    query_edgar.cmd_search(_args(tmp_path / "results.json", "D/A"))

    assert captured["forms"] == "D/A"
    assert captured["raise_errors"] is True


def test_search_exits_nonzero_when_sec_remains_unavailable(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "results.json"

    def unavailable(url, params, *, raise_errors=False):
        assert url == query_edgar.EFTS_URL
        assert raise_errors is True
        raise query_edgar.SecRequestError(
            "HTTP 500 from SEC: internal error",
            url=url,
            status=500,
        )

    monkeypatch.setattr(query_edgar, "_request", unavailable)

    with pytest.raises(SystemExit) as exc:
        query_edgar.cmd_search(_args(output, None))

    assert exc.value.code == 2
    assert not output.exists()
    assert capsys.readouterr().err == (
        "ERROR: EDGAR search unavailable: "
        "HTTP 500 from SEC: internal error\n"
    )


def test_search_retries_http_500_then_exits_nonzero(
    tmp_path, monkeypatch, capsys
):
    attempts = []
    sleeps = []

    def server_error(request, timeout):
        attempts.append((request.full_url, timeout))
        raise HTTPError(
            request.full_url,
            500,
            "Internal Server Error",
            {},
            BytesIO(b"temporary SEC failure"),
        )

    monkeypatch.setattr(query_edgar, "urlopen", server_error)
    monkeypatch.setattr(query_edgar.time, "sleep", sleeps.append)
    monkeypatch.setattr(query_edgar, "_last_request", 0.0)

    with pytest.raises(SystemExit) as exc:
        query_edgar.cmd_search(_args(tmp_path / "results.json", None))

    assert exc.value.code == 2
    assert len(attempts) == query_edgar.MAX_REQUEST_ATTEMPTS
    assert 0.5 in sleeps
    assert 1.0 in sleeps
    assert all(delay <= 5 for delay in sleeps)
    assert "HTTP 500 from SEC" in capsys.readouterr().err


def test_search_recovers_exact_corporate_name_after_transient_http_500(
    tmp_path, monkeypatch
):
    attempts = []
    response = {
        "hits": {
            "total": {"value": 1},
            "hits": [{"_source": {"file_date": "2024-01-01"}}],
        }
    }

    def transient_server_error(request, timeout):
        attempts.append(request.full_url)
        if len(attempts) == 1:
            raise HTTPError(
                request.full_url,
                500,
                "Internal Server Error",
                {},
                BytesIO(b"temporary SEC failure"),
            )
        success = BytesIO(json.dumps(response).encode())
        success.headers = {"Content-Type": "application/json"}
        return success

    monkeypatch.setattr(query_edgar, "urlopen", transient_server_error)
    monkeypatch.setattr(query_edgar.time, "sleep", lambda _delay: None)
    monkeypatch.setattr(query_edgar, "_last_request", 0.0)
    monkeypatch.setattr(query_edgar, "_log", lambda *_args: None)
    output = tmp_path / "geo-transport.json"
    args = _args(output, None)
    args.query = ["GEO Transport, Inc."]

    query_edgar.cmd_search(args)

    assert len(attempts) == 2
    assert parse_qs(urlparse(attempts[-1]).query)["q"] == [
        '"GEO Transport, Inc."'
    ]
    assert json.loads(output.read_text()) == response
