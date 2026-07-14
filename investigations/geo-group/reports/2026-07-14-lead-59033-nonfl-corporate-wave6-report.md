# GEO Group non-Florida corporate political contributions — bounded wave 6

## Outcome

This wave produced 15 verified Georgia recipient-level records from the official PeachFile campaign-finance API: 13 strict GEO corporate/PCA payer rows totaling $31,000 across 2024–2025, plus two PAC-labelled payer rows totaling $2,500 that PeachFile classified as Corporation / Business / Unregistered Committee. Those two rows remain separate and are not eligible for strict corporate aggregation.

The recovered Georgia records are partial against GEO's unaudited company aggregates. They leave coverage differences of $72,500 for 2024 and $38,800 for 2025 under the strict classification. These differences are not treated as errors. Arizona's official interface resolved GEO business entities but did not return usable transaction data; the remaining non-Florida jurisdictions were not queried in this bounded wave and are explicitly frozen as gaps, not zeroes.

## Georgia reconciliation

| Year | GEO company corporate total | Strict primary rows | Strict primary sum | PAC-label ambiguity | Inclusive primary sum | Strict coverage difference |
|---:|---:|---:|---:|---:|---:|---:|
| 2024 | $77,500 | 1 | $5,000 | $0 | $5,000 | $72,500 |
| 2025 | $64,800 | 12 | $26,000 | $2,500 across 2 rows | $28,500 | $38,800 |
| Total | $142,300 | 13 | $31,000 | $2,500 across 2 rows | $33,500 | $111,300 |

If the two PAC-labelled/business-classified rows were included, the 2025 coverage difference would be $36,300. They are not included in the strict corporate result because the payer strings themselves contain PAC.

The company denominators come from GEO's 2024 and 2025 Political Activity and Lobbying Reports. They are unaudited aggregates. PeachFile recipient types are source-reported filer types and do not necessarily reproduce GEO's own candidate-versus-committee categorization.

## Primary extraction boundary

Georgia current system: the public PeachFile API was queried for transaction type TCON, source type TBSN, broad source name GEO, and dates January 1, 2024 through December 31, 2025. All 2,483 returned items across 25 pages were reviewed using exact GEO-name/address filtering. The complete retrieval is now preserved as 25 page-level JSON archives under investigations/geo-group/sources/2026-07-14-lead-59033/nonfl-wave6/. Those files preserve every JSON value from the combined retrieval and reconstruct each request with its correct pageNumber; they are not represented as byte-for-byte raw HTTP response bodies. The durable manifest embeds the 15 selected source records and a file-by-file SHA-256 inventory. Geotoll, Inc. and Georgia/George lexical matches were excluded.

Georgia legacy system: the official contributor search for THE GEO GROUP was exhaustively paged through 17 pages and 164 rows. All 17 original HTML responses and the derived 164-row parse are preserved in the same source archive. No returned row was dated 2024 or 2025. Because this appears to sit across a portal transition, that is a coverage limitation, not a substantive zero.

Arizona: official autocomplete resolved The Geo Group, Inc. business IDs 1963397, 885514, and 883862. The advanced/entity transaction endpoints returned empty datasets even for known PAC records. The autocomplete, advanced-search, six entity-query responses, and advanced-search page response are preserved and hashed in the source archive. Four official recipient PDFs recovered only GEO PAC rows. No corporate row is asserted for Arizona.

## Jurisdiction-year gap table

| Jurisdiction | Years | GEO company corporate denominator | Wave 6 status |
|---|---|---:|---|
| AZ | 2024–2025 | $70,000; $111,000 | Portal endpoint blocked; no corporate rows recovered; not a zero |
| GA | 2024–2025 | $77,500; $64,800 | Verified partial primary recovery |
| CO | 2024 | $35,000 | Not queried |
| IL | 2024–2025 | $2,200; $6,500 | Not queried |
| IN | 2024–2025 | $45,000; $39,000 | Not queried |
| NY | 2024 | $12,000 | Not queried |
| OK | 2024–2025 | $75,000; $45,000 | Not queried |
| CA | 2025 | $1,000 | Not queried |
| NJ | 2025 | $2,000 | Not queried |
| VA | 2024 | $10,000 | Not queried; denominator inherited from lead-owner reconciliation |
| PA | 2025 | $0 corporate | Not queried; company report shows GEO PAC, not corporate |
| TX | 2024 | $0 corporate | Not queried; company report shows GEO PAC, not corporate |

## Merge guidance

Use event_date, jurisdiction_code, exact_payer_legal_name_as_filed, payer_class, recipient_name_as_filed, recipient_type, amount, transaction/report/GUID identifiers, source URL/quote, and aggregation_eligible from the CSV. Party and office are blank because PeachFile did not source-report them. Do not collapse the two Friends of Jon Burns rows: they have distinct transaction IDs, GUIDs, amounts, and election types.

Files:

- Ledger: 2026-07-14-lead-59033-nonfl-corporate-wave6-ledger.csv
- Manifest with source records and query coverage: 2026-07-14-lead-59033-nonfl-corporate-wave6-manifest.json
- Company source PDFs: investigations/geo-group/sources/2026-07-14-lead-59033/
- Full Georgia and Arizona source archive: investigations/geo-group/sources/2026-07-14-lead-59033/nonfl-wave6/
- Source archive hash inventory: investigations/geo-group/sources/2026-07-14-lead-59033/nonfl-wave6/archive-index.json
