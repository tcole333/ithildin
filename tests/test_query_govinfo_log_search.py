from argparse import Namespace

from tools import query_govinfo


def test_search_logs_query_before_source(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        query_govinfo,
        "_post_search",
        lambda query, page_size: {"count": 0, "results": []},
    )
    monkeypatch.setattr(
        query_govinfo,
        "log_search",
        lambda query_text, source, result_count: calls.append(
            (query_text, source, result_count)
        ),
    )

    query_govinfo.cmd_search(
        Namespace(
            query="Adelanto ICE Processing Center",
            collection="GAOREPORTS",
            limit=50,
            output=str(tmp_path / "results.json"),
            json=False,
        )
    )

    assert calls == [
        ("Adelanto ICE Processing Center", "govinfo_gaoreports", 0)
    ]
