#!/usr/bin/env python3
"""Agent-facing CLI over the temporal event index in epstein_derived.db.

Read-only queries against the `event` / `event_participant` / `event_evidence`
tables built by tools/build_temporal_events.py. Dates are stored as integer
epoch-day intervals [start_day_min, start_day_max] (+ optional end_day_*), so a
year-precision event spans its whole year — see tools/date_normalize.py.

Interval overlap test used by `near`/`window`:
    start_day_min <= window_end AND COALESCE(end_day_max, start_day_max) >= window_start

To pull the underlying page for an event's canonical_ref:
    uv run python tools/ingest_kabasshouse.py doc <canonical_ref>

Usage:
    uv run python tools/query_events.py near --date 2005-08-15 --window 30
    uv run python tools/query_events.py near --date 2005-08-15 --window 30 --type call,transaction
    uv run python tools/query_events.py near --date 2005-08-15 --window 7 --actor "EPSTEIN"
    uv run python tools/query_events.py window --start 2005-08-01 --end 2005-08-31
    uv run python tools/query_events.py stats --by-type
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from tools.epstein_derived import get_db  # noqa: E402
from tools.date_normalize import to_epoch_day  # noqa: E402

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output


def _fetch_events(db, where_sql, params, event_types=None, actor=None, limit=None):
    """Shared query: events matching an interval predicate + optional type/actor filters."""
    conditions = [where_sql]
    query_params = list(params)

    if event_types:
        placeholders = ", ".join("?" for _ in event_types)
        conditions.append(f"e.event_type IN ({placeholders})")
        query_params.extend(event_types)

    if actor:
        conditions.append("""
            EXISTS (
                SELECT 1 FROM event_participant ep
                WHERE ep.event_id = e.event_id AND ep.raw_name LIKE ?
            )
        """)
        query_params.append(f"%{actor}%")

    where_clause = " AND ".join(conditions)
    limit_clause = f"LIMIT {int(limit)}" if limit else ""

    rows = db.execute(f"""
        SELECT e.event_id, e.event_type, e.subtype, e.summary, e.date_raw,
               e.date_precision, e.start_day_min, e.start_day_max,
               e.end_day_min, e.end_day_max, e.time_local, e.location,
               e.amount_minor, e.date_confidence, e.assertion_kind
        FROM event e
        WHERE {where_clause}
        ORDER BY e.start_day_min
        {limit_clause}
    """, query_params).fetchall()

    events = []
    for r in rows:
        d = dict(r)
        d["participants"] = [
            dict(p) for p in db.execute("""
                SELECT raw_name, role, core_entity_id, derived_person_id, resolution_confidence
                FROM event_participant WHERE event_id = ?
            """, (d["event_id"],)).fetchall()
        ]
        d["evidence"] = [
            dict(ev) for ev in db.execute("""
                SELECT canonical_ref, evidence_item_id, source_locator
                FROM event_evidence WHERE event_id = ?
            """, (d["event_id"],)).fetchall()
        ]
        events.append(d)
    return events


def near(date_str, window_days, event_types=None, actor=None, limit=None):
    """Events whose interval overlaps [date - window, date + window]."""
    center = to_epoch_day(date_str)
    if center is None:
        raise ValueError(f"could not parse --date {date_str!r} as YYYY-MM-DD")
    lo, hi = center - window_days, center + window_days

    db = get_db()
    events = _fetch_events(
        db,
        "e.start_day_min <= ? AND COALESCE(e.end_day_max, e.start_day_max) >= ?",
        (hi, lo),
        event_types=event_types, actor=actor, limit=limit,
    )
    db.close()
    return {"reference_date": date_str, "window_days": window_days, "count": len(events), "events": events}


def window(start_str, end_str, event_types=None, actor=None, limit=None):
    """Events whose interval overlaps [start, end]."""
    lo, hi = to_epoch_day(start_str), to_epoch_day(end_str)
    if lo is None or hi is None:
        raise ValueError("could not parse --start/--end as YYYY-MM-DD")

    db = get_db()
    events = _fetch_events(
        db,
        "e.start_day_min <= ? AND COALESCE(e.end_day_max, e.start_day_max) >= ?",
        (hi, lo),
        event_types=event_types, actor=actor, limit=limit,
    )
    db.close()
    return {"start": start_str, "end": end_str, "count": len(events), "events": events}


def stats(by_type=False):
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM event").fetchone()[0]
    result = {"total_events": total}

    if by_type:
        by_type_counts = {
            row["event_type"]: row["n"] for row in db.execute("""
                SELECT event_type, COUNT(*) AS n FROM event
                GROUP BY event_type ORDER BY n DESC
            """)
        }
        result["by_type"] = by_type_counts

    row = db.execute("SELECT MIN(start_day_min) lo, MAX(start_day_max) hi FROM event").fetchone()
    result["earliest_day"] = row["lo"]
    result["latest_day"] = row["hi"]

    by_source = {
        (row["name"] or "unknown"): row["n"] for row in db.execute("""
            SELECT ss.name, COUNT(*) AS n FROM event e
            LEFT JOIN source_system ss ON ss.source_system_id = e.source_system_id
            GROUP BY ss.name ORDER BY n DESC
        """)
    }
    result["by_source_system"] = by_source

    db.close()
    return result


# ─────────────────────────── formatting ───────────────────────────

def _format_event(e):
    lines = []
    date_display = e["date_raw"] or "?"
    if e["date_precision"] and e["date_precision"] != "day":
        date_display += f" [{e['date_precision']}]"
    header = f"  #{e['event_id']}  {date_display}  ({e['event_type']}"
    if e.get("subtype"):
        header += f"/{e['subtype']}"
    header += ")"
    lines.append(header)
    if e.get("summary"):
        lines.append(f"      {e['summary']}")
    if e.get("location"):
        lines.append(f"      location: {e['location']}")
    if e.get("amount_minor") is not None:
        lines.append(f"      amount: {e['amount_minor'] / 100:,.2f}")
    if e.get("participants"):
        parts = ", ".join(f"{p['raw_name']} ({p['role']})" for p in e["participants"])
        lines.append(f"      participants: {parts}")
    if e.get("evidence"):
        refs = ", ".join(sorted({ev["canonical_ref"] for ev in e["evidence"] if ev["canonical_ref"]}))
        if refs:
            lines.append(f"      ref: {refs}")
    return "\n".join(lines)


def _split_types(raw):
    return [t.strip() for t in raw.split(",") if t.strip()] if raw else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command")

    p_near = sub.add_parser("near", help="Events within N days of a date")
    p_near.add_argument("--date", required=True, help="YYYY-MM-DD reference date")
    p_near.add_argument("--window", type=int, default=7, help="+/- days (default 7)")
    p_near.add_argument("--type", help="comma-separated event_type filter, e.g. call,transaction")
    p_near.add_argument("--actor", help="filter to events with a participant raw_name LIKE %%NAME%%")
    p_near.add_argument("--limit", type=int)
    add_output_args(p_near)

    p_win = sub.add_parser("window", help="Events overlapping a [start, end] range")
    p_win.add_argument("--start", required=True, help="YYYY-MM-DD")
    p_win.add_argument("--end", required=True, help="YYYY-MM-DD")
    p_win.add_argument("--type", help="comma-separated event_type filter")
    p_win.add_argument("--actor", help="filter to events with a participant raw_name LIKE %%NAME%%")
    p_win.add_argument("--limit", type=int)
    add_output_args(p_win)

    p_stats = sub.add_parser("stats", help="Row counts / date range / source breakdown")
    p_stats.add_argument("--by-type", action="store_true", help="include per-event_type counts")
    add_output_args(p_stats)

    args = parser.parse_args()

    if args.command == "near":
        try:
            result = near(args.date, args.window, event_types=_split_types(args.type),
                          actor=args.actor, limit=args.limit)
        except ValueError as exc:
            print(f"ERROR: {exc}")
            sys.exit(1)
        if getattr(args, "json_out", False):
            import json
            print(json.dumps(result, indent=2, default=str))
            return
        if write_output(result, args, summary=f"near {args.date} +/-{args.window}d"):
            return
        print(f"Events within {args.window} days of {args.date} ({result['count']}):")
        if not result["events"]:
            print("  (none)")
        for e in result["events"]:
            print(_format_event(e))

    elif args.command == "window":
        try:
            result = window(args.start, args.end, event_types=_split_types(args.type),
                            actor=args.actor, limit=args.limit)
        except ValueError as exc:
            print(f"ERROR: {exc}")
            sys.exit(1)
        if getattr(args, "json_out", False):
            import json
            print(json.dumps(result, indent=2, default=str))
            return
        if write_output(result, args, summary=f"window {args.start} to {args.end}"):
            return
        print(f"Events {args.start} to {args.end} ({result['count']}):")
        if not result["events"]:
            print("  (none)")
        for e in result["events"]:
            print(_format_event(e))

    elif args.command == "stats":
        result = stats(by_type=args.by_type)
        if getattr(args, "json_out", False):
            import json
            print(json.dumps(result, indent=2, default=str))
            return
        if write_output(result, args, summary="event stats"):
            return
        print("Temporal Event Index Statistics")
        print("=" * 40)
        print(f"  Total events: {result['total_events']:,}")
        if result.get("earliest_day") is not None:
            from datetime import date, timedelta
            epoch = date(1970, 1, 1)
            lo = epoch + timedelta(days=result["earliest_day"])
            hi = epoch + timedelta(days=result["latest_day"])
            print(f"  Date range:   {lo} to {hi}")
        if "by_type" in result:
            print("\n  By type:")
            for t, n in result["by_type"].items():
                print(f"    {t:<14} {n:>8,}")
        print("\n  By source system:")
        for s, n in result["by_source_system"].items():
            print(f"    {s:<14} {n:>8,}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
