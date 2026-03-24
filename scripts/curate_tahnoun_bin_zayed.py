#!/usr/bin/env python3
"""
Curation script for Tahnoun bin Zayed Al Nahyan dossier.
Target: content/dossiers/tahnoun-bin-zayed-al-nahyan.json

This dossier (slug: tahnoun-bin-zayed-al-nahyan) covers the tech-right and
epstein profiles with 5 findings and 5 connections. A separate dossier
(sheikh-tahnoon-bin-zayed-al-nahyan) holds earlier epstein-profile findings;
this curation synthesizes the two bodies of evidence into the tech-right
context — primarily the chain of UAE sovereign capital deployments into
Trump-adjacent commercial ventures between January 2025 and February 2026.
"""

import json
from pathlib import Path
from datetime import datetime, timezone

DOSSIER_PATH = Path("content/dossiers/tahnoun-bin-zayed-al-nahyan.json")

curation = {
    "curated_at": datetime.now(timezone.utc).isoformat(),
    "key_finding_ids": [3814, 5065, 5066, 5067, 5069],
    "lead": (
        "<p>Tahnoun bin Zayed Al Nahyan (born December 4, 1968, Abu Dhabi) is the UAE National "
        "Security Adviser, Deputy Ruler of Abu Dhabi, and a full brother of UAE President Mohammed "
        "bin Zayed Al Nahyan. He chairs <a href=\"/dossiers/g42\">G42</a> (Group 42), "
        "<a href=\"/dossiers/mgx\">MGX</a> Fund Management, International Holding Company (IHC, "
        "Abu Dhabi Exchange-listed), and ADQ (Abu Dhabi Developmental Holding), while sitting on "
        "the Mubadala board. His private vehicle, Royal Group Holding, owns G42 outright and "
        "holds 61% of IHC. Press coverage as of 2025 estimated assets under his direct or "
        "indirect control at over $1.5 trillion [Finding #3814].</p>"
        "<p>OpenSanctions classifies him as a Politically Exposed Person (ID Q85804913, datasets: "
        "wikidata, wd_categories) and attaches a <code>reg.action</code> flag from the US federal "
        "enforcements dataset, indicating involvement in a US federal enforcement matter. He "
        "appears in the ICIJ Pandora Papers. He is colloquially known as the &#8220;Spy "
        "Sheikh&#8221; in reference to his oversight of UAE offensive cyber capabilities including "
        "the DarkMatter operation [Finding #5065]. LittleSis documents him as a public official "
        "and businessman (entity 447280) with confirmed connections to "
        "<a href=\"/dossiers/world-liberty-financial\">World Liberty Financial</a>, "
        "<a href=\"/dossiers/mgx\">MGX</a>, and ADQ [Finding #5066].</p>"
        "<p>Between January 2025 and November 2025, Tahnoun-controlled entities deployed at "
        "least $9.5 billion into four transactions whose completion required or directly "
        "benefited from Trump administration executive and regulatory action: the $500 million "
        "Aryam Investment 1 acquisition of 49% of "
        "<a href=\"/dossiers/world-liberty-financial\">World Liberty Financial</a> (January 16, "
        "2025 — four days before inauguration), the $2 billion MGX investment in Binance settled "
        "via the Trump family&#8217;s USD1 stablecoin (March 2025), the $7 billion MGX commitment "
        "to Stargate LLC at the White House (January 21, 2025), and the May 2025 Trump "
        "administration approval of up to 35,000 Nvidia GB300 AI systems for G42 [Finding #5067]. "
        "Senator Elizabeth Warren called for reversal of the chip sales after public reporting on "
        "the &#8220;Spy Sheikh&#8221; in February 2026 [Finding #5067].</p>"
    ),
    "system_role": (
        "Tahnoun holds a structurally singular position: he is simultaneously the UAE state's "
        "principal intelligence authority and the controlling beneficial owner of a sovereign "
        "commercial empire spanning AI, cryptocurrency, banking, and infrastructure. Every "
        "commercial transaction he executes carries the policy weight of a state-level "
        "negotiation, and every intelligence interest he holds is backed by the capital "
        "allocation capacity of a multi-trillion-dollar portfolio. In the US context, he "
        "functions as Abu Dhabi's primary counterpart for accessing and shaping the Trump "
        "administration's AI chip export policy, crypto regulatory posture, and digital "
        "infrastructure investment — with commercial investment vehicles providing the "
        "financial mechanism for that access."
    ),
    "sections": [
        {
            "id": "identity-and-formal-roles",
            "title": "Identity and Formal Roles",
            "viz": None,
            "content": (
                "<p>Tahnoun bin Zayed Al Nahyan was born December 4, 1968, in Abu Dhabi — "
                "some sources cite 1971, but the December 4, 1968 date appears in OpenSanctions "
                "primary records. He is the son of UAE founder Sheikh Zayed bin Sultan Al Nahyan "
                "and a full brother of UAE President Mohammed bin Zayed (MBZ). His formal "
                "government title is UAE National Security Adviser; he also holds the title of "
                "Deputy Ruler of Abu Dhabi [Finding #5065].</p>"
                "<p>His institutional chairmanships as of early 2026 include: "
                "<a href=\"/dossiers/g42\">G42</a> (Group 42, Abu Dhabi AI company), "
                "<a href=\"/dossiers/mgx\">MGX</a> Fund Management (co-founded with Mubadala, "
                "March 2024), International Holding Company / IHC (Abu Dhabi Exchange-listed "
                "conglomerate), ADQ (Abu Dhabi Developmental Holding, the $110 billion sovereign "
                "development fund), and First Abu Dhabi Bank. He sits on the Mubadala Investment "
                "Company board. Royal Group Holding, his private vehicle, owns G42 outright and "
                "holds 61% of IHC [Finding #3814].</p>"
                "<p>OpenSanctions (ID Q85804913) lists two distinct Tahnoun Al Nahyan individuals. "
                "The subject of this dossier — UAE National Security Adviser, born 1968 — should "
                "not be confused with Tahnoun bin Mohammed Al Nahyan (born 1942, died 2024), his "
                "uncle, who held different positions. UK Companies House holds officer appointment "
                "records under his name [Finding #3814].</p>"
                "<p>LittleSis describes him as: &#8220;member of the royal family, UAE national "
                "security advisor, mentioned in Pandora Papers, known as the spymaster behind the "
                "country&#8217;s cyberwarfare&#8221; and, in 2025 press, &#8220;the A.I. world&#8217;s "
                "trillion-dollar money man&#8221; [Finding #5066].</p>"
            ),
        },
        {
            "id": "intelligence-background",
            "title": "Intelligence Background and the DarkMatter-G42 Succession",
            "viz": None,
            "content": (
                "<p>Tahnoun&#8217;s &#8220;Spy Sheikh&#8221; designation reflects his oversight "
                "of UAE offensive cyber capabilities, principally DarkMatter Group (2015&#8211;2019). "
                "DarkMatter employed former NSA, CIA, and Israeli intelligence officers and ran "
                "Project Raven, a UAE surveillance operation targeting dissidents, journalists, "
                "and US persons. Three former Project Raven contractors were criminally charged by "
                "the US Department of Justice under export control laws [Finding #3814].</p>"
                "<p><a href=\"/dossiers/g42\">G42</a> absorbed substantial DarkMatter personnel "
                "and infrastructure as DarkMatter wound down. G42 CEO Peng Xiao previously ran "
                "Pegasus LLC, a DarkMatter subsidiary; Pax AI, a G42 subsidiary, is a rebranding "
                "of Pegasus itself. G42 created the ToTok messaging application (originally "
                "branded G42 IM, rebranded July 2019) through Breej Holding — whose sole director "
                "is Tahnoun&#8217;s adopted son — and the application was identified by US "
                "intelligence as a UAE mass surveillance tool. The CIA opened an investigative "
                "file on Peng Xiao [Finding #3814].</p>"
                "<p>G42&#8217;s CIO Zhang Xiaoping maintained simultaneous roles at Yitu "
                "Technology, a US-sanctioned Chinese AI and surveillance company, while G42 held "
                "Microsoft&#8217;s $1.5 billion investment. These connections formed the core "
                "of US national security concerns: that advanced Nvidia chips supplied to G42 or "
                "<a href=\"/dossiers/mgx\">MGX</a> could be diverted into Chinese "
                "military-civil fusion programs [Finding #3814].</p>"
                "<p>The OpenSanctions <code>reg.action</code> flag from the US federal "
                "enforcements dataset — visible in the Q85804913 entry, first seen 2023-07-18 — "
                "indicates Tahnoun is connected to a US federal enforcement matter. The specific "
                "nature of that matter has not been publicly identified [Finding #5065].</p>"
            ),
        },
        {
            "id": "entity-network",
            "title": "Corporate Architecture: G42, MGX, IHC, and ADQ",
            "viz": "ego_network",
            "content": (
                "<p>Tahnoun controls his commercial portfolio through three overlapping ownership "
                "chains. The first is his private vehicle: Royal Group Holding owns G42 outright "
                "and holds 61% of IHC. IHC (Abu Dhabi Exchange-listed, approximately $250 billion "
                "market cap) contains 2PointZero, a $27 billion holding company that itself holds "
                "Chimera Investment LLC and Lunate Capital. IHC&#8217;s share price grew "
                "approximately 42,000% between 2019 and 2024 [Finding #3814].</p>"
                "<p>The second chain is sovereign: Tahnoun chairs ADQ (the $110 billion Abu Dhabi "
                "development vehicle, LittleSis entity 447278) and sits on the Mubadala board. "
                "Mubadala co-founded <a href=\"/dossiers/mgx\">MGX</a> with G42 in March 2024; "
                "Tahnoun chairs MGX and Mubadala vice-chairman Khaldoon Khalifa Al Mubarak serves "
                "as MGX Vice Chairman [Finding #5066].</p>"
                "<p>The third chain is the intermediary tier: Aryam Investment 1 — the vehicle "
                "used to acquire 49% of "
                "<a href=\"/dossiers/world-liberty-financial\">World Liberty Financial</a> — is "
                "incorporated as two identically named entities, one in Delaware and one in Abu "
                "Dhabi. The Delaware entity is managed by Martin Edelman (G42 General Counsel) "
                "and Peng Xiao (G42 CEO), both of whom also serve on the MGX board. Aryam "
                "thereby secured two of five WLFI board seats without public disclosure at the "
                "time of signing [Finding #5066].</p>"
                "<p>SEC EDGAR records document Tahnoun&#8217;s name in two specific US company "
                "filings: a TeraWulf Inc (WULF, bitcoin mining) 8-K filed May 9, 2025, and an "
                "Endeavor Group Holdings (EDR, entertainment/sports) FWP filed April 20, 2021. "
                "These filings expand his known US investment footprint beyond AI and crypto into "
                "mining infrastructure and entertainment [Finding #5069].</p>"
            ),
        },
        {
            "id": "trump-financial-nexus",
            "title": "Financial Transactions with Trump-Connected Ventures",
            "viz": None,
            "content": (
                "<p>Four confirmed financial transactions link Tahnoun-controlled entities to "
                "ventures whose regulatory fortunes were directly shaped by the Trump "
                "administration between January 2025 and November 2025.</p>"
                "<p><strong>WLFI acquisition (January 16, 2025).</strong> Four days before "
                "inauguration, <a href=\"/dossiers/world-liberty-financial\">World Liberty "
                "Financial</a> signed an agreement with Aryam Investment 1 giving Tahnoun&#8217;s "
                "entity a 49% stake for $500 million. Approximately $187 million flowed to Trump "
                "family entities from this transaction. Aryam secured two of five WLFI board "
                "seats, occupied by Edelman and Peng Xiao, without public disclosure. "
                "<a href=\"/dossiers/steve-witkoff\">Steve Witkoff</a>, as Trump&#8217;s Middle "
                "East Envoy, holds direct diplomatic access to Tahnoun while his family "
                "simultaneously receives 12.5% of WLFI net protocol revenue from that $500 "
                "million investment. No recusal or ethics disclosure for Witkoff specific to his "
                "UAE diplomatic role and the WLFI revenue stream has been identified [Finding #5066].</p>"
                "<p><strong>Stargate commitment (January 21, 2025).</strong> MGX committed $7 "
                "billion to Stargate LLC, the $500 billion AI infrastructure joint venture "
                "announced at the White House alongside SoftBank ($19 billion), OpenAI ($19 "
                "billion), and Oracle ($7 billion). <a href=\"/dossiers/g42\">G42</a> serves as "
                "a key operator for Stargate UAE, launched in May 2025. OpenAI CEO Sam Altman "
                "described Tahnoun as a &#8220;dear personal friend.&#8221; MGX also participated "
                "in OpenAI&#8217;s $6.6 billion round at a $500 billion valuation in October 2025 "
                "[Finding #5066].</p>"
                "<p><strong>MGX&#8211;Binance investment (March 2025).</strong> MGX invested $2 "
                "billion in Binance, with the transaction settled using the USD1 stablecoin issued "
                "by <a href=\"/dossiers/world-liberty-financial\">World Liberty Financial</a>. "
                "WLFI confirmed that MGX and Binance would have used foreign fiat currency had "
                "USD1 not been available — making the use of the Trump family&#8217;s stablecoin "
                "a deliberate selection. Binance founder Changpeng Zhao was pardoned by President "
                "Trump in October 2025. The <a href=\"/dossiers/zachary-witkoff\">Witkoff family</a> "
                "connection to both WLFI and Steve Witkoff&#8217;s UAE diplomatic role was the "
                "basis for a Senate Banking Committee conflict-of-interest inquiry [Finding #5067].</p>"
                "<p><strong>G42 chip deal (May 2025 &#8211; November 2025).</strong> Trump signed "
                "an agreement with <a href=\"/dossiers/g42\">G42</a> in May 2025 for the largest "
                "AI campus outside the US in the UAE. The Trump administration cleared advanced AI "
                "chip exports to the UAE in December 2024 under a Microsoft deal (Axios), and in "
                "November 2025 approved G42&#8217;s direct purchase of up to 35,000 Nvidia GB300 "
                "systems — a reversal of the Biden administration&#8217;s refusal of the same "
                "request. Microsoft&#8217;s total UAE investment reached $15.2 billion by November "
                "2025. Senator Warren called for reversal of UAE chip sales in February 2026 "
                "following public reporting on Tahnoun [Finding #5067].</p>"
                "<p>The sequencing is documented: Tahnoun visited Washington in March 2025 to "
                "discuss AI-government integration with Trump officials; by July 2025 some Trump "
                "officials sought to reduce G42&#8217;s direct chip access (WSJ); by November 2025 "
                "the full approval was granted. Three Congressional inquiries were active as of "
                "March 2026 [Finding #5067].</p>"
            ),
        },
        {
            "id": "gerson-russia-channel",
            "title": "Rick Gerson and the Russia&#8211;UAE&#8211;Kushner Back-Channel",
            "viz": None,
            "content": (
                "<p><a href=\"/dossiers/rick-gerson\">Rick Gerson</a> co-founded Alpha Wave "
                "Global (originally Falcon Edge Capital, 2012) with Navroz Udwadia. Alpha Wave&#8217;s "
                "SEC filings identify Lunate Holding RSC Ltd and Chimera Investment LLC — both "
                "UAE sovereign-capital vehicles within the Tahnoun ownership structure — as "
                "co-reporting entities on 13G and Form 4 disclosures [Connection #2899].</p>"
                "<p>During the Trump transition, Gerson occupied a documented back-channel role. "
                "Per Mueller Report Volume I, UAE national security adviser George Nader "
                "introduced Gerson to Kirill Dmitriev (CEO, Russia Direct Investment Fund / RDIF) "
                "in late November 2016. Gerson and Dmitriev co-drafted a US-Russia economic "
                "reconciliation framework; Dmitriev told Gerson the plan had been cleared through "
                "Putin. On January 18, 2017, Gerson hand-delivered the document to "
                "<a href=\"/dossiers/jared-kushner\">Jared Kushner</a>, who forwarded it to Steve "
                "Bannon and Rex Tillerson. Gerson also attended the undisclosed December 2016 "
                "meeting at the Four Seasons New York where MBZ met with Kushner and other Trump "
                "transition officials, and was in the Seychelles during the same period as Erik "
                "Prince&#8217;s meeting with Dmitriev [Connection #2899].</p>"
                "<p>Tahnoun is the UAE National Security Adviser — the same institutional "
                "principal whose subordinate George Nader brokered the Gerson&#8211;Dmitriev "
                "introduction. Whether Nader acted under Tahnoun&#8217;s direction in facilitating "
                "that introduction is not established in public record. What is established is that "
                "Gerson&#8217;s primary commercial capital — Lunate and Chimera — flows from the "
                "Tahnoun-controlled sovereign structure, and that Gerson served as the mechanism "
                "for conveying a Putin-cleared policy proposal to the incoming administration "
                "through the same UAE network [Connection #2899].</p>"
            ),
        },
        {
            "id": "fara-and-precedent",
            "title": "FARA Compliance and Prior UAE Influence Precedents",
            "viz": None,
            "content": (
                "<p>No FARA registration exists for <a href=\"/dossiers/mgx\">MGX</a>, Aryam "
                "Investment 1, <a href=\"/dossiers/g42\">G42</a>, Tahnoun personally, "
                "<a href=\"/dossiers/steve-witkoff\">Steve Witkoff</a>, or "
                "<a href=\"/dossiers/zachary-witkoff\">Zachary Witkoff</a> in connection with the "
                "WLFI transaction or the chip export and crypto regulatory sequence that followed.</p>"
                "<p>The precedent case is <em>United States v. Barrack</em> (EDNY "
                "1:21-cr-00371): Tom Barrack, Trump&#8217;s inaugural committee chair, was charged "
                "with acting as an unregistered UAE foreign agent. His co-defendant Rashid Al "
                "Malik Alshahhi is a UAE national whose case file in CourtListener references "
                "&#8220;Tahnoon,&#8221; connecting Tahnoun to the earlier lobbying operation. "
                "Barrack was acquitted in October 2022; the Alshahhi case remains open. Elliott "
                "Broidy pleaded guilty to FARA conspiracy for UAE and Saudi lobbying in a separate "
                "matter and received a Trump pardon in January 2021. The UAE has multiple "
                "FARA-registered agents for other purposes (Akin Gump, DLA Piper, "
                "Fleishman-Hillard, theGroup DC LLC), but none cover the WLFI&#8211;crypto&#8211;AI "
                "chip nexus [Finding #5065].</p>"
                "<p>The structural pattern across these precedents is consistent: UAE sovereign "
                "capital flows to Trump-connected principals through commercial transaction "
                "mechanisms (political consulting in the Barrack case; crypto investment in the "
                "WLFI case) that may not trigger FARA filing obligations as the statute is "
                "currently interpreted [Finding #5065].</p>"
            ),
        },
    ],
    "open_questions": [
        "The OpenSanctions <code>reg.action</code> flag from the US federal enforcements dataset "
        "indicates Tahnoun is connected to a US federal enforcement matter (first seen 2023-07-18) — "
        "what is that matter, and does it relate to the WLFI transaction, the chip export sequence, "
        "or an earlier enforcement action? [Finding #5065]",

        "The Aryam Investment 1 agreement signed January 16, 2025 acquired 49% of World Liberty "
        "Financial for $500 million. The agreement was signed before the Trump inauguration. Were "
        "any policy commitments regarding chip exports or crypto regulation discussed with Tahnoun "
        "or his representatives during the transition period, and do those discussions overlap with "
        "the WLFI signing date? [Finding #5066]",

        "Steve Witkoff serves as Trump's Middle East Envoy with direct access to Tahnoun, while "
        "his family receives 12.5% of WLFI net protocol revenue from Tahnoun's $500 million "
        "investment. What, if any, ethics review or recusal was conducted regarding Witkoff's UAE "
        "diplomatic role given this financial arrangement? [Connection #2898]",

        "G42's China divestiture — transferring the 42XFund (ByteDance/JD.com stakes) to Lunate "
        "in July 2024 — moved assets laterally within the same Tahnoun-controlled ownership "
        "structure rather than to an arm's-length third party. Did BIS or CFIUS conduct a "
        "beneficial-ownership analysis of the Lunate transfer before clearing the arrangement? "
        "[Finding #3814]",

        "Rick Gerson's Alpha Wave Partners LLC participated in the TikTok USDS restructuring "
        "while Gerson simultaneously served as an Abu Dhabi&#8211;Kushner intermediary under "
        "Mueller investigation scrutiny. Alpha Wave's primary LPs — Lunate and Chimera — are "
        "Tahnoun-controlled. Was any FARA or CFIUS review triggered by Alpha Wave's TikTok role "
        "given these beneficial ownership connections? [Connection #2899]",

        "The MGX&#8211;Binance $2 billion investment used USD1 stablecoin for settlement. WLFI "
        "confirmed USD1 was a deliberate selection over foreign fiat. What communications, if "
        "any, between Tahnoun-controlled entities and WLFI principals preceded the selection of "
        "USD1 as the settlement currency? [Connection #2898]",

        "TeraWulf Inc (WULF) named Tahnoun in an 8-K filed May 9, 2025, and Endeavor Group "
        "Holdings (EDR) named him in a 2021 FWP. What is the nature of his or his entities' "
        "interest in each company — direct ownership, board representation, or debt arrangement? "
        "[Finding #5069]",
    ],
    "applicable_models": [
        "sovereign-commercial-fusion",
        "regulatory-arbitrage",
        "manufactured-dependency",
        "fara-gap-exploitation",
        "lateral-transfer-opacity",
    ],
}


def main():
    with DOSSIER_PATH.open() as f:
        dossier = json.load(f)

    dossier["curation"].update(
        {
            "lead": curation["lead"],
            "system_role": curation["system_role"],
            "sections": curation["sections"],
            "open_questions": curation["open_questions"],
            "applicable_models": curation["applicable_models"],
            "curated_at": curation["curated_at"],
            "key_finding_ids": curation["key_finding_ids"],
        }
    )

    with DOSSIER_PATH.open("w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  lead length: {len(curation['lead'])} chars")
    print(f"  sections: {len(curation['sections'])}")
    print(f"  open_questions: {len(curation['open_questions'])}")
    print(f"  applicable_models: {curation['applicable_models']}")


if __name__ == "__main__":
    main()
