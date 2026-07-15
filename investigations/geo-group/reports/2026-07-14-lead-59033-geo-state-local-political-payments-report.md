# GEO state/local political-payment ledger and reconciliation

**Lead:** #59033  
**Profile/thread:** `geo-group` / 112  
**Coverage:** January 1, 2015 through July 14, 2026  
**Priority comparison:** calendar 2024 and 2025  
**Analysis runs:** systemic-analysis #101; timeline-analysis #102

## Bottom line

The durable ledger contains **1,958 primary-source rows**: **1,161** recipient-side records from the Florida Division of Elections, **782** payer-side GEO PAC Schedule B state/nonfederal political-payment records, and a bounded **15-row** Georgia recipient-side slice from the official PeachFile API. The legal streams are kept separate. Across Florida and Georgia, **1,106** rows are conservatively classified as GEO-family corporate legal entities. Florida also contains **68** rows carrying an explicit PAC/Political Action Committee label; 22 match payer-side FEC records with high confidence and are counted only once through the FEC row. Georgia adds two payer strings containing `PAC` that PeachFile classified as business/unregistered-committee transactions; those **$2,500** of rows are preserved but excluded from the strict corporate aggregate.

The main 2025 PAC result reconciles cleanly under a gross-positive convention: GEO reported **$61,500** of state/local GEO PAC contributions, and Schedule B shows **$61,500** of positive payments in the same three reported jurisdictions—Arizona **$43,000**, Oklahoma **$17,500**, and Pennsylvania **$1,000**. Schedule B signed net is **$56,000** because it also contains four negative void/adjustment entries totaling **$5,500**. This establishes the gross-positive convention for the 2025 company PAC table; it does not prove that every company table or year uses one uniform convention.

Florida does not fully reconcile to the company aggregate. For 2024, the conservative corporate class has **119 rows / $601,500**, compared with the company's **$564,500** Florida corporate total, a **-$37,000 company-minus-state difference**. For 2025, **122 rows / $1,646,000** compare with the company's **$1,922,600**, a **+$276,600 company-minus-state residual**. These are reconciliation differences, not findings that either source made an error. Period cutoffs, amendments absent from the export, statewide/multicounty versus county/municipal filing scope, payer-alias coverage, and GEO's internal candidate/committee category definitions remain unresolved.

The timing crosswalk places the Florida payments next to official state immigration-policy dates and exact-matched ICE procurement actions. It establishes simultaneity and named-recipient relationships only. The reviewed records do not establish a request, communication, procurement decision, official intervention, or causal link between a contribution and an ICE action.

## Sources and denominator

### Florida recipient-side records

The official Division of Elections export exposes clean tab-separated fields for `Candidate/Committee`, `Date`, `Amount`, transaction `Typ`, exact `Contributor Name`, address, city/state/ZIP, occupation, and in-kind description. The search covered eight aliases: `THE GEO GROUP`, `GEO CARE`, `GEO PAC`, `GEO CORRECTIONS`, `GEO REENTRY`, `GEO SECURE`, `GEO ACQUISITION`, and `B.I. INCORPORATED`. Four searches returned rows. A separate address/ZIP search for 4955 Technology Way / 33431 did not identify another GEO legal name.

The export does **not** provide report number, amendment number, check number, or a stable state transaction ID. It does expose `REF` and `INK` types; the only negative Florida row is a **-$1,681.25** October 30, 2023 refund from `THE GEO GROUP INC` to `Panhandle United (PAC)`. Exact-row multiplicity is therefore flagged but not collapsed.

The state search covers statewide and multicounty filers. County and municipal filing offices are outside the export. That is a possible coverage explanation, not an allocation of the residual.

### GEO PAC payer-side records

The FEC input contains all 1,559 C00382150 Schedule B disbursement rows returned for 2015–2026. The political-payment ledger selects 782 `Other Disbursements` to COM, PTY, CCM, or ORG recipients and excludes three California Secretary of State registration-fee/void rows, including two misspelled `SECRETARY OR STATE`. Each FEC row preserves transaction ID, `sub_id`, filing number, image number, amendment indicator, description, recipient state, and document-image URL.

These rows are nonfederal/state payment reporting by the payer. They are not independent corroboration when a state recipient filing describes the same check.

### Georgia recipient-side records

The bounded non-Florida wave archived 25 PeachFile JSON pages containing all **2,483** values returned by the combined retrieval, 17 legacy-search HTML pages, parsed legacy rows, and nine Arizona diagnostics. Exact name/address filtering produced **15** Georgia rows for 2024–2025. Thirteen strict corporate/PCA rows total **$31,000**; two PAC-labelled payer rows total **$2,500** and remain aggregation-ineligible. Every merged quote equals the `exact_quote` embedded with its selected source record in the revised wave manifest. The archive reconstructs the correct page-number requests and preserves the returned JSON values; it is not represented as byte-for-byte raw HTTP response bodies.

### Company aggregates

The official company reports' state/local table headers are `Type | GEO PAC | Corporate`. The Florida values sit in the Corporate column and the Florida GEO PAC column is blank in both years. The reports also state that they are unaudited company disclosures. Their state/local totals are:

| Calendar year | Corporate | GEO PAC | Combined state/local |
|---|---:|---:|---:|
| 2024 | $891,200 | $78,500 | $969,700 |
| 2025 | $2,191,900 | $61,500 | $2,253,400 |

## Florida exact-payer classification

The ledger preserves the filed string and applies a conservative alias decision:

- `THE GEO GROUP...`, `GEO CARE...`, `GEO ACQUISITION...`, or `GEO REENTRY...` without a PAC/SSF label is corporate.
- `POLITICAL CONTRIBUTION ACCOUNT`, `POLITICAL CONTRIBUTIONS ACCT`, `POLITICAL CONTRIBUTING ACCOUNT`, and `PCA` remain corporate political-contribution-account labels. They are not treated as the employee-funded PAC. This is also consistent with GEO's blank Florida GEO PAC column in 2024 and 2025.
- `PAC` or `POLITICAL ACTION COMMITTEE` is a PAC/SSF-label class and is excluded from Florida aggregate totals to avoid double counting with Schedule B.
- No Florida row in these alias results was classified as an individual/officer or unrelated payer.

The resulting Florida source rows by class are:

| Year | Corporate-class rows | Corporate signed net | PAC-label rows | PAC-label signed net |
|---|---:|---:|---:|---:|
| 2015 | 13 | $263,000.00 | 4 | $16,500.00 |
| 2016 | 123 | $786,309.94 | 25 | $167,000.00 |
| 2017 | 97 | $938,000.00 | 9 | $18,000.00 |
| 2018 | 107 | $1,332,000.00 | 5 | $5,000.00 |
| 2019 | 122 | $963,500.00 | 6 | $153,000.00 |
| 2020 | 104 | $631,000.00 | 7 | $411,000.00 |
| 2021 | 38 | $197,500.00 | 3 | $155,000.00 |
| 2022 | 95 | $1,028,500.00 | 3 | $5,000.00 |
| 2023 | 120 | $670,818.75 | 4 | $5,500.00 |
| 2024 | 119 | $601,500.00 | 1 | $5,000.00 |
| 2025 | 122 | $1,646,000.00 | 0 | $0.00 |
| 2026 through July 14 | 33 | $1,181,500.00 | 1 | $15,000.00 |

These historical Florida totals are source-row totals, not company-reconciled annual totals.

## 2024–2025 Florida reconciliation

| Measure | 2024 | 2025 |
|---|---:|---:|
| Florida corporate-class rows | 119 | 122 |
| Gross positive | $601,500 | $1,646,000 |
| Negative adjustments/refunds | $0 | $0 |
| Signed net | $601,500 | $1,646,000 |
| GEO reported Florida Corporate | $564,500 | $1,922,600 |
| Company minus state gross/signed | **-$37,000** | **+$276,600** |

The raw state output originally totals $606,500 in 2024 only if the one **$5,000** `THE GEO GROUP INC PAC ACCOUNT` row is mixed into the corporate denominator. The ledger does not do that. The 2025 source has no PAC-label row.

Exact multiplicity cannot be adjudicated from the export. A sensitivity that keeps only the first occurrence of each exact-row group removes two corporate rows / **$7,500** in 2024 and two / **$15,000** in 2025. It yields $594,000 and $1,631,000, respectively. Those are hypothetical bounds, not asserted corrected totals.

The company's candidate/committee subcategories cannot be reproduced from the state suffix alone. The Florida export's direct candidate-name rows total **$52,000** in 2024 and **$43,000** in 2025, while GEO's Candidate column reports $522,500 and $1,007,600. Candidate-associated committees such as `Friends of ... (PAC)` appear to require a broader internal category rule, but the reports do not publish that rule. This category mismatch is another reason not to force row-level reconciliation.

Largest 2025 corporate-class recipient aggregates in the official state export were:

| Recipient as filed | Rows | Amount |
|---|---:|---:|
| Friends of Byron Donalds PAC (PAC) | 1 | $500,000 |
| Quiet Professionals FL (PAC) | 2 | $252,500 |
| Florida Republican Senatorial Campaign C (PAP) | 3 | $205,000 |
| Republican Party of Florida (PTY) | 2 | $200,000 |
| Friends of James Uthmeier (PAC) | 2 | $50,000 |
| Honest Leadership (PAC) | 3 | $40,000 |

Party is source-reported only for direct candidate rows containing `(REP)`, `(DEM)`, or `(NOP)`. Values such as `REP_name_based` are explicit name-based inferences from strings such as `Republican Party of Florida`; they are not source-reported party fields.

## GEO PAC reconciliation

### 2025: exact gross-positive match

| Jurisdiction | Company GEO PAC | FEC gross positive | Negative adjustments | FEC signed net |
|---|---:|---:|---:|---:|
| Arizona | $43,000 | $43,000 | -$3,000 | $40,000 |
| Oklahoma | $17,500 | $17,500 | -$2,500 | $15,000 |
| Pennsylvania | $1,000 | $1,000 | $0 | $1,000 |
| **Total** | **$61,500** | **$61,500** | **-$5,500** | **$56,000** |

The negative entries are later void/adjustment records preserved in Schedule B. GEO's 2025 jurisdiction table therefore matches positive payments, not signed net.

### 2024: no single convention fully reconciles

| Jurisdiction | Company GEO PAC | FEC gross positive | Negative adjustments | FEC signed net |
|---|---:|---:|---:|---:|
| Arizona | $56,000 | $58,000 | -$2,000 | $56,000 |
| Oklahoma | $12,500 | $7,500 | -$2,000 | $5,500 |
| Texas | $10,000 | $10,000 | -$500 | $9,500 |
| **Total** | **$78,500** | **$75,500** | **-$4,500** | **$71,000** |

Arizona matches signed net; Texas matches gross positive; Oklahoma remains $5,000 above gross positive. The source record does not justify choosing one convention to eliminate the remaining difference.

## Recipient, policy, and ICE timing crosswalk

The official Florida record shows a **$20,000** February 18, 2025 payment to `Friends of Ben Albritton (PAC)`. The Florida Senate identifies Ben Albritton as Senate President. An official January 27 legislature document issued under Albritton and the House Speaker proposed the TRUMP Act and described coordination with President Trump's immigration orders and local law enforcement. The contribution was 22 days later. This establishes recipient identity and timing; it does not establish a request, favorable act, procurement role, or causation.

The state record also shows $25,000 to `Friends of James Uthmeier (PAC)` on February 28, another $25,000 on September 30, and a direct $3,000 candidate-name row on September 30. The official Attorney General bio says Uthmeier was appointed in February 2025. The cited records establish office identity and timing only.

The December 30 state record reports $500,000 to `Friends of Byron Donalds PAC (PAC)`. Donalds' official House page identifies him as Florida's 19th District representative. That official bio does not establish a Florida detention-procurement role.

Monthly Florida corporate-class totals and exact-matched GEO ICE action totals show both overlap and non-overlap:

| Month | Florida corporate payments | Broward ICE net action obligations | All GEO ICE net action obligations | Policy marker |
|---|---:|---:|---:|---|
| Jan. 2025 | $0 | $6,777,267 | $43,662,143.28 | Jan. 27 Florida TRUMP Act proposal |
| Feb. 2025 | $382,500 | $2,790,904 | $91,611,946.50 | Feb. 19 additional Florida/ICE 287(g) agreements |
| May 2025 | $0 | $7,733,800 | $81,255,571.72 | May 12 state detention-capacity proposal |
| July 2025 | $2,500 | $0 | $31,721,279.26 | July 4 Public Law 119-21 |
| Aug. 2025 | $0 | $8,772,350 | $65,684,098.58 | — |
| Sept. 2025 | $422,500 | $6,458,711.58 | $206,730,750.11 | — |
| Dec. 2025 | $592,000 | $0 | $39,103,490 | — |

The crosswalk uses federal action obligations, not invoices, outlays, occupied beds, or recognized GEO revenue. Florida recipients are state candidates/committees, while ICE procurement actions are federal decisions. The absence of contribution dollars in several large procurement months and the absence of Broward actions in the largest contribution month are counterevidence to a simple same-month payment/procurement explanation. Internal communications, contribution requests, meeting records, or procurement-intervention evidence would be needed to test a causal mechanism.

## Coverage gaps and non-Florida status

Georgia is now partially resolved at recipient level:

| Year | GEO Georgia Corporate | Strict primary rows | Strict sum | PAC-label/business ambiguity | Company-minus-strict coverage difference |
|---:|---:|---:|---:|---:|---:|
| 2024 | $77,500 | 1 | $5,000 | $0 | $72,500 |
| 2025 | $64,800 | 12 | $26,000 | $2,500 across 2 excluded rows | $38,800 |

These are partial-coverage differences, not findings that either source erred. The two PAC-labelled rows would reduce the inclusive 2025 difference to $36,300, but they are not included in the strict corporate result.

The Arizona official interface resolved GEO business entities but returned no usable transaction data through the tested advanced/entity endpoints, even for combinations visible in official recipient PDFs. Four 2024 PDFs corroborate GEO PAC rows only. Arizona is therefore **blocked, not zero**; papercut #973 records the endpoint/index failure.

Colorado, Illinois, Indiana, New York, Oklahoma, California, New Jersey, and Virginia were not queried in the bounded non-Florida wave. Pennsylvania 2025 and Texas 2024 have zero company **corporate** denominators but their portals were not queried; the company reports instead show GEO PAC amounts there. Every unqueried jurisdiction remains an explicit gap in the revised non-Florida manifest and a residual in the main reconciliation rather than an invented zero.

## Novelty and ACH decision

No ACH or database hypothesis was created. The evidence spans multiple independent contexts—company disclosure, state recipient records, FEC payer filings, official office/policy records, and USAspending actions—but it does not identify a distinct causal mechanism. The strongest new results are reconciliation mechanics and bounded timing facts. A coordination or intent hypothesis would require evidence of a request, communication, decision path, or intervention that is currently absent. The null explanation—ordinary political giving plus independently timed policy and procurement activity—remains fully compatible with the record.

## Durable outputs

- `2026-07-14-lead-59033-geo-state-local-political-ledger.csv` — 1,958 source rows with exact payer/recipient names, party/type labels, amendments/voids, IDs, quotes, aliases, and dedup notes.
- `2026-07-14-lead-59033-geo-state-local-reconciliation.json` — 2024/2025 company-versus-primary gross, adjustments, signed net, residuals, and duplicate sensitivity.
- `2026-07-14-lead-59033-geo-state-local-finding-support.json` — compact, quoteable reconciliation blocks supporting every numerical database synthesis.
- `2026-07-14-lead-59033-geo-state-fec-pac-crosswalk.csv` — 22 high-confidence payer/recipient-source matches.
- `2026-07-14-lead-59033-geo-florida-ice-timing-crosswalk.csv` — monthly Florida payments, Broward/all-GEO ICE actions, and official policy markers.
- `2026-07-14-lead-59033-geo-recipient-office-policy-crosswalk.csv` — selected recipient identity/office relationships with explicit no-causation status.
- `2026-07-14-lead-59033-geo-state-local-quote-audit.csv` — source quote/hash coverage for every ledger row.
- `2026-07-14-lead-59033-geo-state-local-manifest.json` — source/output hashes, counts, exclusions, and warnings.
- `2026-07-14-lead-59033-nonfl-corporate-wave6-{ledger.csv,manifest.json,report.md}` — bounded Georgia extraction, all selected source records, explicit gap table, and archived-source crosswalk.
- `2026-07-14-lead-59033-finding-{12935,12936,12937,12938}-provenance.json` — exact post-verification database snapshots hashed by the main manifest.
- `scripts/build_geo_state_local_political_ledger.py` — deterministic offline rebuild.

Accepted database findings are **#12935–#12938**. The manifest enumerates every retracted audit draft so they cannot be mistaken for accepted evidence.

Primary source links: [Florida campaign-finance search](https://dos.elections.myflorida.com/campaign-finance/contributions/), [FEC GEO PAC disbursements](https://www.fec.gov/data/disbursements/?committee_id=C00382150), [GEO 2024 report](https://www.geogroup.com/media/tufn44mo/geo-political-activity-and-lobbying-report-_2024_.pdf), [GEO 2025 report](https://www.geogroup.com/geo-2025-political-activity-and-lobbying-report/), [Florida Senate President](https://www.flsenate.gov/Offices/President), [January 27 TRUMP Act document](https://www.flsenate.gov/PublishedContent/Offices/2024-2026/President/Documents/TRUMP_Act.pdf), [Florida Attorney General bio](https://legacy.myfloridalegal.com/pages.nsf/Main/1515CE372E59D1E885256CC60071B1C4), [Byron Donalds official bio](https://donalds.house.gov/about/), and [Public Law 119-21 text](https://www.congress.gov/bill/119th-congress/house-bill/1/text).
