#!/usr/bin/env python3
"""Write curation fields into content/dossiers/scott-mayer.json."""

import json
import sys
from pathlib import Path

DOSSIER_PATH = Path(__file__).parent.parent / "content" / "dossiers" / "scott-mayer.json"

CURATION = {
    "lead": (
        "<p>Scott Andrew Mayer spent three and a half years as Boeing's Chief Labor Counsel — "
        "the company's lead attorney before the National Labor Relations Board — before being nominated "
        "by President Trump in July 2025 to sit as a Member on that same Board [Finding #5424]. During his "
        "Boeing tenure, Mayer personally represented the company as its attorney of record in NLRB cases "
        "as recently as October 2024, including Case 19-CA-352164, an 8(a)(5) bad-faith bargaining charge "
        "filed in Seattle [Finding #5427]. His financial disclosure at the time of nomination listed Boeing "
        "holdings of $5–25 million in stock, $100–250 million in employer equity, unvested RSUs valued at "
        "$250–500 thousand, a 401(k), an executive supplemental savings plan, and an anticipated bonus — "
        "all still formally carried as active while he was a sitting Board member [Finding #5250].</p>"
        "\n\n"
        "<p>FEC records document that Mayer made biweekly $50 payroll-deduction contributions to The Boeing "
        "Company PAC continuously from at least October 2023 through December 18, 2025 — the day the Senate "
        "confirmed him — totaling $2,500 across 50 transactions, with contributions proceeding uninterrupted "
        "through his nomination date, his Senate HELP Committee hearing, and his confirmation vote [Finding #5426]. "
        "At the October 1, 2025 committee hearing, Mayer testified under questioning from Senators Sanders and "
        "Hawley that he was 'not involved in the negotiations' and 'not serving as a representative to the company "
        "at the hearing,' at a time when NLRB docket records placed him as Boeing's listed legal representative "
        "in a case filed twelve months earlier [Finding #5431]. The committee advanced his nomination 12-11 on "
        "December 3, 2025; he was sworn in January 7, 2026 [Finding #5424].</p>"
        "\n\n"
        "<p>Mayer's August 28, 2025 ethics agreement requires divestiture of all Boeing stock within 90 days of "
        "confirmation — a deadline falling around March 18, 2026 — and a 2-year cooling period under 5 CFR 2635.503 "
        "after RSU vesting dates that extends recusal obligations potentially into 2027–2028 [Finding #5425]. "
        "As of March 2026, no recusal list for Mayer has been published on nlrb.gov, despite the NLRB's own 2019 "
        "Ethics Recusal Report establishing that standard for all Board members; weekly decision summaries show "
        "Mayer participating in published decisions since January 7, 2026 [Finding #5433]. He is one of at least "
        "three Boeing executives who moved into Trump administration roles with substantial retained Boeing holdings, "
        "alongside Sean McMaster (now FHWA Administrator at DOT) and Luisa Guerra-Young (DOT Deputy Assistant "
        "Secretary for Public Liaison) [Finding #5430].</p>"
    ),

    "system_role": (
        "Mayer illustrates how a company can position its own labor litigation counsel inside the federal agency "
        "that adjudicates that company's labor disputes — converting direct legal representation into adjudicatory "
        "authority at the same institution, with financial ties to the former employer persisting through the "
        "transition period and ethics obligations that are unverifiable because required transparency mechanisms "
        "have not been activated."
    ),

    "sections": [
        {
            "id": "career-and-confirmation",
            "title": "Career Trajectory and Confirmation",
            "content": (
                "<p>Mayer's pre-government career was built entirely on the management side of labor law. "
                "He trained at Morgan Lewis &amp; Bockius, one of the country's largest management-side labor "
                "practices, then moved through Blank Rome LLP and in-house counsel positions at Aramark, "
                "InterContinental Hotels Group (IHG), and MGM Resorts International before joining Boeing as "
                "Chief Labor Counsel in June 2022 [Finding #5424]. His academic background — Cornell's School "
                "of Industrial and Labor Relations and Villanova Law — is the standard credentialing path for "
                "management-side NLRB practitioners. At Boeing, his portfolio covered NLRB litigation, union "
                "contract interpretation, labor arbitrations, and what Boeing termed 'positive employee relations "
                "strategy' [Finding #5424].</p>"
                "\n\n"
                "<p>Trump nominated Mayer on July 17, 2025. The Senate HELP Committee held his hearing on "
                "October 1, 2025, initially scheduled a vote that was subsequently withdrawn, then advanced "
                "him 12-11 on December 3, 2025. The Senate confirmed him December 18, 2025; he was sworn in "
                "January 7, 2026, with a term expiring December 16, 2029 [Finding #5424]. The narrowness of "
                "the committee vote — and the fact that it required two attempts — reflected opposition from "
                "both Democratic members and Sen. Josh Hawley (R-MO), whose state was then experiencing an "
                "active IAM 837 strike at Boeing's St. Louis facility [Finding #5431].</p>"
                "\n\n"
                "<p>Mayer joins a Board reconstituted under the Trump administration. As of January 7, 2026, "
                "the NLRB's three seated members are David Prouty (Democrat, term expires August 2026), "
                "James Murphy (Republican, term expires December 2027), and Mayer (Republican, term expires "
                "December 2029). Murphy and Mayer hold a 2-1 Republican majority. When Prouty's term expires "
                "in August 2026, the Board will again drop below quorum unless a replacement is confirmed. "
                "Murphy and Mayer have publicly reserved judgment on overturning Biden-era NLRB precedent "
                "until a third Republican member is seated [Finding #5428].</p>"
            ),
            "viz": "timeline",
        },
        {
            "id": "boeing-financial-ties",
            "title": "Financial Ties to Boeing",
            "content": (
                "<p>Mayer's financial disclosure at nomination listed retained Boeing compensation and equity "
                "in six categories: stock valued at $5–25 million, employer equity valued at $100–250 million, "
                "an executive supplemental savings plan, a 401(k), unvested RSUs valued at $250–500 thousand, "
                "and an anticipated bonus [Finding #5250]. At the time the disclosure was filed, his Boeing "
                "employment status was listed as 'Present,' meaning his financial exposure to Boeing's stock "
                "price and to Boeing's labor litigation outcomes was active during the confirmation process "
                "[Finding #5250].</p>"
                "\n\n"
                "<p>FEC records provide a second data set on the Boeing financial relationship. Mayer made "
                "50 biweekly contributions of $50 each to The Boeing Company PAC between at least October 2023 "
                "and December 18, 2025, with employer listed as BOEING, Arlington, VA [Finding #5426]. The "
                "contribution series was unbroken: it continued through his July 17, 2025 nomination, his "
                "October 1, 2025 Senate hearing, his December 3, 2025 committee advancement, and ended on "
                "December 18, 2025 — his Senate confirmation date [Finding #5426]. Payroll-deduction PAC "
                "contributions of this regularity require employer cooperation to maintain, meaning Boeing's "
                "payroll infrastructure was processing these contributions through the day of his confirmation.</p>"
                "\n\n"
                "<p>Boeing's broader government relations posture during this period included $2.6 million "
                "spent on 60 federal lobbyists in Q1 2025 alone, and at least two other executives — "
                "Sean McMaster and Luisa Guerra-Young — placed in Trump administration positions at agencies "
                "(DOT/FAA) that directly regulate Boeing [Finding #5430]. "
                "<a href=\"/dossiers/brian-benczkowski\">Brian Benczkowski</a>, formerly a senior DOJ official, "
                "joined Boeing in September 2025 as VP and Assistant General Counsel for Government Operations, "
                "managing Boeing's relationships with the same federal agencies he previously oversaw from "
                "inside DOJ [Finding #5430].</p>"
            ),
            "viz": None,
        },
        {
            "id": "nlrb-representation-and-recusal",
            "title": "NLRB Representation and Recusal Obligations",
            "content": (
                "<p>Mayer's transition from Boeing's NLRB representative to a seat on the NLRB is documented "
                "in the Board's own case dockets. He is listed as Boeing's attorney of record in Case "
                "19-CA-352164 (The Boeing Company, Region 19, Seattle, filed October 7, 2024), an 8(a)(5) "
                "refusal to bargain and bad-faith bargaining charge, and in Case 16-CA-337549 (Region 16, "
                "San Antonio, filed March 6, 2024), an 8(a)(1) retaliation and discharge charge. Both cases "
                "closed via withdrawal [Finding #5427]. His last documented appearance as Boeing's NLRB "
                "representative predates his nomination by nine months.</p>"
                "\n\n"
                "<p>At his October 1, 2025 Senate HELP Committee hearing, Mayer testified he was 'not involved "
                "in the negotiations' and 'not serving as a representative to the company at the hearing' in "
                "response to questions about the Boeing-IAM 837 strike [Finding #5431]. The NLRB case docket "
                "showing him as Boeing's representative in Case 19-CA-352164 — filed twelve months before the "
                "hearing — was publicly available at the time. Sen. Hawley's opposition to a nominee from his "
                "own party's president, on grounds of that nominee's corporate ties, was significant enough "
                "to narrow the committee vote to 12-11 and require a second vote attempt [Finding #5431].</p>"
                "\n\n"
                "<p>His August 28, 2025 ethics agreement (OGE-filed) contains five commitments: resignation "
                "from the Boeing Chief Labor Counsel role; forfeiture of unvested RSUs; divestiture of all "
                "Boeing stock within 90 days of confirmation (deadline approximately March 18, 2026); "
                "non-participation in Boeing matters until divestiture is complete absent a written waiver "
                "under 18 USC 208(b)(1); and a 2-year cooling period under 5 CFR 2635.503 running from each "
                "RSU vesting date [Finding #5425]. The rolling nature of RSU vesting schedules means specific "
                "recusal end-dates are unknown without access to his full vesting calendar, and the obligations "
                "potentially extend to 2027–2028 [Finding #5433].</p>"
                "\n\n"
                "<p>As of March 2026, the NLRB's Board Member Recusal Lists page shows only a July 2024 "
                "recusal list for member David Prouty [Finding #5425] [Finding #5433]. No recusal list for "
                "Mayer has been published, despite the NLRB's own 2019 Ethics Recusal Report establishing "
                "publication as the standard practice for all Board members. Weekly NLRB decision summaries "
                "show Mayer's name on all published decisions since January 7, 2026, but without a public "
                "recusal list, which cases he has recused from — and on what basis — cannot be verified "
                "externally [Finding #5433].</p>"
            ),
            "viz": "timeline",
        },
    ],

    "open_questions": [
        "Has Mayer completed the Boeing stock divestiture required by his ethics agreement by the March 18, 2026 deadline, and has the NLRB's Designated Agency Ethics Official confirmed compliance?",
        "Which specific NLRB cases or matters has Mayer recused from since January 7, 2026, and on what legal basis — and why has the Board not published a recusal list given the 2019 Ethics Recusal Report standard?",
        "Do Mayer's unvested RSU vesting schedules create rolling recusal obligations extending into 2027 or 2028, and if so, for which categories of cases?",
        "At the October 1, 2025 Senate hearing, Mayer testified he was 'not serving as a representative to the company at the hearing.' Did his role as listed attorney of record in NLRB Case 19-CA-352164 remain active at that date, and was this disclosed to the committee?",
        "Does the Boeing government placement pattern — Mayer at NLRB, McMaster at FHWA/DOT, Guerra-Young at DOT, Benczkowski managing Boeing's DOJ and DOT relationships — reflect a coordinated government relations strategy, and what internal Boeing records document the placement decisions?",
        "What is the full vesting schedule for Mayer's Boeing RSUs, and when does the last 2-year cooling period under 5 CFR 2635.503 expire?",
    ],

    "applicable_models": [
        "revolving-door",
        "regulatory-capture",
        "enabler-gradient",
        "narrative-shield",
    ],
}


def main():
    with open(DOSSIER_PATH) as f:
        dossier = json.load(f)

    existing_curation = dossier.get("curation", {})

    # Preserve fields we are not overwriting
    for key, value in CURATION.items():
        existing_curation[key] = value

    dossier["curation"] = existing_curation

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  lead: {len(CURATION['lead'])} chars")
    print(f"  sections: {len(CURATION['sections'])}")
    print(f"  open_questions: {len(CURATION['open_questions'])}")
    print(f"  applicable_models: {CURATION['applicable_models']}")


if __name__ == "__main__":
    main()
