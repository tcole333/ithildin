#!/usr/bin/env python3
"""Write curation fields into content/dossiers/daniel-berulis.json."""

import json
from pathlib import Path

DOSSIER_PATH = (
    Path(__file__).parent.parent / "content" / "dossiers" / "daniel-berulis.json"
)

CURATION = {
    "lead": (
        "<p>Daniel Berulis is a network security architect who was employed at the National Labor Relations "
        "Board when DOGE personnel arrived in early March 2025 and obtained unrestricted &ldquo;tenant "
        "owner&rdquo; level access to the agency&rsquo;s Azure environment [Finding #6396]. Berulis "
        "documented the operation from inside the NLRB&rsquo;s IT division, where he reported to Chief "
        "Information Officer <a href=\"/dossiers/prem-aburvasamy\">Prem Aburvasamy</a>. On April 14, 2025 "
        "&mdash; the same day NLRB IT staff had their administrative access stripped &mdash; he filed a "
        "formal whistleblower disclosure to Congress and the U.S. Office of Special Counsel through "
        "Whistleblower Aid, represented by attorney <a href=\"/dossiers/andrew-bakaj\">Andrew Bakaj</a> "
        "[Finding #6415].</p>"
        "\n\n"
        "<p>The disclosure and its exhibits document a sequence beginning March 3, 2025, when DOGE "
        "personnel deployed container technology the NLRB had never previously used and created accounts "
        "with tenant-admin privileges configured to be exempt from logging. Between 3 a.m. and 4 a.m. EST "
        "on March 4&ndash;5, Berulis observed an anomalous spike in outbound data traffic consistent with "
        "approximately 10 gigabytes of text files leaving the NxGen case management system &mdash; the "
        "NLRB&rsquo;s repository for active labor cases, union member personal information, witness "
        "testimony, trade secrets, and proprietary company data submitted under confidentiality protections "
        "[Finding #6399]. Azure network watcher was set to off by March 5. On March 10, alerting and "
        "monitoring tools were disabled. On March 11, over twenty login attempts against the newly created "
        "DOGE accounts arrived from IP address 83.149.30.186, located in Primorskiy Krai in Russia&rsquo;s "
        "Far East; many attempts occurred within fifteen minutes of account creation and used the correct "
        "username and password. The attempts were blocked solely because the NLRB&rsquo;s geolocation "
        "policy disallows overseas access [Finding #6400].</p>"
        "\n\n"
        "<p>On April 3&ndash;4, NLRB staff were instructed to halt US-CERT incident reporting. On April "
        "14, the day Berulis filed, IT administrative access was stripped from career staff. "
        "<a href=\"/dossiers/lasharn-hamilton\">NLRB director Lasharn Hamilton</a> stated the day after "
        "NPR published the disclosure that there had been no &ldquo;official&rdquo; prior DOGE contact at "
        "the agency [Finding #6429]. While Berulis was preparing a supplemental disclosure, someone affixed "
        "a threatening note to his home door accompanied by drone photographs showing him in his "
        "neighborhood; attorney Bakaj confirmed the note referenced the specific disclosure under "
        "preparation [Finding #6403]. A subsequent Krebs on Security forensic analysis identified three "
        "external GitHub libraries downloaded to NLRB systems, one designed for proxy pool rotation for "
        "web scraping and brute-forcing [Finding #6429].</p>"
    ),

    "system_role": (
        "Berulis is the primary documentary source on the DOGE operation at the NLRB: a career IT "
        "professional who observed, logged, and formally disclosed the sequence of access provisioning, "
        "data movement, monitoring suppression, and credential exposure that occurred inside the agency "
        "in March 2025. His disclosure is the evidentiary foundation for subsequent Congressional "
        "investigation and independent forensic analysis of that operation."
    ),

    "sections": [
        {
            "id": "key-relationships",
            "title": "Key Relationships",
            "viz": "ego_network",
            "content": (
                "<p>Berulis&rsquo;s direct supervisor at the NLRB was Chief Information Officer "
                "<a href=\"/dossiers/prem-aburvasamy\">Prem Aburvasamy</a>. Berulis held the role of "
                "network security architect, placing him in the chain responsible for monitoring and "
                "maintaining the agency&rsquo;s Azure environment &mdash; the same systems DOGE "
                "personnel accessed beginning March 3, 2025 [Finding #6429]. The CIO chain of command "
                "is relevant because DOGE access provisioning bypassed the standard approval process "
                "that would ordinarily require CIO-level authorization for tenant-owner privileges "
                "[Finding #6396].</p>"
                "\n\n"
                "<p>Andrew Bakaj of <a href=\"/dossiers/andrew-bakaj\">Whistleblower Aid</a> represented "
                "Berulis in both the original April 14 disclosure to Congress and the Office of Special "
                "Counsel and in the subsequent supplemental disclosure that added the physical intimidation "
                "evidence. Bakaj personally confirmed to journalists that the threatening note left at "
                "Berulis&rsquo;s home referenced the specific disclosure then being prepared "
                "[Finding #6403].</p>"
                "\n\n"
                "<p><a href=\"/dossiers/lasharn-hamilton\">Lasharn Hamilton</a>, who served as NLRB "
                "Director in the relevant period, publicly stated on April 16 that there had been no "
                "&ldquo;official&rdquo; prior DOGE contact with the agency &mdash; a characterization "
                "that Berulis&rsquo;s disclosure, filed two days earlier, directly contradicts. The "
                "qualifier &ldquo;official&rdquo; is notable: it may technically exclude informal or "
                "undocumented access that Berulis documented as occurring outside standard IT provisioning "
                "channels [Finding #6429].</p>"
            ),
        },
        {
            "id": "the-nlrb-doge-operation",
            "title": "The NLRB DOGE Operation",
            "viz": None,
            "content": (
                "<p>The DOGE operation at the NLRB followed a pattern documented across multiple federal "
                "agencies: rapid provisioning of high-privilege accounts, suppression of logging and "
                "monitoring, and data movement that preceded or accompanied the suppression of incident "
                "reporting channels [Finding #6396]. At the NLRB, the specific technical steps Berulis "
                "documented were: account creation with tenant-admin privileges exempt from logging (March 3); "
                "deployment of container technology the agency had not previously used (March 3); Azure "
                "network watcher disabled (March 5); alerting and monitoring tools disabled (March 10); "
                "a 10 GB data transfer from NxGen in the early morning hours of March 4&ndash;5 "
                "[Finding #6399]; and instructions to halt US-CERT reporting (April 3&ndash;4) "
                "[Finding #6429].</p>"
                "\n\n"
                "<p>The NxGen case management system held data with significant competitive and legal "
                "sensitivity. Employers and labor organizations submit confidential business records, "
                "witness identities, and litigation strategy documents to NLRB proceedings under "
                "confidentiality protections that are foundational to the agency&rsquo;s adjudicatory "
                "function. Among the companies with active NLRB cases at the time of the access was "
                "SpaceX, which simultaneously had a pending constitutional challenge to the NLRB&rsquo;s "
                "structure in the Fifth Circuit [Finding #6440]. Elon Musk led DOGE during this period "
                "as a special government employee [Finding #6441].</p>"
                "\n\n"
                "<p>The Senate Homeland Security and Governmental Affairs Committee report issued by "
                "Senator Peters in September 2025 identified a cross-agency pattern in which career "
                "cybersecurity officials who raised objections were sidelined or terminated, and DOGE "
                "personnel were installed in chief information officer roles to approve their own data "
                "access without standard oversight procedures [Finding #6409]. The Peters report "
                "concluded that DOGE operations likely violated the Privacy Act of 1974, the "
                "E-Government Act of 2002, FISMA, the Federal Records Act, and potentially the Computer "
                "Fraud and Abuse Act [Finding #6408]. The NLRB sequence Berulis documented is one of "
                "the named incidents in that report.</p>"
            ),
        },
        {
            "id": "russian-credential-access-attempt",
            "title": "Russian Credential Access Attempt",
            "viz": None,
            "content": (
                "<p>On March 11, 2025, more than twenty login attempts arrived against the DOGE accounts "
                "newly created at the NLRB, originating from IP address 83.149.30.186, which geolocates "
                "to Primorskiy Krai in Russia&rsquo;s Far East. Berulis&rsquo;s disclosure records that "
                "many of these attempts occurred within fifteen minutes of the accounts being created, "
                "and that the attempts used the correct username and password for those accounts "
                "[Finding #6400]. The attempts were blocked only by the NLRB&rsquo;s standing geolocation "
                "policy that does not permit overseas logins.</p>"
                "\n\n"
                "<p>The Krebs on Security forensic review, which corroborated Berulis&rsquo;s account "
                "through independent analysis, noted the presence of three external GitHub libraries "
                "downloaded to NLRB systems, including one specifically designed for proxy pool rotation "
                "for web scraping and brute-forcing &mdash; a tool consistent with credential "
                "enumeration or external data harvesting [Finding #6429]. The disclosure does not "
                "assert attribution for the Russian login attempts; it records them as observed events. "
                "The proximity of the attempts to account creation &mdash; within minutes, using valid "
                "credentials &mdash; is a factual detail whose explanation remains unresolved.</p>"
            ),
        },
        {
            "id": "intimidation-and-institutional-response",
            "title": "Intimidation and Institutional Response",
            "viz": None,
            "content": (
                "<p>While Berulis was preparing the supplemental disclosure, a note was affixed to the "
                "door of his home alongside drone photographs showing him walking in his neighborhood. "
                "Attorney Bakaj confirmed to journalists that the note made direct reference to the "
                "specific disclosure Berulis was then preparing. Berulis included this evidence in the "
                "supplemental filing as the basis for witness intimidation allegations [Finding #6403].</p>"
                "\n\n"
                "<p>The timing of institutional events around his disclosure is documented. On April 14 "
                "&mdash; the date of the original filing and the date NPR published its account of the "
                "disclosure &mdash; administrative access was stripped from career NLRB IT staff "
                "[Finding #6429]. On April 16, DOGE personnel visited the NLRB [Finding #6415]. That "
                "same day, Director Hamilton publicly characterized the DOGE contact as having no "
                "&ldquo;official&rdquo; prior existence [Finding #6429]. The sequence &mdash; access "
                "stripped on the day of publication, DOGE physically present two days later &mdash; "
                "is documented but not explained in any NLRB public statement.</p>"
            ),
        },
    ],

    "open_questions": [
        (
            "The Russian login attempts on March 11 used valid credentials for DOGE accounts created days "
            "earlier. How were those credentials obtained, and by whom? The disclosure records the event "
            "but does not resolve whether the credential exposure occurred through the DOGE provisioning "
            "process itself, through the GitHub libraries downloaded to NLRB systems, or through another "
            "channel."
        ),
        (
            "The NLRB issued instructions on April 3\u20134 to halt US-CERT incident reporting. Who "
            "within the NLRB chain of command issued that instruction, under what authority, and was "
            "it relayed from DOGE personnel or from career leadership?"
        ),
        (
            "The 10 GB data transfer from NxGen occurred on March 4\u20135. Where did the data go? "
            "Berulis\u2019s disclosure identifies the outbound traffic but does not identify a "
            "destination; Congressional and OIG investigations have not publicly confirmed the "
            "transfer destination or whether the data was retained, copied, or forwarded."
        ),
        (
            "Director Hamilton\u2019s April 16 statement qualified prior DOGE contact as lacking "
            "\u2018official\u2019 status. What is the NLRB\u2019s definition of \u2018official\u2019 "
            "contact in this context, and does informal or undocumented access fall outside that "
            "definition?"
        ),
        (
            "The threatening note affixed to Berulis\u2019s door referenced the specific disclosure "
            "under preparation. Who had knowledge of that disclosure\u2019s contents and timeline "
            "before it was filed, and is there a documented chain of custody for that information "
            "between Whistleblower Aid and any government or DOGE-connected party?"
        ),
        (
            "One of the three GitHub libraries downloaded to NLRB systems was described as designed "
            "for proxy pool rotation for web scraping and brute-forcing. Were those libraries executed "
            "on NLRB infrastructure, and if so, what systems or external endpoints did they interact with?"
        ),
    ],

    "applicable_models": [
        "regulatory-capture",
        "private-order",
        "narrative-shield",
        "enabler-gradient",
    ],
}


def main():
    with open(DOSSIER_PATH) as f:
        dossier = json.load(f)

    existing_curation = dossier.get("curation", {})

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
