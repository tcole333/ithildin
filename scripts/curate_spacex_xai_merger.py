#!/usr/bin/env python3
"""Curation script for SpaceX-xAI Merger dossier."""
import json
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/spacex-xai-merger.json")

curation = {
    "lead": (
        "<p>On February 2, 2026, SpaceX acquired xAI in an all-stock transaction valued at $1.25 trillion — "
        "SpaceX at $1 trillion, xAI at $250 billion — structured through X.AI Holdings Corp, a Nevada vehicle "
        "with Jared Birchall as Corporate Secretary that had already raised $1.6 billion across two SEC Form D "
        "offerings between August 2025 and January 2026 [Finding #4501]. The share exchange ratio was set at "
        "0.1433 xAI shares per SpaceX share, pre-merger SpaceX shareholders were diluted 20 percent, and Sullivan "
        "&amp; Cromwell's fairness opinion valued X at $33 billion and xAI at $80 billion; a SpaceX IPO targeting "
        "$50 billion in proceeds was announced for mid-2026 [Finding #4502].</p>"
        "<p>The combined entity controls roughly 60 percent of US commercial rocket launches, 7,000-plus Starlink "
        "satellites, the Starshield classified military communications platform, an NRO spy satellite constellation "
        "worth $1.8 billion, a $200 million Pentagon contract for Grok integration across approximately 3 million "
        "military and civilian personnel, the X social media platform, and X Money payments infrastructure — "
        "consolidated under a single corporate owner who simultaneously holds more than $14.6 billion in NASA and "
        "DoD contract obligations [Finding #4702] [Finding #4505]. Six of xAI's twelve co-founders departed before "
        "the deal closed, citing safety concerns, and the Pentagon AI chief confirmed Grok's approval for classified "
        "networks despite the elimination of xAI's safety team [Finding #4505].</p>"
        "<p>The transaction closed nine months after Musk's formal departure from DOGE on May 30, 2025 — the same "
        "period during which the FTC lost staff from its antitrust division, the FCC cut spending by roughly one "
        "third, and the NLRB lost quorum, allowing dismissal of pending SpaceX unfair labor cases [Finding #4506]. "
        "A shareholder derivative suit filed in Delaware Chancery Court by the Cleveland Bakers and Teamsters "
        "Pension Fund alleged Musk diverted Tesla resources, employees, and AI research to xAI with no corresponding "
        "benefit to Tesla shareholders; Tesla separately invested $2 billion in xAI in January 2026 [Finding #4507].</p>"
    ),

    "system_role": (
        "The SpaceX-xAI Merger is the structural event through which Elon Musk consolidated his aerospace, "
        "satellite, artificial intelligence, communications, and social media holdings into a single corporation "
        "ahead of a planned public offering. It serves as the node connecting the DOGE regulatory-incapacitation "
        "period, the federal defense contract portfolio, the xAI Pentagon relationship, and the Tesla "
        "self-dealing litigation thread."
    ),

    "sections": [
        {
            "id": "deal-structure",
            "title": "Deal Structure and Financing",
            "content": (
                "X.AI Holdings Corp (CIK 0002079267), incorporated in Nevada in 2025 with Jared Birchall as "
                "Corporate Secretary, served as the restructuring vehicle for the transaction. The entity filed "
                "two SEC Form D Rule 506(b) exempt offerings: a $3.39 billion raise in August 2025 across seven "
                "investors, and a $4 billion target in January 2026, with $1.6 billion already sold at filing "
                "against 131 investors [Finding #4501]. Birchall, who appears as executive officer across all "
                "four Musk-controlled entities with Form D filings — Neuralink, The Boring Company, X.AI Corp, "
                "and X.AI Holdings Corp — managed the administrative mechanics of the deal through the same "
                "Excession LLC family office infrastructure used across the broader Musk entity network. "
                "The all-stock exchange at 0.1433 xAI per SpaceX share imposed a 20 percent dilution on "
                "pre-merger SpaceX shareholders [Finding #4502]. Sullivan &amp; Cromwell advised xAI; "
                "Gibson Dunn advised SpaceX. The fairness opinions placed X Corp at $33 billion and xAI "
                "at $80 billion, with SpaceX carrying $1 trillion of the combined $1.25 trillion valuation. "
                "See also: <a href='/dossiers/jared-birchall'>Jared Birchall</a>, "
                "<a href='/dossiers/xai'>xAI</a>, <a href='/dossiers/spacex'>SpaceX</a>."
            ),
            "viz": None
        },
        {
            "id": "federal-contract-consolidation",
            "title": "Federal Contract Consolidation",
            "content": (
                "The merger brought the following federal contract positions under a single corporate roof "
                "[Finding #4702] [Finding #5348]: a $1.8 billion NRO classified spy satellite constellation "
                "(Starshield); a $5.9 billion NSSL Phase 3 Lane 2 launch contract (April 2025); a $13 billion "
                "ceiling Space Force PLEO communications IDIQ (Starshield received the majority of $660 million "
                "in initial task orders); $733.5 million in Space Development Agency missions; a $200 million "
                "Pentagon AI contract for Grok integration covering approximately 3 million DoD and civilian "
                "personnel; and a $241,814 White House Communications Agency Starlink procurement. NASA "
                "obligations total $7.46 billion, DoD obligations $7.18 billion, for a combined all-time "
                "federal award base exceeding $14.6 billion [Finding #4963]. Musk also announced a proposal "
                "to build orbital AI data centers combining compute with satellite infrastructure, requesting "
                "FCC authorization for up to one million satellites. The merger occurred while a $2 billion "
                "contract for a 600-satellite missile-tracking custody layer under the Golden Dome program "
                "remained pending OMB release [Finding #4702]. "
                "See also: <a href='/dossiers/spacexstarshield'>SpaceX/Starshield</a>, "
                "<a href='/dossiers/golden-dome'>Golden Dome</a>, "
                "<a href='/dossiers/doge'>DOGE</a>."
            ),
            "viz": None
        },
        {
            "id": "regulatory-review",
            "title": "Regulatory Review and Oversight Gaps",
            "content": (
                "The transaction exceeds Hart-Scott-Rodino 2026 notification thresholds ($133.9 million) by "
                "a factor of roughly 1,800 [Finding #4503]. CFIUS has authority to review due to SpaceX's "
                "classified launch portfolio and Starlink's role as military infrastructure. The FCC separately "
                "opened review of the orbital data center proposal. Senators Warren and Kim asked the Pentagon "
                "to probe SpaceX for undisclosed Chinese investment routed through Cayman Islands "
                "special-purpose vehicles, a potential violation of FOCI (Foreign Ownership, Control, or "
                "Influence) rules [Finding #4503]. "
                "Each federal agency with direct oversight authority over a Musk company experienced staffing "
                "reductions or leadership replacement during the DOGE period that preceded the merger: the FTC "
                "saw a 15 percent budget cut proposed and staff dismissed ahead of the deal; the FCC's "
                "operating budget fell to approximately one-third of 2024 levels; the NLRB lost quorum for "
                "a year, and the SpaceX unfair labor practice case was dismissed in February 2026 — the same "
                "month the merger closed [Finding #4506] [Finding #5499]. In total, DOGE terminated "
                "$71.1 billion in federal contracts while zero SpaceX contract dollars were cut; SpaceX "
                "competitors were among the specifically targeted cuts [Finding #4767]. "
                "See also: <a href='/dossiers/doge'>DOGE</a>, "
                "<a href='/dossiers/elon-musk'>Elon Musk</a>."
            ),
            "viz": "timeline"
        },
        {
            "id": "ai-military-integration",
            "title": "AI-Military Integration and Security Clearance Questions",
            "content": (
                "xAI received a DoD contract worth up to $200 million in July 2025 for Grok integration into "
                "military systems; a former defense contracting official stated xAI had not been mentioned in "
                "prior contract discussions before the award [Finding #4707]. Grok was subsequently approved "
                "for classified networks, confirmed by the Pentagon AI chief, despite xAI having eliminated "
                "its safety team and six of twelve co-founders having departed citing safety-related concerns "
                "[Finding #4505]. The Starshield platform — which requires personnel security clearances at "
                "the top-secret level — was now joined under the same corporate entity as an AI system "
                "authorized for classified use. The merger created a structural question: standard national "
                "security vetting timelines (12-18 months for top-secret clearances) did not align with the "
                "speed at which xAI's systems gained classified access [Finding #4766]. The combined entity "
                "also controls the X platform and its data, X Money payment infrastructure, and the Grok AI "
                "model — an intelligence-collection surface that is now organizationally colocated with "
                "classified NRO satellite operations [Finding #4505]. "
                "See also: <a href='/dossiers/spacexstarshield'>SpaceX/Starshield</a>, "
                "<a href='/dossiers/xai'>xAI</a>."
            ),
            "viz": None
        },
        {
            "id": "fiduciary-disputes",
            "title": "Tesla Shareholder Litigation and Self-Dealing",
            "content": (
                "The Cleveland Bakers and Teamsters Pension Fund filed a derivative action in Delaware "
                "Chancery Court alleging Musk used the Tesla board to divert AI research, employees, and "
                "resources to xAI without corresponding benefit to Tesla shareholders [Finding #4507]. "
                "Tesla invested $2 billion in xAI in January 2026, two weeks before the SpaceX-xAI deal "
                "closed. xAI told investors it would build AI for Tesla's Optimus humanoid robot program. "
                "Musk holds a higher ownership percentage in xAI and SpaceX than he does in Tesla (Tesla: "
                "approximately 13 percent following dilution from his compensation package dispute), creating "
                "a structural incentive to route value from Tesla — the only publicly traded entity — "
                "into the private companies that will benefit most from an IPO [Finding #4507]. Musk "
                "negotiated both sides of any inter-company transaction across the Tesla, SpaceX, and xAI "
                "ecosystem. The D&amp;O liability implications were noted in legal commentary: the merger "
                "creates a new tier of board-level disclosure obligations once SpaceX files for a public "
                "offering [Finding #5301]. "
                "See also: <a href='/dossiers/elon-musk'>Elon Musk</a>, "
                "<a href='/dossiers/musk-entities'>Musk Entities</a>."
            ),
            "viz": None
        }
    ],

    "open_questions": [
        "Did the Hart-Scott-Rodino filing trigger substantive antitrust review, and if so, what conditions if any were imposed?",
        "What CFIUS determination, if any, was issued regarding Starshield's classified NRO operations under the post-merger corporate structure?",
        "What is the disposition of the Chinese investment FOCI inquiry raised by Senators Warren and Kim — specifically, which Cayman Islands SPVs were identified and have they been disclosed?",
        "Did the xAI safety team elimination occur before or after Grok received classified network authorization from the Pentagon AI chief?",
        "What is the ownership structure of X.AI Holdings Corp post-merger, and does Birchall's role as Corporate Secretary give him signatory authority over classified contract vehicles?",
        "Has the Delaware Chancery Court action by the Cleveland Bakers and Teamsters Pension Fund survived a motion to dismiss, and has the Tesla board produced a record of its xAI investment deliberations?",
        "What was the role of DOGE-obtained federal data — including competitor contract data from agencies DOGE teams accessed — in shaping SpaceX's 2025-2026 contract positioning?",
        "On what timeline did the six departing xAI co-founders leave relative to the classified Grok authorization and the merger announcement?",
        "Has the FCC's review of the orbital data center / one million satellite proposal resulted in any spectrum allocation decision, and who reviewed the national security implications?",
        "What is the current status of the OMB hold on the $2 billion AMTI Golden Dome satellite contract for which SpaceX was the identified recipient?"
    ],

    "applicable_models": [
        {
            "name": "Regulatory Capture Through Agency Incapacitation",
            "description": (
                "DOGE's concurrent weakening of FTC (antitrust), FCC (spectrum/orbital), NLRB (labor), "
                "FAA (launch licensing), SEC (securities), NHTSA (automotive), and FDA (neural) created "
                "a pre-merger environment in which each body responsible for reviewing a Musk company was "
                "simultaneously understaffed, underled, or operationally impaired. The SpaceX-xAI merger "
                "is the largest transaction to pass through this incapacitation window."
            )
        },
        {
            "name": "Convergent Policy Channeling",
            "description": (
                "The merger consolidates the beneficiary of five parallel federal spending channels: "
                "launch services (NASA/NSSL), military satellite communications (Space Force/Starshield), "
                "intelligence infrastructure (NRO), AI procurement (Pentagon/Grok), and the emerging "
                "Golden Dome missile defense build-out. A single corporate entity now holds competitive "
                "positioning across all five channels simultaneously."
            )
        },
        {
            "name": "Vertical Integration of Classified and Commercial Infrastructure",
            "description": (
                "The combined entity integrates classified NRO access, unclassified Starlink commercial "
                "service, the X social media platform (mass data collection), Grok AI (now authorized "
                "for classified networks), and X Money payments under one corporate owner. This creates "
                "a configuration in which intelligence-grade satellite operations, AI inference on "
                "classified data, and civilian communications infrastructure share a corporate ownership "
                "chain — a structure with no clear precedent in post-Cold War procurement policy."
            )
        },
        {
            "name": "Insider Positioning Ahead of IPO",
            "description": (
                "The merger consolidates $14.6 billion in contract obligations into the IPO vehicle "
                "at a moment when the regulatory agencies capable of challenging the structure are "
                "operationally weakened. Pre-IPO SEC Form D raises ($1.6 billion across 131 investors "
                "as of January 2026) established the valuation floor before public pricing. The "
                "Tesla-to-xAI resource transfer alleged in the Delaware litigation, if proven, would "
                "constitute a value extraction from public Tesla shareholders to private SpaceX/xAI "
                "shareholders ahead of the IPO."
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
