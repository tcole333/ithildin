#!/usr/bin/env python3
"""Write curation fields into content/dossiers/trae-stephens.json"""
import json
from datetime import datetime, timezone

DOSSIER_PATH = "content/dossiers/trae-stephens.json"

with open(DOSSIER_PATH) as f:
    dossier = json.load(f)

curation = dossier.get("curation", {})

# ── LEAD ────────────────────────────────────────────────────────────────────
curation["lead"] = (
    "<p>Trae Stephens (full name: Traevor Stephens) is a partner at "
    "<a href=\"/dossiers/peter-thiel\">Peter Thiel</a>'s "
    "<a href=\"/dossiers/founders-fund\">Founders Fund</a> — a position he has held since "
    "2013–2014 — and Executive Chairman of "
    "<a href=\"/dossiers/anduril-industries\">Anduril Industries</a>, the defense technology "
    "contractor he co-founded in 2017 with "
    "<a href=\"/dossiers/palmer-luckey\">Palmer Luckey</a> and others. Before joining Founders "
    "Fund, Stephens spent six years at Palantir Technologies (2008–2013) building its "
    "defense and intelligence sector business; before that, he held a role in the US "
    "intelligence community working on computational linguistics [Finding #4712].</p>"
    "<p>Anduril's valuation reached $30.5 billion after a June 2025 Series G round of "
    "$2.5 billion led by Founders Fund — the largest single check in that fund's history "
    "[Finding #4587]. Stephens is simultaneously one of the fund's managing members "
    "(Founders Fund IX and Growth III, alongside Peter Thiel and Napoleon Ta) and the "
    "chairman of the fund's largest portfolio company [Finding #5688].</p>"
    "<p>Stephens led the Department of Defense transition team for President-elect Trump "
    "in late 2016. The Wall Street Journal reported in late 2024 that he was under "
    "consideration for Deputy Secretary of Defense — the second-highest civilian Pentagon "
    "position — in the second Trump administration; the role went instead to Stephen Feinberg "
    "of Cerberus Capital. Reporting by Yahoo News noted that the extent of Stephens's "
    "financial conflicts — spanning Anduril, Palantir, and other Founders Fund portfolio "
    "companies — posed recognized ethics obstacles to confirmation [Finding #4712].</p>"
    "<p>FEC records show a minimal personal political contribution footprint: $85 to the "
    "Trump 2016 campaign (donated in December 2016, after the election, while he was "
    "leading the DOD transition), $500 to a Palantir PAC in 2012, and five $27/month "
    "ActBlue recurring donations in 2019 that listed his occupation as 'Not Employed' — "
    "despite his active status as a Founders Fund partner and Anduril chairman at that time "
    "[Finding #4993].</p>"
)

# ── SYSTEM ROLE ──────────────────────────────────────────────────────────────
curation["system_role"] = (
    "Stephens is the Founders Fund partner with the deepest structural entanglement between "
    "venture capital and defense procurement: he creates companies (Anduril co-founder), "
    "funds companies (FF partner who invests in defense-tech at every stage), shapes policy "
    "access (DOD transition team lead, deputy secretary finalist), and profits from contracts "
    "through equity in both a portfolio he manages and a company he chairs. "
    "No other single person in the tech-right defense ecosystem simultaneously holds all "
    "four positions. His Federalist Society membership adds a judicial and regulatory philosophy "
    "dimension, shaping the legal framework that governs defense procurement ethics rules. "
    "The Carbyne connection extends this network into the Israeli intelligence-tech corridor via "
    "the Epstein-Thiel nexus."
)

# ── SECTIONS ─────────────────────────────────────────────────────────────────
curation["sections"] = [
    {
        "id": "career-trajectory-and-structural-position",
        "title": "Career Trajectory and Structural Position",
        "viz": None,
        "content": (
            "<p>Stephens's career forms a direct line from the US intelligence community "
            "through two consecutive Thiel-controlled institutions to his current combined "
            "role as investor and defense contractor executive. He began in computational "
            "linguistics work for an undisclosed intelligence agency before joining Palantir "
            "in 2008 as an early employee. His role at Palantir was business development "
            "for the defense and intelligence sector — expanding the company's customer base "
            "inside the agencies he had previously worked within [Finding #4712].</p>"
            "<p>He joined Founders Fund in 2013 and became a partner in 2014. That same year, "
            "the concept for Anduril originated at a Founders Fund retreat where Stephens met "
            "<a href=\"/dossiers/palmer-luckey\">Palmer Luckey</a>. Stephens is credited with "
            "recruiting Luckey into the project after Luckey's 2017 departure from Facebook "
            "[Finding #2752]. Anduril was incorporated in 2017, with Stephens as Executive "
            "Chairman and Luckey as CEO. The company's founding thesis — that a software-native "
            "defense contractor could outcompete legacy primes on AI and autonomous systems — "
            "originated within the Founders Fund network, was funded by Founders Fund at every "
            "subsequent round, and is now operationally overseen by a Founders Fund partner "
            "who chairs the company's board [Finding #4694].</p>"
            "<p>In late 2016, Stephens led the Department of Defense transition team for "
            "President-elect Trump. That role gave him direct access to Pentagon leadership, "
            "planned program priorities, and key personnel decisions at the precise moment "
            "Anduril was being incubated. He consulted again with the Trump transition on "
            "defense transformation in late 2024 [Finding #4572]. SEC Form D filings confirm "
            "his designation as managing member of Founders Fund IX LP (a 2023–2025 vehicle) "
            "and Founders Fund Growth III LP ($4.6 billion, 270 investors, first sale "
            "March 2025), alongside Peter Thiel and Napoleon Ta [Finding #5688]. "
            "<a href=\"/dossiers/kenneth-howery\">Kenneth Howery</a>, the fund's third "
            "co-founder and current Ambassador to Denmark, is absent from both fund governance "
            "structures, having stepped back from active management after his 2019 Senate "
            "confirmation [Finding #5652].</p>"
            "<p>The structural consequence of holding both positions simultaneously — managing "
            "member of the GP that controls Founders Fund's $17B portfolio and chairman of "
            "the fund's largest single investment — is that Stephens sets investment and "
            "governance policy for a portfolio that directly benefits from the defense "
            "contracts his portfolio company competes for. He also oversees the company "
            "strategy of Anduril at a board level while co-managing the fund that has "
            "invested over $1 billion in Anduril at a $30.5 billion valuation [Finding #4587].</p>"
        ),
    },
    {
        "id": "anduril-defense-portfolio-and-conflicts",
        "title": "Anduril, the Defense Portfolio, and the Conflict Surface",
        "viz": "ego_network",
        "content": (
            "<p>Anduril holds or is pursuing several of the largest active US defense programs. "
            "USASpending confirms $2.32 billion in total government contracts: $1.43 billion "
            "from DoD and $862 million from DHS [Finding #5664]. The program suite includes "
            "joint prime contractor status on the Army TITAN deep-sensing system (alongside "
            "<a href=\"/dossiers/palantir-technologies\">Palantir</a>, $104.4 million), "
            "a position in the Golden Dome missile defense consortium alongside SpaceX, Palantir, "
            "Northrop, and Lockheed, and the April 2025 novation of Microsoft's $22 billion "
            "IVAS augmented-reality headset contract [Finding #4568] [Finding #4569] "
            "[Finding #4679].</p>"
            "<p>Stephens simultaneously manages Founders Fund's defense-technology portfolio, "
            "which includes Anduril ($1B+ invested), Palantir (early investor, $18.1B realized), "
            "SpaceX ($18.2B unrealized position), Varda Space Industries (co-founded by FF "
            "partner Delian Asparouhov, $36M in DoD contracts), and Gecko Robotics, whose SEC "
            "Form D filings list Stephens as executive or director [Finding #4996] "
            "[Finding #4694]. The finding that Stephens helped Gecko Robotics win DoD contracts "
            "while listed as a director in its Form D filings is documented but not independently "
            "verified [Finding #4599].</p>"
            "<p>The DOD official most directly overseeing this portfolio is "
            "<a href=\"/dossiers/emil-michael\">Emil Michael</a>, who was confirmed as Under "
            "Secretary of Defense for Research and Engineering on May 20, 2025. Michael's stated "
            "six technology priorities — applied AI, scaled hypersonics, directed energy, "
            "biomanufacturing, contested logistics, and battlefield information dominance — "
            "map to Anduril's product lines. As USD(R&E), Michael oversees IVAS, TITAN, "
            "Golden Dome, and Altius production [Finding #4713]. Michael was previously a "
            "senior advisor at Coatue Management, founded by "
            "<a href=\"/dossiers/philippe-laffont\">Philippe Laffont</a>, who is a co-investor "
            "with Stephens in Blend Labs [Finding #5453].</p>"
            "<p>If Stephens had been confirmed as Deputy Secretary of Defense, he would have "
            "required formal recusal from all matters involving Anduril, Palantir, SpaceX, "
            "Varda Space, Gecko Robotics, and other Founders Fund portfolio companies. "
            "Yahoo News reporting characterized the breadth of these conflicts as an obstacle "
            "to confirmation [Finding #4712]. The fact that Stephen Feinberg of Cerberus Capital "
            "— whose DynCorp holdings present their own conflicts — was selected instead does "
            "not resolve the underlying question: both finalists held financial interests in "
            "companies embedded in the defense programs each would have overseen.</p>"
        ),
    },
    {
        "id": "key-relationships",
        "title": "Key Relationships",
        "viz": None,
        "content": (
            "<p><a href=\"/dossiers/peter-thiel\">Peter Thiel</a> is the connecting institution "
            "across Stephens's entire professional career. Stephens joined Thiel's Palantir in "
            "2008, joined Thiel's Founders Fund in 2013, co-founded Anduril with Founders Fund "
            "capital, and now co-manages Founders Fund's most active investment vehicles "
            "alongside Thiel [Finding #2686]. The Carbyne connection traces the same network "
            "into a separate geography: Stephens introduced Thiel to Carbyne Ltd., the "
            "Israeli emergency-response AI company backed by "
            "<a href=\"/dossiers/ehud-barak\">Ehud Barak</a> and financed in part through "
            "Jeffrey Epstein's $3.6 million investment via Southern Trust Company. Founders "
            "Fund led Carbyne's $15 million Series B, and Stephens holds a board role at "
            "Carbyne Ltd. (Israeli entity, jurisdiction IL) [Connection #617] [Entity #223].</p>"
            "<p><a href=\"/dossiers/palmer-luckey\">Palmer Luckey</a> is Anduril's CEO and "
            "Stephens's co-founder. The relationship began at a 2014 Founders Fund retreat; "
            "Luckey is the public-facing figure and primary equity holder while Stephens "
            "operates as Executive Chairman managing the governance and capital architecture "
            "[Finding #2752]. Their roles are structurally complementary: Luckey drives product "
            "identity and public positioning; Stephens manages the Pentagon relationships, "
            "investor alignment, and political access.</p>"
            "<p><a href=\"/dossiers/kenneth-howery\">Kenneth Howery</a>, as a Founders Fund "
            "co-founder, shares the institutional platform with Stephens, though Howery has "
            "stepped back from active fund management since his 2019 ambassador confirmation. "
            "A documented ethics gap in Howery's State Department ethics agreement is "
            "directly relevant to Stephens's position: the agreement requires Howery to recuse "
            "from SpaceX and certain Founders Fund matters, but does not list Anduril — despite "
            "Founders Fund having invested $1 billion in Anduril as of June 2025. This means "
            "Howery, as Ambassador to Denmark, oversees Greenland infrastructure negotiations "
            "that are directly relevant to Golden Dome — a program for which Anduril is a "
            "frontrunner — without a formal Anduril recusal requirement [Finding #5682].</p>"
            "<p><a href=\"/dossiers/philippe-laffont\">Philippe Laffont</a> of Coatue Management "
            "is a co-investor with Stephens in Blend Labs (BLND): Stephens invested via Founders "
            "Fund, Laffont via Coatue. This is one of at least three co-investment nodes "
            "connecting the tech-right network — Joe Lonsdale of 8VC is the third Blend Labs "
            "investor [Finding #5453]. Laffont's Coatue co-led the Anthropic Series G while "
            "Emil Michael — former Coatue advisor — was conducting the Pentagon's Anthropic "
            "standoff, a separate documented conflict surface [Finding #4713].</p>"
        ),
    },
    {
        "id": "financial-activity",
        "title": "Financial Activity",
        "viz": None,
        "content": (
            "<p>SEC EDGAR returns 39 filings mentioning Trae Stephens. The Form D private "
            "placement filings list him as an executive or director across: Founders Fund IX LP "
            "(2023–2025), Founders Fund Growth III LP ($4.6 billion, first sale March 2025), "
            "Varda Space Industries (2021), Gecko Robotics (2025 filing), Flexport (2019–2022), "
            "Eight Sleep (2019–2021), and Blend Labs [Finding #4996]. He is also listed as a "
            "board member of ReNew Energy Global plc (RNW), an Indian renewable energy company "
            "that went public via SPAC in 2021–2022 — a commercial holding outside the defense "
            "portfolio [Finding #4996].</p>"
            "<p>Founders Fund Growth III LP, the most recent vehicle in which Stephens is named "
            "as a managing member of the GP, has a total offering of $4,595,493,889 from "
            "270 investors. The GP structure runs through FF Upper Tier GP LLC. Stephens signed "
            "no SEC filings in that fund — Peter Thiel signed the Form D — but he is listed as "
            "a related person [Finding #5688]. Founders Fund IX LP ($971.6 million, 235 "
            "investors) uses the same GP structure with the same three managing members: Thiel, "
            "Napoleon Ta, and Stephens [Finding #5652].</p>"
            "<p>FEC records show seven contributions total under both 'Trae Stephens' and "
            "'Traevor Stephens.' The sum is minimal relative to his network position: $500 to "
            "a Palantir PAC in February 2012 (when he was still a Palantir employee, listed "
            "as Forward Deployed Engineer), $85 to Trump for President in December 2016 "
            "(donated after the election, during his DOD transition role), and five recurring "
            "$27/month ActBlue donations from February to June 2019 listing occupation as "
            "'Not Employed' [Finding #4993]. The occupation discrepancy — he was an active "
            "Founders Fund partner and Anduril chairman during that period — is a factual "
            "inconsistency in the FEC record, not an inference about intent.</p>"
            "<p>The contrast between a $134 total personal political contribution record and "
            "Stephens's political access — leading two presidential transition processes, "
            "being a finalist for the second-highest civilian Pentagon position — indicates "
            "his influence operates through institutional channels: the Founders Fund "
            "platform, the Anduril executive role, and the Federalist Society network, "
            "rather than through personal campaign finance.</p>"
        ),
    },
    {
        "id": "epstein-network-and-carbyne",
        "title": "Epstein Network and Carbyne",
        "viz": None,
        "content": (
            "<p>Stephens's connection to the Epstein investigation arises through Carbyne Ltd., "
            "an Israeli emergency-response AI company co-founded by IDF veterans and backed by "
            "<a href=\"/dossiers/ehud-barak\">Ehud Barak</a>. Stephens introduced "
            "<a href=\"/dossiers/peter-thiel\">Peter Thiel</a> to Carbyne; Founders Fund "
            "subsequently led Carbyne's $15 million Series B [Connection #617]. Stephens "
            "holds a board position at the Israeli entity Carbyne Ltd. (jurisdiction IL, "
            "entity ID 223) [Entity #223].</p>"
            "<p>The Epstein connection to Carbyne runs through a separate capital channel: "
            "Jeffrey Epstein invested $3.6 million in Carbyne via Southern Trust Company. "
            "The PPP loan data shows Carbyne Inc. (the US entity) received $396,000 from "
            "Valley National Bank in April 2020, of which $360,605 was forgiven — a 91.1% "
            "forgiveness rate, below the expected full forgiveness for compliant uses "
            "[Finding #4887]. Stephens's board role and the Founders Fund investment predate "
            "public knowledge of Epstein's Carbyne connection. No evidence in the database "
            "directly links Stephens to Epstein personally.</p>"
        ),
    },
]

# ── OPEN QUESTIONS ───────────────────────────────────────────────────────────
curation["open_questions"] = [
    (
        "Stephens listed his occupation as 'Not Employed' on ActBlue contributions made in "
        "February through June 2019, while he was an active Founders Fund partner and Anduril "
        "executive chairman. Was this an error in data entry, a deliberate omission, or a "
        "technical classification (e.g., GP carry structure without W-2 employment)? "
        "FEC regulations require accurate employer and occupation disclosure. [Finding #4993]"
    ),
    (
        "Stephens is named as managing member of the GP for both Founders Fund IX and "
        "Founders Fund Growth III, the two most recent active vehicles. What recusal or "
        "wall procedures, if any, does Founders Fund apply when making investment decisions "
        "in defense companies that also receive government contracts overseen by Anduril "
        "competitors or partners? Does the fund's LPA contain any disclosure requirement "
        "to limited partners regarding the chairman-of-portfolio-company conflict? "
        "[Finding #5688] [Finding #4996]"
    ),
    (
        "Stephens is documented as having 'helped Gecko Robotics win DOD contracts' while "
        "simultaneously listed as an executive or director in Gecko Robotics Form D filings "
        "at Founders Fund [Finding #4599] [Finding #4996]. What is the precise mechanism — "
        "portfolio advocacy, introductions to Pentagon officials, or formal business "
        "development — and does this constitute a conflict with his DOD transition team role?"
    ),
    (
        "Kenneth Howery's State Department ethics agreement does not list Anduril as a "
        "recusal trigger, despite Founders Fund having invested $1 billion in Anduril "
        "as of June 2025 [Finding #5682]. Stephens co-manages both Founders Fund IX "
        "and Growth III with Howery's former co-GP position now held by Napoleon Ta. "
        "Was Anduril's omission from Howery's ethics agreement flagged during Senate "
        "confirmation review, and has it been supplemented since the June 2025 "
        "Series G investment?"
    ),
    (
        "Stephens introduced Thiel to Carbyne; Founders Fund led Carbyne's Series B; "
        "Stephens holds a board role at Carbyne Ltd. (Israeli entity). Ehud Barak was "
        "Carbyne's chairman and is also documented in the Epstein network. "
        "What due diligence did Founders Fund conduct on Carbyne's capital sources "
        "before leading the Series B, and was Epstein's $3.6 million STC investment "
        "in Carbyne known to FF at the time of investment? [Connection #617] [Entity #223]"
    ),
    (
        "Stephens was reported as a finalist for Deputy Secretary of Defense. Responsible "
        "Statecraft and Yahoo News documented ethics obstacles. What specific conflict "
        "waivers, if any, were discussed internally during the vetting process, and "
        "was the conflict breadth (Anduril + Palantir + SpaceX + Varda + Gecko) ever "
        "formally assessed by the Office of Government Ethics or transition counsel? "
        "[Finding #4712]"
    ),
]

# ── APPLICABLE MODELS ────────────────────────────────────────────────────────
curation["applicable_models"] = [
    "revolving-door",
    "conflict-of-interest",
    "incubator-to-contractor",
    "regulatory-capture",
    "bridge-actor",
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
