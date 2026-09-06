#!/usr/bin/env python3
"""Read a profile-scoped status snapshot without initializing or modifying its DB."""

import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from tools.investigation_context import task_environment
    from tools.output_util import write_output
except ImportError:
    from investigation_context import task_environment
    from output_util import write_output


def collect_status(profile_id=None, db_path=None, *, recent_days=7, environ=None, now=None):
    """Return bounded aggregate metrics; absent schema is unavailable, never zero."""
    if recent_days < 1:
        raise ValueError("recent_days must be positive")
    environment = task_environment(profile_id, db_path, environ=environ)
    selected_db = Path(environment["ITHILDIN_DB_PATH"])
    selected_profile = environment["ITHILDIN_PROFILE"]
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must have a timezone")
    generated_at = now.astimezone(timezone.utc).isoformat()
    recent_since = (now - timedelta(days=recent_days)).astimezone(timezone.utc).isoformat()
    metrics = {}
    with sqlite3.connect(selected_db.as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only = ON")
        db.execute("BEGIN")
        tables = {
            row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if "investigation_profiles" not in tables:
            profile_validation = {
                "available": False,
                "reason": "missing table: investigation_profiles; profile membership is unverified",
            }
        elif "profile_id" not in {
            row[1] for row in db.execute('PRAGMA table_info("investigation_profiles")')
        }:
            profile_validation = {
                "available": False,
                "reason": "missing columns in investigation_profiles: profile_id; profile membership is unverified",
            }
        else:
            registered = db.execute(
                "SELECT 1 FROM investigation_profiles WHERE profile_id = ? LIMIT 1",
                (selected_profile,),
            ).fetchone()
            if registered is None:
                raise ValueError(f"Unknown investigation profile {selected_profile!r} in selected database")
            profile_validation = {"available": True, "registered": True}

        def metric(name, table, columns, expression, *, group_by=None, recent=False):
            required = {"profile_id", *columns}
            if table not in tables:
                metrics[name] = {"available": False, "reason": f"missing table: {table}"}
                return
            actual = {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}
            missing = required - actual
            if missing:
                metrics[name] = {
                    "available": False,
                    "reason": f"missing columns in {table}: {', '.join(sorted(missing))}",
                }
                return
            query = f'SELECT {expression} FROM "{table}" WHERE profile_id = ?'
            values = [selected_profile]
            if recent:
                query += " AND julianday(created_at) >= julianday(?) AND julianday(created_at) <= julianday(?)"
                values.extend([recent_since, generated_at])
            if group_by:
                query += f" GROUP BY {group_by} ORDER BY {group_by}"
            rows = db.execute(query, values).fetchall()
            value = (
                [{group_by: row[0], "count": row[1]} for row in rows]
                if group_by else rows[0][0]
            )
            metrics[name] = {"available": True, "value": value}

        metric("lead_count", "leads", [], "COUNT(*)")
        metric("leads_by_status", "leads", ["status"], "status, COUNT(*)", group_by="status")
        metric("findings_count", "findings", [], "COUNT(*)")
        metric(
            "findings_by_confidence", "findings", ["confidence"],
            "confidence, COUNT(*)", group_by="confidence",
        )
        metric("recent_findings_count", "findings", ["created_at"], "COUNT(*)", recent=True)
        metric("latest_finding_at", "findings", ["created_at"], "MAX(datetime(created_at))")
        metric("analysis_runs_count", "analysis_runs", [], "COUNT(*)")
        metric(
            "analysis_runs_by_status", "analysis_runs", ["status"],
            "status, COUNT(*)", group_by="status",
        )
        metric("latest_analysis_at", "analysis_runs", ["started_at"], "MAX(datetime(started_at))")
    return {
        "schema_version": "investigation-status/1",
        "status": (
            "ok" if profile_validation["available"]
            and all(item["available"] for item in metrics.values()) else "partial"
        ),
        "generated_at": generated_at,
        "profile_id": selected_profile,
        "profile_validation": profile_validation,
        "db_path": str(selected_db),
        "recent_since": recent_since,
        "metrics": metrics,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", help="Profile ID; otherwise inherit the pinned/default context")
    parser.add_argument("--db", help="Selected database; otherwise inherit ITHILDIN_DB_PATH")
    parser.add_argument("--output", help="Write JSON snapshot to this file")
    parser.add_argument("--recent-days", type=int, default=7, help="Recent findings window (default: 7)")
    args = parser.parse_args(argv)
    try:
        # Resolve once, and protect the selected DB from an accidental output overwrite.
        environment = task_environment(args.profile, args.db)
        if args.output:
            output = Path(args.output).expanduser().resolve()
            selected_db = Path(environment["ITHILDIN_DB_PATH"])
            protected = [selected_db, *(
                Path(str(selected_db) + suffix) for suffix in ("-wal", "-shm", "-journal")
            )]
            if any(
                output == item or (output.exists() and item.exists() and output.samefile(item))
                for item in protected
            ):
                raise ValueError("output must not overwrite the selected database or its sidecars")
            args.output = str(output)
        result = collect_status(recent_days=args.recent_days, environ=environment)
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(2, f"investigation status unavailable: {exc}\n")
    if not write_output(result, args, summary=f"status for {result['profile_id']}"):
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
