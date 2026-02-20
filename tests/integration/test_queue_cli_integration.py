from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from queue_system.queue import JobQueue


def _db_count(path: Path, sql: str, params: tuple = ()) -> int:
    conn = sqlite3.connect(str(path))
    try:
        return int(conn.execute(sql, params).fetchone()[0])
    finally:
        conn.close()


@pytest.mark.integration
def test_queue_tools_submit_and_status_with_db_override(tmp_path: Path, run_python_script) -> None:
    db_path = tmp_path / "queue.db"
    JobQueue(db_path=db_path)

    submit = run_python_script(
        "scripts/queue_tools.py",
        "--db-path",
        str(db_path),
        "submit",
        "--type",
        "echo",
        "--domain",
        "system",
        "--payload",
        '{"message":"hello"}',
    )
    assert submit.returncode == 0, submit.stderr or submit.stdout
    assert "Job submitted:" in submit.stdout

    pending_echo = _db_count(
        db_path,
        "SELECT COUNT(*) FROM job_queue WHERE status='pending' AND job_type='echo'",
    )
    assert pending_echo == 1

    status = run_python_script(
        "scripts/queue_tools.py",
        "--db-path",
        str(db_path),
        "status",
    )
    assert status.returncode == 0, status.stderr or status.stdout
    assert "Paused:" in status.stdout
    assert "PENDING BY DOMAIN:" in status.stdout
    assert "system" in status.stdout


@pytest.mark.integration
def test_queue_dispatcher_dry_run_honors_db_path(tmp_path: Path, run_python_script) -> None:
    db_path = tmp_path / "queue.db"
    queue = JobQueue(db_path=db_path)
    queue.create_job(job_type="echo", domain="system", payload={"message": "dispatch"})

    config_path = tmp_path / "dispatch.json"
    config_path.write_text(
        json.dumps(
            {
                "agents": [
                    {
                        "persona": "echo",
                        "job_types": ["echo"],
                        "max_workers": 2,
                        "min_workers": 0,
                        "enabled": True,
                    }
                ]
            }
        )
    )

    dry_run = run_python_script(
        "scripts/queue_dispatcher.py",
        "--db-path",
        str(db_path),
        "--config",
        str(config_path),
        "--dry-run",
        "run",
    )
    assert dry_run.returncode == 0, dry_run.stderr or dry_run.stdout
    payload = json.loads(dry_run.stdout)
    assert payload["actions"]
    assert payload["actions"][0]["persona"] == "echo"
    assert payload["results"][0]["status"] == "dry_run"

    status = run_python_script(
        "scripts/queue_dispatcher.py",
        "--db-path",
        str(db_path),
        "--config",
        str(config_path),
        "status",
    )
    assert status.returncode == 0, status.stderr or status.stdout
    status_payload = json.loads(status.stdout)
    echo_row = next(row for row in status_payload if row["persona"] == "echo")
    assert echo_row["pending"] >= 1
