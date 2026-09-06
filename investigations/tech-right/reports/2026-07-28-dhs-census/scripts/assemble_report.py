#!/usr/bin/env python3
"""Assemble census-report.md (the orchestrator-facing deliverable) from pipeline artifacts."""
import csv
import json
import sqlite3
from decimal import Decimal

WORK = "/tmp/osint-GWLtvuxV/work-census"
csv.field_size_limit(50_000_000)

recon = json.load(open(f"{WORK}/recon.json"))
screens = json.load(open(f"{WORK}/screens-summary.json"))
canon = json.load(open(f"{WORK}/canonical-validation.json"))
con = sqlite3.connect(f"{WORK}/census.db")


def fmt(x):
    return f"${float(x):,.0f}"


L = []
add = L.append

add("# DHS Procurement Census — Phase 0 (window 2025-01-20 .. 2026-07-28)")
add("")
add(f"Census agent output, 2026-07-28. All artifacts in `{WORK}/`. No database writes were made; investigation.db untouched.")
add("")
add("Confidence labels: **CONFIRMED** = recomputed from cached primary bulk data held in this work dir; "
    "**UNCONFIRMED** = single API read or interpretation not re-verified against a second source.")
add("")

# ---------------- method ----------------
add("## 1. Method and reconciliation")
add("")
add("### API calls used (probe-first log)")
add("- `POST https://api.usaspending.gov/api/v2/bulk_download/awards/` — filters: `prime_award_types` = A,B,C,D + IDV_A,IDV_B,IDV_B_A,IDV_B_B,IDV_B_C,IDV_C,IDV_D,IDV_E; `agencies` = awarding/toptier/'Department of Homeland Security'; `date_type=action_date`. **API limit discovered: date_range must be within 1 year** (HTTP 400 otherwise), so the window ran as two jobs: 2025-01-20..2026-01-19 (57,542 rows) and 2026-01-20..2026-07-28 (25,698 rows).")
add("- `GET https://api.usaspending.gov/api/v2/download/status?file_name=...` — polled ~30-60s, sequential.")
add("- Two hedge jobs (window-1 split into 6-month halves) were submitted when the 12-month job passed ~20 min generation, per fallback policy; the 12-month job finished first, so the hedge zips were **never downloaded** and are unused.")
add("- Enrichment (S4/S5): `POST /api/v2/search/spending_by_transaction/` sequential with 0.4s spacing and exponential backoff; local `datasets/sam.db` (read-only) for registration dates.")
add("- The paged `spending_by_transaction` fallback was NOT used for the census itself: that endpoint does not expose competition fields, ceilings, or cumulative columns, and would have produced a materially degraded census.")
add("")
add("### Verified column semantics (probe file, CONFIRMED empirically)")
add("- `federal_action_obligation` and `base_and_all_options_value` are **per-action deltas**.")
add("- `total_dollars_obligated` and `potential_total_value_of_award` are **cumulative as of that action** (termination example: delta -39,600 -> cumulative 0). This allows full ceiling-ledger reconstruction including pre-window baselines.")
add("- **Bulk-file column swap bug**: `extent_competed_code` holds the *label* and `extent_competed` holds the one-letter code; same swap for the `solicitation_procedures` pair. Set-aside and other-than-full-and-open pairs are normal. Normalized at load with a length heuristic (`build_census.py:normalize_pair`).")
add("- AWARD and IDV rows arrive in one CSV, discriminated by `award_or_idv_flag`.")
add("")
add("### Pipeline reconciliation (CONFIRMED)")
add("| stage | count |")
add("|---|---|")
for f in recon["files"]:
    add(f"| logical rows in {f['file']} (csv module, not wc -l) | {f['logical_rows']:,} |")
add(f"| transactions loaded (dedupe on contract_transaction_unique_key) | {recon['inserted']:,} |")
add(f"| duplicate transactions across window boundary | {recon['dupes_across_windows']} |")
add(f"| distinct awards touched in window | {recon['awards_total']:,} |")
add(f"| awards passing keep rule (window obligations >= $250K OR current ceiling >= $250K) | {recon['awards_kept_250k']:,} |")
add(f"| awards dropped under threshold | {recon['awards_dropped_under_250k']:,} |")
add(f"| mod-ledger rows for kept awards (census-transactions.csv) | {recon['ledger_rows_kept_awards']:,} |")
add("")
add(f"Window net obligations, full universe: **{fmt(recon['window_obligations_total_full_universe'])}**; "
    f"kept awards cover {fmt(recon['window_obligations_total_kept'])} (99.0%).")
add("")
add("### Sanity check against expected magnitude (CONFIRMED)")
add("DHS historical contract spend is ~$25-35B/yr; this window annualizes to ~$50.5B/yr. The excess is fully attributable to identified mega-programs, dominated by CBP border-barrier construction task orders of $0.5-2.6B each (Fisher Sand & Gravel, Barnard, BCCG JV, Southwest Valley, SLS, Spencer, Cochrane, AMI Metals bulk steel) plus USCG Arctic cutter letter contracts (Bollinger, Rauma, Davie). Not a data artifact.")
add("")
add("### Totals by component (CONFIRMED, full universe)")
add("| component | actions | window net obligations |")
add("|---|---:|---:|")
for c in recon["by_component_full_universe"]:
    add(f"| {c['component']} | {c['actions']:,} | {fmt(c['window_obligations'])} |")
add("")
add("### Canonical-numbers validation (CONFIRMED — exact reproduction)")
add("Method law applied: obligations summed from child task orders, never read off the parent IDV; ceilings reported as ceilings.")
add("")
add("| target (wave-3 brief) | expected | census reproduces |")
add("|---|---|---|")
add("| Skip tracing 26-SOL-DCR-01 IDIQ count | 14 | **14** (PIIDs 70CDCR26D00000003..21 subset) |")
add("| Skip tracing combined ceiling | $1,442,909,640 | **$1,442,909,640.02** |")
add("| Skip tracing obligations via child DOs | $19,032,607 | **$19,032,607.00** (14 child orders) |")
add("| UAC 70CDCR26R00000015 IDIQ count | 18 (D00000030-47) | **18, exact PIID match** |")
add("| UAC combined ceiling | ~$20,583,928,204 | **$20,583,928,204.05** |")
add("| UAC strict new-family obligations | $85,376,317 | **$85,376,317.14** (18 child orders) |")
add("| UAC initiative incl. MVM FR0000052 (FY24 vehicle 70CDCR24D00000002) | $86,822,317 | **$86,822,317.14** ($1,446,000.00 MVM) |")
add("")

# ---------------- S1 ----------------
add("## 2. S1 — Competition base rates (closes the wave-3 denominator gap)")
add("")
add("Transaction-dollar-weighted, full universe (83,240 actions, $76.6B). Bucketing: competed = A/D/F/CDO; not-competed = B/C/G/E/NDO (FPDS convention; E=follow-on counted not-competed).")
add("")
b = screens["s1_dhs_baseline"]


def bshare(key):
    v = b.get(key)
    return f"{v['actions']:,} actions ({v['action_share']:.1%}), {fmt(v['dollars'])} ({v['dollar_share']:.1%})" if v else "n/a"


add(f"- **DHS-wide baseline (CONFIRMED)**: competed {bshare('competed')}; not-competed {bshare('not_competed')}.")
add("- Per-component and per-month tables: `s1-competition-by-component.csv`, `s1-competition-by-month.csv`. Monthly not-competed dollar share ranges 2.9%-27.6%; peak months: Oct 2025 (27.6%), Dec 2025 (22.5%, wall + Arctic cutter letter contracts), Jul 2026 (20.1%). June 2025 shows net negative not-competed dollars (-$132M) = deobligation wave.")
add("")
add("### One-bid base rate (award level, CONFIRMED)")
add("- Born-in-window awards: $50.28B window obligations; offers known for $41.06B (81.7%); **one-offer dollars $10.97B = 21.8% of all / 26.7% of known**. Offers-missing dollars 18.3%.")
add("- All census-universe awards: one-offer = 19.8% of all / 24.4% of known-offer dollars.")
add("- Implication for wave-3: the GEO-cohort ~25% full-and-open/one-offer rate is **typical of DHS-wide dollars, not an outlier**.")
add("")
add("### Other-than-full-and-open authorities (award level, window dollars; CONFIRMED)")
add("| authority | awards | window dollars |")
add("|---|---:|---:|")
for a in screens["s1_otfo_top"]:
    add(f"| {a['authority']} | {a['awards']:,} | {fmt(a['window_dollars'])} |")
add("")
add("**Headline**: FAR 6.302-2 URGENCY stamps sit on 138 awards carrying **$29.2B window obligations (38% of all DHS window dollars)** — dominated by CBP border-barrier task orders (extent code D, 'full and open after exclusion of sources', negotiated). Urgency-as-default for a multi-year construction program is the single biggest structural competition fact in the census.")
add("")

# ---------------- S2 ----------------
add("## 3. S2 — 100%-win multiple-award families")
add("")
add(f"{screens['s2_families_multi_awardee']} multi-awardee solicitation families; **{screens['s2_everyone_won']} families where modal offers == distinct awardees** (everyone who offered won). Full list: `s2-families.csv`. Top by exposure:")
add("")
add("| solicitation | awardees | offers | family ceilings | child-order window obligations | component | note |")
add("|---|---:|---:|---:|---:|---|---|")
rows = list(csv.DictReader(open(f"{WORK}/s2-families.csv")))
for r in rows:
    if r["everyone_who_offered_won"] != "1":
        continue
    ceil_note = f"shared ~{fmt(r['shared_or_max_ceiling'])}" if r["shared_ceiling_suspected"] == "1" else f"sum {fmt(r['family_ceiling_sum'])} (max member {fmt(r['shared_or_max_ceiling'])})"
    add(f"| {r['solicitation_id']} | {r['n_distinct_awardees']} | {r['modal_offers_received']} | {ceil_note} | {fmt(r['child_task_order_window_obligations'])} | {r['components'][:40]} | {r['sample_recipients'][:60]} |")
add("")
add("Key families:")
add("- **TSA 70T05025R5900N002 (UNCONFIRMED interpretation, CONFIRMED records)**: 21 offers -> 21 IDIQs awarded 2026-05-28, aviation guard services; every IDIQ stamps an identical $5,300,000,000 ceiling -> read as a ~$5.3B shared program ceiling, NOT $111B. Obligations so far: six $5,000 minimum-guarantee orders ($75K). Structurally identical to the UAC 18/18 pattern but larger headcount, mixing Leidos with small guard firms. Same corroboration caveat as UAC: each record self-stamps 21 offers.")
add("- **ICE UAC 70CDCR26R00000015**: 18/18 reproduced exactly (see canonical block).")
add("- **ICE 70CDCR24R00000012**: CoreCivic + GEO, 2 offers/2 awards, $83.3M child obligations in window — the detention duopoly both winning its own competition.")
add("- **OPO 70RDA224Q00000073**: 5/5 = Deloitte, EY, KPMG, Guidehouse, Kearney financial-audit BPAs — the benign face of everyone-won (professional-services pools). Kearney holds $30.2M of $32.9M ordered.")
add("- **FEMA logistics pairs** (70FB7020R00000002 CEVA/Crowley $1.08B ceilings; 70FB7021R00000004 CEVA/Matson; 70FB7021R00000005 DeWitt/Matson): 2/2 dual-award pools, weak signal individually.")
add("")
add("**S2 method gap (important negative)**: the largest everyone-won family in the census is INVISIBLE to solicitation grouping — the 11-vendor CBP border-barrier IDIQ cohort 70B01C26D00000003-13 (awarded 2025-10-31) carries a **blank solicitation_identifier** in FPDS. Reconstructed by PIID block: 11 offers received -> 11 awards, extent D, URGENCY authority, $5B ceiling each ($56.6B recorded total; SLS later raised to $6.636B), **$25.8B child-order obligations in under 9 months**. Members: SLS, Granite, BCCG JV, Barnard, Southwest Valley, Cochrane, Sundt, Posillico, Coastal Environmental, Fisher, Spencer. (CONFIRMED from ledger.)")
add("- 57 families show MORE awardees than modal offers — dominated by per-order offer stamping semantics (e.g., FEMA manufactured-home lease pools where each lease reports its own 1 offer), a data-semantics caveat, not a fraud signal (list in s2-families.csv `awardees_exceed_offers`).")
add("")

# ---------------- S3 ----------------
add("## 4. S3 — Ceiling forensics from the mod ledger")
add("")
fc = screens["s3_flag_counts"]
add(f"Flags: {fc}. Full list: `s3-ceiling-flags.csv` (ceiling deltas derivable per-mod in census-transactions.csv: ceiling_before/after columns).")
add("")
add("Top exemplars (CONFIRMED from ledger; interpretations UNCONFIRMED):")
add("- **Obligations exceed recorded ceiling — Fisher Sand & Gravel IDIQ 70B01C26D00000012**: child task orders total **$12,675,318,052 against a parent ceiling still recorded at $5,000,000,000 (2.54x)**. The IDV record was re-stamped $5B as late as 2026-03-15 while orders blew past it. Either FPDS ceiling maintenance failed or vehicle capacity was informally overridden. Barnard's sibling sits at 0.91 of ceiling; SLS at 0.36 after its raise to $6.636B. Single most acute record-integrity anomaly in the census.")
add("- **TSA Screening Partnership Program coordinated raises**: HSTS0516DSPP906-913 (Covenant Aviation, Firstline, Jackson Hole Airport Board, PAE NSS, Technica, Trinity, VMD +) all raised in-window from $200-500M to an **identical $3.3B ceiling each** — a 6.6-16.5x jump across the entire privatized-screening vendor pool. Capacity for a major screening-privatization expansion, described as capacity: obligations flow later via orders.")
add("- **Fisher order 70B01C26F00000017**: started 2025-11 at $55.8M ceiling, now **$2.83B obligated == ceiling (50x growth)** via 'ADDED CONSTRUCTION WORK' mods; sibling 70B01C25F00001112 went $574M -> $1.23B.")
add("- **Salus Worldwide Solutions Corp 70RDA225FR0000018 (OPO, parent 70RDA225D00000005)**: 'Comprehensive Support to Removal Operations (CSRO)' citing **'E.O. Section 4(a)' in the description**; NAICS 481211 / PSC V119 (charter air). Born 2025-05-22 at $30M obligated / $38.9M ceiling; 23 mods later: **$697.7M obligated / $706.6M ceiling (18.2x)** by 2026-05-22. Same buy-inside-a-vehicle-then-grow shape wave-3 documented on skip tracing, at 8x the dollars.")
add("- **CSI Aviation 70CDCR25FR0000022 (ICE Air)**: $119.8M -> $585.5M ceiling (4.9x); CSI window obligations total $1.394B.")
add("- **Detention letter-contract churn**: GEO 70CDCR25D00000009 (North Lake, the wave-3 letter contract) x6.0 to $223.1M; CoreCivic 70CDCR25D00000010 x8.4 to $262.0M and 70CDCR25D00000008 x8.0 to $181.1M; GEO 70CDCR25D00000007 ceiling **cut -$421.9M** (2025-11-13) to $788.7M. Undefinitized instruments repricing massively in both directions.")
add("- **Big cuts**: Mythics (OPO Oracle reseller BPA) -$620M; Eastern Shipbuilding OPC -$370.9M; PAE/USCIS -$362.1M; Huntington Ingalls -$241.7M; Leidos TSA -$32.5M.")
add("- **Capacity parking (ceiling >= $50M, <=5% obligated, vehicle >= 180 days old)**: 523 awards. Top of list is a *legacy-stamp noise class* — 2013-era EAGLE II IDIQs each carrying a $22B shared-ceiling stamp with $0 window obligations (admin closeout actions only): treat as stale records, not live capacity. Live examples worth attention: skip-tracing family ($1.44B/1.3%), UAC family ($20.58B/0.4%), TSA guard MAIDIQ ($5.3B/<0.1%), CBP design-build family (see below).")
add("- **CBP design-build family 70B01C26R00000007 (awarded 2026-05-11, age-gated out of parking flag)**: 10 IDIQs x **$10B each = $100B recorded ceiling capacity** (BL Harbert, Brasfield & Gorrie, Clark, ECC, Grunley, Hensel Phelps, Southwest Valley, Tutor Perini, Walsh Federal, Whiting-Turner), 22 offers -> 10 awards, full-and-open two-step, minimum guarantees only so far. The largest new capacity block in DHS; watch which vendors receive the first orders.")
add("")

# ---------------- S4 ----------------
add("## 5. S4 — New entrants (bounded enrichment)")
add("")
try:
    s4 = list(csv.DictReader(open(f"{WORK}/s4-new-entrants.csv")))
    flagged = [r for r in s4 if r["flag_new_entrant_post_2024_11_05"] == "1"]
    errs = [r for r in s4 if r["error"]]
    unres = [r for r in s4 if r["unresolved_expansion"] == "True"]
    reg_post = [r for r in s4 if r["sam_registered_post_election"] == "1"]
    add(f"Coverage: {len(s4)} top-slice vendors enriched (window obligations >= $1M or ceiling >= $10M, cap 300); {len(errs)} API errors; {len(unres)} unresolved recipient-expansion cases (UEI text search returned only affiliates within page budget). SAM registration dates from local sam.db extract (snapshot ~2026-02; absence after that is NOT evidence of newness).")
    add("")
    add(f"**{len(flagged)} vendors show no federal contract history before 2024-11-05** (USASpending transaction search, contracts+IDVs since 2007-10-01, client-side UEI match; assistance/grants also checked where zero). UNCONFIRMED beyond USASpending coverage (pre-2008 history invisible, name-change/UEI-reissue possible):")
    add("")
    add("| vendor | UEI | window obligations | ceiling sum | SAM registered | SAM entity start | state |")
    add("|---|---|---:|---:|---|---|---|")
    for r in sorted(flagged, key=lambda x: -float(x["window_obligations"]))[:22]:
        add(f"| {r['recipient_name'][:42]} | {r['recipient_uei']} | {fmt(r['window_obligations'])} | {fmt(r['ceiling_sum'])} | {r['sam_registration_date']} | {r['sam_entity_start_date']} | {r['sam_state_of_incorporation']} |")
    add("")
    if reg_post:
        add(f"{len(reg_post)} top-slice vendors' SAM registrations date after 2024-11-05: " + "; ".join(f"{r['recipient_name'][:36]} ({r['sam_registration_date']})" for r in reg_post[:12]) + ".")
    add("")
    add("Flag interpretations (award context CONFIRMED from census.db; entity readings UNCONFIRMED):")
    add("- **Daedalus Aviation Corporation** (DE, entity start 2024-02-21, SAM 2024-03-20): zero federal history before its OSAD aircraft contract. Sole-source (extent C, 1 offer, sol 70QS0326R00000009), URGENCY, $463.6M fully obligated.")
    add("- **Salus Worldwide Solutions Corp.** (WY, entity start 2023-02-07): zero federal history; then WON its own single-award CSRO IDIQ 70RDA225D00000005 ($915M ceiling, 4 offers, extent D + URGENCY, sol 70RDA225R00000018) and the $697.7M order under it, plus small ICE aviation orders. A 2-year-old Wyoming corp operating removal flights at $700M.")
    add("- **Safe America Media LLC** (DE, entity start 2025-02-06, SAM registered 2025-02-10 — 17 days after inauguration): zero federal history; holds 'NATIONAL EMERGENCY AT THE SOUTHERN BORDER: STRONGER BORDERS' ad-campaign task orders 1 and 4 ($62.8M + $65.0M, URGENCY) under multiple-award media IDIQ 70RDA225D00000004 ($240M ceiling, 3 offers) plus a $15M ICE media-buy order. Total $142.8M obligated / $382.8M ceilings. This is the DHS ad campaign as a procurement object.")
    add("- **Savvy Professor LLC** (VA, entity start 2024-07-17, SAM registered 2026-02-05): zero federal history; holds UAC IDIQ **70CDCR26D00000045 ($1.596B ceiling)** + $4.7M minimum-guarantee order. Concretely corroborates wave-3's thin-record UAC cohort concern, by name.")
    add("- **SLS Federal Services LLC** (TX, entity 2020): $2.38B obligated with zero pre-election federal history under this UEI — plausibly the SLSCO Ltd (Sullivan Land Services, Galveston TX wall incumbent) family under a newer entity/UEI; treat the 'new entrant' read as naming-structure artifact until ownership is traced. Same JV caveat for WSP HDR JV, Collins-Mott MacDonald-STV JV, M&N-Stantec JV, Metro East JV, Barnard Spencer JV (new JV shells of established firms).")
    add("- **Davie Defense Inc.** (DE 2025-04-28) and **Rauma Marine Constructions OY** (SAM 2025-09-10): explainable market entries — ICE-Pact Arctic cutter builders (Canadian/Finnish yards) newly registering US entities.")
    add("- **Severance Security Services LLC** and **Critical Response Strategies, LLC** (UAC family): not present in the local SAM extract at all (snapshot ends ~2026-02) — registration recency cannot be ruled in or out locally; API lookup deferred (10 req/day cap).")
    add("- **Compass United** (TX entity since 2000, SAM 2022): zero federal prime history before the window under this UEI — consistent with wave-3's BCFS/ORR-linked reading; $2.34B ceiling sum, $8.9M obligated.")
    add("")
except FileNotFoundError:
    add("S4 enrichment file missing at assembly time.")
    add("")

# ---------------- S5 ----------------
add("## 6. S5 — NAICS drift (best-effort)")
add("")
try:
    s5 = list(csv.DictReader(open(f"{WORK}/s5-naics-drift.csv")))
    d2 = [r for r in s5 if r["naics_differs_2digit"] == "1"]
    add(f"Coverage: {len(s5)} top-slice vendors with a pre-window transaction NAICS sample (earliest-100 transactions per vendor); {len(d2)} differ from their DHS-window modal NAICS at the 2-digit sector level. Honest limits: modal-of-earliest-sample is a coarse proxy; vendors without pre-window history have no drift measure by construction (they appear in S4 instead).")
    add("")
    add("| vendor | window obligations | DHS NAICS | historical modal | SAM primary | sector change |")
    add("|---|---:|---|---|---|---|")
    for r in d2[:15]:
        add(f"| {r['recipient_name'][:40]} | {fmt(r['window_obligations'])} | {r['dhs_modal_naics']} | {r['historical_modal_naics']} | {r['sam_primary_naics']} | {r['naics_differs_2digit']} |")
    add("")
except FileNotFoundError:
    add("S5 file missing at assembly time.")
    add("")

# ---------------- S6 ----------------
add("## 7. S6 — Concentration")
add("")
add("Top-10 recipients by window obligations (full table incl. top-200: `s6-concentration.csv`; ceilings summed without double-counting task orders under in-census parents):")
add("")
add("| recipient | window obligations | not-competed share (extent-code basis) |")
add("|---|---:|---:|")
for r in screens["s6_top10_by_window_obligations"]:
    add(f"| {r['recipient_name'][:44]} | {fmt(r['window_obligations'])} | {r['not_competed_share']} |")
add("")
add("- **Fisher Sand & Gravel: $14.28B window obligations (18.6% of ALL DHS window dollars)** across 17 awards — the census's single-vendor concentration story. Its orders are coded extent D (competed after exclusion) so its not-competed share reads 0.0; the competition reality is the 11-offer urgency family plus order-level fair opportunity.")
add("- Top-10 by ceiling: " + "; ".join(f"{r['recipient_name'][:30]} {fmt(r['ceiling_sum_no_double_count'])}" for r in screens["s6_top10_by_ceiling"][:5]) + " ...")
add(f"- DHS-wide not-competed dollar share {screens['s6_dhs_notcompeted_dollar_share']:.1%}. Office outliers (>=2x baseline and >=$10M): `s6-office-outliers.csv` — USCG HQ Contract Operations 65.9% ($3.51B; Arctic cutters), USCG Aviation Logistics Center 61.8%, **OPO 'OSAD ACQ OFFICE 3' 100.0% not-competed ($463.6M in 5 actions — all one contract, see below)**, USCG SILC-CON 64.8%, USCG CEU Honolulu 91.9%.")
add("- **Daedalus Aviation Corporation 70QS0326C00005002 (UNCONFIRMED interpretation)**: sole-source, URGENCY, via OSAD (DHS's selective/sensitive-acquisitions office), PSC **1510 = fixed-wing AIRCRAFT purchase**, NAICS 481219, description 'supply commercial aviation in support of the United States Immigration...'. Base 2025-11-21 $139.9M; single action 2026-03-24 +$303.2M; **$463.6M obligated = 100% of ceiling in 4 months**. Buying aircraft for immigration operations through the classified-acquisitions office is structurally unusual on every axis this census measures.")
add("- Removal-aviation build-up across THREE offices (UNCONFIRMED as a coordinated program): CSI Aviation $1.394B (ICE), Salus CSRO $697.7M (OPO), Daedalus $463.6M (OSAD) — combined ~$2.55B in window.")
add("")

# ---------------- top 20 ----------------
add("## 8. Ranked TOP-20 anomalies")
add("")
add("Ranked by dollar exposure x structural oddity relative to S1 base rates. Obligations and ceilings labeled separately throughout.")
add("")
top20 = [
    ("1", "Fisher IDIQ 70B01C26D00000012 obligations 2.54x recorded ceiling", "OBL $12.675B vs CEIL $5.0B (recorded)", "S3+S6", "child orders exceed parent's stamped ceiling; ceiling never raised in FPDS", "pull full FPDS mod history via query_fpds.py REF_IDV_PIID + PIID; locate ceiling-raise mod or J&A; if absent, this is a reportable records-integrity failure on the largest wall vehicle"),
    ("2", "CBP wall family-1: 11 IDIQs, blank solicitation id, 2025-10-31", "OBL $25.8B family child orders; CEIL $56.6B recorded", "S2(manual)+S1", "11 offers -> 11 awards (everyone won) under URGENCY, extent D; invisible to solicitation grouping", "FPDS records for D00000003-13; the urgency J&A(s); SAM.gov solicitation trail (why blank?)"),
    ("3", "URGENCY authority carries 38% of all DHS window dollars", "OBL $29.2B on 138 awards", "S1", "FAR 6.302-2 as the operating mode of a multi-year construction program", "harvest the J&A documents (SAM.gov) for the top urgency awards; test 'unusual and compelling urgency' against multi-year repetition"),
    ("4", "Daedalus Aviation: sole-source aircraft purchase via OSAD by a 2024-formed DE corp with zero federal history", "OBL $463.6M = 100% of CEIL, 4 months", "S6+S1+S4", "extent C, 1 offer (sol 70QS0326R00000009), URGENCY, PSC 1510 fixed-wing aircraft for immigration ops through the sensitive-acquisitions office; entity start 2024-02-21", "corporate registry + FAA aircraft registry trace on UEI KE7ZAT98UBM7; FPDS workflow fields (query_fpds.py); the J&A"),
    ("5", "Salus Worldwide: 2023-formed WY corp with zero federal history wins $915M removal-flights IDIQ; order grows 18.2x", "OBL $697.7M on order 70RDA225FR0000018 / vehicle CEIL $915M", "S3+S4", "E.O.-Section-4(a)-justified CSRO program, URGENCY + extent D, 4 offers; $30M start grown by 23 mods in 12 months", "WY registry + beneficial owners; who were the other 3 offerors; per-flight economics vs CSI Aviation"),
    ("5b", "Safe America Media LLC: DE LLC formed 17 days after inauguration takes the border ad campaign", "OBL $142.8M / CEIL $382.8M", "S4+S1", "'National Emergency at the Southern Border: Stronger Borders' campaign orders under URGENCY, extent D, 3-offer media IDIQ 70RDA225D00000004; zero federal history; entity start 2025-02-06", "DE registry + agency-of-record trace; who are the other 2 IDIQ holders; ad-spend reconciliation vs public reporting"),
    ("6", "TSA SPP coordinated ceiling raises to identical $3.3B", "CEIL $3.3B x ~8 vendors (capacity)", "S3", "entire privatized-screening pool re-ceilinged 6.6-16.5x in coordinated mods", "pull the SPP mods' award notices; check TSA budget justification for screening-privatization expansion"),
    ("7", "CBP design-build family-2: $100B new ceiling capacity", "CEIL $10B x 10 IDIQs; OBL minimum guarantees only", "S3+S2", "created 2026-05-11 full-and-open (22 offers/10 awards); purpose language generic 'CBP projects'", "watch first task orders; obtain the solicitation 70B01C26R00000007 scope docs"),
    ("8", "TSA guard MAIDIQ 21/21 everyone-won", "CEIL ~$5.3B shared; OBL $75K", "S2", "same shape as UAC 18/18 at bigger headcount, weeks after it", "corroborate offer count from solicitation record, not award stamps (same caveat as UAC)"),
    ("9", "UAC 18/18 family (wave-3, revalidated exactly) + Savvy Professor LLC", "CEIL $20.584B; OBL $86.82M; Savvy Professor holds $1.596B of that ceiling", "S2+S3+S4", "reproduced to the cent; capacity 0.4% used; S4 adds: UAC member 'Savvy Professor LLC' (VA 2024, SAM-registered 2026-02-05) has zero prior federal history", "VA registry on Savvy Professor; extend the wave-3 UAC cohort workup with the S4 columns for all 18"),
    ("10", "Detention letter-contract churn (GEO/CoreCivic 70CDCR25D0000000[7-10])", "CEIL swings +8.4x/+6.0x and -$421.9M; OBL flowing", "S3", "undefinitized instruments repricing both directions within months", "definitization records; compare priced vs letter values; link to wave-3 Delaney Hall thread"),
    ("11", "CSI Aviation ICE Air expansion", "OBL $1.394B window; order ceiling x4.9 to $585.5M", "S3+S6", "removal-flight incumbent scaling inside existing order", "flight-ops data cross-check (witness lists ICE Air Ops); per-hour pricing vs Salus/Daedalus"),
    ("12", "Fisher order F00000017 50x order-level growth", "OBL $2.83B == CEIL, from $55.8M start", "S3", "'added construction work' mods converted a $56M order into a $2.8B one", "mod-by-mod scope language; was added work within scope (CICA)?"),
    ("13", "Fisher single-vendor concentration", "OBL $14.28B = 18.6% of DHS window dollars", "S6", "politically connected vendor (Trump-1 wall litigation history) takes largest DHS share", "beneficial-ownership + political-giving join (next pass); GAO/DoD-IG prior findings context"),
    ("14", "Sep-2025 / Dec-2025 / Mar-2026 obligation spikes", "OBL $12.1B / $8.1B / $11.9B months", "S1 timeline", "year-end + wall order waves + Arctic cutters; Oct-Nov 2025 shutdown halves action counts", "none — context row for other screens"),
    ("15", "Arctic cutter sole-sourcing to foreign-linked yards", "OBL Bollinger $1.33B (94.7% nc), Rauma $1.12B (100% nc), Davie $777M definitization", "S6+S1", "ICE-Pact policy-driven; letter contracts definitized at scale", "explainable-but-watch: definitization deltas; Davie letter-contract terms"),
    ("16", "USCG HQ office 65.9% not-competed on $5.33B", "OBL $3.51B not-competed", "S6", "office-level outlier 5x DHS baseline", "decompose: cutters explain most; residual after removing 9321-prefix contracts"),
    ("17", "OPO audit-pool 5/5 (Deloitte/EY/KPMG/Guidehouse/Kearney)", "CEIL ~$100M shared; OBL $32.9M (Kearney $30.2M)", "S2", "benign-class everyone-won; useful as the control case", "none"),
    ("18", "FEMA dual-award logistics pairs (CEVA/Crowley/Matson/DeWitt)", "CEIL $1.08B + $469M + $237M sums", "S2", "2/2 everyone-won x3 solicitations", "low priority; verify offers from solicitations"),
    ("19", "SLS Federal Services: $2.38B obligated, zero pre-election federal history under this UEI, + only family-1 member with a recorded ceiling raise", "OBL $2.38B; CEIL $5.0B -> $6.636B 2026-03-15", "S3+S4", "plausibly the SLSCO/Sullivan wall-incumbent family under a new entity (TX 2020) — naming-structure artifact vs true newcomer needs registry trace; contrast: Fisher's ceiling never raised at 2.54x usage", "TX registry ownership trace; the raise mod's justification"),
    ("20", "57 families where awardees > recorded offers", "n/a", "S2", "offer-stamp semantics break family analysis (per-order stamps)", "data-quality note for all future S2 passes; use solicitation records not award stamps"),
]
add("| # | anomaly | exposure (labeled) | screens | why anomalous vs base rates | next verification step |")
add("|---|---|---|---|---|---|")
for row in top20:
    add("| " + " | ".join(row) + " |")
add("")

add("### Explicit negative results (stated plainly)")
add("")
add("- The DHS-wide one-bid dollar rate (24-27% of known) means one-offer awards are NOT inherently anomalous; wave-3's GEO-cohort rate is typical.")
add("- No everyone-won family beyond those listed reaches $1B exposure; most of the 38 are 2-awardee logistics/parts pools or benign professional-services pools.")
add("- Border-wall vendors show 0.0 'not-competed' shares on the extent-code basis — the S1 headline lives in the urgency-authority field, not the extent field; neither field alone supports a 'no-bid' claim about the wall program (11 offers are recorded).")
add("- Zero duplicate transactions across the two download windows; the boundary split introduced no artifacts.")
add("- Fisher, Barnard, SWVC, Granite, Sundt, Cochrane, AMI Metals and most other wall vendors have long pre-2025 federal histories (S4 negative on them); the new-entrant pattern concentrates in aviation/removal services, media, UAC, and new JV shells.")
add("- S5 drift is mostly benign product-vs-service NAICS variance (e.g., Dell, Gulfstream). One notable miscode: AMI Metals' $1.47B bulk-steel contract is coded NAICS 541614 (logistics consulting) against a 331491 rolled-steel history — a records error on a mega-award, not a scheme signal by itself.")
add("")

# ---------------- data quality ----------------
add("## 9. Data-quality caveats")
add("")
add("- **FPDS reporting lag (quantified)**: max action_date in pull = 2026-07-26; last-30-day action count 4,513 vs trailing-3-month average ~4,254/mo -> no visible collapse, but individual actions may post up to 90 days late, so June-July dollars are a floor. Max last_modified in data = 2026-07-26 23:04 UTC (pull is current to the day).")
add("- **Oct-Nov 2025 trough is real-world, not lag**: action counts halve (2,099/2,303 vs ~4,600 norm) during the government shutdown.")
add("- **USASpending refresh cadence**: nightly from FPDS-NG; the bulk download reflects the previous FPDS day.")
add("- **Subaward invisibility**: prime-only census; FSRS pull is a next-pass hook. Wave-3 already showed reported_subaward_count=0 has no discriminating power.")
add("- **IGSA invisibility**: ICE detention via intergovernmental service agreements does not appear in FPDS at all; ICE window obligations here ($8.93B) understate detention economics.")
add("- **Offer counts are self-stamped per award record** (UAC caveat generalizes); 18.7% of window dollars carry no offer count.")
add("- **Extent-competed code D** ('full and open after exclusion of sources') buckets as 'competed' in the FPDS convention; the entire urgency wall program rides in that bucket. Read S1 with S1's OTFO table, never alone.")
add("- **Ceiling fields**: parent-IDV `potential_total_value_of_award` is unreliable for family capacity (shared-ceiling stamping: TSA $5.3B x21, EAGLE II $22B legacy stamps; per-member for UAC). Anomaly #1 shows the reverse failure (ceiling not maintained upward).")
add("- census-transactions.csv ceiling_before/after are exact only within an award's in-window ledger; pre-window ceiling baseline derives from cumulative-minus-delta on the first in-window action (verified semantics).")
add("- Two same-day duplicate-looking IDV rows for family-2 members (2026-05-11 + Jul re-stamps) are distinct FPDS actions (mods), not load dupes (dedupe key = contract_transaction_unique_key; 0 collisions).")
add("")

# ---------------- next pass ----------------
add("## 10. Out-of-scope next-pass hooks (with identifiers)")
add("")
add("- **SAM.gov J&A harvest** targets (solicitation_ids / PIIDs): urgency family-1 IDVs 70B01C26D00000003-13 (no solicitation id — search by PIID); 70B01C26R00000007 (design-build); 70QS0326C00005002 (Daedalus); 70RDA225FR0000018 + parent 70RDA225D00000005 (Salus); 70T05025R5900N002 (TSA guard); HSTS05-15-R-SPP047 + HSTS0516DSPP906-913 (SPP raises); 70CDCR26R00000015 (UAC, already tracked); 26-SOL-DCR-01 (skip).")
add("- **FSRS subaward pull** top-slice UEIs: XAVBDA4D13N7 (Fisher), LEGGW1TNMVC9 (Barnard), VLDKT27H2AG1 (SLS), MKMNZ369ZB59 (Spencer), W31DQKBPJCD3 (SWVC), KE7ZAT98UBM7 (Daedalus), EA4VD72SB1W3 (Salus), plus s4-new-entrants.csv flagged set.")
add("- **County IGSA records**: ICE detention counties (not in FPDS).")
add("- **Political-network joins**: Fisher Sand & Gravel (Tommy Fisher), Spencer Construction, Daedalus, Salus beneficial owners -> FEC/state contributions.")
add("")

# ---------------- needs orchestrator ----------------
add("## 11. NEEDS ORCHESTRATOR")
add("")
add("- **DB writes wanted** (I made none): leads for top-20 anomalies (esp. #1, #2, #4, #5, #6); findings for the canonical revalidation (citable: this census independently reproduces wave-3 numbers from a fresh bulk pull); source_reliability note for the USASpending bulk-file column-swap bug.")
add("- **User decisions**: whether Fisher/wall program becomes its own investigation profile vs tech-right thread; whether to spend HigherGov quota on vehicle/teaming data for Daedalus/Salus (10K records/month cap).")
add("- **Paid/gated**: OpenCorporates dead (per wave-3) — manual registry lookups for Daedalus Aviation Corporation, Salus Worldwide Solutions Corp, Spencer Construction LLC, AMI Metals; DE/VA/OH/MO registries behind CAPTCHA (user).")
add("- **SAM_API_KEY tier**: 10 req/day basic tier blocks J&A/entity API harvest at scale; request SAM role (1K/day) or schedule drip.")
add("- Wave-3 asks answered by this census: ICE-wide multiple-award-family baseline (S2: 362 families, 38 everyone-won), DHS-wide one-bid rate (26.7% of known dollars), newcomer base rate context (S4), 561611 comparator possible from census.db on demand.")
add("")
add("## Artifact inventory")
add("")
add("`census-awards.csv` (16,722 awards), `census-transactions.csv` (41,400 ledger rows), `census.db` (full 83,240-txn universe + award table), `recon.json`, `canonical-validation.json`, `screens-summary.json`, `s1-competition-by-component.csv`, `s1-competition-by-month.csv`, `s1-offers-distribution.csv`, `s1-otfo-authorities.csv`, `s2-families.csv`, `s3-ceiling-flags.csv`, `s4-new-entrants.csv`, `s5-naics-drift.csv`, `s6-concentration.csv`, `s6-office-outliers.csv`, `enrich_state.json`, raw zips + extracted CSVs under `raw/`, scripts (`probe_bulk.py`, `submit_full.py`, `poll_download.py`, `build_census.py`, `run_screens.py`, `enrich_s4_s5.py`, `validate_canonical.py`, `assemble_report.py`), `state.json`/`full_jobs.json`/`hedge_jobs.json` (job provenance).")

with open(f"{WORK}/census-report.md", "w") as f:
    f.write("\n".join(L) + "\n")
print(f"wrote {len(L)} lines to census-report.md")
