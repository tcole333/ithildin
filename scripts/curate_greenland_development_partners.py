#!/usr/bin/env python3
"""Curation script for Greenland Development Partners LLC dossier."""

import json
import sys
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/greenland-development-partners-llc.json")


def build_curation() -> dict:
    return {
        "lead": (
            "<p>Greenland Development Partners LLC (GDP LLC) is a Delaware-registered investor consortium "
            "that functions as the US-side vehicle for <a href='/dossiers/ronald-lauder'>Ronald Lauder</a>'s "
            "commercial interests in Greenland. GDP LLC holds a confirmed 25–33.32% stake in Greenland Water Bank "
            "ApS (Danish CVR 12941218) and a controlling stake in Greenland Investment Group ApS (GIG), the "
            "Greenland-based operating entity bidding for the Tasersiaq hydropower concession — a 680 MW to "
            "2,250 MW project that would power an aluminium smelter.<sup>[ArcticToday, bisbase:DK1670228]</sup> "
            "The LLC is managed by <a href='/dossiers/josette-sheeran'>Josette Sheeran</a>, former US Deputy "
            "Secretary of State, as Portfolio Lead and Chair of both operating subsidiaries. Delaware law requires "
            "no public disclosure of LLC members or formation dates; no registered-agent record or EDGAR filing "
            "exists for GDP LLC.<sup>[registry-search, ArcticToday/Irish Times]</sup></p>"
        ),

        "system_role": (
            "US-registered holding vehicle for Greenland resource-sector investments; functions as the "
            "legal and financial wrapper separating Ronald Lauder's personal involvement from the "
            "Greenland-registered operating entities (GIG and Greenland Water Bank)."
        ),

        "sections": [
            {
                "id": "corporate-structure",
                "title": "Corporate Structure",
                "body": (
                    "<p>GDP LLC sits at the top of a three-tier structure. The LLC (Delaware entity #766) "
                    "holds a controlling stake in Greenland Investment Group ApS (#782), a Greenland/Denmark "
                    "private limited company co-founded by Jørgen Wæver Johansen, and a 25–33.32% minority "
                    "stake in Greenland Water Bank ApS (#790, CVR 12941218).<sup>[bisbase:DK1670228, "
                    "ArcticToday/Politiken]</sup> The majority position in Greenland Water Bank "
                    "(66.67–89.99%) is held by Greenland Invest ApS, the Danish holding company in which "
                    "<a href='/dossiers/svend-hardenberg'>Svend Hardenberg</a> holds a 50–66.65% direct "
                    "stake and chairs since 2015.<sup>[ownr.dk, bisbase]</sup></p>"
                    "<p>A LittleSis entry records the ownership direction as GIG owning GDP LLC rather than "
                    "the reverse — this conflicts with bisbase data showing GDP LLC as the direct owner of "
                    "Greenland Water Bank. The more likely explanation is a data-entry error in LittleSis "
                    "rather than a genuinely circular structure, but the precise ownership percentages "
                    "between GDP LLC and GIG are not publicly confirmed.<sup>[LittleSis rel 2043488, "
                    "bisbase:DK1670228]</sup></p>"
                    "<p>Delaware was chosen deliberately. LLC formation documents are not ingested by the "
                    "unified corporate registry tool; members are not required to be publicly disclosed "
                    "under Delaware LLC law. The ArcticToday and Irish Times investigations confirmed "
                    "the investments were not publicly disclosed through any accessible registry at the "
                    "time of reporting.<sup>[registry-search, ArcticToday/Irish Times 2025]</sup></p>"
                ),
                "finding_ids": [6171, 6283, 6293, 6317, 6291],
                "connection_ids": [3190, 3191],
            },
            {
                "id": "key-people",
                "title": "Key People",
                "body": (
                    "<p><strong><a href='/dossiers/ronald-lauder'>Ronald Lauder</a></strong> is the "
                    "confirmed investor behind GDP LLC (LittleSis ID 5617, SEC CIK 0000942617). He "
                    "published a February 2025 New York Post op-ed defending the Trump Greenland "
                    "acquisition concept and stated he had worked closely with Greenland business and "
                    "government leaders for years. John Bolton's memoir records Lauder as the person who "
                    "originated the Greenland purchase idea with Trump. On the political-donation side, "
                    "Lauder contributed $5 million to MAGA Inc. in March 2025, $1 million to the Trump "
                    "Inaugural in December 2024, and additional sums to Security Is Strength PAC, Grow "
                    "The Majority, and One Team Senate Majority.<sup>[LittleSis 5617, FEC, Bolton memoir, "
                    "NYPost Feb 2025]</sup> His son-in-law Kevin Warsh — married to Lauder's daughter "
                    "Jane — was nominated by Trump as Federal Reserve Chair in March 2026.<sup>[FEC, "
                    "LittleSis, reporting]</sup> No FARA registrations or LDA lobbying filings exist "
                    "for Lauder in connection with Greenland.<sup>[LittleSis 5617]</sup></p>"

                    "<p><strong>Josette Sheeran</strong> leads the portfolio as Chair of both GIG "
                    "(from 2025-10-16) and Greenland Water Bank ApS (from 2025-07-31).<sup>[bisbase "
                    "GWB registry, bisbase GIG registry]</sup> Her concurrent roles include "
                    "founder/CEO of Firefly Global Group (geopolitical consulting), board member of "
                    "Capital Group (which manages over $2.5 trillion), board member of Mars "
                    "Incorporated, and trustee of the McCain Institute. She previously served as "
                    "Executive Director of the World Food Programme, Vice Chair of the World Economic "
                    "Forum, and US Deputy Secretary of State under the Bush administration. LittleSis "
                    "lists her as a Clinton Global Initiative member. She also consented to be named "
                    "director of Trailblazer Holdings Inc./Cyabra Strategy Ltd. in an EDGAR S-4/A "
                    "filing dated 2025-01-30, and previously served on the board of Canoo Inc. (GOEV)."
                    "<sup>[bisbase, LittleSis 82179, EDGAR S-4/A 2025-01-30, LinkedIn]</sup> Earlier "
                    "in her career she was a member of the Unification Church and worked as an editor "
                    "at the Washington Times before her diplomatic career.<sup>[ArcticToday/Politiken]"
                    "</sup></p>"

                    "<p><strong>Jørgen Wæver Johansen</strong> is CEO/Director of Greenland Water Bank "
                    "ApS and co-founder of Greenland Investment Group. He is the chairman of the "
                    "governing Siumut party and a former Greenlandic MP (1999–2008), four-term cabinet "
                    "minister, and Mayor of South Greenland. He and <a href='/dossiers/svend-hardenberg'>"
                    "Svend Hardenberg</a> sold partial stakes in Greenland Water Bank to the Lauder "
                    "consortium. His wife is Vivian Motzfeldt, Greenland's Foreign Minister since 2022, "
                    "who previously served on the Greenland Water Bank board until 2018 — before the "
                    "Lauder consortium's entry — and who now negotiates Greenland's relationship with "
                    "the United States while her husband is CEO of a company the Lauder group partially "
                    "owns. Greenlandic media outlet Sermitsiaq documented the conflict of interest."
                    "<sup>[bisbase GWB, LittleSis rel 2043488, Sermitsiaq]</sup></p>"

                    "<p><strong><a href='/dossiers/svend-hardenberg'>Svend Hardenberg</a></strong> "
                    "is co-owner of Greenland Water Bank ApS (board member from July 2025) and holds "
                    "a 50–66.65% stake in Greenland Invest ApS, the majority owner of GWB. He is "
                    "simultaneously General Manager Greenland for Energy Transition Minerals (ASX:ETM, "
                    "appointed May 2025) — which controls the Kvanefjeld REE/uranium deposit — and a "
                    "business partner of <a href='/dossiers/drew-horn'>Drew Horn</a> (GreenMet CEO, "
                    "former Pence policy director) on an AI data center in Kangerlussuaq and a seaweed "
                    "treatment project. Hardenberg holds 21 documented Danish business roles and is the "
                    "primary Greenlandic intermediary connecting the Lauder consortium to the GreenMet "
                    "network, which presents publicly as a separate operation.<sup>[ownr.dk, LittleSis, "
                    "bisbase, ArcticToday, synthesis #6352]</sup></p>"
                ),
                "finding_ids": [6119, 6123, 6163, 6165, 6287, 6294, 6317, 6324, 6333, 6335],
                "connection_ids": [],
            },
            {
                "id": "operating-assets",
                "title": "Operating Assets",
                "body": (
                    "<p><strong>Greenland Water Bank ApS</strong> (CVR 12941218) was incorporated on "
                    "2016-12-09 and is registered at Inspektørbakken 35, st., Postboks 836, 3900 Nuuk. "
                    "It bottles Lyngmark Spring water from Qeqertarsuaq, Disko Island, under the brand "
                    "Imivik on a 20-year license. The company's registered address is a former school "
                    "building in Nuuk with new security cameras installed. Financial performance has "
                    "been consistently negative: the 2024 annual result was a loss of 20,014 DKK, with "
                    "total assets of 699,000 DKK. The original founders, Svend Hardenberg and Jørgen "
                    "Wæver Johansen, sold partial stakes to the Lauder consortium; GDP LLC now holds "
                    "25–33.32% with the majority remaining under Greenland Invest ApS.<sup>[bisbase "
                    "CVR 12941218, ArcticToday, Fortune, CNBC]</sup></p>"

                    "<p><strong>Greenland Investment Group ApS</strong> (#782) is the primary operating "
                    "entity for the consortium's energy ambitions. GIG is bidding for the Tasersiaq "
                    "hydropower concession at Greenland's largest lake (65 km long, southwest Greenland), "
                    "announced by Greenland Minister Kalistat Lund. The projected output ranges from "
                    "680 MW to 2,250 MW; the project is conceived as the power source for an aluminium "
                    "smelter. The license tender round is expected in the second half of 2026. No LDA "
                    "lobbying filings, EDGAR filings, or SAM/USASpending records have been found for "
                    "GIG.<sup>[bisbase GIG, ArcticToday, Fortune, Irish Times]</sup></p>"
                ),
                "finding_ids": [6171, 6283, 6284, 6318, 6329],
                "connection_ids": [3190, 3191],
            },
            {
                "id": "network-position",
                "title": "Network Position",
                "body": (
                    "<p>GDP LLC is one of at least three distinct Trump-allied networks operating "
                    "simultaneously in Greenland's resource sector. The Lauder consortium "
                    "(GDP LLC → GIG → Greenland Water Bank) focuses on water and hydropower; the "
                    "<a href='/dossiers/drew-horn'>GreenMet network</a> (Horn / Sorial / Schiller → "
                    "Tanbreez → Critical Metals Corp) focuses on rare earths; and Erik Prince has "
                    "publicly advocated Greenland acquisition without having registered entities. "
                    "<a href='/dossiers/svend-hardenberg'>Svend Hardenberg</a> bridges all three: "
                    "he is simultaneously a co-owner of Greenland Water Bank in the Lauder consortium, "
                    "a business partner of Drew Horn on unrelated Greenland ventures, and General "
                    "Manager of ETM's Greenland arm (a third rare-earth deposit, Kvanefjeld). "
                    "Horn's 2-hop network graph places Lauder two hops away via Hardenberg, making "
                    "Hardenberg the structural link between operations that present publicly as "
                    "separate.<sup>[synthesis #6352, #6376, LittleSis, ownr.dk, graph analysis #6204]"
                    "</sup></p>"
                    "<p>Ronald Lauder has no FARA registrations and no LDA lobbying filings connected "
                    "to Greenland. GIG has no lobbying, EDGAR, or SAM records. The consortium's "
                    "policy-influencing capacity therefore runs through personal access rather than "
                    "registered lobbying channels.<sup>[LittleSis 5617, LDA search, SAM search]</sup>"
                    "</p>"
                ),
                "finding_ids": [6352, 6376, 6290, 6204, 6294],
                "connection_ids": [3163],
            },
        ],

        "open_questions": [
            "What is GDP LLC's exact ownership percentage in Greenland Investment Group ApS? The "
            "bisbase data quantifies GWB at 25–33.32% but no equivalent figure is confirmed for GIG.",
            "Who are the other members of GDP LLC beyond Lauder and Sheeran? Delaware law permits "
            "full non-disclosure; investigative reporting has not named additional members.",
            "When was GDP LLC formed? No formation date, registered agent, or operating agreement "
            "has surfaced in any accessible registry or filing.",
            "Has GDP LLC or any affiliated entity submitted a FARA registration for activities "
            "that could constitute representation of a foreign political party (Siumut) or "
            "Greenland governmental interest, given the Johansen/Motzfeldt relationship?",
            "What is the valuation basis for GDP LLC's GWB stake given the company has operated "
            "at a loss for nearly a decade with total assets of 699,000 DKK?",
            "Did Greenland Foreign Minister Vivian Motzfeldt recuse from any US-Greenland "
            "sovereignty or trade discussions that intersected with the Lauder consortium's "
            "commercial interests, and has the Greenlandic government made any formal "
            "conflict-of-interest determination?",
            "What is the timeline for the Tasersiaq hydropower license tender (expected 2H 2026) "
            "and what competing bidders have registered interest?",
            "Is the LittleSis ownership inversion (GIG as owner of GDP LLC) a data error or "
            "does it reflect a layered structure not visible in public registries?",
        ],

        "applicable_models": [
            "Conflict-of-interest capture: A foreign minister (Motzfeldt) negotiating her "
            "country's status with the United States while her husband is CEO of a company "
            "partially owned by a major US GOP donor — this is a textbook principal-agent "
            "conflict at the governmental level.",
            "Jurisdictional opacity: Deliberate use of Delaware LLC structure to avoid member "
            "disclosure requirements that would apply under Danish/Greenlandic law to the "
            "operating entities. The investor identity is visible only because journalists "
            "reported it, not because any registry required disclosure.",
            "Policy-investment entanglement: The sequence — Lauder plants the Greenland "
            "purchase idea with Trump → Trump administration pursues Greenland acquisition "
            "as policy → Lauder invests commercially in Greenland assets — raises a causal "
            "ambiguity that cannot be resolved from public records alone.",
            "Supernode intermediary: Svend Hardenberg functions as a structural bridge "
            "between the Lauder consortium and the GreenMet network, creating a hidden "
            "connectivity between operations that present as independent competitors for "
            "Greenland resources.",
        ],
    }


def main():
    dossier_path = Path("content/dossiers/greenland-development-partners-llc.json")
    if not dossier_path.exists():
        print(f"ERROR: {dossier_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(dossier_path) as f:
        dossier = json.load(f)

    curation = build_curation()

    # Preserve existing curation fields that we are not replacing
    existing = dossier.get("curation", {})
    existing.update(curation)
    dossier["curation"] = existing

    with open(dossier_path, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote curation to {dossier_path}")
    print(f"  lead: {len(curation['lead'])} chars")
    print(f"  sections: {len(curation['sections'])}")
    print(f"  open_questions: {len(curation['open_questions'])}")
    print(f"  applicable_models: {len(curation['applicable_models'])}")


if __name__ == "__main__":
    main()
