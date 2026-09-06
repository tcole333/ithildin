"""Boundary regressions for reviewed imports and supervised collection workers."""
import json
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

from queue_system.queue import JobQueue
from queue_system.worker import (
    AgentWorker,
    DeepPersonWorker,
    ExecutionContext,
    LeadTriageWorker,
    _execution_context,
    _run_process,
)
from scripts import dispatcher
from tools.lead_tracker import _ensure_schema

PROFILE = "feeding-our-future"
REF = "https://example.org/records/fixture"


@pytest.fixture
def store(tmp_path):
    db = sqlite3.connect(tmp_path / "test.db")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    _ensure_schema(db)
    dispatcher.ensure_dispatch_table(db)
    yield db
    db.close()


def candidate(**overrides):
    return {
        "target_name": "Review Fixture Entity", "summary": "Fixture inference",
        "finding_type": "financial", "claim_type": "inference", "confidence": "confirmed",
        "source_datasets": ["official_website"], "evidence_ids": [REF],
        "source_quotes": {REF: {"quote": "An exact fixture quotation", "page": "1"}},
        "date_of_event": "2025", **overrides,
    }


def staged_run(db, tmp_path, records=None, disposition="keep_open", status="completed", lead_id=None):
    root = tmp_path / f"bundle-{time.monotonic_ns()}"
    root.mkdir()
    (root / "report.md").write_text("# Fixture investigation report\n")
    records = [candidate()] if records is None else records
    (root / "run.json").write_text(json.dumps({
        "summary": "Fixture outcome", "status": status, "sources_checked": ["official_website"],
        "counts": {"findings": len(records), "leads": 0, "entities": 0}, "notes": [],
        "lead_disposition": disposition,
    }))
    (root / "candidate_findings.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records))
    (root / "candidate_leads.jsonl").write_text("")
    (root / "candidate_entities.jsonl").write_text("")
    cursor = db.execute(
        """INSERT INTO dispatch_runs (run_type,status,review_required,staging_dir,expected_artifacts,task_contract_json,lead_id)
           VALUES ('trace_entity','completed',1,?,?,?,?)""",
        (str(root), json.dumps(dispatcher.REQUIRED_ARTIFACTS), json.dumps({"profile_id": PROFILE}), lead_id),
    )
    db.commit()
    return cursor.lastrowid, root


def approve(db, run_id):
    dispatcher.approve_staged_run(db, run_id, {}, "fixture-reviewer")


def test_canonical_evidence_roundtrip_and_idempotent_replay(store, tmp_path):
    run_id, _ = staged_run(store, tmp_path)
    approve(store, run_id)
    counts = dispatcher.import_staged_run(store, run_id, {}, "fixture")
    assert counts["findings"] == 1
    row = store.execute("SELECT * FROM findings").fetchone()
    assert row["confidence"] == "medium"
    assert row["confidence_requested"] == "confirmed"
    assert json.loads(row["source_datasets"]) == ["official_website"]
    assert row["event_date_iso"] == "2025-01-01"
    assert row["date_precision"] == "year"
    evidence = store.execute("SELECT * FROM finding_evidence").fetchone()
    assert evidence["evidence_ref"] == REF
    assert evidence["source_quote"] == "An exact fixture quotation"
    assert store.execute("SELECT COUNT(*) FROM finding_entities").fetchone()[0] == 1
    assert dispatcher.import_staged_run(store, run_id, {}, "retry") == counts
    assert store.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 1


@pytest.mark.parametrize("artifact", dispatcher.REQUIRED_ARTIFACTS)
def test_missing_required_artifact_cannot_be_approved(store, tmp_path, artifact):
    run_id, root = staged_run(store, tmp_path)
    (root / artifact).unlink()
    with pytest.raises(ValueError, match="Missing required artifact"):
        approve(store, run_id)
    assert store.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 0


@pytest.mark.parametrize("artifact", ["report.md", "candidate_findings.jsonl", "candidate_connections.jsonl"])
def test_changed_or_added_artifact_requires_new_review(store, tmp_path, artifact):
    run_id, root = staged_run(store, tmp_path)
    approve(store, run_id)
    with (root / artifact).open("a") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="changed after approval"):
        dispatcher.import_staged_run(store, run_id, {}, "fixture", force=True)
    assert store.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 0


def test_running_process_and_incomplete_outcome_cannot_be_approved(store, tmp_path):
    run_id, root = staged_run(store, tmp_path)
    store.execute("UPDATE dispatch_runs SET status='running' WHERE id=?", (run_id,))
    store.commit()
    with pytest.raises(ValueError, match="finished successful"):
        approve(store, run_id)
    store.execute("UPDATE dispatch_runs SET status='completed' WHERE id=?", (run_id,))
    store.commit()
    (root / "run.json").write_text("{}")
    with pytest.raises(ValueError, match="missing fields"):
        approve(store, run_id)


@pytest.mark.parametrize("disposition,research_status,expected", [
    ("keep_open", "completed", "open"), ("completed", "completed", "completed"),
    ("blocked", "partial", "blocked"), ("dead_end", "dead_end", "dead_end"),
])
def test_reviewed_lead_disposition_is_explicit(store, tmp_path, disposition, research_status, expected):
    lead_id = store.execute("INSERT INTO leads (title,status,profile_id) VALUES ('Fixture lead','open',?)", (PROFILE,)).lastrowid
    store.commit()
    run_id, _ = staged_run(store, tmp_path, records=[], disposition=disposition, status=research_status, lead_id=lead_id)
    approve(store, run_id)
    dispatcher.import_staged_run(store, run_id, {}, "fixture")
    assert store.execute("SELECT status FROM leads WHERE id=?", (lead_id,)).fetchone()[0] == expected


def test_partial_outcome_cannot_claim_completed_disposition(store, tmp_path):
    run_id, _ = staged_run(store, tmp_path, disposition="completed", status="partial")
    with pytest.raises(ValueError, match="Only completed research"):
        approve(store, run_id)


def test_invalid_canonical_record_rolls_back_entire_bundle(store, tmp_path):
    run_id, _ = staged_run(store, tmp_path, records=[candidate(), candidate(source_datasets=["unregistered-source"])])
    approve(store, run_id)
    with pytest.raises(ValueError, match="Unsupported source"):
        dispatcher.import_staged_run(store, run_id, {}, "fixture")
    assert store.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 0
    assert store.execute("SELECT COUNT(*) FROM dispatch_import_raw").fetchone()[0] == 0


def test_concurrent_imports_write_once(store, tmp_path):
    run_id, _ = staged_run(store, tmp_path)
    approve(store, run_id)
    barrier = threading.Barrier(2)

    def import_on_connection():
        db = sqlite3.connect(tmp_path / "test.db", timeout=10)
        db.row_factory = sqlite3.Row
        try:
            barrier.wait(timeout=5)
            return dispatcher.import_staged_run(db, run_id, {}, "fixture")
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: import_on_connection(), range(2)))
    assert results[0] == results[1]
    assert store.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 1
    assert store.execute("SELECT COUNT(*) FROM dispatch_import_raw").fetchone()[0] == 1


def test_triage_retains_distinct_questions_and_profiles(store, tmp_path):
    queue = JobQueue(tmp_path / "test.db")
    for title, state, profile in [
        ("Ownership question", "open", PROFILE), ("Testimony question", "pending_triage", PROFILE),
        ("Ownership question", "pending_triage", "another-profile"),
    ]:
        store.execute("INSERT INTO leads (title,target_name,status,profile_id) VALUES (?,'Same subject',?,?)", (title, state, profile))
    store.commit()
    worker = LeadTriageWorker(queue, "fixture", "lead_triage")
    result = worker.execute({"id": "fixture", "payload": {"profile_id": PROFILE}})
    assert result["total"] == 1
    assert result["duplicates"] == []
    assert store.execute("SELECT status FROM leads WHERE title='Testimony question'").fetchone()[0] == "open"
    assert store.execute("SELECT status FROM leads WHERE profile_id='another-profile'").fetchone()[0] == "pending_triage"


@pytest.mark.parametrize("codes,expected", [([1, 1], "blocked"), ([0, 1], "blocked"), ([0, 0], "open")])
def test_collection_outcome_never_completes_research_lead(store, tmp_path, monkeypatch, codes, expected):
    monkeypatch.setenv("OSINT_WORKDIR_BASE", str(tmp_path))
    queue = JobQueue(tmp_path / "test.db")
    lead_id = store.execute("INSERT INTO leads (title,target_name,status,profile_id) VALUES ('Question','Subject','open',?)", (PROFILE,)).lastrowid
    store.commit()
    worker = DeepPersonWorker(queue, "fixture", "deep_person")
    job = {"id": "collection", "payload": {"profile_id": PROFILE, "lead_id": lead_id, "target_name": "Subject", "sources": ["doj", "lmsband"]}}
    results = [{"returncode": code, "stderr": "fixture", "output_path": "fixture.json"} for code in codes]
    with patch("queue_system.worker._run_tool", side_effect=results):
        if all(codes):
            with pytest.raises(RuntimeError, match="no source completed"):
                worker.execute(job)
        else:
            assert worker.execute(job)["job_status"] == "awaiting_review"
    assert store.execute("SELECT status FROM leads WHERE id=?", (lead_id,)).fetchone()[0] == expected


def test_subprocess_deadline_and_cancellation_are_enforced():
    cancelled = threading.Event()
    token = _execution_context.set(ExecutionContext(time.monotonic() + 0.1, cancelled, {}))
    try:
        with pytest.raises(Exception, match="timed out"):
            _run_process([sys.executable, "-c", "import time; time.sleep(10)"])
        cancelled.set()
        with pytest.raises(RuntimeError, match="cancelled"):
            _run_process([sys.executable, "-c", "raise AssertionError('must not start')"])
    finally:
        _execution_context.reset(token)


def test_worker_heartbeats_during_execution_and_uses_selected_database(store, tmp_path, monkeypatch):
    monkeypatch.setenv("OSINT_WORKDIR_BASE", str(tmp_path))
    queue = JobQueue(tmp_path / "test.db")
    queue.register_agent("fixture", "echo", ["echo"])
    queue.create_job("echo", "system", payload={"profile_id": PROFILE}, timeout_seconds=2)
    claimed = queue.claim_next("fixture", ["echo"])

    class ProbeWorker(AgentWorker):
        def execute(self, job):
            context = _execution_context.get()
            assert Path(context.env["ITHILDIN_DB_PATH"]) == tmp_path / "test.db"
            assert context.env["ITHILDIN_PROFILE"] == PROFILE
            time.sleep(0.6)
            return {"ok": True}

    with patch.object(queue, "heartbeat_job", wraps=queue.heartbeat_job) as heartbeat:
        ProbeWorker(queue, "fixture", "echo", ["echo"]).run_job(claimed)
    assert heartbeat.call_count >= 1
    assert queue.get_job(claimed["id"])["status"] == "completed"
