# Financial Data Catalog

As of: 2026-02-19  
Workspace: `/Users/travcole/projects/osint-research`

## Scope

This catalog inventories:

1. Financial datasets currently integrated into product artifacts.
2. Financial datasets available locally but not fully productized.
3. Filing/document types represented in financial evidence.
4. Completeness and data quality constraints that affect interpretation.

## Quality Rubric

- `High`: Primary-source, structured, and key analysis fields are mostly populated.
- `Medium`: Strong signal but meaningful gaps in provenance, entity resolution, or verification.
- `Low`: Mostly conceptual or narrative scaffolding, not comprehensive ledger-grade data.

## A) Integrated Financial Data (Current Product Surface)

| Dataset | Source + Filing/Doc Types | Storage | Coverage | Completeness Snapshot | Quality |
|---|---|---|---|---|---|
| DS10 transactions (raw) | DOJ EFTA corpus, parsed transaction rows | `datasets/lmsband_epstein_files.db` `ds10_transactions` | 724 rows, 261 distinct EFTA IDs, `2013-08-12` to `2020-01-13` | amount/date: `724/724`; sender: `580/724` (80.1%); receiver: `413/724` (57.0%); both counterparties: `357/724` (49.3%); one side missing: `279/724` (38.5%); both missing: `88/724` (12.2%); duplicate `(efta_id, tx_date, amount)` groups: 152 (312 rows) | `Medium-High` |
| DS10 balances (raw) | DOJ EFTA account statements | `datasets/lmsband_epstein_files.db` `ds10_balances` | 590 rows, 86 holders, `2013-07-01` to `2019-05-31` | holder populated: `550/590` (93.2%); date/balance: `590/590` | `High` |
| DS10 positions (raw) | DOJ EFTA position snapshots | `datasets/lmsband_epstein_files.db` `ds10_positions` | 39 rows, 4 entities, `2018-12-31` to `2019-02-28` | entity/investment/date/value: `39/39` | `Medium` (narrow timespan) |
| DS10 financial export | Filtered DS10 flow graph for UI | `site/content/financials/ds10-flows.json` | 67 nodes, 63 links, 50 top transactions, 4 balance entities / 78 points | top tx sender: `35/50` (70.0%); receiver: `36/50` (72.0%); reference: `21/50` (42.0%); EFTA ID: `50/50`; export filter retains `304/724` rows after counterparty/self/internal filters and `73/724` rows (10.1%) after `>= $50k` threshold | `Medium` |
| Apollo flow model | Curated flow model + linked findings | `site/content/financials/apollo-pipeline.json` | 8 nodes, 7 links, 114 findings | dated findings: `110/114` (96.5%); confidence populated: `114/114`; link values are curated constants, not exhaustive transaction ledger | `Medium` |
| Wexner architecture model | Curated structure/trust model | `site/content/financials/wexner-architecture.json` | 8 nodes, 7 links | labeled links: `7/7`; amount links: `3/7`; structural unit-value links (`value=1`): `4/7` | `Low-Medium` (conceptual scaffold) |
| Financial findings + evidence | Cross-source financial claims | `investigation.db` `findings`, `finding_evidence` | 1,133 findings, 2,229 evidence links | with date: `914/1133` (80.7%); with detail: `169/1133` (14.9%); with source_datasets: `53/1133` (4.7%); verified: `14/1133` (1.2%); evidence with source_quote: `997/2229` (44.7%); evidence with source_page: `0/2229` | `Medium` |
| Financial connections + evidence | Relationship graph edges | `investigation.db` `connections`, `connection_evidence` | 552 financial edges, 580 evidence links | with date_range: `71/552` (12.9%); with description: `459/552` (83.2%); verified: `0/552`; connection evidence quote/page currently `0/580` each | `Medium-Low` |
| IRS 990 tracked ingest | IRS 990 XML for tracked EINs | `investigation.db` `irs990_filings`, `irs990_grants`, `irs990_related_orgs` | 87 filings, 243 grants, 0 related-org rows | return types: 990PF (44), 990 (39), 990EZ (4); Schedule I: `27/87` (31.0%); grants recipient name: `243/243`; recipient EIN: `1/243` (0.4%); purpose: `241/243` (99.2%); cash grants total: 96,323,358 | `Medium-Low` for network inference, `Medium` for grant-level facts |
| FARA corpus | FARA bulk filings/docs | `investigation.db` `fara_documents`, `fara_short_forms` | 151,036 documents, 44,314 short forms | documents with type/date/url: `151,036/151,036`; short forms with state: `43,504/44,314` (98.2%); top doc types: Short-Form (42,846), Supplemental Statement (40,942) | `High` structural ingest, `Medium` direct financial signal |

## B) Filing and Source-Type Inventory

| Source Family | Filing/Doc Types in Dataset | Integration State | Completeness + Constraints |
|---|---|---|---|
| DOJ EFTA / LMSBAND | Wire/transfer records, account statements, positions | Integrated into DS10 raw + DS10 export + evidence graph | Strong for amount/date, weaker for counterparties and dedupe; dominant evidence base for financial findings |
| IRS 990 | 990, 990PF, 990EZ; Schedule I grants; Schedule R related orgs | Focused tracked subset integrated; national bulk DB query-capable | Grant purpose coverage is high, recipient EIN coverage low-to-medium; related-org names absent in current bulk table |
| FinCEN Files | SAR transaction map + bank connection map | Query-capable local CSV datasets | Transactions: 4,507; key fields mostly complete (begin/end date `4501/4507`, tx count `4396/4507`) |
| SEC EDGAR | 10-K, 8-K, DEF 14A, Forms 3/4/5, etc. | Query wrapper/evidence refs; not deeply materialized in financial pages | High-value primary corporate filings, but current integration is sparse and mostly reference-level |
| FEC | Campaign finance contribution records (including Schedule A in API workflows) | Query wrapper/evidence refs; not deeply materialized in financial pages | Useful contextual financial signal, currently ancillary to flow views |
| NYC ACRIS | Deeds, mortgages, liens, related property docs | Query wrapper/evidence refs; not deeply materialized | High-value for property-linked financial analysis; limited productized views today |
| FARA | Registration statements, supplemental statements, short forms, informational materials, amendments | Ingested and queryable in `investigation.db`; selectively used in findings | Strong structural completeness; financial relevance depends on downstream extraction/labeling |
| Court records | SDNY/USVI/case filings and references | Used in evidence-level linkage | High evidentiary value, but structured extraction is inconsistent across records |
| Corporate registries | Delaware, UK Companies House, OpenCorporates variants | Present in evidence refs and some dossier entities | High entity-structure value; currently uneven normalization in evidence refs |

## C) Financial Evidence Mix (Current State)

Heuristic bucket classification over financial `finding_evidence` rows (`n=2,229`):

| Bucket | Distinct Findings | Evidence Links |
|---|---:|---:|
| DOJ EFTA docs | 715 | 1,529 |
| IRS 990 refs | 65 | 112 |
| FEC refs | 71 | 101 |
| SEC / EDGAR refs | 81 | 85 |
| NYC ACRIS refs | 14 | 33 |
| OffshoreAlert refs | 30 | 30 |
| Court filings (CourtListener refs) | 5 | 6 |
| Corporate registry refs | 3 | 3 |
| Other/uncategorized refs | 200 | 330 |

Implications:

- The current financial evidence base is EFTA-heavy.
- Non-EFTA sources are present but fragmented across heterogeneous `evidence_ref` formats.
- Page-level citation anchoring remains weak (`source_page` currently empty for financial evidence).

## D) Query-Capable High-Volume Datasets (Not Fully Productized)

| Dataset | Scale | Key Completeness Metrics | Quality Notes |
|---|---|---|---|
| IRS 990 bulk grants DB (`datasets/irs990_grants.db`) | 4,744,145 filings; 22,676,368 grants; 314,815 related-org rows; 221,142 distinct filers | grants: recipient name `21,760,527/22,676,368` (96.0%), recipient EIN `6,777,205/22,676,368` (29.9%), purpose `21,566,181/22,676,368` (95.1%); Schedule I on filings `1,305,285/4,744,145` (27.5%); Schedule R `94,909/4,744,145` (2.0%); related EIN `258,564/314,815` (82.1%); related_name `0/314,815` | Very high analytical potential; main blocker is entity-resolution and related-org normalization quality |
| FinCEN Files (`datasets/fincen_files/*.csv`) | 4,507 transaction rows; 5,498 connection rows; 1,508 unique SAR IDs combined | transactions: begin/end date present `4,501/4,507` each (99.9%), number_transactions `4,396/4,507` (97.5%), key counterparty/bank fields complete; connections core fields complete `5,498/5,498` | Strong directional signal for suspicious flow patterns; interpret as SAR-linked intelligence rather than complete ledger history |

## E) Data Quality Risks and Gaps

1. Verification bottleneck: only `14/1,133` financial findings are marked verified.
2. Provenance metadata sparsity: `source_datasets` is populated for only `53/1,133` findings.
3. Citation anchoring gap: `source_page` is empty in financial evidence, limiting auditability.
4. DS10 counterparties gap: only `49.3%` of transactions have both sender and receiver populated.
5. DS10 dedupe/canonicalization gap: duplicate signatures and OCR variants inflate ambiguity.
6. IRS 990 entity-resolution gap: recipient EIN coverage is weak, related-org names absent in bulk table.
7. Model-vs-ledger ambiguity: curated Apollo/Wexner flows are useful scaffolds but not exhaustive transaction maps.

## F) Recommended Next Steps

1. Add a reproducible metrics script (SQLite + JSON checks) that regenerates this catalog on each data refresh.
2. Enforce controlled vocabularies for `source_datasets` and `evidence_ref` prefixes.
3. Require `source_quote` and `source_page` for new financial evidence inserts.
4. Add DS10 canonicalization/dedupe before `site/pipeline/export_financials.py`.
5. Split UI semantics into explicit modes: `model edges`, `ledger-backed edges`, and `inferred edges`.
