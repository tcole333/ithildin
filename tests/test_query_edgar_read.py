import argparse
import gzip
import json
from urllib.error import HTTPError

import pytest

from tools import query_edgar


class _Response:
    def __init__(self, body, headers=None):
        self.body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit=None):
        return self.body if limit is None else self.body[:limit]


def _read_args(**overrides):
    values = {
        "url": "https://www.sec.gov/Archives/edgar/data/1/2/filing.htm",
        "ticker": None,
        "form_type": "10-K",
        "lines": 5,
        "find": None,
        "context": 2,
        "max_matches": 20,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_strip_html_preserves_nested_table_footnotes():
    filing = """
    <html><head><script>discard me</script></head><body>
      <table>
        <tr><th>Name</th><th>Beneficial ownership</th></tr>
        <tr>
          <td><span>Malcolm <b>Scott</b> Macintyre</span><sup>(4)</sup></td>
          <td>Consists of <font>200,000 Ordinary Shares</font> held indirectly.</td>
        </tr>
      </table>
    </body></html>
    """

    text = query_edgar._strip_html(filing)

    assert "Malcolm Scott Macintyre(4)" in text
    assert "Consists of 200,000 Ordinary Shares held indirectly." in text
    assert "discard me" not in text


def test_read_output_contains_complete_late_table_text(monkeypatch, tmp_path):
    prefix = "".join(f"<tr><td>Prefix row {number}</td></tr>" for number in range(650))
    filing = f"""
    <html><body><table>{prefix}
      <tr><td>Malcolm Scott Macintyre<sup>(4)</sup></td>
      <td>Consists of 200,000 Ordinary Shares held indirectly.</td></tr>
    </table></body></html>
    """
    monkeypatch.setattr(
        query_edgar,
        "_fetch_filing_document",
        lambda *_args, **_kwargs: (filing.encode(), "http"),
    )
    output = tmp_path / "filing.json"

    query_edgar.cmd_read(_read_args(output=str(output)))

    result = json.loads(output.read_text())
    assert result["line_count"] > 500
    assert "Malcolm Scott Macintyre(4)" in result["text"]
    assert "Consists of 200,000 Ordinary Shares held indirectly." in result["text"]


def test_read_find_searches_beyond_preview(monkeypatch, capsys):
    prefix = "".join(f"<p>Prefix line {number}</p>" for number in range(550))
    filing = f"<html><body>{prefix}<p>Party M is the institutional investor.</p></body></html>"
    monkeypatch.setattr(
        query_edgar,
        "_fetch_filing_document",
        lambda *_args, **_kwargs: (filing.encode(), "http"),
    )

    query_edgar.cmd_read(_read_args(lines=2, find=["Party M"], context=1))

    displayed = capsys.readouterr().out
    assert "Party M is the institutional investor." in displayed
    assert "match 'Party M'" in displayed


def test_read_find_output_bounds_minified_inline_xbrl_context(
    monkeypatch, tmp_path
):
    term = "government investigation"
    filing = (
        "<html><body><div>Heading</div><div>"
        + ("A" * 100_000)
        + term
        + ("B" * 100_000)
        + "</div></body></html>"
    )
    monkeypatch.setattr(
        query_edgar,
        "_fetch_filing_document",
        lambda *_args, **_kwargs: (filing.encode(), "http"),
    )
    output = tmp_path / "matches.json"

    query_edgar.cmd_read(
        _read_args(
            output=str(output),
            find=[term],
            context=5,
        )
    )

    result = json.loads(output.read_text())
    assert result["line_count"] == 2
    assert result["text_included"] is False
    assert "text" not in result
    assert result["matches"][0]["column"] > 100_000
    context = result["matches"][0]["context"]
    assert any(term in item["text"] for item in context)
    assert all(
        len(item["text"]) <= query_edgar.MAX_MATCH_CONTEXT_CHARS
        for item in context
    )
    assert any(item.get("truncated") for item in context)
    assert output.stat().st_size < 5_000


def test_request_declares_identity_and_decodes_gzip(monkeypatch):
    compressed = gzip.compress(b"filing content")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _Response(
            compressed,
            {"Content-Encoding": "gzip", "Content-Type": "text/html"},
        )

    monkeypatch.setattr(query_edgar, "urlopen", fake_urlopen)
    monkeypatch.setattr(query_edgar, "_last_request", 0.0)

    result = query_edgar._request(
        "https://www.sec.gov/Archives/edgar/data/1/2/filing.htm",
        accept="text/html",
        max_bytes=1024,
        raise_errors=True,
        max_attempts=1,
    )

    assert result == b"filing content"
    assert captured["request"].get_header("User-agent") == query_edgar.USER_AGENT
    assert captured["request"].get_header("Accept-encoding") == "gzip, deflate"
    assert captured["timeout"] == 30


def test_request_retries_429_with_bounded_attempts(monkeypatch):
    attempts = []
    sleeps = []

    def fake_urlopen(request, timeout):
        attempts.append(request.full_url)
        if len(attempts) == 1:
            raise HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                {"Retry-After": "0"},
                None,
            )
        return _Response(b"ok", {"Content-Type": "text/plain"})

    monkeypatch.setattr(query_edgar, "urlopen", fake_urlopen)
    monkeypatch.setattr(query_edgar.time, "sleep", sleeps.append)
    monkeypatch.setattr(query_edgar, "_last_request", 0.0)

    result = query_edgar._request(
        "https://www.sec.gov/Archives/edgar/data/1/2/filing.htm",
        accept="text/plain",
        raise_errors=True,
        max_attempts=2,
    )

    assert result == b"ok"
    assert len(attempts) == 2
    assert sleeps
    assert all(delay <= 5 for delay in sleeps)


def test_complete_submission_location_is_official_and_deterministic():
    url = "https://www.sec.gov/Archives/edgar/data/1/2/filing.htm"
    assert query_edgar._complete_submission_location(url) is None
    assert query_edgar._complete_submission_location(
        "https://www.sec.gov/Archives/edgar/data/1951089/"
        "000121390026019356/ea0272973-f3_critical.htm"
    ) == (
        "https://www.sec.gov/Archives/edgar/data/1951089/000121390026019356/"
        "0001213900-26-019356.txt",
        "ea0272973-f3_critical.htm",
    )
    assert query_edgar._complete_submission_location(
        "https://example.com/Archives/edgar/data/1951089/"
        "000121390026019356/ea0272973-f3_critical.htm"
    ) is None


def test_complete_submission_fallback_extracts_requested_document_after_403(monkeypatch):
    archive_url = (
        "https://www.sec.gov/Archives/edgar/data/1951089/"
        "000121390026019356/ea0272973-f3_critical.htm"
    )
    submission_url = (
        "https://www.sec.gov/Archives/edgar/data/1951089/000121390026019356/"
        "0001213900-26-019356.txt"
    )
    calls = []

    def fake_request(url, **_kwargs):
        calls.append(url)
        if url == archive_url:
            raise query_edgar.SecRequestError("forbidden", url=url, status=403)
        assert url == submission_url
        return b"""
            <DOCUMENT><FILENAME>other.htm\n<TEXT>wrong</TEXT></DOCUMENT>
            <DOCUMENT><FILENAME>ea0272973-f3_critical.htm\n<TEXT>
            <html><body>Malcolm Scott Macintyre</body></html>
            </TEXT></DOCUMENT>
        """

    monkeypatch.setattr(query_edgar, "_request", fake_request)

    data, retrieval = query_edgar._fetch_filing_document(archive_url)

    assert retrieval == "submission-text"
    assert b"Malcolm Scott Macintyre" in data
    assert b"wrong" not in data
    assert calls == [archive_url, submission_url]


def test_complete_submission_fallback_does_not_bypass_rate_control(monkeypatch):
    archive_url = (
        "https://www.sec.gov/Archives/edgar/data/1951089/"
        "000121390026019356/ea0272973-f3_critical.htm"
    )
    calls = []

    def rate_limited(*_args, **_kwargs):
        calls.append(True)
        raise query_edgar.SecRequestError("slow down", url=archive_url, status=429)

    monkeypatch.setattr(query_edgar, "_request", rate_limited)

    with pytest.raises(query_edgar.SecRequestError):
        query_edgar._fetch_filing_document(archive_url)
    assert calls == [True]
