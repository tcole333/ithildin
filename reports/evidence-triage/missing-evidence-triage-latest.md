# Missing Evidence Citation Triage

- Generated: `2026-02-19T16:17:32`
- Total missing `source_quote` rows: **3284**
- High-priority rows (`direct_quote` or `confirmed`): **919**
- DS10 missing rows: **13**
- Duggan missing rows: **18**
- Missing EFTA rows: **874**
- Missing EFTA rows absent from local docs DB: **874**

## Bucket Counts

| bucket | total | high-priority |
|---|---:|---:|
| canonical-but-missing-quote | 1708 | 580 |
| search-breadcrumb | 329 | 23 |
| malformed | 1247 | 316 |

## Top High-Priority: canonical-but-missing-quote

| finding_id | target | claim/confidence | evidence_ref | action |
|---|---|---|---|---|
| 11 | Kathy Ruemmler | direct_quote/confirmed | `EFTA01266278` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 11 | Kathy Ruemmler | direct_quote/confirmed | `EFTA01266434` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 50 | Kathy Ruemmler | direct_quote/confirmed | `EFTA00335051` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 90 | International Peace Institute | direct_quote/confirmed | `EFTA01357084` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 90 | International Peace Institute | direct_quote/confirmed | `EFTA01360128` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 90 | International Peace Institute | direct_quote/confirmed | `EFTA01362195` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 108 | Steve Bannon | direct_quote/high | `EFTA01615902` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 108 | Steve Bannon | direct_quote/high | `EFTA01615903` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 111 | Steve Bannon | direct_quote/high | `EFTA01615908` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 111 | Steve Bannon | direct_quote/high | `EFTA01615909` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 149 | Lawrence Summers | direct_quote/confirmed | `EFTA01920171` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 154 | Lawrence Summers | direct_quote/confirmed | `EFTA01919974` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 154 | Lawrence Summers | direct_quote/confirmed | `EFTA01920248` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 159 | Lawrence Summers | direct_quote/medium | `EFTA02731420` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 161 | Lawrence Summers | direct_quote/confirmed | `EFTA01930111` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 161 | Lawrence Summers | direct_quote/confirmed | `EFTA01930265` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 259 | Jeffrey Epstein | direct_quote/confirmed | `EFTA01941232` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 540 | Fortress Value Recovery Fund | direct_quote/confirmed | `EFTA01299431` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 540 | Fortress Value Recovery Fund | direct_quote/confirmed | `EFTA01300517` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 541 | Marc Rowan | direct_quote/high | `EFTA02730996` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 550 | Prytanee LLC | direct_quote/confirmed | `EFTA01386389` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 553 | Forums LLC | direct_quote/confirmed | `EFTA01340334` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 554 | Financial Ballistics Trust | direct_quote/confirmed | `EFTA01873997` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 555 | CDE Inc | direct_quote/confirmed | `EFTA01873997` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 556 | Mort Inc | direct_quote/confirmed | `EFTA01873997` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 557 | FT Real Estate Inc | direct_quote/confirmed | `EFTA01873997` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 562 | NA Property Inc | direct_quote/high | `EFTA01314734` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 570 | Financial Infomatics Inc | direct_quote/confirmed | `EFTA01298264` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 570 | Financial Infomatics Inc | direct_quote/confirmed | `EFTA01360708` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 577 | L.A.W. Plantation Management Corp | direct_quote/confirmed | `EFTA01295770` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |

## Top High-Priority: search-breadcrumb

| finding_id | target | claim/confidence | evidence_ref | action |
|---|---|---|---|---|
| 1871 | Bill Siegel | direct_quote/high | `https://api.open.fec.gov/v1/schedules/schedule_a/?contributor_name=William+D+Siegel` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 2218 | Wachtel & Masyr | direct_quote/high | `NY SoS address search 110 East 59th St` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 2253 | Xenophon Galinas | direct_quote/confirmed | `https://api.open.fec.gov/v1/schedules/schedule_a/?contributor_name=Xenophon+Galinas` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 2265 | Xenophon Galinas | direct_quote/confirmed | `DugganUSA-645Fifth-1000hits` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 2316 | Jack Abramoff | direct_quote/high | `FEC Schedule A filings via api.open.fec.gov` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 2318 | Jack Abramoff | direct_quote/high | `LDA Senate lobbying API via lda.senate.gov/api/v1` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 2413 | Isaac Dabah | direct_quote/confirmed | `FEC records (API)` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 2803 | Tom Barrack | direct_quote/confirmed | `WebSearch:PBS-Barrack-acquittal` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 3295 | Ron Soffer | synthesis/confirmed | `EDGAR EFTS API` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 3295 | Ron Soffer | synthesis/confirmed | `FARA API` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 3295 | Ron Soffer | synthesis/confirmed | `FEC API` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 3295 | Ron Soffer | synthesis/confirmed | `GLEIF API` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 3365 | Safra National Bank of New York | direct_quote/confirmed | `CourtListener docket search for Safra National Bank` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 3399 | Nan Morabia | direct_quote/confirmed | `France SIRENE registry search` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 3458 | David Petraeus | direct_quote/confirmed | `FARA search results (empty)` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 3458 | David Petraeus | direct_quote/confirmed | `LDA search results (empty)` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 3462 | Paula Broadwell | direct_quote/confirmed | `CourtListener search 'Paula Broadwell'` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 3465 | David Petraeus | direct_quote/confirmed | `CourtListener search 'Giuffre Maxwell Petraeus' (no relevant results)` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 3522 | Robert Kraft | direct_quote/confirmed | `FEC.gov campaign finance database donor search Robert Kraft` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 3524 | Robert Kraft | direct_quote/confirmed | `SEC EDGAR EFTS full-text search lookup 'Robert Kraft' - 339 total filings` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 3530 | Robert Kraft | synthesis/confirmed | `CourtListener search Rand-Whitney` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 3535 | Robert Kraft | synthesis/confirmed | `CourtListener search New England Patriots` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |
| 3605 | Noam Chomsky | paraphrase/confirmed | `Registry search, ACRIS search, EDGAR search, DS10 search, OpenSanctions search, FEC search` | Replace with concrete source IDs (EFTA/SEC/CL/etc.); move search notes into finding detail. |

## Top High-Priority: malformed

| finding_id | target | claim/confidence | evidence_ref | action |
|---|---|---|---|---|
| 29 | Gratitude America Ltd | direct_quote/confirmed | `IRS-990PF-2015` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 29 | Gratitude America Ltd | direct_quote/confirmed | `IRS-990PF-2017` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 29 | Gratitude America Ltd | direct_quote/confirmed | `IRS-990PF-2019` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 43 | Leon Black | direct_quote/high | `HF-unified:dubin-black-tax-article` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 49 | Leon Black | direct_quote/confirmed | `SEC-EDGAR:CIK-1032666` | Normalize evidence_ref to canonical token: https://www.sec.gov/edgar/search/#/q=CIK-1032666 |
| 62 | Gratitude America Ltd | direct_quote/confirmed | `IRS-990PF-2018` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 69 | International Peace Institute | direct_quote/confirmed | `datasets/IPI-KPMG-Forensic-Review-12-18-2020.pdf` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 74 | Enhanced Education | direct_quote/confirmed | `KPMG-IPI-Report-p9 KPMG-IPI-Report-p10 EFTA02713369` | Normalize evidence_ref to canonical token: EFTA02713369 |
| 792 | Ron Soffer | direct_quote/confirmed | `FEC Schedule A` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 845 | Eduardo Teodorani-Fabbri | direct_quote/confirmed | `SEC-EDGAR:SC13D-CNH-2013-10-11` | Normalize evidence_ref to canonical token: https://www.sec.gov/edgar/search/#/q=SC13D-CNH-2013-10-11 |
| 864 | Eduardo Teodorani-Fabbri | direct_quote/high | `ilgiornaleditalia.it:Teodorani-Epstein-article` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 864 | Eduardo Teodorani-Fabbri | direct_quote/high | `open.online:Teodorani-Epstein-2026-02-06` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1234 | Landon Thomas Jr. | direct_quote/confirmed | `hf_to-be:20161019094300` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1234 | Landon Thomas Jr. | direct_quote/confirmed | `hf_to-be:20161019134735` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1237 | Raafat Alsabbagh | direct_quote/confirmed | `hf_to-be:20160602102117` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1380 | Marcel Kellerhals | direct_quote/confirmed | `USVI_Registry:582110` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1414 | Reid Hoffman | direct_quote/confirmed | `CBP-2019-083151_RC` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1460 | Leon Black | direct_quote/confirmed | `SEC 8-K 000119312521016405 EX-99.1` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1491 | Leon Black | direct_quote/confirmed | `SEC 8-K 000119312521016405 EX-99.2` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1508 | Leslie Wexner | direct_quote/high | `SEC:701985:000090951805000716` | Normalize evidence_ref to canonical token: SEC:0000909518-05-000716 |
| 1510 | Leslie Wexner | direct_quote/confirmed | `SEC:901359:000090951807000835` | Normalize evidence_ref to canonical token: SEC:0000909518-07-000835 |
| 1524 | Leon Black | direct_quote/confirmed | `990-PF-EIN-66-0789697-2015` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1624 | Vincenzo Iozzo | direct_quote/high | `0001916133-22-000002` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1624 | Vincenzo Iozzo | direct_quote/high | `0001916133-25-000003` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1624 | Vincenzo Iozzo | direct_quote/high | `SEC EDGAR CIK 0001916133 Form D filings 0001916133-22-000001` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1660 | David Fiszel | direct_quote/confirmed | `FEC_FISZEL_DAVID` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1660 | David Fiszel | direct_quote/confirmed | `SEC_EDGAR_CIK_0001316313` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1660 | David Fiszel | direct_quote/confirmed | `SEC_v_Mazzola_3:12-cv-01258` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1664 | Honeycomb Asset Management LP | direct_quote/confirmed | `SEC_EDGAR_CIK_0001675688` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |
| 1664 | Honeycomb Asset Management LP | direct_quote/confirmed | `SEC_EDGAR_CIK_0001873197` | Normalize evidence_ref format; if no concrete source exists, replace with valid evidence token. |

## Top Queue (All Buckets)

| finding_id | target | claim/confidence | evidence_ref | action |
|---|---|---|---|---|
| 11 | Kathy Ruemmler | direct_quote/confirmed | `EFTA01266278` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 11 | Kathy Ruemmler | direct_quote/confirmed | `EFTA01266434` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 50 | Kathy Ruemmler | direct_quote/confirmed | `EFTA00335051` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 90 | International Peace Institute | direct_quote/confirmed | `EFTA01357084` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 90 | International Peace Institute | direct_quote/confirmed | `EFTA01360128` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 90 | International Peace Institute | direct_quote/confirmed | `EFTA01362195` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 108 | Steve Bannon | direct_quote/high | `EFTA01615902` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 108 | Steve Bannon | direct_quote/high | `EFTA01615903` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 111 | Steve Bannon | direct_quote/high | `EFTA01615908` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 111 | Steve Bannon | direct_quote/high | `EFTA01615909` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 149 | Lawrence Summers | direct_quote/confirmed | `EFTA01920171` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 154 | Lawrence Summers | direct_quote/confirmed | `EFTA01919974` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 154 | Lawrence Summers | direct_quote/confirmed | `EFTA01920248` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 159 | Lawrence Summers | direct_quote/medium | `EFTA02731420` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 161 | Lawrence Summers | direct_quote/confirmed | `EFTA01930111` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 161 | Lawrence Summers | direct_quote/confirmed | `EFTA01930265` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 259 | Jeffrey Epstein | direct_quote/confirmed | `EFTA01941232` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 540 | Fortress Value Recovery Fund | direct_quote/confirmed | `EFTA01299431` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 540 | Fortress Value Recovery Fund | direct_quote/confirmed | `EFTA01300517` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 541 | Marc Rowan | direct_quote/high | `EFTA02730996` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 550 | Prytanee LLC | direct_quote/confirmed | `EFTA01386389` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 553 | Forums LLC | direct_quote/confirmed | `EFTA01340334` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 554 | Financial Ballistics Trust | direct_quote/confirmed | `EFTA01873997` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 555 | CDE Inc | direct_quote/confirmed | `EFTA01873997` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 556 | Mort Inc | direct_quote/confirmed | `EFTA01873997` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 557 | FT Real Estate Inc | direct_quote/confirmed | `EFTA01873997` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 562 | NA Property Inc | direct_quote/high | `EFTA01314734` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 570 | Financial Infomatics Inc | direct_quote/confirmed | `EFTA01298264` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 570 | Financial Infomatics Inc | direct_quote/confirmed | `EFTA01360708` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |
| 577 | L.A.W. Plantation Management Corp | direct_quote/confirmed | `EFTA01295770` | Ingest missing EFTA document into docs DB, then rerun quote backfill. |

## Notes

- `search-breadcrumb` rows usually represent tool/search provenance rather than citable evidence items.
- `malformed` rows usually include packed refs, free-text references, or non-canonical token variants.
- `canonical-but-missing-quote` rows usually need quote extraction/backfill from the underlying source.

