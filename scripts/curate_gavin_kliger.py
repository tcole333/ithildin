#!/usr/bin/env python3
"""Curation script for Gavin Kliger dossier."""

import json
from datetime import datetime, timezone

DOSSIER_PATH = "content/dossiers/gavin-kliger.json"

LEAD = """<p>Gavin Kliger is a software engineer from <a href="/dossiers/doge">DOGE</a> who, starting January 20, 2025, held concurrent Senior Adviser roles across at least eight federal agencies — OPM, CFPB, USAID, USDA, NIH, IRS, FTC, and Voice of America — while remaining listed as an active employee of Databricks AI [Finding #5517] [Finding #5986]. He was 25 years old at the time of deployment. His OGE Form 278 public financial disclosure shows Databricks vested stock units valued at $1&nbsp;million–$5&nbsp;million, a Databricks salary and bonus of $251,000, and an employment agreement listed as still current as of the disclosure date [Finding #5733]. He also disclosed Bitcoin holdings of $100,000–$250,000 via Robinhood, Solana of $1,000–$15,000, Tesla stock of $50,000–$100,000, Apple stock of $100,000–$250,000, and Robinhood Markets equity of $50,000–$100,000, among other positions [Finding #5733] [Finding #5768].</p>
<p>At the CFPB, ethics attorneys warned Kliger in writing that he held up to $715,000 in equities that bureau employees are legally prohibited from owning, and that he could not participate in agency actions affecting those holdings. Days later he managed the reduction-in-force that terminated approximately 1,400 of the agency's 1,700 staff — roughly 90 percent of the workforce. A former CFPB general counsel characterized the episode as a likely violation of the federal criminal conflict-of-interest statute [Finding #5783]. Court declarations filed in subsequent litigation described Kliger keeping staff awake through a 36-hour marathon to ensure the termination notices issued on schedule [Finding #5758]. He departed CFPB on May 8, 2025.</p>"""

SYSTEM_ROLE = (
    "Kliger occupied a functional position as a concurrent multi-agency access point: "
    "a single private-sector employee with no prior government experience given simultaneous "
    "credentials at eight agencies spanning financial regulation, workforce administration, "
    "tax enforcement, foreign aid, and broadcasting — while retaining equity and employment "
    "ties to a company that competes for federal data-analytics contracts at those same agencies."
)

SECTIONS = [
    {
        "id": "background-and-deployment",
        "title": "Background and Deployment",
        "body": (
            "<p>Kliger attended UC Berkeley but left without completing a degree. "
            "His FEC record shows a single $94 WinRed donation in July 2024 from "
            "Dove Canyon, California, listing his employer as Brainstorm — his only "
            "documented political contribution before the DOGE deployment [Finding #5517]. "
            "He joined Databricks as a Senior Software Engineer in May 2020 and was "
            "still listed under that employment agreement on his OGE disclosure filed "
            "after taking government roles [Finding #5733].</p>"
            "<p>On January 20, 2025, Kliger was formally appointed Senior Advisor to the "
            "Director for Technology and Delivery at OPM. He was simultaneously detailed "
            "to USDA, CFPB, USAID, and sought access at the IRS — court filings across "
            "multiple cases confirmed these concurrent positions [Finding #5784]. "
            "At <a href='/dossiers/doge'>DOGE</a>, he was part of a cohort of young "
            "engineers — predominantly from elite California university programs or "
            "Musk-affiliated companies — given A-suite GSA clearances with limited vetting "
            "[Finding #5304]. Investigators and journalists identified him as one of the "
            "most widely deployed DOGE operatives by agency count [Finding #5517].</p>"
        ),
        "finding_ids": [5517, 5733, 5784, 5304],
        "connection_ids": [2958],
    },
    {
        "id": "financial-disclosures-and-conflicts",
        "title": "Financial Disclosures and Conflicts of Interest",
        "body": (
            "<p>Kliger's OGE Form 278 disclosure — document ID 1987 in the ProPublica "
            "database — is the primary financial record of his holdings at the time of "
            "government service. The disclosure shows Databricks RSUs valued at "
            "$1&nbsp;million–$5&nbsp;million and a salary and bonus of $251,000, with "
            "the employment agreement listed as Present (May 2020–Present), leaving open "
            "whether a formal separation from Databricks occurred before or during his "
            "federal service [Finding #5733].</p>"
            "<p>His equity portfolio at OPM included holdings in companies directly "
            "regulated by or contracting with the agencies he served: Tesla ($50K–$100K) "
            "at an agency where Tesla's labor practices had drawn NLRB attention; "
            "Apple ($100K–$250K) and Alphabet ($50K–$100K) at agencies overseeing consumer "
            "technology; Robinhood Markets ($50K–$100K) at an agency with jurisdiction over "
            "financial products Robinhood was expanding into; and crypto assets (Bitcoin "
            "$100K–$250K, Solana $1K–$15K) on a platform whose equity he also held "
            "[Finding #5768]. He was one of at least four DOGE-linked appointees with "
            "cryptocurrency or crypto-company equity holdings at agencies with regulatory "
            "authority over those assets [Finding #5760].</p>"
            "<p>At CFPB, the conflict was legally acute. Bureau employees are subject to "
            "an agency-specific ethics rule prohibiting ownership of equity in firms the "
            "CFPB regulates. Ethics attorneys warned Kliger in writing that his holdings "
            "— valued up to $715,000 in CFPB-regulated companies — disqualified him from "
            "participating in agency actions affecting those companies. He proceeded to "
            "oversee the mass layoff of approximately 1,400 employees, an action a "
            "former CFPB general counsel characterized as a likely violation of 18 U.S.C. "
            "§ 208, the federal criminal conflict-of-interest statute [Finding #5783] "
            "[Finding #5501].</p>"
        ),
        "finding_ids": [5733, 5768, 5760, 5783, 5501],
        "connection_ids": [],
    },
    {
        "id": "cfpb-operations",
        "title": "CFPB Mass Layoff Operations",
        "body": (
            "<p>Kliger entered USAID alongside Jeremy Lewin and Pete Marocco as part of "
            "the initial DOGE deployment wave [Finding #5501]. His most extensively "
            "documented operational role was at the CFPB, where court declarations "
            "described a 36-hour RIF process he personally managed. An anonymous CFPB "
            "staffer declaration filed in the agency's subsequent litigation stated that "
            "'Gavin was screaming at people' to keep the termination timeline on schedule. "
            "The operation cut approximately 1,400 of 1,700 CFPB employees — roughly "
            "90 percent of the workforce — in a single action [Finding #5758].</p>"
            "<p>The Revolving Door Project profiled Kliger as an illustrative case of the "
            "DOGE conflict-of-interest pattern: a young private-sector engineer with "
            "financial interests in regulated companies placed at the agency regulating "
            "those companies, receiving ethics warnings, and proceeding with consequential "
            "agency actions regardless [Finding #5501]. Kliger departed CFPB on "
            "May 8, 2025 [Finding #5986].</p>"
        ),
        "finding_ids": [5758, 5501, 5986],
        "connection_ids": [2958],
    },
    {
        "id": "opm-and-system-access",
        "title": "OPM, IRS, and Federal Data System Access",
        "body": (
            "<p>As Senior Advisor to the OPM Director, Kliger was positioned at the "
            "agency that controls personnel records for the entire federal workforce — "
            "employment histories, SF-86 security clearance questionnaires, medical "
            "records, bank account information, and biometric data. "
            "<a href='/dossiers/scott-kupor'>Scott Kupor</a> (a16z Managing Partner, "
            "appointed OPM Director) and Amanda Scales (xAI Recruiting Lead, appointed "
            "OPM Chief of Staff) were simultaneously placed at the same agency, "
            "concentrating Silicon Valley-aligned personnel at OPM's leadership level "
            "[Finding #5754].</p>"
            "<p>In February 2025, Kliger arrived at IRS headquarters, placed five "
            "government-issued laptops on a table, and requested a sixth for IRS Integrated "
            "Data Retrieval System access — a system containing criminal investigation "
            "files, taxpayer returns, and accounts for approximately 150 million filers. "
            "He made this request while simultaneously holding OPM, USDA, and CFPB "
            "positions [Finding #5480]. Treasury ultimately negotiated a restriction "
            "limiting DOGE representatives to anonymized IRS data, blocking individual "
            "return access. <a href='/dossiers/doge'>DOGE</a> subsequently organized a "
            "'hackathon' to build a centralized 'mega API' aggregating data across "
            "agencies, with <a href='/dossiers/palantir-technologies'>Palantir</a> "
            "reportedly involved [Finding #5480].</p>"
            "<p>In June 2025, U.S. District Judge Denise Cote found that OPM 'violated "
            "the law and bypassed established cybersecurity practices' in granting DOGE "
            "access to federal personnel databases. That injunction was subsequently "
            "reversed by the appeals court in August 2025 [Finding #5474].</p>"
        ),
        "finding_ids": [5754, 5480, 5474],
        "connection_ids": [2958],
    },
]

OPEN_QUESTIONS = [
    (
        "Kliger's OGE Form 278 lists Databricks employment as 'Present' through the disclosure date. "
        "Did a formal employment separation occur before his January 20, 2025 appointment, "
        "and if so, on what date, and does he retain any unvested equity or deferred compensation "
        "that creates ongoing alignment with Databricks performance? [Finding #5733]"
    ),
    (
        "Did the CFPB ethics attorneys' written warning — and Kliger's subsequent participation "
        "in the RIF despite that warning — result in a criminal referral under 18 U.S.C. § 208, "
        "and if not, which official had authority to authorize a conflict waiver and whether "
        "one was issued? [Finding #5783]"
    ),
    (
        "What specific systems at the IRS did Kliger access with the government-issued laptops "
        "he brought to IRS headquarters in February 2025, and was a formal IDRS access credential "
        "ultimately granted? [Finding #5480]"
    ),
    (
        "Kliger's FEC record lists his pre-DOGE employer as 'Brainstorm' rather than Databricks. "
        "What is Brainstorm, and does it represent a separate entity or project within "
        "Kliger's professional history that predates the Databricks role? [Finding #5517]"
    ),
    (
        "Court filings document Kliger holding simultaneous positions at OPM, USDA, CFPB, and USAID. "
        "Which agency's ethics office, if any, served as his primary ethics counsel, "
        "and did any of the four agencies independently assess the conflicts created by "
        "his concurrent placement at the others? [Finding #5784]"
    ),
]

APPLICABLE_MODELS = [
    "regulatory-capture",
    "revolving-door",
    "access-capitalism",
    "enabler-gradient",
]


def main():
    with open(DOSSIER_PATH, "r") as f:
        dossier = json.load(f)

    curation = dossier.get("curation", {})

    # Build the sections list in the expected schema
    sections_out = []
    for s in SECTIONS:
        sections_out.append(
            {
                "id": s["id"],
                "title": s["title"],
                "body": s["body"],
                "finding_ids": s["finding_ids"],
                "connection_ids": s["connection_ids"],
            }
        )

    curation["lead"] = LEAD
    curation["system_role"] = SYSTEM_ROLE
    curation["sections"] = sections_out
    curation["open_questions"] = OPEN_QUESTIONS
    curation["applicable_models"] = APPLICABLE_MODELS
    curation["curated_at"] = datetime.now(timezone.utc).isoformat()

    dossier["curation"] = curation

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  lead: {len(LEAD)} chars")
    print(f"  system_role: {len(SYSTEM_ROLE)} chars")
    print(f"  sections: {len(sections_out)}")
    print(f"  open_questions: {len(OPEN_QUESTIONS)}")
    print(f"  applicable_models: {APPLICABLE_MODELS}")


if __name__ == "__main__":
    main()
