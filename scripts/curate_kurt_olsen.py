#!/usr/bin/env python3
"""Curation script for Kurt Olsen dossier."""

import json
from datetime import datetime

DOSSIER_PATH = "content/dossiers/kurt-olsen.json"


def build_curation() -> dict:
    lead = (
        "<p>Kurt B. Olsen (b. August 20, 1962) is a product-liability defense attorney who spent his career "
        "outside election law before pivoting abruptly in late 2020 to become one of the principal legal "
        "architects of the effort to overturn the presidential election result. In December 2020, Texas "
        "Attorney General Ken Paxton appointed him special counsel for <em>Texas v. Pennsylvania</em>, the "
        "Supreme Court action seeking to invalidate electoral votes in four states; SCOTUS rejected the case "
        "unanimously for lack of standing [Finding #6567]. After that rejection, Olsen contacted acting "
        "Attorney General <a href=\"/dossiers/jeffrey-rosen\">Jeffrey Rosen</a> by phone to relay Trump's "
        "demand that the DOJ file its own Supreme Court complaint — by noon that day — to nullify electors in "
        "six swing states [Finding #6567]. He spoke with Trump by phone at least twice on the evening of "
        "January 6, 2021, after the Capitol attack [Finding #6567].</p>\n\n"
        "<p>In October 2025 Trump appointed Olsen White House Director of Election Security and Integrity, "
        "in a special government employee capacity. In that role, Olsen drafted the criminal referral to the "
        "Department of Justice that triggered the FBI's January 28, 2026 seizure of approximately 700 boxes "
        "of Fulton County 2020 general election materials — physical ballots, ballot images, tabulator tapes, "
        "and voter rolls. DNI Tulsi Gabbard was personally present at the raid at Trump's direction "
        "[Finding #6531]. The DOJ itself later stated that the affidavit underlying the warrant merely "
        "mentions Olsen's referral as the investigation's origin and does not rely on him as a witness or for "
        "evidence, while Fulton County's legal challenge alleges the FBI agent omitted material facts from "
        "the affidavit. See the <a href=\"/dossiers/fulton-county-ballot-seizure\">Fulton County ballot "
        "seizure</a> dossier for warrant and litigation details [Finding #6568].</p>\n\n"
        "<p>Federal courts have sanctioned Olsen for the litigation he filed along the way: a district court "
        "imposed $122,200 in attorneys' fees under FRCP Rule 11 and 28 U.S.C. § 1927 for frivolous claims "
        "with misleading statements about Arizona voting processes in the Kari Lake / Mark Finchem lawsuit, "
        "a penalty the Ninth Circuit affirmed in March 2025. The Arizona Supreme Court separately sanctioned "
        "Kari Lake's attorneys — Olsen among them — for repeating claims courts had found unequivocally false "
        "[Finding #6566].</p>"
    )

    system_role = (
        "Olsen occupies a specific structural position: a practitioner with no prior election-law experience "
        "who was recruited into the 2020 overturn effort, accumulated a judicial sanctions record across "
        "federal and state courts, and was then installed inside the White House to translate the political "
        "demand for re-examination of the 2020 election into a formal criminal referral — one that bypassed "
        "the civil process DOJ had unsuccessfully pursued for months and escalated directly to a federal "
        "warrant. His role links the original 2020 legal campaign to the 2025-2026 enforcement action, "
        "providing continuity of purpose across administrations."
    )

    sections = [
        {
            "id": "background-and-career",
            "title": "Background and Career",
            "viz": None,
            "finding_ids": [6564],
            "connection_ids": [],
            "prose": (
                "<p>Kurt B. Olsen was born August 20, 1962 and attended the U.S. Naval Academy, graduating "
                "in 1984. He served as a Navy SEAL before transitioning to law. In 2003 he co-founded "
                "Klafter Olsen &amp; Lesser LLP in New York, where his practice concentrated on product "
                "liability defense — client-side corporate litigation with no election-law component "
                "[Finding #6564].</p>\n\n"
                "<p>In 2009 Olsen filed for Chapter 7 bankruptcy in the Northern District of New York "
                "(case 09-11708, terminated 2015). At the time he had never handled an election case "
                "[Finding #6564]. After his election-related work became public in early 2021, his firm "
                "partners removed his name; the entity was renamed Klafter Lesser LLP in February 2021 "
                "[Finding #6564].</p>"
            ),
        },
        {
            "id": "2020-election-overturn-campaign",
            "title": "2020 Election Overturn Campaign",
            "viz": None,
            "finding_ids": [6567, 6566],
            "connection_ids": [3317, 3318],
            "prose": (
                "<p>Olsen's entry into election litigation was through Ken Paxton's office. In December 2020 "
                "Paxton appointed him special counsel for <em>Texas v. Pennsylvania</em>, the Supreme Court "
                "original-jurisdiction action in which Texas sought to invalidate electoral votes in "
                "Pennsylvania, Georgia, Michigan, and Wisconsin. The Court rejected the case 9–0 on standing "
                "grounds without reaching the merits [Finding #6567].</p>\n\n"
                "<p>The day of that rejection, Olsen called acting Attorney General "
                "<a href=\"/dossiers/jeffrey-rosen\">Jeffrey Rosen</a> to relay Trump's demand that DOJ file "
                "its own Supreme Court complaint to nullify electors in six swing states — by noon. Rosen "
                "declined [Finding #6567]. Senate Judiciary Committee investigators documented this exchange "
                "as part of the wider pressure campaign on DOJ leadership in late December 2020 and early "
                "January 2021.</p>\n\n"
                "<p>In parallel, Olsen represented Kari Lake and Mark Finchem in a federal lawsuit "
                "challenging electronic voting equipment in Arizona filed in April 2022. A district court "
                "found the claims frivolous, imposed $122,200 in attorneys' fees against Olsen and co-counsel "
                "under FRCP Rule 11 and 28 U.S.C. § 1927 for misleading statements about Arizona voting "
                "processes, and the Ninth Circuit affirmed that penalty in March 2025. The Arizona Supreme "
                "Court separately sanctioned the Lake legal team for repeating claims that courts had found "
                "unequivocally false [Finding #6566]. Ethics complaints regarding this conduct were filed by "
                "the Lawyers Defending American Democracy (LDAD) and the States United Democracy Center "
                "[Finding #6566].</p>\n\n"
                "<p>Olsen also testified as a defense witness for John Eastman, the attorney who drafted the "
                "legal theory for Vice President Pence to reject certified electors, in Eastman's subsequent "
                "bar disciplinary proceedings [Finding #6567]. He maintained ties to Mike Lindell's election "
                "denial network during this period [Connection #3316].</p>"
            ),
        },
        {
            "id": "january-6-communications",
            "title": "January 6, 2021 Communications",
            "viz": None,
            "finding_ids": [6567],
            "connection_ids": [3314],
            "prose": (
                "<p>On the evening of January 6, 2021, after the Capitol attack, Olsen spoke with Trump by "
                "phone at least twice. The January 6 Committee documented those calls. The content of the "
                "conversations has not been publicly disclosed in full, but their occurrence places Olsen "
                "among the small number of outside attorneys in direct phone contact with Trump on that "
                "evening [Finding #6567].</p>"
            ),
        },
        {
            "id": "white-house-role-and-fulton-county",
            "title": "White House Role and Fulton County Ballot Seizure",
            "viz": None,
            "finding_ids": [6526, 6531],
            "connection_ids": [3291, 3314, 3294],
            "prose": (
                "<p>In October 2025 Trump appointed Olsen as White House Director of Election Security and "
                "Integrity in a special government employee capacity. Ed Martin, who chaired the DOJ's "
                "Weaponization Working Group under Attorney General Pam Bondi, stated publicly on the War "
                "Room podcast in January 2026 that he was working with Olsen on election integrity "
                "[Connection #3294].</p>\n\n"
                "<p>Olsen drafted the criminal referral to the Department of Justice that became the "
                "predicate for the FBI's January 28, 2026 search of the Fulton County Election Hub and "
                "Operations Center in Union City, Georgia. The warrant, approved by Magistrate Judge "
                "Catherine M. Salinas on a 22-page affidavit by FBI Special Agent Hugh Raymond Evans, "
                "authorized seizure of approximately 700 boxes of 2020 General Election materials — physical "
                "ballots, ballot images, tabulator tapes, and voter rolls — under 52 U.S.C. §§ 20701 and "
                "20511 [Finding #6531]. Full warrant details are in the "
                "<a href=\"/dossiers/fulton-county-ballot-seizure\">Fulton County ballot seizure</a> "
                "dossier.</p>\n\n"
                "<p>DNI Tulsi Gabbard accompanied FBI Deputy Director Bailey and Atlanta Acting SAC Pete "
                "Ellis to observe the raid, at Trump's personal direction. Gabbard facilitated a "
                "speakerphone call allowing Trump to address FBI agents during or after the operation "
                "[Connection #3291]. The DOJ subsequently stated that the affidavit merely notes Olsen's "
                "referral as the investigation's origin and does not rely on him as a witness or for "
                "substantive evidence — a clarification that distances the department from the referral's "
                "author even while executing the search it generated.</p>\n\n"
                "<p>The Fulton County seizure was preceded by months of unsuccessful civil proceedings in "
                "which DOJ sought the same materials and was rebuffed by courts; the criminal warrant "
                "represented an escalation from civil to criminal process after those attempts failed "
                "[Finding #6526].</p>"
            ),
        },
        {
            "id": "key-relationships",
            "title": "Key Relationships",
            "viz": "ego_network",
            "finding_ids": [],
            "connection_ids": [3314, 3291, 3315, 3317, 3318, 3316, 3294],
            "prose": (
                "<p><strong>Donald Trump</strong> — Olsen has been in direct contact with Trump at multiple "
                "critical junctures: through the Texas v. Pennsylvania case, during the post-SCOTUS-rejection "
                "DOJ pressure campaign, by phone on the evening of January 6, 2021, and as a White House "
                "appointee in 2025–2026. Trump personally directed Gabbard's presence at the FBI raid that "
                "Olsen's referral triggered [Connection #3314].</p>\n\n"
                "<p><strong>Tulsi Gabbard</strong> (DNI) — Olsen's criminal referral from within the White "
                "House produced the direct operational result of Gabbard's personal attendance at the Fulton "
                "County raid. The two operate in overlapping lanes — Olsen through the White House office, "
                "Gabbard through ODNI — on election-related enforcement [Connections #3291, #3315].</p>\n\n"
                "<p><strong>Ken Paxton</strong> — Paxton's appointment of Olsen as Texas special counsel in "
                "December 2020 was Olsen's entry point into high-profile election litigation. Without that "
                "appointment, Olsen would have had no platform from which to contact Rosen or develop the "
                "profile that led to his White House role [Connection #3317].</p>\n\n"
                "<p><strong>Kari Lake</strong> — Olsen served as Lake's attorney in the Arizona electronic "
                "voting equipment lawsuit; both were sanctioned for filings courts found frivolous and false "
                "[Connection #3318].</p>\n\n"
                "<p><strong>Mike Lindell</strong> — LittleSis documentation identifies Olsen within "
                "Lindell's election-denial attorney network. The nature and depth of the operational "
                "relationship beyond shared litigation posture is not fully documented [Connection #3316].</p>\n\n"
                "<p><strong>Ed Martin</strong> (Weaponization Working Group, DOJ) — Martin's January 2026 "
                "War Room podcast statement that he was working with Olsen on election integrity establishes "
                "a direct coordination channel between Olsen's White House office and the DOJ working group "
                "Bondi established to address perceived weaponization of government [Connection #3294].</p>\n\n"
                "<p><strong><a href=\"/dossiers/jeffrey-rosen\">Jeffrey Rosen</a></strong> — Olsen's call "
                "to Rosen in December 2020, relaying Trump's demand for an emergency Supreme Court filing, "
                "placed Rosen in the position of explicitly declining a presidential directive conveyed "
                "through an outside attorney. Rosen's documented refusals across multiple pressure vectors "
                "are central to the January 6 Senate investigation record.</p>"
            ),
        },
    ]

    open_questions = [
        (
            "What communications — emails, memos, calls — exist between Olsen and White House counsel, "
            "DOJ leadership, or the FBI between October 2025 and January 28, 2026 documenting how the "
            "criminal referral was drafted, reviewed, and transmitted, and who at DOJ accepted it?"
        ),
        (
            "The DOJ statement that the FBI affidavit does not rely on Olsen as a witness or for evidence "
            "raises the question of which of the 11 cited witnesses Olsen identified or vetted in preparing "
            "his referral, and whether Olsen knew about Key Witness 7's (Kevin Moncla's) 2023 FBI referral "
            "for threatening state election officials before including material from his claims."
        ),
        (
            "What is the scope of Olsen's special government employee appointment — specifically, what "
            "access credentials, clearances, and authorities attach to the White House Director of Election "
            "Security title, and whether that role has a statutory or executive order basis?"
        ),
        (
            "What other criminal referrals, if any, has Olsen drafted or initiated from his White House "
            "office targeting election officials or materials in states other than Georgia?"
        ),
        (
            "The full record of Olsen's communications with Trump on the evening of January 6, 2021 "
            "has not been publicly disclosed. What did those calls cover, and were they documented in "
            "White House call logs?"
        ),
        (
            "Are there bar disciplinary proceedings pending against Olsen in any jurisdiction arising "
            "from the LDAD and States United Democracy Center ethics complaints, beyond the federal "
            "sanctions that have already been affirmed?"
        ),
    ]

    applicable_models = [
        "revolving-door",
        "legal-shield",
        "accountability-gap",
        "procurement-capture",
    ]

    return {
        "lead": lead,
        "system_role": system_role,
        "sections": sections,
        "open_questions": open_questions,
        "applicable_models": applicable_models,
        "curated_at": datetime.utcnow().isoformat(),
    }


def main():
    with open(DOSSIER_PATH) as f:
        dossier = json.load(f)

    existing_curation = dossier.get("curation", {})

    new_curation = build_curation()

    # Preserve structural fields from existing curation
    for key in ("key_finding_ids", "key_identifiers", "section_suggestions"):
        if key in existing_curation:
            new_curation[key] = existing_curation[key]

    dossier["curation"] = new_curation

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Curation written to {DOSSIER_PATH}")
    print(f"  lead: {len(new_curation['lead'])} chars")
    print(f"  system_role: {len(new_curation['system_role'])} chars")
    print(f"  sections: {len(new_curation['sections'])}")
    print(f"  open_questions: {len(new_curation['open_questions'])}")
    print(f"  applicable_models: {new_curation['applicable_models']}")


if __name__ == "__main__":
    main()
