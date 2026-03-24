#!/usr/bin/env python3
"""
Curation script for Brad Edwards dossier.
Writes the `curation` block into content/dossiers/brad-edwards.json.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/brad-edwards.json")

# ---------------------------------------------------------------------------
# Curation content
# ---------------------------------------------------------------------------

LEAD = """\
<p>Brad Edwards is a Fort Lauderdale, Florida plaintiffs' attorney and Board Certified Trial Lawyer \
who represented Epstein victims in the Crime Victims' Rights Act (CVRA) federal case in the Southern \
District of Florida, working as co-counsel alongside University of Utah law professor Paul Cassell. \
Edwards maintained a direct personal email correspondence with Jeffrey Epstein from at least 2015 \
through February 2019 — spanning the same period during which he served as lead advocate for \
Epstein's victims in the CVRA proceedings. That correspondence, preserved in the DOJ-released \
document corpus and cited under EFTA reference numbers, documents regular phone contacts, \
in-person breakfast meetings in Palm Beach and Fort Lauderdale, a personal wager over Bill Clinton \
flight logs (<a href="https://efts.org/EFTA02481057">EFTA02481057</a>), and direct exchanges about \
strategic litigation matters affecting both Epstein and his accusers [Finding #293, #224].</p>

<p>The email record establishes three distinct roles Edwards occupied simultaneously in late 2018 \
through early 2019: (1) adversary to Epstein as victims' counsel in ongoing CVRA litigation; \
(2) negotiating party in his own defamation settlement with Epstein, which concluded in December \
2018 with a written public apology from Epstein acknowledging his lawsuit had been "my unreasonable \
attempt to damage Edwards's business reputation"; and (3) intermediary who facilitated direct \
email contact between Epstein and <a href="/dossiers/jeffrey-epstein">David Boies</a> of Boies \
Schiller Flexner for purposes of settling the Sarah Ransome (Jane Doe 43) SDNY case (17-cv-00616), \
which terminated December 26, 2018 [Finding #280, #281]. Following settlement, Epstein directed \
a donation from his <a href="/dossiers/enhanced-education">Enhanced Education</a> foundation trade \
name — confirmed via FedEx delivery from the St. Thomas USVI address — to the National Crime \
Victim Bar Association at Edwards's written request, dated January 24, 2019 \
(<a href="https://efts.org/EFTA02626876">EFTA02626876</a>) [Finding #223].</p>"""

SYSTEM_ROLE = (
    "Brad Edwards is a Fort Lauderdale plaintiffs' attorney who represented Epstein victims in "
    "the federal CVRA case alongside Paul Cassell, while simultaneously maintaining a direct "
    "personal correspondence with Epstein that produced his own defamation settlement and placed "
    "him as a communications conduit between Epstein and Boies Schiller Flexner during the Sarah "
    "Ransome settlement negotiations in late 2018."
)

SECTION_LEGAL_PROCEEDINGS = """\
<p>Edwards first appears in Epstein litigation as co-counsel with Paul Cassell in the CVRA \
federal case seeking to void the 2008 non-prosecution agreement in the Southern District of Florida. \
That litigation, which produced a landmark 2019 ruling finding the NPA was negotiated in violation \
of the CVRA, continued through the period during which Edwards was also negotiating personally with \
Epstein.</p>

<p>In parallel, Epstein filed a defamation suit against Edwards. The civil litigation general file \
(GRM Box #004740716) confirms a Florida Bar complaint against Edwards was also active during this \
period, alongside focus group materials and AIG insurance defense requests reflecting Epstein's \
organized legal counter-strategy against the victims' counsel [Finding #2524 in related records]. \
The defamation case was resolved by direct bilateral negotiation between Edwards and Epstein, \
conducted without lawyers — Edwards's own phrase in the emails was "Without lawyers, we can get \
things done. Impossible once you bring in the opinions of a bunch of lawyers" \
(<a href="https://efts.org/EFTA02614384">EFTA02614384</a>). Epstein's lawyer Martin Weinberg \
("Marty") objected to the apology language on grounds it could constitute an "admission of a \
crime," and Epstein sought modifications to protect a separate suit against Fowler White Burnett. \
The final settlement, completed December 2018, included: (a) a public written apology from \
Epstein, (b) payment of Edwards's legal costs, and (c) Epstein's agreement to donate to the \
National Crime Victim Bar Association at Edwards's direction [Finding #281].</p>

<p>The Dershowitz defamation track runs as a separate but intersecting thread. In October 2015, \
Epstein served as direct intermediary between Edwards and Alan Dershowitz, who were engaged in \
defamation litigation against each other stemming from Dershowitz's public statements about \
Epstein victims. Epstein's emails document him relaying settlement offers: "would you guys take \
200k each from the offer of settlement from dersh?" and later "the deal on the table is 1 million \
dollars split between you three. or 1 million given to the charities of your choices... alan \
thinks the charity is better so as not to look like money is going into each others pockets" \
(<a href="https://efts.org/EFTA02487391">EFTA02487391</a>, \
<a href="https://efts.org/EFTA02485300">EFTA02485300</a>). By October 9, 2015, Edwards was \
reporting to Epstein that Dershowitz had "agreed to the settlement and to agree to a joint public \
statement" (<a href="https://efts.org/EFTA02484887">EFTA02484887</a>). The structural position \
this created — Epstein acting as go-between for his victims' lawyer and his former defense counsel, \
in litigation those two parties were conducting against each other — has no documented precedent \
in the corpus [Finding #283].</p>

<p>The Sarah Ransome backchannel role is the third distinct legal track. Epstein's November 13, \
2018 email to Edwards explicitly thanked him for "the david call" — referring to David Boies — \
after Edwards made the introduction that opened direct settlement discussions in SDNY 17-cv-00616 \
(<a href="https://efts.org/EFTA02614962">EFTA02614962</a>). Edwards's facilitation of that \
connection occurred in the same weeks he was negotiating his own settlement with Epstein. By \
December 12, 2018, Epstein informed Kathy Ruemmler the Ransome case was "settled ransome" \
(<a href="https://efts.org/EFTA02610455">EFTA02610455</a>); the case terminated December 26, \
2018 [Finding #280].</p>"""

SECTION_KEY_RELATIONSHIPS = """\
<p><strong>Jeffrey Epstein</strong> — The relationship with \
<a href="/dossiers/jeffrey-epstein">Jeffrey Epstein</a> was formally adversarial but operationally \
personal. Regular phone-date scheduling, in-person breakfast meetings in Palm Beach and Fort \
Lauderdale, personal wagers, and the exchange of confidential litigation communications directly \
between the parties (not through counsel) characterize the documented correspondence. Epstein told \
Edwards, "you and I get along better than others" \
(<a href="https://efts.org/EFTA02614488">EFTA02614488</a>). The email record spans the October \
2015 Dershowitz mediation through the February 2019 Enhanced Education donation request, a period \
of more than three years during which Edwards simultaneously pursued victims' claims against \
Epstein. The defamation settlement's financial component — Epstein directing a donation from his \
foundation to a victim advocacy organization at Edwards's personal written request — documents a \
continuing financial relationship post-settlement [Finding #224, #223].</p>

<p><strong>David Boies</strong> — Edwards served as the introduction point connecting Epstein \
directly to <a href="/dossiers/david-boies">David Boies</a> (Boies Schiller Flexner) for purposes \
of negotiating the Sarah Ransome SDNY settlement in November 2018. The independent significance of \
this role derives from timing: Edwards was simultaneously negotiating his own settlement with \
Epstein when he facilitated the Epstein-Boies channel. Boies's own communications in the corpus \
show him corresponding with Epstein directly about Ransome settlement terms through late November \
and December 2018, following Edwards's introduction \
(<a href="https://efts.org/EFTA02613626">EFTA02613626</a>, \
<a href="https://efts.org/EFTA02614358">EFTA02614358</a>). Separately, Boies's relationship with \
Epstein's network extended to the Virginia Roberts/Giuffre litigation and Boies's own reputational \
positioning around Epstein disclosures — Epstein questioned whether Boies "would put himself so out \
there if he knew he had been scammed by virginia" [Finding #280].</p>

<p><strong>Sarah Ransome</strong> — Edwards's documented connection to \
<a href="/dossiers/jeffrey-epstein">Sarah Ransome</a> (Jane Doe 43, plaintiff in SDNY \
17-cv-00616) is indirect and structural: Edwards was not Ransome's attorney of record in that \
case, but he served as the conduit through which Ransome's opposing party (Epstein) established \
direct contact with Ransome's attorney (Boies) to negotiate her settlement. The case terminated \
December 26, 2018, eight days after Epstein confirmed to Ruemmler that it was settled. No \
evidence in the corpus indicates Edwards had any representation agreement with Ransome or that \
Ransome's counsel was informed of his simultaneous personal settlement negotiations with Epstein \
[Connection #249, Finding #280].</p>

<p><strong>Enhanced Education</strong> — The <a href="/dossiers/enhanced-education">Enhanced \
Education</a> trade name of J. Epstein Virgin Islands Foundation Inc. (USVI trade name TN0002420, \
same Red Hook Quarter B3 address as STC and other Epstein entities) was the disbursement vehicle \
for the January-February 2019 donation to the National Crime Victim Bar Association at Edwards's \
request. Epstein confirmed by email on February 1, 2019 that a check had been "put on the jan \
giving list" and dispatched by FedEx from Enhanced Education \
(<a href="https://efts.org/EFTA02628571">EFTA02628571</a>). This placed Epstein's charitable \
foundation — which also disbursed funds to universities, arts organizations, and personal \
recipients — in a direct financial relationship with the advocacy organization representing the \
class of people Edwards was suing Epstein on behalf of [Finding #223].</p>"""

OPEN_QUESTIONS = [
    "Florida Bar records: Was the bar complaint referenced in GRM Box #004740716 resolved, and on "
    "what terms? The simultaneous adversarial and personal roles documented in the email record "
    "are directly relevant to Florida professional conduct rules on conflicts of interest "
    "(Rule 4-1.7 RRTFB).",

    "Client disclosure: Did Edwards's victims-clients in the CVRA case receive disclosure of his "
    "concurrent personal defamation settlement negotiations with Epstein? Edwards's emails document "
    "direct bilateral settlement discussions without counsel; Florida Rule 4-4.2 prohibits "
    "communication with represented parties — and Epstein was always represented.",

    "Ransome connection: Did David Boies or Sarah Ransome know that the attorney who introduced "
    "Boies to Epstein was simultaneously negotiating his own settlement with Epstein? No "
    "documentation has been found establishing what disclosures were made.",

    "Dershowitz settlement outcome: The October 2015 email exchange documents Epstein relaying "
    "a $1 million settlement offer between Edwards/Cassell and Dershowitz. Did that settlement "
    "complete? Court records for the defamation case between Giuffre v. Dershowitz and related "
    "matters are not in the current corpus.",

    "Enhanced Education donation amount: The January 24, 2019 Edwards email requests a donation "
    "to NCVBA but does not specify an amount. Epstein's February 1 confirmation does not specify "
    "an amount. The actual check figure is not documented in any corpus record found.",

    "Edwards Pottinger LLC: Stanley Pottinger — Epstein's former roommate and DOJ AAG Civil "
    "Rights 1973–1977 — later operated 'Edwards Pottinger LLC' as a law firm. The relationship "
    "between the two attorneys named Edwards and Pottinger in that entity has not been "
    "investigated. This is a different Brad Edwards from Brad J. Edwards of Fort Lauderdale if "
    "names do not match, but the coincidence of name and shared Epstein adjacency warrants "
    "verification.",
]

APPLICABLE_MODELS = [
    {
        "name": "Dual-Role Conflict Structure",
        "description": (
            "Edwards occupied simultaneous adversarial and cooperative roles with the same "
            "counterparty (Epstein) across overlapping time periods. This structure — where "
            "a lawyer pursuing claims against a subject also negotiates personal financial "
            "settlements with that subject — creates alignment of personal and client interests "
            "that is not reflected in public case records. The pattern recurs in the corpus: "
            "multiple attorneys who nominally opposed Epstein maintained direct personal channels "
            "that bypassed formal representation structures."
        ),
    },
    {
        "name": "Perpetrator-as-Mediator",
        "description": (
            "The October 2015 Dershowitz settlement emails document Epstein actively mediating "
            "a financial dispute between his victims' attorney (Edwards) and his former defense "
            "counsel (Dershowitz), both of whom were engaged in defamation litigation against each "
            "other. The perpetrator's centrality to dispute resolution among parties who were "
            "nominally his adversaries illustrates how Epstein's network operated through "
            "information asymmetry: he had direct access to both sides and neither side could "
            "independently verify what he was telling the other."
        ),
    },
    {
        "name": "Foundation-as-Settlement-Vehicle",
        "description": (
            "The Enhanced Education donation to NCVBA at Edwards's request follows the same "
            "structural pattern seen elsewhere in the corpus: Epstein directing charitable "
            "disbursements to organizations with personal or legal significance to a "
            "counterparty, structured as foundation giving rather than direct payment. This "
            "pattern appears in the Leon Black donation structuring (where explicit steps "
            "were taken to avoid public disclosure of Black's name), the Gratitude America "
            "disbursements to Landon Thomas Jr.'s charity, and the IPI giving coordinated "
            "through Richard Kahn. In each case, the foundation vehicle obscures the "
            "relationship between the ultimate payer and the ultimate recipient."
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
            "id": "legal-proceedings",
            "title": "Legal Proceedings",
            "content": SECTION_LEGAL_PROCEEDINGS,
            "viz": "timeline",
        },
        {
            "id": "key-relationships",
            "title": "Key Relationships",
            "content": SECTION_KEY_RELATIONSHIPS,
            "viz": "ego_network",
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
