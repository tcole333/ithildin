#!/usr/bin/env python3
"""
Louisiana property records via Socrata SODA API.

Queries parish-level open data portals for property ownership, tax rolls,
parcel data, and adjudicated (tax-defaulted) properties.

Supported parishes:
  - East Baton Rouge (data.brla.gov): Tax Roll, Tax Parcel, Property Info, Adjudicated

Datasets (EBR):
  - Tax Roll (myfc-nh6n): Taxpayer names, addresses, assessed values, legal descriptions
  - Tax Parcel (ei2c-krsr): Owner, physical address, sale year, value breakdowns, GeoJSON
  - Property Info (re5c-hrw9): Full address, zoning, land use (no owner field)
  - Adjudicated (a4h4-zi7e): Tax-defaulted properties with owner and assessed value

Usage:
    python tools/query_la_property.py owner "SMITH" --parish ebr
    python tools/query_la_property.py address "MAIN ST" --parish ebr
    python tools/query_la_property.py parcel "011-0499-3" --parish ebr
    python tools/query_la_property.py details "1104993" --parish ebr
    python tools/query_la_property.py adjudicated "SMITH" --parish ebr
    python tools/query_la_property.py parishes
"""

import argparse
import json
import os
import sqlite3
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

try:
    from tools.lead_tracker import log_search
except ImportError:
    from lead_tracker import log_search

# Load .env for optional app token
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"'))

# Rate limiting between SODA requests
RATE_LIMIT_DELAY = 0.5

# Parish configurations
PARISHES = {
    "ebr": {
        "name": "East Baton Rouge",
        "base_url": "https://data.brla.gov/resource",
        "token_env": "BRLA_SODA_APP_TOKEN",
        "datasets": {
            "tax_roll": "myfc-nh6n",
            "tax_parcel": "ei2c-krsr",
            "property_info": "re5c-hrw9",
            "adjudicated": "a4h4-zi7e",
        },
    },
}

DEFAULT_PARISH = "ebr"


def _soda_request(parish_key, dataset_key, params, limit=50, timeout=60):
    """Make a SODA API request to a parish open data portal."""
    parish = PARISHES[parish_key]
    dataset_id = parish["datasets"][dataset_key]
    url = f"{parish['base_url']}/{dataset_id}.json"
    params["$limit"] = limit

    token = os.environ.get(parish["token_env"])
    if token:
        params["$$app_token"] = token

    full_url = url + "?" + urlencode(params)
    headers = {"Accept": "application/json"}
    req = Request(full_url, headers=headers)

    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except TimeoutError:
        print(f"ERROR: Request timed out ({timeout}s). Try a more specific query.", file=sys.stderr)
        return []
    except HTTPError as e:
        body = e.read().decode()[:500]
        print(f"ERROR: HTTP {e.code}: {body}", file=sys.stderr)
        return []
    except URLError as e:
        print(f"ERROR: {e.reason}", file=sys.stderr)
        return []


def _format_assessment_no(raw_digits):
    """Convert raw assessment digits to formatted NNN-NNNN-N.

    EBR assessment_no_new is numeric (e.g. 3076237), but assessment_num
    in the Tax Parcel dataset is zero-padded to 8 digits and formatted
    as NNN-NNNN-N (e.g. 030-7623-7).
    """
    padded = raw_digits.zfill(8)
    return f"{padded[:3]}-{padded[3:7]}-{padded[7:]}"


def _format_money(val):
    """Format a numeric string as currency."""
    try:
        n = float(val)
        if n == 0:
            return "$0"
        return f"${n:,.0f}"
    except (ValueError, TypeError):
        return str(val) if val else ""


def _print_tax_roll_record(rec):
    """Print a formatted Tax Roll record."""
    name = rec.get("taxpayer_name", "?")
    addr1 = rec.get("taxpayer_addr_1", "")
    addr2 = rec.get("taxpayer_addr_2", "")
    assess = rec.get("assessment_no", rec.get("assessment_no_new", ""))
    fmv = _format_money(rec.get("fair_market_val"))
    assessed = _format_money(rec.get("total_value"))
    legal = rec.get("legal_description", "")
    year = rec.get("tax_year", "")
    homestead = rec.get("homestead_exempt_type", "")
    vacant = rec.get("vacant_lot_yn", "")
    freeze = rec.get("tax_freeze", "")

    print(f"  {name}")
    print(f"    Assessment: {assess} | Tax Year: {year}")
    if addr1:
        print(f"    Address: {addr1}")
    if addr2:
        print(f"    City/State: {addr2}")
    if fmv:
        print(f"    Fair Market Value: {fmv} | Assessed: {assessed}")
    if homestead and homestead != "NO":
        extra = f" | Tax Freeze: {freeze}" if freeze and freeze != "NONE" else ""
        print(f"    Homestead Exempt: {homestead}{extra}")
    if vacant == "YES":
        print(f"    Vacant Lot: YES")
    if legal:
        print(f"    Legal: {legal}")
    print()


def _print_parcel_record(rec):
    """Print a formatted Tax Parcel record."""
    owner = rec.get("owner", "?")
    addr = rec.get("physical_address", "")
    owner_addr = rec.get("owner_address", "")
    owner_csz = rec.get("owner_city_state_zip", "")
    assess = rec.get("assessment_num", "")
    subdiv = rec.get("subdivision", "")
    fmv = _format_money(rec.get("sum_fair_market_value"))
    land = _format_money(rec.get("sum_land_value"))
    improvement = _format_money(rec.get("sum_improvement_value"))
    assessed = _format_money(rec.get("sum_assessed_value"))
    sale_year = rec.get("sale_year", "")
    flood = rec.get("flood_zone", "")

    print(f"  {owner}")
    print(f"    Assessment: {assess}")
    if addr:
        print(f"    Property: {addr}")
    if owner_addr:
        line = owner_addr
        if owner_csz:
            line += f", {owner_csz}"
        print(f"    Owner Address: {line}")
    if subdiv:
        print(f"    Subdivision: {subdiv}")
    if fmv:
        print(f"    FMV: {fmv} | Land: {land} | Improvement: {improvement} | Assessed: {assessed}")
    if sale_year:
        print(f"    Last Sale Year: {sale_year}")
    if flood:
        print(f"    Flood Zone: {flood}")
    print()


def cmd_owner(args):
    """Search property records by owner/taxpayer name."""
    parish = args.parish
    timeout = args.timeout
    name = args.query.upper().replace("'", "''")

    # Search Tax Roll by taxpayer_name
    where = f"upper(taxpayer_name) like '%{name}%'"
    tax_results = _soda_request(parish, "tax_roll", {"$where": where}, limit=args.limit, timeout=timeout)
    time.sleep(RATE_LIMIT_DELAY)

    # Search Tax Parcel by owner
    where = f"upper(owner) like '%{name}%'"
    parcel_results = _soda_request(parish, "tax_parcel", {"$where": where}, limit=args.limit, timeout=timeout)

    total = len(tax_results) + len(parcel_results)
    parish_name = PARISHES[parish]["name"]
    print(f"Found {len(tax_results)} tax roll + {len(parcel_results)} parcel records for '{args.query}' in {parish_name}")
    print()

    log_search(args.query, f"la_property_{parish}", total)

    combined = {"query": args.query, "parish": parish, "tax_roll": tax_results, "parcels": parcel_results}
    if write_output(combined, args, summary=f"LA property owner '{args.query}' ({parish_name})"):
        return

    if tax_results:
        print(f"--- Tax Roll ({len(tax_results)} records) ---")
        print()
        for rec in tax_results[:args.max_results]:
            _print_tax_roll_record(rec)

    if parcel_results:
        print(f"--- Tax Parcels ({len(parcel_results)} records) ---")
        print()
        for rec in parcel_results[:args.max_results]:
            _print_parcel_record(rec)

    shown = min(len(tax_results), args.max_results) + min(len(parcel_results), args.max_results)
    if total > shown:
        print(f"  ... {total - shown} more records (use --max-results or --output to see all)")


def cmd_address(args):
    """Search property records by address."""
    parish = args.parish
    timeout = args.timeout
    addr = args.query.upper().replace("'", "''")

    # Search Tax Parcel by physical_address
    where = f"upper(physical_address) like '%{addr}%'"
    parcel_results = _soda_request(parish, "tax_parcel", {"$where": where}, limit=args.limit, timeout=timeout)
    time.sleep(RATE_LIMIT_DELAY)

    # Search Property Info by full_address
    where = f"upper(full_address) like '%{addr}%'"
    info_results = _soda_request(parish, "property_info", {"$where": where}, limit=args.limit, timeout=timeout)

    total = len(parcel_results) + len(info_results)
    parish_name = PARISHES[parish]["name"]
    print(f"Found {len(parcel_results)} parcel + {len(info_results)} property info records for '{args.query}' in {parish_name}")
    print()

    log_search(args.query, f"la_property_{parish}", total)

    combined = {"query": args.query, "parish": parish, "parcels": parcel_results, "property_info": info_results}
    if write_output(combined, args, summary=f"LA property address '{args.query}' ({parish_name})"):
        return

    if parcel_results:
        print(f"--- Tax Parcels ({len(parcel_results)} records) ---")
        print()
        for rec in parcel_results[:args.max_results]:
            _print_parcel_record(rec)

    if info_results:
        print(f"--- Property Info ({len(info_results)} records) ---")
        print()
        for rec in info_results[:args.max_results]:
            addr_str = rec.get("full_address", "?")
            city = rec.get("city", "")
            zoning = rec.get("zoning_type", "")
            land_use = rec.get("existing_land_use", "")
            lot_id = rec.get("lot_id", "")
            acres = rec.get("area_meas_acres", "")
            print(f"  {addr_str}, {city}")
            print(f"    Lot: {lot_id} | Zoning: {zoning} | Land Use: {land_use} | Acres: {acres}")
            print()

    shown = min(len(parcel_results), args.max_results) + min(len(info_results), args.max_results)
    if total > shown:
        print(f"  ... {total - shown} more records (use --max-results or --output to see all)")


def cmd_parcel(args):
    """Look up a specific parcel by assessment number."""
    parish = args.parish
    timeout = args.timeout
    assess = args.assessment_no.replace("-", "").strip()

    # Try assessment_no_new (numeric) on Tax Roll
    tax_results = _soda_request(parish, "tax_roll", {"assessment_no_new": assess}, limit=10, timeout=timeout)
    time.sleep(RATE_LIMIT_DELAY)

    # Also try formatted assessment_no (NNN-NNNN-N)
    if not tax_results and "-" not in args.assessment_no and assess.isdigit():
        formatted = _format_assessment_no(assess)
        where = f"assessment_no = '{formatted}'"
        tax_results = _soda_request(parish, "tax_roll", {"$where": where}, limit=10, timeout=timeout)
        time.sleep(RATE_LIMIT_DELAY)

    # Search Tax Parcel by assessment_num (formatted NNN-NNNN-N)
    parcel_key = _format_assessment_no(assess) if assess.isdigit() else args.assessment_no
    parcel_results = _soda_request(parish, "tax_parcel", {"assessment_num": parcel_key}, limit=10, timeout=timeout)

    total = len(tax_results) + len(parcel_results)
    parish_name = PARISHES[parish]["name"]
    print(f"Found {len(tax_results)} tax roll + {len(parcel_results)} parcel records for assessment '{args.assessment_no}' in {parish_name}")
    print()

    log_search(f"parcel:{args.assessment_no}", f"la_property_{parish}", total)

    combined = {"assessment_no": args.assessment_no, "parish": parish, "tax_roll": tax_results, "parcels": parcel_results}
    if write_output(combined, args, summary=f"LA parcel '{args.assessment_no}' ({parish_name})"):
        return

    for rec in tax_results:
        _print_tax_roll_record(rec)
    for rec in parcel_results:
        _print_parcel_record(rec)


def cmd_details(args):
    """Cross-dataset detail view for a single parcel."""
    parish = args.parish
    timeout = args.timeout
    raw = args.assessment_no.replace("-", "").strip()

    # Tax Roll — uses assessment_no_new (digits only)
    tax_results = _soda_request(parish, "tax_roll", {"assessment_no_new": raw}, limit=10, timeout=timeout)
    time.sleep(RATE_LIMIT_DELAY)

    # Tax Parcel — uses formatted assessment_num (NNN-NNNN-N)
    formatted = _format_assessment_no(raw) if raw.isdigit() else args.assessment_no
    parcel_results = _soda_request(parish, "tax_parcel", {"assessment_num": formatted}, limit=10, timeout=timeout)
    time.sleep(RATE_LIMIT_DELAY)

    # Property Info — join via address from parcel
    info_results = []
    if parcel_results:
        phys_addr = parcel_results[0].get("physical_address", "")
        if phys_addr:
            safe_addr = phys_addr.upper().replace("'", "''")
            where = f"upper(full_address) = '{safe_addr}'"
            info_results = _soda_request(parish, "property_info", {"$where": where}, limit=10, timeout=timeout)

    parish_name = PARISHES[parish]["name"]
    total = len(tax_results) + len(parcel_results) + len(info_results)
    print(f"Detail view for assessment {args.assessment_no} in {parish_name}")
    print(f"  Tax Roll: {len(tax_results)} | Parcel: {len(parcel_results)} | Property Info: {len(info_results)}")
    print()

    log_search(f"details:{args.assessment_no}", f"la_property_{parish}", total)

    combined = {
        "assessment_no": args.assessment_no, "parish": parish,
        "tax_roll": tax_results, "parcels": parcel_results, "property_info": info_results,
    }
    if write_output(combined, args, summary=f"LA detail '{args.assessment_no}' ({parish_name})"):
        return

    if tax_results:
        print("--- Tax Roll ---")
        print()
        for rec in tax_results:
            _print_tax_roll_record(rec)

    if parcel_results:
        print("--- Tax Parcel ---")
        print()
        for rec in parcel_results:
            _print_parcel_record(rec)

    if info_results:
        print("--- Property Info ---")
        print()
        for rec in info_results:
            addr = rec.get("full_address", "?")
            city = rec.get("city", "")
            zoning = rec.get("zoning_type", "")
            land_use = rec.get("existing_land_use", "")
            future_use = rec.get("future_land_use", "")
            design = rec.get("design_level", "")
            acres = rec.get("area_meas_acres", "")
            fire = rec.get("fire_district", "")
            school = rec.get("school_district", "")
            flood_data = ""
            if parcel_results:
                flood_data = parcel_results[0].get("flood_zone", "")

            print(f"  {addr}, {city}")
            print(f"    Zoning: {zoning} | Land Use: {land_use} | Future: {future_use}")
            print(f"    Design Level: {design} | Acres: {acres}")
            print(f"    Fire: {fire} | School: {school}")
            if flood_data:
                print(f"    Flood Zone: {flood_data}")
            print()


def cmd_adjudicated(args):
    """Search tax-defaulted (adjudicated) properties."""
    parish = args.parish
    timeout = args.timeout
    name = args.query.upper().replace("'", "''")

    where = f"upper(owner) like '%{name}%'"
    results = _soda_request(parish, "adjudicated", {"$where": where}, limit=args.limit, timeout=timeout)

    parish_name = PARISHES[parish]["name"]
    print(f"Found {len(results)} adjudicated properties for '{args.query}' in {parish_name}")
    print()

    log_search(f"adjudicated:{args.query}", f"la_property_{parish}", len(results))

    if write_output(results, args, summary=f"LA adjudicated '{args.query}' ({parish_name})"):
        return

    for rec in results[:args.max_results]:
        owner = rec.get("owner", "?")
        assess = rec.get("assessment_num", "")
        addr = rec.get("physadd", "")
        city = rec.get("owncity", "")
        assessed = _format_money(rec.get("sum_tol_as"))
        fmv = _format_money(rec.get("sum_fair_m"))
        tax_year = rec.get("tax_roll_year", "")
        council = rec.get("council_district_no", "")
        subdiv = rec.get("subd", "")

        print(f"  {owner}")
        print(f"    Assessment: {assess} | Tax Year: {tax_year}")
        if addr:
            print(f"    Address: {addr}")
        if city:
            print(f"    Owner City: {city}")
        if fmv:
            print(f"    FMV: {fmv} | Assessed: {assessed}")
        if subdiv:
            print(f"    Subdivision: {subdiv}")
        if council:
            print(f"    Council District: {council}")
        print()

    if len(results) > args.max_results:
        print(f"  ... {len(results) - args.max_results} more records")


def cmd_parishes(args):
    """List supported parishes and their data sources."""
    data = []
    for key, cfg in PARISHES.items():
        entry = {
            "key": key,
            "name": cfg["name"],
            "base_url": cfg["base_url"],
            "datasets": list(cfg["datasets"].keys()),
        }
        data.append(entry)

    if write_output(data, args, summary="LA property supported parishes"):
        return

    print("Supported Louisiana parishes:")
    print()
    for key, cfg in PARISHES.items():
        print(f"  {key}: {cfg['name']}")
        print(f"    Portal: {cfg['base_url']}")
        print(f"    Datasets: {', '.join(cfg['datasets'].keys())}")
        print()
    print("Use --parish <key> to select (default: ebr)")


def main():
    parser = argparse.ArgumentParser(description="Louisiana property records via SODA API")
    sub = parser.add_subparsers(dest="command", required=True)

    # owner — search by taxpayer/owner name
    p = sub.add_parser("owner", help="Search by owner/taxpayer name")
    p.add_argument("query", help="Owner or taxpayer name to search")
    p.add_argument("--parish", default=DEFAULT_PARISH, choices=list(PARISHES.keys()), help="Parish to search")
    p.add_argument("--limit", type=int, default=50, help="Max records per dataset")
    p.add_argument("--max-results", type=int, default=20, help="Max records to display")
    p.add_argument("--timeout", type=int, default=60, help="Per-request timeout in seconds")
    add_output_args(p)

    # address — search by property address
    p = sub.add_parser("address", help="Search by property address")
    p.add_argument("query", help="Address or street name to search")
    p.add_argument("--parish", default=DEFAULT_PARISH, choices=list(PARISHES.keys()), help="Parish to search")
    p.add_argument("--limit", type=int, default=50, help="Max records per dataset")
    p.add_argument("--max-results", type=int, default=20, help="Max records to display")
    p.add_argument("--timeout", type=int, default=60, help="Per-request timeout in seconds")
    add_output_args(p)

    # parcel — look up by assessment number
    p = sub.add_parser("parcel", help="Look up by assessment number")
    p.add_argument("assessment_no", help="Assessment number (with or without dashes)")
    p.add_argument("--parish", default=DEFAULT_PARISH, choices=list(PARISHES.keys()), help="Parish to search")
    p.add_argument("--timeout", type=int, default=60, help="Per-request timeout in seconds")
    add_output_args(p)

    # details — cross-dataset detail view
    p = sub.add_parser("details", help="Cross-dataset detail view for a parcel")
    p.add_argument("assessment_no", help="Assessment number")
    p.add_argument("--parish", default=DEFAULT_PARISH, choices=list(PARISHES.keys()), help="Parish to search")
    p.add_argument("--timeout", type=int, default=60, help="Per-request timeout in seconds")
    add_output_args(p)

    # adjudicated — tax-defaulted properties
    p = sub.add_parser("adjudicated", help="Search tax-defaulted (adjudicated) properties")
    p.add_argument("query", help="Owner name to search")
    p.add_argument("--parish", default=DEFAULT_PARISH, choices=list(PARISHES.keys()), help="Parish to search")
    p.add_argument("--limit", type=int, default=50, help="Max records")
    p.add_argument("--max-results", type=int, default=20, help="Max records to display")
    p.add_argument("--timeout", type=int, default=60, help="Per-request timeout in seconds")
    add_output_args(p)

    # parishes — list supported parishes
    p = sub.add_parser("parishes", help="List supported parishes and data sources")
    add_output_args(p)

    args = parser.parse_args()

    commands = {
        "owner": cmd_owner,
        "address": cmd_address,
        "parcel": cmd_parcel,
        "details": cmd_details,
        "adjudicated": cmd_adjudicated,
        "parishes": cmd_parishes,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
