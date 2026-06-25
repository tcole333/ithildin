#!/usr/bin/env python3
"""
DeHashed v2 API wrapper — breach/credential aggregator for selector pivoting.

Search breached/leaked records by one selector (email, username, phone, name,
domain, IP, address, VIN, hashed_password) and return the records — each
carrying the OTHER selectors for that identity. One email -> the usernames,
phones, addresses, and names that co-occur in breach data: the core
credential-pivot primitive.

API: https://api.dehashed.com/v2/search  (POST, header `DeHashed-Api-Key`)
Auth: DEHASHED_API_KEY in .env. Requires an ACTIVE search subscription — the v2
      API needs a subscription, not just a credit balance (a lapsed sub 401s).
Credits: each search page consumes credits; the remaining `balance` comes back on
      every response and is surfaced in output. Pagination multiplies cost, so
      this tool fetches a SINGLE page by default (--paginate to override).
Caveats: `*` wildcard is broken server-side (since May 2025) — use `?`. regex is
      unreliable. Result fields come back as lists (or the string "null").

Usage:
    python tools/query_dehashed.py search --email jane@example.com --output out.json
    python tools/query_dehashed.py search --username jdoe --output out.json
    python tools/query_dehashed.py search --domain example.com --size 100 --output out.json
    python tools/query_dehashed.py search --name "Jane Doe" --output out.json
    python tools/query_dehashed.py balance
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

PROJECT_ROOT = Path(__file__).resolve().parent.parent

try:
    from tools.output_util import add_output_args, write_output
    from tools.env_loader import load_env_file
except ImportError:
    from output_util import add_output_args, write_output
    from env_loader import load_env_file

load_env_file()

SEARCH_URL = "https://api.dehashed.com/v2/search"
USER_AGENT = "OSINT-Research osint-research@proton.me"

# Selector fields accepted by the v2 query language.
SEARCH_FIELDS = ["email", "username", "hashed_password", "ip_address",
                 "name", "phone", "address", "vin", "domain"]


def _get_api_key():
    key = os.environ.get("DEHASHED_API_KEY")
    if not key:
        print("ERROR: DEHASHED_API_KEY not set in .env.", file=sys.stderr)
        sys.exit(1)
    return key


def _post(payload, key):
    req = Request(SEARCH_URL, data=json.dumps(payload).encode(), method="POST",
                  headers={"Content-Type": "application/json",
                           "DeHashed-Api-Key": key, "User-Agent": USER_AGENT})
    with urlopen(req, timeout=45) as r:
        return json.loads(r.read())


def _build_query(field, value):
    # Domains are not quoted; every other field is.
    return f"domain:{value}" if field == "domain" else f'{field}:"{value}"'


def _http_fail(e):
    body = e.read()[:300].decode(errors="replace")
    print(f"ERROR: Dehashed HTTP {e.code}: {body}", file=sys.stderr)
    if e.code == 401:
        print("  (401 = key invalid OR no active search subscription — check your Dehashed plan.)",
              file=sys.stderr)
    sys.exit(1)


def cmd_search(args):
    key = _get_api_key()
    provided = [(f, getattr(args, f)) for f in SEARCH_FIELDS if getattr(args, f, None)]
    if len(provided) != 1:
        flags = ", ".join("--" + f.replace("_", "-") for f in SEARCH_FIELDS)
        print(f"ERROR: provide exactly one selector field ({flags}).", file=sys.stderr)
        sys.exit(1)
    field, value = provided[0]
    if "*" in str(value) and not args.regex:
        print("WARNING: '*' wildcard is broken server-side (Dehashed, since May 2025). "
              "Use '?' for single characters.", file=sys.stderr)

    query = _build_query(field, value)
    entries, balance, total, pages = [], None, None, 0
    page = args.page
    try:
        while True:
            resp = _post({"query": query, "page": page, "size": args.size,
                          "wildcard": args.wildcard, "regex": args.regex,
                          "de_dupe": args.dedupe}, key)
            balance = resp.get("balance")
            total = resp.get("total")
            entries.extend(resp.get("entries") or [])
            pages += 1
            if not args.paginate or not total:
                break
            if (args.size * page) >= total or (args.size * page) >= 10000:
                break
            page += 1
    except HTTPError as e:
        _http_fail(e)
    except URLError as e:
        print(f"ERROR: Dehashed unreachable: {e}", file=sys.stderr)
        sys.exit(1)

    result = {"query": query, "field": field, "value": value, "total": total,
              "balance": balance, "pages_fetched": pages, "returned": len(entries),
              "entries": entries}
    summary = f"Dehashed {field}='{value}': {len(entries)} of {total} records, balance={balance} credits"
    if balance is not None and balance < args.min_balance:
        print(f"WARNING: Dehashed balance {balance} below floor {args.min_balance}.", file=sys.stderr)
    if write_output(result, args, summary=summary):
        return
    print(summary)


def cmd_balance(args):
    # No free balance endpoint — a size=1 search returns balance (costs ~1 credit).
    key = _get_api_key()
    try:
        resp = _post({"query": "domain:example.com", "page": 1, "size": 1,
                      "wildcard": False, "regex": False, "de_dupe": False}, key)
    except HTTPError as e:
        _http_fail(e)
    except URLError as e:
        print(f"ERROR: Dehashed unreachable: {e}", file=sys.stderr)
        sys.exit(1)
    out = {"balance": resp.get("balance")}
    if write_output(out, args, summary=f"Dehashed balance: {resp.get('balance')} credits"):
        return
    print(f"Dehashed balance: {resp.get('balance')} credits remaining")


def main():
    parser = argparse.ArgumentParser(description="DeHashed v2 breach/credential search")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("search", help="Search breach records by one selector field")
    for f in SEARCH_FIELDS:
        p.add_argument(f"--{f.replace('_', '-')}", dest=f, help=f"Search by {f}")
    p.add_argument("--size", type=int, default=100, help="Results per page (1-10000, default 100)")
    p.add_argument("--page", type=int, default=1, help="Start page (default 1)")
    p.add_argument("--paginate", action="store_true", help="Fetch all pages (multiplies credit cost)")
    p.add_argument("--wildcard", action="store_true", help="Enable '?' wildcard ('*' is server-broken)")
    p.add_argument("--regex", action="store_true", help="Regex search (unreliable server-side)")
    p.add_argument("--dedupe", action="store_true", help="Server-side de_dupe")
    p.add_argument("--min-balance", type=int, default=25, help="Warn if balance falls below this floor")
    add_output_args(p)
    p.set_defaults(func=cmd_search)

    pb = sub.add_parser("balance", help="Check remaining API credits (costs ~1 credit)")
    add_output_args(pb)
    pb.set_defaults(func=cmd_balance)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
