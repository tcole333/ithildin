import gzip
import json
from argparse import Namespace
from email.message import Message

import pytest

from tools import query_wayback


class FakeResponse:
    def __init__(self, payload, *, url="https://web.archive.org/example"):
        self.payload = payload
        self.url = url
        self.headers = Message()
        self.headers["Content-Encoding"] = "gzip"
        self.headers["Content-Type"] = "text/html; charset=utf-8"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


def test_decode_http_body_handles_gzip_header_and_magic_bytes():
    content = "<html><body>Archived café</body></html>"
    compressed = gzip.compress(content.encode())

    assert query_wayback._decode_http_body(compressed, "gzip") == content
    assert query_wayback._decode_http_body(compressed) == content


def test_cdx_timeout_exits_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr(
        query_wayback,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()),
    )

    with pytest.raises(SystemExit):
        query_wayback._cdx_fetch({"url": "slow.example"}, timeout=9)

    error = capsys.readouterr().err
    assert "did not respond within 9s" in error
    assert "Traceback" not in error


def test_fetch_writes_decoded_gzip_content(monkeypatch, tmp_path):
    content = "<html><body>Readable archive</body></html>"
    response = FakeResponse(gzip.compress(content.encode()))
    output_path = tmp_path / "fetch.json"
    monkeypatch.setattr(query_wayback, "urlopen", lambda *_args, **_kwargs: response)

    query_wayback.cmd_fetch(
        Namespace(
            url="example.com",
            timestamp="20250101000000",
            max_length=0,
            output=str(output_path),
            json_out=False,
        )
    )

    artifact = json.loads(output_path.read_text())
    assert artifact["content"] == content
    assert artifact["content_length"] == len(content)
