#!/usr/bin/env python3
"""Curate the Michael Russo dossier with lead, system_role, sections, open_questions, applicable_models."""

import json
from datetime import datetime, timezone

DOSSIER_PATH = "content/dossiers/michael-russo.json"

LEAD = (
    "<p>Michael Russo is a technology executive who spent the bulk of his career in hospitality and retail "
    "payment systems before becoming Chief Information Officer of the Social Security Administration on "
    "January 30, 2025 — appointed directly by Frank Bisignano, a payment-industry veteran of twenty years' "
    "acquaintance who had just been nominated as SSA Commissioner. [Finding #6463] Russo held the CIO title "
    "through late March 2025, then transitioned to a special advisor role focused on technology modernization. "
    "On June 25, 2025, while still inside the agency in that advisory capacity, he signed the written authorization "
    "that allowed DOGE-aligned staffer John Solly to upload a full production copy of the NUMIDENT database to "
    "a test cloud environment that lacked independent security controls. [Finding #6398] The NUMIDENT is the SSA "
    "master file linking Social Security numbers to birth records, citizenship status, race and ethnicity, and "
    "parents' names and Social Security numbers for over 300 million Americans. [Finding #6466]</p>"
    "<p>Russo's prior employer of six-plus years was Shift4 Payments, where he served as Chief Technology Officer. "
    "Shift4 processes payments for Starlink, Elon Musk's satellite internet company. Shift4's CEO, Jared Isaacman, "
    "was nominated as NASA administrator the same period Russo joined SSA. [Finding #6464] Russo's authorization "
    "of the NUMIDENT transfer was issued nine days after SSA's own internal risk assessment determined the "
    "probability of a catastrophic data breach at 35–65 percent. [Finding #6395] He is a named defendant in "
    "federal litigation arising from that authorization. [Finding #6464]</p>"
)

SYSTEM_ROLE = (
    "Technology executive appointed SSA Chief Information Officer in January 2025 through a personal referral "
    "from SSA Commissioner nominee Frank Bisignano; subsequently authorized transfer of the NUMIDENT database "
    "to an unsecured cloud environment in June 2025 despite an internal risk assessment flagging high probability "
    "of catastrophic breach."
)

SECTIONS = [
    {
        "id": "background-and-career",
        "title": "Background and Career",
        "content": (
            "<p>Russo holds a Bachelor of Science in Chemical Engineering from California State University Long "
            "Beach. In 1994 he co-founded a healthcare software company that he sold in 2000, after which he "
            "held CTO positions at Artromick International and Prematics Inc. He then spent over seven years as "
            "CTO of MICROS Systems, a hospitality and retail technology vendor, continuing in that role after "
            "Oracle acquired MICROS and rebranded the division as Oracle Hospitality. [Finding #6463]</p>"
            "<p>In 2018 Russo joined Shift4 Payments as Chief Technology Officer. Shift4, headquartered in "
            "Pennsylvania, is a payment processing company that counts Starlink among its commercial clients — "
            "Shift4 processes Starlink's subscription payments. Russo served as CTO through approximately early "
            "2025, transitioning to a part-time senior technical advisor role before leaving. Shift4's CEO "
            "during this period was Jared Isaacman, who was nominated by the Trump administration as NASA "
            "administrator in early 2025. [Finding #6464]</p>"
            "<p>Russo's career was entirely in commercial payments and hospitality IT before his federal "
            "appointment. He had no prior government service on record.</p>"
        ),
    },
    {
        "id": "appointment-and-network",
        "title": "Appointment and Network",
        "content": (
            "<p>On January 30, 2025, Russo was appointed SSA Chief Information Officer. The appointment was "
            "made personally by <a href='/dossiers/frank-bisignano'>Frank Bisignano</a>, who had been nominated "
            "as SSA Commissioner and was simultaneously serving as acting head of the agency. Bisignano "
            "described a twenty-year industry friendship with Russo, both having circulated in the payments and "
            "financial technology sector. [Finding #6463] The appointment did not follow a competitive selection "
            "process or standard career-track vetting; it was a direct placement by the incoming commissioner "
            "into the agency's top technology role. [Connection #3268]</p>"
            "<p>The network surrounding Russo's appointment creates a triangle of overlapping interests. "
            "Bisignano, whose prior role was CEO of Fiserv, brought Russo — his CTO counterpart from the "
            "payments world — into SSA. At the same time, Russo's most recent employer, Shift4, processed "
            "payments for Starlink, a company controlled by <a href='/dossiers/elon-musk'>Elon Musk</a>, "
            "who simultaneously headed DOGE — the structure that was directing technology access operations "
            "at SSA. [Finding #6464] [Connection #3266] Shift4's CEO Jared Isaacman was nominated to run NASA "
            "in the same government. These were not incidental overlaps; they were concurrent roles held by "
            "people with direct financial relationships to one another.</p>"
            "<p>At SSA, Russo's conduct was described as 'evasive' in congressional testimony regarding DOGE "
            "access arrangements, and he was reported to have advocated for DOGE personnel to receive access "
            "to 'everything including source code.' Witnesses characterized him as reporting operationally "
            "to DOGE rather than to SSA's acting commissioner. [Finding #6464]</p>"
        ),
    },
    {
        "id": "numident-authorization",
        "title": "NUMIDENT Authorization",
        "content": (
            "<p>The NUMIDENT is the SSA master record file. It contains Social Security card application data "
            "for all Americans who have ever received a Social Security number: names, dates and places of "
            "birth, citizenship status, race and ethnicity, parents' names, and parents' Social Security "
            "numbers. The database covers over 300 million living Americans, with additional records for "
            "deceased persons bringing the total SSN count to over 548 million. [Finding #6466]</p>"
            "<p>On June 10–11, 2025, DOGE-aligned SSA CIO office staffer "
            "<a href='/dossiers/aram-moghaddassi'>John Solly</a> formally requested that a copy of the "
            "NUMIDENT production database be migrated to a private cloud environment within SSA's Amazon Web "
            "Services infrastructure. [Finding #6422] On June 16, 2025, SSA's internal Risk Assessment Form "
            "determined the probability of a data breach with 'catastrophic adverse effect' at 35–65 percent. "
            "[Finding #6395] Career cybersecurity officials within SSA raised formal objections. [Finding #6398]</p>"
            "<p>On June 25, 2025 — nine days after the adverse risk assessment was issued — Russo signed the "
            "written authorization allowing Solly to proceed with the upload. The destination cloud environment "
            "lacked independent security controls and bypassed SSA's standard security protocols. A full "
            "production copy of the NUMIDENT was transferred to the unsecured AWS test environment that day. "
            "[Finding #6466] [Finding #6398]</p>"
            "<p>The Senate HSGAC Minority Staff Report (Peters Report, released September 26, 2025) "
            "documents this authorization chain through internal SSA records. [Finding #6398] The report "
            "also notes that SSA Commissioner Bisignano subsequently stated publicly that NUMIDENT data had "
            "'not been accessed, leaked, hacked, or shared in any unauthorized fashion' — a statement that "
            "directly conflicts with the internal risk documentation and whistleblower disclosures. "
            "[Finding #6425]</p>"
            "<p>On July 25, 2025, <a href='/dossiers/aram-moghaddassi'>Aram Moghaddassi</a> — who had "
            "succeeded Russo as SSA CIO — issued a Provisional Authorization to Operate for the cloud "
            "environment, explicitly writing that the business need was higher than the security risk. "
            "[Finding #6401] Russo's June 25 authorization was the predicate act that enabled Moghaddassi's "
            "subsequent formal ATO. The Peters Report described the 49-day sequence from the June 6 "
            "Supreme Court ruling lifting the DOGE access ban to the completed upload as operationally "
            "pre-planned rather than reactive. [Finding #6516]</p>"
        ),
    },
    {
        "id": "conflict-of-interest",
        "title": "Conflict of Interest",
        "content": (
            "<p>The documented conflict structure involves three layers. First, Russo was appointed to oversee "
            "SSA's technology systems by a commissioner nominee — Bisignano — who was his longtime industry "
            "peer and who selected him through a personal channel rather than institutional process. "
            "[Finding #6463] Second, Russo's prior employer, Shift4, processed payments for Starlink, the "
            "Musk company whose founder was simultaneously directing DOGE operations at SSA. [Finding #6464] "
            "Third, Russo subsequently authorized a data transfer that DOGE personnel had requested — the "
            "same DOGE structure whose principal's company was Russo's prior business counterpart.</p>"
            "<p>An additional layer involves the Starlink installation at GSA headquarters that occurred "
            "without authorization during the same period. The whistleblower disclosure filed by SSA Chief "
            "Data Officer Charles Borges (August 26, 2025) noted that Russo's prior role at a Starlink "
            "payment processor created a direct conflict with any oversight responsibility for DOGE "
            "operations that included unauthorized Starlink deployments at federal facilities. [Finding #6421]</p>"
            "<p>Russo is a named defendant in federal litigation arising from the NUMIDENT authorization. "
            "[Finding #6464] The suit follows a pattern documented across the DOGE data operations: "
            "DOGE-affiliated CIOs were placed at agencies, questioned by career staff, and then authorized "
            "access that career security officials had flagged as high-risk. The Senate HSGAC report "
            "characterized this as a deliberate institutional pattern across multiple agencies. [Finding #6409]</p>"
        ),
    },
    {
        "id": "key-relationships",
        "title": "Key Relationships",
        "content": (
            "<p><a href='/dossiers/frank-bisignano'>Frank Bisignano</a>: Russo's appointment originator and "
            "a twenty-year industry acquaintance. Bisignano, formerly CEO of Fiserv, was nominated as SSA "
            "Commissioner in January 2025 and personally placed Russo as CIO on January 30. Bisignano's "
            "subsequent public statements denying unauthorized NUMIDENT access directly contradict the "
            "internal SSA risk assessment that Russo received before authorizing the transfer. "
            "[Connection #3268]</p>"
            "<p>John Solly: The DOGE-aligned CIO office staffer whose cloud upload request Russo authorized "
            "on June 25, 2025. Solly joined the SSA CIO office in March 2025 and filed the formal NUMIDENT "
            "cloud copy request on June 10–11. Russo's written authorization was the enabling action for "
            "Solly's transfer of the full production database. [Connection #3243]</p>"
            "<p><a href='/dossiers/aram-moghaddassi'>Aram Moghaddassi</a>: Russo's successor as SSA CIO. "
            "Moghaddassi, a Neuralink and X Corp engineer, was appointed SSA CIO after Russo stepped to "
            "special advisor status in late March 2025. On July 25, 2025, Moghaddassi issued the Provisional "
            "ATO formalizing the cloud environment that Russo had authorized, overriding the CISO's "
            "security objections in a written memo stating business need exceeded security risk. "
            "[Finding #6401]</p>"
            "<p><a href='/dossiers/elon-musk'>Elon Musk</a>: Indirect relationship through two channels. "
            "Russo's employer Shift4 processed Starlink subscription payments, creating a client-side "
            "financial relationship. Musk's DOGE structure was the organizational home of the personnel "
            "whose data access requests Russo authorized at SSA. The relationship is structural rather "
            "than documented as direct personal contact. [Connection #3246] [Connection #3266]</p>"
        ),
    },
]

OPEN_QUESTIONS = [
    (
        "Russo was described as reporting to DOGE rather than to SSA's acting commissioner. What documented "
        "chain of command governed his authorization decisions — was his June 25 NUMIDENT sign-off "
        "reviewed by anyone above him within SSA, or did it flow directly to DOGE?",
    ),
    (
        "Russo transitioned from CIO to 'special advisor on technology modernization' in late March 2025 "
        "while retaining the authority to authorize data transfers in June. What specific authorities and "
        "permissions did that advisory role retain, and who approved that retention?",
    ),
    (
        "Shift4's processing relationship with Starlink is documented. Was Russo required to file a "
        "recusal or financial disclosure covering that relationship when he was appointed SSA CIO, and if "
        "so, what did that disclosure contain?",
    ),
    (
        "The Peters Report characterizes the 49-day NUMIDENT authorization sequence as pre-planned. Were "
        "there any communications between Russo and DOGE-affiliated personnel between June 6 (SCOTUS ruling) "
        "and June 10 (Solly's formal request) that bear on whether the upload was pre-coordinated?",
    ),
    (
        "The federal lawsuit naming Russo as a defendant — what specific legal theory is alleged against "
        "him individually, and has any government ethics referral been made separate from the litigation?",
    ),
]

APPLICABLE_MODELS = [
    "revolving-door",
    "conflict-of-interest",
    "institutional-capture",
    "enabler-gradient",
    "procurement-capture",
]


def main():
    with open(DOSSIER_PATH) as f:
        dossier = json.load(f)

    curation = dossier.get("curation", {})
    curation["lead"] = LEAD
    curation["system_role"] = SYSTEM_ROLE
    curation["sections"] = SECTIONS
    curation["open_questions"] = [q[0] for q in OPEN_QUESTIONS]
    curation["applicable_models"] = APPLICABLE_MODELS
    curation["curated_at"] = datetime.now(timezone.utc).isoformat()

    dossier["curation"] = curation

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  lead length: {len(LEAD)} chars")
    print(f"  sections: {[s['id'] for s in SECTIONS]}")
    print(f"  open_questions: {len(OPEN_QUESTIONS)}")
    print(f"  applicable_models: {APPLICABLE_MODELS}")


if __name__ == "__main__":
    main()
