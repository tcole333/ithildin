#!/usr/bin/env python3
"""
Curation script for Boris Nikolic dossier.
Writes the 'curation' block to content/dossiers/boris-nikolic.json.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/boris-nikolic.json")


CURATION = {
    "lead": (
        "<p>Boris Nikolic is a Harvard-trained physician (MD, PhD) who served as Chief Science Advisor "
        "to Bill Gates and led scientific strategy at bgC3, Gates's private research office. "
        "Between 2010 and 2019 he occupied a documented position at the intersection of three power nodes "
        "that define the Epstein network: the Gates philanthropic apparatus, the Epstein social circuit, "
        "and the Tech-&amp;-Life-Sciences investment world. "
        "Email evidence from the EFTA corpus places him as the person who arranged the Gates–Epstein "
        "relationship, as the conduit for Epstein's IPI grant brokering inside the Gates Foundation, "
        "and as the link between Epstein and Kimbal Musk across a five-year period. "
        "Two days before Epstein's death in August 2019, Nikolic was named first-choice successor trustee "
        "of the $577 million 1953 Trust. He declined to serve and publicly described the designation as a "
        "surprise. <em>All evidence is derived from the Epstein Federal Task Force Archive (EFTA) and "
        "publicly reported court filings; confidence levels follow platform conventions.</em></p>"
    ),

    "system_role": (
        "Science-sector bridge between Jeffrey Epstein and the Bill Gates network; "
        "principal intermediary connecting Epstein to Kimbal Musk; "
        "first-named successor trustee of the Epstein estate."
    ),

    "sections": [
        {
            "id": "gates-science-advisor",
            "title": "Role at bgC3 and the Gates Foundation",
            "body": (
                "<p>Nikolic's formal relationship with Bill Gates ran through bgC3, Gates's private "
                "think tank and research office, where Nikolic held the title of Chief Science Advisor. "
                "That role gave him direct access to Gates Foundation grant processes and positioned him "
                "to broker introductions to the Foundation's scientific program officers.</p>"

                "<p>The Gates–Epstein connection ran through Nikolic from the start. "
                "A December 2010 email from Gates to Nikolic—confirmed in the EFTA corpus—reads: "
                "<em>\"I wont be able to do the dinner with Jeff Epstein. I was looking forward to the dinner. "
                "Nathan had agreed with you that I would enjoy meeting with him.\"</em> "
                "This establishes Nikolic as the person who initially arranged meetings between Gates and Epstein "
                "(Finding #282, EFTA corpus, confidence: high).</p>"

                "<p>By September 2013, a formal financial partnership agreement between Gates and Nikolic was "
                "executed—effective September 3, 2013—covering co-investments in Foundation Medicine (FMI) and "
                "ResearchGate, with Nikolic serving as an observer board member at FMI. "
                "The partnership was extended to September 3, 2018 by amendment dated October 6, 2015. "
                "This agreement was present in Epstein's email corpus, meaning Nikolic or Gates shared it with "
                "Epstein directly. "
                "Source: <cite data-ref=\"EFTA02685163\">EFTA02685163</cite> "
                "(Finding #284, confidence: high).</p>"

                "<p>Eight days after that partnership was executed, on September 11, 2013, Nikolic attended the "
                "IPI–Gates Foundation meeting at the Gates campus in Redmond, listed on the agenda as "
                "\"Scientific Advisor.\" That meeting concerned the International Peace Institute's polio "
                "eradication grant proposal, which became grant OPP1096058 ($2.5 million). "
                "Three months earlier, on June 10, 2013, Epstein had forwarded IPI bank wiring instructions to "
                "Nikolic with the note: <em>\"These are the wiring instructions for the 5 million from the "
                "foundatoin. for IPI.\"</em> Nikolic was therefore the person inside the Gates organization "
                "who received the donation routing instructions that Epstein was brokering. "
                "Sources: <cite data-ref=\"EFTA02725118\">EFTA02725118</cite> (meeting), "
                "EFTA01891138 (IPI Vienna query). "
                "(Findings #285, #238, #73; confidence: high.)</p>"
            ),
        },
        {
            "id": "epstein-personal-relationship",
            "title": "Personal Relationship with Epstein",
            "body": (
                "<p>The EFTA corpus documents Nikolic's presence inside Epstein's personal world across at "
                "least eight years, beginning no later than April 2011 and continuing through at least mid-2018.</p>"

                "<p>In April 2011, Nikolic transmitted an NDA for 9 East 71st Street—Epstein's Manhattan "
                "mansion—to Epstein. He appeared on email chains alongside Sarah Kellen, Epstein's personal "
                "assistant. He traveled on Epstein's private jet alongside Karyna Shuliak "
                "(Lesley Groff to Nikolic, August 6, 2013: <em>\"The tail # Of Jeffrey's plane is N9091=. "
                "Karyna can update you tomorrow on exact ti=ing since she will be with...\"</em>, "
                "source: <cite data-ref=\"EFTA02336502\">EFTA02336502</cite>). "
                "He met Epstein regularly at the 71st Street residence, including a confirmed breakfast on "
                "July 11, 2015 (<cite data-ref=\"EFTA02497227\">EFTA02497227</cite>) and an afternoon "
                "appointment on January 30, 2017—the same day Leon Black met Epstein at 5 pm and Deutsche "
                "Bank bankers met at 4 pm.</p>"

                "<p>In January 2013, Nikolic emailed Epstein: <em>\"Yesterday, I wanted to punch a guy "
                "yesterday that does not like you. From Highbridge capital.\"</em> Epstein replied: "
                "<em>\"better than punching him, get his name.\"</em> "
                "(<cite data-ref=\"EFTA01908297\">EFTA01908297</cite>, Finding #699, confidence: confirmed.) "
                "Nikolic was defending Epstein's reputation in financial circles and reporting hostility back "
                "to him; Epstein's immediate instinct was intelligence-gathering.</p>"

                "<p>In June 2015, Nikolic introduced Ilya Ponomarev—then a Russian State Duma member in "
                "exile—to Epstein, writing: <em>\"I wont be able to do the dinner with Jeff Epstein... "
                "with my next email I will introduce you to Ilya Ponamarev. He is a member of Duma and "
                "perhaps the most...\"</em> "
                "(<cite data-ref=\"EFTA02360267\">EFTA02360267</cite>, Finding #303, confidence: medium). "
                "The nature of Epstein's interest in a dissident Russian parliamentarian is unestablished "
                "in the record.</p>"

                "<p>In April 2018, Epstein forwarded Nikolic a Forbes article about Charlie Sheen's $10 million "
                "blackmail tax-deduction claim "
                "(<cite data-ref=\"EFTA02476126\">EFTA02476126</cite>, Finding #536, confidence: high). "
                "The same article was sent to Kathy Ruemmler. The distribution list places Nikolic among "
                "Epstein's innermost legal and financial confidants.</p>"

                "<p>Nikolic also appears on Epstein's WEF Davos participant lists (2011, 2013) and is "
                "documented as attending a June 2017 Harvard lunch with Epstein and Joi Ito at Hanscom Field, "
                "consistent with the recurring Cambridge academic-circuit itineraries Epstein ran from "
                "Teterboro to Hanscom "
                "(<cite data-ref=\"EFTA02214958\">EFTA02214958</cite>, Finding #1400, confidence: confirmed).</p>"
            ),
        },
        {
            "id": "kimbal-musk-intermediary",
            "title": "Intermediary Between Epstein and Kimbal Musk",
            "body": (
                "<p>Across a documented five-year span, Nikolic served as the channel between "
                "<a href=\"/dossiers/kimbal-musk\">Kimbal Musk</a> and Epstein. "
                "The pattern is consistent and directional: Nikolic brought Kimbal into Epstein's orbit "
                "and reported information about Kimbal back to Epstein.</p>"

                "<p><strong>September 2012 — Gala invitation.</strong> Kimbal emailed Nikolic on September 21, "
                "2012: <em>\"Let Jeffrey and his friends know they are invited tomorrow night. Four Seasons. "
                "7pm. Black tie.\"</em> Nikolic was the routing node. "
                "(<cite data-ref=\"EFTA02560007\">EFTA02560007</cite>, Finding #4508, confidence: confirmed.)</p>"

                "<p><strong>October 2012 — Lunch at 71st Street.</strong> Nikolic was among those invited to "
                "the October 7 lunch at Epstein's Manhattan residence where Kimbal Musk was a confirmed "
                "attendee. Logistics were coordinated between Epstein's assistant Lesley Groff and Kimbal's "
                "assistant Karla Shaw. "
                "(<cite data-ref=\"EFTA02565784\">EFTA02565784</cite>, Finding #4509, confidence: confirmed.)</p>"

                "<p><strong>February 2013 — Divorce disclosure forwarded.</strong> Kimbal emailed Nikolic on "
                "February 9, 2013: <em>\"I'm now divorced! Free to live my life. Talking to [name redacted] "
                "again.\"</em> Nikolic forwarded this to Epstein on February 13. The forwarding of personal "
                "relationship news to Epstein is a direct action, not an inference. "
                "(<cite data-ref=\"EFTA02358398\">EFTA02358398</cite>, Finding #4511, confidence: confirmed.)</p>"

                "<p><strong>April 2017 — TED scouting report.</strong> Nikolic told Epstein at TED: "
                "<em>\"Kimbal, elon, and few new interesting for you are around here.\"</em> "
                "This is a report identifying persons of potential interest to Epstein at a venue where "
                "Nikolic had access to both the Musk brothers and others. "
                "(Finding #4512, confidence: high.)</p>"

                "<p>Read together with Finding #4535—that Epstein held $5 million in preferred stock in "
                "Jawbone/AliphCom and that Nikolic facilitated that connection—the pattern is one of "
                "sustained network cultivation running through Nikolic as the connective node between "
                "Epstein's financial interests and Silicon Valley principals.</p>"
            ),
        },
        {
            "id": "epstein-trust",
            "title": "Named in the Epstein Estate",
            "body": (
                "<p>The 1953 Trust—named for Epstein's birth year—was executed on August 8, 2019, "
                "two days before Epstein's death. "
                "Primary trustees were Darren Indyke and Richard Kahn. "
                "The trust document states: "
                "<em>\"BORIS NIKOLIC shall be appointed to fill any such vacancy, and if he is unwilling or "
                "unable to serve, BARNABY MARSH shall be appointed to fill any such vacancy.\"</em> "
                "(<cite data-ref=\"EFTA01266204\">EFTA01266204</cite>, Finding #287, confidence: confirmed.) "
                "The estate was valued at $577,672,654.</p>"

                "<p>Nikolic publicly stated he was shocked by the designation and declined to serve. "
                "The full succession chain in the trust—Indyke/Kahn (primary), Nikolic (first alternate), "
                "<a href=\"/dossiers/barnaby-marsh\">Barnaby Marsh</a> (second), Anthony Barrett (third), "
                "Kathy Ruemmler (fourth), David Mitchell (fifth), Steve Hanson (sixth), Eva Dubin (seventh)—"
                "places Nikolic ahead of Ruemmler, who had been Epstein's lawyer for five years and was "
                "named trustee of a separate trust instrument. "
                "The ordering is a document of relative trust, not a legal accident. "
                "Finding #378, confidence: confirmed.</p>"

                "<p>The trust's execution two days before Epstein's death—along with its naming of a "
                "scientist rather than a lawyer as first alternate—has not been explained by any party "
                "in the public record.</p>"
            ),
        },
        {
            "id": "network-position",
            "title": "Network Position and Cross-Links",
            "body": (
                "<p>Nikolic's documented connections span four distinct sub-networks within the broader "
                "Epstein graph:</p>"

                "<p><strong>Gates Foundation science program.</strong> Via bgC3, Nikolic had access to the "
                "Foundation's scientific advisory processes and grant pipelines. He co-invested with Gates "
                "personally (Foundation Medicine, ResearchGate) while simultaneously carrying Epstein's IPI "
                "grant brokering into Gates Foundation meetings. "
                "See: <a href=\"/dossiers/jeffrey-epstein\">Jeffrey Epstein</a>, "
                "<a href=\"/dossiers/international-peace-institute\">International Peace Institute</a>.</p>"

                "<p><strong>Silicon Valley investment circuit.</strong> Nikolic appeared on Epstein's March 2012 "
                "MONEY seminar invite list alongside Marc Andreessen, Jeff Bezos, Sergey Brin, Bill Gates, "
                "Michael Milken, Larry Page, Eric Schmidt, Jim Simons, Jes Staley, and "
                "<a href=\"/dossiers/peter-thiel\">Peter Thiel</a> "
                "(<cite data-ref=\"EFTA02760\">EFTA02760</cite>, Finding #2760, confidence: high). "
                "He also appears on the September 19, 2014 Epstein schedule alongside Thiel at noon, "
                "Nikolic at 2 pm, Jabor Y. (Al Thani) at 3 pm, and Terje Rod-Larsen at 8 pm—a schedule "
                "that also names Bill Burns, Kathy Ruemmler, and Leon Black as tentative attendees "
                "(<cite data-ref=\"EFTA02377982\">EFTA02377982</cite>, Finding #2761).</p>"

                "<p><strong>Kimbal Musk channel.</strong> Documented separately above; see "
                "<a href=\"/dossiers/kimbal-musk\">Kimbal Musk</a>.</p>"

                "<p><strong>Apollo / financial sector.</strong> Nikolic shared the January 9, 2014 "
                "Epstein calendar with <a href=\"/dossiers/joshua-harris\">Joshua Harris</a> "
                "(Harris at 11:15 am, Nikolic at 5 pm), placing him in the same day's schedule as "
                "a core Apollo partner during the period of Apollo's heaviest Epstein engagement "
                "(<cite data-ref=\"EFTA02578836\">EFTA02578836</cite>, Finding #1284).</p>"

                "<p><strong>WEF and international policy.</strong> Nikolic provided Epstein with WEF Davos "
                "participant lists for 2011 and 2013, and brokered Nicole Junkermann's WEF nomination "
                "alongside Larry Summers (Finding #160, confidence: medium / synthesis).</p>"
            ),
        },
    ],

    "open_questions": [
        (
            "What was the nature of Nikolic's relationship with Ilya Ponomarev, the Russian Duma member "
            "he introduced to Epstein in June 2015? Ponomarev was the only Duma member to vote against "
            "the annexation of Crimea and was living in exile. The introduction is documented "
            "(EFTA02360267) but no further correspondence between Epstein and Ponomarev has been "
            "identified in the corpus."
        ),
        (
            "Why was Nikolic designated first alternate trustee of the 1953 Trust in preference to "
            "Epstein's lawyers (Ruemmler appears fourth)? The trust was executed forty-eight hours "
            "before Epstein's death. No explanation has appeared in court filings, public statements, "
            "or the email corpus."
        ),
        (
            "Nikolic's full scope at bgC3 is not documented in the corpus. What other Gates Foundation "
            "grant processes did he participate in during 2011–2019 beyond the IPI polio grant? The "
            "Gates–Nikolic investment partnership (Foundation Medicine, ResearchGate) and Nikolic's "
            "bgC3 role overlapped precisely with Epstein's most intensive engagement with Gates."
        ),
        (
            "The Jawbone/AliphCom connection (Finding #4535: Epstein held $5M in preferred stock, "
            "Nikolic facilitated) is sparsely documented. What was Nikolic's specific role in that "
            "introduction? Were there other technology investments that followed the same pattern?"
        ),
        (
            "Nikolic's April 2018 receipt of the Charlie Sheen blackmail article from Epstein "
            "(EFTA02476126) places him among a small group of Epstein confidants who received that "
            "communication. What was the conversational context, and are there follow-on emails in "
            "that thread?"
        ),
    ],

    "applicable_models": [
        {
            "model": "network-broker",
            "description": (
                "Nikolic functioned as a structural broker between the Gates science program and Epstein's "
                "personal and financial network. He held positions in two otherwise-disconnected clusters "
                "(Gates Foundation grantmaking; Epstein's social world) and was the node through which "
                "information and introductions crossed between them. The IPI grant brokering is the clearest "
                "documented instance: Epstein used Nikolic as the inside channel to move a $5 million "
                "grant proposal through the Gates Foundation's scientific review."
            ),
        },
        {
            "model": "information-conduit",
            "description": (
                "Across multiple documented instances, Nikolic relayed information about third parties to "
                "Epstein: Kimbal Musk's divorce (February 2013), the identity of an Epstein critic at "
                "Highbridge Capital (January 2013), WEF participant lists (2011, 2013), and the presence "
                "of Kimbal and Elon Musk at TED 2017. Whether these transmissions were deliberate reporting "
                "or ordinary social correspondence cannot be established from the email evidence alone."
            ),
        },
        {
            "model": "trust-chain-positioning",
            "description": (
                "Nikolic's placement as first alternate trustee of the 1953 Trust—above Epstein's own lawyers—"
                "is a data point about how Epstein ranked personal trust. The succession chain (Indyke/Kahn → "
                "Nikolic → Marsh → Barrett → Ruemmler → Mitchell → Hanson → Eva Dubin) consistently places "
                "scientists and close social contacts ahead of legal professionals in the order of succession. "
                "Nikolic's position at the top of that chain, despite his lack of formal legal or financial "
                "qualifications for the role, is the primary unresolved question in his dossier."
            ),
        },
    ],

    "key_finding_ids": [287, 303, 284, 285, 4512, 282, 699, 4511, 4508, 4509, 536],
    "key_identifiers": {
        "jurisdictions": [],
        "officers": [],
        "entities": ["bgC3", "Foundation Medicine", "ResearchGate", "International Peace Institute"],
    },
    "section_suggestions": [
        {
            "id": "key-relationships",
            "title": "Key Relationships",
            "viz": "ego_network",
            "finding_ids": [303, 285, 4512, 282],
            "connection_ids": [169, 275, 607, 2658, 61, 608, 647],
            "guidance": (
                "Narrative about the most significant relationships. Name each person with a link to their "
                "dossier. Explain the nature and significance of each relationship, not just that it exists."
            ),
        }
    ],
    "curated_at": datetime.now(timezone.utc).isoformat(),
}


def main() -> int:
    if not DOSSIER_PATH.exists():
        print(f"ERROR: {DOSSIER_PATH} not found", file=sys.stderr)
        return 1

    data = json.loads(DOSSIER_PATH.read_text())
    data["curation"] = CURATION
    DOSSIER_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"Written: {DOSSIER_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
