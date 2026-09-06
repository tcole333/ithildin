import json
from argparse import Namespace

from tools import query_courtlistener
from tools.courtlistener_api_client import CourtListenerClient


def test_client_follows_next_links_and_records_pagination(monkeypatch):
    client = CourtListenerClient(token="test-token")
    calls = []
    responses = iter(
        [
            {
                "count": 4,
                "results": [{"id": 1}, {"id": 2}],
                "next": (
                    "https://www.courtlistener.com/api/rest/v4/search/"
                    "?q=example&type=rd&cursor=next-page"
                ),
            },
            {
                "count": 4,
                "results": [{"id": 3}, {"id": 4}],
                "next": None,
            },
        ]
    )

    def fake_request(method, endpoint, params=None, json_body=None, retries=3):
        calls.append((method, endpoint, dict(params or {}), retries))
        return next(responses)

    monkeypatch.setattr(client, "_request", fake_request)

    results = list(
        client._paginate(
            "search/",
            {"q": "example", "type": "rd"},
            max_results=10,
        )
    )

    assert [row["id"] for row in results] == [1, 2, 3, 4]
    assert calls[1][2] == {
        "q": "example",
        "type": "rd",
        "cursor": "next-page",
    }
    assert client.last_pagination == {
        "requested_limit": 10,
        "returned": 4,
        "upstream_count": 4,
        "pages": 2,
        "complete": True,
        "limit_reached": False,
        "upstream_ended_early": False,
        "next_url": None,
    }


def test_client_records_missing_next_link_as_upstream_truncation(monkeypatch):
    client = CourtListenerClient(token="test-token")
    monkeypatch.setattr(
        client,
        "_request",
        lambda *_args, **_kwargs: {
            "count": 5,
            "results": [{"id": 1}, {"id": 2}],
            "next": None,
        },
    )

    assert len(list(client._paginate("search/", max_results=10))) == 2
    assert client.last_pagination["complete"] is False
    assert client.last_pagination["upstream_ended_early"] is True


def test_direct_client_import_loads_project_env_before_token_lookup(monkeypatch):
    monkeypatch.delenv("COURTLISTENER_TOKEN", raising=False)
    loaded = []

    def fake_load_env():
        loaded.append(True)
        monkeypatch.setenv("COURTLISTENER_TOKEN", "from-project-env")

    monkeypatch.setattr(
        "tools.courtlistener_api_client.load_env_file",
        fake_load_env,
    )

    client = CourtListenerClient()

    assert loaded == [True]
    assert client.token == "from-project-env"
    assert client.session.headers["Authorization"] == "Token from-project-env"


def test_pagination_report_warns_when_upstream_ends_early(capsys):
    client = type(
        "Client",
        (),
        {
            "last_pagination": {
                "requested_limit": 200,
                "returned": 40,
                "upstream_count": 112,
                "pages": 1,
                "complete": False,
                "limit_reached": False,
                "upstream_ended_early": True,
                "next_url": None,
            }
        },
    )()

    query_courtlistener._report_pagination(client, 200)

    assert (
        "ended without a next link after 40 of 112 reported results"
        in capsys.readouterr().err
    )


def test_search_reports_complete_upstream_count_below_limit(
    monkeypatch, tmp_path, capsys
):
    class CompleteClient:
        last_pagination = None

        def search(self, *_args, **_kwargs):
            self.last_pagination = {
                "requested_limit": 200,
                "returned": 2,
                "upstream_count": 2,
                "pages": 1,
                "complete": True,
                "limit_reached": False,
                "upstream_ended_early": False,
                "next_url": None,
            }
            return [{"id": 1}, {"id": 2}]

    output_path = tmp_path / "recap.json"
    monkeypatch.setattr(query_courtlistener, "_client", CompleteClient)

    query_courtlistener.cmd_search(
        Namespace(
            query="",
            party=None,
            firm=None,
            attorney=None,
            assigned_to=None,
            docket_number="1:26-cv-00809",
            semantic=False,
            highlight=False,
            after=None,
            before=None,
            type="rd",
            court="gand",
            limit=200,
            output=str(output_path),
            json_out=False,
        )
    )

    assert json.loads(output_path.read_text()) == [{"id": 1}, {"id": 2}]
    assert (
        "pagination complete: returned 2 of 2 upstream results"
        in capsys.readouterr().err
    )


def test_investment_search_writes_explicit_zero_result_artifact(
    monkeypatch, tmp_path, capsys
):
    class EmptyClient:
        def get_investments(self, **_kwargs):
            return []

    output_path = tmp_path / "investments.json"
    monkeypatch.setattr(query_courtlistener, "_client", EmptyClient)
    monkeypatch.setattr(
        query_courtlistener,
        "_record_search",
        lambda *_args, **_kwargs: None,
    )

    query_courtlistener.cmd_investments(
        Namespace(
            query="GEO Group",
            person_id=None,
            limit=100,
            output=str(output_path),
            json_out=False,
        )
    )

    assert json.loads(output_path.read_text()) == []
    assert "0 results" in capsys.readouterr().out
