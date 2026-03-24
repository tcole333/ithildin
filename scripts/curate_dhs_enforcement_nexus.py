#!/usr/bin/env python3
"""
Curation script for DHS Enforcement Nexus dossier.
Writes the `curation` block: lead, system_role, sections, open_questions, applicable_models.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DOSSIER_PATH = Path(__file__).parent.parent / "content/dossiers/dhs-enforcement-nexus.json"

LEAD = (
    '<p>The DHS Enforcement Nexus is the interconnected set of financial positions, '
    'personnel placements, procurement contracts, and data pipeline agreements that '
    'link White House immigration policy to a concentrated group of private contractors '
    'executing it. The nexus runs from <a href="/dossiers/stephen-miller">Stephen Miller</a>\'s '
    'policy directives through <a href="/dossiers/palantir-technologies">Palantir '
    'Technologies</a>\'s targeting infrastructure and GEO Group\'s detention and '
    'monitoring operations, and is structured around documented financial conflicts '
    'at every level: the policy author, the department head, the deputy secretary, '
    'and the Under Secretary for Science and Technology each held Palantir stock '
    'while overseeing agency contracts worth more than $1 billion [Finding #4775] '
    '[Finding #4845] [Finding #5209] [Finding #5227].</p>'
    '<p>The scale of the financial flows is concrete. The One Big Beautiful Bill Act '
    '(H.R. 1), signed July 4, 2025, allocated $170.7 billion to immigration enforcement '
    'through FY2029, including $45 billion for detention construction — a 311 percent '
    'increase in ICE\'s annual detention budget — with GEO Group and CoreCivic as the '
    'primary beneficiaries of a market where 90 percent of beds are operated by '
    'for-profit corporations [Finding #4844]. GEO Group and CoreCivic contributed a '
    'combined $2.8 million to the Trump 2024 campaign and inauguration; within months '
    'each company received nine or more new or expanded ICE contracts [Finding #4846]. '
    'Palantir holds $287 million in cumulative ICE contracts including the $30 million '
    'ImmigrationOS sole-source award [Finding #4841]. The top ten ICE contractors '
    'collectively received approximately $3.8 billion of a $5.4 billion total '
    'procurement pool — a 69 percent increase since January 20, 2025 [Finding #4856].</p>'
    '<p>The data infrastructure the nexus operates is more pervasive than the '
    'detention footprint. Palantir\'s ELITE targeting tool ingests Medicaid records '
    'from approximately 80 million patients through a January 2025 ICE-CMS data-sharing '
    'agreement to generate confidence scores on deportation targets [Finding #4819]. '
    'FALCON, the legacy system ELITE sits atop, scans driver\'s license photos of one '
    'in three U.S. adults and can access driver data for three in four [Finding #4836]. '
    'GEO Group\'s subsidiary B.I. Incorporated operates SmartLINK GPS monitoring on '
    '253,875 people under a $2.2 billion sole-source contract, collecting geolocation, '
    'facial recognition, voice recognition, contacts, and vehicle data under a June '
    '2025 ICE directive mandating monitors "whenever possible" [Finding #4808] '
    '[Finding #4854].</p>'
)

SYSTEM_ROLE = (
    "The DHS Enforcement Nexus is the structural arrangement through which White House "
    "immigration policy is converted into contracted detention, surveillance, and data "
    "operations. It operates across three interlocking layers: a policy layer (Miller's "
    "directives and the executive orders creating the legal basis for emergency "
    "procurement), a financial conflict layer (stock holdings across the DHS "
    "decision-making chain from the Deputy Chief of Staff through to department-level "
    "procurement officials), and a technical infrastructure layer (Palantir's targeting "
    "platforms and GEO Group's detention and monitoring operations). Palantir is the "
    "single entity that connects immigration enforcement infrastructure to broader "
    "federal data systems, providing the platform used for both military targeting "
    "and deportation targeting through the same Gotham architecture and personnel "
    "pipeline. The nexus has operated in its current form since January 20, 2025, "
    "when the Day 1 executive order blitz established the emergency procurement "
    "authority that compressed the policy-to-contract timeline to 36 days."
)

SECTIONS = [
    {
        "id": "policy-to-contract-pipeline",
        "title": "Policy-to-Contract Timeline: Day 1 Through H.R. 1",
        "viz": None,
        "content": (
            '<p>On January 20, 2025, five executive orders and one proclamation — '
            'EO 14159 (enforcement expansion), EO 14160 (birthright citizenship), '
            'EO 14161 (extreme vetting), EO 14165 (border operations and CBP One '
            'shutdown), EO 14167 (military border role), and Proclamation 10886 '
            '(national emergency) — established the legal foundation for emergency '
            'procurement before any border emergency had materially changed. The '
            'emergency declaration invoked the National Emergencies Act and 10 U.S.C. '
            '§ 2808, allowing DoD construction funds to be redirected to border '
            'infrastructure. The first major no-bid contracts were awarded within '
            '36 days of inauguration [Finding #4822].</p>'
            '<p><a href="/dossiers/stephen-miller">Stephen Miller</a>, serving as '
            'Deputy Chief of Staff for Policy and Homeland Security Advisor, authored '
            'those executive orders and issued a standing arrest quota of 3,000 per '
            'day. Miller holds $100,001 to $250,000 in Palantir stock — classified '
            'under 18 U.S.C. § 208 as his own because it is held in a minor child\'s '
            'account — while overseeing the ICE deportation policy that drives '
            'Palantir\'s contract volume [Finding #4775]. Ethics officials concluded '
            'he was required to recuse from decisions affecting Palantir; no '
            'recusal documentation has been produced publicly [Finding #4775].</p>'
            '<p>The One Big Beautiful Bill Act (H.R. 1), signed July 4, 2025, '
            'converted the emergency funding baseline into permanent appropriations: '
            '$170.7 billion total through FY2029, $45 billion for new detention '
            'construction, $29.9 billion lump sum for enforcement operations. ICE\'s '
            'annual detention budget rose to at least $14 billion — a 311 percent '
            'increase over FY2024 [Finding #4844]. An internal ICE memorandum dated '
            'February 13, 2026, set a target of 92,600 beds with eight 10,000-bed '
            'mega-centers by November 30, 2026, at a cost of $38.3 billion '
            '[Finding #4844]. CoreCivic\'s CEO stated: "Never in our 42-year company '
            'history have we had so much activity and demand" [Finding #4844].</p>'
            '<p>The procurement vehicles used to execute this expansion included '
            'structures originally designed for unrelated purposes. The Navy\'s '
            'WEXMAC (Worldwide Expeditionary Multiple Award Contract), built for '
            'overseas military logistics, was extended domestically as WEXMAC TITUS '
            '(Territorial Integrity of the United States) and its ceiling raised to '
            '$65 billion, with GEO Group and CoreCivic added as awardees alongside '
            '109 companies [Finding #4704]. An analysis of WEXMAC 2.0 task orders '
            'found that 94.5 percent of the $671 million task order ceiling was '
            'allocated to border and immigration enforcement [Finding #4855].</p>'
        ),
    },
    {
        "id": "financial-conflicts-across-the-dhs-chain",
        "title": "Financial Conflicts Across the DHS Decision-Making Chain",
        "viz": None,
        "content": (
            '<p>Palantir stock holdings run through the DHS decision-making chain '
            'from the White House policy author to department-level procurement '
            'officials. <a href="/dossiers/stephen-miller">Stephen Miller</a> '
            '($100,001–$250,000 in a child\'s brokerage account, attributed to him '
            'under 18 U.S.C. § 208) oversees enforcement policy [Finding #4775]. '
            'Troy Dean Edgar, DHS Deputy Secretary, disclosed Palantir holdings '
            'and agreed to divest while serving as the department\'s number-two '
            'official [Finding #4845]. Pedro Allende, DHS Under Secretary for '
            'Science and Technology, holds $100,001 to $250,000 in Palantir stock '
            'and oversees the directorate that evaluates and procures technology '
            'for ICE, CBP, and TSA — agencies that collectively make DHS Palantir\'s '
            'third-largest customer [Finding #5227]. Robert Law, Under Secretary '
            'for Strategy, Policy, and Plans, agreed to divest [Finding #4845]. '
            'Paul Ingrassia, DHS White House liaison ($1,000–$15,000), and Zachariah '
            'Hoag, special assistant, also held stock [Finding #4845].</p>'
            '<p>The DHS blanket purchase agreement with Palantir, active as of '
            'February 2026, carries a value of over $1 billion [Finding #5209]. '
            'Palantir\'s cumulative ICE contract total stands at $287 million, '
            'and its lifetime federal contracts total $1.4 billion across DoD, '
            'HHS, DHS, DOJ, and Treasury [Finding #5494]. The conflict structure '
            'is not limited to equity positions: Troy Edgar also disclosed holdings '
            'in RTX/Raytheon ($1,000–$15,000), another major DHS contractor, '
            'and had served as a senior advisor to the America First Policy '
            'Institute, a think tank with financial ties to the administration\'s '
            'policy network [Finding #5209].</p>'
            '<p>David Venturella, now serving as the number-two official overseeing '
            'ICE\'s Enforcement and Removal Operations — the division that manages '
            'detention contracts — spent 12 years at GEO Group earning over $6 million '
            'after leaving ICE in 2012. He was granted an ethics waiver by the '
            'administration to return to government in a role directly overseeing '
            'contracts benefiting his former employer [Finding #4776]. GEO Group\'s '
            'revolving door extends to six former ICE officials in senior roles, '
            'including three former ICE directors or deputy directors: Matthew '
            'Albence (Acting ICE Director, now GEO SVP Client Relations), Daniel '
            'Ragsdale (ICE Deputy Director, now GEO SVP Contract Administration), '
            'and Julie Myers Wood (ICE Assistant Secretary, GEO Board of Directors '
            'at approximately $250,000 per year) [Finding #4778].</p>'
            '<p>Kristi Noem, DHS Secretary, disclosed the independent financial '
            'conflict: ProPublica reported that Noem secretly took a personal cut '
            'of donations raised for American Resolve Policy Fund — a nonprofit '
            'promoting her political career — through an $80,000 payment routed '
            'to a Delaware LLC she recently established, which she failed to '
            'disclose on her DHS ethics form [Finding #4780].</p>'
        ),
    },
    {
        "id": "surveillance-data-infrastructure",
        "title": "Surveillance and Data Infrastructure",
        "viz": None,
        "content": (
            '<p>Physical detention is preceded by digital identification through '
            'four interconnected <a href="/dossiers/palantir-technologies">Palantir</a> '
            'platforms: FALCON (analytical platform with FALCON-SA and '
            'FALCON-Roadrunner modules, ingesting SSNs, financial records, call '
            'records, ISP records, and CBP border crossing data); ICM (Investigative '
            'Case Management for case workflows); ELITE (address mapping and '
            'confidence scoring for raid targeting); and ImmigrationOS, a $60 million '
            'two-task-order contract for deportation lifecycle management [Finding #4836] '
            '[Finding #4841]. FALCON\'s scope, documented by Georgetown Law\'s '
            'American Dragnet study, extends to scanning driver\'s license photos '
            'of one in three U.S. adults and accessing driver data for three in '
            'four [Finding #4836].</p>'
            '<p>ELITE provides ICE field agents with a map-based interface to draw '
            'geographic polygons and generate deportation dossiers for everyone '
            'within those boundaries. Confidence scores for each target\'s current '
            'address are calculated from a January 2025 ICE-CMS data-sharing '
            'agreement giving ICE access to personal records of approximately '
            '80 million Medicaid patients — names, addresses, and case data collected '
            'under the social service enrollment process [Finding #4819]. Additional '
            'inputs include DMV records, utility bills, and court records. The '
            'USCIS VOWS contract (October 2025, under $100,000 for Phase 0) extends '
            'Palantir\'s reach from ICE enforcement into USCIS benefits vetting, '
            'creating a Palantir presence at both ends of the immigration adjudication '
            'process [Finding #4820].</p>'
            '<p>The IRS "Unified API," built by Palantir employees installed at the '
            'IRS building, creates a single searchable database of taxpayer records '
            'for cross-agency access. A June 17, 2025, letter from ten congressional '
            'signatories — led by Sen. Wyden and Rep. AOC — to Palantir CEO Alex '
            'Karp alleged Privacy Act violations and demanded answers about whether '
            'tax data was being shared beyond IRS-authorized uses [Finding #4821]. '
            'Palantir\'s own term for the system is "Unified API"; the congressional '
            'letter characterized it as enabling government-wide data fusion '
            '[Finding #4821].</p>'
            '<p>GEO Group\'s subsidiary B.I. Incorporated operates SmartLINK '
            'as the sole provider of ICE\'s Intensive Supervision Appearance Program '
            'for over 21 years. Its current 2-year contract (effective October 1, '
            '2025) covers up to 465,000 participants — more than double the prior '
            'enrollment — and a June 9, 2025, ICE directive mandates ankle monitors '
            '"whenever possible" for all adults in alternative-to-detention programs. '
            'SmartLINK collects continuous GPS location, facial recognition, voice '
            'recognition, contacts, and vehicle data. DHS privacy impact assessments '
            'state a 7-year retention period; FOIA-obtained documents indicate '
            'indefinite retention in practice [Finding #4808] [Finding #4854]. '
            'The algorithmic "absconder" status flag triggers automatically based '
            'on SmartLINK data, and the potential pipeline from that flag into '
            'Palantir ELITE targeting algorithms — where SmartLINK monitoring '
            'data could feed the confidence scoring used to direct future raids — '
            'has not been confirmed or denied by either contractor [Finding #4854].</p>'
        ),
    },
    {
        "id": "palantir-as-cross-domain-bridge",
        "title": "Palantir: The Cross-Domain Infrastructure Layer",
        "viz": None,
        "content": (
            '<p><a href="/dossiers/palantir-technologies">Palantir</a> is the only '
            'company operating at scale across both the DHS enforcement domain and '
            'the defense-tech sector. Its Gotham platform — originally built for '
            'CIA and NSA counterterrorism — serves ICE\'s FALCON, ELITE, and '
            'ImmigrationOS and simultaneously positions as the AI backbone for the '
            'Golden Dome missile defense program\'s command-and-control layer. The '
            'Foundry commercial platform shares a common ontology with Gotham, '
            'enabling interoperability between targeting systems: the same data model '
            'connecting entities across databases works for insurgent targeting and '
            'for immigration targeting with minimal adaptation [Finding #4842].</p>'
            '<p>The personnel pipeline runs through <a href="/dossiers/doge">DOGE</a>. '
            'Clark Minor, a Palantir engineer, was deployed as CIO of HHS — the '
            'agency whose Medicaid data feeds ELITE confidence scores — while '
            'the agency also holds active Palantir contracts [Finding #4829]. '
            'Gregory Barbaccia, a 10-year Palantir veteran, was appointed as the '
            'federal CIO at OMB, which controls federal IT procurement spending '
            'across agencies [Finding #4829]. Allan Mangaser (Theorem/Palantir) '
            'serves as Senior Adviser to the CIO at OMB and GSA; Akash Bobba '
            '(Palantir intern) was placed at OPM and SSA [Finding #5550]. '
            'Palantir alumni are now positioned at the agencies controlling '
            'federal budget (OMB), health data (HHS), and personnel systems '
            '(OPM) while Palantir holds contracts with all three [Finding #5550].</p>'
            '<p>Jacob Helberg, Palantir\'s senior advisor to CEO Alex Karp, was '
            'confirmed as Under Secretary of State for Economic Growth, Energy, and '
            'the Environment in 2025, after donating $1 million to the Trump '
            'campaign and $3.9 million to Trump-aligned PACs and inaugurals '
            '[Finding #4827]. He launched the Pax Silica initiative at State in '
            'December 2025, aimed at AI and supply chain security. Karp himself '
            'moved from donating $360,000 to Biden-Harris in 2023 to $1 million '
            'to MAGA Inc in 2024; Palantir relocated its headquarters from Denver '
            'to Miami on February 17, 2026, following a year of anti-ICE employee '
            'protests at the Denver campus [Finding #4850].</p>'
            '<p>Institutional investors hold coordinated positions across the '
            'entire contractor ecosystem. BlackRock holds 16 percent of GEO Group '
            '(NYSE: GEO), 17 percent of CoreCivic (NYSE: CXW), and 5.45 percent '
            'of Palantir (PLTR). Vanguard holds 10.7 percent of GEO, 11 percent of '
            'CXW, and 9.32 percent of PLTR. State Street holds positions in all '
            'three [Finding #4825]. Cooper Creek Partners holds top positions in '
            'both GEO and CXW; River Road Asset Management holds 8 percent of CXW '
            'and cited immigration enforcement upside in its Q4 2024 investor '
            'letter [Finding #4825].</p>'
        ),
    },
    {
        "id": "revolving-door-and-lobbying-infrastructure",
        "title": "Revolving Door and Lobbying Infrastructure",
        "viz": None,
        "content": (
            '<p>GEO Group\'s lobbying infrastructure is 20-plus years mature. Its '
            'PAC (FEC: C00382150) has operated continuously since 2002, peaking at '
            '$977,000 in 2018 and rebounding in the 2026 cycle after contracting '
            'during Biden-era policy reversals [Finding #4812]. GEO spent $1.37 '
            'million on lobbying in 2025; 10 of its 13 lobbyists in 2024 were '
            'government revolvers [Finding #4805]. Its primary firm, Ballard '
            'Partners, is led by Brian Ballard, Trump\'s 2016 Florida finance '
            'chairman. Continental Strategy\'s Carlos Trujillo, a former Trump '
            'adviser, was hired post-election [Finding #4805]. Attorney General '
            'Pam Bondi earned $390,000 from Ballard Partners lobbying for GEO '
            'Group before her confirmation — she now exercises AG oversight of '
            'federal prisons and is the designated recipient of OCC referrals '
            'against banks that restrict private prison credit [Finding #4805] '
            '[Finding #4847].</p>'
            '<p>The lobbying network extends into congressional oversight. '
            'Former Rep. Martha Roby, who served on the House Appropriations '
            'Committee, is a current GEO Group lobbyist. Border Czar Thomas '
            'Homan received GEO Group consulting fees before his appointment '
            '[Finding #4816]. GEO\'s 60-plus subsidiary structure enables PAC '
            'donations to flow through entities that do not directly hold detention '
            'contracts, distancing the donation source from the contracting '
            'relationship [Finding #4794].</p>'
            '<p>DonorsTrust, a donor-advised fund enabling anonymous charitable '
            'giving, increased its allocation to America First Legal Foundation '
            'from $3.2 million in 2023 to $21.3 million in 2024, part of $195.3 '
            'million DonorsTrust distributed to 300-plus organizations that year '
            '[Finding #4781]. AFL, co-founded by Miller, litigated election '
            'integrity and immigration policy from the outside during 2021–2025; '
            'its donor base remains undisclosed by design [Finding #4781].</p>'
            '<p>The debanking counterattack illustrates the industry\'s political '
            'durability. In 2018–2019, following ESG reviews, JPMorgan, Wells '
            'Fargo, BNP Paribas, Bank of America, PNC, SunTrust, and Fifth Third '
            'Bancorp collectively withdrew approximately $2.4 billion — 87.4 percent '
            'of total industry credit — from GEO Group and CoreCivic [Finding #4847]. '
            'The industry lobbied for legislation requiring non-discriminatory bank '
            'lending. A Trump August 2025 executive order empowered federal banking '
            'regulators to monitor financial institutions for politically motivated '
            'lending denials; a December 2025 OCC report listed private prisons as '
            'an affected sector and threatened AG referrals [Finding #4847].</p>'
        ),
    },
    {
        "id": "maturity-comparison-and-predictive-value",
        "title": "Maturity Relative to Defense-Tech Capture Patterns",
        "viz": None,
        "content": (
            '<p>The DHS enforcement capture pattern is 20-plus years older than the '
            'defense-tech capture pattern emerging in 2025–2026 around Golden Dome. '
            'The maturity difference is visible in five structural indicators. First, '
            'revolving door depth: GEO Group has placed six former ICE officials in '
            'senior roles, including three former directors or deputy directors, '
            'versus defense-tech companies on first-cycle government appointments '
            '[Finding #4778]. Second, financial resilience: the private prison '
            'industry survived the 2019 ESG debanking of $2.4 billion in credit '
            'and leveraged the episode into political pressure that produced '
            'regulatory protection under the second Trump administration; defense-tech '
            'companies have not been tested against comparable financial pressure '
            '[Finding #4847]. Third, PAC infrastructure: GEO\'s PAC has operated '
            'since 2002 with $6.86 million in total receipts; defense-tech PACs '
            'are nascent [Finding #4812]. Fourth, subsidiary architecture: GEO\'s '
            '60-plus subsidiaries create channels for political giving through '
            'non-contracting entities; most defense-tech companies operate as '
            'single corporate entities [Finding #4794]. Fifth, institutional '
            'investor penetration: 342 institutions hold GEO and 492 hold CXW; '
            'defense-tech companies have smaller institutional bases [Finding #4825].</p>'
            '<p>Palantir is the exception to the defense-vs-enforcement division: '
            'it operates the same Gotham platform, the same Forward Deployed '
            'Engineer model, and the same personnel pipeline across both domains. '
            'The $287 million in ICE contracts and the $1 billion Golden Dome '
            'C2 positioning draw on the same product architecture and the same '
            'government relationships. In this respect the DHS pattern is not '
            'separate from the defense-tech pattern — Palantir connects them '
            'structurally, using the same data model that targets insurgents to '
            'target immigrants [Finding #4857] [Finding #4842].</p>'
        ),
    },
]

OPEN_QUESTIONS = [
    (
        "Does a documented data feed exist between GEO Group's B.I. Incorporated "
        "SmartLINK monitoring system — collecting continuous GPS, facial recognition, "
        "voice, contacts, and vehicle data on 253,875 monitored individuals — and "
        "Palantir ELITE's confidence-scoring inputs? The June 9, 2025, ICE ATD "
        "directive expanded SmartLINK deployment, and ELITE ingests multiple "
        "real-time data streams; whether SmartLINK's AI-flagged absconder status "
        "triggers an ELITE update has not been confirmed or denied by either "
        "contractor or ICE. [Finding #4854] [Finding #4819]"
    ),
    (
        "David Venturella received an ethics waiver to serve as the number-two "
        "official at ICE ERO overseeing detention contracts that benefit GEO Group, "
        "his employer of 12 years. What are the specific terms of that waiver — "
        "which decisions is he recused from, who issues those recusals, and has "
        "he participated in any ImmigrationOS, ISAP, or detention IDIQ task order "
        "decisions since taking office? [Finding #4776]"
    ),
    (
        "The Palantir IRS Unified API — a centralized taxpayer record database "
        "built by Palantir engineers at the IRS — is the subject of the June 2025 "
        "Wyden-AOC congressional letter alleging Privacy Act violations. Has IRS "
        "responded formally to that letter? Has the Unified API been used to "
        "generate leads for immigration enforcement actions, and if so, under "
        "what legal authority? [Finding #4821]"
    ),
    (
        "Miller, Edgar, Allende, Law, Ingrassia, and Hoag all held Palantir stock "
        "while overseeing enforcement policy or DHS technology procurement. Which "
        "of these officials filed formal recusal certifications, which divested "
        "and on what schedule, and which continued to participate in "
        "Palantir-related procurement decisions after disclosure? The DHS "
        "$1 billion blanket purchase agreement with Palantir, active as of "
        "February 2026, was approved during the period when at least four of "
        "these officials held undivested stock. [Finding #4845] [Finding #5209] "
        "[Finding #5227]"
    ),
    (
        "DonorsTrust increased its allocation to America First Legal Foundation "
        "from $3.2 million in 2023 to $21.3 million in 2024 — a 565 percent "
        "increase. AFL co-founder Miller returned to the White House in January "
        "2025; AFL co-founder Gene Hamilton became Deputy White House Counsel. "
        "Does DonorsTrust's 2024 allocation to AFL reflect pre-arranged giving "
        "timed to the transition, and do the undisclosed DonorsTrust donors "
        "overlap with GEO Group, CoreCivic, or Palantir institutional investors? "
        "[Finding #4781]"
    ),
    (
        "Gregory Barbaccia, 10-year Palantir veteran and now federal CIO at OMB, "
        "controls federal IT spending approvals across all agencies. Clark Minor, "
        "Palantir engineer and now CIO of HHS, controls the agency whose Medicaid "
        "database feeds ELITE. Neither has publicly disclosed the scope of their "
        "recusals from Palantir-related procurement. Has OMB's federal CIO "
        "participated in approving or reviewing the DHS $1 billion Palantir BPA, "
        "and has HHS's CIO participated in the ICE-CMS data-sharing agreement "
        "administration? [Finding #4829]"
    ),
]

APPLICABLE_MODELS = [
    "policy-to-profit",
    "revolving-door",
    "regulatory-capture",
    "procurement-capture",
    "conflict-of-interest",
    "data-as-leverage",
    "manufactured-dependency",
    "pay-to-play",
]


def main():
    with open(DOSSIER_PATH) as f:
        data = json.load(f)

    existing_curation = data.get("curation", {})

    data["curation"] = {
        **existing_curation,
        "lead": LEAD,
        "system_role": SYSTEM_ROLE,
        "sections": SECTIONS,
        "open_questions": OPEN_QUESTIONS,
        "applicable_models": APPLICABLE_MODELS,
        "curated_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(DOSSIER_PATH, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    print(f"Curation written to {DOSSIER_PATH}")
    print(f"  lead: {len(LEAD)} chars")
    print(f"  system_role: {len(SYSTEM_ROLE)} chars")
    print(f"  sections: {len(SECTIONS)}")
    print(f"  open_questions: {len(OPEN_QUESTIONS)}")
    print(f"  applicable_models: {APPLICABLE_MODELS}")


if __name__ == "__main__":
    main()
