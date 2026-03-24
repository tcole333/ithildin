#!/usr/bin/env python3
"""
Curate the Shield AI dossier.
Writes lead, system_role, sections, open_questions, applicable_models into
content/dossiers/shield-ai.json curation block.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

DOSSIER_PATH = Path(__file__).parent.parent / "content" / "dossiers" / "shield-ai.json"


LEAD = """\
<p>Shield AI is a privately held defense technology company founded in 2015 and incorporated in Delaware, headquartered at 600 W Broadway, Suite 250, San Diego, California (CIK 0001675769) [Finding #5087]. The company was founded by brothers Ryan Tseng (CEO) and Brandon Tseng and has grown to approximately 900 employees as of 2024, with reported revenue of roughly $200 million that year, representing 64% year-over-year growth [Finding #4607]. Its core product is Hivemind, an autonomous AI flight software stack that enables fixed-wing and rotary aircraft to operate without GPS, communications links, or human pilots [Finding #4970]. The V-BAT, a vertical-takeoff-and-landing (VTOL) unmanned aerial vehicle, is the primary hardware platform sold to government customers [Finding #5375].</p>\
<p>Shield AI holds $52.1 million in documented federal contracts across 20 active awards from the Defense Department and Department of Homeland Security combined, with the largest allocations directed toward U.S. Coast Guard shore-based V-BAT deployments ($18.2 million), Air Force autonomous systems research and development ($16.4 million), and Navy V-BAT VTOL aircraft ($7.9 million) [Finding #5375]. The company also holds a position on the $8 billion Enhanced Wide-Area Communications and Computing (EWACC) 10-year IDIQ vehicle, which provides a ceiling authority for future task orders exceeding its current obligated contract base by two orders of magnitude [Finding #4607]. Total documented federal obligations including EWACC positioning reach $72.1 million [Finding #5352].</p>\
<p>Shield AI is a portfolio company of both <a href="/dossiers/andreessen-horowitz">Andreessen Horowitz</a>'s American Dynamism fund and <a href="/dossiers/coatue-management">Coatue Management</a>, with ARK Invest also a named investor in EDGAR Form D filings [Finding #4607]. The company was valued at approximately $5.6 billion as of the last disclosed round [Finding #5370]. Five Trump administration appointees disclosed financial holdings in Shield AI in OGE 278 filings [Finding #5200]. In February 2026, Shield AI's Hivemind software was reported as the autonomous flight controller for Collaborative Combat Aircraft platforms during Operation Epic Fury, the U.S.-Israel joint strike on Iran [Finding #4719].</p>"""


SYSTEM_ROLE = (
    "Shield AI functions as the autonomous flight AI layer within the broader defense technology "
    "investment ecosystem anchored by Andreessen Horowitz and Coatue Management, converting venture "
    "capital into Pentagon and DHS procurement revenue through GPS-denied autonomous aircraft "
    "systems while maintaining a personnel and governance structure that links its board directly "
    "to those investors and creates a recurring conflict-of-interest surface as appointees holding "
    "its equity oversee the agencies awarding its contracts."
)


SECTIONS = [
    {
        "id": "corporate-structure-and-capital",
        "title": "Corporate Structure and Capital Formation",
        "viz": None,
        "content": (
            "<p>Shield AI, Inc. is incorporated in Delaware and headquartered in San Diego. "
            "Its most recent SEC EDGAR filing is a Form D/A dated January 8, 2024, disclosing a "
            "Regulation D offering with $500 million sought and $300 million sold to 21 investors "
            "as of the filing date [Finding #5087]. The board of directors identified in that filing "
            "consists of Ryan Tseng (CEO and Director), Brandon Tseng (Executive Officer and "
            "Director), Peter Levine (Director, a General Partner at "
            "<a href=\"/dossiers/andreessen-horowitz\">Andreessen Horowitz</a> leading the American "
            "Dynamism practice), Gaetano Crupi (Director), Daniel Gwak (Director), Doug Stiles "
            "Philippone (Director), and Andrew Berlin (Director) [Finding #5087]. Levine's board "
            "seat reflects the depth of the a16z relationship: Shield AI appears on the American "
            "Dynamism 50 list and is a named portfolio company in the $1.176 billion dedicated "
            "defense/national security fund that Andreessen Horowitz launched within its January "
            "2026 $15 billion raise [Finding #4705].</p>"
            "<p>Disclosed investors across Form D rounds include "
            "<a href=\"/dossiers/coatue-management\">Coatue Management</a>, "
            "<a href=\"/dossiers/andreessen-horowitz\">Andreessen Horowitz</a> (American Dynamism), "
            "and ARK Invest [Finding #4607]. Coatue's private portfolio position in Shield AI is not "
            "reflected in its quarterly 13F-HR public equity disclosures, which show zero defense "
            "prime or defense technology company holdings; the Shield AI investment exists entirely "
            "in Coatue's private portfolio alongside SpaceX, Anthropic, OpenAI, and Scale AI "
            "[Finding #5370]. The company was last publicly valued at approximately $5.6 billion "
            "[Finding #5370]. Revenue reached approximately $200 million in fiscal 2024, up 64% "
            "year-over-year [Finding #4607].</p>"
            "<p>In September 2025, Shield AI incorporated Shield AI UK Ltd (Companies House "
            "number 16696206) at C/O Womble Bond Dickinson (UK) LLP, 4 More London Riverside, "
            "London SE1 2AU. The entity had filed only three documents as of its most recent review. "
            "Directors are Kingsley Afemikhe (British national resident in the United States, "
            "appointed September 5, 2025) and Michael Yang (American, appointed September 23, 2025). "
            "No Persons of Significant Control data had been filed at time of incorporation check "
            "[Finding #4942]. The UK entity is the company's first documented Five Eyes jurisdiction "
            "footprint.</p>"
        ),
        "finding_ids": [5087, 4607, 4705, 5370, 4942],
        "connection_ids": [],
    },
    {
        "id": "federal-contracts-and-programs",
        "title": "Federal Contracts and Programs",
        "viz": None,
        "content": (
            "<p>Shield AI holds 20 documented federal contracts totaling $52.1 million in obligated "
            "value from USASpending data retrieved March 2026 [Finding #5375]. The largest block is "
            "five DHS task orders for U.S. Coast Guard shore-based V-BAT deployments totaling "
            "$18.2 million. The second-largest is a single Air Force contract (FA864920C0158, "
            "$16.4 million) for COVID-era reinforcement learning research for autonomous systems. "
            "The Navy holds a $7.9 million V-BAT VTOL aircraft contract (N0001925F0971). A Hivemind "
            "software contract ($1.83 million, FA865822CB011) and an autonomous capabilities award "
            "($4.48 million, FA228023C0008) round out the Air Force footprint [Finding #5375].</p>"
            "<p>Total federal spending across DoD and DHS stands at $65 million, split roughly "
            "evenly — $33.8 million DoD and $31.2 million DHS [Finding #4970]. This places Shield "
            "AI substantially below its peer companies in the same investor networks: Anduril at "
            "$2.32 billion, Palantir at $3.42 billion, and SpaceX at $14.6 billion in documented "
            "federal obligations [Finding #4973]. The disparity likely reflects the stage of the "
            "company's contract development and possible reliance on Other Transaction Authority "
            "and SBIR mechanisms not fully captured in the USASpending database, as well as the "
            "$8 billion EWACC IDIQ position that represents ceiling authority rather than obligated "
            "value [Finding #4607]. An Army AI aviation SBIR award of approximately $4.2 million "
            "is separately documented [Finding #4607].</p>"
            "<p>Across fiscal years, the documented DoD obligations show a pattern of accelerating "
            "engagement: FY2024 and FY2025 awards have grown relative to the earliest contracts, "
            "with FY2026 showing $3.7 million in early-year obligations [Finding #4559]. The primary "
            "programs — V-BAT VTOL UAV, Hivemind autonomous AI behaviors, and shore-based Coast Guard "
            "deployments — span three distinct mission types: maritime domain awareness, Air Force "
            "R&D pipeline, and ISR for border and port security [Finding #4559].</p>"
        ),
        "finding_ids": [5375, 4970, 4973, 4559, 4607],
        "connection_ids": [],
    },
    {
        "id": "investor-network-and-conflict-surface",
        "title": "Investor Network and Conflict-of-Interest Surface",
        "viz": None,
        "content": (
            "<p>Shield AI's investor base creates an unusually concentrated conflict-of-interest "
            "surface at the Pentagon level. Five Trump administration appointees disclosed financial "
            "holdings in Shield AI in OGE 278 public financial disclosure filings [Finding #5200]. "
            "The appointees are not individually named in the finding, but the number matches the "
            "scale of Anduril (8 appointees), SpaceX (7), and Coatue (7) — all significantly higher "
            "than traditional defense primes, where no such pattern appears [Finding #5200].</p>"
            "<p><a href=\"/dossiers/emil-michael\">Emil Michael</a>, confirmed as Under Secretary "
            "of Defense for Research and Engineering (USD R&amp;E) in May 2025 and also serving as "
            "Acting Director of the Defense Innovation Unit (DIU), served as a senior advisor at "
            "<a href=\"/dossiers/coatue-management\">Coatue Management</a> from October 2018 through "
            "his Pentagon nomination in December 2024 [Finding #5369]. During that advisory period, "
            "Coatue made its Shield AI investment. Michael committed only to the statutory 18 U.S.C. "
            "§ 208 minimum recusal upon taking office; Senator Warren requested a broader recusal "
            "scope [Finding #5369]. USD R&amp;E is the primary Pentagon advisor on technology "
            "development and prototyping — the office that oversees the programs awarding contracts "
            "to autonomous systems companies including Shield AI [Finding #4597].</p>"
            "<p><a href=\"/dossiers/coatue-management\">Coatue</a>'s private portfolio position in "
            "Shield AI sits entirely outside its 13F-HR public disclosures. Its Q4 2025 13F shows "
            "$40 billion in public equities with zero positions in defense primes, defense IT "
            "services, or Palantir [Finding #4980]. Shield AI's valuation, along with SpaceX, "
            "Anthropic, OpenAI, and Scale AI, constitutes Coatue's undisclosed defense and AI "
            "technology concentration [Finding #5370]. The CTEK vehicle — rebranded as the Coatue "
            "Innovative Strategies Fund and anchored by $1 billion from Jeff Bezos and Michael Dell "
            "— provides high-net-worth retail investors indirect access to this private portfolio, "
            "extending the alignment structure beyond institutional investors [Finding #5364].</p>"
            "<p>Scott Kupor, the <a href=\"/dossiers/andreessen-horowitz\">Andreessen Horowitz</a> "
            "managing partner who serves as director of the Office of Personnel Management under the "
            "Trump administration, disclosed net worth exceeding $182 million and remains associated "
            "with a16z's American Dynamism fund, which holds Shield AI as a portfolio company "
            "[Finding #5961]. The USD R&amp;E and OPM conflicts are distinct in character — the "
            "former involves direct technology acquisition authority, the latter involves personnel "
            "appointments — but both are held by individuals with financial ties to Shield AI's "
            "investor network [Finding #5200].</p>"
        ),
        "finding_ids": [5200, 5369, 4597, 4980, 5370, 5364, 5961],
        "connection_ids": [],
    },
    {
        "id": "lobbying-and-government-relations",
        "title": "Lobbying and Government Relations",
        "viz": None,
        "content": (
            "<p>Shield AI has filed 100 Lobbying Disclosure Act reports disclosing $6.85 million in "
            "federal lobbying expenditures between 2018 and 2024 [Finding #5079]. This total makes "
            "Shield AI the second-highest lobbying spender among the seven defense tech companies "
            "analyzed in the investigation, behind only Anduril ($7.95 million) and ahead of "
            "SpaceX, Scale AI, and Palantir. All of Shield AI's disclosed lobbying is classified "
            "as defense-focused [Finding #5084].</p>"
            "<p>In 2021, the company established in-house lobbying capacity, registering SHIELD AI "
            "as its own LDA registrant and accounting for $4.15 million of its total disclosed "
            "spend. The shift to in-house lobbying coincided with the engagement of multiple "
            "external firms in the same year: Crossroads Strategies, J.A. Green and Company, "
            "American Defense International, C. Baker Consulting, and Liz Williams [Finding #5084]. "
            "J.A. Green and Company also appears in SpaceX lobbying records [Finding #5073], "
            "reflecting the shared roster of defense-focused lobbying firms across the Silicon "
            "Valley defense technology sector.</p>"
            "<p>LDA filings list CHRIS MILLER among the lobbyists registered on Shield AI's behalf. "
            "Christopher Miller served as Acting Secretary of Defense from November 2020 through "
            "January 2021. The available evidence does not conclusively confirm the lobbyist is "
            "identical to the former Acting SecDef — verification of that identity remains an open "
            "research task — but the coincidence of name and defense focus is documented in the "
            "record [Finding #5084].</p>"
        ),
        "finding_ids": [5079, 5084, 5073],
        "connection_ids": [],
    },
    {
        "id": "operational-deployment",
        "title": "Operational Deployment: Operation Epic Fury",
        "viz": None,
        "content": (
            "<p>Operation Epic Fury, the U.S.-Israel joint strike campaign against Iran beginning "
            "February 28, 2026, was described in contemporaneous reporting as the first large-scale "
            "AI-coordinated military operation [Finding #4719]. Shield AI's Hivemind software was "
            "reported to have piloted autonomous Collaborative Combat Aircraft (CCA) platforms "
            "during the operation. Anduril's Lattice software managed drone swarms alongside LUCAS "
            "kamikaze drones, and Palantir's AIP platform provided intelligence fusion and strike "
            "direction. The three companies — all portfolio companies of overlapping Silicon Valley "
            "investors — were simultaneously fielding technology during the same operation "
            "[Finding #4719].</p>"
            "<p>The operation occurred against the backdrop of the Iran war supplemental spending "
            "discussion that began March 3, 2026, with Congressional leaders confirming emergency "
            "munitions replenishment funding would be forthcoming [Finding #5112]. Shield AI's "
            "position in a conflict producing demand for autonomous drone operations is consistent "
            "with the pre-positioning documented across the broader defense technology network — "
            "Anduril's $22 billion IVAS novation, Palantir's $10 billion Army AI contract, and the "
            "$13.4 billion FY2026 allocation for the Golden Dome program [Finding #4770]. Shield AI "
            "holds a documented position on the Golden Dome-aligned SHIELD IDIQ contract vehicle, "
            "which carries a $151 billion 10-year ceiling and was awarded to 2,100+ companies in "
            "two tranches in December 2025 [Finding #4582].</p>"
            "<p>Hivemind's reported combat use provides the company with an operational proof-of-"
            "concept that feeds directly back into future procurement decisions. The finding carries "
            "a synthesis confidence level given its basis in contemporaneous news reporting rather "
            "than official government documentation [Finding #4719].</p>"
        ),
        "finding_ids": [4719, 5112, 4770, 4582],
        "connection_ids": [],
    },
    {
        "id": "context-within-defense-tech-ecosystem",
        "title": "Position Within the Defense Technology Ecosystem",
        "viz": None,
        "content": (
            "<p>Shield AI is one of 17 defense-specific companies named on the "
            "<a href=\"/dossiers/andreessen-horowitz\">Andreessen Horowitz</a> American Dynamism 50 "
            "list for 2025, which the firm describes as 'Companies Shaping the Fight of the Future' "
            "[Finding #5319]. The list functions as a16z's forward signal of which companies it "
            "expects to benefit from defense spending. Other named defense companies on the list "
            "include Anduril Industries, Castelion (hypersonic weapons), Forterra (autonomous "
            "military vehicles), Saronic (autonomous naval vessels), and Vannevar Labs (national "
            "security AI) — nearly all of which hold positions on the SHIELD IDIQ and have received "
            "documented federal contracts [Finding #5319].</p>"
            "<p>The aggregated federal contract value flowing to a16z American Dynamism portfolio "
            "companies exceeds $23 billion when Anduril's IVAS novation is included, with Shield "
            "AI's $72.1 million in total documented contract ceiling (obligated plus EWACC position) "
            "placing it in the lower tier of the portfolio by contract value [Finding #5352]. Within "
            "the defense tech cohort tracked by this investigation, Shield AI's $65 million in "
            "obligated contracts compares to Anduril's $1.4 billion DoD and $862 million DHS, "
            "Palantir's $2.3 billion DoD, and SpaceX's $7.2 billion DoD [Finding #4973]. Legacy "
            "defense primes hold 99.3% of total DoD contract value; all new-entrant defense tech "
            "companies combined — including Shield AI — hold less than 1% [Finding #4973].</p>"
            "<p>The pattern of Coatue and a16z co-investing in the same defense technology "
            "companies (Shield AI, and through separate vehicles Anduril) while their associated "
            "personnel rotate into government positions overseeing those programs represents the "
            "central structural dynamic this dossier documents. Coatue co-led both the Anthropic "
            "$10 billion round (January 2026) and the OpenAI $110 billion round (early 2026) "
            "while its former six-year advisor Emil Michael simultaneously served as Pentagon CTO "
            "[Finding #5365] [Finding #5369]. That conflict pattern — invisible private defense "
            "holdings paired with personnel in acquisition authority roles — is the same structure "
            "in which Shield AI sits [Finding #5408].</p>"
        ),
        "finding_ids": [5319, 5352, 4973, 5365, 5369, 5408],
        "connection_ids": [],
    },
]


OPEN_QUESTIONS = [
    "Has the identity of CHRIS MILLER listed in Shield AI's LDA lobbying filings been confirmed as Christopher Miller, the former Acting Secretary of Defense (November 2020 - January 2021)? If confirmed, what recusal obligations applied or were waived?",
    "Which five Trump administration appointees disclosed Shield AI financial holdings in OGE 278 filings, and do any of them hold positions with direct authority over the DHS Coast Guard procurement programs or Air Force autonomous systems programs that are Shield AI's largest contract sources?",
    "What is the specific task order history under the $8 billion EWACC IDIQ — has Shield AI received any EWACC task orders, and if so, through what agencies and for what periods of performance?",
    "Has Shield AI UK Ltd (Companies House 16696206) filed any PSC disclosures since incorporation in September 2025, and have any UK Ministry of Defence or Five Eyes partner agency contracts been awarded to the UK entity?",
    "What are the terms of Emil Michael's 18 U.S.C. § 208 recusal with respect to Coatue portfolio companies? Does USD R&E's authority over the Defense Innovation Unit and autonomous systems R&D create procurement decisions that affect Shield AI where recusal should apply?",
    "Does Shield AI hold any classified contracts or Other Transaction Authority agreements not captured in USASpending, which would explain the gap between its reported revenue growth trajectory and its documented obligated contract base?",
]


APPLICABLE_MODELS = [
    "manufactured-dependency",
    "enabler-gradient",
    "bridge-tax",
]


def main() -> None:
    with open(DOSSIER_PATH, "r") as f:
        dossier = json.load(f)

    existing_curation = dossier.get("curation", {})

    updated_curation = {
        **existing_curation,
        "lead": LEAD,
        "system_role": SYSTEM_ROLE,
        "sections": SECTIONS,
        "open_questions": OPEN_QUESTIONS,
        "applicable_models": APPLICABLE_MODELS,
        "curated_at": datetime.now(timezone.utc).isoformat(),
    }

    dossier["curation"] = updated_curation

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  lead: {len(LEAD)} chars")
    print(f"  system_role: {len(SYSTEM_ROLE)} chars")
    print(f"  sections: {len(SECTIONS)}")
    print(f"  open_questions: {len(OPEN_QUESTIONS)}")
    print(f"  applicable_models: {APPLICABLE_MODELS}")


if __name__ == "__main__":
    main()
