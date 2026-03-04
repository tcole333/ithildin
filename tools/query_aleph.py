#!/usr/bin/env python3
"""
OCCRP Aleph API wrapper for OSINT investigations.

Searches the OCCRP Aleph platform — corporate registries, court records,
sanctions lists, leaks, and investigative datasets from around the world.

Public datasets accessible without authentication. For private/restricted
datasets, set ALEPH_API_KEY in .env.

Usage:
    python tools/query_aleph.py search "Jeffrey Epstein"
    python tools/query_aleph.py search "Financial Trust Company" --schema Company
    python tools/query_aleph.py search "Liquid Funding" --schema Company --countries vg
    python tools/query_aleph.py entity <entity_id>
    python tools/query_aleph.py expand <entity_id>
    python tools/query_aleph.py collections --query "epstein"
    python tools/query_aleph.py similar <entity_id>
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

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


BASE_URL = "https://aleph.occrp.org/api/2"

# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"'))

# FTM schema types useful for investigation
SCHEMAS = {
    "Person": "Person",
    "Company": "Company",
    "Organization": "Organization",
    "LegalEntity": "LegalEntity",
    "Document": "Document",
    "Email": "Email",
    "Address": "Address",
    "BankAccount": "BankAccount",
    "RealEstate": "RealEstate",
    "CourtCase": "CourtCase",
    "Vessel": "Vessel",
    "Vehicle": "Vehicle",
    "Airplane": "Airplane",
    "Ownership": "Ownership",
    "Directorship": "Directorship",
    "Membership": "Membership",
}


def _request(path, params=None):
    """Make an API request to Aleph."""
    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + urlencode(params, doseq=True)

    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; OSINT-Research/1.0)",
    }
    token = os.environ.get("ALEPH_API_KEY")
    if token:
        headers["Authorization"] = f"Token {token}"

    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        body = e.read().decode()[:500]
        print(f"ERROR: HTTP {e.code} from Aleph: {body}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"ERROR: Cannot reach Aleph: {e.reason}", file=sys.stderr)
        sys.exit(1)


def _paginate(path, params, max_results=50):
    """Paginate through Aleph results."""
    results = []
    params["limit"] = min(max_results, 50)
    params["offset"] = 0

    while len(results) < max_results:
        data = _request(path, params)
        batch = data.get("results", [])
        if not batch:
            break
        results.extend(batch)
        if len(results) >= data.get("total", 0):
            break
        params["offset"] += len(batch)
        time.sleep(0.5)  # Rate limiting courtesy

    return results[:max_results], data.get("total", len(results))


def format_entity(entity, verbose=False):
    """Format an Aleph entity for display."""
    props = entity.get("properties", {})
    coll = entity.get("collection", {})
    schema = entity.get("schema", "?")

    name = ", ".join(props.get("name", ["?"]))
    lines = [f"  [{schema}] {name}"]

    # Collection info
    coll_label = coll.get("label", "")
    if coll_label:
        lines.append(f"    Source: {coll_label}")

    countries = props.get("country", coll.get("countries", []))
    if countries:
        lines.append(f"    Countries: {', '.join(countries)}")

    # Address
    addresses = props.get("address", props.get("addressEntity", []))
    if addresses:
        for addr in addresses[:2]:
            lines.append(f"    Address: {addr}")

    # For companies
    reg_num = props.get("registrationNumber", [])
    if reg_num:
        lines.append(f"    Reg #: {', '.join(reg_num)}")

    jurisdiction = props.get("jurisdiction", [])
    if jurisdiction:
        lines.append(f"    Jurisdiction: {', '.join(jurisdiction)}")

    inc_date = props.get("incorporationDate", [])
    if inc_date:
        lines.append(f"    Incorporated: {', '.join(inc_date)}")

    diss_date = props.get("dissolutionDate", [])
    if diss_date:
        lines.append(f"    Dissolved: {', '.join(diss_date)}")

    status = props.get("status", [])
    if status:
        lines.append(f"    Status: {', '.join(status)}")

    # For persons
    birth = props.get("birthDate", [])
    if birth:
        lines.append(f"    DOB: {', '.join(birth)}")

    nationality = props.get("nationality", [])
    if nationality:
        lines.append(f"    Nationality: {', '.join(nationality)}")

    # ID and link
    entity_id = entity.get("id", "")
    if entity_id:
        lines.append(f"    ID: {entity_id}")
        lines.append(f"    URL: https://aleph.occrp.org/entities/{entity_id}")

    if verbose:
        # Show all properties
        for key, vals in sorted(props.items()):
            if key not in ("name", "country", "address", "addressEntity",
                           "registrationNumber", "jurisdiction",
                           "incorporationDate", "dissolutionDate", "status",
                           "birthDate", "nationality"):
                if vals:
                    lines.append(f"    {key}: {', '.join(str(v) for v in vals)}")

    return "\n".join(lines)


def cmd_search(args):
    """Search entities across all Aleph datasets."""
    params = {"q": args.query}
    if args.schema:
        params["filter:schemata"] = args.schema
    if args.countries:
        params["filter:countries"] = args.countries
    if args.collection:
        params["filter:collection_id"] = args.collection

    results, total = _paginate("/entities", params, max_results=args.limit)

    _log(args.query, "aleph", total)

    schema_label = f" (schema={args.schema})" if args.schema else ""
    print(f"Found {total} total results for '{args.query}'{schema_label} (showing {len(results)})")
    print()

    for r in results:
        print(format_entity(r, verbose=args.verbose))
        print()

    if write_output(results, args, summary=f"Aleph search '{args.query}'"):
        pass
    elif args.json_out:
        print(json.dumps(results, indent=2, default=str))


def cmd_entity(args):
    """Get full entity details by ID."""
    entity = _request(f"/entities/{args.entity_id}")

    print(f"=== Entity {args.entity_id} ===")
    print(format_entity(entity, verbose=True))
    print()

    if write_output(entity, args, summary=f"Aleph entity {args.entity_id}"):
        pass
    elif args.json_out:
        print(json.dumps(entity, indent=2, default=str))


def cmd_expand(args):
    """Expand entity relationships (connected entities)."""
    params = {"limit": args.limit}
    if args.schema:
        params["filter:schema"] = args.schema

    data = _request(f"/entities/{args.entity_id}/expand", params)

    # The expand endpoint returns property-grouped results
    results = data.get("results", [])
    total = data.get("total", 0)
    print(f"Found {total} relationships for entity {args.entity_id}")
    print()

    for group in results:
        prop = group.get("property", "?")
        prop_label = prop if isinstance(prop, str) else prop.get("label", prop.get("name", "?"))
        entities = group.get("entities", [])
        count = group.get("count", len(entities))
        print(f"  --- {prop_label} ({count}) ---")
        for e in entities:
            print(format_entity(e))
        print()

    if write_output(data, args, summary=f"Aleph expand {args.entity_id}"):
        pass
    elif args.json_out:
        print(json.dumps(data, indent=2, default=str))


def cmd_similar(args):
    """Find entities similar to a given entity."""
    params = {"limit": args.limit}
    data = _request(f"/entities/{args.entity_id}/similar", params)

    results = data.get("results", [])
    total = data.get("total", 0)
    print(f"Found {total} similar entities")
    print()

    for r in results:
        print(format_entity(r))
        print()

    if write_output(data, args, summary=f"Aleph similar to {args.entity_id}"):
        pass
    elif args.json_out:
        print(json.dumps(data, indent=2, default=str))


def cmd_collections(args):
    """List or search collections (datasets) on Aleph."""
    params = {"limit": args.limit}
    if args.query:
        params["q"] = args.query
    if args.countries:
        params["filter:countries"] = args.countries
    if args.category:
        params["filter:category"] = args.category

    data = _request("/collections", params)
    results = data.get("results", [])
    total = data.get("total", 0)

    print(f"Found {total} collections" + (f" matching '{args.query}'" if args.query else ""))
    print()

    for c in results:
        label = c.get("label", "?")
        cid = c.get("id", "?")
        category = c.get("category", "?")
        countries = c.get("countries", [])
        count = c.get("count", 0)
        publisher = c.get("publisher", "")
        summary = c.get("summary", "")

        print(f"  [{category}] {label} (id={cid})")
        if countries:
            print(f"    Countries: {', '.join(countries)}")
        if count:
            print(f"    Records: {count:,}")
        if publisher:
            print(f"    Publisher: {publisher}")
        if summary:
            print(f"    Summary: {summary[:200]}")
        print(f"    URL: https://aleph.occrp.org/datasets/{cid}")
        print()

    if write_output(data, args, summary=f"Aleph collections{' ' + args.query if args.query else ''}"):
        pass
    elif args.json_out:
        print(json.dumps(data, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="OCCRP Aleph API for OSINT investigation")
    sub = parser.add_subparsers(dest="command", required=True)

    # search
    p = sub.add_parser("search", help="Search entities")
    p.add_argument("query")
    p.add_argument("--schema", choices=list(SCHEMAS.keys()),
                   help="Filter by FTM schema type")
    p.add_argument("--countries", help="Filter by country code (e.g., us, vg, gb)")
    p.add_argument("--collection", help="Filter by collection ID")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--verbose", "-v", action="store_true", help="Show all properties")
    add_output_args(p)

    # entity
    p = sub.add_parser("entity", help="Get entity by ID")
    p.add_argument("entity_id")
    add_output_args(p)

    # expand
    p = sub.add_parser("expand", help="Expand entity relationships")
    p.add_argument("entity_id")
    p.add_argument("--schema", help="Filter relationships by schema")
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    # similar
    p = sub.add_parser("similar", help="Find similar entities")
    p.add_argument("entity_id")
    p.add_argument("--limit", type=int, default=10)
    add_output_args(p)

    # collections
    p = sub.add_parser("collections", help="List/search datasets")
    p.add_argument("--query", "-q", help="Search collections by name")
    p.add_argument("--countries", help="Filter by country code")
    p.add_argument("--category", help="Filter by category (e.g., court, leak, gazette)")
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    args = parser.parse_args()

    handlers = {
        "search": cmd_search,
        "entity": cmd_entity,
        "expand": cmd_expand,
        "similar": cmd_similar,
        "collections": cmd_collections,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
