#!/usr/bin/env python3
"""Write curation fields into content/dossiers/stephen-miller.json"""
import json
from datetime import datetime, timezone

DOSSIER_PATH = "content/dossiers/stephen-miller.json"

with open(DOSSIER_PATH) as f:
    dossier = json.load(f)

curation = dossier.get("curation", {})

# ── LEAD ────────────────────────────────────────────────────────────────────
curation["lead"] = (
    "<p>Stephen Miller is the Deputy Chief of Staff for Policy and Homeland Security Advisor "
    "in the Trump White House, a position he has held since January 20, 2025. He is the "
    "primary author of the administration's immigration executive orders and has issued a "
    "standing directive demanding 3,000 ICE arrests per day [Finding #4786]. His office holds "
    "weekly coordination meetings with DHS and DOJ leadership on election enforcement plans "
    "[Finding #6527], and he drafted a plan to give the White House expanded influence over "
    "DHS, FBI, and DOJ investigations [Finding #6529].</p>"
    "<p>Miller disclosed holding $100,001 to $250,000 in <a href=\"/dossiers/palantir-technologies\">Palantir Technologies</a> "
    "stock in a child's brokerage account — classified as his own under 18 U.S.C. § 208 "
    "conflict-of-interest law — while directly overseeing ICE deportation policy that is "
    "operationally dependent on Palantir systems, including the $30 million ImmigrationOS "
    "sole-source contract and the FALCON, ICM, and ELITE platforms [Finding #4775] "
    "[Finding #4627]. Multiple DHS officials beyond Miller also hold Palantir stock [Finding #4845].</p>"
    "<p>From February 2021 through January 2025, Miller co-founded and served as President and "
    "Executive Director of <a href=\"/dossiers/america-first-legal-foundation\">America First Legal Foundation</a>, "
    "drawing $527,000 in annual compensation from the organization [Finding #4786]. AFL's revenue "
    "spiked from $6.4 million in 2021 to $44.4 million in 2022, a period that aligns with a "
    "$50 million-plus donation from <a href=\"/dossiers/elon-musk\">Elon Musk</a> to Citizens for Sanity, "
    "an organization run by AFL employees [Finding #4775] [Finding #4627].</p>"
)

# ── SYSTEM ROLE ──────────────────────────────────────────────────────────────
curation["system_role"] = (
    "Miller occupies the intersection of White House policy authority, federal law enforcement "
    "coordination, and nonprofit litigation infrastructure: he wrote the executive orders that "
    "define immigration and election enforcement priorities, controls the DHS and DOJ coordination "
    "cadence through his office, and built the external legal organization that litigated the same "
    "policy agenda during the interregnum between Trump administrations — while holding a disclosed "
    "financial stake in the primary technology contractor executing that agenda."
)

# ── SECTIONS ─────────────────────────────────────────────────────────────────
curation["sections"] = [
    {
        "id": "government-role-and-authority",
        "title": "Government Role and Authority",
        "viz": None,
        "content": (
            "<p>Miller serves as Deputy Chief of Staff for Policy and Homeland Security Advisor, "
            "a dual-hatted position making him the most senior White House official dedicated to "
            "immigration and enforcement policy. He has been described by reporting from Axios and "
            "ProPublica as effectively calling the shots at DHS [Finding #6529]. His office directly "
            "coordinates with both DHS and DOJ leadership, conducting weekly meetings on election "
            "enforcement plans [Finding #6527]. He drafted a plan to give the White House direct "
            "influence over DHS, FBI, and DOJ investigations — an arrangement that would centralize "
            "operational control of federal law enforcement in his office [Finding #6529].</p>"
            "<p>On immigration, Miller functions as the policy principal above Border Czar "
            "Tom Homan: Miller writes the executive orders and sets arrest quotas of 3,000 per day; "
            "Homan executes the resulting deportation operations [Finding #4786]. The chain runs "
            "from Miller's office through Homan's field operations to Palantir's ImmigrationOS "
            "targeting platform [Finding #4793]. On election enforcement, Miller's office coordinates "
            "with DOJ's Pam Bondi on voter roll demands and investigations [Finding #6527], and "
            "directs Heather Honey, the DHS election integrity deputy, through those weekly "
            "enforcement meetings [Finding #6529].</p>"
        ),
    },
    {
        "id": "palantir-conflict-of-interest",
        "title": "Palantir Stock and Policy Conflict",
        "viz": None,
        "content": (
            "<p>Miller's financial disclosure reported $100,001 to $250,000 in "
            "<a href=\"/dossiers/palantir-technologies\">Palantir Technologies</a> stock held in "
            "a brokerage account for one of his three children. Under federal ethics law "
            "(18 U.S.C. § 208), financial interests held in a minor child's account are attributed "
            "to the parent and trigger the same conflict restrictions as direct holdings "
            "[Finding #4775]. Ethics experts cited in POGO's investigation concluded that Miller "
            "was required to recuse from decisions affecting Palantir, which he did not do "
            "[Finding #4627].</p>"
            "<p>The conflict is material because Palantir holds the primary ICE surveillance "
            "contracts executing the policy Miller designs: the $30 million ImmigrationOS "
            "sole-source contract, the FALCON dragnet database, the ICM case management system, "
            "and the ELITE targeting tool that generates confidence-scored deportation dossiers "
            "from Medicaid and DMV data [Finding #4775]. Miller's 3,000-arrests-per-day quota "
            "is operationally dependent on the throughput capacity of these platforms. At least "
            "four other DHS officials held Palantir stock simultaneously, suggesting the conflict "
            "extended across the enforcement chain [Finding #4845].</p>"
        ),
    },
    {
        "id": "america-first-legal-interregnum",
        "title": "America First Legal Foundation: The Interregnum Organization",
        "viz": None,
        "content": (
            "<p>Miller co-founded <a href=\"/dossiers/america-first-legal-foundation\">America First Legal Foundation</a> "
            "in February 2021 and served as its President and Executive Director until returning to "
            "the White House in January 2025 [Finding #6529]. During that four-year period he drew "
            "$527,000 in annual compensation from AFL [Finding #4786]. Co-founder "
            "Gene Hamilton — also a Sessions alumni and key coordination partner from Trump 1.0 — "
            "served as Vice President and General Counsel at $645,000 per year before rotating "
            "to Deputy White House Counsel in January 2025 [Finding #4786].</p>"
            "<p>AFL's revenue rose sharply from $6.4 million in 2021 to $44.4 million in 2022, "
            "then dropped to $9.6 million in 2023 before recovering to $32 million in 2024. "
            "The 2022 spike aligns with <a href=\"/dossiers/elon-musk\">Elon Musk</a>'s $50 million-plus "
            "donation to Citizens for Sanity, an organization run by AFL employees [Finding #4775]. "
            "AFL received $21.3 million from DonorsTrust in 2024 — up from $3.2 million the "
            "prior year — which is a fiscally sponsored conduit for anonymous donors [Finding #4781]. "
            "Russ Vought, now OMB Director, served as AFL board treasurer during the interregnum, "
            "connecting the organization's budget architecture directly to the official now "
            "controlling DHS and ICE appropriations [Finding #4793].</p>"
            "<p>AFL's litigation portfolio during Miller's presidency mirrored the enforcement "
            "agenda he would later implement from the White House: NVRA lawsuits demanding voter "
            "roll purges across Arizona counties, challenges to refugee admissions, and DEI-focused "
            "employment litigation. The AFL revolving door extended beyond Miller and Hamilton: "
            "Reed Rubinstein (AFL SVP) was confirmed as State Department Legal Adviser in May 2025; "
            "John Zadrozny, a FAIR alumnus who carried out Miller's immigration agenda at USCIS "
            "during Trump 1.0, continued in that network [Finding #4793].</p>"
        ),
    },
    {
        "id": "network-origins-and-ideological-formation",
        "title": "Network Origins and Ideological Formation",
        "viz": "ego_network",
        "content": (
            "<p>Miller's entry to Washington immigration policy ran through Jeff Sessions. He joined "
            "Sessions's Senate office as press secretary in 2009 and rose to chief of communications. "
            "It was in Sessions's orbit that he met Gene Hamilton, who became his closest policy "
            "collaborator across both Trump administrations [Finding #4786]. The Sessions–Miller–Hamilton "
            "triad coordinated immigration policy in Trump 1.0 largely without the knowledge of "
            "other senior officials [Finding #4793].</p>"
            "<p>The alliance with <a href=\"/dossiers/steve-bannon\">Steve Bannon</a> dates to a "
            "2012 dinner attended by Bannon and Sessions. From 2015 to 2016, while still working "
            "for Sessions, Miller sent approximately 900 emails to Breitbart editors, functioning "
            "as a de facto assignment editor who directed coverage including content sourced from "
            "white nationalist websites. The Southern Poverty Law Center obtained those emails "
            "through a leak and published them in 2019. Bannon recruited Miller to the Trump "
            "campaign in January 2016 [Finding #4793].</p>"
            "<p>Miller's pre-government formation included executive roles at the Duke Conservative "
            "Union and Students for Academic Freedom, where he encountered Richard Spencer. He "
            "developed working relationships with organizations in the Tanton network — FAIR, CIS, "
            "and NumbersUSA — and collaborated with David Horowitz's Freedom Center "
            "[Finding #4813]. These organizational ties provided the policy infrastructure "
            "that Miller deployed once inside government.</p>"
        ),
    },
    {
        "id": "election-enforcement-coordination",
        "title": "Election Enforcement Coordination",
        "viz": None,
        "content": (
            "<p>As of March 2026, Miller's office is running weekly meetings with DHS and DOJ "
            "leadership on election enforcement plans, making him the central node in a coordination "
            "structure that spans Homeland Security Investigations, the Justice Department, and the "
            "White House [Finding #6527]. The <a href=\"/dossiers/doj-voting-section\">DOJ Voting Section</a> "
            "— restructured under the new administration to pursue voter roll purges rather than "
            "access protection — operates within the policy framework Miller's office sets "
            "[Finding #6529].</p>"
            "<p>Heather Honey serves as the DHS election integrity deputy and participates in "
            "those weekly meetings under Miller's direction. Separately, Miller's office coordinates "
            "with <a href=\"/dossiers/pam-bondi\">Pam Bondi</a>'s DOJ on voter roll demands sent to "
            "states [Finding #6527]. The parallel structure — HSI conducting field investigations "
            "while DOJ pursues data through litigation — mirrors the architecture AFL built from "
            "the outside during 2021–2025, when it filed NVRA lawsuits against Arizona counties "
            "demanding noncitizen voter roll removals [Finding #4813].</p>"
        ),
    },
    {
        "id": "household-network",
        "title": "Household and Spousal Network",
        "viz": None,
        "content": (
            "<p>Miller is married to Katie Miller, who served as communications director for "
            "<a href=\"/dossiers/doge\">DOGE</a> while Stephen held the Deputy Chief of Staff "
            "role. The arrangement placed DOGE's public messaging and White House immigration "
            "and enforcement policy within the same household, alongside Katie's concurrent "
            "membership on the President's Intelligence Advisory Board [Finding #3084].</p>"
            "<p>Before joining DOGE, Katie Miller served as a Senior Advisor to Building America's "
            "Future from September 2024. P2 Pathway Public Affairs — a firm she co-operated with "
            "Generra Peck and Phil Cox — received $210,000 from Building America's Future during "
            "that period [Finding #3358]. The overlap between transition-adjacent consulting revenue "
            "and subsequent government appointments is one pattern investigators have flagged "
            "across multiple Trump transition figures.</p>"
        ),
    },
]

# ── OPEN QUESTIONS ───────────────────────────────────────────────────────────
curation["open_questions"] = [
    (
        "Did Miller execute a formal recusal from any Palantir-related procurement decisions — "
        "ImmigrationOS, FALCON, ELITE, or USCIS VOWS — after his Palantir stock holding was "
        "disclosed, and if so, which official served as the recusal designee for those decisions? "
        "[Finding #4775] [Finding #4627]"
    ),
    (
        "What was the full capitalization and donor composition of Citizens for Sanity during 2022, "
        "and is the $50 million-plus Musk attribution to that organization fully corroborated by "
        "available 990 data, or does the underlying donation flow through one or more fiscal "
        "sponsors including DonorsTrust? [Finding #4775]"
    ),
    (
        "Russ Vought served as AFL board treasurer while AFL litigated election and immigration "
        "policy — now, as OMB Director, he controls the DHS and ICE budget lines that fund "
        "Palantir and GEO Group contracts. Is there documentary evidence of coordination between "
        "Vought's OMB and Miller's office on DHS appropriations or contract approvals that "
        "directly benefit AFL-adjacent organizations? [Finding #4793]"
    ),
    (
        "The 900 emails Miller sent to Breitbart editors were obtained by SPLC through a leak. "
        "Were any of those emails sent from a government email account while Miller was employed "
        "by Sessions's Senate office, and has any congressional oversight body subpoenaed them? "
        "[Finding #4793]"
    ),
    (
        "Katie Miller's P2 Pathway Public Affairs received $210,000 from Building America's Future "
        "before she joined DOGE. What services did P2 Pathway provide, who authorized the BAF "
        "payment, and does BAF's donor list overlap with AFL's major contributors? [Finding #3358]"
    ),
    (
        "Gene Hamilton's AFL compensation was $645,000 in 2024 (including a $120,000 deferred "
        "payment) before he rotated to Deputy White House Counsel in January 2025. What are the "
        "terms of any deferred compensation arrangement between Hamilton and AFL, and does that "
        "arrangement create ongoing financial ties to the organization while he serves in government?"
    ),
]

# ── APPLICABLE MODELS ────────────────────────────────────────────────────────
curation["applicable_models"] = [
    "enabler-gradient",
    "revolving-door",
    "bridge-tax",
    "private-order",
    "narrative-shield",
]

curation["curated_at"] = datetime.now(timezone.utc).isoformat()

dossier["curation"] = curation

with open(DOSSIER_PATH, "w") as f:
    json.dump(dossier, f, indent=2)
    f.write("\n")

print("Curation written successfully.")
print(f"  lead: {len(curation['lead'])} chars")
print(f"  system_role: {len(curation['system_role'])} chars")
print(f"  sections: {len(curation['sections'])}")
print(f"  open_questions: {len(curation['open_questions'])}")
print(f"  applicable_models: {curation['applicable_models']}")
