from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from queue_system.queue import JobQueue


def _count(path: Path, sql: str, params: tuple = ()) -> int:
    conn = sqlite3.connect(str(path))
    try:
        return int(conn.execute(sql, params).fetchone()[0])
    finally:
        conn.close()


def _write_config(path: Path) -> None:
    payload = {
        "budget_per_hour": 10,
        "scheduled": [
            {
                "name": "pytest_scheduled_echo",
                "enabled": True,
                "interval_minutes": 1,
                "job_type": "echo",
                "domain": "system",
                "payload": {"message": "scheduled"},
            }
        ],
        "thresholds": [
            {
                "name": "pytest_pending_threshold",
                "enabled": True,
                "metric": "queue_pending",
                "threshold": 1,
                "job_type": "echo",
                "domain": "system",
                "payload": {"message": "threshold"},
            }
        ],
    }
    path.write_text(json.dumps(payload))


@pytest.mark.integration
def test_trigger_engine_run_scheduled_honors_db_override(tmp_path: Path, run_python_script) -> None:
    db_path = tmp_path / "trigger.db"
    JobQueue(db_path=db_path)
    config_path = tmp_path / "trigger_config.json"
    _write_config(config_path)

    result = run_python_script(
        "scripts/trigger_engine.py",
        "--db-path",
        str(db_path),
        "--config",
        str(config_path),
        "run-scheduled",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload
    assert payload[0]["name"] == "pytest_scheduled_echo"

    pending_jobs = _count(db_path, "SELECT COUNT(*) FROM job_queue WHERE status='pending'")
    trigger_runs = _count(db_path, "SELECT COUNT(*) FROM trigger_runs WHERE trigger_name='pytest_scheduled_echo'")
    assert pending_jobs >= 1
    assert trigger_runs >= 1


@pytest.mark.integration
def test_trigger_engine_threshold_and_status_with_db_override(tmp_path: Path, run_python_script) -> None:
    db_path = tmp_path / "trigger.db"
    queue = JobQueue(db_path=db_path)
    queue.create_job(job_type="echo", domain="system", payload={"message": "seed pending"})
    config_path = tmp_path / "trigger_config.json"
    _write_config(config_path)

    threshold = run_python_script(
        "scripts/trigger_engine.py",
        "--db-path",
        str(db_path),
        "--config",
        str(config_path),
        "run-thresholds",
    )
    assert threshold.returncode == 0, threshold.stderr or threshold.stdout
    payload = json.loads(threshold.stdout)
    assert payload
    assert payload[0]["name"] == "pytest_pending_threshold"
    assert payload[0]["value"] >= 1

    status = run_python_script(
        "scripts/trigger_engine.py",
        "--db-path",
        str(db_path),
        "--config",
        str(config_path),
        "status",
        "--name",
        "pytest_pending_threshold",
        "--limit",
        "5",
    )
    assert status.returncode == 0, status.stderr or status.stdout
    status_payload = json.loads(status.stdout)
    assert status_payload
    assert status_payload[0]["trigger_name"] == "pytest_pending_threshold"


@pytest.mark.integration
def test_trigger_engine_dry_run_does_not_create_jobs(tmp_path: Path, run_python_script) -> None:
    db_path = tmp_path / "trigger.db"
    JobQueue(db_path=db_path)
    config_path = tmp_path / "trigger_config.json"
    _write_config(config_path)

    dry = run_python_script(
        "scripts/trigger_engine.py",
        "--db-path",
        str(db_path),
        "--config",
        str(config_path),
        "--dry-run",
        "run",
    )
    assert dry.returncode == 0, dry.stderr or dry.stdout
    payload = json.loads(dry.stdout)
    assert payload
    assert all(row["status"] == "dry_run" for row in payload)

    pending_jobs = _count(db_path, "SELECT COUNT(*) FROM job_queue WHERE status='pending'")
    trigger_runs = _count(db_path, "SELECT COUNT(*) FROM trigger_runs")
    assert pending_jobs == 0
    assert trigger_runs == 0
