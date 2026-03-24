#!/usr/bin/env python3
"""Write curation fields into content/dossiers/rick-gerson.json."""

import json
from pathlib import Path

DOSSIER = Path("content/dossiers/rick-gerson.json")

with DOSSIER.open() as f:
    data = json.load(f)

# ---------------------------------------------------------------------------
# Curation content
# ---------------------------------------------------------------------------

lead = (
    "<p>Rick Gerson is a hedge fund executive who co-founded Falcon Edge Capital in 2012 — "
    "a Tiger grandcub fund with Julian Robertson lineage — before rebranding the enterprise as "
    "Alpha Wave Global. Alpha Wave's SEC filings name Lunate Holding RSC Ltd and Chimera "
    "Investment LLC, both UAE sovereign-capital vehicles, as co-reporting entities on 13G and "
    "Form 4 disclosures [Finding #5061]. Gerson also carried corporate FARA registration "
    "(#6023) as a foreign agent for the Kingdom of Morocco from March 2011 through March 2012, "
    "operating through Gerson Global Strategic Advisors, LLC at 70 East 55th Street, New York "
    "[Finding #5059]. SEC records confirm him as an insider across at least four vehicles: "
    "Alpha Wave Global LP, Frontier Acquisition Corp, Pioneer Merger Corp, and Golden Falcon "
    "Acquisition Corp [Finding #5060].</p>"
    "<p>During the Trump transition, Gerson occupied a documented back-channel role between "
    "Jared Kushner and Kirill Dmitriev, CEO of the Russian Direct Investment Fund (RDIF). "
    "Per Mueller Report Volume I, UAE national security advisor George Nader introduced "
    "Dmitriev to Gerson in late November 2016 [Finding #5062]. Gerson and Dmitriev then "
    "co-drafted a US-Russia reconciliation proposal — which Dmitriev represented had been "
    "cleared through Putin — and on January 18, 2017, Gerson delivered a copy to Kushner, "
    "who passed it to Steve Bannon and Rex Tillerson [Finding #5062]. NBC News reported "
    "flight manifests placing Gerson in the Seychelles during the same period as Erik "
    "Prince's separate meeting with Dmitriev [Finding #4143]. Mueller's office scrutinized "
    "Gerson's contacts from this period, including his attendance at a secret December 2016 "
    "meeting between MBZ and Trump transition officials at the Four Seasons in New York "
    "[Finding #4143].</p>"
    "<p>UAE officials described Gerson as 'Kushner's guy,' and the Mueller investigation "
    "confirmed that MBZ had a 'long relationship' with Gerson [Finding #4143]. That "
    "relationship has a structural commercial dimension: Alpha Wave's co-filing entities "
    "— Lunate (spun out of Mubadala) and Chimera — sit squarely within the Abu Dhabi "
    "sovereign wealth architecture overseen by Tahnoun bin Zayed al-Nahyan, UAE national "
    "security advisor [Finding #5061]. Gerson's FEC record, sourced to Falcon Edge Capital, "
    "shows contributions exclusively to Democratic candidates through 2020, indicating that "
    "his influence in the Trump orbit operated through personal relationships rather than "
    "party-aligned donations [Finding #5063].</p>"
)

system_role = (
    "Back-channel intermediary between Trump-aligned US political principals and UAE/Russian "
    "sovereign-fund counterparties during the 2016-2017 transition period; hedge fund principal "
    "structurally embedded in UAE sovereign capital through Alpha Wave Global."
)

sections = [
    {
        "id": "background-and-fund-structure",
        "title": "Background and Fund Structure",
        "content": (
            "Gerson built his investment career inside Blue Ridge Capital, the Julian Robertson "
            "Tiger Cub firm, before co-founding Falcon Edge Capital in 2012 alongside Navroz D. "
            "Udwadia and James Minshull. The fund launched with roughly $1.2 billion and returned "
            "28 percent in its first full year [Finding #5064]. He also co-founded Blue Ridge China, "
            "a private equity vehicle, and held a board seat at Orascom Housing Communities in Egypt "
            "[Finding #5064]. LittleSis documents 50 relationships tied to his entity profile, "
            "including a documented social connection to Kirill Dmitriev [Finding #5064]. "
            "Falcon Edge subsequently rebranded as Alpha Wave Global. SEC records show Gerson "
            "(CIK 0001742201) as an insider in four distinct vehicles: Alpha Wave Global LP, "
            "Frontier Acquisition Corp, Pioneer Merger Corp, and Golden Falcon Acquisition Corp — "
            "the latter three all SPACs [Finding #5060]. Alpha Wave Partners LLC filed a Form D "
            "as recently as February 4, 2026 [Finding #5060]."
        ),
        "viz": None,
    },
    {
        "id": "uae-sovereign-capital-ties",
        "title": "UAE Sovereign Capital Ties",
        "content": (
            "Alpha Wave Global LP's SEC filings list Lunate Holding RSC Ltd (CIK 0002009522) and "
            "Chimera Investment LLC (CIK 0002009884) as co-reporting entities on 13G and Form 4 "
            "submissions covering positions in LENZ Therapeutics (March 2024) and Alto Neuroscience "
            "(February 2024) [Finding #5061]. Lunate was spun out of Mubadala Investment Company, "
            "Abu Dhabi's primary sovereign wealth platform. Chimera is a separate Abu Dhabi-listed "
            "investment company. Both sit within the broader capital ecosystem controlled by "
            "Tahnoun bin Zayed al-Nahyan, whose dossier is at "
            "<a href='/dossiers/tahnoun-bin-zayed-al-nahyan'>Tahnoun bin Zayed Al Nahyan</a> "
            "[Finding #5061]. Gerson's board membership on Abu Dhabi Catalyst Partners — a "
            "joint venture between Mubadala and Alpha Wave — further formalizes this structural "
            "relationship [Finding #4143]. The commercial tie is therefore not circumstantial: "
            "UAE sovereign funds and Gerson's fund share mandatory disclosure obligations to the SEC."
        ),
        "viz": "ego_network",
    },
    {
        "id": "transition-period-back-channel",
        "title": "Transition-Period Back-Channel: Nader, Dmitriev, and the Seychelles",
        "content": (
            "The Mueller investigation placed Gerson at the intersection of UAE and Russian "
            "transition-period outreach. George Nader — UAE national security advisor and "
            "convicted sex trafficker — introduced Gerson to Kirill Dmitriev in late November "
            "2016 [Finding #5062]. Nader's dossier is at "
            "<a href='/dossiers/epstein-network'>Epstein Network</a> for context on his broader "
            "role. Dmitriev, CEO of Russia's sovereign RDIF, had been tasked by Moscow to develop "
            "contacts with the incoming Trump administration. Between December 2016 and January "
            "2017, Gerson and Dmitriev co-drafted a US-Russia economic reconciliation framework; "
            "Dmitriev told Gerson the plan had been cleared through Putin [Finding #5062]. On "
            "January 18, 2017 — two days before the inauguration — Gerson hand-delivered the "
            "document to <a href='/dossiers/jared-kushner'>Jared Kushner</a>, who forwarded "
            "copies to Steve Bannon and Rex Tillerson [Finding #5062]. "
            "NBC News flight-manifest reporting placed Gerson in the Seychelles around the same "
            "time <a href='/dossiers/erik-prince'>Erik Prince</a> held his separate meeting with "
            "Dmitriev there, though the two interactions appear to have been parallel rather than "
            "joint [Finding #4143]. Gerson also attended the undisclosed December 2016 meeting at "
            "the Four Seasons New York where MBZ met with Kushner and other Trump transition "
            "officials [Finding #4143]. WhatsApp messages recovered by Mueller showed Nader and "
            "Gerson in contact on January 10, 2017, with Nader sharing a photo of himself with "
            "MBZ taken in Morocco [Finding #5062 / Connection #2897]."
        ),
        "viz": None,
    },
    {
        "id": "fara-and-political-finance",
        "title": "FARA Registration and Political Finance",
        "content": (
            "Prior to his transition-period role, Gerson operated a formally registered foreign "
            "agent practice. Gerson Global Strategic Advisors, LLC filed under FARA as registration "
            "#6023 on March 14, 2011, representing the Kingdom of Morocco, and terminated the "
            "registration on March 30, 2012 [Finding #5059]. The registered address — 70 East 55th "
            "Street, 21st Floor, New York — matches his known business footprint. The filing "
            "subcontracted CRAFT I Media Digital and BLJ Worldwide LTD for Morocco-related work "
            "[Finding #5059]. This predates but contextualizes his subsequent UAE and Russia "
            "transition work as part of a longer pattern of foreign government advisory activity. "
            "FEC contribution records for Richard M. Gerson, employer listed as Falcon Edge Capital, "
            "show donations to Al Lawson for Congress (2020 primary and general cycles; 2017) and "
            "Alejandra Campoverdi for Congress (2017), along with an ActBlue contribution in "
            "December 2016 [Finding #5063]. The contribution record is exclusively Democratic, "
            "which is atypical for someone embedded in the Trump transition network — "
            "Gerson's access operated through personal proximity to "
            "<a href='/dossiers/jared-kushner'>Jared Kushner</a>, not through political donations "
            "[Finding #5063]."
        ),
        "viz": None,
    },
    {
        "id": "network-position",
        "title": "Network Position",
        "content": (
            "Gerson sits at the intersection of three distinct networks that rarely overlap "
            "in documented form: the Kushner family social circle, UAE sovereign capital "
            "infrastructure, and Russian sovereign fund outreach. "
            "<a href='/dossiers/jared-kushner'>Jared Kushner</a> is his primary US political "
            "connection — UAE officials used 'Kushner's guy' as a descriptor, and Gerson's "
            "brother Mark invested in Cadre, the real estate tech platform co-founded by "
            "Josh Kushner [Connection #2478]. "
            "Mohammed bin Zayed (MBZ), UAE President, had a documented 'long relationship' "
            "with Gerson per Mueller findings; the December 2016 Four Seasons meeting was a "
            "trilateral between MBZ, Gerson, and Trump transition principals [Finding #4143]. "
            "Kirill Dmitriev at RDIF used Gerson as the channel for delivering a policy "
            "framework to Kushner; LittleSis independently documents a social relationship "
            "between Gerson (entity 49863) and Dmitriev (entity 345191) [Finding #5062]. "
            "George Nader, who brokered the Dmitriev introduction, also appears in the "
            "Seychelles-era WhatsApp record — making Nader the common node linking Gerson "
            "to both the UAE and Russia channels simultaneously [Finding #5062]. "
            "<a href='/dossiers/tahnoun-bin-zayed-al-nahyan'>Tahnoun bin Zayed Al Nahyan</a>, "
            "as the Abu Dhabi official overseeing Lunate/Mubadala, represents Gerson's "
            "continuing institutional tie to the UAE sovereign apparatus post-transition "
            "[Finding #5061]."
        ),
        "viz": "ego_network",
    },
]

open_questions = [
    "Alpha Wave's Lunate and Chimera co-filings are SEC-disclosed, but the governance terms "
    "of those co-investment arrangements — including any preferential rights, information "
    "sharing, or board representation — are not public. What obligations does Gerson carry "
    "toward UAE sovereign principals under those agreements?",
    "The Mueller Report documents Gerson delivering the Dmitriev reconciliation plan to "
    "Kushner but does not detail whether Gerson received any compensation, direction, or "
    "advance coordination from either Dmitriev or UAE officials for that delivery. Was the "
    "back-channel self-initiated or tasked?",
    "Gerson's FARA registration for Morocco terminated in 2012. Were there subsequent "
    "unregistered advisory relationships with foreign governments, including UAE, that may "
    "have warranted FARA disclosure?",
    "Abu Dhabi Catalyst Partners (Mubadala–Alpha Wave JV) — what is the current portfolio, "
    "size, and governance? Gerson's board membership there is confirmed but the fund's "
    "positions in US technology are not fully documented.",
    "Gerson's SPAC vehicles (Frontier, Pioneer, Golden Falcon) — did any of these complete "
    "a merger, and if so, what were the target companies and their relationships to his "
    "UAE or Russia-adjacent network?",
    "FEC records show no large Trump-cycle contributions from Gerson. Are there state-level "
    "PAC or dark-money contributions not captured by federal FEC search?",
]

applicable_models = [
    {
        "name": "Dual-Hat Intermediary",
        "description": (
            "Gerson simultaneously operates as a commercial investor with documented UAE "
            "sovereign capital ties and as an informal political intermediary for Kushner with "
            "foreign state principals. The two roles are structurally reinforcing: commercial "
            "credibility with sovereign funds creates access; political proximity creates deal "
            "flow. Neither role alone explains the pattern."
        ),
    },
    {
        "name": "Network Broker",
        "description": (
            "Gerson's value to each of his principals derives from exclusive access to the "
            "others. He gave Kushner access to Dmitriev and MBZ; he gave Dmitriev access to "
            "Kushner; he gave UAE officials a trusted channel into the incoming administration. "
            "This is the classic structural broker position — bridging otherwise disconnected "
            "clusters for mutual benefit."
        ),
    },
    {
        "name": "Foreign Government Advisory Pattern",
        "description": (
            "The FARA registration for Morocco (2011-2012), followed by undisclosed UAE and "
            "Russian transition-period facilitation, fits a recurring pattern where formal "
            "foreign-agent registration is used early in a career and later advisory work with "
            "foreign state actors is conducted through informal channels that may not trigger "
            "FARA filing obligations as currently interpreted."
        ),
    },
]

# ---------------------------------------------------------------------------
# Inject into curation block (preserve existing fields, overwrite curated ones)
# ---------------------------------------------------------------------------

data["curation"].update(
    {
        "lead": lead,
        "system_role": system_role,
        "sections": sections,
        "open_questions": open_questions,
        "applicable_models": applicable_models,
    }
)

with DOSSIER.open("w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Wrote curation fields to", DOSSIER)
