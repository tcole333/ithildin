#!/usr/bin/env python3
"""
Curation script for content/dossiers/republic-national-bank.json
"""

import json
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/republic-national-bank.json")

CURATION = {
    "lead": (
        "<p>Republic National Bank of New York (RNB) was the American institutional "
        "anchor of the <a href=\"/dossiers/edmond-safra\">Edmond Safra</a> banking empire — "
        "founded by Safra in 1966 at 452 Fifth Avenue, Manhattan, and grown into one of the "
        "largest privately controlled banks in the United States with a parent holding company "
        "(Republic New York Corporation) that at peak held over $50 billion in assets. The bank "
        "operated in deliberate tandem with Safra's offshore architecture: "
        "<a href=\"/dossiers/trade-development-bank\">Trade Development Bank</a> in Geneva, "
        "Safra Republic Holdings in Luxembourg, and branches in Monaco, Guernsey, Singapore, "
        "and the Bahamas. RNB's FARA registration from 1975 to 1976 as agent for Trade "
        "Development Bank Overseas Inc. formally documented this institutional interdependence "
        "between the New York and Geneva operations.</p>"

        "<p>RNB sits at the convergence of multiple investigative threads documented by "
        "primary sources. The Walsh Independent Counsel's Iran-Contra Final Report placed "
        "both RNB and Trade Development Bank Geneva at the center of the Enterprise's "
        "financial infrastructure: RNB processed wire transfers through official channels "
        "while bank officer <a href=\"/dossiers/nan-morabia\">Nan Morabia</a> ran a parallel "
        "off-books cash operation, structured below the $10,000 Currency Transaction Report "
        "threshold, delivering funds to Enterprise operatives including "
        "<a href=\"/dossiers/adnan-khashoggi\">Adnan Khashoggi</a>. A decade later, RNB's "
        "compliance team became the institution that exposed the $10 billion Bank of New York "
        "/ Benex Russian money-laundering scandal — filing SARs with the FBI in August 1998 "
        "months before Safra's death in a Monaco arson fire in December 1999. The "
        "HSBC acquisition, completed at noon on December 31, 1999, just 28 days after "
        "Safra's death, transferred the entire Safra offshore private banking network "
        "to one of the world's largest financial institutions for $9.85 billion.</p>"

        "<p>The connection to the Epstein investigation is structural rather than direct. "
        "An exhaustive search across all local document corpora — the DOJ Vol. 11 corpus, "
        "Duggan, LMSBAND, Unified, and Epstein 20K datasets — found zero direct mentions "
        "of RNB in Epstein's banking records, wire transfers, or correspondence (Finding 3341). "
        "The link runs instead through the Safra family social network: Edmond Safra's nephew "
        "<a href=\"/dossiers/jacqui-safra\">Jacqui Safra</a> was a documented member of "
        "Epstein's social circle, appearing in at least 15 DOJ EFTA documents and confirmed "
        "on guest lists for Edge Foundation dinners alongside Jeff Bezos, Sergey Brin, and "
        "Bill Gates. <a href=\"/dossiers/ron-soffer\">Ron Soffer</a>, who worked in banking "
        "law at RNB from 1988 to 1991, later bridged the Safra world to the Epstein legal "
        "network. The bank's significance to this investigation lies in its historical role "
        "as covert financial infrastructure and in the family network that persisted long "
        "after the institution itself was absorbed by "
        "<a href=\"/dossiers/deutsche-bank\">HSBC</a>.</p>"
    ),

    "system_role": (
        "Republic National Bank illustrates how a single privately controlled institution "
        "can simultaneously serve as a lender of record for covert government operations, "
        "a compliance whistleblower against organized crime, an offshore shell intermediary, "
        "and eventually the prize asset in a multi-billion-dollar acquisition — each role "
        "enabled by the same underlying architecture of cross-jurisdictional opacity and "
        "discretionary client service."
    ),

    "sections": [
        {
            "id": "iran-contra-dual-channel",
            "title": "Iran-Contra: Institutional Wire Transfers and the Off-Books Cash Operation",
            "viz": None,
            "content": (
                "<p>The Walsh Independent Counsel's Iran-Contra Final Report (Vol. 1, "
                "p. 195 and p. 221, fn. 20) documented that Republic National Bank of "
                "New York served the Enterprise through two separate and structurally "
                "distinct channels. At the institutional level, RNB processed wire "
                "transfers for the Enterprise through normal banking channels. Running "
                "in parallel was a cash-delivery operation run by "
                "<a href=\"/dossiers/nan-morabia\">Nan Morabia</a>, an RNB officer who "
                "explicitly told the FBI in her November 16, 1987 interview that the "
                "operation \"was conducted by her outside bank channels\" (FBI 302, "
                "11/16/87, p. 4). Nan and her brother David Morabia were granted immunity "
                "from prosecution in exchange for their testimony; a third Morabia sibling, "
                "Elliot, died in March 1987 before investigators could interview him.</p>"

                "<p>The documented cash drops connected directly to the most prominent "
                "Iran-Contra figures. In August 1985, Nan Morabia delivered $7,000 to "
                "Robert W. Owen at RNB in New York. On November 26, 1986 — days after "
                "the scandal became public — she delivered $150,000 in cash to "
                "<a href=\"/dossiers/adnan-khashoggi\">Adnan Khashoggi</a>, the Saudi arms "
                "dealer who had provided approximately $30 million in bridge financing for "
                "US arms sales to Iran. Willard Zucker, who directed Morabia's domestic "
                "cash drops from the Swiss side, wired corresponding amounts into a "
                "\"Codelis\" account at Safra's <a href=\"/dossiers/trade-development-bank\">"
                "Trade Development Bank</a> in Geneva, controlled by the Mizrahi brothers. "
                "Walsh identified at least 21 cash transactions totaling approximately "
                "$91,000 involving Oliver North alone, all structured below the $10,000 "
                "Currency Transaction Report threshold.</p>"

                "<p>The structural implication is that both ends of the Enterprise's "
                "US-Swiss cash pipeline ran through institutions owned by the same person: "
                "RNB in New York and TDB Geneva in Switzerland, both controlled by "
                "<a href=\"/dossiers/edmond-safra\">Edmond Safra</a>. Whether Safra had "
                "personal knowledge of the Enterprise's use of his institutions is "
                "unestablished by the Walsh record. The American Express smear campaign "
                "of 1986 to 1989 — which planted stories falsely linking Safra to "
                "Iran-Contra money laundering and was later settled for $8 million with "
                "a public apology from AmEx Chairman James D. Robinson III — is notable "
                "in this context: AmEx targeted the Iran-Contra angle specifically, "
                "suggesting that the bank's entanglement with the Enterprise was known "
                "to competitors even before the Walsh investigation formally documented it "
                "(Finding 3343).</p>"
            ),
        },
        {
            "id": "russian-organized-crime",
            "title": "Russian Organized Crime Exposure and the Safra Death Timeline",
            "viz": None,
            "content": (
                "<p>In August 1998, RNB's compliance team closed a suspicious account "
                "belonging to Benex Worldwide and filed Suspicious Activity Reports with "
                "the FBI identifying massive Russian money flows through Bank of New York. "
                "Benex was linked to Semion Mogilevich, alleged head of a Russian organized "
                "crime network. RNB alerted both the FBI and Swiss authorities about possible "
                "laundering of IMF funds involving officials at the Russian Ministry of "
                "Finance and the Russian Central Bank. Through 18 Benex accounts at Bank of "
                "New York, approximately $10 billion was laundered within two years "
                "(Finding 3339). This act of institutional whistleblowing against a "
                "competitor bank was the most consequential compliance action in RNB's "
                "documented history.</p>"

                "<p>The timeline that follows this disclosure is a matter of public record. "
                "Safra also provided $25 million in seed capital to Bill Browder's Hermitage "
                "Capital Management in 1996 for Russian investments — giving Safra direct "
                "financial exposure to the same Russian financial ecosystem his bank was "
                "reporting to the FBI. Edmond Safra died in a fire at his Monaco penthouse "
                "on December 3, 1999, approximately 16 months after the Benex SARs were "
                "filed. The fire was set by Ted Maher, a nurse and former US Army Green "
                "Beret in Safra's employ, who was convicted of arson and manslaughter. "
                "Maher claimed he intended to set a small fire to position himself as a "
                "hero, but recanted and reconvened multiple accounts. The HSBC acquisition "
                "closed 28 days later (Finding 3370).</p>"

                "<p>The Russian intelligence service's documented practice of targeting "
                "bankers who exposed Mogilevich-linked operations is established by "
                "multiple independent investigations. Whether that pattern applies to the "
                "Safra case is not established by primary sources in this investigation. "
                "What the primary record confirms is the sequence: RNB exposes a "
                "$10 billion Mogilevich-linked operation in August 1998; Safra dies in "
                "a fire in December 1999; HSBC acquires the entire Safra banking network "
                "28 days later, transferring 70 offshore entities and six jurisdictions "
                "of client relationships to one of the world's largest financial "
                "institutions (Finding 3370).</p>"
            ),
        },
        {
            "id": "offshore-architecture",
            "title": "Offshore Architecture and Compliance Paradox",
            "viz": None,
            "content": (
                "<p>The ICIJ Panama Papers and Offshore Leaks databases reveal five "
                "distinct RNB entities operating in the offshore financial system: RNB's "
                "Swiss subsidiary (Republic National Bank of New York (Suisse) S.A.) as "
                "an intermediary in the Panama Papers (ICIJ node 11008265); RNB's Guernsey "
                "subsidiary as trustee of the Munbank Trust in the Panama Papers (node "
                "12200780); Republic National Bank as an intermediary in Singapore "
                "(Offshore Leaks, node 295164); a fourth RNB entity in an undetermined "
                "jurisdiction (node 186385); and Republic National Leasing &amp; Investment "
                "Limited in the Bahamas (Bahamas Leaks, node 20012725). These entries "
                "document RNB's subsidiaries serving as conduits and trustees for shell "
                "company structures across at least four offshore jurisdictions (Finding 3346).</p>"

                "<p>Against this offshore footprint, the Senate Permanent Subcommittee on "
                "Investigations' 2001 Correspondent Banking report singled out RNB — by "
                "then operating as HSBC USA — as a \"notable exception\" among US banks for "
                "having adopted a written Know Your Customer Policy Statement for its "
                "International Banking Group, effective December 31, 1998, requiring "
                "mandatory written due-diligence analysis of every bank applying for a "
                "correspondent relationship. Anne Vitale, former Managing Director and "
                "Deputy General Counsel of RNB, testified before the committee. The Levin "
                "PSI report cited this policy as a model (Finding 3359). That the KYC "
                "policy took effect on the same date as the HSBC acquisition closed — "
                "December 31, 1999 per GLEIF records for the Uruguay subsidiary — suggests "
                "the policy was either part of HSBC's pre-acquisition compliance overhaul "
                "or adopted by RNB immediately prior to the transition.</p>"

                "<p>The compliance posture was not merely performative. In late 1999, RNB "
                "joined <a href=\"/dossiers/deutsche-bank\">Deutsche Bank</a> and Bank of "
                "New York in blocking correspondent wire transfers to South Pacific island "
                "nations — Nauru, Palau, Niue, and Vanuatu — over laundering concerns "
                "with Nauru-licensed banks (Finding 3360). This coordinated action by three "
                "major banks demonstrated genuine operational enforcement of correspondent "
                "banking restrictions. The juxtaposition — a bank with active offshore "
                "shell intermediary activity simultaneously leading industry compliance "
                "initiatives — is a documented feature of the financial architecture "
                "of the period, not an anomaly confined to Safra's institutions.</p>"
            ),
        },
        {
            "id": "key-relationships",
            "title": "Key Relationships",
            "viz": "ego_network",
            "content": (
                "<p><a href=\"/dossiers/nan-morabia\">Nan Morabia</a> was an RNB officer "
                "whose documented role in the Iran-Contra cash operation is the bank's most "
                "direct connection to covert intelligence activity. Her cash drops — "
                "coordinated by Willard Zucker, who managed the Enterprise's Swiss accounts "
                "for Albert Hakim — were conducted outside official bank channels, giving "
                "RNB institutional deniability while using an officer's position and "
                "professional credibility to facilitate deliveries to Khashoggi, Owen, and "
                "Haskell. Zucker's relationship with RNB extended beyond the Morabia "
                "operation: Enterprise wire transfers were routed through RNB with Zucker "
                "managing the Swiss side via CSF Geneva (Connection 2024).</p>"

                "<p><a href=\"/dossiers/trade-development-bank\">Trade Development Bank</a> "
                "(TDB) in Geneva was the institutional sibling to RNB — both owned by "
                "<a href=\"/dossiers/edmond-safra\">Edmond Safra</a>, both documented as "
                "Enterprise fund conduits, and both absorbed into HSBC through the 1999 "
                "acquisition. RNB's FARA registration as agent for Trade Development Bank "
                "Overseas Inc. from September 1975 to June 1976 formalizes the institutional "
                "relationship at the primary-source level. The Iran-Contra use of TDB's "
                "Codelis account as the Swiss counterpart to RNB's domestic wire processing "
                "made the two banks a single operational unit for Enterprise fund flows "
                "(Connection 2008).</p>"

                "<p><a href=\"/dossiers/adnan-khashoggi\">Adnan Khashoggi</a> was the "
                "most prominent recipient of RNB-connected cash flows, receiving $150,000 "
                "from Nan Morabia on November 26, 1986 — a delivery that placed an RNB "
                "officer in direct physical contact with the primary financier of the "
                "Iran arms sales at the moment the scandal was becoming public. Khashoggi "
                "had provided approximately $30 million in bridge financing for the arms "
                "sales through BCCI, and the Morabia delivery represents the RNB "
                "network's most direct documented intersection with the Enterprise's "
                "principal private financier (Connection 2009).</p>"

                "<p>The Epstein network connection flows through "
                "<a href=\"/dossiers/jacqui-safra\">Jacqui Safra</a>, Edmond's nephew, "
                "who was a documented presence at Edge Foundation dinners alongside "
                "<a href=\"/dossiers/jeffrey-epstein\">Jeffrey Epstein</a>, Jeff Bezos, "
                "Sergey Brin, and Bill Gates from 2012 to 2014. John Brockman's June 2010 "
                "email to Epstein — reporting Jacqui's banking difficulties and asking "
                "\"Something for you??\" — established Epstein as a potential creditor to "
                "Safra family members while Jacqui simultaneously attempted to sell "
                "Epstein his Jerusalem property, which had previously been in negotiations "
                "with Ronald Lauder. <a href=\"/dossiers/ron-soffer\">Ron Soffer</a>, "
                "who worked in banking law at RNB from 1988 to 1991, later became a "
                "key figure in the Epstein legal network, bridging the Safra professional "
                "world to the Epstein orbit through legal rather than banking channels "
                "(Finding 3370).</p>"
            ),
        },
        {
            "id": "legal-proceedings",
            "title": "Legal and Regulatory Proceedings",
            "viz": None,
            "content": (
                "<p>A federal forfeiture case, <em>United States v. Republic National Bank</em> "
                "(1:90-cv-00613, EDNY), was filed February 21, 1990, and terminated April 30, "
                "1993. The case fell under nature-of-suit code 690 (Other forfeiture and "
                "penalty suits) and was assigned to Judge Raymond Joseph Dearie, with "
                "Magistrate Allyne R. Ross. A three-year contested proceeding implies RNB "
                "disputed a government asset seizure connected to alleged illegal activity. "
                "The case was filed approximately three years after the Iran-Contra cash "
                "drops and the Walsh investigation's commencement, though the formal "
                "connection between this forfeiture action and the Enterprise's use of "
                "RNB has not been established by publicly available docket materials "
                "(Finding 3362).</p>"

                "<p>The criminal conviction that reduced the HSBC acquisition price from "
                "$10.3 billion to $9.85 billion was separate: RNB was convicted in a "
                "scheme to defraud Japanese investors, with fines exceeding $600 million. "
                "This conviction occurred during the pendency of the HSBC acquisition, "
                "announced in May 1999. RNB's FARA registration (Registration #2604, "
                "452 Fifth Avenue, New York) from September 4, 1975, to June 10, 1976, "
                "on behalf of Trade Development Bank (Overseas) Inc. in the Philippines "
                "provides primary-source confirmation of the institutional relationship "
                "between RNB and TDB Geneva, and documents the bank's formal role as "
                "a registered agent for Safra's offshore banking interests within the "
                "US regulatory framework (Finding 3361).</p>"
            ),
        },
    ],

    "open_questions": [
        (
            "What was the substance of the 1990 federal forfeiture case "
            "(US v. Republic National Bank, 1:90-cv-00613 EDNY)? What assets were "
            "seized and what underlying criminal activity did the government allege, "
            "and does the three-year timeline connect to the Walsh Iran-Contra "
            "investigation's parallel proceedings?"
        ),
        (
            "Did Edmond Safra have personal knowledge of the Enterprise's use of both "
            "RNB (New York) and TDB (Geneva) for covert fund flows, or were the Morabia "
            "cash operations and the Codelis account exploitations of access by "
            "intelligence-adjacent operatives working through an officer of the bank?"
        ),
        (
            "What was the relationship, if any, between RNB's August 1998 whistleblowing "
            "on Bank of New York / Benex / Mogilevich and Safra's death in December 1999? "
            "Were there documented threats, surveillance operations, or retaliation "
            "linked to the exposure of the $10 billion laundering scheme?"
        ),
        (
            "Who were the Munbank Trust beneficiaries behind the RNB Guernsey trustee "
            "structure identified in the Panama Papers (ICIJ node 12200780), and what "
            "is the provenance of the assets held in that structure?"
        ),
        (
            "How much of HSBC's subsequent AML failures — culminating in the 2012 "
            "$1.9 billion settlement for anti-money-laundering control failures — "
            "traces to infrastructure, client relationships, or compliance gaps "
            "inherited from the Safra network acquired in December 1999?"
        ),
        (
            "What was the nature of Ron Soffer's work at RNB from 1988 to 1991, "
            "and did it overlap with the period of the federal forfeiture case or "
            "the AmEx smear campaign? What specific clients or matters did Soffer "
            "handle during his time at the bank?"
        ),
        (
            "The ACRIS database returns 100+ NYC property records for Republic National "
            "Bank. Do any of these transactions connect to properties associated with "
            "Epstein-linked entities, Safra family holdings, or Iran-Contra "
            "network figures?"
        ),
    ],

    "applicable_models": [
        "parallel-financial-system",
        "jurisdictional-arbitrage",
        "enabler-gradient",
        "complexity-as-credential",
        "narrative-shield",
    ],
}


def main():
    with open(DOSSIER_PATH) as f:
        dossier = json.load(f)

    existing = dossier.get("curation", {})
    existing.update(CURATION)

    # Preserve curated_at if already set
    from datetime import datetime, timezone
    if "curated_at" not in existing or existing.get("curated_at") == "2026-03-11T23:00:53.954460":
        existing["curated_at"] = datetime.now(timezone.utc).isoformat()

    dossier["curation"] = existing

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)

    print(f"Curation written to {DOSSIER_PATH}")
    print(f"  lead: {len(CURATION['lead'])} chars")
    print(f"  system_role: {len(CURATION['system_role'])} chars")
    print(f"  sections: {len(CURATION['sections'])}")
    print(f"  open_questions: {len(CURATION['open_questions'])}")
    print(f"  applicable_models: {CURATION['applicable_models']}")


if __name__ == "__main__":
    main()
