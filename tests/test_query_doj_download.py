from __future__ import annotations

from io import BytesIO

import pytest

from tools import query_doj


class _Response:
    def __init__(self, body, content_type):
        self._body = BytesIO(body)
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        return self._body.read(size)


def test_download_epstein_pdf_sets_age_cookie_and_validates_pdf(tmp_path):
    captured = {}

    def opener(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _Response(b"%PDF-1.7\npublic record", "application/pdf")

    output = tmp_path / "EFTA00634292.pdf"
    result = query_doj.download_epstein_pdf(
        "https://www.justice.gov/epstein/files/DataSet%209/EFTA00634292.pdf",
        output,
        opener=opener,
    )

    assert output.read_bytes() == b"%PDF-1.7\npublic record"
    assert captured["request"].get_header("Cookie") == (
        "justiceGovAgeVerified=true"
    )
    assert captured["request"].get_header("Accept") == "application/pdf"
    assert captured["timeout"] == 60
    assert result["bytes"] == len(output.read_bytes())
    assert len(result["sha256"]) == 64
    assert result["source_url"] == (
        "https://www.justice.gov/epstein/files/DataSet%209/EFTA00634292.pdf"
    )


def test_download_epstein_pdf_rejects_age_gate_html_without_output(tmp_path):
    output = tmp_path / "not-a-pdf.pdf"

    with pytest.raises(ValueError, match="non-PDF response"):
        query_doj.download_epstein_pdf(
            "https://www.justice.gov/epstein/files/DataSet%209/EFTA00634292.pdf",
            output,
            opener=lambda *_args, **_kwargs: _Response(
                b"<html>age verification</html>",
                "text/html; charset=UTF-8",
            ),
        )

    assert not output.exists()


@pytest.mark.parametrize(
    "url",
    [
        "http://www.justice.gov/epstein/files/DataSet%209/EFTA00634292.pdf",
        "https://example.com/epstein/files/DataSet%209/EFTA00634292.pdf",
        "https://www.justice.gov/other/file.pdf",
    ],
)
def test_download_epstein_pdf_rejects_unofficial_urls(tmp_path, url):
    with pytest.raises(ValueError, match="official HTTPS"):
        query_doj.download_epstein_pdf(url, tmp_path / "record.pdf")


def test_download_epstein_pdf_accepts_legacy_indexed_court_path(tmp_path):
    output = tmp_path / "061.pdf"
    legacy_url = (
        "https://www.justice.gov/multimedia/Court%20Records/"
        "United%20States%20v.%20Epstein%2C%20No.%20119-cr-00490%20"
        "%28S.D.N.Y.%202019%29/061.pdf"
    )

    result = query_doj.download_epstein_pdf(
        legacy_url,
        output,
        opener=lambda *_args, **_kwargs: _Response(
            b"%PDF-1.7\nlegacy indexed record",
            "application/pdf",
        ),
    )

    assert result["source_url"] == legacy_url
    assert output.read_bytes().startswith(b"%PDF-")


def test_download_epstein_pdf_honors_only_caller_selected_size_bound(tmp_path):
    output = tmp_path / "bounded.pdf"

    with pytest.raises(ValueError, match="caller-selected"):
        query_doj.download_epstein_pdf(
            "https://www.justice.gov/epstein/files/DataSet%209/EFTA00634292.pdf",
            output,
            max_bytes=8,
            opener=lambda *_args, **_kwargs: _Response(
                b"%PDF-1.7\nmore than eight bytes",
                "application/pdf",
            ),
        )

    assert not output.exists()
