#!/usr/bin/env python3
"""
Curation script for Raafat Alsabbagh dossier.
Writes the `curation` field with lead, system_role, sections, open_questions, and applicable_models.
"""

import json
from pathlib import Path
from datetime import datetime, timezone

DOSSIER_PATH = Path("content/dossiers/raafat-alsabbagh.json")


def build_curation() -> dict:
    lead = (
        '<p>Raafat Alsabbagh is the Saudi contact who arranged Jeffrey Epstein\'s November 2016 trip to Riyadh '
        'and served as Epstein\'s primary point of access to the Saudi royal court. Email correspondence in the '
        'DOJ document set (<a href="#efta-EFTA02353684">EFTA02353684</a>, '
        '<a href="#efta-EFTA02461943">EFTA02461943</a>, '
        '<a href="#efta-EFTA02668843">EFTA02668843</a>, '
        '<a href="#efta-EFTA02459671">EFTA02459671</a>) documents a relationship from May 2016 through at least '
        'January 2018 in which Alsabbagh introduced Epstein to Saudi government officials, facilitated his travel '
        'to Riyadh, and received a stream of U.S. financial and political intelligence that Epstein curated and '
        'forwarded to his Gulf contacts as a group. No public biography for Alsabbagh has been located; his identity '
        'is known solely from the Epstein corpus.</p>'
    )

    system_role = (
        "Saudi facilitator and access provider. Alsabbagh's documented function in the Epstein network "
        "was to translate Epstein's relationship capital — introductions to former White House counsel, "
        "independent prosecutors, and MIT researchers — into access to the Saudi royal court, specifically "
        "to an unnamed prince referred to as 'the prince' and to MBS. Reciprocally, Alsabbagh provided "
        "Epstein with the institutional endorsement needed to travel to Riyadh and use MBS as a reference "
        "credential in other Gulf contexts. He operated as one node in a four-person Saudi/Gulf tier "
        "(Alsabbagh, Aziza Alahmadi, Anas Alrasheed, Sultan Bin Sulayem) that Epstein grouped and addressed "
        "as a coherent unit in his contact architecture."
    )

    sections = [
        {
            "id": "initial-contact-and-relationship-arc",
            "title": "Initial Contact and Relationship Arc",
            "content": (
                "<p>The documentary record begins on May 17, 2016, when Alsabbagh sent Epstein a thank-you "
                "note after visiting Epstein's Manhattan townhouse: <em>\"Thank you very much for your "
                "hospitality. It was my great pleasure to meet you at your beautiful house specially the (GYM) "
                "area. I am looking forward to continue our coversation and laughters in New York.\"</em> "
                "(<a href=\"#efta-EFTA02353684\">EFTA02353684</a>.) This first-meeting note establishes "
                "Alsabbagh as a new contact, not a longstanding associate.</p>"
                "<p>Within two weeks Epstein moved to deepen the relationship by offering Alsabbagh access "
                "to U.S. legal and political networks. In June 2016 Epstein told Alsabbagh he could introduce "
                "him to <em>\"obamas former counsel for the past 5 years\"</em> — Kathryn Ruemmler, then a "
                "partner at Latham &amp; Watkins — describing her as <em>\"a good friend if you would like "
                "to meet. she is in wash today\"</em> (<a href=\"#efta-EFTA02461943\">EFTA02461943</a>). "
                "The same month Epstein extended the offer to Alsabbagh's Saudi principal: <em>\"If Mohammed "
                "really wants to see the future, after seeing the past in Washington with Obama, we should take "
                "him to see the Laboratory at MIT. advanced robotics. Artificial Intelligence.\"</em> "
                "(<a href=\"#efta-EFTA02639071\">EFTA02639071</a>, dated June 2, 2016.) The unnamed Mohammed "
                "is the same prince referenced later as 'the prince' in Epstein's market-tutoring offer, and "
                "consistent with documentary context, likely MBS.</p>"
                "<p>By October 2016 — five months into the relationship — Epstein had arranged for Ruemmler to "
                "meet both Alsabbagh and <a href=\"/dossiers/aziza-alahmadi\">Aziza Alahmadi</a> simultaneously: "
                "<em>\"kathy will see you both in new york on the weekend\"</em> "
                "(<a href=\"#efta-EFTA02447907\">EFTA02447907</a>). On October 2, 2016, Epstein formalized "
                "the introduction in writing: <em>\"kathy - raafat, raafat - kathy\"</em>, with Alahmadi CC'd "
                "(<a href=\"#efta-EFTA02449625\">EFTA02449625</a>).</p>"
                "<p>After Epstein's Riyadh visit in November 2016 — which Alsabbagh arranged "
                "(<a href=\"#efta-EFTA02448271\">EFTA02448271</a>: Epstein had been requesting an official "
                "invitation letter since October 18, noting it would be <em>\"the fourth time I arrange my "
                "schedule\"</em>) — Epstein introduced Alsabbagh to <a href=\"/dossiers/ken-starr\">Ken Starr</a> "
                "on November 26, 2016: <em>\"Ken-Raafat, Raafat-Ken\"</em> "
                "(<a href=\"#efta-EFTA02668843\">EFTA02668843</a>). Starr was then a Kirkland &amp; Ellis "
                "partner and former Independent Counsel who had also been recruited into Epstein's own criminal "
                "defense. Introducing Alsabbagh to Starr immediately after the Riyadh trip follows the same "
                "pattern as the Ruemmler introduction: each Saudi visit was followed by an escalated credential "
                "offer from Epstein.</p>"
            )
        },
        {
            "id": "riyadh-trip-and-prince-access",
            "title": "The Riyadh Trip and Prince Access",
            "content": (
                "<p>The November 2016 Riyadh visit is the clearest evidence of Alsabbagh's functional role. "
                "Epstein had been pursuing the trip since at least October 18, 2016, and Alsabbagh was the "
                "person responsible for obtaining the formal invitation "
                "(<a href=\"#efta-EFTA02448271\">EFTA02448271</a>). The trip occurred during the week of the "
                "U.S. presidential election, a period in which the Gulf state thread of the Epstein network "
                "was at its highest documented activity level — 30% of all findings in the October–December 2016 "
                "period belong to that thread.</p>"
                "<p>In a separate undated email, Epstein wrote to Alsabbagh that <em>\"the prince might want "
                "to set aside some real time. to take private tutoring from me, on markets how they work. "
                "i can explain everything in easy to understand terms, totally private so no embarassment.\"</em> "
                "(<a href=\"#efta-EFTA02459671\">EFTA02459671</a>.) This offer — private, confidential "
                "financial tutoring for a Saudi royal — was Epstein's core value proposition to the Saudi "
                "side: access to sophisticated U.S. financial intelligence delivered outside any institutional "
                "channel.</p>"
                "<p>By October 2017, Alsabbagh's role as Epstein's credential with the Saudi court was "
                "sufficiently established that Epstein used him by name when pitching himself to the UAE "
                "ruler. In a message to intermediary David Stern on October 3, 2017, Epstein wrote: "
                "<em>\"i suggest you tell MBZ that he should meet with me about digital currency, he can "
                "check my name with mohammed bin rashid from dubai (sultan suleiman,) or MBS "
                "(raafat friend)\"</em> "
                "(<a href=\"#efta-EFTA02664708\">EFTA02664708</a>). Epstein was offering MBZ a reference "
                "check — and the reference was Alsabbagh's relationship, not Alsabbagh himself. This indicates "
                "Epstein believed his connection to MBS ran through Alsabbagh and was credible enough to use "
                "as a door-opener with a different Gulf head of state.</p>"
            )
        },
        {
            "id": "paired-conduit-with-alahmadi",
            "title": "Paired Conduit with Aziza Alahmadi",
            "content": (
                "<p>Across ten DOJ documents, Epstein addressed Alsabbagh and "
                "<a href=\"/dossiers/aziza-alahmadi\">Aziza Alahmadi</a> as co-recipients on the same emails, "
                "treating them as a unit rather than independent contacts. The content of those emails was "
                "consistently Saudi financial and political intelligence: Saudi bond issuance warnings "
                "(<a href=\"#efta-EFTA02455101\">EFTA02455101</a>: <em>\"I understand the kingdom is coming "
                "to market with approx [X] billion in bonds. in september. politics will play a great role. "
                "careful\"</em>), Saudi bankruptcy risk "
                "(<a href=\"#efta-EFTA02447885\">EFTA02447885</a>), 9/11 families' lawsuit against Saudi Arabia "
                "(<a href=\"#efta-EFTA02656241\">EFTA02656241</a>), a Doha bank CEO's commentary on Saudi debt "
                "(<a href=\"#efta-EFTA02449910\">EFTA02449910</a>), and Tom Barrack's role in the Trump "
                "inauguration (<a href=\"#efta-EFTA02663993\">EFTA02663993</a>, "
                "<a href=\"#efta-EFTA02664708\">EFTA02664708</a>).</p>"
                "<p>The Barrack inauguration emails are the clearest example of the intelligence function. On "
                "January 6, 2017, Sultan Bin Sulayem (DP World chairman, UAE) asked Epstein whether to accept "
                "Barrack's inauguration invitation. Epstein replied with a CNN article, then the same day sent "
                "that article to Alahmadi and Alsabbagh. Three days later he sent a Los Angeles Times piece "
                "on Barrack and the inauguration to Alahmadi, Alsabbagh, and "
                "<a href=\"/dossiers/terje-rod-larsen\">Terje Rod-Larsen</a> as a group. Epstein was "
                "distributing U.S. political intelligence simultaneously to a Saudi pair and a Norwegian "
                "diplomat — the same article, the same day, to different national audiences.</p>"
                "<p>The pairing of Alsabbagh and Alahmadi was not accidental. Alahmadi handled logistics "
                "(she followed up on Epstein's Riyadh trip from the Saudi side, asking about a tent for "
                "Epstein's island on November 16, 2016: <em>\"hope you enjoyed your staying in Riyadh\"</em> "
                "(<a href=\"#efta-EFTA02325450\">EFTA02325450</a>)), while Alsabbagh held the relationship "
                "with the royal court and arranged the formal invitation. The two functions — institutional "
                "access and logistical support — were divided between them but directed at the same target.</p>"
            )
        },
        {
            "id": "connections-and-network-position",
            "title": "Connections and Network Position",
            "content": (
                "<p>Alsabbagh's documented connections run through Epstein to five identifiable individuals "
                "and one structural network position.</p>"
                "<p><strong><a href=\"/dossiers/jeffrey-epstein\">Jeffrey Epstein</a></strong> — primary "
                "relationship, ten months of documented email correspondence (May 2016–January 2017 in the "
                "DOJ corpus, with continued grouping through January 2018). Epstein was the active party in "
                "the relationship: he offered introductions, forwarded intelligence, proposed market tutoring, "
                "and used Alsabbagh's credential with the Saudi court in other contexts.</p>"
                "<p><strong><a href=\"/dossiers/aziza-alahmadi\">Aziza Alahmadi</a></strong> — Saudi "
                "co-recipient across ten documents. Alsabbagh and Alahmadi were addressed as a unit and appear "
                "to have had overlapping but distinct roles within the same access channel "
                "(<a href=\"#efta-EFTA02449625\">EFTA02449625</a>).</p>"
                "<p><strong><a href=\"/dossiers/kathryn-ruemmler\">Kathryn Ruemmler</a></strong> — introduced "
                "by Epstein in June 2016 and formally connected on October 2, 2016 with Alahmadi CC'd. "
                "Ruemmler was then a Latham &amp; Watkins partner and former Obama White House Counsel. "
                "The introduction placed her at the nexus of Epstein's Saudi, UAE, and Qatar client brokering "
                "simultaneously: she was introduced to Alsabbagh (Saudi) in October 2016, offered the Qatari "
                "PM HBJ as a client in June 2017, and connected to George Nader (UAE-aligned Mueller witness) "
                "by early 2018 (<a href=\"#efta-EFTA02449625\">EFTA02449625</a>).</p>"
                "<p><strong><a href=\"/dossiers/ken-starr\">Ken Starr</a></strong> — introduced on November 26, "
                "2016, the day after Epstein's return from Riyadh. Starr was a Kirkland &amp; Ellis partner "
                "who had also served on Epstein's own defense team. His introduction to Alsabbagh immediately "
                "post-Riyadh follows the same credential-escalation pattern as the Ruemmler introduction "
                "(<a href=\"#efta-EFTA02668843\">EFTA02668843</a>).</p>"
                "<p><strong><a href=\"/dossiers/jabor-al-thani\">Jabor Al Thani</a></strong> — connected "
                "through shared Gulf network groupings. Alsabbagh and Jabor appear together in Epstein's "
                "January 2018 'radical breakthrough' contacts list alongside Sultan Bin Sulayem and Anas "
                "Alrasheed, and both received signed copies of Michael Wolff's <em>Fire and Fury</em> "
                "dispatched from Paris in January 2018 "
                "(<a href=\"#efta-EFTA02540965\">EFTA02540965</a>). The connection to Jabor is documented "
                "via <a href=\"#efta-EFTA02236300\">EFTA02236300</a>.</p>"
                "<p><strong>Anas Alrasheed</strong> — co-listed with Alsabbagh in the Gulf quartet grouping. "
                "Alrasheed is documented elsewhere as Epstein's KSA political touchline and Qatar blockade "
                "intelligence source. The two men appear to have operated in parallel Saudi channels without "
                "direct documented contact with each other "
                "(<a href=\"#efta-EFTA02540965\">EFTA02540965</a>).</p>"
                "<p><strong><a href=\"/dossiers/terje-rod-larsen\">Terje Rod-Larsen</a></strong> — co-recipient "
                "of the January 9, 2017 Tom Barrack inauguration email alongside Alahmadi and Alsabbagh. The "
                "three-country distribution (Saudi Arabia, Norway) of a single U.S. political intelligence "
                "item in one day is the clearest documentation of Epstein's simultaneous multi-channel "
                "distribution function (<a href=\"#efta-EFTA02664708\">EFTA02664708</a>).</p>"
            )
        },
        {
            "id": "the-beauty-queen-exchange",
            "title": "The September 2016 Exchange",
            "content": (
                "<p>On September 23, 2016, Alsabbagh forwarded Epstein an article about a Russian beauty queen "
                "who had auctioned her virginity in Dubai. Epstein replied: <em>\"finally you send me "
                "something worthwhile. this is a russian bond offering\"</em> "
                "(<a href=\"#efta-EFTA02450831\">EFTA02450831</a>).</p>"
                "<p>This exchange is documented here factually, not editorially. Its evidentiary value is "
                "narrow but specific: it shows Alsabbagh was aware of the type of content Epstein found "
                "interesting and chose to send it to him. Epstein's response — framing the article in "
                "financial terms — is characteristic of his documented communication style. What the exchange "
                "does not establish is whether Alsabbagh understood its implications beyond forwarding a "
                "salacious news item, or whether the exchange reflects ongoing communication about women "
                "more broadly. It is a single documented instance.</p>"
            )
        },
        {
            "id": "fara-status",
            "title": "FARA Status",
            "content": (
                "<p>A search of the Foreign Agents Registration Act database returned zero registrations for "
                "Raafat Alsabbagh. He is one of four Epstein Saudi/Gulf intermediaries — alongside Alahmadi, "
                "Alrasheed, and Jabor Al Thani — with no FARA filing despite documented facilitation of "
                "meetings between Epstein and Saudi government officials, arrangement of official travel to "
                "Riyadh, and receipt of real-time U.S. financial and political intelligence forwarded to a "
                "Saudi audience. Whether FARA would have been required depends on whether Alsabbagh was acting "
                "at the direction or control of a foreign government or official — a legal determination not "
                "resolvable from the email corpus alone. The documented absence is consistent with the broader "
                "pattern across the Epstein network: zero FARA registrations for any of the fifteen-plus "
                "documented foreign intermediaries spanning six countries "
                "(<a href=\"#finding-1238\">Finding #1238</a>).</p>"
            )
        }
    ]

    open_questions = [
        {
            "question": "Identity of 'the prince'",
            "detail": (
                "Epstein offered private market tutoring to 'the prince' via Alsabbagh "
                "(EFTA02459671) and referenced MBS as 'raafat friend' when pitching himself to MBZ "
                "(EFTA02664708). The June 2016 email about MIT labs names 'Mohammed.' Whether these "
                "references all point to MBS or to different Saudi royals cannot be determined from "
                "the corpus. LEAD #1001 is open on this question."
            )
        },
        {
            "question": "Alsabbagh's institutional affiliation",
            "detail": (
                "No public record locates Alsabbagh in any corporate registry, government roster, or "
                "media database. His role — obtaining official Riyadh invitation letters, providing "
                "access to 'the prince,' and serving as a recognized Saudi credential for Epstein — "
                "is consistent with a government-adjacent facilitator, but his actual position is "
                "undocumented. Saudi government directories and corporate registries have not been "
                "searched under his name."
            )
        },
        {
            "question": "Nature of the Alahmadi-Alsabbagh relationship",
            "detail": (
                "The two were consistently paired as co-recipients but appear to have had distinct "
                "roles. Whether they knew each other independently of Epstein, and whether their "
                "pairing reflects a pre-existing Saudi institutional connection or a relationship "
                "Epstein assembled, is not established in the documentary record."
            )
        },
        {
            "question": "Continuity of the relationship post-2017",
            "detail": (
                "The last direct Alsabbagh email in the DOJ corpus is January 2017. He appears by "
                "name in the January 2018 contacts list (EFTA02540965) and receives a copy of "
                "Fire and Fury in January 2018, but no email traffic involving him after "
                "the Barrack inauguration email has been located. Whether the relationship "
                "continued is unknown."
            )
        },
        {
            "question": "Whether Ruemmler or Starr subsequently engaged Alsabbagh",
            "detail": (
                "Both introductions are documented as Epstein brokering the initial connection. "
                "No evidence in the corpus establishes whether either attorney subsequently took "
                "Alsabbagh or his Saudi principal as a client."
            )
        }
    ]

    applicable_models = [
        {
            "model": "Access Broker",
            "description": (
                "Alsabbagh's function is the clearest documented example of a Saudi-side access broker "
                "in the Epstein network. He held institutional standing with the Saudi royal court, "
                "converted that standing into formal invitations for Epstein, and in return received "
                "introductions to U.S. legal and political figures. The exchange is symmetrical and "
                "transactional: Epstein's credential portfolio (Ruemmler, Starr, MIT, Harvard) "
                "for Alsabbagh's Saudi access portfolio."
            )
        },
        {
            "model": "Paired-Node Distribution",
            "description": (
                "The Alahmadi-Alsabbagh pairing illustrates a pattern visible elsewhere in the "
                "Epstein network: a single country or institution is represented by two contacts "
                "with complementary functions — one holding the principal relationship (Alsabbagh, "
                "royal access) and one handling logistics (Alahmadi, invitation letters, tent "
                "procurement). The pair is addressed as a unit by the network center."
            )
        },
        {
            "model": "Intelligence Aggregation and Distribution",
            "description": (
                "Epstein's role with Alsabbagh was not purely social. The ten group-emails document "
                "a pattern of Epstein curating U.S. financial and political news — bond issuance "
                "warnings, 9/11 lawsuit risk, inauguration intelligence — and distributing it to "
                "Saudi contacts. This is distinguishable from ordinary news forwarding by its "
                "targeting: the content was consistently Saudi-relevant, the recipients were "
                "consistently Saudi, and the commentary Epstein added (e.g., 'politics will play "
                "a great role. careful') was advisory in tone."
            )
        },
        {
            "model": "Credential Laundering",
            "description": (
                "Each Epstein introduction to Alsabbagh deployed a different U.S. credential: "
                "former White House Counsel (Ruemmler), former Independent Counsel and K&E partner "
                "(Starr), MIT AI laboratories (tech access). These introductions built Epstein's "
                "value to the Saudi side incrementally. The October 2017 use of Alsabbagh's "
                "relationship as a reference when approaching MBZ — 'check my name with MBS "
                "(raafat friend)' — shows the credential was successfully laundered into a "
                "reusable reference across Gulf jurisdictions."
            )
        }
    ]

    return {
        "lead": lead,
        "system_role": system_role,
        "sections": sections,
        "open_questions": open_questions,
        "applicable_models": applicable_models,
        "curated_at": datetime.now(timezone.utc).isoformat()
    }


def main():
    dossier = json.loads(DOSSIER_PATH.read_text())
    dossier["curation"] = build_curation()
    DOSSIER_PATH.write_text(json.dumps(dossier, indent=2, ensure_ascii=False))
    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  Sections: {len(dossier['curation']['sections'])}")
    print(f"  Open questions: {len(dossier['curation']['open_questions'])}")
    print(f"  Applicable models: {len(dossier['curation']['applicable_models'])}")


if __name__ == "__main__":
    main()
