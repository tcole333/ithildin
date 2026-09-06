"""Search-history regressions with all OpenCorporates requests mocked."""

import json

import pytest

from tools import query_opencorporates as oc


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    monkeypatch.setattr(oc.requests, "get", lambda *_a, **_k: pytest.fail("No network calls permitted"))


@pytest.mark.parametrize("call,endpoint,params,response,source,key,count", [
    (lambda: oc.search_companies("Example", jurisdiction="us_ma", country="us", inactive=True,
                                address="1 Main St", per_page=2, page=3),
     "companies/search", {"q": "Example", "jurisdiction_code": "us_ma", "country_code": "us",
                          "inactive": "true", "registered_address": "1 Main St", "per_page": 2, "page": 3},
     {"results": {"companies": [{"company": {"name": "A"}}, {"company": {"name": "B"}}], "total_count": 98}},
     "opencorporates", {"mode": "search", "query": "Example", "jurisdiction": "us_ma", "country": "us",
                        "inactive": True, "address": "1 Main St", "per_page": 2, "page": 3}, 2),
    (lambda: oc.search_officers("Example", jurisdiction="us_ma", per_page=2, page=3),
     "officers/search", {"q": "Example", "jurisdiction_code": "us_ma", "per_page": 2, "page": 3, "order": "score"},
     {"results": {"officers": [{"officer": {"name": "A"}}], "total_count": 99}},
     "opencorporates_officers", {"mode": "officers", "query": "Example", "jurisdiction": "us_ma", "per_page": 2, "page": 3}, 1),
    (lambda: oc.get_company("us_ma", "123", sparse=True),
     "companies/us_ma/123", {"sparse": "true"}, {"results": {"company": {"name": "Example"}}},
     "opencorporates", {"mode": "entity", "query": "us_ma/123", "sparse": True}, 1),
    (lambda: oc.get_filings("us_ma", "123", per_page=2, page=3),
     "companies/us_ma/123/filings", {"per_page": 2, "page": 3},
     {"results": {"filings": [{"filing": {"title": "Report"}}], "total_count": 54}},
     "opencorporates", {"mode": "filings", "query": "us_ma/123", "per_page": 2, "page": 3}, 1),
])
def test_correct_argument_order_scalar_counts_and_scoped_keys(
        monkeypatch, call, endpoint, params, response, source, key, count):
    calls, logged = [], []
    def request(actual_endpoint, actual_params):
        calls.append((actual_endpoint, dict(actual_params)))
        actual_params["api_token"] = "must-not-be-logged"
        return response
    def logger(query_text, source, result_count):
        assert isinstance(query_text, str)
        assert type(result_count) is int
        logged.append((query_text, source, result_count))
    monkeypatch.setattr(oc, "api_request", request)
    monkeypatch.setattr(oc, "log_search", logger)
    result = call()
    assert calls == [(endpoint, params)]  # No extra request or request behavior change.
    assert len(logged) == 1
    actual_key, actual_source, actual_count = logged[0]
    assert json.loads(actual_key) == key
    assert actual_source == source and actual_count == count
    assert "must-not-be-logged" not in actual_key and "api_token" not in actual_key
    if "total_count" in response["results"]:
        assert result["total_count"] == response["results"]["total_count"]


@pytest.mark.parametrize("call,response", [
    (lambda: oc.search_companies("Example"), {"results": {"companies": []}}),
    (lambda: oc.search_officers("Example"), {"results": {"officers": []}}),
    (lambda: oc.get_company("us_ma", "123"), {"results": {"company": {"name": "Example"}}}),
    (lambda: oc.get_filings("us_ma", "123"), {"results": {"filings": []}}),
])
def test_log_failure_is_visible_redacted_and_preserves_result(monkeypatch, capsys, call, response):
    monkeypatch.setattr(oc, "api_request", lambda *_: response)
    def fail(**_):
        raise RuntimeError("failure including secret api_token=not-for-output")
    monkeypatch.setattr(oc, "log_search", fail)
    assert isinstance(call(), dict)
    stderr = capsys.readouterr().err
    assert "WARNING" in stderr and "not recorded in search history" in stderr
    assert "RuntimeError" in stderr
    assert "api_token" not in stderr and "not-for-output" not in stderr


def test_paging_filters_and_sparse_requests_get_distinct_keys(monkeypatch):
    keys = []
    monkeypatch.setattr(oc, "api_request", lambda *_: {"results": {"company": {"name": "Example"}}})
    monkeypatch.setattr(oc, "log_search", lambda query_text, source, result_count: keys.append(query_text))
    oc.search_companies("Example", page=1)
    oc.search_companies("Example", page=2)
    oc.search_companies("Example", jurisdiction="us_ma")
    oc.search_by_address("1 Main St")
    oc.search_by_address("2 Main St")
    oc.get_company("us_ma", "123", sparse=False)
    oc.get_company("us_ma", "123", sparse=True)
    assert len(keys) == len(set(keys)) == 7
