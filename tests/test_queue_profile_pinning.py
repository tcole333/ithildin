"""Research queue context survives delay, competing defaults, and custom DBs."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from threading import Barrier

import pytest

from queue_system.queue import JobQueue
from queue_system.triggers import TriggerEngine
from queue_system.worker import AgentWorker, DossierFreshnessWorker, DossierWriterWorker, _execution_context


def set_default(queue, profile):
    with sqlite3.connect(queue.db_path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS investigation_config (key TEXT PRIMARY KEY, value TEXT)")
        db.execute("INSERT OR REPLACE INTO investigation_config VALUES ('active_profile', ?)", (profile,))


@pytest.fixture
def queue(tmp_path, monkeypatch):
    monkeypatch.delenv("ITHILDIN_PROFILE", raising=False)
    monkeypatch.delenv("ITHILDIN_DB_PATH", raising=False)
    monkeypatch.setenv("OSINT_WORKDIR_BASE", str(tmp_path / "jobs"))
    return JobQueue(tmp_path / "queue.db")


def test_queued_context_survives_default_change_and_caller_mutation(queue):
    set_default(queue, "alpha")
    payload = {"target_name": "Example"}
    job_id = queue.create_job("deep_person", "investigation", payload)
    payload["profile_id"] = "mutated"
    set_default(queue, "beta")
    assert queue.get_job(job_id)["payload"] == {
        "target_name": "Example", "profile_id": "alpha", "db_path": str(queue.db_path),
    }


def test_explicit_jobs_and_children_keep_own_context_in_parallel(queue, monkeypatch):
    set_default(queue, "ambient")
    parents = {
        name: queue.create_job("deep_investigate", "investigation", {"profile_id": name})
        for name in ("alpha", "beta")
    }
    monkeypatch.setenv("ITHILDIN_PROFILE", "unrelated")
    set_default(queue, "changed")

    def create_children(name):
        return [queue.create_job("source_scan", "discovery", parent_job_id=parents[name]) for _ in range(3)]

    with ThreadPoolExecutor(max_workers=2) as pool:
        children = list(pool.map(create_children, parents))
    for name, ids in zip(parents, children):
        assert all(queue.get_job(job_id)["payload"]["profile_id"] == name for job_id in ids)
    override = queue.create_job("source_scan", "discovery", {"profile_id": "gamma"}, parent_job_id=parents["alpha"])
    assert queue.get_job(override)["payload"]["profile_id"] == "gamma"


def test_custom_database_without_context_never_uses_repository_default(queue, tmp_path, monkeypatch):
    from tools import investigation_context

    unrelated = tmp_path / "unrelated.db"
    with sqlite3.connect(unrelated) as db:
        db.execute("CREATE TABLE investigation_config (key TEXT, value TEXT)")
        db.execute("INSERT INTO investigation_config VALUES ('active_profile', 'wrong')")
    monkeypatch.setattr(investigation_context, "DB_PATH", unrelated)
    with pytest.raises(ValueError, match="Research jobs require"):
        queue.create_job("source_scan", "discovery")
    assert queue.list_jobs() == []
    pinned = queue.create_job("source_scan", "discovery", {"profile_id": "explicit"})
    assert queue.get_job(pinned)["payload"]["db_path"] == str(queue.db_path)


@pytest.mark.parametrize("bad_profile", [None, "", "../wrong", "two profiles"])
def test_invalid_explicit_pin_cannot_fall_back(queue, bad_profile):
    set_default(queue, "valid")
    with pytest.raises(ValueError, match="Invalid investigation profile"):
        queue.create_job("source_scan", "discovery", {"profile_id": bad_profile})


def test_explicit_db_conflict_is_rejected_without_creating_other_db(queue, tmp_path):
    other = tmp_path / "other.db"
    with pytest.raises(ValueError, match="match the queue database"):
        queue.create_job("source_scan", "discovery", {"profile_id": "alpha", "db_path": str(other)})
    assert not other.exists()
    assert queue.list_jobs() == []


def test_research_child_of_unpinned_parent_requires_explicit_profile(queue):
    parent = queue.create_job("echo", "system")
    set_default(queue, "ambient")
    with pytest.raises(ValueError, match="pinned parent"):
        queue.create_job("source_scan", "discovery", parent_job_id=parent)
    child = queue.create_job("source_scan", "discovery", {"profile_id": "explicit"}, parent_job_id=parent)
    assert queue.get_job(child)["payload"]["profile_id"] == "explicit"


def test_system_and_infrastructure_jobs_remain_global(queue, monkeypatch):
    monkeypatch.setenv("ITHILDIN_PROFILE", "ambient")
    for domain in ("system", "infrastructure"):
        job_id = queue.create_job("echo", domain)
        assert queue.get_job(job_id)["payload"] == {"db_path": str(queue.db_path)}


class ContextWorker(AgentWorker):
    def execute(self, job):
        context = _execution_context.get()
        return {key: context.env.get(key) for key in ("ITHILDIN_PROFILE", "ITHILDIN_DB_PATH")}


def run_context_job(queue, job_id):
    queue.register_agent("test-worker", "context", ["context"])
    job = queue.claim_next("test-worker", ["context"])
    assert job["id"] == job_id
    worker = ContextWorker(queue, "test-worker", "context")
    worker.run_job(job)
    return queue.get_job(job_id)


def test_worker_uses_queued_profile_and_restores_ambient_environment(queue, monkeypatch):
    set_default(queue, "alpha")
    job_id = queue.create_job("context", "investigation")
    set_default(queue, "beta")
    monkeypatch.setenv("ITHILDIN_PROFILE", "ambient")
    job = run_context_job(queue, job_id)
    assert job["status"] == "completed"
    assert job["output"] == {"ITHILDIN_PROFILE": "alpha", "ITHILDIN_DB_PATH": str(queue.db_path)}
    assert os.environ["ITHILDIN_PROFILE"] == "ambient"


def test_legacy_unpinned_research_job_fails_before_execution(queue, monkeypatch):
    job_id = queue.create_job("context", "investigation", {"profile_id": "alpha"}, max_attempts=1)
    with sqlite3.connect(queue.db_path) as db:
        db.execute("UPDATE job_queue SET payload='{}' WHERE id=?", (job_id,))
    monkeypatch.setenv("ITHILDIN_PROFILE", "ambient")
    job = run_context_job(queue, job_id)
    assert job["status"] == "failed"
    assert "Research jobs require" in job["error_message"]
    assert job["output"] is None


def test_global_execution_does_not_inherit_worker_profile(queue, monkeypatch):
    monkeypatch.setenv("ITHILDIN_PROFILE", "ambient")
    job_id = queue.create_job("context", "system")
    job = run_context_job(queue, job_id)
    assert job["output"]["ITHILDIN_PROFILE"] is None
    assert os.environ["ITHILDIN_PROFILE"] == "ambient"


def test_parallel_workers_do_not_mutate_ambient_context(queue, monkeypatch):
    monkeypatch.setenv("ITHILDIN_PROFILE", "ambient")
    barrier = Barrier(2)
    jobs = []
    for profile in ("alpha", "beta"):
        queue.register_agent(profile, "context", [profile])
        queue.create_job(profile, "investigation", {"profile_id": profile})
        jobs.append(queue.claim_next(profile, [profile]))

    class ParallelWorker(AgentWorker):
        def execute(self, job):
            barrier.wait(timeout=5)
            context = _execution_context.get()
            assert os.environ["ITHILDIN_PROFILE"] == "ambient"
            assert context.env["ITHILDIN_PROFILE"] == job["payload"]["profile_id"]
            return {"profile": context.env["ITHILDIN_PROFILE"]}

    def run(job):
        ParallelWorker(queue, job["claimed_by"], "context").run_job(job)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, jobs))
    assert [queue.get_job(job["id"])["output"] for job in jobs] == [{"profile": "alpha"}, {"profile": "beta"}]


def config_path(tmp_path, triggers, mode="scheduled", **fields):
    path = tmp_path / "triggers.json"
    path.write_text(json.dumps({mode: triggers, **fields}))
    return path


def research_trigger(**overrides):
    return {"name": "research", "job_type": "synthesis", "domain": "analysis", "interval_minutes": 60, **overrides}


def test_trigger_lifetime_captures_default_but_preserves_per_job_override(queue, tmp_path):
    set_default(queue, "alpha")
    path = config_path(tmp_path, [research_trigger(), research_trigger(name="explicit", payload={"profile_id": "beta"})])
    engine = TriggerEngine(queue, config_path=path)
    set_default(queue, "changed")
    results = engine.run_scheduled()
    assert {row["name"]: queue.get_job(row["job_id"])["payload"]["profile_id"] for row in results} == {
        "research": "alpha", "explicit": "beta",
    }


def test_trigger_with_no_starting_context_cannot_adopt_later_default(queue, tmp_path):
    engine = TriggerEngine(queue, config_path=config_path(tmp_path, [research_trigger()]))
    set_default(queue, "later")
    with pytest.raises(ValueError, match="Research jobs require"):
        engine.run_scheduled()
    assert queue.list_jobs() == []


@pytest.mark.parametrize("metric", ["pending_triage", "findings_total", "findings_delta"])
def test_research_thresholds_ignore_other_profile_records(queue, tmp_path, metric):
    with sqlite3.connect(queue.db_path) as db:
        db.execute("CREATE TABLE findings (id INTEGER PRIMARY KEY, profile_id TEXT)")
        db.execute("CREATE TABLE leads (id INTEGER PRIMARY KEY, profile_id TEXT, status TEXT)")
        db.executemany("INSERT INTO findings(profile_id) VALUES (?)", [("alpha",), ("beta",), ("beta",)])
        db.executemany("INSERT INTO leads(profile_id,status) VALUES (?, 'pending_triage')", [("alpha",), ("beta",), ("beta",)])
    trigger = research_trigger(metric=metric, threshold=2)
    engine = TriggerEngine(queue, config_path=config_path(tmp_path, [trigger], "thresholds"), profile_id="alpha")
    assert engine.run_thresholds() == []
    other = TriggerEngine(queue, config_path=engine.config_path, profile_id="beta")
    fired = other.run_thresholds()
    assert len(fired) == 1
    assert fired[0]["value"] == 2
    assert queue.get_job(fired[0]["job_id"])["payload"]["profile_id"] == "beta"
    if metric == "findings_delta":
        assert other.run_thresholds() == []


def test_cooldowns_and_hourly_budget_are_shared_between_profiles(queue, tmp_path):
    trigger = research_trigger(cooldown_minutes=60)
    path = config_path(tmp_path, [trigger], budget_per_hour=1)
    first = TriggerEngine(queue, config_path=path, profile_id="alpha")
    second = TriggerEngine(queue, config_path=path, profile_id="beta")
    assert len(first.run_scheduled()) == 1
    assert second.run_scheduled() == []
    trigger["name"] = "another"
    config_path(tmp_path, [trigger], budget_per_hour=1)
    assert second.run_scheduled() == []


def test_trigger_cli_honors_environment_db_and_explicit_profile(queue, tmp_path):
    path = config_path(tmp_path, [research_trigger()])
    env = dict(os.environ, ITHILDIN_DB_PATH=str(queue.db_path))
    env.pop("ITHILDIN_PROFILE", None)
    result = subprocess.run(
        [sys.executable, "scripts/trigger_engine.py", "--config", str(path), "--profile", "explicit", "run-scheduled"],
        env=env, capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1],
    )
    assert result.returncode == 0, result.stderr
    jobs = queue.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["payload"]["profile_id"] == "explicit"
    with sqlite3.connect(queue.db_path) as db:
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='investigation_config'").fetchone()


def freshness_tables(queue):
    with sqlite3.connect(queue.db_path) as db:
        db.execute("CREATE TABLE findings (target_name TEXT, profile_id TEXT, verification_status TEXT, created_at TEXT)")
        db.execute("CREATE TABLE connections (person_a TEXT, person_b TEXT, profile_id TEXT, verification_status TEXT, created_at TEXT)")


def test_freshness_jobs_and_pending_dedupe_are_profile_scoped(queue, tmp_path, monkeypatch):
    monkeypatch.setenv("ITHILDIN_CONTENT_ROOT", str(tmp_path / "content"))
    freshness_tables(queue)
    with sqlite3.connect(queue.db_path) as db:
        db.executemany(
            "INSERT INTO findings VALUES (?, ?, 'unverified', '2026-01-01')",
            [("Same Subject", "alpha"), ("Same Subject", "beta"), ("Beta Only", "beta")],
        )
    beta_update = queue.create_job("wiki_dossier_update", "curation", {"target_name": "Same Subject", "profile_id": "beta"})
    parent_id = queue.create_job("dossier_freshness_audit", "curation", {"profile_id": "alpha", "min_findings": 1})
    parent = queue.get_job(parent_id)
    worker = DossierFreshnessWorker(queue, "freshness", "dossier_freshness_audit")
    result = worker.execute(parent)
    assert result["updates_needed"] == ["Same Subject"]
    assert len(result["jobs_created"]) == 1
    child = queue.get_job(result["jobs_created"][0])
    assert child["id"] != beta_update
    assert child["parent_job_id"] == parent_id
    assert child["payload"]["profile_id"] == "alpha"
    assert child["payload"]["db_path"] == str(queue.db_path)
    assert worker.execute(parent)["jobs_created"] == []


def test_freshness_connection_dates_and_snapshot_scope_ignore_other_profile(queue, tmp_path, monkeypatch):
    content = tmp_path / "content"
    dossiers = content / "dossiers"
    dossiers.mkdir(parents=True)
    monkeypatch.setenv("ITHILDIN_CONTENT_ROOT", str(content))
    freshness_tables(queue)
    with sqlite3.connect(queue.db_path) as db:
        db.executemany(
            "INSERT INTO findings VALUES (?, 'alpha', 'unverified', '2020-01-01')",
            [("Current Subject",), ("Other Snapshot",)],
        )
        db.execute("INSERT INTO connections VALUES ('Current Subject', 'Beta Person', 'beta', 'unverified', '2030-01-01')")
    for name, profile in [("Current Subject", "alpha"), ("Other Snapshot", "beta")]:
        (dossiers / f"{name}.json").write_text(json.dumps({
            "name": name, "profile_ids": [profile], "last_updated": "2025-01-01",
            "curation": {"key_finding_ids": [1]},
        }))
    job_id = queue.create_job("dossier_freshness_audit", "curation", {"profile_id": "alpha", "min_findings": 1, "dry_run": True})
    result = DossierFreshnessWorker(queue, "freshness", "dossier_freshness_audit").execute(queue.get_job(job_id))
    assert result["updates_needed"] == ["Other Snapshot"]


def test_dossier_review_child_inherits_queued_parent_context(queue, tmp_path, monkeypatch):
    from queue_system import worker as worker_module

    monkeypatch.setenv("ITHILDIN_CONTENT_ROOT", str(tmp_path / "content"))
    monkeypatch.setattr(worker_module, "_run_script", lambda *_: {"returncode": 0})
    parent_id = queue.create_job("wiki_dossier_update", "curation", {
        "profile_id": "alpha", "target_name": "Example", "spawn_review": True,
    })
    set_default(queue, "changed")
    result = DossierWriterWorker(queue, "writer", "wiki_dossier_update").execute(queue.get_job(parent_id))
    child = queue.get_job(result["review_job_id"])
    assert child["parent_job_id"] == parent_id
    assert child["payload"]["profile_id"] == "alpha"
