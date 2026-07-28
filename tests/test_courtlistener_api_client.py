"""Unit tests for CourtListener request construction."""

from types import SimpleNamespace

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


def test_opinion_auto_prefers_cluster_when_numeric_ids_collide(
    monkeypatch, tmp_path
):
    calls = []

    class CollisionClient:
        def get_cluster(self, cluster_id):
            calls.append(("cluster", cluster_id))
            return {
                "id": cluster_id,
                "sub_opinions": [
                    "https://www.courtlistener.com/api/rest/v4/opinions/8495830/"
                ],
            }

        def get_opinion(self, opinion_id):
            calls.append(("opinion", opinion_id))
            return {"id": opinion_id, "plain_text": "Correct cluster opinion text."}

    output = tmp_path / "opinion.json"
    monkeypatch.setattr(query_courtlistener, "_client", CollisionClient)

    query_courtlistener.cmd_opinion(
        SimpleNamespace(
            opinion_id=8523350,
            id_type="auto",
            lines=100,
            output=str(output),
            json_out=False,
        )
    )

    assert calls == [("cluster", 8523350), ("opinion", 8495830)]
    assert output.read_text().find('"id": 8495830') >= 0


def test_opinion_id_type_can_force_raw_opinion_lookup(monkeypatch, tmp_path):
    calls = []

    class OpinionClient:
        def get_opinion(self, opinion_id):
            calls.append(opinion_id)
            return {"id": opinion_id, "plain_text": "Raw opinion text."}

    output = tmp_path / "opinion.json"
    monkeypatch.setattr(query_courtlistener, "_client", OpinionClient)

    query_courtlistener.cmd_opinion(
        SimpleNamespace(
            opinion_id=8523350,
            id_type="opinion",
            lines=100,
            output=str(output),
            json_out=False,
        )
    )

    assert calls == [8523350]
