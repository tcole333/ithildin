#!/usr/bin/env python3
"""query_fin.py — agent-facing query surface over the normalized financial model.

Reads the financial tables in epstein_derived.db (built by build_financials.py)
and answers the questions an investigator actually asks: what moved near a date,
who a counterparty is, where spend went, capital flows, balances, positions,
flights, and the outlier review queue.

Amounts are stored as signed INTEGER minor units (cents) and printed as dollars.
By default, statement markers (is_structural) and collapsed duplicates
(is_duplicate_of) are excluded so counts reflect real activity, not artifacts.

Usage:
    uv run python tools/query_fin.py near-date 2019-03-07 --window 3
    uv run python tools/query_fin.py counterparty "Maxwell" --min-amount 10000
    uv run python tools/query_fin.py spend --group-by category
    uv run python tools/query_fin.py spend --cardholder "Epstein" --group-by merchant
    uv run python tools/query_fin.py flows --from "Epstein" --to "FIRSTBANK"
    uv run python tools/query_fin.py balances --owner "Southern"
    uv run python tools/query_fin.py positions --owner "Epstein"
    uv run python tools/query_fin.py flights --passenger "Maxwell"
    uv run python tools/query_fin.py review --outliers
Common flags: --limit N, --output FILE (write results), --json (JSON output).
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from tools.epstein_derived import DERIVED_DB  # noqa: E402
from tools.date_normalize import normalize_date, to_epoch_day  # noqa: E402

EPOCH = "1970-01-01"


def _db():
    db = sqlite3.connect(f"file:{DERIVED_DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def _dollars(minor):
    if minor is None:
        return "—"
    return f"${minor / 100:,.2f}"


def _day_to_iso(db, day):
    if day is None:
        return "—"
    row = db.execute("SELECT date(?, '+' || ? || ' days') AS d", (EPOCH, day)).fetchone()
    return row["d"] or "—"


# Default filters: exclude structural markers and collapsed duplicates.
# t.* qualified so it composes with queries that also join the merchant table.
_ACTIVE = ("t.is_duplicate_of IS NULL "
           "AND (t.merchant_id IS NULL OR t.merchant_id NOT IN "
           "(SELECT merchant_id FROM merchant WHERE is_structural=1))")


# ─────────────────────────── output formatting ───────────────────────────────

def _emit(rows, columns, args, title=None):
    """Print rows as an aligned table (or JSON), optionally to --output."""
    dict_rows = [dict(r) for r in rows]
    if args.json:
        text = json.dumps(dict_rows, indent=2, default=str)
    else:
        lines = []
        if title:
            lines.append(title)
        widths = {c: len(c) for c in columns}
        for r in dict_rows:
            for c in columns:
                widths[c] = max(widths[c], len(str(r.get(c, ""))))
        header = "  ".join(c.ljust(widths[c]) for c in columns)
        lines.append(header)
        lines.append("  ".join("-" * widths[c] for c in columns))
        for r in dict_rows:
            lines.append("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in columns))
        lines.append(f"\n({len(dict_rows)} rows)")
        text = "\n".join(lines)
    if args.output:
        Path(args.output).write_text(text)
        print(f"wrote {len(dict_rows)} rows -> {args.output}")
    else:
        print(text)


# ──────────────────────────────── commands ───────────────────────────────────

def cmd_near_date(db, args):
    iso, _p = normalize_date(args.date)
    if not iso:
        sys.exit(f"unparseable date: {args.date}")
    center = to_epoch_day(iso)
    lo, hi = center - args.window, center + args.window
    rows = db.execute(f"""
        SELECT t.transaction_id AS id,
               date(?, '+' || t.txn_day_min || ' days') AS date,
               t.amount_minor, t.direction, t.txn_type,
               COALESCE(m.canonical_name, t.counterparty_raw, t.cardholder_raw, '') AS party,
               ss.name AS source, t.canonical_ref, t.is_outlier
        FROM financial_transaction t
        LEFT JOIN merchant m ON m.merchant_id = t.merchant_id
        LEFT JOIN source_system ss ON ss.source_system_id = t.source_system_id
        WHERE t.txn_day_min BETWEEN ? AND ? AND {_ACTIVE}
        ORDER BY t.txn_day_min, ABS(t.amount_minor) DESC
        LIMIT ?
    """, (EPOCH, lo, hi, args.limit)).fetchall()
    out = [{"id": r["id"], "date": r["date"], "amount": _dollars(r["amount_minor"]),
            "direction": r["direction"] or "", "type": r["txn_type"] or "",
            "party": r["party"], "source": r["source"], "ref": r["canonical_ref"] or "",
            "outlier": "*" if r["is_outlier"] else ""}
           for r in rows]
    _emit(out, ["id", "date", "amount", "direction", "type", "party", "source", "ref", "outlier"],
          args, title=f"transactions within +/-{args.window}d of {iso}")


def cmd_counterparty(db, args):
    like = f"%{args.name}%"
    params = [like, like]
    amt_clause = ""
    if args.min_amount is not None:
        amt_clause = "AND ABS(t.amount_minor) >= ?"
        params.append(int(round(args.min_amount * 100)))
    params.append(args.limit)
    rows = db.execute(f"""
        SELECT t.transaction_id AS id,
               date(?, '+' || t.txn_day_min || ' days') AS date,
               t.amount_minor, t.direction, t.txn_type,
               COALESCE(t.counterparty_raw, t.cardholder_raw, '') AS party,
               ss.name AS source, t.canonical_ref
        FROM financial_transaction t
        LEFT JOIN source_system ss ON ss.source_system_id = t.source_system_id
        WHERE (t.counterparty_raw LIKE ? OR t.cardholder_raw LIKE ?)
          AND {_ACTIVE} {amt_clause}
        ORDER BY ABS(t.amount_minor) DESC
        LIMIT ?
    """, ([EPOCH] + params)).fetchall()
    out = [{"id": r["id"], "date": r["date"], "amount": _dollars(r["amount_minor"]),
            "direction": r["direction"] or "", "type": r["txn_type"] or "",
            "party": r["party"], "source": r["source"], "ref": r["canonical_ref"] or ""}
           for r in rows]
    _emit(out, ["id", "date", "amount", "direction", "type", "party", "source", "ref"],
          args, title=f"transactions where counterparty/cardholder LIKE '{args.name}'")


def cmd_spend(db, args):
    """Aggregate outflow (debits). Excludes structural markers; optional cardholder filter."""
    where = ["t.is_duplicate_of IS NULL",
             "(m.is_structural IS NULL OR m.is_structural = 0)",
             "t.amount_minor IS NOT NULL"]
    params = []
    if args.cardholder:
        where.append("t.cardholder_raw LIKE ?")
        params.append(f"%{args.cardholder}%")

    if args.group_by == "merchant":
        group_expr, label = "COALESCE(m.canonical_name, t.counterparty_raw, '(unknown)')", "merchant"
    else:  # category
        group_expr, label = "COALESCE(m.merchant_category, t.txn_type, '(uncategorized)')", "category"

    params.append(args.limit)
    rows = db.execute(f"""
        SELECT {group_expr} AS grp,
               COUNT(*) AS txns,
               SUM(CASE WHEN t.amount_minor < 0 THEN -t.amount_minor ELSE 0 END) AS outflow_minor,
               SUM(CASE WHEN t.amount_minor > 0 THEN t.amount_minor ELSE 0 END) AS inflow_minor
        FROM financial_transaction t
        LEFT JOIN merchant m ON m.merchant_id = t.merchant_id
        WHERE {' AND '.join(where)}
        GROUP BY grp
        ORDER BY outflow_minor DESC
        LIMIT ?
    """, params).fetchall()
    out = [{label: r["grp"], "txns": r["txns"],
            "outflow": _dollars(r["outflow_minor"]), "inflow": _dollars(r["inflow_minor"])}
           for r in rows]
    title = f"spend by {label}" + (f" for cardholder LIKE '{args.cardholder}'" if args.cardholder else "")
    _emit(out, [label, "txns", "outflow", "inflow"], args, title=title)


def cmd_flows(db, args):
    """Directed flows keyed by counterparty/cardholder text (--from / --to)."""
    where = [_ACTIVE, "t.amount_minor IS NOT NULL"]
    params = []
    if args.from_name:
        where.append("(t.cardholder_raw LIKE ? OR t.counterparty_raw LIKE ?)")
        params += [f"%{args.from_name}%", f"%{args.from_name}%"]
    if args.to_name:
        where.append("(t.counterparty_raw LIKE ? OR t.cardholder_raw LIKE ?)")
        params += [f"%{args.to_name}%", f"%{args.to_name}%"]
    params.append(args.limit)
    rows = db.execute(f"""
        SELECT COALESCE(t.cardholder_raw, '(acct)') AS src,
               COALESCE(t.counterparty_raw, '(unknown)') AS dst,
               t.direction,
               COUNT(*) AS txns,
               SUM(ABS(t.amount_minor)) AS total_minor
        FROM financial_transaction t
        WHERE {' AND '.join(where)}
        GROUP BY src, dst, t.direction
        ORDER BY total_minor DESC
        LIMIT ?
    """, params).fetchall()
    out = [{"from": r["src"], "to": r["dst"], "direction": r["direction"] or "",
            "txns": r["txns"], "total": _dollars(r["total_minor"])} for r in rows]
    _emit(out, ["from", "to", "direction", "txns", "total"], args, title="capital flows")


def cmd_balances(db, args):
    where, params = ["1=1"], []
    if args.owner:
        where.append("owner_raw LIKE ?")
        params.append(f"%{args.owner}%")
    params.append(args.limit)
    rows = db.execute(f"""
        SELECT owner_raw, date(?, '+' || as_of_day || ' days') AS as_of,
               balance_minor
        FROM balance_snapshot
        WHERE {' AND '.join(where)}
        ORDER BY as_of_day DESC
        LIMIT ?
    """, ([EPOCH] + params)).fetchall()
    out = [{"owner": r["owner_raw"], "as_of": r["as_of"], "balance": _dollars(r["balance_minor"])}
           for r in rows]
    title = "balances" + (f" for owner LIKE '{args.owner}'" if args.owner else "")
    _emit(out, ["owner", "as_of", "balance"], args, title=title)


def cmd_positions(db, args):
    where, params = ["1=1"], []
    if args.owner:
        where.append("p.owner_raw LIKE ?")
        params.append(f"%{args.owner}%")
    params.append(args.limit)
    rows = db.execute(f"""
        SELECT p.owner_raw, s.canonical_name AS security,
               date(?, '+' || p.as_of_day || ' days') AS as_of,
               p.market_value_minor, p.cost_basis_minor, p.is_outlier
        FROM position_snapshot p
        LEFT JOIN security s ON s.security_id = p.security_id
        WHERE {' AND '.join(where)}
        ORDER BY p.as_of_day DESC, ABS(COALESCE(p.market_value_minor,0)) DESC
        LIMIT ?
    """, ([EPOCH] + params)).fetchall()
    out = [{"owner": r["owner_raw"], "security": r["security"] or "", "as_of": r["as_of"],
            "market_value": _dollars(r["market_value_minor"]),
            "cost_basis": _dollars(r["cost_basis_minor"]),
            "outlier": "*" if r["is_outlier"] else ""} for r in rows]
    title = "positions" + (f" for owner LIKE '{args.owner}'" if args.owner else "")
    _emit(out, ["owner", "security", "as_of", "market_value", "cost_basis", "outlier"], args, title=title)


def cmd_flights(db, args):
    where, params = ["1=1"], []
    if args.passenger:
        where.append("passenger_raw LIKE ?")
        params.append(f"%{args.passenger}%")
    params.append(args.limit)
    rows = db.execute(f"""
        SELECT date(?, '+' || f.flight_day || ' days') AS flight_date,
               f.passenger_raw, f.airline, f.flight_number, f.origin, f.destination,
               f.ticket_cost_minor, f.record_locator, ei.canonical_ref
        FROM fin_flight f
        LEFT JOIN evidence_item ei ON ei.evidence_item_id = f.evidence_item_id
        WHERE {' AND '.join(where).replace('passenger_raw', 'f.passenger_raw')}
        ORDER BY f.flight_day DESC
        LIMIT ?
    """, ([EPOCH] + params)).fetchall()
    out = [{"date": r["flight_date"], "passenger": r["passenger_raw"] or "",
            "airline": r["airline"] or "", "flight": r["flight_number"] or "",
            "from": r["origin"] or "", "to": r["destination"] or "",
            "cost": _dollars(r["ticket_cost_minor"]), "locator": r["record_locator"] or "",
            "ref": r["canonical_ref"] or ""} for r in rows]
    title = "flights" + (f" for passenger LIKE '{args.passenger}'" if args.passenger else "")
    _emit(out, ["date", "passenger", "airline", "flight", "from", "to", "cost", "locator", "ref"],
          args, title=title)


def cmd_review(db, args):
    if not args.outliers:
        sys.exit("review: pass --outliers")
    rows = db.execute(f"""
        SELECT t.transaction_id AS id, ss.name AS source, t.source_native_id,
               date(?, '+' || t.txn_day_min || ' days') AS date,
               t.amount_minor, t.raw_amount,
               COALESCE(t.counterparty_raw, t.cardholder_raw, '') AS party,
               t.canonical_ref
        FROM financial_transaction t
        LEFT JOIN source_system ss ON ss.source_system_id = t.source_system_id
        WHERE t.is_outlier = 1
        ORDER BY ABS(COALESCE(t.amount_minor, 0)) DESC
        LIMIT ?
    """, (EPOCH, args.limit)).fetchall()
    out = [{"id": r["id"], "source": r["source"], "native_id": r["source_native_id"],
            "date": r["date"], "amount": _dollars(r["amount_minor"]),
            "raw_amount": r["raw_amount"] or "", "party": r["party"],
            "ref": r["canonical_ref"] or ""} for r in rows]
    _emit(out, ["id", "source", "native_id", "date", "amount", "raw_amount", "party", "ref"],
          args, title="outlier review queue (is_outlier=1)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_common(p):
        p.add_argument("--limit", type=int, default=50)
        p.add_argument("--output", help="write results to FILE instead of stdout")
        p.add_argument("--json", action="store_true", help="emit JSON")

    p = sub.add_parser("near-date", help="transactions within +/-N days of a date")
    p.add_argument("date")
    p.add_argument("--window", type=int, default=3)
    add_common(p)

    p = sub.add_parser("counterparty", help="transactions by counterparty/cardholder (LIKE)")
    p.add_argument("name")
    p.add_argument("--min-amount", type=float, help="min |amount| in dollars")
    add_common(p)

    p = sub.add_parser("spend", help="aggregate spend (excludes structural markers)")
    p.add_argument("--cardholder")
    p.add_argument("--group-by", choices=["category", "merchant"], default="category")
    add_common(p)

    p = sub.add_parser("flows", help="directed capital flows by party text")
    p.add_argument("--from", dest="from_name")
    p.add_argument("--to", dest="to_name")
    add_common(p)

    p = sub.add_parser("balances", help="balance snapshots")
    p.add_argument("--owner")
    add_common(p)

    p = sub.add_parser("positions", help="investment positions")
    p.add_argument("--owner")
    add_common(p)

    p = sub.add_parser("flights", help="travel flights")
    p.add_argument("--passenger")
    add_common(p)

    p = sub.add_parser("review", help="review queues")
    p.add_argument("--outliers", action="store_true", help="show flagged outliers")
    add_common(p)

    args = ap.parse_args()
    db = _db()
    dispatch = {
        "near-date": cmd_near_date, "counterparty": cmd_counterparty, "spend": cmd_spend,
        "flows": cmd_flows, "balances": cmd_balances, "positions": cmd_positions,
        "flights": cmd_flights, "review": cmd_review,
    }
    dispatch[args.cmd](db, args)
    db.close()


if __name__ == "__main__":
    main()
