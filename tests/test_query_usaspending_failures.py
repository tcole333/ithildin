"""Offline acquisition regressions: absence, failure, and incomplete coverage differ."""

import io
import json
from http.client import IncompleteRead
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from tools import query_usaspending as usa


def _args(tmp_path, **overrides):
    values = dict(
        query="Test Recipient", uei=None, agency=None, grants=False,
        agency_tier="toptier", date_range=None, naics=None, psc=None,
        limit=100, page=1, award_id=None, scope="recipient_location",
        geo_layer="state", group="fiscal_year", keyword="skip tracing",
        start="2025-01-01", end="2026-01-01", all_pages=False,
        from_file=None, output=str(tmp_path / "response.json"), json_out=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _http_sequence(monkeypatch, responses):
    pending = iter(responses)
    requests = []

    def fake_urlopen(request, **kwargs):
        requests.append((request.full_url, json.loads(kwargs["data"]) if "data" in kwargs else None))
        response = next(pending)
        if isinstance(response, Exception):
            raise response
        return io.BytesIO(response if isinstance(response, bytes) else json.dumps(response).encode())

    monkeypatch.setattr(usa, "urlopen", fake_urlopen)
    return requests


LIST_COMMANDS = [
    usa.cmd_search, usa.cmd_awards, usa.cmd_recipient, usa.cmd_loans,
    usa.cmd_subawards, usa.cmd_transactions, usa.cmd_transactions_keyword,
    usa.cmd_spending_by_geography, usa.cmd_spending_over_time,
    usa.cmd_top_recipients, usa.cmd_agencies, usa.cmd_covid,
]


@pytest.mark.parametrize("command", LIST_COMMANDS, ids=lambda fn: fn.__name__)
def test_empty_success_writes_a_query_envelope(monkeypatch, tmp_path, command):
    _http_sequence(monkeypatch, [{"results": [], "page_metadata": {"hasNext": False}}] * 4)
    args = _args(tmp_path)
    command(args)

    saved = json.loads((tmp_path / "response.json").read_text())
    assert saved["status"] == "success"
    assert saved["results"] == []
    assert saved["errors"] == []
    assert saved["query"]["command"]
    assert "output" not in saved["query"]
    assert saved["retrieval"]["requests"]
    assert all(request["status"] == "success" for request in saved["retrieval"]["requests"])


@pytest.mark.parametrize("command", LIST_COMMANDS, ids=lambda fn: fn.__name__)
def test_transport_failure_writes_error_and_exits_nonzero(monkeypatch, tmp_path, capsys, command):
    _http_sequence(monkeypatch, [URLError("offline")] * 4)
    with pytest.raises(SystemExit) as exc:
        command(_args(tmp_path))
    assert exc.value.code == 1

    saved = json.loads((tmp_path / "response.json").read_text())
    assert saved["status"] == "error"
    assert saved["results"] == []
    assert saved["retrieval"]["complete"] is False
    assert all(error["kind"] == "transport" for error in saved["errors"])
    assert all(request["status"] == "error" for request in saved["retrieval"]["requests"])
    output = capsys.readouterr()
    assert "No recipient found" not in output.out
    assert "No COVID-19 relief awards" not in output.out
    assert "results unavailable" in output.out


@pytest.mark.parametrize("response", [
    b"<html>upstream error</html>", b"\xff", None, [], {},
    {"results": None}, {"results": "unexpected"}, {"results": ["unexpected"]},
])
def test_malformed_success_is_an_acquisition_error(monkeypatch, tmp_path, response):
    _http_sequence(monkeypatch, [response])
    with pytest.raises(SystemExit, match="1"):
        usa.cmd_search(_args(tmp_path))
    saved = json.loads((tmp_path / "response.json").read_text())
    assert saved["status"] == "error"
    assert saved["errors"][0]["kind"] == "invalid_response"


@pytest.mark.parametrize("error", [TimeoutError("timed out"), IncompleteRead(b"partial", 100)])
def test_read_failures_use_the_same_error_contract(monkeypatch, tmp_path, error):
    _http_sequence(monkeypatch, [error])
    with pytest.raises(SystemExit, match="1"):
        usa.cmd_search(_args(tmp_path))
    saved = json.loads((tmp_path / "response.json").read_text())
    assert saved["errors"][0]["kind"] == "transport"


def test_recipient_retained_when_agency_spending_fails(monkeypatch, tmp_path):
    recipient = {"recipient_name": "TEST RECIPIENT", "uei": "TESTUEI"}
    requests = _http_sequence(monkeypatch, [{"results": [recipient]}, URLError("offline")])
    with pytest.raises(SystemExit, match="1"):
        usa.cmd_recipient(_args(tmp_path))

    saved = json.loads((tmp_path / "response.json").read_text())
    assert saved["status"] == "partial"
    assert saved["recipient"] == recipient
    assert saved["results"] == [recipient]
    assert saved["spending_by_agency"] is None  # Unknown, not a zero-spending result.
    assert saved["errors"][0]["endpoint"].endswith("awarding_agency/")
    assert requests[1][1]["filters"]["recipient_search_text"] == ["TESTUEI"]


def test_covid_keeps_other_groups_when_one_fails(monkeypatch, tmp_path):
    row = {"Award ID": "VALID"}
    _http_sequence(monkeypatch, [
        URLError("contracts unavailable"),
        {"results": [row], "page_metadata": {"hasNext": False}},
        {"results": [], "page_metadata": {"hasNext": False}},
        {"results": [], "page_metadata": {"hasNext": False}},
    ])
    with pytest.raises(SystemExit, match="1"):
        usa.cmd_covid(_args(tmp_path))
    saved = json.loads((tmp_path / "response.json").read_text())
    assert saved["status"] == "partial"
    assert saved["results"] == [row]
    assert len(saved["retrieval"]["requests"]) == 4
    assert len(saved["errors"]) == 1


def test_keyword_later_failure_keeps_rows_and_retry_page(monkeypatch, tmp_path):
    row = {"Award ID": "FIRST", "Mod": "P00001"}
    requests = _http_sequence(monkeypatch, [
        {"results": [row], "page_metadata": {"hasNext": True, "next": 2}},
        URLError("second page unavailable"),
    ])
    with pytest.raises(SystemExit, match="1"):
        usa.cmd_transactions_keyword(_args(tmp_path, all_pages=True))
    saved = json.loads((tmp_path / "response.json").read_text())
    assert saved["status"] == "partial"
    assert saved["results"] == [row]
    assert saved["retrieval"]["complete"] is False
    assert saved["pagination"]["next_page"] == 2
    assert saved["pagination"]["pages_retrieved"] == 1
    assert saved["pagination"]["has_next"] is True
    assert saved["pagination"]["stopped_reason"] == "acquisition_error"
    assert [payload["page"] for _, payload in requests] == [1, 2]


def test_keyword_safety_cap_reports_continuation_without_acquisition_error(monkeypatch, tmp_path):
    requests = _http_sequence(monkeypatch, [
        {"results": [{"Award ID": f"PAGE-{page}"}],
         "page_metadata": {"hasNext": True, "next": page + 1}}
        for page in range(1, 51)
    ])
    usa.cmd_transactions_keyword(_args(tmp_path, all_pages=True))
    saved = json.loads((tmp_path / "response.json").read_text())
    assert saved["status"] == "partial"
    assert saved["errors"] == []
    assert len(saved["results"]) == len(requests) == 50
    assert saved["pagination"]["next_page"] == 51
    assert saved["pagination"]["has_next"] is True
    assert saved["pagination"]["stopped_reason"] == "page_cap"
    assert saved["retrieval"]["complete"] is False


def test_keyword_can_resume_at_continuation_page(monkeypatch, tmp_path):
    requests = _http_sequence(monkeypatch, [{"results": [], "page_metadata": {"hasNext": False}}])
    usa.cmd_transactions_keyword(_args(tmp_path, page=51, all_pages=True))
    saved = json.loads((tmp_path / "response.json").read_text())
    assert requests[0][1]["page"] == 51
    assert saved["status"] == "success"
    assert saved["pagination"]["next_page"] is None
    assert saved["pagination"]["requested_page"] == 51
    assert saved["retrieval"]["complete"] is False  # Earlier pages are absent.


def test_keyword_from_file_failure_is_not_silently_successful(tmp_path):
    with pytest.raises(SystemExit, match="1"):
        usa.cmd_transactions_keyword(_args(tmp_path, from_file=str(tmp_path / "absent.json")))
    saved = json.loads((tmp_path / "response.json").read_text())
    assert saved["status"] == "error"
    assert saved["errors"][0]["kind"] == "invalid_file"


def test_saved_partial_failure_cannot_be_reclassified_as_success(tmp_path):
    fixture = tmp_path / "partial.json"
    row = {"Award ID": "FIRST"}
    fixture.write_text(json.dumps({
        "status": "partial", "results": [row],
        "errors": [{"kind": "transport", "message": "offline"}],
        "pagination": {"has_next": True, "next_page": 2},
    }))
    with pytest.raises(SystemExit, match="1"):
        usa.cmd_transactions_keyword(_args(tmp_path, from_file=str(fixture)))
    saved = json.loads((tmp_path / "response.json").read_text())
    assert saved["status"] == "partial"
    assert saved["results"] == [row]
    assert saved["pagination"]["next_page"] == 2
    assert saved["errors"][0]["kind"] == "saved_acquisition_error"


def test_invalid_text_encoding_in_saved_response_writes_error(tmp_path):
    fixture = tmp_path / "invalid.json"
    fixture.write_bytes(b"\xff")
    with pytest.raises(SystemExit, match="1"):
        usa.cmd_transactions_keyword(_args(tmp_path, from_file=str(fixture)))
    saved = json.loads((tmp_path / "response.json").read_text())
    assert saved["status"] == "error"
    assert saved["errors"][0]["kind"] == "invalid_file"


def test_paginated_results_do_not_claim_complete_coverage_without_metadata(monkeypatch, tmp_path):
    _http_sequence(monkeypatch, [{"results": [{"Award ID": "FIRST"}]}])
    usa.cmd_awards(_args(tmp_path))
    saved = json.loads((tmp_path / "response.json").read_text())
    assert saved["status"] == "success"
    assert saved["retrieval"]["complete"] is None


def test_error_json_stdout_remains_machine_readable(monkeypatch, tmp_path, capsys):
    _http_sequence(monkeypatch, [URLError("offline")])
    with pytest.raises(SystemExit, match="1"):
        usa.cmd_search(_args(tmp_path, output=None, json_out=True))
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "error"
    assert "offline" in captured.err


def test_error_state_does_not_leak_between_commands(monkeypatch, tmp_path):
    _http_sequence(monkeypatch, [URLError("offline"), {"results": []}])
    with pytest.raises(SystemExit, match="1"):
        usa.cmd_search(_args(tmp_path))
    usa.cmd_search(_args(tmp_path))
    saved = json.loads((tmp_path / "response.json").read_text())
    assert saved["status"] == "success"
    assert saved["errors"] == []


def test_cli_from_file_failure_writes_envelope_and_exits_one(run_python_script, tmp_path):
    output = tmp_path / "result.json"
    completed = run_python_script(
        "tools/query_usaspending.py", "transactions-keyword", "test",
        "--from-file", str(tmp_path / "missing.json"), "--output", str(output),
    )
    assert completed.returncode == 1
    assert json.loads(output.read_text())["status"] == "error"


def test_cli_rejects_nonpositive_resume_page(run_python_script):
    completed = run_python_script(
        "tools/query_usaspending.py", "transactions-keyword", "test", "--page", "0",
    )
    assert completed.returncode == 2
    assert "page must be a positive integer" in completed.stderr
