#!/usr/bin/env python3
"""Write curation fields into the PILF dossier."""

import json
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/public-interest-legal-foundation.json")

data = json.loads(DOSSIER_PATH.read_text())

curation = data.setdefault("curation", {})

# ── lead ─────────────────────────────────────────────────────────────────────
curation["lead"] = (
    "<p>The Public Interest Legal Foundation (PILF) is a 501(c)(3) nonprofit "
    "(EIN 45-4355641) incorporated in 2012 and headquartered at 1729 King Street, "
    "Alexandria, Virginia. PILF's stated mission is enforcement of the National "
    "Voter Registration Act, primarily through litigation demanding access to state "
    "voter rolls and seeking removal of allegedly ineligible registrants. [Finding #6552] "
    "President J. Christian Adams — who received $274,000 in 2024 compensation — "
    "is the organization's public voice and litigation director; the board is led by "
    "Chair Cleta Mitchell and includes Hans von Spakovsky, the disbarred attorney "
    "John Eastman, former RNC general counsel David Norcross, former Ohio Secretary "
    "of State Ken Blackwell, and Treasurer Neil Corkery. [Finding #6676]</p>"
    "<p>Revenue grew from $562,000 in 2015 to $3.83 million in the 2020 election "
    "year and reached an all-time high of $4.90 million in 2024. [Finding #6563] "
    "Identified foundation funding totals $4.46 million, led by the Lynde and Harry "
    "Bradley Foundation at $3.31 million (2015–2024), the John William Pope "
    "Foundation at $670,000 (2014–2022), and Jaquish &amp; Kenninger Foundation "
    "at $475,000 (2020–2023). [Finding #6563] The twin revenue spikes in 2020 "
    "and 2024 — both presidential election years — track PILF's own press-release "
    "volume around those cycles.</p>"
    "<p>Beginning in 2025, PILF's research output began flowing directly into "
    "federal enforcement. PILF copies all voter-roll demand letters simultaneously "
    "to its former staff attorney Maureen Riordan — who served as Acting Chief of "
    "the DOJ Voting Section from May 2025 — and to Assistant Attorney General "
    "Harmeet Dhillon. [Finding #6641] In July 2025, the DOJ cited PILF data "
    "verbatim in a letter to Pennsylvania Secretary of State Al Schmidt, referencing "
    "19,489 cross-state duplicate registrants, 3,170 same-address duplications, "
    "and 321 placeholder birthdates identified by PILF's research. [Finding #6643] "
    "PILF's two standing-to-sue petitions — PILF v. Schmidt (Pennsylvania) and "
    "PILF v. Benson (Michigan) — were both denied certiorari by the Supreme Court "
    "on March 2, 2026. [Finding #6664]</p>"
)

# ── system_role ───────────────────────────────────────────────────────────────
curation["system_role"] = (
    "PILF functions as the research and litigation arm of an election-integrity "
    "network that connects conservative foundation funding to voter roll enforcement "
    "at the state level, and since 2025 operates as a data supplier to the DOJ "
    "Voting Section through a personnel channel created by the movement of its own "
    "former staff attorney into that office."
)

# ── sections ──────────────────────────────────────────────────────────────────
curation["sections"] = [
    {
        "id": "leadership-and-governance",
        "title": "Leadership and Governance",
        "viz": "ego_network",
        "content": (
            "<p>PILF's board concentrates personnel drawn from prior government "
            "service, Republican Party legal infrastructure, and overlapping "
            "election-integrity organizations. [Finding #6676] Board Chair "
            "<a href=\"/dossiers/cleta-mitchell\">Cleta Mitchell</a> also "
            "leads the Conservative Partnership Institute's Election Integrity "
            "Network, chaired an ALEC election working group, and participated "
            "in the January 6, 2021 call between Donald Trump and Georgia "
            "Secretary of State Brad Raffensperger. Director Hans von Spakovsky "
            "served in the DOJ Civil Rights Division from 2002 to 2005 and "
            "subsequently ran the <a href=\"/dossiers/heritage-foundation\">Heritage "
            "Foundation</a>'s Election Law Reform Initiative before moving to "
            "the Advancing American Freedom Meese Institute in January 2026. "
            "Director John Eastman was disbarred in connection with the Trump "
            "fake-electors scheme. Director David Norcross is a former RNC "
            "general counsel; Director Ken Blackwell is a former Ohio Secretary "
            "of State; Treasurer Neil Corkery has affiliations across multiple "
            "conservative donor-coordination structures.</p>"
            "<p>The board's composition creates institutional ties to "
            "<a href=\"/dossiers/heritage-foundation\">Heritage Foundation</a> "
            "(von Spakovsky), to the Republican National Committee's legal "
            "apparatus (Norcross, Mitchell), and to state-election administration "
            "networks (Blackwell). Legal counsel Charlie Spies is a GOP election "
            "lawyer; outside counsel comes from the Dickinson Wright firm. "
            "[Finding #6676] This concentration of personnel from Republican "
            "electoral infrastructure in PILF's governance positions the "
            "organization to coordinate litigation strategy, research sharing, "
            "and personnel placement across the broader network.</p>"
        ),
    },
    {
        "id": "financial-profile",
        "title": "Financial Profile",
        "viz": None,
        "content": (
            "<p>IRS 990 filings (EIN 45-4355641) record PILF's revenue history "
            "from $1.26 million in 2012 to a trough of $562,000 in 2015, then "
            "growth to $2.20 million in 2017, $3.83 million in 2020, and $4.90 "
            "million in 2024 — the organization's highest recorded year. [Finding "
            "#6563] Net assets grew from $87,000 in 2012 to $2.29 million in "
            "2024. [Finding #6563] Senior staff compensation in 2024 included "
            "$274,000 for Adams, $171,000 for litigation director Noel Johnson, "
            "and $163,000 for litigation counsel Kaylan Phillips. [Finding #6563]</p>"
            "<p>Identified foundation grants total $4.46 million over the period "
            "documented: the Lynde and Harry Bradley Foundation (administered "
            "through <a href=\"/dossiers/bradley-impact-fund-inc\">Bradley Impact Fund</a>) "
            "contributed $3.31 million between 2015 and 2024, designated for PILF's "
            "election law initiative. [Finding #6563] The John William Pope "
            "Foundation granted $670,000 between 2014 and 2022, and Jaquish "
            "&amp; Kenninger Foundation granted $475,000 between 2020 and 2023. "
            "[Finding #6563] The Bradley Impact Fund also granted America First "
            "Legal Foundation $27.1 million in 2022, representing 61 percent of "
            "AFL's revenue that year — an indication of the Fund's scale relative "
            "to its PILF grants and of the broader network it supports.</p>"
            "<p>Revenue in 2020 and 2024 both exceeded prior-year figures by "
            "substantial margins, while the off-cycle years of 2015, 2018, and "
            "2022 show relative troughs. [Finding #6552] [Finding #6563] The "
            "majority of PILF's revenue comes from donors whose identities are "
            "not disclosed in 990 public filings; the three identified foundations "
            "account for roughly 90 percent of provenance-tracked funding.</p>"
        ),
    },
    {
        "id": "litigation-portfolio",
        "title": "Litigation Portfolio",
        "viz": "timeline",
        "content": (
            "<p>PILF's litigation strategy centers on Section 8 of the NVRA, "
            "which requires states to conduct voter list maintenance. The "
            "organization has pursued two distinct legal theories: (1) that "
            "states that deny access to voter roll data violate the NVRA's "
            "public-inspection provision, and (2) that states fail to adequately "
            "remove ineligible registrants — specifically deceased voters, "
            "moved registrants, and alleged noncitizens. [Finding #6553]</p>"
            "<p>PILF v. Winfrey (Detroit, 2019–2020) and PILF v. Boockvar "
            "(Pennsylvania, 2020) were both dismissed. PILF v. Benson (Michigan, "
            "filed 2021) alleged that Michigan failed to remove deceased voters; "
            "it was dismissed by the district court in 2024, appealed, and "
            "certiorari was denied by the Supreme Court on March 2, 2026. "
            "[Finding #6553] PILF v. Schmidt (Pennsylvania) sought to establish "
            "that denial of voter roll access automatically confers standing to "
            "sue, a theory rejected by the Third Circuit's nexus requirement; "
            "the Supreme Court also denied cert in that case on March 2, 2026. "
            "[Finding #6664] <a href=\"/dossiers/judicial-watch\">Judicial Watch</a> "
            "and the Center for Election Confidence filed amicus briefs supporting "
            "PILF's cert petitions. [Finding #6664]</p>"
            "<p>PILF is also co-party with "
            "<a href=\"/dossiers/true-the-vote\">True the Vote</a> in TTV v. IRS "
            "(DC Circuit, 2025–26), which challenges the IRS's treatment of "
            "election-integrity organizations. J. Christian Adams previously served "
            "as True the Vote's counsel in 2013 Colorado voter roll cases. "
            "[Connection #3302] In the Michigan matter, the Trump DOJ filed suit "
            "against Michigan Secretary of State Jocelyn Benson on the same legal "
            "theory as PILF's dismissed case approximately two weeks after PILF's "
            "Supreme Court petition was denied — a sequence consistent with "
            "parallel or coordinated strategy. [Finding #6553]</p>"
        ),
    },
    {
        "id": "doj-channel",
        "title": "DOJ Voting Section Channel",
        "viz": None,
        "content": (
            "<p>Between 2021 and June 2025, Maureen Riordan served as PILF "
            "litigation counsel. In May 2025 she became Acting Chief of the DOJ "
            "Voting Section. [Connection #3307] Beginning in July 2025, PILF "
            "adopted the practice of copying all voter-roll demand letters "
            "simultaneously to Riordan and to AAG Harmeet Dhillon. [Finding #6641] "
            "On July 24, 2025, the DOJ sent a letter to Pennsylvania Secretary "
            "of State Al Schmidt citing PILF research figures directly: 19,489 "
            "cross-state duplicate registrants, 3,170 same-address duplications, "
            "and 321 placeholder birthdates. [Finding #6643] The DOJ also filed "
            "an amicus brief supporting PILF in the Maine voter-roll case, "
            "PILF v. Bellows. [Connection #3309]</p>"
            "<p>The DOJ's Civil Rights Division, overseen by Dhillon, filed "
            "enforcement actions against multiple states on voter roll maintenance "
            "grounds during the same period PILF was sending letters to the "
            "same offices — including Pennsylvania, Michigan, and Maine. [Connection "
            "#3362] Riordan was succeeded as Acting Chief by Eric Neff in December "
            "2025. Neff previously prosecuted the Konnech case relying on "
            "True the Vote evidence, creating a second personnel connection "
            "between PILF's peer organizations and the Voting Section leadership. "
            "[Connection #3307]</p>"
            "<p>The simultaneous denial of PILF's two Supreme Court petitions on "
            "March 2, 2026 limits PILF's ability to compel voter roll access "
            "through independent litigation, which may increase the operational "
            "weight of the DOJ channel as the primary enforcement pathway. "
            "[Finding #6664]</p>"
        ),
    },
]

# ── open_questions ─────────────────────────────────────────────────────────────
curation["open_questions"] = [
    (
        "Who are the anonymous donors accounting for the gap between identified "
        "foundation grants (~$4.46M documented) and total revenue ($4.90M in 2024 "
        "alone)? PILF's 990 Schedule B is not publicly disclosed, and no donor-advised "
        "fund intermediary beyond Bradley Impact Fund has been identified."
    ),
    (
        "What formal or informal coordination mechanisms exist between PILF's "
        "letter-writing campaigns and DOJ Voting Section enforcement target selection? "
        "The simultaneous copying of Riordan and Dhillon on all state letters "
        "is documented, but whether a shared target list or decision protocol "
        "exists has not been established."
    ),
    (
        "What is the full scope of personnel movement among PILF, True the Vote, "
        "Judicial Watch, America First Legal Foundation, Heritage Foundation, and "
        "the DOJ Voting Section? Riordan and Neff are documented; the network "
        "almost certainly extends further."
    ),
    (
        "Did PILF or affiliated personnel participate in the DOGE-SSA voter data "
        "agreement identified by congressional investigators? True the Vote "
        "was separately documented soliciting a DOGE partnership during the same "
        "period, and PILF's DOGE-adjacent board connections have not been traced."
    ),
    (
        "Following the March 2, 2026 Supreme Court cert denials in both PILF v. "
        "Schmidt and PILF v. Benson, will PILF shift its litigation theory, "
        "seek congressional intervention, or rely exclusively on DOJ parallel "
        "enforcement to achieve voter roll access in non-cooperative states?"
    ),
]

# ── applicable_models ──────────────────────────────────────────────────────────
curation["applicable_models"] = [
    "revolving-door",
    "narrative-shield",
    "enabler-gradient",
    "regulatory-capture",
]

# ── write back ────────────────────────────────────────────────────────────────
DOSSIER_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print("Curation written successfully.")
