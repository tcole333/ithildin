#!/usr/bin/env python3
"""Write curation fields into michael-kratsios.json."""
import json
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/michael-kratsios.json")

with DOSSIER_PATH.open() as f:
    dossier = json.load(f)

curation = dossier.setdefault("curation", {})

# ── lead ──────────────────────────────────────────────────────────────────────
curation["lead"] = (
    "<p>Michael John Kotsakas Kratsios (born November 7, 1986) is the Director of the "
    "Office of Science and Technology Policy (OSTP), confirmed by the Senate on March 25, "
    "2025 by a vote of 74–25. [Finding #5096] He previously served as the United States "
    "Chief Technology Officer under Trump's first term (confirmed unanimously, August 2019) "
    "and as Acting Under Secretary of Defense for Research and Engineering from July 2020 "
    "through January 2021, a post that carried oversight of the Pentagon's approximately "
    "$106 billion annual research and development budget. [Finding #4592]</p>"
    "<p>Before his first government stint and between his two government stints, Kratsios "
    "worked inside the investment entities controlled by Peter Thiel. His career began at "
    "Barclays Capital, then moved to Clarium Capital Management (a Thiel macro fund) and "
    "then to Thiel Capital itself, where he served as principal, Chief Financial Officer, "
    "Chief Compliance Officer, and Chief of Staff. [Finding #5096] He left government in "
    "January 2021 and became Managing Director at Scale AI, an AI data-labeling company "
    "with documented ties to Thiel's network and a federal defense contract portfolio that "
    "reached $183.7 million during his tenure. [Finding #5101] He was nominated for his "
    "current OSTP role in December 2024 and confirmed the following March.</p>"
    "<p>FEC records show Kratsios donated $24,850 in federal contributions, of which the "
    "entirety after a $50 Republican National Committee donation in 2008 went to Blake "
    "Masters — a former Chief Operating Officer of Thiel Capital who ran for Arizona Senate "
    "with Thiel's financial backing. All donations listed his employer as Scale AI and his "
    "occupation as Managing Director. [Finding #5098]</p>"
)

# ── system_role ───────────────────────────────────────────────────────────────
curation["system_role"] = (
    "Federal science and technology policy director occupying the White House's top "
    "technology coordination role. Kratsios sets national AI strategy and defense "
    "technology priorities after a career arc running Thiel Capital finance operations, "
    "managing US CTO and Pentagon R&D portfolios, and then serving as a senior executive "
    "at a defense AI company — Scale AI — that accumulated $183.7 million in federal "
    "contracts during his tenure there. He is the second consecutive Thiel-network "
    "figure to hold the White House's senior technology policy position across the two "
    "Trump terms."
)

# ── sections ──────────────────────────────────────────────────────────────────
curation["sections"] = [
    {
        "id": "career-arc",
        "title": "Career Arc",
        "content": (
            "Kratsios graduated from Princeton University and began his career as an "
            "analyst at Barclays Investment Bank. He then joined Clarium Capital "
            "Management, a Thiel-controlled global macro hedge fund, followed by Thiel "
            "Capital itself, where LittleSis records document him holding the roles of "
            "principal, Chief Financial Officer, Chief Compliance Officer, and Chief of "
            "Staff across approximately seven years. [Finding #5096] In 2017 he joined "
            "the Trump White House as Deputy Assistant to the President for Technology "
            "Policy, was designated US Chief Technology Officer the same year, and was "
            "confirmed by the Senate without opposition in August 2019. From July 2020 "
            "to January 2021 he simultaneously served as Acting Under Secretary of "
            "Defense for Research and Engineering — the Pentagon's senior civilian "
            "technology position — overseeing an R&D budget of approximately $106 "
            "billion. [Finding #4592]"
            "\n\n"
            "After leaving government in January 2021, Kratsios became Managing "
            "Director at Scale AI, a San Francisco-based company that labels and "
            "annotates training data for AI models and holds substantial federal "
            "defense contracts. He remained at Scale AI through late 2024. Trump "
            "nominated him as OSTP Director in December 2024; the Senate confirmed "
            "him 74–25 on March 25, 2025. [Finding #4678] OpenSanctions lists him "
            "as a Politically Exposed Person under his full legal name. [Finding #5096] "
            "He is also a World Economic Forum Young Global Leader and has spoken to "
            "the OECD on AI policy. [Finding #5096]"
        ),
        "viz": None,
    },
    {
        "id": "scale-ai-defense-contracts",
        "title": "Scale AI Defense Contracts",
        "content": (
            "During Kratsios's tenure as Managing Director, Scale AI accumulated a "
            "documented federal defense contract portfolio of $183.7 million. The "
            "largest single award was a $110 million Army R&D AI/ML testing contract "
            "(W911QX20C0051). Additional awards included a $36.3 million Army prototype "
            "and data-labeling contract (W519TC2392045), a $9.8 million Space "
            "Development Agency generative AI joint planning tool (HQ08452590034), "
            "a $5 million autonomous perimeter security project (HQ08452290064), "
            "a $4.6 million Army prototype, a $4.5 million Army Research Laboratory AI "
            "contract awarded in 2025 (W911QX25DA011), a $2.5 million DLA PIEE "
            "transition project, a $1.5 million AFRL Tradewinds Donovan award, a $1.2 "
            "million NASIC JWICS deployment, and a $1 million Project ZION LLM "
            "integration. [Finding #5101] SAM.gov registers Scale AI under two "
            "Unique Entity Identifiers: DHU2LMKSDQD9 (San Francisco) and "
            "CNE4V1J27PM9 (Washington DC). [Finding #5101]"
            "\n\n"
            "Scale AI lobbied on defense and intelligence issues through its own "
            "registration and via two retained firms: Ballard Partners at $40,000 per "
            "quarter and The Halcrow Group at $50,000 per quarter. [Finding #5101] "
            "Ballard Partners was founded by Brian Ballard, a major Trump fundraiser. "
            "[Finding #5082] Scale AI and Anduril Industries share Cornerstone "
            "Government Affairs and Mehlman Consulting as lobbying firms, a configuration "
            "that links the two companies' government relations efforts. [Finding #5080] "
            "FEC employer-based donation analysis shows Scale AI employees donated 97% "
            "to Republican candidates and committees — a figure dominated by CEO "
            "Alexandr Wang's $250,000 donation to the Republican National Committee. "
            "[Finding #5382]"
            "\n\n"
            "Kratsios returned to government as OSTP Director with authority over "
            "federal AI policy, including defense AI procurement strategy — the precise "
            "domain his former employer had been building a contract base in throughout "
            "his tenure there. No public evidence of divestiture from Scale AI financial "
            "interests has emerged. [Finding #4592] A second Scale AI alumnus, Ethan A. "
            "Klein, followed Kratsios to OSTP as Associate Director for Technology "
            "— having served at Scale AI from 2021 through 2025. [Finding #5281]"
        ),
        "viz": None,
    },
    {
        "id": "thiel-network-position",
        "title": "Thiel Network Position",
        "content": (
            "Kratsios's career is structured around a persistent affiliation with "
            "<a href='/dossiers/peter-thiel'>Peter Thiel</a>'s financial and political "
            "network. His pre-government employment ran through two Thiel-controlled "
            "investment vehicles — Clarium Capital and Thiel Capital — where he "
            "held senior financial and compliance roles. [Finding #5096] ProPublica's "
            "analysis of Trump administration financial disclosures identified Kratsios "
            "as one of four appointees who reference 'Thiel' directly in their ethics "
            "filings, alongside Jamie Gillespie (White House), Jared Smith (DOT), and "
            "Tristan Abbey (DOE). [Finding #5204] The broader Thiel network spans 152 "
            "unique appointees across 31 agencies, with the deepest penetration in "
            "State (18), the White House (13), and HHS (13). [Finding #5236]"
            "\n\n"
            "Kratsios's exclusive political donation record reinforces this network "
            "membership. His $24,800 in federal contributions went entirely to Blake "
            "Masters, a former Thiel Capital Chief Operating Officer who ran for Arizona "
            "Senate with Thiel's direct financial backing. [Finding #5098] All donations "
            "were filed under employer Scale AI, a company that Thiel's investment "
            "network has backed. The pattern — Thiel Capital Chief of Staff donating "
            "exclusively to Thiel Capital COO — is consistent across multiple cycles "
            "and predates Kratsios's return to government. [Finding #5098]"
            "\n\n"
            "Founders Fund, Thiel's venture capital firm, holds portfolio investments "
            "in SpaceX, Anduril, and Palantir — companies receiving billions in federal "
            "contracts that fall within the technology policy domain Kratsios administers. "
            "[Finding #5451] Palantir, co-founded by Thiel, is documented as the "
            "Pentagon's primary commercial software platform. [Finding #4678] The "
            "systemic pattern across both Trump terms is one of sequential Thiel-network "
            "occupancy of the White House's senior technology policy role: Kratsios held "
            "the CTO position in Trump's first term; <a href='/dossiers/david-sacks'>"
            "David Sacks</a>, from the PayPal Mafia cohort, holds the AI and Crypto Czar "
            "role in the second. [Finding #5452]"
        ),
        "viz": "ego_network",
    },
    {
        "id": "ostp-policy-mandate",
        "title": "OSTP Policy Mandate",
        "content": (
            "OSTP coordinates federal R&D strategy and advises the President on science, "
            "technology, and innovation policy. Kratsios has described his approach as a "
            "'promote and protect' strategy for AI, which involves ingesting federal "
            "data into AI models to improve government services while establishing "
            "guardrails against foreign adversary access. [Finding #4592] This mandate "
            "places him at the center of decisions about which AI vendors receive federal "
            "data, which companies are authorized to operate on government networks, and "
            "which standards govern defense AI procurement."
            "\n\n"
            "The broader Silicon Valley defense tech network in which Kratsios is "
            "embedded — encompassing Palantir, SpaceX, Anduril, and Scale AI — "
            "generated approximately $1.64 billion in combined FY2025 federal contracts, "
            "a 54% increase from FY2023. [Finding #4608] Nine or more senior Trump "
            "administration appointees hold direct financial ties to these defense tech "
            "companies, occupying positions from requirements (Emil Michael as USD "
            "for Research and Engineering) to budget (OMB) to IT to policy (Sacks and "
            "Kratsios). [Finding #4608] Kratsios's OSTP coordinates directly with these "
            "positions on federal technology procurement priorities."
            "\n\n"
            "SpaceX's lobbying registration lists OSTP as one of the agencies targeted, "
            "alongside DOD, NASA, FAA, DARPA, Air Force, and OMB. [Finding #5606] "
            "GreenMet, a critical minerals company, similarly targeted OSTP through its "
            "in-house lobbying arm Greentech Minerals Holdings LLC. [Finding #6373] "
            "These filings document OSTP as an active object of federal lobbying across "
            "sectors relevant to Kratsios's prior industry positions."
        ),
        "viz": None,
    },
    {
        "id": "financial-activity",
        "title": "Financial Activity",
        "content": (
            "FEC records identify $24,850 in total federal political contributions by "
            "Kratsios. The earliest donation — $50 to the Republican National Committee "
            "in 2008, filed under employer Barclays Capital — predates his Thiel "
            "employment. All subsequent contributions were made while he was at Scale AI "
            "and directed exclusively to Blake Masters. [Finding #5098]"
            "\n\n"
            "The Masters donations break down as follows: $6,600 via WinRed and $6,600 "
            "direct to Blake Masters Congress (October 2023); $5,800, $2,900, and $2,900 "
            "via WinRed to Masters for Senate (July 2021). All filings list employer as "
            "Scale AI and occupation as Managing Director. [Finding #5098] Masters "
            "received $15 million from Thiel personally for his 2022 Arizona Senate "
            "primary run, making him one of the most direct expressions of Thiel network "
            "political investment in the cycle. [Finding #5098]"
            "\n\n"
            "Scale AI employees as a group donated 97% to Republican candidates and "
            "committees during the same period, a figure dominated by CEO Alexandr "
            "Wang's $250,000 RNC contribution. Wang's personal FEC record also shows "
            "$7,700 via ActBlue and $6,600 to Senator Martin Heinrich (D-NM, Senate "
            "Armed Services Committee) — a more bipartisan personal distribution than "
            "the company-level aggregate. [Finding #5410] Six Trump administration "
            "appointees held Scale AI in their financial disclosures. [Finding #5200]"
        ),
        "viz": None,
    },
]

# ── open_questions ─────────────────────────────────────────────────────────────
curation["open_questions"] = [
    (
        "Kratsios's OSTP ethics filing references Thiel and lists Scale AI holdings. "
        "What specific recusal obligations govern his role in federal AI procurement "
        "decisions involving Scale AI or Thiel-portfolio companies (Palantir, Anduril, "
        "SpaceX), and have those recusals been documented publicly?"
    ),
    (
        "Scale AI's defense contract portfolio — $183.7 million documented — grew "
        "substantially during Kratsios's tenure as Managing Director. What were the "
        "specific contract award dates relative to his time in that role, and did any "
        "procurement decisions involve officials he knew from his prior DoD service?"
    ),
    (
        "The OSTP 'promote and protect' strategy involves ingesting federal data into "
        "AI models. Which specific commercial AI vendors are authorized or under "
        "consideration for that data access, and what role does OSTP play in the "
        "vendor selection process relative to contracting agencies?"
    ),
    (
        "Ethan A. Klein followed Kratsios from Scale AI to OSTP as Associate Director "
        "for Technology. What is Klein's specific portfolio within OSTP, and does it "
        "include any oversight of AI procurement programs in which Scale AI participates?"
    ),
    (
        "Kratsios served as Acting Under Secretary of Defense for Research and "
        "Engineering from July 2020 to January 2021, then joined Scale AI, which "
        "holds Army and intelligence community contracts in exactly the programs his "
        "office would have overseen. Were any Scale AI awards preceded by program "
        "structures established during his DoD tenure?"
    ),
    (
        "Clarium Capital Management, the Thiel macro fund where Kratsios worked before "
        "Thiel Capital, is not well documented in public records. What was the nature "
        "of his role there and what was Clarium's investment mandate during his tenure?"
    ),
    (
        "The LittleSis record lists 23 relationships for Kratsios (entity 282287). "
        "Several of those relationships remain unverified against primary sources. "
        "Which of his Thiel Capital roles — principal, CFO, CCO, or Chief of Staff — "
        "are confirmed by corporate registry or regulatory filings rather than "
        "biographical summaries?"
    ),
]

# ── applicable_models ──────────────────────────────────────────────────────────
curation["applicable_models"] = [
    {
        "name": "Government-Industry-Government Revolving Door",
        "description": (
            "Kratsios's career follows a documented three-phase structure: Thiel Capital "
            "finance roles → Trump White House/Pentagon technology policy → Scale AI "
            "Managing Director (defense AI contracts) → Trump White House technology "
            "policy again. The middle private-sector phase directly overlapped with the "
            "policy domain he had managed and would manage again, and the company he "
            "joined accumulated its largest defense contract base during his tenure there."
        ),
    },
    {
        "name": "Sequential Institutional Occupation",
        "description": (
            "The Thiel network has held the White House's senior technology policy "
            "position across both Trump terms without interruption: Kratsios (CTO, "
            "2017–2021) and then David Sacks (AI/Crypto Czar, 2025–present). Both came "
            "from the same network of approximately 11 interconnected individuals. This "
            "pattern is distinct from individual appointments; it represents persistent "
            "occupancy of a single institutional position across administrations."
        ),
    },
    {
        "name": "Network-Exclusive Political Giving",
        "description": (
            "Kratsios's entire documented political giving history after 2008 targets a "
            "single recipient — Blake Masters, the former Thiel Capital COO — across "
            "multiple cycles and both Senate and House races. This donor-recipient pair "
            "shares a direct prior employment relationship at the same firm. The giving "
            "pattern is less consistent with general Republican alignment than with "
            "deliberate investment in a specific network member's political career."
        ),
    },
    {
        "name": "Former-Employer Contract Alignment",
        "description": (
            "Scale AI's federal defense contract portfolio of $183.7 million is "
            "concentrated in Army AI/ML research, autonomous systems, and intelligence "
            "community AI deployment — precisely the procurement categories that fall "
            "within OSTP's coordination authority and that Kratsios managed at the "
            "Pentagon as acting USD(R&E). The company that employed him between "
            "government stints is now a significant vendor in the policy space he "
            "currently administers."
        ),
    },
    {
        "name": "Two-Person Company-to-Agency Pipeline",
        "description": (
            "The co-movement of Kratsios and Ethan A. Klein from Scale AI to OSTP — "
            "a Managing Director and a former intern arriving at the same office — "
            "illustrates a sub-pattern within the revolving door structure: not just "
            "individual placement but cohort transfer from a single private employer "
            "to a single government office. This creates shared institutional memory "
            "and durable professional loyalty within the receiving agency."
        ),
    },
]

# ── preserve existing key_finding_ids and key_identifiers ────────────────────
curation.setdefault("key_finding_ids", [5101, 4678, 5098, 5096, 5103, 4592])
curation.setdefault("key_identifiers", {"jurisdictions": [], "officers": [], "entities": []})

# ── write back ────────────────────────────────────────────────────────────────
with DOSSIER_PATH.open("w") as f:
    json.dump(dossier, f, indent=2)

print("Curation written to", DOSSIER_PATH)
