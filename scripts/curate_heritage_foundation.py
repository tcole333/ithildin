#!/usr/bin/env python3
"""
Curate Heritage Foundation dossier.
Writes curation fields into content/dossiers/heritage-foundation.json.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

DOSSIER_PATH = Path("content/dossiers/heritage-foundation.json")

LEAD = (
    "<p>The Heritage Foundation is a 501(c)(3) public-policy research organization founded in 1973 "
    "(EIN 23-7327730), headquartered at 214 Massachusetts Avenue NE, Washington, D.C. It reports "
    "annual revenue consistently in the $100–120 million range, making it the largest think tank "
    "principally organized around conservative domestic and foreign policy. Heritage's structural "
    "significance inside the current investigation derives from three roles it performs "
    "simultaneously: authoring the policy blueprint for the second Trump administration "
    "(Project 2025), maintaining the primary private-sector database used to justify federal "
    "election-enforcement actions (the Election Fraud Database), and serving as the institutional "
    "home that trained and credentialed the personnel who now populate <a href=\"/dossiers/advancing-american-freedom\">Advancing American Freedom</a>, "
    "<a href=\"/dossiers/public-interest-legal-foundation\">Public Interest Legal Foundation</a>, and the broader DOJ Voting Section alumni network "
    "[Finding #6549] [Finding #6551].</p>"
    "<p>In October 2025, Heritage President Kevin Roberts refused to retract a statement defending "
    "Tucker Carlson's interview with white nationalist Nick Fuentes, triggering a mass departure of "
    "more than 60 staff by January 2026. The exodus was not a random personnel churn: it removed "
    "the heads of Heritage's legal center (John Malcolm), economic center (Richard Stern), and "
    "data team (Kevin Dayaratna), along with Hans von Spakovsky, who managed Heritage's Election "
    "Law Reform Initiative and authored the federal election oversight chapter of Project 2025. All "
    "migrated to AAF's three newly created institutes, which are structural mirrors of the Heritage "
    "centers they vacated [Finding #6634] [Finding #6649]. The Diana Davis Spencer Foundation "
    "simultaneously withdrew a multi-million-dollar five-year funding commitment and its CEO "
    "resigned as Heritage trustee [Finding #6634]. What the event produced, in operational terms, "
    "was a transfer of institutional capability — legal, economic, and data-analytic — from one "
    "organization to another, while the underlying Election Fraud Database and Project 2025 "
    "infrastructure remained at Heritage.</p>"
)

SYSTEM_ROLE = (
    "Heritage Foundation is the policy and personnel factory for the American conservative "
    "movement, functioning in this investigation primarily as the source organization for the "
    "election-enforcement and executive-power infrastructure now operating inside and adjacent to "
    "the second Trump administration. Its significance is threefold: (1) Project 2025, authored "
    "under Heritage's coordination, served as the staffing and policy manual that the "
    "administration implemented from day one, including the chapters written by personnel who "
    "subsequently entered government; (2) the Election Fraud Database has operated since 2017 as "
    "the intellectual justification for NVRA voter-roll litigation filed by PILF, AFL, and Judicial "
    "Watch, even though the Brennan Center concluded its own data undermines claims of widespread "
    "fraud; (3) the December 2025 staff exodus effectively transplanted Heritage's operational "
    "legal, economic, and data teams into AAF, splitting the conservative think-tank ecosystem "
    "along a Pence/traditional-conservative vs. Roberts/MAGA fault line without dissolving the "
    "underlying network. Heritage trained and credentialed the people now running election "
    "enforcement litigation, election integrity advocacy, and federal spending oversight — the "
    "institution's influence persists through its alumni even as its own organizational coherence "
    "is now contested."
)

SECTIONS = [
    {
        "id": "project-2025-and-policy-pipeline",
        "title": "Project 2025 and the Policy-to-Government Pipeline",
        "viz": None,
        "content": (
            "<p>Heritage coordinated the production of Project 2025, the 887-page Mandate for "
            "Leadership that served as the policy and personnel blueprint for the second Trump "
            "administration. Within the document, Heritage scholars authored or co-authored "
            "chapters covering federal election oversight (Hans von Spakovsky), Arctic and "
            "Greenland policy (through the Allison Center for Foreign Policy Studies), and "
            "multiple domestic policy domains. The Arctic section explicitly recommended "
            "'enhanced economic ties' with Greenland and a permanent U.S. consulate there — "
            "recommendations Heritage subsequently publicized under the tagline 'Heritage Leads "
            "the Way on U.S. Policy With Greenland' [Finding #6146]. Luke Coffey, then director "
            "of the Allison Center, published multiple papers arguing for U.S. Arctic defense "
            "integration with Greenland before departing for the Hudson Institute.</p>"
            "<p>The Project 2025 pipeline operated through Heritage Action for America, "
            "Heritage's 501(c)(4) affiliate, which received $8.8 million from the Only Citizens "
            "Vote Coalition's identified donor network (the Issue One figure, covering the "
            "2020–2024 period). That coalition, coordinated by "
            "<a href=\"/dossiers/cleta-mitchell\">Cleta Mitchell</a> through the "
            "<a href=\"/dossiers/conservative-partnership-institute\">Conservative Partnership "
            "Institute</a>'s Election Integrity Network, co-hosted EIN summits with the RNC and "
            "lists Heritage as a sponsor [Finding #6678]. Twenty or more EIN member organizations "
            "participated in Project 2025, creating an overlap between Heritage's intellectual "
            "output and the litigation and activation network built around Mitchell's EIN "
            "[Finding #6680].</p>"
            "<p>The Greenland policy thread links Heritage directly to "
            "<a href=\"/dossiers/rebekah-mercer\">Rebekah Mercer</a>, who holds a Heritage "
            "trustee seat. Mercer co-founded <a href=\"/dossiers/1789-capital\">1789 Capital</a> "
            "with Donald Trump Jr. and Omeed Malik; the fund holds positions in Vulcan Elements "
            "(which received a $620 million DoD loan under Project Vault), Anduril, and SpaceX — "
            "companies whose contract revenues are materially affected by the Greenland mineral "
            "and Arctic defense policies Heritage publicly advocated [Finding #6146] "
            "[Finding #6141]. Heritage praised Project Vault as 'Trump's Bold Plan To Stop China "
            "From Starving Our Military.' The Mercer-Heritage-1789 Capital triangle places a "
            "Heritage trustee simultaneously on the board of a private fund that profits from "
            "the defense and resource policies Heritage's scholars recommended in Project 2025.</p>"
        ),
    },
    {
        "id": "election-fraud-database",
        "title": "The Election Fraud Database and NVRA Enforcement Architecture",
        "viz": None,
        "content": (
            "<p>Heritage launched the Election Fraud Database at electionfraud.heritage.org in "
            "2017, managed by Hans von Spakovsky through Heritage's Election Law Reform "
            "Initiative. The database catalogs instances of alleged voter fraud across the "
            "United States and is routinely cited by NVRA litigants as evidence that voter-roll "
            "maintenance is necessary to address a documented fraud problem. The Brennan Center "
            "for Justice published a counter-analysis concluding the database's own data "
            "demonstrates voter fraud is statistically rare — not the basis for broad voter-roll "
            "purge programs. The database's evidentiary value is thus contested, yet it continues "
            "to function as the cited authority in filings by "
            "<a href=\"/dossiers/public-interest-legal-foundation\">Public Interest Legal "
            "Foundation</a> and "
            "<a href=\"/dossiers/america-first-legal-foundation\">America First Legal "
            "Foundation</a> [Finding #6551].</p>"
            "<p>Von Spakovsky also served on Trump's 2017 Presidential Advisory Commission on "
            "Election Integrity (PACEI), alongside J. Christian Adams (now PILF president), Ken "
            "Blackwell, and Kris Kobach. All four remain active in the election enforcement "
            "network as of March 2026, operating through PILF, AAF, FRC/AFPI, and the Kansas "
            "Attorney General's office respectively [Finding #6609]. The network's coordination "
            "hub is the Election Integrity Network at CPI: Heritage was a summit sponsor, "
            "von Spakovsky sat on the PILF board while running Heritage's election operation, "
            "and Mitchell simultaneously chairs PILF while running EIN — positions that create "
            "a closed feedback loop between database production (Heritage/AAF), litigation "
            "strategy (PILF/AFL/JW), and grassroots activation (EIN) [Finding #6678] "
            "[Finding #6560].</p>"
            "<p>Von Spakovsky's departure to AAF in January 2026 transferred his personal "
            "expertise and network relationships to the Pence organization, but the Election "
            "Fraud Database's intellectual property remained at Heritage. Heritage stated "
            "publicly that election integrity remains a 2026 organizational priority, meaning "
            "both institutions now claim the same policy domain with partially overlapping "
            "personnel histories [Finding #6636].</p>"
        ),
    },
    {
        "id": "december-2025-fracture",
        "title": "The December 2025 Staff Exodus and Factional Split",
        "viz": None,
        "content": (
            "<p>On October 30, 2025, Heritage President Kevin Roberts posted a video defending "
            "Tucker Carlson's friendly interview with white nationalist Nick Fuentes, using the "
            "phrase 'venomous coalition' to describe critics. Roberts declined to retract the "
            "statement over the following seven weeks. On December 22, 2025, thirteen staff "
            "members moved simultaneously to "
            "<a href=\"/dossiers/advancing-american-freedom\">Advancing American Freedom</a>, "
            "which launched three new institutes that day: the Edwin Meese III Institute for the "
            "Rule of Law (legal), the Plymouth Rock Institute (economic), and the Center for "
            "Statistical Modeling (data). The names mirror Heritage's own Meese Center for Legal "
            "and Judicial Studies, Roe Institute for Economic Policy Studies, and data analytics "
            "group [Finding #6634] [Finding #6649].</p>"
            "<p>The confirmed departures by name, drawn from AAF press releases, Jewish Insider, "
            "Reason.com, and Washington Examiner coverage, include: from the legal team — John "
            "Malcolm (VP), Hans von Spakovsky (Senior Legal Fellow), Tom Jipping, Paul Larkin, "
            "Amy Swearer, Jessica Reinsch, Jenna Hageman, and Meaghen McManus; from the economic "
            "team — Richard Stern (VP), Joel Griffith, Rachel Greszler, David Burton, Andrew "
            "Hale, Preston Brashers, John Peluso, and Austin Gae; from the data team — Kevin "
            "Dayaratna (VP), Philip Eigen, and Gadai Bulgac. Three Heritage trustees also "
            "resigned: Robby George (Princeton), Shane McCullar, and Abby Spencer Moffat (CEO "
            "of the Diana Davis Spencer Foundation). Moffat's resignation came with the "
            "withdrawal of a multi-million-dollar five-year funding commitment from the "
            "foundation. Eight or more members of Heritage's internal antisemitism task force "
            "resigned separately. By January 2026, Think Tank Watch reported total departures "
            "exceeding 60 [Finding #6649] [Finding #6634].</p>"
            "<p>Heritage restocked key positions: Jay Richards was promoted to Vice President, "
            "Stewart Whitson hired as Chief of Staff, and Peter St. Onge returned as Senior "
            "Economist. Heritage maintained that election integrity and its core policy work "
            "would continue. The ideological diagnosis offered by the departing Pence faction — "
            "that the split reflected a choice between Reagan-era free-market conservatism and "
            "Trump-era economic nationalism and tolerance of far-right figures — is framing "
            "supplied by one side of the dispute and cannot be independently verified from "
            "primary sources. What the primary record documents is the scale of the personnel "
            "transfer and the structural mirroring of AAF's new institutes to Heritage's vacated "
            "centers [Finding #6640].</p>"
        ),
    },
    {
        "id": "key-relationships",
        "title": "Key Organizational Relationships",
        "viz": "ego_network",
        "content": (
            "<p><strong><a href=\"/dossiers/advancing-american-freedom\">Advancing American "
            "Freedom</a></strong>: The successor relationship between Heritage and AAF is not "
            "merely adversarial — AAF absorbed Heritage's functional legal, economic, and data "
            "infrastructure wholesale. AAF's three new institutes replicate Heritage's three "
            "departing centers in structure, personnel, and stated mission. Marc Short, AAF's "
            "board chairman and former Pence Chief of Staff, commands an organization that is "
            "simultaneously a competitor to Heritage for conservative donor funding and an "
            "inheritor of Heritage's operational capability [Connection #3340].</p>"
            "<p><strong><a href=\"/dossiers/public-interest-legal-foundation\">Public Interest "
            "Legal Foundation</a></strong>: Heritage and PILF are connected through two distinct "
            "channels. First, von Spakovsky served on the PILF board while simultaneously "
            "directing Heritage's election law initiative — making him a structural link between "
            "Heritage's database production and PILF's litigation deployment of that data "
            "[Connection #3306]. Second, both von Spakovsky and PILF president J. Christian "
            "Adams are DOJ Civil Rights Division and 2017 PACEI alumni, placing them in the same "
            "founding cohort of the modern election-enforcement network [Finding #6560] "
            "[Connection #3366].</p>"
            "<p><strong><a href=\"/dossiers/america-first-legal-foundation\">America First "
            "Legal Foundation</a></strong>: AFL cites Heritage's Election Fraud Database and "
            "Project 2025 election chapter as the intellectual framework justifying its NVRA "
            "voter-roll litigation. AFL's September 2024 filings against fifteen Arizona "
            "counties and its July 2025 EAC rulemaking petition parallel the policy positions "
            "Heritage's scholars articulated in Project 2025. The Heritage-AFL relationship is "
            "advisory rather than financial or organizational [Connection #3305].</p>"
            "<p><strong><a href=\"/dossiers/1789-capital\">1789 Capital</a></strong>: The "
            "Mercer-Heritage trustee connection creates a policy-investment overlap: a Heritage "
            "trustee holds financial interests in companies whose contract revenues are affected "
            "by policies Heritage scholars publicly recommended. The connection is indirect — "
            "Mercer is a trustee, not Heritage's funder in a controlling sense — but the overlap "
            "is documented by SEC Form D filings (1789 Capital) and Heritage's own impact page "
            "on Greenland policy [Connection #3165] [Finding #6146].</p>"
            "<p><strong>Diana Davis Spencer Foundation</strong>: As Heritage's former major "
            "multi-year funder, the foundation's withdrawal of a multi-million-dollar commitment "
            "and CEO Abby Spencer Moffat's resignation as trustee represent a concrete financial "
            "consequence of the Roberts controversy. The dollar amount reported in multiple "
            "outlets is in the several-million-dollar range for a five-year commitment; Heritage "
            "has not disclosed the figure in public filings [Connection #3344].</p>"
        ),
    },
    {
        "id": "financial-profile",
        "title": "Financial Profile",
        "viz": None,
        "content": (
            "<p>Heritage's IRS Form 990 (EIN 23-7327730) documents revenue stable in the "
            "$100–120 million range from 2013 through 2022, with assets significantly above "
            "$100 million as of the most recent available filing year. The organization is "
            "classified under NTEE code W050 (public policy research) and has held 501(c)(3) "
            "status since 1973. Its revenue scale dwarfs the organizations that absorbed its "
            "departing staff: AAF reported $10.7 million in 2024 revenue across its two "
            "entities, and PILF reported approximately $3.4 million. Even post-exodus, Heritage "
            "retains an order-of-magnitude financial advantage over the organizations it spawned "
            "[Finding #6549].</p>"
            "<p>Heritage Action for America, the 501(c)(4) affiliate, received $8.8 million "
            "from the Only Citizens Vote Coalition donor network as tracked by Issue One over the "
            "2020–2024 period. Heritage does not publicly disclose individual donors to either "
            "the 501(c)(3) or the 501(c)(4), consistent with the donor-advised fund opacity "
            "structure that characterizes the broader conservative funding network. The Diana "
            "Davis Spencer Foundation withdrawal and the loss of the multi-million-dollar "
            "five-year commitment represent the first documented major donor defection tied "
            "directly to a Heritage leadership decision [Finding #6634] [Finding #6667].</p>"
        ),
    },
]

OPEN_QUESTIONS = [
    (
        "What is the precise dollar figure of the Diana Davis Spencer Foundation's withdrawn "
        "multi-year funding commitment, and what was the complete inventory of other major donors "
        "who reduced or ended support following the Roberts-Fuentes controversy? Heritage's 990 "
        "filings will not reflect this until the 2025 return is filed; the full financial impact "
        "of the December 2025 crisis is not yet documented in primary sources."
    ),
    (
        "Did Kevin Roberts take any formal board or advisory position at any organization linked "
        "to Nick Fuentes, Tucker Carlson, or the broader nationalist media network? His refusal "
        "to retract the Fuentes defense has been attributed to ideological alignment rather than "
        "organizational relationship, but the underlying financial or organizational connections, "
        "if any, have not been established from primary sources."
    ),
    (
        "How does Heritage intend to maintain its Election Fraud Database operational capacity "
        "after losing von Spakovsky and the data analytics team to AAF? The database's principal "
        "architect has left, but Heritage stated publicly it remains committed to election "
        "integrity work in 2026. Who now manages the database, and has any methodology or data "
        "changed?"
    ),
    (
        "What is the nature of Rebekah Mercer's active involvement as Heritage trustee — does she "
        "sit on any subcommittees with authority over research priorities or personnel decisions — "
        "and did she take any position on the Roberts controversy before or after the December "
        "2025 exodus? Her Heritage board role and 1789 Capital partnership with Trump Jr. are "
        "documented; her specific governance activity at Heritage is not."
    ),
    (
        "Project 2025 was publicly disavowed by the Trump campaign in July 2024 but its policy "
        "recommendations were implemented at a high rate after inauguration. What is Heritage's "
        "current public account of which Project 2025 chapters have been adopted, and does the "
        "organization maintain any formal tracking relationship with White House personnel who "
        "were identified in the document?"
    ),
]

APPLICABLE_MODELS = [
    "revolving-door",
    "parallel-financial-system",
    "regulatory-capture",
    "private-order",
    "narrative-shield",
]


def main():
    with open(DOSSIER_PATH) as f:
        dossier = json.load(f)

    existing_curation = dossier.get("curation", {})

    existing_curation["lead"] = LEAD
    existing_curation["system_role"] = SYSTEM_ROLE
    existing_curation["sections"] = SECTIONS
    existing_curation["open_questions"] = OPEN_QUESTIONS
    existing_curation["applicable_models"] = APPLICABLE_MODELS
    existing_curation["curated_at"] = datetime.now(timezone.utc).isoformat()

    dossier["curation"] = existing_curation

    with open(DOSSIER_PATH, "w") as f:
        json.dump(dossier, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote curation to {DOSSIER_PATH}")
    print(f"  lead: {len(LEAD)} chars")
    print(f"  system_role: {len(SYSTEM_ROLE)} chars")
    print(f"  sections: {len(SECTIONS)}")
    print(f"  open_questions: {len(OPEN_QUESTIONS)}")
    print(f"  applicable_models: {APPLICABLE_MODELS}")


if __name__ == "__main__":
    main()
