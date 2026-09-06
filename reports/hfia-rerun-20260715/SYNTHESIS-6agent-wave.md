# HFIA Rerun — 6-Agent Forensics Wave Synthesis (2026-07-15)

> **Companion document.** A parallel session's `SYNTHESIS.md` already exists in this directory covering a *3-agent* forensics wave (cluster-screen / compliance-gap / cohort-extension), findings #13529–13585, auto-leads #70352–70363, and infra #158. THIS document covers a **separate 6-agent wave (A–F)** dispatched in a different session, plus the Eldad Brik identification and the TASE cross-regulator contradiction. The two share the universe DB and the Weiss verification (#13364–13437) but otherwise cover different ground and should be MERGED. Overlap/conflict notes at the bottom.

Run entirely under the profile-override constraint: active profile (`epstein-gates-ipi`) never switched; every write carried explicit `--profile hfia`. Verified zero leakage — 82/82 wave findings correctly `hfia`-tagged while five other sessions wrote concurrently.

## What this session ran
1. **Universe rebuild (Codex gpt-5.6-sol).** `datasets/hfia_universe.db` — 1,389 FPI issuers, 11,685 filings, 9,515 transactions, 241 clusters, 524 never-filers + analytics CSVs (clusters, hot_form4 [1,221], never_filers, sync_batches, convergence).
2. **Weiss cluster verification** — 14 March findings re-verified (5 as-written, 8 corrected), 39 new, 13 corrections. Shared with the parallel synthesis.
3. **Eldad Brik identification (Dehashed) + TASE contradiction** — new this session.
4. **Job 3 forensics wave — 6 parallel agents (A–F)** — 82 findings, all hfia.

## Story ranking

### Flagship (publication-grade)
- **Weiss / E.D.B. / AutoMax** — dual-chairman merger, no fairness opinion, E.D.B. one-person shop, indicted target management, collapse amid Israeli criminal probe, $5.97M write-off. (Detail: report-weiss-verification.md.)
- **NEW — cross-regulator contradiction (#13728 contradicts #8885).** SciSparc told the SEC its board relied on the E.D.B. DCF valuation ($44.8M); AutoMax told TASE (issuer 2280 convocation §3.14.6, verbatim Hebrew) its board "did not receive any document or work regarding a valuation... and did not base the transaction value on any methodology such as DCF or the net-asset-value method." The two merger parties told their regulators contradictory things about whether a valuation existed. Sharpest new fact of the rerun.
- **NEW — E.D.B. author = Eldad Brik (אלדד בריק), #13589.** Two SEC-filed selectors (email ebrik10@gmail.com + cell 052-3817124) both resolve to the name via Dehashed. Single-source (Covve), medium confidence; TASE ruled out as confirmation path (SciSparc delisted from TASE 2018); confirm via SEC-side signed exhibit / comment letters or ₪11 registry nesach.

### Genuine secondary stories (Job 3)
- **HFIA structural inversion (#13730, meta).** Section-16 signal captures HFT market makers (Hudson River Trading, Jane Street) + megabank note vehicles that cross 10%, while real predatory financiers hide at a 9.99% conversion cap (L.I.A. Pure Capital), and ~285 offshore never-filers have no Item-405 backstop (no Form 20-F equivalent). Unreported regulatory story.
- **Compliance-gap universe (F).** 20/20 verified top never-filers are genuine (FPI-confirmed, zero Forms 3/4/5). Four (AKANDA, Top Wealth, Bluemount, Optimi) asserted the removed exemption in POST-Act filings. 75% of top-20 share filing agents 0001213900 / 0001493152 — same as the Weiss/Pure Capital cluster.
- **AXIA = Eletrobras / BTG (B).** BTG/Radar Gestora asset-manager director churning ~$230M of the issuer's stock — related-party governance conflict.
- **SCHMID Group (B).** Book-insolvent de-SPAC (neg equity -€60.4M) diluting via debt-for-equity set-offs + serial resale shelves.
- **Sean Shao gatekeeper conflict (D).** Chaired Luckin's audit committee during the SEC-found $180M fraud window; now audit chair at VNET + FCPA-sanctioned UTStarcom.
- **Greek shipping super-voting (C).** Vafias 400M votes via Imperial Series B; Panagiotidis Pelagos Series B across Castor/Toro/Robin — control-for-par, newly legible.
- **BBB Foods (E).** Four insiders sold $26.4M in a disclosed secondary front-running an Aug-2026 Class C unlock — cleanest HFIA-newly-visible example.

### Killed / deflated (discipline)
- **HRT "17-issuer network" — FALSE POSITIVE**: Hudson River Trading market-making inventory, not financing.
- **Most top-convergence names**: fund churn, 10b5-1, external sellers, de-SPAC mechanics; Nomura/MUFG/Mizuho = noise.
- **hot_form4**: debt-shelf false positives, broker nominees, insider buys; no undisclosed dumping outside BBB.
- **Jimmy Lai**: clean; disambiguated from the HK media figure.
- **E.D.B. repeat-player**: refuted for the two TASE valuations checked (Shor, Endymed = different CPAs, #13729).

## Meta-finding
The naive cluster/convergence rankings are dominated by false positives (market makers, debt shelves, broker nominees, de-SPAC dilution, fund churn). The raw HFIA signal needs heavy filtering; "benign, explained" verdicts are as valuable as anomalies. No second Weiss hides in the top clusters.

## Consolidated proposed leads (this wave; dedupe against SYNTHESIS.md before enqueue)
High: (1) confirm Brik + his credential (SEC exhibit / registry nesach); (2) counsel review of the two Section 16 gap claims; (3) Israeli primary docs for the AutoMax probe; (4) HFIA market-maker over-inclusion + 9.99%-cap evasion pattern; (5) identify filing agents 0001213900 / 0001493152 and whether they advised on HFIA duties.
Medium: (6) Pure Capital/Silberman fund complex + base-rate; (7) AXIA/Eletrobras BTG fund map; (8) SCHMID set-off counterparties; (9) Shao's full ADR portfolio; (10) AMTD $1.3B intra-group receivable + Choi SFC status; (11) never-filer verification F-ranks 21–60; (12) active-ATM overlap.
Low: (13) BBB Class C unlock; (14) CRML/Zhernov 10b5-1; (15) Clearmind 20-F re-pull for #8893.

## Overlap / conflict with the parallel SYNTHESIS.md
- **Shared:** universe DB, Weiss verification (#13364–13437), Pure Capital thread, never-filer/compliance-gap theme.
- **Unique to this wave:** HRT false-positive kill + inversion meta (#13730), AXIA/Eletrobras, SCHMID, Sean Shao/Luckin, Greek shipping super-voting, AMTD group, BBB Foods, 20/20 never-filer verification, Brik ID (#13589), TASE contradiction (#13728/#13729).
- **Unique to SYNTHESIS.md:** Polyrizon as cohort's 7th board, SEALSQ/QTREX/SOPHiA timing flags, Form 144 shadow-exhibit sweep, Telkom/Electra compliance stats, VEON/Kyivstar, infra #158.
- **Reconcile:** SYNTHESIS.md says Pure Capital is documented at **seven** issuers; this session's Agent A said **six** — the 7th is likely Polyrizon/Nexentis from the parallel cohort-extension. Verify and adopt the higher count if confirmed.

## Findings this session
82 (Job 3 wave A–F) + Weiss-verification 39 + #13589 (Brik), #13728 (contradiction), #13729 (repeat-player refutation), #13730 (inversion meta). All hfia. Reports: report-job3-{A,B,C,D,E,F}.md, report-tase-edb.md (in workdir; copy into this dir if retaining).
