import io
import json
import sys
from types import SimpleNamespace
from urllib.error import HTTPError

from tools import query_lobbying


def _rate_limit_error():
    return HTTPError(
        "https://lda.senate.gov/api/v1/filings/",
        429,
        "rate limited",
        {"Retry-After": "0"},
        io.BytesIO(b'{"detail":"Request was throttled."}'),
    )


def test_fetch_retries_429_then_raises_source_error():
    attempts = []
    sleeps = []

    def opener(_request, timeout):
        attempts.append(timeout)
        raise _rate_limit_error()

    try:
        query_lobbying._fetch(
            "/filings/",
            opener=opener,
            sleeper=sleeps.append,
        )
    except query_lobbying.LDARequestError as exc:
        assert "HTTP 429" in str(exc)
    else:
        raise AssertionError("rate limiting must not be converted into zero results")

    assert attempts == [60, 60]
    assert sleeps == [0.0]


def test_cli_failure_is_nonzero_and_does_not_write_output(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "filings.json"
    monkeypatch.setattr(
        query_lobbying,
        "_paginate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            query_lobbying.LDARequestError("HTTP 429: throttled")
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_lobbying.py",
            "filings",
            "--client",
            "The GEO Group",
            "--output",
            str(output),
        ],
    )

    assert query_lobbying.main() == 1
    assert not output.exists()
    assert "ERROR: HTTP 429" in capsys.readouterr().err


def test_zero_result_lobbyist_search_writes_empty_output(tmp_path, monkeypatch):
    output = tmp_path / "lobbyist.json"
    monkeypatch.setattr(
        query_lobbying,
        "_fetch",
        lambda *_args, **_kwargs: {"count": 0, "results": []},
    )
    monkeypatch.setattr(
        query_lobbying,
        "_paginate",
        lambda *_args, **_kwargs: ([], 0),
    )
    monkeypatch.setattr(query_lobbying, "_log", lambda *_args: None)

    query_lobbying.cmd_lobbyist(
        SimpleNamespace(
            query="No Such Lobbyist",
            limit=100,
            output=str(output),
            json_out=False,
        )
    )

    assert json.loads(output.read_text()) == []
