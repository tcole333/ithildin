# Reporting-Corpus Entity Mining — People & Orgs the Investigation Under-Covers
**Date:** 2026-07-13 | **Corpus:** `datasets/epstein_reporting.db` (7,775 articles / 6,837 full-text, 30+ languages)
**Method:** capitalized n-gram harvest over titles+deks+abstracts+body (43,498 raw names), frequency-ranked and cross-checked against `investigation.db` (findings + entities) and `epstein_derived.db` person_resolution (83.7K primary-doc persons).
**Agent:** entity-gaps lens (Claude Fable 5 subagent). Working scripts preserved in /tmp/osint-4sJjo0zA/ (harvest.py, crosscheck.py, gapfts.py, readarts.py).

**Evidence discipline:** everything below is SECONDARY (reporting). Recommendations only. Same wire story in many outlets = one source. Primary-doc mention counts come from `person_resolution.py` (the verification target); reporting only tells us *who to look for* and *what relationship to test*.

## KEY DISCOVERIES (top 10)

The single most valuable output: **reporting re-identifies several people the coverage-gap scan mislabeled as generic "staff" or "financial."**

1. **Natalia Molotkova is NOT Epstein "staff" — she is the American Express / Centurion dedicated relationship manager assigned to Epstein's account.** CBS (#5612, #5732) shows her arranging "decoy flights" at Lesley Groff's request to manufacture visa itineraries for women/girls, pushing back in writing ("It is against AMEX policy, to be honest… but here is the option, we can hold it till tonight"). Human node connecting Epstein's travel-booking to the ~29K-page Amex org gap. **8,277 primary pages, 0 findings.** Highest-value single re-identification.

2. **Paul Barrett is Epstein's in-house TRADER, not generic "financial ops."** Fortune "Butterfly Trust" (#2060) quotes DB KYC calling him "a talented full-time trader" who was **"JE's primary contact when he worked at JPM,"** now running Epstein's positions via an RIA called **Alpha Group**. JPM→DB continuity on the trading side (parallel to Paul Morris on banking). **4,853 primary mentions, 0 findings; Alpha Group = 0 entities/0 findings.**

3. **Ann Rodriguez is the Little St. James island PROPERTY MANAGER (since 2003), not "NY office staff."** RadarOnline #2113 + Daily Mail #2123/#2112: ran LSJ day-to-day from 2003, **retained by buyer Stephen Deckoff after the May 2023 $60M sale**, arrested 2026 for allegedly pulling a BB-gun on documentary jet-skiers. **14,760 primary pages, 0 findings** — #2 most-mentioned uncovered human, an island-operations witness.

4. **The Deutsche Bank private-banker desk is fully named in ONE article** — Fortune #2060: **Stewart Oldfield** (US wealth director, handled Epstein 2017–19), **Bradley Gillin** (DB VP, did KYC + coordinated $35K/$100K cash pickups for Indyke/Kahn), **Harry Beller** + **Erika Kellerhals** as "acting trustees" who amended the Butterfly Trust roster (deleted Maxwell, added Shuliak, 9 Dec 2014). The DS10 servicing pipeline the coverage-gap memo wanted reconstructed.

5. **Timothy "Bill" Routch — CBP agricultural inspector at St Thomas (Cyril E. King airport), FBI preliminary investigation (Oct 2019) over a 7-year "ongoing friendship" with Epstein.** Guardian #405; investigators subpoenaed 3 more CBP officers, identified 2 others. **MISSING EVERYWHERE** (0 findings, 0 entities, 11 primary mentions). Border-control corruption mechanism — how minors cleared customs onto the island.

6. **French recruitment + Rothschild-banking cluster — a national sub-network with heavy primary presence and zero findings:** **Daniel Siad** (model recruiter, Élite/Karin lineage, **888 primary mentions**, Paris criminal complaint, allegedly 3 identities); **Fabrice Aidan** (French diplomat, 200+ Epstein exchanges from 2010, Engie-fired, **134 mentions**); **Olivier Colom** (ex-Sarkozy Élysée advisor, **got Aidan hired at Edmond de Rothschild 2014**, **1,314 mentions**); **Cynthia Tobiano** (Ariane de Rothschild's deputy, emailed Epstein the Aidan alert, **302 mentions**). All 0 findings.

7. **Southern Country International — Epstein's dormant USVI bank moved ~$45M around his 2019 death** ($20M Apr–Jul pre-arrest; $25M post-death; a "mysterious $15M" from DB NY the day after his death triggered a 2020 wire-fraud probe closed unexplained). Miami Herald via #2063. Only 5–6 findings / 2 entities. Kellerhals wrote the 2012 memo calling it the "first existing IBE in the USVI."

8. **A new-banking-relationships layer opened as Deutsche exited (2019):** **Fidelity** (Southern Trust account mid-April 2019, $5M, SAR 19 Jul 2019 — ICIJ #12), **Charles Schwab** (accounts April 2019, ~$20M, SAR post-arrest), **FirstBank** (relationship "since at least the late 1990s… through Present Day," new Boies Schiller class action #2059). Fidelity/Schwab = 0 findings/0 entities.

9. **Anil Ambani (Reliance) — Epstein backroom-broker episode.** Drop Site #28: Ambani texted that "Leadership" (Modi's govt) wanted help reaching "jared and Bannon asap" before Modi's 2017 US/Israel visits; Epstein brokered intros to Barak, Barrack, Pritzker. **48 primary mentions, 0 findings.** (Overlaps tech-right/softbank "backroom broker" theme — cross-profile check advised.)

10. **Faith Kates / Next Management — modeling-agency recruitment infrastructure.** Guardian #316/#314: Kates (Next founder) "connected a number of her models with Epstein," took secret business advice + discussed multimillion-dollar loans; **5,000+ file mentions.** 1 finding; Next Management = 0 entities/0 findings. Third leg alongside Brunel (MC2) and Siad (Élite/Karin).

## GAP TABLE
Priority **1** = missing everywhere but high primary presence/unique role; **2** = thin vs salience; **3** = reporting-only/context. `prim` = primary-doc mentions; `find` = targeted findings.

| Name | Role per reporting | Key items | prim | ent/find | Pri | Why |
|---|---|---|---|---|---|---|
| Natalia Molotkova | Amex Centurion relationship mgr (NOT staff) | 5612, 5732 | 8,277 | 0/0 | 1 | Human node of Amex ~29K-page gap; decoy/visa flights |
| Paul Barrett | Epstein in-house trader ex-JPM; Alpha Group RIA | 2060 | 4,853 | 0/0 | 1 | JPM→DB continuity, trading side; new vehicle Alpha Group |
| Stewart Oldfield | DB US wealth director, handled Epstein 2017–19 | 2060, 2758 | 9,891* | 0/10 | 1 | Ran DB relationship to the end |
| Bradley Gillin | DB VP — KYC + $35K/$100K cash pickups | 2060 | 2,788 | 0/0 | 1 | Branch officer who executed cash-outs |
| Ann Rodriguez | LSJ property mgr since 2003 (NOT NY staff) | 2113, 2123 | 14,760 | 0/0 | 1 | #2 uncovered human; island-ops witness; kept by Deckoff |
| Timothy "Bill" Routch | CBP inspector St Thomas; FBI probe 2019 | 405 | 11 | 0/0 | 1 | Border-control corruption angle; missing everywhere |
| Mary Erdoes | JPM AWM CEO; took Epstein referrals | 7278, 7037 | 523 | 0/0 | 1 | The JPM private-bank gap has a name |
| Southern Country Intl | Dormant USVI bank; ~$45M moved 2019 | 2063 | (org) | 2/5–6 | 1 | Terminal money-laundering vehicle; thin vs role |
| Daniel Siad | French model recruiter; Paris complaint | 379, 4141 | 888 | 0/0 | 1 | Brunel-successor recruitment node |
| Olivier Colom | Ex-Sarkozy advisor; placed Aidan at Rothschild | 3989 | 1,314 | 0/0 | 1 | 1,314 primary mentions, invisible in findings |
| Fabrice Aidan | French diplomat; 200+ Epstein exchanges | 94, 3989 | 134 | 0/0 | 2 | Diplomatic-services allegation (Mediapart/Radio France) |
| Cynthia Tobiano | Ariane de Rothschild's deputy | 3989 | 302 | 0/0 | 2 | Inside the Edmond de Rothschild relationship |
| Faith Kates | Next Mgmt founder; introduced models | 316, 314 | 5K+ | 0/1 | 1 | Modeling-agency recruitment leg; Next Mgmt = 0 entities |
| Anil Ambani | Reliance; Modi-Barak-Kushner broker | 28 | 48 | 0/0 | 2 | Backroom-broker geopolitics; check tech-right first |
| Fidelity Investments | Southern Trust acct Apr 2019; $5M; SAR | 12 | (org) | 0/0 | 2 | New-banking layer as DB exited |
| Charles Schwab | Epstein-co accounts Apr 2019; ~$20M; SAR | 12 | (org) | 0/0 | 2 | Same layer; entirely uncovered |
| FirstBank | Multi-decade relationship; new class action | 2059 | (org) | 1/0 | 2 | Estate funds "maintained… Present Day"; live litigation |
| Brice Gordon | Zorro Ranch mgr; 2007 FBI re "masseuses" | 6798 | 8,257 | 0/0 | 1 | Re-ID of CSV "staff"; NM ranch witness (truth commission) |
| Leon Botstein | Bard president; 25+ townhouse visits | 2106, 260 | 1,678 | 0/0 | 2 | Academia; resigned 2026; 1,678 primary pages |
| Peter Attia | Longevity MD; resigned CBS role | 6793, 5844 | 1,159 | 0/0 | 2 | Science-network; 0 findings |
| Richard Axel | Nobel laureate (Columbia); resigned | 381, 6768 | 726 | 0/0 | 2 | Science-donations cluster (w/ Nowak/Krauss) |
| Philip Levine | Ex-Miami Beach mayor; Kellen allegation | 221, 2085 | 710 | 0/0 | 2 | DOJ criminal referral (w/ Fekkai) |
| Frédéric Fekkai | Hairstylist; Kellen allegation | 221, 2026 | 181 | 0/0 | 2 | DOJ criminal referral |
| Steve Hanson | Epstein associate/handler | 460 | low | 0/1 | 2 | Re-ID of CSV "unidentified staff" |
| Reinaldo Avila da Silva | Mandelson's husband; received wires | 3166 | 53 | 0/0 | 3 | Mandelson money-trail corroborator |
| Bella Klein/Kirby/Stepanian/Smith/Young/Sabba | NY bookkeeping + private-wealth-banker layer | 2060 | 2.9K–11K | 0–1 | 1 | Money-movement machinery; real transactional actors |

*Oldfield's 9,891 is the coverage-gap CSV figure (direct correspondence, 0.4% noise).

## KNOWN-GAP ILLUMINATION

- **Paul Morris (9,778 pages, 0 findings — top gap):** reporting is thin. FTS "Paul Morris" = 9 hits, all false-positive co-occurrences (Larry Summers stories, TikTok). **No Morris profile exists in reporting.** Reporters build the DB story around Oldfield/Gillin/Barrett, not Morris. He stays a **primary-docs-only** target (DS10 valuation/wire statements). His 10,007 primary mentions confirm centrality.
- **Larry Visoski (15,057 pages, 0 findings):** well-contextualized. 18 FTS hits; Maxwell-trial testimony ("remembers specific alleged victims," NBC #7185/#7359), and Guardian #405 notes he was interviewed by FBI about **Epstein's CBP contacts** — Visoski is a witness bridge to the Routch/CBP angle. A findings pass off his trial testimony + CBP interview is well-supported.
- **JPMorgan layer (≥140K pages, 0 targeted findings):** reporting supplies names. **Mary Erdoes** (JPM AWM CEO) personally fielded Epstein's 2019 Ruemmler referral (#7278) and recurs across USVI-v-JPM coverage. **Stephen Cutler** (JPM GC who warned about Epstein, #1031) also surfaces. Best-supported org gap to convert — *if* USVI-v-JPM exhibits are ingested first.
- **Deutsche Bank + Morris pairing:** Fortune #2060 + Digi24 #2758 are the richest single sources for the servicing desk (Oldfield, Gillin, Beller, Kellerhals, Barrett/Alpha Group, the Christian Sewing client-call, "$1M+/yr in fees" retention rationale).
- **Amex/Centurion (~29,600 pages, 0 findings):** now actionable via Molotkova + decoy-flight emails (#5612, #5732).
- **Unidentified-staff triage:** reporting resolves **two** — Steve Hanson = handler (#460), Brice Gordon = Zorro Ranch manager (#6798). Kerney, Roth, Bussue, Ruan, Alexanderson, Brennan, Joslin, Hanna, Denett return **0 FTS hits** — pure primary-doc email correspondents; triage from corpus.
- **Krauss/ASU (4,146 pages):** only in science-donations roundups; pairs now with Botstein/Attia/Axel/Church as an "academics who resigned/were investigated" wave.
- **Mitchell Mitchell Holdings / Glendower:** 0 FTS hits — reporting-invisible, primary-docs-only.

## NEW CONNECTIONS (asserting item → verify in primary docs)

1. **Molotkova** — Amex relationship mgr for **Epstein's account**, arranging decoy/visa flights at **Groff's** direction | #5612, #5732 | DS10/11 Groff↔Molotkova threads; Amex Centurion records; Groff House Oversight transcript (already ingested).
2. **Oldfield** — DB wealth director managing **Epstein 2017–19**, keeping accounts open past Dec-2018 termination | #2060 | DB "Epstein account closure" emails (10 May 2019); DB Sept-2019 prosecutor timeline.
3. **Gillin (DB VP)** — executed KYC + cash withdrawals collected by **Indyke** (POA) and **Kahn** | #2060 | DB cash-withdrawal emails; KYC listing Epstein as "President of Southern Financial LLC."
4. **Barrett** — Epstein's in-house trader (ex-JPM), running positions via **Alpha Group (RIA)** | #2060 | DB 2017 KYC; 2018 trade blotter (euro FX options, DB London); SEC IARD lookup on "Alpha Group."
5. **Beller + Kellerhals** — "acting trustees" who amended **the Butterfly Trust** (deleted Maxwell, added Shuliak/Indyke/Kahn), 9 Dec 2014 | #2060 | Trust amendment instruments; DB KYC roster; USVI trust filings.
6. **Routch (CBP)** — 7-year "ongoing friendship" clearing Epstein flights at **St Thomas** | #405 | FBI Oct-2019 opening email (in DOJ files); CBP pre-clearance logs; Visoski FBI interview.
7. **Erdoes (JPM)** — received Epstein's referral of **Kathy Ruemmler** as JPM client, Feb 2019 | #7278 | JPM email exhibit (USVI-v-JPM).
8. **Colom** — got **Aidan** hired (2014) at **Edmond de Rothschild**; both later fired | #3989 | Rothschild HR records; Aidan UN secondment file.
9. **Tobiano** (for **Ariane de Rothschild**) — emailed Epstein the Aidan exposure alert (13 Apr 2016); Epstein reassured via **Terje Rød-Larsen** | #3989 | DOJ-released Epstein↔Tobiano email + "Ariane a lu l'article" SMS.
10. **Siad** — recruited models via **Élite/Karin** for the **Epstein/Brunel pipeline**, allegedly 3 identities | #4141, #379 | Paris complaint; agency records; primary docs (888 mentions).
11. **Kates (Next)** — introduced agency models to, took loans/advice from **Epstein** (40 yrs) | #316 | DOJ cache (5,000+ Kates mentions); Next booking records; Dec-2010 Prince Andrew store meeting.
12. **Ambani** — asked Epstein to broker **Kushner/Bannon/Barrack/Pritzker** for **Modi's govt** ahead of 2017 visits | #28 | DOJ Epstein↔Ambani texts (Mar 2017); cross-check existing Barak/Barrack findings.
13. **Reinaldo Avila da Silva** — received Epstein wires ($13K + "$2K/mo → $4K") via accountant **Kahn** | #3166 | Epstein↔Reinaldo 2009–10 emails; Kahn instruction emails.
14. **Southern Country International** — received "mysterious $15M" from **Epstein's DB NY account** day after his death | #2063 | DB wire records; USVI banking-license file; closed 2020 wire-fraud memo.
15. **Fidelity + Schwab** — opened accounts for **Southern Trust Company** April 2019 as **DB phased Epstein out** | #12 | Fidelity SAR (19 Jul 2019); Schwab SAR; account-opening docs.

## STORY ANGLES (ranked — infrastructure first)

1. **"The Servicing Desk"** — reconstruct the private-banking pipeline from named humans. Fortune #2060 gives the DB org chart (Oldfield/Gillin/Barrett/Beller/Kellerhals) + JPM referral chain (Erdoes, #7278), combined with the Morris/Kirby/Stepanian/Smith/Sabba/Young banker list. Biggest uncovered layer; primary-verifiable. **Run as a /deep-investigate cluster.**
2. **"Amex Was the Travel Desk"** — Molotkova + decoy flights; ties the 29K-page Amex gap to the trafficking mechanism, corroborated by Groff's sworn testimony.
3. **"The Bank He Owned"** — Southern Country International + the 2019 money-in-motion + parallel Fidelity/Schwab/FirstBank onboarding. Follow-the-money spine; ties to Kellerhals + de Jongh.
4. **"The French Network"** — Siad/Aidan/Colom/Tobiano + Edmond de Rothschild; 800–1,300 primary mentions each, zero findings; active French criminal proceedings; strong multilingual sourcing.
5. **"Island Operations"** — Rodriguez + Gordon + Routch (+ Visoski); the people who ran the physical infrastructure. NM "truth commission" (#6798) is an active evidence generator for the ranch leg.
6. **"The Model Agencies"** — Kates/Next + Siad/Élite + Brunel/MC2 as one recruitment system.
7. **"The Academics Who Resigned" (2026 wave)** — Botstein/Attia/Axel/Church + Nowak/Krauss. Lower priority (reputational, not mechanistic).

## DEAD ENDS

- **Paul Morris via reporting:** top gap not illuminated — FTS hits are name-collisions. Primary docs only.
- **Mitchell Mitchell Holdings, Glendower, Kirby, Stepanian, Smith, Sabba, Young:** 0 FTS hits each. Real in primary docs (2.9K–5.4K pages) but reporting-invisible — go to DS10.
- **Unidentified-staff residue (Kerney, Roth, Bussue, Ruan, Alexanderson, Brennan, Joslin, Hanna, Denett):** 0 FTS hits. Triage from corpus.
- **Harvest noise:** publisher chrome, place names, news-cycle apparatus dominate raw n-grams — filtered; flagging so the method isn't re-run naively.
- **Wire-story inflation:** Fekkai/Levine DOJ-referral (#221 → many NBC affiliates) and Wasserman items are one syndicated story in 20–40 "publishers." Counted as single sources; people still valid, publisher-count is not corroboration.
- **Already well-covered (skip):** Richard Kahn (a *ratio* gap — 43K pages/11 findings, not a coverage gap), Shuliak, Groff, Brunel, Maxwell, Indyke, Kellerhals, Leon Black, Ruemmler, Staley.
