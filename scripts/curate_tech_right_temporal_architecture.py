#!/usr/bin/env python3
"""Curation script for Tech-Right Temporal Architecture dossier."""
import json
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/tech-right-temporal-architecture.json")

curation = {
    "lead": (
        "<p>The January 20, 2025 inauguration functioned as a coordinated zero-day deployment across at "
        "least twelve distinct policy and regulatory domains simultaneously: the White House revoked ethics "
        "EO 13989 with no replacement — the first gap in executive ethics pledges since 1989 — while "
        "establishing DOGE by executive order, nominating Emil Michael as USD(R&amp;E), placing Corey "
        "Lewandowski at DHS as an unpaid Special Government Employee, signing seven immigration-related "
        "executive orders, and dropping the SEC's Nova Labs enforcement case on the same day that digital "
        "assets and crypto task force executive orders were issued [Finding #5446] [Finding #6513]. The "
        "Aryam/World Liberty Financial 49 percent deal had been signed four days earlier; the TRUMP meme "
        "coin launched three days earlier. The simultaneity across DOGE formation, nominee announcements, "
        "regulatory rollbacks, and enforcement pauses is consistent with pre-written policy templates "
        "deployed across agencies on a single day, rather than independent policy decisions reached "
        "organically during a transition.</p>"
        "<p>Between February 14 and February 17, 2025, DOGE executed what the investigation's findings "
        "designate the 'Valentine's Day Massacre': NHTSA lost 30 staff including three of seven AV "
        "safety specialists (NHTSA was investigating Tesla FSD crashes); FAA lost 332 employees on the "
        "same day; Starlink was installed at GSA headquarters the following day bypassing standard "
        "procurement timelines; and 20 FDA neurological device reviewers — those handling brain-computer "
        "interface clinical trials — were terminated on February 17. The three agencies whose staff "
        "were cut in this 72-hour window were the primary regulatory bodies for Tesla, SpaceX, and "
        "Neuralink respectively [Finding #6514]. FAA cuts preceded the Starlink FAA contract by 11 "
        "days; FDA cuts preceded Neuralink's FDA Breakthrough Device Designation by three months.</p>"
        "<p>The DHS enforcement domain, not defense technology, led the sequence. Stephen Miller's "
        "America First Legal had spent 2021–2024 preparing litigation templates, personnel lists, and "
        "policy frameworks including Project 2025. GEO Group and CoreCivic contributed $2.8 million "
        "in campaign donations during the 2024 cycle. Proclamation 10886 activated DHS emergency "
        "authority on Day 1. The first no-bid contracts — GEO Group's Delaney Hall detention facility "
        "and CSI Aviation charter flights — arrived within 36 days. DOGE subsequently terminated "
        "$71.1 billion in competitor contracts while zero SpaceX contract dollars were cut. The "
        "Golden Dome program ($175–$542 billion) was announced in June 2025 and the SpaceX-Anduril-Palantir "
        "consortium submitted its joint proposal within three weeks of Emil Michael's confirmation as "
        "Pentagon CTO [Finding #4863] [Finding #6518].</p>"
    ),

    "system_role": (
        "Tech-Right Temporal Architecture is the analytical framework capturing the sequenced deployment "
        "of pre-planned institutional changes across DHS enforcement, defense procurement, regulatory "
        "agency incapacitation, and financial market positioning from January 2025 through the onset of "
        "Operation Epic Fury in February 2026. It maps the observable timing patterns — coordinated "
        "zero-day actions, compressed 72-hour regulatory clearances, synchronized policy enablement "
        "windows — that connect the DOGE thread, the Emil Michael/Golden Dome thread, the crypto "
        "enforcement rollback thread, and the pre-war defense contractor positioning thread into a "
        "single documented timeline."
    ),

    "sections": [
        {
            "id": "inauguration-zero-day",
            "title": "The Inauguration as Coordinated Deployment",
            "content": (
                "Twelve documented events occurred on January 20, 2025, each in a distinct policy domain. "
                "The ethics framework was dismantled (EO 13989 revoked) on the same day Emil Michael was "
                "nominated — removing the pledge that would have governed his conflicts of interest involving "
                "Coatue Management and D-Wave. The SEC dropped the Nova Labs/Helium case on inauguration "
                "day, signaling a crypto enforcement pause before the formal Crypto Task Force announcement "
                "three days later. FAA Administrator Whitaker resigned under Musk pressure on inauguration "
                "day itself — before any formal DOGE authority existed — requiring that pressure to have "
                "been applied in advance [Finding #5446] [Finding #6513]. The Aryam entity had signed its "
                "49 percent World Liberty Financial stake four days prior; the TRUMP meme coin had launched "
                "three days prior. Within seven days: DOGE was established by executive order with Musk as "
                "Special Government Employee; Thomas Shedd (Tesla-to-GSA) entered government; the digital "
                "assets executive order issued; Joseph Alm (Tesla-to-DHS) began DOGE participation. "
                "The pattern of simultaneous action across DOGE formation, regulatory rollbacks, enforcement "
                "pauses, and financial deal closings in the days bracketing January 20 establishes a "
                "pre-planned deployment window rather than a reactive transition. "
                "See also: <a href='/dossiers/doge'>DOGE</a>, "
                "<a href='/dossiers/emil-michael'>Emil Michael</a>, "
                "<a href='/dossiers/world-liberty-financial'>World Liberty Financial</a>."
            ),
            "viz": None
        },
        {
            "id": "regulatory-clearance-window",
            "title": "72-Hour Regulatory Clearance: February 14–17, 2025",
            "content": (
                "On February 14, 2025, DOGE fired 30 NHTSA employees including three of seven AV safety "
                "specialists; the NHTSA office responsible for investigating Tesla Full Self-Driving crashes "
                "lost critical capacity. On the same day, the FAA lost 332 employees. On February 15, "
                "Starlink satellite internet was installed at GSA headquarters — within days of the DOGE "
                "request, bypassing the procurement timeline that normally takes weeks to months. On "
                "February 17, DOGE fired 20 FDA neurological device reviewers specifically handling "
                "brain-computer interface clinical trials — the regulatory pathway for Neuralink [Finding #6514]. "
                "The FAA cuts preceded a Starlink FAA contract by 11 days. The FDA cuts preceded Neuralink's "
                "FDA Breakthrough Device Designation by three months. NHTSA opened a new FSD investigation "
                "(PE25012) only in October 2025 — eight months after the capacity reduction. Public Citizen "
                "subsequently documented Musk conflicts at 23 of 32 agencies targeted by DOGE. The three "
                "agencies whose staff were hollowed out in this 72-hour window were the primary oversight "
                "bodies for Tesla, SpaceX, and Neuralink respectively — a coincidence pattern that holds "
                "across all three [Finding #5787]. "
                "See also: <a href='/dossiers/doge'>DOGE</a>, "
                "<a href='/dossiers/elon-musk'>Elon Musk</a>, "
                "<a href='/dossiers/spacex'>SpaceX</a>."
            ),
            "viz": None
        },
        {
            "id": "sec-crypto-rollback",
            "title": "SEC Crypto Enforcement: 10 Cases in 70 Days",
            "content": (
                "Between January 20 and March 27, 2025, the SEC dropped or paused ten crypto enforcement "
                "cases: Nova Labs on inauguration day; Robinhood, OpenSea, Uniswap, and Crypto.com on "
                "February 21; Coinbase dismissed and Justin Sun's fraud case paused on February 27 — "
                "Sun had invested millions in World Liberty Financial and attended the Trump meme coin "
                "dinner; Kraken, ConsenSys, Cumberland, and Gemini dropped on March 27 [Finding #6515]. "
                "Every major crypto company that donated to the Fairshake PAC (which supported "
                "Trump-aligned congressional candidates) had cases dropped. DOGE accessed SEC offices "
                "on April 1; lead SEC attorney Robin Andrews resigned April 4, describing the day as "
                "'heartbreaking'; Paul Atkins was sworn in as SEC chair on April 21 with approximately "
                "$6 million in disclosed crypto holdings. The case closures all resolved favorably for "
                "Trump-adjacent interests before the new chair arrived — the sequencing moves from "
                "inaugural-day enforcement freeze through political-donor-specific closures through "
                "personnel replacement, a three-stage pattern inconsistent with ordinary new-administration "
                "policy recalibration. "
                "See also: <a href='/dossiers/world-liberty-financial'>World Liberty Financial</a>, "
                "<a href='/dossiers/doge'>DOGE</a>."
            ),
            "viz": None
        },
        {
            "id": "may-2025-coordination-peak",
            "title": "May 2025: Maximum Cross-Thread Coordination Density",
            "content": (
                "May 2025 generated 74 documented findings across 11 investigation threads simultaneously — "
                "the highest coordination density month in the investigation. The linchpin event was "
                "Emil Michael's Senate confirmation (54–43) on May 14 and swearing-in on May 20 as "
                "USD(R&amp;E), the Pentagon's chief technology officer. Within the same month: DOGE "
                "reached its $71.1 billion contract termination peak (zero SpaceX dollars cut); "
                "Philippe Laffont launched Coatue CTEK — a closed-end defense-tech fund anchored by "
                "$1 billion combined from Jeff Bezos and Michael Dell — the same month Laffont's "
                "long-term Coatue advisory client Michael assumed R&amp;E authority; the SpaceX-Anduril-Palantir "
                "consortium submitted its joint Golden Dome proposal three weeks after Michael took "
                "the position overseeing the program; the G42/Trump AI deal linked UAE sovereign "
                "fund capital to the same investment class as the Aryam/WLFI structure; and World "
                "Liberty Financial's USD1 stablecoin was used for the UAE/Binance transaction [Finding #6518]. "
                "The three most politically connected defense technology firms bid the largest active "
                "procurement together, three weeks after the single official with acquisition authority "
                "over the program assumed office. "
                "See also: <a href='/dossiers/emil-michael'>Emil Michael</a>, "
                "<a href='/dossiers/golden-dome'>Golden Dome</a>, "
                "<a href='/dossiers/coatue-management'>Coatue Management</a>, "
                "<a href='/dossiers/palantir-technologies'>Palantir</a>."
            ),
            "viz": None
        },
        {
            "id": "pre-war-positioning",
            "title": "13-Month Pre-War Positioning Sequence",
            "content": (
                "The 13 months from January 2025 through February 2026 produced a documented sequence "
                "in which policy decisions framed as anti-waste or budget reform simultaneously eliminated "
                "traditional defense contractors and positioned tech-right-aligned companies for "
                "wartime procurement surges. DOGE terminated $71.1 billion in contracts from traditional "
                "primes while zero SpaceX dollars were cut [Finding #4863]. The Golden Dome program "
                "($175–$542 billion) was created in June 2025 with a procurement structure favoring "
                "non-traditional vendors and an OTA mechanism shielding 18 space-based interceptor "
                "contracts from public disclosure [Finding #4724]. Emil Michael consolidated the Defense "
                "Innovation Unit, Chief Digital and AI Office, and Operational Science Center under "
                "R&amp;E authority — maximum single-point procurement control [Finding #4735]. "
                "RTX/Raytheon signed five 7-year framework agreements with the Department of War on "
                "February 4, 2026 — 24 days before Operation Epic Fury began on February 28 — covering "
                "Tomahawk (60/year to 1,000+/year), AMRAAM (to 1,900/year), and SM-6 (to 500/year) "
                "[Finding #6519]. Defense stocks hit all-time highs on March 2 (the first trading day "
                "after strikes): LMT +3.37%, RTX +4.7%, NOC +6%, PLTR +5.8%. Multiple members of "
                "Congress serving on defense and homeland security committees held these stocks. "
                "Palantir's AIP platform directed intelligence fusion and targeting during Operation "
                "Epic Fury; Anduril's Lattice managed autonomous drone swarms; SpaceX/Starshield "
                "provided satellite communications; the LUCAS drone deployed in seven months from "
                "public debut. Every weapon expended in the conflict generates a replenishment contract "
                "for RTX, Lockheed Martin, and Northrop Grumman [Finding #4714] [Finding #4730]. "
                "See also: <a href='/dossiers/golden-dome'>Golden Dome</a>, "
                "<a href='/dossiers/palantir-technologies'>Palantir</a>, "
                "<a href='/dossiers/anduril-industries'>Anduril Industries</a>, "
                "<a href='/dossiers/1789-capital'>1789 Capital</a>."
            ),
            "viz": None
        },
        {
            "id": "dhs-as-lead-domain",
            "title": "DHS as Lead Domain: The Enforcement Template",
            "content": (
                "The DHS enforcement domain preceded and enabled the defense technology procurement "
                "expansion by establishing the legal and operational infrastructure for emergency "
                "authority contracting. Stephen Miller's America First Legal spent 2021–2024 "
                "preparing litigation, policy templates, and personnel lists through Project 2025. "
                "GEO Group and CoreCivic had a 20-plus-year revolving door pipeline — mature versus "
                "the first-cycle defense tech relationships. Proclamation 10886 activated DHS emergency "
                "authority on Day 1. The first no-bid contracts (Delaney Hall detention facility, "
                "36 days post-inauguration; CSI Aviation charter flights, days 48+) preceded the "
                "first major defense technology contract expansions. DOGE launched in January 2025 "
                "destroying regulatory and oversight capacity before defense tech contracts expanded "
                "in scale [Finding #4863]. The Iran conflict — an external trigger — arrived after "
                "both DHS and defense tech systems were fully operational. The sequence is: personnel "
                "placement (pre-inauguration) → policy changes (Day 1) → oversight destruction "
                "(DOGE, months 1–5) → contracts (month 2 onward) → crisis amplification (Iran, "
                "month 13+). The DHS model provided the template; defense technology followed with "
                "larger dollar amounts. "
                "See also: <a href='/dossiers/doge'>DOGE</a>, "
                "<a href='/dossiers/america-first-legal-foundation'>America First Legal Foundation</a>."
            ),
            "viz": None
        }
    ],

    "open_questions": [
        "What pre-inauguration coordination mechanism produced simultaneous action across 12 distinct "
        "policy domains on January 20, 2025 — specifically, was there a single coordinating document, "
        "structured transition working group, or informal network of principals responsible for the "
        "synchronized timing?",
        "The Aryam/WLFI 49% deal (Jan 16) and TRUMP meme coin launch (Jan 17) preceded inauguration "
        "by 3–4 days. Were the financial transactions deliberately front-run before the ethics EO "
        "revocation took effect, and did any transition official have advance knowledge that EO 13989 "
        "would be revoked on Day 1?",
        "The FAA Administrator's resignation under Musk pressure occurred on inauguration day before "
        "any formal DOGE authority existed. Who conveyed the pressure, through what channel, and when "
        "did communications begin relative to inauguration?",
        "DOGE terminated $71.1 billion in defense contracts while zero SpaceX dollars were cut. What "
        "was the selection methodology for contract terminations — specifically, did DOGE teams with "
        "Musk company affiliations have access to competitive intelligence on non-SpaceX contractors "
        "before termination decisions were made?",
        "The Valentine's Day 72-hour window (Feb 14–17) cut the three regulatory bodies responsible "
        "for Tesla, SpaceX, and Neuralink in sequence. Was there a unified DOGE directive covering "
        "all three agencies, or did each agency receive separate instructions that happened to be "
        "executed in the same 72 hours?",
        "The Coatue CTEK fund launched the same month Philippe Laffont's long-term advisory client "
        "Emil Michael assumed R&E authority. Was there pre-coordination between Laffont and Michael "
        "on the fund's launch timing, and did Michael disclose his Coatue advisory relationship in "
        "his Senate confirmation ethics disclosures?",
        "RTX framework agreements were signed February 4, 2026 — 24 days before Operation Epic Fury. "
        "At what classification level did RTX executives have access to Iran strike planning at the "
        "time of signing, and were the agreements negotiated with any awareness of the upcoming "
        "operational timeline?",
        "The Polymarket 'Magamyman' account placed the first Iran-strike bet 71 minutes before news "
        "broke at 17% probability, netting $553K. CFTC had been warned by six senators four days "
        "before the strikes. Was there coordination between prediction market positioning and "
        "personnel with classified knowledge of strike timing?",
        "The SEC dropped 10 crypto enforcement cases in 70 days, all involving Trump-adjacent "
        "interests, before Paul Atkins was sworn in. Were any of these dismissals coordinated "
        "with transition officials, and what formal legal rationale was provided for each closure?",
        "Golden Dome's 18 space-based interceptor contracts were awarded 'in secret' under OTA "
        "mechanisms. What was the contracting officer's written justification for using OTA rather "
        "than competitive acquisition, and has Congress received the required architecture "
        "documentation?"
    ],

    "applicable_models": [
        {
            "name": "Coordinated Zero-Day Deployment",
            "description": (
                "A playbook pre-written during a transition period is executed simultaneously across "
                "multiple agencies and domains on a single triggering date. The zero-day pattern is "
                "distinguishable from ordinary new-administration policy shifts by: (1) simultaneity "
                "across unrelated domains (ethics, immigration, crypto enforcement, regulatory "
                "appointments, financial deal closings) within hours; (2) actions that required "
                "advance preparation (e.g., FAA Administrator pressure before DOGE authority existed); "
                "(3) financial transactions front-run before the enabling legal change took effect. "
                "The January 20, 2025 inauguration window is the documented example."
            )
        },
        {
            "name": "Sequenced Conflict Clearance",
            "description": (
                "Regulatory bodies with oversight authority over specific private interests are "
                "systematically weakened in a compressed time window before the interests those "
                "bodies regulate receive significant contract awards or regulatory determinations. "
                "The February 14–17 NHTSA/FAA/FDA sequence is the tightest documented instance: "
                "72 hours, three separate agencies, three separate companies under the same "
                "beneficial owner. The general pattern appears across DOGE's 12-month activity: "
                "FTC weakened before SpaceX-xAI merger review; DOT&E gutted before Golden Dome "
                "oversight listing; SEC enforcement frozen before crypto policy formalized."
            )
        },
        {
            "name": "Policy-Financial Synchronization",
            "description": (
                "Government policy decisions that appear as budget reform or procurement modernization "
                "simultaneously eliminate competitors and position connected entities for the resulting "
                "contract or market opportunity. The $71.1 billion DOGE contract terminations "
                "combined with zero SpaceX cuts, the 'commercial first' procurement policy favoring "
                "new entrants, and the Golden Dome OTA structure collectively transferred procurement "
                "positioning from legacy primes to tech-right-affiliated companies. The defense stock "
                "surge on March 2, 2026 demonstrated that the holders of these positions captured "
                "value at the moment the Iran conflict validated the spending pipeline."
            )
        },
        {
            "name": "Enabling Event Cascade",
            "description": (
                "A single personnel confirmation or structural change triggers coordinated responses "
                "across multiple networked actors who had pre-positioned around the anticipated "
                "enabling event. The May 2025 Emil Michael confirmation is the clearest instance: "
                "within weeks, the three most politically connected defense technology firms submitted "
                "a joint Golden Dome proposal; Philippe Laffont's Coatue CTEK launched; G42 closed "
                "its Trump AI deal; and WLFI's stablecoin completed the UAE/Binance transaction. "
                "No single actor orchestrated all activity — but the temporal compression confirms "
                "networked actors responding to a shared enabling trigger."
            )
        },
        {
            "name": "Crisis Front-Running vs. Crisis Exploitation",
            "description": (
                "The DHS enforcement domain manufactured its crisis trigger (immigration emergency) "
                "through policy and proclamation on Day 1 — the emergency authority was self-created. "
                "The defense technology domain exploited an external crisis trigger (Iran conflict) "
                "that arrived after the infrastructure was operational. Both sequences follow the "
                "same procurement logic — emergency authority enables no-bid contracts at accelerated "
                "timelines — but differ in whether the enabling condition was endogenous or exogenous "
                "to the network. The distinction matters for legal exposure: self-manufactured "
                "emergencies face a different constitutional challenge than genuine external events "
                "exploited by pre-positioned interests."
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
print(f"  system_role: {len(curation['system_role'])} chars")
print(f"  sections: {len(curation['sections'])}")
print(f"  open_questions: {len(curation['open_questions'])}")
print(f"  applicable_models: {len(curation['applicable_models'])}")
