#!/usr/bin/env python3
"""Write curation fields into content/dossiers/shyam-sankar.json"""
import json
from datetime import datetime, timezone

DOSSIER_PATH = "content/dossiers/shyam-sankar.json"

with open(DOSSIER_PATH) as f:
    dossier = json.load(f)

curation = dossier.get("curation", {})

# ── LEAD ────────────────────────────────────────────────────────────────────
curation["lead"] = (
    "<p>Shyam Sankar is the Chief Technology Officer of "
    "<a href=\"/dossiers/palantir-technologies\">Palantir Technologies</a>, the data analytics "
    "and AI platform company that holds a $10 billion Army Enterprise Agreement, a $1.3 billion "
    "Maven Smart System contract ceiling, and $3.87 billion in documented all-time federal "
    "obligations. He holds $200 million or more in Palantir stock through equity compensation. "
    "[Finding #5088] In June 2025 he was commissioned as a United States Army Reserve "
    "Lieutenant Colonel in Detachment 201, the Executive Innovation Corps — a unit that "
    "simultaneously commissioned Meta CTO Andrew Bosworth, OpenAI CPO Kevin Weil, and former "
    "OpenAI CRO Bob McGrew. [Finding #4676] No formal recusal mechanism from DoD business "
    "dealings was reported at the time of commissioning; Army officials told Breaking Defense that "
    "the executives \"are not making acquisition decisions,\" without specifying what oversight "
    "structure governs the arrangement. [Finding #4676]</p>"
    "<p>FEC records for the 2025–2026 cycle show $77,125 in personal political donations. [Finding #5086] "
    "The giving is concentrated on members of the Senate and House Armed Services Committees: "
    "Todd Young (SASC, $7,000), Zach Nunn (HASC, $7,000), Tim Sheehy (Montana Senate, $7,000), "
    "and Pat Ryan (HASC, $3,500 via ActBlue). The $10,500 to Jon Husted (Ohio Senate) and "
    "$5,000 to OORAH! PAC (Marine-linked) extend the pattern. [Finding #5086] Within Palantir, "
    "Sankar is the second-largest individual donor after CEO Alex Karp: employee-level giving "
    "runs 63% Democratic, but Karp personally gave $4.08 million — 69% Republican, including "
    "$2 million to Trump vehicles. Sankar's $32,000 falls between the rank-and-file and Karp, "
    "targeted to Armed Services oversight rather than partisan committees. [Finding #5413]</p>"
    "<p>Sankar attended the a16z American Dynamism Summit in Washington DC in early 2026, "
    "alongside Anduril CSO Christian Brose, Pentagon procurement officials from the Defense "
    "Innovation Unit, and CEOs from Castelion, Hadrian, and Apex. [Finding #5340] The summit "
    "is a private event controlled by Andreessen Horowitz at which portfolio company leadership "
    "meets senior Pentagon procurement figures — a channel outside standard government "
    "procurement processes.</p>"
)

# ── SYSTEM ROLE ──────────────────────────────────────────────────────────────
curation["system_role"] = (
    "Sankar occupies the technical leadership position at the company most deeply embedded in "
    "US government data infrastructure: as CTO he is the senior architect of the platform "
    "Palantir is installing across the Army, the intelligence community, and federal civilian "
    "agencies through a $10 billion Enterprise Agreement and dozens of agency-level contracts. "
    "His concurrent Army Reserve commission as a lieutenant colonel in the Executive Innovation "
    "Corps places him in an officer role at the primary customer for Palantir's largest contract "
    "while he retains equity worth $200 million or more. His political giving targets the specific "
    "congressional committees that authorize and appropriate Pentagon software budgets. "
    "The combination — CTO authority over the product, officer rank at the buyer, equity "
    "stake in the contract value, and systematic political cultivation of oversight members — "
    "positions Sankar at the convergence of all three institutional levers governing the "
    "Palantir-government relationship."
)

# ── SECTIONS ─────────────────────────────────────────────────────────────────
curation["sections"] = [
    {
        "id": "army-reserve-commission",
        "title": "Army Reserve Commission and the Conflict Structure",
        "viz": None,
        "content": (
            "<p>In June 2025, Sankar was commissioned as an Army Reserve Lieutenant Colonel "
            "in Detachment 201, formally designated the Executive Innovation Corps. [Finding #4676] "
            "The unit simultaneously commissioned three other Silicon Valley executives whose "
            "companies hold active Pentagon contracts: Andrew Bosworth (Meta CTO, whose company "
            "partnered with <a href=\"/dossiers/anduril-industries\">Anduril</a> on IVAS); "
            "Kevin Weil (OpenAI CPO, whose company signed a $200 million defense deal in "
            "June 2025); and Bob McGrew (former OpenAI CRO, then affiliated with Thinking "
            "Machines Lab). [Finding #4598] The unit's stated purpose is advising the Army "
            "on technology strategy.</p>"
            "<p>The structural tension is documented rather than speculative. "
            "<a href=\"/dossiers/palantir-technologies\">Palantir</a> holds a $10 billion "
            "Army Enterprise Agreement IDIQ (W519TC25D0039), a $1.3 billion Maven Smart "
            "System ceiling, and a CDAO task order of $80 million awarded October 2025. "
            "[Finding #5088] Sankar retains at least $200 million in Palantir equity. [Finding #4676] "
            "Army officials responding to press inquiries stated that the commissioned "
            "executives \"are not making acquisition decisions\" — but no formal recusal "
            "agreement, ethics opinion, or OGE instrument governing the arrangement "
            "has been identified in the public record. [Finding #4676]</p>"
            "<p>The Breaking Defense and Military.com coverage documented the absence of "
            "oversight mechanisms rather than the presence of recusal. The Democracy Defenders "
            "Fund sent a formal letter to Army officials on this point. [Finding #4676] "
            "The question the public record leaves open is whether \"not making acquisition "
            "decisions\" in the formal procurement sense excludes the advisory and strategy "
            "functions that Detachment 201 was specifically created to perform — functions "
            "that can shape requirements, platform architecture preferences, and technology "
            "roadmaps upstream of formal acquisition decisions.</p>"
        ),
    },
    {
        "id": "political-giving-architecture",
        "title": "Political Giving and Defense Oversight Targeting",
        "viz": None,
        "content": (
            "<p>FEC Schedule A filings for the 2025–2026 cycle show $77,125 in personal "
            "donations from Shyam Sankar. [Finding #5086] The distribution maps directly "
            "onto the congressional committees that authorize and appropriate funding for "
            "Palantir's primary federal customers. Todd Young (Indiana, SASC) received "
            "$7,000 total. Zach Nunn (Iowa, HASC) received $7,000. Tim Sheehy (Montana "
            "Senate, veteran and Armed Services aspirant) received $7,000 through the "
            "Sheehy Victory Committee. Jon Husted (Ohio Senate) received $10,500 — the "
            "single largest recipient. Pat Ryan (New York, HASC) received $3,500 via "
            "ActBlue, representing the Democratic Armed Services element of the portfolio. "
            "OORAH! PAC, linked to the Marine Corps community, received $5,000. [Finding #5086]</p>"
            "<p>The bipartisan distribution is consistent with the contract-driven logic "
            "documented in FEC data: Sankar donated to Armed Services members in both "
            "parties while the dominant partisan axis within his giving tracks defense "
            "oversight rather than general party alignment. [Finding #5092] This placing "
            "him in a structurally similar position to "
            "<a href=\"/dossiers/palmer-luckey\">Palmer Luckey</a>, whose FEC giving "
            "also targeted SASC and HASC members across party lines, and to Anduril as "
            "a company — which splits bipartisanly at the leadership level to maintain "
            "access to both parties' Armed Services oversight infrastructure.</p>"
            "<p>Within Palantir's giving landscape, Sankar's $32,000 sits between the "
            "rank-and-file workforce (63% Democratic, driven by $108,000 to ActBlue) and "
            "CEO Alex Karp ($4.08 million, 69% Republican, including $2 million to Trump "
            "vehicles). [Finding #5413] Sankar is designated in the FEC data as \"COO\" "
            "in one filing set and his employer as Palantir, with payroll-deduction "
            "contributions to the Palantir PAC also present. The identity finding notes "
            "him as CTO rather than COO; the discrepancy in employer self-description "
            "across FEC filings is a minor data inconsistency to monitor.</p>"
        ),
    },
    {
        "id": "palantir-contract-portfolio",
        "title": "Palantir Contract Portfolio and Sankar's CTO Role",
        "viz": None,
        "content": (
            "<p><a href=\"/dossiers/palantir-technologies\">Palantir Technologies</a> holds "
            "$3.87 billion in documented all-time federal contract obligations through the "
            "Palantir Technologies Inc. entity (UEI FSY4LVSBGWB7, CAGE 470F5). The shift "
            "to a separate contracting entity — Palantir USG Inc. (UEI HNN4F9JZWDY8) — "
            "began around 2024 and holds an additional $1.65 billion in DoD obligations. "
            "Combined, the two entities hold the largest federal contract exposure of any "
            "pure-software vendor in the defense sector. [Finding #5088]</p>"
            "<p>The largest single contract is the Army Enterprise Agreement IDIQ "
            "(W519TC25D0039), awarded July–August 2025, which consolidated 75 prior Army "
            "contracts into a single $10 billion ceiling vehicle covering a decade. "
            "The Maven Smart System ceiling was separately raised by $795 million (May 2025) "
            "to $1.3 billion before the ESA was awarded. A CDAO MSS task order of "
            "approximately $80 million followed in October 2025. [Finding #5088] "
            "Key civilian-agency contracts: VA National Center for Veterans Analysis "
            "($385 million), ICE Investigative Case Management ($159 million), VA SaaS "
            "($103 million), DOE SAFER ($91 million), FDA Enterprise Data Platform "
            "($48 million), Army BPA ($46 million). [Finding #5088]</p>"
            "<p>As CTO, Sankar is the senior technical decision-maker shaping Palantir's "
            "platform architecture — the AIP (Artificial Intelligence Platform) and "
            "Foundry products that the Army ESA and federal agency deployments run on. "
            "The CTO role in a company of Palantir's structure is upstream of product "
            "management and delivery; it determines technical roadmap and the platform "
            "capabilities that government program offices specify in future task orders. "
            "Sankar has been publicly identified as a primary voice on Palantir's AI "
            "strategy in the defense context, including in his capacity as a commissioned "
            "Army officer advising on technology requirements.</p>"
        ),
    },
    {
        "id": "network-position",
        "title": "Network Position: Palantir, a16z, and the Defense-Tech Ecosystem",
        "viz": "ego_network",
        "content": (
            "<p>Sankar's documented network connections place him at the intersection of "
            "Palantir's Thiel-origin corporate structure and the broader Silicon Valley "
            "defense-tech ecosystem that has consolidated around the DOGE-era Pentagon. "
            "<a href=\"/dossiers/peter-thiel\">Peter Thiel</a> co-founded Palantir in 2003 "
            "and remains chairman; Founders Fund has been the primary institutional "
            "investor since inception. Sankar joined Palantir in 2009 and rose to CTO, "
            "making him one of the longest-tenured non-founding C-suite executives at "
            "the company.</p>"
            "<p>His attendance at the 2026 a16z American Dynamism Summit — the fourth "
            "annual private convening of defense-tech CEOs, Pentagon officials, and "
            "policymakers hosted by Andreessen Horowitz — documents a formal relationship "
            "with the $1.176 billion American Dynamism fund. [Finding #5340] Other "
            "documented attendees from the defense-tech sector included Christian Brose "
            "(<a href=\"/dossiers/anduril-industries\">Anduril</a> CSO), Liz Young McNally "
            "(Deputy Director of the Defense Innovation Unit), and the CEOs of Castelion, "
            "Hadrian, and Apex. The summit's access structure — a16z-controlled guest list, "
            "no public agenda — means it functions as a private relationship channel "
            "between defense contractors and procurement officials outside the formal "
            "Federal Advisory Committee Act framework. [Finding #5340]</p>"
            "<p>Within Palantir's government-pipeline structure, Sankar is the most senior "
            "internal figure. The documented Palantir alumni network placed into federal "
            "IT roles since January 2025 — "
            "<a href=\"/dossiers/gregory-barbaccia\">Gregory Barbaccia</a> (Federal CIO, "
            "OMB), <a href=\"/dossiers/clark-minor\">Clark Minor</a> (HHS CIO), "
            "Allan Mangaser (Senior Adviser to CIO, OMB), Anthony Jancso (DOGE AI agents), "
            "Akash Bobba (OPM/SSA/Education) — operates on the government side of the "
            "relationship Sankar manages on the corporate side. [Finding #5948] As CTO, "
            "Sankar's product decisions are directly relevant to what those alumni are "
            "procuring and deploying inside federal agencies.</p>"
        ),
    },
]

# ── OPEN QUESTIONS ───────────────────────────────────────────────────────────
curation["open_questions"] = [
    (
        "What ethics instrument, OGE opinion, or Army Inspector General review governs "
        "Sankar's concurrent roles as Palantir CTO (with $200M+ equity in a company holding "
        "a $10B Army contract) and Army Reserve Lieutenant Colonel in Detachment 201? "
        "Army officials told press that the executives are 'not making acquisition decisions,' "
        "but no formal recusal agreement or legal opinion has been identified in the public "
        "record. Does one exist, and under what authority was it issued? [Finding #4676]"
    ),
    (
        "Detachment 201 commissions tech executives to 'advise the Army on technology "
        "strategy.' What is the specific scope of that advisory function — does it include "
        "requirements definition, architecture reviews, vendor landscape assessments, or "
        "any input into future contract structures? Any of these functions could shape "
        "program requirements in ways that benefit Palantir upstream of formal procurement "
        "decisions. What are the unit's written terms of reference? [Finding #4598]"
    ),
    (
        "FEC filings list Sankar as both 'CTO' and 'COO' at Palantir across different "
        "filings. What is the accurate current title, and does Sankar hold COO-equivalent "
        "operational authority in addition to the CTO technical role? The distinction matters "
        "because a COO designation would place him in the operational chain for business "
        "development and contract execution as well as product architecture. [Finding #5090]"
    ),
    (
        "Sankar's $5,000 to OORAH! PAC and the targeting of Armed Services members across "
        "both parties is consistent with a systematic cultivation strategy. Is there a documented "
        "Palantir-level political strategy that coordinates Sankar's personal giving with "
        "the Palantir PAC, CEO Alex Karp's giving, and the company's lobbying expenditures "
        "(documented at $10M+ via Morgan Cunningham, Invariant, and others)? Or does each "
        "giving channel operate independently? [Finding #5086] [Finding #5413]"
    ),
    (
        "The $10B Army ESA was awarded while DOGE-placed Palantir alumnus Gregory Barbaccia "
        "held the Federal CIO position at OMB, which oversees government-wide IT procurement "
        "policy. Barbaccia's role does not directly execute Army contracts, but OMB's FITARA "
        "compliance reviews apply to large IT investments. Did Barbaccia or any OMB official "
        "with a Palantir background participate in any FITARA review, approval, or waiver "
        "process related to the Army ESA or the Maven Smart System ceiling increase? "
        "[Finding #6447] [Finding #5948]"
    ),
    (
        "Sankar attended the a16z American Dynamism Summit alongside Deputy DIU Director "
        "Liz Young McNally and other senior procurement officials. The DIU is one of the "
        "primary channels through which non-traditional defense contractors enter DoD "
        "procurement. Did any DIU solicitation, OTA, or other procurement action involving "
        "Palantir proceed during the period in which Young McNally and Sankar shared "
        "attendance at the summit? [Finding #5340]"
    ),
]

# ── APPLICABLE MODELS ────────────────────────────────────────────────────────
curation["applicable_models"] = [
    "conflict-of-interest",
    "revolving-door",
    "bridge-tax",
    "manufactured-dependency",
]

curation["curated_at"] = datetime.now(timezone.utc).isoformat()

dossier["curation"] = curation

with open(DOSSIER_PATH, "w") as f:
    json.dump(dossier, f, indent=2)
    f.write("\n")

print("Curation written successfully.")
print(f"  lead: {len(curation['lead'])} chars")
print(f"  system_role: {len(curation['system_role'])} chars")
print(f"  sections: {len(curation['sections'])}")
print(f"  open_questions: {len(curation['open_questions'])}")
print(f"  applicable_models: {curation['applicable_models']}")
