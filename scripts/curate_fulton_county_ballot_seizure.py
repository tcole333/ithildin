#!/usr/bin/env python3
"""
Curate dossier: Fulton County ballot seizure
Writes curation fields: lead, system_role, sections, open_questions, applicable_models
"""

import json
from pathlib import Path

DOSSIER_PATH = Path(__file__).parent.parent / "content" / "dossiers" / "fulton-county-ballot-seizure.json"

CURATION = {
    "lead": (
        "<p>On January 28, 2026, FBI special agents executed a federal search warrant at the Fulton County "
        "Election Hub and Operations Center in Union City, Georgia, seizing approximately 700 boxes of "
        "physical ballots, ballot images, tabulator tapes, and voter rolls from the 2020 General Election "
        "[Finding #6568]. The warrant was authorized by Magistrate Judge Catherine M. Salinas on a "
        "22-page affidavit by FBI Special Agent Hugh Raymond Evans, citing 52 U.S.C. \u00a7\u00a7 20701 and 20511 "
        "\u2014 federal statutes governing election record retention and voting law violations. The docket is "
        "assigned to Judge J.P. Boulee (N.D. Ga.), a 2019 Trump appointee, under case reference "
        "Gov.uscourts.gand.355087 [Finding #6568].</p>"
        "\n\n"
        "<p>The investigation originated from a criminal referral drafted by "
        "<a href=\"/dossiers/kurt-olsen\">Kurt Olsen</a>, White House Director of Election Security and "
        "Integrity since October 2025 [Finding #6568]. According to records reviewed across multiple news "
        "accounts, Director of National Intelligence Tulsi Gabbard traveled to Georgia and was physically "
        "present during the raid at Trump\u2019s personal direction [Finding #6569].</p>"
        "\n\n"
        "<p>Fulton County filed suit on February 4, 2026 seeking return of the seized materials, arguing "
        "a Fourth Amendment violation on the grounds that the affidavit established only possible cause "
        "rather than probable cause [Finding #6572]. Judge Boulee ordered mediation on February 26, 2026, "
        "with an outcome due by March 18, 2026 [Finding #6572].</p>"
    ),

    "system_role": (
        "The Fulton County ballot seizure traces how a White House-directed criminal referral, "
        "processed through DOJ and executed with DNI participation, converted a years-long civil records "
        "dispute into a federal criminal seizure after civil litigation had repeatedly failed to compel "
        "production of the same materials."
    ),

    "sections": [
        {
            "id": "warrant-and-chain-of-command",
            "title": "The Warrant and Its Chain of Command",
            "content": (
                "<p>The search warrant was the culmination of a process that began in the White House, "
                "not the FBI. Kurt Olsen, appointed White House Director of Election Security and Integrity "
                "in October 2025, drafted the criminal referral that DOJ used to open the investigation "
                "[Finding #6568]. Olsen\u2019s background is in product liability defense: he co-founded "
                "Klafter Olsen and Lesser LLP in 2003 in New York, specialized in product liability, "
                "filed for personal bankruptcy in 2009, and had never worked in election law before 2020. "
                "His law firm removed his name and renamed itself in February 2021 following his election "
                "denial activities [Finding #6564; <a href=\"/dossiers/kurt-olsen\">Kurt Olsen</a>]. "
                "His 2020\u20132021 activities included advising Texas AG Ken Paxton on the Texas v. Pennsylvania "
                "case that the Supreme Court unanimously rejected for lack of standing, telephoning acting AG "
                "<a href=\"/dossiers/jeffrey-rosen\">Jeffrey Rosen</a> to demand DOJ file a Supreme Court "
                "complaint to invalidate electors in six swing states, and speaking with Trump by phone at "
                "least twice on January 6, 2021 after the Capitol attack [Finding #6567]. He was sanctioned "
                "USD 122,200 in attorneys\u2019 fees by a federal district court under FRCP Rule 11 for filing "
                "frivolous election claims in the Kari Lake lawsuit, affirmed by the Ninth Circuit in "
                "March 2025 [Finding #6566].</p>"
                "\n\n"
                "<p>After DOJ opened the investigation based on Olsen\u2019s referral, FBI Special Agent "
                "Hugh Raymond Evans prepared the 22-page affidavit citing 11 witnesses and presented it "
                "to Magistrate Judge Catherine Salinas, who approved the warrant. According to a synthesis "
                "of multiple news accounts, the affidavit cited federal statutes 52 USC \u00a7\u00a7 20701 "
                "and 20511, governing election record retention obligations and prohibiting deprivation of "
                "rights secured by federal election laws [Finding #6569]. According to DOJ\u2019s own "
                "subsequent statements, the affidavit merely noted the investigation originated from "
                "Olsen\u2019s referral and did not rely on him as a witness or as a source of evidence "
                "[Finding #6575].</p>"
                "\n\n"
                "<p>Records indicate that DNI Gabbard\u2019s participation was directed by Trump personally; "
                "she accompanied FBI Deputy Director Bailey and Atlanta Acting SAC Pete Ellis to the "
                "facility [Finding #6569]. According to news accounts, Trump\u2019s own explanation for "
                "her presence shifted: he first asserted he directed it, then later claimed that AG Pam "
                "Bondi had insisted on Gabbard providing oversight [Finding #6569]. Gabbard\u2019s claimed "
                "statutory basis was that 50 U.S.C. \u00a7 3024 grants the DNI authority to coordinate, "
                "integrate, and analyze intelligence related to election security, including "
                "counterintelligence and foreign and other malign influences. Former senior intelligence "
                "officials and Senator Mark Warner publicly disputed this reading, noting that the statute "
                "explicitly ties the DNI\u2019s election security authority to risks posed by <em>foreign</em> "
                "entities, not to domestic search warrant execution [Finding #6570]. Gabbard had separately "
                "announced an ODNI investigation of electronic voting machine vulnerabilities in April 2025, "
                "including physical seizure and testing of Puerto Rico voting machines in May 2025, where no "
                "evidence of foreign interference was found [Finding #6532].</p>"
                "\n\n"
                "<p>Olsen was simultaneously working with Ed Martin\u2019s DOJ Weaponization Working Group "
                "[Finding #6531]. Martin, who was installed as interim U.S. Attorney for the District "
                "of Columbia in January 2025 without prior prosecutorial or judicial experience, led the "
                "Weaponization Working Group established by AG Bondi on February 5, 2025. Martin helped "
                "plan and finance the January 6, 2021 rally and subsequently represented some of the "
                "defendants as an attorney; he was demoted from the Working Group chair role in "
                "February 2026 and DC Bar initiated disciplinary proceedings against him [Finding #6574; "
                "<a href=\"/dossiers/pam-bondi\">Pam Bondi</a>].</p>"
            ),
            "viz": None
        },
        {
            "id": "affidavit-credibility",
            "title": "Affidavit Witness Credibility and the Probable Cause Dispute",
            "content": (
                "<p>Fulton County\u2019s legal challenge centers on the adequacy of the probable cause "
                "showing in Agent Evans\u2019s affidavit. The county argues Evans established only possible "
                "cause, not probable cause, by relying on unsubstantiated hypotheticals about intentional "
                "acts by unidentified persons \u2014 a standard that requires speculation about unknown "
                "criminal intent rather than articulable facts supporting a belief that a crime was "
                "committed [Finding #6572]. Expert Ryan Macias, a former official at the Election "
                "Assistance Commission, submitted a declaration stating that witness accounts cited in "
                "the affidavit reflect gross mischaracterizations of how elections operate [Finding #6572].</p>"
                "\n\n"
                "<p>According to investigative reporting, Key Witness 7 is identified as Kevin Moncla, "
                "whose fraud claims were rejected repeatedly by courts over multiple years [Finding #6575]. "
                "Records indicate Moncla published a 263-page report in early January 2026 as part of a "
                "yearslong campaign to compel access to Fulton County\u2019s 2020 records [Finding #6575]. "
                "According to the same reporting, in 2023 Moncla was referred to the FBI for sending "
                "threatening emails to Georgia State Election Board members and an aide to Secretary of "
                "State Brad Raffensperger; that referral was omitted from Evans\u2019s affidavit, which "
                "cited him as a credibility-bearing witness [Finding #6575]. Records indicate that a "
                "second prominent witness, Janice Johnston, is a retired physician who has sustained a "
                "multi-year campaign alleging election fraud [Finding #6575].</p>"
                "\n\n"
                "<p>NPR reporting independently characterized the affidavit as relying on debunked claims. "
                "The county\u2019s filing argues these omissions and mischaracterizations amounted to deliberate "
                "misleading of Magistrate Judge Salinas, which if established could warrant suppression "
                "of the seized evidence under the <em>Franks v. Delaware</em> doctrine governing affidavit "
                "integrity [Finding #6572]. According to court filings, Johnston\u2019s prior history and "
                "the full scope of Moncla\u2019s 2023 FBI referral remain subjects of ongoing proceedings "
                "[Finding #6575].</p>"
                "\n\n"
                "<p>The NAACP and civil rights organizations filed a separate motion seeking court-imposed "
                "restrictions on the use of the seized voter data, on the grounds that the voter rolls "
                "included sensitive personal information for hundreds of thousands of Georgia voters "
                "whose data was swept up in a broad seizure not targeted at specific individuals "
                "[Finding #6572].</p>"
            ),
            "viz": None
        },
        {
            "id": "escalation-from-civil-to-criminal",
            "title": "Escalation from Civil Records Requests to Criminal Seizure",
            "content": (
                "<p>The January 2026 warrant was not the first federal attempt to obtain Fulton County\u2019s "
                "2020 election materials. For months prior, the DOJ had pursued the same records through "
                "civil proceedings, which Fulton County resisted. Those civil efforts failed. The FBI "
                "search warrant converted the dispute from a civil records access question to a criminal "
                "investigation, giving federal agents the authority to compel physical seizure without "
                "the county\u2019s consent [Finding #6576].</p>"
                "\n\n"
                "<p>The Fulton County action is one component of a broader campaign by the "
                "<a href=\"/dossiers/doj-voting-section\">DOJ Voting Section</a> to obtain election "
                "records from across the country. The section sued 29 states and the District of Columbia "
                "in seven waves between September 2025 and February 2026, seeking production of "
                "unredacted voter registration databases including Social Security and driver\u2019s license "
                "numbers [Finding #6576]. Federal courts in multiple states rejected those requests. "
                "Twelve Republican-led states complied voluntarily. Separately, AG "
                "<a href=\"/dossiers/pam-bondi\">Pam Bondi</a> sent demand letters to 15-plus states "
                "for voter registration rolls and sued Georgia in December 2025 specifically seeking "
                "2020 ballot documents [Finding #6524].</p>"
                "\n\n"
                "<p>A DOJ attorney signing cases against both Georgia voter rolls and Fulton County\u2019s "
                "2020 ballots is Christopher J. Gardner, who participated in the Georgia fake-electors "
                "legal effort alongside John Eastman and Kenneth Chesebro [Finding #6682; "
                "<a href=\"/dossiers/doj-voting-section\">DOJ Voting Section</a>]. Gardner is now a "
                "Trial Attorney in the Voting Section. The Voting Section\u2019s acting chief, Eric Neff, "
                "previously prosecuted a county elections vendor based on a tip from True the Vote, "
                "saw the charges dismissed within six weeks, and was placed on administrative leave "
                "before being hired into DOJ [Finding #6613].</p>"
                "\n\n"
                "<p>The DOJ concurrently shared voter roll data obtained from states with the Department "
                "of Homeland Security\u2019s SAVE citizenship verification program, which was upgraded from "
                "single-name to bulk-search capability for mass voter registration scanning. Senators "
                "Sheldon Whitehouse and Richard Blumenthal formally called for investigation of the "
                "Fulton County seizure in the context of this broader voter data collection effort "
                "[Finding #6576].</p>"
            ),
            "viz": None
        },
        {
            "id": "litigation-and-mediation",
            "title": "Litigation Status and Mediation",
            "content": (
                "<p>Fulton County Commission Chairman Robb Pitts, the full board of commissioners, "
                "the elections board, and Court Clerk Che Alexander filed suit on February 4, 2026 "
                "seeking return of the 650-plus boxes of seized materials. Alexander was added as a "
                "plaintiff specifically to address standing: DOJ argued the county as a governmental "
                "body lacked standing to seek return of election records, a position the clerk\u2019s "
                "independent constitutional role was intended to counter [Finding #6572].</p>"
                "\n\n"
                "<p>Judge J.P. Boulee ordered the parties to mediation on February 26, 2026. "
                "Former Georgia Supreme Court Chief Justice Harold Melton was appointed mediator "
                "on March 5, 2026, with a report to the court due by March 18, 2026 [Finding #6572]. "
                "The docket had been unsealed on Judge Boulee\u2019s order on February 7, 2026, making "
                "the warrant materials publicly accessible under docket reference "
                "Gov.uscourts.gand.355087 [Finding #6568].</p>"
                "\n\n"
                "<p>The county\u2019s Fourth Amendment theory \u2014 that an affidavit built on "
                "speculative hypotheticals about unidentified persons does not establish probable cause "
                "\u2014 has not yet been decided on the merits. If the mediation does not resolve "
                "the dispute, the constitutional adequacy of the probable cause showing and the "
                "Franks challenge to the affidavit\u2019s completeness will proceed to briefing "
                "[Finding #6572].</p>"
            ),
            "viz": "timeline"
        }
    ],

    "open_questions": [
        "What is the full list of the 11 witnesses in Evans\u2019s affidavit, what specific evidence each "
        "provided, which witnesses\u2019 credibility problems were known to DOJ or Olsen\u2019s White House "
        "office prior to the warrant application, and what connections do those witnesses have to the "
        "election denial litigation network, including Kurt Olsen, True the Vote, or the Election "
        "Integrity Network?",

        "Did the DOJ\u2019s pre-raid civil litigation seek the same ballot materials subsequently seized, "
        "and were the civil requests rejected by the same court that issued the warrant \u2014 which "
        "would bear on whether the criminal process was used to circumvent civil litigation outcomes?",

        "What specific statutory or regulatory authority did Gabbard cite to AG Bondi or DOJ to "
        "authorize DNI presence at a domestic search warrant execution, and has that authority claim "
        "been reviewed by the Office of Legal Counsel?",

        "Has the DOJ shared the seized Fulton County ballot materials, ballot images, or voter roll "
        "data with any other executive branch office, state actor, or outside organization \u2014 "
        "and if so, under what legal framework?",

        "What is Kevin Moncla\u2019s relationship to any White House, DOJ, or affiliated organization "
        "personnel, and was his 263-page January 2026 report coordinated in timing with the "
        "preparation of Evans\u2019s affidavit?"
    ],

    "applicable_models": [
        "private-order",
        "narrative-shield",
        "enabler-gradient",
        "institutional-capture"
    ]
}


def main():
    with open(DOSSIER_PATH, "r") as f:
        dossier = json.load(f)

    existing_curation = dossier.get("curation", {})
    existing_curation.update(CURATION)
    dossier["curation"] = existing_curation

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Curation written to {DOSSIER_PATH}")
    print(f"  lead: {len(CURATION['lead'])} chars")
    print(f"  system_role: {len(CURATION['system_role'])} chars")
    print(f"  sections: {len(CURATION['sections'])} sections")
    print(f"  open_questions: {len(CURATION['open_questions'])}")
    print(f"  applicable_models: {CURATION['applicable_models']}")


if __name__ == "__main__":
    main()
