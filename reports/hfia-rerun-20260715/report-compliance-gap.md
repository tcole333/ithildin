# HFIA First Season of Forced Disclosure — Compliance-Gap Analysis (Agent C2)

Run date: 2026-07-15. Inputs: `datasets/hfia_universe.db` (rebuild of 2026-07-15, see `report-universe.md`), `never_filers.csv`, `late_filers.csv`, live `data.sec.gov` submissions feeds (User-Agent per SEC fair-access policy), eleven issuer 20-Fs read in full-text, 139 Form 3 XMLs sampled for event dates, SEC Corp Fin HFIA staff FAQ (fetched 2026-07-15, page last updated 2026-03-13).

Findings written (profile `hfia`, thread 39): **#13552, #13554, #13556, #13558, #13560 (corrected once), #13563, #13564, #13566, #13568, #13572, #13577, #13581**.

---

## 1. Regulatory frame (what "late" and "never" can and cannot mean)

From the Corp Fin staff FAQ (published 2026-03-09, updated through 2026-03-13; saved at `c2-sec-faq.txt`):

- **Form 3 deadline for incumbents**: a person serving as director/officer of a Section 12-registered-equity FPI on 2025-12-18 (enactment) owed a Form 3 **on 2026-03-18** (the effective date), unless no longer a D&O by that date. Post-enactment appointees: later of 2026-03-18 or 10 days after appointment.
- **Only relief described**: an EDGAR-access no-action position (Form ID backlog) requiring filing **no later than 2026-04-01**. Every row in our >30-day late screen is far outside it.
- **The FAQ contains zero foreign-law exemption mechanics.** The words "substantially similar" and "foreign law" do not appear. But—
- **The exemption channel is real and being claimed in practice**: Electra Battery Materials' 20-F (filed 2026-03-30) states its D&Os "were exempted from this requirement because the Company is organized in Canada and its directors and officers are subject to the insider reporting requirements of Canada's National Instrument 55-104" (finding **#13577**, direct quote). Whether this is self-executing statutory text, an SEC rule/order, or the issuer's own legal position is **not determinable from sources reviewed here** — the single most important caveat in this report.
- **Scope limit**: Section 16 attaches only to issuers with a class of **equity** registered under Section 12. 15(d)-only reporters, delisted/deregistered issuers, and debt-only programs are out of scope regardless of 20-F/6-K history.
- **No Item 405 equivalent exists on Form 20-F.** The FAQ mentions Item 405 delinquency disclosure only for domestic issuers. None of the eleven 20-Fs reviewed contained any Section 16 delinquency disclosure; several post-Act 20-Fs still recite pre-HFIA "our insiders are exempt" boilerplate (see section 5).

## 2. Population statistics (Task 1)

All derivations from `hfia_universe.db` unless noted; the universe = 1,389 issuers with a 6-K/20-F/40-F filed 2025-01-01..2026-07-15 (a likely-FPI heuristic, not a legal determination).

### Filing vs zero-filing

| Metric | Value | Derivation |
|---|---|---|
| Likely-FPI issuers | 1,389 | issuers table |
| Issuers with >=1 post-Act ownership filing | **865 (62.3%)** | distinct issuer_cik in filings |
| Issuers with zero post-Act Section 16 filings | **524 (37.7%)** | complement |
| Filing-owner rows (2026-03-18..07-15) | 11,718 | Forms 3: 7,183; 3/A: 239; 4: 4,232; 4/A: 61; 5: 3 |
| Distinct reporting owners | 7,340 | persons table |
| Form 3 rows filed ON 2026-03-18 | **4,068 (56.6% of all Form 3 rows)** | the single-day statutory cliff |
| Form 3 rows within the no-action window (03-18..04-01) | 5,694 (79.3%) | |
| Form 3/A amendment rate | 239/7,183 rows = **3.33%** (238/7,167 unique accessions = 3.32%) | first-season error-correction rate |

### Zero-filers (524), segmented

**Bank ETN complexes — reported separately, excluded from all "egregious" rankings** (8 issuers): UBS AG, Barclays Bank PLC, BMO, RBC, Bank of Nova Scotia, TD, CIBC, Deutsche Bank. Together they account for **55,225** of the financing-filing counts (overwhelmingly 424B2 note takedowns) — 87% of the whole universe's financing volume — and would drown every statistic. Their D&O posture requires separate legal analysis (the ETN issuers' Section 12 securities are largely debt; several parents' listed equity sits at a different CIK; home regimes such as UK/EU MAR PDMR reporting may support exemption claims). I additionally segregated five **megabank/agency note-program parents** whose counts are >=90% 424B2/424B5 debt takedowns: Barclays PLC (10), Lloyds (10), BBVA (10), Santander (9), Swedish Export Credit (9) — same volume-distortion character, same bank-sector legal posture question.

**Non-ETN zero-filers: 516.** By reported country (SEC address field, not normalized domicile): British Columbia 83, Ontario 64, China 39, Cayman 34, Unknown 32, UK 27, Alberta 21, Singapore 15, NY-addressed 15, Canada-federal 14, Quebec 14, Netherlands 13, Hong Kong 12, France 10, Israel 8.

**The Canada calibration (critical)**: ~196 of 516 (38%) are Canadian-addressed, and 152 of 516 show 40-F/6-K (MJDS) evidence. Given Electra's disclosed NI 55-104 exemption claim (#13577), Canadian zero-filing is weak evidence of anything. The residual signal-bearing population is non-Canadian zero-filers with national-exchange listings.

**Exchange evidence (non-ETN)**: NYSE 168, Nasdaq 158, none-recorded 99, OTC 60, mixed 24, "None" 7. 350 of 516 have a national exchange recorded — but exchange fields persist after delisting (see section 3 validation drop-outs), so live Section 12 status must be checked per issuer.

**FPI-evidence mix (non-ETN)**: 20-F+6-K 289; 40-F+6-K 152 (the MJDS/Canada block); 6-K-only 63; 20-F-only 9; other 3.

**Financing-active zero-filers**: 176 total; **168 excluding ETN banks**, spanning 795 F-1/F-3/424B filings; by country: China 26, Cayman 24, UK 16, Singapore 12, Ontario 12, BC 11. Of the 168, **72 had financing activity on/after the Act date** (370 filings) — the sharpest "raised while dark" cut.

### Late Form 3 distribution (839 rows >30 days post-Act)

- 306 issuers, 782 owners. Raw days-after-Act: min 33, **median 63**, mean 67.1, max 118 (filed 2026-07-14).
- Histogram: 31-45d: 203 | 46-60d: 179 | 61-75d: 164 | 76-90d: 120 | 91-105d: 105 | 106-118d: 68.
- Role mix: 796 director/officer rows, 32 pure 10%-owner rows (event-driven deadlines — screen confound), 11 unclear.
- Agent-prefix concentration (rows/issuers/median days): 0001213900: 225/76/58 | 0001493152: 125/35/58 | 0001104659: 72/31/64 | 0001193125: 68/31/60.5 | 0000905148: 39/4/75.

**Event-date decomposition (the screen's honesty check).** I fetched `periodOfReport` from 139 Form 3 XMLs (all 39 rows of prefix 0000905148, 45/225 of 0001213900, 55/575 others; 138 parsed):

| Class | n | Meaning |
|---|---|---|
| Event = 2026-03-18 | 55 | self-declared Act-date incumbents — late on the face of the form |
| Event pre-Act (2021..2026-03-17) | 10 | incumbents declaring historical events — also late |
| Event post-Act, filed <=10d after event | 62 | timely new-appointee filings — **screen false positives** |
| Event post-Act, filed >10d after event | 11 | late relative to their own declared event |

Strata-weighted extrapolation: **~53% of the 839 (~450 rows) are genuinely late incumbent filings; ~47% are routine appointment-driven filings** the >30-day screen cannot distinguish. Median days-after-Act among sampled genuinely-late rows: **43** (vs 75 for the appointee class — the raw median 63 blends the two).

## 3. Top-10 egregious zero-filers, validated (Task 2)

Ranked by financing intensity (f1_f3_424 count) among the 168 non-ETN financing-active zero-filers, after excluding the five note-program megabank parents; every entry validated 2026-07-15 against the live submissions JSON (all history segments, forms 3/3A/4/4A/5/5A, window 2026-03-18..2026-07-15) and its latest annual report read in full text. **None of these is a violation allegation — each finding records a filing state plus the exemption caveat.**

| # | Issuer (ticker) | Fin. filings | Latest fin. | Annual naming D&O | Post-Act Sec16 | Notable | Finding |
|---|---|---|---|---|---|---|---|
| 1 | Genius Group (GNS, NYSE, Singapore) | 12 | 2026-07-01 (post-Act) | 20-F 2026-03-09 (9 days pre-Act): Hamilton CEO/Chairman + 7 | 0 (0 ever) | takedowns continued post-Act | #13552 |
| 2 | TNL Mediagene (TNMG, Nasdaq, Cayman) | 11 | 2026-03-18 (Act day) | 20-F 2026-04-30 POST-Act: 11 D&O incl. Chairman Marcus Brauchli | 0 (0 ever) | post-Act 20-F still recites pre-HFIA exemption boilerplate | #13554 |
| 3 | Akanda (AKAN, Nasdaq, Ontario-inc) | 11 | 2026-03-20 (post-Act) | 20-F 2026-06-09 POST-Act: 6 D&O as of 2026-06-08 | 0 (only 2 pre-Act HRT 10%-owner forms) | zero D&O filings ever; Canada caveat | #13556 |
| 4 | EShallGo (EHGO, Nasdaq, Cayman/PRC) | 10 | 2026-07-01 (post-Act) | 20-F 2025-08-14 pre-Act: Mao/Miao/Lyu (continuity inference) | 0 (0 ever) | FY2026 20-F due ~2026-07-31 | #13558 |
| 5 | LATAM Airlines (LTM, NYSE, Chile) | 10 (424B7 resales) | 2026-02-11 | 20-F 2026-03-05: 8 directors, terms spanning Act date | 0 (0 ever) | largest-cap validated case; Chile CMF regime caveat; board renewal due ~Apr 2026 | #13560 |
| 6 | EPWK (EPWKF, Nasdaq then delisted) | 9 | 2026-05-06 (post-Act) | 20-F 2026-01-14: Huang CEO + 8 | 0 (0 ever) | 12(b) spanned Act date (8-A 2025-02-03, 25-NSE 2026-06-02); raised post-Act, then delisted | #13563 |
| 7 | One & one Green (YDDL, Nasdaq) | 9 | 2026-05-26 (post-Act) | 20-F 2026-04-27 POST-Act: Yan CEO/Chair + 5 | 0 (0 ever) | **its own post-Act 20-F concedes insiders "will be required to report"** | #13564 |
| 8 | Psyence Biomedical (PBM, Nasdaq, Ontario-inc) | 9 | 2025-11-20 (pre-Act only) | 20-F 2026-06-22 POST-Act: Aufrichtig CEO/Chair + 4 | 0 (0 ever) | post-Act 20-F still recites blanket exemption; Canada caveat | #13566 |
| 9 | Top Wealth (TWG, Nasdaq, Cayman/HK) | 9 | 2026-06-26 (post-Act) | 20-F 2026-05-15 POST-Act: Wong CEO/Chair + 5 | 0 (0 ever) | **post-Act 20-F affirmatively asserts insiders "will not be required to report" — no stated basis** | #13568 |
| 10 | Global Mofy AI (GMM, Nasdaq, Cayman/PRC) | 8 | 2026-05-26 (post-Act) | 20-F 2026-01-09: Yang CEO/Chairman + 6 | 0 (0 ever) | post-Act 424B2/424B5 takedowns during gap | #13572 |

**Validation drop-outs (screen artifacts, no findings written):**
- **Damon Inc.** (50 filings, rank-1 raw): Form 25-NSE 2025-07-18, now files 10-K (domestic-form), 18 historical Section 16 filings exist — not an HFIA story.
- **LeddarTech** (19): Form 25-NSE 2025-08-22 — Nasdaq 12(b) registration terminated pre-enactment.
- **Optimi Health** (10): 8-A12B effective only 2026-05-19 — post-Act fresh registrant; different clock; no annual on file.
- **Electra Battery Materials** (10): reclassified — disclosed exemption claim (#13577), the report's key calibration datapoint.
- **Phaos Technology** (9): 20-F primary-doc split prevented officer-table capture in-session; replaced by Global Mofy (next rank).

**Cross-cutting observations**: 6 of the 10 validated issuers' latest 20-Fs were themselves filed via agent prefix 0001213900 (TNL, Akanda, EPWK, One&one, Psyence, Top Wealth) — the same account that dominates the late-Form-3 wave files these issuers' annuals while no ownership forms exist for their insiders. Five post-Act 20-Fs still carry pre-HFIA "insiders are exempt" boilerplate (TNL, Akanda, Psyence, Top Wealth affirmatively; Genius pre-Act by 9 days); only One & one's acknowledges the new duty; only Electra's claims a specific exemption.

## 4. Weiss-gate fold-in (Task 3)

`never_filers.csv` carries 9 `record_type=weiss_gate_audit` rows (live audit, 92 requests, XML issuer-CIK validated). Statuses: 5x `post_act_weiss_filing` (SciSparc 19/2, Nexera 18/2, Maris 11/1, ParaZero 10/1, Viewbix 6/1 = issuer post-Act Sec16 count / Weiss count), 3x `post_act_section16_but_no_weiss_filing` (N2OFF 2/0, **Clearmind 5/0**, Rail Vision 12/0), 1x `no_post_act_section16_filing` (**Gix Internet 0/0**).

Cross-reference to existing findings — cited, not re-derived:
- **#13413** (Weiss signed Clearmind's F-3 as chairman 2026-02-17, filed Form 3s at four sibling issuers on 2026-03-18, never at Clearmind) — the issuer-level audit independently corroborates: Clearmind's 5 post-Act filings are all HRT Financial (10% owner), none by Weiss or any D&O.
- **#13414** (Clearmind zero D&O filers ever) — directly corroborated by the audit row's accession-level enumeration.
- **#13416** (Charging Robotics: the pre-HFIA domestic-registrant analog of the same gap) — unaffected by this audit (12(g) domestic issuer, outside the FPI screen), cited as the pattern's domestic precedent.

Corroboration value: the chairman-gap pattern now rests on two independent derivations — the person-level EDGAR owner history and the issuer-level submissions audit — which query different EDGAR indexes. (Redundancy note: both ultimately read EDGAR; this is corroboration of *our pipeline*, primary-source-independence remains single-system.) Sibling-agent findings #13573/#13574/#13578/#13579/#13582 (same wave) extend the person-level side; no duplication with the issuer-level work here.

## 5. Late-filer texture: prefix 0001213900 (Task 4)

**Answer: industry-infrastructure volume story, not a coherent client cohort — with one genuine mass-late cohort found elsewhere.** Finding **#13581**.

- Prefix 0001213900 is the biggest pipe in the entire post-Act wave: **1,526 of 7,183 Form 3 rows (21.2%)**. Its 225 late rows sprawl across **76 issuers and 218 owners** (Cayman 17, China 12, Israel 9, HK 7...); largest same-day batch just 13 rows across 4 issuers; only 7 owners have >=2 late rows (Adler, Revach, Weiss among them — the Israeli cluster again). 23 of the 76 issuers had their entire Form 3 wave late.
- Its late share is moderately elevated: **14.7%** of its Form 3 rows vs **10.9%** for all other prefixes pooled (11.7% overall); and its late rows are more *real*: sampled truly-late share **73%** (33/45) vs **46%** (25/54) elsewhere. Median 58 days vs 65 for others.
- The concentrated outlier is elsewhere: prefix **0000905148** — 39 late rows across only 4 issuers, late share 66.1% (39/59). Decomposed by event dates: **Telkom Indonesia (TLK, NYSE, state-controlled) is the single cleanest mass-late cohort in the universe: 17 of 17 insider Form 3s, every one self-declaring event date 2026-03-18, 16 filed 2026-04-21 + 1 on 2026-04-23 (34-36 days past the statutory deadline)**. The other 21 rows (VEON, Kyivstar — incl. director Michael Pompeo — and Aspen's new CFO) declare a 2026-05-29 (or later) event date and filed within days of it: event-driven filings, *not* provable Act-date lateness. What the shared 2026-05-29 VEON/Kyivstar trigger event was is an open question (proposed lead below).

## 6. Story stat sheet (Task 5)

Each stat with derivation and its load-bearing caveat:

1. **"Six in ten foreign issuers' insider populations showed up; nearly four in ten never filed at all."** 865/1,389 = 62.3% filed; 524/1,389 = 37.7% zero. *Caveat: denominator is a 6-K/20-F/40-F heuristic including out-of-scope issuers (delisted, 15(d)-only, debt-only); the 37.7% is an upper bound on true non-participation.*
2. **"More than half of all initial insider reports hit EDGAR on a single day."** 4,068 of 7,183 Form 3 rows (56.6%) filed 2026-03-18; 79.3% by the 2026-04-01 no-action cutoff. *Clean stat, direct from filing dates.*
3. **"Roughly 450 insiders blew the deadline by a month or more — the median genuine straggler was ~6 weeks late (43 days past deadline)."** 839 rows >30 days late; event-date sampling shows ~53% (~450) self-declare Act-date/pre-Act incumbency; sampled truly-late median 43 days. *Caveat: sample-based split (n=138, stratified); the raw 839 includes ~47% timely new-appointee filings; "late" is not adjudicated delinquency.*
4. **"72 foreign issuers raised or registered money from U.S. investors after the deadline passed while not one of their insiders had filed."** 72 of 168 non-ETN financing-active zero-filers have latest F-1/F-3/424B activity on/after 2026-03-18 (370 filings). *Caveat: filing counts, not dollars; includes resale registrations (e.g., LATAM's 424B7s register shareholder resales, not company raises); exemptions may apply.*
5. **"Canada is the elephant in the zero-filer room."** ~196 of 516 non-ETN zero-filers are Canadian-addressed; 152 show 40-F/MJDS evidence; and one Canadian issuer (Electra) states in its 20-F that its insiders "were exempted" via NI 55-104. *This deflates naive readings of stat #1 — and is itself a story: the exemption's mechanics appear nowhere in the SEC's own FAQ.*
6. **"An issuer whose own annual report says its insiders 'will be required to report' has zero insider reports on file"** (One & one Green, #13564); its mirror: **"an issuer told investors two months after the deadline that its insiders 'will not be required to report' — with no stated basis"** (Top Wealth, #13568). *Both direct quotes from post-Act 20-Fs.*
7. **"Indonesia's state telecom missed the deadline for its entire board and management — 17 for 17 — then filed everyone at once five weeks later."** Telkom Indonesia, event dates 2026-03-18, filed 2026-04-21/23 (#13581). *Every accession independently fetchable.*
8. **"The first-season error rate: 1 in 30 initial reports had to be amended."** 239 Form 3/A rows vs 7,183 Form 3 rows = 3.33%. *Amendments may correct trivia; content not reviewed.*
9. **"One filing agent moved a fifth of the entire first season."** Prefix 0001213900: 1,526/7,183 Form 3 rows, 227 issuers (per sibling finding #13582), 225 of 839 late rows. *Prefix = submitting EDGAR account, not identified counsel; do not name a firm without verification.*

## 7. Proposed leads (NOT written to DB)

1. **Resolve the exemption's legal machinery**: pull the HFIA statutory text (NDAA FY2026 sec. 8103) and any SEC exemptive rule/order; determine whether Electra's NI 55-104 claim is self-executing statute, Commission action, or unilateral legal position. Everything in sections 2-3 recalibrates on the answer.
2. **VEON/Kyivstar 2026-05-29 trigger event**: 21 D&O Form 3s across two issuers declare the same event date (incl. Michael Pompeo, Betsy Cohen). Candidate explanations: FPI-status loss (becoming domestic-filer D&Os), a registration event, or counsel-chosen convention. One 6-K/8-K sweep around 2026-05-29 should resolve it.
3. **Telkom Indonesia mass-late cohort**: establish whether Indonesian state-issuer counsel treated the obligation as contested (any 6-K, or OJK-side disclosure, around 2026-03-18..04-21), and identify the 0000905148 agent account.
4. **FY2026 20-F season as the next checkpoint**: EShallGo (due ~2026-07-31) and other March-FY zero-filers must refresh their D&O lists post-Act — recheck the bounded negatives after 2026-08-01.
5. **Top Wealth's non-obligation assertion** (#13568): a post-Act affirmative representation with no stated basis is either a drafting failure or a legal theory; a comment-letter watch (UPLOAD/CORRESP) on CIK 1978057 would show whether Corp Fin challenges it.
6. **The 6-K-only zero-filers (63 issuers)**: most likely out-of-scope (no Section 12 equity) — a batch 8-A/25/15 status sweep would clean the denominator for any published rate.
7. **Bank ETN complexes as a standalone piece**: 8 complexes, 55K financing filings, zero Section 16 — the real question is whether HFIA even reaches debt-only-registered FPI programs; needs securities-law analysis, not more screening.

## 8. Honest limits

- **The likely-FPI screen over-includes**: three of my initial top-13 candidates fell out on live validation (delisted/deregistered/domestic-form). Published rates must not use the raw 1,389/524 without the Section 12-status cleanup (lead 6).
- **"Zero filings" is an EDGAR-observable state, not a legal conclusion**; the Electra discovery proves at least one exemption theory is in live use, and the staff FAQ's silence means I cannot map which zero-filers hold valid exemptions. Every issuer finding carries this caveat in its text.
- **Event-date decomposition is sampled** (139 of 839; complete only for prefix 0000905148). The ~450 truly-late estimate carries roughly +/-60-row sampling uncertainty on the unsampled strata.
- **Financing intensity is filing counts, not dollars**; no market-cap or proceeds data was joined (universe report's `small_cap_proxy` caveat stands). "Raised while dark" claims should quote filing counts and dates, not amounts, until offering sizes are parsed.
- **Officer continuity for pre-Act 20-Fs** (EShallGo, Global Mofy, LATAM, EPWK, Genius at 9 days) is inference from absence of contrary disclosure — stated as such in each finding; LATAM's scheduled April 2026 board renewal is explicitly flagged.
- **Country fields are SEC address metadata**, not legal domicile (EPWK shows "VA" while being a Cayman/PRC structure).
- **20-F full texts were read via stripped HTML of the primary document only**; exhibits and multi-document filings (Phaos) were not parsed.
- The two agent-account identities (0001213900, 0000905148) were deliberately left unresolved: EDGAR's browse endpoint returns no entity data for agent CIKs, and naming a service provider from an accession prefix alone would be exactly the inference the universe report warns against.
