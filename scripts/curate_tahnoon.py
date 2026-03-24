#!/usr/bin/env python3
"""
Curation script for Sheikh Tahnoon bin Zayed Al Nahyan dossier.
Writes the `curation` field into content/dossiers/sheikh-tahnoon-bin-zayed-al-nahyan.json.
"""
import json
from pathlib import Path
from datetime import datetime, timezone

DOSSIER_PATH = Path("content/dossiers/sheikh-tahnoon-bin-zayed-al-nahyan.json")

curation = {
    "curated_at": "2026-03-11T20:00:00",
    "key_finding_ids": [
        3756, 3833, 3840, 3848, 3862, 3863, 3979, 3981, 3982,
        4050, 4053, 4057, 4065, 4071, 4094, 4097, 4102, 4106,
        4141, 4143, 4223, 4267, 4271, 4272
    ],
    "lead": (
        "<p>Sheikh Tahnoon bin Zayed Al Nahyan (born December 4, 1968, Abu Dhabi) is the UAE National "
        "Security Adviser and a full brother of UAE President Mohammed bin Zayed Al Nahyan (MBZ). He "
        "chairs Abu Dhabi Investment Authority (ADIA), MGX, G42, International Holding Company (IHC), "
        "ADQ, First Abu Dhabi Bank (FAB), and in February 2026 assumed the chairmanship of Judan "
        "Financial Holding, a newly consolidated entity managing $237 billion across banking, insurance, "
        "and asset management in 13 countries [Finding #4267]. His private vehicle, Royal Group Holding, "
        "is the parent of G42 and controls 61% of IHC. Total assets under his direct or indirect "
        "control have been estimated in press coverage at over $1.5 trillion [Finding #3862].</p>"
        "<p>OpenSanctions classifies Tahnoon as a Politically Exposed Person under both Wikidata and "
        "wd_categories datasets (ID: Q85804913) and flags him under the <code>reg.action</code> tag "
        "from the US federal enforcements dataset, indicating involvement in a US federal enforcement "
        "matter [Finding #4271] [Finding #5065]. He is colloquially known as the &#8220;Spy Sheikh&#8221; "
        "for his oversight of UAE offensive cyber capabilities, including the DarkMatter operation [Finding #3833]. "
        "He appeared in the ICIJ Pandora Papers [Finding #5065]. UK Companies House holds officer appointment "
        "records for him, and LittleSis documents his role as a public official and businessman (profile "
        "ID 447280) [Finding #4272].</p>"
        "<p>Between January 2025 and February 2026, Tahnoon-controlled entities deployed at least $9.5 "
        "billion into five deals whose execution required or directly benefited from Trump administration "
        "regulatory and executive actions: the 49% <a href=\"/dossiers/world-liberty-financial\">World "
        "Liberty Financial</a> acquisition via Aryam Investment 1 ($500M), the $2 billion MGX investment "
        "in Binance settled via the Trump family&#8217;s USD1 stablecoin, the $7 billion MGX commitment "
        "to the Stargate AI joint venture announced at the White House, MGX&#8217;s 15% stake in the "
        "TikTok US restructuring, and MGX&#8217;s participation in two OpenAI funding rounds [Finding #4097]. "
        "Three separate Congressional inquiries were active as of March 2026: a Warren-Merkley Senate "
        "Banking Committee investigation, a Ro Khanna House Select Committee on CCP inquiry, and a "
        "Commerce Department Inspector General review requested by Rep. Kamlager-Dove [Finding #3862].</p>"
    ),
    "system_role": (
        "Tahnoon holds a dual structural position that has no direct Western equivalent: he is "
        "simultaneously the UAE state's principal intelligence authority and the controlling principal "
        "of a sovereign commercial empire spanning AI, crypto, banking, and infrastructure. That fusion "
        "means every commercial transaction he executes carries the policy weight of a government "
        "negotiation, and every intelligence interest he holds is backed by the capital allocation "
        "capacity of a multi-trillion-dollar portfolio. In the US context he functions as the primary "
        "Abu Dhabi counterpart for accessing and shaping the Trump administration's AI chip export "
        "policy, crypto regulatory posture, and TikTok restructuring — with commercial investment "
        "vehicles providing the financial mechanism for that access."
    ),
    "sections": [
        {
            "id": "identity-and-formal-roles",
            "title": "Identity and Formal Roles",
            "content": (
                "<p>Sheikh Tahnoon bin Zayed Al Nahyan was born December 4, 1968, in Abu Dhabi; some "
                "sources cite 1971, but the December 4, 1968 date appears in OpenSanctions primary records "
                "[Finding #4271]. He is the son of UAE founder Sheikh Zayed bin Sultan Al Nahyan and a "
                "full brother of UAE President MBZ. His formal government title is UAE National Security "
                "Adviser. He holds the title of Deputy Ruler of Abu Dhabi [Finding #4267].</p>"
                "<p>His formal institutional chairmanships as of early 2026 include: Abu Dhabi Investment "
                "Authority (ADIA), <a href=\"/dossiers/mgx\">MGX</a> Fund Management Limited, "
                "<a href=\"/dossiers/g42\">G42</a> (Group 42), International Holding Company/IHC (listed "
                "on ADX), ADQ (Abu Dhabi Developmental Holding), First Abu Dhabi Bank, and Judan Financial "
                "Holding (announced February 2026, consolidating Chimera, Lunate, and International "
                "Securities into a 237-billion-AUM financial services group across 13 countries) [Finding #4267]. "
                "He sits on the Mubadala board. His private vehicle, Royal Group Holding, owns 61% of IHC "
                "and 100% of G42 [Finding #3982]. UK Companies House records document officer appointments "
                "associated with his name [Finding #3756].</p>"
                "<p>OpenSanctions flags two distinct Tahnoon Al Nahyan individuals: the subject of this "
                "dossier (DOB 1968-12-04, national security adviser) should not be confused with Tahnoon "
                "bin Mohammed Al Nahyan (born 1942, died 2024), his uncle, who held different posts [Finding #4271].</p>"
            ),
            "viz": None
        },
        {
            "id": "intelligence-and-cyberwarfare",
            "title": "Intelligence and Cyberwarfare",
            "content": (
                "<p>Tahnoon&#8217;s &#8220;Spy Sheikh&#8221; designation reflects his oversight of UAE "
                "offensive cyber programs, including DarkMatter Group (2015&#8211;2019). DarkMatter was "
                "staffed by former NSA, CIA, and Israeli intelligence officers and ran Project Raven, "
                "a UAE surveillance operation that targeted dissidents, journalists, and Americans. "
                "Three former Project Raven contractors &#8212; Baier, Adams, and Gericke &#8212; were "
                "criminally charged by the US Department of Justice under export control laws [Finding #4057].</p>"
                "<p>G42 absorbed substantial DarkMatter personnel and infrastructure as the latter wound "
                "down. <a href=\"/dossiers/g42\">G42</a> CEO Peng Xiao had previously served as CEO of "
                "Pegasus LLC, a DarkMatter subsidiary; Pax AI, a G42 subsidiary, is a rebranding of "
                "Pegasus itself [Finding #4057]. G42 created the ToTok messaging application (originally "
                "branded G42 IM, rebranded July 2019) through Breej Holding &#8212; whose sole director "
                "is Tahnoon&#8217;s adopted son &#8212; and the application was identified by US "
                "intelligence as a UAE mass surveillance tool [Finding #4057]. The CIA opened an "
                "investigative file on Peng Xiao; the House Select Committee on CCP documented that "
                "Xiao operates a network of UAE and PRC-based companies developing dual-use technologies "
                "supporting PRC military-civil fusion [Finding #4065].</p>"
                "<p>G42&#8217;s CIO Zhang Xiaoping maintained simultaneous roles at Yitu Technology, a "
                "US-sanctioned Chinese AI and surveillance firm, while G42 held Microsoft&#8217;s $1.5 "
                "billion investment and a WLFI board seat [Finding #4057]. These connections fed the "
                "primary US national security concern: that advanced Nvidia chips supplied to G42 or "
                "MGX could be diverted into Chinese military-civil fusion programs [Finding #3840].</p>"
            ),
            "viz": None
        },
        {
            "id": "entity-network",
            "title": "Entity Network and Corporate Architecture",
            "content": (
                "<p>Tahnoon controls his commercial empire through three overlapping ownership chains. "
                "The first is his private vehicle: Royal Group Holding owns G42 outright and holds 61% "
                "of IHC [Finding #3982]. IHC (Abu Dhabi Exchange-listed, $250 billion conglomerate) "
                "contains 2PointZero, a $27 billion holding company that itself holds Chimera Investment "
                "LLC and Lunate Capital. IHC&#8217;s share price grew approximately 42,000% between "
                "2019 and 2024 [Finding #3862]. Judan Financial Holding, announced February 2026 with "
                "Tahnoon as chairman, consolidates Chimera, Lunate, and International Securities into "
                "the new structure across 13 countries with $237 billion AUM [Finding #4267].</p>"
                "<p>The second chain is sovereign: Tahnoon chairs ADIA (multi-trillion sovereign wealth "
                "fund), ADQ (state development holding), and FAB (First Abu Dhabi Bank). Mubadala "
                "Investment Company, the sovereign wealth fund, co-founded <a href=\"/dossiers/mgx\">MGX</a> "
                "with G42 in March 2024; Tahnoon chairs MGX and Mubadala vice-chairman Khaldoon Khalifa "
                "Al Mubarak serves as MGX Vice Chairman [Finding #3831].</p>"
                "<p>The third chain is the investment intermediary tier: Aryam Investment 1 (the WLFI "
                "acquisition vehicle) is incorporated as two identically named entities, one in Delaware "
                "and one in Abu Dhabi. The Delaware entity is managed by <a href=\"/dossiers/martin-edelman\">Martin Edelman</a> "
                "(G42 General Counsel) and Peng Xiao (G42 CEO), both of whom also serve on the MGX board "
                "[Finding #3979]. Alpha Wave Global &#8212; nominally independent but whose primary "
                "capital derives from Tahnoon&#8217;s sovereign vehicles (IHC/Alpha Dhabi is sole LP "
                "of the $10 billion Alpha Wave Ventures II fund) &#8212; participated in the TikTok "
                "USDS restructuring through Alpha Wave Partners LLC [Finding #4141].</p>"
                "<p>A notable internal transfer occurred in 2024: the 42XFund, a G42-originated "
                "$10 billion Shanghai-based fund holding stakes in ByteDance and JD.com, was transferred "
                "to Lunate (IHC subsidiary) in July 2024, formally satisfying G42&#8217;s divestiture "
                "commitment to the Biden administration and Commerce Department Bureau of Industry and "
                "Security while keeping the economic interest within the Tahnoon ownership structure "
                "[Finding #4053] [Finding #4082]. Lunate thereby held ByteDance equity while MGX "
                "simultaneously held 15% of TikTok USDS JV &#8212; Tahnoon entities on both sides "
                "of the TikTok restructuring [Finding #4071].</p>"
            ),
            "viz": None
        },
        {
            "id": "trump-financial-nexus",
            "title": "Financial Transactions with Trump-Connected Ventures",
            "content": (
                "<p>Five confirmed financial transactions link Tahnoon-controlled entities to ventures "
                "whose regulatory fortunes were directly shaped by the Trump administration between "
                "January 2025 and February 2026.</p>"
                "<p><strong>WLFI acquisition (January 2025).</strong> Four days before inauguration, "
                "<a href=\"/dossiers/world-liberty-financial\">World Liberty Financial</a> signed an "
                "agreement with Aryam Investment 1 giving Tahnoon&#8217;s entity a 49% stake for "
                "$500 million. Eric Trump signed for WLFI; <a href=\"/dossiers/martin-edelman\">Martin "
                "Edelman</a> and Peng Xiao signed for Aryam [Finding #3981]. Approximately $187 million "
                "flowed to Trump family entities from this transaction [Finding #3840]. Aryam thereby "
                "secured two of five WLFI board seats, occupied by Edelman and Xiao, without public "
                "disclosure [Finding #3981]. In May 2025, the Trump administration approved the annual "
                "sale of 500,000 advanced Nvidia AI chips to the UAE &#8212; reversing the Biden "
                "administration&#8217;s refusal on the same request &#8212; with 100,000 chips allocated "
                "directly to G42 [Finding #3840]. Senator Warren characterized the arrangement as "
                "&#8220;corruption, plain and simple&#8221; [Finding #3840].</p>"
                "<p><strong>MGX-Binance investment (March 2025).</strong> MGX invested $2 billion in "
                "Binance, the world&#8217;s largest cryptocurrency exchange, with the transaction "
                "settled using the USD1 stablecoin issued by World Liberty Financial. WLFI confirmed "
                "that MGX and Binance would have used foreign fiat currency had USD1 not been available, "
                "making the use of the Trump family&#8217;s stablecoin a deliberate selection [Finding "
                "#4002]. Binance founder Changpeng Zhao (CZ) was pardoned by President Trump in October "
                "2025 [Finding #3862]. Senators Warren and Merkley sent document-preservation demands "
                "to MGX and Binance asking whether Trump or WLFI affiliates influenced the USD1 "
                "selection [Finding #4002].</p>"
                "<p><strong>Stargate commitment (January 2025).</strong> MGX committed $7 billion to "
                "Stargate LLC, the $500 billion AI infrastructure joint venture announced at the White "
                "House on January 21, 2025, alongside SoftBank ($19 billion), OpenAI ($19 billion), "
                "and Oracle ($7 billion) [Finding #4307]. <a href=\"/dossiers/g42\">G42</a> serves as "
                "a key operator for Stargate UAE, launched in May 2025 with Sam Altman &#8212; who "
                "described Tahnoon as a &#8220;dear personal friend&#8221; [Finding #3771]. The "
                "Stargate JV requires ongoing US government forbearance from antitrust enforcement "
                "and continued willingness to export advanced AI chips to the UAE to be viable "
                "[Finding #4320].</p>"
                "<p><strong>TikTok USDS restructuring (September 2025 &#8211; January 2026).</strong> "
                "Trump approved a TikTok US restructuring in September 2025 in which Oracle, Silver "
                "Lake, and MGX collectively held approximately 45% of the new US entity [Finding "
                "#3845]. Alpha Wave Partners LLC (Rick Gerson, backed primarily by Tahnoon&#8217;s "
                "IHC) participated as a separate investor in the same restructuring [Finding #4140]. "
                "Because Lunate (IHC subsidiary) continued to hold ByteDance equity through the "
                "42XFund, Tahnoon entities held economic interest on both the ByteDance parent side "
                "and the TikTok US restructured side simultaneously [Finding #4071].</p>"
                "<p><strong>OpenAI rounds (October 2025 and February 2026).</strong> MGX participated "
                "in OpenAI&#8217;s $6.6 billion funding round at a $500 billion valuation in October "
                "2025 and co-led the $30 billion round in February 2026 [Finding #4267]. MGX also "
                "participated in the Anthropic $30 billion funding round in February 2026 alongside "
                "Coatue and GIC [Finding #4984].</p>"
            ),
            "viz": None
        },
        {
            "id": "intermediaries-and-personnel",
            "title": "Key Intermediaries and Personnel",
            "content": (
                "<p><strong><a href=\"/dossiers/martin-edelman\">Martin Edelman</a></strong> is General "
                "Counsel of G42, a board member of MGX, an adviser to Mubadala, and Of Counsel at Paul "
                "Hastings LLP. He served as lead negotiator alongside Peng Xiao, Tahnoon, and UAE "
                "Ambassador Al Otaiba in the Biden-era discussions with the Bureau of Industry and "
                "Security over G42&#8217;s China divestiture [Finding #3857]. He signed both the "
                "Aryam-WLFI agreement and holds a WLFI board seat alongside Peng Xiao. He also "
                "appears in an Epstein calendar from December 2016, and in a 2017 Epstein email list "
                "labeled &#8220;list for bannon steve&#8221; &#8212; a connection that predates his "
                "current Tahnoon roles by several years [Finding #4102].</p>"
                "<p><strong>Peng Xiao</strong> is Group CEO of <a href=\"/dossiers/g42\">G42</a> and "
                "a co-signatory of the WLFI agreement. He previously ran Pegasus LLC, a DarkMatter "
                "subsidiary, renounced his US citizenship for Emirati citizenship, and is the subject "
                "of a CIA classified report. Pegasus Technology Beijing, where Xiao serves as executive "
                "director, is a G42 Chinese subsidiary [Finding #4050].</p>"
                "<p><strong>Khaldoon Khalifa Al Mubarak</strong> is Vice Chairman of MGX and Mubadala "
                "CEO. He is the same Khaldoon Al Mubarak to whom MBZ delegated digital currency matters "
                "in October 2017, as documented in Epstein network emails from EFTA02586299 [Finding "
                "#3745]. He bridges the Epstein-era Abu Dhabi institutional interface and the current "
                "MGX-WLFI structure [Finding #3863].</p>"
                "<p><strong>Rick Gerson</strong> co-founded Alpha Wave Global (originally Falcon Edge "
                "Capital, 2012) with Navroz Udwadia. Alpha Wave&#8217;s primary capital comes from "
                "Tahnoon&#8217;s IHC/Chimera/Lunate vehicles [Finding #4141]. Gerson attended a "
                "secret December 2016 meeting between Trump transition officials (including "
                "<a href=\"/dossiers/jared-kushner\">Jared Kushner</a>) and Crown Prince MBZ at "
                "the Four Seasons in New York, was in the Seychelles in January 2017 during the "
                "Erik Prince-Kirill Dmitriev meeting investigated by Robert Mueller, and came under "
                "Mueller investigation scrutiny for those contacts [Finding #4143]. UAE officials "
                "describe him as &#8220;Kushner&#8217;s guy&#8221; and he serves as a bridge "
                "between both the Abu Dhabi channel and the Saudi PIF-Kushner channel [Finding "
                "#4143].</p>"
            ),
            "viz": None
        },
        {
            "id": "fara-and-regulatory-gaps",
            "title": "FARA Compliance and Regulatory Posture",
            "content": (
                "<p>No FARA registration exists for MGX, Aryam Investment 1, G42, Tahnoon personally, "
                "<a href=\"/dossiers/steve-witkoff\">Steve Witkoff</a>, or <a href=\"/dossiers/zachary-witkoff\">Zach Witkoff</a> "
                "in connection with the WLFI transaction or subsequent chip export and crypto regulatory "
                "actions [Finding #3774]. The UAE has multiple FARA-registered agents for other purposes "
                "(Akin Gump, DLA Piper, Fleishman-Hillard, theGroup DC LLC for the UAE Ministry of "
                "Investment as of December 2025), but none cover the WLFI-crypto-AI chip nexus "
                "[Finding #3774].</p>"
                "<p>The precedent case is United States v. Barrack (EDNY 1:21-cr-00371): Tom Barrack, "
                "Trump&#8217;s inaugural committee chair, was charged with acting as an unregistered "
                "UAE foreign agent; his co-defendant Rashid Al Malik Alshahhi is a UAE national whose "
                "case file in CourtListener references &#8220;Tahnoon,&#8221; connecting Tahnoon to "
                "the earlier lobbying operation [Finding #3807]. Barrack was acquitted in October 2022; "
                "the Alshahhi case remains open [Finding #3807]. Elliott Broidy pleaded guilty to FARA "
                "conspiracy for UAE and Saudi lobbying in a separate matter and received a Trump pardon "
                "in January 2021 [Finding #3801]. The WLFI channel uses commercial crypto investment "
                "rather than traditional political consulting as the transaction mechanism, but the "
                "structural pattern &#8212; UAE sovereign capital flowing to Trump-connected individuals "
                "outside FARA &#8212; mirrors both precedents [Finding #3801].</p>"
                "<p>Steve Witkoff&#8217;s dual position is of particular relevance to FARA analysis: "
                "as Trump&#8217;s Middle East Envoy he holds direct diplomatic access to Tahnoon, "
                "while his family simultaneously receives 12.5% of WLFI net protocol revenue from "
                "Tahnoon&#8217;s $500 million investment [Finding #3768]. No recusal or ethics "
                "disclosure has been identified for Witkoff specific to his UAE diplomatic role "
                "and the WLFI revenue stream [Finding #3768].</p>"
            ),
            "viz": None
        },
        {
            "id": "china-entanglement",
            "title": "China Entanglement and G42 Divestiture",
            "content": (
                "<p>G42&#8217;s China ties were the primary basis for Biden administration concerns "
                "about Nvidia chip exports to the UAE. G42 had partnered with BGI Genomics (Chinese "
                "genomics company with military ties), co-invested with Sinopharm in COVID vaccine "
                "manufacturing, operated two direct Chinese subsidiaries run by G42 CIO Zhang Xiaoping "
                "(who simultaneously held a role at US-sanctioned Yitu Technology), and launched the "
                "$10 billion 42XFund with ByteDance and JD.com stakes from a Shanghai base [Finding "
                "#4060].</p>"
                "<p>In February 2024, G42 announced divestiture of all Chinese investments as a "
                "condition of Microsoft&#8217;s $1.5 billion investment and informal Commerce "
                "Department clearance. However, the 42XFund was transferred to Lunate (under IHC, "
                "which is majority-owned by Tahnoon&#8217;s Royal Group) in July 2024 rather than "
                "sold to an unrelated third party [Finding #4082]. The transfer was lateral within "
                "the same ownership structure: G42 and Lunate are both ultimately controlled by "
                "Tahnoon [Finding #4053]. A CFIUS review of G42&#8217;s stake in Cerebras Systems "
                "(an AI chip company) delayed Cerebras&#8217; IPO until March 2025, when CFIUS "
                "cleared the structure only after G42&#8217;s stake was converted to non-voting "
                "shares [Finding #4094].</p>"
                "<p>The Trump administration&#8217;s May 2025 decision to approve 500,000 advanced "
                "Nvidia chips annually to the UAE &#8212; with 100,000 going directly to G42 &#8212; "
                "reversed the Biden administration&#8217;s denial of the same request. The reversal "
                "came four months after Tahnoon&#8217;s $500 million WLFI investment and amid active "
                "Congressional scrutiny of the sequence [Finding #3840]. Representative Ro Khanna "
                "stated publicly that UAE officials were lobbying the Trump administration to reduce "
                "export controls while simultaneously buying a stake in the Trump family&#8217;s "
                "business [Finding #3768].</p>"
            ),
            "viz": None
        },
        {
            "id": "historical-context",
            "title": "Historical Context: Epstein-Era Abu Dhabi Channels",
            "content": (
                "<p>The Abu Dhabi institutional infrastructure now channeling capital through MGX "
                "and WLFI intersected with the Epstein network in documented ways nearly a decade "
                "earlier. A October 2017 Epstein email (EFTA02586299) shows David Stern reporting "
                "to Epstein that &#8220;MBZ handed [digital currency matters] to Khaldoon&#8221; &#8212; "
                "the same Khaldoon Al Mubarak who is now MGX Vice Chairman [Finding #3745]. The same "
                "email seeks to broker a meeting between Leon Black (Apollo) and the Chairman of "
                "Abu Dhabi Global Markets [Finding #3745].</p>"
                "<p>Ian Osborne, who sat on the Mubadala board, is documented in Epstein records "
                "coordinating tech investments during the same period. Martin Edelman appears in an "
                "Epstein calendar from December 2016 and in a 2017 email list [Finding #4102]. The "
                "continuity is institutional: the same sovereign architecture &#8212; MBZ, Mubadala, "
                "Khaldoon &#8212; that Epstein&#8217;s network sought to access on digital currency "
                "and investment brokering in 2017 is the same architecture behind MGX&#8217;s 2025 "
                "crypto and AI infrastructure transactions [Finding #3863].</p>"
                "<p>Separately, Sultan Bin Sulayem (DP World chairman), who was an Epstein-era "
                "UAE connector, was FARA-registered through a firm employing Ari Ben-Menashe, an "
                "Israeli intelligence figure [Finding #3801]. The pattern of UAE sovereign influence "
                "operations flowing through Trump-connected individuals outside FARA &#8212; from "
                "Barrack (2016&#8211;2018) to Broidy to the current WLFI channel &#8212; spans "
                "multiple administrations and has accelerated in scale with each iteration [Finding #3801].</p>"
            ),
            "viz": None
        }
    ],
    "open_questions": [
        "What specific policy commitments, if any, were made by Trump administration officials to UAE counterparts during Tahnoon's meetings with Trump and senior US officials between November 2024 and inauguration, and do those discussions overlap with the January 2025 WLFI signing date? [Finding #3756]",
        "The OpenSanctions <code>reg.action</code> flag from the US federal enforcements dataset indicates Tahnoon is connected to a US federal enforcement matter — what is that matter, and does it relate to the WLFI transaction, the chip export sequence, or an earlier action? [Finding #5065]",
        "The 42XFund transfer from G42 to Lunate in July 2024 was described as a China divestiture to the Commerce Department — did BIS or CFIUS review whether the transfer constituted a genuine arm's-length divestiture given that both entities are controlled by the same beneficial owner? [Finding #4053] [Finding #4082]",
        "Rick Gerson's Alpha Wave entities participated in the TikTok USDS restructuring through Alpha Wave Partners LLC while Gerson simultaneously served as an Abu Dhabi-Kushner intermediary under Mueller scrutiny — was any FARA or national security review triggered by Alpha Wave's TikTok role? [Finding #4143] [Finding #4140]",
        "Aryam Investment 1 has unnamed co-investors alongside Tahnoon as ultimate beneficial owner — who are those co-investors, and do they include other UAE or Gulf sovereign entities? [Finding #3979]",
        "What, if any, conflict-of-interest review was conducted within the Commerce Department before the May 2025 decision to approve 500,000 Nvidia chips for UAE, given the prior WLFI investment and the active Congressional inquiries into the sequence? [Finding #3840] [Finding #3862]",
        "Judan Financial Holding, announced February 2026, consolidates Chimera, Lunate, and International Securities into a 13-country $237 billion AUM structure under Tahnoon's chairmanship — what jurisdictions are included, and does the structure create new opacity for tracing the 42XFund&#8217;s ByteDance holdings? [Finding #4267]"
    ],
    "applicable_models": [
        "sovereign-commercial-fusion",
        "regulatory-arbitrage",
        "manufactured-dependency",
        "parallel-financial-system",
        "lateral-transfer-opacity"
    ]
}

def main():
    with open(DOSSIER_PATH, "r") as f:
        dossier = json.load(f)

    dossier["curation"] = curation

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  lead length: {len(curation['lead'])} chars")
    print(f"  sections: {len(curation['sections'])}")
    print(f"  open_questions: {len(curation['open_questions'])}")
    print(f"  applicable_models: {curation['applicable_models']}")

if __name__ == "__main__":
    main()
