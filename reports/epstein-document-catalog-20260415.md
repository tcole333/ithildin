# Epstein document catalog — 2026-04-15

A structured inventory of locally-stored Epstein-related documents, classified along three orthogonal axes: investigative origin (what proceeding produced it), document form (what kind of document), and custodian (who held it). Rule-based classification; see §9 for method.

## 1. Executive summary

- **Documents in structured corpora:** 1,050,250
- **Loose files catalogued:** 564,276

Per-corpus totals:

| Corpus | Documents | Share |
|---|---:|---:|
| lmsband | 591,286 | 56.3% |
| doj_vol11 | 331,655 | 31.6% |
| unified | 79,144 | 7.5% |
| doc_explorer | 25,232 | 2.4% |
| epstein_20k | 22,933 | 2.2% |

Top document forms (axis 2) across all corpora:

| Form | Count | Share |
|---|---:|---:|
| `unknown` | 641,080 | 61.0% |
| `email` | 365,972 | 34.8% |
| `other` | 9,332 | 0.9% |
| `media_article` | 9,176 | 0.9% |
| `forensic_kyc_report` | 7,480 | 0.7% |
| `bank_statement` | 3,344 | 0.3% |
| `transaction_wire_record` | 2,655 | 0.3% |
| `interview_proffer_transcript` | 2,295 | 0.2% |
| `exhibit` | 1,542 | 0.1% |
| `flight_log` | 1,385 | 0.1% |
| `indictment` | 1,207 | 0.1% |
| `trust_estate_document` | 940 | 0.1% |
| `doj_memo` | 925 | 0.1% |
| `motion` | 542 | 0.1% |
| `deposition_transcript` | 532 | 0.1% |

Most-populated (origin × form × custodian) triples:

| Origin | Form | Custodian | Count |
|---|---|---|---:|
| unknown | unknown | doj_main | 577,289 |
| unknown | email | doj_main | 333,574 |
| unknown | unknown | unknown | 35,662 |
| unknown | email | unknown | 26,225 |
| congressional_house_oversight | unknown | house_oversight | 24,136 |
| congressional_house_oversight | email | house_oversight | 6,114 |
| congressional_house_oversight | other | house_oversight | 5,054 |
| congressional_house_oversight | media_article | house_oversight | 4,828 |
| unknown | media_article | journalist | 4,348 |
| unknown | other | unknown | 4,265 |
| congressional_house_oversight | forensic_kyc_report | house_oversight | 3,827 |
| unknown | forensic_kyc_report | unknown | 3,579 |
| unknown | transaction_wire_record | doj_main | 2,352 |
| unknown | unknown | fbi | 1,957 |
| personal_records | flight_log | doj_main | 1,363 |

## 2. Corpus inventory


### 2.1 doj_vol11

DOJ Vol 11 OCR'd release (EFTA bates; `~/projects/epstein-docs/output/documents.db`)

- **Documents:** 331,655
- **Signal coverage:** filename 100.0%, prior category 0.0%, dataset# 0.0%, source prefix 0.0%, content sample 100.0%

Top forms in this corpus:

| Form | Count |
|---|---:|
| `email` | 319,747 |
| `unknown` | 11,732 |
| `trust_estate_document` | 47 |
| `transaction_wire_record` | 42 |
| `flight_log` | 26 |
| `deposition_transcript` | 23 |
| `forensic_kyc_report` | 15 |
| `indictment` | 11 |

### 2.2 lmsband

LMSBAND corpus — 12 DOJ datasets with entity extraction (`datasets/lmsband_epstein_files.db`)

- **Documents:** 591,286
- **Signal coverage:** filename 100.0%, prior category 0.0%, dataset# 100.0%, source prefix 0.4%, content sample 100.0%

Top forms in this corpus:

| Form | Count |
|---|---:|
| `unknown` | 569,404 |
| `email` | 13,867 |
| `transaction_wire_record` | 2,319 |
| `flight_log` | 1,355 |
| `indictment` | 1,148 |
| `bank_statement` | 796 |
| `trust_estate_document` | 595 |
| `motion` | 520 |

### 2.3 unified

Unified DB — emails + docs + entities + triples (`datasets/unified_epstein.db`)

- **Documents:** 79,144
- **Signal coverage:** filename 10.2%, prior category 100.0%, dataset# 0.0%, source prefix 100.0%, content sample 100.0%

Top forms in this corpus:

| Form | Count |
|---|---:|
| `unknown` | 35,808 |
| `email` | 26,244 |
| `media_article` | 4,348 |
| `other` | 4,265 |
| `forensic_kyc_report` | 3,579 |
| `bank_statement` | 1,359 |
| `interview_proffer_transcript` | 1,101 |
| `exhibit` | 746 |

### 2.4 epstein_20k

House Oversight 20K release (`datasets/epstein_files_20k.db`)

- **Documents:** 22,933
- **Signal coverage:** filename 100.0%, prior category 0.0%, dataset# 0.0%, source prefix 100.0%, content sample 100.0%

Top forms in this corpus:

| Form | Count |
|---|---:|
| `unknown` | 22,933 |

### 2.5 doc_explorer

Epstein Doc Explorer — LLM-categorized + RDF triples of the 20K (`datasets/Epstein-doc-explorer/document_analysis.db`)

- **Documents:** 25,232
- **Signal coverage:** filename 100.0%, prior category 100.0%, dataset# 0.0%, source prefix 0.0%, content sample 100.0%

Top forms in this corpus:

| Form | Count |
|---|---:|
| `email` | 6,114 |
| `other` | 5,054 |
| `media_article` | 4,828 |
| `forensic_kyc_report` | 3,827 |
| `unknown` | 1,203 |
| `interview_proffer_transcript` | 1,194 |
| `bank_statement` | 1,187 |
| `exhibit` | 796 |

**Known overlaps between corpora:**

- **Epstein 20K ⇄ Doc Explorer:** 21,884 shared `HOUSE_OVERSIGHT_*` IDs (Doc Explorer is an LLM-analyzed derivative of the 20K release).
- **LMSBAND dataset 9 ⇄ loose ds09_extracted:** 531,287 LMSBAND docs vs 531,360 loose files — the loose tree appears to be the raw extraction that fed LMSBAND.
- **DOJ Vol 11 ⇄ LMSBAND:** 439 filenames match (EFTA*.pdf); LMSBAND carries extraction metadata, DOJ Vol 11 carries OCR text — treat as two views of the same docs.

## 3. Cross-corpus form matrix

Where to look for each document form:

| Form | lmsband | doj_vol11 | unified | doc_explorer | epstein_20k |
|---|---:|---:|---:|---:|---:|
| `unknown` | 569,404 | 11,732 | 35,808 | 1,203 | 22,933 |
| `email` | 13,867 | 319,747 | 26,244 | 6,114 | - |
| `other` | 13 | - | 4,265 | 5,054 | - |
| `media_article` | - | - | 4,348 | 4,828 | - |
| `forensic_kyc_report` | 59 | 15 | 3,579 | 3,827 | - |
| `bank_statement` | 796 | 2 | 1,359 | 1,187 | - |
| `transaction_wire_record` | 2,319 | 42 | 294 | - | - |
| `interview_proffer_transcript` | - | - | 1,101 | 1,194 | - |
| `exhibit` | - | - | 746 | 796 | - |
| `flight_log` | 1,355 | 26 | 4 | - | - |
| `indictment` | 1,148 | 11 | 48 | - | - |
| `trust_estate_document` | 595 | 47 | 298 | - | - |
| `doj_memo` | - | - | 438 | 487 | - |
| `motion` | 520 | 3 | 16 | 3 | - |
| `deposition_transcript` | 504 | 23 | 5 | - | - |
| `letter_correspondence` | - | - | 244 | 278 | - |
| `corporate_record` | - | - | 236 | 255 | - |
| `fbi_302` | 472 | 3 | 10 | - | - |
| `tax_return_990` | 126 | 2 | 92 | - | - |
| `subpoena` | 103 | 1 | - | - | - |
| `message_pad` | 5 | 1 | 3 | - | - |
| `brief` | - | - | 4 | 4 | - |
| `fbi_memo` | - | - | 2 | 2 | - |

## 4. Origin × form matrix

What kinds of material do we have from each investigation/proceeding? Only cells with ≥1 doc are shown.


**congressional_house_oversight**

| Form | Count |
|---|---:|
| `unknown` | 24,136 |
| `email` | 6,114 |
| `other` | 5,054 |
| `media_article` | 4,828 |
| `forensic_kyc_report` | 3,827 |
| `interview_proffer_transcript` | 1,194 |
| `bank_statement` | 1,187 |
| `exhibit` | 796 |
| `doj_memo` | 487 |
| `letter_correspondence` | 278 |
| `corporate_record` | 255 |
| `brief` | 4 |
| `motion` | 3 |
| `fbi_memo` | 2 |

**grand_jury**

| Form | Count |
|---|---:|
| `unknown` | 1,264 |
| `indictment` | 210 |
| `fbi_302` | 30 |
| `motion` | 29 |
| `email` | 22 |
| `bank_statement` | 16 |
| `subpoena` | 7 |
| `transaction_wire_record` | 4 |
| `trust_estate_document` | 3 |
| `deposition_transcript` | 3 |
| `forensic_kyc_report` | 2 |

**personal_records**

| Form | Count |
|---|---:|
| `flight_log` | 1,379 |
| `subpoena` | 9 |
| `message_pad` | 9 |
| `deposition_transcript` | 7 |
| `fbi_302` | 1 |

**state_criminal_fl_2008_npa**

| Form | Count |
|---|---:|
| `unknown` | 772 |
| `indictment` | 105 |
| `motion` | 68 |
| `flight_log` | 6 |
| `email` | 5 |
| `trust_estate_document` | 2 |
| `transaction_wire_record` | 2 |
| `fbi_302` | 2 |
| `deposition_transcript` | 2 |

**unknown**

| Form | Count |
|---|---:|
| `email` | 359,831 |
| `media_article` | 4,348 |
| `other` | 4,278 |
| `forensic_kyc_report` | 3,651 |
| `transaction_wire_record` | 2,649 |
| `bank_statement` | 2,141 |
| `interview_proffer_transcript` | 1,101 |
| `trust_estate_document` | 935 |
| `indictment` | 892 |
| `exhibit` | 746 |
| `deposition_transcript` | 520 |
| `fbi_302` | 452 |
| `motion` | 442 |
| `doj_memo` | 438 |
| `letter_correspondence` | 244 |
| `corporate_record` | 236 |
| `tax_return_990` | 220 |
| `subpoena` | 88 |
| `brief` | 4 |
| `fbi_memo` | 2 |

## 5. Coverage gaps

Taxonomy types with fewer than 10 documents found — either genuinely rare in the corpus, or signals aren't strong enough for the rule-based classifier to detect them.

**Axis 2 (form) gaps (<10 docs):**

- `complaint`: 0
- `brief`: 8
- `opinion_order`: 0
- `trial_hearing_transcript`: 0
- `grand_jury_testimony`: 0
- `fbi_memo`: 4
- `search_warrant`: 0
- `affidavit`: 0
- `contact_list`: 0
- `calendar_schedule`: 0
- `message_pad`: 9
- `brokerage_statement`: 0
- `contract_agreement`: 0
- `photograph_video`: 0
- `handwritten_note`: 0
- `cover_sheet_separator`: 0

**Axis 1 (origin) gaps (<10 docs):**

- `federal_criminal_sdny`: 0
- `federal_civil_sdny`: 0
- `state_criminal_fl_2006`: 0
- `state_civil_usvi`: 0
- `civil_victim_litigation`: 0
- `civil_bank_litigation`: 0
- `congressional_senate`: 0
- `fbi_investigation`: 0
- `doj_prosecutorial`: 0
- `regulatory`: 0
- `estate_probate`: 0
- `journalism`: 0
- `corporate_internal`: 0

**Axis 3 (custodian) gaps (<10 docs):**

- `sdny_usao`: 0
- `usvi_ag`: 0
- `pb_sheriff`: 2
- `pb_state_attorney`: 0
- `senate_finance`: 0
- `senate_judiciary`: 0
- `jpmorgan`: 0
- `deutsche_bank`: 0
- `epstein_estate`: 0
- `ncd`: 0
- `maxwell_defense`: 0
- `victim_counsel`: 0
- `private_counsel`: 0
- `regulator`: 0

## 6. Confidence and low-coverage strata

Confidence distribution:

| Bucket | Count | Share |
|---|---:|---:|
| low (0-0.5) | 578,328 | 55.1% |
| medium (0.5-0.8) | 375,514 | 35.8% |
| high (>=0.8) | 61,385 | 5.8% |
| zero | 35,023 | 3.3% |

**LLM validation:** not yet run. Stage 3 (`tools/catalog_llm_sample.py`) is staged but requires `ANTHROPIC_API_KEY` in .env and `anthropic` added to `pyproject.toml`. Run after key setup to sanity-check rule output and discover missing types.

**Highest-unknown strata** (most opportunity for rule refinement):

| Corpus | axis1 | axis2 | axis3 | Count |
|---|---|---|---|---:|
| lmsband | unknown | unknown | doj_main | 565,591 |
| unified | unknown | unknown | unknown | 35,662 |
| doj_vol11 | unknown | unknown | doj_main | 11,698 |
| lmsband | unknown | unknown | fbi | 1,889 |
| unified | unknown | unknown | fbi | 65 |
| doj_vol11 | unknown | unknown | fbi | 3 |

## 7. Loose files inventory

File-level inventory of dataset directories not backed by a structured DB. Sizes in MB.

| Group | Files | Total size (MB) | Top extensions |
|---|---:|---:|---|
| **ds09_extracted** — WARC-extracted files from LMSBAND dataset 9 (heavily duplicated with lmsband corpus) | 531,360 | 96,777.2 | `pdf` (531,308), `docx` (18), `doc` (10), `xls` (7), `ppt` (5) |
| **epstein_archive** — Epstein-archive web project — curated docs (Black Book, Flight Logs, Court Exhibits) | 32,902 | 2,218.1 | `eml` (26,027), `txt` (4,704), `meta` (925), `html` (479), `jpg` (445) |
| **epstein_emails_hf** — HuggingFace email dump sources (feed Unified DB) | 5 | 1.1 | `lock` (2), `parquet` (1), `metadata` (1) |
| **standalone_root_pdfs** — Standalone EFTA PDFs at datasets/ root (overlap with DOJ Vol 11) | 5 | 128.3 | `pdf` (5) |
| **epstractor_sample** — Epstractor sample outputs | 4 | 482.0 | `parquet` (1), `metadata` (1), `lock` (1) |

## 8. EpsteinExposed person network (appendix)

EpsteinExposed.com person database — 1,271 persons (not documents).

| Category | Persons |
|---|---:|
| associate | 802 |
| business | 147 |
| celebrity | 80 |
| other | 59 |
| academic | 51 |
| politician | 48 |
| legal | 38 |
| socialite | 34 |
| royalty | 9 |
| military-intelligence | 3 |

- **Black book entries:** 0
- **Use case:** cross-reference entity mentions in the document corpora against curated person metadata (categories, aliases, short bios). Query via `uv run python tools/ingest_epstein_exposed.py persons`.

## 9. Methodology

- **Working DB:** `/tmp/osint-catalog-KyRjkc62/catalog.db` (intermediate; not committed)
- **Taxonomy:** `investigations/epstein/document_taxonomy.yaml` (3-axis: origin × form × custodian)
- **Pipeline:** `tools/catalog_epstein_docs.py` (ingest + rule-based classify), `tools/catalog_build_report.py` (this report)
- **Rule families (in precedence order):**
  1. Reuse of existing `category` fields from Unified DB and Doc Explorer
  2. LMSBAND dataset 9/10 financial-subtable and travel-subtable lookup
  3. Document-ID prefix (`HOUSE_OVERSIGHT_*`, `EFTA*`)
  4. Filename regex (302, deposition, subpoena, indictment, flight_log, etc.)
  5. Source path directory segments (`sdny/`, `usvi/`, `giuffre/`, etc.)
  6. File extension fallback (.eml → email, .jpg → photograph_video, etc.)
  7. Content keyword scan on first 2KB (FD-302, deposition of, NPA, compound email headers)

- **Not yet run:** Stage 3 LLM-sampled validation.
- **Caveats:**
  - 3 sources returning the same document is redundancy, not corroboration (see CLAUDE.md). Overlaps are noted in §2 rather than deduplicated.
  - The `email` count in DOJ Vol 11 is ~96% of the corpus because the release is largely Epstein's comms records (OCR'd scans preserving From/To/Subject headers).
  - `unknown` at axis 1 (origin) is high because most local documents were released into collections (DOJ, HouseO) without preserved provenance back to the original proceeding that generated them.
