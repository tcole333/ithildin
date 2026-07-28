import argparse
import json

from tools import query_courtlistener, query_florida_ucc, query_lobbying


class _CourtListenerClient:
    @staticmethod
    def search(*_args, **_kwargs):
        return []

    @staticmethod
    def search_cases(*_args, **_kwargs):
        return []


def test_recap_output_logs_before_return_with_canonical_source(
    tmp_path, monkeypatch
):
    logged = []
    output = tmp_path / "recap.json"
    monkeypatch.setattr(
        query_courtlistener,
        "_client",
        lambda: _CourtListenerClient(),
    )
    monkeypatch.setattr(
        query_courtlistener,
        "_log",
        lambda query, source, count: logged.append((query, source, count)),
    )

    query_courtlistener.cmd_recap_search(
        argparse.Namespace(
            query="Phillippe Kouzmine",
            court="nysd",
            limit=20,
            output=str(output),
            json_out=False,
        )
    )

    assert output.exists()
    assert len(logged) == 1
    key, source, count = logged[0]
    assert json.loads(key) == {
        "mode": "recap_search",
        "query": "Phillippe Kouzmine",
        "court": "nysd",
    }
    assert source == "courtlistener"
    assert count == 0


def test_courtlistener_modes_do_not_collapse_same_term(monkeypatch):
    logged = []
    monkeypatch.setattr(
        query_courtlistener,
        "_client",
        lambda: _CourtListenerClient(),
    )
    monkeypatch.setattr(
        query_courtlistener,
        "_log",
        lambda query, source, count: logged.append((query, source, count)),
    )
    monkeypatch.setattr(
        query_courtlistener,
        "write_output",
        lambda *_args, **_kwargs: True,
    )

    query_courtlistener.cmd_cases(
        argparse.Namespace(
            query="Example Name",
            court=None,
            after=None,
            before=None,
            limit=20,
        )
    )
    query_courtlistener.cmd_search(
        argparse.Namespace(
            query="Example Name",
            party=None,
            firm=None,
            attorney=None,
            assigned_to=None,
            docket_number=None,
            semantic=False,
            highlight=False,
            after=None,
            before=None,
            type="r",
            court=None,
            limit=20,
        )
    )

    assert [source for _, source, _ in logged] == [
        "courtlistener",
        "courtlistener",
    ]
    assert logged[0][0] != logged[1][0]
    assert json.loads(logged[0][0])["mode"] == "cases"
    assert json.loads(logged[1][0])["mode"] == "search"


def test_lobbying_modes_and_filing_filters_have_distinct_keys(monkeypatch):
    logged = []
    monkeypatch.setattr(
        query_lobbying,
        "_paginate",
        lambda *_args, **_kwargs: ([], 7),
    )
    monkeypatch.setattr(
        query_lobbying,
        "_log",
        lambda query, source, count: logged.append((query, source, count)),
    )
    monkeypatch.setattr(
        query_lobbying,
        "write_output",
        lambda *_args, **_kwargs: True,
    )

    query_lobbying.cmd_client(
        argparse.Namespace(query="GEO Group", year=2024, limit=20)
    )
    query_lobbying.cmd_registrant(
        argparse.Namespace(query="GEO Group", year=2024, limit=20)
    )
    query_lobbying.cmd_filings(
        argparse.Namespace(
            client="GEO Group",
            registrant="Checkmate Government Relations",
            type="q1",
            year=2024,
            limit=20,
        )
    )

    keys = [json.loads(query) for query, _, _ in logged]
    assert [key["mode"] for key in keys] == [
        "client",
        "registrant",
        "filings",
    ]
    assert len({query for query, _, _ in logged}) == 3
    assert {source for _, source, _ in logged} == {"lobbying"}
    assert keys[2] == {
        "mode": "filings",
        "client": "GEO Group",
        "registrant": "Checkmate Government Relations",
        "filing_type": "Q1",
        "year": 2024,
    }


def test_lobbying_contributions_logs_even_when_output_returns(monkeypatch):
    logged = []
    monkeypatch.setattr(
        query_lobbying,
        "_paginate",
        lambda *_args, **_kwargs: ([], 0),
    )
    monkeypatch.setattr(
        query_lobbying,
        "_log",
        lambda query, source, count: logged.append((query, source, count)),
    )
    monkeypatch.setattr(
        query_lobbying,
        "write_output",
        lambda *_args, **_kwargs: True,
    )

    query_lobbying.cmd_contributions(
        argparse.Namespace(query="GEO Group", limit=20)
    )

    assert json.loads(logged[0][0]) == {
        "mode": "contributions",
        "query": "GEO Group",
    }
    assert logged[0][1:] == ("lobbying", 0)


def test_florida_ucc_uses_current_log_signature_and_filter_key(monkeypatch):
    logged = []
    monkeypatch.setattr(
        query_florida_ucc,
        "_search_page",
        lambda *_args, **_kwargs: {
            "debtors": [{"uccNumber": str(index)} for index in range(7)],
            "totalExactMatches": 7,
        },
    )
    monkeypatch.setattr(
        query_florida_ucc,
        "log_search",
        lambda query, source, count: logged.append((query, source, count)),
    )

    result = query_florida_ucc.search_org(
        "GEO TRANSPORT, INC.",
        status="all",
    )

    assert result["returned"] == 7
    assert len(logged) == 1
    key, source, count = logged[0]
    assert json.loads(key) == {
        "mode": "organization",
        "query": "GEO TRANSPORT, INC.",
        "status": "all",
        "pagination": "first_page",
        "match": "exact",
    }
    assert source == "florida_ucc"
    assert count == 7
