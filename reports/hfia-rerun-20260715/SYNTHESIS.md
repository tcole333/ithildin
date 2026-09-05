# HFIA Rerun — Synthesis (2026-07-15)

Full rebuild of the March 29-30 HFIA analysis (which covered only the first 12 days of the
Holding Foreign Insiders Accountable Act's filing regime) with a 4-month refresh, a
publication-grade verification pass, and a 3-agent forensics wave. Executed entirely with
explicit `--profile hfia` overrides; the active investigation profile was never touched.
Codex (gpt-5.6-sol) built the universe; Claude agents did verification, screening,
compliance analysis, and cohort extension.

## Durable assets

| Asset | Location |
|---|---|
| Post-Act Section 16 universe (1,389 likely-FPI issuers, 11,718 filings, 9,515 transactions, 241 clusters) | `datasets/hfia_universe.db` (regenerable: `build_hfia_universe.py` in this dir) |
| Universe methodology + top-20 clusters + escalation screen | `report-universe.md` |
| Weiss cluster verification (14 findings re-verified, story-grade claim inventory) | `report-weiss-verification.md` |
| Cluster triage + Tier 0 screen + insider-timing forensics | `report-cluster-screen.md` |
| First-season compliance-gap analysis + story stat sheet | `report-compliance-gap.md` |
| Cohort extension (bridge map, Polyrizon, agent-prefix scan) | `report-cohort-extension.md` |
| Analytics CSVs (clusters, sync batches, late/never filers, Form-4-near-financing) | this dir |

DB deltas: **78 new findings** (#13364-13437, #13529-13585), **13 audited corrections**
(incl. #8882/#8885/#8887/#8888), ~14 entities created/updated (E.D.B. #5324, L.I.A. Pure
Capital #5344, Capitalink #5349, QTREX #5461, Polyrizon web #5488-5495), 11 auto-leads
(#70352-70363), infra request #158 (20-F screening support).

## Story 1 — The Weiss/SciSparc/AutoMax arc (lead story, publication-grade)

One financier chaired both sides of a Nasdaq merger — with no fairness opinion, a $12,935
one-person valuation shop with a Gmail contact and no named author standing in for one,
a $150K closing bonus, and a counterparty whose management the F-4 itself disclosed as
criminally indicted — and the target then collapsed amid an Israeli police/ISA
investigation with arrests, costing SciSparc a $5.97M write-off. Around it: an 8-board
cluster (chairman of 6) with a traveling six-person cohort, one financier (L.I.A. Pure
Capital / Kfir Silberman) now documented at **seven** issuers with identical discounted
convertible programs, and a four-exit disengagement in the five weeks after the Act made
Weiss's positions visible.

- Claim-by-claim inventory with rebuttals: `report-weiss-verification.md` §6.
- Novelty: zero journalism in any language on the synthesis; only PR-wire/aggregator echoes
  of individual events; Calcalist (Hebrew) owns the AutoMax criminal probe alone.
- **Pre-print blockers**: (1) securities-counsel review of the two Section 16 gap claims
  (#13413/#13414/#13416); (2) E.D.B. principal identity — ₪11 Israeli registry extract for
  co. 514752195 (human action: payment) or AutoMax's Aug 2025 TASE meeting materials
  (free path); (3) Israeli primary documents for the 2025 probe (currently
  Calcalist-attributed).

## Story 2 — The first season of forced disclosure (data story)

The quotable, caveated stat sheet is `report-compliance-gap.md` §6. Headlines: 56.6% of all
initial insider reports hit EDGAR on one day; ~450 insiders were genuinely a month-plus
late (median 43 days); 72 issuers raised or registered money post-deadline with zero
insider filings; Telkom Indonesia's entire board (17/17) filed five weeks late; One & one's
own 20-F concedes the duty while nobody filed; Top Wealth asserts non-obligation with no
stated basis. Critical calibration: ~38% of zero-filers are Canadian and at least one
(Electra) claims a home-country-regime exemption whose mechanics appear nowhere in the
SEC's own FAQ — resolving that exemption's legal machinery (NDAA FY2026 §8103 text + any
SEC exemptive action) is the blocking lead for any published rate.

## Story 3 — What the new visibility caught in real time (timing flags)

All correlation-only pending 10b5-1 footnote reads (`report-cluster-screen.md` §4):
- **Polyrizon** (the cohort's newly confirmed 7th board, fully cluster-wired — SciSparc
  license warrants assigned to Pure Capital/Capitalink, would-be 50.3% holder): CEO, CTO,
  chairman Adler, and Carmel sold at $10.90-12.36 on Mar 30-31, then the company priced a
  $9.00 raise 8-9 days later.
- **SEALSQ**: CFO's near-daily selling program ($557K) began one day after HFIA effect,
  two days after a 424B5; none of it reportable pre-Act.
- **QTREX** (screen score 10/10): CFO+CTO sold ~$399K 3-8 days before a new shelf.
- **SOPHiA Genetics**: founder sold ~$1.06M within weeks of two June supplements during
  his CEO transition.
- The pre-Act shadow exhibit: Weiss's Dec 2024 ParaZero **Form 144** ($127,786 sale) —
  visible only as a broker notice because Section 16 didn't yet reach FPI insiders (#13569).

## Corrections to the March analysis (why reruns matter)

| Was | Is |
|---|---|
| "9 simultaneous boards, chairman of 5" | 8 unique US-listed issuers (Save Foods/N2OFF double-counted), chairman of 6 |
| "CHEV uplisted to Nasdaq Dec 2025" | Uplisting never completed; OTC, $25K cash |
| Viewbix comp "share grant" | Cash fees per the 10-K comp table |
| "No independent fairness opinion" (bare) | True, plus the E.D.B. valuation-in-lieu context, recusal, and $150K contingent bonus |
| "Three F-3 shelfs in 48h may indicate coordination" | Three *resale registrations for the same investor* (Pure Capital; + Capitalink) in 3 days |

## Consolidated next actions (deduped across all proposed-leads sections)

1. **[HUMAN]** ₪11 registry extract for E.D.B. (co. 514752195) — or pull AutoMax Aug 2025
   TASE meeting materials (free) — to name the valuation author.
2. **[COUNSEL]** Section 16 gap claims + the Polyrizon sell-before-raise MNPI question.
3. Resolve the HFIA exemption machinery (statute text + SEC exemptive rules/orders) —
   recalibrates every compliance stat.
4. Israeli primary documents: ISA/police probe, 2025-10-21 court freeze, trustee filings.
5. Form 144 sweep across the cohort's owner CIKs (cheap, high yield — reconstructs
   pre-HFIA FPI selling the way #13569 did for Weiss).
6. SciSparc-side accounting of the 12/30/24 Polyrizon warrant assignment to Pure
   Capital/Capitalink (what consideration?).
7. Eli Zamir / Pure Capital paired 159,235-share stakes at Polyrizon — origin and
   pre-Act exit path.
8. FY2026 20-F season recheck of the bounded-negative zero-filer findings (~Aug 1).
9. VEON/Kyivstar shared 2026-05-29 trigger event (incl. director Michael Pompeo Form 3).

## Platform notes

- The concurrent-profile override pattern (explicit `--profile`, no skills, no
  `investigation_context.py set`, leads via `auto_leads run --profile`) worked end-to-end
  while another session ran `epstein-gates-ipi` concurrently.
- `codex exec` needs `-c 'sandbox_workspace_write.network_access=true'` for fetch jobs
  (memory updated).
- Tier 0 screening can't read 20-F filers — infra request #158 filed with the companyfacts
  fallback as reference implementation.
- `findings_tracker.py verify` is blocked on pre-migration rows by comma-string
  `source_datasets` — cleanup running as separate session (task chip task_c87ab263).
