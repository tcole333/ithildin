#!/usr/bin/env python3
"""Curation script for Dechert LLP dossier."""

import json
from pathlib import Path
from datetime import datetime, timezone

DOSSIER_PATH = Path("content/dossiers/dechert-llp.json")


def build_curation() -> dict:
    lead = (
        "<p><strong>Dechert LLP</strong> is an international law firm best known in this investigation as the firm retained by "
        "<a href=\"/dossiers/apollo-global-management\">Apollo Global Management</a>'s Conflicts Committee in October 2020 to conduct "
        "an independent examination of the financial and professional relationship between <a href=\"/dossiers/jeffrey-epstein\">Jeffrey Epstein</a> "
        "and Apollo co-founder <a href=\"/dossiers/leon-black\">Leon Black</a>. The resulting report, issued January 22, 2021, was filed as Exhibit 99.1 "
        "to an Apollo 8-K (ADSH 0001193125-21-016405) and became the principal public record documenting $158 million in advisory fee payments from "
        "Black to Epstein between 2013 and 2017. The report's two core conclusions &mdash; that Apollo \"never did any business with\" Epstein and "
        "that \"neither co-founder hired Epstein\" &mdash; define the corporate narrative that Apollo subsequently defended in shareholder communications "
        "and public statements.</p>"
        "<p>Those conclusions are in tension with the documentary record produced by DOJ Volume 11 and House Oversight disclosures. "
        "Dechert itself acknowledged that <a href=\"/dossiers/financial-trust-company\">Epstein's Financial Trust Company</a> purchased 263,257 Apollo IPO shares, "
        "invested $910,000 in AP SHL Investors LLC, and invested $1.3 million in AP Technology Partners LLC &mdash; entities \"formed by certain Apollo "
        "executives\" &mdash; yet characterized these as not constituting \"business\" with Epstein, describing the language as \"perhaps more nuanced than "
        "might appear at first glance.\" Separately, EFTA documents show <a href=\"/dossiers/paul-weiss\">Paul Weiss</a> was preparing IRS Form 8865 "
        "filings for \"all three guys\" (EFTA02670537) at Epstein's coordination, <a href=\"/dossiers/marc-rowan\">Marc Rowan</a> transmitted confidential "
        "Tax Receivable Agreement calculations to Epstein, and Epstein's \"leon agenda\" directed a meeting with all three co-founders on partnership "
        "amendments. The report's investigative scope did not reach these communications because they ran through personal email accounts and "
        "<a href=\"/dossiers/brad-karp\">Brad Karp</a>'s firm &mdash; the same firm that assisted in document collection for the Dechert investigation.</p>"
    )

    system_role = (
        "Dechert LLP functions as the institutional author of the corporate narrative that bounded Epstein's role as personal adviser to Leon Black, "
        "producing the only independent investigation of the relationship whose scope was simultaneously limited by the conflict-laden document "
        "collection process it relied upon &mdash; a process assisted by Paul Weiss, the firm whose chairman had been forwarding confidential client "
        "tax correspondence to Epstein throughout the period under review."
    )

    sections = [
        {
            "id": "commission-and-scope",
            "title": "The Commission and Its Structural Constraints",
            "viz": "timeline",
            "content": (
                "<p>In October 2020, Apollo's Conflicts Committee retained Dechert LLP to conduct what it described as an independent investigation "
                "of the Epstein-Black relationship and any relationship between Epstein and Apollo as an institution (EFTA02730996). The engagement "
                "followed public reporting on the relationship and came amid pressure from Apollo limited partners. Dechert issued its report on "
                "January 22, 2021, and Apollo filed it as Exhibit 99.1 to a Form 8-K on January 25, 2021.</p>"
                "<p>The report's own language defines its investigative perimeter. Document collection extended to \"Apollo for current and former "
                "employees of Apollo dating back to 1998 as well as for all current and former employees of the Family Office.\" This perimeter "
                "captured work email accounts at Apollo and <a href=\"/dossiers/elysium-management\">Elysium Management</a> (Black's family office) "
                "but excluded personal email accounts and third-party legal accounts. The documented communications between "
                "<a href=\"/dossiers/joshua-harris\">Joshua Harris</a>, his attorney Gary Bodian, and Epstein &mdash; which ran through "
                "jeevacation@gmail.com and Mintz Levin accounts &mdash; would not have appeared in any Apollo collection. Dechert noted it "
                "\"interviewed every witness that it had requested with only one exception\" without disclosing the identity of the exception.</p>"
                "<p>The collection was assisted by <a href=\"/dossiers/paul-weiss\">Paul, Weiss, Rifkind, Wharton &amp; Garrison LLP</a>, "
                "Apollo's primary outside counsel. Paul Weiss chairman <a href=\"/dossiers/brad-karp\">Brad Karp</a> had, during the period under "
                "Dechert's review, been forwarding confidential Black family tax correspondence to Epstein, coordinating IRS \"reasonable cause\" "
                "filings, and receiving updates on Harris's tax matters directly from Epstein (EFTA02667860). The firm that assisted in collecting "
                "the documents whose absence shaped the investigation's conclusions had an undisclosed relationship with the subject of the "
                "investigation. Dechert acknowledged this configuration without addressing the conflict.</p>"
            ),
        },
        {
            "id": "payment-reconstruction",
            "title": "The Payment Ledger and Fee Dispute",
            "viz": "timeline",
            "content": (
                "<p>The Dechert report's most durable contribution to the public record is its reconstruction of the payment timeline. "
                "Dechert Exhibit A (referenced in EFTA00027019) documents five years of transfers from "
                "<a href=\"/dossiers/leon-black\">Black</a> to Epstein's "
                "<a href=\"/dossiers/southern-trust-company-inc\">Southern Trust Company</a>: $50 million in 2013, $70 million in 2014, "
                "$30 million in 2015, nothing in 2016, and $8 million in April 2017, totaling $158 million. The 2013 total comprises two "
                "distinct streams: $23.5 million under a signed February 13, 2013 service agreement for GRAT remediation work ($15 million "
                "in February, $8.5 million in October), and a further $26.5 million representing the first two installments of a second, "
                "unsigned agreement negotiated in May 2013 for $56.5 million payable over five installments.</p>"
                "<p>The 2014 figure of $70 million included $20 million attributed to a \"step-up basis transaction\" &mdash; a tax strategy "
                "Dechert identified as generating approximately $600 million in perceived tax benefit for Black. Epstein subsequently demanded "
                "10 percent of that perceived benefit, or $60 million, as his fee for the step-up transaction. Black paid $20 million. "
                "This $40 million gap became the central dispute that ended the relationship: no payments were made in 2016, and the final "
                "$8 million in April 2017 was described as a settlement rather than a continuation of advisory work. The Dechert report "
                "explicitly states Black erroneously believed his payments to Epstein were tax-deductible because Epstein had represented "
                "them as sixty-cent-on-the-dollar transactions &mdash; a representation Dechert found was false.</p>"
                "<p>Separately, Dechert Exhibit B documents 47 hedge and investment fund transactions from Black-origin funds into "
                "Epstein's Deutsche Bank accounts between May 2014 and April 2019. The exhibit shows major allocations into Valar "
                "Ventures funds, Honeycomb Partners, and four additional Ventures vehicles, with Honeycomb alone receiving approximately "
                "$34 million across five transactions. This ledger, generated by Deutsche Bank AML compliance in 2019, captured payment "
                "flows that continued after Epstein's 2018 sex trafficking charges in the USVI &mdash; two years after the advisory fee "
                "relationship formally ended.</p>"
            ),
        },
        {
            "id": "conclusions-versus-record",
            "title": "Stated Conclusions Against the Documentary Record",
            "viz": None,
            "content": (
                "<p>The Dechert report's central conclusion is that <a href=\"/dossiers/apollo-global-management\">Apollo</a> \"never did any "
                "business with\" Epstein and that \"neither co-founder hired Epstein or consulted with him on their personal matters.\" The "
                "report acknowledged its own difficulties with this framing, noting the phrases were \"perhaps more nuanced than might appear "
                "at first glance.\" The specific acknowledgments supporting that qualification are significant: FTC purchased 263,257 Apollo "
                "IPO shares through the directed share program at the 2011 public offering, invested $910,562 in AP SHL Investors LLC in "
                "January 2002, and invested $1,311,522 in AP Technology Partners LLC beginning in fiscal year 2000. Both AP SHL and AP "
                "Technology were formed by \"certain Apollo executives\" to explore investment opportunities Apollo chose not to pursue. "
                "FTC received annual K-1s from these vehicles. FTC also invested in Environmental Solutions World Wide (ESWW) alongside "
                "<a href=\"/dossiers/leon-black\">Black</a> and Black family members in 2011 (Finding 1469).</p>"
                "<p>The \"neither co-founder hired Epstein\" conclusion requires that the following documented interactions not constitute "
                "a hiring or consultation. EFTA02670537 records an email asking whether <a href=\"/dossiers/paul-weiss\">Paul Weiss</a> was "
                "\"writing for all three guys\" on IRS Form 8865 reasonable cause statements, with Epstein as the coordinator. EFTA02655647 "
                "records Epstein's fee proposal naming <a href=\"/dossiers/marc-rowan\">Marc Rowan</a> and "
                "<a href=\"/dossiers/joshua-harris\">Joshua Harris</a> explicitly as required signatories. EFTA02455405 records Epstein's "
                "\"leon agenda\" directing a meeting with all three co-founders to discuss BRH Holdings LP amendments. Rowan transmitted "
                "confidential Tax Receivable Agreement calculations to Epstein via Apollo CFO Chris Weidler. Harris's attorney Gary Bodian "
                "routed tax compliance correspondence to Epstein through personal and Mintz Levin accounts, outside the Dechert collection. "
                "An October 22, 2013 meeting at Epstein's 9 East 71st Street residence brought all three co-founders together in a single "
                "documented event (EFTA02576529).</p>"
                "<p>Dechert's resolution of the three-founder question was to note that Black \"did positively comment on the substantial value "
                "of Epstein's services and, at Epstein's repeated request, did try to introduce Epstein to his co-founders.\" This characterization "
                "of the documented record treats Epstein's coordination of tax filings for \"all three guys\" as an introduction rather than an "
                "engagement, a reading the EFTA documents do not clearly support.</p>"
            ),
        },
        {
            "id": "apollo-conflict-structure",
            "title": "The Conflict Structure of the Investigation",
            "viz": "ego_network",
            "content": (
                "<p>The structural conflicts embedded in the Dechert engagement are documented within the report itself. "
                "<a href=\"/dossiers/paul-weiss\">Paul Weiss</a> was retained to assist in document collection as Apollo's primary outside "
                "counsel. At the time of the investigation, Dechert had an existing business relationship with Apollo (LittleSis relationship "
                "ID 2018121). Whether alternative firms were considered for the engagement is not addressed in the report or the 8-K. The "
                "Conflicts Committee that commissioned Dechert was a committee of Apollo's own board, not an independent regulator. No "
                "SEC enforcement action or court proceeding supervised the scope of the investigation or the completeness of the production.</p>"
                "<p>The Paul Weiss conflict is the most operationally significant because it was Paul Weiss that possessed &mdash; and could "
                "suppress &mdash; the most sensitive documents. <a href=\"/dossiers/brad-karp\">Brad Karp</a> had forwarded confidential "
                "Harris tax compliance correspondence to Epstein (EFTA02667860). Karp had been managing <a href=\"/dossiers/leon-black\">Black</a>'s "
                "fee disputes with Epstein directly. Paul Weiss had prepared the service agreement governing Black's payments to Epstein "
                "(EFTA01909135), drafted Black's 2013 Will and Revocable Trust documents that were routed to Epstein before Black saw them "
                "(EFTA02707648), and prepared IRS materials for BRH Holdings that Epstein had coordinated. Paul Weiss's own privilege log "
                "would have covered a substantial volume of the most relevant communications. Dechert acknowledged Paul Weiss's role "
                "without identifying this as a limitation on the investigation's completeness.</p>"
                "<p>The temporal scope of the investigation also warrants note. Dechert's collection of Apollo employee documents ran "
                "\"dating back to 1998.\" The Apollo co-founders' personal tax and estate work touched by Epstein extended from approximately "
                "2000 through 2017 for fee-related matters and through 2019 for investment positions. The investigation's focus on "
                "the fee payments, while the most visible aspect of the relationship, treated Epstein's structural position as an "
                "investor in Apollo-affiliated vehicles &mdash; spanning twenty years &mdash; as subsidiary to the advisory fee question.</p>"
            ),
        },
    ]

    open_questions = [
        "Did Dechert request or review Paul Weiss's privilege log, and if so, how many documents were withheld on grounds of attorney-client privilege?",
        "Which witness was the single exception Dechert was unable to interview, and was that witness connected to the Harris-Bodian-Epstein channel?",
        "Did Dechert's pre-existing business relationship with Apollo (LittleSis rel 2018121) influence the firm's selection for the engagement, and were competing firms evaluated?",
        "Was the scope of the investigation defined by the Conflicts Committee before or after the Committee reviewed Apollo's document universe, and who at Apollo determined which employees were included in the collection?",
        "Why did Dechert characterize FTC's Apollo IPO share purchase through the directed share program as not constituting 'business' with Apollo, given that directed share allocations require institutional authorization?",
        "Did Dechert review the full ESWW investment record, including board documents and co-investor agreements, in assessing whether FTC's joint investment with Black family members constituted a business relationship?",
        "Were the 47 Deutsche Bank investment transactions in Dechert Exhibit B provided voluntarily by Deutsche Bank or produced through a formal subpoena, and did Dechert examine whether post-2017 flows had any Apollo nexus?",
    ]

    applicable_models = [
        "narrative-shield",
        "enabler-gradient",
        "complexity-as-credential",
    ]

    return {
        "lead": lead,
        "system_role": system_role,
        "sections": sections,
        "open_questions": open_questions,
        "applicable_models": applicable_models,
        "curated_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    with open(DOSSIER_PATH) as f:
        dossier = json.load(f)

    dossier["curation"] = build_curation()

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  lead: {len(dossier['curation']['lead'])} chars")
    print(f"  sections: {len(dossier['curation']['sections'])}")
    print(f"  open_questions: {len(dossier['curation']['open_questions'])}")
    print(f"  applicable_models: {dossier['curation']['applicable_models']}")


if __name__ == "__main__":
    main()
