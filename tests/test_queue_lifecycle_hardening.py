"""Queue invariants exercised against isolated databases and mocked process launch."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pytest

from queue_system.queue import JobQueue
from queue_system.triggers import TriggerEngine
from scripts import agent_worker, queue_dispatcher


@pytest.fixture
def queue(tmp_path):
    return JobQueue(tmp_path / "queue.db", busy_timeout_ms=500, retry_attempts=1)


def count_rows(queue, table):
    db = queue._connect()
    try:
        return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        db.close()


def claimed_job(queue, agent_id="worker"):
    queue.register_agent(agent_id, "echo", ["echo"])
    job_id = queue.create_job("echo", "system", retry_delay_seconds=0)
    job = queue.claim_next(agent_id, ["echo"])
    assert job["id"] == job_id
    assert job["status"] == "claimed"
    assert job["claimed_by"] == agent_id
    assert job["attempts"] == 1
    return job


def trigger_config(tmp_path, mode, names=("first", "second"), **config_fields):
    triggers = []
    for name in names:
        trigger = {
            "name": name, "job_type": "echo", "domain": "system",
            "cooldown_minutes": 60,
        }
        if mode == "scheduled":
            trigger["interval_minutes"] = 60
        else:
            trigger.update(metric="queue_pending", threshold=0)
        triggers.append(trigger)
    config_path = tmp_path / f"{mode}-{'-'.join(names)}.json"
    config_path.write_text(json.dumps({mode: triggers, **config_fields}))
    return config_path


def pool_config(max_workers=1):
    return {"agents": [{"persona": "echo", "job_types": ["echo"], "max_workers": max_workers}]}


def test_create_job_joins_caller_transaction_without_committing(queue):
    parent_id = queue.create_job("echo", "system")
    db = queue._connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        child_id = queue.create_job("echo", "system", depends_on=[parent_id], conn=db)
        assert db.in_transaction
        assert db.execute("SELECT status FROM job_queue WHERE id=?", (child_id,)).fetchone()[0] == "blocked"
        assert queue.get_job(child_id) is None
        db.rollback()
        assert db.execute("SELECT COUNT(*) FROM job_queue").fetchone()[0] == 1
    finally:
        db.close()
    assert queue.get_job(child_id) is None
    assert count_rows(queue, "job_dependencies") == 0
    assert count_rows(queue, "job_events") == 1


@pytest.mark.parametrize("mode", ["scheduled", "thresholds"])
def test_two_due_triggers_commit_jobs_and_receipts_together(queue, tmp_path, mode):
    engine = TriggerEngine(queue, config_path=trigger_config(tmp_path, mode))
    run = engine.run_scheduled if mode == "scheduled" else engine.run_thresholds
    results = run()
    assert len(results) == 2
    assert count_rows(queue, "job_queue") == 2
    assert {row["job_id"] for row in engine.list_runs()} == {row["job_id"] for row in results}
    assert run() == []


@pytest.mark.parametrize("mode", ["scheduled", "thresholds"])
def test_receipt_failure_rolls_back_trigger_jobs(queue, tmp_path, monkeypatch, mode):
    engine = TriggerEngine(queue, config_path=trigger_config(tmp_path, mode))

    def reject_receipt(*args, **kwargs):
        raise RuntimeError("receipt insert failed")

    monkeypatch.setattr(engine, "_record_run", reject_receipt)
    run = engine.run_scheduled if mode == "scheduled" else engine.run_thresholds
    with pytest.raises(RuntimeError, match="receipt insert failed"):
        run()
    assert count_rows(queue, "job_queue") == 0
    assert count_rows(queue, "job_events") == 0
    assert engine.list_runs() == []


@pytest.mark.parametrize("mode", ["scheduled", "thresholds"])
def test_concurrent_triggers_share_cooldown(queue, tmp_path, mode):
    engine = TriggerEngine(queue, config_path=trigger_config(tmp_path, mode))
    barrier = Barrier(2)

    def run():
        barrier.wait(timeout=5)
        return engine.run_scheduled() if mode == "scheduled" else engine.run_thresholds()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert sum(map(len, results)) == 2
    assert count_rows(queue, "job_queue") == count_rows(queue, "trigger_runs") == 2


def test_concurrent_trigger_engines_share_hourly_budget(queue, tmp_path):
    engines = [
        TriggerEngine(queue, config_path=trigger_config(tmp_path, "scheduled", (name,), budget_per_hour=1))
        for name in ("a", "b")
    ]
    barrier = Barrier(2)

    def run(engine):
        barrier.wait(timeout=5)
        return engine.run_scheduled()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, engines))
    assert sum(map(len, results)) == 1
    assert count_rows(queue, "job_queue") == count_rows(queue, "trigger_runs") == 1


def test_trigger_dry_run_does_not_claim_cooldown(queue, tmp_path):
    engine = TriggerEngine(queue, config_path=trigger_config(tmp_path, "scheduled"))
    assert len(engine.run_scheduled(dry_run=True)) == 2
    assert count_rows(queue, "job_queue") == count_rows(queue, "trigger_runs") == 0
    assert len(engine.run_scheduled()) == 2


def test_trigger_rejects_split_database(queue, tmp_path):
    with pytest.raises(ValueError, match="same database"):
        TriggerEngine(queue, db_path=tmp_path / "other.db")


@pytest.mark.parametrize("terminal", ["cancelled", "stale", "completed", "failed", "awaiting_review"])
def test_late_worker_cannot_replace_terminal_state(queue, terminal):
    job = claimed_job(queue)
    started = queue.start_job(job["id"], "worker", job["attempts"])
    assert started["status"] == "in_progress"
    assert started["attempts"] == 1
    dependent = queue.create_job("echo", "system", depends_on=[job["id"]])
    queue.set_status(job["id"], terminal)
    event_count = count_rows(queue, "job_events")
    assert queue.start_job(job["id"], "worker", 1) is None
    assert not queue.complete_job(job["id"], {"late": True}, agent_id="worker", attempt=1)
    assert not queue.fail_job(job["id"], "late failure", agent_id="worker", attempt=1)
    assert not queue.heartbeat_job(job["id"], "worker", 1)
    assert queue.get_job(job["id"])["status"] == terminal
    assert queue.get_job(dependent)["status"] == "blocked"
    assert count_rows(queue, "job_events") == event_count


def test_attempt_token_rejects_old_result_even_when_agent_id_reused(queue):
    first = claimed_job(queue)
    queue.start_job(first["id"], "worker", first["attempts"])
    assert queue.fail_job(first["id"], "retry", agent_id="worker", attempt=1)
    second = queue.claim_next("worker", ["echo"])
    assert second["attempts"] == 2
    assert queue.start_job(first["id"], "worker", 1) is None
    assert queue.start_job(first["id"], "intruder", 2) is None
    assert queue.start_job(second["id"], "worker", 2)["attempts"] == 2
    event_count = count_rows(queue, "job_events")
    assert not queue.complete_job(first["id"], agent_id="worker", attempt=1)
    assert not queue.complete_job(first["id"], agent_id="intruder", attempt=2)
    assert not queue.fail_job(first["id"], "old failure", agent_id="worker", attempt=1)
    assert not queue.heartbeat_job(first["id"], "worker", 1)
    assert count_rows(queue, "job_events") == event_count
    assert queue.complete_job(second["id"], {"attempt": 2}, agent_id="worker", attempt=2)
    assert queue.get_job(first["id"])["output"] == {"attempt": 2}


def test_heartbeat_preserves_deadline_and_rejects_expired_execution(queue):
    job = claimed_job(queue)
    started = queue.start_job(job["id"], "worker", 1)
    db = queue._connect()
    try:
        db.execute("UPDATE agent_instances SET last_heartbeat=datetime('now', '-80 seconds')")
        db.commit()
        before = db.execute("SELECT last_heartbeat FROM agent_instances").fetchone()[0]
        assert queue.heartbeat_job(job["id"], "worker", 1)
        after = db.execute("SELECT last_heartbeat FROM agent_instances").fetchone()[0]
        assert after > before
        assert queue.get_job(job["id"])["stale_after"] == started["stale_after"]
        db.execute("UPDATE job_queue SET stale_after=datetime('now', '-1 second')")
        db.commit()
        assert not queue.heartbeat_job(job["id"], "worker", 1)
    finally:
        db.close()
    assert queue.mark_stale_jobs() == 1
    assert not queue.complete_job(job["id"], agent_id="worker", attempt=1)


def test_abandoned_claim_expires_without_start(queue):
    job = claimed_job(queue)
    db = queue._connect()
    try:
        db.execute("UPDATE job_queue SET stale_after=datetime('now', '-1 second')")
        db.commit()
    finally:
        db.close()
    assert queue.start_job(job["id"], "worker", 1) is None
    assert queue.mark_stale_jobs() == 1
    assert queue.get_job(job["id"])["status"] == "stale"


def test_administrative_completion_still_unblocks_pending_dependency(queue):
    parent = queue.create_job("echo", "system")
    child = queue.create_job("echo", "system", depends_on=[parent])
    assert queue.complete_job(parent, {"reviewed": True})
    assert queue.get_job(child)["status"] == "pending"
    with pytest.raises(ValueError, match="both agent_id and attempt"):
        queue.complete_job(child, agent_id="worker")


def test_concurrent_dispatchers_reserve_only_configured_capacity(queue):
    for _ in range(6):
        queue.create_job("echo", "system")
    barrier = Barrier(4)

    def reserve(_):
        barrier.wait(timeout=5)
        return queue_dispatcher.reserve_workers(pool_config(2), queue.db_path)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(reserve, range(4)))
    assert sum(len(reservations) for _, reservations in results) == 2
    assert len(queue.list_agents(status="active")) == 2
    assert queue_dispatcher.reserve_workers(pool_config(2), queue.db_path) == ([], [])


def test_expired_reservation_cannot_revive_after_replacement(queue):
    queue.create_job("echo", "system")
    _, reservations = queue_dispatcher.reserve_workers(pool_config(), queue.db_path)
    retired_id = reservations[0]["agent_id"]
    db = queue._connect()
    try:
        db.execute("UPDATE agent_instances SET last_heartbeat=datetime('now', '-91 seconds')")
        db.commit()
    finally:
        db.close()
    _, replacement = queue_dispatcher.reserve_workers(pool_config(), queue.db_path)
    assert len(replacement) == 1
    assert replacement[0]["agent_id"] != retired_id
    assert not queue.register_agent(retired_id, "echo", ["echo"], require_reserved=True)
    assert not queue.register_agent(retired_id, "echo", ["echo"])
    assert not queue.heartbeat_agent(retired_id)
    assert queue.claim_next(retired_id, ["echo"]) is None
    assert len(queue.list_agents(status="active")) == 1


def test_retired_running_agent_cannot_complete_or_retry(queue):
    job = claimed_job(queue)
    queue.start_job(job["id"], "worker", 1)
    queue.stop_agent("worker")
    assert not queue.complete_job(job["id"], agent_id="worker", attempt=1)
    assert not queue.fail_job(job["id"], "retired", agent_id="worker", attempt=1)
    assert not queue.heartbeat_job(job["id"], "worker", 1)


def test_dispatcher_propagates_database_profile_and_reserves_before_launch(queue, monkeypatch):
    queue.create_job("echo", "system")
    launches = []

    def launch(cmd, *, env, cwd):
        launches.append((cmd, env, cwd))
        assert len(queue.list_agents(status="active")) == 1
        return SimpleNamespace(pid=123)

    monkeypatch.setattr(queue_dispatcher.subprocess, "Popen", launch)
    result = queue_dispatcher.spawn_workers([], pool_config(), False, db_path=queue.db_path, profile="epstein")
    assert result[0]["pid"] == 123
    cmd, env, cwd = launches[0]
    assert cmd[cmd.index("--db-path") + 1] == str(queue.db_path.resolve())
    assert cmd[cmd.index("--profile") + 1] == env["ITHILDIN_PROFILE"] == "epstein"
    assert env["ITHILDIN_DB_PATH"] == str(queue.db_path.resolve())
    assert "--reserved" in cmd
    assert Path(cwd) == queue_dispatcher.PROJECT_ROOT


def test_failed_spawn_releases_reservation(queue, monkeypatch):
    queue.create_job("echo", "system")

    def fail_launch(*args, **kwargs):
        raise OSError("worker executable unavailable")

    monkeypatch.setattr(queue_dispatcher.subprocess, "Popen", fail_launch)
    result = queue_dispatcher.spawn_workers([], pool_config(), False, db_path=queue.db_path)
    assert result[0]["status"] == "failed"
    assert queue.list_agents(status="active") == []
    assert len(queue_dispatcher.reserve_workers(pool_config(), queue.db_path)[1]) == 1


def test_paused_dispatcher_reserves_nothing(queue):
    queue.create_job("echo", "system")
    queue.set_paused(True)
    assert queue_dispatcher.reserve_workers(pool_config(), queue.db_path) == ([], [])
    assert queue.list_agents() == []


def test_worker_entry_uses_pinned_database_and_profile(queue, monkeypatch):
    from queue_system.worker import WORKER_REGISTRY

    _, reservations = queue_dispatcher.reserve_workers(
        {"agents": [{"persona": "echo", "min_workers": 1}]}, queue.db_path
    )
    agent_id = reservations[0]["agent_id"]
    seen = []

    class StubWorker:
        JOB_TYPES = ["echo"]

        def __init__(self, **kwargs):
            seen.append(kwargs)

        def run_forever(self):
            return

    monkeypatch.setitem(WORKER_REGISTRY, "echo", StubWorker)
    monkeypatch.setenv("ITHILDIN_DB_PATH", str(queue.db_path.parent / "wrong.db"))
    monkeypatch.setenv("ITHILDIN_PROFILE", "wrong-profile")
    monkeypatch.setattr("sys.argv", [
        "agent_worker.py", "--persona", "echo", "--id", agent_id,
        "--db-path", str(queue.db_path), "--profile", "epstein", "--reserved",
    ])
    agent_worker.main()
    assert seen[0]["queue"].db_path == queue.db_path
    assert JobQueue().db_path == queue.db_path
    assert len(queue.list_agents(status="stopped")) == 1
    assert not (queue.db_path.parent / "wrong.db").exists()


def test_worker_entry_rejects_unknown_profile_before_opening_database(tmp_path, monkeypatch):
    db_path = tmp_path / "must-not-open.db"
    monkeypatch.setenv("ITHILDIN_DB_PATH", str(db_path))
    monkeypatch.setattr("sys.argv", [
        "agent_worker.py", "--persona", "echo", "--profile", "no-such-test-profile",
    ])
    with pytest.raises(SystemExit) as exc:
        agent_worker.main()
    assert exc.value.code == 2
    assert not db_path.exists()
