#!/usr/bin/env python3
"""Curate the Kirkland & Ellis Foundation dossier."""

import json
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/kirkland-ellis-foundation.json")


def load_dossier():
    with open(DOSSIER_PATH) as f:
        return json.load(f)


def build_curation():
    return {
        "lead": (
            "<p>The Kirkland &amp; Ellis Foundation (EIN 36-3160355) is the charitable giving arm of "
            "Kirkland &amp; Ellis LLP (EIN 36-1326630), one of the largest law firms in the world. "
            "Operating since at least 2006 as a 509(a)(2) public charity, the Foundation distributed "
            "$78.6 million across 348 grant cycles between 2015 and 2024, funding legal aid organizations, "
            "universities, social services, and civic institutions. <a href=\"#financial-activity\">Funding flows</a> "
            "through a matching-gift structure in which individual K&amp;E partners contribute cash and "
            "publicly traded securities; the Foundation matches and distributes to roughly 300 recipient "
            "organizations per year. The Foundation's investigative relevance in the Epstein context is "
            "structural rather than financial: <strong>no grants were made to any Epstein-connected entity</strong>, "
            "and the Foundation shares its address, mailing list, and administrative staff with K&amp;E LLP — "
            "the same firm whose partners negotiated Jeffrey Epstein's 2008 non-prosecution agreement and whose "
            "alumni subsequently held positions as U.S. Attorney General, Deputy Attorney General, White House "
            "Counsel, and Associate Justice of the Supreme Court. "
            "(<a href=\"#financial-activity\">990:363160355</a>)</p>"
        ),

        "system_role": (
            "The Kirkland & Ellis Foundation is the institutional philanthropy vehicle of Kirkland & Ellis LLP. "
            "It functions as a pass-through matching-gift program: partner contributions (cash and appreciated "
            "stock) flow in, are pooled and matched by firm-level contributions, then distributed annually to "
            "roughly 300 nonprofit organizations. The Foundation's board is composed entirely of current K&E "
            "partners serving without compensation. It files as a 509(a)(2) public charity — qualifying on the "
            "basis of broad public support rather than private endowment — and explicitly does not monitor "
            "end-use of grant funds after disbursement (IRS Form 990, Schedule I, Part IV). The Foundation's "
            "significance in this investigation is as an indicator of K&E's institutional character and "
            "philanthropic priorities, and as a data point for ruling out financial entanglement with "
            "Epstein-network foundations."
        ),

        "sections": [
            {
                "id": "financial-activity",
                "title": "Financial Activity",
                "viz": "timeline",
                "content": (
                    "<p>The Foundation's IRS filings document a decade of consistent grant-making punctuated by "
                    "one significant financing anomaly. Annual revenue held in the $6–10 million range from 2011 "
                    "through 2015, then spiked to $25.5 million in 2016 before settling back to $8.6 million by "
                    "2023. That 2016 spike is fully explained by the filing data: partners contributed 317 "
                    "noncash gifts of publicly traded securities valued at $11.3 million, on top of $14.2 million "
                    "in cash. Rather than distributing the full windfall immediately, the Foundation moved most "
                    "of it into temporarily restricted net assets, which swelled from $6.2 million to $18.6 million "
                    "that year. Grants in 2016 were held at $11.9 million to 321 organizations; the deferred "
                    "funds were released in 2017, when grants jumped to $14.6 million against only $9.6 million "
                    "in new revenue. (<cite>990:363160355</cite>)</p>"

                    "<p>The financial relationship between the Foundation and K&E LLP is documented in Schedule R "
                    "filings. In 2016, K&E LLP transferred $154,853 as a gift/grant plus $23,000 in "
                    "reimbursements. By 2022, the firm-level transfer had grown to $13,743,532 in a single "
                    "cash gift. Both filings confirm sharing of facilities, mailing lists, and a de minimis "
                    "number of paid employees. K&E LLP is designated as the Foundation's sole related entity. "
                    "(<cite>990:363160355</cite>)</p>"

                    "<p>Across 2015–2024, total Foundation grant disbursements reached $78.6 million. The 2015 "
                    "filing is the last year in which individual recipients were itemized in the public return; "
                    "from 2016 onward, the 300+ recipient schedules are attached as separate documents marked "
                    "'SEE ATTACHED' and are not included in the publicly filed XML. The 2015 itemized data "
                    "($10.8 million across 341 named organizations) reveals the Foundation's distributional "
                    "priorities: legal and policy organizations received $2.66 million across 83 recipients; "
                    "universities received $2.22 million across 29 institutions, weighted toward K&amp;E feeder "
                    "schools such as Northwestern ($588K), University of Chicago ($565K), and the University of "
                    "Chicago Law School; social services received $3.44 million across 140 organizations; "
                    "Jewish communal and Israel-related organizations received $591K across 16 recipients "
                    "including the Jewish United Fund ($159K), UJA-Federation ($104K), and the American "
                    "Jewish Committee ($101K); youth and education received $811K; arts and culture $764K; "
                    "and medical $301K. The Federalist Society received $8,167 — a de minimis amount "
                    "inconsistent with the narrative that K&amp;E is primarily a conservative legal institution. "
                    "(<cite>990:363160355</cite>)</p>"

                    "<p>A negative finding with investigative weight: cross-referencing the 2015 itemized "
                    "recipient list against known Epstein-network foundations — Gratitude America Ltd, "
                    "Enhanced Education, the J. Epstein Virgin Islands Foundation, Southern Trust Company, "
                    "and Ghislaine Maxwell's TerraMar Project — returns zero matches. The Foundation did not "
                    "fund any of these entities. Combined with the Wave 3 synthesis finding that K&amp;E's "
                    "investigative significance is institutional rather than financial, this rules out the "
                    "Foundation as a channel for direct financial flows to the Epstein network. "
                    "(<cite>990:363160355</cite>)</p>"
                ),
                "finding_ids": [3172, 3176, 3173, 3174],
                "connection_ids": []
            },
            {
                "id": "governance",
                "title": "Governance and Board Composition",
                "viz": None,
                "content": (
                    "<p>The Foundation's board consists entirely of current K&amp;E partners who receive no "
                    "compensation for their service. In 2016, the board was led by Andrew R. McGaan as "
                    "President, with David B. Feirstein, Ashley S. Gregory, David A. Handler, Mikaal Shoaib, "
                    "Seth D. Traxler, and Karen N. Walker serving as Secretary/Treasurer. By 2022, Daniel "
                    "Laytin had replaced McGaan as President; Handler, Shoaib, and Traxler continued as "
                    "directors, joined by Jennifer Levy (Secretary/Treasurer), Jai Agrawal, Jason Kanner, "
                    "and Leo Plank. (<cite>990:363160355</cite>)</p>"

                    "<p>One governance provision documented in the 990 filings is notable for investigative "
                    "purposes: the Foundation explicitly discloses that it does not monitor the use of grant "
                    "funds after disbursement (Schedule I, Part IV). This is standard practice for many "
                    "matching-gift foundations distributing to hundreds of established nonprofits, but it "
                    "means the Foundation lacks internal controls that would detect if a grant recipient "
                    "subsequently directed funds to related parties. In the context of the 2015 itemized "
                    "recipient list — which is the last year of full public disclosure — there is no "
                    "indication of any problematic end-use. (<cite>990:363160355</cite>)</p>"
                ),
                "finding_ids": [3175],
                "connection_ids": []
            },
            {
                "id": "institutional-context",
                "title": "Institutional Context: K&E LLP and the Epstein Matter",
                "viz": "ego_network",
                "content": (
                    "<p>The Foundation is legally and operationally distinct from K&amp;E LLP, but understanding "
                    "the Foundation requires placing it within the firm's broader profile. K&amp;E LLP "
                    "(EIN 36-1326630) represented Jeffrey Epstein in the 2007–2008 federal prosecution in "
                    "Florida. Partner Jay Lefkowitz served as lead defense counsel, corresponding directly with "
                    "SDFL prosecutors and meeting with the U.S. Attorney alongside co-counsel Ken Starr. The "
                    "firm billed at least $1,319,336 on the Epstein defense matter through December 31, 2008, "
                    "plus $9,000 for an FTC/DB Zwirn matter through September 30, 2009. The resulting "
                    "non-prosecution agreement — signed when K&amp;E partner Alex Acosta served as U.S. "
                    "Attorney for SDFL — was ruled a Crime Victims' Rights Act violation by a federal judge "
                    "in 2019. (<cite>990:363160355</cite>; dossier: "
                    "<a href=\"/dossiers/kirkland-ellis\">Kirkland &amp; Ellis</a>)</p>"

                    "<p>K&amp;E's network significance extends well beyond the Epstein matter. Graph analysis "
                    "of the full investigation network places K&amp;E at degree rank 6 (47 direct connections) "
                    "and betweenness centrality rank 15. The firm anchors the largest closed triad cluster: "
                    "the clique {Brian Benczkowski, Jeffrey Rosen, K&amp;E, Mark Filip, William Barr} "
                    "represents concentrated DOJ leadership — all K&amp;E alumni who held positions in the "
                    "Criminal Division, the Deputy Attorney General's office, or the Attorney General's office "
                    "during periods relevant to this investigation. Additional K&amp;E alumni holding relevant "
                    "positions include Brett Kavanaugh (SCOTUS), Pat Cipollone (White House Counsel), "
                    "John Eisenberg (Deputy White House Counsel and NSC Legal Adviser, now AAG National "
                    "Security Division), Erin Nealy Cox (U.S. Attorney for NDTX who brought the Boeing DPA), "
                    "and Patrick Philbin (Deputy White House Counsel). "
                    "(<a href=\"/dossiers/kirkland-ellis\">Kirkland &amp; Ellis</a>; "
                    "<a href=\"/dossiers/william-barr\">William Barr</a>; "
                    "<a href=\"/dossiers/brian-benczkowski\">Brian Benczkowski</a>; "
                    "<a href=\"/dossiers/jeffrey-rosen\">Jeffrey Rosen</a>; "
                    "<a href=\"/dossiers/mark-filip\">Mark Filip</a>)</p>"

                    "<p>Mark Filip's trajectory is worth specific attention: as a K&amp;E partner, he became "
                    "Deputy Attorney General in 2008 — the highest DOJ official to review the Epstein NPA. "
                    "He returned to K&amp;E after his DOJ service and subsequently led the firm's defense of "
                    "Boeing in the 737 MAX criminal matter, BP in Deepwater Horizon, Volkswagen in the "
                    "emissions scandal, and Goldman Sachs in the 1MDB case. The Deferred Prosecution "
                    "Agreement framework that shaped all of those outcomes was substantially developed "
                    "during Filip's tenure as DAG. (<a href=\"/dossiers/mark-filip\">Mark Filip</a>)</p>"

                    "<p>William Barr served as K&amp;E Of Counsel from 2009 to 2011 and again from 2017 to "
                    "2018, joining the firm one year after K&amp;E secured Epstein's NPA. When Barr became "
                    "Attorney General in 2019, he partially recused from the Epstein matter — only from "
                    "review of the NPA itself, not from the ongoing prosecution. "
                    "(<a href=\"/dossiers/william-barr\">William Barr</a>)</p>"
                ),
                "finding_ids": [],
                "connection_ids": [1717]
            }
        ],

        "open_questions": [
            {
                "id": "oq-1",
                "question": (
                    "Post-2015 grant recipient schedules are withheld from the public 990 XML as 'SEE "
                    "ATTACHED.' What organizations appear in the 2016–2024 attached schedules, and does "
                    "the recipient mix shift after 2016 (the year revenue spiked due to stock donations)?"
                ),
                "priority": "medium"
            },
            {
                "id": "oq-2",
                "question": (
                    "The 2016 Schedule R shows K&E LLP paid $154,853 to the Foundation; by 2022 that "
                    "figure was $13,743,532 — an 89x increase. What explains this trajectory? Are the "
                    "intervening years (2017–2021) documented in Schedule R, and when did the firm-level "
                    "contribution scale up?"
                ),
                "priority": "medium"
            },
            {
                "id": "oq-3",
                "question": (
                    "The Chicago Council on Global Affairs received $513K from the Foundation in 2015 — "
                    "the fourth-largest single grant. K&E has significant overlap with foreign policy "
                    "networks. Who from K&E sits on CCGA's board or committees, and does CCGA have "
                    "documented relationships with any Epstein network nodes?"
                ),
                "priority": "low"
            },
            {
                "id": "oq-4",
                "question": (
                    "The Foundation explicitly does not monitor grant fund use after disbursement. For "
                    "the 83 legal and policy organizations that received $2.66 million in 2015, are any "
                    "of those organizations also recipients of Epstein network foundation grants (from "
                    "Gratitude America, Enhanced Education, or the JEVI Foundation), creating an "
                    "indirect overlap at the recipient level rather than the donor level?"
                ),
                "priority": "low"
            },
            {
                "id": "oq-5",
                "question": (
                    "Do any of the 2016–2022 board members (Daniel Laytin, Jennifer Levy, Jai Agrawal, "
                    "Jason Kanner, Leo Plank) have documented connections to Epstein clients, "
                    "counterparties, or affiliated institutions beyond their K&E partnership?"
                ),
                "priority": "low"
            }
        ],

        "applicable_models": [
            {
                "id": "am-1",
                "model": "BigLaw Philanthropy as Talent Pipeline Signal",
                "description": (
                    "The Foundation's university grant distribution — $2.22 million to 29 institutions in "
                    "2015, weighted toward Northwestern, University of Chicago, and other K&E feeder schools "
                    "— functions as a form of institutional investment in the recruitment pipeline. Law firm "
                    "foundations commonly use this mechanism to reinforce relationships with law school "
                    "faculties and deans. This model does not require coordination with the firm's "
                    "client-facing work, but the overlap between grant recipients and K&E's feeder institutions "
                    "is structural rather than incidental."
                )
            },
            {
                "id": "am-2",
                "model": "Revolving Door Institutional Capture",
                "description": (
                    "K&E's documented alumni placement across DOJ leadership, White House Counsel, and SCOTUS "
                    "over a 15-year period constitutes a case study in how a single institutional actor can "
                    "achieve distributed influence without any individual action being improper. No K&E "
                    "partner or alumnus is alleged to have coordinated government decisions for the firm's "
                    "benefit. The pattern is structural: the firm selects partners with the background for "
                    "government service; those partners rotate through; they return. The Foundation's role "
                    "in this model is as a reputational anchor — its broadly distributed grant-making to "
                    "legal aid organizations, civic institutions, and universities reinforces K&E's "
                    "self-presentation as a civic institution rather than a private-interest firm."
                )
            },
            {
                "id": "am-3",
                "model": "Stock-Donation Liquidity Management",
                "description": (
                    "The 2016 revenue spike (317 noncash contributions of publicly traded securities, "
                    "$11.3 million in market value) is consistent with a common tax-optimization pattern: "
                    "partners with appreciated stock positions donate shares to the Foundation rather than "
                    "selling them directly, avoiding capital gains tax while claiming a charitable deduction "
                    "at fair market value. The Foundation then liquidates and distributes. The temporary "
                    "restriction mechanism — holding $12 million in reserve from 2016 to release in 2017 — "
                    "allowed the Foundation to smooth its grant-making without forcing rushed disbursement "
                    "of the windfall. This is structurally routine but documents that individual K&E partners "
                    "were contributing substantial concentrated positions in publicly traded equities."
                )
            }
        ]
    }


def main():
    dossier = load_dossier()

    curation = build_curation()

    # Preserve existing key_finding_ids and section_suggestions structure where compatible
    # but write the full curated content
    dossier["curation"] = {
        "lead": curation["lead"],
        "system_role": curation["system_role"],
        "sections": curation["sections"],
        "open_questions": curation["open_questions"],
        "applicable_models": curation["applicable_models"],
        "key_finding_ids": [3176, 3173, 3175, 3172, 3174],
        "key_identifiers": {
            "jurisdictions": ["IL"],
            "officers": [
                "Andrew R. McGaan",
                "Daniel Laytin",
                "David A. Handler",
                "Jennifer Levy",
                "Jay Lefkowitz",
                "Mark Filip"
            ],
            "entities": [
                "Kirkland & Ellis LLP (EIN 36-1326630)"
            ]
        },
        "curated_at": dossier.get("curation", {}).get("curated_at", "2026-03-11T23:00:46.761812"),
    }

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"Sections: {[s['id'] for s in curation['sections']]}")
    print(f"Open questions: {len(curation['open_questions'])}")
    print(f"Applicable models: {len(curation['applicable_models'])}")


if __name__ == "__main__":
    main()
