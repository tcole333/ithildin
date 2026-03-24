#!/usr/bin/env python3
"""Write curation fields into content/dossiers/adnan-khashoggi.json"""

import json
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/adnan-khashoggi.json")

with open(DOSSIER_PATH) as f:
    dossier = json.load(f)

curation = dossier.setdefault("curation", {})

# ── system_role ──────────────────────────────────────────────────────────────
curation["system_role"] = (
    "Adnan Khashoggi was a Saudi arms broker whose career spanned five decades of "
    "covert weapons transactions and structured financial intermediation on behalf of "
    "Western governments and private arms networks. He is documented in Congressional "
    "investigation records as the primary bridge financier for the Iran arms sales at "
    "the core of the Iran-Contra affair — providing approximately USD 30 million in "
    "short-term credit routed through BCCI Monte Carlo to enable transactions that "
    "US officials could not directly fund. His FARA registration as a Saudi foreign "
    "principal, held through Hill & Knowlton from 1984 to December 1986, terminated "
    "precisely as the scandal broke publicly. He subsequently appeared in the same "
    "criminal indictment as Imelda Marcos in the SDNY but was acquitted. In the network "
    "graph of the Epstein investigation, Khashoggi occupies an 11th-place betweenness "
    "centrality position despite only eight documented connections — a structural signal "
    "that he serves as a historical bridge between Iran-Contra-era financial "
    "infrastructure and the banking networks later associated with Jeffrey Epstein."
)

# ── lead ─────────────────────────────────────────────────────────────────────
curation["lead"] = (
    "<p>Adnan Khashoggi (1935–2017) was a Saudi businessman who became the world's most "
    "prominent independent arms broker during the 1970s and 1980s, facilitating weapons "
    "procurement for Saudi Arabia, Iran, Egypt, Jordan, and others while building a "
    "personal fortune estimated at its peak near USD 4 billion. His significance in this "
    "investigation is not biographical but structural: he was the primary short-term "
    "credit provider for the US arms sales to Iran that formed the financial core of "
    "the Iran-Contra affair. The Senate's Kerry/Brown Report on BCCI (1992) documents "
    "him depositing USD 2.5 million on February 7, 1986, USD 2.5 million on February 10, "
    "two installments totaling USD 10 million on February 18, and USD 5 million on May 18 "
    "— all from BCCI Monte Carlo into Enterprise (the Oliver North covert funds) accounts "
    "held by Albert Hakim [Finding #3398, #3409].</p>"

    "<p>BCCI's role was not incidental. Khashoggi maintained two to three 'very active' "
    "deposit accounts at BCCI's Monte Carlo branch, keeping very large balances and paying "
    "his crew through the branch at USD 100,000–150,000 per month in traveler's checks. "
    "BCCI officer Manir Karim constructed the bridge-financing mechanism by exploiting "
    "BCCI's internal float: Khashoggi would present a check Thursday or Friday, receive "
    "immediate credit, direct arms delivery over the weekend, then repay via demand draft "
    "from Credit Suisse the following Tuesday or Wednesday. Five or more transactions "
    "totaling USD 8–10 million were processed before BCCI Paris manager Nazir Chinoy "
    "became aware of them. Karim received a USD 100,000 bribe deposited in a non-BCCI "
    "Swiss account [Finding #3409]. The FBI subsequently investigated the BCCI transactions; "
    "the bank agreed to provide records on the condition that the US government prevent "
    "public exposure of the arrangement [Finding #3409].</p>"

    "<p>His registered Washington presence during this period was formally structured. "
    "FARA registration #3301 shows Hill & Knowlton registered as Khashoggi's agent "
    "representing Saudi interests from May 4, 1984, terminating December 12, 1986 — "
    "weeks after Iran-Contra broke publicly on November 3, 1986, and three days after "
    "the November 26, 1986 delivery of USD 150,000 in cash from Republic National Bank "
    "officer <a href=\"/dossiers/nan-morabia\">Nan Morabia</a> to Khashoggi in New York, "
    "drawn from a Samir Trabigulsi account at the bank [Finding #3395, #3382; "
    "Connection #2009, #2016].</p>"

    "<p>In the network graph of the Epstein investigation, Khashoggi holds the 11th "
    "highest betweenness centrality score (0.039) despite only eight documented connections. "
    "His betweenness-to-degree ratio is among the highest in the graph, meaning each "
    "individual connection carries disproportionate structural weight. He bridges "
    "<a href=\"/dossiers/republic-national-bank-of-new-york\">Republic National Bank of "
    "New York</a>, BCCI, the Enterprise covert financial network, and — through "
    "LittleSis-documented client and collaborator relationships — "
    "<a href=\"/dossiers/jeffrey-epstein\">Jeffrey Epstein</a> and Douglas Leese "
    "[Finding #3469].</p>"
)

# ── sections ─────────────────────────────────────────────────────────────────
curation["sections"] = [
    {
        "id": "iran-contra-bridge-financing",
        "title": "Iran-Contra Bridge Financing",
        "content": (
            "<p>The Walsh Independent Counsel's Final Report (Volume I, pp. 194–196) "
            "establishes Khashoggi's financing role in granular transactional detail. "
            "The arms pipeline to Iran required a credit intermediary because the US "
            "government could not directly advance funds for weapons sales it was "
            "officially not authorizing. Khashoggi provided what the report terms "
            "'bridge financing': short-term loans to Iran arms middleman Manucher "
            "Ghorbanifar, who would use the funds to purchase weapons from Israeli "
            "government stocks, with the understanding that Iranian payments would "
            "repay the credit after delivery [Finding #3382].</p>"

            "<p>For the February 1986 transactions — covering the delivery of TOW "
            "missiles — Hakim's ledgers show four separate Khashoggi deposits into "
            "Enterprise accounts: USD 2.5 million (February 7), USD 2.5 million "
            "(February 10), and two payments totaling USD 10 million (February 18). "
            "For the May 1986 HAWK spare parts transaction, Khashoggi deposited "
            "USD 5 million on May 14–16. The May financing required Khashoggi to "
            "assemble funds from multiple sources: he approached Tiny Rowlands, who "
            "declined; he obtained USD 5 million from Oussama Lababidi via a vehicle "
            "called Kremdale Corp; and USD 5 million via Vertex International (Cayman "
            "Islands), backed by Ernie Walter Miller and Donald Fraser of Canada, "
            "channeled through Trivert International [Finding #3398].</p>"

            "<p>The repayment record was poor. Ghorbanifar ultimately repaid Khashoggi "
            "only USD 8.1 million of the USD 10 million owed from the February "
            "transactions, including Khashoggi's contracted 20 percent commission, "
            "leaving Khashoggi financially exposed for the remainder [Finding #3398]. "
            "This exposure did not lead to public legal action; Khashoggi was never "
            "questioned by the Walsh investigation about the November 1986 USD 150,000 "
            "cash delivery from the Trabigulsi account at Republic National Bank, despite "
            "the Walsh team identifying the transaction [Finding #3382, Connection #2041].</p>"
        ),
        "viz": None,
    },
    {
        "id": "bcci-and-the-float-mechanism",
        "title": "BCCI and the Float Mechanism",
        "content": (
            "<p>The Kerry/Brown Senate Report on BCCI (pp. 299–303) provides the most "
            "detailed account of the banking structure Khashoggi used. BCCI Monte Carlo "
            "was not simply a deposit institution for Khashoggi — it was the operational "
            "nerve center of his liquidity management. He maintained multiple 'very active' "
            "accounts with large standing balances, paid crew expenses through the branch "
            "at USD 100,000–150,000 monthly in traveler's checks, and used the branch's "
            "float capacity to execute transactions that Credit Suisse, which held the "
            "Enterprise accounts, would not have processed directly [Finding #3409].</p>"

            "<p>BCCI officer Manir Karim's float mechanism worked as follows: Khashoggi "
            "would deliver a personal check on a Thursday or Friday; BCCI credited his "
            "account immediately; the arms delivery occurred over the weekend; and "
            "Khashoggi would repay via Credit Suisse demand draft on Tuesday or Wednesday. "
            "Five or more iterations of this cycle, totaling USD 8–10 million in aggregate, "
            "proceeded before BCCI Paris manager Nazir Chinoy became aware of them. Chinoy "
            "testified to the Kerry Committee about the arrangement. Karim was separately "
            "paid USD 100,000 into a non-BCCI Swiss account for enabling the transactions "
            "[Finding #3409].</p>"

            "<p>The FBI's subsequent investigation resulted in BCCI agreeing to provide "
            "its records to US authorities on condition that the government would prevent "
            "public exposure of the bank's role in the arms transactions. This arrangement "
            "— the bank purchasing investigative protection through cooperation — "
            "contextualizes the broader pattern of BCCI's institutional survival strategy, "
            "which Kerry/Brown documented across multiple jurisdictions and transactions "
            "before the bank's 1991 collapse [Finding #3409].</p>"
        ),
        "viz": None,
    },
    {
        "id": "republic-national-bank-and-the-cash-delivery",
        "title": "Republic National Bank and the November 1986 Cash Delivery",
        "content": (
            "<p>On November 26, 1986 — twenty-three days after Iran-Contra broke publicly "
            "and fourteen days after the first Congressional hearings began — "
            "<a href=\"/dossiers/nan-morabia\">Nan Morabia</a>, an officer at "
            "<a href=\"/dossiers/republic-national-bank-of-new-york\">Republic National "
            "Bank of New York</a>, delivered USD 150,000 in cash to Khashoggi in New York. "
            "The funds were drawn from an account held by Samir Trabigulsi at RNB. "
            "Walsh investigators described the payment as an 'authorized payment,' but "
            "noted that Trabigulsi was 'not identified as an Iran-Contra figure.' Khashoggi "
            "was never questioned about it [Finding #3382, #3395; Connection #2041, #2016].</p>"

            "<p>Republic National Bank was at this time owned by Edmond Safra and served "
            "as one of the US domestic cash distribution nodes for Enterprise operations. "
            "Nan Morabia and her husband David Morabia conducted multiple cash drops for "
            "Enterprise on behalf of Willard Zucker, including a USD 7,000 delivery to "
            "Robert Owen in August 1985 and a USD 150,000 delivery to Secord intermediary "
            "William Haskell in November 1986. Both Nan and David Morabia received immunity "
            "from prosecution in exchange for their Walsh testimony; a third family member, "
            "Elliot Morabia, died in March 1987 before he could be questioned "
            "[<a href=\"/dossiers/nan-morabia\">Nan Morabia dossier</a>].</p>"

            "<p>The timing of the November 26 cash delivery — within the post-exposure "
            "window when participants in the operation were severing connections and "
            "terminating formal registrations — is consistent with a pattern of resolving "
            "outstanding financial obligations before the investigation tightened. The "
            "FARA termination for Hill & Knowlton's Khashoggi registration followed sixteen "
            "days later, on December 12, 1986 [Finding #3395, Connection #2028].</p>"
        ),
        "viz": "ego_network",
    },
    {
        "id": "fara-registration-and-us-political-presence",
        "title": "FARA Registration and US Political Presence",
        "content": (
            "<p>Khashoggi's formal US presence as a Saudi foreign principal is documented "
            "through FARA registration #3301. Hill & Knowlton Strategies LLC filed as his "
            "registered agent on May 4, 1984, covering his activities as a representative "
            "of Saudi interests, and terminated the registration on December 12, 1986 — "
            "the cleanup date that followed both Iran-Contra's exposure and the Trabigulsi "
            "cash delivery [Finding #3395].</p>"

            "<p>FEC records show a separate, more modest US political presence: five "
            "contributions to the Republican National Committee between 1990 and 1995, "
            "totaling USD 2,200, all from New York City. The employer listed on the FEC "
            "filings alternates between AKORP NV — his Netherlands Antilles holding "
            "company — and 'self-employed.' AKORP NV is the registered vehicle through "
            "which Khashoggi structured his international holding interests; its Netherlands "
            "Antilles incorporation provided the standard offshore opacity advantages "
            "of that jurisdiction during the period [Finding #3395].</p>"

            "<p>The RNC contributions are operationally minor but structurally notable: "
            "they document Khashoggi maintaining a US political donor presence four "
            "years after Iran-Contra through a post-scandal acquittal, sustaining "
            "his Washington relationships into the mid-1990s [Finding #3395].</p>"
        ),
        "viz": None,
    },
    {
        "id": "family-corporate-footprint",
        "title": "Family Corporate Footprint",
        "content": (
            "<p>SEC EDGAR and state registry records document an active corporate presence "
            "maintained by Khashoggi family members well after Adnan's peak period. Essam "
            "Khashoggi (CIK 0001107077) and Layla Khashoggi (CIK 0001252550) appear as "
            "material insiders at EarthShell Corp (CIK 0000911801), a packaging technology "
            "company; both filed Form 4s and SC 13Gs from 2001 through 2006. E. Khashoggi "
            "Industries LLC (CIK 0001308722) filed Form 4s for EarthShell during the same "
            "period, indicating that family financial interests were held through a named "
            "entity rather than direct personal positions [Finding #3397].</p>"

            "<p>Florida corporate registry records show Nabila Khashoggi as a director of "
            "In Motion Pictures Inc and Plum Pictures Inc, both Van Nuys, California "
            "entities. Husni Khashoggi appears as Vice Chairman and Director of Interchange "
            "Associates Inc, listed at two addresses: PO Box 13162, Jeddah, and c/o 725 "
            "Fifth Avenue, New York — Trump Tower. Mohamad Khashoggi appears as director "
            "of TMAN GLOBAL.COM INC at a Marbella address. NYC ACRIS records show Essam "
            "Khashoggi holding property in Santa Barbara; Soheir Khashoggi appears in NYC "
            "records care of Nabila in Hillsdale, New York [Finding #3397].</p>"

            "<p>The Trump Tower address for Husni Khashoggi's Interchange Associates is "
            "a factual registry entry. It does not establish a relationship with Trump "
            "or the Trump Organization; the building's prestige made it a common address "
            "of convenience for international businesspeople maintaining New York offices "
            "during the 1990s and 2000s. It is recorded here because of its literal "
            "presence in primary source materials and its potential relevance to other "
            "threads in this investigation [Finding #3397].</p>"
        ),
        "viz": None,
    },
    {
        "id": "network-position-and-epstein-connection",
        "title": "Network Position and Epstein Connection",
        "content": (
            "<p>Network analysis of the Epstein investigation graph assigns Khashoggi "
            "the 11th highest betweenness centrality score (0.039) across all nodes, "
            "despite having only eight documented connections. His betweenness-to-degree "
            "ratio — 0.039 divided by 8, yielding 0.0049 per connection — is among the "
            "highest in the graph, which means each individual tie he holds is "
            "disproportionately significant for connecting otherwise separate clusters "
            "[Finding #3469].</p>"

            "<p>The structural connections are: "
            "<a href=\"/dossiers/republic-national-bank-of-new-york\">Republic National "
            "Bank of New York</a> (the Trabigulsi/Morabia cash delivery channel); "
            "<a href=\"/dossiers/nan-morabia\">Nan Morabia</a> (the RNB officer who "
            "executed the delivery); BCCI (the arms-financing bank); Samir Trabigulsi "
            "(the RNB account holder from whose funds the delivery was drawn); Samir "
            "Traboulsi (his business partner from 1970 through the Iran-Contra period); "
            "Hill and Knowlton (his FARA-registered US representative); Douglas Leese "
            "(LittleSis documents a collaboration between them as arms dealers); and "
            "<a href=\"/dossiers/jeffrey-epstein\">Jeffrey Epstein</a> "
            "(LittleSis relationships #2037411 and #2016804 identify Khashoggi as an "
            "Epstein financial client, with Epstein described in that context as a "
            "financial fixer) [Connection #1200, #2055].</p>"

            "<p>The Leese connection is the second-degree pathway most worth noting. "
            "Douglas Leese is separately documented as Jeffrey Epstein's mentor from 1981, "
            "predating the Epstein-Khashoggi financial relationship. Leese collaborated "
            "with Khashoggi in arms dealing; Leese introduced Epstein to the financial "
            "networks that would define his subsequent career. The Khashoggi–Leese–Epstein "
            "chain places two of Epstein's key patron relationships — the Iranian arms "
            "financier and the British arms dealer — in a common professional context "
            "before Epstein had fully established himself as an independent operator "
            "[Finding #3469, Connection #1200].</p>"
        ),
        "viz": "ego_network",
    },
]

# ── open_questions ────────────────────────────────────────────────────────────
curation["open_questions"] = [
    (
        "Khashoggi was never questioned by the Walsh investigators about the November 26, "
        "1986 USD 150,000 cash delivery from the Trabigulsi account at Republic National "
        "Bank, despite Walsh identifying the transaction. What was the investigative "
        "rationale for not pursuing Khashoggi as a witness or subject, and are there "
        "classified supplements to Walsh's Final Report that address this gap?"
    ),
    (
        "AKORP NV, the Netherlands Antilles holding company Khashoggi used for US FEC "
        "contributions, was his primary international holding vehicle. What entities did "
        "AKORP NV control or hold interests in during the 1985–1995 period, and are there "
        "Dutch Antilles corporate registry records documenting its officers and beneficial "
        "ownership structure?"
    ),
    (
        "LittleSis relationships #2037411 and #2016804 identify Epstein as a 'financial "
        "fixer' for Khashoggi and Khashoggi as Epstein's financial client. What is the "
        "date range and specific nature of that advisory relationship — are there Epstein "
        "email records, Rolodex entries, or financial records that establish when and how "
        "Khashoggi became a client?"
    ),
    (
        "The FBI investigated BCCI's role in the Khashoggi arms transactions, and BCCI "
        "provided records on condition of non-disclosure. Were those records later "
        "incorporated into the Kerry/Brown Committee record, or do they remain in "
        "classified FBI and DOJ files? Has any FOIA request produced them?"
    ),
    (
        "Oussama Lababidi and his vehicle Kremdale Corp contributed USD 5 million to "
        "Khashoggi's May 1986 HAWK spare parts bridge financing. Who is Lababidi, what is "
        "the corporate history of Kremdale Corp, and what was his relationship to Khashoggi "
        "and to the Enterprise network?"
    ),
    (
        "Husni Khashoggi's Interchange Associates Inc listed Trump Tower (725 Fifth Avenue) "
        "as a New York address. What was Interchange Associates' business purpose and "
        "active period, and are there any documented interactions between Interchange "
        "Associates and Trump Organization entities sharing the building?"
    ),
    (
        "The Walsh Report documents that Ghorbanifar failed to fully repay Khashoggi "
        "from the February 1986 transactions. Did this non-repayment lead to any dispute "
        "resolution proceeding, arbitration, or subsequent financial settlement? "
        "The financial exposure from under-repayment is documented but its resolution "
        "is not in the available record."
    ),
]

# ── applicable_models ────────────────────────────────────────────────────────
curation["applicable_models"] = [
    {
        "name": "Covert Credit Intermediary",
        "description": (
            "Khashoggi's Iran-Contra function was not to traffic weapons but to provide "
            "the short-term credit that allowed officially deniable arms transactions to "
            "proceed. Governments that cannot directly fund covert arms sales require a "
            "private actor to absorb the float risk and hold counterparty exposure. "
            "Khashoggi fit that role structurally: wealthy enough to extend USD 30 million "
            "in unsecured credit, connected enough to both sellers and buyers to manage "
            "delivery logistics, and motivated enough by the 20 percent commission to "
            "accept the repayment risk. The model recurs wherever state actors need "
            "private financial cover for transactions they cannot formally authorize."
        ),
    },
    {
        "name": "Parallel-Financial-System",
        "description": (
            "BCCI Monte Carlo, Republic National Bank, Credit Suisse Enterprise accounts, "
            "and Netherlands Antilles holding companies formed an integrated private "
            "banking layer that processed transactions US domestic financial institutions "
            "could not have handled without triggering disclosure obligations. The float "
            "mechanism Karim built for Khashoggi at BCCI was not an anomaly — it was "
            "BCCI's standard product for customers whose transactions required weekend "
            "delivery windows and immediate credit without a paper trail. The network of "
            "offshore banks, Cayman entities, and Swiss demand drafts was the financial "
            "infrastructure of the covert state operating inside the public one."
        ),
    },
    {
        "name": "Jurisdictional-Arbitrage",
        "description": (
            "Khashoggi's corporate structure — AKORP NV in the Netherlands Antilles, "
            "BCCI accounts in Monaco, arms commissions routed through Swiss banks — "
            "used jurisdictional fragmentation to distribute legal exposure across "
            "multiple sovereigns, each of which had visibility into only one piece. "
            "The July 1990 acquittal on the Imelda Marcos SDNY charges demonstrated "
            "the practical limit of US prosecutorial reach when the underlying financial "
            "conduct was structured through offshore vehicles and foreign banking "
            "relationships."
        ),
    },
    {
        "name": "Network-Broker",
        "description": (
            "Khashoggi's high betweenness centrality relative to his low connection count "
            "is the quantitative signature of a structural broker: someone whose value "
            "derives not from the size of his immediate network but from the uniqueness "
            "of the clusters he bridges. He connected Saudi arms procurement to US covert "
            "operations, BCCI's offshore banking infrastructure to Enterprise's Hakim "
            "accounts, and — through Douglas Leese and his own direct client relationship "
            "— the Iran-Contra financial world to the Epstein-era private wealth network "
            "that succeeded it."
        ),
    },
]

dossier["curation"] = curation

with open(DOSSIER_PATH, "w") as f:
    json.dump(dossier, f, indent=2, ensure_ascii=False)

print("Curation written successfully.")
