#!/usr/bin/env python3
"""
Curation script for George Sorial dossier.
Writes the curation block with lead, system_role, sections, open_questions, applicable_models.
"""

import json
from datetime import datetime
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/george-sorial.json")


def build_curation() -> dict:
    lead = (
        "<p>George A. Sorial is an Egyptian-American attorney who served as Executive Vice President "
        "and Chief Compliance Counsel at the <a href=\"/dossiers/trump-organization\">Trump Organization</a> "
        "from 2002 to June 2019—seventeen years in which he managed legal exposure across the Organization's "
        "global real estate and licensing portfolio [Finding #6300]. After departing, he operated STMS "
        "Consulting Partners LLC (d/b/a Sorial Consulting) from Delray Beach, Florida, with a single "
        "disclosed LDA client in 2020 generating $10,000 per quarter [Finding #6337]. In November 2024, "
        "Sorial co-founded <a href=\"/dossiers/javelin-advisors-llc\">Javelin Advisors LLC</a> in Delaware "
        "with Keith Schiller, Trump's former personal bodyguard and Director of Oval Office Operations, "
        "and Robert W. Seiden, a private investigator previously associated with Trump [Finding #6285]. "
        "The firm registered as a foreign agent for the Islamic Republic of Pakistan (FARA #7579) in April 2025, "
        "terminated that registration in October 2025, and disclosed approximately $3.4 million in lobbying "
        "income across six clients in its first full operating year [Finding #6369]. Sorial also held a "
        "passive minority equity stake in <a href=\"/dossiers/greenmet\">GreenMet</a> "
        "(Greentech Minerals Holdings Inc.), a Washington DC-based critical minerals company, "
        "from which he resigned his board seat in early 2025 while retaining shares [Finding #6166].</p>"
    )

    system_role = (
        "Sorial functions as the legal-compliance credentialing layer within a small access-brokering "
        "network built from Trump Organization alumni. His role at the Trump Organization gave him "
        "direct exposure to the deal-structuring and compliance architecture of Trump's pre-presidential "
        "business empire. That credential, combined with Schiller's personal proximity to Trump during "
        "both White House terms, allows Javelin Advisors to market access to the Executive Office of "
        "the President across a diverse client roster—foreign governments pursuing mineral agreements, "
        "convicted felons seeking pardons, Taiwanese defense-adjacent manufacturers, and critical "
        "minerals developers seeking Pentagon contracts. Sorial provides the attorney-of-record and "
        "LDA registrant function while Schiller provides the named covered-official contact. "
        "The division of labor is consistent across all six disclosed Javelin clients."
    )

    sections = [
        {
            "id": "career-and-trump-organization-tenure",
            "title": "Career and Trump Organization Tenure",
            "viz": None,
            "content": (
                "<p>Sorial began his legal career at DeCotiis Fitzpatrick &amp; Cole, a New Jersey law firm, "
                "before joining the Trump Organization in 2002 [Finding #6371]. He holds a BA, JD, and MBA "
                "from Boston University and an LLM from Seton Hall Law, and is an active member of the "
                "Florida Bar (Bar #116632) [Finding #6337]. His role at the Trump Organization expanded over "
                "time from general counsel functions to EVP-level oversight of the Organization's global "
                "licensing and development portfolio, and from 2017 he held the title of Chief Compliance "
                "Counsel [Finding #6300].</p>"
                "<p>Sorial departed the Trump Organization on June 7, 2019, amid heightened public and "
                "prosecutorial scrutiny of the Organization's financial practices. He subsequently "
                "co-authored <em>The Real Deal: My Decade Fighting Battles and Winning Wars with Trump</em>, "
                "a book that serves as a public credential establishing his personal relationship with Trump "
                "[Finding #6337]. After departure he formed STMS Consulting Partners LLC (d/b/a Sorial "
                "Consulting) at 455 NE 5th Avenue, Delray Beach, FL. LDA records show a single client in "
                "2020: Lucas Compton LLC on behalf of Berman Law Group, for the Stop COVID Act covering "
                "torts, health, and foreign relations, at $10,000 per quarter [Finding #6337]. Total "
                "disclosed income from STMS in 2020 was $30,000. This represents Sorial's only visible "
                "lobbying activity between his Trump Organization departure and the 2024 formation of "
                "Javelin Advisors.</p>"
            ),
        },
        {
            "id": "javelin-advisors-structure-and-clients",
            "title": "Javelin Advisors: Structure and Client Roster",
            "viz": "ego_network",
            "content": (
                "<p>Javelin Advisors LLC was incorporated in Delaware on November 13, 2024, with three "
                "equal co-owners and Managing Directors: George A. Sorial, Keith Schiller, and Robert W. "
                "Seiden [Finding #6285]. The firm registered its primary address as 433 Plaza Real, Suite "
                "275, Boca Raton, FL 33432 at formation, shifting to 1701 Pennsylvania Avenue NW, Suite "
                "200, Washington DC 20006 by November 2025. A supplemental engagement letter lists "
                "1751 Pinnacle Drive, Tysons, VA 22102. The firm's website is "
                "www.javelinadvisorsllc.com [Finding #6285].</p>"
                "<p><a href=\"/dossiers/javelin-advisors-llc\">Javelin Advisors</a> disclosed six LDA "
                "clients across 2024–2025, generating approximately $3.4–3.9 million in total income "
                "[Finding #6369, #6325]:</p>"
                "<ul>"
                "<li><strong>Fred Daibes</strong> (Q1 2025, $1 million): NJ developer convicted of "
                "bribing Senator Bob Menendez with cash and gold bars; hired Javelin for 'executive "
                "relief' (pardon). Engagement terminated June 2025 [Finding #6301].</li>"
                "<li><strong>Logical Strategies LLC</strong> (Q3 2025, $1.2 million): NY-based entity "
                "whose beneficial owners are not publicly established; hired Javelin to lobby the EPA "
                "on the Final Rule for Asbestos Part 1 (chrysotile asbestos under TSCA) and government "
                "contracts. The EPA had filed a motion with the Fifth Circuit on June 16, 2025 to "
                "reconsider the chrysotile ban; it withdrew that motion July 7, 2025, and Q4 2025 shows "
                "no further Logical Strategies activity [Finding #6365, #6388]. Logical Strategies' "
                "principal is <a href=\"/dossiers/giorgi-rtskhiladze\">Giorgi Rtskhiladze</a>, a "
                "Georgian-American businessman who appeared in the Mueller Report in connection with "
                "efforts to suppress recordings involving Trump, and who has ties to CIS energy "
                "interests [Finding #6384].</li>"
                "<li><strong>Capstone USA Advisory Group LLC</strong> (Q3–Q4 2025, $300,000): "
                "NY-based entity focused on Ukrainian private business technology and defense "
                "reconstruction [Finding #6292].</li>"
                "<li><strong>Greg E. Lindberg</strong> (Q3 2025, minimal fees): NC billionaire who "
                "pleaded guilty in 2024 to $2 billion fraud and money laundering and to bribing the "
                "NC Insurance Commissioner; hired Javelin for an executive pardon [Finding #6301].</li>"
                "<li><strong>NioCorp Developments Ltd</strong> (Q4 2025, $400,000): Nasdaq-listed "
                "Canadian-American critical minerals developer; DOD separately awarded NioCorp's "
                "subsidiary Elk Creek Resources Corp up to $15 million via Defense Production Act "
                "Title III for scandium supply. Javelin lobbied on 'funding and/or contracts with "
                "respect to NioCorp,' contacting the Department of Defense [Finding #6339].</li>"
                "<li><strong>I-MEI Foods Co. Ltd</strong> (Q4 2025, newly registered): Taiwanese food "
                "manufacturer with three affiliated entities—Tansimo Robotic Manufacturing Inc., "
                "Chelpis Quantum Corp (quantum cybersecurity), and Golden Saddle Machinery Co. Ltd. "
                "Javelin targeted the DOD for food products, cybersecurity, and robotics contracts "
                "[Finding #6377, #6302].</li>"
                "</ul>"
                "<p>The covered official listed across Javelin's LDA filings is consistently Keith "
                "Schiller, identified by his former White House title: Deputy Assistant to the President "
                "and Director of Oval Office Operations. Contacts are listed as the Executive Office of "
                "the President [Finding #6365]. Sorial serves as the filer-of-record on LDA and FARA "
                "registrations [Finding #6316].</p>"
                "<p>Seiden's structural position within the Pakistan engagement created a self-dealing "
                "arrangement: Seiden Law LLP held the direct contract with the Government of Pakistan "
                "at $250,000/month, then subcontracted to Javelin Advisors at $50,000/month. Robert "
                "Seiden controlled both sides of this contract as Managing Partner of Seiden Law LLP "
                "and co-equal Managing Director of Javelin [Finding #6299].</p>"
            ),
        },
        {
            "id": "pakistan-fara-and-rare-earth-mandate",
            "title": "Pakistan FARA and Rare Earth Mandate",
            "viz": None,
            "content": (
                "<p>On April 25, 2025, Javelin Advisors registered under FARA (Registration #7579) as a "
                "foreign agent for the Islamic Republic of Pakistan, with the foreign principal listed "
                "at the Pakistan Embassy at 3517 International Court NW, Washington DC 20008 [Finding "
                "#6315]. The engagement arose from the Pakistan Minerals Investment Forum in April 2025, "
                "which produced a US-Pakistan framework for cooperation on rare earth and critical "
                "minerals with an indicative value cited in FARA filings of up to $1 trillion "
                "[Finding #6173]. The military engineering corps of Pakistan, Frontier Works "
                "Organisation (FWO), was identified as the extraction entity in the framework "
                "[Finding #6202].</p>"
                "<p>Javelin's direct contract ran through Seiden Law LLP. Documented payments from "
                "Seiden Law LLP to Javelin totaled $200,000 across four transfers (May 7, May 28, "
                "June 30, and August 20, 2025) [Finding #6286]. The FARA registration was terminated "
                "October 8, 2025 [Finding #6315].</p>"
                "<p>The primary congressional contact Javelin used for the Pakistan mandate was "
                "Representative Ronny Jackson (TX-13, former White House physician). Documented "
                "contacts include: an in-person meeting with Pakistani officials on May 1, 2025; "
                "a phone call on May 6 regarding the India-Pakistan conflict; a dinner arrangement "
                "call on May 16; and a call on May 28 that preceded delivery of a draft bilateral "
                "MoU. Javelin also targeted Representative Dan Crenshaw, Representative Morgan "
                "Luttrell, and former Interior Secretary Ryan Zinke's office, where the draft MoU "
                "was delivered [Finding #6336]. That MoU preceded a September 2025 deal between "
                "US Strategic Metals and Pakistan's FWO [Finding #6336].</p>"
                "<p>Javelin simultaneously lobbied for NioCorp Developments (a US domestic critical "
                "minerals developer) while registered as a foreign agent for Pakistan's critical "
                "minerals program—a dual mandate with overlapping issue areas and the same covered "
                "official [Finding #6374].</p>"
            ),
        },
        {
            "id": "greenmet-equity-position",
            "title": "GreenMet Equity Position",
            "viz": None,
            "content": (
                "<p>Sorial is a beneficial owner and passive minority shareholder of "
                "<a href=\"/dossiers/greenmet\">GreenMet</a> (Greentech Minerals Holdings Inc.), a "
                "Washington DC-incorporated critical minerals company headquartered at 1825 K Street "
                "NW, Suite 515, Washington DC 20006, founded in 2021 [Finding #6331]. GreenMet is "
                "led by CEO <a href=\"/dossiers/drew-horn\">Drew Horn</a>, a former Deputy Policy "
                "Director to Vice President Pence and Afghanistan Policy Director at OSD with a "
                "background in Army Special Forces and USMC [Finding #6166].</p>"
                "<p>Sorial resigned his board and advisory roles at GreenMet in early 2025 but "
                "retained his equity stake [Finding #6166]. His co-shareholder Keith Schiller "
                "underwent the same resignation-while-retaining-shares structure on the same "
                "timeline. The resignation of formal governance roles—but retention of financial "
                "interest—occurred in the months immediately preceding the formation of Javelin "
                "Advisors and Javelin's FARA registration for Pakistan's rare earth program "
                "[Finding #6331].</p>"
                "<p>GreenMet's equity compensation for its work brokering the Critical Metals Corp "
                "partnership (which secured a $120 million EXIM Bank letter of intent for Tanbreez "
                "Mining in Greenland) does not appear in any of the 167 publicly filed SEC documents "
                "from Critical Metals Corp (Nasdaq: CRML) [Finding #6271]. GreenMet, Sorial, and "
                "Schiller are absent from all CRML EDGAR filings, meaning the advisory relationship "
                "and any equity-for-services compensation is held only in private agreements "
                "[Finding #6271].</p>"
                "<p>A separate LittleSis record indicates Sorial held a Board of Directors seat at "
                "The Platinum Group LLC beginning July 1, 2021. This entity does not appear in the "
                "investigation's entity database and its relationship to GreenMet, critical minerals "
                "activity, or other network nodes has not been established [Finding #6375].</p>"
            ),
        },
        {
            "id": "key-relationships",
            "title": "Key Relationships",
            "viz": "ego_network",
            "content": (
                "<p><strong><a href=\"/dossiers/javelin-advisors-llc\">Keith Schiller</a></strong> "
                "is Sorial's most structurally significant partner. The two men share co-equal "
                "ownership of Javelin Advisors, co-held beneficial ownership of GreenMet, and filed "
                "joint FARA short-form disclosures on April 25, 2025. They made a joint $5,000 FEC "
                "contribution to Senator Katie Britt on September 8, 2025 [Finding #6300]. Schiller's "
                "value to Javelin is the covered-official designation: his former White House title "
                "(Deputy Assistant to the President, Director of Oval Office Operations) is cited "
                "consistently in LDA filings as the basis for EOP contacts [Finding #6365].</p>"
                "<p><strong>Robert W. Seiden</strong> is the third co-equal Managing Director of "
                "Javelin Advisors and appears as a lobbyist across all six client filings [Finding "
                "#6320]. As Managing Partner of Seiden Law LLP, he held the prime contract with "
                "Pakistan's government while simultaneously receiving subcontractor payments through "
                "Javelin—a structure in which he controlled both sides of the financial arrangement "
                "[Finding #6299].</p>"
                "<p><strong><a href=\"/dossiers/giorgi-rtskhiladze\">Giorgi Rtskhiladze</a></strong> "
                "is the beneficial controller of Logical Strategies LLC, Javelin's single largest "
                "2025 client at $1.2 million. Rtskhiladze is identified in the Mueller Report as "
                "having claimed to have 'stopped tapes from Russia' involving Trump, and has "
                "documented ties to CIS energy interests and Trump PAC donations [Finding #6384]. "
                "The asbestos lobbying mandate—targeting an EPA reconsideration of the chrysotile "
                "ban—was active for approximately one quarter before the EPA withdrew its "
                "reconsideration motion [Finding #6388].</p>"
                "<p><strong><a href=\"/dossiers/drew-horn\">Drew Horn</a></strong> connects Sorial "
                "to the GreenMet rare earth network. Horn, Sorial, and Schiller are all listed in "
                "DC corporate registry documents as beneficial owners of GreenMet [Finding #6331]. "
                "Horn's concurrent role as GreenMet CEO while Sorial and Schiller simultaneously "
                "held FARA registration for Pakistan's competing rare earth program created a "
                "structural conflict across the network's critical minerals mandates [Finding #6374].</p>"
                "<p><strong>Senator Katie Britt (R-AL)</strong> received a $5,000 joint contribution "
                "from Sorial and Schiller on September 8, 2025, documented in FEC records and "
                "referenced in Javelin's November 2025 FARA supplemental statement [Connection #3215]. "
                "Britt sits on the Senate Banking Committee and the Armed Services Committee, "
                "both relevant to Javelin's NioCorp and Pakistan mandates.</p>"
            ),
        },
    ]

    open_questions = [
        (
            "Who are the beneficial owners of Logical Strategies LLC (NY), Javelin's $1.2 million "
            "Q3 2025 client? The corporate registration does not surface a natural person; the "
            "connection to Rtskhiladze is established only through investigative reporting, "
            "not through public corporate registry records."
        ),
        (
            "What is the nature and compensation structure of The Platinum Group LLC (LittleSis "
            "records Sorial as a board member from July 2021), and does this entity have any "
            "overlap with GreenMet's critical minerals activity or other network nodes?"
        ),
        (
            "GreenMet's advisory compensation from Critical Metals Corp for brokering the Tanbreez "
            "partnership and $120 million EXIM Bank LOI does not appear in any of 167 CRML SEC "
            "filings. What is the structure of the private advisory agreement, and does it include "
            "equity or cash compensation for Sorial, Schiller, or STMS Consulting?"
        ),
        (
            "Why was Javelin's Pakistan FARA terminated on October 8, 2025, approximately five "
            "months after registration? The September 2025 US Strategic Metals / FWO deal that "
            "followed the draft MoU suggests the mandate concluded rather than collapsed—what "
            "triggered formal termination?"
        ),
        (
            "Did the NioCorp lobbying mandate (targeted DOD, active Q4 2025) continue into 2026, "
            "and does Javelin's simultaneous GreenMet equity (another critical minerals vehicle "
            "with an overlapping DOD nexus) create a conflict of interest in the NioCorp mandate?"
        ),
        (
            "Sorial's sole LDA client between Trump Organization departure (June 2019) and Javelin "
            "formation (November 2024) generated $30,000. What sustained his income during this "
            "five-year gap? STMS Consulting's LDA filings show only Q2–Q4 2020 activity."
        ),
    ]

    applicable_models = [
        "access-brokering",
        "alumni-network-monetization",
        "covered-official-as-product",
        "dual-mandate-conflict",
        "private-agreement-gap",
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
    curation["curated_at"] = datetime.utcnow().isoformat()
    dossier["curation"] = curation

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2)
        f.write("\n")

    print(f"Written: {DOSSIER_PATH}")
    print(f"Sections: {[s['id'] for s in new_fields['sections']]}")
    print(f"Open questions: {len(new_fields['open_questions'])}")
    print(f"Applicable models: {new_fields['applicable_models']}")


if __name__ == "__main__":
    main()
