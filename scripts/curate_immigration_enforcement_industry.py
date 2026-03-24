#!/usr/bin/env python3
"""
Curation script for Immigration Enforcement Industry dossier.
Writes the `curation` block: lead, system_role, sections, open_questions, applicable_models.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DOSSIER_PATH = Path(__file__).parent.parent / "content/dossiers/immigration-enforcement-industry.json"

LEAD = (
    '<p>The immigration enforcement industry is a group of private companies that design, '
    'operate, and supply the physical and digital infrastructure of the U.S. deportation '
    'system. Its two dominant detention operators — GEO Group (NYSE: GEO, $2.6B revenue '
    '2025) and CoreCivic (NYSE: CXW, $2.2B revenue 2025) — together account for '
    'approximately 90 percent of all U.S. immigration detention beds operated by for-profit '
    'corporations [Finding #4844]. The sector expanded dramatically under the second Trump '
    'administration: the One Big Beautiful Bill Act (HR 1), signed July 4, 2025, allocated '
    '$170.7 billion to immigration enforcement through FY2029, including $45 billion '
    'specifically for new detention construction [Finding #4844]. An ICE internal memorandum '
    'dated February 13, 2026, projected a target of 92,600 detention beds with eight '
    'mega-centers of 10,000 beds each by November 30, 2026, at a cost of $38.3 billion '
    '[Finding #4844].</p>'
    '<p>GEO Group and CoreCivic donated a combined $2.8 million to the Trump 2024 '
    'presidential campaign and inauguration, then received nine or more new or expanded '
    'federal contracts within months of the inauguration [Finding #4816]. The top ten ICE '
    'contractors collectively received approximately $3.8 billion of a $5.4 billion total '
    'procurement pool — a 69 percent increase since the January 2025 inauguration '
    '[Finding #4853]. Beyond physical detention, surveillance and data infrastructure '
    'is supplied primarily by <a href="/dossiers/palantir-technologies">Palantir '
    'Technologies</a>, which holds $287 million in cumulative ICE contracts including '
    'a $30 million sole-source award for ImmigrationOS [Finding #4853]. Deportation '
    'logistics are dominated by CSI Aviation, which holds a five-year contract with '
    'a $3.6 billion ceiling and received $1.2 billion for deportation flights '
    '[Finding #4853].</p>'
)

SYSTEM_ROLE = (
    "The immigration enforcement industry functions as the physical and digital "
    "infrastructure layer of the U.S. deportation system, converting federal enforcement "
    "mandates into contracted services across detention, surveillance, skip-tracing, and "
    "transportation. Its structural position connects White House policy directives through "
    "congressional appropriations, executive agency contracting, and lobbying channels back "
    "to the same corporate actors that financially backed the administration authorizing the "
    "contracts — forming a closed procurement circuit where political investment precedes "
    "and tracks contract awards. The industry's growth since January 2025 is denominated "
    "in contract ceilings, not just capacity: WEXMAC TITUS raised its ceiling to $65 billion "
    "by adding GEO Group and CoreCivic as awardees on a Navy expeditionary logistics vehicle "
    "originally designed for overseas military operations, illustrating how domestic enforcement "
    "expansion has been routed through pre-existing defense procurement vehicles."
)

SECTIONS = [
    {
        "id": "procurement-circuit",
        "title": "The Procurement Circuit: Policy, Appropriations, and Contract Awards",
        "content": (
            '<p>The financial structure linking policy to revenue runs through three nodes: '
            'White House policy directives, congressional appropriations, and federal contract '
            'awards. <a href="/dossiers/stephen-miller">Stephen Miller</a>, serving as Deputy '
            'Chief of Staff for Policy and Homeland Security Advisor, is described by reporting '
            'as "calling the shots at DHS" and drafted executive orders directing ICE to pursue '
            'mass arrests at a target rate of 3,000 per day [Finding #4816]. Those arrest '
            'targets generate detention bed demand, which the One Big Beautiful Bill Act '
            '(HR 1), signed July 4, 2025, satisfied with $45 billion in new detention '
            'construction funding — part of $170.7 billion in total immigration enforcement '
            'appropriations through FY2029 [Finding #4844]. The bill nearly doubles the '
            'detention population ceiling to 116,000 by 2029 and brings ICE\'s annual '
            'detention budget to at least $14 billion, a 311 percent increase over FY2024 '
            '[Finding #4844].</p>'
            '<p>GEO Group and CoreCivic donated a combined $2.8 million to the Trump 2024 '
            'election and inaugural — GEO Group alone gave $1 million to the MAGA super PAC, '
            '$775,000 to the Republican Congressional Leadership Fund, and $500,000 to the '
            'Senate Leadership Fund [Finding #4816]. Both companies doubled their inaugural '
            'donations from 2017 to 2025. CREW documented that within months of the '
            'inauguration, each company received nine or more new or expanded ICE contracts '
            '[Finding #4844]. CoreCivic\'s ICE revenue doubled year-over-year in Q4 2025 — '
            'from $120.3 million to $244.7 million — while GEO Group secured over $1 billion '
            'in contracts since inauguration, including a $1 billion, 15-year no-bid award '
            'for the Delaney Hall facility in New Jersey [Finding #4853]. CoreCivic\'s CEO '
            'stated: "Never in our 42-year company history have we had so much activity and '
            'demand" [Finding #4844].</p>'
            '<p>The top ten ICE contractors collectively received approximately $3.8 billion '
            'of a $5.4 billion total — 70 percent market concentration, up 69 percent since '
            'January 20, 2025 [Finding #4853]. GEO Group operates across all three ICE '
            'contract vehicles through subsidiaries: GEO Group itself on the detention IDIQ '
            '(70CDCR25D) with $200 million-plus in task orders across Adelanto, Aurora, '
            'Tacoma, and other facilities; B.I. Incorporated on the skip-tracing IDIQ '
            '($121.8 million ceiling); and GEO on WEXMAC TITUS [Finding #4654]. '
            'CSI Aviation holds a five-year deportation flight contract with a ceiling of '
            '$3.6 billion and received $1.2 billion to date, including $262.9 million in '
            'FY2025 alone [Finding #4853].</p>'
            '<p>The procurement vehicles themselves have expanded beyond their original '
            'design parameters. The Navy\'s WEXMAC (Worldwide Expeditionary Multiple Award '
            'Contract), originally built for overseas military logistics, was extended '
            'domestically as WEXMAC TITUS (Territorial Integrity of the United States). '
            'Its ceiling was raised to $65 billion with GEO Group and CoreCivic added as '
            'awardees among 109 companies [Finding #4704]. A separate analysis of 523 '
            'WEXMAC 2.0 task orders found that 94.5 percent of the $0.671 billion task '
            'order ceiling — $0.579 billion — was allocated to border and immigration '
            'enforcement [Finding #5385]. DoD task orders routed through WEXMAC funded '
            'military deployments to interior U.S. cities: Chicago ($0.7 million, Response '
            'AI), Portland ($1 million, Bodwe-KVG), and St. Paul ($0.5 million, Response '
            'AI via ERO), with contract descriptions using "wrap around" language that '
            'obscures the immigration enforcement purpose [Finding #5403].</p>'
        ),
    },
    {
        "id": "lobbying-revolving-door",
        "title": "Lobbying Infrastructure and Revolving Door",
        "content": (
            '<p>GEO Group and CoreCivic collectively spent $5.3 million on lobbying in 2025 '
            '— CoreCivic\'s $3.69 million was its highest since 2007 [Finding #4851]. Both '
            'companies lobby directly on DHS appropriations bills, the Laken Riley Act '
            '(S.5/HR.29), and alternatives to detention while formally stating they do not '
            'lobby for or against immigration enforcement policies [Finding #4851].</p>'
            '<p>GEO Group\'s primary lobbying firm is Ballard Partners, led by Brian Ballard, '
            'Trump\'s 2016 Florida finance chairman. GEO also retains Continental Strategy '
            '(Carlos Trujillo, former Trump adviser and Florida state congressman, hired '
            'after the 2024 election) and a firm led by Ches McDowell, described in reporting '
            'as "Donald Trump Jr.\'s avowed hunting buddy." Ten of GEO Group\'s thirteen '
            'lobbyists in 2024 were government revolvers [Finding #4851].</p>'
            '<p>The revolving door produces direct institutional overlap between GEO Group\'s '
            'lobbying interests and law enforcement oversight. Attorney General Pam Bondi '
            'earned $390,000 from Ballard Partners lobbying for GEO Group before her '
            'confirmation — she now holds AG oversight of DOJ prisons. Former Representative '
            'Martha Roby, who served on the House Appropriations Committee, is a current GEO '
            'Group lobbyist [Finding #4851]. Thomas Homan, appointed Border Czar, received '
            'GEO Group consulting fees before his appointment [Finding #4816]. The OCC\'s '
            'December 2025 report on bank debanking specifically listed private prisons as '
            'an affected sector and threatened referrals to the Attorney General — the same '
            'AG who previously lobbied for GEO [Finding #4847].</p>'
            '<p>CSI Aviation entered lobbying for the first time since 2018 in June 2025, '
            'spending $230,000 via Navigators Global. Its lobbying team includes Chris Cox, '
            'a former White House deputy assistant for legislative affairs [Finding #4851]. '
            'The firm holds a deportation flight contract with a maximum value of $3.6 billion '
            '[Finding #4853].</p>'
            '<p>The skip-tracing contract layer, awarded in December 2025 with ceilings '
            'totaling over $1.1 billion across twelve companies, included multiple '
            'newly-registered entities with minimal operational history: Fraud Inc '
            '(registered November 2025, apartment address in Houston, $25.6 million); '
            'Government Support Services (residential house in the Florida panhandle, '
            '$55.6 million); National Protective Services (firearms training strip mall, '
            '$68.2 million); Gravitas Professional Services (three-person Ohio firm, '
            '$32.1 million) [Finding #4611]. The largest awards went to established firms: '
            'Capgemini ($365.8 million), Bluehawk ($201.4 million), SOS International '
            '($123.2 million), and B.I. Incorporated/GEO Group ($121.8 million) '
            '[Finding #4611].</p>'
        ),
    },
    {
        "id": "surveillance-data-layer",
        "title": "Surveillance and Data Infrastructure",
        "content": (
            '<p>Physical detention is preceded by digital identification. '
            '<a href="/dossiers/palantir-technologies">Palantir Technologies</a> holds '
            '$287 million in cumulative ICE contracts [Finding #4853]. Its ICE technology '
            'stack comprises four platforms: FALCON (analytical platform based on Gotham, '
            'including FALCON-SA and FALCON-Roadrunner modules for trend analysis and '
            'investigative lead generation); ICM (Investigative Case Management, structuring '
            'case workflows); ELITE (address mapping and confidence scoring for deportation '
            'targeting); and ImmigrationOS, a $30 million sole-source contract for 2025–2027 '
            '[Finding #4632, Finding #4853]. ELITE ingests data from a January 2025 '
            'ICE-CMS data-sharing agreement that provides ICE access to personal records '
            'of approximately 80 million Medicaid patients, including names, addresses, '
            'and case data [Finding #4641].</p>'
            '<p><a href="/dossiers/doge">DOGE</a> built a parallel immigration master '
            'database linking SSA, IRS, and DHS data, and converted the SAVE '
            '(Systematic Alien Verification for Entitlements) system from a single-query '
            'benefits verification tool to a push-system allowing bulk scanning of voter '
            'rolls by election officials [Finding #5802]. For the first time, officials '
            'can query SAVE using Social Security numbers to look up U.S.-born citizens '
            '[Finding #5490]. DOGE also brokered data-sharing agreements with IRS and HUD '
            'for noncitizen data and accessed CMS databases containing names, dates of '
            'birth, SSNs, phone numbers, addresses, race, sex, diagnosis codes, procedure '
            'codes, and medical notes [Finding #5490].</p>'
            '<p>Stephen Miller holds between $100,000 and $250,000 in Palantir stock — '
            'held in a brokerage account for one of his three children — while directly '
            'overseeing ICE deportation policy [Finding #4627]. Ethics officials flagged '
            'this position as a conflict of interest. Miller\'s office holds weekly meetings '
            'with DHS and DOJ leadership on enforcement plans [Finding #6527].</p>'
            '<p>BI Incorporated, a GEO Group subsidiary, received a contract worth up to '
            '$1 billion for the Intensive Supervision Appearance Program (ISAP), with '
            'capacity for 465,000 participants — more than double the prior enrollment '
            'of 183,000 [Finding #4853]. ISAP uses SmartLINK GPS monitoring as an '
            'alternative to physical detention; the program\'s expansion means GEO Group '
            'captures revenue from both detained and non-detained populations in the '
            'enforcement pipeline.</p>'
        ),
    },
    {
        "id": "banking-regulatory-protection",
        "title": "Banking Access and Regulatory Protection",
        "content": (
            '<p>Between 2018 and 2019, following ESG reviews and site visits, seven major '
            'banks committed to not renewing financing to private prison operators: '
            'JPMorgan Chase, Wells Fargo, SunTrust, BNP Paribas, Fifth Third Bancorp, '
            'PNC Bank, and Bank of America. The combined credit commitments withdrawn '
            'totaled approximately $2.4 billion — an 87.4 percent shortfall of all credit '
            'available to the industry [Finding #4847]. GEO Group and CoreCivic responded '
            'by lobbying Congress to pass legislation requiring banks to provide services '
            'regardless of political considerations [Finding #4847].</p>'
            '<p>The Trump administration intervened on the industry\'s behalf through two '
            'mechanisms. An August 2025 executive order empowered federal banking regulators '
            'including the SBA to monitor financial institutions for politically motivated '
            'lending denials [Finding #4847]. In December 2025, the Treasury\'s Office of '
            'the Comptroller of the Currency published a report scrutinizing nine banks, '
            'specifically listing private prisons as a sector affected by debanking and '
            'stating intent to make referrals to the Attorney General [Finding #4847]. '
            'The AG designated to receive those referrals — Pam Bondi — had earned '
            '$390,000 lobbying for GEO Group at Ballard Partners before her confirmation '
            '[Finding #4851].</p>'
        ),
    },
    {
        "id": "capital-ownership",
        "title": "Institutional Capital Ownership Overlap",
        "content": (
            '<p>The three largest index fund managers hold structural positions across '
            'the full enforcement ecosystem. BlackRock holds 16 percent of GEO Group '
            '(NYSE: GEO), 17 percent of CoreCivic (NYSE: CXW), and 5.45 percent of '
            'Palantir (PLTR). Vanguard holds 10.7 percent of GEO, 11 percent of CXW, '
            'and 9.32 percent of PLTR. State Street holds positions in all three '
            '[Finding #4825]. As of September 2025, 342 institutions held GEO and '
            '492 institutions held CXW [Finding #4825].</p>'
            '<p>The same passive capital pools that own the detention operators '
            'simultaneously hold nearly 20 percent of Palantir, whose $287 million in '
            'ICE contracts provide the targeting infrastructure that fills detention '
            'beds [Finding #4825]. Active managers have made concentrated sector bets: '
            'Cooper Creek Partners holds top positions in both GEO and CXW; River Road '
            'Asset Management holds 8 percent of CXW and cited immigration enforcement '
            'upside in its Q4 2024 investor letter; Barrow Hanley holds 3 percent of '
            'GEO ($73 million); Pentwater Capital holds 11.7 million or more GEO shares '
            '[Finding #4825].</p>'
            '<p>GEO Group stated that Trump\'s expansion plans could fill 18,000 empty '
            'beds for $400 million in additional annual revenue [Finding #4844]. For '
            'passive index holders, increased enforcement activity translates directly '
            'into higher earnings per share across multiple portfolio positions '
            'simultaneously — a structural alignment of financial interest with '
            'enforcement volume that does not require any active coordination.</p>'
        ),
    },
]

OPEN_QUESTIONS = [
    (
        "What data flows, if any, exist between GEO Group's BI Incorporated SmartLINK "
        "GPS monitoring system — which now tracks 465,000 ISAP participants — and "
        "Palantir's ImmigrationOS and ELITE platforms? Both systems are under active "
        "ICE contracts but no public documentation confirms a direct data feed between them."
    ),
    (
        "CSI Aviation entered ICE deportation flight contracting with a $3.6 billion "
        "ceiling contract. Its corporate ownership structure is not publicly documented. "
        "Who are CSI Aviation's beneficial owners, and do any of them have prior "
        "financial relationships with the administration or with GEO Group or CoreCivic?"
    ),
    (
        "The December 2025 OCC debanking report threatened AG referrals for banks that "
        "denied services to private prisons. Did the OCC formally refer any bank to "
        "AG Bondi, and if so, which banks and for what conduct?"
    ),
    (
        "Ten of GEO Group's thirteen 2024 lobbyists are government revolvers, and six "
        "of CoreCivic's ten are revolvers. What specific prior government positions did "
        "each hold, and which of those positions involved oversight of ICE detention "
        "contracts or DHS appropriations?"
    ),
    (
        "The skip-tracing contract layer awarded $1.1 billion to twelve companies "
        "in December 2025, including four newly-registered entities with minimal "
        "operational footprints. Were these entities formed specifically to receive "
        "federal contracts, and do any share officers, addresses, or investors with "
        "established defense or prison contractors?"
    ),
]

APPLICABLE_MODELS = [
    "manufactured-dependency",
    "policy-to-profit",
    "revolving-door",
    "regulatory-capture",
    "procurement-capture",
]


def main():
    with open(DOSSIER_PATH) as f:
        data = json.load(f)

    # Preserve the existing section_suggestions if present
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
