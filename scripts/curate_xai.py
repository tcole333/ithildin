#!/usr/bin/env python3
"""Curation script for xAI dossier."""
import json
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/xai.json")

curation = {
    "lead": (
        "<p>xAI Corp, incorporated in Nevada and headquartered at 1450 Page Mill Road, Palo Alto, California, "
        "was founded by Elon Musk in 2023 to compete directly with OpenAI and Anthropic. Within thirty months "
        "of incorporation it had raised $12 billion across two rounds — a $6 billion Series B in May 2024 and "
        "a $6 billion Series C in December 2024 — from investors including a16z, Sequoia, Fidelity, BlackRock, "
        "Lightspeed, Qatar Investment Authority, Nvidia, AMD, and Saudi Prince Alwaleed's Kingdom Holding "
        "[Finding #5349]. A parallel network of small SPV fund vehicles managed by Sydecar LLC filed five "
        "additional Form D offerings between June 2024 and February 2026, all registered to a Claymont, "
        "Delaware registered-agent address, none identifying xAI Corp itself as a registered SEC entity "
        "[Finding #5615].</p>"
        "<p>In July 2025, the Pentagon awarded a contract worth up to $200 million to AIQ Phase LLC — a Wyoming "
        "entity registered at xAI's Palo Alto office address, incorporated May 2024 and activated in SAM.gov "
        "on November 6, 2025, two weeks before the award announcement — for integration of xAI's Grok model "
        "across approximately three million military and civilian DoD personnel [Finding #5934] [Finding #5298]. "
        "By February 2026 xAI had secured access to classified Pentagon systems, replacing Anthropic's Claude, "
        "which had held that position but lost it after refusing a Pentagon demand to make its model available "
        "for 'all lawful purposes,' a standard that specifically covers mass surveillance of Americans and "
        "development of fully autonomous weapons [Finding #5346].</p>"
        "<p>SpaceX acquired xAI on February 2, 2026 in an all-stock transaction that set the combined "
        "valuation at $1.25 trillion, using X.AI Holdings Corp — a Nevada merger vehicle with Jared Birchall "
        "as Corporate Secretary — as the structural vehicle [Finding #5301] [Finding #5560]. The Colossus "
        "supercomputer facility in Memphis, Tennessee, which began Phase 1 with 100,000 Nvidia H100 GPUs "
        "in 122 days and is expanding toward 555,000 GPUs at 2 gigawatts of power capacity, operates through "
        "CTC Property LLC, a Nevada entity managed by Birchall's Excession LLC family office under a "
        "21-year lease on the former Electrolux factory at 3231 Paul R. Lowry Road [Finding #4395] "
        "[Finding #5921] [Finding #6218].</p>"
    ),

    "system_role": (
        "xAI is Elon Musk's artificial intelligence operating company — the entity that develops the Grok "
        "model, operates the Colossus supercomputer facility, holds the Pentagon's classified AI contract, "
        "and served as the AI business being absorbed into SpaceX through the February 2026 all-stock merger. "
        "It is the node that connects the DOGE-era federal data access episode, the government contracting "
        "pipeline, the Musk private entity infrastructure managed by Jared Birchall, and the regulatory "
        "incapacitation sequence that preceded the merger. Amanda Scales, who managed xAI recruiting, "
        "carried xAI equity into her role as OPM Chief of Staff where she coordinated federal workforce "
        "terminations before returning to xAI — making xAI the employer on both sides of that revolving "
        "door transaction."
    ),

    "sections": [
        {
            "id": "corporate-structure",
            "title": "Corporate Structure and Capitalization",
            "content": (
                "xAI Corp is incorporated in Nevada and maintains its operational headquarters at "
                "1450 Page Mill Road, Palo Alto, California. It is not itself a registered SEC entity; "
                "the primary Form D filers in the xAI ecosystem are X.AI Corp (CIK 0002002695, four filings "
                "2023–2025) and X.AI Holdings Corp (CIK 0002079267, two filings 2025–2026), both with "
                "Jared Birchall listed as executive officer [Finding #5615] [Finding #6213]. A separate "
                "cluster of five small SPV vehicles — xAI 2 May 2024 (CIK 2026824), xAi a Series of OORI "
                "LLC (CIK 2054050), xAI 2025(1) (CIK 2080444), xAI 2025(2) (CIK 2102114, three investors), "
                "and xAI Grain Ventures Jan 2026 (CIK 2109943, eleven investors) — were administered by "
                "Sydecar LLC and registered to 2093 Philadelphia Pike, Claymont, Delaware 19703 (a "
                "registered-agent address) [Finding #5615]. These SPVs represent secondary-market and "
                "co-investment vehicles distinct from xAI's primary fundraising rounds. "
                "FEC employer-field records identify Marc Tessier-Lavigne, former Stanford president who "
                "resigned in 2023 under allegations of research misconduct, as CEO at xAI — a personnel "
                "datum that does not appear in xAI's own public disclosures [Finding #5619]. "
                "No LDA lobbying registration appears in the Senate database for xAI or X.AI despite "
                "regulatory exposure at the FTC and Commerce Department [Finding #5622]. "
                "See also: <a href='/dossiers/elon-musk'>Elon Musk</a>, "
                "<a href='/dossiers/jared-birchall'>Jared Birchall</a>, "
                "<a href='/dossiers/musk-entities'>Musk Entities</a>."
            ),
            "viz": None
        },
        {
            "id": "colossus-infrastructure",
            "title": "Colossus Supercomputer and Physical Infrastructure",
            "content": (
                "xAI's compute backbone is the Colossus facility at 3231 Paul R. Lowry Road, Memphis, "
                "Tennessee, occupying the former Electrolux factory under a 21-year lease signed through "
                "CTC Property LLC (Nevada) [Finding #5921]. Phase 1 reached 100,000 Nvidia H100 GPUs within "
                "122 days of groundbreaking. Phase 2 expanded to 200,000 GPUs by May 2025. Phase 3, with a "
                "third building purchased in January 2026, targets 555,000 GPUs at 2 gigawatts of total "
                "power capacity, requiring a purpose-built $80 million wastewater treatment center to "
                "recycle 13 million gallons per day [Finding #4395]. Nvidia GPU procurement for Colossus "
                "totals $18 billion. Ultimate plans call for 1 million GPUs. "
                "The entity operating the facility, CTC Property LLC, is a Nevada LLC managed through "
                "the Excession LLC family office; Jared Birchall's name appears in Solaris Energy "
                "Infrastructure's August 2025 SEC 10-Q filing in connection with a 900-megawatt power "
                "joint venture (Stateline Power, LLC) constructed to supply primary power to this "
                "data center campus [Finding #6218]. CTC Holding LLC, incorporated in Texas in July 2024 "
                "at the xAI headquarters address, holds the membership interest [Finding #5582]. The "
                "Southern Environmental Law Center filed a Clean Air Act notice in June 2025 regarding "
                "emissions from the Memphis facility [Finding #5921]. "
                "See also: <a href='/dossiers/jared-birchall'>Jared Birchall</a>, "
                "<a href='/dossiers/musk-entities'>Musk Entities</a>."
            ),
            "viz": None
        },
        {
            "id": "government-contracting",
            "title": "Pentagon Contract and GSA Procurement",
            "content": (
                "The primary vehicle for xAI's federal contracting is AIQ Phase LLC (UEI: KY8TXYKMJU95, "
                "CAGE: 13TH1), a Wyoming entity with its registered address at 1530 Page Mill Road, "
                "Suite 250, Palo Alto — an xAI office address. AIQ Phase was incorporated May 17, 2024, "
                "registered in SAM.gov on July 1, 2025, and activated November 6, 2025 — placing its "
                "SAM registration two weeks before the announced Pentagon contract [Finding #5934]. "
                "In July 2025, the Chief Digital and Artificial Intelligence Office (CDAO) awarded the "
                "contract, worth up to $200 million, for Grok integration across approximately three "
                "million military and civilian DoD personnel. A former defense contracting official told "
                "media that xAI had not appeared in prior contract discussions before the award "
                "[Finding #4707]. Senator Warren wrote to Defense Secretary Hegseth on September 10, "
                "2025 requesting answers on five specific questions: whether Musk discussed the contract "
                "during his DOGE tenure; whether the contract received standard government approval "
                "processes; and whether any waiver of competitive bidding requirements was obtained "
                "[Finding #5331]. The GSA separately entered a deal allowing federal agencies to "
                "purchase Grok 4 at 42 cents per query through March 2027 [Finding #4389]. "
                "Reuters reported in May 2025 that DOGE staff had spent months pushing federal agencies "
                "to adopt Grok before the formal contract was in place [Finding #5351]. "
                "See also: <a href='/dossiers/doge'>DOGE</a>, "
                "<a href='/dossiers/elon-musk'>Elon Musk</a>."
            ),
            "viz": None
        },
        {
            "id": "classified-access",
            "title": "Classified Systems Access and the Anthropic Displacement",
            "content": (
                "As of February 2026, Grok holds access to classified Pentagon systems that previously "
                "belonged exclusively to Anthropic's Claude. Anthropic lost that position after refusing "
                "the Pentagon's demand to make its model available for 'all lawful purposes' — a contractual "
                "standard that Anthropic's counsel identified as covering mass surveillance of Americans "
                "and development of fully autonomous lethal weapons systems. xAI accepted the standard "
                "[Finding #5346]. The Pentagon AI chief publicly confirmed Grok's authorization for "
                "classified networks; six of xAI's twelve co-founders had departed the company before "
                "the deal closed, with safety concerns cited in contemporaneous reporting [Finding #5298]. "
                "OpenAI and Google were separately reported to be in discussions for classified access "
                "of their own [Finding #5346]. In February 2026, SpaceX and the newly merged xAI were "
                "selected as one of a small group of competitors for the Pentagon's $100 million "
                "autonomous drone swarm competition, run by the Defense Innovation Unit and Defense "
                "Autonomous Warfare Group under US Special Operations Command [Finding #5328]. "
                "The combination of classified Grok authorization with the Colossus compute facility, "
                "the X social media platform data, and the Starshield classified satellite communications "
                "network — all consolidated under a single owner through the SpaceX merger — created a "
                "corporate configuration in which intelligence-grade satellite operations and AI inference "
                "on classified data share the same ownership chain [Finding #4702]. "
                "See also: <a href='/dossiers/spacex-xai-merger'>SpaceX-xAI Merger</a>, "
                "<a href='/dossiers/spacexstarshield'>SpaceX/Starshield</a>."
            ),
            "viz": None
        },
        {
            "id": "doge-pipeline",
            "title": "DOGE Personnel Pipeline and the Amanda Scales Revolving Door",
            "content": (
                "Amanda Scales joined xAI as Recruiting Leader in October 2024 and was appointed OPM "
                "Chief of Staff on January 20, 2025. Her OGE 278 financial disclosure lists xAI equity "
                "valued at $100 million to $250 million, an active xAI Employment Agreement, and an "
                "unvested xAI equity tranche, alongside a salary of $59,392 from OPM [Finding #5720]. "
                "As OPM Chief of Staff, Scales served as the designated point of contact coordinating "
                "all agency guidance on federal employee terminations during the 2025 workforce reduction, "
                "which resulted in approximately 352,000 federal employees departing — including 123,000 "
                "deferred resignations — the largest federal workforce reduction on record [Finding #5498] "
                "[Finding #5998]. Brian Bjelde (SpaceX VP of Human Resources) was concurrently installed "
                "at OPM, giving Musk-company employees supervisory access to OPM personnel databases "
                "containing personally identifiable information on millions of federal workers, including "
                "Social Security numbers, medical histories, and home addresses [Finding #5190]. "
                "Scales departed OPM and returned to xAI by April 2025 [Finding #5947]. Her disclosed "
                "net worth of $415,005 to $1,050,000 reflected the unvested status of her xAI equity "
                "at time of disclosure; the actual future value of that equity, contingent on vesting "
                "and the SpaceX-xAI merger, was not disclosed [Finding #5947]. The DOGE operative "
                "cohort that xAI and Tesla supplied to government agencies — Scales to OPM, Thomas Shedd "
                "(Tesla) to GSA and DOL, Nicholas Alm (Tesla) to DHS — all entered government on "
                "January 20, 2025 and all returned to their prior employers within the year [Finding #5756] "
                "[Finding #5990]. "
                "See also: <a href='/dossiers/doge'>DOGE</a>, "
                "<a href='/dossiers/elon-musk'>Elon Musk</a>."
            ),
            "viz": "ego_network"
        },
        {
            "id": "merger-and-consolidation",
            "title": "SpaceX Acquisition and Post-Merger Structure",
            "content": (
                "SpaceX completed its acquisition of xAI on February 2, 2026 through an all-stock exchange "
                "at a ratio of 0.1433 xAI shares per SpaceX share, implying a $250 billion xAI valuation "
                "and a $1 trillion SpaceX valuation, for a combined $1.25 trillion. The merger vehicle "
                "was X.AI Holdings Corp (CIK 0002079267), a Nevada entity incorporated in 2025 with "
                "Birchall as Corporate Secretary, which had raised $1.6 billion across two Form D "
                "offerings by January 2026 [Finding #5301] [Finding #5560]. Two shell corporations — "
                "X12 Inc. and X42 Inc., both Nevada, both incorporated March 27, 2025 and both dissolved "
                "the same day — appear to have served as structural transaction vehicles alongside "
                "X.AI Holdings Corp [Finding #5560]. The combined entity post-merger controls the "
                "Grok classified Pentagon contract, the Starshield NRO and military satellite "
                "infrastructure, the X social media platform, and the Colossus compute campus, alongside "
                "$14.6 billion in all-time NASA and DoD contract obligations [Finding #4702]. "
                "The FTC entered the post-merger period with a 15 percent budget cut proposed, staff "
                "dismissed from its antitrust division, and a new chair who signaled departure from "
                "aggressive antitrust enforcement — conditions established during DOGE's operational "
                "period [Finding #5499]. No challenge to the transaction has been publicly reported "
                "from FTC, CFIUS, or any other regulatory body. "
                "See also: <a href='/dossiers/spacex-xai-merger'>SpaceX-xAI Merger</a>, "
                "<a href='/dossiers/spacex'>SpaceX</a>, "
                "<a href='/dossiers/jared-birchall'>Jared Birchall</a>."
            ),
            "viz": None
        }
    ],

    "open_questions": [
        "AIQ Phase LLC was registered in SAM.gov two weeks before the Pentagon contract award — was a sole-source justification filed, and if so on what grounds?",
        "Marc Tessier-Lavigne appears in FEC records as CEO of xAI; what is his actual role and when did he join relative to his Stanford resignation in 2023?",
        "The six xAI co-founders who departed before the SpaceX merger closed: who are they, when exactly did they leave relative to the classified Grok authorization, and what have they disclosed about their reasons?",
        "Amanda Scales returned to xAI in April 2025 with unvested equity that would vest under the merger's terms; what was the ultimate realized value of that equity and was any OGE ethics review conducted before her departure?",
        "CTC Property LLC operates under a 21-year Memphis lease; who are the named lessors, what are the lease payment terms, and does the Southern Environmental Law Center Clean Air Act notice remain open?",
        "The Stateline Power LLC joint venture provides 900 MW of primary power to Colossus; who is the undisclosed counterparty in the Solaris 10-Q (the 49.9 percent JV partner with redacted address), and is that entity Musk-connected?",
        "xAI filed no LDA lobbying registrations despite the Pentagon contract and GSA procurement deal — did xAI use any intermediary lobbyists or consulting firms to advance these government relationships?",
        "What security clearance determinations were made for xAI personnel who administer the classified Pentagon Grok deployment, and on what timeline relative to the July 2025 contract award?",
        "Senator Warren's September 2025 letter demanded answers on five specific questions; what, if any, response did the Pentagon provide, and did any congressional committee open a formal inquiry?",
        "The xAI drone swarm competition (February 2026) was run by a newly formed Defense Autonomous Warfare Group; what is that group's authorizing directive and what are the terms of the $100M competition?"
    ],

    "applicable_models": [
        {
            "name": "Government Data Access Preceding Commercial Deployment",
            "description": (
                "DOGE operatives with xAI affiliations gained access to federal personnel databases, Treasury "
                "payment systems, and IRS data in February through April 2025. DOGE staff then spent months "
                "pushing agencies to adopt Grok before a formal contract existed. The Pentagon contract "
                "followed in July 2025, and classified access followed in February 2026. The sequence — "
                "data access, informal adoption pressure, formal contract, classified authorization — "
                "describes a funnel in which government relationships established through the DOGE role "
                "preceded and may have enabled the commercial contract awards."
            )
        },
        {
            "name": "Revolving Door With Equity Retention",
            "description": (
                "Amanda Scales entered OPM with active xAI equity, an active xAI Employment Agreement, "
                "and a pending unvested equity tranche. She coordinated the largest federal workforce "
                "reduction in recorded history and returned to xAI within three months. The structure — "
                "in which a government official retains financial interest in and contractual ties to a "
                "private employer while executing government policy that affects that employer's "
                "competitive environment — is the pattern repeated across multiple DOGE placements, "
                "but is most clearly documented in Scales's OGE 278 disclosure."
            )
        },
        {
            "name": "SPV Fragmentation of a Single Operating Business",
            "description": (
                "xAI's capital structure runs through at least seven distinct legal entities: the "
                "operating company (X.AI Corp), the merger vehicle (X.AI Holdings Corp), the debt "
                "issuance vehicle (X.AI Co Issuer Corp), the government contracting subsidiary "
                "(AIQ Phase LLC), the Memphis real estate operator (CTC Property LLC), the Memphis "
                "real estate holding company (CTC Holding LLC), and five Sydecar-administered SPVs "
                "for secondary investors. This fragmentation distributes liabilities and disclosure "
                "obligations across jurisdictions (Nevada, Wyoming, Texas, California) and prevents "
                "any single public filing from presenting a consolidated view of xAI's assets, "
                "revenues, or exposures."
            )
        },
        {
            "name": "Ethics Guardrail Removal as Competitive Differentiator",
            "description": (
                "Anthropic's Claude held classified Pentagon AI access and lost it specifically because "
                "Anthropic refused to permit use cases covering mass surveillance and autonomous weapons. "
                "xAI accepted those terms and displaced Anthropic. This is a documented instance in which "
                "the removal of internal policy constraints became the differentiating factor in a "
                "government contract competition — a dynamic with implications for how AI safety policies "
                "interact with federal procurement incentives."
            )
        }
    ]
}

with open(DOSSIER_PATH) as f:
    dossier = json.load(f)

dossier["curation"].update(curation)

with open(DOSSIER_PATH, "w") as f:
    json.dump(dossier, f, indent=2)

print(f"Wrote curation to {DOSSIER_PATH}")
print(f"  lead: {len(curation['lead'])} chars")
print(f"  sections: {len(curation['sections'])}")
print(f"  open_questions: {len(curation['open_questions'])}")
print(f"  applicable_models: {len(curation['applicable_models'])}")
