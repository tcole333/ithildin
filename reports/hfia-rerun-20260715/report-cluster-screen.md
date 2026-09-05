# HFIA C1 — Cluster Triage + Tier 0 Financial Screen

Agent C1 of 3-agent wave · profile `hfia` · 2026-07-15
Inputs: `datasets/hfia_universe.db`, `clusters.csv` (241), `hot_form4.csv` (1,221), `report-universe.md`
Findings written: **#13529-13533, #13546-13551** (threads 39/40, profile hfia). No leads written.

---

## 1. Cluster classification (top ~25 of 241)

Types: (a) sponsor/family complex · (b) market-maker footprint · (c) professional serial director · (d) governance cohort at financing-pressure small-caps · (e) serial-spinoff family

| # | Cluster (owner CIK) | Issuers | Type | Priority | Note |
|---|---------------------|---------|------|----------|------|
| 1 | HRT FINANCIAL LP (1475597) | 17 micro-caps | **b** | color only | 30/72 Form 3/4 as 10% owner; the issuer list doubles as a micro-float/high-churn watchlist (incl. Hub Cyber, Clearmind, Rubico, YY Group). Post-Act change filings = position churn, not governance signal |
| 2 | Yang Conor Chia-hung (2121924) | 5 China ADRs (iQIYI, UP Fintech, EHang, NovaBridge, Smart Share) | **c** | low-med | initial-disclosure footprint only (5×Form 3) |
| 3 | Adler Oz (1973096) | SciSparc, Rail Vision, Nexera, **Polyrizon** | **d** | **HIGH** | CEO-and-CFO/director roles; incl. post-Act change filing (PLRZ sale 3/31); overlaps #6/#17 |
| 4 | Blidner Jeffrey M (1245162) | 4 Brookfield partnerships | **a** | low | single-sponsor compliance batch |
| 5 | Pittas Aristeidis J (2121849) | Euroseas, Pyxis, EuroDry, Euroholdings | **e** | medium | Greek shipping spinoff family; echoed by Karmiri/Kyriakopoulos/Pariaros/Tamvakakis/Taniskidis clusters (same trio) |
| 6 | Weiss Amitay (1826620) | SciSparc, Maris Tech, Nexera, ParaZero | **d** | **HIGH** | the profile's seed pattern; gate audit resolved (4 in-universe + Viewbix out-of-scope) |
| 7/9/15/18 | Elsztain A. / Elsztain E. / Gaivironsky / Zang (IRSA group) | IRSA, Cresud, BrasilAgro | **a** | low | one Argentine family complex counted 4× — treat as a single cluster |
| 8 | Shao Sean (1432657) | UTStarcom, VNET, Luckin Coffee | **c** | medium color | audit-committee professional incl. Luckin (2020 fraud history); 4 post-Act Form 4s worth periodic review |
| 10 | Lai Jimmy Y. (1975788) | 51Talk, FinVolution, Youdao | **c** | low | |
| 11 | Falk Dan Michael (1966097) | NICE, Evogene, Innoviz | **c** | low | Israeli serial independent |
| 12 | Panagiotidis Petros (2118775) | Castor, Toro, Robin Energy | **e** | medium | known dilution-machine family; **universe shows zero post-Act open-market dispositions** (only 2 grant-type Form 4s at Toro) — no timing flag yet |
| 13 | Vafias Harry (1328921) | StealthGas, Imperial Petroleum, C3is | **e** | medium | IMPP screened below; shares 4.78M→44.6M in 4yrs (9.3×) but currently profitable; no post-Act dispositions |
| 14 | Zheng Yeeli Hua (2123010) | Bitfufu, MaxsMaking, Youlife | **c** | watch | 2 post-Act Form 4s across China small-caps |
| 16 | Karmiri Stefania (2122338) | Euroseas trio | **e** | dup of #5 | corporate secretary echo |
| 17 | Revach Moshe (1973293) | SciSparc, Nexera, ParaZero | **d** | **HIGH** | Weiss-cohort overlap; 5 Form 3s + 1 change |
| 19 | Baudo Giampietro (2125501) | AMTD IDEA, AMTD Digital, Generation Essentials | shared-CEO complex | evaluated | one person as CEO of three listed vehicles of the 2022 HKD meme-stock group; Form 3s only, zero transactions — structural watch, see §2 |
| 20 | Bevilacqua Flavia (2131749) | TGS, Edenor, Pampa | **a** | low | Pampa/Mindlin group batch (Mindlin himself: 9 post-Act Form 4s, all Pampa-group buys — accumulation, not exit) |
| 21 | Cohen Yuval (1374287) | Radware, Stratasys, Kornit | **c** | low | |
| 22 | Gruber Dafna (1971695) | ICL, Check Point, Cellebrite | **c** | low | |
| 23 | JIAO Jie (2114483) | Amber Intl, QUHUO, GrowHub | **c/d** | watch | crypto-adjacent (Amber Group vehicle) |
| 24 | Jin Xin "Moore" (2118954) | Cango, Aurelion, Antalpha | **c/d** | watch | Bitmain-ecosystem overlap (Antalpha; Cango mining pivot) |
| 25 | Kostogiannis Ioannis (2118310) | StealthGas trio | **e** | dup of #13 | |
| 26 | Shin Ho Chuen (2121135) | SuperX AI, Globavend, Luda Technology | **d** | watch | AI-hype nano-caps, 1213900 filing-agent cohort |
| 27 | Li Dong (2124606) | GreenTree, TH International, Yuanbao | **c** | low | |
| 28 | Lin Frank Hurst (2002613) | Vipshop, 51Talk, Here Group | **c** | low | VC (DCM) footprint |
| — | Manor Sagit (1999977) | TAT Technologies, Nayax | **c** | color | CFO with 7 post-Act Form 4s across two Israeli issuers |

**Excluded from targeting per mandate:** UBS, Barclays, BMO, RBC, BNS, TD, CIBC, Deutsche Bank ETN complexes — "escalation scores" are shelf-volume artifacts (also excluded from convergence: Nomura, MUFG, Mizuho, Sony despite hot-match counts — structured-program/size artifacts).

---

## 2. Target selection (10) — cluster membership × post-Act Form 4 × financing windows

| Ticker | CIK | In | Why (one line) |
|--------|-----|----|-----|
| PLRZ | 1893645 | YES (mandated) | Adler-cohort nano-cap; 3 cluster owners; 6 open-market sales in first 2 post-Act weeks; 18 hot matches |
| SOPH | 1840706 | YES (mandated) | Heaviest hot count in universe (115); 99 post-Act Form 4 rows; 106 open-market sales; 11 financing/resale filings |
| QTEX | 1837493 | YES | Hype-pivot rename (Inspira Technologies IINN → QTREX Quantum); 21 hot; 7 open-market sales; serial 424B5/F-1/F-3 |
| ARQQ | 1859690 | YES | Quantum small-cap; 28 hot + 57 post-Act Form 4s; 76 open-market sale rows ($2.5M dispositions) |
| LAES | 1951222 | YES | 4 cluster owners; 35 open-market sales; WISeKey serial-spinoff family; quantum-hype raise machine |
| SPRC | 1611746 | YES | Hub of Weiss/Adler/Revach cohort (4 cluster owners); financing treadmill; 1 post-Act sale |
| ALAR | 1725332 | YES | 42 hot matches (2nd-highest small-cap); Israeli; option-exercise clusters near financings |
| NEGG | 1474627 | YES | Cluster member (Zheng Fuya); 28 post-Act open-market sales ($7.7M); China-linked; meme history |
| IMPP | 1876581 | YES (trio rep) | Vafias Greek-shipping trio representative; the family's dilution vehicle (9.3× share growth since 2021) |
| HKD | 1809691 | YES (evaluated) | AMTD complex representative for the mandated evaluation; Baudo triple-CEO structure |

Evaluated and excluded (one line each):
- **AMTD IDEA (1769731)**: zero post-Act transactions (3 Form 3s only); complex evaluated via HKD; structural review proposed as lead, not a Tier 0 target.
- **Generation Essentials (2053456)**: new listing, zero transactions, no annual XBRL history to screen — premature for Tier 0.
- **Castor/Toro/Robin (Panagiotidis trio)**: zero post-Act open-market dispositions in universe DB (grants only) — IMPP better represents the Greek-shipping dilution pattern this window.
- **Nexera Technologies (1885408)**: 5 cluster owners but zero post-Act Form 4s — cohort covered via SPRC/PLRZ findings.
- **Codere Online / Himalaya Shipping / Rubico**: real single-signal candidates (sales near financings) — deferred to Proposed Leads.
- **Vesta/AXIA and Japanese banks**: hot counts are structured-program or shelf-volume artifacts.

---

## 3. Tier 0 screening matrix

Standard pipeline (`query_edgar.py sections` → `financial_ratios.py`) **cannot process 20-F filers** ("ERROR: No 10-K filings found" for all 9 FPIs; NEGG's only 10-K is a stale 2013 filing yielding all-null ratios). Screen executed via documented fallback: SEC companyfacts XBRL (us-gaap + ifrs-full), same severity framework (HIGH=3/MED=2/LOW=1; ≥6 deep-dive, 4-5 standard). Artifacts: `facts-screen-report.json`, `facts-<CIK>.json`, per-target `*-sec-enf.json` / `*-finra.json`.

| # | Ticker | Company | CIK | Anomalies | Score | SEC exact actions | FINRA firm | Top flag | Recommendation |
|---|--------|---------|-----|-----------|-------|--------------------|------------|----------|----------------|
| 1 | QTEX | QTREX Quantum Ltd. | 1837493 | 2H+2M | **10** | 0 | 0 | Net loss 45.7× revenue; <4mo cash; 48%/yr dilution; gross profit $2K | **Deep Dive** |
| 2 | SPRC | SciSparc Ltd. | 1611746 | 2H | **6+** | 0 | 0 | FY25 auditor going-concern paragraph; losses $5.9M→$7.5M→$12.6M | **Deep Dive** |
| 3 | ARQQ | Arqit Quantum Inc. | 1859690 | 1H+1M (FY2025 restated from 20-F text) | **5** | 0 | 0 | Net loss $35.3M vs revenue $0.53M (66.7×); 12-month sufficiency language | Standard |
| 4 | PLRZ | Polyrizon Ltd. | 1893645 | 1H+1M | **5** | 0 | 0 | Cash $1.31M vs burn $4.53M/yr (~3.5 months); pre-revenue | Standard→**escalated by timing flag** |
| 5 | LAES | SEALSQ Corp | 1951222 | 1H+1M | **5** | 0 | 0 | Shares +92%/yr (100.0M→191.5M in FY2025); loss 1.9× revenue; $417.7M cash raised | Standard→**escalated by timing flag** |
| 6 | SOPH | SOPHiA GENETICS SA | 1840706 | 2M | **4** | 0 | 0 | Loss $79.0M ≈ revenue $77.3M; cash <2yr burn | Standard |
| 7 | ALAR | Alarum Technologies Ltd. | 1725332 | 1H | **3** | 0 | 0 | +$0.96M net income vs -$2.01M operating CF (accrual divergence) | Monitor |
| 8 | NEGG | Newegg Commerce, Inc. | 1474627 | 1M (stale) | **2*** | 0 | 0 | XBRL concept discontinuity → partial coverage; $7.7M post-Act insider sales noted | Monitor (re-screen) |
| 9 | IMPP | Imperial Petroleum Inc. | 1876581 | 1M | **2** | 0 (4 hits = name collision, see gaps) | 0 | 31%/yr continued dilution; otherwise profitable ($50.0M NI, $80.8M OCF) | Monitor |
| 10 | HKD | AMTD Digital Inc. | 1809691 | 0 | **0** | 0 | 0 | Tier 0 clean (NI $97.0M on rev $136.1M FYE 2025-10-31); no share-count facts | Clean (structural watch only) |

*Skips/documented failures*: all 9 FPIs skipped by the standard sections pipeline (20-F unsupported); NEGG ratios JSON produced but all-null (stale 2013 10-K auto-selected). Fallback covered everything except HKD share counts and NEGG post-2022 revenue concepts.

---

## 4. Insider-vs-financing forensics (top scorers + mandated SOPH)

Exact dates; windows = ±30d vs financing filings (F-1/F-3/424B/EFFECT/POS AM/S-8). Full detail: `timing-out.txt`, `forensics-out.txt`. All flags are timing correlations from primary filings; 10b5-1/footnote status not examined; no scienter claim.

### PLRZ — Polyrizon (finding #13548, thread 40) — STRONGEST FLAG
- 2026-03-30/31: CEO Izraeli ($48,435), dir. Adler ($39,668), CTO Turgeman ($31,795), dir. Carmel ($12,743) sold at **$10.90–$12.36** — total ~$132.6K, the issuer's first-ever Section 16 disclosures.
- 2026-04-08 (**Δ8-9d later**): 424B5 prices 87,777 shares at **$9.00** (+190K pre-funded warrants) — 17-27% below insider sale prices. F-1 follows 04-23 (EFFECT 05-04).
- Company had ~3.5 months of cash (finding #13531).

### QTEX — QTREX Quantum (finding #13549, thread 40)
- 2026-05-27→06-01: CFO Tehila 90,000 sh / **$248,980** (incl. $0.12-strike exercise, same-day sale at $2.03); CTO Yechezkely Hayon 50,000 sh / **$150,000** (05-29), into a $2.01→$3.51 rising tape.
- 2026-06-04 (**Δ3-8d later**): new F-3 shelf (0001185185-26-002343), EFFECT 06-16; POS AMs 06-16/07-07.
- 2026-07-06: CFO/CTO/CBO each granted 550,000 shares (~1.5% of company each).

### LAES — SEALSQ (finding #13550, thread 40)
- 424B5 2026-03-17 → CFO O'Hara starts near-daily 10,000-sh sales 2026-03-19 (**Δ2d; also day+1 of HFIA effect**): 22 sales, 195,664 sh, **$556,880** through 06-05.
- Secretary Verjus sold 5,000 sh on **2026-03-18 — the Act's effective date**. CEO Moreira $112,291 (May-Jun). VPs Buonanno/Enguent/Feuardent: $0.01-strike exercise + same-day sales; dir. Ward: 366,746-option exercise 06-16.
- None of this was SEC-reportable pre-HFIA.

### SPRC — SciSparc (finding #13547 context)
- Zero post-Act dispositions within financing windows (single $4,620 sale outside). Flag is financial (going concern) + cohort centrality, not timing.

### ARQQ — Arqit (finding #13546 context)
- Only in-window disposition pattern: dir. Lefebvre d'Ovidio daily micro-sales (~$25K total, Δ0-30d around 05-21 424B3) — value-immaterial; likely program selling. Larger officer dispositions fall outside financing windows. No timing finding recorded.

### SOPH — SOPHiA GENETICS (finding #13551, thread 40)
- 424B5s 2026-06-16 + 06-17 → founder Camblong sold 183,792 sh / **~$1,064,127** 06-25→07-10 (incl. 95,419 × $3.16 option exercise-and-sell into $5.7-$6.3 tape), **Δ5-23d after** the supplements, exactly across his CEO→Executive Chairman transition (Muken to CEO). Whole C-suite sold in window (mostly small sell-to-cover-pattern amounts); CFO Cardoza bought 20,000 sh (P, 06-05) — a countervailing signal.

---

## 5. Escalation recommendations

1. **QTEX → Tier 1 deep dive now** (`/analyze-filing --cik 1837493`, 20-F 0001185185-26-001072 + June F-3): pivot-promotion mechanics, option repricing/grants, placement agents, and the July 550K-share grants.
2. **PLRZ → Tier 1 deep dive** (424B5 0001213900-26-041507 + F-1 0001213900-26-047091): read Form 4 footnotes for 10b5-1 language, identify placement agent and buyers; hand off to C2/C3 for Adler/Weiss cohort-wide replication of the sell-before-raise pattern (SciSparc #13547, ParaZero, Maris Tech, Rail Vision, Nexera).
3. **LAES → Tier 1**: O'Hara program vs WISeKey parent-level history (entity #2183 family); check whether 20-F discloses selling plans; monitor further WISeKey spinoffs.
4. **SPRC → Tier 1** (20-F 0001213900-26-049322): going-concern + who buys the serial 424B5s; map the 1213900-agent cohort financings as a system.
5. **SOPH → monitor + one targeted check**: pull Camblong Form 4 footnotes for plan adoption dates vs the June 424B5s; if no plan, escalate.
6. **ALAR → peer-compare** (`/compare-peers`): accrual divergence check against Israeli data/proxy peers.

## 6. Proposed leads (NOT written to DB)

1. [high] Financial forensics: QTREX Quantum — score 10; CFO/CTO pre-shelf sales; 550K-share July grants (SEC:CIK1837493:0001185185-26-001072)
2. [high] Polyrizon insider-sales-before-$9.00-offering — Form 4 footnote/plan verification + placement agent chain (SEC:CIK1893645:0001213900-26-041507)
3. [high] SEALSQ CFO daily-sale program from HFIA day 1 — plan disclosure + WISeKey family pattern (SEC:CIK1951222:0001104659-26-029206)
4. [medium] SciSparc going-concern financing treadmill + Weiss/Adler/Revach cohort-wide sell-near-raise sweep across ParaZero/Maris/Rail Vision/Nexera (SEC:CIK1611746:0001213900-26-049322)
5. [medium] SOPHiA GENETICS Camblong transition-window sales — 10b5-1 adoption-date check (SEC:CIK1840706:0001193125-26-274381)
6. [medium] Himalaya Shipping: single $5.35M insider sale near EFFECT 2026-06-18 (convergence.csv) — one-shot verification
7. [medium] Codere Online: director sales same-day as 424B3s (hot_form4 rows, 2026-06-10) — verify
8. [low] Newegg re-screen with post-2022 revenue concepts + Zheng Fuya cross-issuer review
9. [low] Greek trios standing watch: alert on first post-Act disposition near any ATM/424B5 (Castor/Toro/Robin, StealthGas/IMPP/C3is)
10. [low] AMTD complex structural review: Baudo as CEO of three listed vehicles; GEG new-listing mechanics (Form 3s only so far)

## 7. Coverage gaps

- **Standard Tier 0 pipeline is 10-K/10-Q-only**: all nine FPI targets skipped by `query_edgar.py sections`; NEGG auto-selected a 2013 10-K with null XBRL. Fallback = SEC companyfacts (documented above). Infra suggestion: extend sections/financial_ratios to 20-F XBRL.
- **companyfacts staleness**: ARQQ FY2025 20-F (0001104659-25-119500) and SPRC FY2025 20-F (0001213900-26-049322) filed but absent from the companyfacts API; both restated from 20-F text.
- **HKD**: no share-count concepts in companyfacts → dilution not computable; FY is Oct-end (latest 2025-10-31).
- **NEGG**: revenue concept discontinuity after 2022 → ratios partial; treat score as floor.
- **IMPP name collision (documented, dismissed)**: 4 exact SEC-enforcement matches ("Imperial Petroleum, Inc.", LR-22800/AAER-3485 2013, 34-76005 2015, LR-23599 2016) are the Indiana biodiesel company, not the 2021 Marshall Islands Vafias entity. QTEX alias fuzzy hits (17) are generic "Technologies" noise — no true Inspira match. WISeKey/AMTD/Therapix alias checks: 0.
- **FINRA**: 0 firm results for all 10 — expected (issuers are not member firms); checks run per skill, recorded as coverage context, not cleanliness.
- **10b5-1 status unexamined**: universe DB does not carry Form 4 footnotes; every timing flag above is correlation-only pending footnote reads.
- **No market-cap field** in universe (per report-universe caveat): small-cap bias applied via share counts × Form 4 prices, not measured cap.
- Regulatory DBs cover SEC litigation/admin releases as ingested 2026-03; recent-weeks actions may lag.

## Artifacts (workdir /tmp/osint-yg3uYgJy)
`convergence.csv`, `facts-screen-report.json`, `facts-<CIK>.json`, `forensics-out.txt`, `timing-out.txt`, `<TKR>-financing.json`, `<TKR>-sec-enf.json`, `<TKR>-finra.json`, `PLRZ-424b5.json`, `ARQQ-20f.json`, `SPRC-20f.json`, scripts (`converge.py`, `facts_screen.py`, `timing_map.py`, `screen.sh`, `regcheck.sh`, `findings*.sh`).

## DB writes
- Findings (profile hfia): thread 39 → #13529, #13530, #13531, #13532, #13533, #13546, #13547; thread 40 → #13548, #13549, #13550, #13551.
- Entities: created #5461 QTREX Quantum Ltd., #5462 Arqit Quantum Inc., #5463 Alarum Technologies Ltd. (SOPHiA GENETICS SA resolved to existing #2210); 10 officer/director roles added to #2541 (Polyrizon), #5461 (QTREX), #2183 (SEALSQ), #2210 (SOPHiA).
- No lead_tracker writes; no profile switches; no skill invocations.
