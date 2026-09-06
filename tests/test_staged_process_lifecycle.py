"""Local-process regressions for staged dispatch; no backend or canonical DB calls."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from scripts import dispatcher


class LocalBackend:
    def __init__(self, command, before_launch=None):
        self.command = command
        self.before_launch = before_launch

    def preflight(self):
        if self.before_launch:
            self.before_launch()
        return True, "healthy", "local fixture"

    def build_command(self, prompt, config, system_prompts):
        return self.command


@pytest.fixture
def local_dispatch(tmp_path, monkeypatch):
    database_file = tmp_path / "dispatch.db"
    monkeypatch.setattr(dispatcher, "DB_PATH", database_file)
    monkeypatch.delenv("ITHILDIN_PROFILE", raising=False)
    db = dispatcher.get_db()
    dispatcher.ensure_dispatch_table(db)
    db.execute("CREATE TABLE investigation_config (key TEXT PRIMARY KEY, value TEXT)")
    db.execute("INSERT INTO investigation_config VALUES ('active_profile', 'profile-a')")
    db.commit()
    config = dispatcher.deep_merge(dispatcher.DEFAULT_CONFIG, {"staging_root": str(tmp_path / "staging")})
    terminate_group = dispatcher.terminate_process_group
    yield db, config
    for row in db.execute("SELECT pid FROM dispatch_runs WHERE pid IS NOT NULL"):
        terminate_group(row[0], grace_seconds=0.1)
    db.close()


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.02)
    raise AssertionError("Local subprocess did not reach the expected state")


def launch_local(db, config, code, *, review_required=False, before_launch=None):
    backend = LocalBackend([sys.executable, "-c", code], before_launch)
    assert dispatcher.launch_job(
        db, config, dispatcher.TaskContract(job_type="trace_entity", target="Fixture Co", review_required=review_required),
        backend=backend,
    )
    return db.execute("SELECT * FROM dispatch_runs ORDER BY id DESC LIMIT 1").fetchone()


@pytest.mark.parametrize("exit_code", [0, 7])
def test_actual_subprocess_exit_survives_new_dispatch_connection(local_dispatch, exit_code):
    db, config = local_dispatch
    run = launch_local(db, config, f"import sys; print('{{\"result\":\"2 findings\"}}'); sys.exit({exit_code})")
    receipt = dispatcher.process_exit_path(Path(run["output_file"]))
    wait_until(receipt.exists)
    wait_until(lambda: not dispatcher.process_alive(run["pid"]))
    # A later one-shot invocation has no Popen object/returncode from launch.
    with dispatcher.get_db() as later:
        dispatcher.reap_completed(later, config)
        row = later.execute("SELECT * FROM dispatch_runs WHERE id=?", (run["id"],)).fetchone()
    assert row["exit_code"] == exit_code
    assert row["status"] == ("completed" if exit_code == 0 else "failed")
    assert row["findings_added"] == 2
    if exit_code:
        assert "status 7" in row["error"]


@pytest.mark.parametrize("payload", [{}, [], {"is_error": True, "result": "API failure"}, {"subtype": "error_max_turns", "result": "Partial output"}])
def test_zero_exit_does_not_approve_empty_or_error_output(local_dispatch, payload):
    db, config = local_dispatch
    run = launch_local(db, config, f"print({json.dumps(json.dumps(payload))})")
    wait_until(lambda: not dispatcher.process_alive(run["pid"]))
    dispatcher.reap_completed(db, config)
    row = db.execute("SELECT status, exit_code, error FROM dispatch_runs WHERE id=?", (run["id"],)).fetchone()
    assert row["status"] == "failed"
    assert row["exit_code"] == 0
    assert row["error"]


@pytest.mark.parametrize("damage", ["missing", "wrong_pid", "wrong_run", "boolean_exit"])
def test_json_cannot_replace_a_missing_or_foreign_exit_receipt(local_dispatch, damage):
    db, config = local_dispatch
    run = launch_local(db, config, "print('{\"result\":\"done\"}')")
    wait_until(lambda: not dispatcher.process_alive(run["pid"]))
    target = dispatcher.process_exit_path(Path(run["output_file"]))
    if damage == "missing":
        target.unlink()
    else:
        receipt = json.loads(target.read_text())
        key, value = {"wrong_pid": ("supervisor_pid", -1), "wrong_run": ("run_id", -1), "boolean_exit": ("exit_code", False)}[damage]
        receipt[key] = value
        target.write_text(json.dumps(receipt))
    dispatcher.reap_completed(db, config)
    row = db.execute("SELECT status, exit_code, error FROM dispatch_runs WHERE id=?", (run["id"],)).fetchone()
    assert row["status"] == "failed"
    assert row["exit_code"] is None
    assert "Process exit status unavailable" in row["error"]


def test_successful_process_with_missing_required_artifacts_is_failed(local_dispatch):
    db, config = local_dispatch
    run = launch_local(db, config, "print('{\"result\":\"done\"}')", review_required=True)
    wait_until(lambda: not dispatcher.process_alive(run["pid"]))
    dispatcher.reap_completed(db, config)
    row = db.execute("SELECT status, exit_code, health_status FROM dispatch_runs WHERE id=?", (run["id"],)).fetchone()
    assert tuple(row) == ("failed", 0, "invalid_artifacts")


def test_launch_context_is_captured_before_preflight_mutates_default(local_dispatch):
    db, config = local_dispatch

    def switch_default():
        db.execute("UPDATE investigation_config SET value='profile-b' WHERE key='active_profile'")
        db.commit()

    code = "import json, os; print(json.dumps({'result': 'done', 'profile': os.environ['ITHILDIN_PROFILE'], 'db': os.environ['ITHILDIN_DB_PATH']}))"
    run = launch_local(db, config, code, before_launch=switch_default)
    wait_until(lambda: not dispatcher.process_alive(run["pid"]))
    output = json.loads(Path(run["output_file"]).read_text())
    assert output["profile"] == "profile-a"
    assert Path(output["db"]).resolve() == dispatcher.DB_PATH.resolve()
    assert json.loads(run["task_contract_json"])["profile_id"] == "profile-a"


def test_unresolved_profile_refuses_scoped_worker(local_dispatch):
    db, config = local_dispatch
    db.execute("DELETE FROM investigation_config")
    db.commit()
    backend = LocalBackend([sys.executable, "-c", "raise AssertionError('must not run')"])
    assert not dispatcher.launch_job(db, config, dispatcher.TaskContract(job_type="trace_entity"), backend)
    row = db.execute("SELECT pid, health_status FROM dispatch_runs").fetchone()
    assert tuple(row) == (None, "context_missing")


def test_concurrent_launchers_reserve_only_one_process(local_dispatch, tmp_path):
    db, config = local_dispatch
    rendezvous = threading.Barrier(2)
    marker = tmp_path / "workers.txt"
    code = f"from pathlib import Path; import time; p=Path({str(marker)!r}); p.open('a').write('worker\\n'); time.sleep(30)"

    def launch():
        with dispatcher.get_db() as connection:
            backend = LocalBackend([sys.executable, "-c", code], rendezvous.wait)
            return dispatcher.launch_job(connection, config, dispatcher.TaskContract(job_type="trace_entity", target="Concurrent"), backend)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: launch(), range(2)))
    assert sorted(results) == [False, True]
    assert db.execute("SELECT COUNT(*) FROM dispatch_runs WHERE status='running'").fetchone()[0] == 1
    wait_until(marker.exists)
    assert marker.read_text() == "worker\n"


def test_supervisor_refuses_a_cancelled_reservation(local_dispatch, tmp_path):
    db, _ = local_dispatch
    marker = tmp_path / "must-not-exist"
    output = tmp_path / "cancelled.json"
    cursor = db.execute("INSERT INTO dispatch_runs (run_type, status, pid) VALUES ('trace_entity', 'failed', ?)", (os.getpid(),))
    db.commit()
    assert dispatcher.supervise_process(dispatcher.DB_PATH, cursor.lastrowid, output, [sys.executable, "-c", f"open({str(marker)!r},'w').close()"]) == 1
    assert not marker.exists()
    assert "no longer running" in json.loads(dispatcher.process_exit_path(output).read_text())["error"]


def test_group_termination_reaches_and_kills_term_resistant_descendant(tmp_path):
    heartbeat = tmp_path / "heartbeat"
    term_marker = tmp_path / "term-received"
    child_code = (
        "import signal, time; from pathlib import Path; "
        f"signal.signal(signal.SIGTERM, lambda *_: Path({str(term_marker)!r}).write_text('term')); "
        f"p=Path({str(heartbeat)!r}); "
        "\nwhile True:\n p.write_text(str(time.monotonic_ns())); time.sleep(0.01)"
    )
    parent_code = (
        "import signal, subprocess, sys, time; "
        "signal.signal(signal.SIGTERM, lambda *_: None); "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}]); time.sleep(30)"
    )
    proc = subprocess.Popen([sys.executable, "-c", parent_code], start_new_session=True)
    try:
        wait_until(heartbeat.exists)
        first = heartbeat.read_text()
        wait_until(lambda: heartbeat.read_text() != first)
        dispatcher.terminate_process_group(proc.pid, grace_seconds=0.2)
        proc.wait(timeout=5)
        assert term_marker.read_text() == "term"
        last = heartbeat.read_text()
        time.sleep(0.1)
        assert heartbeat.read_text() == last
    finally:
        dispatcher.terminate_process_group(proc.pid, grace_seconds=0)
        proc.wait(timeout=5)


@pytest.mark.parametrize("action", ["timeout", "stop", "dead_leader"])
def test_supervision_uses_group_termination_even_after_leader_exits(local_dispatch, monkeypatch, action):
    db, config = local_dispatch
    db.execute("INSERT INTO dispatch_runs (run_type, pid, started_at, timeout_seconds) VALUES ('trace_entity', 123456789, '2000-01-01 00:00:00', 1)")
    db.commit()
    terminated = []
    monkeypatch.setattr(dispatcher, "process_alive", lambda _: action != "dead_leader")
    monkeypatch.setattr(dispatcher, "terminate_process_group", terminated.append)
    if action == "stop":
        # cmd_stop owns its connection; let the fixture retain its own connection.
        dispatcher.cmd_stop(argparse.Namespace(run_id=None))
    else:
        dispatcher.reap_completed(db, config)
    assert terminated == [123456789]
    row = db.execute("SELECT status FROM dispatch_runs").fetchone()
    assert row[0] == ("timeout" if action == "timeout" else "failed")


def test_supervisor_never_executes_an_uncommitted_reservation(local_dispatch, tmp_path, monkeypatch):
    db, _ = local_dispatch
    marker = tmp_path / "must-not-exist"
    output = tmp_path / "uncommitted.json"
    cursor = db.execute("INSERT INTO dispatch_runs (run_type, pid) VALUES ('trace_entity', ?)", (os.getpid(),))
    ticks = iter([0, 11])
    monkeypatch.setattr(dispatcher.time, "monotonic", lambda: next(ticks))
    try:
        assert dispatcher.supervise_process(dispatcher.DB_PATH, cursor.lastrowid, output, [sys.executable, "-c", f"open({str(marker)!r},'w').close()"]) == 1
        assert not marker.exists()
        assert "not committed" in json.loads(dispatcher.process_exit_path(output).read_text())["error"]
    finally:
        db.rollback()


def test_failed_launch_transaction_cannot_leave_a_worker_executing(local_dispatch, tmp_path):
    db, config = local_dispatch
    marker = tmp_path / "must-not-exist"
    db.execute("""CREATE TRIGGER reject_pid BEFORE UPDATE OF pid ON dispatch_runs
                  BEGIN SELECT RAISE(FAIL, 'injected PID registration failure'); END""")
    db.commit()
    backend = LocalBackend([sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"])
    assert not dispatcher.launch_job(db, config, dispatcher.TaskContract(job_type="trace_entity"), backend)
    assert not marker.exists()
    rows = db.execute("SELECT status, pid, error FROM dispatch_runs").fetchall()
    assert len(rows) == 1
    assert tuple(rows[0][:2]) == ("failed", None)
    assert "injected PID" in rows[0]["error"]


def test_late_finalizer_does_not_replace_a_manual_stop(local_dispatch):
    db, config = local_dispatch
    stale_run = launch_local(db, config, "print('{\"result\":\"done\"}')")
    wait_until(lambda: not dispatcher.process_alive(stale_run["pid"]))
    db.execute("UPDATE dispatch_runs SET status='failed', error='Manually stopped' WHERE id=?", (stale_run["id"],))
    db.commit()
    dispatcher.finalize_run(db, stale_run, config)
    row = db.execute("SELECT status, error FROM dispatch_runs WHERE id=?", (stale_run["id"],)).fetchone()
    assert tuple(row) == ("failed", "Manually stopped")


@pytest.mark.parametrize("job_type, override, expected", [
    ("triage", True, False),
    ("build_infra", True, False),
    ("auto_leads", True, False),
    ("analyze_network", None, True),
    ("analyze_network", False, False),
    ("pursue_lead", None, True),
])
def test_auto_contracts_keep_maintenance_semantics_and_honor_explicit_review_setting(local_dispatch, monkeypatch, job_type, override, expected):
    _, config = local_dispatch
    metric = {
        "triage": "pending_triage", "build_infra": "infra_open", "auto_leads": "completions_since_last_auto",
        "analyze_network": "analyze_network_new_findings", "pursue_lead": "high_critical_open",
    }[job_type]
    queues = dict.fromkeys(["pending_triage", "infra_open", "completions_since_last_auto", "high_critical_open"], 0)
    queues[metric] = 100
    config["max_research_agents"] = 1
    if override is not None:
        config["job_defaults"] = {job_type: {"review_required": override}}
    monkeypatch.setattr(dispatcher, "get_queue_depths", lambda *_, **__: queues)
    monkeypatch.setattr(dispatcher, "get_next_infra_id", lambda _: "14")
    monkeypatch.setattr(dispatcher, "get_next_lead_id", lambda *_, **kw: None if kw.get("for_skill") == "deep_investigate" else "23")
    captured = []
    monkeypatch.setattr(dispatcher, "launch_job", lambda _, __, contract, **kw: captured.append(contract))
    dispatcher.dispatch_cycle(config)
    assert len(captured) == 1
    contract = captured[0]
    assert contract.job_type == job_type
    assert contract.review_required is expected
    assert contract.profile_id == "profile-a"
    if job_type == "pursue_lead":
        assert contract.lead_id == 23


def test_group_probe_permission_does_not_abort_cleanup_of_exiting_process(monkeypatch):
    calls = []
    probes = iter([PermissionError("exiting"), ProcessLookupError("gone")])

    def kill_group(pid, sig):
        calls.append(sig)
        if sig == 0:
            raise next(probes)

    monkeypatch.setattr(dispatcher.os, "killpg", kill_group)
    monkeypatch.setattr(dispatcher, "process_alive", lambda _: False)
    monkeypatch.setattr(dispatcher.time, "sleep", lambda _: None)
    dispatcher.terminate_process_group(123456789)
    assert calls == [dispatcher.signal.SIGTERM, 0, 0]


def test_inaccessible_group_still_escalates_and_reports_a_denied_kill(monkeypatch):
    calls = []
    ticks = iter([0, 0, 1])

    def kill_group(pid, sig):
        calls.append(sig)
        if sig != dispatcher.signal.SIGTERM:
            raise PermissionError("denied")

    monkeypatch.setattr(dispatcher.os, "killpg", kill_group)
    monkeypatch.setattr(dispatcher, "process_alive", lambda _: True)
    monkeypatch.setattr(dispatcher.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(dispatcher.time, "sleep", lambda _: None)
    with pytest.raises(PermissionError, match="denied"):
        dispatcher.terminate_process_group(123456789, grace_seconds=0.5)
    assert calls == [dispatcher.signal.SIGTERM, 0, dispatcher.signal.SIGKILL]
