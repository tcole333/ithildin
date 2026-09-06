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

    assert logged == [(query_fec.canonical_search_key(
        "donor", "Example Donor", filters={
            "contributor_name": "Example Donor", "sort": "-contribution_receipt_date",
        }, limit=100,
    ), "fec", 1)]
    assert (tmp_path / "fec.json").exists()


def test_scoped_keys_distinguish_fec_operation_cycle_and_filters(monkeypatch):
    logged = []
    monkeypatch.setattr(query_fec, "_fetch", lambda *a, **k: ([], {"count": 0}))
    monkeypatch.setattr(query_fec, "_log", lambda key, *args: logged.append(key))
    monkeypatch.setattr(query_fec, "write_output", lambda *a, **k: True)
    args = SimpleNamespace(
        query="Example", employer=None, min_amount=None, max_amount=None,
        cycle=2022, state=None, limit=100,
    )
    query_fec.cmd_donor(args)
    args.cycle = 2024
    query_fec.cmd_donor(args)
    args.employer = 'Other Employer'
    query_fec.cmd_donor(args)
    query_fec.cmd_employer(args)
    assert len(set(logged)) == 4
    assert json.loads(logged[0])["filters"]["two_year_transaction_period"] == 2022
    assert json.loads(logged[1])["filters"]["two_year_transaction_period"] == 2024
    assert json.loads(logged[2])["filters"]["contributor_employer"] == 'Other Employer'
    assert json.loads(logged[3])["mode"] == 'employer'


def test_fec_scope_snapshot_excludes_request_credentials_and_cursor(monkeypatch):
    logged = []
    pages = []

    def fetch(endpoint, params, max_pages):
        pages.append(max_pages)
        params.update(api_key='never-log-this', last_index=123)
        return [{'sub_id': '1'}], {'count': 500}

    monkeypatch.setattr(query_fec, '_fetch', fetch)
    monkeypatch.setattr(query_fec, '_log', lambda *args: logged.append(args))
    query_fec._fetch_logged('donor', 'Example', '/test', {'contributor_name': 'Example'}, 100)
    assert pages == [1]
    assert 'never-log-this' not in logged[0][0]
    assert 'last_index' not in logged[0][0]
    assert logged[0][2] == 1


def test_timeout_writes_audit_artifact_and_exits_nonzero(monkeypatch, tmp_path, capsys):
    output = tmp_path / "fec-timeout.json"
    logged = []

    monkeypatch.setenv("FEC_API_KEY", "test-secret-key")
    monkeypatch.setattr(
        query_fec,
        "urlopen",
        lambda request, timeout: (_ for _ in ()).throw(TimeoutError("timed out")),
    )
    monkeypatch.setattr(query_fec.time, "sleep", lambda _delay: None)
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
    monkeypatch.setattr(query_fec.time, "sleep", lambda _delay: None)

    with pytest.raises(query_fec.FECRequestError) as exc_info:
        query_fec._fetch("/schedules/schedule_a/", {"contributor_name": "Example"})

    assert exc_info.value.kind == "http_error"
    assert exc_info.value.http_status == 504
    assert str(exc_info.value) == "FEC API returned HTTP 504"


def test_transient_http_failure_is_retried(monkeypatch):
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"results": [{"sub_id": "1"}], "pagination": {}}'

    def fake_open(request, timeout):
        calls.append((request.full_url, timeout))
        if len(calls) == 1:
            raise HTTPError(
                request.full_url,
                502,
                "Bad Gateway",
                {"Retry-After": "0"},
                io.BytesIO(),
            )
        return Response()

    monkeypatch.setattr(query_fec, "urlopen", fake_open)
    monkeypatch.setattr(query_fec.time, "sleep", lambda _delay: None)

    results, _pagination = query_fec._fetch(
        "/schedules/schedule_b/", {"committee_id": "C00811166"}
    )

    assert results == [{"sub_id": "1"}]
    assert len(calls) == 2
