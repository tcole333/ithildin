# GEO direct ICE prime-award and vehicle universe

**As of:** 2026-07-13  
**Leads:** #57689 and #57697  
**Scope:** The GEO Group parent, B.I. Incorporated, GEO Transport, GEO Care Services, Correctional Services Corporation, Cornell Companies, GEO Secure Services, and GEO Reentry Services. This report covers direct ICE prime instruments. County, parish, state, and public-authority IGSAs where GEO operates below the public prime are outside the monetary totals.

## Result

The official USAspending parent-UEI reconstruction corrects finding #12403. It returns **228 unique direct ICE awards** and **$7,774,205,537.65 in cumulative net award obligations**, not 202 awards / $7.749 billion. The earlier name-only method omitted 26 awards and $24,998,972.94 attributed to GEO Care Services, Cornell Companies, and Correctional Services Corporation.

HigherGov adds **28 pre-2007 legacy instruments** and **$121,970,964.53** not returned by the official award search. The resulting **256-instrument / $7,896,705,593.45** figure is a useful working universe, but the 28-row legacy supplement remains secondary-source evidence until validated against primary FPDS/SAM archives. One overlapping award, `70CDCR24FR0000038`, also differs by $529,091.27 between the two sources. Accordingly:

- **Primary baseline:** 228 USAspending awards / $7.774 billion.
- **Provisional full-history baseline:** 256 HigherGov-reconciled instruments / $7.897 billion.
- Neither figure is revenue, an IDV ceiling, outlays, payments, annual run rate, guaranteed spending, or remaining contract value.

| Legal recipient | Primary USAspending awards | Primary obligations | Provisional instruments | HigherGov obligations |
|---|---:|---:|---:|---:|
| The GEO Group, Inc. | 173 | $5,248,298,699.21 | 193 | $5,357,192,755.01 |
| B.I. Incorporated | 27 | $2,485,749,878.19 | 27 | $2,485,749,878.19 |
| GEO Care Services, LLC | 10 | $19,003,220.26 | 10 | $19,003,220.26 |
| GEO Transport, Inc. | 2 | $15,157,987.29 | 2 | $15,157,987.29 |
| Correctional Services Corporation | 3 | $5,959,800.50 | 11 | $19,565,800.50 |
| Cornell Companies, Inc. | 13 | $35,952.20 | 13 | $35,952.20 |
| **Total** | **228** | **$7,774,205,537.65** | **256** | **$7,896,705,593.45** |

GEO Secure Services (`JLG3JBCL4CC7`) and GEO Reentry Services (`CLKXSJLN8EN1`) returned no direct ICE contracts or IDVs in bounded USAspending and HigherGov queries. Secure Services has Department of Justice/US Marshals activity, so this is an ICE-specific negative, not a no-federal-business conclusion.

## Award instruments versus action rows

The 228 primary awards expand into **1,864 USAspending ICE transaction/action rows** with a net `Transaction Amount` sum of **$7,542,303,243.21**. Every action is preserved separately with its award ID, modification number, action date, recipient UEI, PSC, NAICS, and description.

The action sum is **$231,902,294.44 below** the award-level cumulative obligation total. The action endpoint begins on 2007-10-01 while the award set contains earlier instruments, so this is an archive/API coverage difference—not evidence of missing payments, fraud, unreported revenue, or unexplained deobligation. Award-level obligations and transaction sums must not be substituted for each other.

SAM's current Contract Awards service is also action/modification-oriented. A prior live parent-UEI query recorded on lead #57697 reported 4,599 rows across all agencies, not 4,599 ICE contracts. The current run reached the basic 10-request daily quota before pagination; SAM is therefore a coverage cross-check, not the normalized row source in this report.

## Vehicle and order families

HigherGov returned **51 ICE IDVs** across the verified entity set. Forty-seven IDVs link to **219** normalized orders or calls. Thirty-three instruments are standalone, while four parent-referenced awards do not resolve to an IDV in the entity result set: `15M40018DA3500001` (two awards), `GS07F0518N`, and legacy `ACD8C0006`.

Largest resolved order families by cumulative obligations are:

| Parent IDV | Orders/calls | Obligations | Function |
|---|---:|---:|---|
| `70CDCR20D00000011` | 5 | $1,448,645,184.92 | ISAP IV |
| `70CDCR20D00000009` | 10 | $815,613,686.19 | Los Angeles AOR / Adelanto family |
| `HSCEDM15D00015` | 11 | $710,388,399.60 | Tacoma/Seattle detention and transport predecessor |
| `HSCEDM14D00004` | 6 | $643,009,491.02 | ISAP predecessor family |
| `HSCEDM17D00009` | 11 | $371,951,105.80 | Montgomery/Houston family |
| `70CDCR20D00000008` | 7 | $354,568,632.66 | San Francisco AOR / Mesa Verde / Golden State |
| `HSCEDM12D00001` | 8 | $344,745,466.35 | South Texas predecessor |
| `70CDCR20D00000012` | 6 | $334,821,783.83 | South Texas current family |
| `HSCEDM11D00003` | 11 | $314,480,954.48 | Aurora predecessor |
| `70CDCR22D00000001` | 5 | $274,099,959.58 | Aurora current family |

The description/date record supports candidate succession chains—ISAP IV to ISAP V (`70CDCR25D00000062`), South Texas predecessor to `70CDCR20D00000012`, Aurora predecessor to `70CDCR22D00000001`, Broward predecessor to `70CDCR21D00000004`, and Tacoma predecessor to `70CDCR26D00000026`. These are **descriptive succession hypotheses**, not proof that ICE formally designated every newer instrument as a bridge or recompete. Solicitation, acquisition-plan, and award-decision files are needed for that conclusion.

### New 2026 vehicles and orders

- `70CDCR26D00000049` is a July 9, 2026 Big Horn Contract Detention Facility IDV with a reported **$528,678,643.44 potential value**, one offer, and `Not Competed` / `Sole Source` fields. No linked order had appeared in the HigherGov contract result set by July 13. Potential value is not obligated or guaranteed money.
- `70CDCR26FC0000004`, a $300,000 Robert A. Deyton detention-bed BPA call, was signed July 9 with a reported performance start of July 23.
- `70CDCR26D00000026` had a linked $39.0 million Tacoma/Northwest order by May 21.
- `70CDCR25D00000062` had a $108.3 million ISAP V order; `70CDCR26D00000005` had a $1.625 million B.I. skip-tracing order. These identifiers are linked for the dedicated B.I./ISAP agent rather than re-analyzed here.

Potential IDV values are deliberately not summed: vehicle ceilings can overlap with order values, options, and predecessor/successor instruments.

## Competition and subcontract reporting

At the prime-instrument level, offer counts are reported for 149 of 256 instruments: 115 report one offer, 16 report three, 9 report two, and the remainder report other counts. Another 107 lack an offer count. A one-offer or non-competed field is a procurement fact, not by itself evidence of restrictive specifications, improper steering, or a defective justification.

All **228 official USAspending award-detail records report `subaward_count = 0`** and no positive `total_subaward_amount`. HigherGov returned zero partnership rows for GEO parent awardee key `10000076`. These bounded negatives do not establish that GEO used no vendors or subcontractors. Primary ICE instruments separately identify GEO below Charlton County, Evangeline Parish Sheriff, LaSalle Economic Development District, Clearfield County, and Karnes County in the IGSA channel. That public-prime/private-operator structure is documented in the existing [IGSA systemic analysis](systemic-analysis-ice-igsa-pass-through-2026-07-13.md) and must not be double-counted as direct GEO prime awards.

## Source reconciliation

| Source | Unit returned | Useful coverage | Limitation in this run |
|---|---|---|---|
| USAspending | Unique award rows, award details, and separate transaction rows | Official primary baseline; child hierarchy under parent UEI; offices, PSC/NAICS, competition and subaward counts | Award search omits 28 pre-2007 legacy records; transaction endpoint begins in 2007 and does not sum to the award-level total |
| HigherGov | Unique contracts and IDVs | Legacy FPDS coverage, parent-IDV relationships, potential/current values, competition fields, current links | Secondary aggregator; exact parent UEI does not expand every child, requiring separate verified-child queries; one overlapping amount differs from USAspending |
| SAM Contract Awards | Action/modification rows | Current federal action cross-check | Prior 4,599 count spans all agencies; current basic quota prevented full pagination and unique-instrument reconstruction |

USAspending and HigherGov agree on the 228 primary award IDs. HigherGov adds 28 legacy IDs; USAspending adds none that HigherGov lacks in the 228-row cohort. USAspending reports 10 additional parent-hierarchy CBP awards / $3,129,104.54, but they are excluded from all ICE totals here. Non-ICE Department of Justice, Bureau of Prisons, US Marshals, State Department, USCIS, and other records were also excluded.

## Durable data

- `direct-ice-prime-award-universe-2026-07-13.csv` — 256 normalized prime instruments.
- `direct-ice-prime-award-universe-2026-07-13.json` — same universe with null-preserving types and source URLs.
- `direct-ice-usaspending-action-rows-2026-07-13.csv` — 1,864 official ICE action/modification rows.
- `direct-ice-idv-task-order-families-2026-07-13.csv` — 51 normalized IDVs and linked child PIIDs.
- `direct-ice-prime-award-reconciliation-2026-07-13.json` — machine-readable counts, totals, and coverage caveats.

Primary source: [USAspending API and award pages](https://www.usaspending.gov/). Supplemental source: [HigherGov](https://www.highergov.com/). SAM service documentation: [GSA Contract Awards API](https://open.gsa.gov/api/contract-awards/).

## Remaining gaps and stop conditions

The direct-prime universe, action pagination, award details, IDV links, competition fields, subaward counts, entity cross-checks, and SAM bounded check are complete for the named scope. Remaining work is narrower:

1. Retrieve primary FPDS/SAM archive records for the 28 HigherGov-only pre-2007 instruments.
2. Resolve parent IDVs `15M40018DA3500001`, `GS07F0518N`, and `ACD8C0006` from their owning-agency records.
3. Obtain acquisition plans, justifications, source-selection records, and award decisions before classifying the candidate succession families as bridges or recompetes.
4. Obtain first-tier subcontract reports or contracting files because public award-detail `subaward_count` fields are uniformly zero and do not resolve operating vendors.

These gaps do not change the corrected 228-award official baseline, but they prevent calling the 256-row full-history working set fully primary-validated.
