#!/usr/bin/env python3
"""Curation script for Ronald Lauder dossier."""

import json
from datetime import datetime, timezone
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/ronald-lauder.json")


def build_curation() -> dict:
    lead = (
        "<p>Ronald Stephen Lauder (born November 26, 1944) is an American billionaire, "
        "heir to the Estée Lauder cosmetics fortune, and longtime personal friend of Donald Trump "
        "dating to their shared undergraduate years at the Wharton School of the University of "
        "Pennsylvania. He served as U.S. Ambassador to Austria under President Reagan (1986–1987) "
        "and as Deputy Assistant Secretary of Defense for European and NATO policy. He chairs the "
        "World Jewish Congress and the Ronald S. Lauder Foundation, and serves as a trustee of "
        "the Museum of Modern Art. His SEC CIK is 0000942617 and his LittleSis ID is 5617.</p>"
        "<p>FEC records confirm Lauder donated $5,000,000 to MAGA Inc in March 2025, $1,000,000 "
        "to the Trump Vance Inaugural Committee in December 2024, $250,000 to Security Is Strength "
        "PAC in November 2025, and $150,000 each to Grow The Majority and One Team Senate Majority "
        "in December 2025, among other contributions to NRCC and individual Republican "
        "lawmakers. [Finding #6163] [Finding #6323]</p>"
        "<p>Former National Security Advisor John Bolton has stated that Lauder originated the idea "
        "of a U.S. purchase of Greenland in Trump's mind. While Trump publicly advanced that "
        "proposal, Lauder simultaneously built a private investment portfolio in Greenland through "
        "Greenland Development Partners LLC (Delaware), acquiring ownership stakes in Greenland "
        "Water Bank and Greenland Investment Group. The consortium is chaired by Josette Sheeran, "
        "former Under Secretary of State under Condoleezza Rice. Lauder's Greenland business "
        "partners include Jørgen Wæver Johansen, husband of Greenland's sitting Foreign Minister "
        "Vivian Motzfeldt, who herself previously served on the Greenland Water Bank board. "
        "[Finding #6119] [Finding #6165] [Finding #6294]</p>"
        "<p>Kevin Warsh, Trump's nominated Federal Reserve Chair as of March 4, 2026, is married "
        "to Jane Lauder, Ronald Lauder's granddaughter. [Finding #6330] ICIJ Offshore Leaks "
        "records show Ronald S. Lauder as an officer of Tech Water, Ltd. (Bermuda), registered "
        "at the same two Bermuda addresses used by Jeffrey Epstein's Liquid Funding, Ltd. "
        "[Finding #4898] A separate connection to the Epstein network runs through "
        '<a href="/dossiers/jacqui-safra">Jacqui Safra</a>, '
        "who negotiated with Lauder over the sale of a Jerusalem property before the deal fell "
        "through and the property was subsequently offered to Epstein. [Connection #1988]</p>"
    )

    system_role = (
        "Lauder illustrates how a private investor with a decades-long personal relationship "
        "to a sitting president can function as a policy originator — planting a geopolitical "
        "concept publicly attributed to sovereign interest while simultaneously positioning "
        "private capital to benefit from that policy's execution. The Greenland portfolio "
        "concentrates multiple conflict layers in a single structure: the policy architect "
        "also holds the investment; the investment's local partner is the husband of the "
        "official responsible for the counterparty government's foreign policy; and the "
        "investor's family member controls the monetary institution whose rate decisions "
        "would affect the cost of capital for those very investments. No registered lobbying "
        "or FARA filings exist for any participant in this structure."
    )

    sections = [
        {
            "id": "trump-relationship-and-policy-origin",
            "title": "Trump Relationship and Greenland Policy Origin",
            "viz": None,
            "finding_ids": [6119, 6165],
            "connection_ids": [3161, 3220],
            "body": (
                "<p>Ronald Lauder and Donald Trump have known each other since at least their "
                "undergraduate years at Wharton. Former National Security Advisor John Bolton "
                "identified Lauder as the person who first planted the idea of purchasing "
                "Greenland in Trump's mind. In February 2025, Lauder published an op-ed in the "
                "<em>New York Post</em> titled \u201cI\u2019m a Greenland expert \u2014 these 3 paths can make "
                "it America\u2019s next frontier,\u201d in which he wrote: \u201cTrump\u2019s Greenland concept was "
                "never absurd \u2014 it was strategic\u201d and \u201cI have worked closely with Greenland\u2019s "
                "business and government leaders for years to develop strategic investments there.\u201d "
                "[Finding #6165] This public statement is notable because it was published while "
                "Lauder held active ownership stakes in Greenlandic operating companies — he was "
                "not a disinterested commentator on U.S. Arctic policy but a named investor in "
                "the territory whose acquisition he was endorsing.</p>"
                "<p>Lauder and Trump's relationship is documented in LittleSis records and "
                "corroborated by Fortune reporting as of January 30, 2026. [Connection #3220] "
                "FEC records show Lauder contributed $5,000,000 to MAGA Inc on March 24, 2025, "
                "using a self-employed designation from New York City, alongside $1,000,000 to "
                "the Trump Vance Inaugural Committee on December 16, 2024. The total documented "
                "political spend in the 2024–2025 cycle exceeds $6.7 million in confirmed FEC "
                "filings. [Finding #6163]</p>"
            ),
        },
        {
            "id": "greenland-investment-structure",
            "title": "Greenland Investment Structure",
            "viz": None,
            "finding_ids": [6119, 6171, 6294, 6317],
            "connection_ids": [3152, 3184, 3185, 3219],
            "body": (
                "<p>Lauder's Greenland investments operate through a three-tier structure. "
                "Greenland Development Partners LLC, a Delaware-registered consortium with no "
                "registered agent or formation date publicly disclosed, serves as the U.S. "
                "investment vehicle. Its confirmed members are Lauder and "
                '<a href="/dossiers/josette-sheeran">Josette Sheeran</a>, '
                "who chairs the portfolio. [Finding #6317] Delaware registration was chosen; "
                "no EDGAR filings exist specific to GDP LLC, no lobbying disclosures, and no "
                "FARA registrations for any consortium participant. [Finding #6294]</p>"
                "<p>GDP LLC holds ownership stakes in two Greenlandic operating entities. "
                "Greenland Investment Group ApS is the primary operating vehicle; Sheeran "
                "chairs and serves as CEO. GIG has bid on a hydroelectric concession at "
                "Lake Tasersiaq, Greenland's largest lake, which would power an aluminium "
                "smelter. Greenland Water Bank ApS bottles spring water from Lyngmark Spring "
                "on Disko Island under the Imivik brand on a 20-year license; the company "
                "was operating at a loss after nearly a decade of operation before the "
                "Lauder consortium's entry. [Finding #6171]</p>"
                "<p>The Greenland-side partners are "
                '<a href="/dossiers/svend-hardenberg">Svend Hardenberg</a>, '
                "a former Greenlandic government civil servant and energy executive, and "
                "Jørgen Wæver Johansen, a former Greenlandic MP and four-time cabinet minister "
                "who chairs the governing Siumut party in Nuuk. Hardenberg and Johansen "
                "co-owned Greenland Water Bank and sold partial stakes to the Lauder "
                "consortium. [Connection #3152] [Connection #3185] Johansen is also "
                "co-founder of Greenland Investment Group, the entity Sheeran now chairs. "
                "[Finding #6333]</p>"
                "<p>Josette Sheeran's background adds a diplomatic layer to the structure. "
                "She served as Deputy U.S. Trade Representative (2001–2005) and Under "
                "Secretary of State for Economic Growth, Energy, and the Environment under "
                "Condoleezza Rice (2005–2007), then led the UN World Food Programme "
                "(2006–2012). Prior to her diplomatic career she edited the "
                "<em>Washington Times</em> as a member of the Unification Church. She was "
                "subsequently nominated as a director of Cyabra Strategy and served on the "
                "Canoo board. [Finding #6160] Lauder deployed her as Chair/CEO of GIG to "
                "lead the Greenland portfolio. [Connection #3184]</p>"
            ),
        },
        {
            "id": "political-conflict-greenland",
            "title": "Conflict Structure: Investment, Policy, and Governance",
            "viz": "ego_network",
            "finding_ids": [6126, 6161, 6174, 6296, 6333],
            "connection_ids": [3185, 3161],
            "body": (
                "<p>The Greenland investment structure concentrates multiple conflict-of-interest "
                "layers. Lauder is identified by Bolton as the originator of the U.S. Greenland "
                "acquisition concept while simultaneously holding equity in Greenlandic companies "
                "that would benefit from increased U.S. engagement or a sovereignty transfer. "
                "Lauder's February 2025 op-ed, published under his own byline, publicly advocates "
                "for U.S. Greenland policy while disclosing that he has spent years cultivating "
                "relationships with Greenland's business and government leaders — relationships "
                "that produced his current investment positions. [Finding #6165]</p>"
                "<p>The local political dimension centers on Jørgen Wæver Johansen. Johansen "
                "chairs the Siumut party, which governs Greenland. His wife, Vivian Motzfeldt, "
                "has served as Greenland's Minister of Foreign Affairs and Statehood since 2022 "
                "and is responsible for Greenland's sovereign response to U.S. acquisition "
                "pressure. Motzfeldt previously served on the board of Greenland Water Bank — "
                "the same operating entity her husband co-owned and partially sold to the "
                "Lauder consortium. Her board tenure predated the American investment, but "
                "it documents her prior direct involvement with the company. [Finding #6296] "
                "Johansen has publicly dismissed concerns about the arrangement as fabricated "
                "controversy. Danish media, including Politiken, has reported on the conflict, "
                "and Greenlandic outlet Sermitsiaq has documented the concerns. [Finding #6333]</p>"
                "<p>Motzfeldt's position is structurally anomalous: she negotiates Greenland's "
                "sovereignty posture with the United States while her husband is in a business "
                "partnership with the American who originated the acquisition idea and continues "
                "to advocate for it publicly. In January 2026 she conducted Greenland's first EU "
                "diplomatic visit to France, seeking to strengthen ties as a counterweight to "
                "U.S. pressure — a trip taken while her family's financial interests remained "
                "tied to the Lauder consortium. [Finding #6174]</p>"
            ),
        },
        {
            "id": "warsh-fed-nomination",
            "title": "Kevin Warsh: Federal Reserve Nomination and Family Connection",
            "viz": None,
            "finding_ids": [6121, 6162, 6330],
            "connection_ids": [3187],
            "body": (
                "<p>On March 4, 2026, Trump formally nominated Kevin Warsh to serve as the "
                "next Chair of the Federal Reserve, replacing Jerome Powell whose term expires "
                "in May 2026. Warsh is married to Jane Lauder, Ronald Lauder's granddaughter "
                "and an heir to the Estée Lauder fortune. [Finding #6162] [Finding #6330] "
                "Warsh previously served on the Federal Reserve Board of Governors from 2006 "
                "to 2011, resigning over disagreements about monetary expansion. His FEC record "
                "shows contributions to Dave McCormick for Senate via Vicarage LLC, Elise "
                "Stefanik, Mitt Romney, John Boehner, and the 55th Presidential Inaugural "
                "Committee. He serves on the boards of UPS (Form 4, CIK 1090727) and Coupang "
                "Inc. [Finding #6162]</p>"
                "<p>The family connection establishes a direct link between Lauder's active "
                "Greenland investment portfolio and the nominated head of U.S. monetary policy. "
                "The Federal Reserve's rate decisions affect the cost of capital for infrastructure "
                "investments of the type Greenland Investment Group is pursuing — including the "
                "proposed Lake Tasersiaq hydroelectric project. Lauder simultaneously holds "
                "equity in Greenland, advocates for U.S. Greenland policy, and is the "
                "grandfather-in-law of the man nominated to chair the institution that sets "
                "borrowing costs. As of March 2026, Warsh's Senate confirmation remains "
                "uncertain; Senator Thom Tillis has stated opposition pending resolution of "
                "a Powell investigation. [Finding #6121] [Connection #3187]</p>"
            ),
        },
        {
            "id": "offshore-structure-epstein-adjacency",
            "title": "Offshore Entities and Epstein-Adjacent Infrastructure",
            "viz": None,
            "finding_ids": [4898, 4911],
            "connection_ids": [1988],
            "body": (
                "<p>ICIJ Offshore Leaks records identify Ronald S. Lauder (node ID 80090658) as "
                "an officer of Tech Water, Ltd., a Bermuda-registered entity, alongside RSL "
                "Investments Corporation, Henry J. Charrabe, Jacob Z. Schuster, Nea "
                "Williams-Grant, and Rovonne Roberts. All parties are registered at 767 Fifth "
                "Avenue, Suite 4200, New York — Lauder's known office address in the GM "
                "Building. Tech Water is registered at two Bermuda addresses: Canon's Court, "
                "22 Victoria Street, Hamilton HM 12, and Argyle House, 41a Cedar Avenue, "
                "Hamilton HM 12. These are the same two Bermuda registered addresses used by "
                "Jeffrey Epstein's Liquid Funding, Ltd. Ronald's son Scott Lauder also appears "
                "in the ICIJ data. The shared addresses indicate use of a common corporate "
                "services provider — Appleby — but do not establish a direct relationship "
                "between Lauder and Epstein's offshore operations. [Finding #4898]</p>"
                "<p>A separate Epstein-network connection is documented through "
                '<a href="/dossiers/jacqui-safra">Jacqui Safra</a>. '
                "Epstein-corpus documents (EFTA01902608, EFTA02392189, EFTA02707165) show "
                "that Safra was in negotiations with Lauder to purchase The Sherover House, "
                "a Jerusalem property in the Talbieh neighborhood. That deal fell through; "
                "Safra subsequently offered the property to Epstein through John Brockman "
                "as intermediary. The failed negotiation establishes a direct commercial "
                "relationship between Lauder and a person who was deeply embedded in "
                "Epstein's social and financial network. [Connection #1988]</p>"
                "<p>UK Companies House records show Lauder holds two British directorships: "
                "CME Development Corp (FC018103), with an address at 71 East 71st Street "
                "New York 10021, and Educating for Impact (10924797), registered at Acre "
                "House, 11/15 William Road London NW1 3ER, from September 2017. [Finding #4911] "
                "Central European Media Enterprises (SEC CIK 0000925645), a regional TV "
                "broadcaster in which Lauder held a board seat from 2001 to 2012, provided "
                "his historical SEC filing identity. [Finding #6165]</p>"
            ),
        },
        {
            "id": "political-spending-profile",
            "title": "Political Spending Profile",
            "viz": None,
            "finding_ids": [6163, 6323],
            "connection_ids": [],
            "body": (
                "<p>Lauder's FEC donor record, filed under self-employed and Clinique "
                "Laboratories Chairman designations from New York City, documents a concentrated "
                "pattern of Republican political contributions. The largest single contribution "
                "is $5,000,000 to MAGA Inc (committee C00858373) on March 24, 2025. "
                "Additional 2024–2025 contributions include $1,000,000 to the Trump Vance "
                "Inaugural Committee (December 16, 2024); $250,000 to Security Is Strength "
                "PAC (committee C00075820, November 5, 2025, listed under Estée Lauder "
                "Companies employer); $150,000 each to Grow The Majority and One Team Senate "
                "Majority (December 22, 2025); $86,700 and $44,300 to NRCC; $17,000 each "
                "to Team Jordan and Graham Majority Fund; and $3,500 each to Mike Johnson "
                "for Louisiana and Team Graham. [Finding #6163] [Finding #6323]</p>"
                "<p>The 2025 MAGA Inc contribution of $5 million is timed approximately "
                "six weeks before Lauder's public defense of the Greenland acquisition "
                "concept appeared in the <em>New York Post</em> in February 2025. The "
                "contribution sequence — inaugural, then MAGA Inc, then Security Is "
                "Strength PAC, then Senate leadership PACs — follows the standard "
                "pattern of a major donor seeking broad access across the executive "
                "and legislative branches simultaneously.</p>"
            ),
        },
    ]

    open_questions = [
        (
            "No FARA registration or lobbying disclosure exists for Lauder, Sheeran, "
            "Greenland Development Partners LLC, or Greenland Investment Group, despite "
            "Lauder's stated multi-year relationship with Greenland government and "
            "business leaders and his direct advocacy for U.S. Greenland policy in a "
            "national publication. Does this pattern meet the threshold for FARA "
            "registration under 22 U.S.C. § 611, given that he was acting to influence "
            "U.S. government policy with respect to a foreign territory while holding "
            "financial interests contingent on that policy's outcome?"
        ),
        (
            "What is the precise ownership percentage and capital contribution that "
            "Lauder's consortium paid for stakes in Greenland Water Bank and Greenland "
            "Investment Group? The ArcticToday reporting establishes the transaction "
            "occurred but does not disclose valuation, dilution terms, or the timeline "
            "relative to Lauder's first contacts with the Trump administration about "
            "Greenland."
        ),
        (
            "Kevin Warsh's pending Federal Reserve confirmation raises the question "
            "of whether Senate disclosure requirements will surface the full scope "
            "of the Lauder family's Greenland holdings and whether any recusal "
            "obligations apply to a Fed Chair whose grandfather-in-law holds active "
            "infrastructure investment positions dependent on U.S. Arctic policy."
        ),
        (
            "The ICIJ Offshore Leaks connection — Lauder's Tech Water, Ltd. using "
            "the same two Bermuda registered addresses as Epstein's Liquid Funding, "
            "Ltd. — has not been explained. Did both entities use Appleby as their "
            "registered agent independently, or is there a documented operational "
            "relationship between the Lauder and Epstein Bermuda structures?"
        ),
        (
            "Josette Sheeran's Unification Church background and her Washington Times "
            "editorship (1982–late 1990s) have not been investigated for any ongoing "
            "organizational affiliations. The Church maintains commercial and media "
            "operations globally; her current role chairing a Delaware LLC with no "
            "public registry footprint invites scrutiny of whether any Church-aligned "
            "capital participates in the Lauder Greenland consortium."
        ),
        (
            "Svend Hardenberg simultaneously bridges the Lauder consortium and the "
            "GreenMet/Drew Horn network — two U.S.-backed Greenland investment clusters "
            "that present publicly as separate. Has Hardenberg disclosed his dual role "
            "to either principal, and does his position as General Manager of Energy "
            "Transition Minerals' Greenland arm create a further undisclosed overlap "
            "with REE extraction interests?"
        ),
    ]

    applicable_models = [
        "bridge-tax",
        "jurisdictional-arbitrage",
        "convergent-policy-channeling",
        "private-market-opacity-shield",
        "moral-proxying",
    ]

    return {
        "lead": lead,
        "system_role": system_role,
        "sections": sections,
        "open_questions": open_questions,
        "applicable_models": applicable_models,
    }


def main():
    with open(DOSSIER_PATH, "r", encoding="utf-8") as f:
        dossier = json.load(f)

    curation = dossier.get("curation", {})
    new_curation = build_curation()

    # Preserve existing structural keys, overwrite narrative keys
    for key in ("lead", "system_role", "sections", "open_questions", "applicable_models"):
        curation[key] = new_curation[key]

    curation["curated_at"] = datetime.now(timezone.utc).isoformat()
    dossier["curation"] = curation

    with open(DOSSIER_PATH, "w", encoding="utf-8") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  lead: {len(new_curation['lead'])} chars")
    print(f"  system_role: {len(new_curation['system_role'])} chars")
    print(f"  sections: {len(new_curation['sections'])}")
    print(f"  open_questions: {len(new_curation['open_questions'])}")
    print(f"  applicable_models: {new_curation['applicable_models']}")


if __name__ == "__main__":
    main()
