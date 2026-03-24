#!/usr/bin/env python3
"""Curation script for Svend Hardenberg dossier."""

import json
import sys
from datetime import datetime

DOSSIER_PATH = "content/dossiers/svend-hardenberg.json"

LEAD = (
    "<p>Svend Hardenberg is a Greenlandic businessman and former senior civil servant who "
    "now holds simultaneous board and executive positions across three distinct clusters of "
    "US-backed commercial interest in Greenland: "
    "<a href=\"/dossiers/ronald-lauder\">Ronald Lauder</a>'s water and hydropower consortium, "
    "a proposed 1.5-gigawatt AI data center venture with former Trump administration official "
    "<a href=\"/dossiers/drew-horn\">Drew Horn</a>, and the Kvanefjeld rare-earth and uranium "
    "deposit controlled by Energy Transition Minerals (ASX: ETM) [Finding #6356]. "
    "No other Greenlandic private-sector figure is documented as bridging all three of those "
    "networks simultaneously [Finding #6376].</p>"
    "\n\n"
    "<p>Hardenberg served as Permanent Secretary of the Greenland Premier's Office before "
    "departing government roughly a decade ago, and subsequently as Chief Executive of "
    "Nukissiorfiit, Greenland's national energy utility [Finding #6288]. Danish business "
    "registry records document 21 directorial and ownership positions across entities "
    "incorporated in Greenland and Denmark, including direct control of Qappik ApS, "
    "Amaroq ApS, Greenland Invest ApS (50–66.65% stake), and Inuit Development Company "
    "ApS, as well as a dissolved UK entity, Inuit Development Company London Ltd "
    "(Companies House 13273140) [Finding #6361].</p>"
    "\n\n"
    "<p>His co-ownership of Greenland Water Bank ApS alongside Jørgen Wæver Johansen — "
    "chairman of the ruling Siumut party and husband of Greenland Foreign Minister "
    "Vivian Motzfeldt — and the subsequent partial sale of that stake to the Lauder "
    "consortium's vehicle <a href=\"/dossiers/greenland-development-partners-llc\">"
    "Greenland Development Partners LLC</a> places Hardenberg at the commercial "
    "intersection of the Lauder investment program and Greenlandic political leadership "
    "[Finding #6318] [Finding #6284].</p>"
)

SYSTEM_ROLE = (
    "Hardenberg functions as the indispensable Greenlandic intermediary for US commercial "
    "interests in Greenland's resource economy. His value to each of the three networks he "
    "bridges derives from the same underlying asset: government-grade access built during "
    "his tenure as Permanent Secretary and national energy CEO, now deployed commercially "
    "across competing and potentially conflicting positions in water, hydropower, rare earths, "
    "uranium, AI infrastructure, and blue economy ventures."
)

SECTIONS = [
    {
        "id": "government-career",
        "title": "Government Career and Institutional Access",
        "content": (
            "<p>Hardenberg rose to the peak of Greenlandic public administration as Permanent "
            "Secretary of the Premier's Office, making him among the most senior non-elected "
            "officials in the Greenlandic Self-Government. He was subsequently appointed Chief "
            "Executive of Nukissiorfiit, the state-owned entity responsible for Greenland's "
            "electricity, water, and heating infrastructure [Finding #6288]. "
            "His departure from government — described in reporting as a firing approximately "
            "a decade before 2026 — preceded the commercial career he has since built "
            "[Finding #6167]. The institutional contacts, regulatory familiarity, and "
            "credibility accumulated in those roles are the foundation of his current "
            "brokering function for external investors.</p>"
            "\n\n"
            "<p>His transition to commercial activity began no later than 2015, when Danish "
            "registry records show him taking a 50–66.65% stake in Greenland Invest ApS "
            "(CVR 12713460) [Finding #6361]. The Nanoq Power ApS chairmanship follows from "
            "December 2016, consistent with a pivot toward energy project development "
            "following his Nukissiorfiit tenure. Greenland Development A/S, which Hardenberg "
            "previously chaired, reflects a pattern of using dedicated Greenland-branded "
            "holding and development structures [Finding #6334].</p>"
        ),
        "viz": "timeline",
    },
    {
        "id": "lauder-consortium",
        "title": "Lauder Consortium and Greenland Water Bank",
        "content": (
            "<p>Hardenberg and Jørgen Wæver Johansen co-founded Greenland Invest ApS, "
            "which holds the parent position in Greenland Water Bank ApS "
            "(CVR 12941218, incorporated 2016). The Water Bank bottles Lyngmark Spring "
            "water from Disko Island under the Imivik brand. Danish corporate registry data "
            "records a 2024 annual result of −20,014 DKK against total assets of 699,000 DKK, "
            "indicating a loss-making operation at present scale [Finding #6284].</p>"
            "\n\n"
            "<p><a href=\"/dossiers/ronald-lauder\">Ronald Lauder</a>'s Delaware vehicle, "
            "<a href=\"/dossiers/greenland-development-partners-llc\">Greenland Development "
            "Partners LLC</a>, acquired partial stakes in both Greenland Water Bank and "
            "Greenland Investment Group. As of the July 2025 board appointment recorded in "
            "the Danish registry, Josette Sheeran chairs the Greenland Water Bank board "
            "alongside Hardenberg and Johansen [Finding #6318]. Sheeran separately chairs "
            "and serves as CEO of Greenland Investment Group, Lauder's principal Greenlandic "
            "operating entity, which is competing for the Tasersiaq hydroelectric concession "
            "(rated 680–2,250 MW) [Finding #6284].</p>"
            "\n\n"
            "<p>The Greenland Water Bank partial-stake sale to the Lauder consortium was "
            "jointly executed by Hardenberg and Johansen [Finding #6167]. Johansen's "
            "simultaneous position as Siumut party chairman and husband of Foreign Minister "
            "Vivian Motzfeldt — who previously sat on the Greenland Water Bank board — "
            "was documented by Greenlandic newspaper Sermitsiaq as a political conflict of "
            "interest [Finding #6333]. Hardenberg's presence on the same board places him "
            "inside that documented governance overlap.</p>"
        ),
        "viz": "ego_network",
    },
    {
        "id": "horn-data-center",
        "title": "Drew Horn Partnership: Data Center and Seaweed Ventures",
        "content": (
            "<p><a href=\"/dossiers/drew-horn\">Drew Horn</a> served in the Trump "
            "administration as Chief of Staff and Acting Principal Deputy Assistant Secretary "
            "at the Department of Energy's Office of International Affairs, as Associate "
            "Director of Policy for Vice President Pence, and as Senior Advisor to the "
            "Director of National Intelligence. He founded <a href=\"/dossiers/greenmet\">"
            "GreenMet</a> in January 2021 immediately after leaving government "
            "[Finding #6176 from drew-horn.json].</p>"
            "\n\n"
            "<p>Hardenberg's Inuit Development Company ApS signed a letter of intent with "
            "Horn's AmForge Corporation for a proposed AI data center in Kangerlussuaq, "
            "initially rated at 300 MW with a stated scaling target of 1.5 GW by 2028, "
            "to be powered by Greenlandic hydropower [Finding #6167]. Horn describes the "
            "division of labor in published statements: \"He handles everything related to "
            "Greenland and Denmark, I handle everything related to the United States\" "
            "[Finding #6354]. GreenMet's role is advisory — Hardenberg approached Horn to "
            "identify a US corporate partner, and GreenMet continues as an advisor for "
            "securing US government investment — rather than a formal joint-venture position "
            "[Finding #6354].</p>"
            "\n\n"
            "<p>As of reporting, the project had not secured land or regulatory approvals, "
            "and Greenland's Department of Business had not entered into dialogue with Horn "
            "or GreenMet [Finding #6167]. Hardenberg and Horn are also partners on a seaweed "
            "treatment project modeled on Royal Greenland's state-owned seaweed operation, "
            "constituting a multi-project commercial relationship rather than a "
            "single-transaction engagement [Finding #6355].</p>"
            "\n\n"
            "<p>GreenMet's minority shareholders include George Sorial, former Executive "
            "Vice President of the Trump Organization, and Keith Schiller, Trump's former "
            "personal bodyguard [Finding #6290 from drew-horn.json]. The data center project "
            "therefore connects Hardenberg to a Trump-aligned commercial network whose other "
            "members include figures with concurrent foreign agent registrations and federal "
            "lobbying activity [Finding #6376].</p>"
        ),
        "viz": None,
    },
    {
        "id": "etm-kvanefjeld",
        "title": "Energy Transition Minerals and Kvanefjeld",
        "content": (
            "<p>In May 2025, Hardenberg was appointed Chair of ETM Greenland A/S and General "
            "Manager Greenland for Energy Transition Minerals (ASX: ETM), the Australian "
            "listed company that controls the Kvanefjeld rare-earth and uranium deposit in "
            "southern Greenland [Finding #6356]. ETM Greenland A/S is the operating "
            "subsidiary through which that deposit is managed. Chinese state-linked company "
            "Shenghe Resources holds approximately 7% of ETM [Finding #6133], creating a "
            "disclosed Chinese equity interest in the deposit over which Hardenberg now "
            "serves as the on-the-ground executive.</p>"
            "\n\n"
            "<p>Kvanefjeld is a separate deposit from Tanbreez, the rare-earth asset that "
            "GreenMet's Horn brokered into Critical Rare Metals Ltd (CRML, formerly "
            "Greenland Resources Inc). The two deposits are operated by different corporate "
            "structures, different listed vehicles, and different external investor groups. "
            "Hardenberg's concurrent involvement with both Horn's Tanbreez-adjacent "
            "commercial activities and ETM's Kvanefjeld operations means he holds executive "
            "positions in competing Greenlandic rare-earth interests [Finding #6356].</p>"
            "\n\n"
            "<p>Danish registry records show the ETM Greenland A/S appointment alongside "
            "board roles at Imivik of Greenland ApS (from August 2025) and Greenland "
            "Minerals A/S (from October 2024), with the latter being the ETM subsidiary "
            "through which the Kvanefjeld project has historically been organized "
            "[Finding #6361]. The sequence of appointments — Greenland Minerals A/S in "
            "October 2024, then ETM Greenland A/S chair in May 2025 — tracks the "
            "consolidation of ETM's Greenlandic management under Hardenberg.</p>"
        ),
        "viz": None,
    },
    {
        "id": "corporate-structure",
        "title": "Corporate Structure",
        "content": (
            "<p>Danish registry ownr.dk documents 21 directorial and ownership positions for "
            "Hardenberg as of mid-2025 [Finding #6361]. The core vehicles break into three "
            "functional groups:</p>"
            "\n\n"
            "<p><strong>Personal holding and consulting entities:</strong> Qappik ApS "
            "(CVR 43890484, 100% ownership, founded 2023) functions as his primary consulting "
            "vehicle. Amaroq ApS (CVR 42270458, 100% ownership, founded 2024) is a "
            "recently-incorporated personal holding entity. Greenland Invest ApS "
            "(CVR 12713460, 50–66.65% stake held since 2015) is the co-founding vehicle "
            "shared with Johansen that sits above Greenland Water Bank.</p>"
            "\n\n"
            "<p><strong>US-partnership vehicles:</strong> Inuit Development Company ApS "
            "(Danish-registered, chair since 2024) is the entity through which the AmForge "
            "data center letter of intent was signed. A now-dissolved UK counterpart, "
            "Inuit Development Company London Ltd (Companies House 13273140), was "
            "incorporated in March 2021, likely predating the AmForge engagement and "
            "consistent with a period of attempted UK-side structuring that was subsequently "
            "abandoned [Finding #6361].</p>"
            "\n\n"
            "<p><strong>Sector-specific positions:</strong> Nanoq Power ApS (chair since "
            "December 2016) reflects a long-standing energy project structure. ETM Greenland "
            "A/S (chair from May 2025) is the Kvanefjeld operational entity. Greenland "
            "Minerals A/S (board from October 2024) is the earlier ETM Greenland subsidiary. "
            "Imivik of Greenland ApS (chair from August 2025) is the Disko Island water "
            "brand vehicle held through the Greenland Water Bank corporate chain.</p>"
            "\n\n"
            "<p>Mannvit ApS appears in some registry records as a vehicle through which "
            "Hardenberg has held CEO-level roles; it is distinct from the Icelandic "
            "engineering firm Mannvit hf and its Danish subsidiary [Finding #6334]. The "
            "proliferation of vehicles across Greenland, Denmark, and the dissolved UK "
            "entity is consistent with a structuring approach designed to match the "
            "jurisdictional expectations of different foreign investor counterparties.</p>"
        ),
        "viz": None,
    },
]

OPEN_QUESTIONS = [
    (
        "What specific terms govern Hardenberg's equity or compensation arrangements with "
        "the Lauder consortium — specifically, what consideration was paid by Greenland "
        "Development Partners LLC for its stakes in Greenland Water Bank and Greenland "
        "Investment Group, and what stake Hardenberg retained after the partial sale?"
    ),
    (
        "What is the current regulatory status of the Kvanefjeld deposit under ETM's "
        "management, given that the Greenlandic parliament previously passed a zero-tolerance "
        "uranium policy that blocked the project, and whether Hardenberg's appointment "
        "as General Manager Greenland represents a strategy to re-engage on licensing?"
    ),
    (
        "Do Hardenberg's concurrent executive positions at ETM Greenland A/S (Kvanefjeld) "
        "and his advisory and commercial relationships with the GreenMet/Horn network "
        "(Tanbreez-adjacent) create a legally cognizable conflict under Greenlandic "
        "or Danish fiduciary law, and has any such conflict been disclosed to ETM's board?"
    ),
    (
        "What became of Inuit Development Company London Ltd (Companies House 13273140), "
        "dissolved after being incorporated in March 2021: what activity did it conduct "
        "before dissolution, and which counterparties were engaged through the UK vehicle "
        "rather than the Danish ApS structure?"
    ),
    (
        "What is the ownership structure and capitalization of AmForge Corporation, "
        "Horn's counterparty entity in the data center letter of intent, and who are "
        "its investors beyond Horn himself?"
    ),
    (
        "Greenland's Department of Business stated it had not entered into dialogue with "
        "Horn or GreenMet regarding the Kangerlussuaq data center project. Has it engaged "
        "with Hardenberg's Inuit Development Company ApS directly, and what land and "
        "permitting approvals would be required for a project of 300 MW initial capacity?"
    ),
]

APPLICABLE_MODELS = [
    "bridge-tax",
    "revolving-door",
    "jurisdictional-arbitrage",
    "conflict-of-interest-disclosure-gap",
]


def main():
    with open(DOSSIER_PATH, "r") as f:
        dossier = json.load(f)

    curation = dossier.get("curation", {})
    curation["lead"] = LEAD
    curation["system_role"] = SYSTEM_ROLE
    curation["sections"] = SECTIONS
    curation["open_questions"] = OPEN_QUESTIONS
    curation["applicable_models"] = APPLICABLE_MODELS
    curation["curated_at"] = datetime.utcnow().isoformat()

    dossier["curation"] = curation

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote curation to {DOSSIER_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
