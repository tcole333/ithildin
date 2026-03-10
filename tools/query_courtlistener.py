#!/usr/bin/env python3
"""
CourtListener API wrapper for OSINT investigations.

Loads credentials from .env and provides investigation-friendly output.

Usage:
    python tools/query_courtlistener.py search "Jeffrey Epstein"
    python tools/query_courtlistener.py cases "Epstein" --court nysd
    python tools/query_courtlistener.py docket 16066603
    python tools/query_courtlistener.py party "Ghislaine Maxwell"
    python tools/query_courtlistener.py opinions "Epstein" --court ca2
    python tools/query_courtlistener.py judge "Preska"
    python tools/query_courtlistener.py disclosures --person-id 1234
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output


def _log(query, source, count):
    """Log search to prevent redundant queries."""
    try:
        from tools.lead_tracker import log_search
        log_search(query, source, count)
    except Exception:
        pass


# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"'))

def _client():
    try:
        from tools.courtlistener_api_client import CourtListenerClient
    except ImportError:
        from courtlistener_api_client import CourtListenerClient

    token = os.environ.get("COURTLISTENER_TOKEN")
    if not token:
        print("ERROR: COURTLISTENER_TOKEN not set in .env", file=sys.stderr)
        sys.exit(1)
    return CourtListenerClient(token=token)


def cmd_search(args):
    """Generic search (defaults to RECAP/dockets)."""
    client = _client()
    results = client.search(
        args.query,
        search_type=args.type,
        court=args.court,
        max_results=args.limit,
    )

    _log(args.query, "courtlistener", len(results))

    if write_output(results, args, summary=f"CourtListener search '{args.query}'"):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(results, indent=2, default=str))
        return

    print(f"Found {len(results)} results for '{args.query}' (type={args.type})")
    print()
    for r in results:
        court = r.get("court", r.get("court_id", "?"))
        case_name = r.get("caseName", r.get("case_name", "?"))
        date = r.get("dateFiled", r.get("date_filed", ""))
        url = r.get("docket_absolute_url", r.get("absolute_url", ""))
        print(f"  [{court}] {case_name}")
        if date:
            print(f"    Filed: {date}")
        if url:
            print(f"    URL: https://www.courtlistener.com{url}")
        # Show snippet if available
        snippet = r.get("snippet", r.get("text", ""))
        if snippet:
            clean = snippet.replace("<mark>", "**").replace("</mark>", "**")
            print(f"    Snippet: {clean[:200]}")
        print()


def cmd_cases(args):
    """Search RECAP dockets specifically."""
    client = _client()
    results = client.search_cases(
        args.query,
        court=args.court,
        date_filed_after=args.after,
        date_filed_before=args.before,
        max_results=args.limit,
    )
    _log(args.query, "courtlistener", len(results))
    print(f"Found {len(results)} cases for '{args.query}'")
    print()
    for r in results:
        court = r.get("court", "?")
        case_name = r.get("caseName", "?")
        date = r.get("dateFiled", "")
        docket_num = r.get("docketNumber", "")
        nos = r.get("suitNature", "")
        url = r.get("docket_absolute_url", "")
        print(f"  [{court}] {case_name}")
        if docket_num:
            print(f"    Docket #: {docket_num}")
        if date:
            print(f"    Filed: {date}")
        if nos:
            print(f"    Nature of suit: {nos}")
        if url:
            print(f"    URL: https://www.courtlistener.com{url}")
        print()


def cmd_docket(args):
    """Get docket details by ID."""
    client = _client()
    docket = client.get_docket(args.docket_id)

    if write_output(docket, args, summary=f"CourtListener docket #{args.docket_id}"):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(docket, indent=2, default=str))
        return

    print(f"=== Docket #{args.docket_id} ===")
    print(f"Case: {docket.get('case_name', '?')}")
    print(f"Court: {docket.get('court', '?')}")
    print(f"Docket #: {docket.get('docket_number', '?')}")
    print(f"Filed: {docket.get('date_filed', '?')}")
    print(f"Terminated: {docket.get('date_terminated', 'ongoing')}")
    print(f"Nature of suit: {docket.get('nature_of_suit', '?')}")
    print(f"Cause: {docket.get('cause', '?')}")
    judges = docket.get("assigned_to_str", "") or docket.get("referred_to_str", "")
    if judges:
        print(f"Judge: {judges}")
    print(f"URL: https://www.courtlistener.com{docket.get('absolute_url', '')}")
    print()


def cmd_party(args):
    """Search parties across all cases."""
    client = _client()
    parties = client.search_party_by_name(args.name, max_results=args.limit)
    _log(args.name, "courtlistener", len(parties))
    print(f"Found {len(parties)} party records for '{args.name}'")
    print()
    for p in parties:
        name = p.get("name", "?")
        docket_url = p.get("docket", "")
        party_types = [pt.get("name", "?") for pt in p.get("party_types", [])]
        attorneys = p.get("attorneys", [])
        print(f"  {name} ({', '.join(party_types) if party_types else '?'})")
        if docket_url:
            print(f"    Docket: {docket_url}")
        if attorneys:
            for att in attorneys[:3]:
                att_name = att.get("name", "?")
                att_firm = att.get("firm_name", "")
                print(f"    Attorney: {att_name}" + (f" ({att_firm})" if att_firm else ""))
        print()


def cmd_opinions(args):
    """Search opinions."""
    client = _client()
    results = client.search(
        args.query,
        search_type="o",
        court=args.court,
        max_results=args.limit,
    )
    print(f"Found {len(results)} opinions for '{args.query}'")
    print()
    for r in results:
        case_name = r.get("caseName", "?")
        court = r.get("court", "?")
        date = r.get("dateFiled", "")
        cite = r.get("citation", [])
        url = r.get("absolute_url", "")
        print(f"  [{court}] {case_name}")
        if date:
            print(f"    Date: {date}")
        if cite:
            print(f"    Citations: {cite}")
        if url:
            print(f"    URL: https://www.courtlistener.com{url}")
        snippet = r.get("snippet", "")
        if snippet:
            clean = snippet.replace("<mark>", "**").replace("</mark>", "**")
            print(f"    Snippet: {clean[:200]}")
        print()


def cmd_judge(args):
    """Search judges."""
    client = _client()
    judges = client.search_judges(name=args.name, max_results=args.limit)
    print(f"Found {len(judges)} judges matching '{args.name}'")
    for j in judges:
        name = j.get("name_full", "?")
        positions = j.get("positions", [])
        print(f"  {name} (ID: {j.get('id', '?')})")
        for pos in positions[:3]:
            court = pos.get("court", {}).get("short_name", "?")
            title = pos.get("position_type", "?")
            print(f"    {title} at {court}")
        print()


def cmd_disclosures(args):
    """Get financial disclosures for a judge."""
    client = _client()
    results = client.get_financial_disclosures(
        person_id=args.person_id,
        year=args.year,
        max_results=args.limit,
    )

    if write_output(results, args, summary=f"CourtListener disclosures"):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(results, indent=2, default=str))
        return

    print(f"Found {len(results)} disclosure records")
    for d in results:
        year = d.get("year", "?")
        person = d.get("person", "?")
        print(f"  Year {year} — Person ID: {person}")
        if d.get("has_been_extracted"):
            print(f"    Extracted: Yes")
        print()


def main():
    parser = argparse.ArgumentParser(description="CourtListener API for OSINT investigation")
    sub = parser.add_subparsers(dest="command", required=True)

    # search
    p = sub.add_parser("search", help="Search (generic)")
    p.add_argument("query")
    p.add_argument("--type", default="r", help="o=opinions, r=recap/dockets, p=people")
    p.add_argument("--court", help="Court filter (e.g., nysd, ca2, scotus)")
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    # cases
    p = sub.add_parser("cases", help="Search RECAP dockets")
    p.add_argument("query")
    p.add_argument("--court")
    p.add_argument("--after", help="Filed after (YYYY-MM-DD)")
    p.add_argument("--before", help="Filed before (YYYY-MM-DD)")
    p.add_argument("--limit", type=int, default=20)

    # docket
    p = sub.add_parser("docket", help="Get docket by ID")
    p.add_argument("docket_id", type=int)
    add_output_args(p)

    # party
    p = sub.add_parser("party", help="Search parties")
    p.add_argument("name")
    p.add_argument("--limit", type=int, default=20)

    # opinions
    p = sub.add_parser("opinions", help="Search opinions")
    p.add_argument("query")
    p.add_argument("--court")
    p.add_argument("--limit", type=int, default=20)

    # judge
    p = sub.add_parser("judge", help="Search judges")
    p.add_argument("name")
    p.add_argument("--limit", type=int, default=10)

    # disclosures
    p = sub.add_parser("disclosures", help="Financial disclosures")
    p.add_argument("--person-id", type=int, help="Judge person ID")
    p.add_argument("--year", type=int)
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    args = parser.parse_args()
    # Propagate json_out to all subcommands (fallback if not present)
    if not hasattr(args, "json_out"):
        args.json_out = False

    handlers = {
        "search": cmd_search,
        "cases": cmd_cases,
        "docket": cmd_docket,
        "party": cmd_party,
        "opinions": cmd_opinions,
        "judge": cmd_judge,
        "disclosures": cmd_disclosures,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
