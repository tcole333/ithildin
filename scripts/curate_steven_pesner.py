#!/usr/bin/env python3
"""Curation script for Steven Pesner dossier."""

import json
from pathlib import Path

DOSSIER_PATH = Path("/Users/travcole/projects/osint-research/content/dossiers/steven-pesner.json")

curation = {
    "lead": (
        "<p>Steven M. Pesner is a commercial litigator and bankruptcy attorney who spent 24 years "
        "as a partner at Akin Gump Strauss Hauer & Feld LLP before moving to Friedman Kaplan "
        "Seiler & Adelman in January 2018. His practice focused on complex commercial litigation, "
        "bankruptcy and creditors' rights, and securities matters for major private equity and "
        "investment management funds. In 2016, Pesner occupied two distinct roles simultaneously "
        "within the Apollo Global Management orbit: he was the lead Akin Gump partner assigned to "
        "the Caesars Entertainment bankruptcy settlement engagement, and he was a named member of "
        "the cross-firm advisory team assembled to address the Apollo founders' delinquent IRS "
        "Form 8865 filings for BRH Holdings LP, the Cayman Islands partnership through which "
        "<a href='/dossiers/leon-black'>Leon Black</a>, "
        "<a href='/dossiers/marc-rowan'>Marc Rowan</a>, and Joshua Harris held their Apollo "
        "economic interests. <a href='/dossiers/jeffrey-epstein'>Jeffrey Epstein</a>&mdash;a "
        "convicted sex offender acting as the founders' personal tax and financial "
        "advisor&mdash;directed both matters and had direct email correspondence with Pesner "
        "throughout. <a href='/dossiers/nicholas-ribis'>Nicholas Ribis</a>, the gaming industry "
        "mediator brought in to resolve the Caesars matter, warned Epstein in September 2016 "
        "that Pesner was financially incentivized to prolong the Caesars litigation and was "
        "actively obstructing settlement "
        "(<a href='/sources/EFTA02450801'>EFTA02450801</a>). "
        "Epstein in turn described Pesner as &ldquo;difficult to finesse&rdquo; and ultimately "
        "overrode his professional advice on the 8865 filing strategy "
        "(<a href='/sources/EFTA02476189'>EFTA02476189</a>).</p>"
    ),
    "system_role": (
        "Akin Gump Strauss Hauer & Feld LLP partner (commercial litigation and bankruptcy); "
        "member of the Apollo founders' IRS Form 8865 remediation advisory team in 2016; "
        "Akin Gump partner assigned to the Caesars Entertainment bankruptcy settlement matter. "
        "Subsequently partner at Friedman Kaplan Seiler & Adelman from January 2018."
    ),
    "sections": [
        {
            "id": "identity-and-background",
            "title": "Identity and Background",
            "content": (
                "<p>Steven M. Pesner practiced at Akin Gump Strauss Hauer & Feld for 24 years "
                "before departing in January 2018. His practice concentrated on complex commercial "
                "litigation, bankruptcy and creditors' rights, and securities disputes, with a "
                "client base described in his firm biography as including &ldquo;major PE and "
                "investment management funds.&rdquo; Pesner appears in the Epstein email corpus "
                "initially as &ldquo;Steve P,&rdquo; a reference used by "
                "<a href='/dossiers/nicholas-ribis'>Nicholas Ribis</a> in April 2016 before "
                "Ribis named him explicitly as &ldquo;Steve Pesner&rdquo; in "
                "<a href='/sources/EFTA02467282'>EFTA02467282</a>. The identification is "
                "corroborated by Epstein's own September 2016 listing of &ldquo;pezner&rdquo; "
                "among his active advisors (<a href='/sources/EFTA02449580'>EFTA02449580</a>) "
                "and by Pesner's email address appearing directly in the To: field of the "
                "Reasonable Cause Statement call invitation "
                "(<a href='/sources/EFTA02450447'>EFTA02450447</a>). At Friedman Kaplan, Pesner "
                "joined the same firm as Patrick Fenn, who had been his Akin Gump colleague on "
                "the 8865 advisory team.</p>"
            ),
        },
        {
            "id": "caesars-matter",
            "title": "The Caesars Engagement",
            "content": (
                "<p>By early 2016, <a href='/dossiers/marc-rowan'>Marc Rowan</a> and Apollo were "
                "deeply exposed to litigation arising from the Caesars Entertainment Operating "
                "Company (CEOC) bankruptcy. A bankruptcy examiner had found $3.6&ndash;5.1 "
                "billion in potential claims against Apollo. "
                "<a href='/dossiers/nicholas-ribis'>Nicholas Ribis</a>&mdash;a casino industry "
                "veteran and former CEO of Trump Hotels &amp; Casino Resorts&mdash;was brought in "
                "as an intermediary to explore settlement. Pesner was the Akin Gump partner "
                "designated as Ribis's primary professional contact on the engagement.</p>"
                "<p>The relationship between Pesner and Ribis deteriorated quickly. On "
                "March 29, 2016, Ribis met with Pesner and asked "
                "<a href='/dossiers/jeffrey-epstein'>Epstein</a> to follow up by phone "
                "(<a href='/sources/EFTA02467883'>EFTA02467883</a>). By April 5, Ribis wrote "
                "to Epstein: &ldquo;The lawyer Steve Pesner seems to be slow walking me&rdquo; "
                "(<a href='/sources/EFTA02467282'>EFTA02467282</a>). The situation had not "
                "improved by September 11, when Ribis issued a direct warning to Epstein: "
                "&ldquo;when u speak with Steve P later don't forget that he is making much money "
                "having this continue, acts nice and respectful but is not, didn't return calls "
                "and emails for months before I was hired despite being told to, spoke to me once "
                "in 5 months (Mark met with me 5 times), now does not want me around because I "
                "know too much and can settle this&rdquo; "
                "(<a href='/sources/EFTA02450801'>EFTA02450801</a>). Ribis added that Pesner had "
                "made a negative comment about Epstein when he learned that Epstein had "
                "recommended Ribis for the engagement. The following day, Ribis asked Epstein "
                "&ldquo;How did ur call with Steve go?&rdquo; "
                "(<a href='/sources/EFTA02451101'>EFTA02451101</a>).</p>"
                "<p>Ribis's account describes a billing partner with a financial stake in "
                "prolonging the matter he was nominally hired to resolve. Pesner was also "
                "simultaneously embedded in the 8865 filing advisory team for the same Apollo "
                "founders whose litigation exposure he was assigned to manage, creating a "
                "configuration where a single Akin Gump partner held privileged access to "
                "two of the founders' most sensitive concurrent legal crises.</p>"
            ),
        },
        {
            "id": "8865-advisory-team",
            "title": "The IRS Form 8865 Advisory Team",
            "content": (
                "<p>IRS Form 8865 is required of U.S. persons with interests in foreign "
                "partnerships. The Apollo founders held their economic interests through BRH "
                "Holdings LP, a Cayman Islands partnership, and had failed to file the required "
                "returns for multiple years&mdash;dating back to at least 2007 for Harris and "
                "Rowan and filed inaccurately for Black from 2013 to 2015. The remediation effort "
                "in 2016 required a multi-firm advisory team handling both the substantive "
                "compliance work and the preparation of a &ldquo;reasonable cause statement&rdquo; "
                "to present to the IRS as a basis for penalty abatement.</p>"
                "<p>Pesner appears as a named team member in the direct documentary record. "
                "<a href='/sources/EFTA02450447'>EFTA02450447</a> places Pesner on a "
                "Reasonable Cause Statement call with "
                "<a href='/dossiers/brad-karp'>Brad Karp</a> (Paul Weiss chairman) and Patrick "
                "Fenn (Akin Gump, international tax) on September 10&ndash;11, 2016. "
                "<a href='/sources/EFTA02348561'>EFTA02348561</a> shows Brad Wechsler (Black's "
                "CFO) sending 2007&ndash;2014 historical data to Pesner with "
                "<a href='/dossiers/brad-karp'>Karp</a>, "
                "<a href='/dossiers/jeffrey-epstein'>Epstein</a>, and "
                "<a href='/dossiers/leon-black'>Black</a> all CC'd, and a deadline for Pesner "
                "to review the materials. The full team enumeration in "
                "<a href='/sources/EFTA02668080'>EFTA02668080</a> (Fenn's listing) names "
                "&ldquo;Brad S Karp, Pesner Steven, PWC-Josh, Deloitte, Apollo, Akin-the 3 "
                "individuals.&rdquo;</p>"
                "<p>Epstein was not a passive participant. He directed strategy, proposed "
                "filing approaches&mdash;including using the IRS delinquent international "
                "disclosures program and a &ldquo;file minimum 8865 then amend later&rdquo; "
                "position&mdash;and explicitly asked whether Joshua Harris could join the calls "
                "(<a href='/sources/EFTA02450447'>EFTA02450447</a>). By September 29, Epstein "
                "was berating Leon Black's office about the pace of the work and reported having "
                "spoken to &ldquo;each of karp, pezner, fenn, brad, joslin, bodian multiple "
                "times&rdquo; (<a href='/sources/EFTA02449580'>EFTA02449580</a>). By November, "
                "Epstein described Pesner as &ldquo;difficult to finesse&rdquo; in the context "
                "of documents the founders were unwilling to file "
                "(<a href='/sources/EFTA02476189'>EFTA02476189</a>). A separate email "
                "(<a href='/sources/EFTA02659977'>EFTA02659977</a>) records that Epstein "
                "&ldquo;did not give in to the views of pesner, josh.s guy, okun, fenn, brad, "
                "barry&rdquo;&mdash;a list of the professional advisors whose combined judgment "
                "Epstein overrode.</p>"
            ),
        },
        {
            "id": "key-relationships",
            "title": "Key Relationships",
            "content": (
                "<p><strong><a href='/dossiers/jeffrey-epstein'>Jeffrey Epstein</a></strong>: "
                "Epstein had direct email correspondence with Pesner, appeared on calls alongside "
                "him, was CC'd on his work product, and ultimately overrode his professional "
                "advice on filing strategy. In "
                "<a href='/sources/EFTA02448418'>EFTA02448418</a>, Epstein was &ldquo;happy to "
                "bounce some thoughts off&rdquo; Pesner&mdash;positioning himself as a peer "
                "rather than a client on the matter. Pesner made a negative remark about Epstein "
                "when he learned Epstein had recommended Ribis for the Caesars engagement, "
                "documenting awareness of Epstein's background within the advisory team "
                "(<a href='/sources/EFTA02450801'>EFTA02450801</a>). Despite this, the "
                "working relationship continued through at least November 2016.</p>"
                "<p><strong><a href='/dossiers/nicholas-ribis'>Nicholas Ribis</a></strong>: "
                "Ribis was brought in as a settlement intermediary on the Caesars engagement "
                "while Pesner was the designated Akin Gump contact. Ribis characterized the "
                "relationship as one in which Pesner failed to communicate for months, met with "
                "him only once over five months (while Rowan met with him five times), and "
                "ultimately worked against settlement efforts for billing reasons "
                "(<a href='/sources/EFTA02450801'>EFTA02450801</a>). Ribis's warning to "
                "Epstein about Pesner&mdash;specifically that Pesner &ldquo;does not want me "
                "around because I know too much and can settle this&rdquo;&mdash;is the most "
                "direct characterization of Pesner's role in the matter in the documentary "
                "record.</p>"
                "<p><strong><a href='/dossiers/brad-karp'>Brad Karp</a></strong>: Karp (Paul "
                "Weiss chairman) and Pesner (Akin Gump) were the two senior outside counsel on "
                "the 8865 advisory team, appearing together on the Reasonable Cause Statement "
                "calls and named together in multiple Epstein-addressed communications. Karp "
                "had a far more extensive relationship with Epstein that predated and extended "
                "beyond the 8865 matter; for Pesner, the 8865 work is the primary documented "
                "point of contact.</p>"
                "<p><strong><a href='/dossiers/leon-black'>Leon Black</a></strong>: Black was "
                "CC'd on Pesner's data review communications, was the subject of Epstein's "
                "discussions of the Pesner relationship with Spinella (Black's executive "
                "assistant), and was the direct counterparty on the filings Pesner was advising "
                "on. Epstein managed the Pesner relationship as part of his broader management "
                "of Black's financial affairs.</p>"
                "<p><strong><a href='/dossiers/marc-rowan'>Marc Rowan</a></strong>: Pesner's "
                "simultaneous involvement in the Caesars matter (where Rowan had direct board "
                "member liability) and the 8865 remediation (which covered BRH Holdings, the "
                "vehicle holding Rowan's Apollo economic interests) placed Pesner in possession "
                "of privileged information across both of Rowan's most significant concurrent "
                "legal exposures in 2016.</p>"
            ),
        },
    ],
    "open_questions": [
        (
            "The Dechert LLP investigation (commissioned by Apollo's Conflicts Committee in "
            "January 2021) concluded that the Black-Epstein relationship was primarily personal "
            "advisory. The 8865 advisory team&mdash;which included Pesner, Karp, Fenn, and "
            "multiple accounting firms&mdash;operated across all three founders simultaneously. "
            "Whether Pesner was contacted during the Dechert investigation or provided any "
            "account of the filing crisis is not in the public record."
        ),
        (
            "Pesner's departure from Akin Gump in January 2018 occurred approximately when "
            "the 8865 remediation work would have concluded. The timing coincides with the "
            "period when Epstein self-forwarded communications about the filing matter "
            "(EFTA02476189 was forwarded by Epstein on April 7, 2018, of an original "
            "November 29, 2016 email). Whether the departure was professionally motivated "
            "by the conclusion of the matter, or by other considerations, is not established "
            "by available evidence."
        ),
        (
            "The exact scope of Pesner's litigation role in the Caesars CEOC bankruptcy "
            "is not fully documented in the Epstein email corpus. Ribis's account identifies "
            "Pesner as the Akin Gump partner assigned to coordinate with him, but the "
            "underlying retainer scope, which of the Apollo founders was the client, and "
            "whether there were conflicts between Pesner's Caesars and 8865 representations "
            "are not established."
        ),
        (
            "EFTA02659977 lists Pesner among the advisors whose views Epstein overrode on "
            "the 8865 filing strategy: &ldquo;pesner, josh.s guy, okun, fenn, brad, barry.&rdquo; "
            "The nature of the specific professional disagreement&mdash;whether it was about "
            "years of returns to file, the reasonable cause argument, or another dimension "
            "of the strategy&mdash;is truncated in the available source quote."
        ),
    ],
    "applicable_models": [
        {
            "model": "Billing incentive / litigation prolongation",
            "description": (
                "Ribis's account of Pesner describes a configuration in which the partner "
                "responsible for resolving a matter has a financial incentive to extend it. "
                "As a billing partner at a major firm, Pesner's hourly revenue from the "
                "Caesars engagement would increase with duration. This model does not require "
                "bad faith&mdash;the incentive is structural&mdash;but Ribis's characterization "
                "is explicit: Pesner &ldquo;is making much money having this continue.&rdquo;"
            ),
        },
        {
            "model": "Multi-matter privilege concentration",
            "description": (
                "In 2016, Pesner simultaneously held privileged information about the Caesars "
                "litigation exposure (where Rowan had board-member liability) and the 8865 "
                "filing crisis (where all three founders faced IRS penalty exposure). Both "
                "matters involved the same institutional client set. This concentration of "
                "privilege across two simultaneous crises, mediated through a single attorney "
                "who also interacted with Epstein as a co-member of the advisory team, "
                "represents a potential conflict surface that the Dechert investigation did "
                "not address publicly."
            ),
        },
        {
            "model": "Professional knowledge of Epstein / continuation nonetheless",
            "description": (
                "Pesner made a documented negative comment about Epstein's involvement when "
                "he discovered Epstein had recommended Ribis for the Caesars engagement. "
                "This establishes that Akin Gump professionals at partner level had awareness "
                "of Epstein's background (he had been publicly convicted in 2008) and "
                "nonetheless continued to work alongside him on the 8865 filing team through "
                "at least November 2016. This pattern&mdash;documented reservation followed "
                "by continued professional engagement&mdash;appears in multiple members of "
                "the advisory network."
            ),
        },
    ],
}

# Load and update dossier
with open(DOSSIER_PATH) as f:
    dossier = json.load(f)

dossier["curation"].update(curation)

with open(DOSSIER_PATH, "w") as f:
    json.dump(dossier, f, indent=2)

print("Curation written successfully.")
print(f"Sections: {[s['id'] for s in curation['sections']]}")
print(f"Open questions: {len(curation['open_questions'])}")
print(f"Applicable models: {len(curation['applicable_models'])}")
