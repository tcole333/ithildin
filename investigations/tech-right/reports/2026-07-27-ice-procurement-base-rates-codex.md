# ICE procurement base-rate memo — codex-Q

**Prepared:** 2026-07-27  
**Local data snapshot:** 2026-07-13  
**Scope:** Wave 3 ICE skip-tracing / UAC Safety Verification Initiative; local files only; no network or database writes.

## Bottom line and scope correction

**CHANGED — the advertised “308 ICE prime awards” is not the logical CSV denominator.** Parsing `direct-ice-prime-award-universe-2026-07-13.csv` with Python's CSV reader yields **256 normalized prime instruments**, not 308: **228 USAspending-backed awards** plus **28 HigherGov-only legacy supplements**. The file covers only six GEO-linked legal recipients (The GEO Group, B.I. Incorporated, GEO Care Services, GEO Transport, Correctional Services Corporation, and Cornell Companies), not all ICE contractors. The apparent 308 comes from counting physical lines in a CSV containing embedded newlines. The competition matrix has **279 logical rows = 228 prime awards + 51 parent IDVs**. Source: exact `coverage_class` and `acquisition_layer` columns in the July 13 files.

**CONFIRMED — the UAC family is absent from every supplied tabular file.** Exact/local-string checks for solicitation `70CDCR26R00000015`, first IDIQ `70CDCR26D00000030`, and “safety verification” returned **0 rows in each of five CSVs**: the prime universe, competition matrix, IDV-family file, action ledger, and the supplemental B.I./skip ledger. This is because the files are a GEO-recipient reconstruction, not an ICE-wide snapshot, even though the UAC awards predate July 13.

**CONFIRMED — what the data can support.** The local files give a defensible base rate for the reporting behavior and procurement history of the GEO/B.I. direct-ICE cohort. They do **not** establish an ICE-wide rate for newcomer firms, offeror win rates, UAC award structures, or NAICS 561611 use across DHS.

**CONFIRMED — method.** All computations use Python 3 standard-library `csv`, `decimal`, `datetime`, `statistics`, and `collections`. Reusable code and machine-readable results are in `/tmp/osint-FRmkNLeM/work-Q/analyze_base_rates.py` and `/tmp/osint-FRmkNLeM/work-Q/analysis-results.json`. The additional relevant local source used was `bi-ice-skip-channel-task-allocation-ledger-2026-07-13.csv`, because it contains all 14 skip-tracing parent awards and task orders rather than only B.I.'s row.

**CONFIRMED — status convention.** **CONFIRMED** aggregate claims are recomputed from the 228 USAspending-backed rows or carried forward from Wave 3's primary-record verification. Exact aggregates drawn from the HigherGov parent-IDV ledger are labelled **UNCONFIRMED as external procurement facts** even when the local-file computation itself is exact.

**CONFIRMED — carried-forward program evidence.** Skip/UAC program structure and canonical amounts are cited from persisted Wave 1/2 findings **#14378–#14397** as corrected by the `WAVE3.md` canonical block and `fable-I-review.md` §0; this memo does not reopen those primary-source findings.

---

## 1. Offers received versus awardees

### What the files show

| Status | Test | Numerator / denominator and filter | Result |
|---|---|---|---:|
| **CONFIRMED** | UAC canonical win rate | 18 awards / 18 reported offers; solicitation `70CDCR26R00000015`; IDIQs `70CDCR26D00000030`–`...47`; findings #14378–#14397 / Wave 3 primary-record checks | **100.00%** |
| **CONFIRMED** | Skip-tracing canonical win rate | 14 awards / 51 reported offers; solicitation `26-SOL-DCR-01`; findings #14378–#14397 / Wave 3 canonical numbers | **27.45%** |
| **UNCONFIRMED** | Parent-IDV offer-count coverage | 49 nonblank `offers_received` / 51 GEO-linked HigherGov IDVs | **96.08% covered** |
| **UNCONFIRMED** | Where an offer count of 18 falls | 47 of 49 known HigherGov parent-IDV offer counts are below 18; 2 are above | **95.92% below 18** |
| **UNCONFIRMED** | Where an offer count of 51 falls | 47 of 49 known HigherGov parent-IDV offer counts are below 51; 1 equals 51; 1 is above | **95.92% below 51** |
| **UNCONFIRMED** | ICE-wide distribution of awardees per solicitation | No complete awardee roster in the prime universe or IDV file | **Not derivable** |

**UNCONFIRMED externally — exact HigherGov-file distribution.** Among the 51 GEO-linked parent IDVs in `direct-ice-idv-task-order-families-2026-07-13.csv`, the `offers_received` distribution is:

| Offers reported | Parent IDVs | Share of 49 known |
|---:|---:|---:|
| 1 | 27 | 55.10% |
| 2 | 6 | 12.24% |
| 3 | 7 | 14.29% |
| 4 | 6 | 12.24% |
| 8 | 1 | 2.04% |
| 51 | 1 | 2.04% |
| 54 | 1 | 2.04% |

**UNCONFIRMED externally — distribution filter.** The local filter is parent-IDV rows with nonblank `offers_received`; numerator is the row count at each value and denominator is 49.

**CONFIRMED — the files do not pair those offer counts with complete awardee counts.** Only 28 of the 51 parent rows have a nonblank `solicitation_identifier`. Just one nonblank identifier repeats: `70CDCR20R00000002`, represented by two GEO IDVs (`70CDCR20D00000008` and `70CDCR20D00000009`). That is an observed GEO subset, not the full awardee slate. The file also lacks a reliable multiple-award-family flag at the parent layer.

**CHANGED — the supplemental skip ledger is internally inconsistent on the offer stamp.** `bi-ice-skip-channel-task-allocation-ledger-2026-07-13.csv` contains **14 parent IDVs and 14 task orders** for `26-SOL-DCR-01`, corroborating the award count and reproducing **$19,032,607** in task-order obligations. But 12 parent rows report 51 offers while the SOSi and Global Recovery Group rows report 53. Per `WAVE3.md`, this memo uses the canonical **51 offers → 14 awards** and treats the local stamp discrepancy as another reason not to overprecision offer counts.

**UNCONFIRMED — so what (inference).** The UAC result is descriptively exceptional: every reported offer corresponds to an award, versus 27.45% for skip tracing, and an offer count of 18 is higher than 47 of the 49 known GEO-parent offer counts. But the **100% win rate cannot be assigned an empirical ICE percentile** from these files, because the comparison file does not enumerate all awardees for each solicitation. The strongest defensible wording remains: “Each of the eighteen UAC award records reports eighteen offers received, and ICE issued eighteen IDIQ awards.” Calling that statistically anomalous requires an ICE-wide multiple-award-family roster or the UAC source-selection record.

---

## 2. Newcomer awardees

### Derivable proxy

**CONFIRMED — proxy definition.** A recipient is treated as “new to observed ICE prime contracting” if its earliest `period_start` in the **228-row USAspending-backed primary file** is within 6, 12, or 24 months of its first primary award beginning on or after 2025-01-01. This is a same-UEI ICE-history proxy, not a federal-history or corporate-formation test.

| Recipient UEI | Earliest observed ICE instrument | First award beginning in 2025+ | Lag | 2025+ primary awards |
|---|---:|---:|---:|---:|
| GEO Transport, `DFEKRCYPZD84` | 2021-09-22 | 2026-01-09 | 1,570 days | 1 |
| The GEO Group, `JMLKZZ1NL2Z6` | 2003-01-15 | 2025-03-01 | 8,081 days | 16 |
| B.I. Incorporated, `PKK6L9KLMYR5` | 2004-03-22 | 2025-09-30 | 7,862 days | 2 |

| Threshold | Newcomer recipients / recent recipients | Rate | Filter |
|---|---:|---:|---|
| Within 6 months (183 days) | 0 / 3 | **0.00%** | Unique UEIs with a primary award starting 2025-01-01 or later |
| Within 12 months (366 days) | 0 / 3 | **0.00%** | Same |
| Within 24 months (731 days) | 0 / 3 | **0.00%** | Same |

**CONFIRMED — denominator.** There are **19 primary awards** in the 2025+ filter, held by these three UEIs.

**UNCONFIRMED — newcomer base rate for ICE or federal contracting.** The files contain only GEO-linked recipients and no `first_federal_action_date`, SAM registration date, legal-formation date, or non-ICE federal award history. They therefore cannot measure how often ICE awards newcomers generally, nor calibrate Response AI Solutions, National Protective Services, Fraud Inc., GSS, or the UAC cohort.

**UNCONFIRMED — so what (inference).** The zero rate is a property of a deliberately incumbent GEO/B.I. cohort, not evidence that ICE rarely uses newcomers. It is useful only as a contrast: the supplied historical comparator consists entirely of established ICE vendors, while the Wave 3 newcomer claims concern firms outside this file. An ICE-wide UEI history extract is required before describing the newcomer cohort as rare in rate terms.

---

## 3. Subaward-reporting base rate

### USAspending-backed prime awards by cumulative obligation size

**CONFIRMED — filter.** The denominator is the **228** rows where `coverage_class = "USAspending + HigherGov"`. Size band uses `award_amount_usaspending`, which is cumulative award obligations, not ceiling or revenue. A “zero report” means `reported_subaward_count = 0`; `reported_subaward_amount` is blank on all 228 rows.

| Cumulative award obligations | Awards in band | `subaward_count = 0` | Zero-report rate | Obligations represented |
|---|---:|---:|---:|---:|
| $0 | 10 | 10 | **100.00%** | $0.00 |
| >$0 to <$1M | 43 | 43 | **100.00%** | $8,018,211.25 |
| $1M to <$10M | 43 | 43 | **100.00%** | $179,426,481.56 |
| $10M to <$100M | 117 | 117 | **100.00%** | $4,910,985,670.01 |
| $100M+ | 15 | 15 | **100.00%** | $2,675,775,174.83 |
| **All primary awards** | **228** | **228** | **100.00%** | **$7,774,205,537.65** |

**CONFIRMED — reporting result.** Every one of the 228 official award-detail rows reports zero subawards; every `reported_subaward_amount` cell is blank. This reproduces the reconciliation report's bounded negative and holds even in the $100M+ band.

**UNCONFIRMED — actual subcontracting rate.** A zero count and blank amount do not establish that no subcontractor or operating vendor existed. The house pass-through method in `systemic-analysis-ice-igsa-pass-through-2026-07-13.md` specifically warns that legal-prime reporting can coexist with downstream roles identifiable only in contracts, IGSAs, invoices, or first-tier reports.

**UNCONFIRMED — so what (inference).** “Zero reported subawards” has **no discriminating power inside this comparator**: it appears on 228 of 228 GEO-linked ICE primes, including the largest awards. Thus a zero field on Delaney Hall or another ICE prime does not, by itself, strengthen or weaken the Response AI/pass-through hypothesis. It instead shows that the structured field has inadequate sensitivity for this question; signed subcontract files, FSRS records, invoices, or vendor disclosures are needed.

---

## 4. NAICS 561611 and PSC R799 in context

### Award-start cohorts

**CONFIRMED — filter.** The denominator is 228 USAspending-backed prime awards, grouped by fiscal year of `period_start`. Dollars are each award's cumulative `award_amount_usaspending`, grouped by start cohort; they are not annual spending.

| Award-start cohort | All awards | All obligations | 561611 awards | Award share | 561611 obligations | Obligation share |
|---|---:|---:|---:|---:|---:|---:|
| FY2000–FY2022 | 183 | $5,243,296,780.30 | 0 | 0.00% | $0 | 0.00% |
| FY2023 | 10 | $731,083,154.05 | 0 | 0.00% | $0 | 0.00% |
| FY2024 | 11 | $740,111,717.01 | 0 | 0.00% | $0 | 0.00% |
| FY2025 | 14 | $770,014,015.99 | 0 | 0.00% | $0 | 0.00% |
| FY2026 through 2026-07-13 | 10 | $289,699,870.30 | 1 | **10.00%** | $1,624,500 | **0.56%** |

**CONFIRMED — PSC R799 is identical to NAICS 561611 in the 228-row primary cohort.** The one matching award is B.I. Incorporated task order **`70CDCR26FR0000021`** under parent **`70CDCR26D00000005`**, period start 2025-12-16, description “THE PURPOSE OF THIS TASK ORDER IS TO OBTAIN SKIP TRACING SERVICES FOR ENFORCEMENT AND REMOVAL OPERATIONS (ERO).” Source: [USAspending award page](https://www.usaspending.gov/award/CONT_AWD_70CDCR26FR0000021_7012_70CDCR26D00000005_7012) and the local prime-universe row.

### Transaction/action-year view

**CONFIRMED — filter.** The denominator is 1,864 USAspending action rows, grouped by fiscal year of `action_date`. Dollars are net `transaction_amount`; this is the proper time-series measure within this cohort.

| Action period | Action rows | Distinct active awards | All net obligations | 561611/R799 rows | Matching awards | 561611/R799 net obligations | Share |
|---|---:|---:|---:|---:|---:|---:|---:|
| FY2008–FY2022 | 1,390 | 182 | $4,575,569,840.85 | 0 | 0 | $0 | 0.00% |
| FY2023 | 133 | 48 | $759,151,474.22 | 0 | 0 | $0 | 0.00% |
| FY2024 | 135 | 30 | $747,403,018.30 | 0 | 0 | $0 | 0.00% |
| FY2025 | 135 | 33 | $811,728,540.32 | 0 | 0 | $0 | 0.00% |
| FY2026 through snapshot | 71 | 31 | $648,450,369.52 | 2 | 1 | $1,624,500 | **0.25%** |

**CONFIRMED — matching actions.** The two FY2026 code-matching action rows are the $1,624,500 base action dated 2025-12-18 and the $0 extension `P00001` dated 2026-03-11, both for `70CDCR26FR0000021`.

**UNCONFIRMED externally — one HigherGov-only PSC row predates 2025, but its local description is not background-investigation work.** Instrument **`HSCEOP06J00328`**, period start 2006-05-26, is coded PSC R799 and NAICS 561612, carries $0 obligations in this file, and describes detention-facility services. Source: [HigherGov contract page](https://www.highergov.com/contract/HSACD4C0001-HSCEOP06J00328/). This local row shows why PSC R799 alone cannot identify investigative work.

**UNCONFIRMED — broader DHS history.** These files do not include DHS-wide 561611 awardees such as CACI, Omniplex, Peraton, or Anasec. They therefore **cannot corroborate** the separate Wave 3 claim that DHS historically used 561611 for employee/personnel background investigations. The local label “Investigation and Personal Background Check Services” is a code description; the only primary matching scope is ICE skip tracing.

**UNCONFIRMED — so what (inference).** Within the GEO/B.I. ICE cohort, NAICS 561611 appears as a new FY2026 classification attached to skip tracing, not as a longstanding procurement category. That is a genuine within-cohort break, but it is not a DHS base rate. The broader “personnel vetting to migrant-location work” comparison remains dependent on a separate DHS-wide award extract.

---

## 5. Competition extent, one-offer awards, and letter contracts

### Prime-award layer

**CONFIRMED — filter.** The denominator is 228 `acquisition_layer = prime_award` rows in `direct-ice-competition-matrix-2026-07-13.csv`. Dollars use `award_obligations_usaspending`.

**CONFIRMED — code normalization.** The local CSV does not preserve the one-character FPDS value `A`; it stores the normalized `extent_competed` label `FULL AND OPEN COMPETITION`. The one-offer rates below filter on that normalized competition bucket.

| Competition bucket | Awards | Share of 228 | Obligations |
|---|---:|---:|---:|
| Full and open — multiple offers | 25 | 10.96% | $402,622,746.25 |
| Full and open — one offer | 41 | **17.98%** | $950,680,363.48 |
| Full and open — offer count missing | 97 | 42.54% | $5,864,566,754.40 |
| Sole source or not competed | 29 | 12.72% | $282,822,261.53 |
| Simplified acquisition — one offer | 23 | 10.09% | $78,827,913.04 |
| Simplified acquisition — offer count missing | 2 | 0.88% | $200.16 |
| Order competition — one offer | 3 | 1.32% | $133,643,753.04 |
| Other or ambiguous | 8 | 3.51% | $61,041,545.75 |

**CONFIRMED — full-and-open/one-offer is common in this cohort.** It appears on **41/228 awards (17.98%)**, **41/163 full-and-open awards (25.15%)**, and **41/66 full-and-open awards with a known offer count (62.12%)**. Those prime rows are mostly orders or calls, so the field may describe an order action rather than competition for the parent vehicle.

### Parent-IDV layer

**UNCONFIRMED externally — HigherGov parent-IDV filter.** The local denominator is 51 `acquisition_layer = parent_idv` rows.

| Parent competition bucket | IDVs | Share |
|---|---:|---:|
| Full and open — multiple offers | 22 | 43.14% |
| Full and open — one offer | 16 | **31.37%** |
| Sole source or not competed | 11 | 21.57% |
| Competition metadata missing | 2 | 3.92% |

**UNCONFIRMED externally — parent subset.** Among the **38 full-and-open HigherGov parent IDVs**, 16 report one offer: **16/38 = 42.11%**.

**UNCONFIRMED externally — exact local letter-contract keyword base rate.** One of 51 HigherGov parent-IDV descriptions contains “letter contract”: **`70CDCR25D00000009`**, The GEO Group, period start 2025-03-18, “UNDEFINITIZED LETTER CONTRACT” for North Lake detention, one offer, `Not Competed`, `Sole Source`. That is **1/51 = 1.96%** of the parent ledger. Source: [HigherGov IDV page](https://www.highergov.com/idv/70CDCR25D00000009/). Detection is description-keyword based because `idv_type` does not encode letter-contract status.

**UNCONFIRMED — SOSi letter-contract prevalence.** Specific SOSi instrument **`70CDCR26C00000001`** is absent from the 256-row prime universe. The local files therefore do not provide a denominator for ICE letter contracts generally or for contracts issued before a competition.

**UNCONFIRMED — full-and-open with a 100% family award rate.** The files show many full-and-open/one-offer records, but those are not the same fact as 18 offers and 18 awards. Since complete awardee counts by solicitation are unavailable, the base rate for a full-and-open procurement awarding every offeror cannot be calculated.

**UNCONFIRMED — so what (inference).** A full-and-open record with one offer is not unusual inside the GEO/B.I. cohort, and one keyword-identifiable undefinitized letter contract exists in the local parent ledger. Neither result normalizes UAC's reported 18-for-18 outcome: one-offer awards measure market response, while 18-for-18 measures the agency's selection rate among many reported offerors. The local denominator supports caution around “one offer” rhetoric but leaves the UAC selection-rate question open.

---

## 6. IDV family shapes and early utilization

### Family-size and ratio baseline

**UNCONFIRMED externally — HigherGov family filter.** The local denominator is all 51 rows in `direct-ice-idv-task-order-families-2026-07-13.csv`. “Ratio” is `linked_order_obligations_highergov / potential_total_value`; it is labelled as a recorded-field ratio rather than a definitive utilization rate.

| Metric | Numerator / denominator | Result |
|---|---:|---:|
| Child orders/calls per IDV | 51 families | Median **4**; IQR **2–6**; range **0–13** |
| No linked child | 4 / 51 | **7.84%** |
| Positive `potential_total_value` | 42 / 51 | **82.35%** |
| Recorded-field ratio, all positive-potential rows | 42 IDVs | Median **55.74%**; IQR **22.36%–89.85%** |
| Ratios exceeding 100% | 5 / 42 | **11.90%** |
| Sensitivity excluding >100% ratios | 37 IDVs | Median **41.68%**; IQR **10.54%–67.62%** |

**CONFIRMED — ratio-field limitation.** Nine families have a zero `potential_total_value`, and five of the remaining 42 local rows produce ratios above 100%. Thus `potential_total_value` is not a consistently clean ceiling across eras/sources. The median is descriptive, not a reliable ICE utilization norm.

### Age-matched view as of 2026-07-13

**UNCONFIRMED externally — exact local HigherGov comparison.**

| Age since `period_start` | Families | Positive-potential families | Median child count | Median recorded ratio |
|---|---:|---:|---:|---:|
| 0–90 days | 1 | 1 | 0 | 0.00% |
| 91–180 days | 1 | 1 | 1 | 56.53% |
| 181–365 days | 2 | 2 | 1 | 5.94% |
| 366–730 days | 4 | 4 | 1.5 | 6.23% |
| 731+ days | 43 | 34 | 5 | 62.10% |

**UNCONFIRMED externally — the entire local ≤365-day HigherGov comparison set is:**

| IDV | Recipient | Start | Age | Child count | Linked obligations | Potential value | Ratio |
|---|---|---:|---:|---:|---:|---:|---:|
| `70CDCR26D00000049` | The GEO Group | 2026-07-09 | 4 days | 0 | $0 | $528,678,643.44 | 0.00% |
| `70CDCR26D00000026` | The GEO Group | 2026-03-28 | 107 days | 1 | $39,042,746.99 | $69,061,134.27 | 56.53% |
| `70CDCR26D00000005` | B.I. Incorporated skip-tracing IDIQ | 2025-12-16 | 209 days | 1 | $1,624,500 | $121,837,500 | 1.33% |
| `70CDCR25D00000062` | B.I. Incorporated ISAP V | 2025-09-30 | 286 days | 1 | $108,343,853 | $1,027,594,113.39 | 10.54% |

### Where the two programs sit

**CONFIRMED — program inputs.** The following ceilings, child-order obligations, dates, and instrument IDs are carried from findings #14378–#14397 and the corrected Wave 3 canonical block; only the displayed ratios and local-distribution ranks are calculated here.

| Program | Age at July 13 snapshot | Obligations | Ceiling denominator | Ratio | Local comparison |
|---|---:|---:|---:|---:|---|
| Skip tracing, `26-SOL-DCR-01` | 209 days from 2025-12-16 | **$19,032,607** across 14 child task orders | **$1,442,909,640** combined IDIQ ceiling | **1.32%** | Below the only other 181–365-day comparator (ISAP V, 10.54%); 5/42 local positive-potential IDVs are at or below 1.32% |
| UAC new 18-IDIQ family, `70CDCR26R00000015` | 41 days from 2026-06-02 | **$85,376,317** on the 18 new-family orders | **$20,583,928,204** combined IDIQ ceiling | **0.41%** | Only one local 0–90-day comparator exists, at 0%; no robust age-matched baseline |
| Broader UAC initiative including MVM | 41 days for the new parents | **$86,822,317** across 19 orders | Same 18-new-IDIQ ceiling | **0.42% contextual ratio** | Numerator includes MVM `70CDCR26FR0000052` under FY24 vehicle `70CDCR24D00000002`, so this is not a strict same-family utilization measure |

**CONFIRMED — numerator boundary.** The strict UAC-family numerator is the Wave 3 canonical initiative total minus MVM's $1,446,000 older-vehicle order: $86,822,317 − $1,446,000 = $85,376,317. No parent-IDV obligation field was used.

**UNCONFIRMED externally — both ratios sit near the bottom of the unadjusted HigherGov distribution.** For both the 1.32% skip rate and the approximately 0.42% UAC rate, only **5/42 = 11.90%** of local positive-potential IDVs are at or below the target, while 37/42 are above. This unadjusted rank is dominated by mature vehicles.

**UNCONFIRMED — so what (inference).** Low early utilization is not evidence of procurement failure or nonperformance. Skip tracing is low even against its very small age bucket, but the bucket contains only itself and ISAP V. UAC has no meaningful age-matched denominator at all. The safest conclusion is that both programs had deployed only a small fraction of stated capacity by the snapshot; their ceilings must not be presented as spending, and age-adjusted anomaly claims should wait for a broader recent-IDIQ cohort.

---

## Data limitations

- **CHANGED — population limitation:** the prime file is a 256-row GEO-family reconstruction, not 308 logical awards and not an ICE-wide vendor universe. All aggregate rates must be described as GEO/B.I.-cohort rates.
- **CONFIRMED — UAC coverage gap:** zero rows match the UAC solicitation or IDIQs across the five analyzed CSVs. The UAC figures in this memo come from Wave 3's locally stored primary-record synthesis, not the July 13 tables.
- **CONFIRMED — family-completeness gap:** the 51-IDV file holds vehicles awarded to GEO-linked recipients. It does not enumerate every awardee under each solicitation, so offeror-to-awardee win rates are unavailable.
- **CONFIRMED — offer-stamp quality issue:** the skip-specific ledger has 12 parent rows reporting 51 offers and two reporting 53, while Wave 3's corrected canonical value is 51. Multiple-award offer counts can be copied across records or later revised.
- **CONFIRMED — layer mismatch:** prime-award obligations, transaction-action net amounts, linked child-order obligations, parent potential values, and combined program ceilings are different measures. They are never added together here.
- **CONFIRMED — ratio-field quality issue:** 9/51 IDVs have zero potential values and 5/42 positive-potential rows imply over 100% utilization. Cross-era `potential_total_value` is not a clean universal ceiling field.
- **CONFIRMED — missingness:** 107/228 prime awards lack offer counts; missing values are not treated as zero or one.
- **CONFIRMED — subaward sensitivity:** 228/228 primary rows report `subaward_count = 0`, while all 228 amount fields are blank. This is a reporting-base-rate result, not proof of zero subcontracting.
- **UNCONFIRMED — newcomer status:** the files do not contain corporate formation, SAM registration, first federal award, employee count, or acquisition-responsibility records for the skip/UAC newcomers.
- **UNCONFIRMED — DHS code history:** the data cannot test historical DHS-wide use of NAICS 561611 because it excludes non-GEO recipients and non-ICE DHS components.

## NEEDS NETWORK / EXTERNAL PRIMARY RECORDS

1. **UAC award-rate denominator:** the full award notice, source-selection decision, offeror roster, and any unsuccessful-offeror notices for solicitation `70CDCR26R00000015`. This is what would confirm whether “18 reported offers and 18 awards” means every eligible offeror won.
2. **ICE-wide multiple-award-family baseline:** all ICE parent IDVs grouped by normalized solicitation identifier, with distinct awardee UEIs, offer counts, set-asides, cancellation/withdrawal records, and dates. This would locate 18/18 and 51/14 in a real distribution.
3. **Newcomer base rate:** ICE-wide award history by UEI plus government-wide first-action dates and SAM registration dates for all 14 skip and 18 UAC awardees.
4. **Subaward reality:** FSRS/first-tier subcontract reports, signed subcontracting plans, invoices, responsibility files, and vendor ledgers for Delaney Hall, Response AI Solutions, and the suspected pass-through cases.
5. **DHS 561611 comparator:** a DHS-wide pre-2025 award and transaction extract with component, recipient, PIID, description, NAICS, PSC, and obligations. This is required to validate the historical personnel-background-investigation claim.
6. **Letter-contract base rate:** ICE-wide acquisition records identifying letter contracts and undefinitized actions, including SOSi `70CDCR26C00000001`, definitization dates, J&As, competition dates, and obligations.
7. **Recent-IDV utilization baseline:** a cross-vendor cohort of ICE IDVs first awarded in FY2025–FY2026 with child-order obligations and verified ceilings at 30, 60, 90, 180, and 365 days.

## NEEDS MANUAL OPENCORPORATES

- No OpenCorporates lookup can settle the procurement denominators above.
- If “newcomer” is expanded from first federal/ICE action to legal-entity age, manually obtain formation and conversion histories for all 18 UAC and 14 skip-tracing awardees, prioritizing Response AI Solutions, National Protective Services, Fraud Inc., GSS, AI Solutions 87, and the thin-record UAC firms. Treat registry formation as a separate measure from first federal activity.
