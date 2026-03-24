#!/usr/bin/env python3
"""Fix 8 SHOULD_FIX editorial issues in the Chris Buskirk dossier."""

import json
from pathlib import Path

DOSSIER_PATH = Path(__file__).resolve().parent.parent / "content" / "dossiers" / "chris-buskirk.json"


def fix_issue_1_lead_mercer_inference(lead: str) -> str:
    """Finding #6776 'almost certainly Mercer' labeled direct_quote/confirmed but contains inference.
    Don't name Mercer in the lead as if it's established."""
    old = "from a single investor, likely Mercer"
    new = "from a single initial investor whose identity has not been publicly confirmed"
    assert old in lead, f"Issue 1: Could not find expected text in lead: {old!r}"
    return lead.replace(old, new)


def fix_issue_2_lead_absence_framing(lead: str) -> str:
    """'A distinguishing operational pattern is Buskirk's near-total absence from corporate filings'
    frames an inference (Finding #6785, medium confidence) as factual. Qualify it."""
    old = "A distinguishing operational pattern is Buskirk's near-total absence from corporate filings."
    new = "Corporate filings show no record of Buskirk as an officer in most of his associated entities, a pattern that analysis of filings identifies as consistent across the organization."
    assert old in lead, f"Issue 2: Could not find expected text in lead: {old!r}"
    return lead.replace(old, new)


def fix_issue_3_proxy_officer_section(sections: list[dict]) -> None:
    """'Gibson serves as proxy president' — 'proxy' is an inference. Qualify it in
    the ego_network connection description AND in the section prose."""
    for sec in sections:
        if sec["id"] == "proxy-officer-pattern":
            content = sec["content"]
            # The section prose already uses "Analysis of filings indicates" language
            # for the proxy pattern conclusion. But check the opening sentence.
            # Opening: "Buskirk is publicly identified as publisher... yet he is absent
            # from nearly all corporate filings. Analysis of filings indicates this pattern
            # operates through at least two distinct officer clusters"
            # That's fine — it's qualified.
            #
            # But the last paragraph says "using the Gibson household cluster... represents
            # a pattern of maintaining operational control" — that's already attributed to
            # Finding #6785 with "Analysis of filings indicates". OK.
            #
            # The issue is specifically about the connection description in viz_data
            # which says "Gibson serves as proxy president" — we handle that separately.
            # For the section, let's check if "proxy" appears unqualified.
            # Actually, looking at the section content again — it doesn't use the word
            # "proxy" in the body except in the title. The title is "Proxy Officer Pattern"
            # which is a section label. The section body uses "Analysis of filings indicates"
            # language consistently. So the section prose is OK.
            break


def fix_issue_3_viz_data(viz_data: dict) -> None:
    """Fix 'Gibson serves as proxy president' in ego_network connection description."""
    for conn in viz_data.get("ego_network", {}).get("connections", []):
        if conn.get("target") == "Ryan C Gibson":
            old_desc = conn.get("description", "")
            if "proxy president" in old_desc:
                conn["description"] = old_desc.replace(
                    "Gibson serves as proxy president/registered agent for American Greatness Inc while Buskirk is the actual publisher.",
                    "Filing records identify Gibson as president and registered agent of American Greatness Inc, an entity whose publisher is publicly identified as Buskirk."
                )


def fix_issue_4_executive_branch_rockbridge(sections: list[dict]) -> None:
    """'a physical venue for the same network that Rockbridge coordinates financially'
    is editorial synthesis attributed to Finding #6743, which doesn't say this.
    Replace with what the finding actually says."""
    for sec in sections:
        if sec["id"] == "executive-branch-club":
            old = "The club is structured to facilitate private access between business executives and Trump administration officials \u2014 a physical venue for the same network that Rockbridge coordinates financially [Finding #6743]."
            new = "According to reporting, the club is designed to allow business executives private access to Trump advisors and Cabinet members [Finding #6743]."
            assert old in sec["content"], f"Issue 4: Could not find expected text: {old!r}"
            sec["content"] = sec["content"].replace(old, new)
            break


def fix_issue_5_executive_branch_address(sections: list[dict]) -> None:
    """'indicates a tightly integrated business relationship' attributed to Finding #6778
    (address co-location) — the finding only shows shared addresses. Downgrade language."""
    for sec in sections:
        if sec["id"] == "executive-branch-club":
            old = "The co-ownership of a DC access venue plus shared Florida office space indicates a tightly integrated business relationship spanning investment, SPACs, and political access [Finding #6778]."
            new = "The shared Palm Beach address is consistent with an operational relationship between Buskirk and Malik spanning investment, SPACs, and political access [Finding #6778]."
            assert old in sec["content"], f"Issue 5: Could not find expected text: {old!r}"
            sec["content"] = sec["content"].replace(old, new)
            break


def fix_issue_6_chain_bridge_bank(sections: list[dict]) -> None:
    """'financial backbone of Republican political operations' upgrades the sourced description.
    Use the actual quote from Finding #6747."""
    for sec in sections:
        if sec["id"] == "political-infrastructure":
            old = 'Known as the financial backbone of Republican political operations, it has served'
            new = 'Known as "the bank of the Republican Party," it has served'
            assert old in sec["content"], f"Issue 6: Could not find expected text: {old!r}"
            sec["content"] = sec["content"].replace(old, new)
            break


def fix_issue_7_lead_1789_overlap(lead: str) -> str:
    """Lead duplicates 1789 Capital section details ($10M->$3B AUM, portfolio, real estate, Trump Jr.).
    Trim to mention co-founding and approximate scale only; move details to section."""
    old = (
        '<a href="/dossiers/1789-capital">1789 Capital</a> has grown from $10M at launch '
        '(from a single initial investor whose identity has not been publicly confirmed) '
        'to over $3B in total AUM across 11 registered fund entities, a $2B growth equity fund '
        'holding positions in <a href="/dossiers/spacex">SpaceX</a>, '
        '<a href="/dossiers/anduril-industries">Anduril</a>, '
        '<a href="/dossiers/xai">xAI</a>, and Neuralink, and a $1B real estate partnership '
        '[Finding #6776] [Finding #6779]. Donald Trump Jr. joined the firm as a partner in November 2024 [Finding #6779].'
    )
    new = (
        '<a href="/dossiers/1789-capital">1789 Capital</a> has grown to over $3B in total AUM '
        'across 11 registered fund entities [Finding #6776] [Finding #6779].'
    )
    assert old in lead, f"Issue 7: Could not find expected text in lead"
    return lead.replace(old, new)


def fix_issue_8_lead_political_overlap(lead: str) -> str:
    """Lead duplicates political-infrastructure section donor details.
    Keep only the total, move donor breakdown to section."""
    old = (
        'His Turnout for America super PAC raised $45.67M in the 2024 cycle from donors including '
        'Diane Hendricks ($11M), Kelcy Warren ($7.5M+), and '
        '<a href="/dossiers/howard-lutnick">Howard Lutnick</a> ($1.98M) [Finding #6741].'
    )
    new = (
        'His Turnout for America super PAC raised $45.67M in the 2024 cycle [Finding #6741].'
    )
    assert old in lead, f"Issue 8: Could not find expected text in lead"
    return lead.replace(old, new)


def main():
    dossier = json.loads(DOSSIER_PATH.read_text())
    curation = dossier["curation"]
    lead = curation["lead"]
    sections = curation["sections"]

    # Fix issue 1 first (before issue 7 which depends on its output)
    lead = fix_issue_1_lead_mercer_inference(lead)
    print("  [1] Fixed: Mercer inference in lead")

    # Fix issue 2
    lead = fix_issue_2_lead_absence_framing(lead)
    print("  [2] Fixed: Corporate filing absence framing in lead")

    # Fix issue 3 — viz_data connection description
    fix_issue_3_proxy_officer_section(sections)
    fix_issue_3_viz_data(dossier.get("viz_data", {}))
    print("  [3] Fixed: 'proxy president' in connection description")

    # Fix issue 4
    fix_issue_4_executive_branch_rockbridge(sections)
    print("  [4] Fixed: Executive Branch club Rockbridge synthesis")

    # Fix issue 5
    fix_issue_5_executive_branch_address(sections)
    print("  [5] Fixed: Address co-location overclaim")

    # Fix issue 6
    fix_issue_6_chain_bridge_bank(sections)
    print("  [6] Fixed: Chain Bridge Bank quote")

    # Fix issue 7 (depends on issue 1 already applied)
    lead = fix_issue_7_lead_1789_overlap(lead)
    print("  [7] Fixed: Lead/1789 Capital section overlap trimmed")

    # Fix issue 8
    lead = fix_issue_8_lead_political_overlap(lead)
    print("  [8] Fixed: Lead/political infrastructure section overlap trimmed")

    # Write back
    curation["lead"] = lead
    curation["sections"] = sections
    dossier["curation"] = curation

    DOSSIER_PATH.write_text(json.dumps(dossier, indent=2, default=str))
    print(f"\nWrote {DOSSIER_PATH}")


if __name__ == "__main__":
    main()
