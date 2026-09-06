#!/usr/bin/env python3
"""
Generic queue dispatcher for Ithildin agent workers.

Manages worker pools via job_queue and agent_instances tables with heartbeat
tracking. This is the generic execution plane — it manages HOW workers run.

See also: dispatcher.py (investigation-aware dispatcher) which decides WHAT
to run based on lead priorities, triage scheduler fields, and analysis
cooldowns. The two systems use separate tables and operate independently.
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "investigation.db"
CONFIG_PATH = Path(__file__).resolve().parent / "queue_dispatch_config.json"


def _connect(db_path: Path | None = None):
    target = db_path or os.environ.get("ITHILDIN_DB_PATH") or DB_PATH
    db = sqlite3.connect(str(target))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def load_config(path: Path) -> dict:
    return json.loads(path.read_text())


def get_pending_by_type(db: sqlite3.Connection) -> Dict[str, int]:
    rows = db.execute(
        "SELECT job_type, COUNT(*) as n FROM job_queue WHERE status='pending' GROUP BY job_type"
    ).fetchall()
    return {row["job_type"]: row["n"] for row in rows}


def get_active_agents(db: sqlite3.Connection, heartbeat_seconds: int) -> Dict[str, int]:
    rows = db.execute(
        """
        SELECT persona, COUNT(*) as n
        FROM agent_instances
        WHERE status='active'
          AND last_heartbeat >= datetime('now', ?)
        GROUP BY persona
        """,
        (f"-{heartbeat_seconds} seconds",),
    ).fetchall()
    return {row["persona"]: row["n"] for row in rows}


def is_paused(db: sqlite3.Connection) -> bool:
    try:
        row = db.execute("SELECT value FROM system_state WHERE key='paused'").fetchone()
        return row and row["value"] == "true"
    except sqlite3.OperationalError:
        return False


def compute_scale_actions(config: dict, pending_by_type: Dict[str, int], active_by_persona: Dict[str, int]) -> List[dict]:
    actions = []
    for agent in config.get("agents", []):
        if not agent.get("enabled", True):
            continue
        persona = agent["persona"]
        job_types = agent.get("job_types") or [persona]
        max_workers = int(agent.get("max_workers", 1))
        min_workers = int(agent.get("min_workers", 0))

        pending = sum(pending_by_type.get(jt, 0) for jt in job_types)
        active = active_by_persona.get(persona, 0)
        desired = min(max_workers, max(min_workers, pending))
        if desired > active:
            actions.append({"persona": persona, "spawn": desired - active, "pending": pending})
    return actions


def reserve_workers(
    config: dict, db_path: Path, heartbeat_seconds: int = 90
) -> tuple[List[dict], List[dict]]:
    """Count and reserve capacity in one transaction shared by all dispatchers."""
    if heartbeat_seconds <= 0:
        raise ValueError("heartbeat_seconds must be positive")
    db = _connect(db_path)
    try:
        db.execute("BEGIN IMMEDIATE")
        if is_paused(db):
            db.commit()
            return [], []
        # A retired worker cannot heartbeat, register again, or claim more jobs.
        db.execute(
            """
            UPDATE agent_instances SET status='stopped', current_job_id=NULL
            WHERE status='active' AND last_heartbeat < datetime('now', ?)
            """,
            (f"-{heartbeat_seconds} seconds",),
        )
        pending = get_pending_by_type(db)
        active = get_active_agents(db, heartbeat_seconds)
        actions = compute_scale_actions(config, pending, active)
        configurations = {agent["persona"]: agent for agent in config.get("agents", [])}
        reservations = []
        for action in actions:
            persona = action["persona"]
            capabilities = configurations[persona].get("job_types") or [persona]
            for _ in range(action["spawn"]):
                agent_id = f"{persona}-{uuid4().hex}"
                db.execute(
                    "INSERT INTO agent_instances (id, persona, capabilities) VALUES (?, ?, ?)",
                    (agent_id, persona, json.dumps(capabilities)),
                )
                reservations.append({"persona": persona, "agent_id": agent_id})
        db.commit()
        return actions, reservations
    finally:
        db.close()


def _release_reservation(db_path: Path, agent_id: str) -> None:
    db = _connect(db_path)
    try:
        db.execute(
            "UPDATE agent_instances SET status='stopped', current_job_id=NULL WHERE id=?",
            (agent_id,),
        )
        db.commit()
    finally:
        db.close()


def spawn_workers(
    actions: List[dict],
    config: dict,
    dry_run: bool,
    *,
    db_path: Path | None = None,
    heartbeat_seconds: int = 90,
    profile: str | None = None,
    reservations: List[dict] | None = None,
) -> List[dict]:
    target_db = Path(db_path or os.environ.get("ITHILDIN_DB_PATH") or DB_PATH).expanduser().resolve()
    profile = profile or os.environ.get("ITHILDIN_PROFILE")
    if dry_run:
        reservations = [
            {"persona": action["persona"], "agent_id": f"{action['persona']}-{uuid4().hex}"}
            for action in actions for _ in range(action["spawn"])
        ]
    elif reservations is None:
        _, reservations = reserve_workers(config, target_db, heartbeat_seconds)
    results = []
    for reservation in reservations:
        persona = reservation["persona"]
        agent_id = reservation["agent_id"]
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "agent_worker.py"),
            "--persona", persona,
            "--id", agent_id,
            "--db-path", str(target_db),
            "--reserved",
            "--heartbeat-seconds", str(heartbeat_seconds),
        ]
        if profile:
            cmd.extend(["--profile", profile])
        if dry_run:
            results.append({"persona": persona, "cmd": " ".join(cmd), "status": "dry_run"})
            continue
        env = os.environ.copy()
        env["ITHILDIN_DB_PATH"] = str(target_db)
        if profile:
            env["ITHILDIN_PROFILE"] = profile
        try:
            proc = subprocess.Popen(cmd, env=env, cwd=str(PROJECT_ROOT))
        except OSError as exc:
            _release_reservation(target_db, agent_id)
            results.append({"persona": persona, "agent_id": agent_id, "status": "failed", "error": str(exc)})
        else:
            results.append({"persona": persona, "pid": proc.pid, "agent_id": agent_id})
    return results


def cmd_run(args):
    db_path = Path(args.db_path)
    config = load_config(Path(args.config))
    reservations = None
    if args.dry_run:
        db = _connect(db_path)
        try:
            db.execute("BEGIN")
            if is_paused(db):
                print("System paused; no dispatch actions.")
                return
            pending = get_pending_by_type(db)
            active = get_active_agents(db, args.heartbeat_seconds)
            actions = compute_scale_actions(config, pending, active)
        finally:
            db.close()
    else:
        actions, reservations = reserve_workers(config, db_path, args.heartbeat_seconds)
    results = spawn_workers(
        actions, config, args.dry_run, db_path=db_path,
        heartbeat_seconds=args.heartbeat_seconds, profile=getattr(args, "profile", None),
        reservations=reservations,
    )
    print(json.dumps({"actions": actions, "results": results}, indent=2, default=str))


def cmd_daemon(args):
    while True:
        cmd_run(args)
        time.sleep(args.poll_interval)


def cmd_status(args):
    db = _connect(Path(args.db_path))
    try:
        pending = get_pending_by_type(db)
        active = get_active_agents(db, args.heartbeat_seconds)
    finally:
        db.close()
    config = load_config(Path(args.config))
    status = []
    for agent in config.get("agents", []):
        persona = agent["persona"]
        job_types = agent.get("job_types") or [persona]
        pending_count = sum(pending.get(jt, 0) for jt in job_types)
        status.append(
            {
                "persona": persona,
                "pending": pending_count,
                "active": active.get(persona, 0),
                "max_workers": agent.get("max_workers", 1),
                "min_workers": agent.get("min_workers", 0),
                "enabled": agent.get("enabled", True),
            }
        )
    print(json.dumps(status, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="Queue dispatcher for Ithildin")
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--db-path", default=os.environ.get("ITHILDIN_DB_PATH") or str(DB_PATH))
    parser.add_argument("--profile", default=os.environ.get("ITHILDIN_PROFILE"))
    parser.add_argument("--heartbeat-seconds", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="One-shot dispatch")
    p_run.set_defaults(func=cmd_run)

    p_daemon = sub.add_parser("daemon", help="Run dispatch loop")
    p_daemon.add_argument("--poll-interval", type=int, default=30)
    p_daemon.set_defaults(func=cmd_daemon)

    p_status = sub.add_parser("status", help="Show dispatch status")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
