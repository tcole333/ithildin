#!/usr/bin/env python3
"""Write curation fields into content/dossiers/palmer-luckey.json"""
import json
from datetime import datetime, timezone

DOSSIER_PATH = "content/dossiers/palmer-luckey.json"

with open(DOSSIER_PATH) as f:
    dossier = json.load(f)

curation = dossier.get("curation", {})

# ── LEAD ────────────────────────────────────────────────────────────────────
curation["lead"] = (
    "<p>Palmer Luckey (born 1992) is the founder and CEO of "
    "<a href=\"/dossiers/anduril-industries\">Anduril Industries</a>, a defense technology "
    "contractor valued at $30.5 billion (June 2025) that holds or is pursuing the Army's "
    "$22 billion IVAS augmented-reality headset program, the TITAN targeting system, "
    "and a position in the Golden Dome missile defense consortium. He sold Oculus VR "
    "to Facebook for approximately $2 billion in 2014, was fired from Facebook in 2017 "
    "following exposure of his funding of a pro-Trump social media operation, and "
    "co-founded Anduril with <a href=\"/dossiers/trae-stephens\">Trae Stephens</a> that same year "
    "[Finding #4575].</p>"
    "<p>FEC records confirm $921K in political donations, 81% directed to Republican "
    "committees and candidates [Finding #5394]. The giving is concentrated on defense "
    "oversight infrastructure: Senate Armed Services Committee members received $17K "
    "(Ken Calvert, HASC), $3.5K each to Tim Scott, Dan Sullivan, Mike Rogers, and Jim Mullin "
    "(all SASC), and $1.5K each to Cindy Hyde-Smith and Jim Banks — all members or "
    "chair-track legislators for the committees that appropriate Pentagon funds "
    "[Finding #5394]. Luckey simultaneously co-founded "
    "<a href=\"/dossiers/erebor-bank\">Erebor Bank</a> with Joe Lonsdale; the bank's investor "
    "fundraising memo identified Luckey's political network as a factor in securing "
    "regulatory approval from the OCC [Finding #2792].</p>"
    "<p>China sanctioned Luckey in December 2025 — alongside nine other US defense executives "
    "and twenty companies — over Taiwan arms sales. Russia's MFA lists him under "
    "OpenSanctions entity Q16269109 [Finding #4570]. He has been sanctioned by both "
    "major US strategic competitors simultaneously.</p>"
)

# ── SYSTEM ROLE ──────────────────────────────────────────────────────────────
curation["system_role"] = (
    "Luckey occupies the junction between Silicon Valley venture capital and the US defense "
    "procurement system: he converted Oculus exit capital into a defense contractor structured "
    "from the outset to compete directly against Lockheed, Raytheon, and Northrop on autonomous "
    "and AI-enabled weapons programs, then built a political giving strategy targeting the "
    "specific legislators who appropriate and oversee Pentagon budgets. "
    "His co-founding of Erebor Bank with Joe Lonsdale extends that position into financial "
    "infrastructure for the defense-tech and crypto ecosystem. As under-50 leadership of a "
    "company that already holds the IVAS novation and participates in Golden Dome, he is the "
    "central individual in the Silicon Valley defense contractor tier that the Trump-era Pentagon "
    "has described as the new prime."
)

# ── SECTIONS ─────────────────────────────────────────────────────────────────
curation["sections"] = [
    {
        "id": "anduril-and-the-new-prime-thesis",
        "title": "Anduril and the New Prime Thesis",
        "viz": None,
        "content": (
            "<p>Luckey co-founded Anduril in 2017 after his firing from Facebook. The company's "
            "address of record is 1375 Sunflower Ave, Costa Mesa, CA [Finding #2684]. The founding "
            "team included <a href=\"/dossiers/trae-stephens\">Trae Stephens</a>, a "
            "<a href=\"/dossiers/peter-thiel\">Peter Thiel</a> Founders Fund partner who had led "
            "the DOD transition for Trump in 2016; Stephens serves as Executive Chairman while "
            "Luckey is CEO [Finding #2752]. The explicit company thesis — publicly stated by Luckey "
            "and Stephens — is that legacy defense primes are too bureaucratic and slow to build "
            "AI and autonomous systems, and that a software-native contractor can outcompete them "
            "on performance and speed while winning the same program budgets.</p>"
            "<p>That thesis has been validated by contract awards. The most consequential is the "
            "April 2025 novation of Microsoft's $22 billion IVAS contract: after Microsoft "
            "discontinued HoloLens production in 2024 and the program faced years of delays, "
            "Anduril absorbed the contract along with Microsoft employees, hardware, IP, and "
            "facilities. The software release cycle was subsequently reduced from 180 days to "
            "18 hours [Finding #4679]. Anduril also holds a position on the TITAN targeting "
            "system (jointly with <a href=\"/dossiers/palantir-technologies\">Palantir</a>), "
            "a SOCOM counter-drone contract, a Navy counter-drone program, and an autonomous "
            "aircraft program with General Atomics. Revenue doubled from $1 billion in 2024 to "
            "$2 billion in 2025, and valuation reached a reported $60–91 billion range at the "
            "time of Golden Dome contract announcements [Finding #4734].</p>"
            "<p>The Pentagon official most directly positioned to benefit Anduril is "
            "<a href=\"/dossiers/emil-michael\">Emil Michael</a>, appointed Under Secretary of "
            "Defense for Research and Engineering. Michael's six stated technology priorities — "
            "autonomous systems, AI-enabled targeting, counter-drone, augmented reality for "
            "soldiers, next-generation aircraft, and missile defense — map directly onto Anduril's "
            "product portfolio. As USD(R&E), Michael oversees the IVAS program, TITAN, Golden Dome, "
            "and Altius production [Finding #2758]. Separately, DHS CIO Antoine McCord holds "
            "$100M–$250M in Anduril stock — a disclosed financial interest in a contractor that "
            "operates within his department's technology portfolio [Finding #2944].</p>"
        ),
    },
    {
        "id": "political-giving-architecture",
        "title": "Political Giving Architecture",
        "viz": None,
        "content": (
            "<p>Luckey's political giving follows a logic distinct from general Republican "
            "partisanship: it targets the institutional committees and party infrastructure "
            "that control defense appropriations. FEC records show $921K total, 81% Republican "
            "[Finding #5394]. The largest single recipient was the Republican National Committee "
            "at $250K. The next tier — $127K to One Team Senate Majority, $89K to Grow the "
            "Majority, $88K to WinRed, $62K to NRCC, $52K to NRSC — consists entirely of "
            "institutional party infrastructure rather than any individual candidate or "
            "ideological PAC [Finding #5394].</p>"
            "<p>The committee-specific donations follow the defense oversight map: $17K to "
            "Ken Calvert (HASC), $3.5K to Tim Scott (SASC), $3.5K to Dan Sullivan (SASC), "
            "$3.5K to Mike Rogers (SASC), $3.5K to Jim Mullin (SASC), $1.5K to Cindy Hyde-Smith "
            "(SASC), $1.5K to Jim Banks [Finding #5394]. FEC records contain no Trump-vehicle "
            "donations. The pattern is giving to legislators with direct authority over Pentagon "
            "budget lines while leaving Trump-adjacent vehicles to others in the network.</p>"
            "<p>Earlier in this giving history, Luckey funded Nimble America — a pro-Trump "
            "501(c)(4) — in the 2016 cycle at $10K while operating under the Reddit pseudonym "
            "'NimbleRichMan.' The exposure of that arrangement contributed directly to his 2017 "
            "firing from Facebook/Meta [Finding #4575]. By 2024 he donated $400K to Trump's "
            "campaign and co-hosted a fundraiser at John Word's home with a reported $100K-per-person "
            "admission [Finding #4690]. Anduril's internal political architecture is split: "
            "CEO Brian Schimpf donated $245K, 100% to Democratic recipients including ActBlue "
            "($137K). Luckey's $921K ran 81% Republican. The bipartisan structure means Anduril "
            "has documented financial relationships with both parties' leadership [Finding #5406].</p>"
            "<p>Luckey also established a formal Anduril PAC that receives employee contributions. "
            "Key employee donors to the PAC include Chris Brose (former Senate Armed Services "
            "Committee staff director), Gregory Kausner (former DoD official), Matthew Steckman "
            "(COO), and Megan Milam (registered Anduril lobbyist) [Finding #4690]. The PAC "
            "creates a second giving channel that extends political participation to Anduril's "
            "senior defense-connected staff. His participation in the Rockbridge Network — a "
            "conservative donor coordinating organization co-founded by JD Vance — as a speaker "
            "places him in the same donor infrastructure as Vance and David Sacks "
            "[Finding #2977] [Finding #5448].</p>"
        ),
    },
    {
        "id": "thiel-network-and-key-relationships",
        "title": "Thiel Network and Key Relationships",
        "viz": "ego_network",
        "content": (
            "<p>The structural origin of Anduril is a 2014 Founders Fund retreat where Luckey "
            "met <a href=\"/dossiers/trae-stephens\">Trae Stephens</a>, then a Founders Fund "
            "partner [Finding #2752]. "
            "<a href=\"/dossiers/peter-thiel\">Peter Thiel</a>'s Founders Fund has been an "
            "Anduril investor since 2017 and led the Series G round in June 2025 with a "
            "reported $2.5 billion check [Finding #2687]. Thiel's fund also backed "
            "<a href=\"/dossiers/erebor-bank\">Erebor Bank</a> alongside Lux Capital, 8VC, "
            "and Haun Ventures [Finding #4753].</p>"
            "<p>Josh Wolfe, co-founder of Lux Capital and an early Anduril backer, organized "
            "Luckey's February 2026 visit to Israel. The trip was two days, conducted without "
            "advance press disclosure, and included meetings with Prime Minister Netanyahu, "
            "senior Israeli defense officials, and ten Israeli defense startups — Smart Shooter, "
            "Kela, Skana Robotics, Regulus, Magnus Metal, eyesAtop, and AriEV — mediated by "
            "Israel's Directorate of Defense Research and Development [Finding #4571]. The visit "
            "combined Anduril product marketing with business development for potential Israeli "
            "partnerships.</p>"
            "<p>The co-founding relationship with Joe Lonsdale at Erebor Bank connects Luckey "
            "to the Palantir founding network: Lonsdale co-founded Palantir with Thiel in 2003 "
            "and later founded 8VC. Erebor's fundraising memo cited Luckey's political network "
            "as a factor in regulatory approval — the OCC granted a conditional charter in "
            "October 2025 and a full charter in February 2026, a four-month approval that "
            "bank charter observers noted as rapid [Finding #2792] [Finding #4753]. The OCC "
            "Comptroller who approved the charter, Jonathan Gould, had a prior background at "
            "Bitfury (crypto infrastructure), consistent with Erebor's stated stablecoin and "
            "crypto-collateralized loan plans.</p>"
            "<p>Coordinated FEC donation patterns with Keith Rabois — to Yvette Herrell, Take "
            "Back The House 2022, and WinRed — reflect the broader Founders Fund political "
            "giving coordination that has been documented across the tech-right network "
            "[Finding #2980]. Rabois is a former Founders Fund GP and PayPal Mafia participant.</p>"
        ),
    },
    {
        "id": "sanctions-and-international-exposure",
        "title": "Sanctions and International Exposure",
        "viz": None,
        "content": (
            "<p>China's Ministry of Foreign Affairs sanctioned Luckey in December 2025, "
            "alongside nine other US defense executives and twenty companies, over arms sales "
            "to Taiwan. The sanctions froze any assets within Chinese jurisdiction and barred "
            "entry to China. Russia's Ministry of Foreign Affairs lists him on the RU-MFA "
            "sanctions list, catalogued in the OpenSanctions dataset as entity Q16269109 "
            "[Finding #4570]. Both sanctions were imposed for defense industry activities "
            "rather than financial or political conduct.</p>"
            "<p>Luckey's public response — \"I want to thank my family, my team, and my Lord "
            "Jesus Christ for this award\" — was posted on X and widely reprinted "
            "[Finding #4570]. The dual-adversary sanctions, combined with the February 2026 "
            "Netanyahu meeting, are the two primary data points establishing his active role "
            "in US defense export and alliance relationships beyond domestic contracting.</p>"
        ),
    },
    {
        "id": "litigation-record",
        "title": "Litigation Record",
        "viz": None,
        "content": (
            "<p>Three proceedings define Luckey's litigation record. The ZeniMax Media v. "
            "Oculus VR case (N.D. Tex. 3:14-cv-01849) resulted in a jury finding $500M in "
            "damages against Facebook; Luckey was personally ordered to pay $50M for a "
            "non-disclosure agreement violation arising from his pre-acquisition sharing of "
            "Oculus technology [Finding #4573]. The Total Recall Technologies v. Palmer Luckey "
            "case (N.D. Cal. 3:15-cv-02281, appealed at 9th Cir. 19-15544) was a contract "
            "dispute over the origins of Oculus VR itself [Finding #4573]. Both cases relate "
            "to the Oculus period and are closed.</p>"
            "<p>Iron Bird LLC v. Anduril Industries (D. Del. 1:25-cv-00210) was filed in "
            "February 2025 alleging patent infringement and terminated in March 2025 — a "
            "rapid resolution that may reflect settlement rather than adjudication on the "
            "merits [Finding #4573].</p>"
        ),
    },
]

# ── OPEN QUESTIONS ───────────────────────────────────────────────────────────
curation["open_questions"] = [
    (
        "The Erebor Bank fundraising memo cited Luckey's 'political network' as a factor in "
        "securing OCC charter approval. What specific contacts or communications, if any, "
        "passed between Luckey's network and OCC Comptroller Jonathan Gould or his office "
        "during the October 2025–February 2026 charter review period? Did Adam Cohen, "
        "who moved from Skadden (Erebor's charter counsel) to OCC Chief Counsel in August 2025, "
        "participate in reviewing the Erebor application? [Finding #2792]"
    ),
    (
        "Antoine McCord holds $100M–$250M in Anduril stock while serving as DHS CIO. "
        "Has McCord executed a formal recusal from any procurement decisions involving "
        "Anduril — including any DHS border surveillance or counter-drone programs — "
        "and if so, who serves as his recusal designee for those decisions? [Finding #2944]"
    ),
    (
        "Emil Michael as USD(R&E) publicly champions 'new primes' whose product portfolio "
        "maps directly onto Anduril's. Michael's pre-appointment advisory role at Coatue "
        "Management (which co-led Anthropic's Series G) is documented. Does Michael hold "
        "or have options on any equity interest in Anduril, Founders Fund vehicles, or "
        "any Anduril-adjacent portfolio company? [Finding #2758]"
    ),
    (
        "Anduril's bipartisan giving architecture — Luckey 81% Republican, Schimpf 100% "
        "Democratic — distributes donations across both parties' defense oversight members. "
        "Is this structure coordinated at the company level, and does Anduril's lobbying "
        "firm Invariant LLC (which billed $1.1M+ focused on defense/homeland security) "
        "operate with separate client contacts for Democratic and Republican offices? "
        "[Finding #5406] [Finding #4591]"
    ),
    (
        "The February 2026 Israel visit included meetings with ten defense startups mediated "
        "by Israel's DDR&D. Did any of those startups subsequently enter into supply or "
        "integration agreements with Anduril, and were any of those agreements disclosed in "
        "Anduril's filings or government contract modifications? [Finding #4571]"
    ),
    (
        "Luckey supported Trump in a documented letter as early as 2011. The Nimble America "
        "operation in 2016 was run under the 'NimbleRichMan' pseudonym. Was there any "
        "coordination between the Nimble America operation and the Trump campaign's "
        "digital or data operation at the time, and what was the full organizational "
        "structure behind Nimble America beyond Luckey's $10K contribution? [Finding #4575]"
    ),
]

# ── APPLICABLE MODELS ────────────────────────────────────────────────────────
curation["applicable_models"] = [
    "revolving-door",
    "conflict-of-interest",
    "bridge-tax",
    "private-order",
    "regulatory-capture",
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
