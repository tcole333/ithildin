#!/usr/bin/env python3
"""
Curation script for David Schoen dossier.
Writes the `curation` block into content/dossiers/david-schoen.json.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/david-schoen.json")

# ---------------------------------------------------------------------------
# Curation content
# ---------------------------------------------------------------------------

LEAD = """\
<p>David Schoen is a Montgomery, Alabama criminal defense attorney who occupied a \
sustained advisory role inside Jeffrey Epstein's legal and public-relations strategy \
from at least December 2018 through Epstein's death in August 2019 — a period during \
which he was also a registered foreign agent for Ukrainian oligarch Victor Pinchuk \
under FARA registration #6071. Thirty-four emails in the DOJ-released corpus document \
Schoen's engagement with Epstein dating to 2010, introduced through mutual acquaintance \
Bernard Kruger; by 2018 he had moved from informal adviser to embedded strategist \
directing defense counsel, evaluating op-ed drafts, and coordinating media positioning \
[Finding #286, #288, #295].</p>

<p>On December 20, 2018, Schoen reviewed a full draft op-ed intended for \
<a href="/dossiers/ken-starr">Ken Starr</a>'s signature, advising against using Starr's \
name because his forced departure from Baylor University — where he was criticized for \
mishandling sexual harassment complaints — would "undercut the piece." Schoen then offered \
to write and sign the piece himself, explicitly noting he was "not part of the defense team" \
(<a href="https://efts.org/EFTA02609032">EFTA02609032</a>). The draft characterized \
Epstein's crimes as "solicitation of prostitution" and "sexual favors for hire," claimed \
there was "no coercion, violence, alcohol, drugs," asserted victims "lied about being \
eighteen years old," and framed any challenge to the non-prosecution agreement as a \
challenge to "the millions Mr. Epstein paid to the asserted victims" — language that \
functioned as a financial threat directed at victims who had already settled [Finding #288].</p>

<p>Following Epstein's July 2019 federal arrest, Schoen arrived at MCC on August 1, 2019 \
for a five-hour meeting with Epstein to take over as lead defense counsel. Nine days later, \
on August 10, Epstein was found dead in his cell. Within eighteen months, Schoen was serving \
as one of Donald Trump's defense counsel in the second Senate impeachment trial \
(February 2021), then represented Steve Bannon in his federal contempt case, and was \
subsequently elected chairman of the Zionist Organization of America. He has stated publicly \
that he directly asked Epstein whether he possessed information that could harm Trump, and \
that Epstein told him he did not [Finding #295].</p>"""

SYSTEM_ROLE = (
    "David Schoen is a criminal defense attorney who served as an embedded adviser inside "
    "Jeffrey Epstein's legal and public-relations strategy from December 2018 through "
    "Epstein's death, while simultaneously registered as a foreign agent for Ukrainian "
    "oligarch Victor Pinchuk (FARA #6071, 2011–2019). He subsequently represented Donald "
    "Trump in the second Senate impeachment trial (2021), defended Steve Bannon on federal "
    "contempt charges, and became chairman of the Zionist Organization of America."
)

SECTION_EPSTEIN_DEFENSE = """\
<p>The email record places Schoen inside Epstein's defense network earlier than public \
accounts acknowledge. The initial contact was through mutual friend Bernard Kruger, and by \
2013 the relationship had sufficient personal depth that Schoen was consulting Epstein about \
private investigators. By December 2018 — months before the Miami Herald's reporting \
accelerated the federal investigation — Schoen was receiving full draft legal strategy \
documents for review.</p>

<p>The December 20, 2018 exchange over the op-ed draft \
(<a href="https://efts.org/EFTA02609032">EFTA02609032</a>) is the most detailed record of \
Schoen's role in that period. The draft, structured as a public defense of the 2008 \
non-prosecution agreement, ran through four substantive claims: that Epstein's offenses \
amounted to "solicitation of prostitution"; that no coercion or substances were involved; \
that victims had misrepresented their ages; and that Epstein had taken "full responsibility" \
and "led a life characterized by responsible citizenship." Schoen's specific contribution in \
that exchange was twofold: he identified Ken Starr's Baylor liability as a reputational \
problem for the piece, and he proposed recasting the same content as a "pro prosecutor piece" \
written in his own name since he was formally outside the defense team — a distinction \
designed to create the appearance of independent commentary [Finding #288].</p>

<p>In the months that followed, Schoen met Epstein in person multiple times at 9 East 71st \
Street, directed defense counsel Martin Weinberg to "stay focused," and discussed specifics \
of Epstein's case including a lie detector test (March 18, 2019, \
<a href="https://efts.org/EFTA02636859">EFTA02636859</a>) and pending mediation \
(March 27, 2019, <a href="https://efts.org/EFTA02636162">EFTA02636162</a>). In February \
2019, Schoen reviewed the position of <a href="/dossiers/kirkland-ellis">Kirkland &amp; \
Ellis</a> attorney Jay Lefkowitz — who had negotiated the original 2008 NPA — and told \
Epstein that Lefkowitz faced "major exposure" and that his emails to prosecutors had been \
"absolutely moronic" (<a href="https://efts.org/EFTA02634297">EFTA02634297</a>). \
These exchanges reflect a strategic advisory function, not a peripheral consulting one \
[Finding #286, Connection #1607].</p>

<p>The MCC meeting on August 1, 2019 — five hours, with Schoen traveling to New York \
specifically to take over as lead counsel — occurred in the context of Epstein's July 6 \
arrest and the collapse of the prior defense structure. Epstein died nine days later. \
No transcript of that meeting is in the corpus, and Schoen has not provided a public account \
of its contents beyond confirming it took place and that he posed a direct question about \
information that could be used against Trump [Finding #295].</p>"""

SECTION_FARA_AND_FOREIGN_CONNECTIONS = """\
<p>From October 19, 2011 through November 6, 2019, Schoen was a registered agent under \
the Foreign Agents Registration Act for Victor Pinchuk, Ukraine's second-largest steel \
producer and a figure documented to have contributed to the Clinton Foundation during the \
same period (<a href="https://www.justice.gov/nsd-fara/registrant/6071">FARA #6071</a>). \
Monica Crowley — later nominated by Trump as Assistant Secretary of the Treasury for Public \
Affairs — was a short-form registrant under Schoen's Pinchuk FARA registration from \
March 10, 2017 forward [Finding #390, Connection #325].</p>

<p>The FARA registration ran through the entirety of Schoen's active Epstein advisory period \
(December 2018 through August 2019) and terminated on November 6, 2019 — approximately three \
months after Epstein's August 10 death. The overlap is a documented factual matter; the \
FARA record does not specify what activities Schoen conducted for Pinchuk during the \
overlapping period, and no corpus document has been found establishing whether Pinchuk had \
any awareness of or interest in Epstein's legal affairs [Finding #400].</p>

<p>Pinchuk's profile in the relevant period includes documented lobbying engagement with \
both Democratic and Republican figures in Washington, substantial contributions to the \
Clinton Foundation prior to 2016, and public opposition to Russian influence over Ukraine. \
The structural point the FARA record establishes is that Schoen was serving a registered \
foreign principal in the same months he was advising on defense strategy for one of the \
most politically sensitive federal prosecutions in that period — without any public \
disclosure of that dual role [Finding #390].</p>"""

SECTION_SUBSEQUENT_CAREER = """\
<p>Schoen's post-2019 career follows a consistent pattern of representation in politically \
charged federal matters involving conservative clients. In January and February 2021, he \
served as one of two defense attorneys for Donald Trump in the second Senate impeachment \
trial arising from the January 6 Capitol breach; his co-counsel was Bruce Castor. Schoen's \
public explanation for accepting the representation was that he had spoken with Epstein about \
Trump and was satisfied Epstein had no damaging information about him — a statement that, if \
accurate, means Schoen sought from a federal criminal defendant information relevant to a \
political figure, and used the answer to inform a subsequent professional decision \
[Finding #295].</p>

<p>Schoen subsequently represented <a href="/dossiers/steve-bannon">Steve Bannon</a> in \
federal contempt proceedings arising from Bannon's refusal to comply with a January 6 \
committee subpoena. Bannon was convicted in July 2022; Schoen continued to represent him \
through sentencing. Schoen was also elected chairman of the Zionist Organization of America \
during this period, adding an organizational leadership role to his legal practice.</p>

<p>Schoen's trajectory from Epstein defense adviser to Trump impeachment counsel to Bannon \
defense attorney is a matter of public record. Whether the Epstein advisory role contributed \
to building the professional network that produced those subsequent engagements is not \
established by the corpus. The connection to Pinchuk through FARA, the connection to Monica \
Crowley through the same registration, and the connection to Kirkland &amp; Ellis through \
the NPA critique all place Schoen at a junction of Ukrainian foreign lobbying interests, \
Trump-world legal representation, and Epstein's defense infrastructure in the same 2017–2019 \
period [Connection #613, #325, #1607].</p>"""

OPEN_QUESTIONS = [
    "FARA activity logs: FARA registration #6071 establishes the principal-agent relationship "
    "with Victor Pinchuk but the supplemental statements (filed every six months) would specify "
    "what activities Schoen performed for Pinchuk during the 2018–2019 period when he was "
    "simultaneously advising Epstein. Those supplemental filings should be in the FARA public "
    "reading room. No corpus record confirms whether they have been reviewed.",

    "The MCC August 1 meeting: Schoen met with Epstein for five hours nine days before his "
    "death. Schoen's public account confirms he raised the Trump question but has not described "
    "the meeting's other content. No attorney notes, contemporaneous emails, or subsequent "
    "correspondence documenting what Schoen learned about defense strategy, assets, or third "
    "parties has been found in the corpus.",

    "Crowley's activities under FARA #6071: Monica Crowley registered as a short-form "
    "registrant under Schoen's Pinchuk registration on March 10, 2017. This places Crowley "
    "as a Pinchuk agent at the same time she was a Fox News contributor and before her "
    "2017 nomination withdrawal for NSC Deputy National Security Adviser (she later served "
    "as Treasury's Assistant Secretary for Public Affairs starting 2019). The scope of "
    "activities she performed as registrant under #6071 has not been verified.",

    "The Varsity Blues comment: In early 2019 Schoen told Epstein that college admissions "
    "scandal defendants (Operation Varsity Blues) would need Martin Weinberg's services "
    "(EFTA02275436 context). This was a remarkably early awareness of that prosecution, "
    "which became public with arrests in March 2019. Whether this reflected inside knowledge "
    "of the investigation timeline or general awareness of Weinberg's practice area has "
    "not been examined.",

    "Schoen's bar status and ethics filings: Schoen is licensed in Alabama and has appeared "
    "pro hac vice in numerous federal districts. The dual FARA registration and Epstein "
    "advisory role — simultaneously serving a foreign principal while advising a federal "
    "criminal defendant in an active prosecution — has not been examined against applicable "
    "professional conduct rules on conflicts with foreign clients.",
]

APPLICABLE_MODELS = [
    {
        "name": "Outside-the-Team Framing",
        "description": (
            "Schoen's explicit offer to write the pro-Epstein op-ed himself because he was "
            "'not part of the defense team' illustrates a structural role distinct from "
            "formal defense counsel: the informal strategist who can produce public-facing "
            "content with the appearance of independence while coordinating with the defense. "
            "This pattern — maintaining operational separation from the formal legal team "
            "while functionally executing the same strategy — recurs in the corpus and "
            "provides deniability for both the author (not counsel of record) and the "
            "defendant (didn't direct it through counsel)."
        ),
    },
    {
        "name": "Overlapping Principal Registrations",
        "description": (
            "The FARA record documents Schoen serving a foreign principal (Pinchuk) and "
            "a domestic criminal defendant (Epstein) during the same period, with no "
            "public disclosure of the overlap. The termination of the Pinchuk registration "
            "three months after Epstein's death — rather than before, during, or immediately "
            "after Epstein's arrest — is a timing pattern that warrants examination. "
            "The pattern appears elsewhere in the Epstein corpus: advisers who simultaneously "
            "held roles with foreign principals and domestic political figures, where the "
            "compartmentalization between roles is formally maintained but the network "
            "connections are shared."
        ),
    },
    {
        "name": "Political Capital Conversion",
        "description": (
            "Schoen's trajectory from Epstein defense adviser (2018–2019) to Trump "
            "impeachment counsel (2021) to Bannon defense attorney follows a pattern "
            "visible in other Epstein-adjacent legal careers: involvement in a high-stakes "
            "politically sensitive defense generates access to the political network of "
            "the client or the client's allies, which converts into subsequent engagements. "
            "The mechanism is access and demonstrated loyalty in difficult circumstances "
            "rather than any direct exchange. Whether Schoen's specific trajectory was "
            "shaped by the Epstein relationship or emerged from independent political "
            "connections is not established by the corpus."
        ),
    },
]


# ---------------------------------------------------------------------------
# Assemble and write
# ---------------------------------------------------------------------------


def main():
    raw = DOSSIER_PATH.read_text(encoding="utf-8")
    dossier = json.loads(raw)

    curation = dossier.get("curation", {})

    # Preserve existing scaffold fields, overwrite content fields
    curation["lead"] = LEAD
    curation["system_role"] = SYSTEM_ROLE
    curation["sections"] = [
        {
            "id": "epstein-defense",
            "title": "Role in the Epstein Defense",
            "content": SECTION_EPSTEIN_DEFENSE,
            "viz": "timeline",
        },
        {
            "id": "fara-foreign-connections",
            "title": "FARA Registration and Pinchuk",
            "content": SECTION_FARA_AND_FOREIGN_CONNECTIONS,
            "viz": "ego_network",
        },
        {
            "id": "subsequent-career",
            "title": "Post-2019 Career",
            "content": SECTION_SUBSEQUENT_CAREER,
            "viz": None,
        },
    ]
    curation["open_questions"] = OPEN_QUESTIONS
    curation["applicable_models"] = APPLICABLE_MODELS
    curation["curated_at"] = datetime.now(timezone.utc).isoformat()

    dossier["curation"] = curation

    DOSSIER_PATH.write_text(
        json.dumps(dossier, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote curation to {DOSSIER_PATH}")


if __name__ == "__main__":
    main()
