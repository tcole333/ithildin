#!/usr/bin/env python3
"""Fix 7 SHOULD_FIX editorial issues in the Rockbridge Network dossier."""

import json
from pathlib import Path

DOSSIER_PATH = Path(__file__).resolve().parent.parent / "content" / "dossiers" / "rockbridge-network.json"


def fix_system_role(dossier: dict) -> int:
    """Issues #1 and #5: Replace 'designed to obscure' with neutral 501(c)(4) language."""
    sr = dossier["curation"]["system_role"]
    old = "designed to obscure individual donor identities"
    new = "which shields individual donor identities under 501(c)(4) rules"
    if old in sr:
        dossier["curation"]["system_role"] = sr.replace(old, new)
        print("  [1/5] Fixed system_role: 'designed to obscure' -> neutral 501(c)(4) language")
        return 1
    print("  [1/5] SKIP: 'designed to obscure' not found in system_role")
    return 0


def fix_government_personnel_section(dossier: dict) -> int:
    """Issue #2: Add attribution language to Government Personnel Placement section title
    and body where causal placement claims appear."""
    fixes = 0
    for sec in dossier["curation"]["sections"]:
        if sec["id"] != "government-personnel":
            continue

        # Fix section title: "Placement" implies causation as fact
        old_title = "Government Personnel Placement"
        new_title = "Government Personnel and Administration Ties"
        if sec["title"] == old_title:
            sec["title"] = new_title
            fixes += 1
            print(f"  [2a] Fixed section title: '{old_title}' -> '{new_title}'")

        # Fix body: The Transition Project description needs hedging
        content = sec["content"]

        # Add attribution to "was designed to identify, recruit, and train"
        old = "was designed to identify, recruit, and train personnel for a Republican administration"
        new = "was established to identify, recruit, and train personnel for a Republican administration, per leaked prospectus documents"
        if old in content:
            content = content.replace(old, new)
            fixes += 1
            print("  [2b] Fixed: hedged Transition Project description with source attribution")

        sec["content"] = content
        break

    if fixes == 0:
        print("  [2] SKIP: government-personnel section not found or no matches")
    return fixes


def fix_key_relationships_claremont(dossier: dict) -> int:
    """Issue #3: Remove 'intellectual cover for executive power expansion' characterization
    about Claremont Institute. Replace with evidence-based description."""
    fixes = 0
    for sec in dossier["curation"]["sections"]:
        if sec["id"] != "key-relationships":
            continue

        content = sec["content"]

        # Fix the Claremont paragraph
        old = "Claremont supplies doctrine and intellectual cover for executive power expansion, and SACR provides ground-level fraternal organization"
        new = "Claremont supplies the doctrinal framework through which Buskirk and allied thinkers articulate their political vision, and SACR provides ground-level fraternal organization"
        if old in content:
            content = content.replace(old, new)
            fixes += 1
            print("  [3] Fixed: replaced 'intellectual cover for executive power expansion' with evidence-based description")

        sec["content"] = content
        break

    if fixes == 0:
        print("  [3] SKIP: Claremont characterization not found")
    return fixes


def fix_thiel_puppet_master(dossier: dict) -> int:
    """Issue #4: Attribute 'puppet master' in viz_data rather than stating as editorial fact."""
    fixes = 0

    # Check viz_data ego_network connections
    ego = dossier.get("viz_data", {}).get("ego_network", {})
    for conn in ego.get("connections", []):
        if conn.get("target") == "Peter Thiel":
            desc = conn.get("description", "")
            if "Described as puppet master." in desc:
                conn["description"] = desc.replace(
                    "Described as puppet master.",
                    "Described in reporting as 'puppet master' of the network."
                )
                fixes += 1
                print("  [4] Fixed viz_data: attributed 'puppet master' to reporting")
            elif "puppet master" in desc.lower() and "described in reporting" not in desc.lower():
                # Handle other formulations
                conn["description"] = desc.replace(
                    "puppet master",
                    "described in reporting as 'puppet master'"
                )
                fixes += 1
                print("  [4] Fixed viz_data: attributed 'puppet master' to reporting (alt match)")

    # Also check the Claremont viz_data connection for "intellectual cover"
    for conn in ego.get("connections", []):
        if conn.get("target") == "Claremont Institute":
            desc = conn.get("description", "")
            old_desc = "Claremont supplies doctrine/intellectual cover"
            new_desc = "Claremont supplies doctrine and ideological framing"
            if old_desc in desc:
                conn["description"] = desc.replace(old_desc, new_desc)
                fixes += 1
                print("  [4+] Fixed viz_data: replaced 'intellectual cover' in Claremont connection")

    if fixes == 0:
        print("  [4] SKIP: 'puppet master' not found in viz_data or sections")
    return fixes


def fix_international_expansion(dossier: dict) -> int:
    """Issue #6: Hedge 'transforms Rockbridge from a domestic donor network into an
    international influence operation' as analytical assessment."""
    fixes = 0
    for sec in dossier["curation"]["sections"]:
        if sec["id"] != "international-expansion":
            continue

        content = sec["content"]

        old = "This expansion transforms Rockbridge from a domestic donor network into an international influence operation."
        new = "Analysis of these developments indicates Rockbridge is expanding beyond its domestic donor-coordination role into international relationship-building, with direct channels between foreign business elites and the Vice President's office."
        if old in content:
            content = content.replace(old, new)
            fixes += 1
            print("  [6] Fixed: hedged international expansion characterization as analytical assessment")

        # Also remove the redundant "creating direct channels..." that follows
        # since the replacement already includes that concept
        old2 = " Donald Trump Jr., who holds no official government title, is described as instrumental in the global expansion, creating direct channels between foreign business elites and the US Vice President's office via Rockbridge infrastructure."
        new2 = " Donald Trump Jr., who holds no official government title, is described in reporting as instrumental in the global expansion."
        if old2 in content:
            content = content.replace(old2, new2)
            fixes += 1
            print("  [6+] Fixed: trimmed redundant direct-channels language")

        sec["content"] = content
        break

    if fixes == 0:
        print("  [6] SKIP: international expansion text not found")
    return fixes


def fix_lead_trim(dossier: dict) -> int:
    """Issue #7: Trim the lead to summarize at a higher level — remove specific figures
    that are repeated in body sections."""
    lead = dossier["curation"]["lead"]

    # Replace the overly-detailed second paragraph with a high-level summary
    old_p2 = (
        "<p>The network's primary super PAC, Turnout for America (FEC C00883520), "
        "raised $45.67 million in the 2023-2024 cycle, with top donors including "
        "Diane Hendricks ($11 million), Kelcy Warren ($7.5 million), and Andrew Beal "
        "($2 million). Over the Horizon Action served as the central 501(c)(4) financial "
        "distribution hub, receiving $20.7 million and distributing $6.9 million to Better "
        "Tomorrow and $2.05 million to Faithful in Action \u2014 grant flow analysis of 990 "
        "and FEC filings documents these distributions [Finding #6768] [Finding #6721]. "
        "Rockbridge deployed approximately 5,000 field operatives across seven swing states "
        "for the 2024 election and allocated a $3 million Transition Project budget to "
        "identify and train personnel for the Trump administration [Finding #6726] "
        "[Finding #6739].</p>"
    )
    new_p2 = (
        "<p>FEC and 990 filings show tens of millions in super PAC fundraising and "
        "a multi-layered 501(c)(4) grant distribution system routing funds through "
        "Over the Horizon Action to subsidiary entities [Finding #6768] [Finding #6721]. "
        "Rockbridge deployed thousands of field operatives across swing states for the "
        "2024 election and ran a dedicated Transition Project to identify and train "
        "personnel for the Trump administration [Finding #6726] [Finding #6739].</p>"
    )

    if old_p2 in lead:
        lead = lead.replace(old_p2, new_p2)
        dossier["curation"]["lead"] = lead
        print("  [7] Fixed: trimmed lead paragraph 2 — removed repeated dollar figures")
        return 1

    # Try without the em-dash unicode in case encoding differs
    old_p2_alt = old_p2.replace("\u2014", "—")
    if old_p2_alt in lead:
        lead = lead.replace(old_p2_alt, new_p2)
        dossier["curation"]["lead"] = lead
        print("  [7] Fixed: trimmed lead paragraph 2 (alt encoding)")
        return 1

    print("  [7] SKIP: lead paragraph 2 text not matched")
    return 0


def fix_ai_tells(dossier: dict) -> int:
    """Issue #8: Vary the 'analysis of X reveals/documents Y' trailing clause pattern.
    Replace repetitive phrasings with varied alternatives."""
    fixes = 0

    # Define specific replacements for repeated patterns across sections
    replacements = [
        # organizational-structure section (no "and FEC" in this one)
        (
            "grant flow analysis of 990 filings documents these distributions [Finding #6768]",
            "per 990 filings [Finding #6768]"
        ),
        # organizational-structure section (with "and FEC")
        (
            "grant flow analysis of 990 and FEC filings documents these distributions [Finding #6768]",
            "per 990 and FEC filings [Finding #6768]"
        ),
        # financial-flows section
        (
            "financial flow analysis of 990 and FEC filings documents these distributions [Finding #6768]",
            "as 990 and FEC filing data shows [Finding #6768]"
        ),
        (
            "as examination of FEC records reveals [Finding #6770]",
            "per FEC records [Finding #6770]"
        ),
        # government-personnel section
        (
            "analysis of reporting and financial disclosures documents these pathways [Finding #6750]",
            "per reporting and financial disclosures [Finding #6750]"
        ),
        # election-operations section
        (
            "analysis of FEC disbursement records documents these expenditures [Finding #6751]",
            "per FEC disbursement records [Finding #6751]"
        ),
        (
            "as analysis of the results indicates [Finding #6751]",
            "as multiple analysts have noted [Finding #6751]"
        ),
        # buskirk-operational-hub section — "examination of corporate filings" x2
        (
            "examination of FEC filings documents these contributions [Finding #6767]",
            "per FEC filings [Finding #6767]"
        ),
        (
            "examination of corporate filings across multiple jurisdictions reveals this pattern [Finding #6785]",
            "as corporate filings across multiple jurisdictions show [Finding #6785]"
        ),
        # key-relationships section
        (
            "cross-reference of LittleSis records confirms these connections [Connection #3420]",
            "per LittleSis records [Connection #3420]"
        ),
        # lead — already handled in fix_lead_trim but may have leftovers
        (
            "Analysis of personnel records and reporting indicates at least seven officials placed through the Transition Project now serve in the administration, according to analysis of reporting and financial disclosures",
            "Records and reporting indicate at least seven officials with Rockbridge ties now serve in the administration, per financial disclosures and public reporting"
        ),
        # silicon-valley-nexus section
        (
            "cross-reference of LittleSis and FEC records indicates this pattern [Finding #5448]",
            "per LittleSis and FEC records [Finding #5448]"
        ),
    ]

    # Apply to all content fields: lead, sections, system_role
    fields_to_check = []
    if dossier["curation"].get("lead"):
        fields_to_check.append(("lead", None))
    for i, sec in enumerate(dossier["curation"].get("sections", [])):
        fields_to_check.append(("section", i))

    for old, new in replacements:
        # Check lead
        lead = dossier["curation"].get("lead", "")
        if old in lead:
            dossier["curation"]["lead"] = lead.replace(old, new)
            fixes += 1
            print(f"  [8] Fixed AI tell in lead: '{old[:50]}...'")
            continue

        # Check sections
        for sec in dossier["curation"].get("sections", []):
            content = sec.get("content", "")
            if old in content:
                sec["content"] = content.replace(old, new)
                fixes += 1
                print(f"  [8] Fixed AI tell in section '{sec['id']}': '{old[:50]}...'")
                break

    if fixes == 0:
        print("  [8] SKIP: no matching AI tell patterns found")
    return fixes


def main():
    print(f"Loading dossier from {DOSSIER_PATH}")
    dossier = json.loads(DOSSIER_PATH.read_text())

    total_fixes = 0
    print("\nApplying editorial fixes:")

    total_fixes += fix_system_role(dossier)
    total_fixes += fix_government_personnel_section(dossier)
    total_fixes += fix_key_relationships_claremont(dossier)
    total_fixes += fix_thiel_puppet_master(dossier)
    total_fixes += fix_international_expansion(dossier)
    total_fixes += fix_lead_trim(dossier)
    total_fixes += fix_ai_tells(dossier)

    if total_fixes > 0:
        DOSSIER_PATH.write_text(json.dumps(dossier, indent=2, default=str))
        print(f"\nWrote {total_fixes} fixes to {DOSSIER_PATH}")
    else:
        print("\nNo fixes applied.")


if __name__ == "__main__":
    main()
