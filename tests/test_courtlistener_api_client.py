"""Unit tests for CourtListener request construction."""

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
