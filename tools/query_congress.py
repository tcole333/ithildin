#!/usr/bin/env python3
"""
Congress.gov API — bills, members, committees, nominations, CRS reports.

Complements GovInfo (full text) with structured legislative metadata.
Free API key via api.congress.gov. Rate limit: 5,000/hour.

Usage:
    python tools/query_congress.py search "Epstein" --type bills
    python tools/query_congress.py member "Warren"
    python tools/query_congress.py committee SSGA
    python tools/query_congress.py committee-reports SSGA --congress 118
    python tools/query_congress.py nominations --congress 118 --limit 10
    python tools/query_congress.py crs "beneficial ownership"
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

try:
    from tools.output_util import add_output_args, write_output
    from tools.lead_tracker import log_search
except ImportError:
    from output_util import add_output_args, write_output
    from lead_tracker import log_search

BASE_URL = "https://api.congress.gov/v3"
RATE_LIMIT = 0.3
PROJECT_ROOT = Path(__file__).parent.parent


def _get_api_key():
    """Get Congress.gov API key from environment."""
    key = os.environ.get("CONGRESS_API_KEY")
    if not key:
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("CONGRESS_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return key


def _request(endpoint, params=None):
    """Make authenticated request to Congress.gov API."""
    api_key = _get_api_key()
    if not api_key:
        print("ERROR: CONGRESS_API_KEY not set. Get a free key at https://api.congress.gov/sign-up/", file=sys.stderr)
        sys.exit(1)

    if params is None:
        params = {}
    params["api_key"] = api_key
    params.setdefault("format", "json")

    url = f"{BASE_URL}{endpoint}"
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"

    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "OSINT-Research/1.0",
    })

    time.sleep(RATE_LIMIT)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        if e.code == 429:
            print("ERROR: Rate limit exceeded. Wait and retry.", file=sys.stderr)
        else:
            print(f"ERROR: HTTP {e.code}: {body[:200]}", file=sys.stderr)
        return None
    except URLError as e:
        print(f"ERROR: {e.reason}", file=sys.stderr)
        return None


def cmd_search(args):
    """Search bills by keyword."""
    params = {
        "query": args.query,
        "limit": min(args.limit, 250),
    }

    # Bill search endpoint
    endpoint = "/bill"
    if args.congress:
        endpoint = f"/bill/{args.congress}"

    data = _request(endpoint, params)
    if not data:
        print("No results or API error.")
        return

    bills = data.get("bills", [])
    total = len(bills)
    output = {"total": total, "bills": bills}

    log_search("congress_bills", args.query, total)

    if not write_output(output, args, summary=f"Congress bills '{args.query}'"):
        print(f"Congress.gov: {total} bills for '{args.query}'")
        for b in bills:
            number = b.get("number", "?")
            title = b.get("title", "")[:80]
            bill_type = b.get("type", "?")
            congress = b.get("congress", "?")
            date = b.get("latestAction", {}).get("actionDate", "?")
            action = b.get("latestAction", {}).get("text", "")[:60]

            print(f"\n  {bill_type}{number} ({congress}th Congress)")
            print(f"  {title}")
            print(f"  Latest: {date} - {action}")


def cmd_member(args):
    """Look up a member of Congress."""
    # Search members by name — use the member listing endpoint
    params = {"limit": 20}
    data = _request("/member", params)
    if not data:
        print("API error.")
        return

    members = data.get("members", [])
    # Filter by name client-side (API doesn't have name search param)
    query_lower = args.name.lower()
    matched = [m for m in members if query_lower in (m.get("name", "") or "").lower()
               or query_lower in (m.get("firstName", "") or "").lower()
               or query_lower in (m.get("lastName", "") or "").lower()]

    if not matched:
        # Try paginating — the API returns paginated results
        # For broader coverage, try fetching more
        params["limit"] = 250
        data = _request("/member", params)
        if data:
            members = data.get("members", [])
            matched = [m for m in members if query_lower in (m.get("name", "") or "").lower()
                       or query_lower in (m.get("firstName", "") or "").lower()
                       or query_lower in (m.get("lastName", "") or "").lower()]

    log_search("congress_member", args.name, len(matched))

    if not write_output(matched, args, summary=f"Congress member '{args.name}'"):
        if not matched:
            print(f"No members found matching '{args.name}'")
            return

        print(f"Congress members matching '{args.name}': {len(matched)}")
        for m in matched:
            name = m.get("name", "?")
            state = m.get("state", "?")
            party = m.get("partyName", "?")
            bio_id = m.get("bioguideId", "?")
            terms = m.get("terms", {}).get("item", [])
            chamber = terms[-1].get("chamber", "?") if terms else "?"

            print(f"\n  [{bio_id}] {name}")
            print(f"  {party} - {state} | Chamber: {chamber}")
            if terms:
                latest = terms[-1]
                print(f"  Latest term: {latest.get('startYear', '?')}-{latest.get('endYear', '?')}")


def cmd_committee(args):
    """Get committee info and subcommittees."""
    # Try both senate and house committee codes
    for chamber in ["senate", "house", "joint"]:
        data = _request(f"/committee/{chamber}/{args.code}")
        if data and data.get("committee"):
            break
    else:
        # Try without chamber prefix
        data = _request(f"/committee/{args.code}")

    if not data or not data.get("committee"):
        print(f"Committee {args.code} not found.")
        sys.exit(1)

    committee = data["committee"]
    log_search("congress_committee", f"committee:{args.code}", 1)

    if not write_output(committee, args, summary=f"Committee {args.code}"):
        name = committee.get("name", "?")
        chamber = committee.get("chamber", "?")
        committee_type = committee.get("type", "?")

        print(f"\n  Committee: {args.code}")
        print(f"  Name: {name}")
        print(f"  Chamber: {chamber} | Type: {committee_type}")

        subcommittees = committee.get("subcommittees", [])
        if subcommittees:
            print(f"\n  Subcommittees ({len(subcommittees)}):")
            for sc in subcommittees:
                sc_name = sc.get("name", "?")
                sc_code = sc.get("systemCode", "?")
                print(f"    [{sc_code}] {sc_name}")


def cmd_committee_reports(args):
    """Get reports from a specific committee."""
    params = {"limit": min(args.limit, 250)}

    endpoint = f"/committee-report"
    if args.congress:
        endpoint = f"/committee-report/{args.congress}"

    data = _request(endpoint, params)
    if not data:
        print("API error.")
        return

    reports = data.get("reports", [])
    # Filter by committee code if provided
    if args.committee:
        code_lower = args.committee.lower()
        reports = [r for r in reports if code_lower in json.dumps(r).lower()]

    log_search("congress_reports", f"reports:{args.committee or 'all'}:{args.congress or 'all'}", len(reports))

    if not write_output(reports, args, summary=f"Committee reports ({len(reports)})"):
        print(f"Committee reports: {len(reports)}")
        for r in reports:
            number = r.get("number", "?")
            title = r.get("title", "")[:80]
            report_type = r.get("type", "?")
            congress = r.get("congress", "?")
            date = r.get("updateDate", "?")

            print(f"\n  {report_type} {number} ({congress}th Congress)")
            print(f"  {title}")
            print(f"  Updated: {date}")


def cmd_nominations(args):
    """List nominations (useful for tracking DOJ/SEC appointees)."""
    params = {"limit": min(args.limit, 250)}

    endpoint = "/nomination"
    if args.congress:
        endpoint = f"/nomination/{args.congress}"

    data = _request(endpoint, params)
    if not data:
        print("API error.")
        return

    nominations = data.get("nominations", [])

    log_search("congress_nominations", f"nominations:{args.congress or 'all'}", len(nominations))

    if not write_output(nominations, args, summary=f"Nominations ({len(nominations)})"):
        print(f"Nominations: {len(nominations)}")
        for n in nominations:
            number = n.get("number", "?")
            description = n.get("description", "")[:80]
            congress = n.get("congress", "?")
            date = n.get("latestAction", {}).get("actionDate", "?")
            action = n.get("latestAction", {}).get("text", "")[:60]

            print(f"\n  PN{number} ({congress}th Congress)")
            print(f"  {description}")
            print(f"  Latest: {date} - {action}")


def cmd_crs(args):
    """Search CRS reports."""
    params = {
        "query": args.query,
        "limit": min(args.limit, 250),
    }

    data = _request("/crs-report", params)
    if not data:
        print("No results or API error.")
        return

    reports = data.get("CRSReports", [])
    total = len(reports)

    log_search("congress_crs", args.query, total)

    if not write_output(reports, args, summary=f"CRS reports '{args.query}'"):
        print(f"CRS Reports: {total} for '{args.query}'")
        for r in reports:
            report_number = r.get("reportNumber", "?")
            title = r.get("title", "")[:80]
            date = r.get("latestPubDate", "?")

            print(f"\n  [{report_number}] {title}")
            print(f"  Published: {date}")


def main():
    parser = argparse.ArgumentParser(
        description="Congress.gov API — bills, members, committees, nominations, CRS",
        epilog="Auth: CONGRESS_API_KEY (free at https://api.congress.gov/sign-up/). Rate: 5,000/hour.",
    )
    sub = parser.add_subparsers(dest="command")

    # search (bills)
    p_search = sub.add_parser("search", help="Search bills by keyword")
    p_search.add_argument("query", help="Keyword query")
    p_search.add_argument("--congress", type=int, help="Limit to specific congress (e.g., 118)")
    p_search.add_argument("--limit", type=int, default=20, help="Max results")
    add_output_args(p_search)

    # member
    p_member = sub.add_parser("member", help="Look up a member of Congress")
    p_member.add_argument("name", help="Member name to search")
    add_output_args(p_member)

    # committee
    p_committee = sub.add_parser("committee", help="Get committee info and subcommittees")
    p_committee.add_argument("code", help="Committee system code (e.g., SSGA, SSGA01 for PSI)")
    add_output_args(p_committee)

    # committee-reports
    p_reports = sub.add_parser("committee-reports", help="Get committee reports")
    p_reports.add_argument("committee", nargs="?", help="Committee code to filter by")
    p_reports.add_argument("--congress", type=int, help="Limit to specific congress")
    p_reports.add_argument("--limit", type=int, default=20, help="Max results")
    add_output_args(p_reports)

    # nominations
    p_nom = sub.add_parser("nominations", help="List nominations (DOJ/SEC appointees)")
    p_nom.add_argument("--congress", type=int, help="Limit to specific congress")
    p_nom.add_argument("--limit", type=int, default=20, help="Max results")
    add_output_args(p_nom)

    # crs
    p_crs = sub.add_parser("crs", help="Search CRS reports")
    p_crs.add_argument("query", help="Search query")
    p_crs.add_argument("--limit", type=int, default=20, help="Max results")
    add_output_args(p_crs)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    handlers = {
        "search": cmd_search,
        "member": cmd_member,
        "committee": cmd_committee,
        "committee-reports": cmd_committee_reports,
        "nominations": cmd_nominations,
        "crs": cmd_crs,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
