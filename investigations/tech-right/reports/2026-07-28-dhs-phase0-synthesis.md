# DHS Procurement Phase-0 Synthesis — census × coverage cross-reference

**Date:** 2026-07-28 · **Orchestrator:** claude-fable-5 · **Status:** recommendation to user (GO), no DB writes yet
**Inputs:** `2026-07-28-dhs-census/` (Claude census agent — 83,240 transactions, 16,722 awards ≥$250K, $76.60B window, screens S1-S6) and `2026-07-28-dhs-coverage-map/` (Codex gpt-5.6-sol coverage agent — 67-article catalog, per-cluster boundaries, systematic negative ledger). Working data: `/tmp/osint-GWLtvuxV/` incl. `census.db` (full universe, 124M, NOT copied into repo).

## Go/no-go verdict: GO

Phase-0 criterion was ≥3 publication-candidate anomalies unclaimed by press, or one structural statistic strong enough to anchor a story. Result: **at least five unclaimed or materially-unclaimed candidates, plus the structural statistic**, and the coverage map's own cross-cluster assessment independently concludes the unclaimed territory is "the portfolio layer" — exactly what the census now holds.

## Cross-referenced disposition of census anomalies

| Census anomaly (rank) | Coverage verdict | Disposition |
|---|---|---|
| UAC SVI 18 offers → 18 awards; $20.58B ceiling vs $86.8M obligated; full vendor table (#9) | PARTIALLY REPORTED — Project Salt Box 2026-06-23 has 18 companies/$20B+ and Savvy Professor; Guardian 2026-05-02 has "18 firms offered" re: interim MVM. **Nobody has the everyone-won competition result, the PIID enumeration, the exact reconciliation, or Compass United** | **PURSUE — flagship.** Needs source-selection/J&A records before printing "nominal competition" (gaps.md caution) |
| Compass United $1.568B SVI ceiling; BCFS/Compass-Connections lineage question | **NOT FOUND anywhere** (exact negative ledger in gaps.md; AP 2026-07-06 names Compass *Connections* on an unrelated Alexandria facility) | **PURSUE.** TX registry lineage trace; links to Senate Finance 2026-06-03 Compass Connections letter |
| ISAP V: ~$86.4M sole-source skip-tracing insert + Amendment 2 ceiling deletion; 51→14 offers; program dormancy since 2026-05-14 (wave-3) | Skip-tracing *program* saturated (Intercept/WIRED/404/Scripps/WaPo Jan 2026) — **these specific facts NOT FOUND** | **PURSUE.** Strong because the saturated program gives ready context; our facts are the missing procurement layer |
| FPDS workflow-field forensics (method, not the JABYAD7012 claim) | **NOT FOUND — the method itself is unused in press** | **PURSUE as cross-cutting method, with a hard caveat: wave 3 already REVERSED the JABYAD7012 "separation-of-duties failure" — single-user create-and-approve is the office norm at 70CDCR (37-49%; 42.5% pre-program). The dead claim must not be resurrected.** What survives: run the same baseline-first analysis at OTHER offices/components (census.db has the fields), and only flag offices that deviate from their own base rate |
| Urgency authority carries $29.2B = 38% of all window dollars (#3); wall family-1 11 offers → 11 awards, blank solicitation id (#2); Fisher obligations 2.54× recorded ceiling (#1); order F00000017 50× growth (#12) | WaPo 2026-06-05 owns wall *concentration + political ties* ($19.4B/6mo, Fisher $7.8B, Barnard $4.5B). Axios 2026-06-03 has ">$9B less-than-fully-competed" (a different, smaller measure). **Competition-design facts, records-integrity failure, and the 38% statistic unclaimed** | **PURSUE — the structural statistic + records-integrity angle.** Distinct from (and additive to) WaPo's framing |
| TSA SPP coordinated ceiling raises to identical $3.3B each (6.6-16.5×) (#6); TSA guard MAIDIQ 21/21 everyone-won, $5.3B shared ceiling (#8) | **Nothing found in any cluster** | **PURSUE.** Screening-privatization capacity story; corroborate offer counts from solicitation records first |
| CBP design-build family 70B01C26R00000007: $100B recorded ceiling capacity (#7) | Not covered | **WATCH** (full-and-open, 22→10; anomaly is scale not process). Track first task orders |
| Daedalus Aviation: 2024 DE corp, zero history, sole-source urgency aircraft purchase via OSAD, $463.6M = 100% of ceiling (#4) | PARTIALLY — WaPo 2025-12-17 mentions "~$140M aircraft arrangement involving Daedalus" inside the Salus story | **ENRICH.** Growth $140M→$463.6M, OSAD channel, zero-history profile appear fresh; registry + FAA trace |
| Salus Worldwide CSRO order 18.2× growth to $697.7M; "E.O. Section 4(a)" justification (#5) | CLAIMED — WaPo 2025-12-17 (three-day handpicked competition, Walters emails), Axios 2026-06-03 ($915M), NBC 2026-03-19 (alleged Lewandowski-linked pressure), Bloomberg Law 2026-05-12 (CSI standing), NOTUS 2026-04-02 (Walters five-company probe) | **ENRICH only.** Mod-ledger detail feeds oversight narrative; do not lead with it |
| Safe America Media: DE LLC formed 17 days post-inauguration, $142.8M obligated ad campaign (#5b) | CLAIMED — AP 2025-03-10 named it day one; ProPublica 2025-11-14 ($143M + hidden sub Strategy Group/Ben Yoho) | **DROP as story; KEEP as roster node** for network joins (Strategy Group, People Who Think, Lewandowski/Landry circle) |
| Fisher single-vendor 18.6% of all DHS dollars (#13) | CLAIMED (WaPo concentration) | Reframe to unclaimed slices: ceiling-integrity (#1), per-mile normalization (untouched per coverage boundary), workflow fields |
| Detention letter-contract churn ±8× (#10); CSI expansion (#11) | Letter contracts covered as phenomenon (AP 2025-06-16); CSI saturated (POGO) | ENRICH geo-group threads; per-instrument definitization forensics unclaimed |

## What the coverage sweep adds to the census (new work items)

1. **S7 near-threshold screen (new).** Press established Noem's personal approval gate >$100K (NYT 2025-08-21) and Axios/POGO found eleven $99,999.xx awards (2025-11-21). Gap list #11: nobody tested the full transaction universe. We hold it in census.db — run split-purchase/threshold-clustering detection (by office, vendor, month; sequential same-vendor actions summing over the gate).
2. **Warehouse cross-check.** WSJ July 2026 (via secondary AOL/NYPost summary) reports the OIG probe covers ~$1B in "warehouse-related awards" possibly tied to Lewandowski involvement — grep census for warehouse/storage PSC+descriptions to identify the award set before the WSJ story is even pulled.
3. **Oversight-letter harvest** (URLs in gaps.md §Oversight letters): Garcia 2025-09-05 (278e demand), Welch 2025-11-19 (ad campaign OIG), joint House/Senate OIG letter Mar 2026, Blumenthal/Welch 2026-03-26 (Stackhouse memorandum reference), Senate Finance ORR + Compass Connections letters (May/Jun 2026). Letters often append primary documents.
4. **GAO primary docs to ingest:** GAO-26-108886 (Fort Bliss acquisition planning, $11.5M avoidable costs) and GAO-26-108118 (DHS dissolved its acquisition-oversight office Oct 2025, partially reconstituted May 2026 — the guardrails-removed thesis, documented by GAO).
5. **Roster additions for the network join:** William Walters (five companies per NOTUS probe, $10K American Resolve donation), Strategy Group / Ben Yoho (ProPublica), Jay Connaughton + Mike McElwain / People Who Think (AP), Lewandowski Strategic Advisors ($265.5K from American Resolve per CREW 2026-01-16), Nathan Albers / Disaster Management Group (ProPublica), Kenneth Venturella (WaPo detention-standards story; already in geo-group orbit).
6. **DOJ typology seeds:** Zephyr Aviation FCA settlement ($3.9M, inflated CBP charter hours — directly relevant to removal-aviation pricing checks) and Praetorian Shield ($221K, set-aside fraud + kickbacks).
7. **Claim-discipline warnings from press record:** "18 firms offered" (Guardian) refers to the interim MVM justification, NOT the final competition — corroborate our 18/18 from solicitation records, not award stamps (census caveat agrees). Offer counts are self-stamped per award record.

## Consolidated needs-user list

- **Profile decision:** stand up `dhs-procurement` profile (threads must avoid 9-14) vs continue under tech-right thread 7 + geo-group. Orchestrator recommendation: new profile, cross-linking existing findings (#14378-97, geo-group) rather than re-deriving.
- **DB writes authorization:** mint leads for the PURSUE rows + findings for the census canonical revalidation + source_reliability note (USASpending bulk-file column-swap bug).
- **SAM.gov API tier:** basic key = 10 req/day; J&A harvest for the flagged solicitations needs the 1K/day role or a drip schedule.
- **Manual registry lookups (CAPTCHA-gated DE/VA; OpenCorporates dead):** Daedalus Aviation Corporation (DE), Savvy Professor LLC (VA), Safe America Media LLC (DE), Salus Worldwide Solutions Corp (WY — scriptable, agent can try), Compass United (TX — scriptable), SLS Federal Services vs SLSCO lineage (TX).
- **Paywalled must-reads:** WSJ July 2026 OIG-findings piece (primary for the probe), Bloomberg 2026-03-06 ad-blitz investigation, NYT 2025-08-21 ($100K gate) and 2025-10-18 (jets), NBC 2026-03-19 (alleged payment requests), Bloomberg Law 2026-05-12, three Intercept pages (verified only via syndication).
- **HigherGov quota:** whether to spend it on vehicle/teaming data for Daedalus/Salus/UAC cohort.
- **Editorial decision:** treat Project Salt Box as press or specialist newsletter — changes the novelty framing of the SVI story.

## Method notes (for repeatability)

- Codex headless pattern worked as documented in memory (network flag required; GDELT rate-limited mid-run and was correctly excluded from negative evidence; Google News RSS + direct fetches carried the sweep).
- USASpending bulk download caps date ranges at 1 year — split window into two jobs. Bulk-file column-swap bug (`extent_competed` code/label pair reversed, same for `solicitation_procedures`) must be normalized on every future pull.
- Census validated wave-3 canonical numbers to the cent from an independent pull — cite as corroboration when findings are minted.
- Negative result worth keeping: DHS-wide one-bid rate is 24-27% of known-offer dollars; the GEO-cohort ~25% rate is typical, NOT anomalous. Kills any "GEO uniquely uncompeted" framing.
