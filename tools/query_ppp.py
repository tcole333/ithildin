#!/usr/bin/env python3
"""
SBA PPP/EIDL Loan query tool (DuckDB over Parquet).

~11M PPP loan records from SBA FOIA bulk download. Includes borrower name,
address, NAICS code, lender, jobs reported, loan amount, and forgiveness.

Data: https://data.sba.gov/dataset/ppp-foia
Convert: python scripts/convert_ppp_csv.py data/public_*.csv

Usage:
    python tools/query_ppp.py stats
    python tools/query_ppp.py search "Acme Corp"
    python tools/query_ppp.py borrower "EXACT BORROWER NAME"
    python tools/query_ppp.py address "123 Main St"
    python tools/query_ppp.py lender "JPMorgan Chase"
    python tools/query_ppp.py naics 541511
    python tools/query_ppp.py sql "SELECT * FROM ppp WHERE currentapprovalamount > 1000000 LIMIT 10"
"""

import argparse
import sys
from pathlib import Path

try:
    import duckdb
except ImportError:
    print("ERROR: duckdb required. Install: uv add duckdb", file=sys.stderr)
    sys.exit(1)

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PARQUET_PATH = DATA_DIR / "ppp_loans.parquet"


def _connect():
    """Return DuckDB connection with parquet registered as view."""
    if not PARQUET_PATH.exists():
        print(f"ERROR: {PARQUET_PATH} not found.", file=sys.stderr)
        print("Download PPP CSV from https://data.sba.gov/dataset/ppp-foia", file=sys.stderr)
        print("Then convert: python scripts/convert_ppp_csv.py data/public_*.csv", file=sys.stderr)
        sys.exit(1)
    con = duckdb.connect()
    con.execute(f"CREATE VIEW ppp AS SELECT * FROM read_parquet('{PARQUET_PATH}')")
    return con


def _fmt_money(val):
    if val is None:
        return "?"
    return f"${val:,.2f}" if val >= 0 else f"-${abs(val):,.2f}"


def _fmt_int(val):
    return f"{val:,}" if val is not None else "?"


# --- Commands ---

def cmd_stats(con):
    """Dataset summary."""
    r = con.execute("""
        SELECT
            count(*) as total_loans,
            sum(currentapprovalamount) as total_approved,
            sum(forgivenessAmount) as total_forgiven,
            avg(currentapprovalamount) as avg_loan,
            count(DISTINCT borrowername) as unique_borrowers,
            count(DISTINCT servicinglendername) as unique_lenders,
            count(DISTINCT naicscode) as unique_naics,
            min(dateapproved) as first_approval,
            max(dateapproved) as last_approval
        FROM ppp
    """).fetchone()

    return {
        "total_loans": r[0], "total_approved": r[1], "total_forgiven": r[2],
        "avg_loan": r[3], "unique_borrowers": r[4], "unique_lenders": r[5],
        "unique_naics": r[6], "first_approval": str(r[7]), "last_approval": str(r[8]),
    }


def _print_stats(s):
    print(f"\n  SBA PPP Loan Dataset")
    print(f"  {'='*50}")
    print(f"  Total Loans:       {_fmt_int(s['total_loans'])}")
    print(f"  Total Approved:    {_fmt_money(s['total_approved'])}")
    print(f"  Total Forgiven:    {_fmt_money(s['total_forgiven'])}")
    print(f"  Avg Loan:          {_fmt_money(s['avg_loan'])}")
    print(f"  Unique Borrowers:  {_fmt_int(s['unique_borrowers'])}")
    print(f"  Unique Lenders:    {_fmt_int(s['unique_lenders'])}")
    print(f"  NAICS Codes:       {_fmt_int(s['unique_naics'])}")
    print(f"  Period:            {s['first_approval']} to {s['last_approval']}")


def cmd_search(con, query, limit=50):
    """Search borrower names (case-insensitive contains)."""
    rows = con.execute("""
        SELECT borrowername, borroweraddress, borrowercity, borrowerstate, borrowerzip,
               currentapprovalamount, forgivenessAmount, dateapproved,
               servicinglendername, naicscode, jobsreported
        FROM ppp
        WHERE borrowername ILIKE ?
        ORDER BY currentapprovalamount DESC
        LIMIT ?
    """, (f"%{query}%", limit)).fetchall()

    cols = ["borrower", "address", "city", "state", "zip", "approved", "forgiven",
            "date_approved", "lender", "naics", "jobs"]
    records = [dict(zip(cols, r)) for r in rows]
    return {"query": query, "total": len(records), "records": records}


def _print_search(data):
    print(f"\n  PPP Loans matching '{data['query']}': {data['total']} results")
    print(f"  {'='*100}")
    for r in data["records"]:
        addr = ", ".join(filter(None, [r["address"], r["city"], r["state"], str(r["zip"] or "")]))
        print(f"  {r['borrower']}")
        print(f"    {addr}")
        print(f"    Approved: {_fmt_money(r['approved'])}  Forgiven: {_fmt_money(r['forgiven'])}  "
              f"Jobs: {r['jobs']}  NAICS: {r['naics']}  Lender: {r['lender']}")
        print(f"    Date: {r['date_approved']}")
        print()


def cmd_borrower(con, name, limit=20):
    """Exact borrower lookup with full detail."""
    rows = con.execute("""
        SELECT *
        FROM ppp
        WHERE borrowername ILIKE ?
        ORDER BY dateapproved DESC
        LIMIT ?
    """, (name, limit)).fetchall()

    cols = [desc[0] for desc in con.description]
    records = [dict(zip(cols, r)) for r in rows]
    return {"borrower": name, "total": len(records), "records": records}


def _print_borrower(data):
    print(f"\n  PPP Loans for '{data['borrower']}': {data['total']} records")
    print(f"  {'='*80}")
    for r in data["records"]:
        print(f"  Loan #{r.get('loannumber', '?')}")
        for k, v in r.items():
            if v is not None and str(v).strip():
                print(f"    {k}: {v}")
        print()


def cmd_address(con, addr, limit=50):
    """All PPP loans at an address (partial match)."""
    rows = con.execute("""
        SELECT borrowername, borroweraddress, borrowercity, borrowerstate, borrowerzip,
               currentapprovalamount, forgivenessAmount, dateapproved,
               servicinglendername, naicscode, jobsreported
        FROM ppp
        WHERE borroweraddress ILIKE ?
        ORDER BY currentapprovalamount DESC
        LIMIT ?
    """, (f"%{addr}%", limit)).fetchall()

    cols = ["borrower", "address", "city", "state", "zip", "approved", "forgiven",
            "date_approved", "lender", "naics", "jobs"]
    records = [dict(zip(cols, r)) for r in rows]
    return {"address": addr, "total": len(records), "records": records}


def _print_address(data):
    print(f"\n  PPP Loans at '{data['address']}': {data['total']} results")
    print(f"  {'='*100}")
    for r in data["records"]:
        print(f"  {r['borrower']}  ({r['city']}, {r['state']} {r['zip']})")
        print(f"    Approved: {_fmt_money(r['approved'])}  Forgiven: {_fmt_money(r['forgiven'])}  "
              f"Lender: {r['lender']}  NAICS: {r['naics']}")
        print()


def cmd_lender(con, name, limit=50):
    """All loans from a lender."""
    rows = con.execute("""
        SELECT borrowername, borroweraddress, borrowercity, borrowerstate,
               currentapprovalamount, forgivenessAmount, dateapproved, naicscode, jobsreported
        FROM ppp
        WHERE servicinglendername ILIKE ?
        ORDER BY currentapprovalamount DESC
        LIMIT ?
    """, (f"%{name}%", limit)).fetchall()

    cols = ["borrower", "address", "city", "state", "approved", "forgiven",
            "date_approved", "naics", "jobs"]
    records = [dict(zip(cols, r)) for r in rows]

    # Also get aggregate stats for this lender
    agg = con.execute("""
        SELECT count(*) as loan_count, sum(currentapprovalamount) as total_approved,
               sum(forgivenessAmount) as total_forgiven
        FROM ppp WHERE servicinglendername ILIKE ?
    """, (f"%{name}%",)).fetchone()

    return {
        "lender": name, "total": len(records),
        "loan_count": agg[0], "total_approved": agg[1], "total_forgiven": agg[2],
        "records": records,
    }


def _print_lender(data):
    print(f"\n  PPP Loans via '{data['lender']}' (showing {data['total']} of {_fmt_int(data['loan_count'])})")
    print(f"  Total approved: {_fmt_money(data['total_approved'])}  Forgiven: {_fmt_money(data['total_forgiven'])}")
    print(f"  {'='*100}")
    for r in data["records"]:
        print(f"  {r['borrower']}  ({r['city']}, {r['state']})")
        print(f"    Approved: {_fmt_money(r['approved'])}  Forgiven: {_fmt_money(r['forgiven'])}  "
              f"NAICS: {r['naics']}  Jobs: {r['jobs']}")
        print()


def cmd_naics(con, code, limit=50):
    """Loans by NAICS code."""
    rows = con.execute("""
        SELECT borrowername, borrowercity, borrowerstate,
               currentapprovalamount, forgivenessAmount, servicinglendername, jobsreported
        FROM ppp
        WHERE CAST(naicscode AS VARCHAR) LIKE ?
        ORDER BY currentapprovalamount DESC
        LIMIT ?
    """, (f"{code}%", limit)).fetchall()

    cols = ["borrower", "city", "state", "approved", "forgiven", "lender", "jobs"]
    records = [dict(zip(cols, r)) for r in rows]

    agg = con.execute("""
        SELECT count(*) as cnt, sum(currentapprovalamount) as total
        FROM ppp WHERE CAST(naicscode AS VARCHAR) LIKE ?
    """, (f"{code}%",)).fetchone()

    return {"naics": code, "total": len(records), "full_count": agg[0],
            "total_approved": agg[1], "records": records}


def _print_naics(data):
    print(f"\n  NAICS {data['naics']}: {_fmt_int(data['full_count'])} loans, {_fmt_money(data['total_approved'])} total")
    print(f"  Showing top {data['total']} by amount:")
    print(f"  {'='*90}")
    for r in data["records"]:
        print(f"  {r['borrower']}  ({r['city']}, {r['state']})  {_fmt_money(r['approved'])}  Lender: {r['lender']}")


def cmd_sql(con, query):
    """Ad-hoc DuckDB SQL (table: ppp)."""
    rows = con.execute(query).fetchall()
    cols = [desc[0] for desc in con.description]
    records = [dict(zip(cols, r)) for r in rows]
    return {"columns": cols, "total": len(records), "records": records}


def _print_sql(data):
    if not data["records"]:
        print("  No results")
        return
    cols = data["columns"]
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in data["records"])) for c in cols}
    header = "  ".join(f"{c:>{widths[c]}}" for c in cols)
    print(f"\n  {header}")
    print(f"  {'-' * len(header)}")
    for r in data["records"]:
        line = "  ".join(f"{str(r.get(c, '')):>{widths[c]}}" for c in cols)
        print(f"  {line}")
    print(f"\n  {data['total']} rows")


def main():
    parser = argparse.ArgumentParser(description="Query SBA PPP loan data (DuckDB/Parquet)")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("stats", help="Dataset summary")
    add_output_args(p)

    p = sub.add_parser("search", help="Search borrower names")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=50)
    add_output_args(p)

    p = sub.add_parser("borrower", help="Exact borrower lookup with full detail")
    p.add_argument("name")
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    p = sub.add_parser("address", help="All loans at an address")
    p.add_argument("addr")
    p.add_argument("--limit", type=int, default=50)
    add_output_args(p)

    p = sub.add_parser("lender", help="All loans from a lender")
    p.add_argument("name")
    p.add_argument("--limit", type=int, default=50)
    add_output_args(p)

    p = sub.add_parser("naics", help="Loans by NAICS industry code")
    p.add_argument("code")
    p.add_argument("--limit", type=int, default=50)
    add_output_args(p)

    p = sub.add_parser("sql", help="Ad-hoc SQL (table: ppp)")
    p.add_argument("query")
    add_output_args(p)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    con = _connect()

    handlers = {
        "stats": (lambda: cmd_stats(con), _print_stats, "PPP stats"),
        "search": (lambda: cmd_search(con, args.query, args.limit), _print_search,
                   lambda r: f"PPP search '{args.query}': {r['total']} results"),
        "borrower": (lambda: cmd_borrower(con, args.name, args.limit), _print_borrower,
                     lambda r: f"PPP borrower '{args.name}': {r['total']} records"),
        "address": (lambda: cmd_address(con, args.addr, args.limit), _print_address,
                    lambda r: f"PPP address '{args.addr}': {r['total']} results"),
        "lender": (lambda: cmd_lender(con, args.name, args.limit), _print_lender,
                   lambda r: f"PPP lender '{args.name}': {r['total']} results"),
        "naics": (lambda: cmd_naics(con, args.code, args.limit), _print_naics,
                  lambda r: f"NAICS {args.code}: {r['total']} results"),
        "sql": (lambda: cmd_sql(con, args.query), _print_sql, "PPP SQL"),
    }

    run_fn, print_fn, summary_fn = handlers[args.command]
    result = run_fn()
    summary = summary_fn(result) if callable(summary_fn) else summary_fn
    if not write_output(result, args, summary=summary):
        print_fn(result)


if __name__ == "__main__":
    main()
