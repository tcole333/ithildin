#!/usr/bin/env python3
"""
SAM.gov API wrapper for government entity registration, exclusions, and contract awards.

Covers the four main SAM.gov APIs:
- Entity Management: Who is registered to do business with the federal government
- Exclusions: Debarments, suspensions, and exclusions from federal contracting
- Contract Awards: Federal procurement records (replaces FPDS, decommissioned Feb 2026)
- Opportunities: Active and historical contract solicitations

Auth: Requires SAM_API_KEY (free registration at sam.gov → Account Details → API Key).
      Basic non-federal tier: 10 requests/day. Request SAM role for 1,000/day.

Usage:
    uv run python tools/query_sam.py entity "Palantir"
    uv run python tools/query_sam.py entity "Palantir" --status A --sections all
    uv run python tools/query_sam.py exclusions "QUERY" --classification Firm
    uv run python tools/query_sam.py contracts "RECIPIENT" --limit 25
    uv run python tools/query_sam.py opportunities "surveillance" --posted-from 01/01/2025
"""

import argparse
import os
import sys
import time
from datetime import datetime

import requests

try:
    from tools.env_loader import load_env_file
    from tools.output_util import add_output_args, write_output
except ImportError:
    from env_loader import load_env_file
    from output_util import add_output_args, write_output

load_env_file()
SAM_API_KEY = os.environ.get("SAM_API_KEY", "")

ENTITY_BASE = "https://api.sam.gov/entity-information/v4"
EXCLUSIONS_BASE = "https://api.sam.gov/entity-information/v4"
CONTRACTS_BASE = "https://api.sam.gov/contract-awards/v1"
OPPORTUNITIES_BASE = "https://api.sam.gov/opportunities/v2"

RATE_LIMIT_DELAY = 1.5  # Conservative: 10 req/day on basic tier

EXCLUSION_TYPES = (
    "Ineligible (Proceedings Pending)",
    "Ineligible (Proceedings Completed)",
    "Prohibition/Restriction",
    "Voluntary Exclusion",
)


def _check_api_key():
    if not SAM_API_KEY:
        print("ERROR: SAM_API_KEY not set. Get a free key at sam.gov → Account Details → API Key.", file=sys.stderr)
        print("Set it: export SAM_API_KEY=your_key_here", file=sys.stderr)
        sys.exit(1)


def _fetch(url, params=None):
    """Fetch from SAM.gov API with rate limiting."""
    request_params = dict(params or {})
    request_params["api_key"] = SAM_API_KEY
    headers = {
        "User-Agent": "OSINT-Research/1.0",
    }

    try:
        time.sleep(RATE_LIMIT_DELAY)
        response = requests.get(
            url,
            params=request_params,
            headers=headers,
            timeout=(10, 60),
        )
        response.raise_for_status()
        if response.status_code == 204:
            return {"totalRecords": 0}
        return response.json()
    except requests.HTTPError as e:
        response = e.response
        status_code = response.status_code if response is not None else None
        body = response.text[:500] if response is not None else str(e)
        if SAM_API_KEY:
            body = body.replace(SAM_API_KEY, "[REDACTED]")
        if status_code == 429:
            print("ERROR: SAM.gov rate limit exceeded (HTTP 429).", file=sys.stderr)
            print(
                "Non-federal personal keys without a SAM role default to 10 requests/day; "
                "a SAM role raises the default to 1,000/day.",
                file=sys.stderr,
            )
        else:
            print(f"ERROR: HTTP {status_code}: {body}", file=sys.stderr)
        return None
    except requests.Timeout as e:
        message = str(e)
        if SAM_API_KEY:
            message = message.replace(SAM_API_KEY, "[REDACTED]")
        print(f"ERROR: SAM.gov request timed out: {message}", file=sys.stderr)
        return None
    except requests.RequestException as e:
        message = str(e)
        if SAM_API_KEY:
            message = message.replace(SAM_API_KEY, "[REDACTED]")
        print(f"ERROR: {message}", file=sys.stderr)
        return None
    except ValueError as e:
        print(f"ERROR: Invalid JSON response: {e}", file=sys.stderr)
        return None


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


def _contract_date(value):
    """Validate an ISO CLI date and convert it to SAM's MM/DD/YYYY format."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%Y")
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"invalid ISO date '{value}'; expected YYYY-MM-DD"
        ) from e


def _extract_records(result, keys, label):
    """Return the first recognized list, failing closed on an unexpected schema."""
    if not isinstance(result, dict):
        print(
            f"ERROR: SAM.gov {label} response was not a JSON object.",
            file=sys.stderr,
        )
        return None

    for key in keys:
        if key not in result:
            continue
        records = result[key]
        if isinstance(records, list):
            return records
        print(
            f"ERROR: SAM.gov {label} response field '{key}' was not a list.",
            file=sys.stderr,
        )
        return None

    if "totalRecords" not in result:
        expected = " or ".join(repr(key) for key in keys)
        print(
            f"ERROR: SAM.gov {label} response contained neither {expected} nor "
            "'totalRecords'.",
            file=sys.stderr,
        )
        return None

    total = result["totalRecords"]
    try:
        has_records = int(total) > 0
    except (TypeError, ValueError):
        has_records = bool(total)

    if has_records:
        expected = " or ".join(repr(key) for key in keys)
        print(
            f"ERROR: SAM.gov {label} response reported {total} records but contained "
            f"neither {expected}.",
            file=sys.stderr,
        )
        return None
    return []


# ── Entity Management ───────────────────────────────────────

def cmd_entity(args):
    """Search SAM.gov entity registrations."""
    _check_api_key()

    params = {}

    if args.uei:
        params["ueiSAM"] = args.uei
    elif args.cage:
        params["cageCode"] = args.cage
    else:
        params["legalBusinessName"] = args.query

    if args.status:
        params["registrationStatus"] = args.status  # A=Active, E=Expired
    if args.state:
        params["physicalAddressStateCode"] = args.state
    if args.naics:
        params["primaryNaics"] = args.naics

    # Sections to include
    if args.sections == "all":
        params["includeSections"] = "entityRegistration,coreData,assertions,pointsOfContact,integrityInformation"
    elif args.sections:
        params["includeSections"] = args.sections
    else:
        params["includeSections"] = "entityRegistration,coreData"

    result = _fetch(f"{ENTITY_BASE}/entities", params)
    if result is None:
        return 1

    entities = _extract_records(result, ("entityData",), "entity")
    if entities is None:
        return 1
    total = result.get("totalRecords", len(entities))

    if write_output(entities, args, summary=f"SAM.gov entities matching '{args.query or args.uei or args.cage}' ({total} total)"):
        return

    print(f"Found {total} registered entities:")
    for e in entities:
        reg = e.get("entityRegistration", {})
        core = e.get("coreData", {})
        entity_info = core.get("entityInformation", {})
        addr = core.get("physicalAddress", {})

        uei = reg.get("ueiSAM", "N/A")
        name = reg.get("legalBusinessName", "Unknown")
        status = reg.get("registrationStatus", "?")
        cage = reg.get("cageCode", "")
        exp_date = reg.get("registrationExpirationDate", "")

        city = addr.get("city", "")
        state = addr.get("stateOrProvinceCode", "")
        country = addr.get("countryCode", "")
        zip_code = addr.get("zipCode", "")

        print(f"\n  {name}")
        print(f"    UEI: {uei} | CAGE: {cage} | Status: {status}")
        print(f"    Location: {city}, {state} {zip_code} {country}")
        if exp_date:
            print(f"    Registration expires: {exp_date}")

        # Entity type
        entity_type = entity_info.get("entityStructureDesc", "")
        bus_types = entity_info.get("businessTypes", {}).get("businessTypeList", [])
        if entity_type:
            print(f"    Structure: {entity_type}")
        if bus_types:
            type_names = [bt.get("businessTypeDesc", "") for bt in bus_types[:5]]
            print(f"    Business types: {', '.join(t for t in type_names if t)}")

        # Points of contact
        pocs = e.get("pointsOfContact", {})
        if pocs:
            gov_poc = pocs.get("governmentBusinessPOC", {})
            if gov_poc and gov_poc.get("firstName"):
                poc_name = f"{gov_poc.get('firstName', '')} {gov_poc.get('lastName', '')}"
                poc_title = gov_poc.get("title", "")
                print(f"    POC: {poc_name.strip()}" + (f" ({poc_title})" if poc_title else ""))

        # Integrity / proceedings
        integrity = e.get("integrityInformation", {})
        if integrity:
            proceedings = integrity.get("proceedingsList", [])
            if proceedings:
                print(f"    Proceedings: {len(proceedings)} on record")

    print()


# ── Exclusions ──────────────────────────────────────────────

def cmd_exclusions(args):
    """Search SAM.gov exclusions (debarments, suspensions)."""
    _check_api_key()

    params = {}

    if args.query:
        params["q"] = args.query

    if args.classification:
        params["classification"] = args.classification  # Individual, Firm, Vessel, Special Entity Designation
    if args.type:
        params["exclusionType"] = args.type
    if args.agency:
        params["excludingAgencyName"] = args.agency
    if args.state:
        params["stateProvince"] = args.state
    if args.uei:
        params["ueiSAM"] = args.uei
    if args.npi:
        params["npi"] = args.npi

    result = _fetch(f"{EXCLUSIONS_BASE}/exclusions", params)
    if result is None:
        return 1

    exclusions = _extract_records(result, ("excludedEntity", "results"), "exclusions")
    if exclusions is None:
        return 1
    total = result.get("totalRecords", len(exclusions))

    search_term = args.query or args.uei or args.npi or args.agency or args.state or "all"
    if write_output(exclusions, args, summary=f"SAM.gov exclusions matching '{search_term}' ({total} total)"):
        return

    print(f"Found {total} exclusion records:")
    for ex in exclusions:
        details = ex.get("exclusionDetails", {})
        identification = ex.get("exclusionIdentification", {})
        actions = ex.get("exclusionActions", {}).get("listOfActions", [])
        action = actions[0] if actions else {}

        name = identification.get("entityName") or identification.get("exclusionName") or ex.get("name", "Unknown")
        classification = details.get("classificationType") or ex.get("classification", {}).get("classificationDesc", "?")
        exclusion_type = details.get("exclusionType") or ex.get("exclusionType", {}).get("exclusionTypeDesc", "?")
        agency = details.get("excludingAgencyName") or ex.get("excludingAgency", {}).get("excludingAgencyName", "?")

        activation = action.get("activateDate") or ex.get("activationDate", "?")
        termination = action.get("terminationDate") or ex.get("terminationDate") or "Active"

        addr = ex.get("exclusionPrimaryAddress") or ex.get("address", {})
        city = addr.get("city", "")
        state = addr.get("stateOrProvinceCode") or addr.get("stateOrProvince", "")
        country = addr.get("countryCode") or addr.get("country", "")

        print(f"\n  {name} ({classification})")
        print(f"    Type: {exclusion_type}")
        print(f"    Agency: {agency}")
        print(f"    Dates: {activation} to {termination}")
        if city or state:
            print(f"    Location: {city}, {state} {country}")

        uei = identification.get("ueiSAM") or ex.get("ueiSAM", "")
        if uei:
            print(f"    UEI: {uei}")

        desc = ex.get("exclusionOtherInformation", {}).get("additionalComments") or ex.get("description", "")
        if desc:
            print(f"    Description: {desc[:150]}")

    print()


# ── Contract Awards (replaces FPDS) ────────────────────────

def cmd_contracts(args):
    """Search SAM.gov contract awards (federal procurement records)."""
    _check_api_key()

    params = {}

    if args.uei:
        params["awardeeUniqueEntityId"] = args.uei
    elif args.query:
        params["awardeeLegalBusinessName"] = args.query

    if args.piid:
        params["piid"] = args.piid
    if args.naics:
        params["naicsCode"] = args.naics
    if args.psc:
        params["productOrServiceCode"] = args.psc
    if args.agency:
        params["contractingDepartmentName"] = args.agency
    if args.date_signed_from:
        params["dateSigned"] = f"[{args.date_signed_from},{args.date_signed_to or ''}]"
    if args.min_amount is not None:
        params["dollarsObligated"] = f"[{args.min_amount},]"

    if args.sections == "all":
        params["includeSections"] = "contractId,coreData,awardDetails,awardeeData"
    elif args.sections:
        params["includeSections"] = args.sections

    params["limit"] = args.limit

    result = _fetch(f"{CONTRACTS_BASE}/search", params)
    if result is None:
        return 1

    awards = _extract_records(result, ("awardSummary", "data"), "contract awards")
    if awards is None:
        return 1
    total = result.get("totalRecords", len(awards))

    if write_output(awards, args, summary=f"SAM.gov contracts for '{args.query or args.uei}' ({total} total)"):
        return

    print(f"Found {total} contract awards (showing {len(awards)}):")
    for a in awards:
        contract_id = a.get("contractId", {})
        core = a.get("coreData", {})
        details = a.get("awardDetails", {})
        awardee = details.get("awardeeData") or a.get("awardeeData", {})

        piid = contract_id.get("piid", "?")
        contracting = core.get("federalOrganization", {}).get("contractingInformation", {})
        agency = (
            contracting.get("contractingDepartment", {}).get("name")
            or contract_id.get("contractingDepartmentName")
            or contract_id.get("subtier", {}).get("name")
            or "?"
        )
        sub_agency = (
            contracting.get("contractingOffice", {}).get("name")
            or contract_id.get("contractingOfficeName", "")
        )

        awardee_header = awardee.get("awardeeHeader", {})
        awardee_uei_info = awardee.get("awardeeUEIInformation", {})
        awardee_name = (
            awardee_header.get("legalBusinessName")
            or awardee_header.get("awardeeName")
            or awardee.get("awardeeLegalBusinessName")
            or "?"
        )
        awardee_uei = awardee_uei_info.get("uniqueEntityId") or awardee.get("awardeeUniqueEntityId", "")

        award_dates = details.get("dates", {})
        award_dollars = details.get("dollars", {})
        core_product = core.get("productOrServiceInformation", {})
        detail_product = details.get("productOrServiceInformation", {})
        principal_naics = core_product.get("principalNaics", [])
        product_or_service = core_product.get("productOrService", {})

        dollars = award_dollars.get("actionObligation", core.get("dollarsObligated", 0))
        date_signed = award_dates.get("dateSigned") or core.get("dateSigned", "?")
        naics = (
            (principal_naics[0].get("code", "") if principal_naics else "")
            or detail_product.get("idvNAICS", {}).get("code", "")
            or core.get("naicsCode", "")
        )
        psc = product_or_service.get("code") or core.get("productOrServiceCode", "")
        desc = detail_product.get("descriptionOfContractRequirement") or core.get("descriptionOfContractRequirement", "")

        print(f"\n  PIID: {piid} | {_fmt_money(dollars)} | {date_signed}")
        print(f"    Awardee: {awardee_name}" + (f" (UEI: {awardee_uei})" if awardee_uei else ""))
        print(f"    Agency: {agency}" + (f" / {sub_agency}" if sub_agency else ""))
        if naics:
            print(f"    NAICS: {naics} | PSC: {psc}")
        if desc:
            print(f"    Desc: {desc[:120]}")

    print()


# ── Opportunities ───────────────────────────────────────────

def cmd_opportunities(args):
    """Search SAM.gov contract opportunities (solicitations)."""
    _check_api_key()

    params = {
        "postedFrom": args.posted_from,
        "postedTo": args.posted_to,
        "limit": args.limit,
    }

    if args.query:
        params["title"] = args.query
    if args.naics:
        params["ncode"] = args.naics
    if args.state:
        params["state"] = args.state
    if args.sol_num:
        params["solnum"] = args.sol_num
    if args.set_aside:
        params["typeOfSetAside"] = args.set_aside

    result = _fetch(f"{OPPORTUNITIES_BASE}/search", params)
    if result is None:
        return 1

    opps = _extract_records(result, ("opportunitiesData",), "opportunity")
    if opps is None:
        return 1
    total = result.get("totalRecords", len(opps))

    if write_output(opps, args, summary=f"SAM.gov opportunities matching '{args.query}' ({total} total)"):
        return

    print(f"Found {total} opportunities (showing {len(opps)}):")
    for o in opps:
        title = o.get("title", "Untitled")
        sol_num = o.get("solicitationNumber", "")
        notice_type = o.get("type", "?")
        posted = o.get("postedDate", "?")
        deadline = o.get("responseDeadLine", "")
        org = o.get("fullParentPathName", "") or o.get("organizationType", "")
        set_aside = o.get("typeOfSetAside", "")
        naics = o.get("naicsCode", "")
        ui_link = o.get("uiLink", "")

        print(f"\n  {title}")
        print(f"    Sol#: {sol_num} | Type: {notice_type} | Posted: {posted}")
        if deadline:
            print(f"    Deadline: {deadline}")
        if org:
            print(f"    Agency: {org}")
        if naics:
            print(f"    NAICS: {naics}" + (f" | Set-aside: {set_aside}" if set_aside else ""))
        if ui_link:
            print(f"    Link: {ui_link}")

    print()


# ── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="SAM.gov API — entity registrations, exclusions, contracts, opportunities",
        epilog="Requires SAM_API_KEY env var (free at sam.gov). Basic tier: 10 req/day."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Entity
    p = sub.add_parser("entity", help="Search entity registrations")
    p.add_argument("query", nargs="?", help="Legal business name search")
    p.add_argument("--uei", help="Search by UEI (Unique Entity ID)")
    p.add_argument("--cage", help="Search by CAGE code")
    p.add_argument("--status", choices=["A", "E"], help="A=Active, E=Expired")
    p.add_argument("--state", help="Physical address state code (e.g., NY, CA)")
    p.add_argument("--naics", help="Primary NAICS code")
    p.add_argument("--sections", help="Sections to include (or 'all')")
    add_output_args(p)

    # Exclusions
    p = sub.add_parser("exclusions", help="Search debarments, suspensions, exclusions")
    p.add_argument("query", nargs="?", help="Free text search (AND/OR/NOT/wildcard)")
    p.add_argument("--classification", choices=["Individual", "Firm", "Vessel", "Special Entity Designation"])
    p.add_argument("--type", choices=EXCLUSION_TYPES,
                   help="Exclusion type")
    p.add_argument("--agency", help="Excluding agency name")
    p.add_argument("--state", help="State/province code")
    p.add_argument("--uei", help="Search by UEI")
    p.add_argument("--npi", help="Search by NPI")
    add_output_args(p)

    # Contracts
    p = sub.add_parser("contracts", help="Search federal contract awards (replaces FPDS)")
    p.add_argument("query", nargs="?", help="Awardee legal business name")
    p.add_argument("--uei", help="Awardee UEI")
    p.add_argument("--piid", help="Procurement Instrument ID")
    p.add_argument("--naics", help="NAICS code")
    p.add_argument("--psc", help="Product/Service code")
    p.add_argument("--agency", help="Contracting department name")
    p.add_argument("--date-signed-from", type=_contract_date,
                   help="Date signed from (YYYY-MM-DD; converted for SAM.gov)")
    p.add_argument("--date-signed-to", type=_contract_date,
                   help="Date signed to (YYYY-MM-DD; converted for SAM.gov)")
    p.add_argument("--min-amount", type=float, help="Minimum dollars obligated")
    p.add_argument("--limit", type=int, default=25, help="Max results (default 25)")
    p.add_argument("--sections", help="Sections to include (or 'all')")
    add_output_args(p)

    # Opportunities
    p = sub.add_parser("opportunities", help="Search contract solicitations")
    p.add_argument("query", nargs="?", help="Title search")
    p.add_argument("--posted-from", required=True, help="Posted from date (MM/DD/YYYY, required)")
    p.add_argument("--posted-to", help="Posted to date (MM/DD/YYYY, defaults to today)")
    p.add_argument("--naics", help="NAICS code filter")
    p.add_argument("--state", help="State code filter")
    p.add_argument("--sol-num", help="Solicitation number")
    p.add_argument("--set-aside", help="Set-aside type filter")
    p.add_argument("--limit", type=int, default=25, help="Max results")
    add_output_args(p)

    args = parser.parse_args()

    # Default posted-to to today if not provided
    if args.command == "opportunities" and not args.posted_to:
        args.posted_to = datetime.now().strftime("%m/%d/%Y")

    handlers = {
        "entity": cmd_entity,
        "exclusions": cmd_exclusions,
        "contracts": cmd_contracts,
        "opportunities": cmd_opportunities,
    }

    status = handlers[args.command](args)
    if status:
        raise SystemExit(status)
    return 0


if __name__ == "__main__":
    main()
