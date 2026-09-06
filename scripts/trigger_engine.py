#!/usr/bin/env python3
"""
Trigger engine CLI for scheduled and threshold triggers.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from queue_system.queue import JobQueue  # noqa: E402 — bootstrap direct-script imports
from queue_system.triggers import DEFAULT_CONFIG_PATH, TriggerEngine  # noqa: E402


def _print_results(results):
    if not results:
        print("No triggers fired.")
        return
    print(json.dumps(results, indent=2, default=str))


def _engine(args) -> TriggerEngine:
    queue = JobQueue(db_path=Path(args.db_path))
    return TriggerEngine(queue, config_path=args.config, profile_id=args.profile)


def cmd_run_scheduled(args):
    engine = _engine(args)
    results = engine.run_scheduled(dry_run=args.dry_run)
    _print_results(results)


def cmd_run_thresholds(args):
    engine = _engine(args)
    results = engine.run_thresholds(dry_run=args.dry_run)
    _print_results(results)


def cmd_run(args):
    engine = _engine(args)
    results = []
    results.extend(engine.run_scheduled(dry_run=args.dry_run))
    results.extend(engine.run_thresholds(dry_run=args.dry_run))
    _print_results(results)


def cmd_daemon(args):
    engine = _engine(args)
    while True:
        results = []
        results.extend(engine.run_scheduled(dry_run=args.dry_run))
        results.extend(engine.run_thresholds(dry_run=args.dry_run))
        if results:
            _print_results(results)
        time.sleep(args.poll_interval)


def cmd_status(args):
    engine = _engine(args)
    runs = engine.list_runs(limit=args.limit, trigger_name=args.name)
    print(json.dumps(runs, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="Trigger engine")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to trigger config JSON",
    )
    parser.add_argument("--db-path", default=os.environ.get("ITHILDIN_DB_PATH", str(PROJECT_ROOT / "investigation.db")))
    parser.add_argument("--profile", help="Pin research triggers to this profile for the whole run or daemon lifetime")
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(dest="command")

    p_sched = sub.add_parser("run-scheduled", help="Run scheduled triggers")
    p_sched.set_defaults(func=cmd_run_scheduled)

    p_thresh = sub.add_parser("run-thresholds", help="Run threshold triggers")
    p_thresh.set_defaults(func=cmd_run_thresholds)

    p_run = sub.add_parser("run", help="Run scheduled + threshold triggers")
    p_run.set_defaults(func=cmd_run)

    p_daemon = sub.add_parser("daemon", help="Run triggers on a loop")
    p_daemon.add_argument("--poll-interval", type=int, default=60)
    p_daemon.set_defaults(func=cmd_daemon)

    p_status = sub.add_parser("status", help="Show recent trigger runs")
    p_status.add_argument("--limit", type=int, default=20)
    p_status.add_argument("--name", help="Filter by trigger name")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    if not getattr(args, "command", None):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
