#!/usr/bin/env python3
"""
Query interface for the IRS 990 Bulk Grant Database.

Searches grants and related organizations across all US nonprofit e-filings
(2009-2024) stored in datasets/irs990_grants.db.

Usage:
    python tools/query_990_bulk.py search "Epstein"
    python tools/query_990_bulk.py filer 660789697
    python tools/query_990_bulk.py recipient "Gratitude"
    python tools/query_990_bulk.py recipient-ein 030213226
    python tools/query_990_bulk.py network 660789697 --depth 2
    python tools/query_990_bulk.py co-grantors "MELANOMA RESEARCH ALLIANCE"
    python tools/query_990_bulk.py cross-ref
    python tools/query_990_bulk.py top --by amount --limit 20
"""

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

DB_PATH = Path(__file__).parent.parent / "datasets" / "irs990_grants.db"
INVESTIGATION_DB = Path(__file__).parent.parent / "investigation.db"


def get_db():
    if not DB_PATH.exists():
        print(f"Error: {DB_PATH} not found. Run: ingest_990_bulk.py download-index → process", file=sys.stderr)
        sys.exit(1)
    db = sqlite3.connect(str(DB_PATH), timeout=30)
    db.row_factory = sqlite3.Row
    return db


def _has_fts():
    """Check if FTS5 tables exist."""
    db = get_db()
    try:
        db.execute("SELECT COUNT(*) FROM grants_fts LIMIT 1")
        db.close()
        return True
    except sqlite3.OperationalError:
        db.close()
        return False


def _fmt_amount(amt):
    if amt is None:
        return "$0"
    return f"${amt:,.0f}"


# ── search ──────────────────────────────────────────────────────

def cmd_search(args):
    """Full-text search across grants and related orgs."""
    db = get_db()
    query = args.query
    limit = args.limit

    # Try FTS5 first, fall back to LIKE
    fts = _has_fts()
    grants = []
    related = []

    if fts:
        # FTS5 search
        rows = db.execute("""
            SELECT g.* FROM grants g
            JOIN grants_fts ON grants_fts.rowid = g.id
            WHERE grants_fts MATCH ?
            ORDER BY g.cash_amount DESC
            LIMIT ?
        """, (query, limit)).fetchall()
        grants = [dict(r) for r in rows]

        rows = db.execute("""
            SELECT r.* FROM related_orgs r
            JOIN related_orgs_fts ON related_orgs_fts.rowid = r.id
            WHERE related_orgs_fts MATCH ?
            LIMIT ?
        """, (query, limit)).fetchall()
        related = [dict(r) for r in rows]
    else:
        # LIKE fallback
        pattern = f"%{query}%"
        rows = db.execute("""
            SELECT * FROM grants
            WHERE filer_name LIKE ? OR recipient_name LIKE ?
                OR purpose LIKE ? OR filer_ein LIKE ? OR recipient_ein LIKE ?
            ORDER BY cash_amount DESC
            LIMIT ?
        """, (pattern, pattern, pattern, pattern, pattern, limit)).fetchall()
        grants = [dict(r) for r in rows]

        rows = db.execute("""
            SELECT * FROM related_orgs
            WHERE filer_name LIKE ? OR related_name LIKE ?
                OR primary_activities LIKE ? OR filer_ein LIKE ? OR related_ein LIKE ?
            LIMIT ?
        """, (pattern, pattern, pattern, pattern, pattern, limit)).fetchall()
        related = [dict(r) for r in rows]

    print(f"\nSearch '{query}': {len(grants)} grants, {len(related)} related orgs" +
          ("" if fts else " (no FTS — using LIKE, run build-fts for faster search)"))

    if grants:
        print(f"\n  GRANTS ({len(grants)}):")
        for g in grants[:30]:
            print(f"    {g.get('tax_year', '?'):>5}  {_fmt_amount(g.get('cash_amount')):>14}  "
                  f"{g.get('filer_name', '?')[:30]:30s} → {g.get('recipient_name', '?')[:40]}")

    if related:
        print(f"\n  RELATED ORGS ({len(related)}):")
        for r in related[:20]:
            print(f"    {r.get('tax_year', '?'):>5}  [{r.get('relationship_type', ''):20s}] "
                  f"{r.get('filer_name', '?')[:30]:30s} ↔ {r.get('related_name', '?')[:40]}")

    results = {"grants": grants, "related_orgs": related}
    write_output(results, args, summary=f"990 bulk search '{query}'")
    db.close()


# ── filer ───────────────────────────────────────────────────────

def cmd_filer(args):
    """List all grants made by a filer EIN."""
    db = get_db()
    ein = args.ein.replace("-", "")

    rows = db.execute("""
        SELECT * FROM grants
        WHERE filer_ein = ? OR filer_ein = ?
        ORDER BY tax_year DESC, cash_amount DESC
    """, (ein, args.ein)).fetchall()
    results = [dict(r) for r in rows]

    total = sum(r.get("cash_amount", 0) or 0 for r in results)
    filer_name = results[0]["filer_name"] if results else ein

    print(f"\nGrants by {filer_name} (EIN {ein}): {len(results)} grants, {_fmt_amount(total)} total")
    for g in results[:50]:
        print(f"  {g.get('tax_year', '?'):>5}  {_fmt_amount(g.get('cash_amount')):>14}  "
              f"→ {g.get('recipient_name', '?')[:50]}"
              + (f"  ({g.get('recipient_ein')})" if g.get("recipient_ein") else ""))

    if len(results) > 50:
        print(f"  ... and {len(results) - 50} more (use --output to see all)")

    write_output(results, args, summary=f"990 grants by EIN {ein}")
    db.close()


# ── recipient ───────────────────────────────────────────────────

def cmd_recipient(args):
    """Find grants received by name (FTS5 or LIKE)."""
    db = get_db()
    name = args.name
    limit = args.limit

    fts = _has_fts()
    if fts:
        rows = db.execute("""
            SELECT g.* FROM grants g
            JOIN grants_fts ON grants_fts.rowid = g.id
            WHERE grants_fts.recipient_name MATCH ?
            ORDER BY g.cash_amount DESC
            LIMIT ?
        """, (name, limit)).fetchall()
    else:
        rows = db.execute("""
            SELECT * FROM grants
            WHERE recipient_name LIKE ?
            ORDER BY cash_amount DESC
            LIMIT ?
        """, (f"%{name}%", limit)).fetchall()

    results = [dict(r) for r in rows]
    total = sum(r.get("cash_amount", 0) or 0 for r in results)

    print(f"\nGrants to '{name}': {len(results)} grants, {_fmt_amount(total)} total")
    for g in results[:50]:
        print(f"  {g.get('tax_year', '?'):>5}  {_fmt_amount(g.get('cash_amount')):>14}  "
              f"← {g.get('filer_name', '?')[:40]:40s} ({g.get('filer_ein', '?')})")

    write_output(results, args, summary=f"990 grants to '{name}'")
    db.close()


# ── recipient-ein ───────────────────────────────────────────────

def cmd_recipient_ein(args):
    """Find all grants received by a specific EIN."""
    db = get_db()
    ein = args.ein.replace("-", "")

    rows = db.execute("""
        SELECT * FROM grants
        WHERE recipient_ein = ? OR recipient_ein = ?
        ORDER BY tax_year DESC, cash_amount DESC
    """, (ein, args.ein)).fetchall()
    results = [dict(r) for r in rows]
    total = sum(r.get("cash_amount", 0) or 0 for r in results)

    recip_name = results[0]["recipient_name"] if results else ein
    unique_funders = len(set(r["filer_ein"] for r in results if r.get("filer_ein")))

    print(f"\nGrants to {recip_name} (EIN {ein}): {len(results)} grants from {unique_funders} funders, {_fmt_amount(total)} total")
    for g in results[:50]:
        print(f"  {g.get('tax_year', '?'):>5}  {_fmt_amount(g.get('cash_amount')):>14}  "
              f"← {g.get('filer_name', '?')[:40]:40s} ({g.get('filer_ein', '?')})")

    write_output(results, args, summary=f"990 grants to EIN {ein}")
    db.close()


# ── network ─────────────────────────────────────────────────────

def cmd_network(args):
    """BFS grant network from a seed EIN.

    Depth 1: seed's recipients.
    Depth 2: who else funds seed's recipients (co-grantors).
    Depth 3+: repeat.
    """
    db = get_db()
    seed_ein = args.ein.replace("-", "")
    max_depth = args.depth
    limit = args.limit

    visited_eins = set()
    edges = []  # (filer_ein, filer_name, recipient_ein, recipient_name, total_amount, grant_count)
    frontier = {seed_ein}

    for depth in range(1, max_depth + 1):
        if not frontier:
            break
        new_frontier = set()

        for ein in frontier:
            if ein in visited_eins:
                continue
            visited_eins.add(ein)

            if depth % 2 == 1:
                # Odd depth: find recipients of this filer
                rows = db.execute("""
                    SELECT recipient_ein, recipient_name,
                           SUM(cash_amount) as total, COUNT(*) as cnt
                    FROM grants
                    WHERE (filer_ein = ?) AND recipient_ein != ''
                    GROUP BY recipient_ein
                    ORDER BY total DESC
                    LIMIT ?
                """, (ein, limit)).fetchall()
                for r in rows:
                    edges.append({
                        "filer_ein": ein,
                        "recipient_ein": r["recipient_ein"],
                        "recipient_name": r["recipient_name"],
                        "total_amount": r["total"],
                        "grant_count": r["cnt"],
                        "depth": depth,
                        "direction": "outgoing",
                    })
                    if r["recipient_ein"] not in visited_eins:
                        new_frontier.add(r["recipient_ein"])
            else:
                # Even depth: find funders of this recipient
                rows = db.execute("""
                    SELECT filer_ein, filer_name,
                           SUM(cash_amount) as total, COUNT(*) as cnt
                    FROM grants
                    WHERE (recipient_ein = ?) AND filer_ein != ''
                    GROUP BY filer_ein
                    ORDER BY total DESC
                    LIMIT ?
                """, (ein, limit)).fetchall()
                for r in rows:
                    edges.append({
                        "filer_ein": r["filer_ein"],
                        "filer_name": r["filer_name"],
                        "recipient_ein": ein,
                        "total_amount": r["total"],
                        "grant_count": r["cnt"],
                        "depth": depth,
                        "direction": "incoming",
                    })
                    if r["filer_ein"] not in visited_eins:
                        new_frontier.add(r["filer_ein"])

        frontier = new_frontier
        print(f"  Depth {depth}: {len(edges)} edges, {len(frontier)} new EINs to explore")

    print(f"\nNetwork from EIN {seed_ein} (depth {max_depth}): {len(edges)} edges, {len(visited_eins)} nodes")
    for e in edges[:40]:
        direction = "→" if e["direction"] == "outgoing" else "←"
        name = e.get("recipient_name") or e.get("filer_name") or "?"
        other_ein = e["recipient_ein"] if e["direction"] == "outgoing" else e["filer_ein"]
        print(f"  d{e['depth']} {direction} {_fmt_amount(e['total_amount']):>14} ({e['grant_count']}x)  "
              f"{other_ein} {name[:40]}")

    result = {"seed_ein": seed_ein, "depth": max_depth, "edges": edges, "nodes_visited": len(visited_eins)}
    write_output(result, args, summary=f"990 network from {seed_ein}")
    db.close()


# ── co-grantors ─────────────────────────────────────────────────

def cmd_co_grantors(args):
    """Find foundations that fund the same recipient."""
    db = get_db()
    name = args.name
    limit = args.limit

    # First find the recipient's EIN (if available)
    fts = _has_fts()
    if fts:
        recipients = db.execute("""
            SELECT DISTINCT g.recipient_ein, g.recipient_name FROM grants g
            JOIN grants_fts ON grants_fts.rowid = g.id
            WHERE grants_fts.recipient_name MATCH ?
        """, (name,)).fetchall()
    else:
        recipients = db.execute("""
            SELECT DISTINCT recipient_ein, recipient_name FROM grants
            WHERE recipient_name LIKE ?
        """, (f"%{name}%",)).fetchall()

    if not recipients:
        print(f"No recipients found matching '{name}'")
        db.close()
        return

    # Collect EINs and names
    target_eins = list(set(r["recipient_ein"] for r in recipients if r["recipient_ein"]))
    target_names = list(set(r["recipient_name"] for r in recipients if r["recipient_name"]))
    display_name = recipients[0]["recipient_name"]

    print(f"\nCo-grantors of '{display_name}'"
          + (f" (EIN(s): {', '.join(target_eins[:3])})" if target_eins else "")
          + f" ({len(target_names)} name variant(s)):")

    # Find all funders — by EIN if available, otherwise by name
    if target_eins:
        placeholders = ",".join("?" for _ in target_eins)
        rows = db.execute(f"""
            SELECT filer_ein, filer_name,
                   SUM(cash_amount) as total, COUNT(*) as cnt,
                   MIN(tax_year) as first_year, MAX(tax_year) as last_year
            FROM grants
            WHERE recipient_ein IN ({placeholders}) AND filer_ein != ''
            GROUP BY filer_ein
            ORDER BY total DESC
            LIMIT ?
        """, target_eins + [limit]).fetchall()
    else:
        # Fall back to name matching (common for 990-PF which lacks recipient EINs)
        name_conditions = " OR ".join("recipient_name = ?" for _ in target_names)
        rows = db.execute(f"""
            SELECT filer_ein, filer_name,
                   SUM(cash_amount) as total, COUNT(*) as cnt,
                   MIN(tax_year) as first_year, MAX(tax_year) as last_year
            FROM grants
            WHERE ({name_conditions}) AND filer_ein != ''
            GROUP BY filer_ein
            ORDER BY total DESC
            LIMIT ?
        """, target_names + [limit]).fetchall()
    results = [dict(r) for r in rows]

    for r in results:
        print(f"  {_fmt_amount(r['total']):>14} ({r['cnt']}x, {r.get('first_year','?')}-{r.get('last_year','?')})  "
              f"{r.get('filer_name', '?')[:45]:45s} ({r['filer_ein']})")

    write_output(results, args, summary=f"990 co-grantors of '{name}'")
    db.close()


# ── cross-ref ───────────────────────────────────────────────────

def cmd_cross_ref(args):
    """Match investigation.db entities against the bulk grant database."""
    if not INVESTIGATION_DB.exists():
        print("Error: investigation.db not found", file=sys.stderr)
        sys.exit(1)

    inv_db = sqlite3.connect(str(INVESTIGATION_DB))
    inv_db.row_factory = sqlite3.Row

    # Get all entity names and EINs from investigation
    entities = inv_db.execute("""
        SELECT id, name, ein FROM entities WHERE name IS NOT NULL
    """).fetchall()
    inv_db.close()

    if not entities:
        print("No entities in investigation.db")
        return

    db = get_db()
    matches = []

    print(f"Cross-referencing {len(entities)} investigation entities against bulk grants...")

    for ent in entities:
        name = ent["name"]
        ein = ent["ein"]
        entity_id = ent["id"]

        # Search by EIN first (exact)
        if ein:
            clean_ein = ein.replace("-", "")
            as_filer = db.execute("""
                SELECT filer_ein, COUNT(*) as cnt, SUM(cash_amount) as total
                FROM grants WHERE filer_ein = ?
                GROUP BY filer_ein
            """, (clean_ein,)).fetchone()
            if as_filer and as_filer["cnt"]:
                matches.append({
                    "entity_id": entity_id,
                    "entity_name": name,
                    "ein": clean_ein,
                    "role": "filer",
                    "grant_count": as_filer["cnt"],
                    "total_amount": as_filer["total"],
                })

            as_recipient = db.execute("""
                SELECT recipient_ein, COUNT(*) as cnt, SUM(cash_amount) as total
                FROM grants WHERE recipient_ein = ?
                GROUP BY recipient_ein
            """, (clean_ein,)).fetchone()
            if as_recipient and as_recipient["cnt"]:
                matches.append({
                    "entity_id": entity_id,
                    "entity_name": name,
                    "ein": clean_ein,
                    "role": "recipient",
                    "grant_count": as_recipient["cnt"],
                    "total_amount": as_recipient["total"],
                })

        # Name search (LIKE — slower but catches non-EIN matches)
        if name and len(name) > 3:
            as_filer_name = db.execute("""
                SELECT filer_name, filer_ein, COUNT(*) as cnt, SUM(cash_amount) as total
                FROM grants WHERE filer_name LIKE ?
                GROUP BY filer_ein
                LIMIT 5
            """, (f"%{name}%",)).fetchall()
            for r in as_filer_name:
                if r["cnt"]:
                    matches.append({
                        "entity_id": entity_id,
                        "entity_name": name,
                        "matched_name": r["filer_name"],
                        "ein": r["filer_ein"],
                        "role": "filer (name match)",
                        "grant_count": r["cnt"],
                        "total_amount": r["total"],
                    })

    # Deduplicate
    seen = set()
    unique = []
    for m in matches:
        key = (m.get("ein", ""), m["role"], m["entity_id"])
        if key not in seen:
            seen.add(key)
            unique.append(m)

    unique.sort(key=lambda x: x.get("total_amount", 0) or 0, reverse=True)

    print(f"\n{len(unique)} matches found:")
    for m in unique[:40]:
        print(f"  {m['entity_name'][:30]:30s} {m['role']:20s} "
              f"{_fmt_amount(m.get('total_amount')):>14} ({m.get('grant_count', 0)} grants)  "
              f"EIN={m.get('ein', '?')}")

    write_output(unique, args, summary="990 bulk cross-ref")
    db.close()


# ── top ─────────────────────────────────────────────────────────

def cmd_top(args):
    """Top grantmakers or recipients by amount or count."""
    db = get_db()
    by = args.by
    limit = args.limit

    if by == "amount":
        # Top grantmakers by total amount
        rows = db.execute("""
            SELECT filer_ein, filer_name,
                   SUM(cash_amount) as total, COUNT(*) as cnt,
                   COUNT(DISTINCT recipient_ein) as unique_recipients,
                   MIN(tax_year) as first_year, MAX(tax_year) as last_year
            FROM grants
            WHERE filer_ein != ''
            GROUP BY filer_ein
            ORDER BY total DESC
            LIMIT ?
        """, (limit,)).fetchall()
        results = [dict(r) for r in rows]
        print(f"\nTop {limit} grantmakers by total amount:")
        for r in results:
            print(f"  {_fmt_amount(r['total']):>16}  {r['cnt']:>6} grants  "
                  f"{r.get('unique_recipients', '?'):>5} recipients  "
                  f"{r.get('first_year', '?')}-{r.get('last_year', '?')}  "
                  f"{r.get('filer_name', '?')[:40]}  ({r['filer_ein']})")

    elif by == "count":
        # Top by grant count
        rows = db.execute("""
            SELECT filer_ein, filer_name,
                   SUM(cash_amount) as total, COUNT(*) as cnt
            FROM grants
            WHERE filer_ein != ''
            GROUP BY filer_ein
            ORDER BY cnt DESC
            LIMIT ?
        """, (limit,)).fetchall()
        results = [dict(r) for r in rows]
        print(f"\nTop {limit} grantmakers by grant count:")
        for r in results:
            print(f"  {r['cnt']:>6} grants  {_fmt_amount(r['total']):>16}  "
                  f"{r.get('filer_name', '?')[:40]}  ({r['filer_ein']})")

    elif by == "recipients":
        # Top recipients by total received
        rows = db.execute("""
            SELECT recipient_ein, recipient_name,
                   SUM(cash_amount) as total, COUNT(*) as cnt,
                   COUNT(DISTINCT filer_ein) as unique_funders
            FROM grants
            WHERE recipient_name != ''
            GROUP BY COALESCE(NULLIF(recipient_ein, ''), recipient_name)
            ORDER BY total DESC
            LIMIT ?
        """, (limit,)).fetchall()
        results = [dict(r) for r in rows]
        print(f"\nTop {limit} recipients by total received:")
        for r in results:
            print(f"  {_fmt_amount(r['total']):>16}  {r['cnt']:>6} grants from {r.get('unique_funders', '?'):>4} funders  "
                  f"{r.get('recipient_name', '?')[:40]}  ({r.get('recipient_ein', '')})")

    elif by == "single":
        # Largest single grants
        rows = db.execute("""
            SELECT * FROM grants
            ORDER BY cash_amount DESC
            LIMIT ?
        """, (limit,)).fetchall()
        results = [dict(r) for r in rows]
        print(f"\nTop {limit} largest single grants:")
        for r in results:
            print(f"  {r.get('tax_year', '?'):>5}  {_fmt_amount(r.get('cash_amount')):>16}  "
                  f"{r.get('filer_name', '?')[:25]:25s} → {r.get('recipient_name', '?')[:35]}")

    else:
        print(f"Unknown --by option: {by}. Use: amount, count, recipients, single")
        db.close()
        return

    write_output(results, args, summary=f"990 bulk top {by}")
    db.close()


# ── main ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Query IRS 990 Bulk Grant Database")
    sub = parser.add_subparsers(dest="command")

    p_sr = sub.add_parser("search", help="Full-text search grants + related orgs")
    p_sr.add_argument("query", help="Search term")
    p_sr.add_argument("-n", "--limit", type=int, default=100, help="Max results")
    add_output_args(p_sr)

    p_fl = sub.add_parser("filer", help="Grants made by a filer EIN")
    p_fl.add_argument("ein", help="Filer EIN")
    add_output_args(p_fl)

    p_rc = sub.add_parser("recipient", help="Grants received by name (FTS5)")
    p_rc.add_argument("name", help="Recipient name")
    p_rc.add_argument("-n", "--limit", type=int, default=100, help="Max results")
    add_output_args(p_rc)

    p_re = sub.add_parser("recipient-ein", help="Grants received by EIN")
    p_re.add_argument("ein", help="Recipient EIN")
    add_output_args(p_re)

    p_net = sub.add_parser("network", help="BFS grant network from seed EIN")
    p_net.add_argument("ein", help="Seed EIN")
    p_net.add_argument("--depth", type=int, default=2, help="BFS depth (default: 2)")
    p_net.add_argument("-n", "--limit", type=int, default=50, help="Max edges per hop")
    add_output_args(p_net)

    p_cg = sub.add_parser("co-grantors", help="Foundations funding the same recipient")
    p_cg.add_argument("name", help="Recipient name")
    p_cg.add_argument("-n", "--limit", type=int, default=50, help="Max results")
    add_output_args(p_cg)

    p_xr = sub.add_parser("cross-ref", help="Match investigation.db entities against bulk grants")
    add_output_args(p_xr)

    p_top = sub.add_parser("top", help="Top grantmakers/recipients")
    p_top.add_argument("--by", default="amount", help="Rank by: amount, count, recipients, single")
    p_top.add_argument("-n", "--limit", type=int, default=20, help="Number of results")
    add_output_args(p_top)

    args = parser.parse_args()

    if args.command == "search":
        cmd_search(args)
    elif args.command == "filer":
        cmd_filer(args)
    elif args.command == "recipient":
        cmd_recipient(args)
    elif args.command == "recipient-ein":
        cmd_recipient_ein(args)
    elif args.command == "network":
        cmd_network(args)
    elif args.command == "co-grantors":
        cmd_co_grantors(args)
    elif args.command == "cross-ref":
        cmd_cross_ref(args)
    elif args.command == "top":
        cmd_top(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
