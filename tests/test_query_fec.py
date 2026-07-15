import io
import json
import sys
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from tools import query_fec


def test_committee_lookup_uses_singular_fec_endpoint(monkeypatch, capsys):
    seen = {}

    def fake_fetch(endpoint, params):
        seen["endpoint"] = endpoint
        return ([{"committee_id": "C00825851", "name": "MAGA INC."}], {})

    monkeypatch.setattr(query_fec, "_fetch", fake_fetch)
    args = SimpleNamespace(
        committee_id="C00825851",
        output=None,
        json_out=False,
    )

    query_fec.cmd_committee(args)

    assert seen["endpoint"] == "/committee/C00825851/"
    assert "MAGA INC." in capsys.readouterr().out


def test_donor_output_still_logs_search(monkeypatch, tmp_path):
    logged = []

    monkeypatch.setattr(
        query_fec,
        "_fetch",
        lambda endpoint, params, max_pages: ([{"sub_id": "1"}], {"count": 7}),
    )
    monkeypatch.setattr(query_fec, "_log", lambda query, source, count: logged.append((query, source, count)))
    args = SimpleNamespace(
        query="Example Donor",
        employer=None,
        min_amount=None,
        max_amount=None,
        cycle=None,
        state=None,
        limit=100,
        output=str(tmp_path / "fec.json"),
        json_out=False,
    )

    query_fec.cmd_donor(args)

    assert logged == [("Example Donor", "fec", 7)]
    assert (tmp_path / "fec.json").exists()


def test_timeout_writes_audit_artifact_and_exits_nonzero(monkeypatch, tmp_path, capsys):
    output = tmp_path / "fec-timeout.json"
    logged = []

    monkeypatch.setenv("FEC_API_KEY", "test-secret-key")
    monkeypatch.setattr(
        query_fec,
        "urlopen",
        lambda request, timeout: (_ for _ in ()).throw(TimeoutError("timed out")),
    )
    monkeypatch.setattr(query_fec, "_log", lambda *args: logged.append(args))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_fec.py",
            "donor",
            "Example Donor",
            "--state",
            "NY",
            "--output",
            str(output),
        ],
    )

    assert query_fec.main() == 1

    payload = json.loads(output.read_text())
    assert payload == {
        "status": "error",
        "source": "fec",
        "error": "FEC API request timed out after 60 seconds",
        "error_type": "timeout",
        "results": [],
    }
    captured = capsys.readouterr()
    assert "ERROR: FEC API request timed out after 60 seconds" in captured.err
    assert "test-secret-key" not in captured.err
    assert logged == []


def test_http_failure_is_not_converted_to_zero_results(monkeypatch):
    error = HTTPError(
        "https://api.open.fec.gov/v1/example",
        504,
        "Gateway Timeout",
        {},
        io.BytesIO(b'{"message": "upstream timeout"}'),
    )
    monkeypatch.setenv("FEC_API_KEY", "test-secret-key")
    monkeypatch.setattr(
        query_fec,
        "urlopen",
        lambda request, timeout: (_ for _ in ()).throw(error),
    )

    with pytest.raises(query_fec.FECRequestError) as exc_info:
        query_fec._fetch("/schedules/schedule_a/", {"contributor_name": "Example"})

    assert exc_info.value.kind == "http_error"
    assert exc_info.value.http_status == 504
    assert str(exc_info.value) == "FEC API returned HTTP 504"
