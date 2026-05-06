#!/usr/bin/env python3
"""
Florida UCC (Secured Transaction Registry) search via publicsearchapi.floridaucc.com.

No authentication required. JSON REST API backed by the Florida Secured
Transaction Registry — UCC-1, UCC-3 filings under Chapter 679, Fla. Stat.

Data current through: see /filings-completed-through-date endpoint (refreshed daily).

Usage:
    python tools/query_florida_ucc.py search-org "COMPANY NAME"
    python tools/query_florida_ucc.py search-org "COMPANY NAME" --lapsed --all
    python tools/query_florida_ucc.py search-individual "LAST FIRST"
    python tools/query_florida_ucc.py search-individual "SMITH JOHN" --lapsed
    python tools/query_florida_ucc.py filing 202501545298
    python tools/query_florida_ucc.py search-org "COMPANY NAME" --output results.json
"""

import argparse
import sys
import time

import requests

try:
    from tools.output_util import add_output_args, write_output
    from tools.lead_tracker import log_search
except ImportError:
    from output_util import add_output_args, write_output
    from lead_tracker import log_search

API_BASE = "https://publicsearchapi.floridaucc.com"
RATE_LIMIT_DELAY = 0.5
SOURCE_NAME = "florida_ucc"
MAX_PAGES = 20  # safety cap on auto-pagination


def _get(path, params=None, timeout=30):
    """GET from publicsearchapi.floridaucc.com with basic rate-limiting."""
    url = f"{API_BASE}/{path}"
    time.sleep(RATE_LIMIT_DELAY)
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if data.get("notOk"):
        msgs = "; ".join(m.get("message", "") for m in data.get("messages", []))
        print(f"API error: {msgs}", file=sys.stderr)
        sys.exit(1)
    return data.get("payload")


def _search_page(text, search_type, sub_option, category, row_number=None):
    """Single page of search results. Returns payload dict."""
    params = {
        "text": text,
        "searchOptionType": search_type,
        "searchOptionSubOption": sub_option,
        "searchCategory": category,
        "rowNumber": row_number or "",
    }
    return _get("search", params)


def _all_pages(text, search_type, sub_option, category):
    """Paginate through all results up to MAX_PAGES. Returns flat list of debtors."""
    results = []
    row_number = None
    for _ in range(MAX_PAGES):
        page = _search_page(text, search_type, sub_option, category, row_number)
        debtors = page.get("debtors") or []
        results.extend(debtors)
        next_rn = page.get("nextRowNumber")
        if not next_rn or not debtors:
            break
        row_number = next_rn
    return results


def search_org(name, status="filed", all_pages=False, proximity=False):
    """
    Search organization (corporate) debtor filings.

    Args:
        name: Organization name
        status: 'filed' | 'lapsed' | 'all'
        all_pages: If True, paginate through all results
        proximity: If True, use proximity search instead of standard search logic

    Returns:
        dict with query metadata and list of matching debtors
    """
    status_map = {
        "filed": "FiledCompactDebtorNameList",
        "lapsed": "LapsedCompactDebtorNameList",
        "all": "FiledAndLapsedCompactDebtorNameList",
    }
    sub_option = status_map.get(status, "FiledCompactDebtorNameList")
    category = "Standard" if proximity else "Exact"

    try:
        log_search(SOURCE_NAME, f"org:{name}", {"status": status})
    except Exception:
        pass

    if all_pages:
        debtors = _all_pages(name, "OrganizationDebtorName", sub_option, category)
        total = len(debtors)
    else:
        page = _search_page(name, "OrganizationDebtorName", sub_option, category)
        debtors = page.get("debtors") or []
        total = page.get("totalExactMatches") or len(debtors)

    return {
        "query": name,
        "search_type": "OrganizationDebtorName",
        "status_filter": status,
        "search_logic": "proximity" if proximity else "standard",
        "total_matches": total,
        "returned": len(debtors),
        "source": "florida_ucc",
        "source_url": "https://floridaucc.com/search",
        "debtors": debtors,
    }


def search_individual(name, status="filed"):
    """
    Search individual debtor filings.

    Args:
        name: Individual name in "LAST FIRST" or "LAST FIRST MIDDLE" format
        status: 'filed' | 'lapsed' | 'all'

    Returns:
        dict with query metadata and list of matching debtors
    """
    status_map = {
        "filed": "FiledCompactDebtorNameList",
        "lapsed": "LapsedCompactDebtorNameList",
        "all": "FiledAndLapsedCompactDebtorNameList",
    }
    sub_option = status_map.get(status, "FiledCompactDebtorNameList")

    try:
        log_search(SOURCE_NAME, f"individual:{name}", {"status": status})
    except Exception:
        pass

    page = _search_page(name, "IndividualDebtorName", sub_option, "")
    debtors = page.get("debtors") or []
    total = page.get("totalExactMatches") or len(debtors)

    return {
        "query": name,
        "search_type": "IndividualDebtorName",
        "status_filter": status,
        "total_matches": total,
        "returned": len(debtors),
        "source": "florida_ucc",
        "source_url": "https://floridaucc.com/search",
        "debtors": debtors,
    }


def get_filing(ucc_number):
    """
    Fetch full filing detail by UCC document number.

    Args:
        ucc_number: UCC filing number (e.g. 202501545298)

    Returns:
        dict with full filing detail including debtors, secured parties, events
    """
    try:
        log_search(SOURCE_NAME, f"filing:{ucc_number}", {})
    except Exception:
        pass

    params = {
        "searchOptionType": "DocumentNumber",
        "filingNumber": ucc_number,
    }
    payload = _get("filing-details", params)

    # Normalize dates for readability
    def _fmt(dt_str):
        if not dt_str:
            return None
        return dt_str[:10]  # ISO date portion

    return {
        "ucc_number": payload.get("uccNumber"),
        "status": payload.get("status"),
        "date_filed": _fmt(payload.get("fileDate")),
        "expiration_date": _fmt(payload.get("expirationDate")),
        "filings_completed_through": _fmt(payload.get("filingsCompletedThrough")),
        "document_type": payload.get("documentType"),
        "ucc1_number": payload.get("ucc1Number"),
        "filing_events": payload.get("filingEvents"),
        "secured_parties_count": payload.get("securedPartiesTotalCount"),
        "debtor_parties_count": payload.get("debtorPartiesTotalCount"),
        "total_pages": payload.get("numberOfPagesInAllAssociatedForms"),
        "image_available": payload.get("fileImageExists", False),
        "debtors": payload.get("debtors", []),
        "secured_parties": payload.get("secureds", []),
        "source": "florida_ucc",
        "source_url": f"https://floridaucc.com/search?text={ucc_number}&searchOptionType=DocumentNumber",
    }


def _print_debtor_row(d):
    print(f"  {d.get('name','')}")
    addr_parts = [
        d.get("address", ""),
        d.get("city", ""),
        d.get("state", ""),
        d.get("zipCode", ""),
    ]
    print(f"    {', '.join(p for p in addr_parts if p)}")
    print(f"    UCC: {d.get('uccNumber','')}  Status: {d.get('status','')}")


def main():
    parser = argparse.ArgumentParser(
        description="Florida UCC Secured Transaction Registry search"
    )
    sub = parser.add_subparsers(dest="command")

    # search-org
    sorg = sub.add_parser("search-org", help="Search organization debtor filings")
    sorg.add_argument("name", help="Organization name")
    sorg.add_argument(
        "--lapsed", action="store_true",
        help="Search lapsed filings (default: filed only)"
    )
    sorg.add_argument(
        "--all", action="store_true", dest="all_status",
        help="Search both filed and lapsed filings"
    )
    sorg.add_argument(
        "--proximity", action="store_true",
        help="Use proximity search instead of standard search logic"
    )
    sorg.add_argument(
        "--paginate", action="store_true",
        help="Auto-paginate through all results (up to 20 pages)"
    )
    add_output_args(sorg)

    # search-individual
    sind = sub.add_parser("search-individual", help="Search individual debtor filings")
    sind.add_argument("name", help="Name in LAST FIRST format")
    sind.add_argument("--lapsed", action="store_true", help="Search lapsed filings")
    sind.add_argument("--all", action="store_true", dest="all_status", help="Filed + lapsed")
    add_output_args(sind)

    # filing detail
    sfil = sub.add_parser("filing", help="Fetch filing detail by UCC number")
    sfil.add_argument("ucc_number", help="UCC document number (e.g. 202501545298)")
    add_output_args(sfil)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "search-org":
        status = "all" if args.all_status else ("lapsed" if args.lapsed else "filed")
        results = search_org(
            args.name,
            status=status,
            all_pages=args.paginate,
            proximity=args.proximity,
        )
        if not write_output(results, args, summary=f"FL UCC org search '{args.name}'"):
            print(f"\nFL UCC — Organization search: '{args.name}'")
            print(f"Status filter: {results['status_filter']} | Logic: {results['search_logic']}")
            print(f"Results: {results['returned']} returned", end="")
            if results["total_matches"]:
                print(f" (total matched: {results['total_matches']})", end="")
            print()
            for d in results["debtors"]:
                _print_debtor_row(d)

    elif args.command == "search-individual":
        status = "all" if args.all_status else ("lapsed" if args.lapsed else "filed")
        results = search_individual(args.name, status=status)
        if not write_output(results, args, summary=f"FL UCC individual search '{args.name}'"):
            print(f"\nFL UCC — Individual search: '{args.name}'")
            print(f"Results: {results['returned']} returned")
            for d in results["debtors"]:
                _print_debtor_row(d)

    elif args.command == "filing":
        results = get_filing(args.ucc_number)
        if not write_output(results, args, summary=f"FL UCC filing {args.ucc_number}"):
            print(f"\nFL UCC Filing: {results['ucc_number']}")
            print(f"  Status: {results['status']}")
            print(f"  Type: {results['document_type']}")
            print(f"  Filed: {results['date_filed']}")
            print(f"  Expires: {results['expiration_date']}")
            print(f"  Image available: {results['image_available']}")
            print(f"\n  Debtors ({results['debtor_parties_count']}):")
            for d in results["debtors"]:
                print(f"    {d.get('name','')} — {d.get('address','')}, {d.get('city','')}, {d.get('state','')} {d.get('zipCode','')}")
            print(f"\n  Secured Parties ({results['secured_parties_count']}):")
            for s in results["secured_parties"]:
                print(f"    {s.get('name','')} — {s.get('address','')}, {s.get('city','')}, {s.get('state','')} {s.get('zipCode','')}")


if __name__ == "__main__":
    main()
