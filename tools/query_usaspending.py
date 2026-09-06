#!/usr/bin/env python3
"""
USAspending.gov API wrapper for government contract research.

Searches for federal award spending, recipient profiles, and entity hierarchies
to identify wealth flows from the US Treasury to investigation targets.

API: https://api.usaspending.gov/
Auth: None required for public API.
Rate Limits: 10 requests per second (approx).

Usage:
    uv run python tools/query_usaspending.py search "Palantir"
    uv run python tools/query_usaspending.py recipient "Palantir Technologies"
    uv run python tools/query_usaspending.py awards "PALANTIR TECHNOLOGIES INC." --limit 10
    uv run python tools/query_usaspending.py awards --uei "RN99S3S7N977"
    uv run python tools/query_usaspending.py transactions-keyword "skip tracing" --all-pages

Structured output (--output/--json) uses an envelope with query, retrieval,
status, errors, and results. Former bare row lists now live under results;
recipient and award detail fields remain available at the top level. A successful
empty response has status=success. Acquisition failures write the envelope before
exiting 1, retaining any rows already acquired with status=partial. A requested
single page can succeed while retrieval.complete is false; the keyword safety
cap instead has status=partial, errors=[], and a continuation page (exit 0).
retrieval.complete is null when the API does not report pagination coverage.
"""

import argparse
import json
import os
import re
import ssl
import sys
from datetime import date, datetime, timezone
from http.client import HTTPException
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# Global SSL context — use certifi bundle (system store may be stale)
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()
if os.environ.get("OSINT_INSECURE_SSL") == "true" or os.environ.get("PYTHONHTTPSVERIFY") == "0":
    SSL_CONTEXT.check_hostname = False
    SSL_CONTEXT.verify_mode = ssl.CERT_NONE

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

BASE_URL = "https://api.usaspending.gov/api/v2"

# Award types for contracts (A: B: C: D: )
CONTRACT_AWARD_TYPES = ["A", "B", "C", "D"]
# Other award types if needed (Grants: 02, 03, 04, 05; Loans: 07, 08; Insurance: 09; Direct Payments: 10, 11)
GRANT_AWARD_TYPES = ["02", "03", "04", "05"]
LOAN_AWARD_TYPES = ["07", "08"]
IDV_AWARD_TYPES = ["IDV_A", "IDV_B", "IDV_B_A", "IDV_B_B", "IDV_B_C", "IDV_C", "IDV_D", "IDV_E"]

# COVID-19 Disaster Emergency Fund Codes (DEFC)
COVID_DEFC = ["L", "M", "N", "O", "P", "U", "V"]
ADVANCED_SEARCH_LIMIT_MAX = 100


def _advanced_search_limit(value):
    """Validate page sizes accepted by USAspending advanced-search endpoints."""
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("limit must be an integer") from exc
    if not 1 <= limit <= ADVANCED_SEARCH_LIMIT_MAX:
        raise argparse.ArgumentTypeError(
            f"limit must be between 1 and {ADVANCED_SEARCH_LIMIT_MAX}"
        )
    return limit


def _positive_page(value):
    try:
        page = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("page must be a positive integer") from exc
    if page < 1:
        raise argparse.ArgumentTypeError("page must be a positive integer")
    return page


def _agency_filter(args):
    """Build an awarding-agency filter with an explicit hierarchy tier."""
    agency = getattr(args, "agency", None)
    if not agency:
        return None
    return {
        "type": "awarding",
        "tier": getattr(args, "agency_tier", None) or "toptier",
        "name": agency,
    }

class AcquisitionError(Exception):
    """An upstream response could not be acquired or parsed."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def _read_response(req, **kwargs):
    try:
        with urlopen(req, timeout=60, context=SSL_CONTEXT, **kwargs) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as exc:
        body = exc.read().decode(errors="replace")[:500]
        raise AcquisitionError("http", f"HTTP {exc.code}: {body}") from exc
    except (URLError, OSError, HTTPException) as exc:
        raise AcquisitionError("transport", str(getattr(exc, "reason", exc))) from exc
    except (ValueError, UnicodeError) as exc:
        raise AcquisitionError("invalid_response", f"Invalid JSON response: {exc}") from exc


def _fetch_post(endpoint, data):
    """Fetch from USAspending API using POST."""
    url = f"{BASE_URL}{endpoint}"
    req = Request(url, method="POST", headers={
        "Content-Type": "application/json",
        "User-Agent": "OSINT-Research/1.0",
    })
    
    return _read_response(req, data=json.dumps(data).encode())

def _fetch_get(endpoint, params=None):
    """Fetch from USAspending API using GET."""
    query = f"?{urlencode(params)}" if params else ""
    url = f"{BASE_URL}{endpoint}{query}"
    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "OSINT-Research/1.0",
    })
    
    return _read_response(req)


class _Query:
    """Keep request provenance and errors local to one command invocation."""

    def __init__(self, args, command):
        self.args = args
        self.query = {
            key: value for key, value in vars(args).items()
            if key not in {"output", "json_out", "command"}
        }
        self.query["command"] = command
        self.requests = []
        self.errors = []

    def error(self, kind, message, **context):
        self.errors.append({"kind": kind, "message": message, **context})
        print(f"ERROR: {message}", file=sys.stderr)

    def fetch(self, endpoint, payload=None, *, detail=False, allow_list=False):
        request = {"endpoint": endpoint, "method": "GET" if payload is None else "POST"}
        if payload is not None:
            request["payload"] = payload
        self.requests.append(request)
        try:
            response = (
                _fetch_get(endpoint) if payload is None
                else _fetch_post(endpoint, payload)
            )
            if allow_list and isinstance(response, list):
                response = {"results": response}
            if not isinstance(response, dict) or (detail and not response):
                raise AcquisitionError("invalid_response", "Expected a JSON object response")
            if not detail:
                rows = response.get("results")
                if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                    raise AcquisitionError("invalid_response", "Expected a results list of objects")
                request["returned_count"] = len(rows)
            request["status"] = "success"
            request["page_metadata"] = response.get("page_metadata")
            if "messages" in response:
                request["messages"] = response["messages"]
            return response
        except AcquisitionError as exc:
            request["status"] = "error"
            self.error(exc.kind, str(exc), endpoint=endpoint)
            return None

    def write(self, results, *, summary, extra=None, pagination=None, partial=False):
        """Emit before exiting on failure, including successfully acquired rows."""
        output = dict(extra or {})
        query = {**self.query, **output.pop("query", {})}
        continuation = (pagination or {}).get("has_next")
        complete = not (
            self.errors or partial or continuation
            or (pagination or {}).get("requested_page", 1) > 1
        )
        if complete and pagination is not None and continuation is None:
            complete = None  # The API did not report whether more rows exist.
        output.update({
            "query": query,
            "retrieval": {
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "complete": complete,
                "requests": self.requests,
            },
            "status": (
                "partial" if (self.errors and results) or partial
                else "error" if self.errors else "success"
            ),
            "errors": self.errors,
            "results": results,
        })
        if pagination is not None:
            output["pagination"] = pagination
        handled = write_output(
            output, self.args, summary=summary,
            result_count=None if output["status"] == "error" else len(results),
        )
        if self.errors:
            if not handled:
                print(json.dumps(output, indent=2))
            raise SystemExit(1)
        return handled


def _pagination(response, payload):
    metadata = (response or {}).get("page_metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    page = payload.get("page", 1)
    return {
        "requested_page": page,
        "requested_limit": payload.get("limit"),
        "returned_count": len((response or {}).get("results", [])),
        "reported_total": metadata.get("total"),
        "has_next": metadata.get("hasNext"),
        "next_page": metadata.get("next") or (page + 1 if metadata.get("hasNext") else None),
        "raw": metadata,
    }

def cmd_search(args):
    """Search for recipients using the autocomplete endpoint."""
    run = _Query(args, "search")
    data = {"search_text": args.query}
    result = run.fetch("/autocomplete/recipient/", data)
    results = (result or {}).get("results", [])
    
    if run.write(results, summary=f"USAspending search '{args.query}'"):
        return

    print(f"Found {len(results)} recipient matches for '{args.query}':")
    for r in results:
        uei = r.get("uei") or "N/A"
        duns = r.get("duns") or "N/A"
        print(f"  {r.get('recipient_name')} (UEI: {uei}, DUNS: {duns})")

def cmd_awards(args):
    """Search for specific awards by recipient name or UEI."""
    run = _Query(args, "awards")
    # Group types: contracts (A, B, C, D), grants (02, 03, 04, 05), loans (07, 08), insurance (09), direct payments (10, 11)
    # The API throws a 422 if you mix these groups.
    if args.grants:
        award_types = GRANT_AWARD_TYPES
    else:
        award_types = CONTRACT_AWARD_TYPES

    filters = {
        "award_type_codes": award_types
    }
    
    if args.uei:
        filters["recipient_search_text"] = [args.uei]
    else:
        filters["recipient_search_text"] = [args.query]

    if args.agency:
        filters["agencies"] = [{"type": "awarding", "tier": "toptier", "name": args.agency}]

    data = {
        "filters": filters,
        "fields": [
            "Award ID", "Recipient Name", "Start Date", "End Date", 
            "Award Amount", "Description", "Awarding Agency", 
            "Awarding Sub Agency", "Contract Award Type"
        ],
        "limit": args.limit,
        "page": args.page
    }
    
    result = run.fetch("/search/spending_by_award/", data)
    results = (result or {}).get("results", [])
    
    if run.write(results, summary=f"USAspending awards for '{args.query or args.uei}'",
                 pagination=_pagination(result, data)):
        return

    print(f"Found {len(results)} awards (Limit: {args.limit}):")
    for r in results:
        amt = _fmt_money(r.get('Award Amount'))
        print(f"  {r.get('Award ID')} | {amt} | {r.get('Recipient Name')}")
        print(f"    Agency: {r.get('Awarding Agency')} / {r.get('Awarding Sub Agency')}")
        print(f"    Dates: {r.get('Start Date')} to {r.get('End Date')}")
        print(f"    Desc: {(r.get('Description') or '')[:100]}...")
        print()

def cmd_recipient(args):
    """Get detailed recipient profile and children/parent info."""
    run = _Query(args, "recipient")
    # First find the recipient to get the hash (required for profile endpoint)
    search_data = {"search_text": args.query}
    search_result = run.fetch("/autocomplete/recipient/", search_data)
    
    if not (search_result or {}).get("results"):
        if not run.write([], summary=f"USAspending recipient '{args.query}'",
                         extra={"recipient": None, "spending_by_agency": None}):
            print(f"No recipient found matching '{args.query}'")
        return

    # Use the first match
    recipient = search_result["results"][0]
    recipient_name = recipient.get("recipient_name")
    uei = recipient.get("uei")

    # Get spending over time for this recipient
    spending_data = {
        "filters": {
            "recipient_search_text": [uei if uei else recipient_name],
            "award_type_codes": CONTRACT_AWARD_TYPES
        }
    }
    
    # Spending by agency
    agency_spending = run.fetch("/search/spending_by_category/awarding_agency/", spending_data)
    agency_results = (
        agency_spending.get("results", [])
        if isinstance(agency_spending, dict)
        else None
    )
    summary = {
        "recipient": recipient,
        "spending_by_agency": agency_results,
    }
    if run.write(
        [recipient],
        extra=summary,
        pagination=_pagination(agency_spending, spending_data),
        summary=f"USAspending recipient summary for '{args.query}'",
    ):
        return

    print(f"Recipient: {recipient_name}")
    print(f"UEI: {uei}")
    print("-" * 40)
    if agency_results:
        print("Spending by Agency:")
        for r in agency_results[:5]:
            print(f"  {r.get('name')}: ${r.get('amount', 0):,.2f}")
    
    print("\nUse 'awards' command to see individual contract details.")

def cmd_covid(args):
    """Search for COVID-19 relief awards (PPP, EIDL, etc) using DEFC.
    Searches multiple groups (contracts, grants, loans) separately to avoid API 422.
    """
    run = _Query(args, "covid")
    groups = {
        "Contracts": CONTRACT_AWARD_TYPES,
        "Grants": GRANT_AWARD_TYPES,
        "Loans": LOAN_AWARD_TYPES,
        "IDVs": IDV_AWARD_TYPES
    }
    
    all_results = []
    
    group_pagination = {}
    for group_name, types in groups.items():
        filters = {
            "def_codes": COVID_DEFC,
            "recipient_search_text": [args.query],
            "award_type_codes": types
        }
        
        data = {
            "filters": filters,
            "fields": [
                "Award ID", "Recipient Name", "Start Date", "End Date", 
                "Award Amount", "Description", "Awarding Agency", 
                "Awarding Sub Agency", "Contract Award Type"
            ],
            "limit": args.limit
        }
        
        result = run.fetch("/search/spending_by_award/", data)
        group_pagination[group_name] = _pagination(result, data)
        if result and result.get("results"):
            all_results.extend(result.get("results"))
            if len(all_results) >= args.limit:
                break

    results = all_results[:args.limit]
    unqueried_groups = [name for name in groups if name not in group_pagination]
    partial = bool(unqueried_groups) or len(all_results) > args.limit or any(
        page["has_next"] for page in group_pagination.values()
    )
    if run.write(results, summary=f"USAspending COVID awards for '{args.query}'",
                 extra={"group_pagination": group_pagination,
                        "unqueried_groups": unqueried_groups,
                        "omitted_count": len(all_results) - len(results)}, partial=partial):
        return
    
    if not results:
        print(f"No COVID-19 relief awards found for '{args.query}'")
        return

    print(f"Found {len(results)} COVID-19 relief awards:")
    for r in results:
        amount_val = r.get('Award Amount') or 0
        amt = f"${float(amount_val):,.2f}"
        print(f"  {r.get('Award ID')} | {amt} | {r.get('Recipient Name')}")
        print(f"    Agency: {r.get('Awarding Agency')}")
        desc = r.get('Description') or "No description"
        print(f"    Desc: {desc[:100]}...")
        print()

def cmd_loans(args):
    """Search specifically for loan awards (including PPP/EIDL)."""
    run = _Query(args, "loans")
    filters = {
        "award_type_codes": LOAN_AWARD_TYPES,
        "recipient_search_text": [args.query]
    }
    
    data = {
        "filters": filters,
        "fields": [
            "Award ID", "Recipient Name", "Start Date", "End Date", 
            "Award Amount", "Description", "Awarding Agency", 
            "Awarding Sub Agency"
        ],
        "limit": args.limit
    }
    
    result = run.fetch("/search/spending_by_award/", data)
    results = (result or {}).get("results", [])
    if run.write(results, summary=f"USAspending loans for '{args.query}'",
                 pagination=_pagination(result, data)):
        return
    
    print(f"Found {len(results)} loan awards:")
    for r in results:
        amount_val = r.get('Award Amount') or 0
        amt = f"${float(amount_val):,.2f}"
        print(f"  {r.get('Award ID')} | {amt} | {r.get('Recipient Name')}")
        print(f"    Agency: {r.get('Awarding Agency')}")
        print()

def _fmt_money(val):
    if val is None:
        return "N/A"
    try:
        v = float(val)
        if abs(v) >= 1_000_000_000:
            return f"${v/1e9:.1f}B"
        if abs(v) >= 1_000_000:
            return f"${v/1e6:.1f}M"
        if abs(v) >= 1_000:
            return f"${v/1e3:.0f}K"
        return f"${v:,.2f}"
    except (ValueError, TypeError):
        return str(val)


def _is_generated_award_identifier(award_id):
    """Return whether an identifier can be sent directly to the detail API."""
    return award_id.isdigit() or award_id.startswith(("CONT_", "ASST_"))


def _resolve_piid(piid, run):
    """Resolve one exact procurement PIID to a generated award identifier."""
    exact_matches = []
    unavailable_groups = 0
    for award_types in (CONTRACT_AWARD_TYPES, IDV_AWARD_TYPES):
        payload = {
            "filters": {
                # The download endpoint has rejected quoted exact-match IDV
                # filters upstream. Search without quotes, then enforce exact
                # PIID equality on every candidate below.
                "award_ids": [piid],
                "award_type_codes": award_types,
            },
            "fields": [
                "Award ID",
                "Recipient Name",
                "Awarding Agency",
                "Awarding Sub Agency",
                "Contract Award Type",
            ],
            "limit": ADVANCED_SEARCH_LIMIT_MAX,
            "page": 1,
        }
        response = run.fetch("/search/spending_by_award/", payload)
        if response is None:
            unavailable_groups += 1
            continue
        if _pagination(response, payload)["has_next"]:
            run.error("incomplete_resolution", "PIID resolution requires additional search pages",
                      endpoint="/search/spending_by_award/")
            unavailable_groups += 1
        for row in response.get("results", []):
            if str(row.get("Award ID") or "").strip().upper() != piid.upper():
                continue
            generated_id = (
                row.get("generated_internal_id")
                or row.get("generated_unique_award_id")
                or row.get("internal_id")
            )
            if generated_id is not None:
                exact_matches.append((str(generated_id), row))

    unique_matches = {}
    for generated_id, row in exact_matches:
        unique_matches.setdefault(generated_id, row)

    if unavailable_groups:
        print(
            f"ERROR: Could not resolve PIID {piid} because "
            f"{unavailable_groups} USAspending award search request(s) failed.",
            file=sys.stderr,
        )
        return None, list(unique_matches.values())
    if len(unique_matches) == 1:
        return next(iter(unique_matches)), list(unique_matches.values())
    if not unique_matches:
        run.error(
            "unresolved_identifier",
            f"No exact USAspending award matched PIID {piid}. "
            "Run the 'awards' command to inspect candidate identifiers.",
        )
        return None, []

    run.error(
        "ambiguous_identifier",
        f"PIID {piid} matched {len(unique_matches)} awards. "
        "Pass one generated_unique_award_id explicitly:",
    )
    for generated_id, row in unique_matches.items():
        agency = row.get("Awarding Agency") or "unknown agency"
        recipient = row.get("Recipient Name") or "unknown recipient"
        print(
            f"  {generated_id} | {agency} | {recipient}",
            file=sys.stderr,
        )
    return None, list(unique_matches.values())


def cmd_award_detail(args):
    """Get full detail for a generated award identifier or exact plain PIID."""
    run = _Query(args, "award")
    requested_id = str(args.award_id).strip()
    award_id = requested_id
    if not _is_generated_award_identifier(requested_id):
        award_id, candidates = _resolve_piid(requested_id, run)
        if award_id is None:
            run.write([], summary=f"USAspending award detail {requested_id}",
                      extra={"resolution_candidates": candidates})

    result = run.fetch(f"/awards/{award_id}/", detail=True)

    if run.write([result] if result is not None else [], extra=result,
                 summary=f"USAspending award detail {requested_id}"):
        return

    print(f"Award: {result.get('generated_unique_award_id', 'N/A')}")
    print(f"  Type: {result.get('type_description', '?')}")
    print(f"  Recipient: {result.get('recipient', {}).get('recipient_name', '?')}")
    print(f"  UEI: {result.get('recipient', {}).get('recipient_uei', 'N/A')}")
    print(f"  Total obligation: {_fmt_money(result.get('total_obligation'))}")
    print(f"  Base + exercised options: {_fmt_money(result.get('base_exercised_options'))}")
    print(f"  Base + all options: {_fmt_money(result.get('base_and_all_options_value'))}")
    print(f"  Period: {result.get('period_of_performance_start_date', '?')} to {result.get('period_of_performance_current_end_date', '?')}")
    print(f"  Agency: {result.get('awarding_agency', {}).get('toptier_agency', {}).get('name', '?')}")
    print(f"  Sub-agency: {result.get('awarding_agency', {}).get('subtier_agency', {}).get('name', '?')}")
    desc = result.get('description', '')
    if desc:
        print(f"  Description: {desc[:200]}")

    # Subawards count
    subaward_count = result.get('subaward_count', 0)
    if subaward_count:
        print(f"\n  Subawards: {subaward_count} (total {_fmt_money(result.get('total_subaward_amount'))})")

    # Parent award (for IDVs)
    parent = result.get('parent_award', {})
    if parent and parent.get('generated_unique_award_id'):
        print(f"\n  Parent Award: {parent.get('generated_unique_award_id')}")
        print(f"    Agency: {parent.get('agency_name', '?')}")


def cmd_subawards(args):
    """Search subaward/subcontractor data."""
    run = _Query(args, "subawards")
    filters = {}

    if args.uei:
        filters["recipient_search_text"] = [args.uei]
    elif args.query:
        filters["recipient_search_text"] = [args.query]

    if args.award_id:
        # The live API returns HTTP 503 for its documented quoted exact-match
        # form; send the PIID normally and enforce exactness on returned rows.
        filters["award_ids"] = [args.award_id]

    agency_filter = _agency_filter(args)
    if agency_filter:
        filters["agencies"] = [agency_filter]

    award_types = GRANT_AWARD_TYPES if args.grants else CONTRACT_AWARD_TYPES
    filters["award_type_codes"] = award_types

    data = {
        "subawards": True,
        "spending_level": "subawards",
        "filters": filters,
        "fields": [
            "Sub-Award ID", "Sub-Awardee Name", "Sub-Recipient UEI",
            "Sub-Award Amount", "Sub-Award Date", "Sub-Award Description",
            "Sub-Award Type", "Prime Award ID", "Prime Recipient Name",
            "Prime Award Recipient UEI", "Awarding Agency", "Awarding Sub Agency",
        ],
        "limit": args.limit,
        "page": args.page,
        "sort": "Sub-Award Amount",
        "order": "desc",
    }

    result = run.fetch("/search/spending_by_award/", data)
    results = (result or {}).get("results", [])
    if not _subaward_results_in_scope(results, args):
        run.error("scope_mismatch", "USAspending returned out-of-scope subawards")
        run.write([], summary="USAspending subaward scope validation failed")
    total = len(results)

    if run.write(results, summary=f"USAspending subawards ({total} returned)",
                 pagination=_pagination(result, data)):
        return

    print(f"Found {total} subawards (showing {len(results)}):")
    for r in results:
        sub_name = r.get("Sub-Awardee Name", "?")
        amount = r.get("Sub-Award Amount", 0)
        date = r.get("Sub-Award Date", "?")
        desc = r.get("Sub-Award Description", "")
        prime_award = r.get("Prime Award ID", "")

        print(f"\n  {sub_name} | {_fmt_money(amount)} | {date}")
        if prime_award:
            print(f"    Prime Award: {prime_award}")
        if desc:
            print(f"    Desc: {desc[:120]}")

    print()


def _normalized_scope_text(value):
    """Normalize punctuation/case while retaining entity-name token order."""
    return " ".join(re.findall(r"[A-Z0-9]+", str(value or "").upper()))


def _subaward_results_in_scope(results, args):
    """Fail closed if USAspending returns rows outside requested filters."""
    mismatches = []
    expected_uei = str(args.uei or "").strip().upper()
    expected_name = _normalized_scope_text(args.query)
    expected_award = str(args.award_id or "").strip().upper()
    expected_agency = _normalized_scope_text(args.agency)

    for row in results:
        reasons = []
        if expected_uei:
            actual_uei = str(row.get("Sub-Recipient UEI") or "").strip().upper()
            if actual_uei != expected_uei:
                reasons.append(f"sub-recipient UEI {actual_uei or '<missing>'}")
        elif expected_name:
            actual_name = _normalized_scope_text(row.get("Sub-Awardee Name"))
            if expected_name not in actual_name:
                reasons.append(f"sub-awardee {actual_name or '<missing>'}")

        if expected_award:
            actual_award = str(row.get("Prime Award ID") or "").strip().upper()
            if actual_award != expected_award:
                reasons.append(f"prime award {actual_award or '<missing>'}")

        if expected_agency:
            actual_agency = _normalized_scope_text(row.get("Awarding Agency"))
            if actual_agency != expected_agency:
                reasons.append(f"awarding agency {actual_agency or '<missing>'}")

        if reasons:
            mismatches.append((row.get("Sub-Award ID", "<unknown>"), reasons))

    if not mismatches:
        return True

    print(
        f"ERROR: USAspending returned {len(mismatches)} out-of-scope subaward "
        "row(s); refusing to emit potentially unfiltered results.",
        file=sys.stderr,
    )
    for subaward_id, reasons in mismatches[:3]:
        print(f"  {subaward_id}: {', '.join(reasons)}", file=sys.stderr)
    return False


def cmd_transactions(args):
    """Search individual transaction records."""
    run = _Query(args, "transactions")
    filters = {}

    if args.uei:
        filters["recipient_search_text"] = [args.uei]
    elif args.query:
        filters["recipient_search_text"] = [args.query]

    agency_filter = _agency_filter(args)
    if agency_filter:
        filters["agencies"] = [agency_filter]

    if args.date_range:
        parts = args.date_range.split(",")
        if len(parts) == 2:
            filters["time_period"] = [{"start_date": parts[0], "end_date": parts[1]}]

    award_types = GRANT_AWARD_TYPES if args.grants else CONTRACT_AWARD_TYPES
    filters["award_type_codes"] = award_types

    data = {
        "filters": filters,
        "fields": [
            "Award ID", "Recipient Name", "Action Date", "Transaction Amount",
            "Awarding Agency", "Awarding Sub Agency", "Award Type", "Transaction Description",
            "Mod", "Recipient UEI", "NAICS", "PSC"
        ],
        "limit": args.limit,
        "page": args.page,
        "sort": "Transaction Amount",
        "order": "desc"
    }

    result = run.fetch("/search/spending_by_transaction/", data) or {}

    results = result.get("results", [])
    page_metadata = result.get("page_metadata")
    if not isinstance(page_metadata, dict):
        page_metadata = {}
    reported_total = page_metadata.get("total")
    returned_recipients = sorted(
        {
            (
                str(row.get("Recipient UEI") or "").strip() or None,
                str(row.get("Recipient Name") or "").strip() or None,
            )
            for row in results
        },
        key=lambda item: ((item[1] or ""), (item[0] or "")),
    )
    requested_uei = str(args.uei or "").strip().upper()
    returned_ueis = {
        str(uei).upper()
        for uei, _name in returned_recipients
        if uei
    }
    scope_expansion_observed = (
        any(uei != requested_uei for uei in returned_ueis)
        if requested_uei and returned_ueis
        else None
    )
    output = {
        "query": {
            "recipient_name": args.query,
            "recipient_uei": args.uei,
            "agency": args.agency,
            "agency_tier": (
                getattr(args, "agency_tier", None) or "toptier"
                if args.agency
                else None
            ),
            "recipient_scope_expansion_observed": scope_expansion_observed,
            "recipient_scope_note": (
                "USAspending recipient_search_text can return affiliated "
                "recipient records. Compare returned_recipients with the "
                "requested UEI before combining queries."
            ),
        },
        "returned_recipients": [
            {"recipient_uei": uei, "recipient_name": name}
            for uei, name in returned_recipients
        ],
        "results": results,
        "messages": result.get("messages", []),
    }

    summary = (
        f"USAspending transactions (page {args.page}, "
        f"{len(results)} returned"
    )
    if reported_total is not None:
        summary += f", {reported_total} reported total"
    else:
        summary += ", overall total not reported"
    summary += ")"
    if run.write(results, summary=summary, extra=output,
                 pagination=_pagination(result, data)):
        return

    if reported_total is None:
        print(
            f"Returned {len(results)} transactions on page {args.page}; "
            "USAspending did not report an overall total."
        )
    else:
        print(f"Found {reported_total} transactions (showing {len(results)}):")
    if scope_expansion_observed:
        print(
            f"WARNING: Requested UEI {args.uei} returned other recipient "
            "UEIs; this result set includes affiliated recipient records."
        )
        for recipient in output["returned_recipients"]:
            print(
                f"  {recipient['recipient_uei'] or 'N/A'} | "
                f"{recipient['recipient_name'] or 'N/A'}"
            )
    for r in results:
        award_id = r.get("Award ID", "?")
        name = r.get("Recipient Name", "?")
        amount = r.get("Transaction Amount", 0)
        date = r.get("Action Date", "?")
        agency = r.get("Awarding Agency", "?")
        desc = r.get("Transaction Description", "")

        print(f"\n  {award_id} | {_fmt_money(amount)} | {date}")
        print(f"    Recipient: {name}")
        print(f"    Agency: {agency}")
        if desc:
            print(f"    Desc: {desc[:120]}")

    print()


def _transactions_keyword_payload(args, page):
    """Build the verified USAspending transaction-keyword request shape."""
    filters = {
        "time_period": [
            {"start_date": args.start, "end_date": args.end}
        ],
        "award_type_codes": CONTRACT_AWARD_TYPES,
        "keywords": [args.keyword],
    }

    # spending_by_transaction takes bare code strings here; the
    # {"naics_code": ..., "is_primary": ...} object form used by the award
    # endpoints is rejected with HTTP 422 (verified live 2026-07-27).
    if args.naics:
        filters["naics_codes"] = [args.naics]
    if args.psc:
        filters["psc_codes"] = [args.psc]
    agency_filter = _agency_filter(args)
    if agency_filter:
        filters["agencies"] = [agency_filter]

    return {
        "filters": filters,
        "fields": [
            "Award ID",
            "Recipient Name",
            "Transaction Amount",
            "Action Date",
            "Mod",
            "Awarding Sub Agency",
            "naics_code",
            "Transaction Description",
        ],
        "sort": "Action Date",
        "order": "asc",
        "limit": args.limit,
        "page": page,
    }


def _load_transactions_keyword_file(path):
    """Load one saved spending_by_transaction response."""
    try:
        with open(path) as fixture_file:
            response = json.load(fixture_file)
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        print(
            f"ERROR: Could not read USAspending response {path}: {exc}",
            file=sys.stderr,
        )
        return None

    if (not isinstance(response, dict)
            or not isinstance(response.get("results"), list)
            or any(not isinstance(row, dict) for row in response["results"])):
        print(
            "ERROR: Saved USAspending response must contain a results list",
            file=sys.stderr,
        )
        return None
    return response


def _fmt_transaction_amount(value):
    if value is None:
        return "N/A"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _print_keyword_transactions(results):
    if not results:
        print("No USAspending keyword transactions found.")
        return

    for row in results:
        action_date = row.get("Action Date", "?")
        award_id = row.get("Award ID", "?")
        recipient = row.get("Recipient Name", "?")
        amount = _fmt_transaction_amount(row.get("Transaction Amount"))
        modification = row.get("Mod") or "0"
        description = row.get("Transaction Description") or ""
        if len(description) > 120:
            description = f"{description[:117]}..."
        print(
            f"{action_date} | {award_id} | {recipient} | "
            f"{amount} | Mod {modification} | {description}"
        )


def cmd_transactions_keyword(args):
    """Search transaction descriptions by keyword, including modifications."""
    run = _Query(args, "transactions-keyword")
    results = []
    start_page = getattr(args, "page", 1)
    pagination = _pagination(None, {"page": start_page, "limit": args.limit})
    pagination.update({"pages_retrieved": 0, "stopped_reason": None})
    partial = False
    source = {}
    if args.from_file:
        response = _load_transactions_keyword_file(args.from_file)
        if response is None:
            run.error("invalid_file", "Could not load saved USAspending response",
                      path=args.from_file)
        else:
            results = response["results"]
            run.requests.append({"method": "FILE", "path": args.from_file,
                                 "status": "success", "returned_count": len(results)})
            saved_pagination = response.get("pagination")
            if isinstance(saved_pagination, dict):
                pagination.update(saved_pagination)
            else:
                pagination.update(_pagination(response, {"page": start_page, "limit": args.limit}))
                pagination["pages_retrieved"] = 1
            pagination["stopped_reason"] = "from_file"
            source = {"source_query": response.get("query"),
                      "source_retrieval": response.get("retrieval")}
            partial = response.get("status") == "partial"
            if response.get("errors") or response.get("status") == "error":
                run.error("saved_acquisition_error", "Saved response contains acquisition errors")
    else:
        page_cap = 50 if args.all_pages else 1
        for page in range(start_page, start_page + page_cap):
            payload = _transactions_keyword_payload(args, page)
            response = run.fetch(
                "/search/spending_by_transaction/", payload
            )
            if response is None:
                pagination.update({"next_page": page, "has_next": True,
                                   "stopped_reason": "acquisition_error"})
                break
            results.extend(response["results"])
            pages_retrieved = pagination["pages_retrieved"] + 1
            pagination.update(_pagination(response, payload))
            pagination.update({"requested_page": start_page,
                               "pages_retrieved": pages_retrieved})
            has_next = pagination["has_next"]
            if not args.all_pages or not has_next:
                pagination["stopped_reason"] = (
                    "requested_page" if has_next else
                    "exhausted" if has_next is False else "pagination_unreported"
                )
                break
            if pages_retrieved == page_cap:
                partial = True
                pagination["stopped_reason"] = "page_cap"
                print(
                    "WARNING: Stopped after the 50-page safety cap "
                    "while USAspending still reported another page.",
                    file=sys.stderr,
                )

    pagination["returned_count"] = len(results)
    if run.write(
        results,
        pagination=pagination,
        partial=partial,
        extra=source,
        summary=(
            f"USAspending transactions matching '{args.keyword}' "
            f"({len(results)} returned)"
        ),
    ):
        return

    print(f"Found {len(results)} transactions matching '{args.keyword}':")
    _print_keyword_transactions(results)


def cmd_spending_by_geography(args):
    """Analyze spending patterns by geographic area."""
    run = _Query(args, "geography")
    filters = {}

    if args.query:
        filters["recipient_search_text"] = [args.query]
    if args.agency:
        filters["agencies"] = [{"type": "awarding", "tier": "toptier", "name": args.agency}]
    if args.date_range:
        parts = args.date_range.split(",")
        if len(parts) == 2:
            filters["time_period"] = [{"start_date": parts[0], "end_date": parts[1]}]

    award_types = GRANT_AWARD_TYPES if args.grants else CONTRACT_AWARD_TYPES
    filters["award_type_codes"] = award_types

    data = {
        "scope": args.scope,  # place_of_performance or recipient_location
        "geo_layer": args.geo_layer,  # state, county, or district
        "filters": filters,
    }

    result = run.fetch("/search/spending_by_geography/", data)
    results = (result or {}).get("results", [])

    if run.write(results, summary=f"USAspending geographic spending ({len(results)} regions)"):
        return

    # Sort by amount descending
    results.sort(key=lambda x: x.get("aggregated_amount", 0), reverse=True)

    print(f"Spending by {args.geo_layer} ({args.scope}):")
    for r in results[:args.limit]:
        name = r.get("display_name", r.get("shape_code", "?"))
        amount = r.get("aggregated_amount", 0)
        if amount > 0:
            print(f"  {name}: {_fmt_money(amount)}")

    print()


def cmd_spending_over_time(args):
    """Analyze spending trends over time."""
    run = _Query(args, "timeline")
    filters = {}

    if args.query:
        filters["recipient_search_text"] = [args.query]
    if args.agency:
        filters["agencies"] = [{"type": "awarding", "tier": "toptier", "name": args.agency}]

    award_types = GRANT_AWARD_TYPES if args.grants else CONTRACT_AWARD_TYPES
    filters["award_type_codes"] = award_types

    data = {
        "group": args.group,  # fiscal_year, quarter, month
        "filters": filters,
    }

    result = run.fetch("/search/spending_over_time/", data)
    results = (result or {}).get("results", [])

    if run.write(results, summary=f"USAspending spending over time ({len(results)} periods)"):
        return

    print(f"Spending by {args.group}:")
    for r in results:
        fy = r.get("time_period", {})
        period = fy.get("fiscal_year", "")
        if "quarter" in fy:
            period += f" Q{fy['quarter']}"
        if "month" in fy:
            period += f" M{fy['month']}"
        amount = r.get("aggregated_amount", 0)
        if amount != 0:
            print(f"  {period}: {_fmt_money(amount)}")

    print()


def cmd_top_recipients(args):
    """Find top recipients by spending amount."""
    run = _Query(args, "top-recipients")
    filters = {}

    if args.agency:
        filters["agencies"] = [{"type": "awarding", "tier": "toptier", "name": args.agency}]
    if args.naics:
        filters["naics_codes"] = {
            "require": [args.naics],
            "exclude": [],
        }
    if args.date_range:
        parts = args.date_range.split(",")
        if len(parts) == 2:
            filters["time_period"] = [{"start_date": parts[0], "end_date": parts[1]}]

    award_types = GRANT_AWARD_TYPES if args.grants else CONTRACT_AWARD_TYPES
    filters["award_type_codes"] = award_types

    data = {
        "category": "recipient",
        "filters": filters,
        "limit": args.limit,
        "page": 1,
    }

    result = run.fetch("/search/spending_by_category/recipient/", data)
    results = (result or {}).get("results", [])

    if run.write(results, summary=f"Top {len(results)} recipients",
                 pagination=_pagination(result, data)):
        return

    print("Top recipients:")
    for i, r in enumerate(results, 1):
        name = r.get("name", "?")
        amount = r.get("amount", 0)
        print(f"  {i}. {name}: {_fmt_money(amount)}")

    print()


def cmd_agencies(args):
    """List top-tier federal agencies."""
    run = _Query(args, "agencies")
    result = run.fetch("/references/toptier_agencies/", allow_list=True)
    results = (result or {}).get("results", [])

    if run.write(results, summary="USAspending toptier agencies"):
        return

    if isinstance(results, list):
        # Sort by budget
        results.sort(key=lambda x: x.get("budget_authority_amount", 0) or 0, reverse=True)
        print("Top agencies by budget authority:")
        for a in results[:args.limit]:
            name = a.get("agency_name", "?")
            abbr = a.get("abbreviation", "")
            budget = a.get("budget_authority_amount", 0)
            print(f"  {name} ({abbr}): {_fmt_money(budget)}")


def main():
    parser = argparse.ArgumentParser(
        description="USAspending.gov — federal spending, contracts, grants, and recipient analysis",
        epilog="No auth required. Rate limit: ~10 req/sec."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Search
    p = sub.add_parser("search", help="Search for recipients (autocomplete)")
    p.add_argument("query", help="Recipient name fragment")
    add_output_args(p)

    # Awards
    p = sub.add_parser("awards", help="Search spending by award")
    p.add_argument("query", nargs="?", help="Recipient name")
    p.add_argument("--uei", help="Recipient UEI")
    p.add_argument("--limit", type=int, default=20, help="Max results")
    p.add_argument("--page", type=int, default=1, help="Page number")
    p.add_argument("--agency", help="Filter by awarding agency name")
    p.add_argument("--grants", action="store_true", help="Search grants instead of contracts")
    add_output_args(p)

    # Award detail
    p = sub.add_parser("award", help="Get full detail for a specific award")
    p.add_argument(
        "award_id",
        help=(
            "Plain PIID (resolved first), generated_unique_award_id, "
            "or legacy internal ID"
        ),
    )
    add_output_args(p)

    # Recipient Profile
    p = sub.add_parser("recipient", help="Get recipient summary")
    p.add_argument("query", help="Recipient name")
    add_output_args(p)

    # Subawards
    p = sub.add_parser("subawards", help="Search subaward/subcontractor data")
    p.add_argument("query", nargs="?", help="Recipient name")
    p.add_argument("--uei", help="Recipient UEI")
    p.add_argument("--award-id", help="Filter by prime award ID")
    p.add_argument(
        "--agency",
        help=(
            "Filter by awarding agency name; use --agency-tier subtier "
            "for a component name"
        ),
    )
    p.add_argument(
        "--agency-tier",
        choices=["toptier", "subtier"],
        default="toptier",
        help="Hierarchy tier for --agency (default: toptier)",
    )
    p.add_argument("--grants", action="store_true", help="Search grant subawards")
    p.add_argument(
        "--limit",
        type=_advanced_search_limit,
        default=20,
        help="Results per page (1-100; default: 20)",
    )
    p.add_argument("--page", type=int, default=1, help="Page number")
    add_output_args(p)

    # Transactions
    p = sub.add_parser("transactions", help="Search individual transaction records")
    p.add_argument("query", nargs="?", help="Recipient name")
    p.add_argument("--uei", help="Recipient UEI")
    p.add_argument(
        "--agency",
        help=(
            "Filter by awarding agency name; use --agency-tier subtier "
            "for a component name"
        ),
    )
    p.add_argument(
        "--agency-tier",
        choices=["toptier", "subtier"],
        default="toptier",
        help="Hierarchy tier for --agency (default: toptier)",
    )
    p.add_argument("--date-range", help="Date range: YYYY-MM-DD,YYYY-MM-DD")
    p.add_argument("--grants", action="store_true", help="Search grant transactions")
    p.add_argument(
        "--limit",
        type=_advanced_search_limit,
        default=20,
        help="Results per page (1-100; default: 20)",
    )
    p.add_argument("--page", type=int, default=1, help="Page number")
    add_output_args(p)

    # Transactions by keyword
    p = sub.add_parser(
        "transactions-keyword",
        help="Search transaction descriptions by keyword",
    )
    p.add_argument("keyword", help="Keyword or phrase")
    p.add_argument(
        "--start",
        default="2015-10-01",
        help="Start date (default: 2015-10-01)",
    )
    p.add_argument(
        "--end",
        default=date.today().isoformat(),
        help="End date (default: today)",
    )
    p.add_argument("--naics", help="Filter by primary NAICS code")
    p.add_argument("--psc", help="Filter by product/service code")
    p.add_argument("--agency", help="Filter by awarding agency name")
    p.add_argument(
        "--agency-tier",
        choices=["toptier", "subtier"],
        default="toptier",
        help=(
            "Tier for --agency: toptier takes a department name such as "
            "Department of Homeland Security, subtier a component such as "
            "U.S. Immigration and Customs Enforcement (default: toptier)"
        ),
    )
    p.add_argument(
        "--limit",
        type=_advanced_search_limit,
        default=100,
        help="Results per page (1-100; default: 100)",
    )
    p.add_argument(
        "--all-pages",
        action="store_true",
        help="Fetch every page, capped at 50",
    )
    p.add_argument("--page", type=_positive_page, default=1,
                   help="Starting page (use pagination.next_page to resume)")
    p.add_argument(
        "--from-file",
        metavar="PATH",
        help="Render a saved API response instead of fetching",
    )
    add_output_args(p)

    # Spending by geography
    p = sub.add_parser("geography", help="Spending patterns by geographic area")
    p.add_argument("query", nargs="?", help="Recipient name filter")
    p.add_argument("--scope", choices=["place_of_performance", "recipient_location"],
                   default="recipient_location", help="Geography dimension")
    p.add_argument("--geo-layer", choices=["state", "county", "district"],
                   default="state", help="Geographic granularity")
    p.add_argument("--agency", help="Filter by awarding agency name")
    p.add_argument("--date-range", help="Date range: YYYY-MM-DD,YYYY-MM-DD")
    p.add_argument("--grants", action="store_true", help="Grants instead of contracts")
    p.add_argument("--limit", type=int, default=20, help="Max results to show")
    add_output_args(p)

    # Spending over time
    p = sub.add_parser("timeline", help="Spending trends over time")
    p.add_argument("query", nargs="?", help="Recipient name filter")
    p.add_argument("--group", choices=["fiscal_year", "quarter", "month"],
                   default="fiscal_year", help="Time granularity")
    p.add_argument("--agency", help="Filter by awarding agency name")
    p.add_argument("--grants", action="store_true", help="Grants instead of contracts")
    add_output_args(p)

    # Top recipients
    p = sub.add_parser("top-recipients", help="Top recipients by spending")
    p.add_argument("--agency", help="Filter by awarding agency name")
    p.add_argument("--naics", help="Filter by NAICS code")
    p.add_argument("--date-range", help="Date range: YYYY-MM-DD,YYYY-MM-DD")
    p.add_argument("--grants", action="store_true", help="Grants instead of contracts")
    p.add_argument("--limit", type=int, default=20, help="Max results")
    add_output_args(p)

    # Agencies
    p = sub.add_parser("agencies", help="List top-tier federal agencies")
    p.add_argument("--limit", type=int, default=30, help="Max results")
    add_output_args(p)

    # COVID
    p = sub.add_parser("covid", help="Search for COVID-19 relief awards")
    p.add_argument("query", help="Recipient name")
    p.add_argument("--limit", type=int, default=20, help="Max results")
    add_output_args(p)

    # Loans
    p = sub.add_parser("loans", help="Search specifically for loan awards")
    p.add_argument("query", help="Recipient name")
    p.add_argument("--limit", type=int, default=20, help="Max results")
    add_output_args(p)

    args = parser.parse_args()

    handlers = {
        "search": cmd_search,
        "awards": cmd_awards,
        "award": cmd_award_detail,
        "recipient": cmd_recipient,
        "subawards": cmd_subawards,
        "transactions": cmd_transactions,
        "transactions-keyword": cmd_transactions_keyword,
        "geography": cmd_spending_by_geography,
        "timeline": cmd_spending_over_time,
        "top-recipients": cmd_top_recipients,
        "agencies": cmd_agencies,
        "covid": cmd_covid,
        "loans": cmd_loans,
    }

    handlers[args.command](args)

if __name__ == "__main__":
    main()
