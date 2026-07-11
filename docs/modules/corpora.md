# Document Corpora

Tools for searching document collections, email archives, entity databases, and PDF ingestion pipelines.

**When to read this module:** When running /deep-investigate (Agent A), /search-all-sources, /pursue-lead, or performing any full-text search across investigation documents.

## Tool Inventory

| Tool | Scope | Storage | Auth | Size |
|------|-------|---------|------|------|
| `ingest_kabasshouse.py` | **PRIMARY — most complete Epstein corpus** — DOJ DS1-12 + FBI + House, fully OCR'd + structured | Local SQLite (FTS5) | None | 1.42M docs, 10.6M entities, 49.7K txns |
| `query_doj.py` | DOJ Vol 11 OCR'd pages (FALLBACK — strict subset of kabasshouse) | Local SQLite (FTS5) | None | 331K pages |
| `query_lmsband.py` | LMSBAND Epstein Files (text overlaps kabasshouse; unique structured financials) | Local SQLite (FTS5) | None | 60K files, 851K entities |
| `query_unified.py` | Unified DB (emails + docs + entities) | Local SQLite (FTS5) | None | 70K docs, 56K entities |
| `query_documentcloud.py` | DocumentCloud journalism archive | Remote API | None (public) | Millions of docs |
| `query_muckrock.py` | MuckRock FOIA requests | Remote API | None (public) | 114K+ requests |
| `query_investigations.py` | Ingested investigation PDF reports | Local SQLite (FTS5) | None | Varies |
| `ingest_pdf.py` | PDF text extraction pipeline | Local SQLite (FTS5) | None | N/A (ingestion) |
| `ingest_epstein_20k.py` | House Oversight 20K docs | Local SQLite (FTS5) | None | 25.8K docs |
| `ingest_fbi_files.py` | FBI release + named exhibits (Flight Log, Contact Book) | Local SQLite (FTS5) | None | 8,150 docs |
| `ingest_epstein_exposed.py` | EpsteinExposed.com corpus | Remote API + Local DB | None | 1.5M docs, 1.2K persons |

**NOTE:** The first four tools are investigation-specific corpora (configured per investigation profile). DocumentCloud and MuckRock are general-purpose. The `ingest_epstein_*` tools are Epstein-investigation-specific.

## Subcommands & Examples

### ingest_kabasshouse.py -- Most complete Epstein corpus (kabasshouse/epstein-data)

**Preferred first stop for Epstein full-text search.** 1,424,673 OCR'd documents spanning
DOJ DataSets 1-12 + FBI Vault + House Oversight, plus structured layers the other corpora
lack: 10.6M named entities, 49,770 credit-card/bank/flight transactions, 5,766 expert-curated
"gold" docs, communication/investigative records. Adds ~790K text-searchable EFTA pages we
never had (mostly the full DataSet 10 & 11), ~3x the LMSBAND coverage.

```bash
uv run python tools/ingest_kabasshouse.py download            # pull ~1.3GB parquet from HF
uv run python tools/ingest_kabasshouse.py ingest              # build SQLite + FTS5 (~6GB DB)
uv run python tools/ingest_kabasshouse.py search "wexner trust" --limit 20 --output "$WORKDIR/kabass-wexner.json"
uv run python tools/ingest_kabasshouse.py search "loan" --dataset DataSet10 --min-chars 200 --output "$WORKDIR/kabass-loan.json"
uv run python tools/ingest_kabasshouse.py doc EFTA01369264 --full     # all pages of a file_key
uv run python tools/ingest_kabasshouse.py financials --cardholder Epstein --merchant "Bank of America"
uv run python tools/ingest_kabasshouse.py entity "Wexner"             # entity-name aggregation
uv run python tools/ingest_kabasshouse.py curated --subject hoffman   # gold docs by subject
uv run python tools/ingest_kabasshouse.py stats
uv run python tools/ingest_kabasshouse.py overlap                     # EFTA coverage vs LMSBAND
```

DB path: `datasets/kabasshouse_epstein.db` | Source parquet: `datasets/kabasshouse/`

**Deliberately skipped configs:** `embeddings_chunk` (11.6GB of 768-dim vectors, no vector-search
use here) and `chunks` (1.2GB, redundant with `documents.full_text`). Re-add to `CONFIGS` if a
semantic-search need arises.

**OVERLAP CAVEAT:** this re-OCRs the SAME primary DOJ/FBI/House releases held in the other
corpora. A shared EFTA `file_key` is the same page re-extracted (often higher quality), NOT
independent corroboration. The genuinely new value is (a) ~790K newly-OCR'd pages and (b) the
financial/entity/curated structured layers. Provenance quirk: each HF config dir ships TWO export
generations (`<cfg>-N-of-M.parquet` canonical + a bare id-less `<cfg>-N.parquet`); we ingest only
the `-of-` shards to avoid double-counting.

### query_doj.py -- DOJ Vol 11

**FALLBACK only.** Every DOJ Vol 11 EFTA page is present in kabasshouse (verified 99.5%+ on
cited ids) at equal-or-better OCR quality. Use for cross-checking a specific extraction, not
as a primary search target. Note the DB lives at an external path outside this repo.

```bash
uv run python tools/query_doj.py search "churkin ambassador" --limit 20 --context 200
uv run python tools/query_doj.py efta EFTA02663759               # Get document by bates ID
uv run python tools/query_doj.py efta EFTA02663759 --text         # Include full OCR text
uv run python tools/query_doj.py count "rod-larsen"               # Count matching documents
uv run python tools/query_doj.py names EFTA02663759               # Extracted names from doc
```

DB path: `/Users/travcole/projects/epstein-docs/output/documents.db`

### query_lmsband.py -- LMSBAND Epstein Files

```bash
uv run python tools/query_lmsband.py search "rod-larsen" --limit 20
uv run python tools/query_lmsband.py search "rod-larsen" --dataset 3    # Filter by dataset 1-12
uv run python tools/query_lmsband.py entities "Rod-Larsen" --min-count 3
uv run python tools/query_lmsband.py cooccurrence "Rod-Larsen" --top 20
uv run python tools/query_lmsband.py file 12345                         # Get file details + text
uv run python tools/query_lmsband.py stats
```

DB path: `datasets/lmsband_epstein_files.db`

### query_unified.py -- Unified DB

**NOTE:** Uses subcommands `emails`, `docs`, `entities`, `triples`, `cooccurrence`, `stats` -- NOT "search".

```bash
uv run python tools/query_unified.py emails "rod-larsen" --limit 20     # FTS email search
uv run python tools/query_unified.py docs "gates foundation" --limit 20 # FTS document search
uv run python tools/query_unified.py entities "Rod-Larsen" --limit 30   # Entity name search
uv run python tools/query_unified.py triples --actor "Epstein" --target "Gates"
uv run python tools/query_unified.py triples --topic "finance" --limit 30
uv run python tools/query_unified.py cooccurrence "Rod-Larsen" --top 20
uv run python tools/query_unified.py stats
```

Triples require at least one filter: `--actor`, `--action`, `--target`, or `--topic`.

DB path: `datasets/unified_epstein.db`

### query_documentcloud.py -- DocumentCloud

```bash
uv run python tools/query_documentcloud.py search "Jeffrey Epstein" --limit 20
uv run python tools/query_documentcloud.py search "Maxwell" --project 216915
uv run python tools/query_documentcloud.py project                        # Epstein project (216915)
uv run python tools/query_documentcloud.py project 216915
uv run python tools/query_documentcloud.py document 24466257
uv run python tools/query_documentcloud.py document 24466257 --full       # Full metadata
uv run python tools/query_documentcloud.py text 24466257                  # Full document text
uv run python tools/query_documentcloud.py text 24466257 --page 5         # Single page text
uv run python tools/query_documentcloud.py download 24466257              # Download PDF
uv run python tools/query_documentcloud.py download 24466257 --dir /tmp/pdfs
```

**Auth:** None required for public documents. Rate limit: 0.5s between paginated requests.

### query_muckrock.py -- MuckRock FOIA

```bash
uv run python tools/query_muckrock.py project                           # Default project
uv run python tools/query_muckrock.py project 507                       # Epstein project
uv run python tools/query_muckrock.py request 12345                     # FOIA request detail
uv run python tools/query_muckrock.py download 12345 --dir datasets/muckrock
uv run python tools/query_muckrock.py search epstein
uv run python tools/query_muckrock.py agencies "Federal Bureau"
```

**Auth:** None required for public read. Rate limit: 1 req/sec.

### query_investigations.py -- Ingested Reports

```bash
uv run python tools/query_investigations.py search "BCCI" --limit 20
uv run python tools/query_investigations.py search "Deutsche Bank" --category enforcement
uv run python tools/query_investigations.py list                         # All ingested docs
uv run python tools/query_investigations.py read 3 --pages 5-10         # Read pages from doc
uv run python tools/query_investigations.py stats
```

Categories: `congressional`, `enforcement`, `court_order`, `intelligence`, `forensic`, `regulatory`, `legislative`, `academic`, `other`.

### ingest_pdf.py -- PDF Ingestion Pipeline

```bash
uv run python tools/ingest_pdf.py ingest report.pdf --title "Senate Banking Report" \
    --source "GPO" --category congressional --year 1992
uv run python tools/ingest_pdf.py ingest-dir datasets/investigation_reports/
uv run python tools/ingest_pdf.py list
uv run python tools/ingest_pdf.py read 3 --pages 5-10
uv run python tools/ingest_pdf.py stats
```

Requires `pymupdf` (`uv pip install pymupdf`). Use `--force` to re-ingest duplicates.

### ingest_epstein_20k.py -- House Oversight 20K

```bash
uv run python tools/ingest_epstein_20k.py download     # From HuggingFace (teyler/epstein-files-20k)
uv run python tools/ingest_epstein_20k.py ingest
uv run python tools/ingest_epstein_20k.py search "Jeffrey Epstein" --limit 20 --output "$WORKDIR/epstein20k.json"
uv run python tools/ingest_epstein_20k.py doc HOUSE_OVERSIGHT_020367
uv run python tools/ingest_epstein_20k.py stats
uv run python tools/ingest_epstein_20k.py overlap       # Check overlap with DOJ Vol 11
```

IDs use `HOUSE_OVERSIGHT_XXXXXX` format (distinct from DOJ Vol 11 EFTA IDs).

### ingest_epstein_exposed.py -- EpsteinExposed.com

```bash
uv run python tools/ingest_epstein_exposed.py download         # Download persons + connections
uv run python tools/ingest_epstein_exposed.py ingest           # Parse into investigation.db
uv run python tools/ingest_epstein_exposed.py search "query"   # Cross-type search (docs + emails)
uv run python tools/ingest_epstein_exposed.py persons           # List all persons
uv run python tools/ingest_epstein_exposed.py persons --category business
uv run python tools/ingest_epstein_exposed.py person "bill-gates"
uv run python tools/ingest_epstein_exposed.py documents "epstein wexner" --source doj
uv run python tools/ingest_epstein_exposed.py flights --passenger "clinton" --year 2002
uv run python tools/ingest_epstein_exposed.py match-entities   # Cross-ref with investigation.db
uv run python tools/ingest_epstein_exposed.py stats
```

Person categories: `politician`, `business`, `royalty`, `celebrity`, `associate`, `legal`, `academic`, `socialite`, `military-intelligence`, `other`.
Rate limits: 60 req/min (standard), 30 req/min (search).

## Auth Requirements Summary

| Tool | Auth | Env Variable |
|------|------|-------------|
| `ingest_kabasshouse.py` | None (HuggingFace public, CC-BY-4.0) | -- |
| `query_doj.py` | None (local DB) | -- |
| `query_lmsband.py` | None (local DB) | -- |
| `query_unified.py` | None (local DB) | -- |
| `query_documentcloud.py` | None | -- |
| `query_muckrock.py` | None | -- |
| `query_investigations.py` | None (local DB) | -- |
| `ingest_pdf.py` | None (local) | -- |
| `ingest_epstein_20k.py` | None (HuggingFace public) | -- |
| `ingest_epstein_exposed.py` | None (public API) | -- |

## Known Quirks

- **query_unified.py has no `search` subcommand.** Use `emails` or `docs` instead. A bare `search` call will print help and exit.
- **query_lmsband.py FTS5 fallback.** If the FTS index is missing, it falls back to LIKE search (much slower). Run `ingest` to rebuild the index.
- **MuckRock `search=` and `project=` params are broken.** The API's filter params on `/foia/` return all 114K results unfiltered. For project listing, fetch project detail to get request IDs, then fetch individually. Use `tags=` for filtering, which works correctly.
- **DugganUSA (`duggan_search.py`) was RETIRED 2026-06-29** — the `analytics.dugganusa.com` endpoint went permanently HTTP 403 (server-side access revoked). All 12 DOJ datasets it indexed remain reachable via DOJ Vol 11 / LMSBAND / Unified. `duggan` survives only as a historical source name on 42 existing findings.
- **ingest_epstein_20k.py uses CSV ingestion** with large field sizes. The `csv.field_size_limit` is set to `sys.maxsize`.
- **3 sources returning the same document is redundancy, not corroboration.** DOJ, LMSBAND, and Unified DB overlap heavily. Cross-check with independent primary sources.
- **All local tools use `--output FILE` for session isolation.** Use `WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)` and write all output there.

## Skills That Use These Tools

- `/deep-investigate` (Agent A -- Document Corpus Search)
- `/search-all-sources` (fans out across all corpora)
- `/pursue-lead` (searches relevant corpora based on lead type)
