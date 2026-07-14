"""Regression tests for credential-safe HigherGov API failures."""

import sys

import requests

from tools import query_highergov


FAKE_KEY = "fake-highergov-key-must-not-leak"


def test_cli_request_exception_does_not_leak_api_key(
    monkeypatch, capsys, tmp_path
):
    output_path = tmp_path / "should-not-exist.json"

    def fail_request(url, params, timeout):
        request = requests.Request("GET", url, params=params).prepare()
        raise requests.HTTPError(
            f"500 Server Error for url: {request.url}", request=request
        )

    monkeypatch.setattr(query_highergov.requests, "get", fail_request)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_highergov.py",
            "--key",
            FAKE_KEY,
            "contract",
            "--award-id",
            "TEST-AWARD",
            "--output",
            str(output_path),
        ],
    )

    assert query_highergov.main() == 1
    captured = capsys.readouterr()
    assert FAKE_KEY not in captured.out
    assert FAKE_KEY not in captured.err
    assert "api_key=" not in captured.out
    assert "api_key=" not in captured.err
    assert not output_path.exists()


def test_bad_request_body_is_redacted(monkeypatch, capsys, tmp_path):
    output_path = tmp_path / "should-not-exist.json"
    response = requests.Response()
    response.status_code = 400
    response._content = (
        f"Invalid request URL: https://example.test/?api_key={FAKE_KEY}&q=x"
    ).encode()

    monkeypatch.setattr(
        query_highergov.requests, "get", lambda url, params, timeout: response
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_highergov.py",
            "--key",
            FAKE_KEY,
            "contract",
            "--award-id",
            "TEST-AWARD",
            "--output",
            str(output_path),
        ],
    )

    assert query_highergov.main() == 1
    captured = capsys.readouterr()
    assert FAKE_KEY not in captured.out
    assert FAKE_KEY not in captured.err
    assert not output_path.exists()
