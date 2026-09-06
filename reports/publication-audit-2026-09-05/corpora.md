# Corpus coverage and profile evidence ledger

Core/content cutoff: 2026-09-06T01:11:55.470934+00:00

Scope: **platform-wide index review**. Every YAML investigation config and configured corpus tool is accounted for. Selected finding excerpts were read for editorial candidates, but no raw corpus received source-wide semantic review. Live sidecar metadata was observed after the core/content cutoff and is explicitly non-frozen. None of the inspected sidecar mtimes was after the cutoff at observation; this does not substitute for a frozen backup or immutable version.

- 33 actual YAML-backed profiles, plus one excluded template.
- 35 profile values occur among 15,678 frozen findings; crml has findings but no current YAML config, test has 2 findings, and a null profile has 1.
- 13 unique configured corpus tools: 11 readable local sidecars received metadata review, 2 remote APIs excluded from this local-only assessment without service-health inference.
- 22 profiles configure no corpus_tools: allbirds, altman, chesney, curaleaf, eastport-cinemas, election-integrity, elephant-clipping, feeding-our-future, geo-group, hagee, hassan-boston, hfia, manosphere, mark-walter, mike-johnson, nginx, oversight-project, parlatore, peru-lockheed, smci, tech-right, zampolli. This does not mean they lack evidence: many use public-record tools rather than a named local corpus.

| Configured tool | Profiles | Review | Key metadata | Limitation |
|---|---|---|---|---|
| tools/ingest_kabasshouse.py | brad-karp, coscoluella, epstein, epstein-gates-ipi, epstein-oslo, fink, merkin, richard-merkin | index | documents 1,424,673, entities 10,629,198, financial_transactions 49,770, curated_docs 5,766 | Metadata only; corpus record text not semantically reviewed. EFTA overlaps are one source family. |
| tools/query_unified.py | brad-karp, coscoluella, epstein, epstein-aetna, epstein-gates-ipi, epstein-oslo, fink, merkin, richard-merkin, softbank-caper | index | emails 8,316, documents 70,828, triples 107,030 | Metadata only; corpus record text not semantically reviewed. EFTA overlaps are one source family. |
| tools/query_lmsband.py | brad-karp, coscoluella, dfj-network, epstein, epstein-aetna, epstein-gates-ipi, epstein-oslo, fink, merkin, richard-merkin, softbank-caper | index | files 591,286, text_cache 591,286, entities 1,693,889 | Metadata only; corpus record text not semantically reviewed. EFTA overlaps are one source family. |
| tools/ingest_epstein_20k.py | brad-karp, coscoluella, epstein, epstein-gates-ipi, epstein-oslo, softbank-caper | index | documents 25,800 | Metadata only; corpus record text not semantically reviewed. EFTA overlaps are one source family. |
| tools/ingest_fbi_files.py | brad-karp, epstein, epstein-gates-ipi, epstein-oslo, fink, merkin, richard-merkin | index | documents 8,150 | Metadata only; corpus record text not semantically reviewed. EFTA overlaps are one source family. |
| tools/reporting_corpus.py | brad-karp, epstein, epstein-gates-ipi, epstein-oslo | index | reporting_item 7,782, item_version 9,300, reporting_claim 95 | Metadata only; corpus record text not semantically reviewed. EFTA overlaps are one source family. |
| tools/query_doj.py | coscoluella, dfj-network, epstein, epstein-aetna, softbank-caper | index | documents 331,655 | Metadata only; corpus record text not semantically reviewed. EFTA overlaps are one source family. |
| tools/ingest_epstein_exposed.py | coscoluella, epstein, epstein-oslo | index | persons 1,271, person_connections 0 | Metadata only; corpus record text not semantically reviewed. EFTA overlaps are one source family. |
| tools/government_release_corpus.py | epstein, epstein-gates-ipi, epstein-oslo | index | government_release 282,951, government_release_version 276,476 | Metadata only; corpus record text not semantically reviewed. EFTA overlaps are one source family. |
| tools/query_investigations.py | epstein-aetna, epstein-oslo | index | documents 99, pages 10,326 | Metadata only; corpus record text not semantically reviewed. EFTA overlaps are one source family. |
| tools/ingest_faa.py | epstein-aetna | index | aircraft 529,946, acft_ref 93,517 | Metadata only; corpus record text not semantically reviewed. EFTA overlaps are one source family. |
| tools/query_documentcloud.py | epstein-aetna | excluded | Remote endpoint not queried | No local sidecar configured; external source excluded from local-only opportunity assessment, not evidence of unavailable service or zero results. |
| tools/query_muckrock.py | epstein-aetna | excluded | Remote endpoint not queried | No local sidecar configured; external source excluded from local-only opportunity assessment, not evidence of unavailable service or zero results. |

## High-value forms and gaps

Kabasshouse contains 1,424,673 document records, with 6,181 distinct inherited document-type labels. 564,974 records (39.7%) have a null type. Exact labels include Bank Statement (12,511), Court Document (10,636), Court Transcript (7,087), Agreement (2,387), Invoice (1,813), KYC Print (570), Funds Transfer Request (382), and Trust Agreement (115). These are raw extraction labels, not a normalized census or proof of relevance. Case variants and other near-duplicates exist.

The 5,766 curated records are all labeled gold, while all 49,770 extracted financial transactions have null extraction_confidence. Neither label certifies factual reliability. The proper next pass is a deduplicated, provenance-bound review of selected agreements, financial statements and court records, including a sample from the large unclassified pool.

LMSBAND has 591,286 file rows, far above some profile descriptions referring to about 60,000 files. Of these, 591,155 report has_text=1; 131 report no text, including 1 marked needs_ocr. This is a metadata check, not inspection of OCR accuracy.

Reporting has 7,782 items, 9,300 versions and only 95 attributed claims. Access status is unknown for 6,723 items and unavailable for 447. Reporting is useful prior-art/index material and cannot count as independent primary corroboration.

Government releases include 268,908 complete DOJ records and 6,801 complete SEC records; 7,239 DOJ rows remain pending and 3 rows failed. An official release proves the government made the statement, while allegation/disposition language must remain intact.

The ingested investigations corpus has 99 documents/10,326 pages; 48 documents have no category. This gap should not be mistaken for lack of court or oversight material. The local EpsteinExposed sidecar is a persons cache (1,271 people and zero person_connections), not a locally complete mirror of its advertised document/flight service.

The supplementary derived sidecar contains 32,520 events, 53,100 financial transactions, 83,709 canonical-person rows, 172 entity crosswalk rows, and zero derived_fact_provenance rows. Its bulk volume cannot be promoted to reviewed evidence or canonical identity matches without provenance and identity checking.

## Frozen profile evidence counts

“Verified” is the stored status, not a current publication validation result. “With quote” means at least one nonempty stored quote, not a judgment that it supports every part of a claim.

| Profile | Findings | Marked verified | With a quote | Retracted | Disputed |
|---|---:|---:|---:|---:|---:|
| epstein | 5493 | 155 | 2502 | 18 | 18 |
| tech-right | 3303 | 306 | 252 | 4 | 4 |
| geo-group | 689 | 501 | 618 | 127 | 0 |
| softbank-caper | 576 | 6 | 91 | 14 | 0 |
| hfia | 535 | 0 | 164 | 0 | 0 |
| oversight-project | 419 | 13 | 419 | 1 | 0 |
| altman | 413 | 0 | 10 | 0 | 0 |
| zampolli | 376 | 23 | 43 | 1 | 1 |
| parlatore | 345 | 9 | 40 | 0 | 0 |
| curaleaf | 341 | 243 | 341 | 0 | 0 |
| feeding-our-future | 327 | 7 | 21 | 0 | 1 |
| manosphere | 318 | 0 | 1 | 0 | 0 |
| dfj-network | 297 | 59 | 46 | 0 | 1 |
| allbirds | 244 | 15 | 33 | 3 | 0 |
| nginx | 220 | 0 | 0 | 0 | 0 |
| brad-karp | 214 | 140 | 212 | 72 | 0 |
| epstein-gates-ipi | 202 | 36 | 145 | 0 | 1 |
| elephant-clipping | 179 | 0 | 179 | 0 | 0 |
| hassan-boston | 177 | 0 | 177 | 0 | 0 |
| epstein-aetna | 165 | 11 | 80 | 35 | 1 |
| coscoluella | 139 | 44 | 51 | 1 | 0 |
| fink | 139 | 0 | 138 | 9 | 0 |
| mark-walter | 124 | 0 | 124 | 0 | 0 |
| hagee | 96 | 0 | 10 | 0 | 0 |
| richard-merkin | 95 | 12 | 88 | 9 | 0 |
| epstein-oslo | 91 | 0 | 78 | 0 | 0 |
| merkin | 56 | 4 | 54 | 6 | 0 |
| eastport-cinemas | 36 | 0 | 36 | 0 | 0 |
| election-integrity | 18 | 0 | 14 | 0 | 0 |
| smci | 16 | 0 | 1 | 0 | 0 |
| mike-johnson | 14 | 0 | 4 | 0 | 0 |
| crml | 10 | 0 | 0 | 0 | 0 |
| chesney | 8 | 0 | 0 | 0 | 0 |
| test | 2 | 0 | 0 | 2 | 0 |
| (null) | 1 | 0 | 0 | 0 | 0 |

## Scope and privacy exclusions

DocumentCloud and MuckRock are configured remote APIs but were not queried for this local-only index pass. Their omission is an explicit acquisition gap, not a negative search. The template, test/unscoped rows and private-person asset-profile opportunities were excluded from commissioning. No operational data or content was changed.

The companion opportunities report supplies seven bounded existing-profile article/dossier angles, with primary anchors, overlap, counter-evidence and missing checks. There is no claim that a new investigation or article is publication-ready.
