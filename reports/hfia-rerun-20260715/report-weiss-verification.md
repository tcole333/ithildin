# Weiss Microcap Board Cluster — Publication-Grade Verification and Refresh
**Profile:** `hfia` | **Pass date:** 2026-07-15 | **Scope:** findings #8882-8895 re-verification, #8885 known correction, E.D.B. independence probe, issuer refresh 2026-03-30 → 2026-07-15, story-grade claim inventory.
**Method:** every load-bearing claim re-pulled from SEC EDGAR primary documents (accession-level); Israeli registry (data.gov.il) and TASE/MAYA primary documents for the Israeli side; 4 parallel read-only EDGAR subagent sweeps (SciSparc+AutoMax; Clearmind+ParaZero; Viewbix+CHEV+Gix; Nexera+Maris-Tech+Nexentis) whose load-bearing quotes were independently spot-verified before any DB write. All DB writes carry `--profile hfia`; no leads created; no skills invoked; active profile untouched.

---

## 1. Per-finding verification table (#8882-8895)

| # | Claim (original) | Verdict | Basis / what changed |
|---|---|---|---|
| 8882 | 9 simultaneous US boards, chairman of 5 | **NEEDS-CORRECTION → CORRECTED** | The original detail listed only 8 unique CIKs while claiming 9 — Save Foods and N2OFF/Nexentis are the **same CIK (1789192)** double-counted. Verified recount (Weiss owner CIK 1826620 filings + ParaZero 20-F 0001213900-26-034376 bio): **8 unique US-listed/registered issuers as of 2026-03-30, chairman of 6** (SciSparc, Clearmind, ParaZero, Maris-Tech, CHEV, Nexentis). CHEV is OTC/12(g), not Nasdaq. Post-window: seats fell to 6 (CHEV resigned 2026-03-30, Clearmind 2026-04-26). Corrected summary+detail; enumeration recorded as finding #13435 (incl. new fact: Weiss sits on the board of **Tomer Ltd., an Israeli government-owned defense company**, since 2024). |
| 8883 | Four batch Form 3s 2026-03-18 via 0001213900 + Dayan late Form 3 | **VERIFIED-AS-WRITTEN** | All four accessions verified from owner-CIK submissions JSON (029463 PRZO / 030644 SPRC / 030812 MTEK / 031244 JFBR, all 2026-03-18). Dayan Form 3 at SciSparc verified: owner DAYAN ALON, period 2026-03-18, **filed 2026-03-23**, agent 0001213900. |
| 8884 | ~$488K/yr min cross-portfolio comp (4 issuers itemized) | **NEEDS-CORRECTION (minor) → CORRECTED** | ParaZero verified to the dollar ($113,938 + $45,000 + $65,244 = $224,183). CHEV $9,000 and Clearmind $243,511 consistent with agent pulls. **Error:** Viewbix $11,584 was called a "share grant" — the 10-K comp table shows it under *Fees earned or paid in cash* (stock/option columns blank). Also now stale as a run-rate: ParaZero **doubled Weiss's fee to $20,000+VAT/month retroactive to 2026-01-01, plus 325,000 RSUs + $50K bonus, explicitly "in excess of the limitations set forth in the Company's compensation policy"** (approved 6/1 at a quorum-failure-adjourned AGM; finding #13430). |
| 8885 | Dual chairman SciSparc/AutoMax; "no independent fairness opinion" | **NEEDS-CONTEXT → CORRECTED (task 2)** | Core true and verbatim-verified. Context added from F-4/A 0001213900-25-022367: board instead obtained an **E.D.B. Consulting and Investments Ltd. valuation report**; "no legal requirement under Israeli law to obtain a fairness opinion"; "cost implications, as fairness opinions can be expensive"; risk factor concedes investors "will not have assurance from an independent source". Balance facts added: Weiss **recused** from merger/bridge-loan votes (#13368) but was slated for a **$150,000 cash bonus contingent on closing** (Adler $315K, Shrem $50K — #13367). |
| 8886 | $10M convertible facility from Xylo's sole shareholder; $0.123 conversion; 23,037,624 shares | **VERIFIED-AS-WRITTEN + enriched** | F-3 verified: up to $10M principal for $9M (90%); initial $2.0M note for $1.8M; **$0.123 is the floor = 20% of the fixed price** — conversion is variable (88% of lowest 20-day VWAP); 18,368,679 + 3,651,554 + 1,017,391 = 23,037,624 exact. Counterparty identified: **L.I.A. Pure Capital Ltd. (Kfir Silberman)** (#13400). Facility status as of 2026-07-15: no draws beyond the initial note, no conversions (share count flat 573,243), resale F-3 333-293533 **never declared effective**. |
| 8887 | Three F-3 "shelfs" within 48h, "may indicate coordinated activity" | **UPGRADED → CORRECTED** | Dates verified (Feb 17/17/19 — three days, not strictly 48h). All three are **resale registrations, not company shelfs**, and the selling shareholder in all three is the **same investor: L.I.A. Pure Capital (Kfir Silberman)**, plus Capitalink Ltd. (Lavi Krasney) at Clearmind. The synthesis is now a documented common-financier fact (#13400, #13405). |
| 8888 | CHEV "uplisted to Nasdaq Dec 2025", Weiss chairman, Dinar CFO | **NEEDS-CORRECTION → CORRECTED** | **The uplisting never completed**: 8-A12B filed 2025-12-22, but FY2025 10-K lists 12(b) securities "None"; stock on OTCID Basic; $2M PIPE + $3M facility gated on a future "Uplist Date"; cash $25K at 3/31/26. Weiss **resigned the CHEV board 2026-03-30** with Kineret Tzedef, "for personal reasons, effective immediately" (#13415, #13417). |
| 8889 | Weiss "executive officer" of Gix Internet; three-way Viewbix/Gix/Xylo link | **NEEDS-CORRECTION (quote precision) → CORRECTED** | The 10-K actually says **"chief executive officer of Gix Internet Ltd."** — a stronger fact than quoted. Chain precise per the same 10-K: Pure Capital → **Xylo (wholly-owned) → 31.53% of Gix Internet → Viewbix/QXL**. Superseded in part: Weiss resigned as Gix CEO effective **2026-05-03** (#13418). |
| 8890 | N2OFF Form 4: 116,286 restricted shares at $0, 2026-02-09 | **VERIFIED-AS-WRITTEN** | XML verified: code A, $0, 129,144 after. Context added (#13428): same-day 4-officer grant round (CEO Palach's end position identical at 129,144); 600,000 IR-consultant shares issued 11 days later; NXTS ticker live 17 days later. |
| 8891 | Six repeat cohort members | **VERIFIED (substantially)** | Verified from primary docs: Dinar (PRZO Class II director + CHEV CFO), Revach (PRZO Class III + SPRC Form 3 + Nexera Form 3), Adler (SPRC CEO/CFO Form 3 + Clearmind F-3 signature "Director" + Nexera Form 3), Tzedef (VBIX audit chair per 10-K + CHEV board — resigned with Weiss 3/30), Dayan (VBIX audit/comp + SPRC Form 3 late), Baranes (F-4/A: both on CHEV board; "provided market overview services to certain other companies of which Mr. Amitay Weiss serves as a director"). The Tzedef "planned post-uplist audit committee" element is moot (no uplisting). |
| 8892 | Rail Vision: <3-month tenure, "not due to disagreement" | **VERIFIED-AS-WRITTEN** | 20-F verbatim: appointed announced 2024-01-09 (with Hila Kiron-Revach — who later replaced Weiss as **Clearmind** chair), resigned 2024-03-12, "Mr. Weiss's resignation was not due to any disagreement with us or management." New nuance: the board changes came "in connection to the Credit Facility". |
| 8893 | Clearmind-SciSparc March 2022 tech agreement; Adler three-way nexus | **VERIFIED (except one quote unchecked)** | Adler's dual role triply confirmed (F-4/A commissioning statement; Clearmind F-3 signature page "Oz Adler — Director"; SciSparc Form 3 "CEO & CFO"). The specific Clearmind 20-F cross-licensing quote was not re-pulled this pass — left `unverified` in DB; low risk, but pull Clearmind 20-F (Jan 2026) before print. |
| 8894 | Save Foods → N2OFF → Nexentis same CIK; Weiss chairman-since-2020→now director | **VERIFIED + nuance → CORRECTED** | Name chain verified with accessions: rename to Nexentis board-approved 2026-01-26, Nasdaq-effective 2026-02-26 (NITO→NXTS), CUSIP unchanged; ~98% of Save Foods divested to Voice Assist 2026-03-15. **Role discrepancy documented:** his own Forms 3/4 check "Director" only; ParaZero 20-F bio says "Chairman of the Board of Nexentis... since May 2021". Corrected to carry both. |
| 8895 | President + Chairman of SciSparc (President since Oct 2025) | **VERIFIED-AS-WRITTEN (sourcing note)** | Verbatim in ParaZero 20-F bio: "President and Chairman of SciSparc Ltd... having served as Chairman since January 2022 and President since October 2025, and previously as Chief Executive Officer and director from August 2020 to January 2022." (The original detail attributed this to "SciSparc 20-F FY2025"; the fact is verified but the cleanest citation is the ParaZero 20-F bio + SciSparc's own FY2025 20-F "our President and a director".) Note: he became President **10 days after the merger termination and the same month AutoMax collapsed**. |

**DB verification-status caveat:** `findings_tracker.py verify` fails on all 14 rows because the March pass stored `source_datasets` as comma-strings, not JSON (pre-migration format). The verification pass is recorded in each finding's immutable correction audit trail instead (`--by agent:weiss-verify-20260715`). Cleanup task proposed (task chip task_c87ab263).

---

## 2. Corrections made (audited via `findings_tracker.py correct`)

| Finding | Field(s) | Substance |
|---|---|---|
| **8885** | detail, summary | E.D.B. valuation-in-lieu-of-fairness-opinion context, no-Israeli-law-requirement + cost rationale (exact quotes), recusal + $150K closing bonus balance. *(Task 2 — completed as specified, quotes verified against the live F-4/A.)* |
| **8882** | detail, summary | 9 → **8 unique issuers** (Save Foods/N2OFF double-count); chairman 5 → **6**; CHEV OTC not Nasdaq; post-window resignations. |
| **8884** | detail | Viewbix $11,584 = cash fees not share grant; ParaZero figures verified exact; June 2026 ParaZero fee doubling supersedes run-rate. |
| **8887** | detail, summary | "Shelf registrations" → **resale registrations for the same investor** (Pure Capital/Silberman; + Capitalink/Krasney); synthesis substantiated. |
| **8888** | detail, summary | "Uplisted to Nasdaq" → **uplisting never completed**; Weiss resigned 2026-03-30. |
| **8889** | detail | Quote precision ("**chief** executive officer" of Gix); Pure Capital→Xylo(100%)→Gix(31.53%) chain; superseded by 2026-05-03 resignation. |
| **8894** | detail | Nexentis rename verified w/ accessions; Save Foods divestiture; chairman-vs-director source discrepancy documented. |
| **13371** | detail | Weiss's Form 3/As were part of **nine-filer (SciSparc) and eight-filer (Nexera) same-day amendment batches** — firm-wide batch error, not personal. |
| **13364** | thread_id | Fixed config-local thread id (2) → global hfia thread 40 (drift warning at creation). |

---

## 3. New findings added (all `--profile hfia`; threads 39/40 = global ids for config threads 1/2)

**E.D.B. / merger package (from F-4/A 0001213900-25-022367 unless noted):**
- **#13364** — E.D.B. fee NIS 46,800 (~$12,935) flat/non-contingent; engaged 2024-03-04; no prior SciSparc services; prior Matomy-related AutoMax work claimed; Nov 2024 PPA re-engagement NIS 14,040.
- **#13365** — Valuation cover: "Drafted on January 4, 2024", "commissioned by Mr. Oz Adler, CEO of SCISPARC Ltd" — **two months before the disclosed March 4 engagement date**.
- **#13366** — Methodology spread: multiplier ~$21.77M vs DCF $44.8M; report anchored on $44.8M; management projections accepted "without independent verification or investigation".
- **#13367** — Closing bonuses contingent on the merger: Adler $315K, **Weiss $150K**, Shrem $50K.
- **#13368** — COUNTERPOINT: Weiss recused from merger approval, NIS 4M investment, and bridge-loan votes.
- **#13369** — E.D.B. identity block: Israeli co. no. 514752195, 65-66 Bareket St. Mevasseret Zion, **ebrik10@gmail.com**, first-person-singular text, **no named author or credentials anywhere in the SEC-filed translation**.
- **#13394** — F-4/A itself discloses the **Aug 5, 2021 indictment** of AutoMax CEO Daniel Levy, CBO Yinon Amit, and Haim Levy (forgery, fraud, smuggling, money laundering); evidence trials began March 2023; auditor emphasis-of-matter — the same management whose projections E.D.B. relied on.
- **#13397** — TASE primary (Matomy transaction report P1342943-00, 2020-12-30): the Matomy/Global AutoMax merger valuation was authored by **G.S.E Economic Consulting Ltd** (~NIS 97M as of 2020-06-30) — E.D.B.'s claimed prior Matomy engagement was not the headline merger valuation. (New source tokens added to `VALID_SOURCES` in tools/findings_tracker.py: `tase_maya`, `israel_registry`, `calcalist`, `globes_il`.)
- **#13398** — Israeli Corporations Authority record: E.D.B. incorporated 2012-03-15, private, active, Bareket 65 Mevasseret Zion; free layer names no officers.
- **#13399** — Calcalist 2025-10-16 (verbatim Hebrew quotes): Israel Police + ISA investigating suspected fraud/theft/forgery; **brothers Haim and Tomer Levy** allegedly concealed supplier commissions and inflated inventory "by tens of millions of shekels... via forged manufacturer emails"; merger cancellation tied to this. (Secondary, attributed; Tomer Levy = the AutoMax director empowered to execute the merger docs per the F-4/A.)

**Financier layer:**
- **#13400** — **One investor behind all three Feb 2026 F-3s**: L.I.A. Pure Capital (Kfir Silberman) at SciSparc (22.0M sh), Clearmind (4.08M), Jeffs' (1.37M); sole shareholder of Xylo; address = 20 Raoul Wallenberg Tel Aviv = SciSparc's own HQ street address.
- **#13405** — Same discounted convertible structure rolled across the portfolio in 8 months: Jeffs' June 2025 (**up to $100M**, non-recourse, 88%-of-VWAP), Clearmind Sept 2025 ($10M), SciSparc Feb 2026 ($10M, floor = 20% of fixed).
- **#13410** — Pure Capital has been a **paid SciSparc consultant since 2020-12-01**; Side Letter permits consulting payables to be **offset against note purchase prices**.
- **#13411** — Pure Capital 13G/A: **0 SciSparc common shares as of 2026-03-31** — one day before the Additional-Notes window opened.
- **#13429** — Nexentis: Pure Capital facility upsized EUR 6M → **EUR 10M** (2026-05-27) + 1,850,000-share $1.00 warrant with price-maintenance ratchet — Pure Capital financing now documented at a sixth cluster company.

**Merger collapse (primary):**
- **#13406** — Termination Framework Agreement 2025-10-06 (merger null and void; $6.25M loans; repayment schedule).
- **#13407** — SciSparc's 20-F attributes termination to "an investigation by the Israeli Securities Authority and the Israeli Police **and the arrest of senior officials of AutoMax**".
- **#13408** — AutoMax insolvency (court freeze + trustee 2025-10-21); SciSparc impaired **$5,973,000** (~96% of loans); debt petition filed.
- **#13409** — Weiss remained AutoMax chairman **until 2025-10-16** — ten days after termination.

**Section 16 / filing-wave:**
- **#13370** — Weiss sold his entire indirect Viewbix stake (30,296 sh @ $2.00, 2026-03-31, via Amitay Weiss Management Ltd., 0 after) — 13 days after HFIA effectiveness.
- **#13371** — Two of his four batch Form 3s required amendment (corrected: part of 9-filer/8-filer batch amendments).
- **#13412** — Weiss resigned Clearmind chairmanship "effective immediately" 2026-04-26.
- **#13413** — **Apparent HFIA filing gap at Clearmind** (synthesis, medium): chairman through the deadline; personally signed the Feb 17 F-3 that describes the HFIA obligation; filed at four sibling issuers on 3/18; never filed at Clearmind.
- **#13414** — Clearmind: **zero Section 16 filings by any director or officer, ever**; only 10%-owner HRT Financial LP (June 2026).
- **#13415** — Weiss + Tzedef resigned CHEV board 2026-03-30 "for personal reasons, effective immediately".
- **#13416** — **Apparent pre-HFIA Section 16(a) gap at CHEV** (inference, medium): 12(g)-registered since 2021; zero insider filings ever; chairman 2022-2026; no Item 405 disclosure.
- **#13417** — CHEV uplisting never completed (12(b) "None"; OTCID; PIPE gated on "Uplist Date"; $25K cash).
- **#13418** — Weiss resigned Gix Internet CEO effective 2026-05-03 — four-step spring-2026 disengagement (CHEV 3/30 → VBIX stock 3/31 → Clearmind 4/26 → Gix 5/3).

**Refresh (issuer events since 2026-03-30):**
- **#13419** — Viewbix → **Quantum X Labs Inc. (QXL)** (4/30) after acquiring Gix-orbit target (Yoresh on both sides); stock $1.99 → $6.85 after "50+ qubit" PR; Weiss had sold at $2.00 on 3/31.
- **#13420** — Jeffs' Brands → **Nexera Technologies** (3/26; NEXR/NEXRW 3/31); homeland-security/AI rebrand atop 1:14 split (cumulative 1:182).
- **#13421** — Nexera note ladder: five notes; June resale F-3 registers 16,836,315 shares (~**3.4x outstanding**) at $0.1468 floor; $88M capacity remains.
- **#13422** — Maris-Tech cured its Nasdaq equity deficiency by **accelerating 70%-of-VWAP note conversions** (5/29).
- **#13423** — Maris-Tech: $3.0M ATM + **13 defense/drone PRs in 15 weeks** starting the day the ATM prospectus filed; July sequence: reserve tripled → S-8 → 340,353 $0-cost officer shares.
- **#13428** — Nexentis rename + Save Foods divestiture + Weiss grant timing vs IR-share issuance and ticker launch.
- **#13430** — ParaZero doubled Weiss's fee retroactively + 325K RSUs + $50K bonus, "in excess of" comp policy; Revach's only-insider-sale 3 days before re-election.
- **#13434** — Clearmind drip: $7.55M principal for $6.795M cash Apr-Jun 2026; conversions $0.60 → $0.30; floors reset 3x; **cumulative 1-for-400 reverse split in 5 months**.
- **#13435** — Definitive Weiss seat enumeration incl. **Tomer Ltd. (Israeli government-owned defense company) directorship since 2024**.
- **#13436** — SciSparc is a >10% Section 16 owner of N2OFF/Nexentis (MitoCareX sale consideration: $700K cash + $2,027,000 stock).
- **#13437** — SciSparc distress trio: going concern; Nasdaq deficiency → conditional compliance (May 7); 1:9 reverse split.

**Entities registered/updated:** E.D.B. Consulting and Investments Ltd. (#5324: +address, +`engaged_valuator` relation from SciSparc #2531); L.I.A. Pure Capital Ltd. (#5344: +Silberman role, +address, +`sole_shareholder`→Xylo #2527, +`convertible_note_lender`→SciSparc #2531); Capitalink Ltd. (#5349 created, +Krasney role).

---

## 4. E.D.B. independence probe (Task 3)

**Who/what E.D.B. is (all primary):**
- Israeli private company א.ד.ב יעוץ והשקעות בע"מ, co. no. **514752195**, incorporated **2012-03-15**, active; registered at **Bareket 65, Mevasseret Zion** — a residential suburb of Jerusalem; matches the address block on every page of the SEC-filed valuation (65-66 Bareket St.). Free registry layer exposes no officers; the ILS 11 paid extract (nesach) would — flagged as a human action (payment/purchase, not performed by agent).
- The SEC-filed English translation is written **first-person singular** ("I visited... I determine that the current value of Automax is approximately USD 44.8 million"), lists contact **ebrik10@gmail.com** and an 052 cell number, and **names no individual author and no professional credential**. The F-4/A's entire qualification statement is: "an experienced independent valuator, with prior knowledge of AutoMax."
- Fee: **NIS 46,800 incl. VAT (~$12,935)** flat, non-contingent; engaged 2024-03-04; re-engaged Nov 2024 for PPA (NIS 14,040 ~$3,900).

**Independence findings:**
1. **No E.D.B.-Weiss/cohort corporate tie found** in web/registry sweeps (name, phone, email, address searches; Hebrew and English). The email handle "ebrik10" suggests a principal surnamed Brik (unconfirmed — no match tying a Brik to the cohort). **UNRESOLVED: the principal's identity.** Two follow-up paths: the ILS 11 Israeli company extract; AutoMax's TASE meeting materials (Aug 2025) which should contain the Hebrew original with the author's credentials page as required by Israeli practice.
2. **The commissioning is itself a relationship**: the valuation cover states it was "commissioned by Mr. Oz Adler, CEO of SCISPARC Ltd" — a cluster cohort member — and is dated ("Drafted on") **January 4, 2024, two months before the disclosed March 4, 2024 engagement** (#13365). The company would say Jan 4 is the valuation-as-of/market-data date; but "Drafted on" is the document's own word, and the body separately calls Jan 4 "the date of the valuation report."
3. **The "prior knowledge of AutoMax" credential is weaker than presented**: the headline valuation for AutoMax's 2021 TASE listing (Matomy merger) was authored by **G.S.E Economic Consulting Ltd** (~NIS 97M equity value), per Matomy's own transaction report to the ISA (#13397). E.D.B.'s prior Matomy work — whatever it was — was ancillary. SciSparc's F-4/A wording survives literally only under a narrow reading.
4. **Financial-independence facts cut both ways**: the fee was flat and non-contingent (their strongest point) but tiny ($12,935 — under a tenth of the combined proposed closing bonuses), the firm accepted management's projections without verification while that management was under criminal indictment (#13394), the multiplier method produced half the DCF number and the report anchored on the higher (#13366), and the valuator was re-hired by SciSparc eight months later (PPA) — a repeat-business incentive.
5. Claim-type discipline: identity/engagement facts = direct_quote/confirmed; the independence *assessment* = synthesis, max medium, labeled as such in the DB.

---

## 5. Post-March refresh summary (Task 4, 2026-03-30 → 2026-07-15)

**The spring 2026 Weiss disengagement (new central fact pattern):**
| Date | Event |
|---|---|
| 2026-03-18 | Form 3s filed at exactly four FPIs (SPRC/PRZO/MTEK/JFBR) — **not** at Clearmind (FPI, chairman) and **not** at CHEV (domestic 12(g), chairman since 2022) |
| 2026-03-30 | Resigns CHEV board (with Tzedef), "personal reasons, effective immediately" |
| 2026-03-31 | Sells entire indirect Viewbix stake at $2.00 (stock later peaks $6.85 post-quantum-rebrand) |
| 2026-04-26 | Resigns Clearmind chairmanship "effective immediately" (no Form 3 ever filed there) |
| 2026-05-03 | Resigns as Gix Internet CEO (remains its credit-facility lender) |

**Per-issuer highlights (financing vs insiders, ±30d flags):**
- **SciSparc (SPRC):** zero new financing filings in the window; the action is the aftermath — going concern, $5.97M AutoMax write-off, 1:9 split (3/4), Nasdaq conditional compliance (5/7). Only Form 4: Shrem sale 462 sh @ $10.00 (6/1) between two M&A PRs (trivial size, timing noted). Nine Form 3/As on 7/13 fixed the whole board's March option-table errors. Oddity: Form 144 by a self-described 12.9% holder (James Edmond Smith) with no 13D/G on file. Pure Capital facility dormant: no draws/conversions; resale F-3 never effective. **±30d flag:** Pure Capital's 13G/A common exit event-dated one day before the facility's quarterly draw window opened.
- **Clearmind (CMND):** the compliance story (above) plus a live death-spiral: $7.55M drawn Apr-Jun at 90% of face, conversion prices stepping $0.60→$0.30, floor reset 3x, 22.6M-share resale F-3 effective 5/7, cumulative 1:400 reverse split in 5 months. The resignation 6-K and the facility reset ran in the same 6-K window (4/30).
- **ParaZero (PRZO):** fifth RDO ($4.0M @ $0.75, Aegis, 3/23) days before the window; Nasdaq min-bid notice 5/8; 1:5-1:20 split authorization 6/1; **Weiss fee doubled retroactively + 325K RSUs + $50K bonus, above comp-policy limits** (6/1); Revach sold 15,731 sh (5/29) **3 days before his re-election** — the company's only insider sale.
- **Viewbix → QXL:** quantum rebrand (4/30) after the 3/4 acquisition (chairman Yoresh held 4.24% of the target); stock 3.4x; Weiss sold at the bottom pre-rebrand; April resale S-3 filed then withdrawn in a week; Aug 2025 S-3 declared abandoned by SEC Rule 479 order (6/26); Rosenbloom/Tzedef Forms 3 ~8 months late.
- **Charging Robotics (CHEV):** no completed uplisting; $25K cash; $2M PIPE unclosed (gated on Uplist Date); Weiss/Tzedef out 3/30; Gix-orbit replacements (Nardimon); Xylo milestone warrants (6.15M sh ~55% of outstanding) extended to 12/31/26 a week before the board shuffle; zero Section 16 filings ever.
- **Maris-Tech (MTEK):** $2M RD (3/9) → $3M ATM (3/30) → 13 promotional PRs in 15 weeks; NT 20-F late notice same day as a "U.S. pilot order" PR; equity deficiency (5/22) cured by accelerated 70%-of-VWAP conversions (5/29); July: reserve tripled → S-8 → $0-cost officer grants (340,353 sh). Weiss remains Chairman (left audit committee 5/20). **±30d flags:** Form 3 batch +9d after the RD; $0 grants during the live ATM.
- **Jeffs' → Nexera (NEXR):** rename/pivot to "homeland security/AI"; note ladder to five notes (4th $1.75M ~5/10; 5th $2.0M 6/18 + 3.2M-share warrant); June resale F-3 = 3.4x outstanding; $1.2M RD priced the day subsidiary Fort listed on Nasdaq (FRTT, 6/8); zero Forms 4/5 across five financings (insiders hold nominal share counts — fee/control cohort, not equity-aligned). Two Form 3s filed ~50 days late; 8 Form 3/As re-filed 5/7.
- **N2OFF → Nexentis (NXTS):** rename effective 2/26; 98% of Save Foods divested 3/15; 1:7 split (4/8) + fresh 1:2-1:500 authorization (4/30); **Pure Capital facility EUR 6M→10M + 1.85M-share ratchet warrant (5/27)**; two RD+PP rounds 10 days apart at $4.008 then $7.056; 7/13 resale S-1 registers the financier/PP warrant shares. **±30d flags:** Weiss/officers' 2/9 $0-grants 11 days before 600K IR-consultant shares and 17 days before the new ticker.
- **Gix Internet (GIXI):** now registering on Form 20FR12B (6/18) for a Nasdaq listing; deconsolidated Viewbix 9/25/25 ($6.73M gain), holds 21.13% of QXL. Weiss out as CEO 5/3 but still a lender. 13G trio (L.I.A./Capitalink/Nissim Daniel) filed at both QXL and CHEV with the same 3/4/26 event date.
- **AutoMax (TASE):** insolvency freeze + trustee (10/21/25); Calcalist: police/ISA probe of Haim & Tomer Levy (concealed commissions, inflated inventory via forged manufacturer emails). SciSparc filed a debt petition.

---

## 6. Story-grade claim inventory (Task 5)

Narrative: **"One financier chaired both sides of a Nasdaq merger while sitting on 9 microcap boards with a traveling cohort."**

| # | Claim | Status after this pass | Lawyer/editor attack & answer | Still missing |
|---|---|---|---|---|
| 1 | "9 microcap boards" | **REVISE: say 8 US-listed (chairman of 6) as of March 2026 — or "more than a dozen public-company roles" counting TASE** | Attack: your own list double-counted Save Foods/N2OFF. Answer: corrected before publication; the bio-sourced enumeration (#13435) is now airtight. | Nothing — but must use the corrected count. |
| 2 | "Chaired both sides of a Nasdaq merger" | **SOLID (confirmed, verbatim, multiple filings)** | Attack: "he recused himself from every vote" (true, disclosed — #13368) and "shareholders knew" (disclosed conflict). Answer: recusal is disclosed alongside a **$150K bonus contingent on closing** (#13367), no fairness opinion (#8885), and he stayed AutoMax chairman until 10 days after termination (#13409). | Nothing for the fact; fairness requires printing the recusal. |
| 3 | "No independent fairness opinion" | **SOLID with mandatory context (corrected #8885)** | Attack: "Israeli law did not require one; we obtained an independent E.D.B. valuation instead; cost-benefit was reasonable for a microcap." Answer: print their words — then the E.D.B. facts: $12,935 one-person shop, Gmail contact, no named author/credentials in the SEC filing, commissioned by the CEO, drafted-date anomaly, management projections accepted unverified from indicted management, methodology spread $21.7M vs $44.8M anchored high. | E.D.B. principal's name (registry extract or AutoMax Hebrew meeting materials) — get before print; give E.D.B./SciSparc right of reply. |
| 4 | "Traveling cohort" (Adler/Revach/Dinar/Tzedef/Dayan/Baranes) | **SOLID (#8891 verified; strengthened by refresh)** | Attack: "overlapping directorships are legal and common in Israeli microcaps." Answer: true — the story is the *pattern*: same filing agent, same-day Form 3 event dates across issuers, same financier, cross-holdings (SciSparc >10% of Nexentis), and fee/control economics (nominal equity stakes, $0-cost grants). | Optional: comp aggregation per cohort member. |
| 5 | The merger target collapsed amid a criminal probe | **SOLID — SciSparc's own 20-F: "investigation... and the arrest of senior officials of AutoMax" (#13407); insolvency + $5.97M write-off (#13408)** | Attack: "arrests/probe post-date the F-4 valuation; nobody could know." Answer: the F-4/A itself disclosed the **August 2021 indictment** (forgery/fraud/smuggling/money laundering) of the same management whose projections E.D.B. accepted unverified (#13394). | Israeli court/ISA primary documents for the 2025 probe (currently Calcalist-attributed, #13399 labeled secondary). |
| 6 | One financier behind the cluster (new since March) | **SOLID: Pure Capital/Silberman documented at 6 issuers + the Xylo→Gix→QXL chain (#13400/#13405/#13429), consultant-fee offset at SciSparc (#13410), same building as SciSparc (#13400)** | Attack: "arm's-length institutional investor; disclosed in every prospectus." Answer: a five-year paid consultant with fee-offset rights, HQ'd at the issuer's address, is not the ordinary meaning of arm's-length; all documented from their own filings. | Silberman's side; base-rate check (does he run the same structure outside the Weiss cluster?). |
| 7 | HFIA compliance angle: "the new law made him visible — and gaps appeared" | **STRONG but must stay labeled**: Clearmind gap (#13413/#13414, synthesis/medium) and CHEV gap (#13416, inference/medium) | Attack: "there is an exemption you missed" / "forms were filed on paper" / "10% holders only". Answer: documented absence at issuer+owner level; he signed the F-3 describing the obligation; the CHEV gap predates HFIA entirely — but this claim NEEDS counsel-grade confirmation before print (e.g., CHEV 12(g) continuity; any SEC relief). | Securities-law review; company responses. |
| 8 | Death-spiral financing across the cluster | **SOLID (terms verbatim: 88%-of-VWAP, 90%-of-face, 70%-of-VWAP at MTEK; 3.4x resale registrations; 1:182 and 1:400 cumulative splits)** | Attack: "standard microcap financing; fully disclosed; the alternative was insolvency." Answer: print terms + outcomes; the pattern across one chairman's portfolio with one financier is the story. | Retail-holder loss quantification (optional color). |
| 9 | Weiss profits while shareholders diluted | **PARTIAL**: $224K ParaZero comp verified to the dollar + fee doubling above comp policy (#13430); ~$488K/yr floor stands (corrected) | Attack: "comp approved by shareholders." Answer: approved 6/1 at a quorum-failure-adjourned AGM, retroactive, and explicitly "in excess of" the comp policy — their own proxy's words. | SciSparc/Maris/Nexera/Nexentis per-person amounts (not itemized in filings reviewed). |
| 10 | The spring 2026 disengagement | **NEW, SOLID on facts; framing = synthesis/medium (#13418, #13419)** | Attack: "routine portfolio rationalization; personal reasons." Answer: four exits in five weeks, starting 12 days after the Form 3 sweep that omitted exactly the two problem issuers; he sold Viewbix at $2.00 before a 3.4x run — consistent with severance, not profit-taking (cuts against a pump-and-dump reading and should be printed as such). | His answer to "why now?". |

**Bottom line:** the two-sided-chairman + no-fairness-opinion + E.D.B. + indicted-target + collapse arc is publication-grade from primary documents end-to-end, with the company's best rebuttals (recusal, no-legal-requirement, disclosure) captured verbatim and answerable. Weakest links deliberately kept at medium confidence: the two Section 16 gap claims (need securities-counsel sign-off), the E.D.B. principal's identity (needs the registry extract), and the 2025 Israeli criminal probe details (need Israeli primary documents).

---

## 7. Proposed leads (NOT written to DB — lead_tracker cannot target hfia)

1. **Identify E.D.B.'s principal** — purchase Israeli company extract for 514752195 (human action: ILS 11 payment) and/or pull AutoMax's Aug 2025 TASE meeting materials (Hebrew E.D.B. original with credentials page). Category: entity, priority: high. Evidence: SEC:CIK1611746:0001213900-25-022367; ISRAEL_REGISTRY:514752195.
2. **Securities-counsel review of the two Section 16 gap claims** (Clearmind FPI post-HFIA; CHEV domestic 12(g) since 2021, zero filings ever, no Item 405). Category: legal, priority: high. Evidence: findings #13413/#13414/#13416.
3. **Israeli primary documents for the 2025-26 AutoMax probe** (ISA announcements, court freeze order of 2025-10-21, trustee filings; status of Haim/Tomer Levy). Category: legal, priority: high. Evidence: #13399/#13407/#13408.
4. **MitoCareX related-party pass** — SciSparc sold MitoCareX to N2OFF/Nexentis ($700K + $2.027M stock; SciSparc now >10% holder) while Weiss sat on both boards; Nexentis then made MitoCareX its headline business and raised twice in June. Category: financial, priority: medium. Evidence: #13436.
5. **Pure Capital base-rate check** — enumerate all EDGAR issuers where L.I.A. Pure Capital/Silberman/Capitalink appear as selling shareholders or 13G filers, to test whether the pattern is Weiss-specific or Silberman-general. Category: entity, priority: medium. Evidence: #13400/#13405.
6. **QXL quantum-pivot scrutiny** (Yoresh both-sides acquisition, 3.4x run on "50+ qubit" claim, withdrawn/abandoned resale registrations, late Forms 3). Category: financial, priority: medium. Evidence: #13419.
7. **Tomer Ltd. governance question** — Weiss sits on the board of an Israeli government-owned defense company while chairing distressed microcaps financed by discounted convertibles; map appointment process/disclosures. Category: person, priority: medium. Evidence: #13435.
8. **Clearmind 20-F quote re-pull** for #8893 (only remaining unverified quote in the original set). Category: document, priority: low.
9. **source_datasets JSON migration** (platform hygiene; blocks `verify` on pre-migration rows) — spawned as background task chip task_c87ab263.

## Coverage notes / honest limits
- F-4/A (9.6MB) read via full-text extraction with exhaustive passes over: fairness/valuation sections, Annex E (complete, E-1→E-38), interests/conflicts, bonuses, recusals, background-of-merger, AutoMax litigation disclosures. Untouched regions are standard prospectus boilerplate (tax, exchange mechanics, comparative rights). Exhibits inventoried (ex10-8 consulting agreement not read; ex23-1/23-2 consents; ex99-1 proxy card read).
- Clearmind 20-F (Jan 2026) not re-pulled — #8893's direct quote remains verified-by-provenance only.
- Subagent-sourced quotes: all load-bearing ones (termination 6-K, 20-F investigation/impairment/Weiss-AutoMax passages, consultant-offset side letter, Clearmind resignation 6-K, F-3 signature page, Nexera rename, Nexentis warrant) independently re-verified against primary text before DB write; remaining refresh detail (tables, PR cadences, 13G rosters) rests on agent pulls with accessions recorded in the four refresh-*.md files in this directory.
- `verify` status flags blocked by legacy source_datasets format (see task chip); the verification pass is auditable via the `correct` trail (`--by agent:weiss-verify-20260715`).
