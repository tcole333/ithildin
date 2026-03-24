#!/usr/bin/env python3
"""Write curation fields into content/dossiers/alt5-sigma-corp.json"""

import json
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/alt5-sigma-corp.json")

with open(DOSSIER_PATH) as f:
    dossier = json.load(f)

curation = dossier.setdefault("curation", {})

# ── system_role ──────────────────────────────────────────────────────────────
curation["system_role"] = (
    "ALT5 Sigma Corp (NASDAQ: ALTS, CIK 0000862861) is a Nevada-incorporated public company "
    "that in August 2025 reoriented itself as a treasury vehicle for World Liberty Financial "
    "(WLFI) governance tokens. Its 41-year corporate history began as Appliance Recycling "
    "Centers of America (Minnesota, 1983), transitioned to pharmaceutical company JanOne Inc "
    "(reincorporated Nevada 2018, renamed September 2019), and became ALT5 Sigma Corp on "
    "July 15, 2024. The company's primary documented function in the WLFI network is to "
    "provide SEC-regulated public-market access for WLFI token holdings: ALT5 received "
    "approximately 7.3 billion WLFI tokens — face-valued at $1.5 billion — through a "
    "registered direct offering at $7.50 per share (200 million shares). Zach Witkoff, "
    "CEO of WLFI and son of Trump special envoy Steve Witkoff, was appointed ALT5 Chairman "
    "following the offering. Eric Trump, named as a WLFI Promoter on SEC Form D, was "
    "designated board observer, then quietly removed. The offering closed in mid-August 2025; "
    "two weeks later the company disclosed that its Canadian subsidiary had been convicted of "
    "money laundering by a Rwandan court on May 7, 2025 — a conviction not disclosed before "
    "the offering closed. By November 2025 ALT5 had cycled through three CEOs and three "
    "auditors in six weeks and faced Nasdaq delisting for failure to file its 10-Q. The "
    "company's primary asset remains approximately $1.3 billion in WLFI tokens, which are "
    "illiquid governance tokens with no guaranteed secondary market."
)

# ── lead ─────────────────────────────────────────────────────────────────────
curation["lead"] = (
    "<p>ALT5 Sigma Corp (NASDAQ: ALTS) is a publicly traded Nevada shell that became the "
    "SEC-regulated treasury vehicle for <a href='/dossiers/world-liberty-financial'>World "
    "Liberty Financial</a> governance tokens in August 2025. The company traces its "
    "corporate lineage to a 1983 Minnesota appliance recycler, was reincorporated in Nevada "
    "in 2018 and renamed JanOne Inc (a pharmaceutical concern), then rebranded as ALT5 Sigma "
    "Corp on July 15, 2024 [Finding #4190]. Its prior CEO, Jon Isaac, faces SEC fraud "
    "charges dating to 2021 for inflating earnings and conducting secret stock sales at "
    "JanOne and its affiliate Live Ventures; Isaac left before the 2024 rebrand but retained "
    "over one million ALTS shares, and his brother Tony Isaac was subsequently appointed "
    "Acting CEO in November 2025.</p>"

    "<p>In August 2025 ALT5 announced a $1.5 billion registered direct offering — 200 million "
    "shares at $7.50 — for the purpose of holding WLFI tokens as a treasury asset. The "
    "offering delivered approximately 7.3 billion WLFI governance tokens, face-valued at "
    "$1.5 billion but illiquid and without a guaranteed secondary market. WLFI granted itself "
    "the right to nominate two directors: <a href='/dossiers/zachary-witkoff'>Zach Witkoff</a> "
    "was appointed Chairman and <a href='/dossiers/zach-folkman'>Zachary Folkman</a> as "
    "director. <a href='/dossiers/eric-trump'>Eric Trump</a> was designated board observer — "
    "a classification required because Nasdaq rules barred him from serving as a full director "
    "— then quietly removed from that role [Finding #4200, #4270]. The practical effect is "
    "that ALT5's primary asset is a governance token issued by the same entity whose "
    "principals now control the ALT5 board, creating a circular valuation structure in which "
    "both entities' stated values depend on each other.</p>"

    "<p>Two weeks after the offering closed, ALT5 disclosed via SEC 8-K that its Canadian "
    "subsidiary had been convicted of money laundering and illicit enrichment by the "
    "Intermediate Court of Nyarugenge, Rwanda, with the conviction dated May 7, 2025 — "
    "months before the offering. Former subsidiary principal Andre Beauchesne was sentenced "
    "to imprisonment and the court ordered confiscation of approximately $3.5 million and "
    "dissolution of the subsidiary [Finding #4193]. The board launched an internal review "
    "of potential misstatements in prior financial statements, and law firm Hagens Berman "
    "opened a securities fraud investigation in December 2025.</p>"
)

# ── sections ─────────────────────────────────────────────────────────────────
curation["sections"] = [
    {
        "id": "corporate-history",
        "title": "Corporate History",
        "viz": None,
        "finding_ids": [4190],
        "connection_ids": [2521],
        "content": (
            "<p>The corporate structure underlying ALT5 Sigma Corp spans four decades and "
            "three distinct business identities. Appliance Recycling Centers of America "
            "was incorporated in Minnesota in 1983 and operated as a household appliance "
            "retailer and recycler for more than three decades. In 2018 the company "
            "reincorporated in Nevada and the following year rebranded as JanOne Inc, "
            "repositioning as a pharmaceutical holding company focused on pain management "
            "therapies. The Nevada reincorporation and pharma pivot coincided with a period "
            "of SEC scrutiny: Jon Isaac, who served as CEO of JanOne and simultaneously "
            "ran the related public company Live Ventures Inc, faces a civil fraud action "
            "brought by the SEC in 2021 (SEC Litigation Release 25155) alleging he "
            "artificially inflated JanOne's earnings and conducted undisclosed stock sales. "
            "Isaac was not part of the July 2024 rebrand to ALT5 Sigma Corp, but the SEC "
            "litigation remained active and he retained over one million ALTS shares. "
            "His brother Tony Isaac was appointed Acting CEO in November 2025 during the "
            "governance collapse following the WLFI transaction [Finding #4190; "
            "SEC Litigation Release 25155].</p>"

            "<p>The July 15, 2024 rebrand to ALT5 Sigma Corp, announced via PR Newswire, "
            "positioned the company as a blockchain-era fintech operating under SIC code "
            "6221 (Commodity Contracts Dealers/Brokers) — later changed to 2834 — with "
            "SEC CIK 0000862861 retained through all name changes. The company's "
            "operational history across three sectors (recycling, pharmaceuticals, fintech) "
            "with overlapping SEC enforcement exposure on the pharma iteration is the "
            "baseline institutional context into which the WLFI offering was introduced "
            "in August 2025.</p>"
        ),
    },
    {
        "id": "wlfi-transaction-structure",
        "title": "WLFI Transaction Structure",
        "viz": "ego_network",
        "finding_ids": [4200, 4270],
        "connection_ids": [2165, 2520, 2521, 2529],
        "content": (
            "<p>The August 2025 WLFI transaction introduced a financial structure with "
            "interlocking valuation dependencies between ALT5 and <a href='/dossiers/"
            "world-liberty-financial'>World Liberty Financial</a>. ALT5 conducted a "
            "$1.5 billion registered direct offering — 200 million shares at $7.50 per "
            "share — with proceeds deployed to acquire approximately 7.3 billion WLFI "
            "governance tokens at a face value of $0.20 each. The WLFI tokens are "
            "described in disclosure documents as illiquid governance tokens with no "
            "guaranteed secondary market. ALT5's balance sheet therefore rests primarily "
            "on a $1.3 billion token holding whose stated value derives from the same "
            "token face price used to size the original offering [Finding #4200].</p>"

            "<p>As a condition of the transaction, WLFI obtained the right to nominate "
            "two directors to the ALT5 board. <a href='/dossiers/zachary-witkoff'>Zach "
            "Witkoff</a> — CEO of WLFI, signatory on WLFI SEC Form 3, and son of Trump "
            "special envoy <a href='/dossiers/steve-witkoff'>Steve Witkoff</a> — was "
            "appointed Chairman [Connection #2165; BusinessWire Aug 13 2025]. "
            "<a href='/dossiers/zach-folkman'>Zachary Folkman</a>, WLFI co-founder, "
            "was appointed director. <a href='/dossiers/eric-trump'>Eric Trump</a>, "
            "listed as a WLFI Promoter on SEC Form D, was initially designated as a "
            "board director but was reclassified to board observer status to comply with "
            "Nasdaq independence rules, and was later quietly removed from that role "
            "entirely [Connection #2529; CoinTelegraph Sep 10 2025; SEC filing Aug 25 "
            "2025]. The net result of these board appointments is that the entity whose "
            "tokens constitute ALT5's primary asset controls the ALT5 board.</p>"

            "<p>A January 2026 Master Loan and Security Agreement between ALT5 and WLFI "
            "added another layer to the relationship. ALT5 drew the full amount under "
            "that facility, netting $14.2 million, which it deployed into share buybacks "
            "and additional WLFI token purchases — further deepening the mutual financial "
            "dependency [Finding #4270; SEC filing https://www.sec.gov/Archives/edgar/"
            "data/862861/000164117225026082/form8-k.htm].</p>"
        ),
    },
    {
        "id": "governance-collapse",
        "title": "Governance Collapse",
        "viz": None,
        "finding_ids": [4200],
        "connection_ids": [],
        "content": (
            "<p>Between October and December 2025 ALT5 experienced rapid executive and "
            "auditor turnover that coincided with the disclosure of the Rwandan conviction "
            "and the initiation of securities fraud investigations. Three CEOs departed "
            "or were removed within six weeks: CEO Tassiopoulos was suspended in October "
            "2025; Hugh was terminated in November 2025; Tony Isaac — brother of the "
            "former JanOne CEO facing SEC fraud charges — was appointed Acting CEO in "
            "November 2025. The company also cycled through three auditors during the "
            "same six-week period [Finding #4200; CoinDesk Nov 27 2025].</p>"

            "<p>By November 12, 2025, ALT5 had filed an SEC NT 10-Q notification of "
            "late filing, indicating it could not meet its quarterly reporting deadline. "
            "Nasdaq issued a delisting notice for failure to file the 10-Q. The board "
            "simultaneously conducted an internal review of prior financial statements "
            "following the August 29 conviction disclosure, examining whether the "
            "Rwandan proceedings should have been disclosed before the August offering "
            "closed [Finding #4200; SEC NT 10-Q Nov 12 2025].</p>"
        ),
    },
    {
        "id": "legal-proceedings",
        "title": "Legal Proceedings",
        "viz": "timeline",
        "finding_ids": [4193, 4211],
        "connection_ids": [],
        "content": (
            "<p>ALT5 faces legal exposure on two separate tracks. The first is the "
            "Rwandan conviction of its Canadian subsidiary. On May 7, 2025, the "
            "Intermediate Court of Nyarugenge convicted the subsidiary of money "
            "laundering and illicit enrichment. Former subsidiary principal Andre "
            "Beauchesne was sentenced to imprisonment. The court ordered confiscation "
            "of approximately $3.5 million USD and dissolution of the subsidiary. The "
            "conviction was not disclosed publicly until August 29, 2025 — two weeks "
            "after the $1.5 billion WLFI offering closed in mid-August. The disclosure "
            "came via SEC 8-K and triggered the board's internal financial-statement "
            "review. Law firm Hagens Berman opened a securities fraud investigation in "
            "December 2025, citing the timing gap between the May conviction and the "
            "August offering as the central factual predicate [Finding #4193; SEC 8-K "
            "Aug 29 2025; TheBlock.co Nov 2025; Hagens Berman investigation notice "
            "Dec 2025].</p>"

            "<p>The second track is a trade secret case filed and quickly abandoned. "
            "On November 18, 2025, ALT5 filed suit in the District of Delaware "
            "(D. Del. 1:25-cv-01407) against Wellington Peel LLC, Prime Delta Corp, "
            "Hugues Benoit, and Jean-Francois Amyot, seeking a temporary restraining "
            "order and expedited proceedings for alleged trade secret misappropriation. "
            "Eight days later, on November 26, 2025, ALT5 voluntarily dismissed the "
            "case without prejudice. The filing window — during the peak of the "
            "governance crisis — and the rapid dismissal are documented in CourtListener "
            "docket 71937263 but no public explanation for the dismissal was provided "
            "[Finding #4211].</p>"

            "<p>Separately, Jon Isaac — whose tenure as JanOne CEO directly precedes "
            "ALT5's current structure — remains a defendant in an active SEC civil "
            "enforcement action (SEC Litigation Release 25155) for alleged earnings "
            "inflation and undisclosed stock sales. Isaac's continued share ownership "
            "and his brother's appointment as Acting CEO during the governance crisis "
            "create an unresolved question about the continuity of management culture "
            "across the JanOne-to-ALT5 transition [Connection #2521].</p>"
        ),
    },
]

# ── open_questions ────────────────────────────────────────────────────────────
curation["open_questions"] = [
    (
        "The Rwandan court convicted the Canadian subsidiary on May 7, 2025, and ALT5 "
        "did not disclose this in its SEC filings until August 29, 2025 — after the "
        "$1.5 billion offering closed. What did ALT5's board and counsel know about "
        "the conviction, and when did they know it? Were the offering documents reviewed "
        "by outside securities counsel aware of the pending or completed Rwandan "
        "proceedings?"
    ),
    (
        "The WLFI tokens held as ALT5's primary asset are illiquid governance tokens "
        "valued at face price ($0.20 each). What independent valuation methodology, "
        "if any, was applied to determine the $1.5 billion offering size, and did "
        "any of ALT5's three auditors formally opine on the fair market value of "
        "the token holding?"
    ),
    (
        "Jon Isaac, the former JanOne CEO facing SEC civil fraud charges for earnings "
        "inflation and secret stock sales, retained over one million ALTS shares after "
        "departing. Has he sold any shares since the August 2025 offering — and if so, "
        "do those sales constitute reportable transactions under his pending SEC "
        "enforcement action?"
    ),
    (
        "The November 2025 trade secret suit (D. Del. 1:25-cv-01407) named Wellington "
        "Peel LLC, Prime Delta Corp, Hugues Benoit, and Jean-Francois Amyot — and was "
        "dismissed eight days later. What was the specific trade secret at issue, and "
        "what relationship, if any, do the defendants have to the WLFI token treasury "
        "strategy or to the departed executives Tassiopoulos or Hugh?"
    ),
    (
        "Eric Trump was initially designated as a full board director, then reclassified "
        "as a board observer to satisfy Nasdaq independence rules, and later removed "
        "entirely. What governance process governed each of these changes, and did WLFI "
        "retain its right to nominate two directors after Trump's removal, or did that "
        "seat pass to another WLFI-affiliated person?"
    ),
]

# ── applicable_models ─────────────────────────────────────────────────────────
curation["applicable_models"] = [
    "shell-company",
    "circular-valuation",
    "disclosure-timing",
    "bridge-tax",
]

# Preserve existing fields
curation.setdefault("key_finding_ids", [4193, 4200, 4190, 4211, 4270])
curation.setdefault("key_identifiers", {"jurisdictions": [], "officers": [], "entities": []})
curation.setdefault("section_suggestions", [])

with open(DOSSIER_PATH, "w") as f:
    json.dump(dossier, f, indent=2)

print("Curation written to", DOSSIER_PATH)
