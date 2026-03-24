#!/usr/bin/env python3
"""
Curate dossier: Musk Entities
Writes lead, system_role, sections, open_questions, applicable_models
into content/dossiers/musk-entities.json
"""

import json
from datetime import datetime, timezone
from pathlib import Path

DOSSIER_PATH = Path(__file__).parent.parent / "content/dossiers/musk-entities.json"

LEAD = (
    "<p>The \"Musk Entities\" designation covers the full constellation of operating companies, "
    "holding structures, and political-spending vehicles under Elon Musk's direct or indirect "
    "control — including Space Exploration Technologies Corp. (SpaceX), Tesla Inc., "
    "The Boring Company, X Corp. / X Holdings Corp., X.AI Corp. (xAI), Neuralink Corp., "
    "and the Excession LLC family office managed by Jared Birchall at PO Box 341886, "
    "Austin TX [Finding #6238]. The cluster holds $19 billion or more in active federal "
    "contracts [Finding #5620], has embedded at least 38 current or former employees across "
    "federal agencies as Special Government Employees through the Department of Government "
    "Efficiency [Finding #5956], and in February 2026 announced the merger of SpaceX and xAI "
    "at a combined valuation of $1.25 trillion [Finding #5301].</p>"
    "<p>The corporate structure is two-tiered. Musk appears directly on public company filings "
    "(Tesla, SpaceX, X Corp., xAI) while Birchall serves as executive officer or director on "
    "90-plus private entities spanning 15 jurisdictions [Finding #6238]. The day-to-day "
    "family office (Excession LLC), the private security firm (Foundation Security Inc.), "
    "the political payment conduit (Europa 100 LLC), and the venture vehicles "
    "(Red Planet Ventures I, II, III) were all formed on or shortly after July 14, 2020, "
    "coinciding with Musk's relocation from California to Texas [Finding #5567]. Seven "
    "additional entities were formed during Musk's DOGE tenure in 2025, including "
    "the xAI debt-issuance vehicle (X.AI Co Issuer Corp.), the Memphis data-center "
    "holding entity (CTC Holding LLC), and the Pentagon contracting subsidiary "
    "(AIQ Phase LLC) [Finding #5582].</p>"
    "<p>No Musk entity or officer appears in the FARA database, no Birchall-network "
    "private entity has federal contract awards, and none is excluded or debarred "
    "in SAM.gov [Finding #5614; Finding #5592]. Federal revenue flows almost entirely "
    "through SpaceX; Tesla has no active federal contracts, and The Boring Company has "
    "none [Finding #4560].</p>"
)

SYSTEM_ROLE = (
    "The Musk Entities cluster occupies a structural position in which a single beneficial "
    "owner simultaneously holds the largest private contract portfolio in the U.S. national "
    "security supply chain, operates a 90-plus entity private corporate network managed "
    "through a single wealth manager, runs a super PAC that disbursed $363 million in a "
    "single election cycle, and directed a federal workforce-reduction program that targeted "
    "every regulatory agency with jurisdiction over his companies. That combination — "
    "contractor, regulator-selector, and campaign funder operating through the same "
    "individual — is the structural position the cluster occupies, distinct from any "
    "individual company's role."
)

SECTIONS = [
    {
        "id": "corporate-architecture",
        "title": "Corporate Architecture and the Birchall Layer",
        "prose": (
            "<p>The Musk corporate network is organized in two tiers. On the first tier, "
            "Musk appears as named officer on the public-facing operating companies: Tesla "
            "Inc. (redomiciled to Texas, TX SOS #0805587591, effective June 14, 2024 "
            "[Finding #5874]), SpaceX (Space Exploration Technologies Corp., SAM UEI "
            "C6M7C2FLKER5 with six separate facility registrations [Finding #5594]), "
            "X Corp. and X Holdings Corp. (NV, all four officer positions held by Musk "
            "[Finding #5560]), and X.AI Corp. (TX operative, NV incorporated, forfeited "
            "TX status, president listed as Jared Birchall [Finding #5882]).</p>"
            "<p>On the second tier, Birchall — Musk's personal wealth manager and head "
            "of Excession LLC — holds officer or director positions at 90-plus entities "
            "across 15 U.S. jurisdictions plus the UK [Finding #6238]. This tier includes "
            "the family office (Excession LLC, TX SOS #0803683059), the private security "
            "company (Foundation Security Inc., TX SOS #0803683041), the political "
            "payments entity (Europa 100 LLC, TX SOS #0803683010), and Musk Industries LLC "
            "(TX SOS #0803683028) — all four formed on the same day with near-sequential "
            "company numbers [Finding #5562]. Birchall is also listed as Executive Officer "
            "on SEC Form D filings for Neuralink, The Boring Company, X.AI Corp., and "
            "X.AI Holdings Corp., and as Director of X.AI London Ltd. "
            "(UK company 16131916, formed December 2024) [Finding #6213; Finding #6235].</p>"
            "<p>The Musk Revocable Trust (dated July 22, 2003) holds 413 million Tesla "
            "shares and appears as an America PAC donor and as owner of the terminated "
            "Neurotek LLC [Finding #5880]. Asset control thus splits between the Revocable "
            "Trust for personal equity and the Birchall-managed Excession cluster for "
            "operational and political entities [Finding #5892].</p>"
            "<p>During the DOGE period, at least seven new entities formed: Red Planet "
            "Ventures I, II, and III (February 25, 2025, investment fund architecture, "
            "no SEC Form D filed in 13 months [Finding #6239]), X.AI Holdings Corp. "
            "(NV, Merge Dissolved as SpaceX-xAI merger closed), X.AI Co Issuer Corp. "
            "(NV, debt-issuance vehicle), CTC Holding LLC (xAI Memphis data-center "
            "property), and AIQ Phase LLC (Pentagon contracting subsidiary, "
            "SAM UEI KY8TXYKMJU95, registered July 1, 2025 — two weeks before the "
            "$200M Pentagon CDAO contract award [Finding #5934]) [Finding #5582].</p>"
        ),
        "cross_links": [
            {"slug": "jared-birchall", "label": "Jared Birchall"},
            {"slug": "elon-musk", "label": "Elon Musk"},
        ],
        "finding_ids": [5560, 5562, 5564, 5567, 5574, 5582, 5592, 5594, 5614, 5874,
                        5880, 5882, 5884, 5888, 5892, 6213, 6235, 6238, 6239],
    },
    {
        "id": "federal-contracts",
        "title": "Federal Contract Portfolio",
        "prose": (
            "<p>Across the Musk entity cluster, federal contract obligations exceed "
            "$19 billion. SpaceX accounts for the dominant share: $11.2 billion from NASA "
            "(CRS-1 $1.6B, CRS-2 $3.2B, Commercial Crew $3.5B, HLS/Starship $2.9B), "
            "$3.7 billion from DoD and Space Force, and $0.5 billion or more from "
            "intelligence community contracts. Starlink/Starshield holds $2.1 billion in "
            "DoD and FCC awards. The figures previously attributed to Tesla ($1.2B) and "
            "The Boring Company ($350M) in aggregate reporting derive largely from unrelated "
            "companies sharing those names: Tesla Inc. (Musk's company) has a single "
            "federal purchase on record — a $1,373 vehicle purchase in 2015 — and no "
            "active federal contracts; The Boring Company likewise has zero federal "
            "contract awards [Finding #4560; Finding #5588]. Federal revenue flows "
            "through SpaceX exclusively.</p>"
            "<p>SpaceX maintains six separate SAM.gov registrations for its facilities "
            "(Hawthorne CA, Washington DC, Boca Chica TX, Redmond WA, McGregor TX, "
            "Vandenberg AFB CA), each with its own UEI and CAGE code [Finding #5594]. "
            "The single largest contract is the NASA Commercial Crew Program "
            "(NNK17MA01T, $3.03B, 2016–2030). The NSSL Phase 3 Lane 2 award of "
            "$5.9 billion from Space Force on April 4, 2025, is the largest single "
            "post-inauguration award [Finding #5293]. DoD awards since January 20, 2025, "
            "total $1.01 billion, compared with $382 million for all of FY2024 — "
            "a nearly threefold quarterly acceleration [Finding #5586].</p>"
            "<p>xAI entered federal contracting through AIQ Phase LLC, which was registered "
            "in SAM.gov two weeks before the $200 million Pentagon CDAO contract for Grok "
            "AI integration into military systems, including classified access "
            "[Finding #5934; Finding #5298]. In February 2026, SpaceX and xAI entered "
            "an autonomous drone swarm competition worth up to $100 million "
            "[Finding #5328]. The White House Communications Agency procured Starlink "
            "Mobile Priority Service through GSA contract vehicle 47QRAA21D007N "
            "($241,814, 2025–2026), placing SpaceX inside the White House communications "
            "infrastructure during Musk's DOGE tenure [Finding #5072].</p>"
            "<p>The proposed Golden Dome missile defense program represents the largest "
            "prospective contract exposure. SpaceX, Anduril, and "
            "<a href=\"/dossiers/palantir-technologies\">Palantir</a> formed a consortium "
            "proposing 400–1,000 tracking satellites plus 200 attack satellites with "
            "lasers and missiles, with SpaceX as prime integrator for a proposed "
            "subscription model under which the government pays for access rather than "
            "ownership [Finding #4722]. A $2 billion AMTI line item for SpaceX was "
            "confirmed held by OMB as of February 2026 [Finding #4961]. The $37.8 billion "
            "appropriated for Golden Dome includes lines directly relevant to SpaceX "
            "satellite constellation work [Finding #4716].</p>"
            "<p>The Boring Company received $822,395 in PPP loans across two forgiven "
            "loans from Zions Bank in 2020–2021, at a time when its Las Vegas tunnel "
            "contract had already been awarded for $52.5 million and the company had "
            "raised approximately $120 million in venture capital at a roughly $920 million "
            "valuation [Finding #5590; Finding #5595].</p>"
        ),
        "cross_links": [
            {"slug": "spacex", "label": "SpaceX"},
            {"slug": "xai", "label": "xAI"},
            {"slug": "spacex-xai-merger", "label": "SpaceX-xAI Merger"},
            {"slug": "palantir-technologies", "label": "Palantir Technologies"},
            {"slug": "anduril-industries", "label": "Anduril Industries"},
        ],
        "finding_ids": [4560, 4716, 4722, 4961, 5072, 5293, 5298, 5301, 5328, 5374,
                        5586, 5588, 5590, 5594, 5595, 5620, 5934],
    },
    {
        "id": "doge-personnel-and-conflicts",
        "title": "DOGE Personnel Pipeline and Regulatory Conflicts",
        "prose": (
            "<p>At least 38 of the 109 identified DOGE staffers worked for Musk companies "
            "before their federal assignments, with 35 or more coming from SpaceX, Tesla, "
            "X, Neuralink, or The Boring Company [Finding #5956]. The cluster pattern is "
            "documented: four active SpaceX engineers (Brady Glantz, Thomas Kiernan, "
            "Ted Malaska, Sam Smeal) were embedded at the FAA — the agency that issues "
            "SpaceX launch licenses and had proposed $633,000 in fines for violations "
            "[Finding #5525]. Six Musk-company employees occupied OPM, which controls "
            "federal hiring and firing: Brian Bjelde (SpaceX VP People Operations), "
            "Riccardo Biasini (Tesla/Boring), Stephen Duarte (SpaceX HR), Christina Hanna "
            "(SpaceX HR), Bryanne-Michelle Mlodzianowski (SpaceX HR director), and "
            "Joe Gebbia (Tesla board) [Finding #5526].</p>"
            "<p>The February 2025 regulatory timeline is documented across three Musk "
            "companies: FAA laid off 332 employees on February 14; Starlink was installed "
            "at GSA without completing procurement authorization on February 15; FDA "
            "neurological device reviewers — including staff who worked directly on "
            "Neuralink clinical trial applications — were fired on February 17 "
            "[Finding #6514]. The NLRB lost quorum in 2025 after Trump removed board "
            "members, and on February 9, 2026, formally dismissed its unfair labor "
            "practice complaint against SpaceX for firing eight engineers who wrote an "
            "open letter critical of Musk [Finding #5475]. NHTSA fired approximately "
            "30 staff including 43 percent of the AV safety team, which had eight active "
            "Tesla investigations, including Autopilot crash probes [Finding #5455].</p>"
            "<p>FCC Chair Brendan Carr approved 7,500 additional Starlink Gen2 satellites "
            "(bringing the authorized fleet to 15,000), opened 20,000 MHz of spectrum for "
            "satellite broadband, and reversed a Biden-era clawback of approximately "
            "$1 billion in subsidies from Starlink. He also advocated redirecting "
            "$42.5 billion in BEAD broadband infrastructure subsidies toward Starlink "
            "[Finding #5460]. The SpaceX-xAI merger announcement in February 2026 came "
            "after FTC enforcement capacity had been reduced by roughly 15 percent and "
            "its leadership replaced with an enforcement-averse chair; the FTC was "
            "considered unlikely to challenge the deal [Finding #5470].</p>"
            "<p>Thomas Shedd (former Tesla mechanical engineer and software developer, "
            "eight years at the company) was appointed GSA TTS Director in January 2025 "
            "while on unpaid leave from Tesla — an arrangement ethics experts described "
            "as \"unheard of\" [Finding #6499]. He subsequently served simultaneously as "
            "DOL Acting CIO with oversight authority over OSHA, which had active Tesla "
            "investigations, while retaining Tesla stock options [Finding #5949]. "
            "<a href=\"/dossiers/doge\">DOGE</a> leadership was concentrated in Musk-company "
            "alumni: Shedd (Tesla), Amanda Scales (xAI, $100M–$250M in xAI stock "
            "[Finding #5720]), Riccardo Biasini (Tesla/Boring), with Steve Davis "
            "(Boring Company CEO) running daily operations from the GSA commissioner "
            "suite before hitting the 130-day SGE limit [Finding #5487].</p>"
        ),
        "cross_links": [
            {"slug": "doge", "label": "Department of Government Efficiency (DOGE)"},
            {"slug": "spacex", "label": "SpaceX"},
        ],
        "finding_ids": [5193, 5293, 5455, 5457, 5460, 5462, 5467, 5470, 5475, 5487,
                        5499, 5509, 5510, 5524, 5525, 5526, 5527, 5528, 5535, 5536,
                        5543, 5544, 5552, 5621, 5709, 5714, 5715, 5720, 5725, 5728,
                        5729, 5732, 5741, 5744, 5949, 5956, 6435, 6499, 6514],
    },
    {
        "id": "political-spending-structure",
        "title": "Political Spending Structure",
        "prose": (
            "<p>America PAC (C00879510), founded May 22, 2024, with Chris Young as "
            "treasurer, raised $239.5 million in the 2024 cycle and disbursed $236.3 "
            "million, including $157.3 million in independent expenditures supporting "
            "Trump and opposing Harris [Finding #5601]. Elon Musk contributed $295.1 "
            "million to America PAC directly, making his total trackable political giving "
            "$363.5 million — far exceeding that of any other actor in the defense tech "
            "ecosystem [Finding #5384].</p>"
            "<p>The donor architecture routes through Musk-controlled entities. Excession "
            "LLC made an in-kind contribution of $6,324 to America PAC and received a "
            "$6,324 in-kind disbursement back from the PAC; the Elon Musk Revocable Trust "
            "donated $4,425 and received the same amount back as an in-kind disbursement. "
            "United States of America Inc. (TX SOS #0805733050, incorporated October 2, "
            "2024 — a month before the election, with Musk as sole director) contributed "
            "$15.9 million to America PAC across 12 transactions and received $5.3 million "
            "in in-kind flows back [Finding #5607; Finding #5559]. Group America LLC and "
            "Europa 100 LLC also appear as donors [Finding #5607].</p>"
            "<p>Chris Young held three simultaneous roles: America PAC treasurer, "
            "approximately $1 million per year in salary from Europa 100 LLC (a Birchall-"
            "managed entity at PO Box 341886), and DOGE senior advisor at the Consumer "
            "Financial Protection Bureau [Finding #5554]. Europa 100 was originally used "
            "to pay household staff before being repurposed in 2024 to pay a political "
            "operative.</p>"
            "<p>Despite managing what public filings indicate is $250 billion or more in "
            "Musk assets, Birchall himself has zero FEC contribution records [Finding #5901]. "
            "SpaceX employee FEC donations total approximately $4,966 across 15 donors — "
            "a low figure for a 13,000-plus employee company [Finding #5074].</p>"
            "<p>No lobbying registrations exist for The Boring Company, Neuralink, xAI, "
            "Starlink (as a distinct entity), Excession LLC, the Musk Foundation, or "
            "America PAC in the LDA database [Finding #5622]. Tesla has registered lobbying "
            "expenditures of $750,000 in 2024 and $1.57 million in 2025, focused on "
            "Energy, Transportation, and Taxation [Finding #5604]. SpaceX uses an outside "
            "firm (Squire Patton Boggs, including former Sen. John Breaux) but this "
            "arrangement predates DOGE [Finding #5341].</p>"
        ),
        "cross_links": [
            {"slug": "america-pac", "label": "America PAC"},
            {"slug": "elon-musk", "label": "Elon Musk"},
        ],
        "finding_ids": [5074, 5341, 5384, 5554, 5559, 5599, 5600, 5601, 5602, 5603,
                        5604, 5607, 5622, 5901],
    },
    {
        "id": "xai-neuralink-and-new-ventures",
        "title": "xAI, Neuralink, and New Ventures",
        "prose": (
            "<p>xAI Corp. (X.AI Corp., TX/NV) raises capital through both direct rounds "
            "and small SPV vehicles administered by Sydecar LLC. Identified fund entities "
            "include xAI 2 May 2024 (CIK 2026824), xAi a Series of OORI LLC "
            "(CIK 2054050), xAI 2025(1) (CIK 2080444), and xAI 2025(2) (CIK 2102114, "
            "a $1.5 billion offering filed December 2025) [Finding #5615]. Investors in "
            "the Series B ($6 billion, May 2024) and Series C ($6 billion, December 2024) "
            "included Andreessen Horowitz, Sequoia, Fidelity, Saudi Prince Alwaleed's "
            "Kingdom Holding, QIA (Qatar), Nvidia, AMD, BlackRock, and Lightspeed "
            "[Finding #5349]. Marc Tessier-Lavigne — former Stanford president who "
            "resigned in 2023 amid research misconduct allegations — appears in FEC "
            "records as xAI CEO [Finding #5619].</p>"
            "<p>xAI replaced Anthropic as the Pentagon's primary AI contractor after "
            "Anthropic declined a clause permitting use for \"all lawful purposes,\" "
            "including mass surveillance and autonomous weapons [Finding #5346]. "
            "The $200 million CDAO contract for Grok integration, including classified "
            "systems access, was awarded through AIQ Phase LLC (SAM UEI KY8TXYKMJU95, "
            "CAGE 13TH1) [Finding #5934]. Senator Elizabeth Warren's September 2025 "
            "letter asked the Pentagon whether Musk had discussed the xAI contract "
            "during his DOGE tenure [Finding #5331]. SpaceX and xAI merged in February "
            "2026 at a combined $1.25 trillion valuation, consolidating $14.6 billion "
            "or more in federal contracts, the NRO satellite portfolio, and the Pentagon "
            "AI contract into one entity [Finding #4702].</p>"
            "<p>Neuralink Corp. (NV, CEO: Musk, CFO/Director: Birchall, EIN 813312960 "
            "[Finding #5884]) is registered in SAM.gov with PSC codes for R&D medical "
            "and special studies, but has zero federal contract awards [Finding #5587]. "
            "DOGE fired approximately 20 FDA employees from the Office of Neurological "
            "and Physical Medicine Devices in February 2025; some were later rehired "
            "[Finding #5320]. Four months after those firings, the FDA granted Neuralink's "
            "Blindsight device a Breakthrough Device Designation [Finding #5354]. The "
            "USDA Inspector General investigating Neuralink animal welfare violations "
            "was physically escorted from the building [Finding #5818].</p>"
            "<p>The Boring Company's Las Vegas operations accumulated over 800 "
            "environmental violations and $736,000 in fines while remaining exempt from "
            "federal oversight because no federal funding was used [Finding #5343]. "
            "River Bottoms Ranch LLC (TX SOS #0803892275), with NEURALINK CORP as member "
            "and Birchall as president, holds rural Texas real estate likely connected "
            "to Neuralink's animal testing program [Finding #5572].</p>"
        ),
        "cross_links": [
            {"slug": "xai", "label": "xAI"},
            {"slug": "spacex-xai-merger", "label": "SpaceX-xAI Merger"},
            {"slug": "andreessen-horowitz", "label": "Andreessen Horowitz"},
        ],
        "finding_ids": [4702, 5298, 5301, 5320, 5328, 5331, 5343, 5346, 5349, 5354,
                        5572, 5582, 5584, 5587, 5615, 5619, 5818, 5884, 5888, 5927,
                        5934],
    },
]

OPEN_QUESTIONS = [
    (
        "AIQ Phase LLC was registered in SAM.gov on July 1, 2025, two weeks before the "
        "$200 million Pentagon CDAO contract. What is the contracting history — "
        "specifically whether any DOGE-affiliated official was involved in the "
        "procurement decision or whether the contract originated from DOGE's "
        "pre-inauguration coordination with agencies — and has any formal conflict "
        "review been documented?"
    ),
    (
        "Red Planet Ventures I, II, and III were formed on February 25, 2025, with "
        "investment fund architecture (GP, LP, carry structure), but no SEC Form D has "
        "been filed in 13 months. Are these entities dormant, operating without required "
        "SEC filings, or have they deployed capital through undisclosed channels? "
        "What is the intended investment thesis and whether any portfolio companies "
        "overlap with federal contracts?"
    ),
    (
        "Thomas Shedd served as GSA TTS Director on unpaid leave from Tesla while "
        "simultaneously holding the DOL Acting CIO role, with authority over OSHA "
        "investigations into Tesla. What was the formal recusal mechanism, if any, "
        "and what decisions affecting Tesla were made at DOL or GSA during Shedd's "
        "tenure that have not yet been publicly examined?"
    ),
    (
        "The SpaceX-xAI merger at a $1.25 trillion valuation consolidated over "
        "$14.6 billion in federal contracts, an NRO satellite portfolio, and a "
        "Pentagon AI contract into one private entity. The FTC signaled it would not "
        "challenge the deal. Was any formal antitrust review initiated, and if not, "
        "what was the stated basis for waiving review of what would otherwise be the "
        "largest private company merger by valuation in U.S. history?"
    ),
    (
        "Neuralink is registered in SAM.gov with Birchall as government point of "
        "contact and PSC codes for R&D medical, but has zero contract awards. "
        "The DOGE cuts to the FDA neurological device review office preceded a "
        "Breakthrough Device Designation for Neuralink's Blindsight by four months. "
        "What is the formal documentation of the designation review process, and "
        "which FDA staff conducted the review given the staffing disruptions?"
    ),
    (
        "Foundation Security Inc. (three company numbers across TX and CA, with "
        "Birchall holding all officer positions) was reported by the New York Times "
        "to have conducted background investigations on Musk rivals. What is the "
        "full scope of investigations conducted by this entity, what data sources "
        "it accessed, and whether any of that activity involved federal databases "
        "accessible through DOGE placements?"
    ),
]

APPLICABLE_MODELS = [
    "regulatory-capture",
    "revolving-door",
    "manufactured-dependency",
    "procurement-capture",
    "accountability-gap",
]


def main():
    with open(DOSSIER_PATH) as f:
        dossier = json.load(f)

    curation = dossier.get("curation", {})
    curation["lead"] = LEAD
    curation["system_role"] = SYSTEM_ROLE
    curation["sections"] = SECTIONS
    curation["open_questions"] = OPEN_QUESTIONS
    curation["applicable_models"] = APPLICABLE_MODELS
    curation["curated_at"] = datetime.now(timezone.utc).isoformat()

    dossier["curation"] = curation

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2)

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  lead: {len(LEAD)} chars")
    print(f"  system_role: {len(SYSTEM_ROLE)} chars")
    print(f"  sections: {len(SECTIONS)}")
    print(f"  open_questions: {len(OPEN_QUESTIONS)}")
    print(f"  applicable_models: {APPLICABLE_MODELS}")


if __name__ == "__main__":
    main()
