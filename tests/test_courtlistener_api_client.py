"""Unit tests for CourtListener request construction."""

import pytest
import requests

from tools import query_courtlistener
from tools.courtlistener_api_client import CourtListenerClient


def test_search_cases_forwards_search_endpoint_date_filters(monkeypatch):
    """Date-bounded case searches must use parameters the search API honors."""
    client = CourtListenerClient(token="test-token")
    captured = {}

    def fake_search(query, search_type="o", court=None, max_results=100, **kwargs):
        captured.update(
            query=query,
            search_type=search_type,
            court=court,
            max_results=max_results,
            kwargs=kwargs,
        )
        return []

    monkeypatch.setattr(client, "search", fake_search)

    client.search_cases(
        '"The GEO Group, Inc."',
        court="flsd",
        date_filed_after="2023-01-01",
        date_filed_before="2023-12-31",
        max_results=25,
    )

    assert captured == {
        "query": '"The GEO Group, Inc."',
        "search_type": "r",
        "court": "flsd",
        "max_results": 25,
        "kwargs": {
            "filed_after": "2023-01-01",
            "filed_before": "2023-12-31",
        },
    }


def test_fjc_search_uses_one_bounded_request_attempt(monkeypatch):
    client = CourtListenerClient(token="test-token")
    captured = {}

    def fake_request(method, endpoint, params=None, json_body=None, retries=3):
        captured.update(method=method, endpoint=endpoint, retries=retries)
        return {"results": [], "next": None}

    monkeypatch.setattr(client, "_request", fake_request)

    assert client.search_fjc(plaintiff="Joshua Fink", max_results=100) == []
    assert captured == {
        "method": "GET",
        "endpoint": "fjc-integrated-database/",
        "retries": 1,
    }


def test_fjc_timeout_is_concise_and_does_not_write_output(
    monkeypatch, capsys, tmp_path
):
    class TimedOutClient:
        def search_fjc(self, **kwargs):
            raise requests.Timeout("simulated upstream timeout")

    output = tmp_path / "fjc.json"
    monkeypatch.setattr(query_courtlistener, "_client", lambda: TimedOutClient())
    args = type(
        "Args",
        (),
        {
            "plaintiff": "Joshua Fink",
            "defendant": None,
            "nos": None,
            "after": None,
            "before": None,
            "limit": 100,
            "output": str(output),
            "json_out": False,
        },
    )()

    with pytest.raises(SystemExit) as exc:
        query_courtlistener.cmd_fjc(args)

    assert exc.value.code == 1
    assert not output.exists()
    assert capsys.readouterr().err == (
        "ERROR: CourtListener FJC search timed out after one bounded request; "
        "try a narrower name or date range.\n"
    )
