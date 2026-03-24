#!/usr/bin/env python3
"""
Curation script for Tony Sage dossier.
Writes the curation block with lead, system_role, sections, open_questions, applicable_models.
"""

import json
from datetime import datetime
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/tony-sage.json")


def build_curation() -> dict:
    lead = (
        "<p>Tony Sage (born c. 1958, Perth, Western Australia) is an Australian mining entrepreneur "
        "who built his career across West African iron ore, European lithium, and, most recently, "
        "Greenland rare earths. He is CEO and Executive Chairman of "
        "<a href='/dossiers/critical-metals-corp'>Critical Metals Corp</a> (Nasdaq: CRML), a "
        "British Virgin Islands-incorporated vehicle that holds an agreement to acquire up to "
        "92.5% of Tanbreez Mining Greenland A/S—a 4.7-billion-tonne rare earth deposit with a "
        "30-year exploitation license—and that in June 2025 received a $120 million Letter of "
        "Interest from the US Export-Import Bank under the Supply Chain Resiliency "
        "Initiative.<sup>[Finding #6260, #6246]</sup> Sage controls CRML through European "
        "Lithium Ltd (ASX: EUR), his Perth-based holding company, which owned 58.9% of CRML at "
        "the June 2025 reporting date and has subsequently reduced that stake to 37.3% via seven "
        "secondary sales to Alyeska Master Fund, extracting at minimum A$54.75 million in "
        "proceeds.<sup>[Finding #6263, #6273]</sup></p>"
        "<p>Sage's earlier vehicle, Cape Lambert Resources Ltd (ASX: CFE), was the subject of "
        "an Australian Taxation Office investigation from 2012 to 2014 that issued a $96 million "
        "assessment, ultimately settled for $2.4 million. The Australian Federal Police launched "
        "Operation Lemans in 2012, with untested court allegations including bribing a Sierra "
        "Leone official in connection with the Marampa iron ore project, paying secret "
        "commissions, insider trading, and disguising $19.8 million as loans through offshore "
        "entities. As of January 2023, no charges had been filed; Sage was simultaneously "
        "pursuing court access to the AFP's criminal investigation "
        "reports.<sup>[Finding #6381]</sup> A Panamanian entity named Cape Lambert Corporation "
        "appears in the Panama Papers (ICIJ node 10048336), incorporated February 2007 via "
        "Mossack Fonseca with Consulco International Ltd (Ras Al Khaimah Free Trade Zone, UAE) "
        "as intermediary; no officers or beneficial owners are named in the ICIJ database, and "
        "the connection to Sage's ASX-listed company is "
        "unverified.<sup>[Finding #6353]</sup></p>"
    )

    system_role = (
        "Sage functions as the controlling entrepreneur behind a multi-jurisdictional resource "
        "structure built on a single operating hub: 32 Harrogate Street, West Leederville, "
        "Western Australia, which serves as the registered business address for both CRML and "
        "European Lithium. He holds the CEO/Executive Chairman role at CRML while simultaneously "
        "acting as Executive Chairman of European Lithium—the entity that controls CRML's equity. "
        "This dual-role arrangement means Sage effectively sits on both sides of the parent-subsidiary "
        "relationship. European Lithium's systematic reduction of its CRML stake transfers "
        "capital out of the US-listed vehicle to the Australian parent while CRML remains "
        "pre-revenue and carries substantial going concern doubt. Sage provides the Australian "
        "mining-operator credential and the network connections to the Greenland project, while "
        "US-facing functions (defense board placement, EXIM engagement, SAM registration) are "
        "handled by Michael C. Ryan and Cornerstone Government Affairs lobbyists."
    )

    sections = [
        {
            "id": "career-and-cape-lambert",
            "title": "Career and Cape Lambert Resources",
            "viz": None,
            "content": (
                "<p>Sage co-founded International Goldfields (later renamed Hamill Resources), "
                "which merged with Cape Lambert Resources to create Cape Lambert Resources Ltd "
                "(ASX: CFE). He served as Executive Chairman of Cape Lambert from its formation "
                "through the company's most active deal period, which included the A$400 million "
                "sale of an iron ore asset to the Metallurgical Corporation of China—a transaction "
                "that subsequently produced litigation when Sage sued MCC for alleged breach. He "
                "also sued Timis Mining (Sierra Leone) for a $10 million loan plus royalties in "
                "connection with the Marampa iron ore project.<sup>[Finding #6253]</sup></p>"
                "<p>The Marampa project became the focal point of regulatory and law enforcement "
                "attention. The ATO issued a $96 million assessment to Cape Lambert Resources "
                "covering the 2012–2014 period on fraud and evasion grounds; the company settled "
                "for $2.4 million and Cape Lambert's share price fell 75% during the investigation. "
                "In January 2023, West Australian media reported that Sage was applying to court "
                "for access to the AFP's criminal investigation reports from Operation Lemans—a "
                "proceeding that confirms the existence of a criminal referral even though no "
                "charges were ultimately filed.<sup>[Finding #6381]</sup> The untested allegations "
                "include bribery of a Sierra Leone government official, insider trading, and "
                "the reclassification of $19.8 million as loans routed through offshore "
                "structures.<sup>[Finding #6381]</sup></p>"
                "<p>A separate Panamanian entity, Cape Lambert Corporation (ICIJ node 10048336), "
                "was incorporated on February 6, 2007 through Mossack Fonseca, using Consulco "
                "International Ltd (Ras Al Khaimah Free Trade Zone, UAE) as intermediary. The "
                "ICIJ database contains no officer or shareholder names for this entity. No public "
                "record confirms Sage as a beneficiary or officer of the Panamanian entity; the "
                "name correspondence with his ASX-listed company is documented but "
                "unverified.<sup>[Finding #6353]</sup></p>"
            ),
            "finding_ids": [6253, 6381, 6353],
            "connection_ids": [],
        },
        {
            "id": "critical-metals-corp-and-crml-structure",
            "title": "Critical Metals Corp and the CRML Structure",
            "viz": None,
            "content": (
                "<p><a href='/dossiers/critical-metals-corp'>Critical Metals Corp</a> (Nasdaq: CRML, "
                "CIK 0001951089) was incorporated in the British Virgin Islands in 2022 and listed "
                "on February 28, 2024, following a SPAC merger between Sizzle Acquisition Corp "
                "(underwritten by <a href='/dossiers/cantor-fitzgerald'>Cantor Fitzgerald</a>) and "
                "Sage's European Lithium Ltd. Cantor received 1,247,250 CRML shares as deferred "
                "underwriting compensation; "
                "<a href='/dossiers/howard-lutnick'>Howard Lutnick</a>, then Cantor CEO and now "
                "US Commerce Secretary, held indirect ownership of those shares until divesting "
                "to his sons' trusts in May 2025.<sup>[Finding #6251, #6247, #6249]</sup></p>"
                "<p>CRML's business address is Sage's own office at 32 Harrogate Street, West "
                "Leederville, Australia. The company files as a foreign private issuer on Form 20-F, "
                "eliminating most individual officer compensation disclosure requirements. In "
                "FY2025, CRML reported aggregate compensation to directors and officers of "
                "$26.9 million while disclosing zero direct beneficial ownership by any named "
                "director or officer—Sage's exposure is held entirely through European "
                "Lithium.<sup>[Finding #6270, #6276]</sup></p>"
                "<p>The company's financial position is precarious: losses of $51.9 million "
                "(FY2025) and $139.4 million (FY2024), working capital deficit of $15.6 million, "
                "and cash of $7.3 million as of June 30, 2025. CRML is pre-revenue and carries "
                "going concern doubt.<sup>[Finding #6262]</sup> European Lithium's systematic "
                "divestment of CRML shares to Alyeska Master Fund (9.9% holder, $70 million+ "
                "total invested) has extracted at minimum A$54.75 million from the US-listed vehicle "
                "while CRML continues to depend on external financing for "
                "Tanbreez development.<sup>[Finding #6273]</sup></p>"
                "<p>CRML registered on SAM.gov on October 13, 2025 (UEI XW4PVY32Q7K1, CAGE "
                "KD8P2), with Michael C. Ryan listed as government POC, primary NAICS 212290 "
                "(Other Metal Ore Mining), and registration purpose Z2 (federal contracts and "
                "grants)—six days after its lobbying firm, Cornerstone Government Affairs, "
                "filed a termination notice following nine months of advocacy that coincided "
                "with the EXIM LOI.<sup>[Finding #6245, #6248]</sup></p>"
            ),
            "finding_ids": [6260, 6263, 6273, 6262, 6245, 6248],
            "connection_ids": [],
        },
        {
            "id": "corporate-network",
            "title": "Corporate Network",
            "viz": None,
            "content": (
                "<p>Sage operates across at least six active corporate roles plus a set of private "
                "entities. The disclosed public-company positions are: CEO and Executive Chairman "
                "of Critical Metals Corp (NASDAQ: CRML, BVI); Executive Chairman of European "
                "Lithium Ltd (ASX: EUR, West Leederville—holds 37.3% of CRML as of February 2026); "
                "Executive Chairman of Cape Lambert Resources Ltd (ASX: CFE, Australia); Executive "
                "Chairman of CuFe Ltd (ASX: CUF, Australia); and Managing Director of Okewood Pty "
                "Ltd (Perth consulting entity, founded 1997).<sup>[Finding #6382]</sup> Non-executive "
                "directorships include Kupang Resources, Caeneus Minerals, and International "
                "Petroleum. Sage was a founding director of Cyclone Metals (ASX) for 24 years "
                "before being removed as chairman in October 2025 following a contested boardroom "
                "vote; his December 2025 application to the Australian Takeovers Panel alleging "
                "undisclosed associations among Cyclone shareholders was "
                "declined.<sup>[Finding #6383]</sup></p>"
                "<p>Private entities in the documented network include: Marampa Iron Ore Ltd, "
                "Metal Exploration Mauritius Ltd, Metals Exploration Pty Ltd, Millennium Minerals "
                "(Operations) Pty Ltd, Mineral Securities Investments Australia Pty Ltd, "
                "Mooloogool Pty Ltd, and Eastern Petroleum Australia "
                "Pty Ltd.<sup>[Finding #6382]</sup></p>"
                "<p>Sage's ownership of Perth Glory FC (A-League football club) ended when he "
                "stepped down as owner in 2023; the club subsequently entered receivership, "
                "partly attributed to the financial impact of COVID-era home game "
                "restrictions.<sup>[Finding #6383]</sup></p>"
            ),
            "finding_ids": [6382, 6383],
            "connection_ids": [],
        },
        {
            "id": "key-relationships",
            "title": "Key Relationships",
            "viz": "ego_network",
            "content": (
                "<p><strong>Greg Barnes</strong> is Sage's primary counterpart in the Tanbreez "
                "transaction. Barnes, a Perth-based geologist, founded Tanbreez in 2001 through "
                "Rimbal Pty Ltd (controlled via the Barnes Family Trust). Rimbal held 100% of "
                "Tanbreez Mining Greenland A/S prior to the CRML acquisition. Under the Heads "
                "of Agreement and the final deal structure, CRML acquires up to 92.5% of Tanbreez; "
                "Rimbal retains a minority stake and Barnes continues as principal geologist and "
                "director of Tanbreez. As of June 30, 2025, Rimbal held 11,728,174 CRML shares "
                "(11% of outstanding). Sage and Barnes co-signed the October 2025 PIPE agreement "
                "with Alyeska.<sup>[Connection #3208, Finding #6263, #6258]</sup></p>"
                "<p><strong>Michael C. Ryan</strong> was appointed to the CRML board under Sage's "
                "chairmanship in March 2025 (GlobeNewswire, February 26, 2025). Ryan is a former "
                "US Air Force Colonel and graduate of the French War College and National "
                "Intelligence University who served as Deputy Assistant Secretary of Defense for "
                "European and NATO Policy from October 2019 to October 2020. He is listed as "
                "government POC on CRML's SAM.gov registration and his former DASD-Europe title "
                "gives CRML's SAM registration a direct defense-policy "
                "credential.<sup>[Connection #3205, Finding #6277]</sup></p>"
                "<p><strong><a href='/dossiers/greenmet'>GreenMet</a></strong> "
                "(Greentech Minerals Holdings Inc.) brokered the Tanbreez partnership and "
                "facilitated the 10-year offtake agreement between CRML and Ucore Rare Metals "
                "for the DoD-funded Strategic Metals Complex in Louisiana. GreenMet CEO "
                "<a href='/dossiers/drew-horn'>Drew Horn</a> is a former Deputy Policy Director "
                "to Vice President Pence. GreenMet, Horn, and co-principals George Sorial and "
                "Keith Schiller do not appear in any of CRML's 167 publicly filed SEC documents; "
                "their compensation structure—if any—is held entirely in private "
                "agreements.<sup>[Finding #6271, #6282]</sup></p>"
                "<p><strong><a href='/dossiers/howard-lutnick'>Howard Lutnick</a></strong> "
                "held indirect CRML ownership through Cantor Fitzgerald's SPAC underwriting "
                "shares until divesting to his sons in May 2025, shortly before becoming "
                "US Commerce Secretary. Commerce oversees EXIM Bank and the critical minerals "
                "supply chain program through which CRML's $120 million LOI was issued. "
                "Senators Warren, Van Hollen, and Wyden raised the conflict of interest in "
                "February 2026 in connection with a separate Cantor transaction with USA Rare "
                "Earth.<sup>[Finding #6249]</sup></p>"
            ),
            "finding_ids": [6277, 6271, 6249, 6282],
            "connection_ids": [3205, 3208],
        },
    ]

    open_questions = [
        (
            "Cape Lambert Corporation (ICIJ node 10048336) was incorporated in Panama on February 6, "
            "2007 via Mossack Fonseca, using Consulco International (RAK FTZ, UAE) as intermediary—a "
            "timeline that coincides with Cape Lambert Resources' active deal period in Africa and "
            "Asia. The ICIJ database contains no named officers or beneficial owners. What is the "
            "beneficial ownership of this entity, and is there any public-record connection to "
            "Sage, Cape Lambert Resources, or the Marampa project?"
        ),
        (
            "Operation Lemans (AFP, launched 2012) produced untested allegations—bribery, insider "
            "trading, offshore loan reclassification—that remained unresolved as of January 2023 "
            "when Sage was still seeking court access to the AFP's criminal investigation reports. "
            "What is the current status of that proceeding and the AFP's referral to the Commonwealth "
            "Director of Public Prosecutions?"
        ),
        (
            "European Lithium has extracted at minimum A$54.75 million from CRML via secondary "
            "sales to Alyeska between October 2025 and February 2026, reducing its stake from 58.9% "
            "to 37.3%, while CRML operates with $7.3 million cash and substantial going concern "
            "doubt. What is Sage's personal economic benefit from European Lithium's CRML divestment, "
            "and does European Lithium disclose his individual equity position in its ASX filings?"
        ),
        (
            "GreenMet's role in brokering the Tanbreez transaction and EXIM LOI is entirely absent "
            "from CRML's 167 SEC filings. Did GreenMet receive equity compensation in CRML, European "
            "Lithium, or Tanbreez for introducing the parties, and does that compensation trigger any "
            "SEC related-party transaction disclosure obligation?"
        ),
        (
            "CRML registered in SAM.gov six days after its lobbying engagement with Cornerstone "
            "Government Affairs terminated. What federal contracts or grants has CRML pursued or "
            "received since SAM registration, and does the Z2 registration purpose (federal "
            "contracts/grants) reflect a planned direct procurement relationship with DoD, EXIM, "
            "or another agency?"
        ),
        (
            "The Cyclone Metals boardroom removal (October 2025) and subsequent Takeovers Panel "
            "application (declined, December 2025) coincided with Sage selling down his Cyclone "
            "shareholdings. What was the nature of the board dispute and who are the Cyclone "
            "shareholders alleged to have acted in undisclosed association?"
        ),
        (
            "Metal Exploration Mauritius Ltd and the Sierra Leone-adjacent private entities "
            "(Marampa Iron Ore Ltd, Metals Exploration Pty Ltd) remain undocumented in public "
            "registries. What is the current status of these entities, and do any remain active "
            "or hold residual assets from the Marampa transaction?"
        ),
    ]

    applicable_models = [
        "dual-role-principal-agent: Sage holds CEO/Chairman of both CRML (subsidiary) and European "
        "Lithium (controlling parent), placing him on both sides of every significant related-party "
        "transaction between the two entities.",
        "parent-divestment-while-subsidiary-distressed: European Lithium systematically extracts "
        "capital from the US-listed vehicle via secondary sales while CRML operates at a loss with "
        "going concern doubt—a pattern where the controlling shareholder monetizes before the "
        "underlying project generates revenue.",
        "foreign-private-issuer-opacity: CRML's FPI status under SEC rules eliminates individual "
        "officer compensation disclosure, proxy statement requirements, and Section 16 real-time "
        "reporting—structural choices that maximize permissible opacity for an entity seeking US "
        "government financing.",
        "government-credential-insertion: The appointment of Michael C. Ryan (former DASD-Europe, "
        "National Intelligence University) to the CRML board and as SAM.gov POC gives a BVI "
        "mining shell a defense-policy credential positioned to engage EXIM Bank and DoD.",
        "offshore-investigation-unresolved: The Cape Lambert/Operation Lemans cluster illustrates "
        "a pattern where law enforcement investigations (ATO $96M assessment, AFP criminal "
        "referral) are settled or remain open without prosecution while the principal continues "
        "to build new vehicles and access government financing programs.",
    ]

    return {
        "lead": lead,
        "system_role": system_role,
        "sections": sections,
        "open_questions": open_questions,
        "applicable_models": applicable_models,
    }


def main():
    with open(DOSSIER_PATH) as f:
        dossier = json.load(f)

    curation = dossier.get("curation", {})
    new_fields = build_curation()
    curation.update(new_fields)
    curation["curated_at"] = datetime.utcnow().isoformat()
    dossier["curation"] = curation

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Written: {DOSSIER_PATH}")
    print(f"Sections: {[s['id'] for s in new_fields['sections']]}")
    print(f"Open questions: {len(new_fields['open_questions'])}")
    print(f"Applicable models: {new_fields['applicable_models']}")


if __name__ == "__main__":
    main()
