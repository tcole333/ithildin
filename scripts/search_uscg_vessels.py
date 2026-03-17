#!/usr/bin/env python3
"""
USCG Vessel Documentation Search Tool

Queries the US Coast Guard CGMIX (Maritime Information Exchange) system
for vessel documentation records via SOAP XML web services.

Data source:
  CGMIX PSIX SOAP API (https://cgmix.uscg.mil/xml/psixdata.asmx)
  - Weekly FOIA snapshots from the MISLE database
  - Searchable by vessel name, call sign, VIN, HIN, flag, service type, build year
  - Returns: VesselID, name, HIN, status, service type, flag, build year
  - NO owner PII since 2018 (removed from public access)

  Uses the XMLString variant of each SOAP method, which returns embedded XML
  inside the SOAP response (the DataSet variant returns empty diffgrams).

IMPORTANT LIMITATIONS:
  - Owner names and addresses are NOT available in any public USCG database
    (PII was removed from public access in 2018)
  - To get ownership information, you must request an Abstract of Title from
    the USCG NVDC ($25 per vessel), or check state-level boat registrations
  - The PSIX database covers USCG-documented vessels (generally 5+ net tons)
  - Small recreational boats registered only at the state level won't appear
  - Name searches appear to be partial/contains matches (e.g., "LIBERTY"
    also returns "SWEET LIBERTY", "LIBERTY ISLAND", etc.)

Usage:
    uv run python scripts/search_uscg_vessels.py search "VESSEL NAME"
    uv run python scripts/search_uscg_vessels.py search "DOMINO" --flag "UNITED STATES"
    uv run python scripts/search_uscg_vessels.py search --service Recreational --build-year 2010
    uv run python scripts/search_uscg_vessels.py details <VesselID>
    uv run python scripts/search_uscg_vessels.py docs <VesselID>
    uv run python scripts/search_uscg_vessels.py cases <VesselID>
"""

import argparse
import html
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

CGMIX_SOAP_URL = "https://cgmix.uscg.mil/xml/psixdata.asmx"
CGMIX_NAMESPACE = "https://cgmix.uscg.mil"

SOAP_ENVELOPE = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <soap:Body>
    {body}
  </soap:Body>
</soap:Envelope>"""

HEADERS_SOAP = {
    "Content-Type": "text/xml; charset=utf-8",
    "User-Agent": "OSINT-Research/1.0",
}


def soap_request_xml_string(action: str, body_xml: str) -> list[dict]:
    """
    Send a SOAP request using the XMLString variant and parse the response.

    The XMLString methods return HTML-encoded XML inside the SOAP response.
    We decode and parse it to extract row data.
    """
    headers = {
        **HEADERS_SOAP,
        "SOAPAction": f"{CGMIX_NAMESPACE}/{action}",
    }
    envelope = SOAP_ENVELOPE.format(body=body_xml)

    resp = requests.post(CGMIX_SOAP_URL, data=envelope, headers=headers, timeout=60)
    resp.raise_for_status()

    # Parse the outer SOAP envelope
    root = ET.fromstring(resp.content)

    # Find the result element (e.g., getVesselSummaryXMLStringResult)
    result_text = None
    for elem in root.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag.endswith("XMLStringResult") and elem.text:
            result_text = elem.text
            break

    if not result_text:
        return []

    # The result is HTML-encoded XML; decode it
    decoded_xml = html.unescape(result_text)

    # Parse the inner XML
    inner_root = ET.fromstring(decoded_xml)

    # Extract all row elements (they're direct children of NewDataSet)
    rows = []
    for child in inner_root:
        row = {}
        for field in child:
            tag = field.tag.split("}")[-1] if "}" in field.tag else field.tag
            row[tag] = field.text
        if row:
            rows.append(row)

    return rows


def search_vessels(
    name: str = "",
    call_sign: str = "",
    vin: str = "",
    hin: str = "",
    flag: str = "",
    service: str = "",
    build_year: str = "",
    vessel_id: str = "",
) -> list[dict]:
    """Search for vessels using the CGMIX PSIX SOAP API."""
    body = f"""<getVesselSummaryXMLString xmlns="{CGMIX_NAMESPACE}">
      <VesselID>{vessel_id}</VesselID>
      <VesselName>{name}</VesselName>
      <CallSign>{call_sign}</CallSign>
      <VIN>{vin}</VIN>
      <HIN>{hin}</HIN>
      <Flag>{flag}</Flag>
      <Service>{service}</Service>
      <BuildYear>{build_year}</BuildYear>
    </getVesselSummaryXMLString>"""

    return soap_request_xml_string("getVesselSummaryXMLString", body)


def get_vessel_particulars(vessel_id: str) -> list[dict]:
    """Get detailed vessel particulars by VesselID."""
    body = f"""<getVesselParticularsXMLString xmlns="{CGMIX_NAMESPACE}">
      <VesselID>{vessel_id}</VesselID>
    </getVesselParticularsXMLString>"""

    return soap_request_xml_string("getVesselParticularsXMLString", body)


def get_vessel_documents(vessel_id: str) -> list[dict]:
    """Get vessel documents/certifications by VesselID."""
    body = f"""<getVesselDocumentsXMLString xmlns="{CGMIX_NAMESPACE}">
      <VesselID>{vessel_id}</VesselID>
    </getVesselDocumentsXMLString>"""

    return soap_request_xml_string("getVesselDocumentsXMLString", body)


def get_vessel_dimensions(vessel_id: str) -> list[dict]:
    """Get vessel dimensions by VesselID."""
    body = f"""<getVesselDimensionsXMLString xmlns="{CGMIX_NAMESPACE}">
      <VesselID>{vessel_id}</VesselID>
    </getVesselDimensionsXMLString>"""

    return soap_request_xml_string("getVesselDimensionsXMLString", body)


def get_vessel_tonnage(vessel_id: str) -> list[dict]:
    """Get vessel tonnage by VesselID."""
    body = f"""<getVesselTonnageXMLString xmlns="{CGMIX_NAMESPACE}">
      <VesselID>{vessel_id}</VesselID>
    </getVesselTonnageXMLString>"""

    return soap_request_xml_string("getVesselTonnageXMLString", body)


def get_vessel_cases(vessel_id: str) -> list[dict]:
    """Get vessel inspection cases by VesselID."""
    body = f"""<getVesselCasesXMLString xmlns="{CGMIX_NAMESPACE}">
      <VesselID>{vessel_id}</VesselID>
    </getVesselCasesXMLString>"""

    return soap_request_xml_string("getVesselCasesXMLString", body)


def format_results(rows: list[dict], title: str = "Results") -> str:
    """Format results for display."""
    if not rows:
        return f"\n{title}: No results found.\n"

    lines = [f"\n{title} ({len(rows)} records):", "=" * 60]
    for i, row in enumerate(rows, 1):
        lines.append(f"\n--- Record {i} ---")
        for key, value in row.items():
            if value:
                lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def cmd_search(args):
    """Handle the 'search' command."""
    print(f"Searching CGMIX for vessel name='{args.name or ''}' "
          f"flag='{args.flag or ''}' service='{args.service or ''}'...")

    results = search_vessels(
        name=args.name or "",
        call_sign=args.call_sign or "",
        vin=args.vin or "",
        hin=args.hin or "",
        flag=args.flag or "",
        service=args.service or "",
        build_year=args.build_year or "",
    )
    print(format_results(results, "Vessel Search Results"))

    if args.output:
        out = Path(args.output)
        out.write_text(json.dumps(results, indent=2))
        print(f"\nResults written to {out}")


def cmd_details(args):
    """Handle the 'details' command - full vessel info."""
    vessel_id = args.vessel_id
    print(f"Fetching details for VesselID {vessel_id}...")

    particulars = get_vessel_particulars(vessel_id)
    print(format_results(particulars, "Vessel Particulars"))

    dimensions = get_vessel_dimensions(vessel_id)
    print(format_results(dimensions, "Vessel Dimensions"))

    tonnage = get_vessel_tonnage(vessel_id)
    print(format_results(tonnage, "Vessel Tonnage"))

    if args.output:
        out = Path(args.output)
        data = {
            "vessel_id": vessel_id,
            "particulars": particulars,
            "dimensions": dimensions,
            "tonnage": tonnage,
        }
        out.write_text(json.dumps(data, indent=2))
        print(f"\nResults written to {out}")


def cmd_docs(args):
    """Handle the 'docs' command - vessel documents/certs."""
    vessel_id = args.vessel_id
    print(f"Fetching documents for VesselID {vessel_id}...")

    docs = get_vessel_documents(vessel_id)
    print(format_results(docs, "Vessel Documents & Certifications"))

    if args.output:
        out = Path(args.output)
        out.write_text(json.dumps(docs, indent=2))
        print(f"\nResults written to {out}")


def cmd_cases(args):
    """Handle the 'cases' command - inspection cases."""
    vessel_id = args.vessel_id
    print(f"Fetching inspection cases for VesselID {vessel_id}...")

    cases = get_vessel_cases(vessel_id)
    print(format_results(cases, "Vessel Inspection Cases"))

    if args.output:
        out = Path(args.output)
        out.write_text(json.dumps(cases, indent=2))
        print(f"\nResults written to {out}")


def main():
    parser = argparse.ArgumentParser(
        description="Search USCG CGMIX vessel documentation database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search by vessel name (partial match)
  uv run python scripts/search_uscg_vessels.py search "NO SHOES"

  # Search by name and flag (use full country name)
  uv run python scripts/search_uscg_vessels.py search "DOMINO" --flag "UNITED STATES"

  # Search by service type (supports wildcards via partial match)
  uv run python scripts/search_uscg_vessels.py search --service Recreational --build-year 2010

  # Get full details for a vessel (dimensions, tonnage, particulars)
  uv run python scripts/search_uscg_vessels.py details 12345

  # Get documents/certifications
  uv run python scripts/search_uscg_vessels.py docs 12345

  # Get inspection cases
  uv run python scripts/search_uscg_vessels.py cases 12345

NOTE: Owner PII (names, addresses) was removed from public USCG databases
in 2018. To determine vessel ownership, you must:
  1. Request an Abstract of Title from USCG NVDC ($25/vessel)
     https://www.dco.uscg.mil/Our-Organization/Deputy-for-Operations-Policy-and-Capabilities-DCO-D/National-Vessel-Documentation-Center/
  2. Check state-level boat registration databases
  3. Search Florida DHSMV boat registrations (if FL-registered)
  4. Check USVI boat registration records
""",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # search command
    sp_search = subparsers.add_parser("search", help="Search for vessels")
    sp_search.add_argument("name", nargs="?", default="", help="Vessel name (partial match)")
    sp_search.add_argument("--call-sign", help="Radio call sign")
    sp_search.add_argument("--vin", help="Vessel identification number")
    sp_search.add_argument("--hin", help="Hull identification number")
    sp_search.add_argument("--flag", help="Flag country (e.g., 'UNITED STATES', 'PANAMA')")
    sp_search.add_argument("--service", help="Service type (e.g., 'Recreational', 'Sailing Vessel')")
    sp_search.add_argument("--build-year", help="Build year (YYYY)")
    sp_search.add_argument("--output", "-o", help="Output file path (JSON)")
    sp_search.set_defaults(func=cmd_search)

    # details command
    sp_details = subparsers.add_parser("details", help="Get vessel details by VesselID")
    sp_details.add_argument("vessel_id", help="CGMIX VesselID")
    sp_details.add_argument("--output", "-o", help="Output file path (JSON)")
    sp_details.set_defaults(func=cmd_details)

    # docs command
    sp_docs = subparsers.add_parser("docs", help="Get vessel documents by VesselID")
    sp_docs.add_argument("vessel_id", help="CGMIX VesselID")
    sp_docs.add_argument("--output", "-o", help="Output file path (JSON)")
    sp_docs.set_defaults(func=cmd_docs)

    # cases command
    sp_cases = subparsers.add_parser("cases", help="Get vessel inspection cases by VesselID")
    sp_cases.add_argument("vessel_id", help="CGMIX VesselID")
    sp_cases.add_argument("--output", "-o", help="Output file path (JSON)")
    sp_cases.set_defaults(func=cmd_cases)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
