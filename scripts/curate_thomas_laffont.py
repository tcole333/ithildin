#!/usr/bin/env python3
"""Write curation fields into content/dossiers/thomas-laffont.json"""

import json
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/thomas-laffont.json")

with open(DOSSIER_PATH) as f:
    dossier = json.load(f)

curation = dossier.setdefault("curation", {})

# ── system_role ──────────────────────────────────────────────────────────────
curation["system_role"] = (
    "Thomas Laffont is the co-founder of Coatue Management and its Chief Investment "
    "Officer of Privates, overseeing $7 billion in assets across five growth and "
    "venture funds globally. While his brother Philippe Laffont runs the firm's $40 "
    "billion public equity book, Thomas controls the private portfolio — the side of "
    "the business that holds SpaceX, Anthropic, OpenAI, and Shield AI, and that is "
    "invisible on Coatue's 13F disclosures. His EDGAR footprint is limited to two "
    "portfolio-company Form D filings (OneTrust and Weights & Biases), and he does not "
    "appear on any Coatue fund-level regulatory filings. His FEC record shows a "
    "bipartisan donation pattern complementing his brother's Democratic-focused giving: "
    "Philippe covers Senate Democratic leadership (Schumer, DSCC), Thomas covers "
    "Republican Senate leadership (McConnell), with both brothers also donating to "
    "centrist candidates across party lines."
)

# ── lead ─────────────────────────────────────────────────────────────────────
curation["lead"] = (
    "<p>Thomas Laffont co-founded Coatue Management with his brother "
    "<a href=\"/dossiers/philippe-laffont\">Philippe Laffont</a> in 1999 and serves as "
    "the firm's Chief Investment Officer of Privates, overseeing $7 billion across five "
    "growth and venture funds globally. [Finding #5824] His operational domain is the "
    "private side of Coatue — the portfolio that holds SpaceX, Anthropic, OpenAI, and "
    "Shield AI, none of which appear on Coatue's quarterly 13F-HR filings to the SEC. "
    "His brother Philippe is the public face of the firm and manages the $40 billion "
    "public equity book; Thomas's role is structurally distinct, governing precisely the "
    "investments with the most direct exposure to federal defense and AI policy.</p>"

    "<p>Thomas's regulatory footprint within Coatue's own fund structure is minimal. "
    "Across 251 SEC Form D filings and 133 fund entities extracted from Coatue's EDGAR "
    "history, Thomas appears only once — as director of portfolio company OneTrust LLC "
    "(CIK 0001782045), not on any fund-level filing. [Finding #4743] The EDGAR record "
    "also shows his name on a 2023 Form D for Weights &amp; Biases Inc. (CIK 0001987275), "
    "an ML infrastructure company widely used in AI and defense research. [Finding #5843] "
    "His absence from fund-level filings contrasts with Philippe's presence on 61 filings "
    "across 13 fund vehicles.</p>"

    "<p>FEC records list Thomas Laffont (employer: COATUE MANAGEMENT, address: 18 Monte "
    "Vista Ave, Atherton CA) with a bipartisan giving record across Republicans and "
    "Democrats, including $10,000 to Mitch McConnell in 2020. [Finding #5823] The pattern "
    "complements Philippe's giving to Democratic Senate leadership, with the two brothers "
    "collectively covering both parties' Senate leadership infrastructure from the same "
    "investment firm. [Connection #2963]</p>"
)

# ── sections ─────────────────────────────────────────────────────────────────
curation["sections"] = [
    {
        "id": "private-portfolio-and-structural-role",
        "title": "Private Portfolio and Structural Role at Coatue",
        "content": (
            "<p>The division of labor at <a href=\"/dossiers/coatue-management\">Coatue "
            "Management</a> between the two Laffont brothers is functional: "
            "<a href=\"/dossiers/philippe-laffont\">Philippe</a> manages the public "
            "equity book and carries the firm's public profile; Thomas manages the private "
            "growth and venture funds. As CIO of Privates, Thomas oversees $7 billion in "
            "assets across five funds that have backed Tencent, Meituan, Didi, and ByteDance "
            "internationally, and SpaceX, Anthropic, and OpenAI domestically. [Finding #5824] "
            "These private holdings are not disclosed on Coatue's 13F-HR quarterly filings, "
            "which capture only publicly traded positions. The practical effect is that the "
            "Coatue portfolio most directly relevant to federal AI and defense procurement "
            "policy sits entirely in Thomas's domain and entirely outside mandatory periodic "
            "disclosure.</p>"

            "<p>Thomas's board positions document where his active oversight is concentrated. "
            "Current board seats include Lime (micromobility), OneTrust (data privacy and "
            "governance), and Tipping Point Community (Bay Area nonprofit). [Finding #5824] "
            "OneTrust is a data governance and privacy compliance platform used by "
            "enterprises and government agencies — the same company for which Thomas appears "
            "as director in the only Coatue fund-level Form D filing bearing his name. "
            "[Finding #5843] Weights &amp; Biases, the other EDGAR-documented investment, "
            "provides ML experiment tracking and model monitoring infrastructure used widely "
            "in AI and defense research and development. Both positions are consistent with "
            "a private-investment focus on AI infrastructure rather than consumer applications.</p>"

            "<p>The Thomas And Elizabeth Laffont Family Foundation (EIN 861914134) is "
            "a separate philanthropic vehicle from the Ana and Philippe Laffont foundation, "
            "reflecting the independent personal and financial structures the brothers "
            "maintain despite operating the same firm. [Finding #5372]</p>"
        ),
        "viz": None,
    },
    {
        "id": "regulatory-footprint-and-transparency-gaps",
        "title": "Regulatory Footprint and Transparency Gaps",
        "content": (
            "<p>Thomas Laffont's near-absence from Coatue's SEC filing record is "
            "structurally notable. A full extraction of 251 Form D and Form D/A filings "
            "across 133 Coatue fund entities found Philippe Laffont listed on 61 filings "
            "across 13 fund vehicles. Thomas appears on zero fund-level filings. His only "
            "EDGAR appearances are as a director of two portfolio companies: OneTrust LLC "
            "(Form D filed 2023-08-04, CIK 0001782045, Atlanta GA) and Weights &amp; Biases "
            "Inc. (Form D filed 2023-10-03, CIK 0001987275, San Francisco CA). [Finding #4743, "
            "#5843]</p>"

            "<p>Form D filings are triggered by private securities offerings and disclose "
            "the identity of directors, executive officers, and promoters of the issuer — "
            "not of the investing fund. Thomas's name appearing in OneTrust and Weights "
            "&amp; Biases filings reflects his board seats at those companies rather than "
            "any fund-level registration. The Coatue fund vehicles through which those "
            "investments were made list <a href=\"/dossiers/coatue-management\">Coatue "
            "Management LLC</a> as the executive officer, not Thomas individually. This "
            "structure means that the manager of $7 billion in private technology assets "
            "has a de minimis personal regulatory disclosure footprint compared to his "
            "brother, who manages a larger but more transparent public equity book.</p>"
        ),
        "viz": None,
    },
    {
        "id": "political-donations",
        "title": "Political Donations",
        "content": (
            "<p>FEC records identify Thomas Laffont (Coatue Management, 18 Monte Vista "
            "Ave, Atherton CA, occupation: FINANCE) with approximately $33,600 in "
            "documented federal contributions spanning 2011 to 2020. [Finding #5823] The "
            "record is bipartisan across the full span: Romney for President $2,500 (2011); "
            "Cory Booker for Senate $10,000 (2013–2014); Jeb 2016 Inc. $2,700 (2015); "
            "Win the Era PAC (Pete Buttigieg) $5,600 (2019); Cory Gardner for Senate $5,600 "
            "(2019); McConnell For Majority Leader $5,000 (2020); McConnell Senate Committee "
            "$5,000 (2020); Biden for President $500 (2020).</p>"

            "<p>The $10,000 aggregate to Mitch McConnell in 2020 — split across two "
            "separate McConnell committees — is the largest single-cycle contribution in "
            "the record and coincides with McConnell's Senate Majority Leader position. "
            "[Finding #5353] The complementary pattern with Philippe is documented as a "
            "connection in the database: Philippe's largest FEC contributions ran to the "
            "Schumer Majority Committee ($50,000) and DSCC ($20,300), covering Democratic "
            "Senate leadership infrastructure at the same time Thomas was covering "
            "Republican Senate leadership infrastructure. [Connection #2963] No Trump "
            "committee contributions appear in Thomas's FEC sample.</p>"

            "<p>The giving pattern — bipartisan, Senate-leadership-weighted, with "
            "contributions to both McConnell and Buttigieg in the same year — is consistent "
            "with the access-maintenance approach common to large institutional asset "
            "managers dependent on regulatory and legislative conditions affecting private "
            "markets, carried interest treatment, and government procurement.</p>"
        ),
        "viz": None,
    },
    {
        "id": "key-relationships",
        "title": "Key Relationships",
        "content": (
            "<p><strong><a href=\"/dossiers/philippe-laffont\">Philippe Laffont</a></strong> "
            "— Thomas's brother and co-founder of Coatue. Philippe manages the public "
            "equity portfolio and holds the firm's public CIO title; Thomas manages the "
            "private portfolio. Their FEC records show complementary political giving: "
            "Philippe to Democratic Senate leadership, Thomas to Republican Senate "
            "leadership, with both also donating to centrist figures across party lines. "
            "[Connection #2963] Philippe's 61 SEC fund-level filings contrast sharply with "
            "Thomas's zero fund-level appearances — the public structure of the firm is "
            "organized around Philippe's regulatory identity.</p>"

            "<p><strong><a href=\"/dossiers/coatue-management\">Coatue Management</a></strong> "
            "— Thomas is co-founder of the firm but his formal footprint within Coatue's "
            "regulatory filings is limited to portfolio company board seats. [Connection #2777] "
            "As CIO of Privates, he oversees the defense-adjacent investments — SpaceX, "
            "Anthropic, OpenAI, Shield AI — that are not captured in Coatue's mandatory "
            "quarterly 13F disclosures. The management fee and carried interest from $7 "
            "billion in private assets under his oversight represent a significant portion "
            "of Coatue's total economics, concentrated in the part of the portfolio with "
            "direct exposure to DoD procurement decisions.</p>"
        ),
        "viz": "ego_network",
    },
]

# ── open_questions ────────────────────────────────────────────────────────────
curation["open_questions"] = [
    (
        "Thomas Laffont's name does not appear on any Coatue fund-level SEC filing. "
        "What is his formal legal title and fiduciary role in the Coatue fund entities "
        "that hold the private portfolio? Is he a managing member, general partner, or "
        "investment committee member in any of the GP entities, and if so, why is that "
        "role not reflected in Form D disclosures?"
    ),
    (
        "The private portfolio Thomas oversees (SpaceX, Anthropic, OpenAI, Shield AI) "
        "consists of companies subject to active federal procurement decisions. Does "
        "Thomas have any formal ethics, recusal, or conflict-of-interest commitments "
        "in connection with Emil Michael's role as Coatue senior advisor and subsequent "
        "USD(R&E) appointment, given Michael's authority over the Defense Innovation "
        "Unit and Office of Strategic Capital — both of which interact directly with "
        "these portfolio companies?"
    ),
    (
        "Thomas's FEC record shows no contributions to Trump committees through 2020. "
        "Are there contributions in the 2021–2024 cycle, when political access to the "
        "incoming administration would have been relevant given Coatue's SpaceX, "
        "Anduril, and Shield AI positions?"
    ),
    (
        "The Thomas And Elizabeth Laffont Family Foundation (EIN 861914134) is "
        "documented as a separate entity. What organizations has it funded, and do "
        "any of those organizations have connections to the defense-tech or AI policy "
        "network documented in this investigation?"
    ),
    (
        "Thomas's early Coatue private bets included Tencent, Meituan, Didi, and "
        "ByteDance. Philippe separately holds a ByteDance board seat. What is Thomas's "
        "current or historical relationship to ByteDance or any of those Chinese "
        "technology positions, and have any been subject to CFIUS review?"
    ),
]

# ── applicable_models ────────────────────────────────────────────────────────
curation["applicable_models"] = [
    {
        "name": "Division of Labor / Regulatory Asymmetry",
        "description": (
            "The Coatue structure separates the disclosed public portfolio (Philippe, "
            "13F-visible) from the undisclosed private portfolio (Thomas, 13F-invisible). "
            "The result is that the portion of the firm with the most direct government "
            "contract exposure has the thinner regulatory footprint. This is not "
            "inherently improper — private fund managers are not required to file 13Fs "
            "— but it means that standard disclosure-based oversight captures the less "
            "consequential half of the firm."
        ),
    },
    {
        "name": "Complementary Political Access",
        "description": (
            "The brothers' FEC records function as a coordinated access strategy: "
            "Philippe donates to Democratic Senate leadership infrastructure, Thomas "
            "to Republican Senate leadership infrastructure. Neither brother is a "
            "pure partisan donor. The combined effect is that Coatue maintains "
            "institutionalized access to both Senate caucuses simultaneously, regardless "
            "of which party holds the majority."
        ),
    },
    {
        "name": "Board Seat as Control Point",
        "description": (
            "Thomas's board seats at OneTrust and Weights & Biases place him in "
            "governance roles at companies that provide infrastructure for data privacy "
            "compliance and AI model development respectively. These are not consumer "
            "products — they are platforms used by enterprises and government agencies. "
            "Board-level control of vendors in these categories represents a structural "
            "position in the AI infrastructure supply chain that is not visible in "
            "fund-level filings."
        ),
    },
]

# ── preserve existing scaffold fields ────────────────────────────────────────
# key_finding_ids and key_identifiers and section_suggestions are preserved as-is
# (already present from auto-generation); only add if not present
curation.setdefault("key_finding_ids", [5823, 5824, 5843, 5353, 5372])
curation.setdefault("key_identifiers", {"jurisdictions": [], "officers": [], "entities": []})

with open(DOSSIER_PATH, "w") as f:
    json.dump(dossier, f, indent=2)

print(f"Wrote curation to {DOSSIER_PATH}")
print(f"  lead: {len(curation['lead'])} chars")
print(f"  system_role: {len(curation['system_role'])} chars")
print(f"  sections: {len(curation['sections'])}")
print(f"  open_questions: {len(curation['open_questions'])}")
print(f"  applicable_models: {len(curation['applicable_models'])}")
