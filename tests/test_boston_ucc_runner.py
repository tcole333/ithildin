from pathlib import Path
import hashlib
import json

import pytest

from tools.boston_license_review import load, save
from tools.boston_ucc_runner import run, search_key, sync_event_log
from tools.query_massachusetts_ucc import PortalError


def queue_file(tmp_path):
    from tests.test_boston_license_review import make_queue

    queue = make_queue(tmp_path)[2]
    path = tmp_path / "queue.json"
    save(path, queue)
    return path


def empty(payload):
    return {"query": payload, "scope": "lapsed" if payload["lapsed"] else "current",
            "reported_count": 0, "returned": 0, "results": [], "truncated": False,
            "source_url": "https://corp.sec.state.ma.us/corpweb/UCCSearch/UCCSearch.aspx",
            "retrieved_at": "2026-09-03T00:00:00Z"}


def test_identical_query_reuses_capture_and_resume_skips_completed(tmp_path):
    path = queue_file(tmp_path)
    calls = []
    def execute(payload):
        calls.append(payload)
        return empty(payload)
    first = run(path, tmp_path / "results", "current", executor=execute, searched=lambda *_: None)
    assert first["processed_this_run"] == 2
    assert first["network_calls"] == len(calls) == 1
    assert first["cached_results"] == 1
    assert all(h["searches"]["lapsed"]["state"] == "pending" for h in load(path)["holders"])
    second = run(path, tmp_path / "results", "current", executor=execute, searched=lambda *_: None)
    assert second["network_calls"] == 0


def test_challenge_stops_immediately_without_false_empty(tmp_path):
    path = queue_file(tmp_path)
    calls = []
    def fail(payload):
        calls.append(payload)
        raise PortalError("access challenge")
    result = run(path, tmp_path / "results", "current", executor=fail, searched=lambda *_: None)
    assert result["outcome"] == "stopped_on_error"
    assert len(calls) == 1
    assert [h["searches"]["current"]["state"] for h in load(path)["holders"]] == ["blocked", "pending"]
    assert not list((tmp_path / "results/results").glob("*.json"))


def test_truncated_result_stays_partial(tmp_path):
    path = queue_file(tmp_path)
    def partial(payload):
        return {**empty(payload), "reported_count": 10, "returned": 1,
                "results": [{"original_filing_number": "123456789012"}], "truncated": True}
    result = run(path, tmp_path / "results", "current", max_queries=1,
                 executor=partial, searched=lambda *_: {"result_count": 10})
    # The network budget does not prevent reusing this same-query partial cache.
    assert result["coverage"]["search_states"]["current"]["partial"] == 2
    assert result["coverage"]["search_states"]["current"].get("complete", 0) == 0
    assert Path(load(path)["holders"][0]["searches"]["current"]["attempts"][0]["source_file"]).exists()


def test_event_log_sync_idempotent_and_preserves_archive_scope(tmp_path):
    from tests.test_boston_license_review import event, make_queue

    queue = make_queue(tmp_path)[2]
    item = event(queue, scope="lapsed")
    item["query"]["command"] = "search-org"
    events = tmp_path / "events.json"
    save(events, [item])
    calls = []
    checkpoint = tmp_path / "logged.json"
    result = sync_event_log(events, checkpoint, logger=lambda *args: calls.append(args))
    assert result["new_events_logged"] == 1
    assert '"lapsed":true' in calls[0][0]
    assert calls[0][2] == 0
    assert sync_event_log(events, checkpoint, logger=lambda *args: calls.append(args))["new_events_logged"] == 0
    assert len(calls) == 1


@pytest.mark.parametrize("input_flag", [True, False])
def test_name_mode_flags_defer_without_browser_or_blocking(tmp_path, input_flag):
    path = queue_file(tmp_path)
    queue = load(path)
    for holder in queue["holders"]:
        holder["query_input_requires_review"] = input_flag
        holder["name_mode_review_reasons"] = ["personal name requires review"]
    save(path, queue)
    result = run(path, tmp_path / "out", "current",
                 executor=lambda _: pytest.fail("Flagged names must not query"), searched=lambda *_: None)
    assert result["network_calls"] == 0
    assert result["deferred_name_reviews"] == 2
    assert result["coverage"]["search_states"]["current"] == {"pending": 2}
    assert result["outcome"] == "organization_queue_exhausted_with_name_review"
    assert all(item["state"] == "needs_review" for item in load(tmp_path / "out/needs-review.json"))


def test_saved_cua_event_import_skips_completed_holder(tmp_path):
    from tests.test_boston_license_review import event
    path = queue_file(tmp_path)
    saved = event(load(path))
    events_path = tmp_path / "ucc-cua/events.jsonl"
    events_path.parent.mkdir()
    events_path.write_text(json.dumps(saved) + "\n")
    calls = []
    result = run(path, tmp_path / "out", "current",
                 executor=lambda payload: calls.append(payload) or empty(payload), searched=lambda *_: None)
    assert result["processed_this_run"] == 1
    assert len(calls) == 1
    assert result["coverage"]["search_states"]["current"] == {"complete": 2}


def test_raw_checkpoint_recovers_without_query_or_chrome(tmp_path, monkeypatch):
    from tools import query_massachusetts_ucc as ucc
    monkeypatch.setattr(ucc, "log_search", lambda *_: None)
    path = queue_file(tmp_path)
    payload = {**load(path)["holders"][0]["query_proposal"], "lapsed": False}
    raw_path = tmp_path / "out/raw" / (hashlib.sha256(search_key(payload).encode()).hexdigest() + ".json")
    raw = {"ok": True, "submitted": payload, "captured_at": "2026-09-03T00:00:00Z",
           "pages": [{"url": "https://corp.sec.state.ma.us/CorpWeb/UCCSearch/UCCSearchResults.aspx",
                      "html": (Path(__file__).parent / "fixtures/massachusetts_ucc/empty.html").read_text()}]}
    ucc.save_transport(raw_path, payload, raw)
    result = run(path, tmp_path / "out", "current", searched=lambda *_: None,
                 executor=lambda _: pytest.fail("Checkpoint recovery must not query"))
    assert result["network_calls"] == result["browser_sessions_started"] == 0
    assert result["cached_results"] == 2
    assert result["coverage"]["search_states"]["current"] == {"complete": 2}


def test_event_checkpoint_survives_queue_save_failure(tmp_path, monkeypatch):
    from tools import boston_ucc_runner as runner
    path = queue_file(tmp_path)
    real_save = runner.save
    queue_saves = 0
    def interrupted_save(target, value):
        nonlocal queue_saves
        if target == path:
            queue_saves += 1
            if queue_saves == 2:
                raise OSError("Simulated interruption after durable event")
        real_save(target, value)
    monkeypatch.setattr(runner, "save", interrupted_save)
    with pytest.raises(OSError, match="interruption"):
        run(path, tmp_path / "out", "current", executor=empty, searched=lambda *_: None)
    assert (tmp_path / "out/events.jsonl").exists()
    monkeypatch.setattr(runner, "save", real_save)
    result = run(path, tmp_path / "out", "current", searched=lambda *_: None,
                 executor=lambda _: pytest.fail("Saved event and result must recover without query"))
    assert result["network_calls"] == 0
    assert result["coverage"]["search_states"]["current"] == {"complete": 2}


def test_interrupted_event_write_preserves_readable_previous_journal(tmp_path, monkeypatch):
    from tools import boston_ucc_runner as runner
    journal = tmp_path / "events.jsonl"
    runner.append_event(journal, {"sequence": 1})
    previous = journal.read_bytes()
    with monkeypatch.context() as patch:
        def interrupted_flush(_):
            raise OSError("Simulated disk failure before atomic checkpoint replacement")
        patch.setattr(runner.os, "fsync", interrupted_flush)
        with pytest.raises(OSError, match="disk failure"):
            runner.append_event(journal, {"sequence": 2})
    assert journal.read_bytes() == previous
    assert runner.load_events(journal) == [{"sequence": 1}]
    runner.append_event(journal, {"sequence": 2})
    assert runner.load_events(journal) == [{"sequence": 1}, {"sequence": 2}]
