# Document Corpora

Tools for searching document collections, email archives, entity databases, and PDF ingestion pipelines.

**When to read this module:** When running /deep-investigate (Agent A), /search-all-sources, /pursue-lead, or performing any full-text search across investigation documents.

## Tool Inventory

| Tool | Scope | Storage | Auth | Size |
|------|-------|---------|------|------|
| `query_doj.py` | DOJ Vol 11 OCR'd pages | Local SQLite (FTS5) | None | 331K pages |
| `query_lmsband.py` | LMSBAND Epstein Files | Local SQLite (FTS5) | None | 60K files, 851K entities |
| `query_unified.py` | Unified DB (emails + docs + entities) | Local SQLite (FTS5) | None | 70K docs, 56K entities |
| `duggan_search.py` | DugganUSA API (all 12 DOJ datasets) | Remote API | DUGGANUSA_API_KEY | 329K+ docs |
| `query_documentcloud.py` | DocumentCloud journalism archive | Remote API | None (public) | Millions of docs |
| `query_muckrock.py` | MuckRock FOIA requests | Remote API | None (public) | 114K+ requests |
| `query_investigations.py` | Ingested investigation PDF reports | Local SQLite (FTS5) | None | Varies |
| `ingest_pdf.py` | PDF text extraction pipeline | Local SQLite (FTS5) | None | N/A (ingestion) |
| `ingest_epstein_20k.py` | House Oversight 20K docs | Local SQLite (FTS5) | None | 25.8K docs |
| `ingest_epstein_exposed.py` | EpsteinExposed.com corpus | Remote API + Local DB | None | 1.5M docs, 1.2K persons |

**NOTE:** The first four tools are investigation-specific corpora (configured per investigation profile). DocumentCloud and MuckRock are general-purpose. The `ingest_epstein_*` tools are Epstein-investigation-specific.

## Subcommands & Examples

### query_doj.py -- DOJ Vol 11

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

### duggan_search.py -- DugganUSA API

```bash
uv run python tools/duggan_search.py "JPMorgan" -n 20
uv run python tools/duggan_search.py "JPMorgan" --all --limit 200    # Paginate up to 200
uv run python tools/duggan_search.py "JPMorgan" --content             # Show full content
uv run python tools/duggan_search.py "JPMorgan" --output /tmp/results.json
```

**Auth:** Requires `DUGGANUSA_API_KEY` in `.env`. Register at https://epstein.dugganusa.com/register.html

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
uv run python tools/ingest_epstein_20k.py search "Jeffrey Epstein" --limit 20
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
| `query_doj.py` | None (local DB) | -- |
| `query_lmsband.py` | None (local DB) | -- |
| `query_unified.py` | None (local DB) | -- |
| `duggan_search.py` | API key required | `DUGGANUSA_API_KEY` |
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
- **duggan_search.py counts 329K+ docs** but the API wraps responses in `{"success": true, "data": {...}}`. The tool handles unwrapping automatically.
- **ingest_epstein_20k.py uses CSV ingestion** with large field sizes. The `csv.field_size_limit` is set to `sys.maxsize`.
- **3 sources returning the same document is redundancy, not corroboration.** DOJ, LMSBAND, and Unified DB overlap heavily. Cross-check with independent primary sources.
- **All local tools use `--output FILE` for session isolation.** Use `WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)` and write all output there.

## Skills That Use These Tools

- `/deep-investigate` (Agent A -- Document Corpus Search)
- `/search-all-sources` (fans out across all corpora)
- `/pursue-lead` (searches relevant corpora based on lead type)
