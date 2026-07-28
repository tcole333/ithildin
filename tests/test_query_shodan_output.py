import json
from argparse import Namespace

from tools import query_shodan


def test_search_output_counts_returned_matches(monkeypatch, tmp_path, capsys):
    payload = {"total": 40, "matches": [{"ip_str": "192.0.2.1"}, {"ip_str": "192.0.2.2"}]}
    output_path = tmp_path / "search.json"
    monkeypatch.setattr(query_shodan, "_fetch", lambda *_args, **_kwargs: payload)

    query_shodan.cmd_search(
        Namespace(
            query="ssl:example.com",
            facets=None,
            count_only=False,
            page=1,
            output=str(output_path),
            json_out=False,
            limit=20,
        )
    )

    assert capsys.readouterr().out.startswith("2 results ")
    assert json.loads(output_path.read_text()) == payload


def test_count_only_output_uses_api_total(monkeypatch, tmp_path, capsys):
    payload = {"total": 40, "facets": {}}
    output_path = tmp_path / "count.json"
    monkeypatch.setattr(query_shodan, "_fetch", lambda *_args, **_kwargs: payload)

    query_shodan.cmd_search(
        Namespace(
            query="ssl:example.com",
            facets=None,
            count_only=True,
            page=1,
            output=str(output_path),
            json_out=False,
            limit=20,
        )
    )

    assert capsys.readouterr().out.startswith("40 results ")


def test_dns_output_counts_hostname_mappings(monkeypatch, tmp_path, capsys):
    payload = {"a.example": "192.0.2.1", "b.example": None}
    output_path = tmp_path / "dns.json"
    monkeypatch.setattr(query_shodan, "_fetch", lambda *_args, **_kwargs: payload)

    query_shodan.cmd_dns_resolve(
        Namespace(
            hostnames="a.example,b.example",
            output=str(output_path),
            json_out=False,
        )
    )

    assert capsys.readouterr().out.startswith("2 results ")
    assert json.loads(output_path.read_text()) == payload


def test_ssl_output_counts_returned_matches(monkeypatch, tmp_path, capsys):
    payload = {"total": 40, "matches": [{}, {}, {}]}
    output_path = tmp_path / "ssl.json"
    monkeypatch.setattr(query_shodan, "_fetch", lambda *_args, **_kwargs: payload)

    query_shodan.cmd_ssl_cert(
        Namespace(
            domain="example.com",
            output=str(output_path),
            json_out=False,
        )
    )

    assert capsys.readouterr().out.startswith("3 results ")
