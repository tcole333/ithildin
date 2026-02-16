#!/usr/bin/env python3
"""
Shared IRS 990 XML parsing — Schedule I (grants) and Schedule R (related orgs).

Extracted from ingest_990_xml.py for reuse by both the targeted EIN ingest
pipeline and the bulk grant database pipeline.

Two entry points:
    parse_filing(xml_path)       — parse from file path (used by targeted tool)
    parse_filing_bytes(data)     — parse from raw bytes (used by bulk pipeline)
"""

import xml.etree.ElementTree as ET

NS = {"irs": "http://www.irs.gov/efile"}


def _text(el, tag):
    """Get text from a child element, or empty string."""
    if el is None:
        return ""
    child = el.find(f"irs:{tag}", NS)
    if child is None:
        child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _int(el, tag):
    """Get integer from a child element, or 0."""
    val = _text(el, tag)
    if not val:
        return 0
    try:
        return int(val.replace(",", ""))
    except ValueError:
        return 0


def _build_address(el):
    """Build address string from US or foreign address group."""
    if el is None:
        return ""
    for addr_tag in ["USAddress", "AddressUS"]:
        addr = el.find(f"irs:{addr_tag}", NS)
        if addr is not None:
            line1 = _text(addr, "AddressLine1Txt") or _text(addr, "AddressLine1")
            line2 = _text(addr, "AddressLine2Txt") or _text(addr, "AddressLine2")
            city = _text(addr, "CityNm") or _text(addr, "City")
            state = _text(addr, "StateAbbreviationCd") or _text(addr, "State")
            zip_code = _text(addr, "ZIPCd") or _text(addr, "ZIPCode")
            parts = [p for p in [line1, line2, city, state, zip_code] if p]
            return ", ".join(parts)
    for addr_tag in ["ForeignAddress", "AddressForeign"]:
        addr = el.find(f"irs:{addr_tag}", NS)
        if addr is not None:
            line1 = _text(addr, "AddressLine1Txt") or _text(addr, "AddressLine1")
            line2 = _text(addr, "AddressLine2Txt") or _text(addr, "AddressLine2")
            city = _text(addr, "CityNm") or _text(addr, "City")
            country = _text(addr, "CountryCd") or _text(addr, "Country")
            parts = [p for p in [line1, line2, city, country] if p]
            return ", ".join(parts)
    return ""


def _get_business_name(el):
    """Extract business name from BusinessName or RecipientBusinessName group."""
    if el is None:
        return ""
    for name_tag in ["RecipientBusinessName", "BusinessName", "BusinessNameLine1Txt",
                      "OrganizationBusinessName"]:
        name_el = el.find(f"irs:{name_tag}", NS)
        if name_el is not None:
            line1 = _text(name_el, "BusinessNameLine1Txt") or _text(name_el, "BusinessNameLine1")
            if line1:
                return line1
            if name_el.text:
                return name_el.text.strip()
    person = _text(el, "RecipientPersonNm")
    if person:
        return person
    return ""


def _parse_root(root):
    """Parse grants and related orgs from an already-parsed XML root element."""
    header = root.find(".//irs:ReturnHeader", NS)
    filer = root.find(".//irs:Filer", NS) if header is not None else None

    ein = _text(filer, "EIN") if filer is not None else ""
    filer_name = ""
    if filer is not None:
        name_el = filer.find(".//irs:BusinessName", NS)
        if name_el is not None:
            filer_name = _text(name_el, "BusinessNameLine1Txt") or _text(name_el, "BusinessNameLine1")
    tax_period = (_text(header, "TaxPeriodEndDt") or _text(header, "TaxPeriodEndDate")) if header is not None else ""
    return_type = (_text(header, "ReturnTypeCd") or _text(header, "ReturnType")) if header is not None else ""

    result = {
        "ein": ein,
        "filer_name": filer_name,
        "tax_period": tax_period,
        "return_type": return_type,
        "grants": [],
        "related_orgs": [],
    }

    # Schedule I (990): Grants to Organizations
    sched_i = root.find(".//irs:IRS990ScheduleI", NS)
    if sched_i is not None:
        for grant in sched_i.findall(".//irs:RecipientTable", NS):
            recipient_name = _get_business_name(grant)
            if not recipient_name:
                recipient_name = _text(grant, "RecipientPersonNm")
            result["grants"].append({
                "recipient_name": recipient_name,
                "recipient_ein": _text(grant, "RecipientEIN"),
                "recipient_address": _build_address(grant),
                "cash_amount": _int(grant, "CashGrantAmt"),
                "non_cash_amount": _int(grant, "NonCashAssistanceAmt"),
                "purpose": _text(grant, "PurposeOfGrantTxt"),
                "recipient_type": "organization" if _text(grant, "RecipientEIN") else "individual",
            })

    # Schedule I variant (990-PF): Grants
    pf = root.find(".//irs:IRS990PF", NS)
    if pf is not None:
        for grant in pf.findall(".//irs:GrantOrContributionPdDurYrGrp", NS):
            recipient_name = _get_business_name(grant)
            result["grants"].append({
                "recipient_name": recipient_name,
                "recipient_ein": _text(grant, "RecipientEIN"),
                "recipient_address": _build_address(grant),
                "cash_amount": _int(grant, "Amt"),
                "non_cash_amount": 0,
                "purpose": _text(grant, "GrantOrContributionPurposeTxt"),
                "recipient_type": "organization",
            })

    # Schedule R: Related Organizations
    sched_r = root.find(".//irs:IRS990ScheduleR", NS)
    if sched_r is not None:
        rel_groups = [
            ("IdDisregardedEntitiesGrp", "disregarded_entity"),
            ("RelatedTaxExemptOrgGrp", "related_tax_exempt"),
            ("RelatedOrgCtrlEntityGrp", "related_taxable"),
            ("TrnsfrTransRlnspNonExmptGrp", "transaction_partner"),
        ]
        for group_tag, rel_type in rel_groups:
            for org in sched_r.findall(f".//irs:{group_tag}", NS):
                related_name = _get_business_name(org)
                result["related_orgs"].append({
                    "related_name": related_name,
                    "related_ein": _text(org, "EIN") or _text(org, "EINOfRelatedOrgTxt"),
                    "related_address": _build_address(org),
                    "relationship_type": rel_type,
                    "primary_activities": _text(org, "PrimaryActivitiesTxt"),
                    "legal_domicile": _text(org, "LegalDomicileStateCd") or _text(org, "LegalDomicileCountryCd"),
                    "total_income": _int(org, "TotalIncomeAmt"),
                    "end_of_year_assets": _int(org, "EndOfYearAssetsAmt"),
                    "direct_controlling_entity": (
                        _text(org, "DirectControllingEntityName") or
                        _get_business_name(org.find("irs:DirectControllingEntityName", NS))
                        if org.find("irs:DirectControllingEntityName", NS) is not None
                        else _text(org, "DirectControllingNm")
                    ),
                })

    return result


def parse_filing(xml_path):
    """Parse a 990 XML filing from a file path."""
    tree = ET.parse(xml_path)
    return _parse_root(tree.getroot())


def parse_filing_bytes(data):
    """Parse a 990 XML filing from raw bytes.

    Handles UTF-8 BOM prefix that some IRS XMLs include.
    """
    if data[:3] == b"\xef\xbb\xbf":
        data = data[3:]
    root = ET.fromstring(data)
    return _parse_root(root)


def has_grant_data(xml_bytes):
    """Fast byte-scan to check if XML likely contains grant or related-org data.

    Avoids full XML parsing for ~70% of filings that lack Schedule I/R.
    """
    return (b"<IRS990ScheduleI" in xml_bytes or
            b"GrantOrContribution" in xml_bytes or
            b"<IRS990ScheduleR" in xml_bytes)
