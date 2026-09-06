"""Offline award identity and coverage tests use the existing transaction schema."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import query_usaspending as usa


def _args(tmp_path, **overrides):
    values = dict(query="Fixture recipient", uei=None, agency=None, date_range=None,
                  grants=False, page=1, limit=100, all_pages=True, max_pages=50,
                  award_id="CONT_AWD_FIRST_001_-NONE-_-NONE-",
                  output=str(tmp_path / "results.json"), json_out=False)
    return SimpleNamespace(**(values | overrides))


def _row(award_id, *, date="2020-01-01", amount=100):
    return {"Award ID": "SAME-PIID", "generated_internal_id": award_id,
            "Recipient Name": "Fixture recipient", "Action Date": date,
            "Transaction Amount": amount, "Mod": date}


def _responses(monkeypatch, pages):
    calls = []

    def fetch(endpoint, payload):
        calls.append((endpoint, payload))
        response = pages.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(usa, "_fetch_post", fetch)
    return calls


def test_selected_award_collects_every_page_and_excludes_other_awards(monkeypatch, tmp_path):
    args = _args(tmp_path)
    first = _row(args.award_id)
    last = _row(args.award_id, date="2020-03-01", amount=-10)
    calls = _responses(monkeypatch, [
        {"results": [_row("CONT_AWD_OTHER"), first],
         "page_metadata": {"hasNext": True, "next": 2}},
        {"results": [last], "page_metadata": {"hasNext": False}},
    ])
    usa.cmd_transactions(args)
    saved = json.loads(Path(args.output).read_text())
    assert saved["results"] == [first, last]
    assert saved["award_selection"]["excluded_count"] == 1
    assert saved["retrieval"]["complete"] is True
    assert saved["pagination"]["pages_retrieved"] == 2
    assert [payload["page"] for _, payload in calls] == [1, 2]
    assert all(endpoint == "/search/spending_by_transaction/" for endpoint, _ in calls)
    assert all("award_ids" not in payload["filters"] for _, payload in calls)
    assert "not evidence of cash payment" in saved["query"]["amount_semantics"]


@pytest.mark.parametrize("metadata,reason", [
    ({"hasNext": True, "next": 2}, "page_cap"), ({}, "pagination_unknown"),
])
def test_capped_or_unknown_pagination_is_partial(monkeypatch, tmp_path, metadata, reason):
    args = _args(tmp_path, max_pages=1)
    _responses(monkeypatch, [{"results": [_row(args.award_id)], "page_metadata": metadata}])
    usa.cmd_transactions(args)
    saved = json.loads(Path(args.output).read_text())
    assert saved["status"] == "partial"
    assert saved["retrieval"]["complete"] is False
    assert saved["pagination"]["stopped_reason"] == reason


def test_resumed_pages_do_not_claim_whole_search_complete(monkeypatch, tmp_path):
    args = _args(tmp_path, page=2)
    _responses(monkeypatch, [{"results": [], "page_metadata": {"hasNext": False}}])
    usa.cmd_transactions(args)
    saved = json.loads(Path(args.output).read_text())
    assert saved["pagination"]["requested_page"] == 2
    assert saved["retrieval"]["complete"] is False


@pytest.mark.parametrize("failure", [
    usa.AcquisitionError("transport", "offline"),
    {"results": [{"Award ID": "SAME-PIID"}], "page_metadata": {"hasNext": False}},
    {"results": [], "page_metadata": {"hasNext": True, "next": 2}},
])
def test_failures_preserve_matches_without_claiming_complete(monkeypatch, tmp_path, failure):
    args = _args(tmp_path)
    row = _row(args.award_id)
    _responses(monkeypatch, [
        {"results": [row], "page_metadata": {"hasNext": True, "next": 2}}, failure,
    ])
    with pytest.raises(SystemExit) as exc:
        usa.cmd_transactions(args)
    assert exc.value.code == 1
    saved = json.loads(Path(args.output).read_text())
    assert saved["results"] == [row]
    assert saved["status"] == "partial"
    assert saved["retrieval"]["complete"] is False
    assert saved["errors"]


def test_real_saved_schema_supports_exact_canonical_identity(monkeypatch, tmp_path):
    fixture = json.loads((Path(__file__).parent / "fixtures/usaspending_txn_skiptracing.json").read_text())
    selected = fixture["results"][0]["generated_internal_id"]
    args = _args(tmp_path, award_id=selected)
    _responses(monkeypatch, [fixture])
    usa.cmd_transactions(args)
    saved = json.loads(Path(args.output).read_text())
    assert len(saved["results"]) > 1
    assert all(row["generated_internal_id"] == selected for row in saved["results"])
    assert saved["messages"] == fixture["messages"]


def test_selection_requires_canonical_id_and_recipient_before_fetch(monkeypatch, tmp_path):
    def no_fetch(*_args):
        pytest.fail("invalid scope must fail before any network request")
    monkeypatch.setattr(usa, "_fetch_post", no_fetch)
    for overrides in ({"award_id": "PLAIN-PIID"}, {"query": None},
                      {"date_range": "2020-01-01"},
                      {"date_range": "2021-01-01,2020-01-01"}):
        with pytest.raises(SystemExit):
            usa.cmd_transactions(_args(tmp_path, **overrides))


def test_subaward_pagination_keeps_prior_valid_pages_on_scope_failure(monkeypatch, tmp_path):
    args = _args(tmp_path, query=None, award_id="PRIME-1")
    row = {"Sub-Award ID": "SUB-1", "Prime Award ID": "PRIME-1"}
    _responses(monkeypatch, [
        {"results": [row], "page_metadata": {"hasNext": True}},
        {"results": [{"Prime Award ID": "WRONG"}], "page_metadata": {"hasNext": False}},
    ])
    with pytest.raises(SystemExit):
        usa.cmd_subawards(args)
    saved = json.loads(Path(args.output).read_text())
    assert saved["results"] == [row]
    assert saved["status"] == "partial"
    assert saved["pagination"]["next_page"] == 2


def test_cli_pagination_and_award_selection_match_documented_route(monkeypatch, tmp_path):
    output = tmp_path / "cli.json"
    _responses(monkeypatch, [{"results": [], "page_metadata": {"hasNext": False}}])
    monkeypatch.setattr(sys, "argv", ["query_usaspending.py", "transactions", "--uei", "FIXTURE",
                        "--award-id", "CONT_AWD_FIXTURE", "--all-pages", "--max-pages", "2",
                        "--output", str(output)])
    usa.main()
    saved = json.loads(output.read_text())
    assert saved["retrieval"]["complete"] is True
    assert saved["query"]["max_pages"] == 2
    assert saved["award_selection"]["award_id"] == "CONT_AWD_FIXTURE"


@pytest.mark.parametrize("option", ["--page", "--max-pages"])
def test_cli_rejects_nonpositive_page_controls(monkeypatch, option):
    monkeypatch.setattr(sys, "argv", ["query_usaspending.py", "transactions", option, "0"])
    with pytest.raises(SystemExit) as exc:
        usa.main()
    assert exc.value.code == 2
