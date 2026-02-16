#!/usr/bin/env python3
"""
Queue management CLI (SQLite-first).

Usage:
  python scripts/queue_tools.py submit --type echo --domain system --payload '{"message":"hi"}'
  python scripts/queue_tools.py status
  python scripts/queue_tools.py list --status pending --limit 20
  python scripts/queue_tools.py show <job_id>
  python scripts/queue_tools.py pause --by "human"
  python scripts/queue_tools.py resume --by "human"
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from queue_system.queue import JobQueue


def _load_payload(payload_str: Optional[str], payload_file: Optional[str]) -> dict:
    if payload_file:
        raw = Path(payload_file).read_text()
        return json.loads(raw)
    if payload_str:
        return json.loads(payload_str)
    return {}


def cmd_submit(args):
    queue = JobQueue()
    payload = _load_payload(args.payload, args.payload_file)
    job_id = queue.create_job(
        job_type=args.type,
        domain=args.domain,
        payload=payload,
        priority=args.priority,
        created_by=args.created_by,
        scheduled_for=args.scheduled_for,
    )
    print(f"Job submitted: {job_id}")


def cmd_status(args):
    queue = JobQueue()
    paused = queue.is_paused()
    status_counts = queue.status_counts()
    domain_counts = queue.domain_counts()

    print(f"Paused: {'yes' if paused else 'no'}")
    print("\nSTATUS COUNTS:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status:<14} {count}")

    print("\nPENDING BY DOMAIN:")
    if not domain_counts:
        print("  (none)")
    else:
        for domain, count in sorted(domain_counts.items()):
            print(f"  {domain:<14} {count}")


def cmd_list(args):
    queue = JobQueue()
    jobs = queue.list_jobs(
        status=args.status,
        domain=args.domain,
        job_type=args.type,
        limit=args.limit,
    )
    for job in jobs:
        print(f"{job['id']}  {job['status']:<12} {job['job_type']:<18} {job['domain']:<14} {job['created_at']}")


def cmd_show(args):
    queue = JobQueue()
    job = queue.get_job(args.job_id)
    if not job:
        print("Job not found.")
        return
    print(json.dumps(job, indent=2, default=str))


def cmd_pause(args, paused: bool):
    queue = JobQueue()
    queue.set_paused(paused, updated_by=args.by)
    print(f"Paused set to {'true' if paused else 'false'}")


def main():
    parser = argparse.ArgumentParser(description="Queue management CLI")
    sub = parser.add_subparsers(dest="command")

    p_submit = sub.add_parser("submit", help="Submit a job")
    p_submit.add_argument("--type", required=True, help="Job type")
    p_submit.add_argument("--domain", required=True, help="Job domain")
    p_submit.add_argument("--payload", help="JSON payload")
    p_submit.add_argument("--payload-file", help="Path to JSON payload file")
    p_submit.add_argument("--priority", type=int, default=5, help="Priority 1-10")
    p_submit.add_argument("--created-by", help="Creator identifier")
    p_submit.add_argument("--scheduled-for", help="Schedule timestamp (YYYY-MM-DD HH:MM:SS)")
    p_submit.set_defaults(func=cmd_submit)

    p_status = sub.add_parser("status", help="Show queue status")
    p_status.set_defaults(func=cmd_status)

    p_list = sub.add_parser("list", help="List jobs")
    p_list.add_argument("--status", help="Filter by status")
    p_list.add_argument("--domain", help="Filter by domain")
    p_list.add_argument("--type", help="Filter by job type")
    p_list.add_argument("--limit", type=int, default=50, help="Max results")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="Show job details")
    p_show.add_argument("job_id", help="Job ID")
    p_show.set_defaults(func=cmd_show)

    p_pause = sub.add_parser("pause", help="Pause queue claiming")
    p_pause.add_argument("--by", help="Updated by")
    p_pause.set_defaults(func=lambda a: cmd_pause(a, True))

    p_resume = sub.add_parser("resume", help="Resume queue claiming")
    p_resume.add_argument("--by", help="Updated by")
    p_resume.set_defaults(func=lambda a: cmd_pause(a, False))

    args = parser.parse_args()
    if not getattr(args, "func", None):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
