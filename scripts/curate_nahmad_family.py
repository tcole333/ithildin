#!/usr/bin/env python3
"""Curate the Nahmad Family dossier."""

import json
from pathlib import Path
from datetime import datetime, timezone

DOSSIER_PATH = Path("/Users/travcole/projects/osint-research/content/dossiers/nahmad-family.json")


def build_curation():
    lead = (
        '<p>The Nahmad family is a multigenerational Lebanese-Jewish art dealing dynasty whose '
        'members occupy positions across the Geneva freeport system, the Monaco private wealth '
        'circuit, and New York residential real estate. The three principal brothers — David, Ezra, '
        'and Giuseppe Nahmad — built a collection estimated at $3.5–7 billion containing more than '
        '4,500 works, including approximately 300 Picassos, stored in a 15,000 sq ft facility at the '
        'Geneva Freeport. [Finding #4080] The commercial vehicle for that collection, '
        'International Art Center (IAC) S.A., was registered as a Panamanian shell company in 1995 '
        'through the Geneva office of Mossack Fonseca, initially held via bearer shares. '
        '[Finding #4152] Hillel ("Helly") Nahmad, son of David and third-generation heir to the '
        'operation, was convicted in November 2013 of leading a high-stakes illegal gambling '
        'organization that operated from the entire 51st floor of Trump Tower, laundering more than '
        '$100 million through Cyprus shell companies under the protection of a figure assessed by '
        'the FBI as a <em>vor v zakone</em> connected to the Solntsevskaya and Izmailovskaya crime '
        'groups. [Finding #4153] Donald Trump granted Helly Nahmad a full pardon on January 20, '
        '2021, the final day of his first term. [Finding #4075] Jeffrey Epstein\'s email corpus '
        'documents direct social contact with Helly and Joseph Nahmad, and a separate email '
        'chain from July 2016 records an Epstein associate meeting Joseph Nahmad at a '
        'Monte Carlo nightclub and boarding his vessel. [Finding #4086]</p>'
    )

    system_role = (
        "The Nahmad family illustrates how an opaque art market with no beneficial-ownership "
        "disclosure requirements can function in parallel with conventional banking. IAC S.A., "
        "the Panama shell company registered through Mossack Fonseca, held a $3.5–7 billion "
        "collection whose ultimate owner could only be established after the Panama Papers leak. "
        "That opacity served at least two documented purposes: concealment of a judicially "
        "confirmed stolen painting, and—on the criminal record—use of painting sales as wire "
        "transfer cover. The Geneva Freeport arrangement allows works to be bought and sold "
        "inside a duty-free customs zone without triggering any fiscal-authority notification, "
        "a mechanism the family used for decades. Simultaneously, the Nahmad-Trincher gambling "
        "conviction created a direct evidenced link between the gallery business, Russian "
        "organized crime infrastructure, and the Trump Tower building itself. The Trump pardon "
        "of Helly Nahmad—issued on the last day of the first term, alongside 142 other pardons—"
        "terminated that criminal exposure without further judicial scrutiny."
    )

    sections = [
        {
            "id": "family-structure-and-geography",
            "title": "Family Structure and Geographic Footprint",
            "content": (
                "<p>The Nahmad family traces its art dealing business to Edmond Nahmad, who "
                "established the family's presence in the European art market from Milan in the "
                "mid-20th century. The principal generation active in documented records comprises "
                "three brothers: David, Ezra, and Giuseppe Nahmad. David is identified in "
                "Panama Papers corporate records as the sole owner of International Art Center "
                "(IAC) S.A. since January 2014. Ezra and Giuseppe Nahmad held signing authority "
                "on IAC's UBS and Citibank bank accounts. [Finding #4152]</p>"
                "<p>NYC ACRIS property records document a family real estate footprint across "
                "30 instruments. Hillel Nahmad appears in multiple deed and mortgage documents "
                "at 721 Fifth Avenue (Trump Tower), Unit 51-J, dated 2010–2012 — the same "
                "building floor from which he operated the gambling organization. David Nahmad "
                "and Colette Nahmad appear in a 2022 transaction via MBJ Law PLLC at 290 "
                "Ackertown Road, Chestnut Ridge, NY 10952. Eveline Nahmad Matalon — listed at "
                "Via Vittore Pisani 2, Milan (2024) and Grand Place A-Apt.8, Crans sur Sierre, "
                "Switzerland — appears in the most recent ACRIS activity. Ezra Nahmad and Marie "
                "Nahmad are present in older instruments. An entity named NAHMAD FORTUNE appears "
                "in Brooklyn records. [Finding #4155]</p>"
                "<p>The family's geographic center of gravity for financial operations is Monaco: "
                "DHN Ltd., a BVI-registered entity (LEI: 5493002RWQNJJJJ42268, registration "
                "number 1785034), lists its headquarters as c/o Davide Nahmad, Roccabella "
                "Building, 24 Princess Grace Avenue, Monte Carlo MC 98000. DHN Ltd. was created "
                "on July 30, 2013, registered through PFD Corporate Services (BVI) Limited, "
                "Tropic Isle Building, Tortola. GLEIF shows its LEI as lapsed as of December "
                "2025. [Finding #4154]</p>"
            ),
        },
        {
            "id": "art-collection-and-freeport-infrastructure",
            "title": "Art Collection and Geneva Freeport Infrastructure",
            "content": (
                "<p>The Nahmad collection — estimated at $3.5–7 billion and comprising more "
                "than 4,500 works including approximately 300 Picassos — is stored primarily "
                "in a 15,000 sq ft facility within the Geneva Freeport, a customs-controlled "
                "duty-free zone where artworks can be bought and sold without notifying fiscal "
                "authorities. The family has been publicly criticized for holding approximately "
                "90% of its collection in freeport storage rather than making works available "
                "for exhibition. [Finding #4156]</p>"
                "<p>International Art Center S.A. (IAC) was the corporate vehicle for that "
                "holding. It was registered as a Panamanian shell company in 1995 by Giuseppe "
                "Nahmad through the Geneva office of Mossack Fonseca and UBS, initially "
                "structured with bearer shares — a format providing untraceable beneficial "
                "ownership. David Nahmad became the sole documented owner in January 2014. "
                "The April 2016 Panama Papers investigation, published jointly by ICIJ and "
                "OCCRP, identified IAC as the vehicle through which the family sought to "
                "conceal ownership of Amedeo Modigliani's <em>Seated Man with a Cane</em> "
                "(1918). [Finding #4152]</p>"
                "<p>Swiss prosecutors raided the Geneva Freeport and seized the Modigliani. "
                "In proceedings before a New York court, the family initially denied beneficial "
                "ownership, arguing IAC was an independent entity. In November 2025, the NY "
                "Supreme Court ruled in favor of the claimant — grandson of Holocaust survivor "
                "Oscar Stettiner, from whom the painting was looted — finding that David "
                "Nahmad had known the painting was stolen property and had attempted "
                "concealment for decades. The painting had been purchased at Christie's in "
                "1996 for $3.2 million. [Finding #4152]</p>"
                "<p>The Nahmad family were prominent users of Yves Bouvier's Natural Le Coultre "
                "freeport network spanning Geneva, Luxembourg, and Singapore, which provided "
                "the same duty-free buying and selling infrastructure across multiple "
                "jurisdictions. [Finding #4156]</p>"
            ),
        },
        {
            "id": "gambling-conviction-and-russian-organized-crime",
            "title": "Gambling Conviction and Russian Organized Crime Links",
            "content": (
                "<p>Hillel (\"Helly\") Nahmad purchased the entire 51st floor of Trump Tower "
                "(721 Fifth Avenue) for approximately $21.7 million and maintained a Helly "
                "Nahmad Gallery on the premises. From that floor, and from Unit 63A controlled "
                "by co-defendant Vadim Trincher, Nahmad co-led the Nahmad-Trincher "
                "Organization — a sub-enterprise within the broader operation charged in "
                "<em>United States v. Tokhtakhounov</em>, 1:13-cr-00268 (SDNY). The umbrella "
                "case charged 34 defendants across two interlocked organizations in April 2013. "
                "[Finding #4037]</p>"
                "<p>The Taiwanchik-Trincher Organization, the larger of the two enterprises, "
                "was run under the protection of Alimzhan Tokhtakhounov (known as "
                "\"Taiwanchik\" or \"Little Taiwanese\"), an OFAC-sanctioned <em>vor v "
                "zakone</em> connected to the Solntsevskaya and Izmailovskaya crime groups and "
                "to Semyon Mogilevich, who appears on the FBI Ten Most Wanted list. "
                "Tokhtakhounov remains a fugitive in Russia; the U.S. State Department offers "
                "a reward for his apprehension. [Finding #4003] The enterprise laundered more "
                "than $100 million from 2006 to 2012 through Cyprus shell companies. "
                "[Finding #4153]</p>"
                "<p>Helly Nahmad was convicted in November 2013. He was sentenced to one year "
                "and one day, served five months at Otisville Federal Correctional Institution, "
                "was fined $30,000, and forfeited $6.4 million. He was also charged with wire "
                "fraud in connection with a $250,000 painting sale. [Finding #4076] FBI "
                "wiretap evidence from March 2012 captured Nahmad explaining the art market's "
                "utility for financial transfers: <em>\"sometimes a bank needs a justification "
                "for a wire... you are buying a painting.\"</em> [Finding #4153]</p>"
                "<p>Nahmad was also a purchaser of two penthouses at 432 Park Avenue "
                "(Units 71A and 71B) for $60 million, acquired through an LLC. [Finding #4153] "
                "The co-defendant Anatoly Golubchik — who received a five-year sentence — "
                "has a documented corporate link to the Mogilevich network through the shared "
                "directorship of Lytton Ventures Inc., a Cyprus shell company whose other "
                "director served entities held under the name of Mogilevich's first wife. "
                "[Finding #4001] <a href=\"/dossiers/steve-witkoff\">Steve Witkoff</a> wrote "
                "a character reference letter for Golubchik in 2010. [Finding #4007]</p>"
            ),
        },
        {
            "id": "trump-pardon-and-political-context",
            "title": "Trump Pardon",
            "content": (
                "<p>Donald Trump granted Hillel Nahmad a full pardon on January 20, 2021, the "
                "last day of his first term, in a batch of 143 clemency actions. White House "
                "communications cited Nahmad's post-conviction conduct. Attorney Benjamin "
                "Brafman advocated for the pardon. Brafman also secured pardons for Charles "
                "Kushner (tax evasion and witness tampering) and had previously represented "
                "Harvey Weinstein and Martin Shkreli. [Finding #4075, #4087]</p>"
                "<p>The pardon foreclosed any further legal proceedings arising from the "
                "conviction. Nahmad had purchased and operated from the 51st floor of Trump's "
                "own building for the duration of the criminal enterprise, a fact that had "
                "no bearing on the pardon decision as documented in public records. "
                "[Finding #4041]</p>"
                "<p>An analytical synthesis in the investigation database positions the Nahmad "
                "pardon within a broader pattern of Trump clemency actions covering individuals "
                "with pre-existing financial or real estate ties to Trump properties, alongside "
                "pardons for Changpeng Zhao and Charles Kushner. [Finding #4101] The synthesis "
                "also documents that Witkoff — who later became Trump's Special Envoy to the "
                "Middle East — had vouched for Golubchik, Nahmad's co-defendant, a decade "
                "before the pardon. [Finding #4225]</p>"
            ),
        },
        {
            "id": "1mdb-and-offshore-entities",
            "title": "1MDB Connection and Offshore Entity Structure",
            "content": (
                "<p>In April 2014, David Nahmad entered negotiations to sell a Monet "
                "(<em>Waterlilies With Reflections of Tall Grass</em>) to Jho Low — the "
                "Malaysian financier later charged in connection with the 1Malaysia Development "
                "Berhad (1MDB) fraud — for $22.5 million. A $2.25 million wire transfer was "
                "sent to Nahmad's account. Nahmad subsequently stated that the deal fell "
                "through and that the painting remained his, with the painting independently "
                "valued between $13.6 million and $57 million. [Finding #4154]</p>"
                "<p>The 1MDB case also intersects the Nahmad network through the Park Lane "
                "Hotel transaction: <a href=\"/dossiers/steve-witkoff\">Steve Witkoff</a>'s "
                "Witkoff Group purchased the Park Lane Hotel (36 Central Park South) in 2013 "
                "for $654 million in a joint venture with Jho Low, whose stake the DOJ later "
                "alleged was funded with stolen 1MDB proceeds. [Finding #3975]</p>"
                "<p>The BVI entity DHN Ltd. (LEI: 5493002RWQNJJJJ42268) — headquartered at "
                "Davide Nahmad's Monaco address — was created on July 30, 2013, through PFD "
                "Corporate Services in Tortola, four months after the April 2013 indictment of "
                "the Nahmad-Trincher Organization. Its LEI status lapsed in December 2025. "
                "No public beneficial ownership or purpose has been established for DHN Ltd. "
                "beyond the GLEIF registration record. [Finding #4154]</p>"
            ),
        },
        {
            "id": "epstein-corpus-references",
            "title": "Epstein Corpus References",
            "content": (
                "<p>The DOJ Epstein document corpus (EFTA series) contains four references "
                "relevant to the Nahmad family. EFTA02712389, an email dated March 12, 2015 "
                "with the subject line <em>\"Helly Nahmad. New fun friend,\"</em> was sent to "
                "\"Jeffrey\" from an unidentified correspondent — approximately 15 months after "
                "Nahmad's November 2013 guilty plea and shortly after his release from Otisville. "
                "[Finding #4086]</p>"
                "<p>EFTA02386102 and EFTA02369796, both from July 2016, document an "
                "<a href=\"/dossiers/jeffrey-epstein\">Epstein</a> associate meeting Joseph "
                "Nahmad at a venue identified as \"jimmiz\" — consistent with Jimmy'z "
                "nightclub in Monte Carlo — and subsequently boarding \"its boat,\" indicating "
                "social overlap between the Epstein network and Nahmad family members in Monaco. "
                "[Finding #4086] A May 2018 email, EFTA01056533, records an associate "
                "expressing interest in employment at the Nahmad Gallery. [Finding #4086]</p>"
                "<p>None of these references establish a financial or operational relationship "
                "between Epstein and the Nahmad family. They document social contact in Monaco "
                "and New York City gallery circles during the period when the Epstein network "
                "was active.</p>"
            ),
        },
        {
            "id": "art-market-regulatory-context",
            "title": "Art Market Regulatory Context",
            "content": (
                "<p>The U.S. art market was, until recently, the largest legal unregulated "
                "industry in the country at approximately $65 billion annually. The Art Market "
                "Integrity Act, introduced in July 2025, would apply Anti-Money Laundering and "
                "Bank Secrecy Act requirements to art dealers — requirements that have applied "
                "to other financial intermediaries for decades. [Finding #4156]</p>"
                "<p>A 2022 U.S. Treasury study and a March 2025 Harvard HALO report both "
                "examined the vulnerability of high-value art transactions to financial crime. "
                "The Geneva Freeport model specifically — in which works are stored and traded "
                "within a customs-sealed zone — prevents any fiscal-authority notification of "
                "transactions, a gap the Nahmad family's documented operations exploited across "
                "multiple decades. [Finding #4156]</p>"
                "<p>Note: Albert Nahmad, CEO of Watsco (NYSE: WSO, market cap approximately "
                "$7.3 billion, a Miami-based HVAC distribution company) appears in SEC EDGAR "
                "Form 4 filings and is a distinct family branch with no documented connection "
                "to the Geneva freeport or Panama shell company operations described above. "
                "[Finding #4156]</p>"
            ),
        },
    ]

    open_questions = [
        (
            "DHN Ltd. (BVI) was created on July 30, 2013 — three months after the April 2013 "
            "Nahmad-Trincher indictment. What was the purpose of the entity, who are its "
            "beneficial owners beyond Davide Nahmad, and why did its LEI lapse in December 2025?"
        ),
        (
            "The $2.25 million wire transfer from Jho Low to David Nahmad's account in April "
            "2014 was made in connection with a painting sale that Nahmad states did not "
            "complete. Was this transaction disclosed to any regulatory authority, and what "
            "account received the wire?"
        ),
        (
            "IAC S.A. held bank accounts at both UBS and Citibank, with signing authority "
            "distributed across David, Ezra, and Giuseppe Nahmad. Were any of those accounts "
            "examined in the Swiss criminal investigation, and what was the outcome of that "
            "investigation beyond the Modigliani seizure?"
        ),
        (
            "The EFTA email corpus documents Epstein social contact with Helly and Joseph "
            "Nahmad from 2015 to 2018 — a period encompassing Nahmad's release from prison "
            "and the year before Epstein's 2019 arrest. Were any Nahmad family members "
            "contacted during the federal investigation of Epstein?"
        ),
        (
            "What is the current legal status of the Modigliani <em>Seated Man with a "
            "Cane</em> following the November 2025 NY Supreme Court ruling? Has the painting "
            "been transferred to the Stettiner heir, or is the judgment under appeal?"
        ),
        (
            "The wiretap recorded Helly Nahmad discussing art sales as a mechanism to "
            "justify bank wire transfers. Was this statement used to examine whether the "
            "Nahmad Gallery conducted art transactions on behalf of gambling ring participants, "
            "and if so, what was the result of that investigation?"
        ),
    ]

    applicable_models = [
        "parallel-financial-system",
        "jurisdictional-arbitrage",
        "shell-company",
        "offshore-opacity",
        "pay-to-play",
        "narrative-shield",
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
    curation["curated_at"] = datetime.now(timezone.utc).isoformat()
    dossier["curation"] = curation

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print("Wrote curation to", DOSSIER_PATH)
    print(f"  Sections: {len(new_fields['sections'])}")
    print(f"  Open questions: {len(new_fields['open_questions'])}")
    print(f"  Applicable models: {len(new_fields['applicable_models'])}")


if __name__ == "__main__":
    main()
