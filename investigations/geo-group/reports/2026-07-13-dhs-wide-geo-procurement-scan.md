# DHS-wide GEO procurement scan, 2015–2026

**Profile:** `geo-group`  
**Lead:** #58876  
**Thread:** 110  
**Coverage:** federal prime-contract actions dated 2015-01-01 through 2026-07-13, plus separate assistance and subcontract checks  
**Companion data:** [award/action CSV](2026-07-13-dhs-wide-geo-award-actions.csv) and [component summary JSON](2026-07-13-dhs-wide-geo-component-summary.json)

## Bottom line

Within a normalized 14-UEI GEO recipient universe, USAspending returned **1,416 unique DHS prime-contract action rows across 222 award PIIDs, with $6,356,699,228.62 in net action obligations** during the covered period. ICE accounts for 1,362 actions, 212 awards, and $6,354,097,259.08. CBP accounts for the only verified direct prime activity outside ICE: 54 actions, 10 awards, and $2,601,969.54.

The CBP tie is substantive, not merely an administrative agency label. All ten CBP awards name U.S. Customs and Border Protection as the awarding and funding sub-tier; every action uses the Border Enforcement Contracting Division as awarding office, and the funding offices are U.S. Border Patrol/Office of Border Patrol or, on two older instruments, the Office of Field Operations. Nine awards concern detention or jail space. One $2,711.07 purchase order concerns hygiene services for detainees. No direct CBP logistics- or transportation-only program appeared in this universe.

No direct prime-contract actions were verified for DHS headquarters/OPO, USCIS, FEMA, FPS/NPPD/CISA, TSA, Secret Service, Coast Guard, FLETC, or another DHS component. No federal assistance awards appeared for the 14 UEIs. Those are bounded negative results, not proof that GEO had no indirect, local-government, intergovernmental-service-agreement, joint-venture, or subcontract relationship with those components.

This report is a factual procurement inventory. It does not infer that political access, personnel relationships, lobbying, or an administration change caused any award or obligation.

## Corrected universe and deduplication

An early checkpoint counted the parent-UEI result and separately queried child-UEI results as though they were disjoint. USAspending's parent query had already expanded several child recipients. That produced a preliminary ICE figure of 1,586 actions and $8,552,736,402.90; **that preliminary figure is superseded and must not be used**.

The corrected universe combines 1,640 raw rows and removes 224 parent/child overlaps or exact duplicates. The reproducible deduplication key is:

`Award ID | Mod | Action Date | Transaction Amount | Transaction Description | Recipient UEI | Awarding Sub Agency`

The CSV stores a SHA-256 hash of the JSON-serialized key tuple for every retained row. The resulting 1,416 rows are unique on that key. Amounts in this report are the sum of transaction/action obligations, including positive obligations, deobligations, and zero-dollar modifications. They are not ceilings, outlays, cash payments, guaranteed values, or GEO revenue.

The entity universe was assembled from GEO's current SEC guarantor list, the March 2026 SAM public entity extract, live SAM entity checks, and legacy recipients present in USAspending. The 14 UEIs were:

| Legal name | UEI | CAGE | DHS actions |
|---|---|---:|---:|
| B.I. Incorporated | PKK6L9KLMYR5 | 3CUH9 | 166 |
| Community Education Centers, Inc. | K197TCMH5UB5 | 3YET9 | 0 |
| Cornell Companies, Inc. | TLDCDE29G781 | 3MTH6 | 24 |
| Correctional Services Corporation | LTXHRJ986LF3 | 3KGQ1 | 3 |
| GEO Care Services, LLC | G6XJKMJUNB91 | 7D4M5 | 92 |
| GEO Care, Inc. | J8LEF6VCY967 | 15A51 | 0 |
| GEO CPM Inc. | XHRVS1L8YE54 | 99YL8 | 0 |
| GEO Management Services Inc. | ZBJYBK7M9A44 | 7T8J8 | 0 |
| GEO Reentry Inc. | KDQ3R3N44ZJ1 | 7CUD5 | 0 |
| GEO Reentry of Alaska, Inc. | FNT5N5HMB9A7 | 7G0K5 | 0 |
| GEO Reentry Services LLC | CLKXSJLN8EN1 | 7G0N6 | 0 |
| GEO Secure Services, LLC | JLG3JBCL4CC7 | 7G0P0 | 0 |
| GEO Transport, Inc. | DFEKRCYPZD84 | 6PV86 | 3 |
| The GEO Group, Inc. | JMLKZZ1NL2Z6 | 3JMR1 | 1,128 |

The 1,128 parent-recipient rows include the 54 CBP rows. The subsidiary action counts above are based on the named transaction recipient after deduplication, not the result file in which the row happened to appear.

Two name-only gaps remain. “GEO Corrections Holdings, Inc.” appears in GEO's 2025 Exhibit 22 guarantor list, but exact current local/live SAM and USAspending searches did not yield a UEI or award recipient. “GEO Corrections and Detention” / “GEO Corrections & Detention” is not an exact legal name in that exhibit, and exact SAM/USAspending searches also returned no match. These failures do not establish that no historical or differently named registration exists. Existing lead #57693 remains the appropriate entity-resolution workstream.

## Component and administration-period results

| DHS component | Action rows | Unique awards | Net action obligations |
|---|---:|---:|---:|
| ICE | 1,362 | 212 | $6,354,097,259.08 |
| CBP | 54 | 10 | $2,601,969.54 |
| Other DHS components | 0 | 0 | $0.00 |
| **Total** | **1,416** | **222** | **$6,356,699,228.62** |

Administration periods use action dates, not award-start dates. “Pre-Trump I” is included so that actions from the beginning of the requested 2015 window are not silently assigned to a later administration. An award appearing in more than one period is counted once in each period in which it had an action, so period-level award counts are not additive.

| Component | Period | Action dates | Actions | Awards with actions | Net action obligations |
|---|---|---|---:|---:|---:|
| ICE | Pre-Trump I | 2015-01-01–2017-01-19 | 229 | 44 | $478,295,618.46 |
| ICE | Trump I | 2017-01-20–2021-01-19 | 445 | 132 | $1,686,365,164.41 |
| ICE | Biden | 2021-01-20–2025-01-19 | 511 | 101 | $2,900,292,455.05 |
| ICE | Trump II | 2025-01-20–2026-07-13 | 177 | 43 | $1,289,144,021.16 |
| CBP | Pre-Trump I | 2015-01-01–2017-01-19 | 10 | 5 | $458,026.46 |
| CBP | Trump I | 2017-01-20–2021-01-19 | 19 | 4 | $852,954.45 |
| CBP | Biden | 2021-01-20–2025-01-19 | 18 | 7 | $934,664.66 |
| CBP | Trump II | 2025-01-20–2026-07-13 | 7 | 3 | $356,323.97 |

The period totals establish timing and scale only. They do not establish an explanation for changes across administrations.

## The ten CBP awards

All ten CBP records name The GEO Group, Inc., UEI `JMLKZZ1NL2Z6`, CAGE `3JMR1`, as direct prime recipient. Nine are standalone definitive contracts or purchase orders. `HSBP1016J00076` is a BPA call under parent BPA `HSBP1012A00025`; the action obligation belongs to the call, not a separate grant. The period sum below is restricted to covered action dates. “Award obligations” and “potential value” are current award-level fields returned by USAspending and can include activity outside the period; for example, `HSBP1012C00101` began in 2012.

| PIID | Program | Instrument | Parent | 2015–26 actions | 2015–26 net actions | Award obligations | Potential value | Start | Potential end | Competition |
|---|---|---|---|---:|---:|---:|---:|---|---|---|
| [70B03C20P00000219](https://www.usaspending.gov/award/CONT_AWD_70B03C20P00000219_7014_-NONE-_-NONE-) | Detention/jail space | Purchase order | — | 9 | $585,781.54 | $585,781.54 | $987,051.30 | 2020-05-01 | 2024-10-31 | Not competed |
| [70B03C23P00000166](https://www.usaspending.gov/award/CONT_AWD_70B03C23P00000166_7014_-NONE-_-NONE-) | Detention/jail space | Purchase order | — | 5 | $142,298.68 | $142,298.68 | $142,298.68 | 2023-05-01 | 2024-04-30 | Not competed |
| [70B03C24C00000054](https://www.usaspending.gov/award/CONT_AWD_70B03C24C00000054_7014_-NONE-_-NONE-) | Detention/jail space | Definitive contract | — | 7 | $857,297.98 | $857,297.98 | $1,175,318.50 | 2024-07-09 | 2028-06-30 | Not competed |
| [70B03C24P00000592](https://www.usaspending.gov/award/CONT_AWD_70B03C24P00000592_7014_-NONE-_-NONE-) | Detention/jail space | Purchase order | — | 3 | $31,955.33 | $31,955.33 | $31,955.33 | 2024-09-26 | 2024-12-05 | Not competed under SAP |
| [70B03C25P00000029](https://www.usaspending.gov/award/CONT_AWD_70B03C25P00000029_7014_-NONE-_-NONE-) | Detention/jail space | Purchase order | — | 2 | $0.00 | $0.00 | $0.00 | 2024-12-01 | 2025-03-21 | Not competed |
| [HSBP1012C00101](https://www.usaspending.gov/award/CONT_AWD_HSBP1012C00101_7014_-NONE-_-NONE-) | Detention/jail space | Definitive contract | — | 4 | $119,646.94 | $646,781.94 | $737,205.00 | 2012-09-14 | 2021-03-13 | Not competed |
| [HSBP1015P00762](https://www.usaspending.gov/award/CONT_AWD_HSBP1015P00762_7014_-NONE-_-NONE-) | Detainee hygiene services | Purchase order | — | 7 | $2,711.07 | $2,711.07 | $52,711.07 | 2015-09-17 | 2020-09-16 | Not competed |
| [HSBP1016J00076](https://www.usaspending.gov/award/CONT_AWD_HSBP1016J00076_7014_HSBP1012A00025_7014) | Detention/jail space | BPA call | HSBP1012A00025 | 3 | $12,427.00 | $12,427.00 | $12,427.00 | 2015-10-01 | 2016-11-29 | Competed under SAP |
| [HSBP1016P00277](https://www.usaspending.gov/award/CONT_AWD_HSBP1016P00277_7014_-NONE-_-NONE-) | Detention/jail space | Purchase order | — | 13 | $833,449.72 | $833,449.72 | $845,956.19 | 2016-05-01 | 2020-04-30 | Not competed under SAP |
| [HSBP9861659693](https://www.usaspending.gov/award/CONT_AWD_HSBP9861659693_7014_-NONE-_-NONE-) | Detention/jail space | Definitive contract | — | 1 | $16,401.28 | $16,401.28 | $16,401.28 | 2016-04-01 | 2016-04-30 | Not competed |

Current award-level obligations across the ten records total **$3,129,104.54**, compared with **$2,601,969.54** in net actions inside the 2015–2026 period. The difference is principally the pre-2015 activity on `HSBP1012C00101`; it is a measurement-window difference, not a contradiction.

The largest current CBP record, `70B03C24C00000054`, is especially well corroborated. USAspending describes it as “DETENTION SPACE FOR MIGRANTS,” reports one offer, and identifies a $857,297.98 obligation and $1,175,318.50 base-and-all-options value. The live SAM Contract Awards API returned seven modifications and independently identifies:

- contracting office: `BORDER ENFORCEMENT CONTRACTING DIVISION`;
- funding office: `US BORDER PATROL`;
- place of performance: La Villa, Hidalgo County, Texas;
- PSC/NAICS: `X1FF — LEASE/RENTAL OF PENAL FACILITIES` and `922140 — CORRECTIONAL INSTITUTIONS`;
- competition: `NOT COMPETED`, `ONLY ONE SOURCE`, follow-on-contract authority;
- solicitation: `70B03C24Q00000075`.

An exact live SAM Opportunities API search for that solicitation returned no result. That is a solicitation-document gap, not evidence that no procurement notice or justification ever existed.

## ICE program context

The CSV classifies ICE actions from official descriptions and award metadata so the DHS-wide inventory is usable, but those program labels are analytical categories rather than official account totals. The classifications are: detention services; ISAP/electronic monitoring; family case management; skip tracing; transportation/removal services; and other/unresolved. An award can span more than one class when later modifications changed the described work, so program-level award counts can overlap.

The action-level sums are:

| ICE analytical program class | Actions | Net action obligations |
|---|---:|---:|
| Detention services | 1,016 | $3,884,198,529.73 |
| ISAP/electronic monitoring | 161 | $2,094,008,396.27 |
| Other/unresolved | 114 | $240,231,929.15 |
| Skip tracing | 5 | $87,985,925.00 |
| Transportation/removal services | 10 | $37,973,046.79 |
| Family case management | 56 | $9,699,432.14 |

These classes refine the action inventory; they do not replace award-level obligation figures elsewhere in the investigation and should not be compared to GEO corporate revenue without a separate reconciliation.

## Non-contract and indirect coverage

Separate USAspending assistance/grant searches for every UEI returned zero awards. This supports a bounded statement that no federal assistance award was located under those identifiers; it does not cover grants to unrelated intermediaries.

The repository's USAspending subaward command could not produce a reliable result. Fourteen different UEI/DHS searches returned the same unrelated 100-row set, showing that the recipient and agency filters were ignored or mis-serialized. Therefore this report makes **no affirmative or negative subcontract conclusion** from that endpoint. The failure is logged as papercut #827 and high-priority infrastructure request #154. HigherGov returned zero subcontract records for the parent, B.I. Incorporated, and GEO Care Services UEIs, but HigherGov is secondary and that three-UEI result is incomplete; it does not cure the primary-source gap.

The investigation already has dedicated workstreams for other indirect routes:

- lead #57695: identify ICE facilities hidden behind IGSAs and pass-through entities;
- lead #57836: trace GEO's ICE air-transportation subcontract and prime award;
- lead #57693: complete canonical recipient/alias and UEI/CAGE resolution.

Those routes are outside the bounded direct-prime action result here.

## Source reconciliation and audit notes

1. **USAspending is canonical for the action ledger.** The CSV preserves the official award ID, modification, action date, recipient, action obligation, cumulative award fields, office labels, competition fields, PSC/NAICS, and official award URL.
2. **SAM is an independent current-record check, used sparingly.** The repaired live Contract Awards query corroborated the most current CBP award. The March 2026 public extract supplied the current entity registrations. No secret or API key is stored in any artifact.
3. **HigherGov is secondary only.** Exact PIID lookups matched nine of the ten CBP records and missed BPA call `HSBP1016J00076`. Its results were not used to establish action totals or negative coverage.
4. **Component labels were tested for substance.** The CBP results have CBP at the awarding and funding sub-tier and operational Border Patrol/Field Operations funding offices; they are not DHS-wide administrative cross-servicing labels. No other DHS sub-tier appeared in the corrected direct-prime universe.
5. **Award/action and ceiling/value fields remain separate.** A transaction obligation is an action flow; cumulative award obligation is a current award stock; base-and-all-options is a potential value. None is automatically a payment, guaranteed minimum, or revenue figure.
6. **No Tier-2 causal overlay was performed.** Findings from the relationship-map workstream may later be aligned with this dated ledger, but this scan neither tests nor asserts influence.

## Durable outputs

- `investigations/geo-group/reports/2026-07-13-dhs-wide-geo-procurement-scan.md`
- `investigations/geo-group/reports/2026-07-13-dhs-wide-geo-award-actions.csv`
- `investigations/geo-group/reports/2026-07-13-dhs-wide-geo-component-summary.json`

Audited database findings: #12530 (current CBP award), #12531 (corrected DHS universe), #12532 (administration-period timing), #12533 (bounded component/assistance negative), and #12534 (recipient-name gaps). Each evidence row has an exact contiguous source excerpt, and all five findings were verified by `geo-dhs-procurement-wave3`.

Primary corporate source: [GEO Group 2025 Exhibit 22 guarantor list](https://www.sec.gov/Archives/edgar/data/923796/000119312526071747/geo-ex22_1.htm). Primary procurement sources: [USAspending Award Search](https://www.usaspending.gov/search) and [SAM.gov Contract Awards API](https://sam.gov/data-services/Contract%20Awards/api). As-of date: 2026-07-13.
