#!/usr/bin/env python3
"""Write curation fields for joe-gebbia.json"""

import json
from pathlib import Path

DOSSIER_PATH = Path("/Users/travcole/projects/osint-research/content/dossiers/joe-gebbia.json")

curation_patch = {
    "lead": (
        "<p>Joe Gebbia co-founded Airbnb in 2008 and has served on the Tesla board of directors — including its Audit Committee — since 2022. "
        "In early 2025 he joined the Department of Government Efficiency as a volunteer, working on a redesign of the Office of Personnel Management's retirement system. "
        "In August 2025 President Trump appointed him the first US Chief Design Officer under an executive order establishing the National Design Studio within the White House Office, with a three-year term and a mandate to redesign approximately 26,000 federal web portals by July 4, 2026. [Finding #5798] [Finding #6434]</p>"
        "<p>While holding those concurrent government and corporate positions, Gebbia systematically liquidated Airbnb stock through a series of SEC Form 4 filings (CIK 0001834171). "
        "Between January and February 2026 alone he sold roughly 58,000 ABNB shares in four tranches — at prices ranging from approximately $119 to $140 per share — generating over $30 million in proceeds, while retaining only 2,860 shares. [Finding #4518] [Finding #5955]</p>"
        "<p>His political giving underwent a documented shift: before 2024 his Federal Election Commission filings show donations to the Biden Victory Fund, Hillary Clinton, Chuck Schumer, and multiple state Democratic parties; from late 2024 onward the same records show $6,900 to the Kennedy Victory Fund, $6,399 to Libertarian Party committees, and subsequent contributions to Wonder Women PAC, Senator Tuberville, and WinRed, with his FEC employer field updated from \"Samara\" to \"US Government / Chief Design Officer.\" [Finding #4517] [Finding #4519] [Finding #5521]</p>"
    ),

    "system_role": (
        "Silicon Valley design entrepreneur who translated consumer-product credentials into a dual foothold in federal government and corporate boardroom. "
        "Gebbia occupies three structurally overlapping positions simultaneously: Airbnb co-founder and major shareholder, Tesla board Audit Committee member, and White House Chief Design Officer. "
        "Inside the federal government he functions as the principal successor to DOGE's civilian technology program — the National Design Studio absorbed former DOGE personnel and continues their digital-infrastructure work under a different organizational name. "
        "His personal friendship with Elon Musk, documented through LittleSis, predates and contextualizes both the Tesla board seat and the DOGE recruitment."
    ),

    "sections": [
        {
            "id": "government-roles",
            "title": "Government Roles",
            "content": (
                "Gebbia entered federal service in early 2025 as a DOGE volunteer assigned to the Office of Personnel Management, where he led a redesign of the federal retirement system. "
                "His government work became formalized in August 2025 when Trump signed an executive order creating the National Design Studio within the White House Office and naming Gebbia its first Chief Design Officer for a three-year term. "
                "The Studio's stated mission is to redesign the 26,000 federal digital portals — beginning with the ten most-visited government websites — with a July 4, 2026 deadline. [Finding #5798] [Finding #6434]<br><br>"
                "The National Design Studio was staffed in part by former DOGE operatives. "
                "Edward Coristine — who had cycled through OPM, SSA, and nine other agencies during DOGE's operation — moved to the Studio under Gebbia's leadership in December 2025 and was credited with building websites and branding for the administration's \"Genesis\" AI initiative. [Finding #6458] "
                "Additional staffers drawn from the DOGE pool included Zachary Terrell and Kaitlyn Koller. "
                "DOGE was formally dissolved in November 2025, eight months ahead of its July 2026 charter expiration, but its personnel and technical work dispersed rather than ceased — the National Design Studio is one of the principal receiving organizations. [Finding #5491]"
            ),
            "viz": None
        },
        {
            "id": "corporate-positions",
            "title": "Corporate Positions and Conflicts",
            "content": (
                "Gebbia has served on Tesla's board of directors since 2022 as a Class III director and Audit Committee member. "
                "That seat places him in a position of fiduciary oversight over the company led by Elon Musk — the same person who directed DOGE and who maintained a personal friendship with Gebbia documented in LittleSis. "
                "Multiple other Tesla employees entered DOGE or executive-branch roles during this period: Thomas Shedd (Tesla, on leave as GSA TTS director and DOL CIO), Daniel Abrahamson (Tesla senior counsel, assigned to DOT as Senior Adviser while NHTSA investigated Tesla's FSD system), Rajasekar Jegannathan (Tesla VP of IT, assigned to GSA), Riccardo Biasini (Tesla/Boring Company, assigned to OPM), and Tarak Makecha (Tesla Energy, assigned to DOJ, FBI, State, and USAGM). [Finding #4516]<br><br>"
                "Gebbia's original technology company, Airbnb, is subject to municipal and federal regulations that OPM does not directly administer, but his presence at OPM while retaining Airbnb equity and shareholder identity created a documented conflict-of-interest profile that analysts and ProPublica's DOGE tracker flagged. [Finding #5521] "
                "After the CDO appointment he established Samara, a design and venture firm, as his pre-government employer identity on FEC filings before updating the field to reflect his White House role. "
                "He is connected to <a href=\"/dossiers/elon-musk\">Elon Musk</a> through the Tesla board, the personal friendship, and DOGE; to <a href=\"/dossiers/doge\">DOGE</a> as a former member; and to <a href=\"/dossiers/edward-coristine\">Edward Coristine</a> as the supervising official who absorbed Coristine into the National Design Studio."
            ),
            "viz": "ego_network"
        },
        {
            "id": "financial-activity",
            "title": "Financial Activity",
            "content": (
                "The most concrete financial record for Gebbia during his government service is the systematic Airbnb stock liquidation recorded in SEC Form 4 filings under CIK 0001834171 (133 insider filings total). "
                "Between January 12 and February 23, 2026 — while serving as Chief Design Officer — he sold four tranches of approximately 58,000 ABNB shares each: "
                "~$8 million at $137–$140 on January 12; ~$7.7 million at $130–$134 on January 26; ~$7 million at $119–$122 on February 9; and ~$7.1 million at $124–$128 on February 23. "
                "Those four sales alone exceed $29 million in gross proceeds. Following the liquidation, his retained ABNB position shrank to 2,860 shares. [Finding #4518] [Finding #5955]<br><br>"
                "His Federal Election Commission donor history shows two distinct eras separated by a pivot in late 2024. "
                "Prior filings list donations to the Biden Victory Fund, Hillary Clinton's campaign, Chuck Schumer, Bill de Blasio, and multiple state Democratic parties, as well as to Equality PAC. "
                "From late 2024 onward, FEC records show $6,900 to the Kennedy Victory Fund (November 22, 2024), $1,300 to the Libertarian National Committee, $1,099 to the LP of Connecticut, $1,000 to the Montana LP, $1,300 to Team Kennedy, $1,000 to the LP of Hawaii (December 4, 2024), followed by $1,500 to Wonder Women PAC, $1,300 to Tuberville for Senate, $1,333 to American Revival PAC, $1,333 to a Mike Johnson committee, $1,000 to Grow the Majority, $1,000 to WinRed (August 2025), and $250 to the RNC. "
                "He was listed as residing in Redwood City, CA during the Kennedy-era donations and Austin, TX by the time of the 2025 Republican-era donations. [Finding #4517] [Finding #5521]"
            ),
            "viz": None
        },
        {
            "id": "network-and-relationships",
            "title": "Network and Relationships",
            "content": (
                "Gebbia's documented network connects three distinct domains. In the corporate domain, his Tesla board seat links him directly to <a href=\"/dossiers/elon-musk\">Elon Musk</a>, whose broader technology network includes <a href=\"/dossiers/palantir-technologies\">Palantir Technologies</a> (multiple Palantir alumni placed in DOGE roles), "
                "<a href=\"/dossiers/spacex\">SpaceX</a> (personnel cluster at OPM), and the cluster of Tesla employees embedded across federal agencies. [Finding #4516]<br><br>"
                "In the government domain, the DOGE connection links Gebbia to the broader network tracked under <a href=\"/dossiers/doge\">DOGE</a>, including "
                "<a href=\"/dossiers/scott-kupor\">Scott Kupor</a> (OPM director, former a16z managing partner who confirmed DOGE's dissolution), "
                "<a href=\"/dossiers/aram-moghaddassi\">Aram Moghaddassi</a> (SSA CIO who granted Coristine and others database access), and "
                "<a href=\"/dossiers/thomas-shedd\">Thomas Shedd</a> (Tesla employee on leave serving as GSA TTS director). "
                "Edward Coristine's move from SSA to the National Design Studio under Gebbia in December 2025 represents the most direct personnel link between DOGE operations and Gebbia's ongoing role. [Finding #5506] [Finding #6458]<br><br>"
                "In the political-donor domain, Gebbia's FEC history places him within the cohort of tech-sector figures who made parallel pivots toward Kennedy, Libertarian, and then Republican fundraising vehicles during 2024–2025 — a pattern documented more broadly across the tech-right investigation. [Finding #4519]"
            ),
            "viz": "ego_network"
        }
    ],

    "open_questions": [
        "What specific government systems or data did Gebbia access as a DOGE volunteer at OPM, and were any of those systems relevant to Airbnb's regulatory environment or Tesla's federal contracts?",
        "The National Design Studio's July 4, 2026 deadline to redesign 26,000 federal portals has not been assessed for procurement compliance — which vendors are being contracted for the work, and do any have Musk or Gebbia connections?",
        "Gebbia retains a Tesla Audit Committee seat while overseeing a White House design unit with access to federal infrastructure data. Has a formal ethics opinion been issued governing those concurrent roles?",
        "The $30M+ ABNB liquidation during government service was executed in systematic tranches. Were those sales conducted under a pre-existing Rule 10b5-1 plan filed before his government appointment, or were they discretionary trades made after taking the CDO role?",
        "Edward Coristine's move to the National Design Studio came after the EGodly cybercrime association and multiple agency access controversies — what vetting, if any, did Gebbia's organization conduct before bringing him on?",
        "Gebbia's FEC filings show Austin, TX as his address by mid-2025 — a relocation from Redwood City, CA. When did this occur, and does it correspond to any formal White House residency requirement?"
    ],

    "applicable_models": [
        "Revolving door: private-sector executive leveraging personal network and corporate credentials for rapid government appointment without traditional career-track vetting.",
        "Successor-entity displacement: when DOGE dissolved formally in November 2025, the National Design Studio absorbed its personnel and continued its digital-infrastructure mandate under a different organizational identity — a pattern of nominal dissolution with functional continuity.",
        "Concurrent-position conflict: Gebbia simultaneously holds a corporate board seat at a regulated company (Tesla), a government oversight role, and a legacy stake in another regulated company (Airbnb) — a structure in which the same individual sits on both sides of potential regulatory decisions.",
        "Political pivot trajectory: FEC records document a donor moving in a single 12-month window from longtime Democratic giving to Kennedy-Libertarian intermediary vehicles and then to mainstream Republican infrastructure — a pattern seen across multiple tech-sector figures in this investigation cohort.",
        "Asset liquidation timing: systematic stock sales during government service raise the question of whether access to non-public government information about regulatory or policy direction affects the timing of insider liquidations, even where the sales are technically legal."
    ]
}

# Load, patch, write
with open(DOSSIER_PATH) as f:
    dossier = json.load(f)

dossier["curation"].update(curation_patch)

with open(DOSSIER_PATH, "w") as f:
    json.dump(dossier, f, indent=2)

print("Done — curation written to", DOSSIER_PATH)
