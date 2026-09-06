#!/usr/bin/env python3
"""
Agent worker entry point for SQLite queue processing.
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def main():
    parser = argparse.ArgumentParser(description="Run an agent worker")
    parser.add_argument("--persona", required=True, help="Persona name (e.g. echo)")
    parser.add_argument("--id", dest="agent_id", help="Agent ID (defaults to persona)")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Poll interval seconds")
    parser.add_argument("--db-path", default=os.environ.get("ITHILDIN_DB_PATH") or str(PROJECT_ROOT / "investigation.db"))
    parser.add_argument("--profile", default=os.environ.get("ITHILDIN_PROFILE"), help="Pin the investigation profile")
    parser.add_argument("--reserved", action="store_true", help="Require a live dispatcher reservation")
    parser.add_argument("--heartbeat-seconds", type=int, default=90, help="Reservation validity in seconds")
    args = parser.parse_args()

    if args.heartbeat_seconds <= 0:
        parser.error("--heartbeat-seconds must be positive")
    os.environ["ITHILDIN_DB_PATH"] = str(Path(args.db_path).expanduser().resolve())
    if args.profile:
        from tools.investigation_context import load_profile

        try:
            load_profile(args.profile)
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        os.environ["ITHILDIN_PROFILE"] = args.profile

    # Pin the environment before importing workers and their tracker helpers.
    from queue_system.queue import JobQueue
    from queue_system.worker import WORKER_REGISTRY

    persona = args.persona
    agent_id = args.agent_id or f"{persona}-worker"

    worker_cls = WORKER_REGISTRY.get(persona)
    if not worker_cls:
        print(f"Unknown persona '{persona}'. Available: {', '.join(WORKER_REGISTRY)}")
        sys.exit(1)

    capabilities = worker_cls.JOB_TYPES or [persona]
    queue = JobQueue(db_path=Path(os.environ["ITHILDIN_DB_PATH"]))
    if args.reserved and not queue.register_agent(
        agent_id, persona, capabilities, require_reserved=True,
        heartbeat_seconds=args.heartbeat_seconds,
    ):
        parser.error("worker reservation expired or was retired; dispatch again")
    worker = worker_cls(
        queue=queue,
        agent_id=agent_id,
        persona=persona,
        capabilities=capabilities,
        poll_interval=args.poll_interval,
    )
    try:
        worker.run_forever()
    finally:
        queue.stop_agent(agent_id)


if __name__ == "__main__":
    main()
