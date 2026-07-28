"""Regression tests for OpenCorporates credential diagnostics."""

from __future__ import annotations

import requests
import pytest

from tools import query_delaware, query_opencorporates


class _UnauthorizedResponse:
    status_code = 401

    def raise_for_status(self):
        raise requests.HTTPError(response=self)


@pytest.mark.parametrize("module", [query_opencorporates, query_delaware])
def test_rejected_token_has_actionable_redacted_diagnostic(
    module, monkeypatch, capsys
):
    secret = "configured-but-rejected-token"
    monkeypatch.setenv("OPENCORPORATES_API_KEY", secret)
    monkeypatch.setattr(module.time, "sleep", lambda _delay: None)
    monkeypatch.setattr(
        module.requests,
        "get",
        lambda *_args, **_kwargs: _UnauthorizedResponse(),
    )

    with pytest.raises(SystemExit) as exc:
        module.api_request("account_status")

    assert exc.value.code == 1
    stderr = capsys.readouterr().err
    assert "rejected OPENCORPORATES_API_KEY (HTTP 401)" in stderr
    assert "replace or remove the stale token" in stderr.lower()
    assert "query_opencorporates.py account-status" in stderr
    assert secret not in stderr


def test_transport_error_does_not_render_token_bearing_url(
    monkeypatch, capsys
):
    secret = "never-print-this-token"
    monkeypatch.setenv("OPENCORPORATES_API_KEY", secret)
    monkeypatch.setattr(query_opencorporates.time, "sleep", lambda _delay: None)

    def fail_request(*_args, **_kwargs):
        raise requests.ConnectionError(
            "failed URL https://api.opencorporates.test/?api_token="
            f"{secret}"
        )

    monkeypatch.setattr(query_opencorporates.requests, "get", fail_request)

    with pytest.raises(SystemExit) as exc:
        query_opencorporates.api_request("account_status")

    assert exc.value.code == 1
    stderr = capsys.readouterr().err
    assert "ConnectionError" in stderr
    assert "intentionally redacted" in stderr
    assert secret not in stderr
