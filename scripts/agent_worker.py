#!/usr/bin/env python3
"""
Agent worker entry point for SQLite queue processing.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from queue_system.queue import JobQueue
from queue_system.worker import WORKER_REGISTRY


def main():
    parser = argparse.ArgumentParser(description="Run an agent worker")
    parser.add_argument("--persona", required=True, help="Persona name (e.g. echo)")
    parser.add_argument("--id", dest="agent_id", help="Agent ID (defaults to persona)")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Poll interval seconds")
    args = parser.parse_args()

    persona = args.persona
    agent_id = args.agent_id or f"{persona}-worker"

    worker_cls = WORKER_REGISTRY.get(persona)
    if not worker_cls:
        print(f"Unknown persona '{persona}'. Available: {', '.join(WORKER_REGISTRY)}")
        sys.exit(1)

    capabilities = worker_cls.JOB_TYPES or [persona]
    queue = JobQueue()
    worker = worker_cls(
        queue=queue,
        agent_id=agent_id,
        persona=persona,
        capabilities=capabilities,
        poll_interval=args.poll_interval,
    )
    worker.run_forever()


if __name__ == "__main__":
    main()
