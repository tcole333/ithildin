# FY2025 ICE activation and obligation-timing analysis

**Skill:** `timeline-analysis`  
**Analysis run:** 77  
**Profile:** `geo-group`  
**Threads:** 108 — ICE Detention Contracts & Facilities; 110 — Procurement Vehicles, Entities & Money Flow  
**Window:** 2024-01-01 through 2026-07-13  
**Primary comparison:** GEO Group, CoreCivic, and Management & Training Corporation (MTC)

## Executive result

CoreCivic's FY2025 direct-ICE acceleration reflects both real new-capacity activity and pronounced federal-fiscal-year timing. California City and Midwest Regional received **$74.94 million** in FY2025 direct ICE obligations, equal to **59.3%** of CoreCivic's **$126.32 million** increase from FY2024. Of those two facilities' obligations, **$51.24 million** was recorded from September 26 through September 30, 2025—**40.6% of the entire annual increase** in the final five days of the fiscal year.

The late concentration is not sufficient to characterize the rise as an accounting artifact. CoreCivic's 10-K says California City began receiving detainees during August 2025. Dilley resumed operations in March, began receiving residents in April, and completed activation in September under an intergovernmental service agreement (IGSA). Conversely, Midwest Regional demonstrates why obligations cannot be equated with occupied-bed service: the company received activation funding and a longer-term contract, but litigation delayed intake and the company could not predict when it would accept detainees.

The peer chronology supports a **sector-wide demand wave**, but not yet the stronger null that awards were allocated in proportion to ready capacity. GEO announced or made effective new ICE activations at Delaney Hall, North Lake, and D. Ray James between February 27 and June 6, 2025. MTC's direct ICE obligations remained almost entirely concentrated in the existing Imperial Regional facility. Direct-recipient data also omit economically important IGSA activations, so the present evidence cannot normalize company shares by activated beds, rates, geography, or contracting channel.

No new hypothesis pair or lead was created. The dated evidence materially updates existing hypotheses 343–345 but does not distinguish a winner. Temporal proximity across contractors is evidence of a shared demand window, **not evidence of coordination**.

## Methods and scope

The analysis used only `geo-group`-scoped events and findings. It began with the run-76 procurement-audit bundle and hypotheses 343–345, exported the profile timeline and thread 108/110 findings, and then queried the official USAspending transaction-search endpoint for:

- GEO Group parent UEI `JMLKZZ1NL2Z6` — 313 actions in the requested window.
- CoreCivic parent UEI `HJGMJN1JKL46` — 136 actions.
- MTC parent UEI `G58ZEJ7HJGM1` — 22 actions.

Filters were U.S. Immigration and Customs Enforcement as awarding subtier, contract award types A/B/C/D, and action dates from 2024-01-01 through 2026-07-13. Transaction amounts were summed by action date and award ID. Negative obligations were retained. Company 2025 Forms 10-K supplied activation, intake, litigation, recognized-revenue, and IGSA-channel context.

The USAspending wrapper's transaction-field list is stale (`Federal Action Obligation` is no longer accepted); the existing papercut is #757. The analysis therefore used the same official API directly with the current `Transaction Amount` field.

### Period caveats

- **FY2024 transaction decomposition is partial** because the requested window begins January 1, 2024 and omits October–December 2023. The full FY2024 company totals below come from run 76's fiscal-year spending-over-time query.
- **FY2026 is partial through July 13, 2026** and is not annualized or used to claim a trend.
- Federal fiscal-year obligations, calendar-year recognized revenue, and facility-level cash payments are different measures.
- Direct UEI totals omit or misattribute local-government and other IGSA pass-throughs.

## Company transaction timelines

### CoreCivic

| Measure | Amount | Interpretation |
|---|---:|---|
| Full FY2024 direct ICE obligations | $179.44m | Run-76 baseline |
| Full FY2025 direct ICE obligations | $305.77m | +$126.32m / +70.4% |
| FY2026 direct ICE obligations through 2026-07-13 | $233.60m | Partial; excluded from trend inference |
| California City FY2025 task orders | $49.15m | New activation; intake began August |
| Midwest Regional FY2025 task orders | $25.79m | Activation/contract funding; intake delayed |
| California City + Midwest | $74.94m | 24.5% of FY2025 total; 59.3% of annual increase |
| California City + Midwest, Sep. 26–30 | $51.24m | 68.4% of their FY2025 obligations; 40.6% of annual increase |
| Otay Mesa + Houston FY2025 | $150.71m | 49.3% of FY2025 total at legacy facilities |

CoreCivic's FY2025 month-by-month direct obligations were especially concentrated in March ($49.30m), April ($41.66m), and September ($105.50m). September alone was 34.5% of the annual total. The pattern has two pulses:

1. **March–April activation pulse.** Midwest received $5.0 million on March 7 and $5.208 million on April 11. California City received $10.0 million on April 3.
2. **Fiscal-year-end contract pulse.** Midwest received $15.583 million on September 26; California City received $13.226 million on September 27 and $22.426 million on September 30.

The filed operational chronology is mixed:

- Dilley resumed under an amended IGSA on March 5, began receiving residents in April, and completed activation in September. This economically material activation does not appear in the direct-CoreCivic transaction set.
- Midwest's March 7 letter agreement authorized $5.0 million initially and up to $22.6 million for six months. A new contract became effective September 7, but an injunction delayed intake. This is positive evidence that direct obligations include activation and fixed-cost funding before occupied-bed service.
- California City's April 1 letter agreement authorized $10.0 million initially and up to $31.2 million for six months. It began receiving detainees in August, and a two-year contract became effective September 1. This is positive evidence of real operational growth.

Accordingly, hypothesis 343 (a few new activations explain a disproportionate share) and hypothesis 345 (fiscal timing exaggerates the apparent acceleration) are both consistent with the transaction chronology. Neither excludes the other.

### GEO Group

| Fiscal period | Direct ICE obligations | Status |
|---|---:|---|
| FY2024 actions from 2024-01-01 onward | $563.38m | Partial FY2024 transaction window |
| FY2025 | $811.73m | Full fiscal year |
| FY2026 through 2026-07-13 | $648.45m | Partial; excluded from trend inference |

GEO's filed activation sequence provides the strongest peer evidence for broad demand:

- February 27: 15-year Delaney Hall award announced.
- March 20: North Lake announced for immediate activation.
- June 6: D. Ray James/Folkston modification became effective.
- June 10: Adelanto settlement allowed immediate full intake under an existing contract.

Direct task orders identifiable to Delaney Hall and North Lake totaled **$60.68 million**, or 7.5% of GEO's FY2025 direct ICE obligations. D. Ray James was activated under an existing IGSA and is not identifiable as a direct GEO-parent task order in this recipient slice.

GEO's 10-K separately attributed **$152.4 million** of its calendar-2025 U.S. Secure Services revenue increase to activations at Delaney Hall, North Lake, D. Ray James, North Florida, and new transportation contracts. That figure cannot be reconciled one-for-one to the fiscal-year obligation slice, but it confirms that new activations materially affected actual company operations and recognized revenue.

GEO's direct transaction set also contains large legacy or non-detention lines, including $168.37 million for ISAP IV and large task orders for Adelanto, Tacoma, Aurora, Montgomery, South Texas, and Mesa Verde/Golden State. The demand wave was broader than the newly named facilities.

### Management & Training Corporation

| Fiscal period | Direct ICE obligations | Status |
|---|---:|---|
| FY2024 actions from 2024-01-01 onward | $32.09m | Partial FY2024 transaction window |
| FY2025 | $50.62m | Full fiscal year |
| FY2026 through 2026-07-13 | $20.92m | Partial; excluded from trend inference |

MTC serves as a useful negative control for facility proliferation. FY2025 obligations were almost entirely two current/predecessor task orders for the existing Imperial Regional Detention Facility: **$50.621 million**, or **99.9995%** of its $50.621 million total. The only other direct action was a $250 minimum under the emergency detention sourcing vehicle.

MTC's 13.8% FY2025 growth is consistent with continuation and annual task-order replacement at one facility, not a multi-site activation wave. This does not show that MTC lacked indirect, state/local, or other federal activity; it only characterizes the direct-ICE parent-UEI slice.

## Cross-company interpretation

### What the timing establishes

1. **New capacity explains a majority of CoreCivic's direct annual increase.** California City and Midwest cross the pre-registered “more than half” diagnostic for hypothesis 343 at 59.3%.
2. **Year-end booking is material.** Final-five-day obligations to those sites equal 40.6% of CoreCivic's annual increase, supporting hypothesis 345.
3. **The demand shock was not unique to CoreCivic.** GEO disclosed three major activations from late February through early June, and CoreCivic disclosed Dilley, Midwest, and California City activity from early March onward.
4. **Obligation timing and service timing diverge.** Midwest had material obligations without detainee intake; California City had both obligations and physical intake; Dilley had physical intake but no direct-recipient obligation visibility.
5. **MTC is not a symmetric peer in this window.** Its direct ICE activity remained one-facility continuation, which prevents treating the three firms as interchangeable capacity providers.

### What the timing does not establish

- It does not show contractor coordination, favoritism, or wrongdoing.
- It does not show awards were proportional to ready beds, because comparable facility readiness, location, security level, per diem, transportation, and feasible-alternative data are incomplete.
- It does not show all CoreCivic growth was caused by new sites; Otay Mesa and Houston alone represented 49.3% of its FY2025 direct total.
- It does not show the fiscal-year-end actions were improper. Incremental funding and new-period task orders commonly cluster near fiscal boundaries.
- It does not reconstruct local-government pass-through payments or distinguish fixed activation, guaranteed-minimum, per-diem, transportation, and startup components.

## ACH update

Competition group: `corecivic-fy2025-ice-acceleration`

| Hypothesis | New evidence | Assessment after run 77 |
|---|---|---|
| 343 — concentrated CoreCivic activations | California City + Midwest = 59.3% of annual increment; California City intake corroborated | Consistent, but capacity normalization and acquisition-file review remain open |
| 344 (H0) — broad urgent demand allocated by ready capacity | GEO and CoreCivic both disclosed multiple activations; MTC stayed at Imperial | Broad demand is consistent; proportional allocation is not yet tested |
| 345 — fiscal obligation timing exaggerates acceleration | 40.6% of annual increment at the two new sites landed Sep. 26–30; Midwest had obligations without intake | Consistent, but real California City and Dilley activity means timing is not the whole explanation |

The ACH ranking remains tied: all three hypotheses have zero inconsistencies. No new ACH pair was warranted because the timing phenomenon was anticipated by hypotheses 343–345 and is now better decomposed rather than newly unexplained.

## Database work

### Dated source findings

- **12444** — Midwest letter agreement, effective contract, and intake delay.
- **12445** — California City letter agreement, August intake, and September contract.
- **12446** — Dilley IGSA resumption, resident intake, and completed activation.
- **12447** — GEO Delaney/North Lake/D. Ray James activation sequence.

### Synthesis findings

- **12448** — CoreCivic transaction-level activation and fiscal-year-end decomposition.
- **12449** — GEO/CoreCivic/MTC activation-channel comparison and negative result on simple symmetry.

All seven new/updated dated findings were tagged `temporal=fy2025-ice-activation-wave`. Findings 12448 and 12449 are `claim_type=synthesis`, `confidence=medium`, and carry quoted structured metrics. Findings 12444–12447 are primary-source direct quotes. Hypotheses 343–345 were updated and evaluated; no new hypothesis or lead was created.

## Source bundle

Run-77 working bundle: `/tmp/osint-PoEnvwxc`

- `geo-transactions-p1.json` through `geo-transactions-p4.json` — 313 USAspending transaction actions.
- `corecivic-transactions-p1.json` and `corecivic-transactions-p2.json` — 136 actions.
- `mtc-transactions-p1.json` — 22 actions.
- `timeline.json`, `findings-108.json`, `findings-110.json`, and `events.json` — profile-scoped timeline inputs.
- `window-2025-spring.json` and `window-2025-yearend.json` — dated event/finding windows.
- `ach-matrix.json` and `ach-ranking.json` — post-run hypothesis evaluation.

Primary filings:

- CoreCivic 2025 Form 10-K: https://www.sec.gov/Archives/edgar/data/1070985/000119312526060669/cxw-20251231.htm
- GEO Group 2025 Form 10-K: https://www.sec.gov/Archives/edgar/data/923796/000119312526071747/geo-20251231.htm
- USAspending transaction search API: https://api.usaspending.gov/api/v2/search/spending_by_transaction/

## Remaining discriminator

The next useful evidence is not another annual total. It is the acquisition/payment decomposition already scoped in leads 58082, 58084, and 58086: California City and Midwest J&A/price files, fixed-versus-per-diem CLIN schedules, invoice/payment timing, actual intake/occupied-bed dates, and a ready-bed/location normalization across GEO, CoreCivic, and MTC. Those records can test whether CoreCivic remained disproportionate after operational fit and fiscal timing are controlled.
