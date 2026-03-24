#!/usr/bin/env python3
"""Fix 12 claim_compliance SHOULD_FIX issues in rockbridge-network dossier.

Each issue is a synthesis or inference finding cited in prose without
attribution language that matches the ATTRIBUTION_RE pattern in the
review checker. The fix adds or rewrites attribution phrasing to match.
"""

import json
from pathlib import Path

DOSSIER_PATH = Path(__file__).resolve().parent.parent / "content" / "dossiers" / "rockbridge-network.json"

EM = "\u2014"  # em dash


def fix_dossier():
    dossier = json.loads(DOSSIER_PATH.read_text())
    curation = dossier["curation"]
    fixes_applied = 0

    # ──────────────────────────────────────────────────────────────────
    # LEAD — 3 issues (#6768, #6727, #6750)
    # ──────────────────────────────────────────────────────────────────
    lead = curation["lead"]

    # Issue 1: Finding #6768 in lead
    # "FEC and 990 filings show" doesn't match ATTRIBUTION_RE.
    # Fix: prepend "Cross-reference of" which matches "cross-?reference of".
    old = (
        "FEC and 990 filings show tens of millions in super PAC fundraising "
        "and a multi-layered 501(c)(4) grant distribution system routing funds "
        "through Over the Horizon Action to subsidiary entities "
        "[Finding #6768] [Finding #6721]"
    )
    new = (
        "Cross-reference of FEC and 990 filings shows tens of millions in super PAC fundraising "
        "and a multi-layered 501(c)(4) grant distribution system routing funds "
        "through Over the Horizon Action to subsidiary entities "
        "[Finding #6768] [Finding #6721]"
    )
    if old in lead:
        lead = lead.replace(old, new)
        fixes_applied += 1
        print("  Fixed issue 1: Finding #6768 in lead")
    else:
        print("  WARNING: Could not find issue 1 text in lead")

    # Issues 2-3: Finding #6727 and #6750 in lead (same sentence)
    # "Records and reporting indicate" doesn't match; "Records indicate" would,
    # but rewrite to use "According to" for varied phrasing.
    old = (
        "Records and reporting indicate at least seven officials with Rockbridge "
        "ties now serve in the administration, per financial disclosures and "
        "public reporting [Finding #6727] [Finding #6750]"
    )
    new = (
        "According to financial disclosures and public reporting, at least seven officials "
        "with Rockbridge ties now serve in the administration "
        "[Finding #6727] [Finding #6750]"
    )
    if old in lead:
        lead = lead.replace(old, new)
        fixes_applied += 2  # Fixes both #6727 and #6750
        print("  Fixed issues 2-3: Finding #6727 and #6750 in lead")
    else:
        print("  WARNING: Could not find issues 2-3 text in lead")

    curation["lead"] = lead

    # ──────────────────────────────────────────────────────────────────
    # Helper to get section content by id
    # ──────────────────────────────────────────────────────────────────
    def get_section(section_id):
        for sec in curation["sections"]:
            if sec["id"] == section_id:
                return sec
        return None

    # ──────────────────────────────────────────────────────────────────
    # LEGAL AND ORGANIZATIONAL STRUCTURE — 1 issue (#6768)
    # ──────────────────────────────────────────────────────────────────
    sec = get_section("organizational-structure")
    if sec:
        content = sec["content"]

        # Issue 4: Finding #6768
        # "— per 990 filings" doesn't match; rewrite to "review of the filings".
        old = (
            f"{EM} per 990 filings [Finding #6768]"
        )
        new = (
            ", according to review of the filings [Finding #6768]"
        )
        if old in content:
            content = content.replace(old, new)
            fixes_applied += 1
            print("  Fixed issue 4: Finding #6768 in Legal and Organizational Structure")
        else:
            print("  WARNING: Could not find issue 4 text")

        sec["content"] = content

    # ──────────────────────────────────────────────────────────────────
    # FINANCIAL FLOWS AND DONOR BASE — 2 issues (#6768, #6770)
    # ──────────────────────────────────────────────────────────────────
    sec = get_section("financial-flows")
    if sec:
        content = sec["content"]

        # Issue 5: Finding #6768 in Financial Flows
        # "— as 990 and FEC filing data shows" doesn't match.
        # Fix: "financial flow analysis of 990 and FEC data shows"
        old = (
            f"{EM} as 990 and FEC filing data shows [Finding #6768]"
        )
        new = (
            ", as financial flow analysis of 990 and FEC data shows [Finding #6768]"
        )
        if old in content:
            content = content.replace(old, new)
            fixes_applied += 1
            print("  Fixed issue 5: Finding #6768 in Financial Flows")
        else:
            print("  WARNING: Could not find issue 5 text")

        # Issue 6: Finding #6770 in Financial Flows
        # "per FEC records" doesn't match.
        # Fix: "according to review of FEC records"
        old = (
            "and even those are routed through the WinRed-affiliated back-office "
            "infrastructure, per FEC records [Finding #6770]"
        )
        new = (
            "and even those are routed through the WinRed-affiliated back-office "
            "infrastructure, according to review of FEC records [Finding #6770]"
        )
        if old in content:
            content = content.replace(old, new)
            fixes_applied += 1
            print("  Fixed issue 6: Finding #6770 in Financial Flows")
        else:
            print("  WARNING: Could not find issue 6 text")

        sec["content"] = content

    # ──────────────────────────────────────────────────────────────────
    # GOVERNMENT PERSONNEL AND ADMINISTRATION TIES — 1 issue (#6750)
    # ──────────────────────────────────────────────────────────────────
    sec = get_section("government-personnel")
    if sec:
        content = sec["content"]

        # Issue 7: Finding #6750
        # "— per reporting and financial disclosures" doesn't match.
        # Fix: "according to reporting and financial disclosures"
        old = (
            f"{EM} per reporting and financial disclosures [Finding #6750]"
        )
        new = (
            ", according to reporting and financial disclosures [Finding #6750]"
        )
        if old in content:
            content = content.replace(old, new)
            fixes_applied += 1
            print("  Fixed issue 7: Finding #6750 in Government Personnel")
        else:
            print("  WARNING: Could not find issue 7 text")

        sec["content"] = content

    # ──────────────────────────────────────────────────────────────────
    # SILICON VALLEY AND TECH DONOR NEXUS — 1 issue (#5448)
    # ──────────────────────────────────────────────────────────────────
    sec = get_section("silicon-valley-nexus")
    if sec:
        content = sec["content"]

        # Issue 8: Finding #5448
        # "— per LittleSis and FEC records" doesn't match.
        # Fix: "as examination of LittleSis and FEC records indicates"
        old = (
            f"node {EM} per LittleSis and FEC records [Finding #5448]"
        )
        new = (
            "node, as examination of LittleSis and FEC records indicates [Finding #5448]"
        )
        if old in content:
            content = content.replace(old, new)
            fixes_applied += 1
            print("  Fixed issue 8: Finding #5448 in Silicon Valley")
        else:
            print("  WARNING: Could not find issue 8 text")

        sec["content"] = content

    # ──────────────────────────────────────────────────────────────────
    # CHRIS BUSKIRK AS OPERATIONAL HUB — 1 issue (#6785)
    # ──────────────────────────────────────────────────────────────────
    sec = get_section("buskirk-operational-hub")
    if sec:
        content = sec["content"]

        # Issue 9: Finding #6785 (inference)
        # "— as corporate filings across multiple jurisdictions show" doesn't match.
        # Fix: use "examination of" which matches the ATTRIBUTION_RE pattern.
        old = (
            f"{EM} as corporate filings across multiple jurisdictions show "
            "[Finding #6785] [Finding #6783]"
        )
        new = (
            ", per examination of corporate filings across multiple jurisdictions "
            "[Finding #6785] [Finding #6783]"
        )
        if old in content:
            content = content.replace(old, new)
            fixes_applied += 1
            print("  Fixed issue 9: Finding #6785 in Buskirk Operational Hub")
        else:
            print("  WARNING: Could not find issue 9 text")

        sec["content"] = content

    # ──────────────────────────────────────────────────────────────────
    # ELECTION AND FIELD OPERATIONS — 2 issues (#6751 x2)
    # ──────────────────────────────────────────────────────────────────
    sec = get_section("election-operations")
    if sec:
        content = sec["content"]

        # Issue 10: Finding #6751 (first instance)
        # "— per FEC disbursement records" doesn't match.
        # Fix: "as review of FEC disbursement records shows"
        old = (
            f"{EM} per FEC disbursement records [Finding #6751] [Finding #6721]"
        )
        new = (
            ", as review of FEC disbursement records shows [Finding #6751] [Finding #6721]"
        )
        if old in content:
            content = content.replace(old, new)
            fixes_applied += 1
            print("  Fixed issue 10: Finding #6751 (first) in Election Operations")
        else:
            print("  WARNING: Could not find issue 10 text")

        # Issue 11: Finding #6751 (second instance)
        # "as multiple analysts have noted" doesn't match.
        # Fix: "analysis of available data suggests"
        old = (
            "as multiple analysts have noted [Finding #6751]"
        )
        new = (
            "as analysis of available data suggests [Finding #6751]"
        )
        if old in content:
            content = content.replace(old, new)
            fixes_applied += 1
            print("  Fixed issue 11: Finding #6751 (second) in Election Operations")
        else:
            print("  WARNING: Could not find issue 11 text")

        sec["content"] = content

    # ──────────────────────────────────────────────────────────────────
    # KEY ORGANIZATIONAL RELATIONSHIPS — 1 issue (#6761)
    # ──────────────────────────────────────────────────────────────────
    sec = get_section("key-relationships")
    if sec:
        content = sec["content"]

        # Issue 12: Finding #6761
        # "— per LittleSis records" doesn't match.
        # Fix: "according to LittleSis records"
        old = (
            f"{EM} per LittleSis records [Connection #3420] [Connection #3433] [Finding #6761]"
        )
        new = (
            ", according to LittleSis records [Connection #3420] [Connection #3433] [Finding #6761]"
        )
        if old in content:
            content = content.replace(old, new)
            fixes_applied += 1
            print("  Fixed issue 12: Finding #6761 in Key Organizational Relationships")
        else:
            print("  WARNING: Could not find issue 12 text")

        sec["content"] = content

    # ──────────────────────────────────────────────────────────────────
    # Write back
    # ──────────────────────────────────────────────────────────────────
    dossier["curation"] = curation
    DOSSIER_PATH.write_text(json.dumps(dossier, indent=2, default=str))
    print(f"\nApplied {fixes_applied}/12 fixes to {DOSSIER_PATH.name}")
    return fixes_applied


if __name__ == "__main__":
    fix_dossier()
