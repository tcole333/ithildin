#!/usr/bin/env python3
"""
Curate the National Fraud Enforcement Division dossier.
Writes the curation block into content/dossiers/national-fraud-enforcement-division.json.
"""

import json
import datetime
from pathlib import Path

DOSSIER_PATH = Path(__file__).parent.parent / "content/dossiers/national-fraud-enforcement-division.json"

CURATION = {
    "key_finding_ids": [6619, 6546, 6621, 6622, 6623, 6627, 6620, 6624],
    "key_identifiers": {
        "jurisdictions": ["DC", "MN"],
        "officers": [
            {
                "role": "Nominated AAG / Division Head",
                "entity": "National Fraud Enforcement Division",
                "start": "2026-01-28",
                "end": None,
            }
        ],
        "entities": [
            {
                "id": None,
                "name": "Weaponization Working Group",
                "type": "government",
                "jurisdiction": "DC",
                "role": "Coordinating body co-chaired by nominated AAG Colin McDonald",
            }
        ],
    },
    "lead": (
        "<p>The National Fraud Enforcement Division (NFED) was created by a White House announcement on January 8, 2026 as a new DOJ division with Assistant Attorney General-level leadership. "
        "The founding White House fact sheet described its jurisdiction as fraud affecting the federal government, federally funded programs, federally funded benefits, businesses, nonprofits, and private citizens "
        "[Finding #6619]. Election fraud was not enumerated in the founding documents [Finding #6619]. "
        "On January 28, 2026, President Trump nominated Colin McDonald as the division's first AAG; McDonald's Senate confirmation hearing was held February 25, 2026 and he remained unconfirmed as of March 2026 [Finding #6620].</p>"
        "<p>At the announcement, Vice President Vance stated the incoming AAG would operate \"out of the White House, under the supervision of the president and vice president\" with \"all the benefits, resources, authority of a special counsel.\" "
        "Subsequent official documentation contradicted this description: AAG Jolene Ann Lauria's organizational chart submitted to Congress showed the division reporting to the Deputy Attorney General, and McDonald testified at his confirmation hearing that he would report to AG <a href=\"/dossiers/pam-bondi\">Pam Bondi</a> and DAG Todd Blanche [Finding #6621]. "
        "The division's relationship to existing DOJ fraud infrastructure — the Criminal Division Fraud Section, the Civil Division's False Claims Act branch, and the Public Integrity Section — was not resolved in founding documents [Finding #6623].</p>"
        "<p>The division's initial operational focus was Minnesota federal program fraud, particularly cases arising from the Feeding Our Future SNAP/nutrition fraud investigation, Housing Stabilization Services, and Medicaid. "
        "By the time of the NFED announcement, the Minnesota cases had already produced 98 defendants (85 of Somali descent), 64 convictions, more than 1,750 subpoenas, and more than 130 search warrants [Finding #6619]. "
        "Vance indicated the division would expand from Minnesota to Ohio and California.</p>"
    ),
    "system_role": (
        "The NFED is a mechanism for concentrating federal fraud prosecution authority in a new White House-adjacent division while the existing DOJ unit historically responsible for election-related crimes — "
        "the Public Integrity Section's Election Crimes Branch — is simultaneously reduced from 35–36 attorneys to 2–5 and stripped of authority to file new cases. "
        "The structural result is a transfer of potential election fraud jurisdiction from a career-staffed unit operating under traditional DOJ independence norms to a new division whose leadership publicly auditioned loyalty to the administration's \"weaponization\" narrative."
    ),
    "sections": [
        {
            "id": "founding-and-jurisdiction",
            "title": "Founding, Jurisdiction, and Reporting Structure",
            "content": (
                "<p>The NFED was announced on January 8, 2026 alongside a White House fact sheet characterizing the division as targeting \"fraud affecting the federal government and federally funded programs\" and placing an AAG at its head [Finding #6619]. "
                "The announcement did not enumerate election fraud, vote fraud, or election administration as covered conduct. "
                "DOJ's existing Civil Division Commercial Litigation Branch enforces the False Claims Act; the Criminal Division Fraud Section handles federal program fraud; and the Public Integrity Section's Election Crimes Branch has historically handled election-related federal crimes. "
                "No White House or DOJ document released at founding explained how NFED jurisdiction would be delineated from any of these existing units [Finding #6623].</p>"
                "<p>The chain of command announced by Vance — direct White House supervision with special counsel-equivalent authority — has no structural precedent for a permanent DOJ division. "
                "A DOJ Assistant Attorney General is a Senate-confirmed officer who serves within the department's chain of command under the AG and DAG; investment of that office with White House supervisory authority would dissolve the institutional separation between the White House and federal prosecutorial decisions. "
                "The subsequent org chart and McDonald's testimony both placed the division within the normal DOJ hierarchy under the AG and DAG, leaving unresolved whether Vance's characterization reflected intent, misstatement, or a distinction between formal structure and operational direction [Finding #6621].</p>"
                "<p>The administration's public position at founding was that no new funding or attorneys would be required — NFED would be staffed by existing DOJ personnel. "
                "However, Criminal Division AAG Tysen Duva told a bar association audience that the division would hire its own staff once an AAG was confirmed. "
                "This contrasts with the no-new-resources framing and with the fact that DOJ had already lost approximately 8 percent of its workforce in 2025, while simultaneously doubling its attorney roster on the Minnesota fraud cases that became the NFED's flagship matter [Finding #6622].</p>"
            ),
            "viz": "timeline",
        },
        {
            "id": "colin-mcdonald-profile",
            "title": "Colin McDonald: Nominated AAG",
            "content": (
                "<p>Colin Michael McDonald (California Bar #286561; California Western School of Law) spent eleven years as an AUSA in the Southern District of California from 2014 to 2025, working federal fraud, money laundering, and tax crime prosecutions. "
                "He served as Deputy Chief of the Border Enforcement Section, Civil Enforcement Opioid Coordinator, and as a Special Attorney in the District of Hawaii, where he prosecuted Honolulu Police Chief Louis Kealoha on federal corruption charges. "
                "In 2025 he moved to Washington as Associate Deputy Attorney General under Todd Blanche [Finding #6620].</p>"
                "<p>In that role McDonald co-chaired the Weaponization Working Group established by AG Bondi on February 5, 2025. "
                "The group was led by <a href=\"/dossiers/ed-martin\">Ed Martin</a> — then serving simultaneously as interim U.S. Attorney for DC and later as U.S. Pardon Attorney — and was tasked with reviewing the Jack Smith prosecutions of Trump, January 6 prosecutions, anti-abortion protester prosecutions, and FBI actions. "
                "The group also employed Jared Wise, a pardoned January 6 defendant who was filmed telling Capitol Police officers \"kill them\" during the riot, as a senior advisor and investigator to Martin [Finding #6624].</p>"
                "<p>At his February 25, 2026 confirmation hearing, Senate Democrats questioned McDonald's WWG role. "
                "McDonald testified that Trump was right to \"identify the threat of weaponization in the federal government\" and declined to address Wise's hiring [Finding #6624]. "
                "McDonald's confirmation remained pending as of March 2026 [Finding #6620].</p>"
            ),
            "viz": None,
        },
        {
            "id": "overlap-with-existing-components",
            "title": "Overlap With Existing DOJ Fraud and Election Crime Infrastructure",
            "content": (
                "<p>The creation of a new AAG-level fraud division without resolving its relationship to existing components left three structural questions open. "
                "First, whether the Criminal Division Fraud Section — which has historically prosecuted federal program fraud — would be absorbed by, subordinated to, or left parallel to NFED. "
                "Second, whether the Civil Division's False Claims Act enforcement would be coordinated through NFED or remain operationally independent. "
                "Third, and most analytically consequential, whether NFED would become the default venue for election fraud cases as the Public Integrity Section's capacity atrophied [Finding #6623].</p>"
                "<p>The Public Integrity Section (PIN), which houses the Election Crimes Branch — the traditional federal unit for election fraud enforcement — was reduced from 35–36 attorneys to approximately 2–5 over the same period NFED was created. "
                "The remaining PIN staff were stripped of authority to file new cases or consult on Congressional cases. "
                "The Election Crimes Branch's operational capacity was, by early 2026, effectively suspended [Finding #6623].</p>"
                "<p>In parallel, the Civil Rights Division under AAG <a href=\"/dossiers/harmeet-dhillon\">Harmeet Dhillon</a> was demanding Minnesota voter rolls and same-day registration records [Finding #6627]. "
                "Vance publicly stated NFED's Minnesota focus would expand to Ohio and California. "
                "Both Ohio and California had been targeted in DOJ's voter roll litigation campaign [Finding #6619]. "
                "The factual record does not establish that NFED was designed to absorb election fraud jurisdiction, but the combination of PIN atrophy and NFED's nationwide fraud mandate with White House adjacency describes the institutional conditions under which such an absorption could occur without a formal policy decision [Finding #6627].</p>"
            ),
            "viz": None,
        },
        {
            "id": "minnesota-focus",
            "title": "The Minnesota Focus: Federal Program Fraud Cases",
            "content": (
                "<p>The cases cited to justify the NFED's founding were rooted in a pre-existing federal investigation: the Feeding Our Future fraud, in which a nonprofit's SNAP and child nutrition program was used to siphon tens of millions of dollars in federal program funds. "
                "By January 8, 2026, the Minnesota prosecutions had produced 98 charged defendants, of whom 85 were of Somali descent, with 64 convictions, over 1,750 subpoenas served, and more than 130 search warrants executed [Finding #6619]. "
                "These prosecutions predated NFED and were conducted by the U.S. Attorney's Office for the District of Minnesota.</p>"
                "<p>The NFED announcement attributed credit for these cases to the new division while simultaneously treating them as the template for its nationwide mandate — \"fraud affecting federal programs\" including SNAP, housing, education, and Medicaid. "
                "DOJ simultaneously doubled its attorney staffing in Minnesota on fraud cases, in apparent tension with the stated no-new-resources position [Finding #6622].</p>"
                "<p>The announcement's focus on Minnesota, combined with the contemporaneous Civil Rights Division voter roll demands against Minnesota and AG <a href=\"/dossiers/pam-bondi\">Bondi</a>'s January 25, 2026 letter to Governor Walz — which federal judges characterized as \"blackmail\" in the context of linking ICE enforcement to voter data compliance — placed federal fraud and election enforcement activity in Minnesota within the same operational window. "
                "Whether that convergence was coordinated or sequential is not established in the present record [Connection #3298].</p>"
            ),
            "viz": None,
        },
        {
            "id": "network-context",
            "title": "Network Context: DOJ Enforcement Architecture",
            "content": (
                "<p>NFED sits at one node of a broader reorganization of DOJ enforcement that, between January 2025 and March 2026, included: creation of the Weaponization Working Group under <a href=\"/dossiers/ed-martin\">Ed Martin</a> (February 2025); gutting of the Civil Rights Division Voting Section and its reconstitution with personnel from PILF, True the Vote, and fake-electors litigation networks; "
                "a multi-wave voter roll litigation campaign against 29 states; the DOJ-DHS SAVE bulk voter roll data-sharing pipeline; and White House coordination on election enforcement meetings directed by Deputy Chief of Staff <a href=\"/dossiers/stephen-miller\">Stephen Miller</a> [Finding #6527].</p>"
                "<p>McDonald's co-chairmanship of the Weaponization Working Group — whose mandate explicitly covered review of federal prosecutions of Trump and his allies and whose staff included a pardoned January 6 participant — provides the direct personnel link between the administration's retributive prosecution review and the nominee to lead the new fraud division [Finding #6624]. "
                "The DOJ reported quarterly to the White House on the WWG's progress [Finding #6574].</p>"
                "<p><a href=\"/dossiers/pam-bondi\">Pam Bondi</a>'s connection to NFED is both structural (as AG, she is McDonald's nominal superior under the organizational chart) and thematic: her voter roll campaign targeted Minnesota — the same state NFED selected as its founding case jurisdiction — and both programs deploy federal fraud authority as the operative legal theory for demanding state election data [Connection #3298].</p>"
            ),
            "viz": "ego_network",
        },
    ],
    "open_questions": [
        "Has Colin McDonald been confirmed as AAG for NFED, and if so, what cases has the division filed independently of pre-existing Minnesota U.S. Attorney prosecutions?",
        "What formal jurisdictional boundaries, if any, have been established between NFED and the Criminal Division Fraud Section, and has the Public Integrity Section's Election Crimes Branch been formally dissolved or merely defunded?",
        "Has NFED received any formal grant of authority over election fraud cases, either by executive order, AG memorandum, or informal direction from the White House, and has it filed or assumed any election-related cases?",
        "What is the relationship between NFED's Minnesota focus and the Civil Rights Division's concurrent voter roll litigation and data demands targeting Minnesota — was there coordination, sequencing, or coincidence?",
        "What communications between the White House and NFED leadership (Vance's office, Miller's office, or the AG's office) have directed the division's case priorities or geographic expansion to Ohio and California?",
        "Has Jared Wise, who served as senior advisor to WWG chair Ed Martin, had any role in NFED work product or case referrals, given McDonald's co-chairmanship of the WWG?",
    ],
    "applicable_models": [
        "narrative-shield",
        "regulatory-capture",
        "private-order",
    ],
    "curated_at": datetime.datetime.utcnow().isoformat(),
}


def main():
    with open(DOSSIER_PATH) as f:
        dossier = json.load(f)

    dossier["curation"] = CURATION

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  Lead length: {len(CURATION['lead'])} chars")
    print(f"  Sections: {[s['id'] for s in CURATION['sections']]}")
    print(f"  Open questions: {len(CURATION['open_questions'])}")
    print(f"  Applicable models: {CURATION['applicable_models']}")


if __name__ == "__main__":
    main()
