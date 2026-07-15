# Comparative ICE/DHS Procurement Audit: GEO, CoreCivic, MTC, and LaSalle

**Skill:** `audit-contracts` (Tier 2 analysis)  
**Analysis run:** 76  
**Profile:** `geo-group`  
**Research date:** 2026-07-13  
**Source bundle:** `/tmp/osint-V6E2IWgE`  

## Executive result

The only HIGH growth anomaly in the resolved direct-ICE cohort is CoreCivic's FY2025 increase: direct ICE contract obligations rose from $179.4 million in FY2024 to $305.8 million in FY2025, or 70.4%. That compares with 8.6% for GEO's parent recipient, -34.0% for B.I. Incorporated, and 13.8% for Management & Training Corporation (MTC). The median FY2025 change among those four non-zero direct recipient rows was 11.2%.

This is an anomaly to explain, not evidence of favoritism or wrongdoing. The current evidence supports three live explanations that cannot yet be separated: (1) a few CoreCivic-specific new or noncompeted activations account for disproportionate growth, (2) urgent sector-wide demand was allocated in line with ready capacity and CoreCivic happened to have the relevant beds, or (3) annual obligation timing exaggerates the underlying service increase. The ACH matrix correctly returns no winner because the available evidence is mostly non-diagnostic.

Direct-recipient data are especially incomplete for LaSalle and for facilities operated through intergovernmental service agreements (IGSAs). A near-zero direct result must not be interpreted as absence of ICE-derived revenue.

## Cohort and entity resolution

| Company / recipient row | Legal name | UEI | CAGE | HigherGov key | Treatment |
|---|---|---|---|---:|---|
| GEO parent | THE GEO GROUP, INC. | JMLKZZ1NL2Z6 | 3JMR1 | 10000076 | Separate parent row |
| GEO electronic monitoring | B.I. INCORPORATED | PKK6L9KLMYR5 | 3CUH9 | 10147020 | Separate subsidiary row |
| GEO transportation | GEO TRANSPORT, INC. | DFEKRCYPZD84 | 6PV86 | not resolved in this run | Separate subsidiary row |
| GEO secure-services subsidiary | GEO SECURE SERVICES, LLC | JLG3JBCL4CC7 | 7G0P0 | not resolved in this run | Separate subsidiary row; no direct ICE timeline amount in FY2022-26 query |
| GEO reentry subsidiary | GEO REENTRY SERVICES, LLC | CLKXSJLN8EN1 | 7G0N6 | not resolved in this run | Separate subsidiary row; no direct ICE timeline amount in FY2022-26 query |
| CoreCivic parent | CORECIVIC, INC. | HJGMJN1JKL46 | 3HAR6 | 10000166 | Combined with zero-value TN LLC row |
| CoreCivic subsidiary | CORECIVIC OF TENNESSEE, LLC | HLXGZL34WHN8 | 5NXX8 | not resolved | No direct DHS obligations in sampled timeline |
| MTC | MANAGEMENT & TRAINING CORPORATION | G58ZEJ7HJGM1 | 3JBN8 | 10000164 | Parent row |
| LaSalle group | LASALLE CORRECTIONS V LLC | J76AEWGPFZT1 | 7VRH2 | 12490195 | Grouped with three same-address affiliates |
| LaSalle group | LASALLE CORRECTIONS WEST LLC | NTZ7CD687S87 | 7VY44 | not resolved | Same-address affiliate |
| LaSalle group | LASALLE CORRECTIONS VI LLC | SLKTUJ9DLSC5 | 8F3L4 | not resolved | Same-address affiliate |
| LaSalle group | LASALLE CORRECTIONAL CENTER, L.L.C. | GZSNL71M26V6 | 9QEL3 | not resolved | Same-address affiliate |

SAM resolution supports the legal names and identifiers above. The LaSalle entities share the 192 Bastille Lane, Ruston, Louisiana address, making LaSalle independently resolvable as a peer, but its federal role is not visible through direct ICE recipient totals.

## Spending timelines

### Direct ICE contract obligations

Amounts are net obligations from the USAspending `spending_over_time` endpoint with the awarding subtier constrained to U.S. Immigration and Customs Enforcement. FY2026 is partial as of the research date and is excluded from growth/anomaly judgments.

| Recipient | FY2022 | FY2023 | FY2024 | FY2025 | FY2026 partial | FY24→25 | FY22→24 historical CAGR | Flag |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| GEO parent | $667.7m | $759.2m | $747.4m | $811.7m | $648.5m | +8.6% | +5.8% | Normal |
| B.I. Incorporated | $270.1m | $314.2m | $288.3m | $190.3m | $88.0m | -34.0% | +3.3% | Decline |
| GEO Transport | -$3.1m | $0 | $0 | $0 | $10.4m | n/a | n/a | Deobligation / new partial-year activity |
| GEO Secure Services | $0 | $0 | $0 | $0 | $0 | n/a | n/a | No direct row |
| GEO Reentry Services | $0 | $0 | $0 | $0 | $0 | n/a | n/a | No direct row |
| CoreCivic | $139.8m | $159.6m | $179.4m | $305.8m | $233.6m | **+70.4%** | +13.3% | **HIGH / acceleration** |
| MTC | $40.8m | $44.1m | $44.5m | $50.6m | $20.9m | +13.8% | +4.3% | Normal |
| LaSalle resolved group | $0 | $0 | $0 | $0.00025m | $0 | n/a | n/a | Pass-through visibility limitation |

CoreCivic's FY2025 growth was approximately 5.3 times its own FY2022-FY2024 historical CAGR. It is the sole cohort member above the skill's 50% HIGH threshold.

### All-federal contract obligations

These totals are not ICE-specific and should be used only to show agency mix.

| Recipient | FY2022 | FY2023 | FY2024 | FY2025 | FY2026 partial | FY24→25 |
|---|---:|---:|---:|---:|---:|---:|
| GEO parent | $984.0m | $1,011.0m | $1,045.6m | $1,100.4m | $903.5m | +5.2% |
| B.I. Incorporated | $270.1m | $314.2m | $288.3m | $190.3m | $88.0m | -34.0% |
| CoreCivic | $288.3m | $252.6m | $270.8m | $395.9m | $305.0m | +46.2% |
| MTC | $266.9m | $281.7m | $233.6m | $210.6m | $166.8m | -9.9% |
| LaSalle resolved group | $0 | $0 | $0 | $0.00025m | $0 | n/a |

### FY2025 top-tier agency mix

| Recipient | DHS | DOJ | Labor | Other | Total federal |
|---|---:|---:|---:|---:|---:|
| GEO parent | $811.7m | $288.7m | $0 | negligible | $1,100.4m |
| B.I. Incorporated | $190.3m | $0 | $0 | $0 | $190.3m |
| CoreCivic | $305.8m | $90.1m | $0 | $0 | $395.9m |
| MTC | $50.6m | $0 | $159.9m | $0 | $210.6m |
| LaSalle resolved group | $0.00025m | $0 | $0 | $0 | $0.00025m |

For these direct rows, DHS and ICE are nearly identical in FY2025. MTC's broader federal total is primarily Department of Labor work, illustrating why all-federal totals cannot be described as detention spending.

## Competition and vehicle structure

| Award / vehicle | Contractor | Structure | Competition fields | Current significance |
|---|---|---|---|---|
| 70CDCR25D00000062 (ISAP V) | B.I. | Single-award IDIQ; fixed price; $1.028bn potential value | Full and open; negotiated proposal; 2 offers | Distinct electronic-monitoring market; task order 70CDCR25FR0000127 had $108.3m obligations when queried |
| 70CDCR20D00000007 | CoreCivic | California Detention Services IDIQ; San Diego AOR; fixed price; $2.494bn potential value | Full and open; 1 offer | Otay Mesa task order 70CDCR25FR0000011 showed $114.3m obligations |
| 70CDCR20D00000006 | MTC | California Detention Services IDIQ; San Diego AOR; fixed price; $775.0m potential value | Full and open; 1 offer | Imperial task order 70CDCR25FR0000012 showed $47.2m obligations |
| 70CDCR25D00000010 | CoreCivic | California City fixed-price IDIQ / undefinitized letter contract; $262.0m potential value | Not competed; sole source; 1 offer | Task order 70CDCR25FR0000122 showed $94.7m obligations |

The California Detention Services vehicle groups facility-specific single-award IDIQs; it is not a shared multiple-award pool where CoreCivic and MTC compete for each task order. A one-offer result after a full-and-open solicitation is not by itself proof of restrictive specifications. The acquisition plan, market research, independent government estimate, bidder communications, and price-negotiation memoranda are required to determine whether facility requirements naturally limited the field.

## Lobbying-contract timing

The table sums the disclosed `income` or `expenses` field after retaining the latest filing for each registrant/client/year/period. This is a reproducible filing-amount measure, not guaranteed net lobbying spend: outside-firm income and in-house expenses may overlap.

| Client search | 2022 | 2023 | 2024 | 2025 | FY24→25 direct ICE obligations | Timing assessment |
|---|---:|---:|---:|---:|---:|---|
| The GEO Group | $1.050m | $2.135m | $2.530m | $3.015m | +8.6% parent; -34.0% B.I. | Lobbying amounts rose, but no ICE obligation acceleration |
| CoreCivic | $3.490m | $3.140m | $3.304m | $3.500m | +70.4% | Filing amounts rose only 5.9%; no comparable pre-spike lobbying surge |
| MTC | $0.850m | $0.820m | $0.630m | $0.680m | +13.8% | No unusual timing correlation |
| B.I. Incorporated | no separate matches | no separate matches | no separate matches | no separate matches | -34.0% | Parent-company activity may cover subsidiary issues |
| LaSalle Corrections | no matches | no matches | no matches | no matches | direct data unavailable | Negative name search only, not proof of no lobbying |

The CoreCivic negative result weakens a simple hypothesis that a sharp increase in disclosed lobbying expenditure immediately preceded its procurement acceleration. It does not test access, contacts, issue effectiveness, or non-LDA political activity.

## Partnership network

HigherGov's partnership endpoint returned:

- GEO parent: 0 records.
- B.I.: 0 records.
- LaSalle Corrections V: 0 records.
- CoreCivic: 3 records, including Trinity Services Group (84 awards; $54.3m) and TransCor America (25 awards; $22.9m). TransCor's parent is CoreCivic.
- MTC: 100 records on the first returned page, showing a broad operating-subcontract network. No GEO, CoreCivic, B.I., or LaSalle cross-teaming record appeared in the returned cohort-name scan.

These partnership records are all-federal and are not filtered to ICE. No cohort cross-teaming conclusion should be drawn from absence in a single endpoint/page.

## SEC financial cross-check

| Company | SEC disclosure | Direct ICE obligation comparison | Interpretation |
|---|---|---|---|
| GEO | 2025 total revenue $2.632bn; ICE 47.6%, implying approximately $1.253bn of calendar-2025 recognized revenue | FY2025 direct obligations to GEO parent + B.I. were $1.002bn, about 20.0% lower | Consistent with a measurement/attribution gap; cannot isolate IGSA pass-throughs from CY/FY and revenue/obligation timing |
| CoreCivic | Calendar-2025 ICE revenue $770.7m, up from $564.8m (+36.5%) | FY2025 direct ICE obligations $305.8m, about 60.3% below the revenue figure and up 70.4% YoY | Large period/metric mismatch; direct-recipient data alone cannot reconstruct ICE exposure |

The comparison deliberately does not call either delta an "undercount." Calendar-year recognized revenue and federal-fiscal-year obligations are different measures, and customer percentages are rounded. The repeated direction across two issuers is consistent with a cross-company measurement/attribution gap and justifies payment-chain reconciliation.

Automated ratio analysis also flagged receivables growth above revenue growth for both issuers in 2025 (GEO receivables +57.8% versus revenue +8.6%; CoreCivic +54.5% versus revenue +12.7%). No standalone finding was created because ramp-related government receivables, billing timing, and asset changes are plausible; cash collection and aged-receivable data are needed.

## Revolving-door comparison

The current `geo-group` profile already contains SEC-sourced GEO findings:

| Person | Government role | Corporate role | Timing | Existing finding |
|---|---|---|---|---:|
| Matthew T. Albence | ICE roles 2012-2020, culminating as Acting Director | Joined GEO in 2022; SVP, Client Relations | Approximately two years after leaving ICE | 12385 |
| Daniel Ragsdale | ICE 1996-2017; Deputy Director 2012-2017 | Joined GEO July 2017; SVP, Contract Administration and Compliance | Same year as departure | 12386 |
| Julie Myers Wood | Head of ICE, January 2006-November 2008 | GEO director since 2014 | Approximately six years later | 12387 |

FEC name searches returned recent contributions from all three to the GEO PAC; Albence and Ragsdale also had 2025 records to other political committees. These facts do not establish procurement influence. The database currently has no comparably developed CoreCivic/MTC/LaSalle revolving-door roster, so the apparent GEO concentration is a coverage asymmetry, not a comparative conclusion. Lead 58137 was created to build the missing baseline and test role relevance, cooling-off periods, recusals, and contract timing.

## ACH hypotheses

Competition group: `corecivic-fy2025-ice-acceleration`

### Hypothesis 343 — concentrated CoreCivic-specific activations

**Claim:** A few CoreCivic-specific new or noncompeted activations account for a disproportionate share of its FY2025 incremental obligations after controlling for ready capacity.

**Best innocent explanation:** Facility fit and available beds can produce concentrated awards without preferential treatment.

**Diagnostic prediction:** More than half of incremental obligations trace to California City and a small number of new activations, and CoreCivic remains an outlier after normalizing for ready beds, rates, location, service mix, and activation dates.

**Falsification:** The increment is broadly distributed across legacy awards, or capacity-adjusted shares show CoreCivic was proportionate to available capacity.

### Hypothesis 344 (H0) — broad urgent demand allocated by ready capacity

**Claim:** Authentic sector-wide demand explains the change, and peer differences reflect ready beds, location, activation timing, rates, and services.

**Diagnostic prediction:** Obligation or recognized-revenue growth per activated bed is comparable across GEO, CoreCivic, and MTC; files document capacity need and feasible-alternative analysis.

**Falsification:** CoreCivic remains disproportionate after normalization and a few new/noncompeted actions explain most incremental obligations.

### Hypothesis 345 — fiscal obligation timing

**Claim:** Annual obligation timing makes the 70.4% increase materially larger than underlying service growth.

**Diagnostic prediction:** A few late-FY actions dominate; calendar-year revenue/outlays grow less; rolling-12-month and service-period-aligned growth converge below 70.4%.

**Falsification:** Aligned outlays, occupancy, and facility revenue sustain growth near 70.4% after future-period funding is removed.

### ACH result

All three hypotheses currently have zero inconsistent evaluations. The tool warns that the evidence is mostly non-diagnostic; no hypothesis should be described as leading. Lead 58082 contains the transaction, capacity, and acquisition-file tests required to discriminate among them.

The quantified SEC-versus-obligation mismatch was not used to create a duplicate visibility hypothesis. Finding 12414 was evaluated against existing hypotheses 341/342 and linked to existing GEO revenue-reconciliation lead 57844.

## Findings, leads, and run outputs

### Findings created

- **12413** — CoreCivic direct ICE procurement acceleration.
- **12414** — cross-company ICE revenue/obligation measurement-attribution gap.
- **12415** — one-offer and sole-source ICE detention competition structure.
- **12416** — CoreCivic lobbying-spend timing negative result.

All four are `claim_type=synthesis`, `confidence=medium`; every evidence row has a non-empty source quote or exact structured metric excerpt.

### Leads created

- **58082** — decompose CoreCivic FY2025 ICE acceleration and audit California City sole-source basis (`analyze-contract`, critical).
- **58084** — recover California Detention Services IDIQ competition files and one-offer rationale (`analyze-contract`, high).
- **58086** — reconcile CoreCivic ICE revenue to direct awards and IGSA pass-through payments (`analyze-contract`, high).
- **58137** — establish ICE/DHS revolving-door baseline across peers (`investigate-person`, high).

### Hypotheses created

- **343**, **344 (H0)**, **345**, all linked to lead 58082 and left `investigating`.

### Existing hypotheses extended

- **341** — finding 12414 assessed `consistent`, with CY/FY and metric caveats.
- **342 (H0)** — finding 12414 assessed `neutral` because downstream reconciliation is still required.

## Source files

Primary machine-readable artifacts in `/tmp/osint-V6E2IWgE`:

- `*-sam-local.json` — SAM entity/UEI resolution.
- `*-timeline-all.json` — all-federal fiscal-year obligations.
- `*-timeline-dhs.json` — DHS top-tier fiscal-year obligations.
- `*-timeline-ice-raw.json` — ICE subtier fiscal-year obligations.
- `*-fy2025-agencies-raw.json` — FY2025 top-tier agency breakdown.
- `*-awards-dhs.json` — DHS award lists with generated award IDs.
- `*-detail.json` and `*-idv-detail.json` — USAspending task-order/parent-award details.
- `*-hg-awardee.json`, `*-hg-idv.json`, `*-hg-partners.json` — HigherGov entity, competition, vehicle, and partnership data.
- `*-lobbying-2022.json` through `*-lobbying-2025.json` — Senate LDA filings.
- `geo-income.json`, `geo-balance.json`, `geo-ratios.json` — GEO SEC financial extraction.
- `corecivic-income.json`, `corecivic-balance.json`, `corecivic-ratios.json` — CoreCivic SEC financial extraction.
- `geo-2025-10k.html`, `corecivic-2025-10k.html`, `geo-2026-proxy.html` — primary SEC filings.
- `albence-fec.json`, `ragsdale-fec.json`, `wood-fec.json` — FEC donor spot checks.
- `corecivic-ach-matrix.json` — ACH evidence matrix.

Primary web records:

- GEO 2025 10-K: https://www.sec.gov/Archives/edgar/data/923796/000119312526071747/geo-20251231.htm
- CoreCivic 2025 10-K: https://www.sec.gov/Archives/edgar/data/1070985/000119312526060669/cxw-20251231.htm
- GEO 2026 proxy: https://www.sec.gov/Archives/edgar/data/923796/000119312526116014/d923546ddef14a.htm
- USAspending API: https://api.usaspending.gov/
- Senate LDA API: https://lda.senate.gov/api/
- HigherGov ISAP V: https://www.highergov.com/idv/70CDCR25D00000062/
- HigherGov California City: https://www.highergov.com/idv/70CDCR25D00000010/
- HigherGov California Detention Services vehicle: https://www.highergov.com/vehicle/california-detention-services-idiq-2733/

## Limitations and stop-condition audit

1. **FY2026 is partial** and excluded from all YoY flags and anomaly judgments.
2. **Obligations are not revenue, outlays, ceilings, or remaining value.** Negative amounts can represent deobligations.
3. **ICE direct-recipient totals omit pass-throughs.** LaSalle's near-zero result and the SEC comparison demonstrate why legal-prime and local-government payment chains must be reconstructed.
4. **Entity coverage is bounded to verified UEIs.** Counties, parishes, authorities, joint ventures, acquired aliases, and unresolved affiliates can sit outside parent-name queries.
5. **LDA amounts are a reproducible disclosed-field sum, not guaranteed net client spend.** Amended filings were deduplicated by latest registrant/client/year/period record; in-house and outside-firm amounts may overlap.
6. **HigherGov partnership results are all-federal and endpoint-limited.** They are not ICE-filtered and absence is not proof of no partnership.
7. **Revolving-door coverage is uneven.** GEO has SEC-developed biographies; peers do not yet have an equivalent roster. No comparative rate inference is warranted.
8. **Competition coding is not motive evidence.** One offer, sole-source authority, and an undefinitized letter contract require acquisition-file context.
9. **SEC comparisons mix calendar and federal fiscal years.** The deltas identify a reconciliation problem, not an undercount amount.
10. **Tool friction logged:** local SAM punctuation FTS bug (existing #760); LDA 429 written as an empty successful result (#766); EDGAR text sections ignored `--output` (#767); invalid `--related` lead IDs produced a raw FK traceback (#768).

Stop conditions are satisfied: timelines, lobbying, partnerships, SEC checks, revolving-door database/FEC checks, hypotheses with falsification, findings, leads, and a report are complete. The analysis remains appropriately open at the evidence level: its hypotheses are investigating, not confirmed.
