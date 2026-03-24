#!/usr/bin/env python3
"""Curate the Karyna Shuliak dossier."""

import json
from datetime import datetime, timezone
from pathlib import Path

DOSSIER_PATH = Path("/Users/travcole/projects/osint-research/content/dossiers/karyna-shuliak.json")

CURATION = {
    "lead": (
        "<p>Karyna Shuliak (also spelled Shulyak, Shulak; email: karynashuliak@icloud.com, kari.shulia@gmail.com) "
        "is a Ukrainian-born physician who held a doctoral credential and pursued U.S. Virgin Islands professional "
        "licensing beginning in August 2015. She was <a href=\"/dossiers/jeffrey-epstein\">Jeffrey Epstein</a>'s "
        "last long-term partner, documented across at least 13,731 hits in the DOJ Vol. 11 email corpus spanning "
        "roughly 2011 to Epstein's death in August 2019. The documentary record does not frame her as a peripheral "
        "figure: she held an American Express Centurion card on Epstein's account, shared a joint Deutsche Bank "
        "account (routing 021001033, DEUTSCHE BANK TRUST CO AMERICAS) with him, directed property renovation and "
        "logistics on Little St. James island, and received the final external phone call Epstein placed from "
        "Metropolitan Correctional Center before his death.</p>"
        "\n\n"
        "<p>Two days before his death, on August 8, 2019, Epstein signed the instrument that renamed his estate "
        "vehicle The 1953 Trust — the year of his birth — and designated Shuliak as the primary beneficiary. "
        "The bequest ran to approximately $100 million in cash and financial assets, a 32.73-carat diamond ring "
        "described as given \"in contemplation of marriage,\" and the full Epstein property portfolio: "
        "Little St. James and Great St. James islands in the U.S. Virgin Islands, Zorro Ranch in New Mexico, "
        "the Paris apartment near the Arc de Triomphe, the Palm Beach property, and 9 East 71st Street in "
        "Manhattan. Epstein's estate was valued at approximately $450 million at death; after legal fees, taxes, "
        "and a $121 million victim compensation fund, the residual available to Shuliak was substantially lower. "
        "The 1953 Trust had previously been documented under different names, with its architecture evolving in "
        "2017 (Dubin, <a href=\"/dossiers/darren-indyke\">Indyke</a>, <a href=\"/dossiers/richard-kahn\">Kahn</a>) "
        "and 2018 (Ruemmler, Indyke, Kahn) before the final August 2019 renaming.</p>"
        "\n\n"
        "<p>Deutsche Bank's Private Wealth Management unit performed KYC and due diligence on Shuliak (documented "
        "in LMSBAND as PWM BIS-RESEARCH). She also appears in Deutsche Bank AML records under the variant "
        "spellings SHULYAK / SHULIAK / SHULAK, alongside a person associate listed as DZIANIS SHULIAK (age 39), "
        "recorded as a person associate of EPSTEIN JEFFREY E at 9 East 71st Street. DZIANIS SHULIAK carries "
        "alias notations SHULYAK DENNIS and SHULAK DZIANIS, whose relationship to Karyna has not been "
        "established from available records.</p>"
    ),

    "system_role": (
        "Shuliak occupied a role that had no formal title but combined the functions of a principal's personal "
        "representative, property operations director, and designated estate beneficiary. Her position is "
        "significant to the investigation primarily for three reasons. First, the 1953 Trust designation makes "
        "her the intended recipient of Epstein's accumulated wealth, placing her at the center of any post-death "
        "asset-tracing effort. Second, her USVI property management role gives her direct operational knowledge "
        "of the island facilities, their renovation history, and the contractors and staff who worked there. "
        "Third, the Maxim Churkin contact on June 25, 2019 — two weeks before Epstein's arrest — involving a "
        "Switzerland intermediary discussion, raises a question about pre-arrest asset-movement awareness that "
        "remains unresolved. With 13,731 DOJ corpus hits, she is among the most documentable figures in the "
        "network, yet almost no investigative reporting has focused on her specifically."
    ),

    "sections": [
        {
            "id": "recruitment-and-entry-into-the-network",
            "title": "Recruitment and Entry into the Network",
            "content": (
                "<p>The connection record attributes Shuliak's introduction to Epstein to "
                "<a href=\"/dossiers/marcel-kellerhals\">Marcel Kellerhals</a> — whose family's Swiss law firm, "
                "Kellerhals Carrard Geneva, managed multiple Epstein-linked entities including "
                "\"NEW APO MIAMI 2 OWNER LLC\" and \"NEW APO NYC 3 OWNER LLC,\" creating a single family "
                "that operated simultaneously as Epstein's USVI registered agent (through the Ferguson "
                "Kroblin branch) and as his Swiss entity administrator. The USVI branch of the firm, "
                "<a href=\"/dossiers/erika-kellerhals\">Erika Kellerhals</a>' Kellerhals Ferguson Kroblin PLLC "
                "at 9053 Estate Thomas Suite 101, registered and maintained at least 28 Epstein USVI "
                "corporate entities and served as registered agent for Southern Trust Company. Marcel "
                "Kellerhals' recruitment of Shuliak therefore connects her origin point directly to the "
                "family's institutional infrastructure rather than to any casual social introduction.</p>"
                "\n\n"
                "<p>By September 2014, Shuliak was already operating in a coordinated capacity: she emailed "
                "Epstein a floor plan for a dedicated apartment (EFTA02713028), with attachments referencing "
                "Artefacto, a Brazilian luxury furniture supplier, covering rugs and lamps. This apartment, "
                "furnished at Epstein's direction, established a material residential dependency prior to her "
                "USVI licensing application. The relationship was described in the USVI context by internal "
                "correspondence referring to \"Bossman and Karyna\" as a joint decision-making unit on "
                "island furnishings — a shopping list prepared by property coordinator Ann Rodriguez in "
                "November 2017 (EFTA02568255) itemized purchases across at least four cabanas and pool areas, "
                "addressed to both of them together.</p>"
            ),
        },
        {
            "id": "usvi-licensing-and-political-intermediation",
            "title": "USVI Licensing and Political Intermediation",
            "content": (
                "<p>In August 2015, Shuliak submitted her birth certificate to the USVI Department of Health's "
                "Division of Professional Licensure and Health Planning, initiating a formal application for a "
                "USVI medical license (EFTA02302738). Official DOH correspondence addressed her as \"Dr. Shuliak\" "
                "and \"Dr. Karyna Shuliak,\" confirming the professional credential was in active use. What "
                "distinguishes this licensing process from a routine application is the identity of who "
                "monitored it.</p>"
                "\n\n"
                "<p><a href=\"/dossiers/cecile-de-jongh\">Cecile de Jongh</a> — wife of sitting USVI Governor "
                "John de Jongh — emailed Deborah Richardson-Peter, Director of Professional Licensure and "
                "Health Planning at the USVI Department of Health, in November 2015 to inquire about the "
                "status of Dr. Shuliak's application (EFTA02481598). Richardson-Peter confirmed she had spoken "
                "to Dr. Shuliak directly and that Shuliak was aware of her application status. De Jongh then "
                "forwarded this update to Epstein. Cecile de Jongh was herself a documented Epstein network "
                "facilitator: separate records show her intermediating Enhanced Education charitable donations "
                "in the USVI, including Humane Society contributions and coordination with the USVI Department "
                "of Education, and coordinating a February 2019 meeting between Epstein and USVI officials "
                "through Erika Kellerhals' office. The de Jongh relationship was treated as politically "
                "sensitive — Kellerhals explicitly warned Epstein in September 2015 not to mention Cecile "
                "and John to Governor Mapp, indicating the prior administration's ties were a liability with "
                "the new one.</p>"
                "\n\n"
                "<p>The use of the sitting governor's wife as a licensing intermediary for a romantic partner's "
                "professional application, with the status update forwarded to the subject's benefactor, "
                "illustrates the operational scope of Epstein's USVI political relationships. It also establishes "
                "that Shuliak's professional establishment in the USVI was actively facilitated at the "
                "gubernatorial household level.</p>"
            ),
        },
        {
            "id": "financial-structure-and-household-integration",
            "title": "Financial Structure and Household Integration",
            "content": (
                "<p>Shuliak's financial integration into the Epstein household operated through multiple "
                "channels managed by <a href=\"/dossiers/richard-kahn\">Richard Kahn</a> at HBRK Associates "
                "and bookkeeper Bella Klein, both of whom also managed Epstein's broader entity finances. "
                "In January 2013, Kahn processed a wire of $10,000 to Shuliak's mother at Epstein's instruction "
                "(EFTA02299598: \"pleae wire 15k dollars, to karyna mother\"). By October 2013, Klein was "
                "emailing Epstein directly to ask: \"Please advise if I should reimburse 20k to Karyna\" "
                "(EFTA02678226) — framing Shuliak as a reimbursement recipient through the same administrative "
                "channel that handled Epstein's corporate accounts.</p>"
                "\n\n"
                "<p>Shuliak held a joint Deutsche Bank account with Epstein (routing 021001033, DEUTSCHE BANK "
                "TRUST CO AMERICAS), with Klein serving as the account manager on the Epstein side. In June "
                "2017, Shuliak wired $16,000 from her Chase account to the Deutsche Bank account, covering "
                "approximately eight months of rent and telephone charges (EFTA02296565). This transaction "
                "flow — Shuliak contributing toward the DB account while simultaneously receiving "
                "discretionary wires from Epstein's HBRK-managed accounts — reflects an integrated household "
                "finance structure rather than a simple employer-employee or patron-dependent dynamic.</p>"
                "\n\n"
                "<p>Furniture and renovation purchases for USVI property were processed through LSJE LLC and "
                "the Haze Trust, with Klein coordinating wire transfers. An April 2018 transaction of $15,300 "
                "to Heshan Ruihui Furniture (EFTA02306604), copied to Daphne Wallace and Richard Kahn, shows "
                "Shuliak directing purchases that were paid through the LSJE LLC / Haze Trust accounts — the "
                "same trust structure that held approximately $40.58 million under Deutsche Bank relationship "
                "manager 82289 Stewart Oldfield, per the DB Daily Deposit Report (EFTA01383203). A June 2018 "
                "Bali furniture shipment (Benedictus supplier) followed the same Klein-coordinated wire "
                "pattern (EFTA02307778). <a href=\"/dossiers/the-2017-caterpillar-trust\">The 2017 Caterpillar "
                "Trust</a>, held $13.53 million under the same DB relationship manager, situating the "
                "Shuliak-directed renovation spending within Epstein's broader Deutsche Bank trust portfolio.</p>"
                "\n\n"
                "<p><a href=\"/dossiers/eva-dubin\">Eva Andersson-Dubin</a> provided medical advice for "
                "Shuliak's mother's surgery — coordination documented in EFTA02489456 — through the same "
                "personal-physician role she played for Epstein himself, with medical referrals routed through "
                "Sonia Jones' contacts. This places the Shuliak family's medical needs within the network's "
                "informal benefit-provisioning infrastructure.</p>"
            ),
        },
        {
            "id": "property-operations-and-operational-authority",
            "title": "Property Operations and Operational Authority",
            "content": (
                "<p>From at least November 2017 through May 2019, Shuliak exercised operational authority over "
                "Little St. James property logistics. The November 2017 \"Bossman &amp; Karyna Shopping list\" "
                "(EFTA02568255) placed her as co-principal for decisions on cabana furnishings across multiple "
                "units. By mid-2018 she was directing contractors: June 2018 correspondence documents her "
                "coordinating tile work, floor repairs in a specific building unit (\"Floor in 3M\"), and "
                "furniture orders from Bali suppliers. She directed property manager Leo and contractor "
                "Anthony Barrett on maintenance and renovation schedules.</p>"
                "\n\n"
                "<p>In May 2019 — two months before Epstein's arrest — Shuliak was directing Merwin Dela Cruz "
                "to ship defibrillators to the island and tracking shipping confirmations (EFTA02315929). "
                "The defibrillator procurement is notable only in temporal context: equipment maintenance "
                "activity continued on the island less than three months before the July 6, 2019 arrest. "
                "This operational continuity through the pre-arrest period establishes that Shuliak held "
                "active management responsibility over USVI facilities until at least the spring of 2019.</p>"
                "\n\n"
                "<p>The April 2019 U.S. passport photo exchange — Shuliak emailing passport photos to "
                "\"Jeffrey and Yulia\" (EFTA02314208) — is the last dated personal document in the available "
                "record before Epstein's arrest. The identity of Yulia in this context is not established "
                "from the available evidence.</p>"
            ),
        },
        {
            "id": "the-1953-trust-and-estate-position",
            "title": "The 1953 Trust and Estate Position",
            "content": (
                "<p>The trust instrument signed August 8, 2019 — two days before Epstein's death — designated "
                "Shuliak as primary beneficiary of the vehicle renamed The 1953 Trust. The bequest included "
                "approximately $100 million in financial assets, a 32.73-carat diamond ring described "
                "explicitly as given \"in contemplation of marriage,\" and the full Epstein property portfolio. "
                "The trust's architecture had evolved through at least three iterations: a 2017 version with "
                "Glenn Dubin, <a href=\"/dossiers/darren-indyke\">Darren Indyke</a>, and "
                "<a href=\"/dossiers/richard-kahn\">Richard Kahn</a> as trustees; a 2018 version substituting "
                "Kathryn Ruemmler for Dubin; and the August 8 final form naming Shuliak as beneficiary. "
                "<a href=\"/dossiers/eva-dubin\">Eva Andersson-Dubin</a> was listed as seventh alternate "
                "successor trustee in the same instrument.</p>"
                "\n\n"
                "<p>At the time of Epstein's death, the estate was valued at approximately $450 million. "
                "After court-supervised fees, estate taxes, and a $121 million victim compensation fund, "
                "the residual available to Shuliak as primary beneficiary was substantially reduced — "
                "estimates place the net estate at approximately $120 million, with ongoing litigation from "
                "victims' civil suits creating further uncertainty. Shuliak received the last external "
                "telephone call Epstein placed from Metropolitan Correctional Center before his death "
                "on August 10, 2019.</p>"
                "\n\n"
                "<p>The Maxim Churkin contact on June 25, 2019 — documented in the connection record — "
                "involved Churkin reaching Shuliak regarding a Switzerland intermediary, approximately "
                "two weeks before Epstein's arrest on July 6. Churkin was separately identified in the "
                "investigation as someone Epstein attempted to place at Glenn Dubin's firm, introducing "
                "him as the \"son of the Russian amb.\" The substance and outcome of the Switzerland "
                "intermediary discussion is not established from available records.</p>"
            ),
        },
    ],

    "open_questions": [
        (
            "What is the current legal status of the 1953 Trust bequest to Shuliak? "
            "Victims' civil suits, estate administration proceedings, and the USVI government's "
            "$105 million settlement with the estate all affect the residual available to the primary "
            "beneficiary. No public record has been located confirming whether Shuliak received any "
            "portion of the estate or whether the bequest is subject to ongoing litigation."
        ),
        (
            "Who is DZIANIS SHULIAK (aliases: SHULYAK DENNIS, SHULAK DZIANIS, age 39), recorded in "
            "Deutsche Bank AML records as a person associate of EPSTEIN JEFFREY E at 9 East 71st Street? "
            "The DB AML records link this individual to Karyna's own KYC file under the same variant "
            "spellings. The relationship — whether familial, professional, or coincidental — has not "
            "been established."
        ),
        (
            "What is the full substance of the June 25, 2019 Maxim Churkin contact regarding a "
            "Switzerland intermediary? Churkin contacted Shuliak approximately two weeks before Epstein's "
            "arrest. Whether this communication concerned asset movement, legal strategy, travel "
            "arrangements, or an unrelated matter is not determinable from the available record."
        ),
        (
            "What credential does Shuliak's doctoral designation refer to, and was her USVI medical "
            "license ultimately granted? The correspondence from August 2015 and November 2015 "
            "documents an active application and a status update, but no record confirming licensure "
            "or denial has been located. The \"columbiadental1@yahoo.com\" address flagged in the lead "
            "record has not been verified as connected to Shuliak's dental or medical training."
        ),
        (
            "Who is Yulia — the person to whom the April 2019 passport photo was forwarded alongside "
            "Epstein? The document (EFTA02314208) shows Shuliak sending passport photos to both "
            "Jeffrey and Yulia, but no person named Yulia appears in the available connection records. "
            "Given the April 2019 date — three months before arrest — the identity of this co-recipient "
            "is potentially significant for understanding pre-arrest travel coordination."
        ),
        (
            "What happened to the LSJE LLC and Haze Trust assets after Epstein's death? These were "
            "the entities through which Shuliak-directed furniture purchases were routed, and the Haze "
            "Trust held approximately $40.58 million under Deutsche Bank RM 82289 as of the last "
            "available balance record. The disposition of these trust assets — and whether they were "
            "included in or separate from the 1953 Trust bequest — has not been traced."
        ),
    ],

    "applicable_models": [
        "household-integration",
        "enabler-gradient",
        "jurisdictional-arbitrage",
        "manufactured-dependency",
        "principal-representative",
    ],

    "curated_at": datetime.now(timezone.utc).isoformat(),
}


def main() -> None:
    with open(DOSSIER_PATH) as f:
        dossier = json.load(f)

    # Preserve existing curation fields not overwritten
    existing = dossier.get("curation", {})
    existing.update(CURATION)
    dossier["curation"] = existing

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  lead: {len(CURATION['lead'])} chars")
    print(f"  system_role: {len(CURATION['system_role'])} chars")
    print(f"  sections: {len(CURATION['sections'])}")
    print(f"  open_questions: {len(CURATION['open_questions'])}")
    print(f"  applicable_models: {CURATION['applicable_models']}")


if __name__ == "__main__":
    main()
