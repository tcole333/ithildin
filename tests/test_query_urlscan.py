"""Regression tests for URLScan access diagnostics."""

from io import BytesIO
from urllib.error import HTTPError

import pytest

from tools import query_urlscan


def test_result_403_explains_public_search_access_mismatch(monkeypatch, capsys):
    def deny_result(request, timeout):
        raise HTTPError(
            request.full_url,
            403,
            "Forbidden",
            {},
            BytesIO(b'{"message":"You are not logged in."}'),
        )

    monkeypatch.setattr(query_urlscan, "urlopen", deny_result)

    with pytest.raises(SystemExit, match="1"):
        query_urlscan._fetch(
            "https://urlscan.io/api/v1/result/test-uuid/",
            timeout=60,
        )

    error = capsys.readouterr().err
    assert "public search" in error
    assert "logged-in account or URLSCAN_API_KEY" in error
