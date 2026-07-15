#!/usr/bin/env python3
"""Run a bounded reporting-corpus discovery and ingestion update.

This is intentionally a runner, not a scheduler. It records each discovery run
inside the sidecar and can be called by an approved external automation later.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.epstein_reporting import DEFAULT_DB_PATH, connect


CONFIG = ROOT / "investigations" / "epstein" / "reporting_sources.yaml"
CLI = ROOT / "tools" / "reporting_corpus.py"


def run_command(*parts: str) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(CLI), *parts], cwd=ROOT,
        capture_output=True, text=True, check=False,
    )
    output = "\n".join(filter(None, [result.stdout.strip(), result.stderr.strip()]))
    return result.returncode == 0, output


def should_trip_gdelt_breaker(consecutive_errors: int, maximum: int) -> bool:
    return maximum > 0 and consecutive_errors >= maximum


def main() -> None:
    parser = argparse.ArgumentParser(description="Update the Epstein reporting corpus")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--skip-repository", action="store_true")
    parser.add_argument("--skip-seeds", action="store_true")
    parser.add_argument("--skip-pages", action="store_true")
    parser.add_argument("--skip-gdelt", action="store_true")
    parser.add_argument("--discover-wayback", action="store_true", help="Run configured publisher URL discovery through Wayback")
    parser.add_argument("--wayback-pattern", action="append", help="Archived URL term (repeatable; defaults to epstein and maxwell)")
    parser.add_argument("--wayback-max-domains", type=int, default=0)
    parser.add_argument("--max-queries", type=int, default=0, help="0 means all configured queries")
    parser.add_argument("--gdelt-limit", type=int, default=250)
    parser.add_argument("--gdelt-delay", type=float, default=6.0, help="Seconds between GDELT queries")
    parser.add_argument("--gdelt-max-consecutive-errors", type=int, default=3,
                        help="Stop GDELT after this many provider errors; 0 disables")
    parser.add_argument("--ingest-limit", type=int, default=50)
    parser.add_argument("--workers", type=int, default=1, help="Concurrent article fetches")
    parser.add_argument("--archive-limit", type=int, default=0, help="Recover this many failed candidates from public archives")
    parser.add_argument("--archive-provider", choices=["auto", "wayback", "commoncrawl"], default="auto")
    parser.add_argument("--store-text", action="store_true")
    parser.add_argument("--rights-status", choices=["metadata_only", "local_research", "redistributable", "unknown"], default="metadata_only")
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    db_args = ["--db", str(args.db)]
    steps: list[dict] = []

    ok, output = run_command("init", *db_args)
    steps.append({"step": "init", "ok": ok, "output": output})
    if not ok:
        print(json.dumps({"ok": False, "steps": steps}, indent=2))
        raise SystemExit(1)

    if not args.skip_repository:
        ok, output = run_command("discover-repository", "--config", str(args.config), *db_args)
        steps.append({"step": "repository", "ok": ok, "output": output})

    for seed in [] if args.skip_seeds else config.get("candidate_seed_files", []):
        seed_path = Path(seed)
        if not seed_path.is_absolute():
            seed_path = ROOT / seed_path
        ok, output = run_command(
            "discover-file", str(seed_path), "--source", "curated_seed", *db_args,
        )
        steps.append({"step": "candidate_seed", "path": str(seed_path), "ok": ok, "output": output})

    for page in [] if args.skip_pages else config.get("discovery_pages", []):
        command = ["discover-page", page["url"], *db_args]
        for query in page.get("queries", ["epstein", "maxwell"]):
            command.extend(["--query", query])
        if page.get("publisher"):
            command.extend(["--publisher", page["publisher"]])
        if page.get("language"):
            command.extend(["--language", page["language"]])
        if page.get("link_regex"):
            command.extend(["--link-regex", page["link_regex"]])
        ok, output = run_command(*command)
        steps.append({"step": "publisher_page", "url": page["url"], "ok": ok, "output": output})

    if args.discover_wayback:
        command = ["discover-wayback", "--config", str(args.config), *db_args]
        for pattern in args.wayback_pattern or ["epstein", "maxwell"]:
            command.extend(["--url-pattern", pattern])
        if args.wayback_max_domains:
            command.extend(["--max-domains", str(args.wayback_max_domains)])
        ok, output = run_command(*command)
        steps.append({"step": "wayback_discovery", "ok": ok, "output": output})

    if not args.skip_gdelt:
        queries = []
        for family in config.get("search_terms", {}).values():
            queries.extend(family)
        if args.max_queries:
            queries = queries[:args.max_queries]
        consecutive_gdelt_errors = 0
        for position, query in enumerate(queries):
            if position:
                time.sleep(args.gdelt_delay)
            ok, output = run_command(
                "discover-gdelt", query, "--limit", str(args.gdelt_limit), *db_args
            )
            steps.append({"step": "gdelt", "query": query, "ok": ok, "output": output})
            consecutive_gdelt_errors = 0 if ok else consecutive_gdelt_errors + 1
            if should_trip_gdelt_breaker(
                consecutive_gdelt_errors, args.gdelt_max_consecutive_errors,
            ):
                steps.append({
                    "step": "gdelt_circuit_breaker", "ok": True,
                    "output": (
                        f"Stopped after {consecutive_gdelt_errors} consecutive provider errors; "
                        "completed and failed queries are recorded and the run is resumable"
                    ),
                })
                break

    if args.ingest_limit:
        command = [
            "ingest-candidates", "--limit", str(args.ingest_limit),
            "--workers", str(args.workers), "--rights-status", args.rights_status, *db_args,
        ]
        if args.store_text:
            command.append("--store-text")
        ok, output = run_command(*command)
        steps.append({"step": "ingest", "ok": ok, "output": output})

    if args.archive_limit:
        command = [
            "recover-archives", "--failed-candidates", "--limit", str(args.archive_limit),
            "--provider", args.archive_provider, *db_args,
        ]
        if args.store_text:
            command.append("--store-text")
        ok, output = run_command(*command)
        steps.append({"step": "archive_recovery", "ok": ok, "output": output})

    ok, output = run_command("detect-duplicates", *db_args)
    steps.append({"step": "deduplicate", "ok": ok, "output": output})

    db = connect(args.db, create=False)
    counts = {
        "items": db.execute("SELECT COUNT(*) FROM reporting_item WHERE scope_class!='background'").fetchone()[0],
        "background_items": db.execute("SELECT COUNT(*) FROM reporting_item WHERE scope_class='background'").fetchone()[0],
        "claims": db.execute("SELECT COUNT(*) FROM reporting_claim").fetchone()[0],
        "pending_candidates": db.execute("SELECT COUNT(*) FROM discovery_candidate WHERE status='pending'").fetchone()[0],
        "failed_candidates": db.execute("SELECT COUNT(*) FROM discovery_candidate WHERE status='failed'").fetchone()[0],
        "archive_versions": db.execute("SELECT COUNT(*) FROM item_version WHERE archive_url IS NOT NULL").fetchone()[0],
        "primary_gaps": db.execute(
            """SELECT COUNT(*) FROM reporting_claim c WHERE c.verification_status IN
               ('reported_only','unresolved','partially_supported') AND NOT EXISTS
               (SELECT 1 FROM claim_source s WHERE s.claim_id=c.id AND s.is_primary=1)"""
        ).fetchone()[0],
    }
    result = {"ok": all(step["ok"] for step in steps), "counts": counts, "steps": steps}
    print(json.dumps(result, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
