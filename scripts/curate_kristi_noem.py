#!/usr/bin/env python3
"""Write curation fields into content/dossiers/kristi-noem.json"""
import json
from datetime import datetime, timezone

DOSSIER_PATH = "content/dossiers/kristi-noem.json"

with open(DOSSIER_PATH) as f:
    dossier = json.load(f)

curation = dossier.get("curation", {})

# ── LEAD ────────────────────────────────────────────────────────────────────
curation["lead"] = (
    "<p>Kristi Noem served as the 19th Secretary of Homeland Security from January 25, 2025 "
    "until March 5, 2026, when President Trump dismissed her — the first Cabinet secretary to "
    "leave the post in the second administration. The dismissal followed a bipartisan Senate "
    "confrontation over a $220 million taxpayer-funded advertising campaign that DHS awarded "
    "without competitive bidding, during which Noem told the Senate that Trump had approved the "
    "campaign; the White House publicly denied that account [Finding #5850].</p>"
    "<p>Before her Cabinet appointment, Noem served two terms as Governor of South Dakota "
    "(2019–2025) and four terms as South Dakota's at-large member of the U.S. House of "
    "Representatives (2011–2019). Her federal financial disclosure as a DHS nominee reported "
    "a personal net worth of $520,011 to $1,175,000 and disclosed three LLCs: Ashwood Strategies "
    "LLC (managing member since June 2023), and through her spouse Bryon Noem, Noem Insurance LLC "
    "and Noem Properties LLC [Finding #5855].</p>"
    "<p>A ProPublica investigation found that American Resolve Policy Fund — a 501(c)(4) "
    "nonprofit incorporated on the same day as Ashwood Strategies, four minutes later — paid "
    "Ashwood $80,000 in 2023 and $137,842 in 2024 for fundraising consulting. Neither payment "
    "was disclosed on Noem's DHS ethics form. Ethics experts described the omission as a likely "
    "violation of the Ethics in Government Act [Finding #5852]. The arrangement was also "
    "investigated by Citizens for Responsibility and Ethics in Washington [Finding #4780].</p>"
    "<p>At DHS, Noem appointed <a href=\"/dossiers/corey-lewandowski\">Corey Lewandowski</a> "
    "as an unpaid special government employee who functioned as de facto chief of staff. Internal "
    "DHS records show Lewandowski's name as the final political appointee checkpoint before "
    "Noem's signature on contract routing sheets for all awards over $100,000 — an arrangement "
    "Noem denied under oath in Senate testimony [Finding #5157] [Finding #5180].</p>"
)

# ── SYSTEM ROLE ──────────────────────────────────────────────────────────────
curation["system_role"] = (
    "Noem occupied the secretary role at DHS while three overlapping integrity problems "
    "accumulated: undisclosed personal financial arrangements with a nonprofit that promoted "
    "her political career; procurement decisions that benefited entities connected to her "
    "immediate staff; and a contract oversight structure in which her de facto chief of staff "
    "held final approval authority over awards while refusing to disclose his outside income. "
    "Her dismissal — the product of a public conflict over who authorized a $220 million campaign "
    "— illustrates how accountability at DHS operated through public political exposure rather "
    "than internal oversight mechanisms."
)

# ── SECTIONS ─────────────────────────────────────────────────────────────────
curation["sections"] = [
    {
        "id": "dhs-tenure-and-dismissal",
        "title": "DHS Tenure and Dismissal",
        "viz": None,
        "content": (
            "<p>Noem was confirmed as DHS Secretary on January 25, 2025, and dismissed on "
            "March 5, 2026 — the first Cabinet departure of the second Trump administration. "
            "The immediate trigger was a Senate hearing in which she testified that President "
            "Trump had personally approved a $220 million DHS advertising campaign. The White "
            "House publicly contradicted her account, stating that 'POTUS did not sign off on "
            "a 220 MILLION dollar ad campaign' [Finding #5850]. Sen. Markwayne Mullin was "
            "named as her replacement.</p>"
            "<p>The advertising program had already drawn independent scrutiny before the "
            "Senate confrontation. DHS designated a border enforcement emergency to bypass "
            "competitive bidding requirements and routed the ad work to four hand-picked "
            "contractors. Strategy Group — whose chief executive is married to Tricia McLaughlin, "
            "Noem's former spokesperson — received subcontracted work on the campaign. Noem "
            "separately handpicked contractors for a $100 million ICE recruitment campaign. "
            "A ProPublica investigation found that Noem misled Congress about a top aide's "
            "role in the contract awards [Finding #5851].</p>"
            "<p>Contracts awarded through Safe America Media LLC — a company formed eight days "
            "before its first DHS award — totaled at least $100.8 million across three task "
            "orders: $60.8 million in February 2025 for the 'Stronger Borders, Stronger America' "
            "campaign, $30 million in August 2025 for a second task, and $10 million in August "
            "2025 for ICE recruitment (USASpending award IDs: 70RDA225FR0000009, "
            "70RDA225FR0000034, 70CMSW25FR0000082) [Finding #5175].</p>"
        ),
    },
    {
        "id": "financial-disclosure-and-ashwood-strategies",
        "title": "Financial Disclosure and Ashwood Strategies LLC",
        "viz": None,
        "content": (
            "<p>Noem's Form 278 nominee disclosure (ProPublica TrumpTown slug: noem-kristi, "
            "doc_id 2766) reported a net worth range of $520,011 to $1,175,000. Personal assets "
            "consisted primarily of retirement accounts at Schwab, Vanguard, T. Rowe Price, "
            "Fidelity, and American Balanced. Through her spouse, the household held Noem "
            "Insurance LLC, Noem Properties LLC, and Pierre Car Wash LLC, with at least $2 "
            "million in combined value across those entities [Finding #5855].</p>"
            "<p>Ashwood Strategies LLC was registered in Delaware in June 2023, with Noem as "
            "managing member. American Resolve Policy Fund — a 501(c)(4) nonprofit — was "
            "incorporated the same day, four minutes later. American Resolve paid Ashwood "
            "$80,000 in 2023 as a fundraising fee on $800,000 raised, and $137,842 in 2024 "
            "for continued fundraising consulting, a 70 percent increase year-over-year. "
            "Neither payment appeared on Noem's federal financial disclosure form. The "
            "Citizens for Responsibility and Ethics in Washington confirmed the omission "
            "through independent review, and ethics law experts told ProPublica the "
            "non-disclosure was a likely violation of the Ethics in Government Act "
            "[Finding #5852] [Finding #4780].</p>"
            "<p>The same-day incorporation of Ashwood Strategies and American Resolve Policy "
            "Fund, four minutes apart, is documented in Delaware registry filings. American "
            "Resolve's stated purpose was promoting Noem's political career. The $80,000 "
            "payment in 2023 represented approximately 62 percent of her approximately "
            "$130,000 annual governor's salary at the time [Finding #5852].</p>"
        ),
    },
    {
        "id": "procurement-oversight-and-contract-structure",
        "title": "Procurement Oversight and Contract Structure",
        "viz": None,
        "content": (
            "<p>In June 2025, Noem issued a directive lowering the DHS contract review "
            "threshold from $20 million to $100,000 — a change that ostensibly tightened "
            "oversight by requiring her personal sign-off on a far larger number of awards. "
            "A POGO investigation subsequently found at least five contracts in the range of "
            "$99,999 to $99,999.99 awarded after that directive, a pattern consistent with "
            "deliberate structuring to avoid triggering Noem's own review requirement "
            "[Finding #5854].</p>"
            "<p>One of those sub-threshold contracts was a $99,999.99 USCIS award to "
            "<a href=\"/dossiers/palantir-technologies\">Palantir Technologies</a> for phase "
            "zero implementation of the VOWS platform (Vetting of Wedding-based Immigration "
            "Schemes). Palantir's contracting history with DHS reflects a documented practice "
            "of using low-dollar initial awards to establish incumbency before pursuing larger "
            "follow-on contracts. Palantir's DHS contract portfolio had reached a $1 billion-plus "
            "blanket purchase agreement by February 2026 [Finding #5854] [Finding #5203].</p>"
            "<p>The contract oversight structure itself was compromised. "
            "<a href=\"/dossiers/corey-lewandowski\">Corey Lewandowski</a>, serving as an unpaid "
            "SGE and de facto chief of staff, was the final political appointee checkpoint before "
            "Noem's signature on contract routing sheets for all awards over $100,000. Noem told "
            "the Senate Judiciary Committee that Lewandowski had 'no' role in contract decisions. "
            "Internal DHS routing documents obtained by ProPublica showed his name last on "
            "approval checklists [Finding #5180] [Finding #5157]. Lewandowski declined to disclose "
            "his outside income or clients, and the American Oversight organization filed a FOIA "
            "lawsuit to obtain records of his role [Finding #5157].</p>"
        ),
    },
    {
        "id": "key-relationships",
        "title": "Key Relationships",
        "viz": "ego_network",
        "content": (
            "<p><a href=\"/dossiers/corey-lewandowski\">Corey Lewandowski</a> held the most "
            "operationally significant relationship with Noem at DHS. LittleSis records document "
            "both a professional position — shadow chief of staff with contract approval authority "
            "— and a personal relationship dating to 2019. Lewandowski approved contracts and "
            "reviewed policy before Noem signed. In a March 2026 House hearing, Noem was directly "
            "questioned about the reported personal relationship; both she and Lewandowski have "
            "denied it. Multiple outlets described the relationship as 'Washington's worst-kept "
            "secret' [Connection #2921].</p>"
            "<p>Troy Dean Edgar served as DHS Deputy Secretary under Noem. Edgar's personal "
            "financial disclosure reported holdings in Palantir, Raytheon, and Tesla — each of "
            "which held or was pursuing significant DHS contracts — while he occupied the deputy "
            "role overseeing DHS procurement [Connection #2937] [Finding #5203].</p>"
            "<p><a href=\"/dossiers/aram-moghaddassi\">Aram Moghaddassi</a>, a DOGE detail "
            "assigned to the Social Security Administration and later DHS, coordinated with Noem "
            "on the Death Master File operation in April 2025. Moghaddassi sent a list of 6,300 "
            "immigrants with recently revoked temporary legal status to SSA; Noem signed two "
            "memoranda with Acting SSA Commissioner Leland Dudek authorizing their addition to "
            "the Death Master File under fabricated death dates. Career SSA IT chief Greg Pearre "
            "was physically removed from his office for opposing the action as illegal. Dudek "
            "signed the memoranda despite initially believing the action was illegal "
            "[Connection #3269] [Connection #3273] [Finding #6476].</p>"
        ),
    },
    {
        "id": "death-master-file-operation",
        "title": "Death Master File Operation",
        "viz": None,
        "content": (
            "<p>On April 8, 2025, SSA added 6,300 living immigrants to the Death Master File "
            "(renamed 'Ineligible Master File' for this operation). The list originated at DHS "
            "and comprised individuals whose temporary legal status had been revoked. The "
            "additions used synthetic, fabricated death dates. The population included minors, "
            "including a child as young as 13 [Finding #6476].</p>"
            "<p>The authorization chain ran from <a href=\"/dossiers/aram-moghaddassi\">Aram "
            "Moghaddassi</a> (who transmitted the DHS list to SSA) through Acting Commissioner "
            "Leland Dudek (who signed two memoranda with Noem) to Noem herself (who co-signed "
            "those memoranda as DHS Secretary). Dudek signed despite his initial conclusion "
            "that the action was illegal. <a href=\"/dossiers/doge\">DOGE</a> synthesis "
            "reporting placed Moghaddassi as the operational coordinator [Finding #6476] "
            "[Finding #6506].</p>"
            "<p>SSA partially reversed the additions between March 14 and April 19, 2025, "
            "when it added nearly 11 million individuals to the DMF with markers indicating "
            "deceased status — a mass rollback of the earlier living-immigrant additions. "
            "Approximately 407 records of living immigrants added in April remained active in "
            "the Death Master File as of the date of NCTR reporting. No litigation specifically "
            "targeting the DMF manipulation had been filed; the reversal appears to have been "
            "administrative [Finding #6477].</p>"
        ),
    },
]

# ── OPEN QUESTIONS ───────────────────────────────────────────────────────────
curation["open_questions"] = [
    (
        "American Resolve Policy Fund and Ashwood Strategies LLC were incorporated on the same "
        "day, four minutes apart, in Delaware. Who incorporated each entity, and do the "
        "registered agents share a common law firm or formation service? Full Delaware registry "
        "records would establish whether the simultaneous formation was coordinated and by whom. "
        "[Finding #5852]"
    ),
    (
        "Noem's DHS ethics form did not disclose the Ashwood Strategies payments. The Office of "
        "Government Ethics reviews all Form 278 filings for Cabinet nominees. Did OGE's review "
        "process flag the Ashwood payments as requiring disclosure, and if so, what was the "
        "disposition? If OGE did not flag them, what does that reveal about the agency's access "
        "to nonprofit IRS filings during nominee review? [Finding #5852] [Finding #4780]"
    ),
    (
        "Lewandowski served as an unpaid SGE with contract approval authority over DHS awards "
        "exceeding $100,000 while declining to disclose his outside income and clients. Which "
        "specific contracts above $100,000 carried his signature on approval routing sheets "
        "during his tenure, and do any involve entities that were also clients of Avenue "
        "Strategies or Turnberry Solutions? [Finding #5180] [Finding #5157]"
    ),
    (
        "Safe America Media LLC was formed eight days before receiving its first DHS contract. "
        "Who are its registered members, and what is the ownership structure? The Strategy Group "
        "subcontract relationship — where the CEO is married to Noem's former spokesperson "
        "Tricia McLaughlin — was described as secret. Did McLaughlin have any formal or informal "
        "role in the contract award process while at DHS? [Finding #5175] [Finding #5851]"
    ),
    (
        "The $99,999.99 USCIS contract to Palantir for VOWS phase zero was awarded after Noem's "
        "directive established a $100,000 review threshold. Was the Palantir award reviewed by "
        "Lewandowski or Noem despite falling one cent below the threshold, and what is the full "
        "VOWS contract pipeline — have follow-on awards been issued, and if so, at what values? "
        "[Finding #5854]"
    ),
    (
        "The two memoranda that Noem and Acting Commissioner Dudek signed authorizing Death "
        "Master File additions have not been publicly released. What are their precise dates, "
        "what legal authority do they cite, and do they reference the fabricated death dates "
        "or acknowledge the immigrant population involved? [Finding #6476]"
    ),
    (
        "Noem told the Senate that Trump personally approved the $220 million ad campaign; the "
        "White House denied it. Both accounts cannot be correct. Is there documentary evidence — "
        "meeting notes, emails, or approval routing — that establishes which account is accurate, "
        "and has any congressional committee subpoenaed that documentation? [Finding #5850]"
    ),
]

# ── APPLICABLE MODELS ────────────────────────────────────────────────────────
curation["applicable_models"] = [
    "pay-to-play",
    "revolving-door",
    "regulatory-capture",
    "enabler-gradient",
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
