#!/usr/bin/env python3
"""Write curation fields into philippe-laffont.json."""
import json
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/philippe-laffont.json")

with DOSSIER_PATH.open() as f:
    dossier = json.load(f)

curation = dossier.setdefault("curation", {})

# ── lead ──────────────────────────────────────────────────────────────────────
curation["lead"] = (
    "<p>Philippe Laffont is the founder and chief investment officer of Coatue Management, "
    "a New York-based technology-focused hedge fund he established in 1999 after leaving "
    "Julian Robertson's Tiger Management. [Finding #5367] Coatue managed over $54 billion "
    "in combined public and private assets as of December 2024, with a $40 billion public "
    "equity portfolio concentrated in Taiwan Semiconductor, Microsoft, Meta, Amazon, and GE "
    "Vernova and a private portfolio spanning SpaceX, OpenAI, xAI, Scale AI, Anduril, and "
    "Shield AI. [Finding #5820] [Finding #5842]</p>"
    "<p>In February 2026 Coatue co-led Anthropic's $30 billion Series G at a $380 billion "
    "valuation, and two weeks later co-led OpenAI's $110 billion round — the OpenAI close "
    "occurring on the same day the Trump administration banned Anthropic from all federal "
    "use. [Finding #5820] LittleSis data identifies Laffont as holding a director seat at "
    "ByteDance, the Chinese parent of TikTok, at the same time Coatue holds major positions "
    "in Anthropic and OpenAI and Coatue's former senior advisor Emil Michael serves as "
    "Under Secretary of Defense for Research and Engineering. [Finding #5362]</p>"
    "<p>Laffont's personal federal campaign donations between 2016 and 2022 ran almost "
    "entirely to Democratic infrastructure: $50,000 to the Schumer Committee for the "
    "Majority, $20,300 to the DSCC, and contributions to Democratic Senate candidates in "
    "seven states, alongside $5,600 to Pete Buttigieg's Win the Era PAC. [Finding #5821] "
    "His brother Thomas, who co-founded Coatue and leads its private equity operations, "
    "donated in the same period to Mitch McConnell ($10,000) and Jeb Bush, providing "
    "combined Republican Senate access. [Finding #5368] Coatue's lobbying arm, PE Asia 34 "
    "LLC, retained Gibson Dunn and Crutcher LLP to work government and financial securities "
    "issues. [Finding #4601]</p>"
)

# ── system_role ───────────────────────────────────────────────────────────────
curation["system_role"] = (
    "Technology hedge fund manager bridging late-stage AI private investment and public "
    "equity markets. As founder of Coatue, Laffont allocates capital at scale into both "
    "US AI companies (Anthropic, OpenAI, xAI, Scale AI) and Chinese tech (ByteDance board "
    "seat), while maintaining Democratic Party political access through direct Senate "
    "leadership donations. His fund's former senior advisor now oversees defense acquisition "
    "policy for the portfolio companies Coatue backed."
)

# ── sections ──────────────────────────────────────────────────────────────────
curation["sections"] = [
    {
        "id": "career-and-tiger-cub-lineage",
        "title": "Career and Tiger Cub Lineage",
        "content": (
            "Laffont was born in Belgium and earned bachelor's and master's degrees in "
            "computer science from MIT in 1991. After two years as a McKinsey consultant "
            "(1992–1994), he joined Julian Robertson's Tiger Management as a research "
            "analyst in 1996. [Finding #5367] Robertson's firm produced a generation of "
            "hedge fund founders now known collectively as Tiger Cubs: Chase Coleman at "
            "Tiger Global, Andreas Halvorsen at Viking Global, John Griffin at Blue Ridge, "
            "and Lee Ainslie at Maverick. Laffont founded Coatue Management in 1999, naming "
            "it after a beach on Nantucket. The Tiger Cub network's collective AUM exceeds "
            "$100 billion and represents an informal but durable capital-allocation "
            "ecosystem built on shared training and deal flow."
        ),
        "viz": None,
    },
    {
        "id": "coatue-portfolio-and-defense-tech-exposure",
        "title": "Coatue Portfolio and Defense-Tech Exposure",
        "content": (
            "Coatue's Q4 2025 13F filing reported 257 positions totaling $40 billion in "
            "public equities; the five largest were TSM, MSFT, META, AMZN, and GEV. "
            "[Finding #5842] The firm's private portfolio held no defense-prime equities "
            "across any quarter from Q4 2024 through Q4 2025 — Palantir, Lockheed, "
            "Northrop, and Raytheon were absent. [Finding #5383] Instead, Coatue invested "
            "directly in pre-IPO defense-adjacent companies: SpaceX, Shield AI (a UAV "
            "contractor with $72 million in federal awards), Anthropic, OpenAI, xAI, Scale "
            "AI, and Anduril. [Finding #5820] In May 2025 Coatue launched CTEK (Coatue "
            "Innovation Fund), a closed-end tender-offer vehicle providing qualified "
            "individual investors access to the private portfolio; Jeff Bezos (Bezos "
            "Expeditions) and Michael Dell (DFO Management) provided $1 billion in combined "
            "anchor capital. [Finding #5364] EDGAR lists 1,339 filings under Coatue "
            "Management LLC (CIK 0001135730) and 944 under Laffont's personal CIK "
            "0001279618, spanning 104 fund entities across 13 vehicles from 2009 to 2025. "
            "[Finding #5842]"
        ),
        "viz": None,
    },
    {
        "id": "anthropic-openai-and-the-federal-ban-timeline",
        "title": "Anthropic, OpenAI, and the Federal Ban Timeline",
        "content": (
            "Coatue's relationship with Anthropic began with participation in the Series F "
            "(September 2025), then accelerated to co-leading a $10 billion round in January "
            "2026 and co-leading the $30 billion Series G at a $380 billion valuation on "
            "February 12, 2026. [Finding #5820] Laffont appeared on CNBC on February 13, "
            "2026, describing Coatue as an AI-first fund and framing the Anthropic investment "
            "around 'AI agents and enterprise-level systems.' [Finding #5371] On February 27, "
            "2026, the Trump administration banned Anthropic from federal use. That same day "
            "Coatue co-led OpenAI's $110 billion round. [Finding #4736] The combined "
            "Coatue commitment to Anthropic is estimated at $2–5 billion. Coatue also "
            "invested in xAI and Scale AI within the same window, representing a concentrated "
            "dual bet on the two dominant US AI model companies immediately before and after "
            "a federal exclusion order against one of them."
        ),
        "viz": None,
    },
    {
        "id": "bytedance-board-seat",
        "title": "ByteDance Board Seat",
        "content": (
            "LittleSis relationship records (entity 49837 to entity 328823) show Laffont "
            "holding a director position at ByteDance, the Chinese parent company of TikTok. "
            "[Finding #5362] ByteDance was subject to US forced-divestiture legislation and "
            "national security review throughout the same period Coatue was leading "
            "multibillion-dollar rounds in Anthropic and OpenAI. This creates a direct "
            "personal link between Laffont and a Chinese AI and social media company under "
            "government scrutiny, concurrent with Coatue's portfolio company Anthropic facing "
            "a federal use ban and Coatue's former senior advisor Emil Michael serving as "
            "the Pentagon's chief technology acquisition officer. The ByteDance directorship "
            "was not surfaced in Coatue's SEC filing disclosures reviewed to date."
        ),
        "viz": None,
    },
    {
        "id": "key-relationships",
        "title": "Key Relationships",
        "content": (
            "The most consequential relationship in the Coatue network is with "
            "<a href='/dossiers/emil-michael'>Emil Michael</a>, who served as Coatue's "
            "senior advisor from October 2018 through his confirmation as Under Secretary "
            "of Defense for Research and Engineering in May 2025. [Finding #5362] Michael's "
            "DoD portfolio directly covers AI and defense technology acquisition — the "
            "precise sector where Coatue holds its largest private investments. Michael also "
            "has a documented advisory role at Anthropic through DPCM Capital connections, "
            "and his six stated Pentagon technology priorities map to Anduril's product "
            "portfolio, another Coatue portfolio company. [Finding #4711]"
            "\n\n"
            "Laffont's brother <a href='/dossiers/thomas-laffont'>Thomas Laffont</a> "
            "co-founded Coatue and leads its private equity operations with approximately "
            "$7 billion in AUM. Thomas holds board seats at Lime, OneTrust, and Tipping "
            "Point Community. He is absent from all Coatue fund-level Form D filings, "
            "appearing only as a director of OneTrust LLC at the portfolio company level. "
            "[Finding #5824] FEC records show the brothers' political donations create "
            "bipartisan Senate leadership access: Philippe concentrates on Democratic "
            "leadership (Schumer, DSCC), Thomas on Republican leadership (McConnell). "
            "[Finding #5368]"
            "\n\n"
            "Coatue and <a href='/dossiers/trae-stephens'>Trae Stephens</a> co-invested "
            "in Blend Labs Inc (BLND), with Stephens via Founders Fund and Laffont via "
            "Coatue Management. [Finding #5453] Stephens co-founded Anduril Industries, "
            "in which Coatue also holds a direct investment, creating overlapping financial "
            "interests. <a href='/dossiers/joe-lonsdale'>Joe Lonsdale</a> (8VC, Palantir "
            "co-founder) is a third Blend Labs co-investor. J.P. Morgan Private Investments "
            "acts as Executive Officer and Promoter across 15 Coatue Private Investors "
            "feeder fund vehicles, channeling private wealth capital into Coatue's "
            "defense-adjacent AI investment thesis."
        ),
        "viz": "ego_network",
    },
    {
        "id": "political-donations-and-lobbying",
        "title": "Political Donations and Lobbying",
        "content": (
            "FEC individual contribution records show Philippe Laffont donated $50,000 to "
            "the Schumer Committee for the Majority on October 31, 2016, and $20,300 to the "
            "DSCC in the same cycle — the two dominant Democratic Senate fundraising "
            "committees. [Finding #5821] He also donated to seven Democratic Senate "
            "candidates in competitive 2016 races (Ross, Van Hollen, Murphy, Bayh, "
            "Duckworth, Feingold, Cortez Masto), $5,600 to Pete Buttigieg's Win the Era "
            "PAC in 2019, and $2,900 to Kyrsten Sinema in 2022. His sole Republican "
            "donation — $5,800 to Jimmy Crumpacker for Congress in 2022 — was partially "
            "refunded ($2,900). [Finding #5357] His employer is listed on all FEC filings "
            "as Coatue Management. Combined identified federal donations total approximately "
            "$93,000. [Finding #5368]"
            "\n\n"
            "At the fund level, Coatue PE Asia 34 LLC retained Gibson Dunn and Crutcher LLP "
            "to lobby on government issues and financial securities issues. [Finding #4601] "
            "Coatue employees' aggregate FEC donations run heavily Democratic, including "
            "contributions to the Harris Victory Fund and DNC. [Finding #4604]"
        ),
        "viz": None,
    },
]

# ── open_questions ─────────────────────────────────────────────────────────────
curation["open_questions"] = [
    (
        "The ByteDance directorship was not found in Coatue's SEC filings. When was "
        "this board seat initiated, and was it disclosed to Coatue's LPs or regulators "
        "given simultaneous investment in competing US AI companies?"
    ),
    (
        "What is the current status of the ByteDance board seat following the US "
        "forced-divestiture legislation and the TikTok sale process?"
    ),
    (
        "Emil Michael's Pentagon tenure ran from May 2025 onward. What recusal or "
        "ethics agreements, if any, govern his role with respect to Coatue portfolio "
        "companies (Anthropic, Shield AI, Anduril, OpenAI, SpaceX) that are subject "
        "to DoD acquisition decisions he oversees?"
    ),
    (
        "Coatue PE Asia 34 LLC lobbied via Gibson Dunn on 'government issues and "
        "financial securities issues.' What specific legislative or regulatory matters "
        "were being worked, and in what timeframe?"
    ),
    (
        "Thomas Laffont manages approximately $7 billion in private AUM but does not "
        "appear on any Coatue fund-level Form D filings. What is the formal legal "
        "structure separating his private equity role from Philippe's public fund "
        "operations?"
    ),
    (
        "Coatue co-led both Anthropic ($30B round, Feb 12, 2026) and OpenAI ($110B "
        "round, Feb 27, 2026). What information barriers, if any, exist within Coatue "
        "between investment teams working with these competing AI companies?"
    ),
    (
        "The CTEK closed-end fund (renamed Coatue Innovative Strategies Fund, Nov 2025) "
        "has $1B anchor capital from Bezos and Dell. What are the governance rights and "
        "reporting obligations for this vehicle relative to Coatue's existing fund "
        "structures?"
    ),
]

# ── applicable_models ──────────────────────────────────────────────────────────
curation["applicable_models"] = [
    {
        "name": "Dual-Bet Concentration",
        "description": (
            "Coatue simultaneously holds major positions in direct competitors "
            "(Anthropic and OpenAI, then OpenAI and xAI). This pattern recurs across "
            "the fund's history and gives it structural influence at both competing "
            "AI companies regardless of which prevails in the market or in government "
            "procurement."
        ),
    },
    {
        "name": "Advisor-to-Regulator Pipeline",
        "description": (
            "Emil Michael's path from Coatue senior advisor (Oct 2018) to Pentagon "
            "Under Secretary for Research and Engineering (May 2025) illustrates a "
            "recurring structure in this investigation: fund relationships convert into "
            "regulatory and procurement relationships. The same portfolio companies "
            "Coatue backed are now subject to DoD decisions Michael oversees."
        ),
    },
    {
        "name": "Bipartisan Sibling Access Strategy",
        "description": (
            "Philippe and Thomas Laffont's respective FEC donation patterns — Philippe "
            "covering Democratic Senate leadership, Thomas covering Republican Senate "
            "leadership — together produce access to both parties' dominant Senate "
            "fundraising infrastructure without either brother appearing to cross-donate. "
            "This structure is documented across hedge fund families in this investigation "
            "and represents a coordinated rather than individual political strategy."
        ),
    },
    {
        "name": "Private Portfolio Opacity via Closed-End Feeder",
        "description": (
            "The CTEK / Coatue Innovative Strategies Fund vehicle channels individual "
            "investor capital into Coatue's defense-adjacent private holdings while "
            "keeping those holdings off the public 13F, which covers only liquid "
            "equities. The anchor-investor structure (Bezos, Dell) replicates a "
            "pattern seen across this investigation where billionaire LPs gain "
            "economic exposure to government-contract-dependent companies."
        ),
    },
    {
        "name": "US-China Simultaneous Exposure",
        "description": (
            "The ByteDance directorship alongside Anthropic and OpenAI investments "
            "creates simultaneous personal and financial exposure to both US and Chinese "
            "AI ecosystems at a moment of active government intervention in both. This "
            "structural position is distinct from diversified passive investing: a board "
            "seat entails fiduciary duty to ByteDance while Coatue's capital actively "
            "bets on its US competitors."
        ),
    },
]

# ── write back ────────────────────────────────────────────────────────────────
with DOSSIER_PATH.open("w") as f:
    json.dump(dossier, f, indent=2)

print("Curation written to", DOSSIER_PATH)
