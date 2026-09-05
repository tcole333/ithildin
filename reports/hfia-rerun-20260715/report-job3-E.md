# Job 3 Forensics Wave — AGENT E: hot_form4-near-financing forensics (breadth pass)

**Profile:** hfia | **Thread:** 40

## 5-line summary
1. Ranked all 1,221 hot_form4 rows by disposition-proximity-value; excluded 972 (agents A–D), leaving 249 rows / 55 distinct issuers disjoint from A–D. Verified top ~15.
2. Flagship anomaly: **BBB Foods (TBBB, Mexico)** — four FPI insiders (Chair/CEO Hatoum, CFO Pizzuto, 2 directors) sold 813,336 shares ≈ $26.4M at $32.50 on 2026-06-01 as selling shareholders in a registered secondary (424B5, 2026-05-29). Disclosed, but the cleanest demonstration of what HFIA newly makes Form-4-visible.
3. Signal dominated by benign patterns: debt-shelf false positives (HSBC 424B5 = $4.5B senior notes; Sony/AerCap/Nomura/Mizuho/MUFG same), broker-nominee 10%-holders (Cetera/RPGL, Jane Street/HKIT), insider *buys* near raises (Globus/Canaan/Sol-Gel/ProQR).
4. No undisclosed dumping into a discounted dilutive raise, no grant-timed-to-raise anomaly found outside the disclosed BBB secondary. SEC-enforcement/FINRA clean on all sharp names.
5. Findings added: #13653 (BBB Foods, direct_quote/confirmed), #13654 (debt-shelf false positives, synthesis/medium). Both hfia / thread 40.

## Ranking methodology
Joined each hot row to universe `transactions` by form4_accession to recover tx_code/shares/price/acquired_disposed and disposal value. Score = days-proximity (|Δ|=0→40 … ≤5→26 … >20→2) + code priority (S→40, P→18, A→16, F→8, M→4; F-only <$250K demoted) + value (2.5·log10). Elevates near-concurrent real-dollar open-market dispositions over routine grants/exercises/withholding. Artifact: E-hot-ranked.csv (all 1,221 rows enriched + excl-tagged + score).

## Exclusions (agents A–D)
- B: SOPHiA/AXIA/SCHMID/Arqit/SEALSQ/Pharvaris/Vertical + convergence top-30 → 964 rows (30 issuers), dominant overlap.
- A: HRT's 17 → 17 rows (Rubico [also B], Clearmind, YY Group, Decent).
- C: Panagiotidis/Vafias/Xiradakis shipping → 0 rows (not in hot_form4).
- D: AMTD/Yang/Shao/Lai → 0 rows (AMTD not in hot_form4).
My 249-row / 55-issuer set is genuinely disjoint from all four.

## Top-15 triage (distinct non-excluded issuers)
1. BBB Foods (TBBB) MX — Hatoum CEO +3 — S 813,336sh/$26.4M @$32.50 — ANOMALY→disclosed secondary (#13653)
2. HSBC (HSBC) UK — Palomaki officer — S $418K — BENIGN, 424B5=$4.5B notes (#13654)
3. Republic Power (RPGL) SG — Cetera Wealth (10%) — S 680K/$374K — BENIGN broker nominee
4. Aurora Mobile (JG) KY — Lee Hon Sang Dir — S ~$10K — BENIGN de-minimis near F-3
5. RedHill (RDHL) IL — Raday officer — M+S ~$1.4K — BENIGN exercise+sell-to-cover, ATM
6. HiTek (HKIT) CN — Jane Street (10%) — P+S $60K — BENIGN market-maker inventory
7. Wearable (WLDS) IL — Barel CMO — S 7,182sh/$7.2K — BENIGN de-minimis
8. Sony (SONY) JP — Kodera/Totoki/Ahuja/Mitomo — S ~$7.4M (5) — BENIGN routine exec RSU; notes shelf
9. Digi Power X (DGXX) CA — Amar President — S 55K/$165K — BENIGN sold before run; ATM
10. Sol-Gel (SLGL) IL — Opaleye (10%) — P (buy) ~$2.8M — BENIGN fund accumulation
11. Globus Maritime (GLBS) GR — Feidakis chairman — P (buy) ~$150K — BENIGN chairman support buy
12. Canaan (CAN) SG — Zhang CEO/Cheng CFO — P (buy) ~$350K — BENIGN founders buying @$0.33
13. Critical Metals (CRML) AU — Zhernov Director — S 50K/$402K — MONITOR near PIPE-resale F-3
14. Webull (BULL) — Denier President — S 75K/$466K — BENIGN-leaning post-SPAC resale
15. AerCap (AER) NL — Stuart CFO — S $1.66M — BENIGN notes shelf; routine CFO sale

## Sharpest anomaly — BBB Foods (#13653, confirmed)
424B5 0001193125-26-248693: "Bolton Partners Ltd., a vehicle affiliated with our founder, Chairman and Chief Executive Officer, is offering for sale 150,000 Class A common shares … [and] to subscribe 10,000 Class B common shares" — matches Hatoum Form 4 (…255987, S 150,000 + P 10,000) exactly. Khouri (S 350,000), Pizzuto (S 180,000), Apalategui (S 133,336), all 2026-06-01 @ $32.50. Front-runs the Class C unlock (2026-08-06). Convergence pass under-ranked it (score 10.8, ~rank 39); disposition-value weighting surfaced it #1.

## Debt-shelf false positives (#13654, medium)
HSBC 424B5 0001193125-26-214630 = "$2.25B 4.711% Senior Unsecured Notes due 2030 + $2.25B 5.208% due 2034" — debt, unrelated to the matched RSU sale. Generalizes to Sony/AerCap/Nomura/Mizuho/MUFG. Every P-cluster is an insider buy (support/participation); no discounted-raise dumping, no timed grants.

## Proposed leads (not written to DB)
1. BBB Foods Class C unlock 2026-08-06 — watch follow-on FPI-insider Form 4 selling as ~12.6M Class C→A restrictions expire.
2. Equity-only 424B5 filter — drop senior-notes/MTN takedowns to kill debt-shelf false positives.
3. Tag broker-nominee 10%-holders (Cetera, Jane Street, custodians) as a distinct class — custodial noise.
4. Selling-shareholder-secondary detector — flag Form 4 S-codes at exactly the 424B5 offering price on offering date (highest-value HFIA-newly-visible class).
5. CRML/Zhernov — pull Form 4 footnotes to confirm/deny 10b5-1 on the $402K sale near the PIPE-resale shelf (low).

## Findings
#13653 (BBB Foods — direct_quote/confirmed), #13654 (debt-shelf false positives — synthesis/medium). Artifacts: E-hot-ranked.csv, E-rank.py, E-distinct.py, E-findings.sh.
