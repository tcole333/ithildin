# DHS Procurement Census — Phase 0 (window 2025-01-20 .. 2026-07-28)

Census agent output, 2026-07-28. All artifacts in `/tmp/osint-GWLtvuxV/work-census/`. No database writes were made; investigation.db untouched.

Confidence labels: **CONFIRMED** = recomputed from cached primary bulk data held in this work dir; **UNCONFIRMED** = single API read or interpretation not re-verified against a second source.

## 1. Method and reconciliation

### API calls used (probe-first log)
- `POST https://api.usaspending.gov/api/v2/bulk_download/awards/` — filters: `prime_award_types` = A,B,C,D + IDV_A,IDV_B,IDV_B_A,IDV_B_B,IDV_B_C,IDV_C,IDV_D,IDV_E; `agencies` = awarding/toptier/'Department of Homeland Security'; `date_type=action_date`. **API limit discovered: date_range must be within 1 year** (HTTP 400 otherwise), so the window ran as two jobs: 2025-01-20..2026-01-19 (57,542 rows) and 2026-01-20..2026-07-28 (25,698 rows).
- `GET https://api.usaspending.gov/api/v2/download/status?file_name=...` — polled ~30-60s, sequential.
- Two hedge jobs (window-1 split into 6-month halves) were submitted when the 12-month job passed ~20 min generation, per fallback policy; the 12-month job finished first, so the hedge zips were **never downloaded** and are unused.
- Enrichment (S4/S5): `POST /api/v2/search/spending_by_transaction/` sequential with 0.4s spacing and exponential backoff; local `datasets/sam.db` (read-only) for registration dates.
- The paged `spending_by_transaction` fallback was NOT used for the census itself: that endpoint does not expose competition fields, ceilings, or cumulative columns, and would have produced a materially degraded census.

### Verified column semantics (probe file, CONFIRMED empirically)
- `federal_action_obligation` and `base_and_all_options_value` are **per-action deltas**.
- `total_dollars_obligated` and `potential_total_value_of_award` are **cumulative as of that action** (termination example: delta -39,600 -> cumulative 0). This allows full ceiling-ledger reconstruction including pre-window baselines.
- **Bulk-file column swap bug**: `extent_competed_code` holds the *label* and `extent_competed` holds the one-letter code; same swap for the `solicitation_procedures` pair. Set-aside and other-than-full-and-open pairs are normal. Normalized at load with a length heuristic (`build_census.py:normalize_pair`).
- AWARD and IDV rows arrive in one CSV, discriminated by `award_or_idv_flag`.

### Pipeline reconciliation (CONFIRMED)
| stage | count |
|---|---|
| logical rows in All_Contracts_PrimeTransactions_2026-07-29_H02M15S56_1.csv (csv module, not wc -l) | 57,542 |
| logical rows in All_Contracts_PrimeTransactions_2026-07-29_H02M15S59_1.csv (csv module, not wc -l) | 25,698 |
| transactions loaded (dedupe on contract_transaction_unique_key) | 83,240 |
| duplicate transactions across window boundary | 0 |
| distinct awards touched in window | 45,589 |
| awards passing keep rule (window obligations >= $250K OR current ceiling >= $250K) | 16,722 |
| awards dropped under threshold | 28,867 |
| mod-ledger rows for kept awards (census-transactions.csv) | 41,400 |

Window net obligations, full universe: **$76,596,473,325**; kept awards cover $75,858,618,179 (99.0%).

### Sanity check against expected magnitude (CONFIRMED)
DHS historical contract spend is ~$25-35B/yr; this window annualizes to ~$50.5B/yr. The excess is fully attributable to identified mega-programs, dominated by CBP border-barrier construction task orders of $0.5-2.6B each (Fisher Sand & Gravel, Barnard, BCCG JV, Southwest Valley, SLS, Spencer, Cochrane, AMI Metals bulk steel) plus USCG Arctic cutter letter contracts (Bollinger, Rauma, Davie). Not a data artifact.

### Totals by component (CONFIRMED, full universe)
| component | actions | window net obligations |
|---|---:|---:|
| U.S. Customs and Border Protection | 9,720 | $42,051,786,550 |
| U.S. Coast Guard | 33,915 | $11,025,205,553 |
| U.S. Immigration and Customs Enforcement | 6,342 | $8,928,775,632 |
| Office of Procurement Operations | 8,810 | $6,500,142,498 |
| Transportation Security Administration | 3,888 | $3,233,643,364 |
| U.S. Citizenship and Immigration Services | 2,281 | $2,019,117,722 |
| Federal Emergency Management Agency | 11,731 | $1,369,145,226 |
| U.S. Secret Service | 2,706 | $760,185,703 |
| Federal Law Enforcement Training Center | 3,324 | $621,279,560 |
| Office of the Inspector General | 523 | $87,191,516 |

### Canonical-numbers validation (CONFIRMED — exact reproduction)
Method law applied: obligations summed from child task orders, never read off the parent IDV; ceilings reported as ceilings.

| target (wave-3 brief) | expected | census reproduces |
|---|---|---|
| Skip tracing 26-SOL-DCR-01 IDIQ count | 14 | **14** (PIIDs 70CDCR26D00000003..21 subset) |
| Skip tracing combined ceiling | $1,442,909,640 | **$1,442,909,640.02** |
| Skip tracing obligations via child DOs | $19,032,607 | **$19,032,607.00** (14 child orders) |
| UAC 70CDCR26R00000015 IDIQ count | 18 (D00000030-47) | **18, exact PIID match** |
| UAC combined ceiling | ~$20,583,928,204 | **$20,583,928,204.05** |
| UAC strict new-family obligations | $85,376,317 | **$85,376,317.14** (18 child orders) |
| UAC initiative incl. MVM FR0000052 (FY24 vehicle 70CDCR24D00000002) | $86,822,317 | **$86,822,317.14** ($1,446,000.00 MVM) |

## 2. S1 — Competition base rates (closes the wave-3 denominator gap)

Transaction-dollar-weighted, full universe (83,240 actions, $76.6B). Bucketing: competed = A/D/F/CDO; not-competed = B/C/G/E/NDO (FPDS convention; E=follow-on counted not-competed).

- **DHS-wide baseline (CONFIRMED)**: competed 61,286 actions (73.6%), $66,633,782,260 (87.0%); not-competed 21,230 actions (25.5%), $9,957,147,040 (13.0%).
- Per-component and per-month tables: `s1-competition-by-component.csv`, `s1-competition-by-month.csv`. Monthly not-competed dollar share ranges 2.9%-27.6%; peak months: Oct 2025 (27.6%), Dec 2025 (22.5%, wall + Arctic cutter letter contracts), Jul 2026 (20.1%). June 2025 shows net negative not-competed dollars (-$132M) = deobligation wave.

### One-bid base rate (award level, CONFIRMED)
- Born-in-window awards: $50.28B window obligations; offers known for $41.06B (81.7%); **one-offer dollars $10.97B = 21.8% of all / 26.7% of known**. Offers-missing dollars 18.3%.
- All census-universe awards: one-offer = 19.8% of all / 24.4% of known-offer dollars.
- Implication for wave-3: the GEO-cohort ~25% full-and-open/one-offer rate is **typical of DHS-wide dollars, not an outlier**.

### Other-than-full-and-open authorities (award level, window dollars; CONFIRMED)
| authority | awards | window dollars |
|---|---:|---:|
| URGENCY (FAR 6.302-2) | 138 | $29,200,614,271 |
| PUBLIC INTEREST (FAR 6.302-7) | 5 | $3,347,440,466 |
| ONLY ONE SOURCE-OTHER (FAR 6.302-1 OTHER) | 1,272 | $2,569,366,046 |
| AUTHORIZED BY STATUTE (FAR 6.302-5(A)(2)(I)) | 1,420 | $1,444,041,218 |
| FOLLOW-ON CONTRACT (FAR 6.302-1(A)(2)(II/III)) | 57 | $483,777,575 |
| SAP NON-COMPETITION (FAR 13) | 431 | $303,493,643 |
| NATIONAL SECURITY (FAR 6.302-6) | 2 | $176,677,500 |
| BRAND NAME DESCRIPTION (FAR 6.302-1(C)) | 52 | $109,489,768 |

**Headline**: FAR 6.302-2 URGENCY stamps sit on 138 awards carrying **$29.2B window obligations (38% of all DHS window dollars)** — dominated by CBP border-barrier task orders (extent code D, 'full and open after exclusion of sources', negotiated). Urgency-as-default for a multi-year construction program is the single biggest structural competition fact in the census.

## 3. S2 — 100%-win multiple-award families

362 multi-awardee solicitation families; **38 families where modal offers == distinct awardees** (everyone who offered won). Full list: `s2-families.csv`. Top by exposure:

| solicitation | awardees | offers | family ceilings | child-order window obligations | component | note |
|---|---:|---:|---:|---:|---|---|
| 70T05025R5900N002 | 21 | 21 | sum $111,300,030,000 (max member $5,300,000,000) | $75,000 | Transportation Security Administration | AMERICAN EAGLE PROTECTIVE SERVICES CORP;AVIATION SECURITY MA |
| 70CDCR26R00000015 | 18 | 18 | sum $20,583,928,204 (max member $3,105,250,000) | $85,376,317 | U.S. Immigration and Customs Enforcement | ALPHA RECOVERY LLC;APPLIED INTELLECT LLC;CADUCEUS INC.;COMPA |
| 70FB7020R00000002 | 2 | 2 | sum $1,080,504,495 (max member $611,384,311) | $0 | Federal Emergency Management Agency | CEVA FREIGHT LLC;CROWLEY GOVERNMENT SERVICES, INC. |
| 70CDCR24R00000012 | 2 | 2 | sum $980,614,468 (max member $788,696,563) | $83,347,673 | U.S. Immigration and Customs Enforcement | CORECIVIC, INC.;THE GEO GROUP, INC. |
| 70RDA224Q00000073 | 5 | 5 | shared ~$99,998,042 | $32,851,672 | Office of Procurement Operations | DELOITTE & TOUCHE LLP;ERNST & YOUNG LLP;GUIDEHOUSE INC.;KEAR |
| 70FB7021R00000004 | 2 | 2 | sum $469,044,070 (max member $279,206,605) | $0 | Federal Emergency Management Agency | CEVA FREIGHT LLC;MATSON LOGISTICS, INC. |
| 70FB7021R00000005 | 2 | 2 | sum $237,462,865 (max member $118,731,433) | $9,508,500 | Federal Emergency Management Agency | DEWITT COMPANIES LTD., LLC;MATSON LOGISTICS, INC. |
| 70Z08524RIBCT0006 | 5 | 5 | shared ~$26,271,876 | $7,156,138 | U.S. Coast Guard | BAYONNE DRYDOCK & REPAIR CORP.;GMD SHIPYARD CORP.;J. GOODISO |
| 70FB7021R00000015 | 2 | 2 | sum $87,545,751 (max member $48,173,796) | $-4,856 | Federal Emergency Management Agency | IEM INTERNATIONAL, INC.;MAG DS CORP |
| 70Z08523RIBCT0002 | 6 | 6 | sum $73,496,455 (max member $18,581,144) | $3,089,669 | U.S. Coast Guard | BAYONNE DRYDOCK & REPAIR CORP.;COLONNA'S SHIP YARD, INCORPOR |
| 70Z08026R21303B00 | 2 | 2 | sum $38,487,598 (max member $19,890,447) | $0 | U.S. Coast Guard | DEFENSE MARITIME SOLUTIONS, INC.;WILDCAT PROPELLERS, INC |
| 70LGLY24BGLB00003 | 5 | 5 | sum $34,200,000 (max member $18,000,000) | $11,724,772 | Federal Law Enforcement Training Center | GLOBAL ORDNANCE LLC;HORNADY MANUFACTURING COMPANY;OLIN WINCH |
| 70Z08421RBHQ02400 | 2 | 2 | sum $31,729,697 (max member $17,176,435) | $13,237,522 | U.S. Coast Guard | COLUMBUS MCKINNON CORP;LISTER CHAIN & FORGE INC |
| 70Z04023Q62301B00 | 2 | 2 | sum $20,000,000 (max member $10,000,000) | $4,879,308 | U.S. Coast Guard | EASE PAINTING AND CONSTRUCTION, INC;SURFACE TECHNOLOGIES COR |
| 70T05023R7668N003 | 2 | 2 | sum $19,800,000 (max member $9,900,000) | $468,878 | Transportation Security Administration | AMERICAN BADGE INC;VH BLACKINTON & CO INC |
| HSFE70-13-R-0046 | 3 | 3 | sum $11,948,500 (max member $5,999,500) | $0 | Federal Emergency Management Agency | ATLANTIC DIVING SUPPLY, INC.;PROPAC, INC.;TRIBUTE CONTRACTIN |
| 70Z03822RB2000007 | 2 | 2 | sum $10,371,604 (max member $7,718,151) | $1,600,924 | U.S. Coast Guard | LUFTHANSA TECHNIK COMPONENT SERVICES LLC;SAFRAN ELECTRONICS  |
| 70LGLY24BGLB00002 | 3 | 3 | sum $7,450,000 (max member $4,000,000) | $1,890,767 | Federal Law Enforcement Training Center | GENERAL DYNAMICS ORDNANCE AND TACTICAL SYSTEMS - SIMUNITION  |
| 70RFP322QEH000017 | 2 | 2 | sum $5,713,176 (max member $5,049,580) | $0 | Office of Procurement Operations | BOLD TECHNOLOGIES LTD.;NATIONAL LAW ENFORCEMENT TELECOMMUNIC |
| 70Z03825QE0000041 | 2 | 2 | sum $4,556,631 (max member $4,547,931) | $0 | U.S. Coast Guard | NODE.DIGITAL LLC;TESTVONICS INC |
| 70Z02324QCGRC0002 | 2 | 2 | sum $4,522,864 (max member $4,060,486) | $0 | U.S. Coast Guard | EDJJ SOLUTIONS LLC;LEMPUGH INC |
| 70T04023BAA7573N001 | 2 | 2 | sum $4,448,146 (max member $3,753,695) | $0 | Transportation Security Administration | LIBERTY DEFENSE TECHNOLOGIES, INC.;ROHDE & SCHWARZ USA, INC. |
| 70T01024Q7668N001 | 2 | 2 | sum $3,135,305 (max member $1,581,305) | $0 | Transportation Security Administration | THE UNDERDOGS UNLIMITED, LLC;TMC-TELESOLV |
| 70RSAT22R00000005 | 3 | 3 | sum $2,999,720 (max member $999,993) | $0 | Office of Procurement Operations | MAKEL ENGINEERING, INC.;N5 SENSORS INC;NOVATEUR RESEARCH SOL |
| 70Z08521QP4502000 | 2 | 2 | sum $2,214,749 (max member $1,656,871) | $306,552 | U.S. Coast Guard | GLOBAL FIRE AND SAFETY, INC.;JAG INDUSTRIAL SERVICES, INC |
| 70Z08521QP4502100 | 2 | 2 | sum $1,605,918 (max member $1,225,223) | $178,625 | U.S. Coast Guard | GLOBAL FIRE AND SAFETY, INC.;JAG INDUSTRIAL SERVICES, INC |
| 70SBUR25Q00000059 | 2 | 2 | sum $1,259,160 (max member $1,259,160) | $0 | U.S. Citizenship and Immigration Service | PANAMERICA COMPUTERS, INC.;WESTWIND COMPUTER PRODUCTS, INC. |
| 70T05024Q7670N003 | 2 | 2 | sum $858,200 (max member $849,200) | $0 | Transportation Security Administration | JC HOSPITALITY LLC;OLIN WINCHESTER LLC |
| 70Z03823QB2000005 | 3 | 3 | sum $722,082 (max member $293,454) | $73,745 | U.S. Coast Guard | AERO TECHNICAL COMPONENTS, INC.;ALA - ADVANCED LOGISTICS FOR |
| 70Z03824QK0000002 | 2 | 2 | sum $609,636 (max member $441,145) | $237,311 | U.S. Coast Guard | EXACT MACHINE SERVICE, INC.;PHILLIPS CORPORATION |
| 70Z08026QPBPL0035 | 3 | 3 | sum $550,571 (max member $247,440) | $0 | U.S. Coast Guard | BENJAMIN MILLER;GECKO ROBOTICS, INC.;MARINE GROUP BOAT WORKS |
| 70Z03821QJ0000013 | 2 | 2 | sum $516,461 (max member $271,914) | $215,162 | U.S. Coast Guard | FRACCARO INDUSTRIES INC;SIKORSKY AIRCRAFT CORPORATION |
| N6817120R0001 | 4 | 4 | sum $466,990 (max member $200,000) | $0 | U.S. Coast Guard | MLS-MULTINATIONAL LOGISTIC SERVICES LIMITED;PARSH MARINE (S) |
| 67100PR230000068 | 2 | 2 | sum $168,964 (max member $96,964) | $0 | U.S. Coast Guard | BINARY EXCHANGE TECHNOLOGIES LLC;MAIN LINE COMMERCIAL POOLS  |
| 70LGLY25QGLB00073 | 2 | 2 | sum $131,993 (max member $114,659) | $0 | Federal Law Enforcement Training Center | OFFICE FURNITURE GROUP, LLC;SUPPLYSOURCE DC, LLC |
| 2124404Y6132807001 | 2 | 2 | sum $109,215 (max member $93,725) | $0 | U.S. Coast Guard | JO-KELL INC.;MULTIMARINE SERVICES, INC. |
| 70RFPW23QW8000005 | 2 | 2 | sum $35,528 (max member $28,902) | $0 | Office of Procurement Operations | CANON FINANCIAL SERVICES, INC.;CANON U.S.A., INC. |
| 1131789 | 2 | 2 | sum $29,816 (max member $29,816) | $0 | U.S. Immigration and Customs Enforcement | ANACAPA MICRO PRODUCTS, INC.;C & C INTERNATIONAL COMPUTERS & |

Key families:
- **TSA 70T05025R5900N002 (UNCONFIRMED interpretation, CONFIRMED records)**: 21 offers -> 21 IDIQs awarded 2026-05-28, aviation guard services; every IDIQ stamps an identical $5,300,000,000 ceiling -> read as a ~$5.3B shared program ceiling, NOT $111B. Obligations so far: six $5,000 minimum-guarantee orders ($75K). Structurally identical to the UAC 18/18 pattern but larger headcount, mixing Leidos with small guard firms. Same corroboration caveat as UAC: each record self-stamps 21 offers.
- **ICE UAC 70CDCR26R00000015**: 18/18 reproduced exactly (see canonical block).
- **ICE 70CDCR24R00000012**: CoreCivic + GEO, 2 offers/2 awards, $83.3M child obligations in window — the detention duopoly both winning its own competition.
- **OPO 70RDA224Q00000073**: 5/5 = Deloitte, EY, KPMG, Guidehouse, Kearney financial-audit BPAs — the benign face of everyone-won (professional-services pools). Kearney holds $30.2M of $32.9M ordered.
- **FEMA logistics pairs** (70FB7020R00000002 CEVA/Crowley $1.08B ceilings; 70FB7021R00000004 CEVA/Matson; 70FB7021R00000005 DeWitt/Matson): 2/2 dual-award pools, weak signal individually.

**S2 method gap (important negative)**: the largest everyone-won family in the census is INVISIBLE to solicitation grouping — the 11-vendor CBP border-barrier IDIQ cohort 70B01C26D00000003-13 (awarded 2025-10-31) carries a **blank solicitation_identifier** in FPDS. Reconstructed by PIID block: 11 offers received -> 11 awards, extent D, URGENCY authority, $5B ceiling each ($56.6B recorded total; SLS later raised to $6.636B), **$25.8B child-order obligations in under 9 months**. Members: SLS, Granite, BCCG JV, Barnard, Southwest Valley, Cochrane, Sundt, Posillico, Coastal Environmental, Fisher, Spencer. (CONFIRMED from ledger.)
- 57 families show MORE awardees than modal offers — dominated by per-order offer stamping semantics (e.g., FEMA manufactured-home lease pools where each lease reports its own 1 offer), a data-semantics caveat, not a fraud signal (list in s2-families.csv `awardees_exceed_offers`).

## 4. S3 — Ceiling forensics from the mod ledger

Flags: {'capacity_parking_ceiling50M_le5pct': 523, 'ceiling_growth_gt2x_in_window': 315, 'ceiling_cut_ge_10M': 118, 'ceiling_growth_gt2x_from_initial': 165}. Full list: `s3-ceiling-flags.csv` (ceiling deltas derivable per-mod in census-transactions.csv: ceiling_before/after columns).

Top exemplars (CONFIRMED from ledger; interpretations UNCONFIRMED):
- **Obligations exceed recorded ceiling — Fisher Sand & Gravel IDIQ 70B01C26D00000012**: child task orders total **$12,675,318,052 against a parent ceiling still recorded at $5,000,000,000 (2.54x)**. The IDV record was re-stamped $5B as late as 2026-03-15 while orders blew past it. Either FPDS ceiling maintenance failed or vehicle capacity was informally overridden. Barnard's sibling sits at 0.91 of ceiling; SLS at 0.36 after its raise to $6.636B. Single most acute record-integrity anomaly in the census.
- **TSA Screening Partnership Program coordinated raises**: HSTS0516DSPP906-913 (Covenant Aviation, Firstline, Jackson Hole Airport Board, PAE NSS, Technica, Trinity, VMD +) all raised in-window from $200-500M to an **identical $3.3B ceiling each** — a 6.6-16.5x jump across the entire privatized-screening vendor pool. Capacity for a major screening-privatization expansion, described as capacity: obligations flow later via orders.
- **Fisher order 70B01C26F00000017**: started 2025-11 at $55.8M ceiling, now **$2.83B obligated == ceiling (50x growth)** via 'ADDED CONSTRUCTION WORK' mods; sibling 70B01C25F00001112 went $574M -> $1.23B.
- **Salus Worldwide Solutions Corp 70RDA225FR0000018 (OPO, parent 70RDA225D00000005)**: 'Comprehensive Support to Removal Operations (CSRO)' citing **'E.O. Section 4(a)' in the description**; NAICS 481211 / PSC V119 (charter air). Born 2025-05-22 at $30M obligated / $38.9M ceiling; 23 mods later: **$697.7M obligated / $706.6M ceiling (18.2x)** by 2026-05-22. Same buy-inside-a-vehicle-then-grow shape wave-3 documented on skip tracing, at 8x the dollars.
- **CSI Aviation 70CDCR25FR0000022 (ICE Air)**: $119.8M -> $585.5M ceiling (4.9x); CSI window obligations total $1.394B.
- **Detention letter-contract churn**: GEO 70CDCR25D00000009 (North Lake, the wave-3 letter contract) x6.0 to $223.1M; CoreCivic 70CDCR25D00000010 x8.4 to $262.0M and 70CDCR25D00000008 x8.0 to $181.1M; GEO 70CDCR25D00000007 ceiling **cut -$421.9M** (2025-11-13) to $788.7M. Undefinitized instruments repricing massively in both directions.
- **Big cuts**: Mythics (OPO Oracle reseller BPA) -$620M; Eastern Shipbuilding OPC -$370.9M; PAE/USCIS -$362.1M; Huntington Ingalls -$241.7M; Leidos TSA -$32.5M.
- **Capacity parking (ceiling >= $50M, <=5% obligated, vehicle >= 180 days old)**: 523 awards. Top of list is a *legacy-stamp noise class* — 2013-era EAGLE II IDIQs each carrying a $22B shared-ceiling stamp with $0 window obligations (admin closeout actions only): treat as stale records, not live capacity. Live examples worth attention: skip-tracing family ($1.44B/1.3%), UAC family ($20.58B/0.4%), TSA guard MAIDIQ ($5.3B/<0.1%), CBP design-build family (see below).
- **CBP design-build family 70B01C26R00000007 (awarded 2026-05-11, age-gated out of parking flag)**: 10 IDIQs x **$10B each = $100B recorded ceiling capacity** (BL Harbert, Brasfield & Gorrie, Clark, ECC, Grunley, Hensel Phelps, Southwest Valley, Tutor Perini, Walsh Federal, Whiting-Turner), 22 offers -> 10 awards, full-and-open two-step, minimum guarantees only so far. The largest new capacity block in DHS; watch which vendors receive the first orders.

## 5. S4 — New entrants (bounded enrichment)

Coverage: 300 top-slice vendors enriched (window obligations >= $1M or ceiling >= $10M, cap 300); 0 API errors; 1 unresolved recipient-expansion cases (UEI text search returned only affiliates within page budget). SAM registration dates from local sam.db extract (snapshot ~2026-02; absence after that is NOT evidence of newness).

**22 vendors show no federal contract history before 2024-11-05** (USASpending transaction search, contracts+IDVs since 2007-10-01, client-side UEI match; assistance/grants also checked where zero). UNCONFIRMED beyond USASpending coverage (pre-2008 history invisible, name-change/UEI-reissue possible):

| vendor | UEI | window obligations | ceiling sum | SAM registered | SAM entity start | state |
|---|---|---:|---:|---|---|---|
| SLS FEDERAL SERVICES LLC | VLDKT27H2AG1 | $2,379,100,930 | $9,916,156,930 | 20200924 | 20200921 | TX |
| RAUMA MARINE CONSTRUCTIONS OY | RNHNMK7VCEL1 | $1,122,648,775 | $1,122,648,775 | 20250910 | 20140321 |  |
| DAVIE DEFENSE INC. | DYABDAZV92C1 | $957,006,922 | $3,500,000,000 | 20250521 | 20250428 | DE |
| SALUS WORLDWIDE SOLUTIONS CORP. | EA4VD72SB1W3 | $702,024,888 | $1,625,899,678 | 20230224 | 20230207 | WY |
| DAEDALUS AVIATION CORPORATION | KE7ZAT98UBM7 | $463,638,746 | $463,638,746 | 20240320 | 20240221 | DE |
| SAFE AMERICA MEDIA LLC | R64SJRYFDKM7 | $142,826,104 | $382,825,854 | 20250210 | 20250206 | DE |
| COMPASS UNITED | LB2PEHVPDGB2 | $8,916,302 | $2,342,452,057 | 20220729 | 20001002 | TX |
| SEPTIMO SOLUTIONS, LLC | SL5DUHMP9163 | $8,686,250 | $4,659,125,000 | 20240702 | 20230322 | VA |
| LEMOINE DISASTER RECOVERY LLC | C182PM2K1463 | $7,690,000 | $2,675,716,653 | 20171016 | 20171004 | TX |
| METRO EAST JOINT VENTURE LLC | CQBAWMPKSNY4 | $6,626,537 | $1,208,921,500 | 20230530 | 20230522 | TN |
| SECURITY INSIGHTS LLC | GS9LV7EPJQ74 | $5,507,232 | $2,928,296,704 | 20240904 | 20190613 | TX |
| MAVERICK STRATEGIES LLC | JEAMMN4L4GT1 | $5,494,679 | $1,210,856,480 | 20220613 | 20220531 | MD |
| SEVERANCE SECURITY SERVICES LLC | DKFGF41MVR41 | $4,770,000 | $1,137,000,000 |  |  |  |
| SAVVY PROFESSOR LLC | HHZZRGNWPL44 | $4,727,750 | $2,333,253,000 | 20260205 | 20240717 | VA |
| VEARY ENTERPRISES LLC | X7PTTJRDRJ73 | $2,033,613 | $1,141,877,010 | 20230411 | 20190507 | MD |
| CRITICAL RESPONSE STRATEGIES, LLC | ZDN8V5GKJ959 | $1,614,000 | $975,586,000 |  |  |  |
| MTAC INC | KNK9UFNFFMV6 | $0 | $5,300,000,000 | 20201030 | 20201009 | MD |
| NATI-NVE SUPPORT SERVICES, LLC | Z2HMYE5JUEN3 | $0 | $5,300,000,000 | 20250227 | 20250219 | MD |
| DATABRICKS FEDERAL LLC | HKJ3X29D3L59 | $0 | $1,000,000,000 | 20190131 | 20180724 | DE |
| WSP HDR, A JOINT VENTURE | ZTB1ZS168ZF3 | $0 | $1,000,000,000 | 20230619 | 20230501 | DE |
| COLLINS--MOTT MACDONALD-STV DHS AE JV | RCAWVU557T69 | $0 | $1,000,000,000 |  |  |  |
| M&N-STANTEC NATIONWIDE JV | PFFNTGHCMUG6 | $0 | $1,000,000,000 | 20230712 | 20230111 | WA |

5 top-slice vendors' SAM registrations date after 2024-11-05: RAUMA MARINE CONSTRUCTIONS OY (20250910); DAVIE DEFENSE INC. (20250521); SAFE AMERICA MEDIA LLC (20250210); SAVVY PROFESSOR LLC (20260205); NATI-NVE SUPPORT SERVICES, LLC (20250227).

Flag interpretations (award context CONFIRMED from census.db; entity readings UNCONFIRMED):
- **Daedalus Aviation Corporation** (DE, entity start 2024-02-21, SAM 2024-03-20): zero federal history before its OSAD aircraft contract. Sole-source (extent C, 1 offer, sol 70QS0326R00000009), URGENCY, $463.6M fully obligated.
- **Salus Worldwide Solutions Corp.** (WY, entity start 2023-02-07): zero federal history; then WON its own single-award CSRO IDIQ 70RDA225D00000005 ($915M ceiling, 4 offers, extent D + URGENCY, sol 70RDA225R00000018) and the $697.7M order under it, plus small ICE aviation orders. A 2-year-old Wyoming corp operating removal flights at $700M.
- **Safe America Media LLC** (DE, entity start 2025-02-06, SAM registered 2025-02-10 — 17 days after inauguration): zero federal history; holds 'NATIONAL EMERGENCY AT THE SOUTHERN BORDER: STRONGER BORDERS' ad-campaign task orders 1 and 4 ($62.8M + $65.0M, URGENCY) under multiple-award media IDIQ 70RDA225D00000004 ($240M ceiling, 3 offers) plus a $15M ICE media-buy order. Total $142.8M obligated / $382.8M ceilings. This is the DHS ad campaign as a procurement object.
- **Savvy Professor LLC** (VA, entity start 2024-07-17, SAM registered 2026-02-05): zero federal history; holds UAC IDIQ **70CDCR26D00000045 ($1.596B ceiling)** + $4.7M minimum-guarantee order. Concretely corroborates wave-3's thin-record UAC cohort concern, by name.
- **SLS Federal Services LLC** (TX, entity 2020): $2.38B obligated with zero pre-election federal history under this UEI — plausibly the SLSCO Ltd (Sullivan Land Services, Galveston TX wall incumbent) family under a newer entity/UEI; treat the 'new entrant' read as naming-structure artifact until ownership is traced. Same JV caveat for WSP HDR JV, Collins-Mott MacDonald-STV JV, M&N-Stantec JV, Metro East JV, Barnard Spencer JV (new JV shells of established firms).
- **Davie Defense Inc.** (DE 2025-04-28) and **Rauma Marine Constructions OY** (SAM 2025-09-10): explainable market entries — ICE-Pact Arctic cutter builders (Canadian/Finnish yards) newly registering US entities.
- **Severance Security Services LLC** and **Critical Response Strategies, LLC** (UAC family): not present in the local SAM extract at all (snapshot ends ~2026-02) — registration recency cannot be ruled in or out locally; API lookup deferred (10 req/day cap).
- **Compass United** (TX entity since 2000, SAM 2022): zero federal prime history before the window under this UEI — consistent with wave-3's BCFS/ORR-linked reading; $2.34B ceiling sum, $8.9M obligated.

## 6. S5 — NAICS drift (best-effort)

Coverage: 277 top-slice vendors with a pre-window transaction NAICS sample (earliest-100 transactions per vendor); 81 differ from their DHS-window modal NAICS at the 2-digit sector level. Honest limits: modal-of-earliest-sample is a coarse proxy; vendors without pre-window history have no drift measure by construction (they appear in S4 instead).

| vendor | window obligations | DHS NAICS | historical modal | SAM primary | sector change |
|---|---:|---|---|---|---|
| AMI METALS, INC | $1,474,828,686 | 541614 | 331491 | 423510 | 1 |
| CSI AVIATION, INC | $1,393,809,472 | 561599 | 481211 | 481211 | 1 |
| COCHRANE USA INC | $641,277,600 | 236220 | 336999 | 332618 | 1 |
| DELL FEDERAL SYSTEMS L.P | $458,679,771 | 511210 | 334111 | 334111 | 1 |
| TRIBALCO LLC | $402,150,303 | 334220 | 541519 | 541519 | 1 |
| GENERAL ATOMICS AERONAUTICAL SYSTEMS, IN | $379,480,177 | 488190 | 334290 | 336411 | 1 |
| FOUR POINTS TECHNOLOGY, L.L.C. | $311,633,852 | 541519 | 334111 | 541519 | 1 |
| LEIDOS, INC. | $266,543,185 | 334517 | 443120 | 541715 | 1 |
| MVM, INC. | $215,583,888 | 561612 | 541930 | 561612 | 1 |
| GULFSTREAM AEROSPACE CORPORATION | $182,303,171 | 532411 | 336413 | 336411 | 1 |
| BOWMAN CONSULTING GROUP LTD | $176,677,500 | 541191 | 561210 | 541330 | 1 |
| SMITHS DETECTION INC. | $174,800,695 | 532490 | 334513 | 334519 | 1 |
| BOOZ ALLEN HAMILTON INC | $174,695,776 | 541330 | 611430 | 541512 | 1 |
| LEIDOS, INC. | $150,827,934 | 541512 | 332722 | 541715 | 1 |
| LOYAL SOURCE GOVERNMENT SERVICES LLC | $150,208,461 | 561320 | 622110 | 621111 | 1 |

## 7. S6 — Concentration

Top-10 recipients by window obligations (full table incl. top-200: `s6-concentration.csv`; ceilings summed without double-counting task orders under in-census parents):

| recipient | window obligations | not-competed share (extent-code basis) |
|---|---:|---:|
| FISHER SAND & GRAVEL CO | $14,281,092,256 | 0.0 |
| BARNARD CONSTRUCTION COMPANY, INCORPORATED | $4,543,151,504 | 0.0 |
| BCCG A JOINT VENTURE | $3,248,042,851 | 0.0 |
| SLS FEDERAL SERVICES LLC | $2,379,100,930 | 0.0 |
| SPENCER CONSTRUCTION LLC | $2,359,541,157 | 0.0 |
| SOUTHWEST VALLEY CONSTRUCTORS CO | $2,243,969,041 | 0.0 |
| AMI METALS, INC | $1,474,828,686 | 0.0 |
| CSI AVIATION, INC | $1,393,809,472 | 0.0 |
| BOLLINGER SHIPYARDS LOCKPORT, L.L.C. | $1,333,453,559 | 0.9474 |
| RAUMA MARINE CONSTRUCTIONS OY | $1,122,648,775 | 1.0 |

- **Fisher Sand & Gravel: $14.28B window obligations (18.6% of ALL DHS window dollars)** across 17 awards — the census's single-vendor concentration story. Its orders are coded extent D (competed after exclusion) so its not-competed share reads 0.0; the competition reality is the 11-offer urgency family plus order-level fair opportunity.
- Top-10 by ceiling: AVANTUS FEDERAL LLC $22,228,764,734; ARDENT MANAGEMENT CONSULTING,  $22,221,320,392; PERATON INC. $22,019,401,098; PPT SOLUTIONS, LLC $22,003,241,666; LOGISTICS SYSTEMS INCORPORATED $22,002,004,598 ...
- DHS-wide not-competed dollar share 13.0%. Office outliers (>=2x baseline and >=$10M): `s6-office-outliers.csv` — USCG HQ Contract Operations 65.9% ($3.51B; Arctic cutters), USCG Aviation Logistics Center 61.8%, **OPO 'OSAD ACQ OFFICE 3' 100.0% not-competed ($463.6M in 5 actions — all one contract, see below)**, USCG SILC-CON 64.8%, USCG CEU Honolulu 91.9%.
- **Daedalus Aviation Corporation 70QS0326C00005002 (UNCONFIRMED interpretation)**: sole-source, URGENCY, via OSAD (DHS's selective/sensitive-acquisitions office), PSC **1510 = fixed-wing AIRCRAFT purchase**, NAICS 481219, description 'supply commercial aviation in support of the United States Immigration...'. Base 2025-11-21 $139.9M; single action 2026-03-24 +$303.2M; **$463.6M obligated = 100% of ceiling in 4 months**. Buying aircraft for immigration operations through the classified-acquisitions office is structurally unusual on every axis this census measures.
- Removal-aviation build-up across THREE offices (UNCONFIRMED as a coordinated program): CSI Aviation $1.394B (ICE), Salus CSRO $697.7M (OPO), Daedalus $463.6M (OSAD) — combined ~$2.55B in window.

## 8. Ranked TOP-20 anomalies

Ranked by dollar exposure x structural oddity relative to S1 base rates. Obligations and ceilings labeled separately throughout.

| # | anomaly | exposure (labeled) | screens | why anomalous vs base rates | next verification step |
|---|---|---|---|---|---|
| 1 | Fisher IDIQ 70B01C26D00000012 obligations 2.54x recorded ceiling | OBL $12.675B vs CEIL $5.0B (recorded) | S3+S6 | child orders exceed parent's stamped ceiling; ceiling never raised in FPDS | pull full FPDS mod history via query_fpds.py REF_IDV_PIID + PIID; locate ceiling-raise mod or J&A; if absent, this is a reportable records-integrity failure on the largest wall vehicle |
| 2 | CBP wall family-1: 11 IDIQs, blank solicitation id, 2025-10-31 | OBL $25.8B family child orders; CEIL $56.6B recorded | S2(manual)+S1 | 11 offers -> 11 awards (everyone won) under URGENCY, extent D; invisible to solicitation grouping | FPDS records for D00000003-13; the urgency J&A(s); SAM.gov solicitation trail (why blank?) |
| 3 | URGENCY authority carries 38% of all DHS window dollars | OBL $29.2B on 138 awards | S1 | FAR 6.302-2 as the operating mode of a multi-year construction program | harvest the J&A documents (SAM.gov) for the top urgency awards; test 'unusual and compelling urgency' against multi-year repetition |
| 4 | Daedalus Aviation: sole-source aircraft purchase via OSAD by a 2024-formed DE corp with zero federal history | OBL $463.6M = 100% of CEIL, 4 months | S6+S1+S4 | extent C, 1 offer (sol 70QS0326R00000009), URGENCY, PSC 1510 fixed-wing aircraft for immigration ops through the sensitive-acquisitions office; entity start 2024-02-21 | corporate registry + FAA aircraft registry trace on UEI KE7ZAT98UBM7; FPDS workflow fields (query_fpds.py); the J&A |
| 5 | Salus Worldwide: 2023-formed WY corp with zero federal history wins $915M removal-flights IDIQ; order grows 18.2x | OBL $697.7M on order 70RDA225FR0000018 / vehicle CEIL $915M | S3+S4 | E.O.-Section-4(a)-justified CSRO program, URGENCY + extent D, 4 offers; $30M start grown by 23 mods in 12 months | WY registry + beneficial owners; who were the other 3 offerors; per-flight economics vs CSI Aviation |
| 5b | Safe America Media LLC: DE LLC formed 17 days after inauguration takes the border ad campaign | OBL $142.8M / CEIL $382.8M | S4+S1 | 'National Emergency at the Southern Border: Stronger Borders' campaign orders under URGENCY, extent D, 3-offer media IDIQ 70RDA225D00000004; zero federal history; entity start 2025-02-06 | DE registry + agency-of-record trace; who are the other 2 IDIQ holders; ad-spend reconciliation vs public reporting |
| 6 | TSA SPP coordinated ceiling raises to identical $3.3B | CEIL $3.3B x ~8 vendors (capacity) | S3 | entire privatized-screening pool re-ceilinged 6.6-16.5x in coordinated mods | pull the SPP mods' award notices; check TSA budget justification for screening-privatization expansion |
| 7 | CBP design-build family-2: $100B new ceiling capacity | CEIL $10B x 10 IDIQs; OBL minimum guarantees only | S3+S2 | created 2026-05-11 full-and-open (22 offers/10 awards); purpose language generic 'CBP projects' | watch first task orders; obtain the solicitation 70B01C26R00000007 scope docs |
| 8 | TSA guard MAIDIQ 21/21 everyone-won | CEIL ~$5.3B shared; OBL $75K | S2 | same shape as UAC 18/18 at bigger headcount, weeks after it | corroborate offer count from solicitation record, not award stamps (same caveat as UAC) |
| 9 | UAC 18/18 family (wave-3, revalidated exactly) + Savvy Professor LLC | CEIL $20.584B; OBL $86.82M; Savvy Professor holds $1.596B of that ceiling | S2+S3+S4 | reproduced to the cent; capacity 0.4% used; S4 adds: UAC member 'Savvy Professor LLC' (VA 2024, SAM-registered 2026-02-05) has zero prior federal history | VA registry on Savvy Professor; extend the wave-3 UAC cohort workup with the S4 columns for all 18 |
| 10 | Detention letter-contract churn (GEO/CoreCivic 70CDCR25D0000000[7-10]) | CEIL swings +8.4x/+6.0x and -$421.9M; OBL flowing | S3 | undefinitized instruments repricing both directions within months | definitization records; compare priced vs letter values; link to wave-3 Delaney Hall thread |
| 11 | CSI Aviation ICE Air expansion | OBL $1.394B window; order ceiling x4.9 to $585.5M | S3+S6 | removal-flight incumbent scaling inside existing order | flight-ops data cross-check (witness lists ICE Air Ops); per-hour pricing vs Salus/Daedalus |
| 12 | Fisher order F00000017 50x order-level growth | OBL $2.83B == CEIL, from $55.8M start | S3 | 'added construction work' mods converted a $56M order into a $2.8B one | mod-by-mod scope language; was added work within scope (CICA)? |
| 13 | Fisher single-vendor concentration | OBL $14.28B = 18.6% of DHS window dollars | S6 | politically connected vendor (Trump-1 wall litigation history) takes largest DHS share | beneficial-ownership + political-giving join (next pass); GAO/DoD-IG prior findings context |
| 14 | Sep-2025 / Dec-2025 / Mar-2026 obligation spikes | OBL $12.1B / $8.1B / $11.9B months | S1 timeline | year-end + wall order waves + Arctic cutters; Oct-Nov 2025 shutdown halves action counts | none — context row for other screens |
| 15 | Arctic cutter sole-sourcing to foreign-linked yards | OBL Bollinger $1.33B (94.7% nc), Rauma $1.12B (100% nc), Davie $777M definitization | S6+S1 | ICE-Pact policy-driven; letter contracts definitized at scale | explainable-but-watch: definitization deltas; Davie letter-contract terms |
| 16 | USCG HQ office 65.9% not-competed on $5.33B | OBL $3.51B not-competed | S6 | office-level outlier 5x DHS baseline | decompose: cutters explain most; residual after removing 9321-prefix contracts |
| 17 | OPO audit-pool 5/5 (Deloitte/EY/KPMG/Guidehouse/Kearney) | CEIL ~$100M shared; OBL $32.9M (Kearney $30.2M) | S2 | benign-class everyone-won; useful as the control case | none |
| 18 | FEMA dual-award logistics pairs (CEVA/Crowley/Matson/DeWitt) | CEIL $1.08B + $469M + $237M sums | S2 | 2/2 everyone-won x3 solicitations | low priority; verify offers from solicitations |
| 19 | SLS Federal Services: $2.38B obligated, zero pre-election federal history under this UEI, + only family-1 member with a recorded ceiling raise | OBL $2.38B; CEIL $5.0B -> $6.636B 2026-03-15 | S3+S4 | plausibly the SLSCO/Sullivan wall-incumbent family under a new entity (TX 2020) — naming-structure artifact vs true newcomer needs registry trace; contrast: Fisher's ceiling never raised at 2.54x usage | TX registry ownership trace; the raise mod's justification |
| 20 | 57 families where awardees > recorded offers | n/a | S2 | offer-stamp semantics break family analysis (per-order stamps) | data-quality note for all future S2 passes; use solicitation records not award stamps |

### Explicit negative results (stated plainly)

- The DHS-wide one-bid dollar rate (24-27% of known) means one-offer awards are NOT inherently anomalous; wave-3's GEO-cohort rate is typical.
- No everyone-won family beyond those listed reaches $1B exposure; most of the 38 are 2-awardee logistics/parts pools or benign professional-services pools.
- Border-wall vendors show 0.0 'not-competed' shares on the extent-code basis — the S1 headline lives in the urgency-authority field, not the extent field; neither field alone supports a 'no-bid' claim about the wall program (11 offers are recorded).
- Zero duplicate transactions across the two download windows; the boundary split introduced no artifacts.
- Fisher, Barnard, SWVC, Granite, Sundt, Cochrane, AMI Metals and most other wall vendors have long pre-2025 federal histories (S4 negative on them); the new-entrant pattern concentrates in aviation/removal services, media, UAC, and new JV shells.
- S5 drift is mostly benign product-vs-service NAICS variance (e.g., Dell, Gulfstream). One notable miscode: AMI Metals' $1.47B bulk-steel contract is coded NAICS 541614 (logistics consulting) against a 331491 rolled-steel history — a records error on a mega-award, not a scheme signal by itself.

## 9. Data-quality caveats

- **FPDS reporting lag (quantified)**: max action_date in pull = 2026-07-26; last-30-day action count 4,513 vs trailing-3-month average ~4,254/mo -> no visible collapse, but individual actions may post up to 90 days late, so June-July dollars are a floor. Max last_modified in data = 2026-07-26 23:04 UTC (pull is current to the day).
- **Oct-Nov 2025 trough is real-world, not lag**: action counts halve (2,099/2,303 vs ~4,600 norm) during the government shutdown.
- **USASpending refresh cadence**: nightly from FPDS-NG; the bulk download reflects the previous FPDS day.
- **Subaward invisibility**: prime-only census; FSRS pull is a next-pass hook. Wave-3 already showed reported_subaward_count=0 has no discriminating power.
- **IGSA invisibility**: ICE detention via intergovernmental service agreements does not appear in FPDS at all; ICE window obligations here ($8.93B) understate detention economics.
- **Offer counts are self-stamped per award record** (UAC caveat generalizes); 18.7% of window dollars carry no offer count.
- **Extent-competed code D** ('full and open after exclusion of sources') buckets as 'competed' in the FPDS convention; the entire urgency wall program rides in that bucket. Read S1 with S1's OTFO table, never alone.
- **Ceiling fields**: parent-IDV `potential_total_value_of_award` is unreliable for family capacity (shared-ceiling stamping: TSA $5.3B x21, EAGLE II $22B legacy stamps; per-member for UAC). Anomaly #1 shows the reverse failure (ceiling not maintained upward).
- census-transactions.csv ceiling_before/after are exact only within an award's in-window ledger; pre-window ceiling baseline derives from cumulative-minus-delta on the first in-window action (verified semantics).
- Two same-day duplicate-looking IDV rows for family-2 members (2026-05-11 + Jul re-stamps) are distinct FPDS actions (mods), not load dupes (dedupe key = contract_transaction_unique_key; 0 collisions).

## 10. Out-of-scope next-pass hooks (with identifiers)

- **SAM.gov J&A harvest** targets (solicitation_ids / PIIDs): urgency family-1 IDVs 70B01C26D00000003-13 (no solicitation id — search by PIID); 70B01C26R00000007 (design-build); 70QS0326C00005002 (Daedalus); 70RDA225FR0000018 + parent 70RDA225D00000005 (Salus); 70T05025R5900N002 (TSA guard); HSTS05-15-R-SPP047 + HSTS0516DSPP906-913 (SPP raises); 70CDCR26R00000015 (UAC, already tracked); 26-SOL-DCR-01 (skip).
- **FSRS subaward pull** top-slice UEIs: XAVBDA4D13N7 (Fisher), LEGGW1TNMVC9 (Barnard), VLDKT27H2AG1 (SLS), MKMNZ369ZB59 (Spencer), W31DQKBPJCD3 (SWVC), KE7ZAT98UBM7 (Daedalus), EA4VD72SB1W3 (Salus), plus s4-new-entrants.csv flagged set.
- **County IGSA records**: ICE detention counties (not in FPDS).
- **Political-network joins**: Fisher Sand & Gravel (Tommy Fisher), Spencer Construction, Daedalus, Salus beneficial owners -> FEC/state contributions.

## 11. NEEDS ORCHESTRATOR

- **DB writes wanted** (I made none): leads for top-20 anomalies (esp. #1, #2, #4, #5, #6); findings for the canonical revalidation (citable: this census independently reproduces wave-3 numbers from a fresh bulk pull); source_reliability note for the USASpending bulk-file column-swap bug.
- **User decisions**: whether Fisher/wall program becomes its own investigation profile vs tech-right thread; whether to spend HigherGov quota on vehicle/teaming data for Daedalus/Salus (10K records/month cap).
- **Paid/gated**: OpenCorporates dead (per wave-3) — manual registry lookups for Daedalus Aviation Corporation, Salus Worldwide Solutions Corp, Spencer Construction LLC, AMI Metals; DE/VA/OH/MO registries behind CAPTCHA (user).
- **SAM_API_KEY tier**: 10 req/day basic tier blocks J&A/entity API harvest at scale; request SAM role (1K/day) or schedule drip.
- Wave-3 asks answered by this census: ICE-wide multiple-award-family baseline (S2: 362 families, 38 everyone-won), DHS-wide one-bid rate (26.7% of known dollars), newcomer base rate context (S4), 561611 comparator possible from census.db on demand.

## Artifact inventory

`census-awards.csv` (16,722 awards), `census-transactions.csv` (41,400 ledger rows), `census.db` (full 83,240-txn universe + award table), `recon.json`, `canonical-validation.json`, `screens-summary.json`, `s1-competition-by-component.csv`, `s1-competition-by-month.csv`, `s1-offers-distribution.csv`, `s1-otfo-authorities.csv`, `s2-families.csv`, `s3-ceiling-flags.csv`, `s4-new-entrants.csv`, `s5-naics-drift.csv`, `s6-concentration.csv`, `s6-office-outliers.csv`, `enrich_state.json`, raw zips + extracted CSVs under `raw/`, scripts (`probe_bulk.py`, `submit_full.py`, `poll_download.py`, `build_census.py`, `run_screens.py`, `enrich_s4_s5.py`, `validate_canonical.py`, `assemble_report.py`), `state.json`/`full_jobs.json`/`hedge_jobs.json` (job provenance).
