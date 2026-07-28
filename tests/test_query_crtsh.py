import io
import json
from argparse import Namespace
from urllib.error import HTTPError

import pytest

from tools import query_crtsh


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


def test_fetch_retries_transient_failures_then_returns_json(monkeypatch, capsys):
    responses = iter(
        [
            HTTPError("https://crt.sh", 502, "Bad Gateway", None, io.BytesIO()),
            TimeoutError(),
            FakeResponse(b'[{"serial_number": "abc"}]'),
        ]
    )
    sleeps = []

    def fake_urlopen(_request, timeout):
        assert timeout == 7
        response = next(responses)
        if isinstance(response, BaseException):
            raise response
        return response

    monkeypatch.setattr(query_crtsh, "urlopen", fake_urlopen)
    monkeypatch.setattr(query_crtsh.time, "sleep", sleeps.append)

    assert query_crtsh._fetch({"q": "example.com"}, timeout=7) == [
        {"serial_number": "abc"}
    ]
    assert sleeps == [1, 2]
    assert capsys.readouterr().err.count("WARNING: crt.sh attempt") == 2


def test_fetch_exhausted_timeout_is_concise(monkeypatch, capsys):
    calls = 0

    def fake_urlopen(_request, timeout):
        nonlocal calls
        calls += 1
        assert timeout == 5
        raise TimeoutError

    monkeypatch.setattr(query_crtsh, "urlopen", fake_urlopen)
    monkeypatch.setattr(query_crtsh.time, "sleep", lambda _delay: None)

    with pytest.raises(SystemExit):
        query_crtsh._fetch({"q": "slow.example"}, timeout=5)

    error = capsys.readouterr().err
    assert calls == 3
    assert "failed after 3 attempts" in error
    assert "q=slow.example" in error
    assert "Traceback" not in error


def test_cert_command_uses_shared_fetch(monkeypatch, capsys):
    calls = []

    def fake_fetch(params, timeout):
        calls.append((params, timeout))
        return {"id": 123}

    monkeypatch.setattr(query_crtsh, "_fetch", fake_fetch)

    query_crtsh.cmd_cert(
        Namespace(cert_id="123", output=None, json_out=False)
    )

    assert calls == [({"id": "123"}, 30)]
    assert json.loads(capsys.readouterr().out) == {"id": 123}


def test_timeline_output_preserves_replayable_certificate_rows(
    monkeypatch, tmp_path
):
    records = [
        {
            "serial_number": "one",
            "not_before": "2024-02-01T00:00:00",
            "name_value": "a.example.com\nexample.com",
            "issuer_name": "C=US, O=Issuer One",
        },
        {
            "serial_number": "two",
            "not_before": "2023-01-01T00:00:00",
            "name_value": "b.example.com",
            "issuer_name": "C=US, O=Issuer Two",
        },
    ]
    output_path = tmp_path / "timeline.json"
    monkeypatch.setattr(query_crtsh, "_fetch", lambda *_args, **_kwargs: records)

    query_crtsh.cmd_timeline(
        Namespace(domain="example.com", output=str(output_path), json_out=False)
    )

    artifact = json.loads(output_path.read_text())
    assert artifact["first_seen"] == "2023-01-01"
    assert [row["serial_number"] for row in artifact["records"]] == ["two", "one"]
    assert artifact["records"][1]["name_value"] == "a.example.com\nexample.com"
