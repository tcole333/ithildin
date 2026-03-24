#!/usr/bin/env python3
"""Write curation fields into content/dossiers/oleg-boyko.json"""

import json
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/oleg-boyko.json")

with open(DOSSIER_PATH) as f:
    dossier = json.load(f)

curation = dossier.setdefault("curation", {})

# ── system_role ──────────────────────────────────────────────────────────────
curation["system_role"] = (
    "Oleg Boyko is a Russian billionaire and chairman of Finstar Financial Group, "
    "an investment vehicle managing approximately USD 2 billion in assets across "
    "gaming, consumer lending, and media in 30-plus countries. He is notable in this "
    "investigation as the intermediate owner of Trump Tower Unit 63A from 1994 to 2009 "
    "\u2014 a transaction personally executed by Donald Trump \u2014 and as a figure named "
    "in the US Treasury CAATSA Putin List (January 2018) and sanctioned by Ukraine, "
    "Australia, Poland, and (temporarily) Canada. Polish ABW intelligence assessed that "
    "his casino operations may serve to launder funds for both organized crime and Russian "
    "intelligence services."
)

# ── lead ─────────────────────────────────────────────────────────────────────
curation["lead"] = (
    "<p>Oleg Boyko is a Russian businessman whose career spans high-stakes banking "
    "during the Yeltsin era, Eastern European gambling, consumer microlending, and "
    "media. He is the chairman of Finstar Financial Group, which he established in 1996 "
    "and which now claims approximately USD 2 billion in assets under management across "
    "30-plus countries. In 1994, Donald Trump personally sold Boyko Unit 63A at Trump "
    "Tower, a transaction documented by the New Republic\u2019s investigation into Russian "
    "financial activity in the building. Boyko held the unit for fifteen years before "
    "selling it in 2009 to Vadim Trincher for USD 5 million. That apartment subsequently "
    "became the command center for the Taiwanchik-Trincher Organization, a Russian-American "
    "gambling and money-laundering ring that federal prosecutors documented as handling over "
    "USD 100 million \u2014 operating three floors below Trump\u2019s penthouse residence "
    "[Finding #4052, #4078].</p>"

    "<p>Boyko appears on the US Treasury CAATSA Putin List published in January 2018, "
    "placing him among individuals identified as close to the Russian government. He has "
    "been sanctioned by Ukraine, Australia, and Poland, with Poland\u2019s December 2024 "
    "order including an asset freeze. Canada sanctioned him and subsequently lifted those "
    "sanctions in November 2023. The Polish ABW intelligence service assessed directly "
    "that Boyko has connections to organized crime and Russian intelligence services, and "
    "that his casinos may serve as vehicles for laundering funds from both [Finding #4215]. "
    "The Senate Intelligence Committee separately reported ties between Boyko and the Russian "
    "government, intelligence services, and organized crime [Finding #4052].</p>"

    "<p>A secondary chain of association connects Boyko to the Epstein investigation. Boyko "
    "co-founded Ritzio Entertainment and Fintech Ventures with Serguei Kouzmine. Kouzmine "
    "subsequently co-founded QWAVE Capital with Serguei Beloussov. QWAVE\u2019s publicist "
    "was Masha Drokova, who also served as Jeffrey Epstein\u2019s publicist. Drokova appears "
    "1,627 times in DOJ Epstein file releases, and FBI Washington Field Office\u2019s "
    "Transnational Organized Crime (Eastern Hemisphere) squad investigated her under "
    "Operation Trip Knot. These linkages are documented in FBI document EFTA00129096, an "
    "April 2025 ARMS Reach vetting memo [Finding #4217].</p>"
)

# ── sections ─────────────────────────────────────────────────────────────────
curation["sections"] = [
    {
        "id": "trump-tower-chain-of-title",
        "title": "Trump Tower: Chain of Title for Unit 63A",
        "content": (
            "<p>The documented sequence for Trump Tower Unit 63A spans three transactions "
            "over fifteen years. In 1994, Donald Trump personally sold the unit to Oleg Boyko. "
            "The transaction was personally handled by Trump, not through an intermediary, "
            "a detail documented by the New Republic investigation into Russian financial "
            "activity in the building. Boyko held the unit without notable public activity "
            "until 2009, when he sold it to Vadim Trincher for USD 5 million [Finding #4052].</p>"

            "<p>Trincher and his son Illya then used the apartment as the operational base "
            "for the Taiwanchik-Trincher Organization, a Russian-American gambling and "
            "money-laundering enterprise that federal prosecutors documented as having "
            "processed over USD 100 million. The organization operated in coordination "
            "with Alimzhan Tokhtakhounov, a vor-v-zakone figure based in Russia who "
            "provided criminal authority while Trincher ran US operations. <a href=\"/dossiers/anatoly-golubchik\">Anatoly Golubchik</a> "
            "was a co-defendant and co-principal, sentenced alongside Trincher to five years "
            "in April 2014. A parallel operation \u2014 the Nahmad-Trincher Organization "
            "\u2014 was co-led by Illya Trincher and <a href=\"/dossiers/nahmad-family\">Hillel Nahmad</a> "
            "from the 51st floor of the same building [Finding #4052].</p>"

            "<p>The chain of title establishes Boyko as the intermediary owner between "
            "Trump and Trincher. No record has been found establishing that Boyko knew "
            "in 1994 what Trincher would do with the apartment fifteen years later, nor "
            "that the 2009 sale was anything other than a private real estate transaction. "
            "The structural significance is that the same residential unit passed from a "
            "transaction personally executed by Trump to a figure the Senate Intelligence "
            "Committee described as connected to Russian government, intelligence services, "
            "and organized crime \u2014 who then sold it to a person convicted of operating "
            "one of the largest organized crime gambling operations ever prosecuted in the "
            "Southern District of New York [Finding #4078].</p>"
        ),
        "viz": "ego_network",
    },
    {
        "id": "sanctions-and-intelligence-assessments",
        "title": "Sanctions and Intelligence Assessments",
        "content": (
            "<p>Boyko\u2019s sanctions profile is extensive and multi-jurisdictional. The US "
            "Treasury included him in the CAATSA Section 241 \u201cPutin List\u201d published "
            "January 2018, a statutory report listing oligarchs and senior political figures "
            "with close ties to the Russian government. The list did not itself impose "
            "sanctions but established a public record of US government assessment. Ukraine "
            "and Australia subsequently sanctioned him. Poland sanctioned Boyko in December "
            "2024 with an accompanying asset freeze, citing Polish ABW (Internal Security "
            "Agency) intelligence findings. Canada sanctioned him and then lifted those "
            "sanctions in November 2023 [Finding #4215].</p>"

            "<p>The Polish ABW assessment is the most specific public intelligence judgment "
            "in the record. It states that Boyko has connections to organized crime and "
            "Russian intelligence services, and that his casino operations may serve to "
            "launder funds from both. The assessment is cited in the Polish Ministry of "
            "Interior and Administration sanctions decision (DPP-WTPZ.0272.69.2024) and "
            "is cross-referenced in OpenSanctions entity Q4090404. The Senate Intelligence "
            "Committee separately described Boyko\u2019s ties to the Russian government, "
            "intelligence services, and organized crime in its Russia investigation report "
            "[Finding #4215, #4078].</p>"

            "<p>These assessments are government-generated intelligence judgments, not "
            "judicial findings. No US criminal charge against Boyko has been documented "
            "in the source record. The distinction matters: the ABW and Senate Intel "
            "characterizations reflect intelligence agency conclusions rather than "
            "prosecuted conduct. Boyko has disputed the characterizations underlying "
            "some sanctions proceedings [Finding #4215].</p>"
        ),
        "viz": None,
    },
    {
        "id": "finstar-financial-group",
        "title": "Finstar Financial Group: Structure and Holdings",
        "content": (
            "<p>Boyko established Finstar Financial Group in 1996. As of the investigation "
            "date, the firm claims approximately USD 2 billion in assets under management "
            "across 30-plus countries, with offices in Cyprus, Serbia, and the UAE. "
            "Finstar\u2019s principal holdings cluster around three business lines: gaming, "
            "consumer lending, and media [Finding #4216].</p>"

            "<p>In gaming, Finstar controls Ritzio Entertainment, which Boyko co-founded "
            "with Serguei Kouzmine and which operates as the largest Eastern European gaming "
            "chain by outlet count, with over 1,000 locations. In Ukraine, where Boyko faces "
            "sanctions, the Vulkan Casino brand \u2014 Ritzio\u2019s primary consumer brand "
            "\u2014 is operated under license by Maksym Krippa and a partner, who received "
            "rights from Boyko to manage the casino websites. Krippa is thus a licensed "
            "operator of Boyko\u2019s brand in a country that has sanctioned Boyko "
            "[Finding #4216, Connection #2540].</p>"

            "<p>In consumer lending, Finstar controls 4Finance, a Latvian-incorporated "
            "consumer lender. 4Finance\u2019s US operations \u2014 conducted through "
            "4Finance US Holding Inc., a Delaware entity, operating via North Star Finance "
            "LLC \u2014 used the tribal sovereignty of the Fort Belknap Indian Community "
            "(Montana) and the Lac du Flambeau Band of Lake Superior Chippewa Indians "
            "(Wisconsin) to offer payday loans to US consumers. This structure, "
            "\u201ctribal lending,\u201d exploits sovereign immunity doctrines to avoid "
            "state usury caps, a practice that multiple states and the Consumer Financial "
            "Protection Bureau have challenged in separate proceedings [Finding #4216].</p>"

            "<p>In media, Boyko co-owned Fashion TV (FTV), a global cable and satellite "
            "channel. His co-ownership through FTV BVI Ltd. is confirmed by US federal "
            "court records in <em>Fashion One Television LLC v. Fashion TV Programmgesellschaft "
            "MbH</em> (SDNY 1:16-cv-05328), where Boyko, Finstar Financial Group LLC, "
            "and FTV BVI Ltd. appear as defendants. A separate US trademark action, "
            "<em>Boyko v. Kondratiev</em> (D.Ariz. 2:23-cv-01186), lists Finstar-Holding "
            "LLC as a co-plaintiff, confirming Finstar\u2019s active US corporate presence "
            "[Finding #4222, #4221].</p>"

            "<p>In sports finance, Boyko invested in 777 Partners, a Miami-based firm that "
            "acquired minority stakes in multiple football clubs including Sevilla FC. In 2024, "
            "Boyko demanded 777 Partners shares in Sevilla FC as collateral for a loan he "
            "had extended. 777 Partners subsequently collapsed amid federal criminal fraud "
            "charges against co-founder Josh Wander and CFO Damien Alfalla for an alleged "
            "USD 500 million scheme to defraud lenders [Finding #4221].</p>"
        ),
        "viz": None,
    },
    {
        "id": "kouzmine-qwave-drokova-chain",
        "title": "Kouzmine, QWAVE Capital, and the Drokova Connection",
        "content": (
            "<p>The connection between Boyko and the Epstein investigation runs through a "
            "chain of professional relationships documented in FBI vetting materials. Boyko "
            "co-founded Ritzio Entertainment and Fintech Ventures with Serguei Kouzmine, "
            "who subsequently ran operations within Finstar\u2019s portfolio. Kouzmine then "
            "co-founded QWAVE Capital \u2014 a quantum computing-focused venture fund \u2014 "
            "with Serguei Beloussov in December 2012, serving as Managing Partner while "
            "Beloussov served as Venture Partner. QWAVE Capital is identified in FBI "
            "document EFTA00129096 (an April 2025 ARMS Reach vetting memo) as having "
            "retained <a href=\"/dossiers/masha-drokova\">Masha Drokova</a> as its publicist "
            "[Finding #4217].</p>"

            "<p>Drokova served simultaneously as Jeffrey Epstein\u2019s publicist. She appears "
            "1,627 times across DOJ Epstein file releases. The FBI Washington Field Office\u2019s "
            "Transnational Organized Crime (Eastern Hemisphere) squad investigated Drokova "
            "under Operation Trip Knot, the details of which are not fully declassified. "
            "The chain \u2014 Boyko \u2192 Kouzmine \u2192 QWAVE Capital \u2192 Drokova "
            "\u2192 Epstein \u2014 is a two-step professional relationship documented in "
            "primary FBI materials, not media inference [Finding #4217].</p>"

            "<p>Kouzmine\u2019s later role as President of Constructor University (2025), "
            "where Beloussov is the primary sponsor, extends the documented relationship "
            "between Boyko\u2019s former co-founder and Beloussov\u2019s institutional network. "
            "No direct documented relationship between Boyko and Drokova, or between Boyko "
            "and Epstein, has been found in the current record. The significance of the chain "
            "is structural: it identifies Boyko as a first-degree associate of a figure who "
            "had documented professional proximity to Epstein and who was investigated by "
            "the FBI\u2019s transnational organized crime unit [Finding #4217, Connection #2560].</p>"
        ),
        "viz": None,
    },
]

# ── open_questions ────────────────────────────────────────────────────────────
curation["open_questions"] = [
    (
        "What, if any, due diligence did Donald Trump or the Trump Organization perform "
        "on Oleg Boyko prior to the 1994 personal sale of Unit 63A, and are any internal "
        "communications about that transaction preserved in Trump Organization records "
        "produced in subsequent litigation?"
    ),
    (
        "On what basis did Canada impose and then lift its sanctions against Boyko "
        "in November 2023 \u2014 was the lifting driven by a successful legal challenge, "
        "a change in evidentiary assessment, or political discretion, and has Canada "
        "published its reasoning?"
    ),
    (
        "4Finance\u2019s tribal-lending structure via Fort Belknap and Lac du Flambeau "
        "has been the subject of state and federal regulatory challenges; what is the "
        "current legal status of North Star Finance LLC and whether Finstar retains "
        "any active US consumer lending operations?"
    ),
    (
        "What specific financial terms governed Boyko\u2019s loan to 777 Partners, and "
        "has Boyko filed a creditor claim in 777 Partners\u2019 insolvency proceedings "
        "seeking recovery of the principal?"
    ),
    (
        "FBI document EFTA00129096 establishes Drokova\u2019s role as QWAVE\u2019s "
        "publicist and her investigation under Operation Trip Knot; what is the current "
        "disposition of that investigation, and does any portion of Operation Trip Knot "
        "touch Kouzmine or Finstar entities directly?"
    ),
    (
        "Maksym Krippa\u2019s license to operate the Vulkan Casino brand in Ukraine "
        "while Boyko is sanctioned by Ukraine raises questions about the terms of "
        "that license and whether Ukrainian regulators have reviewed the arrangement "
        "in light of the sanctions; what is the current regulatory status of Krippa\u2019s "
        "Vulkan license?"
    ),
]

# ── applicable_models ────────────────────────────────────────────────────────
curation["applicable_models"] = [
    "jurisdictional-arbitrage",
    "parallel-financial-system",
    "enabler-gradient",
    "offshore-opacity",
]

dossier["curation"] = curation

with open(DOSSIER_PATH, "w") as f:
    json.dump(dossier, f, indent=2, ensure_ascii=False)

print("Curation written successfully.")
