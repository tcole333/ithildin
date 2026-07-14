from __future__ import annotations

import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from tools import query_documentcloud


def _args(output, *, query="Ballard Partners DHS", project=216915, limit=2):
    return SimpleNamespace(
        query=query,
        project=project,
        limit=limit,
        output=str(output),
        json_out=False,
    )


def test_search_uses_scoped_endpoint_and_preserves_cursor_filters(monkeypatch, tmp_path):
    output = tmp_path / "results.json"
    urls = []
    query = "Ballard Partners DHS"
    next_url = (
        "https://api.www.documentcloud.org/api/documents/search/"
        "?q=Ballard+Partners+DHS&project=216915&per_page=2&cursor=NEXT"
    )

    responses = [
        {
            "count": 2,
            "escaped": False,
            "results": [{"id": "6359032", "title": "Ballard communications"}],
            "next": next_url,
        },
        {
            "count": 2,
            "escaped": False,
            "results": [{"id": "5751683", "title": "DHS no-record response"}],
            "next": None,
        },
    ]

    def fake_request(url):
        urls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(query_documentcloud, "_request", fake_request)
    monkeypatch.setattr(query_documentcloud.time, "sleep", lambda _: None)
    query_documentcloud.cmd_search(_args(output, query=query))

    first = urlparse(urls[0])
    assert first.path.endswith("/api/documents/search/")
    assert parse_qs(first.query) == {
        "q": [query],
        "per_page": ["2"],
        "project": ["216915"],
    }
    assert urls[1] == next_url
    assert [row["id"] for row in json.loads(output.read_text())] == [
        "6359032",
        "5751683",
    ]


def test_search_rejects_unfiltered_list_response(monkeypatch, tmp_path, capsys):
    output = tmp_path / "leaked.json"
    monkeypatch.setattr(
        query_documentcloud,
        "_request",
        lambda url: {
            "results": [{"id": 1, "title": "A.I.G. Bailout"}],
            "next": "https://api.www.documentcloud.org/api/documents/?cursor=NEXT",
        },
    )

    with pytest.raises(SystemExit) as exc_info:
        query_documentcloud.cmd_search(_args(output, project=None, limit=1))

    assert exc_info.value.code == 1
    assert not output.exists()
    assert "refusing potentially unfiltered documents" in capsys.readouterr().err
